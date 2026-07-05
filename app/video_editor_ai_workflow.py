from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QProcess, Qt, QTimer, QVariantAnimation
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import current_language, tr
from app.subtitles import Subtitle
from app.video_editor_subtitle_workflow import WhisperDialog


def _generate_ai_subtitles(self) -> None:
    """Open WhisperDialog to auto-generate subtitles for the active track."""
    try:
        from app.local_ml import local_ml_temporarily_disabled

        if local_ml_temporarily_disabled():
            self._flash_status(
                "AI ?먮쭑? ?꾩떆濡?鍮꾪솢?깊솕?섏뼱 ?덉뒿?덈떎. TIGERCAPTURE_LOCAL_ML_ENABLED=1濡??ㅼ떆 耳????덉뒿?덈떎."
            )
            return
    except Exception:
        self._flash_status("AI ?먮쭑? ?꾩옱 ?ъ슜?????놁뒿?덈떎")
        return
    # ???? Check Whisper availability ????????????????????????????????????????????????????????????????????????
    has_whisper = False
    try:
        import faster_whisper  # noqa: F401
        has_whisper = True
    except ImportError:
        try:
            import whisper  # noqa: F401
            has_whisper = True
        except ImportError:
            pass

    if not has_whisper:
        ret = QMessageBox.question(
            self,
            "AI ?먮쭑",
            "Whisper媛 ?ㅼ튂?섏? ?딆븯?듬땲??\n"
            "pip install faster-whisper 瑜??ㅽ뻾?????ㅼ떆 ?쒕룄?섏꽭??\n\n"
            "吏湲??ㅼ튂?섏떆寃좎뒿?덇퉴?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            import subprocess
            import sys
            from app.subprocess_utils import hidden_subprocess_kwargs
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "faster-whisper"],
                check=False,
                **hidden_subprocess_kwargs(),
            )
        return

    # ???? Resolve video path ????????????????????????????????????????????????????????????????????????????????????????
    path: Path | None = None
    if self._active_track_id is not None:
        t = self._find_track(self._active_track_id)
        if t and t.source_path:
            path = t.source_path
    if path is None:
        for t in self._tracks:
            if t.source_path:
                path = t.source_path
                break
    if path is None:
        # Try the first clip source across all tracks
        for t in self._tracks:
            for clip in t.clips:
                if getattr(clip, "source_path", None):
                    path = clip.source_path
                    break
            if path:
                break

    if path is None:
        QMessageBox.warning(self, "AI ?먮쭑", "癒쇱? ?곸긽????꾨씪?몄뿉 ?щ젮二쇱꽭??")
        return

    # ???? Run dialog ????????????????????????????????????????????????????????????????????????????????????????????????????????
    dlg = WhisperDialog(path, self)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        segments = dlg.segments
        if not segments:
            return
        from app.subtitles import Subtitle
        from app.screenstudio_parity import screenstudio_transcript_subtitle_plan

        transcript_segments = []
        for seg in segments:
            try:
                transcript_segments.append(
                    {
                        "text": str(seg.get("text") or ""),
                        "start_ms": int(float(seg.get("start", 0.0)) * 1000),
                        "end_ms": int(float(seg.get("end", 0.0)) * 1000),
                    }
                )
            except Exception:
                continue
        plan = screenstudio_transcript_subtitle_plan(
            getattr(self, "_project_settings", {}) or {},
            transcript_segments,
        )
        layer = self._subtitle_panel.layer
        count = 0
        for row in plan.get("subtitle_rows", []) or []:
            try:
                sub = Subtitle(
                    text=str(row.get("text") or ""),
                    start_ms=int(row.get("start_ms", 0) or 0),
                    end_ms=int(row.get("end_ms", 0) or 0),
                    show_box=bool(row.get("show_box", True)),
                    style=dict(row.get("style", {}) or {}),
                )
                layer.add(sub)
                count += 1
            except Exception:
                pass
        try:
            self._subtitle_panel._refresh_list()
        except Exception:
            pass
        try:
            self._subtitle_panel.subtitles_changed.emit()
        except Exception:
            pass
        try:
            self._on_subtitles_changed()
        except Exception:
            pass
        QMessageBox.information(
            self, "AI ?먮쭑", f"?먮쭑 {count}媛??앹꽦 ?꾨즺!"
        )


def _open_ai_script_review_dialog(self, *, prompt: str = "", plan=None) -> None:
    dialog = getattr(self, "_ai_review_dialog", None)
    if dialog is not None and dialog.isVisible():
        panel = getattr(self, "_ai_review_panel", None)
        self._prime_ai_review_panel(panel, prompt=prompt, plan=plan)
        dialog.raise_()
        dialog.activateWindow()
        return
    try:
        from app.ai_script_edit_panel import ScriptEditPanel
    except Exception as exc:
        self._flash_status(f"AI Review load failed: {exc}")
        return

    dialog = QDialog(self)
    dialog.setObjectName("AIReviewDialog")
    dialog.setWindowTitle("AI Review")
    dialog.setMinimumSize(820, 620)
    try:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            dialog.resize(
                max(820, min(1160, int(available.width() * 0.62))),
                max(620, min(860, int(available.height() * 0.78))),
            )
    except Exception:
        dialog.resize(960, 720)
    dialog.setStyleSheet(
        """
        QDialog#AIReviewDialog {
            background: #080B13;
            color: #F8FAFF;
        }
        QWidget#AIReviewHeader {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(255, 106, 69, 58),
                stop:.46 rgba(122, 99, 255, 44),
                stop:1 rgba(50, 215, 232, 32));
            border: 1px solid rgba(140, 150, 206, 115);
            border-radius: 18px;
        }
        QLabel#AIReviewTitle {
            color: #FFFFFF;
            font-size: 18px;
            font-weight: 950;
        }
        QLabel#AIReviewSubtitle {
            color: rgba(239, 243, 255, 205);
            font-size: 12px;
            font-weight: 760;
        }
        """
    )

    root = QVBoxLayout(dialog)
    root.setContentsMargins(14, 14, 14, 14)
    root.setSpacing(10)

    header = QWidget(dialog)
    header.setObjectName("AIReviewHeader")
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(16, 12, 16, 12)
    header_layout.setSpacing(12)
    badge = QLabel("AI", header)
    badge.setObjectName("AICommandBadge")
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setFixedSize(46, 38)
    badge.setStyleSheet(
        """
        QLabel#AICommandBadge {
            color: #FFFFFF;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #FF704F, stop:.52 #8B67FF, stop:1 #32D7E8);
            border: 1px solid rgba(255,255,255,145);
            border-radius: 17px;
            font-weight: 950;
        }
        """
    )
    header_layout.addWidget(badge)
    title_box = QVBoxLayout()
    title_box.setSpacing(2)
    title = QLabel("AI Review", header)
    title.setObjectName("AIReviewTitle")
    subtitle = QLabel("Plan?먯꽌 留뚮뱺 ?묒뾽???뺤씤?섍퀬, 泥댄겕????ぉ留???꾨씪?몄뿉 ?곸슜?⑸땲??", header)
    subtitle.setObjectName("AIReviewSubtitle")
    subtitle.setWordWrap(True)
    title_box.addWidget(title)
    title_box.addWidget(subtitle)
    header_layout.addLayout(title_box, stretch=1)
    close_btn = QPushButton("?リ린", header)
    close_btn.setObjectName("ToolButton")
    close_btn.clicked.connect(dialog.close)
    header_layout.addWidget(close_btn)
    root.addWidget(header)

    panel = ScriptEditPanel(dialog)
    try:
        panel.set_external_provider_setup_handler(self._open_ai_provider_setup_for_id)
    except Exception:
        pass
    try:
        panel.set_review_mode(True)
    except Exception:
        pass
    panel.plan_generated.connect(self._on_ai_script_edit_plan_generated)
    panel.preview_requested.connect(self._on_ai_script_edit_plan_generated)
    panel.apply_selected_requested.connect(self._apply_ai_script_edit_selected)
    panel.apply_all_requested.connect(self._apply_ai_script_edit_all)
    panel.apply_cuts_requested.connect(self._apply_ai_script_edit_cuts)
    self._prime_ai_review_panel(panel, prompt=prompt, plan=plan)
    root.addWidget(panel, stretch=1)

    self._ai_review_dialog = dialog
    self._ai_review_panel = panel
    dialog.finished.connect(lambda *_args: self._clear_ai_review_dialog(dialog))
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


def _refresh_ai_command_provider_status(self) -> str:
    try:
        from app.ai_providers import (
            ai_provider_readiness,
            provider_state_label,
            provider_interaction_model,
            provider_snapshot,
            provider_status_label,
            provider_user_label,
            selected_ai_provider_id,
        )

        statuses = ai_provider_readiness()
        snapshot = provider_snapshot()
        provider_id = selected_ai_provider_id()
        status_text = provider_status_label()
        row = statuses.get(provider_id) or {}
        interaction = provider_interaction_model(provider_id, row)
        tooltip = "\n".join(
            f"{item.get('label')}: {'ready' if item.get('available') else 'not ready'} - {item.get('reason')}"
            for item in statuses.values()
        )
        if provider_id != "rule_based" and row.get("available") and row.get("executor_wired"):
            status_text = f"{status_text} 쨌 Review required"
        if provider_id == "claude_mcp":
            status_text = f"{status_text} 쨌 Claude Code connected"
        elif provider_id == "local_llm":
            status_text = f"{status_text} 쨌 Local plan generation"
        combo = getattr(self, "_ai_command_provider_combo", None)
        if combo is not None:
            self._ai_command_provider_loading = True
            combo.blockSignals(True)
            combo.clear()
            for item_id in snapshot.get("provider_order") or statuses.keys():
                item = statuses.get(str(item_id)) or {}
                if not item:
                    continue
                combo.addItem(provider_user_label(str(item_id)), str(item_id))
            idx = combo.findData(provider_id)
            if idx < 0:
                idx = combo.findData("rule_based")
            combo.setCurrentIndex(max(0, idx))
            combo.setToolTip(tooltip)
            combo.blockSignals(False)
            self._ai_command_provider_loading = False
        label = getattr(self, "_ai_command_provider_status", None)
        if label is not None:
            label.setText(status_text)
            label.setToolTip(tooltip)
        setup_btn = getattr(self, "_ai_command_provider_setup_btn", None)
        if setup_btn is not None:
            setup_btn.setToolTip(tr("veditor.ai_command.setup.tooltip"))
        input_widget = getattr(self, "_ai_command_input", None)
        action_text = str(interaction.get("run_label") or tr("veditor.ai_command.run"))
        action_tip = str(interaction.get("summary") or tr("veditor.ai_command.status.default"))
        placeholder = tr("veditor.ai_command.placeholder")
        setup_tip = tr("veditor.ai_command.setup.tooltip")
        if input_widget is not None:
            input_widget.setPlaceholderText(placeholder)
        if setup_btn is not None:
            setup_btn.setToolTip(setup_tip)
        run_btn = getattr(self, "_ai_command_run_btn", None)
        if run_btn is not None:
            run_btn.setText(tr("veditor.ai_command.run"))
            run_btn.setToolTip(f"{action_text}: {action_tip}")
        review_btn = getattr(self, "_ai_command_review_btn", None)
        if review_btn is not None:
            if provider_id == "claude_mcp":
                review_btn.setText(tr("veditor.ai_command.open_claude"))
                review_btn.setToolTip(
                    "Claude CLI mode opens the terminal workflow first."
                )
            elif provider_id == "local_llm":
                review_btn.setText(str(interaction.get("review_label") or tr("veditor.ai_command.review")))
                review_btn.setToolTip(
                    "Review the generated edit plan before applying it."
                )
            else:
                review_btn.setText(str(interaction.get("review_label") or tr("veditor.ai_command.review")))
                review_btn.setToolTip("Review the generated AI edit plan.")
        if review_btn is not None:
            review_btn.setText(
                tr("veditor.ai_command.open")
                if provider_id == "claude_mcp"
                else tr("veditor.ai_command.review")
            )
            review_btn.setToolTip(tr("veditor.ai_command.status.default"))
        return status_text
    except Exception as exc:
        self._ai_command_provider_loading = False
        fallback = f"AI Provider: rule-based fallback ({exc})"
        label = getattr(self, "_ai_command_provider_status", None)
        if label is not None:
            label.setText(fallback)
        return fallback


def _find_claude_cli(self) -> str:
    for name in ("claude", "claude.cmd", "claude.exe"):
        path = shutil.which(name)
        if path:
            return str(path)
    try:
        npm_dir = Path.home() / "AppData" / "Roaming" / "npm"
        for name in ("claude.cmd", "claude.exe", "claude.ps1"):
            candidate = npm_dir / name
            if candidate.is_file():
                return str(candidate)
    except Exception:
        pass
    return ""


def _claude_mcp_add_args(self) -> list[str]:
    try:
        from app.ai_providers import default_mcp_server_command_parts

        python_exe, script, stdio_arg = default_mcp_server_command_parts()
    except Exception:
        python_exe = sys.executable
        script = str(Path(__file__).resolve().parents[1] / "tools" / "automation_mcp_server.py")
        stdio_arg = "--stdio"
    return ["mcp", "add", "--transport", "stdio", "tiger-studio", "--", python_exe, script, stdio_arg]


def _quote_powershell_literal(self, value: str | Path) -> str:
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def _write_claude_code_terminal_files(self, *, initial_prompt: str = "") -> tuple[Path, Path]:
    try:
        from app.paths import runtime_data_dir

        root_dir = runtime_data_dir() / "claude_code"
    except Exception:
        root_dir = Path.home() / ".tigercapture" / "claude_code"
    root_dir.mkdir(parents=True, exist_ok=True)

    workspace = Path(__file__).resolve().parents[1]
    clean_prompt = " ".join(str(initial_prompt or "").split())
    guide_path = root_dir / "TIGER_STUDIO_CLAUDE_START.md"
    ps1_path = root_dir / "start_tiger_studio_claude.ps1"
    cmd_path = root_dir / "start_tiger_studio_claude.cmd"
    cli = self._find_claude_cli()
    add_args = self._claude_mcp_add_args()

    prompt_block = clean_prompt or "(?꾩쭅 ?낅젰???몄쭛 紐낅졊???놁뒿?덈떎. Tiger Studio 李쎌뿉??紐낅졊???낅젰?섍굅??Claude ?곕??먯뿉??吏곸젒 ?붿껌???묒꽦?섏꽭??)"
    guide = f"""# Tiger Studio + Claude Code ?묒뾽 ?쒖옉

?뱀떊? 吏湲?Tiger Studio 鍮꾨뵒???몄쭛湲곗? ?④퍡 ?묒뾽?섎뒗 Claude Code?낅땲??

## ?곌껐 ?뺣낫
- ?묒뾽 ?대뜑: `{workspace}`
- MCP ?쒕쾭 ?대쫫: `tiger-studio`
- Tiger Studio 履?MCP ?쒕쾭??Python stdio ?쒕쾭濡??ㅽ뻾?⑸땲??

## ?쒖옉 ?덉감
1. Claude Code?먯꽌 `/mcp`瑜??낅젰??`tiger-studio` ?쒕쾭媛 蹂댁씠?붿? ?뺤씤?⑸땲??
2. `tiger-studio`媛 ?뱀씤?섏? ?딆븯?ㅻ㈃ Claude Code???덈궡???곕씪 ?뱀씤?⑸땲??
3. ?ъ슜?먯쓽 ?붿껌??諛붾줈 ?뚯씪 ?섏젙?쇰줈 諛붽씀湲??꾩뿉 Tiger Studio???꾨줈?앺듃? ??꾨씪???곹깭瑜?癒쇱? ?뺤씤?⑸땲??
4. ??꾨씪?? 誘몃뵒???, ?뚰겕踰ㅼ튂, Live2D/Spine, 而щ윭, ?먮쭑, ?뚮뜑 ?묒뾽? 媛?ν븯硫?Tiger Studio MCP ?꾧뎄濡??섑뻾?⑸땲??
5. ?꾪뿕???쇨큵 蹂寃? ??젣, export, overwrite ?꾩뿉 ?ъ슜?먯뿉寃??뺤씤?⑸땲??
6. UI?먯꽌 吏곸젒 ?뺤씤?댁빞 ?섎뒗 ?묒뾽? ?ъ슜?먭? ?뚯뒪?명븷 ???덇쾶 援ъ껜?곸쑝濡??덈궡?⑸땲??

## ?꾩옱 ?ъ슜?먭? ?낅젰???붿껌
{prompt_block}
"""
    guide_path.write_text(guide, encoding="utf-8")

    ps_lines = [
        "$ErrorActionPreference = 'Continue'",
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()",
        "try { chcp 65001 | Out-Null } catch {}",
        f"Set-Location -LiteralPath {self._quote_powershell_literal(workspace)}",
        "Write-Host ''",
        "Write-Host '=== Tiger Studio + Claude Code ===' -ForegroundColor Cyan",
        "Write-Host 'Tiger Studio ?묒뾽 ?대뜑?먯꽌 Claude Code瑜??쒖옉?⑸땲??'",
        "Write-Host ''",
        "Write-Host '[1/3] tiger-studio MCP ?깅줉 ?뺤씤...' -ForegroundColor Yellow",
        "& " + " ".join(self._quote_powershell_literal(part) for part in [cli, *add_args]),
        "Write-Host ''",
        "Write-Host '[2/3] Claude ?쒖옉 ?덈궡瑜??대┰蹂대뱶??蹂듭궗?⑸땲??' -ForegroundColor Yellow",
        f"$guidePath = {self._quote_powershell_literal(guide_path)}",
        "if (Test-Path -LiteralPath $guidePath) {",
        "  try {",
        "    Get-Content -Raw -LiteralPath $guidePath | Set-Clipboard",
        "    Write-Host \"?덈궡 留덊겕?ㅼ슫???대┰蹂대뱶??蹂듭궗?덉뒿?덈떎: $guidePath\" -ForegroundColor Green",
        "  } catch {",
        "    Write-Host \"?대┰蹂대뱶 蹂듭궗 ?ㅽ뙣: $($_.Exception.Message)\" -ForegroundColor Red",
        "    Write-Host \"?덈궡 ?뚯씪??吏곸젒 ?댁뼱 Claude??遺숈뿬?ｌ쑝?몄슂: $guidePath\"",
        "  }",
        "}",
        "Write-Host ''",
        "Write-Host '[3/3] Claude Code瑜??ㅽ뻾?⑸땲??' -ForegroundColor Yellow",
        "Write-Host '?쒖옉 ?덈궡 留덊겕?ㅼ슫??Claude 泥??꾨＼?꾪듃濡??꾨떖?⑸땲??' -ForegroundColor Green",
        "Write-Host 'Claude媛 鍮??붾㈃?쇰줈 ?대━硫?Ctrl+V ??Enter瑜??꾨Ⅴ怨? 洹??ㅼ쓬 /mcp濡?tiger-studio瑜??뺤씤?섏꽭??' -ForegroundColor DarkGray",
        "Write-Host ''",
        "$initialPrompt = ''",
        "if (Test-Path -LiteralPath $guidePath) {",
        "  $initialPrompt = Get-Content -Raw -LiteralPath $guidePath",
        "}",
        "& "
        + " ".join(
            [
                self._quote_powershell_literal(cli),
                "--add-dir",
                self._quote_powershell_literal(workspace),
                "--name",
                self._quote_powershell_literal("Tiger Studio"),
                "$initialPrompt",
            ]
        ),
        "Write-Host ''",
        "Write-Host 'Claude Code媛 醫낅즺?섏뿀?듬땲?? ??李쎌? ?レ븘???⑸땲??' -ForegroundColor DarkGray",
    ]
    ps1_path.write_text("\n".join(ps_lines) + "\n", encoding="utf-8")

    cmd = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "title Tiger Studio Claude Code\r\n"
        "powershell.exe -NoLogo -NoExit -ExecutionPolicy Bypass "
        f"-File \"{ps1_path}\"\r\n"
    )
    cmd_path.write_text(cmd, encoding="utf-8")
    return cmd_path, guide_path


def _launch_claude_code_terminal(self, *, initial_prompt: str = "") -> bool:
    cli = self._find_claude_cli()
    if not cli:
        QMessageBox.warning(
            self,
            "Claude Code",
            "Claude Code CLI瑜?李얠쓣 ???놁뒿?덈떎.\n"
            "?곕??먯뿉??`claude --version`???ㅽ뻾?섎뒗吏 ?뺤씤?????ㅼ떆 ?쒕룄?섏꽭??",
        )
        self._ai_command_set_status("Claude Code CLI瑜?李얠쓣 ???놁뒿?덈떎.")
        return False

    try:
        from app.ai_providers import (
            default_mcp_server_command,
            save_ai_provider_preference,
            save_claude_mcp_config,
        )

        save_claude_mcp_config(
            enabled=True,
            command=default_mcp_server_command(),
            cli_command=cli,
        )
        save_ai_provider_preference("claude_mcp")
        self._refresh_ai_command_provider_status()
    except Exception:
        pass

    clean_prompt = " ".join(str(initial_prompt or "").split())
    if clean_prompt:
        try:
            QApplication.clipboard().setText(clean_prompt)
        except Exception:
            pass

    start_notice = (
        "Claude Code瑜?PowerShell?먯꽌 ?쒖옉?⑸땲?? Tiger Studio MCP ?깅줉???뺤씤?섍퀬, "
        "?쒖옉 ?덈궡 留덊겕?ㅼ슫??Claude 泥??꾨＼?꾪듃濡??꾨떖?⑸땲??"
    )
    if clean_prompt:
        start_notice = f"{start_notice} ?꾩옱 ?낅젰??紐낅졊???덈궡???ы븿?덉뒿?덈떎."
    self._ai_command_append_chat("Tiger Studio", start_notice)
    self._ai_command_set_status(start_notice)

    if sys.platform.startswith("win"):
        try:
            cmd_path, guide_path = self._write_claude_code_terminal_files(initial_prompt=clean_prompt)
            os.startfile(str(cmd_path))
            launched = True
        except Exception:
            cmd_path = Path()
            guide_path = Path()
            launched = QProcess.startDetached(
                "powershell.exe",
                [
                    "-NoLogo",
                    "-NoExit",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    f"Set-Location -LiteralPath {self._quote_powershell_literal(Path(__file__).resolve().parents[1])}; & {self._quote_powershell_literal(cli)}",
                ],
            )
    else:
        cmd_path = Path()
        guide_path = Path()
        launched = QProcess.startDetached(cli, [], str(Path(__file__).resolve().parents[1]))

    if isinstance(launched, tuple):
        launched = bool(launched[0])
    else:
        launched = bool(launched)

    if not launched:
        QMessageBox.warning(self, "Claude Code", "Claude Code ?곕??먯쓣 ?댁? 紐삵뻽?듬땲??")
        self._ai_command_set_status("Claude Code ?곕????ㅽ뻾 ?ㅽ뙣")
        return False

    notice = (
        "Claude Code PowerShell???댁뿀?듬땲?? ?쒖옉 ?덈궡 留덊겕?ㅼ슫??Claude 泥??꾨＼?꾪듃濡??꾨떖?덇퀬 ?대┰蹂대뱶?먮룄 蹂듭궗?덉뒿?덈떎. "
        "Claude?먯꽌 /mcp濡?tiger-studio ?곌껐???뺤씤?섏꽭?? 鍮??붾㈃?쇰줈 ?대━硫?Ctrl+V ??Enter瑜??꾨Ⅴ?몄슂."
        if clean_prompt
        else "Claude Code PowerShell???댁뿀?듬땲?? ?쒖옉 ?덈궡瑜?Claude 泥??꾨＼?꾪듃濡??꾨떖?덉뒿?덈떎. /mcp濡?tiger-studio ?곌껐???뺤씤?섏꽭??"
    )
    if sys.platform.startswith("win") and guide_path:
        notice = f"{notice} ?덈궡 ?뚯씪: {guide_path}"
    self._ai_command_append_chat("Tiger Studio", notice)
    self._ai_command_set_status(notice)
    try:
        self._flash_status("Claude Code terminal opened")
    except Exception:
        pass
    return True


def _open_claude_provider_setup_dialog(self) -> None:
    try:
        from app.ai_providers import ai_provider_readiness, provider_setup_instructions, saved_claude_mcp_config

        info = provider_setup_instructions("claude_mcp")
        saved = saved_claude_mcp_config()
        row = ai_provider_readiness().get("claude_mcp") or {}
    except Exception as exc:
        QMessageBox.warning(self, "Claude ?곌껐", f"?곌껐 ?덈궡瑜?遺덈윭?ㅼ? 紐삵뻽?듬땲??\n{exc}")
        return
    cli = self._find_claude_cli()
    message = QMessageBox(self)
    message.setWindowTitle("Claude ?곌껐")
    message.setIcon(QMessageBox.Icon.Information)
    message.setText(str(info.get("summary") or "Claude Code? Tiger Studio MCP ?쒕쾭瑜??곌껐?⑸땲??"))
    current = [
        f"Claude CLI: {cli}" if cli else "Claude CLI: 李얠쓣 ???놁뒿?덈떎",
        "MCP status: available" if row.get("available") else "MCP status: not connected",
    ]
    if saved.get("command"):
        current.append(f"??λ맂 ?쒕쾭 紐낅졊: {saved.get('command')}")
    body = str(info.get("body") or "")
    message.setInformativeText(f"{body}\n\n?꾩옱 ?곹깭\n" + "\n".join(current))
    message.setDetailedText(
        "\n".join(
            [
                str(info.get("claude_command") or ""),
                str(info.get("server_command") or ""),
                "Claude Code?먯꽌 ?깅줉 ??`/mcp`瑜??낅젰?섎㈃ tiger-studio ?쒕쾭 ?뱀씤 ?곹깭瑜??뺤씤?????덉뒿?덈떎.",
            ]
        ).strip()
    )
    terminal_btn = message.addButton("Claude Code ?곕????닿린", QMessageBox.ButtonRole.ActionRole)
    auto_btn = message.addButton("MCP ?깅줉留??ㅽ뻾", QMessageBox.ButtonRole.ActionRole)
    status_btn = message.addButton("?곹깭 ?뺤씤", QMessageBox.ButtonRole.ActionRole)
    guide_btn = message.addButton("?곌껐 ?덈궡", QMessageBox.ButtonRole.HelpRole)
    message.addButton(QMessageBox.StandardButton.Close)
    message.exec()
    clicked = message.clickedButton()
    if clicked is terminal_btn:
        self._launch_claude_code_terminal()
    elif clicked is auto_btn:
        self._start_claude_mcp_auto_connect()
    elif clicked is status_btn:
        self._start_claude_mcp_status_check()
    elif clicked is guide_btn:
        self._show_ai_provider_instructions("claude_mcp")


def _open_claude_mcp_progress_dialog(self, *, title: str = "Claude ?곌껐") -> None:
    dialog = getattr(self, "_claude_mcp_dialog", None)
    if dialog is not None and dialog.isVisible():
        dialog.raise_()
        dialog.activateWindow()
        return
    dialog = QDialog(self)
    dialog.setWindowTitle(title)
    dialog.setMinimumSize(700, 420)
    dialog.setObjectName("ClaudeMcpDialog")
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(10)

    title_label = QLabel("Claude Code? Tiger Studio瑜??곌껐?⑸땲??", dialog)
    title_label.setObjectName("DialogTitle")
    title_label.setWordWrap(True)
    layout.addWidget(title_label)

    state = QLabel("以鍮?以?..", dialog)
    state.setWordWrap(True)
    layout.addWidget(state)

    progress = QProgressBar(dialog)
    progress.setRange(0, 0)
    progress.setTextVisible(True)
    layout.addWidget(progress)

    console = QPlainTextEdit(dialog)
    console.setReadOnly(True)
    console.setMinimumHeight(210)
    console.setPlaceholderText("Claude ?곌껐 濡쒓렇媛 ?ш린???쒖떆?⑸땲??")
    layout.addWidget(console, stretch=1)

    button_row = QHBoxLayout()
    button_row.addStretch(1)
    cancel_btn = QPushButton("痍⑥냼", dialog)
    close_btn = QPushButton("?リ린", dialog)
    close_btn.setEnabled(False)
    close_btn.setDefault(True)
    cancel_btn.clicked.connect(self._claude_mcp_cancel)
    close_btn.clicked.connect(dialog.close)
    button_row.addWidget(cancel_btn)
    button_row.addWidget(close_btn)
    layout.addLayout(button_row)

    self._claude_mcp_dialog = dialog
    self._claude_mcp_title_label = title_label
    self._claude_mcp_state_label = state
    self._claude_mcp_progress = progress
    self._claude_mcp_console = console
    self._claude_mcp_cancel_btn = cancel_btn
    self._claude_mcp_close_btn = close_btn
    self._claude_mcp_process = None
    self._claude_mcp_output = []
    self._claude_mcp_close_anim = None
    dialog.finished.connect(lambda *_args: self._claude_mcp_stop_close_attention())
    dialog.show()


def _claude_mcp_log(self, text: str) -> None:
    console = getattr(self, "_claude_mcp_console", None)
    if console is None:
        return
    clean = str(text or "").replace("\r", "\n")
    for line in clean.splitlines():
        if line.strip():
            console.appendPlainText(line.rstrip())
            try:
                self._claude_mcp_output.append(line.rstrip())
            except Exception:
                pass
    try:
        console.verticalScrollBar().setValue(console.verticalScrollBar().maximum())
    except Exception:
        pass


def _claude_mcp_state(self, text: str, *, value: int | None = None, busy: bool = False) -> None:
    label = getattr(self, "_claude_mcp_state_label", None)
    if label is not None:
        label.setText(text)
    progress = getattr(self, "_claude_mcp_progress", None)
    if progress is not None:
        if busy:
            progress.setRange(0, 0)
        else:
            progress.setRange(0, 100)
            if value is not None:
                progress.setValue(max(0, min(100, int(value))))


def _start_claude_mcp_auto_connect(self) -> None:
    self._open_claude_mcp_progress_dialog(title="Claude MCP ?깅줉")
    self._claude_mcp_state("Claude Code CLI瑜?李얜뒗 以묒엯?덈떎.", busy=True)
    self._claude_mcp_log("Claude MCP ?먮룞 ?곌껐???쒖옉?⑸땲??")
    cli = self._find_claude_cli()
    if not cli:
        self._claude_mcp_state("Claude Code CLI瑜?李얠쓣 ???놁뒿?덈떎.", value=0)
        self._claude_mcp_log("Claude Code CLI媛 PATH???놁뒿?덈떎. Claude Code瑜??ㅼ튂?????ㅼ떆 ?쒕룄?섏꽭??")
        self._claude_mcp_log("?ㅼ튂 ?꾩뿉??媛먯??섏? ?딆쑝硫??곕??먯뿉??`claude --version`???ㅽ뻾?섎뒗吏 ?뺤씤?섏꽭??")
        self._claude_mcp_finish_ui(close_enabled=True, cancel_enabled=False, success=False)
        return
    args = self._claude_mcp_add_args()
    self._claude_mcp_state("Tiger Studio MCP ?쒕쾭瑜?Claude???깅줉?섎뒗 以묒엯?덈떎.", busy=True)
    self._claude_mcp_log(f"Claude CLI 諛쒓껄: {cli}")
    self._claude_mcp_log("?ㅽ뻾: " + " ".join([cli, *args]))
    self._start_claude_mcp_process(cli, args, mode="add")


def _start_claude_mcp_status_check(self) -> None:
    self._open_claude_mcp_progress_dialog(title="Claude ?곌껐 ?곹깭 ?뺤씤")
    self._claude_mcp_state("Claude MCP ?깅줉 ?곹깭瑜??뺤씤?섎뒗 以묒엯?덈떎.", busy=True)
    self._claude_mcp_log("Claude MCP ?곹깭 ?뺤씤???쒖옉?⑸땲??")
    cli = self._find_claude_cli()
    if not cli:
        self._claude_mcp_state("Claude Code CLI瑜?李얠쓣 ???놁뒿?덈떎.", value=0)
        self._claude_mcp_log("Claude Code CLI媛 PATH???놁뒿?덈떎. Claude Code瑜??ㅼ튂?????ㅼ떆 ?쒕룄?섏꽭??")
        self._claude_mcp_finish_ui(close_enabled=True, cancel_enabled=False, success=False)
        return
    args = ["mcp", "list"]
    self._claude_mcp_log(f"?ㅽ뻾: {cli} {' '.join(args)}")
    self._start_claude_mcp_process(cli, args, mode="list")


def _start_claude_mcp_process(self, executable: str, args: list[str], *, mode: str) -> None:
    from app.subprocess_utils import configure_hidden_qprocess

    proc = QProcess(self)
    proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
    configure_hidden_qprocess(proc)
    proc.readyReadStandardOutput.connect(lambda p=proc: self._claude_mcp_read_output(p))
    proc.errorOccurred.connect(lambda _err, p=proc: self._claude_mcp_process_error(p))
    proc.finished.connect(lambda code, _status, p=proc, m=mode: self._claude_mcp_process_finished(p, m, code))
    self._claude_mcp_process = proc
    proc.start(executable, args)


def _claude_mcp_read_output(self, proc: QProcess) -> None:
    try:
        text = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace")
    except Exception:
        text = ""
    if text:
        self._claude_mcp_log(text)


def _claude_mcp_process_error(self, proc: QProcess) -> None:
    try:
        error_text = proc.errorString()
    except Exception:
        error_text = ""
    self._claude_mcp_log(f"Claude CLI ?ㅻ쪟: {error_text or 'process error'}")


def _claude_mcp_process_finished(self, proc: QProcess, mode: str, exit_code: int) -> None:
    self._claude_mcp_read_output(proc)
    if getattr(self, "_claude_mcp_process", None) is proc:
        self._claude_mcp_process = None
    output_text = "\n".join(getattr(self, "_claude_mcp_output", []) or [])
    lowered = output_text.casefold()
    if mode == "add":
        already_registered = "tiger-studio" in lowered and "already exists" in lowered
        if int(exit_code) == 0 or already_registered:
            try:
                from app.ai_providers import (
                    default_mcp_server_command,
                    save_ai_provider_preference,
                    save_claude_mcp_config,
                )

                save_claude_mcp_config(
                    enabled=True,
                    command=default_mcp_server_command(),
                    cli_command=self._find_claude_cli(),
                )
                save_ai_provider_preference("claude_mcp")
                self._refresh_ai_command_provider_status()
                self._refresh_ai_script_edit_provider_status()
            except Exception as exc:
                self._claude_mcp_log(f"?ㅼ젙 ????ㅽ뙣: {exc}")
            self._claude_mcp_state(
                "Claude MCP媛 ?대? ?깅줉?섏뼱 ?덉뒿?덈떎. Claude Code?먯꽌 /mcp瑜??댁뼱 tiger-studio瑜??뱀씤?섏꽭??"
                if already_registered
                else "Claude MCP ?깅줉 ?꾨즺. Claude Code?먯꽌 /mcp瑜??댁뼱 tiger-studio瑜??뱀씤?섏꽭??",
                value=100,
            )
            self._claude_mcp_log("?대? ?깅줉??tiger-studio MCP瑜??뺤씤?덉뒿?덈떎." if already_registered else "?깅줉???꾨즺?섏뿀?듬땲??")
            self._claude_mcp_log("?ㅼ쓬 ?④퀎: Claude Code ?곕??먯뿉??`/mcp`瑜??낅젰?섍퀬 tiger-studio瑜??뱀씤?섏꽭??")
            self._claude_mcp_finish_ui(close_enabled=True, cancel_enabled=False, success=True)
            try:
                self._flash_status("Claude MCP ?깅줉 ?뺤씤" if already_registered else "Claude MCP ?깅줉 ?꾨즺")
            except Exception:
                pass
            return
        self._claude_mcp_state("Claude MCP ?먮룞 ?깅줉???꾨즺?섏? 紐삵뻽?듬땲??", value=0)
        self._claude_mcp_log(f"Claude CLI 醫낅즺 肄붾뱶: {exit_code}")
        self._claude_mcp_log("?대? ?깅줉???대쫫 異⑸룎?닿굅??Claude CLI 濡쒓렇?몄씠 ?꾩슂?????덉뒿?덈떎. ?곹깭 ?뺤씤 ?먮뒗 ?곌껐 ?덈궡瑜??뺤씤?섏꽭??")
        self._claude_mcp_finish_ui(close_enabled=True, cancel_enabled=False, success=False)
        return
    if mode == "list":
        if int(exit_code) == 0 and "tiger-studio" in lowered:
            try:
                from app.ai_providers import default_mcp_server_command, save_claude_mcp_config

                save_claude_mcp_config(
                    enabled=True,
                    command=default_mcp_server_command(),
                    cli_command=self._find_claude_cli(),
                )
                self._refresh_ai_command_provider_status()
                self._refresh_ai_script_edit_provider_status()
            except Exception as exc:
                self._claude_mcp_log(f"?ㅼ젙 ????ㅽ뙣: {exc}")
            self._claude_mcp_state("Claude MCP媛 ?깅줉?섏뼱 ?덉뒿?덈떎. Claude?먯꽌 ?뱀씤 ?곹깭瑜??뺤씤?섏꽭??", value=100)
            self._claude_mcp_log("tiger-studio MCP ?깅줉???뺤씤?덉뒿?덈떎.")
            self._claude_mcp_finish_ui(close_enabled=True, cancel_enabled=False, success=True)
            return
        if int(exit_code) == 0:
            self._claude_mcp_state("Claude CLI???ㅽ뻾?먯?留?tiger-studio ?깅줉??李얠? 紐삵뻽?듬땲??", value=0)
            self._claude_mcp_log("?먮룞 ?곌껐???ㅽ뻾??tiger-studio MCP ?쒕쾭瑜??깅줉?섏꽭??")
        else:
            self._claude_mcp_state("Claude MCP ?곹깭 ?뺤씤???ㅽ뙣?덉뒿?덈떎.", value=0)
            self._claude_mcp_log(f"Claude CLI 醫낅즺 肄붾뱶: {exit_code}")
        self._claude_mcp_finish_ui(close_enabled=True, cancel_enabled=False, success=False)


def _claude_mcp_finish_ui(self, *, close_enabled: bool, cancel_enabled: bool, success: bool = False) -> None:
    title = getattr(self, "_claude_mcp_title_label", None)
    close_btn = getattr(self, "_claude_mcp_close_btn", None)
    cancel_btn = getattr(self, "_claude_mcp_cancel_btn", None)
    dialog = getattr(self, "_claude_mcp_dialog", None)
    if title is not None:
        title.setText("Claude connected" if success else "Claude connection needs attention")
    if close_btn is not None:
        close_btn.setEnabled(bool(close_enabled))
        close_btn.setText("Done - Close" if success else "Close")
        if close_enabled:
            close_btn.setDefault(True)
            close_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        if success:
            self._claude_mcp_start_close_attention()
        else:
            self._claude_mcp_stop_close_attention()
    if cancel_btn is not None:
        cancel_btn.setEnabled(bool(cancel_enabled))
        cancel_btn.setVisible(bool(cancel_enabled))
    if dialog is not None and close_enabled:
        dialog.raise_()
        dialog.activateWindow()


def _claude_mcp_start_close_attention(self) -> None:
    close_btn = getattr(self, "_claude_mcp_close_btn", None)
    if close_btn is None:
        return
    self._claude_mcp_stop_close_attention()

    def _apply(value: Any) -> None:
        pulse = float(value or 0.0)
        border_alpha = 150 + int(90 * pulse)
        close_btn.setStyleSheet(
            f"""
            QPushButton {{
                color: #FFFFFF;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #FF704F, stop:.55 #FF4EA8, stop:1 #765DFF);
                border: 2px solid rgba(255, 255, 255, {border_alpha});
                border-radius: 18px;
                padding: 10px 22px;
                font-weight: 950;
                font-size: 15px;
            }}
            """
        )

    anim = QVariantAnimation(close_btn)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setDuration(760)
    anim.setLoopCount(-1)
    anim.valueChanged.connect(_apply)
    anim.start()
    self._claude_mcp_close_anim = anim


def _claude_mcp_stop_close_attention(self) -> None:
    anim = getattr(self, "_claude_mcp_close_anim", None)
    if anim is not None:
        try:
            anim.stop()
            anim.deleteLater()
        except Exception:
            pass
    self._claude_mcp_close_anim = None
    close_btn = getattr(self, "_claude_mcp_close_btn", None)
    if close_btn is not None and close_btn.text() != "?꾨즺 - ?リ린":
        close_btn.setStyleSheet("")


def _claude_mcp_cancel(self) -> None:
    proc = getattr(self, "_claude_mcp_process", None)
    if proc is not None and proc.state() != QProcess.ProcessState.NotRunning:
        self._claude_mcp_log("?ъ슜?먭? Claude ?곌껐 ?묒뾽??痍⑥냼?덉뒿?덈떎.")
        self._shutdown_qwen_local_processes(reason="user_cancel")
    self._claude_mcp_state("痍⑥냼?덉뒿?덈떎.", value=0)
    self._claude_mcp_finish_ui(close_enabled=True, cancel_enabled=False, success=False)


def _generate_ai_command_plan(self) -> None:
    try:
        prompt = self._ai_command_input.text().strip()
    except Exception:
        prompt = ""
    provider_id = self._selected_ai_command_provider_id()
    if not prompt:
        self._ai_command_set_status("癒쇱? AI?먭쾶 吏?쒗븷 ?몄쭛 紐낅졊???낅젰?섏꽭??")
        return

    self._ai_command_append_chat("User", prompt)
    if self._handle_ai_command_status_prompt(prompt):
        return
    if provider_id == "claude_mcp":
        self._ai_command_append_chat(
            "Tiger Studio",
            "Claude Code ?곕??먮줈 ?섍퉩?덈떎. ?곕??먯뿉 遺숈뿬 ?ｊ퀬 Claude媛 EditPlan??留뚮뱾硫?Review?먯꽌 寃?좏븯?몄슂.",
        )
        self._ai_command_set_status("Claude CLI ?닿린: ?꾩옱 ?먮쭑/Review ?뚮옖? 諛붾줈 諛붽씀吏 ?딆뒿?덈떎.")
        self._launch_claude_code_terminal(initial_prompt=prompt)
        return
    action_plan = self._build_ai_command_action_plan_payload(prompt)
    if action_plan is not None:
        self._ai_command_action_plan = action_plan
        self._ai_script_edit_plan = None
        steps = len(action_plan.get("steps") or [])
        warnings = len(action_plan.get("warnings") or [])
        if steps:
            self._ai_command_append_chat(
                self._ai_command_selected_provider_name(),
                f"{action_plan.get('summary') or '?≪뀡 ?뚮옖'} Review?먯꽌 ?뺤씤 ???ㅽ뻾?섏꽭??",
            )
            status = f"Action plan ready: {steps} action(s)"
            if warnings:
                status += f"; warnings {warnings}"
            status += "; run from Review"
            self._ai_command_set_status(status)
        else:
            warning_text = " ".join(str(row) for row in list(action_plan.get("warnings") or [])).strip()
            self._ai_command_append_chat(
                "Tiger Studio",
                f"{action_plan.get('summary') or '?≪뀡 ?뚮옖??留뚮뱾吏 紐삵뻽?듬땲??'}"
                + (f" {warning_text}" if warning_text else ""),
            )
            self._ai_command_set_status(
                f"?≪뀡 ?ㅽ뻾 遺덇?: {action_plan.get('summary') or '?꾩슂????곸쓣 李얠쓣 ???놁뒿?덈떎.'}"
            )
        return
    self._ai_command_action_plan = None
    if provider_id == "local_llm":
        try:
            from app.ai_providers import ai_provider_readiness

            row = ai_provider_readiness().get("local_llm") or {}
            if not row.get("available"):
                self._open_local_llm_provider_setup_dialog()
                self._ai_command_set_status(
                    "濡쒖뺄 LLM ?ㅽ뻾 紐낅졊???꾩쭅 ?ㅼ젙?섏? ?딆븯?듬땲?? ?ㅼ젙 ?덈궡瑜??뺤씤?섏꽭??"
                )
                return
        except Exception:
            pass
    self._ai_command_set_status("AI ?몄쭛 ?뚮옖 ?앹꽦 以?..")
    try:
        from app.ai_script_edit_panel import ScriptEditPanelModel
        from app.ai_providers import generate_selected_provider_plan, provider_user_label

        transcript_text = self._ai_command_transcript_text(prompt, allow_prompt_fallback=False)
        def _fallback_ai_command_plan():
            try:
                from app.ltx_storyboard import (
                    build_ltx_storyboard_plan,
                    prompt_requests_storyboard,
                    storyboard_to_edit_plan,
                )

                if prompt_requests_storyboard(prompt):
                    snapshot = self._ai_project_snapshot()
                    summary = dict(snapshot.get("summary") or {})
                    duration_ms = int(snapshot.get("duration_ms", 0) or 0)
                    if duration_ms:
                        summary.setdefault("duration_s", duration_ms / 1000.0)
                    media_items = list(summary.get("media_items") or snapshot.get("media_pool") or [])
                    if media_items:
                        summary.setdefault("media_items", media_items)
                    storyboard = build_ltx_storyboard_plan(prompt, summary, media_items)
                    return storyboard_to_edit_plan(storyboard)
            except Exception:
                pass
            return self._ai_command_prompt_only_plan(prompt)

        panel = getattr(self, "_ai_script_edit_panel", None)
        provider_note = ""
        provider_note_is_failure = False
        if panel is not None:
            try:
                panel._prompt_input.setPlainText(prompt)
                provider_document = None
                if transcript_text:
                    panel._format_combo.setCurrentIndex(max(0, panel._format_combo.findData("srt")))
                    panel._transcript_input.setPlainText(transcript_text)
                    panel.model.import_transcript_text(
                        transcript_text,
                        source_format="srt",
                        language=current_language(),
                    )
                    panel._refresh_transcript_rows()
                    provider_document = panel.model.document
                if transcript_text and getattr(panel.model, "document", None) is not None:
                    plan = panel.model.generate_plan_from_prompt(prompt, **panel._collect_plan_kwargs())
                    provider_document = panel.model.document
                else:
                    clear_context = getattr(panel, "clear_transcript_context", None)
                    if callable(clear_context):
                        clear_context(clear_plan=False)
                    plan = _fallback_ai_command_plan()
                provider_result = generate_selected_provider_plan(prompt, plan, document=provider_document)
                if provider_result.ok and provider_result.plan is not None:
                    plan = provider_result.plan
                    provider_note = f"{provider_user_label(provider_result.provider)}媛 留뚮뱺 ?뚮옖"
                elif provider_result.provider != "rule_based":
                    provider_note = str(provider_result.reason or "").strip()
                    provider_note_is_failure = True
                panel.set_plan(plan)
            except Exception:
                model = ScriptEditPanelModel(language=current_language())
                provider_document = None
                if transcript_text:
                    model.import_transcript_text(transcript_text, source_format="srt", language=current_language())
                    plan = model.generate_plan_from_prompt(prompt)
                    provider_document = model.document
                else:
                    plan = _fallback_ai_command_plan()
                provider_result = generate_selected_provider_plan(prompt, plan, document=provider_document)
                if provider_result.ok and provider_result.plan is not None:
                    plan = provider_result.plan
                    provider_note = f"{provider_user_label(provider_result.provider)}媛 留뚮뱺 ?뚮옖"
                elif provider_result.provider != "rule_based":
                    provider_note = str(provider_result.reason or "").strip()
                    provider_note_is_failure = True
        else:
            model = ScriptEditPanelModel(language=current_language())
            provider_document = None
            if transcript_text:
                model.import_transcript_text(transcript_text, source_format="srt", language=current_language())
                plan = model.generate_plan_from_prompt(prompt)
                provider_document = model.document
            else:
                plan = _fallback_ai_command_plan()
            provider_result = generate_selected_provider_plan(prompt, plan, document=provider_document)
            if provider_result.ok and provider_result.plan is not None:
                plan = provider_result.plan
                provider_note = f"{provider_user_label(provider_result.provider)}媛 留뚮뱺 ?뚮옖"
            elif provider_result.provider != "rule_based":
                provider_note = str(provider_result.reason or "").strip()
                provider_note_is_failure = True

        self._on_ai_script_edit_plan_generated(plan)
        operations = len(getattr(plan, "operations", []) or [])
        resolved = str((getattr(plan, "metadata", {}) or {}).get("prompt_resolved_action") or getattr(plan, "intent", "") or "")
        provider_status = self._refresh_ai_command_provider_status()
        if provider_note:
            speaker = "Tiger Studio" if provider_note_is_failure else self._ai_command_selected_provider_name()
            message = (
                f"{provider_note} ????덉쟾??湲곕낯 ?뚮옖 {operations}媛쒕? 留뚮뱾?덉뒿?덈떎. Review?먯꽌 ?뺤씤?섍퀬 ?먰븯????ぉ留??곸슜?섏꽭??"
                if provider_note_is_failure
                else f"{provider_note}. ?묒뾽 {operations}媛쒕? 留뚮뱾?덉뒿?덈떎. Review?먯꽌 ?뺤씤?섍퀬 ?먰븯????ぉ留??곸슜?섏꽭??"
            )
            self._ai_command_append_chat(
                speaker,
                message,
            )
            self._ai_command_set_status(
                f"Plan ready: {operations} action(s); {provider_note}; review before applying"
            )
        else:
            ai_reply = (
                f"{resolved or '?붿껌'} ?묒뾽?쇰줈 ?댁꽍?덉뒿?덈떎. ?묒뾽 {operations}媛쒕? 留뚮뱾?덇퀬, Review?먯꽌 泥댄겕 ???곸슜?????덉뒿?덈떎."
            )
            self._ai_command_append_chat(self._ai_command_selected_provider_name(), ai_reply)
            status = f"Plan ready: {operations} action(s)"
            if resolved:
                status += f"; {resolved}"
            status += f"; {provider_status}; review before applying"
            self._ai_command_set_status(status)
    except Exception as exc:
        self._ai_command_append_chat("AI", f"?뚮옖??留뚮뱾吏 紐삵뻽?듬땲?? {exc}")
        self._ai_command_set_status(f"AI ?뚮옖 ?앹꽦 ?ㅽ뙣: {exc}")


def _open_ai_action_review_dialog(self, payload: dict) -> None:
    dialog = getattr(self, "_ai_action_review_dialog", None)
    if dialog is not None and dialog.isVisible():
        view = getattr(self, "_ai_action_review_text", None)
        if view is not None:
            view.setPlainText(self._format_ai_action_plan_text(payload))
        dialog.raise_()
        dialog.activateWindow()
        return

    dialog = QDialog(self)
    dialog.setObjectName("AIActionReviewDialog")
    dialog.setWindowTitle("AI Action Review")
    dialog.setMinimumSize(720, 520)
    dialog.setStyleSheet(
        """
        QDialog#AIActionReviewDialog {
            background: #080B13;
            color: #F8FAFF;
        }
        QLabel#AIActionReviewTitle {
            color: #FFFFFF;
            font-size: 18px;
            font-weight: 950;
        }
        QLabel#AIActionReviewSubtitle {
            color: rgba(239, 243, 255, 205);
            font-size: 12px;
            font-weight: 760;
        }
        QPlainTextEdit#AIActionReviewText {
            background: #111621;
            border: 1px solid rgba(140, 150, 206, 95);
            border-radius: 12px;
            color: #F8FAFF;
            padding: 10px;
        }
        """
    )

    root = QVBoxLayout(dialog)
    root.setContentsMargins(14, 14, 14, 14)
    root.setSpacing(10)

    title = QLabel("AI Action Review", dialog)
    title.setObjectName("AIActionReviewTitle")
    root.addWidget(title)
    subtitle = QLabel(
        "紐낇솗???몄쭛 紐낅졊? Python Action Registry濡??ㅽ뻾?⑸땲?? ?ㅽ뻾 ??dry-run 寃곌낵瑜??뺤씤?섏꽭??",
        dialog,
    )
    subtitle.setObjectName("AIActionReviewSubtitle")
    subtitle.setWordWrap(True)
    root.addWidget(subtitle)

    text = QPlainTextEdit(dialog)
    text.setObjectName("AIActionReviewText")
    text.setReadOnly(True)
    text.setPlainText(self._format_ai_action_plan_text(payload))
    root.addWidget(text, stretch=1)

    buttons = QHBoxLayout()
    buttons.setSpacing(8)
    buttons.addStretch(1)
    close_btn = QPushButton("?リ린", dialog)
    close_btn.setObjectName("ToolButton")
    run_btn = QPushButton("?≪뀡 ?ㅽ뻾", dialog)
    run_btn.setObjectName("PrimaryButton")
    steps = list(payload.get("steps") or [])
    preview = payload.get("preview") if isinstance(payload.get("preview"), dict) else {}
    run_btn.setEnabled(bool(steps) and bool(preview.get("ok", True)))

    def _run_actions() -> None:
        result = self._execute_ai_command_action_plan(payload)
        text.setPlainText(self._format_ai_action_plan_text(payload, result=result))
        run_btn.setEnabled(False)

    run_btn.clicked.connect(_run_actions)
    close_btn.clicked.connect(dialog.close)
    buttons.addWidget(close_btn)
    buttons.addWidget(run_btn)
    root.addLayout(buttons)

    self._ai_action_review_dialog = dialog
    self._ai_action_review_text = text
    dialog.finished.connect(lambda *_args: self._clear_ai_action_review_dialog(dialog))
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


def _apply_ai_script_edit_cuts(self, operation_ids=None) -> None:
    plan = self._current_ai_script_edit_plan()
    if plan is None:
        self._flash_status("Script Edit: generate a plan before applying cuts")
        return
    ok, validation = self._validate_ai_script_edit_plan(plan, operation_ids=operation_ids, destructive_apply=True)
    if not ok:
        blocked = ", ".join((validation or {}).get("blocked") or ["validation failed"])
        self._flash_status(f"Script Edit cuts blocked: {blocked}")
        return
    from app.ai_edit_apply import (
        apply_ai_script_cut_intents_to_tracks,
        build_ai_script_apply_payload,
    )

    result = build_ai_script_apply_payload(plan, operation_ids=operation_ids)
    payload = dict(result.payload or {})
    cut_intents = list(payload.get("cut_intents") or [])
    if not cut_intents:
        self._flash_status("Script Edit: selected plan has no cut ranges")
        return
    locked = [
        int(getattr(track, "id", -1))
        for track in getattr(self, "_tracks", []) or []
        if bool(getattr(track, "locked", False)) and bool(getattr(track, "clips", None))
    ]
    if locked:
        self._flash_status(f"Script Edit cuts blocked: locked track {locked[0]}")
        return
    apply_result = apply_ai_script_cut_intents_to_tracks(
        getattr(self, "_tracks", []) or [],
        getattr(self, "_audio_tracks", []) or [],
        cut_intents,
    )
    if not apply_result.get("ok"):
        self._store_ai_script_edit_payload(
            payload,
            {**result.to_dict(), "cut_materialize_result": dict(apply_result)},
        )
        self._flash_status("Script Edit cuts: no matching timeline range")
        return
    for row in getattr(self, "_track_rows", {}).values():
        try:
            if hasattr(row, "_recalc_width"):
                row._recalc_width()
            row.update()
        except Exception:
            pass
    for track in getattr(self, "_audio_tracks", []) or []:
        row = getattr(self, "_audio_rows", {}).get(int(getattr(track, "id", -1)))
        if row is not None:
            try:
                row.update()
            except Exception:
                pass
        try:
            self._audio_mixer.update_track(track)
        except Exception:
            pass
    self._refresh_player_tracks()
    self._update_tracks_host_width()
    try:
        self._update_timeline_status()
    except Exception:
        pass
    self._sync_ai_script_applied_cut_markers(apply_result)
    self._store_ai_script_edit_payload(
        payload,
        {**result.to_dict(), "cut_materialize_result": dict(apply_result)},
    )
    self._register_change("AI Script Edit ripple cuts")
    self._log_ai_script_action(
        "ai_script_apply_materialized_cuts",
        {
            "plan_id": str(getattr(plan, "id", "") or ""),
            "provider": str(getattr(plan, "provider", "") or ""),
            "operation_ids": list(operation_ids or []) if operation_ids is not None else None,
            "result": result.to_dict(),
            "cut_materialize_result": dict(apply_result),
            "validation": validation,
        },
    )
    self._flash_status(
        "Script Edit cuts applied: "
        f"{len(apply_result.get('applied_ranges') or [])} range(s), "
        f"{int(apply_result.get('removed_ms', 0) or 0)} ms removed"
    )


def _open_local_llm_provider_setup_dialog(self) -> None:
        try:
            from app.ai_providers import (
                ai_provider_readiness,
                save_ai_provider_preference,
                save_local_llm_provider_config,
                saved_local_llm_config,
            )

            current = str(saved_local_llm_config().get("command") or "").strip()
        except Exception as exc:
            QMessageBox.warning(self, "濡쒖뺄 LLM ?ㅼ젙", f"濡쒖뺄 LLM ?ㅼ젙??遺덈윭?????놁뒿?덈떎.\n{exc}")
            return

        command, ok = QInputDialog.getText(
            self,
            "濡쒖뺄 LLM ?ㅼ젙",
            "EditPlan JSON??stdout?쇰줈 諛섑솚?섎뒗 濡쒖뺄 LLM ?ㅽ뻾 紐낅졊:",
            QLineEdit.EchoMode.Normal,
            current,
        )
        if not ok:
            return
        command = str(command or "").strip()
        if not command:
            QMessageBox.information(
                self,
                "濡쒖뺄 LLM ?ㅼ젙",
                "?ㅽ뻾 紐낅졊??鍮꾩뼱 ?덉뒿?덈떎. 濡쒖뺄 LLM???ъ슜?섎젮硫?runner 紐낅졊???낅젰?댁빞 ?⑸땲??",
            )
            return

        saved = save_local_llm_provider_config(command=command)
        try:
            save_ai_provider_preference("local_llm")
        except Exception:
            pass
        self._refresh_ai_command_provider_status()

        if not saved:
            QMessageBox.warning(self, "濡쒖뺄 LLM ?ㅼ젙", "?ㅽ뻾 紐낅졊???ㅼ젙????ν븯吏 紐삵뻽?듬땲??")
            return

        row = {}
        try:
            row = ai_provider_readiness().get("local_llm") or {}
        except Exception:
            row = {}

        if row.get("available"):
            message = "濡쒖뺄 LLM ?ㅽ뻾 紐낅졊????ν뻽怨?吏湲덈???AI Plan ?앹꽦???ъ슜?????덉뒿?덈떎."
            QMessageBox.information(self, "濡쒖뺄 LLM ?곌껐 ?꾨즺", message)
            self._ai_command_set_status(message)
        else:
            message = (
                "?ㅽ뻾 紐낅졊? ??ν뻽吏留??꾩옱 ?ㅽ뻾 ?뚯씪??李얠쓣 ???놁뒿?덈떎. "
                "紐낅졊??泥?踰덉㎏ ?ㅽ뻾 ?뚯씪 寃쎈줈 ?먮뒗 PATH ?깅줉???뺤씤?섏꽭??"
            )
            QMessageBox.warning(self, "濡쒖뺄 LLM ?뺤씤 ?꾩슂", message)
            self._ai_command_set_status(message)


def _apply_ai_script_edit_plan(self, operation_ids=None) -> None:
        plan = self._current_ai_script_edit_plan()
        if plan is None:
            self._flash_status("Script Edit: generate a plan before applying")
            return
        ok, validation = self._validate_ai_script_edit_plan(plan, operation_ids=operation_ids, destructive_apply=False)
        if not ok:
            blocked = ", ".join((validation or {}).get("blocked") or ["validation failed"])
            self._flash_status(f"Script Edit apply blocked: {blocked}")
            return
        from app.ai_edit_apply import build_ai_script_apply_payload

        result = build_ai_script_apply_payload(plan, operation_ids=operation_ids)
        payload = dict(result.payload or {})
        subtitle_count = self._apply_ai_script_subtitles(payload.get("subtitle_rows") or [])
        marker_count = self._apply_ai_script_markers(payload.get("timeline_markers") or [])
        queue_result = self._stage_ai_script_render_jobs(payload) if payload.get("render_queue_jobs") else {"added": 0, "skipped": 0}
        auto_zoom_count = self._apply_ai_script_auto_suggestions(payload)
        self._sync_ai_script_preview_markers(payload)
        self._store_ai_script_edit_payload(payload, result.to_dict())

        if subtitle_count:
            try:
                self._update_subtitle_overlay(self._player.position())
            except Exception:
                pass
        changed = any(
            (
                subtitle_count,
                marker_count,
                int(queue_result.get("added", 0) or 0),
                auto_zoom_count,
                len(payload.get("cut_intents") or []),
                len(payload.get("short_candidates") or []),
                len(payload.get("sidecars") or []),
            )
        )
        if changed:
            self._register_change("AI Script Edit apply")
        self._log_ai_script_action(
            "ai_script_apply_review_safe",
            {
                "plan_id": str(getattr(plan, "id", "") or ""),
                "provider": str(getattr(plan, "provider", "") or ""),
                "operation_ids": list(operation_ids or []) if operation_ids is not None else None,
                "result": result.to_dict(),
                "validation": validation,
            },
        )
        warning_count = len(result.warnings)
        cut_count = len(payload.get("cut_intents") or [])
        self._flash_status(
            f"Script Edit apply: subtitles {subtitle_count}, markers {marker_count}, "
            f"queue {int(queue_result.get('added', 0) or 0)}, auto zoom {auto_zoom_count}, "
            f"review cuts {cut_count}, warnings {warning_count}"
        )


def _remove_ai_script_preview_markers(self) -> list[dict]:
        kept: list[dict] = []
        for marker in list(getattr(self, "_timeline_markers", []) or []):
            if not isinstance(marker, dict):
                continue
            if str(marker.get("source") or "") in {"ai_script_preview", "ai_script_applied_cut"}:
                continue
            kept.append(marker)
        return kept


def _sync_ai_script_preview_markers(self, payload: dict | None = None) -> int:
        payload = dict(payload or {})
        markers = self._remove_ai_script_preview_markers()
        added = 0
        for idx, cut in enumerate(payload.get("cut_intents") or [], start=1):
            if not isinstance(cut, dict):
                continue
            start_ms = max(0, int(cut.get("start_ms", 0) or 0))
            end_ms = max(start_ms + 1, int(cut.get("end_ms", start_ms + 1) or start_ms + 1))
            label = str(cut.get("text") or cut.get("reason") or f"AI cut {idx}")
            markers.append(
                {
                    "ms": start_ms,
                    "end_ms": end_ms,
                    "color": "#FF5F57",
                    "label": f"AI Cut: {label[:40]}",
                    "id": str(cut.get("id") or f"ai-script-preview-cut-{idx}"),
                    "source": "ai_script_preview",
                    "kind": "cut_range",
                }
            )
            added += 1
        for idx, candidate in enumerate(payload.get("short_candidates") or [], start=1):
            if not isinstance(candidate, dict):
                continue
            start_ms = max(0, int(candidate.get("start_ms", 0) or 0))
            end_ms = max(start_ms + 1, int(candidate.get("end_ms", start_ms + 1) or start_ms + 1))
            label = str(candidate.get("label") or candidate.get("text") or f"Short {idx}")
            markers.append(
                {
                    "ms": start_ms,
                    "end_ms": end_ms,
                    "color": "#FFB454",
                    "label": f"AI Short: {label[:40]}",
                    "id": str(candidate.get("id") or f"ai-script-preview-short-{idx}"),
                    "source": "ai_script_preview",
                    "kind": "short_candidate",
                }
            )
            added += 1
        if self._ai_script_auto_zoom_sidecars(payload):
            markers.append(
                {
                    "ms": self._first_ai_script_video_start_ms(),
                    "color": "#8A7CFF",
                    "label": "AI Auto Zoom suggestions",
                    "id": f"ai-script-preview-auto-zoom-{payload.get('plan_id') or 'latest'}",
                    "source": "ai_script_preview",
                    "kind": "auto_zoom_suggestion",
                }
            )
            added += 1
        self._timeline_markers = sorted(markers, key=lambda marker: int(marker.get("ms", 0) or 0))
        self._sync_markers_to_ruler()
        return added


# Extracted VideoEditorWindow AI command/provider helpers.
def _open_ai_command_review_panel(self) -> None:
    prompt = ""
    try:
        prompt = self._ai_command_input.text().strip()
    except Exception:
        prompt = ""
    if self._selected_ai_command_provider_id() == "claude_mcp":
        if prompt:
            self._ai_command_append_chat(
                "Tiger Studio",
                "Claude Code ?곕??먯쓣 ?쎈땲?? Review??Claude媛 留뚮뱺 EditPlan??寃?좏븷 ?뚮쭔 ?ъ슜?⑸땲??",
            )
            self._ai_command_set_status("Claude CLI ?닿린: ?곕??먯뿉??Claude? ??뷀븯?몄슂.")
            self._launch_claude_code_terminal(initial_prompt=prompt)
        else:
            self._ai_command_set_status("Claude CLI??蹂대궪 紐낅졊???낅젰?섍굅??Claude ?곌껐 ?ㅼ젙???뺤씤?섏꽭??")
            self._open_claude_provider_setup_dialog()
        return
    action_plan = self._current_ai_command_action_plan(prompt)
    plan = self._current_ai_script_edit_plan()
    plan_prompt = ""
    try:
        plan_prompt = str((getattr(plan, "metadata", {}) or {}).get("prompt_text") or "").strip()
    except Exception:
        plan_prompt = ""
    if prompt and action_plan is None and (plan is None or plan_prompt != prompt):
        try:
            self._generate_ai_command_plan()
        except Exception:
            pass
        action_plan = self._current_ai_command_action_plan(prompt)
        plan = self._current_ai_script_edit_plan()
    try:
        self._set_collapsible_host_open(getattr(self, "_ai_script_edit_section_host", None), False)
    except Exception:
        pass
    if action_plan is not None:
        self._open_ai_action_review_dialog(action_plan)
        self._ai_command_set_status("?≪뀡 寃??李쎌쓣 ?댁뿀?듬땲?? ?뺤씤 ???ㅽ뻾?섏꽭??")
        return
    self._open_ai_script_review_dialog(prompt=prompt, plan=plan)
    self._ai_command_set_status("寃??李쎌쓣 ?댁뿀?듬땲?? ?곸슜????ぉ??泥댄겕?섍퀬 ?곸슜 踰꾪듉???꾨Ⅴ?몄슂.")


def _prime_ai_review_panel(self, panel: QWidget, *, prompt: str = "", plan=None) -> None:
    if panel is None:
        return
    try:
        if prompt:
            panel._prompt_input.setPlainText(prompt)
    except Exception:
        pass
    try:
        transcript_text = self._ai_command_transcript_text(prompt, allow_prompt_fallback=False) if prompt else ""
        if transcript_text:
            panel._format_combo.setCurrentIndex(max(0, panel._format_combo.findData("srt")))
            panel._transcript_input.setPlainText(transcript_text)
            if getattr(panel.model, "document", None) is None:
                panel.model.import_transcript_text(
                    transcript_text,
                    source_format="srt",
                    language=current_language(),
                )
                panel._refresh_transcript_rows()
        else:
            clear_context = getattr(panel, "clear_transcript_context", None)
            if callable(clear_context):
                clear_context(clear_plan=False)
    except Exception:
        pass
    try:
        if plan is not None:
            panel.set_plan(plan)
    except Exception:
        pass


def _current_ai_command_action_plan(self, prompt: str = "") -> dict | None:
    payload = getattr(self, "_ai_command_action_plan", None)
    if not isinstance(payload, dict):
        return None
    if prompt and str(payload.get("prompt") or "").strip() != str(prompt or "").strip():
        return None
    return payload


def _ensure_python_action_registry(self):
    from app.video_editor_automation_facade import _ensure_python_action_registry

    return _ensure_python_action_registry(self)


def _run_review_scenario(self, scenario: str, params: dict | None = None) -> dict:
    from app.review_automation.live_runner import run_live_review_scenario

    return run_live_review_scenario(self, str(scenario or ""), params or {})


def _build_ai_command_action_plan_payload(self, prompt: str) -> dict | None:
    try:
        from app.ai_action_command import build_ai_action_command_plan

        snapshot = self._ai_project_snapshot()
        plan = build_ai_action_command_plan(prompt, snapshot)
        if plan is None:
            return None
        payload = plan.to_dict()
        payload["snapshot_hash"] = str(snapshot.get("snapshot_hash") or "")
        steps = list(payload.get("steps") or [])
        if steps:
            registry = self._ensure_python_action_registry()
            payload["preview"] = registry.execute_sequence(steps, dry_run=True)
        else:
            payload["preview"] = {
                "ok": False,
                "failed_index": -1,
                "results": [],
                "message": "?ㅽ뻾???≪뀡???놁뒿?덈떎.",
            }
        return payload
    except Exception as exc:
        return {
            "prompt": str(prompt or ""),
            "summary": "?≪뀡 ?뚮옖??留뚮뱾吏 紐삵뻽?듬땲??",
            "steps": [],
            "warnings": [str(exc)],
            "confidence": 0.0,
            "source": "rule_based_action_router",
            "preview": {"ok": False, "results": [], "message": str(exc)},
        }


def _format_ai_action_plan_text(self, payload: dict, *, result: dict | None = None) -> str:
    lines: list[str] = []
    lines.append(str(payload.get("summary") or "?≪뀡 ?뚮옖"))
    warnings = [str(row) for row in list(payload.get("warnings") or []) if str(row).strip()]
    if warnings:
        lines.append("")
        lines.append("二쇱쓽:")
        lines.extend(f"- {row}" for row in warnings)
    steps = list(payload.get("steps") or [])
    lines.append("")
    lines.append(f"Actions: {len(steps)}")
    if not steps:
        lines.append("- No executable actions.")
    for index, step in enumerate(steps, 1):
        action = str(step.get("action") or "")
        params = step.get("params") if isinstance(step.get("params"), dict) else {}
        try:
            params_text = json.dumps(params, ensure_ascii=False, sort_keys=True)
        except Exception:
            params_text = str(params)
        lines.append(f"{index}. {action}")
        lines.append(f"   {params_text}")
    preview = payload.get("preview") if isinstance(payload.get("preview"), dict) else {}
    if preview:
        lines.append("")
        lines.append(f"?ъ쟾 寃利?{'?듦낵' if preview.get('ok') else '?뺤씤 ?꾩슂'}")
        for row in list(preview.get("results") or []):
            action = str(row.get("action") or "")
            ok = "OK" if row.get("ok") else "FAIL"
            error = str(row.get("error") or "")
            suffix = f" - {error}" if error else ""
            lines.append(f"- {ok} {action}{suffix}")
    if result is not None:
        lines.append("")
        lines.append(f"?ㅽ뻾 寃곌낵: {'?꾨즺' if result.get('ok') else '?ㅽ뙣'}")
        for row in list(result.get("results") or []):
            action = str(row.get("action") or "")
            ok = "OK" if row.get("ok") else "FAIL"
            error = str(row.get("error") or "")
            suffix = f" - {error}" if error else ""
            lines.append(f"- {ok} {action}{suffix}")
    return "\n".join(lines)


def _execute_ai_command_action_plan(self, payload: dict) -> dict:
    steps = [dict(step) for step in list(payload.get("steps") or []) if isinstance(step, dict)]
    if not steps:
        result = {"ok": False, "failed_index": -1, "results": [], "message": "?ㅽ뻾???≪뀡???놁뒿?덈떎."}
        self._ai_command_set_status("?ㅽ뻾??AI ?≪뀡???놁뒿?덈떎.")
        return result
    try:
        registry = self._ensure_python_action_registry()
        result = registry.execute_sequence(steps, dry_run=False, confirm_destructive=False)
        payload["last_result"] = result
        if result.get("ok"):
            try:
                self._refresh_player_tracks()
                self._update_tracks_host_width()
                self._update_timeline_status()
            except Exception:
                pass
            self._ai_command_append_chat("Tiger Studio", f"?≪뀡 {len(steps)}媛쒕? ?ㅽ뻾?덉뒿?덈떎.")
            self._ai_command_set_status(f"AI action complete: {len(steps)} step(s)")
        else:
            failed = result.get("failed_index")
            self._ai_command_append_chat("Tiger Studio", f"?≪뀡 ?ㅽ뻾 以?{failed}踰??④퀎?먯꽌 ?ㅽ뙣?덉뒿?덈떎.")
            self._ai_command_set_status("AI ?≪뀡 ?ㅽ뻾 ?ㅽ뙣: Review 寃곌낵瑜??뺤씤?섏꽭??")
        return result
    except Exception as exc:
        result = {"ok": False, "failed_index": -1, "results": [], "message": str(exc)}
        self._ai_command_append_chat("Tiger Studio", f"?≪뀡 ?ㅽ뻾 ?ㅽ뙣: {exc}")
        self._ai_command_set_status(f"AI ?≪뀡 ?ㅽ뻾 ?ㅽ뙣: {exc}")
        return result


def _clear_ai_action_review_dialog(self, dialog: QDialog) -> None:
    if getattr(self, "_ai_action_review_dialog", None) is dialog:
        self._ai_action_review_dialog = None
        self._ai_action_review_text = None


def _clear_ai_review_dialog(self, dialog: QDialog) -> None:
    if getattr(self, "_ai_review_dialog", None) is dialog:
        self._ai_review_dialog = None
        self._ai_review_panel = None


def _ai_command_set_status(self, message: str) -> None:
    label = getattr(self, "_ai_command_status", None)
    if label is not None:
        label.setText(str(message or ""))
    self._refresh_ai_command_provider_status()
    try:
        self._flash_status(str(message or "AI Command updated"))
    except Exception:
        pass


def _ai_command_append_chat(self, speaker: str, message: str) -> None:
    chat = getattr(self, "_ai_command_chat_log", None)
    if chat is None:
        return
    clean_speaker = str(speaker or "AI").strip()
    clean_message = " ".join(str(message or "").strip().split())
    if not clean_message:
        return
    try:
        if chat.toPlainText().strip():
            chat.appendPlainText("")
        chat.appendPlainText(f"{clean_speaker}: {clean_message}")
        chat.verticalScrollBar().setValue(chat.verticalScrollBar().maximum())
    except Exception:
        pass


def _ai_command_selected_provider_name(self) -> str:
    try:
        from app.ai_providers import provider_user_label

        return provider_user_label(self._selected_ai_command_provider_id())
    except Exception:
        return "AI"


def _on_ai_command_provider_changed(self, *_args) -> None:
    if getattr(self, "_ai_command_provider_loading", False):
        return
    combo = getattr(self, "_ai_command_provider_combo", None)
    provider_id = ""
    if combo is not None and combo.currentIndex() >= 0:
        provider_id = str(combo.currentData() or "")
    try:
        from app.ai_providers import save_ai_provider_preference

        if provider_id:
            save_ai_provider_preference(provider_id)
    except Exception:
        pass
    self._refresh_ai_command_provider_status()
    if provider_id == "claude_mcp":
        try:
            from app.ai_providers import ai_provider_readiness

            row = ai_provider_readiness().get("claude_mcp") or {}
            if not row.get("available") and not getattr(self, "_claude_mcp_prompted", False):
                self._claude_mcp_prompted = True
                QTimer.singleShot(0, self._open_claude_provider_setup_dialog)
        except Exception:
            pass


def _selected_ai_command_provider_id(self) -> str:
    combo = getattr(self, "_ai_command_provider_combo", None)
    if combo is not None and combo.currentIndex() >= 0:
        value = combo.currentData()
        if value:
            return str(value)
    try:
        from app.ai_providers import selected_ai_provider_id

        return selected_ai_provider_id()
    except Exception:
        return "qwen_local"


def _open_ai_provider_setup_dialog(self) -> None:
    self._open_ai_provider_setup_for_id(self._selected_ai_command_provider_id())


def _open_ai_provider_setup_for_id(self, provider_id: str) -> None:
    provider_id = str(provider_id or "").strip() or self._selected_ai_command_provider_id()
    if provider_id == "qwen_local":
        self._open_qwen_provider_setup_dialog()
        return
    if provider_id == "claude_mcp":
        self._open_claude_provider_setup_dialog()
        self._refresh_ai_script_edit_provider_status()
        return
    if provider_id == "local_llm":
        self._open_local_llm_provider_setup_dialog()
        self._refresh_ai_script_edit_provider_status()
        return
    self._show_ai_provider_instructions(provider_id)


def _refresh_ai_script_edit_provider_status(self) -> None:
    for panel in (
        getattr(self, "_ai_script_edit_panel", None),
        getattr(self, "_ai_review_panel", None),
    ):
        if panel is None:
            continue
        try:
            panel._refresh_provider_status()
        except Exception:
            pass


def _show_ai_provider_instructions(self, provider_id: str) -> None:
    try:
        from app.ai_providers import provider_setup_instructions

        info = provider_setup_instructions(provider_id)
    except Exception as exc:
        info = {
            "title": "AI ?곌껐 ?덈궡",
            "summary": "AI ?곌껐 ?덈궡瑜?遺덈윭?ㅼ? 紐삵뻽?듬땲??",
            "body": str(exc),
        }
    message = QMessageBox(self)
    message.setWindowTitle(str(info.get("title") or "AI ?곌껐 ?덈궡"))
    message.setIcon(QMessageBox.Icon.Information)
    message.setText(str(info.get("summary") or "?좏깮??AI ?곌껐 諛⑸쾿?낅땲??"))
    message.setInformativeText(str(info.get("body") or ""))
    details = [
        str(value)
        for key, value in info.items()
        if key not in {"title", "summary", "body", "primary_action"} and value
    ]
    if details:
        message.setDetailedText("\n".join(details))
    message.exec()


def _open_qwen_provider_setup_dialog(self) -> None:
    try:
        from app.ai_providers import provider_setup_instructions, qwen_install_plan, saved_qwen_config

        info = provider_setup_instructions("qwen_local")
        plan = qwen_install_plan()
        saved = saved_qwen_config()
    except Exception as exc:
        QMessageBox.warning(self, "湲곕낯 臾대즺 AI", f"?ㅼ튂 ?덈궡瑜?遺덈윭?ㅼ? 紐삵뻽?듬땲??\n{exc}")
        return
    message = QMessageBox(self)
    message.setWindowTitle("湲곕낯 臾대즺 AI ?ㅼ튂")
    message.setIcon(QMessageBox.Icon.Information)
    message.setText(str(info.get("summary") or "湲곕낯 臾대즺 AI瑜??ㅼ튂?섍굅???곌껐?⑸땲??"))
    current = []
    if saved.get("endpoint"):
        current.append(f"??λ맂 ?쒕쾭: {saved.get('endpoint')}")
    if saved.get("model_path"):
        current.append(f"??λ맂 紐⑤뜽: {saved.get('model_path')}")
    body = str(info.get("body") or "")
    if current:
        body = f"{body}\n\n?꾩옱 ?ㅼ젙\n" + "\n".join(current)
    message.setInformativeText(body)
    message.setDetailedText(
        "\n".join(
            [
                f"Model: {plan.get('model_ref')}",
                f"Model page: {plan.get('model_page')}",
                f"Server: {plan.get('server_command')}",
                f"Endpoint: {plan.get('endpoint')}",
                f"Windows install: {plan.get('windows_install_command')}",
            ]
        )
    )
    install_btn = message.addButton("臾대즺 AI ?ㅼ튂", QMessageBox.ButtonRole.ActionRole)
    endpoint_btn = message.addButton("Copy endpoint", QMessageBox.ButtonRole.ActionRole)
    model_btn = message.addButton("紐⑤뜽 ?뚯씪 ?좏깮", QMessageBox.ButtonRole.ActionRole)
    guide_btn = message.addButton("?곌껐 ?덈궡", QMessageBox.ButtonRole.HelpRole)
    message.addButton(QMessageBox.StandardButton.Close)
    message.exec()
    clicked = message.clickedButton()
    if clicked is install_btn:
        self._start_default_free_ai_install()
    elif clicked is endpoint_btn:
        self._save_qwen_endpoint_from_dialog()
    elif clicked is model_btn:
        self._choose_qwen_model_path()
    elif clicked is guide_btn:
        self._show_ai_provider_instructions("qwen_local")


def _start_default_free_ai_install(self) -> None:
    self._open_qwen_install_progress_dialog()
    QTimer.singleShot(0, self._qwen_install_begin)


def _open_qwen_install_progress_dialog(self) -> None:
    dialog = getattr(self, "_qwen_install_dialog", None)
    if dialog is not None and dialog.isVisible():
        dialog.raise_()
        dialog.activateWindow()
        return
    dialog = QDialog(self)
    dialog.setWindowTitle("湲곕낯 臾대즺 AI ?ㅼ튂")
    dialog.setMinimumSize(680, 420)
    dialog.setObjectName("QwenInstallDialog")
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(10)

    title = QLabel("湲곕낯 臾대즺 AI瑜??ㅼ튂?섍퀬 ?곌껐?⑸땲??", dialog)
    title.setObjectName("DialogTitle")
    title.setWordWrap(True)
    layout.addWidget(title)
    self._qwen_install_title_label = title

    state = QLabel("以鍮?以?..", dialog)
    state.setWordWrap(True)
    layout.addWidget(state)

    progress = QProgressBar(dialog)
    progress.setRange(0, 0)
    progress.setTextVisible(True)
    layout.addWidget(progress)

    console = QPlainTextEdit(dialog)
    console.setReadOnly(True)
    console.setMinimumHeight(210)
    console.setPlaceholderText("?ㅼ튂 濡쒓렇媛 ?ш린???쒖떆?⑸땲??")
    layout.addWidget(console, stretch=1)

    button_row = QHBoxLayout()
    button_row.addStretch(1)
    cancel_btn = QPushButton("痍⑥냼", dialog)
    close_btn = QPushButton("?リ린", dialog)
    close_btn.setEnabled(False)
    close_btn.setDefault(True)
    cancel_btn.clicked.connect(self._qwen_install_cancel)
    close_btn.clicked.connect(dialog.close)
    button_row.addWidget(cancel_btn)
    button_row.addWidget(close_btn)
    layout.addLayout(button_row)

    self._qwen_install_dialog = dialog
    self._qwen_install_state_label = state
    self._qwen_install_progress = progress
    self._qwen_install_console = console
    self._qwen_install_cancel_btn = cancel_btn
    self._qwen_install_close_btn = close_btn
    self._qwen_install_process = None
    self._qwen_install_probe_count = 0
    self._qwen_install_runner_command = ""
    self._qwen_install_close_anim = None
    dialog.finished.connect(lambda *_args: self._qwen_install_stop_close_attention())
    dialog.show()


def _qwen_install_log(self, text: str) -> None:
    console = getattr(self, "_qwen_install_console", None)
    if console is None:
        return
    clean = str(text or "").replace("\r", "\n")
    for line in clean.splitlines():
        if line.strip():
            console.appendPlainText(line.rstrip())
    try:
        console.verticalScrollBar().setValue(console.verticalScrollBar().maximum())
    except Exception:
        pass


def _qwen_install_state(self, text: str, *, value: int | None = None, busy: bool = False) -> None:
    label = getattr(self, "_qwen_install_state_label", None)
    if label is not None:
        label.setText(text)
    progress = getattr(self, "_qwen_install_progress", None)
    if progress is not None:
        if busy:
            progress.setRange(0, 0)
        else:
            progress.setRange(0, 100)
            if value is not None:
                progress.setValue(max(0, min(100, int(value))))


def _qwen_install_cached_model_path(self) -> str:
    cache_root = Path.home() / ".cache" / "huggingface" / "hub" / "models--Qwen--Qwen3-1.7B-GGUF"
    if not cache_root.exists():
        return ""
    candidates: list[Path] = []
    for root_name in ("snapshots", "blobs"):
        root = cache_root / root_name
        if not root.exists():
            continue
        try:
            for path in root.rglob("*"):
                if path.is_file() and (path.suffix.casefold() == ".gguf" or path.stat().st_size > 500_000_000):
                    candidates.append(path)
        except Exception:
            continue
    if not candidates:
        return ""
    try:
        candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    except Exception:
        pass
    return str(candidates[0])


def _qwen_install_runner_candidates(self, names: tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    paths: list[str] = []
    for name in names:
        path = shutil.which(name)
        if path and path not in seen:
            seen.add(path)
            paths.append(path)
    package_root = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if package_root.exists():
        for package_dir in package_root.glob("ggml.llamacpp_*"):
            for name in names:
                path = package_dir / name
                if path.exists():
                    text = str(path)
                    if text not in seen:
                        seen.add(text)
                        paths.append(text)
    return paths


def _qwen_install_find_runner(self) -> tuple[str, list[str], str]:
    try:
        from app.ai_providers import qwen_install_plan

        plan = qwen_install_plan()
        model_ref = str(plan.get("model_ref") or "")
    except Exception:
        model_ref = "Qwen/Qwen3-1.7B-GGUF:Q8_0"
    cached_model = self._qwen_install_cached_model_path()
    model_args = ["-m", cached_model] if cached_model else ["-hf", model_ref]
    common_args = ["--host", "127.0.0.1", "--port", "8080", "--alias", "qwen3-1.7b-q8"]
    model_command = " ".join(model_args + common_args)
    for path in self._qwen_install_runner_candidates(("llama-server", "llama-server.exe")):
        args = model_args + common_args
        return path, args, f'"{path}" {model_command}'
    for path in self._qwen_install_runner_candidates(("llama", "llama.exe")):
        args = ["serve"] + model_args + common_args
        return path, args, f'"{path}" serve {model_command}'
    return "", [], ""


def _qwen_install_begin(self) -> None:
    self._qwen_install_log("湲곕낯 臾대즺 AI ?ㅼ튂瑜??쒖옉?⑸땲??")
    runner, args, runner_command = self._qwen_install_find_runner()
    if runner:
        self._qwen_install_runner_command = runner_command
        self._qwen_install_log(f"llama.cpp 諛쒓껄: {runner}")
        self._qwen_install_start_server(runner, args, runner_command)
        return
    winget = shutil.which("winget")
    if not winget:
        self._qwen_install_state("llama.cpp? winget??李얠쓣 ???놁뒿?덈떎.", value=0)
        self._qwen_install_log("?먮룞 ?ㅼ튂瑜?吏꾪뻾?????놁뒿?덈떎. llama.cpp瑜??ㅼ튂?섍굅??濡쒖뺄 ?쒕쾭 二쇱냼瑜?吏곸젒 ??ν븯?몄슂.")
        self._qwen_install_finish_ui(close_enabled=True, cancel_enabled=False, success=False)
        return
    self._qwen_install_start_winget(winget)


def _qwen_install_start_winget(self, winget: str) -> None:
    from app.subprocess_utils import configure_hidden_qprocess

    self._qwen_install_state("llama.cpp ?ㅼ튂 以묒엯?덈떎. ?ㅼ튂 濡쒓렇瑜??뺤씤?섏꽭??", busy=True)
    self._qwen_install_log(f"winget ?ㅽ뻾: {winget} install llama.cpp")
    proc = QProcess(self)
    proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
    configure_hidden_qprocess(proc)
    proc.readyReadStandardOutput.connect(lambda p=proc: self._qwen_install_read_output(p))
    proc.errorOccurred.connect(lambda _err, p=proc: self._qwen_install_process_error(p, "winget"))
    proc.finished.connect(lambda code, _status, p=proc: self._qwen_install_winget_finished(p, code))
    self._qwen_install_process = proc
    proc.start(
        winget,
        [
            "install",
            "llama.cpp",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ],
    )


def _qwen_install_winget_finished(self, proc: QProcess, exit_code: int) -> None:
    self._qwen_install_read_output(proc)
    self._qwen_install_process = None
    if int(exit_code) != 0:
        self._qwen_install_state("llama.cpp ?ㅼ튂媛 ?꾨즺?섏? ?딆븯?듬땲??", value=0)
        self._qwen_install_log(f"winget 醫낅즺 肄붾뱶: {exit_code}")
        self._qwen_install_finish_ui(close_enabled=True, cancel_enabled=False, success=False)
        return
    self._qwen_install_state("llama.cpp ?ㅼ튂 ?꾨즺. Qwen ?쒕쾭 ?쒖옉??以鍮꾪빀?덈떎.", value=45)
    self._qwen_install_log("winget ?ㅼ튂媛 ?꾨즺?섏뿀?듬땲?? ?ㅼ튂??runner瑜?李얜뒗 以묒엯?덈떎.")
    QTimer.singleShot(800, self._qwen_install_start_server_after_install)


def _qwen_install_start_server_after_install(self) -> None:
    runner, args, runner_command = self._qwen_install_find_runner()
    if not runner:
        self._qwen_install_state("?ㅼ튂???앸궗吏留??꾩옱 ?꾨줈?몄뒪?먯꽌 llama 紐낅졊??李얠쓣 ???놁뒿?덈떎.", value=45)
        self._qwen_install_log("Windows PATH 諛섏쁺????쓣 ???덉뒿?덈떎. ?깆쓣 ?ㅼ떆 ?닿굅???쒕쾭 二쇱냼瑜?吏곸젒 ??ν븯?몄슂.")
        self._qwen_install_finish_ui(close_enabled=True, cancel_enabled=False, success=False)
        return
    self._qwen_install_runner_command = runner_command
    self._qwen_install_start_server(runner, args, runner_command)


def _qwen_install_start_server(self, runner: str, args: list[str], runner_command: str) -> None:
    from app.subprocess_utils import configure_hidden_qprocess

    existing = getattr(self, "_qwen_server_process", None)
    if existing is not None and existing.state() != QProcess.ProcessState.NotRunning:
        self._qwen_install_log("Qwen ?쒕쾭媛 ?대? ?ㅽ뻾 以묒엯?덈떎. ?곌껐 ?곹깭瑜??뺤씤?⑸땲??")
        self._qwen_install_probe_count = 0
        self._qwen_install_probe_server()
        return
    self._qwen_install_state("Qwen ?쒕쾭 ?쒖옉 以묒엯?덈떎. 泥섏쓬 ?ㅽ뻾?섎㈃ 紐⑤뜽 ?ㅼ슫濡쒕뱶媛 吏꾪뻾?⑸땲??", busy=True)
    self._qwen_install_log(f"?쒕쾭 ?ㅽ뻾: {runner_command}")
    proc = QProcess(self)
    proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
    configure_hidden_qprocess(proc)
    proc.readyReadStandardOutput.connect(lambda p=proc: self._qwen_install_server_output(p))
    proc.errorOccurred.connect(lambda _err, p=proc: self._qwen_install_process_error(p, "Qwen server"))
    proc.finished.connect(lambda code, _status, p=proc: self._qwen_install_server_finished(p, code))
    self._qwen_server_process = proc
    self._qwen_install_process = proc
    proc.start(runner, args)
    self._qwen_install_probe_count = 0
    QTimer.singleShot(1800, self._qwen_install_probe_server)


def _qwen_install_read_output(self, proc: QProcess) -> None:
    try:
        text = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace")
    except Exception:
        text = ""
    if text:
        self._qwen_install_log(text)


def _qwen_install_server_output(self, proc: QProcess) -> None:
    self._qwen_install_read_output(proc)
    QTimer.singleShot(500, self._qwen_install_probe_server)


def _qwen_install_process_error(self, proc: QProcess, label: str) -> None:
    try:
        error_text = proc.errorString()
    except Exception:
        error_text = ""
    self._qwen_install_log(f"{label} ?ㅻ쪟: {error_text or 'process error'}")


def _qwen_install_server_finished(self, proc: QProcess, exit_code: int) -> None:
    self._qwen_install_read_output(proc)
    if getattr(self, "_qwen_server_process", None) is proc:
        self._qwen_server_process = None
    if getattr(self, "_qwen_install_process", None) is proc:
        self._qwen_install_process = None
    if int(exit_code) != 0:
        self._qwen_install_state("Qwen ?쒕쾭媛 醫낅즺?섏뿀?듬땲??", value=70)
        self._qwen_install_log(f"Qwen ?쒕쾭 醫낅즺 肄붾뱶: {exit_code}")
        self._qwen_install_finish_ui(close_enabled=True, cancel_enabled=False, success=False)


def _shutdown_qwen_local_processes(self, *, reason: str = "editor_close", timeout_ms: int = 1200) -> None:
    processes = []
    for attr in ("_qwen_install_process", "_qwen_server_process"):
        proc = getattr(self, attr, None)
        if proc is not None and all(proc is not existing for existing in processes):
            processes.append(proc)
    if not processes:
        return
    for proc in processes:
        try:
            if proc.state() == QProcess.ProcessState.NotRunning:
                continue
        except Exception:
            continue
        try:
            self._qwen_install_log(f"Qwen local process shutdown: {reason}")
        except Exception:
            pass
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            if not proc.waitForFinished(max(100, int(timeout_ms))):
                proc.kill()
                proc.waitForFinished(500)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    for attr in ("_qwen_install_process", "_qwen_server_process"):
        if getattr(self, attr, None) in processes:
            setattr(self, attr, None)


def _qwen_install_probe_server(self) -> None:
    try:
        import urllib.request

        from app.ai_providers import (
            QWEN_DEFAULT_ENDPOINT,
            QWEN_LOCAL_PROVIDER_ID,
            qwen_install_plan,
            save_ai_provider_preference,
            save_qwen_provider_config,
        )

        plan = qwen_install_plan()
        endpoint = str(plan.get("endpoint") or QWEN_DEFAULT_ENDPOINT).rstrip("/")
        probe_url = f"{endpoint}/models" if endpoint.endswith("/v1") else f"{endpoint}/v1/models"
        with urllib.request.urlopen(probe_url, timeout=0.9) as response:
            if 200 <= int(getattr(response, "status", 200)) < 500:
                save_qwen_provider_config(
                    endpoint=endpoint,
                    runner_command=str(getattr(self, "_qwen_install_runner_command", "") or plan.get("server_command") or ""),
                )
                save_ai_provider_preference(QWEN_LOCAL_PROVIDER_ID)
                self._refresh_ai_command_provider_status()
                self._refresh_ai_script_edit_provider_status()
                self._qwen_install_state("?꾨즺?섏뿀?듬땲?? ?リ린瑜??뚮윭 ?먮뵒?곕줈 ?뚯븘媛?몄슂.", value=100)
                self._qwen_install_log(f"?곌껐 ?뺤씤: {probe_url}")
                self._qwen_install_log("?ㅼ튂 諛??곌껐???꾨즺?섏뿀?듬땲?? ?댁젣 ?レ븘???⑸땲??")
                self._qwen_install_finish_ui(close_enabled=True, cancel_enabled=False, success=True)
                try:
                    self._flash_status("湲곕낯 臾대즺 AI ?곌껐 ?꾨즺")
                except Exception:
                    pass
                return
    except Exception:
        pass
    proc = getattr(self, "_qwen_server_process", None)
    if proc is None or proc.state() == QProcess.ProcessState.NotRunning:
        return
    count = int(getattr(self, "_qwen_install_probe_count", 0) or 0) + 1
    self._qwen_install_probe_count = count
    if count in {1, 5, 15}:
        self._qwen_install_log("?쒕쾭 ?묐떟??湲곕떎由щ뒗 以묒엯?덈떎. 泥??ㅽ뻾?대㈃ 紐⑤뜽 ?ㅼ슫濡쒕뱶 ?뚮Ц???ㅻ옒 嫄몃┫ ???덉뒿?덈떎.")
    if count < 240:
        QTimer.singleShot(1500, self._qwen_install_probe_server)
    else:
        self._qwen_install_state("?쒕쾭???ㅽ뻾 以묒씠吏留??묐떟 ?뺤씤???ㅻ옒 嫄몃━怨??덉뒿?덈떎.", value=75)
        self._qwen_install_log("?ㅼ슫濡쒕뱶媛 怨꾩냽 吏꾪뻾 以묒씠硫???李쎌쓣 ?댁뼱 ?먭퀬 濡쒓렇瑜??뺤씤?섏꽭??")


def _qwen_install_finish_ui(self, *, close_enabled: bool, cancel_enabled: bool, success: bool = False) -> None:
    title = getattr(self, "_qwen_install_title_label", None)
    close_btn = getattr(self, "_qwen_install_close_btn", None)
    cancel_btn = getattr(self, "_qwen_install_cancel_btn", None)
    dialog = getattr(self, "_qwen_install_dialog", None)
    if title is not None:
        title.setText("湲곕낯 臾대즺 AI ?ㅼ튂 諛??곌껐 ?꾨즺" if success else "湲곕낯 臾대즺 AI ?ㅼ튂媛 以묐떒?섏뿀?듬땲??")
    if close_btn is not None:
        close_btn.setEnabled(bool(close_enabled))
        close_btn.setText("?꾨즺 - ?リ린" if success else "?リ린")
        if close_enabled:
            close_btn.setDefault(True)
            close_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        if success:
            self._qwen_install_start_close_attention()
        else:
            self._qwen_install_stop_close_attention()
    if cancel_btn is not None:
        cancel_btn.setEnabled(bool(cancel_enabled))
        cancel_btn.setVisible(bool(cancel_enabled))
    if dialog is not None and close_enabled:
        dialog.raise_()
        dialog.activateWindow()


def _qwen_install_start_close_attention(self) -> None:
    close_btn = getattr(self, "_qwen_install_close_btn", None)
    if close_btn is None:
        return
    self._qwen_install_stop_close_attention()

    def _apply(value: Any) -> None:
        pulse = float(value or 0.0)
        border_alpha = 150 + int(90 * pulse)
        glow_alpha = 75 + int(70 * pulse)
        close_btn.setStyleSheet(
            f"""
            QPushButton {{
                color: #FFFFFF;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #FF704F, stop:.55 #FF4EA8, stop:1 #765DFF);
                border: 2px solid rgba(255, 255, 255, {border_alpha});
                border-radius: 18px;
                padding: 10px 22px;
                font-weight: 950;
                font-size: 15px;
            }}
            QPushButton:hover {{
                border: 2px solid rgba(255, 255, 255, 255);
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #FF8567, stop:.55 #FF61B2, stop:1 #8A7CFF);
            }}
            QPushButton:focus {{
                outline: none;
                border: 3px solid rgba(255, 255, 255, {glow_alpha});
            }}
            """
        )

    anim = QVariantAnimation(close_btn)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setDuration(760)
    anim.setLoopCount(-1)
    anim.valueChanged.connect(_apply)
    anim.start()
    self._qwen_install_close_anim = anim


def _qwen_install_stop_close_attention(self) -> None:
    anim = getattr(self, "_qwen_install_close_anim", None)
    if anim is not None:
        try:
            anim.stop()
            anim.deleteLater()
        except Exception:
            pass
    self._qwen_install_close_anim = None
    close_btn = getattr(self, "_qwen_install_close_btn", None)
    if close_btn is not None and close_btn.text() != "?꾨즺 - ?リ린":
        close_btn.setStyleSheet("")


def _qwen_install_cancel(self) -> None:
    proc = getattr(self, "_qwen_install_process", None)
    if proc is not None and proc.state() != QProcess.ProcessState.NotRunning:
        self._qwen_install_log("?ъ슜?먭? ?ㅼ튂/?쒖옉 ?묒뾽??痍⑥냼?덉뒿?덈떎.")
        proc.terminate()
        QTimer.singleShot(1200, lambda p=proc: p.kill() if p.state() != QProcess.ProcessState.NotRunning else None)
    self._qwen_install_state("痍⑥냼?섏뿀?듬땲??", value=0)
    self._qwen_install_finish_ui(close_enabled=True, cancel_enabled=False, success=False)


def _save_qwen_endpoint_from_dialog(self) -> None:
    try:
        from app.ai_providers import (
            QWEN_DEFAULT_ENDPOINT,
            QWEN_LOCAL_PROVIDER_ID,
            save_ai_provider_preference,
            save_qwen_provider_config,
            saved_qwen_config,
        )

        saved = saved_qwen_config()
        default = saved.get("endpoint") or QWEN_DEFAULT_ENDPOINT
        endpoint, ok = QInputDialog.getText(
            self,
            "湲곕낯 臾대즺 AI ?쒕쾭",
            "OpenAI ?명솚 濡쒖뺄 ?쒕쾭 二쇱냼",
            QLineEdit.EchoMode.Normal,
            default,
        )
        if not ok:
            return
        endpoint = str(endpoint or "").strip()
        if not endpoint:
            return
        save_qwen_provider_config(endpoint=endpoint)
        save_ai_provider_preference(QWEN_LOCAL_PROVIDER_ID)
        self._refresh_ai_command_provider_status()
        self._refresh_ai_script_edit_provider_status()
        QMessageBox.information(self, "湲곕낯 臾대즺 AI", f"?쒕쾭 二쇱냼瑜???ν뻽?듬땲??\n{endpoint}")
    except Exception as exc:
        QMessageBox.warning(self, "湲곕낯 臾대즺 AI", f"?쒕쾭 二쇱냼瑜???ν븯吏 紐삵뻽?듬땲??\n{exc}")


def _choose_qwen_model_path(self) -> None:
    try:
        from app.ai_providers import QWEN_LOCAL_PROVIDER_ID, save_ai_provider_preference, save_qwen_provider_config

        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Qwen GGUF 紐⑤뜽 ?뚯씪 ?좏깮",
            str(Path.home()),
            "GGUF Model (*.gguf);;All Files (*)",
        )
        if not path:
            directory = QFileDialog.getExistingDirectory(self, "Qwen 紐⑤뜽 ?대뜑 ?좏깮", str(Path.home()))
            path = directory or ""
        if not path:
            return
        save_qwen_provider_config(model_path=path)
        save_ai_provider_preference(QWEN_LOCAL_PROVIDER_ID)
        self._refresh_ai_command_provider_status()
        self._refresh_ai_script_edit_provider_status()
        QMessageBox.information(
            self,
            "湲곕낯 臾대즺 AI",
            "紐⑤뜽 ?꾩튂瑜???ν뻽?듬땲??\nrunner 紐낅졊 ?먮뒗 濡쒖뺄 ?쒕쾭 二쇱냼源뚯? ?곌껐?섎㈃ 湲곕낯 臾대즺 AI濡??ъ슜?????덉뒿?덈떎.",
        )
    except Exception as exc:
        QMessageBox.warning(self, "湲곕낯 臾대즺 AI", f"紐⑤뜽 ?꾩튂瑜???ν븯吏 紐삵뻽?듬땲??\n{exc}")


def _ai_command_format_srt_ms(ms: int) -> str:
    value = max(0, int(ms or 0))
    seconds, millis = divmod(value, 1000)
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02d}:{minute:02d}:{sec:02d},{millis:03d}"


def _ai_command_transcript_text(self, prompt: str = "", *, allow_prompt_fallback: bool = False) -> str:
    rows: list[str] = []
    panel = getattr(self, "_subtitle_panel", None)
    if panel is not None:
        try:
            subtitles = list(panel.subtitles())
        except Exception:
            subtitles = []
        for idx, sub in enumerate(subtitles, start=1):
            text = " ".join(str(getattr(sub, "text", "") or "").split())
            if not text:
                continue
            start_ms = max(0, int(getattr(sub, "start_ms", 0) or 0))
            end_ms = max(start_ms + 1, int(getattr(sub, "end_ms", start_ms + 1000) or start_ms + 1000))
            rows.append(
                f"{idx}\n"
                f"{self._ai_command_format_srt_ms(start_ms)} --> {self._ai_command_format_srt_ms(end_ms)}\n"
                f"{text}"
            )
    if rows:
        return "\n\n".join(rows)
    if not allow_prompt_fallback:
        return ""

    duration_ms = 30_000
    try:
        duration_ms = max(3_000, int(self._player.duration() or duration_ms))
    except Exception:
        pass
    end_ms = max(3_000, min(duration_ms, 45_000))
    clean_prompt = " ".join(str(prompt or "AI ?몄쭛 ?뚮옖").split()) or "AI ?몄쭛 ?뚮옖"
    return (
        "1\n"
        f"{self._ai_command_format_srt_ms(0)} --> {self._ai_command_format_srt_ms(end_ms)}\n"
        f"{clean_prompt}"
    )


def _ai_command_prompt_only_plan(self, prompt: str, *, reason: str = ""):
    from app.ai_edit_plan import EditPlan

    clean_prompt = " ".join(str(prompt or "").split()) or "AI ?몄쭛 紐낅졊"
    warning = (
        reason
        or "?蹂??먮쭑 援ш컙???놁뼱 ?꾨줈?앺듃瑜??먮쭑 湲곗??쇰줈 諛붽씀吏 ?딆뒿?덈떎. AI provider媛 吏곸젒 ?댁꽍?섎㈃ ?묒뾽???앹꽦?섍퀬, ?꾨땲硫?寃?좎슜 鍮??뚮옖?쇰줈 ?〓땲??"
    )
    return EditPlan(
        id="ai_command_prompt_only_review",
        intent="prompt_only_edit_request",
        summary=f"AI 紐낅졊 寃???湲? {clean_prompt}",
        operations=(),
        warnings=(warning,),
        requires_review=True,
        quality_score=45,
        metadata={
            "prompt_text": clean_prompt,
            "prompt_mode": "command_only",
            "transcript_required": False,
            "fallback_used": True,
        },
    )


def _handle_ai_command_status_prompt(self, prompt: str) -> bool:
    try:
        from app.ai_providers import (
            ai_provider_readiness,
            is_ai_provider_status_prompt,
            provider_state_label,
            provider_user_label,
        )

        provider_id = self._selected_ai_command_provider_id()
        if not is_ai_provider_status_prompt(prompt, provider_id):
            return False
        statuses = ai_provider_readiness()
        row = statuses.get(provider_id) or {}
        label = provider_user_label(provider_id)
        state = provider_state_label(row)
        if provider_id == "claude_mcp":
            if row.get("available"):
                reply = (
                    "Claude Code ?곕???諛⑹떇?쇰줈 ?ъ슜?????덉뒿?덈떎. "
                    "`Claude CLI ?닿린`瑜??꾨Ⅴ硫?Tiger Studio ?묒뾽 ?대뜑?먯꽌 Claude Code瑜??닿퀬, ?낅젰??紐낅졊怨??쒖옉 ?덈궡瑜??④퍡 ?꾨떖?⑸땲?? "
                    "?곕??먯뿉??/mcp濡?tiger-studio ?곌껐???뺤씤?섏꽭??"
                )
            else:
                reply = (
                    "Claude Code ?곕????곌껐???꾩쭅 以鍮꾨릺吏 ?딆븯?듬땲?? "
                    "?ㅼ젙 踰꾪듉???뚮윭 Claude Code ?곕????닿린 ?먮뒗 MCP ?깅줉???ㅽ뻾?섏꽭??"
                )
        else:
            reason = str(row.get("reason") or "").strip()
            if row.get("setup_state") == "executor_failed":
                reply = f"{label} ?곹깭: {state}. 留덉?留?吏곸젒 ?몄텧???ㅽ뙣?덉뒿?덈떎. {reason or '?쒕쾭瑜??ㅼ떆 ?쒖옉?섍굅???곌껐???뺤씤?섏꽭??'}"
            elif row.get("available") and row.get("executor_wired"):
                reply = f"{label} ?곹깭: {state}. ?몄쭛 紐낅졊??吏곸젒 ?댁꽍?????덉뒿?덈떎."
            elif row.get("available"):
                reply = f"{label} ?곹깭: {state}. ?곌껐? 蹂댁씠吏留?吏곸젒 ?뚮옖 ?앹꽦? ?꾩쭅 以鍮꾨릺吏 ?딆븯?듬땲??"
            else:
                reply = f"{label} ?곹깭: {state}. {reason or '?ㅼ젙???꾩슂?⑸땲??'}"
        self._ai_command_append_chat("Tiger Studio", reply)
        self._ai_command_set_status(reply)
        return True
    except Exception as exc:
        self._ai_command_append_chat("Tiger Studio", f"?곌껐 ?곹깭瑜??뺤씤?섏? 紐삵뻽?듬땲?? {exc}")
        self._ai_command_set_status(f"AI ?곌껐 ?곹깭 ?뺤씤 ?ㅽ뙣: {exc}")
        return True


def _ensure_ai_script_edit_panel(self) -> list[QWidget]:
    panel = getattr(self, "_ai_script_edit_panel", None)
    if panel is not None:
        return [panel]
    try:
        from app.ai_script_edit_panel import ScriptEditPanel

        host = getattr(self, "_ai_script_edit_section_host", None)
        panel = ScriptEditPanel(host)
        try:
            panel.set_external_provider_setup_handler(self._open_ai_provider_setup_for_id)
        except Exception:
            pass
        panel.plan_generated.connect(self._on_ai_script_edit_plan_generated)
        panel.preview_requested.connect(self._on_ai_script_edit_plan_generated)
        panel.apply_selected_requested.connect(self._apply_ai_script_edit_selected)
        panel.apply_all_requested.connect(self._apply_ai_script_edit_all)
        panel.apply_cuts_requested.connect(self._apply_ai_script_edit_cuts)
        self._ai_script_edit_panel = panel

        placeholder = getattr(self, "_ai_script_edit_placeholder", None)
        layout = host.layout() if host is not None else None
        if layout is not None and placeholder is not None:
            layout.replaceWidget(placeholder, panel)
            placeholder.hide()
            placeholder.setParent(None)
            placeholder.deleteLater()
        elif layout is not None:
            layout.addWidget(panel, stretch=1)
        panel.setVisible(True)
        return [panel]
    except Exception as exc:
        self._flash_status(f"Script Edit load failed: {exc}")
        placeholder = getattr(self, "_ai_script_edit_placeholder", None)
        return [placeholder] if placeholder is not None else []


def _open_ai_script_edit_panel(self) -> None:
    self._set_screenstudio_advanced_visible(True, persist=True, quiet=True)
    loaded = self._ensure_ai_script_edit_panel()
    self._set_collapsible_host_open(getattr(self, "_ai_script_edit_section_host", None), True)
    for widget in loaded or []:
        try:
            widget.setVisible(True)
            widget.raise_()
        except Exception:
            pass
    try:
        self._flash_status("AI Script Edit opened")
    except Exception:
        pass


def _ai_project_snapshot(self) -> dict:
    try:
        from app.ai_project_snapshot import build_project_snapshot_from_editor

        return build_project_snapshot_from_editor(self)
    except Exception as exc:
        return {
            "schema_version": 1,
            "source": "TigerCapture",
            "duration_ms": 0,
            "video_tracks": [],
            "audio_tracks": [],
            "subtitles": [],
            "markers": [],
            "media_pool": [],
            "selected_clips": [],
            "locks": {"locked_video_track_ids": [], "locked_audio_track_ids": []},
            "summary": {},
            "snapshot_hash": "",
            "error": str(exc),
        }


def _log_ai_script_action(self, action: str, payload: dict | None = None) -> None:
    try:
        from app.ai_action_log import append_ai_action_log

        append_ai_action_log(action, payload or {})
    except Exception:
        pass


def _validate_ai_script_edit_plan(self, plan, operation_ids=None, *, destructive_apply: bool = False):
    snapshot = self._ai_project_snapshot()
    try:
        from app.ai_plan_validation import validate_edit_plan_for_snapshot

        validation = validate_edit_plan_for_snapshot(
            plan,
            snapshot,
            operation_ids=operation_ids,
            destructive_apply=destructive_apply,
        )
    except Exception as exc:
        validation = None
        self._ai_script_edit_validation = {
            "ok": False,
            "blocked": [str(exc)],
            "warnings": [],
            "dry_run": {"snapshot_hash": str(snapshot.get("snapshot_hash") or "")},
        }
        self._log_ai_script_action(
            "ai_script_validate_failed",
            {
                "plan_id": str(getattr(plan, "id", "") or ""),
                "error": str(exc),
                "snapshot_hash": str(snapshot.get("snapshot_hash") or ""),
            },
        )
        return False, self._ai_script_edit_validation
    data = validation.to_dict()
    self._ai_script_edit_snapshot = snapshot
    self._ai_script_edit_validation = data
    self._log_ai_script_action(
        "ai_script_validate",
        {
            "plan_id": str(getattr(plan, "id", "") or ""),
            "provider": str(getattr(plan, "provider", "") or ""),
            "destructive_apply": bool(destructive_apply),
            "operation_ids": list(operation_ids or []) if operation_ids is not None else None,
            "validation": data,
            "snapshot_hash": str(snapshot.get("snapshot_hash") or ""),
        },
    )
    return bool(validation.ok), data


def _ensure_automation_registry(self):
    from app.video_editor_automation_facade import _ensure_automation_registry

    return _ensure_automation_registry(self)


def automation_command_specs(self) -> list[dict]:
    from app.video_editor_automation_facade import automation_command_specs

    return automation_command_specs(self)


def automation_execute_command(self, command: str, params: dict | None = None, *, dry_run: bool = False) -> dict:
    from app.video_editor_automation_facade import automation_execute_command

    return automation_execute_command(self, command, params, dry_run=dry_run)


def automation_bridge_handle(self, request) -> dict:
    from app.video_editor_automation_facade import automation_bridge_handle

    return automation_bridge_handle(self, request)


def automation_mcp_handle(self, message) -> dict | None:
    from app.video_editor_automation_facade import automation_mcp_handle

    return automation_mcp_handle(self, message)


def _on_ai_script_edit_plan_generated(self, plan) -> None:
    if plan is None:
        return
    self._ai_script_edit_plan = plan
    ok, validation = self._validate_ai_script_edit_plan(plan)
    try:
        from app.ai_edit_apply import build_ai_script_apply_payload

        self._sync_ai_script_preview_markers(
            dict(build_ai_script_apply_payload(plan).payload or {})
        )
    except Exception:
        pass
    try:
        operations = len(getattr(plan, "operations", []) or [])
        warnings = len(getattr(plan, "warnings", []) or [])
        blocked = len((validation or {}).get("blocked") or [])
        suffix = f", blocked {blocked}" if blocked else ""
        self._flash_status(f"Script Edit plan ready: {operations} op(s), {warnings} warning(s){suffix}")
    except Exception:
        self._flash_status("Script Edit plan ready")
    self._log_ai_script_action(
        "ai_script_plan_generated",
        {
            "plan_id": str(getattr(plan, "id", "") or ""),
            "provider": str(getattr(plan, "provider", "") or ""),
            "ok": bool(ok),
            "validation": validation,
        },
    )


def _current_ai_script_edit_plan(self):
    panel = getattr(self, "_ai_script_edit_panel", None)
    plan = None
    if panel is not None and hasattr(panel, "current_plan"):
        try:
            plan = panel.current_plan()
        except Exception:
            plan = None
    if plan is None:
        plan = getattr(self, "_ai_script_edit_plan", None)
    return plan


def _apply_ai_script_edit_selected(self, operation_ids=None) -> None:
    self._apply_ai_script_edit_plan(operation_ids=operation_ids)


def _apply_ai_script_edit_all(self) -> None:
    self._apply_ai_script_edit_plan(operation_ids=None)


def _apply_ai_script_subtitles(self, rows) -> int:
    rows = [row for row in rows if isinstance(row, dict)]
    if not rows or not hasattr(self, "_subtitle_panel"):
        return 0
    layer = self._subtitle_panel.layer
    existing = {
        (
            int(getattr(sub, "start_ms", 0) or 0),
            int(getattr(sub, "end_ms", 0) or 0),
            " ".join(str(getattr(sub, "text", "") or "").split()).casefold(),
        )
        for sub in layer.items()
    }
    added = 0
    for row in rows:
        text = " ".join(str(row.get("text", "") or "").split())
        if not text:
            continue
        start_ms = max(0, int(row.get("start_ms", 0) or 0))
        end_ms = max(start_ms + 500, int(row.get("end_ms", start_ms + 1800) or start_ms + 1800))
        key = (start_ms, end_ms, text.casefold())
        if key in existing:
            continue
        style = dict(row.get("style") or {})
        preset_id = str(row.get("style_preset_id") or style.get("preset_id") or "caption-capcut-word-pop")
        style["preset_id"] = preset_id
        style.setdefault("source", "ai_script_edit")
        style.setdefault("word_highlight", bool(row.get("word_highlight", "word" in preset_id or "karaoke" in preset_id)))
        layer.add(Subtitle(start_ms=start_ms, end_ms=end_ms, text=text, show_box=bool(row.get("show_box", True)), style=style))
        existing.add(key)
        added += 1
    if added:
        self._subtitle_panel._refresh_list()
        if hasattr(self, "_subtitle_lane"):
            self._subtitle_lane.update()
        try:
            self._subtitle_panel_toggle_btn.setChecked(True)
        except Exception:
            pass
    return added


def _apply_ai_script_markers(self, rows) -> int:
    rows = [row for row in rows if isinstance(row, dict)]
    if not rows:
        return 0
    markers = list(getattr(self, "_timeline_markers", []) or [])
    existing = {
        (
            int(marker.get("ms", 0) or 0),
            str(marker.get("id") or marker.get("label") or ""),
        )
        for marker in markers
        if isinstance(marker, dict)
    }
    added = 0
    for row in rows:
        start_ms = max(0, int(row.get("ms", row.get("start_ms", 0)) or 0))
        label = str(row.get("label") or row.get("id") or "AI Script Marker")
        marker_id = str(row.get("id") or f"ai-script-marker-{start_ms}-{added + 1}")
        key = (start_ms, marker_id or label)
        if key in existing:
            continue
        marker = dict(row)
        marker["ms"] = start_ms
        marker["label"] = label
        marker["id"] = marker_id
        marker.setdefault("color", "#8A7CFF")
        marker.setdefault("source", "ai_script_edit")
        markers.append(marker)
        existing.add(key)
        added += 1
    if added:
        self._timeline_markers = sorted(markers, key=lambda marker: int(marker.get("ms", 0) or 0))
        self._sync_markers_to_ruler()
    return added


def _ai_script_auto_zoom_sidecars(self, payload: dict | None) -> list[dict]:
    return [
        dict(row)
        for row in list((payload or {}).get("sidecars") or [])
        if isinstance(row, dict) and str(row.get("type") or "") == "add_auto_zoom"
    ]


def _apply_ai_script_auto_suggestions(self, payload: dict | None = None) -> int:
    sidecars = self._ai_script_auto_zoom_sidecars(payload)
    if not sidecars:
        return 0
    try:
        from app.screenstudio_polish import screenstudio_polish_preset
    except Exception:
        return 0
    intent = str((payload or {}).get("plan_intent") or "").casefold()
    preset_id = "clean_tutorial"
    if "product" in intent:
        preset_id = "product_demo"
    elif "short" in intent:
        preset_id = "shorts_vertical"
    before = sum(
        len(getattr(clip, "zoom_actors", []) or [])
        for track in getattr(self, "_tracks", []) or []
        for clip in getattr(track, "clips", []) or []
    )
    try:
        self._apply_screenstudio_auto_polish(screenstudio_polish_preset(preset_id))
    except Exception:
        return 0
    after = sum(
        len(getattr(clip, "zoom_actors", []) or [])
        for track in getattr(self, "_tracks", []) or []
        for clip in getattr(track, "clips", []) or []
    )
    return max(0, int(after) - int(before))


def _first_ai_script_video_start_ms(self) -> int:
    starts = [
        int(getattr(clip, "timeline_in_ms", 0) or 0)
        for track in getattr(self, "_tracks", []) or []
        for clip in getattr(track, "clips", []) or []
        if getattr(clip, "source_path", None) is not None
    ]
    return min(starts) if starts else 0


def _sync_ai_script_applied_cut_markers(self, apply_result: dict | None = None) -> int:
    markers = self._remove_ai_script_preview_markers()
    added = 0
    for idx, row in enumerate((apply_result or {}).get("applied_ranges") or [], start=1):
        if not isinstance(row, dict):
            continue
        start_ms = max(0, int(row.get("applied_start_ms", 0) or 0))
        removed_ms = max(0, int(row.get("removed_ms", 0) or 0))
        markers.append(
            {
                "ms": start_ms,
                "color": "#31D0AA",
                "label": f"AI Cut Applied: -{removed_ms} ms",
                "id": str(row.get("id") or f"ai-script-applied-cut-{idx}"),
                "source": "ai_script_applied_cut",
                "kind": "applied_cut",
            }
        )
        added += 1
    self._timeline_markers = sorted(markers, key=lambda marker: int(marker.get("ms", 0) or 0))
    self._sync_markers_to_ruler()
    return added


def _store_ai_script_edit_payload(self, payload: dict, result: dict | None = None) -> None:
    self._ai_script_edit_payload = dict(payload or {})
    settings = dict(getattr(self, "_project_settings", {}) or {})
    sidecar = dict(settings.get("ai_script_edit") or {})
    sidecar["last_plan_id"] = str((payload or {}).get("plan_id") or "")
    sidecar["last_intent"] = str((payload or {}).get("plan_intent") or "")
    sidecar["last_apply_payload"] = dict(payload or {})
    sidecar["last_apply_result"] = dict(result or {})
    sidecar["review_cut_intents"] = list((payload or {}).get("cut_intents") or [])
    sidecar["short_candidates"] = list((payload or {}).get("short_candidates") or [])
    sidecar["auto_zoom_suggestions"] = self._ai_script_auto_zoom_sidecars(payload)
    sidecar["last_provider"] = str((payload or {}).get("plan_provider") or "rule_based")
    sidecar["last_validation"] = dict(getattr(self, "_ai_script_edit_validation", {}) or {})
    sidecar["last_snapshot_hash"] = str((getattr(self, "_ai_script_edit_snapshot", {}) or {}).get("snapshot_hash") or "")
    if result and isinstance(result.get("cut_materialize_result"), dict):
        sidecar["last_cut_materialize_result"] = dict(result.get("cut_materialize_result") or {})
    settings["ai_script_edit"] = sidecar
    self._project_settings = settings
    try:
        if hasattr(self._player, "set_project_settings"):
            self._player.set_project_settings(settings)
    except Exception:
        pass
