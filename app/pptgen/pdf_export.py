"""PDF export helpers for user PPT decks."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from app.pptgen.schema import DeckSpec
from app.pptgen.writer_python_pptx import write_pptx_compatible
from app.subprocess_utils import hidden_subprocess_kwargs


PDF_EXPORT_SCHEMA = "tigercapture.ppt.pdf_export.v1"


def _tail(text: str, limit: int = 1600) -> str:
    return str(text or "")[-max(1, int(limit)) :]


def find_libreoffice_executable() -> str | None:
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    if sys.platform == "win32":
        candidates = [
            Path("C:/Program Files/LibreOffice/program/soffice.exe"),
            Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
    return None


def _powershell_executable() -> str | None:
    return shutil.which("powershell") or shutil.which("pwsh")


def _base_result(host: str, output_pdf: Path) -> dict[str, Any]:
    return {
        "schema": PDF_EXPORT_SCHEMA,
        "host": host,
        "status": "skipped",
        "ok": False,
        "output_pdf": str(output_pdf),
        "executable": "",
    }


def _finish_result(result: dict[str, Any], status: str) -> dict[str, Any]:
    result["status"] = status
    result["ok"] = status == "passed"
    return result


def convert_pptx_to_pdf_with_libreoffice(
    pptx: str | Path,
    pdf_path: str | Path,
    *,
    executable: str | None = None,
    timeout_sec: int = 60,
) -> dict[str, Any]:
    """Convert a PPTX to an exact PDF path using LibreOffice headless."""
    target = Path(pptx).resolve()
    output = Path(pdf_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    soffice = executable or find_libreoffice_executable()
    result = _base_result("libreoffice", output)
    result["executable"] = soffice or ""
    if not soffice:
        result["reason"] = "LibreOffice executable not found"
        return result

    with tempfile.TemporaryDirectory(prefix="tigercapture_ppt_pdf_", dir=str(output.parent)) as temp_dir:
        temp_out = Path(temp_dir)
        command = [
            soffice,
            "--headless",
            "--nologo",
            "--nolockcheck",
            "--nodefault",
            "--norestore",
            "--nofirststartwizard",
            "--convert-to",
            "pdf",
            "--outdir",
            str(temp_out),
            str(target),
        ]
        start = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout_sec)),
                check=False,
                **hidden_subprocess_kwargs(),
            )
        except subprocess.TimeoutExpired as exc:
            result.update(
                {
                    "reason": f"LibreOffice timed out after {timeout_sec}s",
                    "duration_ms": int((time.monotonic() - start) * 1000),
                    "stdout_tail": _tail(getattr(exc, "stdout", "") or ""),
                    "stderr_tail": _tail(getattr(exc, "stderr", "") or ""),
                }
            )
            return _finish_result(result, "failed")

        produced = temp_out / f"{target.stem}.pdf"
        ok = completed.returncode == 0 and produced.exists() and produced.stat().st_size > 0
        if ok:
            if output.exists():
                output.unlink()
            shutil.move(str(produced), str(output))
        result.update(
            {
                "returncode": int(completed.returncode),
                "duration_ms": int((time.monotonic() - start) * 1000),
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            }
        )
        if not ok:
            result["reason"] = "LibreOffice conversion did not produce a non-empty PDF"
        return _finish_result(result, "passed" if ok else "failed")


def convert_pptx_to_pdf_with_powerpoint_com(
    pptx: str | Path,
    pdf_path: str | Path,
    *,
    timeout_sec: int = 90,
) -> dict[str, Any]:
    """Convert a PPTX to PDF using local PowerPoint COM on Windows."""
    target = Path(pptx).resolve()
    output = Path(pdf_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    result = _base_result("powerpoint_com", output)
    if sys.platform != "win32":
        result["reason"] = "PowerPoint COM conversion is Windows-only"
        return result
    powershell = _powershell_executable()
    if not powershell:
        result["reason"] = "PowerShell executable not found"
        return result
    result["executable"] = powershell
    pptx_text = str(target).replace("'", "''")
    pdf_text = str(output).replace("'", "''")
    script = f"""
$ErrorActionPreference = 'Stop'
$pptx = '{pptx_text}'
$pdf = '{pdf_text}'
$app = $null
$presentation = $null
try {{
  $app = New-Object -ComObject PowerPoint.Application
  $presentation = $app.Presentations.Open($pptx, $true, $false, $false)
  $presentation.SaveAs($pdf, 32)
}} finally {{
  if ($presentation -ne $null) {{ $presentation.Close() | Out-Null }}
  if ($app -ne $null) {{ $app.Quit() | Out-Null }}
}}
Write-Output $pdf
"""
    start = time.monotonic()
    try:
        completed = subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_sec)),
            check=False,
            **hidden_subprocess_kwargs(),
        )
    except subprocess.TimeoutExpired as exc:
        result.update(
            {
                "reason": f"PowerPoint COM conversion timed out after {timeout_sec}s",
                "duration_ms": int((time.monotonic() - start) * 1000),
                "stdout_tail": _tail(getattr(exc, "stdout", "") or ""),
                "stderr_tail": _tail(getattr(exc, "stderr", "") or ""),
            }
        )
        return _finish_result(result, "failed")
    ok = completed.returncode == 0 and output.exists() and output.stat().st_size > 0
    result.update(
        {
            "returncode": int(completed.returncode),
            "duration_ms": int((time.monotonic() - start) * 1000),
            "stdout_tail": _tail(completed.stdout),
            "stderr_tail": _tail(completed.stderr),
        }
    )
    if not ok:
        result["reason"] = "PowerPoint COM conversion did not produce a non-empty PDF"
    return _finish_result(result, "passed" if ok else "failed")


def export_pptx_to_pdf(
    pptx: str | Path,
    pdf_path: str | Path,
    *,
    backend: str = "auto",
    timeout_sec: int = 90,
) -> dict[str, Any]:
    """Convert a generated PPTX to PDF and report every attempted backend."""
    mode = str(backend or "auto").strip().lower()
    target_pdf = Path(pdf_path).resolve()
    attempts: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "schema": PDF_EXPORT_SCHEMA,
        "requested_backend": mode,
        "backend": "",
        "ok": False,
        "status": "failed",
        "output_pdf": str(target_pdf),
        "attempts": attempts,
    }

    def _try(row: dict[str, Any]) -> bool:
        attempts.append(row)
        if row.get("status") == "passed":
            result.update(
                {
                    "backend": str(row.get("host") or ""),
                    "ok": True,
                    "status": "passed",
                    "duration_ms": int(row.get("duration_ms") or 0),
                }
            )
            return True
        return False

    if mode in {"auto", "libreoffice", "soffice"}:
        if _try(convert_pptx_to_pdf_with_libreoffice(pptx, target_pdf, timeout_sec=timeout_sec)):
            return result
        if mode != "auto":
            result["reason"] = attempts[-1].get("reason") or "LibreOffice PDF export failed"
            return result

    if mode in {"auto", "powerpoint", "powerpoint_com", "com"}:
        if _try(convert_pptx_to_pdf_with_powerpoint_com(pptx, target_pdf, timeout_sec=timeout_sec)):
            return result
        result["reason"] = attempts[-1].get("reason") or "PowerPoint COM PDF export failed"
        return result

    result["reason"] = f"Unknown PDF export backend: {backend}"
    return result


def export_deck_pdf(
    deck: DeckSpec,
    pdf_path: str | Path,
    *,
    backend: str = "auto",
    timeout_sec: int = 90,
    pptx_path: str | Path | None = None,
    keep_intermediate: bool = False,
    include_animations: bool = True,
) -> dict[str, Any]:
    """Write a temporary PPTX for a deck and convert it to PDF."""
    target_pdf = Path(pdf_path).resolve()
    target_pdf.parent.mkdir(parents=True, exist_ok=True)
    source_pptx = Path(pptx_path).resolve() if pptx_path is not None else None
    if source_pptx is not None:
        source_pptx.parent.mkdir(parents=True, exist_ok=True)
        written = write_pptx_compatible(deck, source_pptx, include_animations=include_animations)
        result = export_pptx_to_pdf(written, target_pdf, backend=backend, timeout_sec=timeout_sec)
        result.update({"source_pptx": str(written), "source_pptx_retained": True, "slide_count": len(deck.slides)})
        return result

    with tempfile.TemporaryDirectory(prefix="tigercapture_ppt_export_", dir=str(target_pdf.parent)) as temp_dir:
        temp_pptx = Path(temp_dir) / f"{target_pdf.stem}.pptx"
        written = write_pptx_compatible(deck, temp_pptx, include_animations=include_animations)
        result = export_pptx_to_pdf(written, target_pdf, backend=backend, timeout_sec=timeout_sec)
        result.update({"source_pptx": "", "source_pptx_retained": False, "slide_count": len(deck.slides)})
        if keep_intermediate:
            retained = target_pdf.with_suffix(".pptx")
            if retained.exists():
                retained.unlink()
            shutil.copyfile(written, retained)
            result.update({"source_pptx": str(retained), "source_pptx_retained": True})
        return result


__all__ = [
    "PDF_EXPORT_SCHEMA",
    "convert_pptx_to_pdf_with_libreoffice",
    "convert_pptx_to_pdf_with_powerpoint_com",
    "export_deck_pdf",
    "export_pptx_to_pdf",
    "find_libreoffice_executable",
]
