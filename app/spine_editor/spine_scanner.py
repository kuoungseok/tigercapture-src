"""Spine file scanner — priority-first search + persistent cache."""
from __future__ import annotations
import os
import json
import string
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QProgressBar, QLineEdit, QTextEdit,
)

from app.icons import app_icon, icon_size
from app.style import studio_chrome_qss

# ── cache file ────────────────────────────────────────────────────────────

_CACHE_PATH = Path(os.path.expanduser("~")) / ".tigercapture" / "spine_scan_cache.json"
_IMAGE_EXTS = (".png", ".webp", ".jpg", ".jpeg")


def _save_cache(items: list[dict]) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"items": items, "ts": time.time()}, f, ensure_ascii=False)
    except Exception:
        pass


def _load_cache() -> list[dict]:
    try:
        if _CACHE_PATH.exists():
            with open(_CACHE_PATH, encoding="utf-8") as f:
                return json.load(f).get("items", [])
    except Exception:
        pass
    return []


# ── data class ────────────────────────────────────────────────────────────

class SpineFileInfo:
    __slots__ = ("path", "name", "bone_count", "anim_count",
                 "has_atlas", "has_texture", "size_kb")

    def __init__(self, path: str, name: str, bone_count: int = 0,
                 anim_count: int = 0, has_atlas: bool = False,
                 has_texture: bool = False, size_kb: int = 0):
        self.path = path
        self.name = name
        self.bone_count = bone_count
        self.anim_count = anim_count
        self.has_atlas = has_atlas
        self.has_texture = has_texture
        self.size_kb = size_kb

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}

    @staticmethod
    def from_dict(d: dict) -> "SpineFileInfo":
        return SpineFileInfo(**{k: d.get(k, 0 if k not in ("path","name") else "")
                                for k in SpineFileInfo.__slots__})


# ── file probing ──────────────────────────────────────────────────────────

def _probe_json(path: str) -> tuple[bool, int, int]:
    try:
        if os.path.getsize(path) > 20 * 1024 * 1024:
            return False, 0, 0
        with open(path, "rb") as f:
            head = f.read(512).decode("utf-8", errors="ignore")
        if '"bones"' not in head and '"skeleton"' not in head:
            return False, 0, 0
        with open(path, encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        if "bones" not in data:
            return False, 0, 0
        return True, len(data.get("bones", [])), len(data.get("animations", {}))
    except Exception:
        return False, 0, 0


def _probe_binary(path: str) -> bool:
    try:
        sz = os.path.getsize(path)
        if sz < 16 or sz > 30 * 1024 * 1024:
            return False
        with open(path, "rb") as f:
            head = f.read(64)
        return sum(1 for b in head[:32] if 32 <= b < 127) > 8
    except Exception:
        return False


def _spine_stem(path: str) -> str:
    stem = os.path.splitext(path)[0]
    if stem.endswith(".skel"):
        stem = stem[:-5]
    return stem


def _find_atlas(path: str) -> Optional[str]:
    exact = _spine_stem(path) + ".atlas"
    if os.path.exists(exact):
        return exact

    base_dir = os.path.dirname(path)
    try:
        atlases = sorted(
            p for p in os.listdir(base_dir)
            if p.lower().endswith(".atlas")
        )
    except Exception:
        return None
    if not atlases:
        return None
    return os.path.join(base_dir, atlases[0])


def _atlas_pages(atlas_path: str) -> list[str]:
    pages: list[str] = []
    try:
        with open(atlas_path, encoding="utf-8-sig") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or "." not in stripped:
                    continue
                if line.startswith(" ") or line.startswith("\t"):
                    continue
                if stripped.startswith("#"):
                    continue
                if os.path.splitext(stripped)[1].lower() in _IMAGE_EXTS:
                    pages.append(stripped)
    except Exception:
        pass
    return pages


def _has_texture(path: str, atlas_path: Optional[str]) -> bool:
    base_dir = os.path.dirname(atlas_path or path)
    if atlas_path and os.path.exists(atlas_path):
        for page in _atlas_pages(atlas_path):
            page_path = page if os.path.isabs(page) else os.path.join(base_dir, page)
            if os.path.exists(page_path):
                return True

    stem = _spine_stem(path)
    return any(os.path.exists(stem + ext) for ext in _IMAGE_EXTS)


def _build_info(path: str, name: str, bones: int = 0, anims: int = 0) -> SpineFileInfo:
    atlas_path = _find_atlas(path)
    has_atlas = bool(atlas_path)
    has_tex = _has_texture(path, atlas_path)
    sz = 0
    try:
        sz = os.path.getsize(path) // 1024
    except Exception:
        pass
    return SpineFileInfo(path, name, bones, anims, has_atlas, has_tex, sz)


def _scan_file(fpath: str) -> Optional[SpineFileInfo]:
    fname = os.path.basename(fpath)
    fl = fname.lower()
    if fl.endswith(".skel.json"):
        ok, b, a = _probe_json(fpath)
        return _build_info(fpath, fname, b, a) if ok else None
    if fl.endswith(".skel"):
        return _build_info(fpath, fname) if _probe_binary(fpath) else None
    if fl.endswith(".json") and not fl.endswith(".model3.json"):
        ok, b, a = _probe_json(fpath)
        return _build_info(fpath, fname, b, a) if ok else None
    return None


# ── priority locations ────────────────────────────────────────────────────

def _priority_locations() -> list[str]:
    home = os.path.expanduser("~")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))

    # Fixed high-probability locations
    fixed = [
        os.path.join(project_root, "resources"),
        os.path.join(home, "Desktop"),
        os.path.join(home, "Downloads"),
        os.path.join(home, "Documents"),
        os.path.join(home, "projects"),
        os.path.join(home, "dev"),
        os.path.join(home, "work"),
    ]

    # Steam libraries on each drive
    steam_paths = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:"
        for sub in [
            f"{drive}/Steam/steamapps/common",
            f"{drive}/SteamLibrary/steamapps/common",
            f"{drive}/Program Files (x86)/Steam/steamapps/common",
        ]:
            if os.path.isdir(sub):
                steam_paths.append(sub)

    # Common game / dev folders on each drive
    game_paths = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:"
        for sub in ["Games", "Game", "GameData", "Spine", "Assets", "Project"]:
            p = f"{drive}/{sub}"
            if os.path.isdir(p):
                game_paths.append(p)

    return fixed + steam_paths + game_paths


_SKIP_DIRS = {
    "windows", "system32", "syswow64", "program files", "program files (x86)",
    "programdata", "$recycle.bin", "system volume information",
    "recovery", "boot", "efi", ".git", "__pycache__", "node_modules",
    ".venv", "venv", "env", "site-packages", "dist-packages",
}


# ── worker ────────────────────────────────────────────────────────────────

class ScanWorker(QThread):
    found     = Signal(object)   # SpineFileInfo
    progress  = Signal(str)      # current path
    finished  = Signal(int)      # total count

    def __init__(self, known_paths: set[str], parent=None):
        super().__init__(parent)
        self._known = known_paths   # already-found paths, skip duplicates
        self._stop = False

    def stop(self):
        self._stop = True

    def _walk(self, root: str):
        for dirpath, dirs, files in os.walk(root, topdown=True,
                                             followlinks=False, onerror=None):
            if self._stop:
                return
            dirs[:] = [
                d for d in dirs
                if d.lower() not in _SKIP_DIRS and not d.startswith(".")
            ]
            self.progress.emit(dirpath[:90])
            for fname in files:
                if self._stop:
                    return
                fl = fname.lower()
                if not (fl.endswith(".skel") or fl.endswith(".json")):
                    continue
                fpath = os.path.join(dirpath, fname)
                if fpath in self._known:
                    continue
                info = _scan_file(fpath)
                if info:
                    self._known.add(fpath)
                    self.found.emit(info)

    def run(self):
        count = 0
        # Phase 1: priority locations
        for loc in _priority_locations():
            if self._stop:
                break
            if os.path.isdir(loc):
                self._walk(loc)

        # Phase 2: full drive sweep (skip already-covered drives if priority hit them)
        for letter in string.ascii_uppercase:
            if self._stop:
                break
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                self._walk(drive)

        self.finished.emit(len(self._known))


# ── dialog ────────────────────────────────────────────────────────────────

class SpineScannerDialog(QDialog):
    file_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spine 파일 탐색")
        self.resize(860, 580)
        self.setStyleSheet(studio_chrome_qss("""
            QDialog { background:#0B0D16; color:#E8EAF4; }
            QListWidget { font-size:11px; alternate-background-color:#111421; }
            QProgressBar { background:#111421; border:none; border-radius:3px; height:5px; }
            QProgressBar::chunk { background:#6F5CFF; border-radius:3px; }
        """))

        self._worker: Optional[ScanWorker] = None
        self._all: list[SpineFileInfo] = []
        self._known_paths: set[str] = set()

        self._build_ui()
        self._load_cache()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lay.setContentsMargins(12, 12, 12, 12)

        _btn = ("QPushButton{background:rgba(255,255,255,18);color:#E8EAF4;border:1px solid #37405A;"
                "border-radius:13px;padding:7px 14px;font-size:11px;font-weight:700;}"
                "QPushButton:hover{background:rgba(255,255,255,30);border-color:#7580A5;color:#fff;}"
                "QPushButton:disabled{background:rgba(255,255,255,7);border-color:#252B3A;color:#6F7484;}")

        # Top controls
        top = QHBoxLayout()
        self._scan_btn = QPushButton("탐색 시작")
        self._scan_btn.setIcon(app_icon("zoom", size=15))
        self._scan_btn.setIconSize(icon_size(15))
        self._scan_btn.setStyleSheet(_btn)
        self._scan_btn.clicked.connect(self._start_scan)
        top.addWidget(self._scan_btn)

        self._stop_btn = QPushButton("중지")
        self._stop_btn.setIcon(app_icon("stop", size=15))
        self._stop_btn.setIconSize(icon_size(15))
        self._stop_btn.setStyleSheet(_btn)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_scan)
        top.addWidget(self._stop_btn)

        clear_btn = QPushButton("목록 초기화")
        clear_btn.setIcon(app_icon("trash", size=15))
        clear_btn.setIconSize(icon_size(15))
        clear_btn.setStyleSheet(_btn)
        clear_btn.clicked.connect(self._clear_all)
        top.addWidget(clear_btn)

        self._status_lbl = QLabel("이전 탐색 결과를 불러왔습니다")
        self._status_lbl.setStyleSheet("color:#A7ADC2;font-size:10px;")
        top.addWidget(self._status_lbl, 1)
        lay.addLayout(top)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.hide()
        lay.addWidget(self._progress)

        # Filter row
        frow = QHBoxLayout()
        search_icon = QLabel("")
        search_icon.setPixmap(app_icon("zoom", size=15).pixmap(icon_size(15)))
        frow.addWidget(search_icon)
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("파일명 / 경로 필터")
        self._filter.textChanged.connect(self._apply_filter)
        frow.addWidget(self._filter)

        self._atlas_btn = QPushButton("atlas 포함만")
        self._atlas_btn.setIcon(app_icon("project", size=14))
        self._atlas_btn.setIconSize(icon_size(14))
        self._atlas_btn.setCheckable(True)
        self._atlas_btn.setStyleSheet(_btn)
        self._atlas_btn.toggled.connect(self._apply_filter)
        frow.addWidget(self._atlas_btn)

        self._tex_btn = QPushButton("텍스처 풀셋만")
        self._tex_btn.setIcon(app_icon("media", size=14))
        self._tex_btn.setIconSize(icon_size(14))
        self._tex_btn.setCheckable(True)
        self._tex_btn.setStyleSheet(_btn)
        self._tex_btn.toggled.connect(self._apply_filter)
        frow.addWidget(self._tex_btn)
        lay.addLayout(frow)

        # List
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.currentItemChanged.connect(self._on_sel_changed)
        self._list.itemDoubleClicked.connect(self._on_load)
        lay.addWidget(self._list, 1)

        # Detail
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setFixedHeight(64)
        self._detail.setStyleSheet(studio_chrome_qss(
            "QTextEdit{color:#A7ADC2;font-size:10px;padding:6px;}"
        ))
        lay.addWidget(self._detail)

        # Bottom
        btm = QHBoxLayout()
        self._count_lbl = QLabel("0개")
        self._count_lbl.setStyleSheet("color:#A7ADC2;font-size:10px;")
        btm.addWidget(self._count_lbl)
        btm.addStretch()

        self._load_btn = QPushButton("열기")
        self._load_btn.setIcon(app_icon("project", size=16, color="#FFFFFF"))
        self._load_btn.setIconSize(icon_size(16))
        self._load_btn.setEnabled(False)
        self._load_btn.setStyleSheet(
            "QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #FF8057,stop:0.62 #F65343,stop:1 #E84E78);"
            "color:#fff;border:1px solid #FF9A78;border-radius:14px;padding:7px 20px;font-size:12px;font-weight:800;}"
            "QPushButton:hover{background:#FF714D;}"
            "QPushButton:disabled{background:rgba(255,255,255,7);border-color:#252B3A;color:#6F7484;}")
        self._load_btn.clicked.connect(self._on_load)
        btm.addWidget(self._load_btn)

        cancel_btn = QPushButton("닫기")
        cancel_btn.setStyleSheet(_btn)
        cancel_btn.clicked.connect(self.reject)
        btm.addWidget(cancel_btn)
        lay.addLayout(btm)

    # ── cache ─────────────────────────────────────────────────────────────

    def _load_cache(self):
        cached = _load_cache()
        if not cached:
            self._status_lbl.setText("탐색 버튼을 눌러 시작하세요")
            return
        for d in cached:
            try:
                info = SpineFileInfo.from_dict(d)
                if os.path.exists(info.path):   # skip deleted files
                    info = _build_info(info.path, info.name, info.bone_count, info.anim_count)
                    self._all.append(info)
                    self._known_paths.add(info.path)
            except Exception:
                pass
        self._rebuild_list()
        self._status_lbl.setText(f"캐시에서 {len(self._all)}개 불러옴")

    def _save_cache(self):
        _save_cache([i.to_dict() for i in self._all])

    # ── scanning ──────────────────────────────────────────────────────────

    def _start_scan(self):
        self._scan_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._progress.show()
        self._status_lbl.setText("우선순위 폴더 탐색 중...")

        self._worker = ScanWorker(set(self._known_paths))
        self._worker.found.connect(self._on_found, Qt.ConnectionType.QueuedConnection)
        self._worker.progress.connect(
            lambda p: self._status_lbl.setText(p[:90]),
            Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._on_finished, Qt.ConnectionType.QueuedConnection)
        self._worker.start()

    def _stop_scan(self):
        if self._worker:
            self._worker.stop()
        self._stop_btn.setEnabled(False)
        self._status_lbl.setText(f"중지됨 — {len(self._all)}개 발견 (목록 유지됨)")
        self._progress.hide()
        self._save_cache()

    def _on_found(self, info: SpineFileInfo):
        self._all.append(info)
        self._known_paths.add(info.path)
        if self._matches(info):
            self._add_item(info)
        self._count_lbl.setText(f"{self._list.count()}개 / {len(self._all)}개 발견")

    def _on_finished(self, total: int):
        self._scan_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress.hide()
        self._status_lbl.setText(f"완료 — 총 {len(self._all)}개 발견")
        self._save_cache()

    # ── list ──────────────────────────────────────────────────────────────

    def _add_item(self, info: SpineFileInfo):
        badges = (" atlas" if info.has_atlas else "") + (" tex" if info.has_texture else "")
        meta = (f"  {info.bone_count}b" if info.bone_count else "") + \
               (f"  {info.anim_count}a" if info.anim_count else "")
        folder = os.path.basename(os.path.dirname(info.path))
        label = f"{info.name}{badges}{meta}  —  …/{folder}/"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, info)
        item.setToolTip(info.path)
        if info.has_atlas and info.has_texture:
            item.setForeground(QColor("#80e860"))
        elif info.has_atlas:
            item.setForeground(QColor("#f0c040"))
        else:
            item.setForeground(QColor("#A7ADC2"))
        self._list.addItem(item)

    def _rebuild_list(self):
        self._list.clear()
        for info in self._all:
            if self._matches(info):
                self._add_item(info)
        self._count_lbl.setText(f"{self._list.count()}개 / {len(self._all)}개")

    def _matches(self, info: SpineFileInfo) -> bool:
        filt = self._filter.text().lower()
        if filt and filt not in info.path.lower() and filt not in info.name.lower():
            return False
        if self._atlas_btn.isChecked() and not info.has_atlas:
            return False
        if self._tex_btn.isChecked() and not (info.has_atlas and info.has_texture):
            return False
        return True

    def _apply_filter(self):
        self._rebuild_list()

    def _clear_all(self):
        self._all.clear()
        self._known_paths.clear()
        self._list.clear()
        self._count_lbl.setText("0개")
        self._status_lbl.setText("목록 초기화됨")
        _save_cache([])

    # ── selection / load ──────────────────────────────────────────────────

    def _on_sel_changed(self, cur, _):
        if not cur:
            self._load_btn.setEnabled(False)
            self._detail.clear()
            return
        self._load_btn.setEnabled(True)
        info: SpineFileInfo = cur.data(Qt.ItemDataRole.UserRole)
        self._detail.setHtml(
            f"<b>{info.name}</b><br>"
            f"{info.path}<br>"
            f"크기: {info.size_kb}KB &nbsp;|&nbsp; 뼈대: {info.bone_count} &nbsp;|&nbsp; "
            f"애니메이션: {info.anim_count}<br>"
            f"atlas: {'✓' if info.has_atlas else '✗'} &nbsp;|&nbsp; "
            f"텍스처: {'✓' if info.has_texture else '✗'}"
        )

    def _on_load(self, *_):
        item = self._list.currentItem()
        if not item:
            return
        info: SpineFileInfo = item.data(Qt.ItemDataRole.UserRole)
        self.file_selected.emit(info.path)
        self.accept()

    def closeEvent(self, e):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(1000)
        self._save_cache()
        super().closeEvent(e)
