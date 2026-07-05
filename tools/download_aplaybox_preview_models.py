"""Download public Aplaybox preview model packets for MMD compatibility checks."""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
from pathlib import Path
import sys
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "local_resources" / "mmd" / "aplaybox_preview"
API_ROOT = "https://api.aplaybox.com/api/web/v1/work"


@dataclass(frozen=True)
class Candidate:
    slug: str
    uuid: str
    label: str


DEFAULT_CANDIDATES = (
    Candidate("march7", "CLCDE3lCEAbR", "March 7th"),
    Candidate("keqing", "BHT8uTY9U4HV", "Keqing"),
    Candidate("ganyu", "xfyv7yIWHaxH", "Ganyu"),
    Candidate("raiden", "MxWT1GhpcLKt", "Raiden Shogun"),
)


def _headers(referer: str) -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
        "Origin": "https://details.aplaybox.com",
        "Referer": referer,
    }


def _post_json(endpoint: str, payload: dict, referer: str) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(f"{API_ROOT}/{endpoint}", data=data, headers=_headers(referer), method="POST")
    try:
        with urlopen(request, timeout=45) as response:
            raw = response.read()
    except HTTPError as exc:
        raw = exc.read()
    return json.loads(raw.decode("utf-8"))


def _quote_url_path(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, quote(parts.path), parts.query, parts.fragment))


def _download(url: str, path: Path, referer: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(_quote_url_path(url), headers={"User-Agent": "Mozilla/5.0", "Referer": referer})
    with urlopen(request, timeout=90) as response:
        data = response.read()
    path.write_bytes(data)
    return len(data)


def _result_data(response: dict) -> dict:
    return (((response.get("data") or {}).get("result") or {}).get("data") or {})


def download_candidate(candidate: Candidate, out_root: Path) -> dict:
    referer = f"https://details.aplaybox.com/modelDetails?work_uuid={candidate.uuid}"
    out_dir = out_root / candidate.slug
    out_dir.mkdir(parents=True, exist_ok=True)

    details = _post_json(
        "getWorkDetails",
        {"work_uuid": candidate.uuid, "work_type_id": 1, "user_uid": "", "is_login": 0},
        f"https://www.aplaybox.com/details/model/{candidate.uuid}",
    )
    (out_dir / "details.json").write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")

    file_json = _post_json("getWorkModelFileJson", {"work_uuid": candidate.uuid}, referer)
    (out_dir / "model_file_json.json").write_text(
        json.dumps(file_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    download_response = _post_json(
        "downloadWorkNewV2",
        {
            "work_type_id": 1,
            "work_uuid": candidate.uuid,
            "is_camera": False,
            "download_password": "",
            "ticket": "",
            "randstr": "",
        },
        f"https://www.aplaybox.com/details/model/{candidate.uuid}",
    )
    (out_dir / "original_download_response.json").write_text(
        json.dumps(download_response, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    detail_data = _result_data(details)
    file_data = _result_data(file_json)
    scene = file_data.get("work_model_file_json") or {}
    models = list(scene.get("pmxModels") or [])
    downloads = []
    for model in models:
        model_id = int(model.get("uuid") or 0)
        if model_id <= 0:
            continue
        load = _post_json(
            "getWorkModelLoadUrl",
            {"work_model_file_id": model_id, "work_uuid": candidate.uuid},
            referer,
        )
        url = _result_data(load)
        model_path = out_dir / f"{model_id}.cf.pbx.gz"
        size = _download(str(url), model_path, referer) if url else 0
        downloads.append(
            {
                "id": model_id,
                "name": model.get("name") or "",
                "url": url,
                "path": str(model_path.relative_to(ROOT)),
                "bytes": size,
            }
        )
    cover = detail_data.get("cover") or file_data.get("cover") or ""
    cover_info = None
    if cover:
        suffix = Path(urlsplit(str(cover)).path).suffix or ".jpg"
        cover_path = out_dir / f"cover{suffix}"
        cover_info = {
            "url": cover,
            "path": str(cover_path.relative_to(ROOT)),
            "bytes": _download(str(cover), cover_path, referer),
        }

    manifest = {
        "slug": candidate.slug,
        "uuid": candidate.uuid,
        "label": candidate.label,
        "work_name": detail_data.get("work_name") or "",
        "format": detail_data.get("work_format_name") or "",
        "download_permission": detail_data.get("download_permission"),
        "work_model_zip_ids": file_data.get("work_model_zip_ids") or detail_data.get("work_model_zip_ids") or "",
        "original_download_message": download_response.get("message") or ((download_response.get("data") or {}).get("message")),
        "preview_models": downloads,
        "cover": cover_info,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _parse_candidate(value: str) -> Candidate:
    parts = value.split("=", 2)
    if len(parts) == 1:
        return Candidate(parts[0], parts[0], parts[0])
    if len(parts) == 2:
        return Candidate(parts[0], parts[1], parts[0])
    return Candidate(parts[0], parts[1], parts[2])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download public Aplaybox MMD preview packets")
    parser.add_argument("--out", default=str(OUT_ROOT))
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        help="slug=uuid=label. Defaults to the curated four candidates.",
    )
    args = parser.parse_args(argv)
    out_root = Path(args.out)
    candidates = tuple(_parse_candidate(value) for value in args.candidate) if args.candidate else DEFAULT_CANDIDATES
    manifests = []
    for candidate in candidates:
        manifest = download_candidate(candidate, out_root)
        manifests.append(manifest)
        print(
            f"{candidate.slug}: {len(manifest['preview_models'])} preview packets, "
            f"original={manifest.get('original_download_message')}"
        )
    (out_root / "manifest.json").write_text(json.dumps(manifests, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
