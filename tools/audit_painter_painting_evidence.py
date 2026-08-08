from __future__ import annotations

import ast
import collections
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NUMERIC_LEDGER_PATH = ROOT / "docs" / "PAINTER_NUMERIC_DECISION_LEDGER.json"
EXCEPTION_LEDGER_PATH = ROOT / "docs" / "PAINTER_EXCEPTION_DECISION_LEDGER.json"
AUTO_ROUTED_NUMERIC_STATUSES = frozenset({
    "explicit_normalized_or_signed_unit_channel_domain",
    "explicit_8bit_channel_domain",
    "structural_nonzero_size_count_or_denominator",
    "structural_minimum_points_or_channels",
    "zero_sign_or_nonempty_routing",
    "computational_degeneracy_epsilon",
})
ADVANCED_BRUSH_PRODUCT_SYMBOLS = (
    "dual_brush_intersection",
    "deterministic_noise_field",
    "WetEdgeState",
    "resolve_texture_settings",
)
ADVANCED_BRUSH_PRODUCT_ENTRY_POINTS = ("advanced_dab_alphas",)


def _source_inventory_provenance(paths: list[Path]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for path in sorted({item.resolve() for item in paths}, key=lambda item: item.as_posix()):
        data = path.read_bytes()
        try:
            relative = path.relative_to(ROOT).as_posix()
        except ValueError:
            relative = path.as_posix()
        rows.append({
            "path": relative,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    encoded = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "algorithm": "sha256",
        "file_count": len(rows),
        "inventory_sha256": hashlib.sha256(encoded).hexdigest(),
        "files": rows,
    }


def _advanced_brush_product_reference_matrix(
    paths: list[Path],
) -> list[dict[str, object]]:
    """Report direct or proven one-hop product calls; tests cannot prove integration."""
    trusted_module = "app.painter_advanced_brush"

    def called_symbols(
        source: str,
        symbols: set[str],
        *,
        node: ast.AST | None = None,
        allow_local_definitions: bool = False,
    ) -> set[str]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return set()
        from_imports: dict[str, tuple[str, str]] = {}
        module_imports: dict[str, str] = {}
        local_definitions: set[str] = set()
        shadowed: set[str] = set()
        for statement in ast.walk(tree):
            if isinstance(statement, ast.ImportFrom):
                module = str(statement.module or "")
                for alias in statement.names:
                    from_imports[alias.asname or alias.name] = (module, alias.name)
            elif isinstance(statement, ast.Import):
                for alias in statement.names:
                    module_imports[alias.asname or alias.name.split(".")[0]] = alias.name
        for statement in tree.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                local_definitions.add(statement.name)
                shadowed.add(statement.name)
            elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        shadowed.add(target.id)
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }

        def shadowed_in_enclosing_function(call: ast.Call, name: str) -> bool:
            def target_contains(target: ast.AST, wanted: str) -> bool:
                if isinstance(target, ast.Name):
                    return target.id == wanted
                if isinstance(target, ast.Starred):
                    return target_contains(target.value, wanted)
                if isinstance(target, (ast.Tuple, ast.List)):
                    return any(
                        target_contains(item, wanted) for item in target.elts
                    )
                return False

            current: ast.AST | None = call
            while current is not None:
                current = parents.get(current)
                if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    arguments = current.args
                    parameter_names = {
                        argument.arg
                        for argument in (
                            list(arguments.posonlyargs)
                            + list(arguments.args)
                            + list(arguments.kwonlyargs)
                        )
                    }
                    if arguments.vararg is not None:
                        parameter_names.add(arguments.vararg.arg)
                    if arguments.kwarg is not None:
                        parameter_names.add(arguments.kwarg.arg)
                    if name in parameter_names:
                        return True
                    for child in ast.walk(current):
                        if isinstance(child, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                            targets = (
                                child.targets
                                if isinstance(child, ast.Assign)
                                else [child.target]
                            )
                            if any(
                                target_contains(target, name)
                                for target in targets
                            ):
                                return True
            return False
        called: set[str] = set()
        for call in ast.walk(node or tree):
            if not isinstance(call, ast.Call):
                continue
            if isinstance(call.func, ast.Name):
                local_name = call.func.id
                if allow_local_definitions and local_name in local_definitions:
                    called.update({local_name} & symbols)
                else:
                    module, imported = from_imports.get(local_name, ("", ""))
                    if (
                        module == trusted_module
                        and imported in symbols
                        and local_name not in shadowed
                        and not shadowed_in_enclosing_function(call, local_name)
                    ):
                        called.add(imported)
                continue
            if not isinstance(call.func, ast.Attribute):
                continue
            attributes: list[str] = [call.func.attr]
            owner = call.func.value
            while isinstance(owner, ast.Attribute):
                attributes.append(owner.attr)
                owner = owner.value
            if not isinstance(owner, ast.Name):
                continue
            root = owner.id
            if allow_local_definitions and root in local_definitions and root in symbols:
                called.add(root)
                continue
            module = module_imports.get(root, "")
            imported_module, imported_symbol = from_imports.get(root, ("", ""))
            is_trusted_reference = (
                module == trusted_module and call.func.attr in symbols
            ) or (
                imported_module == trusted_module and imported_symbol in symbols
            )
            if not is_trusted_reference:
                continue
            if root in shadowed or shadowed_in_enclosing_function(call, root):
                continue
            if module == trusted_module and call.func.attr in symbols:
                called.add(call.func.attr)
                continue
            if imported_module == trusted_module and imported_symbol in symbols:
                called.add(imported_symbol)
        return called

    advanced_sources = [
        path for path in paths if path.name == "painter_advanced_brush.py"
    ]
    entry_symbols: dict[str, set[str]] = {
        entry: set() for entry in ADVANCED_BRUSH_PRODUCT_ENTRY_POINTS
    }
    for path in advanced_sources:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in entry_symbols:
                entry_symbols[node.name].update(
                    called_symbols(
                        source,
                        set(ADVANCED_BRUSH_PRODUCT_SYMBOLS),
                        node=node,
                        allow_local_definitions=True,
                    )
                )
    texts = {
        path: path.read_text(encoding="utf-8", errors="replace")
        for path in paths
        if path.name != "painter_advanced_brush.py"
    }
    rows = []
    for symbol in ADVANCED_BRUSH_PRODUCT_SYMBOLS:
        direct = {
            path
            for path, source in texts.items()
            if symbol in called_symbols(
                source, set(ADVANCED_BRUSH_PRODUCT_SYMBOLS)
            )
        }
        via_entries = {
            entry
            for entry, referenced_symbols in entry_symbols.items()
            if symbol in referenced_symbols
        }
        indirect = {
            path
            for path, source in texts.items()
            if bool(called_symbols(source, via_entries))
        }
        product_paths = sorted(
            path.relative_to(ROOT).as_posix()
            if ROOT in path.resolve().parents
            else path.resolve().as_posix()
            for path in direct | indirect
        )
        rows.append({
            "symbol": symbol,
            "product_paths": product_paths,
            "via_entry_points": sorted(via_entries) if indirect else [],
        })
    return rows


def _is_ui_design_function(function: object) -> bool:
    name = str(function or "").casefold()
    return (
        name.startswith("paint_ui_")
        or "painter_ui" in name
        or name in {
            "_add_default_painter_ui_object",
            "_create_painter_ui_object_from_rect",
            "_create_painter_ui_section_from_rect",
            "_update_painter_ui_object_geometry",
            "_convert_painter_ui_selection_to_paint",
            "_handle_painter_ui_key_command",
        }
    )


def _decision_basis(review_status: object) -> str:
    status = str(review_status or "")
    if status.startswith(("unreviewed", "candidate_")):
        return "unresolved"
    if any(token in status for token in ("sourced_", "standard_")):
        return "external_standard"
    if any(token in status for token in (
        "structural_", "exact_", "mathematical_", "computational_",
        "canonical_", "derived_", "domain", "minimum_one_pixel",
        "degenerate_", "file_header_", "icc_header_",
    )):
        return "mathematical_or_format_invariant"
    if any(token in status for token in (
        "excluded", "not_product", "not_runtime_claim", "placeholder",
        "blocked_preflight", "disabled_unimplemented",
    )):
        return "explicit_scope_boundary"
    if any(token in status for token in (
        "authored", "declared", "reviewed", "caller_configured",
        "serialized_", "prefix_stable",
    )):
        return "explicit_tiger_product_policy_no_external_parity_claim"
    return "operational_failure_or_fallback_contract"


def _attach_decision_basis(rows: list[dict[str, object]]) -> None:
    for row in rows:
        row["decision_basis"] = str(
            row.get("ledger_basis") or _decision_basis(row.get("review_status"))
        )


def _candidate_group_fingerprint(rows: list[dict[str, object]]) -> str:
    """Hash semantic locations/text, excluding unstable line numbers."""
    payload = [
        {
            "path": str(row.get("path") or ""),
            "class": str(row.get("class") or ""),
            "function": str(row.get("function") or ""),
            "text": str(row.get("text") or ""),
        }
        for row in rows
    ]
    payload.sort(key=lambda row: (row["path"], row["class"], row["function"], row["text"]))
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _apply_decision_ledger(
    rows: list[dict[str, object]],
    *,
    ledger_path: Path | None = None,
    candidate_prefix: str = "candidate_explicit_ledger_",
) -> dict[str, object]:
    ledger_path = NUMERIC_LEDGER_PATH if ledger_path is None else Path(ledger_path)
    candidates: dict[str, list[dict[str, object]]] = collections.defaultdict(list)
    for row in rows:
        status = str(row.get("review_status") or "")
        if status.startswith(candidate_prefix):
            candidates[status.removeprefix(candidate_prefix)].append(row)
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        ledger = {"contracts": {}}
    contracts = ledger.get("contracts") if isinstance(ledger, dict) else {}
    contracts = contracts if isinstance(contracts, dict) else {}
    accepted: list[str] = []
    stale: list[dict[str, object]] = []
    for contract_id, grouped_rows in sorted(candidates.items()):
        entry = contracts.get(contract_id)
        actual_hash = _candidate_group_fingerprint(grouped_rows)
        if not isinstance(entry, dict) or entry.get("resolution") != "approved":
            continue
        expected_count = int(entry.get("row_count", -1))
        expected_hash = str(entry.get("rows_sha256") or "")
        basis = str(entry.get("decision_basis") or "")
        if expected_count != len(grouped_rows) or expected_hash != actual_hash or basis not in {
            "external_standard",
            "mathematical_or_format_invariant",
            "explicit_scope_boundary",
            "explicit_tiger_product_policy_no_external_parity_claim",
            "operational_failure_or_fallback_contract",
        }:
            stale.append({
                "contract_id": contract_id,
                "expected_count": expected_count,
                "actual_count": len(grouped_rows),
                "expected_sha256": expected_hash,
                "actual_sha256": actual_hash,
            })
            continue
        for row in grouped_rows:
            row["review_status"] = "ledger_approved_" + contract_id
            row["ledger_contract"] = contract_id
            row["ledger_basis"] = basis
            row["ledger_evidence"] = str(entry.get("evidence") or "")
        accepted.append(contract_id)
    try:
        ledger_display_path = str(ledger_path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        ledger_display_path = str(ledger_path)
    return {
        "path": ledger_display_path,
        "accepted_contracts": accepted,
        "stale_contracts": stale,
        "candidate_contracts": sorted(candidates),
        "candidate_inventory": [
            {
                "contract_id": contract_id,
                "row_count": len(candidates[contract_id]),
                "rows_sha256": _candidate_group_fingerprint(candidates[contract_id]),
            }
            for contract_id in sorted(candidates)
        ],
        "pending_contracts": sorted(set(candidates) - set(accepted)),
    }


def _files(directory: str, pattern: str, *, exclude_ui: bool = True) -> list[Path]:
    rows = sorted((ROOT / directory).glob(pattern))
    return [row for row in rows if not (exclude_ui and "painter_ui" in row.name.casefold())]


def _scan(paths: list[Path], pattern: str) -> list[dict[str, object]]:
    regex = re.compile(pattern, re.IGNORECASE)
    output: list[dict[str, object]] = []
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        current_class = ""
        current_function = ""
        for line_number, line in enumerate(lines, start=1):
            class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
            if class_match:
                current_class = class_match.group(1)
                current_function = ""
            function_match = re.match(
                r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(", line
            )
            if function_match:
                current_function = function_match.group(1)
            if regex.search(line):
                output.append({
                    "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "line": line_number,
                    "text": line.strip()[:240],
                    "class": current_class,
                    "function": current_function,
                })
    return output


def _scan_uncovered_numeric_literal_sites(
    paths: list[Path],
    covered_locations: set[tuple[str, int]],
) -> list[dict[str, object]]:
    """Find Painting numeric-literal source lines missed by routed scanners.

    This is a coverage inventory, not a correctness classifier.  One row is
    emitted per source line so several tuple/schema constants on the same line
    remain one reviewable decision site.  UI Design functions are excluded by
    the same semantic boundary as the rest of the Painting audit.
    """
    output: list[dict[str, object]] = []
    seen: set[tuple[str, int]] = set()
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        lines = source.splitlines()
        try:
            relative = str(path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            relative = path.as_posix()

        class Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.classes: list[str] = []
                self.functions: list[str] = []

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self.classes.append(node.name)
                self.generic_visit(node)
                self.classes.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self.functions.append(node.name)
                self.generic_visit(node)
                self.functions.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Constant(self, node: ast.Constant) -> None:
                value = node.value
                if isinstance(value, bool) or not isinstance(value, (int, float, complex)):
                    return
                function = self.functions[-1] if self.functions else ""
                if _is_ui_design_function(function):
                    return
                line = int(getattr(node, "lineno", 0) or 0)
                key = (relative, line)
                if line <= 0 or key in covered_locations or key in seen:
                    return
                seen.add(key)
                output.append({
                    "path": relative,
                    "line": line,
                    "text": lines[line - 1].strip()[:240] if line <= len(lines) else "",
                    "class": self.classes[-1] if self.classes else "",
                    "function": function,
                    "review_status": "candidate_numeric_literal_site_requires_routing",
                })

        Visitor().visit(tree)
    return output


def _scan_suppressed_exceptions(paths: list[Path]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        lines = source.splitlines()

        class Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.classes: list[str] = []
                self.functions: list[str] = []

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self.classes.append(node.name)
                self.generic_visit(node)
                self.classes.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self.functions.append(node.name)
                self.generic_visit(node)
                self.functions.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
                exception_name = ast.unparse(node.type) if node.type is not None else "bare"
                current_function = self.functions[-1] if self.functions else ""
                if _is_ui_design_function(current_function):
                    self.generic_visit(node)
                    return
                pass_only = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
                broad_without_reraise = (
                    exception_name in {"Exception", "bare"}
                    and (
                        path.name.casefold().startswith("painter_")
                        or path.name.casefold() == "drawing.py"
                        or path.name.casefold() == "editor_adapter_paint.py"
                    )
                    and "painter_ui" not in path.name.casefold()
                    and not any(isinstance(child, ast.Raise) for statement in node.body for child in ast.walk(statement))
                )
                typed_persistent_load_fallback = (
                    path.name.casefold() == "painter_palette.py"
                    and current_function == "load_palette_library"
                )
                if pass_only or broad_without_reraise or typed_persistent_load_fallback:
                    line = int(getattr(node, "lineno", 0) or 0)
                    output.append({
                        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                        "line": line,
                        "text": lines[line - 1].strip() if 0 < line <= len(lines) else "",
                        "class": self.classes[-1] if self.classes else "",
                        "function": current_function,
                        "exception": exception_name,
                        "suppression_kind": (
                            "pass" if pass_only else
                            "persistent_load_default_fallback" if typed_persistent_load_fallback else
                            "fallback_without_reraise"
                        ),
                    })
                self.generic_visit(node)

        Visitor().visit(tree)
    return output


def _scan_gl_cleanup_contract(
    paths: list[Path],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Inventory every named GL cleanup delegate and reject direct teardown calls."""

    delegated: list[dict[str, object]] = []
    unwrapped: list[dict[str, object]] = []
    teardown_names = {
        "destroy",
        "release",
        "doneCurrent",
    }
    propagated_primitives = {
        ("PainterRetainedGLTileUploader", "delete"),
        ("_PainterCanvasOffscreenSession", "done_current"),
    }
    for path in paths:
        if path.name.casefold() != "painter_opengl.py":
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        lines = source.splitlines()
        try:
            relative = str(path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            relative = path.as_posix()
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }

        def context(node: ast.AST) -> tuple[str, str]:
            class_name = ""
            function_name = ""
            current: ast.AST | None = node
            while current is not None:
                current = parents.get(current)
                if not function_name and isinstance(
                    current, (ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    function_name = current.name
                if not class_name and isinstance(current, ast.ClassDef):
                    class_name = current.name
                if class_name and function_name:
                    break
            return class_name, function_name

        def row(node: ast.AST) -> dict[str, object]:
            line = int(getattr(node, "lineno", 0) or 0)
            class_name, function_name = context(node)
            return {
                "path": relative,
                "line": line,
                "text": lines[line - 1].strip()[:240] if 0 < line <= len(lines) else "",
                "class": class_name,
                "function": function_name,
            }

        for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
            if isinstance(call.func, ast.Name) and call.func.id == "_best_effort_gl_cleanup":
                delegated.append({
                    **row(call),
                    "exception": "delegated_cleanup",
                    "suppression_kind": "named_cleanup_delegate",
                    "review_status": (
                        "candidate_explicit_ledger_exception_"
                        "best_effort_gl_resource_cleanup_before_error_or_fallback"
                    ),
                })
                continue
            teardown_name = call.func.attr if isinstance(call.func, ast.Attribute) else ""
            if teardown_name not in teardown_names and not teardown_name.startswith(
                "glDelete"
            ):
                continue
            call_row = row(call)
            current: ast.AST | None = call
            wrapped = False
            while current is not None:
                current = parents.get(current)
                if (
                    isinstance(current, ast.Call)
                    and isinstance(current.func, ast.Name)
                    and current.func.id == "_best_effort_gl_cleanup"
                ):
                    wrapped = True
                    break
            if not wrapped:
                callsite = (
                    str(call_row.get("class") or ""),
                    str(call_row.get("function") or ""),
                )
                if callsite in propagated_primitives:
                    delegated.append({
                        **call_row,
                        "exception": "caller_propagated_cleanup",
                        "suppression_kind": "cleanup_primitive_propagates_to_delegate",
                        "review_status": (
                            "candidate_explicit_ledger_exception_"
                            "best_effort_gl_resource_cleanup_before_error_or_fallback"
                        ),
                    })
                    continue
                unwrapped.append({
                    **call_row,
                    "exception": "direct_cleanup_call",
                    "suppression_kind": "unwrapped_gl_teardown",
                    "review_status": "unreviewed_direct_gl_cleanup_call",
                })
    return delegated, unwrapped


def _scan_paint_action_schema_numeric_domains(path: Path) -> list[dict[str, object]]:
    """Inventory numeric JSON-schema bounds with their registered Action ID."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    lines = source.splitlines()
    output: list[dict[str, object]] = []
    keys = {
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minItems",
        "maxItems",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        function = node.func
        if not (
            isinstance(function, ast.Attribute)
            and function.attr == "register_adapter_action"
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            continue
        action_id = str(node.args[0].value)
        if not action_id.startswith("paint.") or action_id.startswith("paint.ui."):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Dict):
                continue
            for key_node, value_node in zip(child.keys, child.values):
                if not (
                    isinstance(key_node, ast.Constant)
                    and key_node.value in keys
                    and isinstance(value_node, (ast.Constant, ast.UnaryOp, ast.Name))
                ):
                    continue
                line = int(getattr(key_node, "lineno", 0) or 0)
                output.append({
                    "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "line": line,
                    "text": lines[line - 1].strip()[:240] if 0 < line <= len(lines) else "",
                    "class": "",
                    "function": "register_paint_actions",
                    "action_id": action_id,
                })
    return output


def _classify_numeric_control(row: dict[str, object]) -> str:
    path = str(row["path"]).casefold()
    text = str(row["text"]).casefold()
    compact = re.sub(r"\s+", "", text)
    function = str(row.get("function") or "").casefold()
    class_name = str(row.get("class") or "").casefold()
    action_id = str(row.get("action_id") or "").casefold()
    if (
        path.endswith("app/painter_open_documents.py")
        and function == "_document_size"
    ):
        return "reviewed_cross_document_exact_pixel_dimension_input_contract"
    # drawing.py is a shared host, so filename exclusion alone cannot remove
    # UI Design implementation from the Painting audit. Route the semantic
    # function boundary before generic clamp/geometry classifiers can claim it.
    if _is_ui_design_function(function):
        return "ui_design_mode_numeric_control_excluded_from_painting_scope"
    if path.endswith("app/painter_brush_dynamics.py"):
        if function in {
            "_normalize_texture_mapping",
            "normalize_brush_dynamics",
            "normalize_pressure_curve",
            "map_pressure",
            "_map_pressure_normalized",
        }:
            if function == "normalize_brush_dynamics" and "pressure_" in text:
                return "reviewed_brush_pressure_window_contract"
            return "reviewed_brush_dynamics_control_domain_contract"
        if function in {
            "stabilize_points",
            "_curve",
            "_noise",
            "_dynamic_dab_plan",
            "dynamic_dab_workload",
            "dynamic_dabs",
        }:
            return "reviewed_brush_response_deterministic_model_contract"
        if function in {
            "_sample_color",
            "_sample_radius_color",
            "_smudge_sample_pixels",
            "_mix_color",
            "capture_dynamic_sample_colors",
        }:
            return "reviewed_smudge_sampling_geometry_and_workload_contract"
        if (
            function == "paint_dynamic_stroke"
            and "qcolor(*row[:4])iflen(row)>=4elseqcolor(*row[:3])" in compact
        ):
            return "reviewed_smudge_sampling_geometry_and_workload_contract"
    if path.endswith("app/painter_legacy_brush.py"):
        return "reviewed_authored_legacy_brush_geometry_contract"
    if (
        path.endswith("app/drawing.py")
        and function == "_restore_state"
        and any(token in compact for token in ("len(snapshot)>=29", "len(snapshot)>=30"))
    ):
        return "structural_saved_selection_history_snapshot_extension"
    if (
        path.endswith("app/painter_saved_selection_channels.py")
        and function == "delete_saved_selection_channel"
        and "len(copied)-1" in compact
    ):
        return "structural_saved_selection_delete_nearest_row_fallback"
    if (
        path.endswith("app/drawing.py")
        and function in {
            "_update_channel_list",
            "_sync_saved_selection_channel_controls",
        }
        and "saved_index" in compact
    ):
        return "structural_saved_selection_move_button_availability"
    if (
        path.endswith("app/painter_quick_mask.py")
        and function == "quick_mask_entry_selection"
        and any(token in compact for token in ("width<=0", "height<=0"))
    ):
        return "structural_positive_quick_mask_raster_extent"
    if function in {"_handle_m3_canvas_interaction", "hit_path_point"}:
        return "reviewed_canvas_selection_mask_or_guide_geometry_contract"
    if (
        path.endswith("app/painter_combo_selection.py")
        and function == "select_combo_data"
    ):
        return "reviewed_combo_semantic_fallback_index_contract"
    if (
        path.endswith("app/painter_output_guides.py")
        and function == "output_guide_geometry"
    ):
        return "reviewed_output_guide_noninverting_geometry_contract"
    if path.endswith("app/painter_zoom.py"):
        return "reviewed_painter_zoom_product_domain_contract"
    if path.endswith("app/painter_brush_domains.py"):
        return "reviewed_painter_brush_width_domain_contract"
    if path.endswith("app/painter_catalog_indices.py"):
        return "reviewed_custom_brush_catalog_index_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "_strict_normalized_real"
    ):
        return "reviewed_painter_action_normalized_input_contract"
    if (
        path.endswith("app/painter_action_contract.py")
        and function == "normalize_painter_numeric_color_components"
    ):
        return "reviewed_numeric_color_three_component_schema_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_pressure_calibration_action"
    ):
        return "reviewed_painter_action_calibration_input_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function in {
            "validate_selection_bounds_action",
            "validate_selection_lasso_action",
        }
    ):
        return "reviewed_painter_action_selection_geometry_input_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function in {"validate_zoom_area_action", "_strict_positive_unit_real"}
    ):
        return "reviewed_painter_action_zoom_area_input_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_layer_opacity_action"
    ):
        return "reviewed_painter_action_layer_opacity_input_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_selection_modify_action"
    ):
        return "reviewed_painter_action_selection_modify_input_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_selection_transform_action"
    ):
        return "reviewed_painter_action_selection_transform_input_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_document_export_action"
    ):
        return "reviewed_painter_action_document_export_input_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_blockout_camera_action"
    ):
        return "reviewed_painter_action_blockout_camera_input_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_paint_stroke_request"
    ):
        return "reviewed_painter_action_stroke_input_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_brush_set_action"
    ):
        return "reviewed_painter_action_brush_input_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function in {
            "validate_editor_objects_list_action",
            "validate_editor_object_locator_action",
            "validate_editor_object_import_geometry_action",
        }
    ):
        return "reviewed_painter_action_editor_object_input_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function in {
            "validate_blockout_primitive_action",
            "validate_blockout_material_preview_action",
            "validate_blockout_camera_preset_action",
            "validate_blockout_duplicate_offset_action",
            "validate_blockout_primitive_id_action",
            "validate_blockout_snap_action",
            "validate_blockout_grid_step",
        }
    ):
        return "reviewed_painter_action_blockout_scene_input_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function in {
            "validate_perspective_guide_action",
            "validate_symmetry_guide_action",
        }
    ):
        return "reviewed_painter_action_guide_input_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function in {
            "validate_view_pan_action",
            "validate_view_pan_result_coordinate",
        }
    ):
        return "reviewed_painter_action_view_pan_input_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function in {
            "validate_path_anchor_action",
            "validate_path_reorder_action",
        }
    ):
        return "reviewed_painter_action_saved_path_mutation_input_contract"
    if (
        path.endswith("app/painter_reference_board.py")
        and function == "sample_reference_color"
    ):
        return "reviewed_reference_sample_pixel_index_contract"
    if (
        path.endswith("app/painter_wet_canvas.py")
        and function in {
            "validate_wet_canvas_settings_update",
            "validate_wet_canvas_advance_seconds",
        }
    ):
        return "reviewed_painter_action_wet_canvas_input_contract"
    if path.endswith("app/painter_action_inputs.py"):
        return "reviewed_painter_action_input_validation_contract"
    if (
        path.endswith("app/actions/editor_adapter_paint.py")
        and function in {
            "_paint_object_payload",
            "_paint_editor_object_render_report",
        }
    ):
        return "reviewed_painter_action_editor_object_fallback_contract"
    if (
        path.endswith("app/actions/editor_adapter_paint.py")
        and function == "paint_editor_object_import"
    ):
        return "reviewed_painter_action_editor_object_commit_contract"
    if (
        path.endswith("app/actions/editor_adapter_paint.py")
        and function in {
            "_paint_positive_extent",
            "_paint_canvas_size",
            "_paint_export_size_for_owner",
        }
    ):
        return "reviewed_painter_action_canvas_size_fallback_contract"
    if "app/drawing.py" in path and function == "_clamped_canvas_pan":
        return "reviewed_canvas_pan_bounds_geometry_contract"
    if (
        "app/drawing.py" in path
        and function == "_sync_color_panel_layout"
        and any(token in compact for token in ("max(120,min(620", "max(280,min(620"))
    ):
        return "reviewed_painting_color_panel_layout_scope_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and (
            action_id in {"paint.document.export_png", "paint.export_png"}
            or function == "_paint_optional_export_size_schema"
        )
    ):
        return "reviewed_painter_action_export_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.brush.set"
    ):
        return "reviewed_painter_action_brush_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id in {"paint.view.zoom", "paint.view.grid"}
    ):
        return "reviewed_painter_action_view_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.view.pan"
    ):
        return "reviewed_painter_action_view_pan_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id in {
            "paint.layer.mask_state.set",
            "paint.layer.mask.paint",
            "paint.layer.mask.gradient",
        }
    ):
        return "reviewed_painter_action_layer_mask_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.brush.calibration.set"
    ):
        return "reviewed_painter_action_calibration_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.performance.configure"
    ):
        return "reviewed_painter_action_performance_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.document.new"
    ):
        return "reviewed_painter_action_document_new_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id in {
            "paint.selection.rectangle",
            "paint.selection.ellipse",
            "paint.selection.lasso",
        }
    ):
        return "reviewed_painter_action_selection_geometry_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.selection.select_by_color"
    ):
        if "tolerance" in compact:
            return "reviewed_painter_action_color_selection_tolerance_schema_contract"
        return "reviewed_painter_action_color_selection_geometry_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.view.zoom_area"
    ):
        return "reviewed_painter_action_zoom_area_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.layer.set_opacity"
    ):
        return "reviewed_painter_action_layer_opacity_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.selection.modify"
    ):
        return "reviewed_painter_action_selection_modify_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.selection.transform"
    ):
        return "reviewed_painter_action_selection_transform_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id in {"paint.image.resize", "paint.canvas.resize"}
    ):
        return "reviewed_painter_action_resize_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.document.export"
    ):
        return "reviewed_painter_action_document_export_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id in {"paint.guide.perspective", "paint.guide.symmetry"}
    ):
        return "reviewed_painter_action_guide_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id in {
            "paint.wet_canvas.settings.set",
            "paint.wet_canvas.advance",
        }
    ):
        return "reviewed_painter_action_wet_canvas_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.material.preview.set"
    ):
        return "reviewed_painter_action_material_preview_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.color.numeric.set"
    ):
        return "reviewed_numeric_color_three_component_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.selection.channel.options.set"
    ):
        return "reviewed_saved_selection_channel_options_input_domain_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.pbr.preview"
    ):
        return "reviewed_painter_pbr_preview_resource_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and "painter_layer_id_min_characters" in text
    ):
        return "reviewed_painter_action_layer_identity_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and (
            "paint_action_path_index_min" in text
            or "paint_action_path_name_min_characters" in text
        )
    ):
        return "reviewed_painter_action_saved_path_mutation_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and (
            action_id == "paint.path.create"
            or "paint_action_path_" in text
        )
    ):
        return "reviewed_painter_action_path_create_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id in {
            "paint.reference.sample_color",
            "paint.reference.extract_palette",
        }
    ):
        return "reviewed_painter_action_reference_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.3d_blockout.camera"
    ):
        return "reviewed_painter_action_blockout_camera_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id == "paint.stroke.draw"
    ):
        return "reviewed_painter_action_stroke_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id in {
            "paint.editor_objects.list",
            "paint.editor_object.render",
            "paint.editor_object.import",
        }
    ):
        return "reviewed_painter_action_editor_object_schema_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and action_id in {
            "paint.3d_blockout.add",
            "paint.3d_blockout.update",
            "paint.3d_blockout.duplicate",
            "paint.3d_blockout.material_preview",
            "paint.3d_blockout.camera_preset",
        }
    ):
        return "reviewed_painter_action_blockout_scene_schema_contract"
    if path.endswith("app/actions/paint_namespace.py"):
        return "reviewed_action_schema_domain_or_authored_action_resource_contract"
    if "app/drawing.py" in path and function in {
        "create_blank_paint_pixmap", "create_checkerboard_paint_pixmap",
        "set_document_size",
    } and any(token in text for token in ("width", "height", "safe_w", "safe_h")):
        return "unreviewed_invalid_canvas_dimension_silently_clamped_to_one_pixel"
    if "app/drawing.py" in path and function == "_set_initial_values" and any(
        token in text for token in ("or 1920", "or 1080")
    ):
        return "unreviewed_invalid_new_canvas_size_silently_replaced_with_full_hd"
    if "editor_adapter_paint.py" in path and function == "paint_brush_set" and "min(60" in compact:
        return "unreviewed_action_brush_width_truncates_published_five_thousand_pixel_domain"
    if "painter_opengl.py" in path and function in {
        "render_blockout_scene_opengl_qimage", "render_canvas_strokes_opengl_qimage",
    } and any(token in text for token in ("target_w", "target_h")):
        return "unreviewed_invalid_render_dimension_silently_clamped_to_one_pixel"
    if path.endswith("app/painter_alpha_channel_exchange.py"):
        if "psd" in function or (not function and compact.startswith("psd_")):
            return "candidate_explicit_ledger_psd_extra_alpha_exchange_input_contract"
        return "candidate_explicit_ledger_tiff_extra_samples_exchange_input_contract"
    # These exact calls have an externally documented normalized channel/API
    # contract.  Route them before the generic 0..1 clamp inventory so that
    # unrelated authored brush, sensor, geometry, and OpenGL policies cannot
    # inherit Qt evidence by proximity.
    if (
        any(token in compact for token in (
            ".setalphaf(", ".setopacity(", "qcolor.fromrgbf(",
        ))
        and any(token in compact for token in (
            "max(0.0,min(1.0", "max(0,min(1.0",
        ))
    ):
        return "reviewed_qt_normalized_color_or_opacity_contract"
    if path.endswith("app/painter_large_canvas.py") and function in {
        "_strict_bounded_resource_integer",
        "_strict_positive_integer",
        "_strict_nonnegative_integer",
        "_strict_nonnegative_real",
        "_strict_unit_real",
        "minimum_tile_budget_mb_for_tile_size",
        "validate_large_canvas_configuration",
    }:
        return "reviewed_large_canvas_configuration_input_contract"
    if path.endswith("app/painter_dimensions.py"):
        return "reviewed_strict_painter_dimension_input_contract"
    if path.endswith("app/painter_opengl.py") and function in {
        "_strict_gl_real",
        "_strict_gl_range",
        "_validated_render_dimensions",
        "composite_normal_layers",
        "composite_tile_records",
        "_draw_face",
        "_draw_shadow",
        "_draw_edge",
        "_draw_grid",
        "_gl_vertex",
        "_gl_vertex_depth",
        "_hex_to_rgba",
        "_collect_canvas_gpu_strokes",
    }:
        return "reviewed_render_resource_or_normalized_graphics_domain_contract"
    if (
        path.endswith("app/drawing.py")
        and function in {
            "_stroke_from_clipboard_dict",
            "_bubble_from_clipboard_dict",
            "_sticker_from_clipboard_dict",
        }
        and any(token in compact for token in (
            "max(0.0,min(1.0", "max(0,min(1.0", "max(-1.0,min(1.0",
            "max(-1,min(1",
        ))
    ):
        return "reviewed_painter_clipboard_normalized_restore_contract"
    if any(token in compact for token in (
        "max(0.0,min(1.0", "max(0,min(1.0", "max(-1.0,min(1.0",
        "max(-1,min(1",
    )):
        return "reviewed_normalized_painting_geometry_sensor_and_channel_contract"
    if any(token in compact for token in ("max(1,min(255", "max(32,min(255")):
        return "reviewed_authored_minimum_visible_alpha_contract"
    if "min(255" in compact and ("max(0" in compact or "alpha" in text or "rgb" in text):
        return "explicit_8bit_channel_domain"
    if (
        "painter_color_management.py" in path
        and function == "inspect_icc_profile"
        and "len(data)" in text
    ):
        return "reviewed_icc_profile_header_field_boundary_contract"
    if (
        "painter_file_exchange.py" in path
        and function == "inspect_layered_psd"
        and "len(raw)" in text
    ):
        return "reviewed_psd_header_length_and_field_extent_contract"
    # A syntactic max(1, ...) scan mixes several unrelated semantics. Route
    # exact, manually reviewed consumers before the generic holding bucket:
    # authored study/material models, discrete raster extents, and transient
    # zero-sized Qt widget guards are not interchangeable evidence.
    if "max(1," in compact:
        if path.endswith("app/painter_ai_study.py"):
            return "reviewed_numeric_control_authored_study_nonzero_extent_contract"
        if path.endswith("app/painter_material_paint.py"):
            return "reviewed_numeric_control_stylized_material_nonzero_extent_contract"
        if path.endswith("app/painter_brush_engine_v2.py"):
            if function == "resolved_bristle_count":
                return "reviewed_numeric_control_bristle_nonzero_extent_contract"
            return "reviewed_derived_raster_or_interpolation_nonzero_extent_contract"
        if path.endswith("app/painter_output.py"):
            return "reviewed_derived_raster_or_interpolation_nonzero_extent_contract"
        if path.endswith("app/painter_reference_board.py") and function == "normalized":
            return "reviewed_structural_serialized_record_and_state_cardinality_contract"
        if path.endswith("app/painter_reference_board.py") and function == "extract_reference_palette":
            return "reviewed_reference_palette_nonzero_sample_denominator_contract"
        if path.endswith("app/painter_3d_blockout.py") and function == "normalized":
            return "reviewed_structural_serialized_record_and_state_cardinality_contract"
        if path.endswith("app/painter_color_boards.py"):
            return "reviewed_structural_product_collection_cardinality_contract"
        if path.endswith("app/drawing.py"):
            if function in {
                "_paint_wet_canvas_layer",
                "_mask_points_from_channel",
                "_mask_points_from_active_layer_alpha",
                "compose_pil_stickers",
            }:
                return "reviewed_derived_raster_or_interpolation_nonzero_extent_contract"
            if function in {
                "_paint_material_preview_overlay",
                "_refresh_reference_board_panel",
                "_refresh_reference_overlay",
            }:
                return "reviewed_reference_or_material_preview_raster_extent_contract"
            if function in {
                "_sync_brush_detail_controls",
                "_apply_brush_library_preset",
                "_apply_brush_preset",
            }:
                return "reviewed_numeric_control_painting_brush_width_clamp_contract"
            if function in {
                "_style_palette_button",
                "_sync_paint_top_bar_density",
                "_ensure_paint_inspector_visible",
                "_hue_rect",
                "_update_brush_detail_preview",
            }:
                return "reviewed_numeric_control_painting_ui_nonzero_extent_scope_contract"
            if function == "_paint_perspective_guides":
                return "reviewed_perspective_guide_mode_product_domain_contract"
            if function in {"_save_canvas_pose", "_recall_canvas_pose"}:
                return "reviewed_canvas_pose_slot_product_domain_contract"
            return "reviewed_qt_transient_paint_widget_extent_guard_contract"
    if "max(1," in compact and any(token in text for token in (
        "width", "height", "count", "size", "len(", "index", "denominator",
        "rows", "columns", "stride", "samples", "points", "duration",
    )):
        return "structural_nonzero_size_count_or_denominator"
    if "len(" in text and (
        path.endswith("app/painter_file_exchange.py")
        or function in {
            "_restore_state",
            "open_document_from_path",
            "_stroke_from_clipboard_dict",
            "import_gpl",
            "import_ase",
            "import_brush_bundle",
        }
    ):
        return "reviewed_structural_serialized_record_and_state_cardinality_contract"
    if "len(" in text and (
        path.endswith("app/painter_soak_baseline.py")
        or function in {
            "_prompt_save_selection_channel",
            "_load_selected_selection_channel",
            "_delete_layer",
            "paint_layer_delete",
        }
    ):
        return "reviewed_structural_product_collection_cardinality_contract"
    if "len(" in text and re.search(
        r"len\([^)]*\)\s*(?:<=|>=|<|>)\s*(?:[0-9]|1[0-9]|2[0-8])\b",
        text,
    ):
        return "reviewed_structural_geometry_and_channel_cardinality_contract"
    if "len(" in text and any(token in text for token in ("< 3", ">= 3", "< 4", ">= 4")):
        return "reviewed_structural_geometry_and_channel_cardinality_contract"
    if re.search(r"\bcount\s*<=\s*1\b", text):
        return "degenerate_interpolation_cardinality"
    if "closed" in text and re.search(r"\bcount\s*>=\s*3\b", text):
        return "structural_closed_path_minimum_points"
    if "alpha" in text and re.search(r"(?:<=|>=|<|>)\s*0(?:\.0+)?(?![.\d])", text):
        return "exact_transparent_sample_boundary"
    if (
        path.endswith("app/actions/editor_adapter_paint.py")
        and function == "paint_brush_set"
        and "style_combo_index" in compact
    ):
        return "reviewed_painter_action_brush_style_lookup_contract"
    zero_relation = bool(re.search(
        r"(?:<=|>=|<|>)\s*0(?:\.0+)?(?![.\d])",
        text,
    ))
    if zero_relation:
        if (
            path.endswith("app/painter_preview_geometry.py")
            or path.endswith("app/painter_output.py")
            or function in {
                "_positive_finite",
                "deterministic_noise_field",
                "blank",
                "_load_painter_document_impl",
                "layer_complete",
                "render_strokes_to_png",
                "open_document_from_path",
                "render_bubble_to_png",
                "render_sticker_to_png",
            }
        ):
            return "reviewed_strict_positive_nonnegative_and_finite_input_validation_contract"
        if path.endswith("app/painter_soak_acceptance.py"):
            return "reviewed_numeric_control_measurement_completeness_contract"
        if path.endswith("app/painter_runtime_metrics.py"):
            return "reviewed_numeric_control_runtime_metric_exact_degeneracy_contract"
        if path.endswith("app/painter_advanced_brush.py"):
            return "reviewed_numeric_control_advanced_brush_zero_identity_contract"
        if path.endswith("app/painter_brush_engine_v2.py"):
            return "reviewed_numeric_control_brush_engine_zero_response_contract"
        if path.endswith("app/painter_material_paint.py"):
            return "reviewed_numeric_control_stylized_material_zero_identity_contract"
        if path.endswith("app/painter_wet_canvas.py"):
            return "reviewed_wet_canvas_exact_zero_identity_contract"
        if path.endswith("app/painter_media_response.py"):
            return "reviewed_media_response_exact_empty_weight_contract"
        if path.endswith("app/painter_stroke_geometry.py"):
            return "reviewed_zero_identity_or_degenerate_geometry_contract"
        if path.endswith("app/drawing.py") and function in {
            "_paint_textured_stroke",
            "_oil_color_variant",
            "_paint_color_power_window",
            "compose_pil_paint_overlays",
        }:
            return "reviewed_authored_paint_render_zero_sign_branch_contract"
        if path.endswith("app/drawing.py") and function in {
            "canvas_content_size",
            "_paint_pixel_grid_overlay",
            "_paint_export_size",
            "_offset_polyline_xy",
            "_refresh_3d_blockout_overlay",
            "_handle_canvas_zoom_request",
            "_selection_bounds",
            "_preview_crop",
            "_update_canvas_geometry",
            "sync_to_parent",
            "_apply_resize",
        }:
            return "reviewed_zero_identity_or_degenerate_geometry_contract"
        return "reviewed_structural_index_sentinel_and_direction_contract"
    if re.search(r"(?:<=|>=|<|>)\s*0(?:\.0+)?(?![.\d])", text) and not any(
        token in text for token in ("noise", "alpha", "opacity", "coverage", "error")
    ):
        return "zero_sign_or_nonempty_routing"
    if any(token in text for token in ("1e-", "0.000001", "0.00001", "0.0001")) and any(
        token in text for token in ("abs(", "denominator", "determinant", "length", "distance")
    ):
        return "computational_degeneracy_epsilon"
    if "painter_palette.py" in path and any(token in text for token in ("0.04045", "0.0031308")):
        return "standard_srgb_transfer_boundary"
    if "painter_palette.py" in path and "0.0 <= channel <= 1.0" in text:
        return "normalized_linear_rgb_gamut_domain"
    if "painter_output.py" in path and "painter_current_canvas_dimension_limit" in text:
        return "declared_tiger_runtime_capacity_not_format_limit"
    if "editor_adapter_paint.py" in path and any(
        token in text for token in ("0.0 <= x <= 1.0", "0.0 <= y <= 1.0")
    ):
        return "declared_normalized_canvas_coordinate_domain"
    if "painter_soak_acceptance.py" in path:
        return "declared_measurement_completeness_contract"
    if "painter_soak_series.py" in path and "elapsed_seconds" in text:
        return "structural_measurement_duration_boundary"
    if "painter_file_exchange.py" in path and any(token in text for token in ("len(data)", "len(raw)", "ifd_offset")):
        return "file_header_structural_boundary"
    if "painter_color_management.py" in path and "len(data)" in text:
        return "icc_header_structural_boundary"
    if "painter_adjustments.py" in path and any(token in text for token in ("len(data)", "len(parts)")):
        return "palette_file_structural_boundary"
    if "painter_brush_engine_v2.py" in path and "lane_noise" in text:
        return "declared_authored_bristle_stylization"
    if "painter_brush_engine_v2.py" in path and "global_index / 64.0" in text:
        return "unreviewed_sample_count_based_paint_depletion_conflicts_pixel_travel_contract"
    if "painter_brush_engine_v2.py" in path and "min(36,requested" in compact:
        return "unreviewed_renderer_ignores_declared_sixty_four_bristle_capacity"
    if "painter_ai_study.py" in path and any(token in text for token in ("local_edge", "direction_x", "focus_weight")):
        return "declared_authored_reference_study_planner"
    if "painter_ai_study.py" in path and "x - start >= 2" in text:
        return "declared_authored_reference_study_planner"
    if "painter_ai_study.py" in path and "pixel_error > 0" in text:
        return "observed_nonzero_mismatch_candidate_admission"
    if "painter_material_paint.py" in path and "deposition" in text:
        return "declared_authored_stylized_relief_numerical_floor"
    if "painter_reference_board.py" in path and "degrees > 180" in text:
        return "canonical_signed_angle_normalization"
    if "painter_selection_mask.py" in path and "alpha.getextrema()[0] < 255" in text:
        return "exact_nonopaque_8bit_alpha_detection"
    if "painter_brush_dynamics.py" in path and "len(samples) >" in text:
        return "unreviewed_brush_sample_capacity"
    if "painter_brush_dynamics.py" in path and "clean[-1][0] < 1.0" in text:
        return "normalized_pressure_curve_endpoint_domain"
    if "app/drawing.py" in path and any(token in text for token in ("noise >", "noise <")):
        return "declared_authored_legacy_texture_stylization"
    if "app/drawing.py" in path and any(token in text for token in ("light > 100", "light < 100", "pos < -0.15")):
        return "declared_authored_legacy_texture_stylization"
    if "app/drawing.py" in path and any(token in text for token in ("rect.width() <= 1", "rect.height() <= 1", "rect.width() > 1", "rect.height() > 1")):
        return "minimum_one_pixel_raster_extent"
    if "app/drawing.py" in path and "material_scale - 1.0" in text:
        return "computational_identity_transform_epsilon"
    if "app/drawing.py" in path and any(token in text for token in ("current.get(\"pages\"", "changes[\"x\"]", "changes[\"y\"]", "available_width <= 40")):
        return "ui_design_or_toolbar_layout_excluded_from_painting_scope"
    if "app/drawing.py" in path and "slot < 4" in text:
        return "declared_four_canvas_pose_slots"
    if "app/drawing.py" in path and "min_cell < 1.0" in text:
        return "one_document_pixel_requires_one_display_pixel"
    if "app/drawing.py" in path and "preview_scale" in text and any(
        token in text for token in ("< 1.0", ">= 1.0")
    ):
        return "exact_unit_scale_branch"
    if "app/drawing.py" in path and any(token in text for token in ("opacity < 1.0", "opacity >= 1.0")):
        return "exact_unit_opacity_boundary"
    if "app/drawing.py" in path and "zoom * 100.0" in text and ">= 400" in text:
        return "declared_pixel_grid_activation_zoom"
    # Clamp expressions are inventoried as well as explicit comparisons. These
    # classifications record the contract used during review; they do not turn
    # Tiger-authored values into external standards or release thresholds.
    if "painter_adjustments.py" in path:
        return "reviewed_adjustment_parameter_or_numeric_domain_contract"
    if "painter_3d_blockout.py" in path:
        return "reviewed_authored_blockout_preview_model_not_physical_claim"
    if "painter_ai_study.py" in path:
        return "reviewed_authored_diagnostic_study_planner_contract"
    if (
        path.endswith("app/painter_brush_dynamics.py")
        and function == "normalize_brush_dynamics"
        and "pressure_" in text
    ):
        return "reviewed_brush_pressure_window_contract"
    if path.endswith("app/painter_brush_dynamics.py") and function in {
        "_normalize_texture_mapping",
        "normalize_brush_dynamics",
    }:
        return "reviewed_brush_dynamics_control_domain_contract"
    if path.endswith("app/painter_brush_dynamics.py") and function == "_curve":
        return "reviewed_brush_curve_interpolation_structure_contract"
    if path.endswith("app/painter_brush_dynamics.py") and function == "dynamic_dabs":
        return "reviewed_brush_sensor_endpoint_response_contract"
    if path.endswith("app/painter_brush_dynamics.py") and function in {
        "_sample_color",
        "_sample_radius_color",
        "_smudge_sample_pixels",
    }:
        return "reviewed_smudge_sampling_geometry_and_workload_contract"
    if "painter_brush_dynamics.py" in path:
        return "reviewed_authored_brush_dynamics_model_and_workload_contract"
    if "painter_advanced_brush.py" in path:
        return "reviewed_advanced_brush_texture_sampling_control_contract"
    if (
        path.endswith("app/painter_saved_selection_channels.py")
        and function == "normalize_saved_selection_channel_overlay_opacity"
        and "0 <= opacity <= 100" in text
    ):
        return "reviewed_saved_selection_channel_options_input_domain_contract"
    if (
        path.endswith("app/painter_brush_engine_v2.py")
        and function == "depleted_load_curve"
    ):
        return "reviewed_brush_load_cumulative_travel_contract"
    if "painter_brush_engine_v2.py" in path:
        return "reviewed_authored_bristle_stylization_contract"
    if "painter_material_paint.py" in path or "painter_media_response.py" in path:
        return "reviewed_authored_stylized_material_model_contract"
    if (
        path.endswith("app/painter_large_canvas.py")
        and function == "_strict_bounded_resource_integer"
    ):
        return "reviewed_large_canvas_configuration_input_contract"
    if "painter_large_canvas.py" in path or "painter_opengl.py" in path:
        return "reviewed_render_resource_or_normalized_graphics_domain_contract"
    if "painter_palette.py" in path or "painter_color_boards.py" in path:
        return "reviewed_color_standard_or_authored_palette_domain_contract"
    if (
        path.endswith("app/painter_document_io.py")
        and function == "load_painter_document"
        and "source_version >= 4" in text
    ):
        return "reviewed_tspaint_v4_dimension_validation_boundary_contract"
    if (
        path.endswith("app/painter_document_io.py")
        and function == "load_painter_document"
        and "source_version >= 5" in text
    ):
        return "reviewed_tspaint_v5_saved_channel_structure_boundary_contract"
    if any(name in path for name in (
        "painter_output.py", "painter_file_exchange.py", "painter_color_management.py",
        "painter_document_io.py", "painter_autosave.py",
    )):
        return "reviewed_output_file_or_archive_contract"
    if any(name in path for name in (
        "painter_layer_compositor.py", "painter_layer_masks.py", "painter_raster_layers.py",
        "painter_selection_mask.py", "painter_pixel_transform.py",
    )):
        return "reviewed_raster_alpha_geometry_or_structural_domain"
    if any(name in path for name in (
        "painter_reference_board.py", "painter_stroke_geometry.py", "painter_bezier_path.py",
        "painter_perspective_snap.py", "painter_stylus.py", "painter_tablet_capture.py",
        "painter_runtime_metrics.py", "painter_wet_canvas.py",
    )):
        return "reviewed_painter_input_geometry_or_authored_model_contract"
    if "editor_adapter_paint.py" in path:
        return "reviewed_action_schema_domain_or_authored_action_resource_contract"
    if "app/drawing.py" in path:
        if class_name == "painteroutputsettingsdialog" and function == "__init__":
            return "reviewed_output_dialog_enum_selection_structure"
        if class_name == "drawingcanvas" and function in {
            "paintevent", "tabletevent", "mousepressevent", "mousereleaseevent",
            "set_layer_view",
        }:
            return "reviewed_canvas_input_raster_bounds_or_layer_percent_domain"
        if class_name == "paintercolorwheel" and function in {"paintevent", "_scale"}:
            return "reviewed_color_wheel_raster_bounds_or_display_scale"
        if class_name in {"speechbubbleitem", "stickeritem"} and function == "mousemoveevent":
            return "reviewed_optional_overlay_parent_bounds_geometry"
        if function == "_refresh_reference_overlay":
            return "reviewed_reference_preview_minimum_raster_extent"
        if function == "create_checkerboard_paint_pixmap":
            return "reviewed_checkerboard_preview_tile_extent"
        if function == "_on_stroke_added":
            return "reviewed_authored_bristle_stylization_contract"
        if function == "_current_stroke_snapshot" and any(
            token in text
            for token in (
                "bristle_count", "brush_engine_version", "stroke.width_px * 0.46",
            )
        ):
            return "reviewed_authored_bristle_stylization_contract"
        if function == "_stroke_from_clipboard_dict" and any(
            token in text
            for token in (
                "brush_engine_version", "bristle_count", "load_depletion",
            )
        ):
            return "reviewed_authored_bristle_stylization_contract"
        if function == "_stroke_from_clipboard_dict" and "material_" in text:
            return "reviewed_authored_stylized_material_model_contract"
        if function in {
            "_current_stroke_snapshot", "_paint_latest_live_stroke_segment",
            "insert_stroke_direct",
        }:
            return "reviewed_history_and_reorder_index_contract"
        if function == "_offset_polyline_xy":
            return "reviewed_painter_input_geometry_or_authored_model_contract"
        if function in {
            "_paint_textured_stroke", "_draw_pil_textured_stroke",
            "_paint_tip_detail_stroke", "_draw_pil_stroke",
            "_draw_pil_dashed_polyline", "_paint_rotated_dab",
            "_sample_polyline_xy", "_offset_polyline_xy", "_on_stroke_added",
            "_paint_latest_live_stroke_segment", "_update_current_stroke_dirty",
            "_current_stroke_snapshot", "_scaled_preview_stroke",
            "insert_stroke_direct", "render_strokes_to_png",
            "compose_pil_paint_overlays", "_stroke_saved_path",
            "_strokes_to_clipboard_image", "_stroke_from_clipboard_dict",
        }:
            return "reviewed_authored_legacy_brush_renderer_or_shared_stroke_contract"
        if function in {
            "_normalized_drag_rect", "_clamp_canvas_point", "_clamp_normalized_point",
            "_snap_canvas_point", "_perspective_snap_stroke_point", "_pixel_grid_metrics",
            "_paint_pixel_grid_overlay", "set_perspective_guides", "set_symmetry_guide",
            "_paint_perspective_guides", "_paint_symmetry_guide", "_remap_points_to_rect",
            "_remap_objects_to_rect", "rotate_point", "_preview_crop",
            "_crop_to_selection", "_paint_layer_mask_circle", "_mask_points_from_channel",
            "_mask_points_from_active_layer_alpha", "add_edge", "_preview_color_range",
            "_handle_m3_canvas_interaction",
        }:
            return "reviewed_canvas_selection_mask_or_guide_geometry_contract"
        if "painter_ui" in function or function in {
            "_add_default_painter_ui_object",
            "_create_painter_ui_object_from_rect", "_create_painter_ui_section_from_rect",
            "_update_painter_ui_object_geometry", "_convert_painter_ui_selection_to_paint",
            "_handle_painter_ui_key_command",
        }:
            return "ui_design_mode_numeric_control_excluded_from_painting_scope"
        if function in {
            "_pick", "_3d_blockout_bounds_for_id", "_3d_blockout_primitive_at",
            "_blockout_gizmo_geometry", "_blockout_drag_mode_at", "_update_3d_blockout_drag",
            "_render_3d_blockout_pixmap", "_pbr_source_image", "_set_material_preview",
            "_paint_material_preview_overlay", "_paint_wet_canvas_layer",
            "_set_wet_canvas_settings", "_advance_wet_canvas",
        }:
            return "reviewed_authored_optional_3d_pbr_material_preview_contract"
        if function in {
            "compose_pil_bubbles", "compose_pil_frame_with_overlays",
            "_build_bubble_path", "_body_rect", "_bubble_from_clipboard_dict",
            "_sticker_from_clipboard_dict", "_place_editor_object_sticker",
            "_create_cutout_sticker", "_duplicate_sticker", "mouseMoveEvent",
        }:
            return "reviewed_optional_overlay_geometry_or_bounds_policy"
        if function == "_restore_state" and "max(1,int(snapshot[11]" in compact:
            return "unreviewed_invalid_restored_canvas_dimension_silently_clamped_to_one_pixel"
        if function in {"_on_preset_changed", "_update_layer_controls"}:
            return "reviewed_ui_enum_selection_routing_contract"
        if function == "_paint_output_guides":
            return "reviewed_output_guide_geometry_contract"
        if function in {
            "_apply_stroke_history_command", "_reorder_path", "_update_history_list",
        }:
            return "reviewed_history_and_reorder_index_contract"
        if function in {"_paint_export_size", "_export_size"}:
            return "reviewed_output_document_or_structural_state_contract"
        if function in {"_field_rect", "_triangle_points"}:
            return "reviewed_color_input_widget_geometry_contract"
        if function == "_build_material_options_menu":
            return "reviewed_wet_canvas_drying_ui_mapping_contract"
        if function == "_build_ui" and "setcurrentindex" in text:
            return "reviewed_ui_enum_selection_routing_contract"
        if function in {
            "_configure_initial_painter_window_size", "_fit_painter_window_to_screen",
            "_scroll_initial_inspector_to_color", "_show_brush_button_menu",
            "_update_brush_detail_preview", "_update_brush_library_preview",
            "_brush_preset_icon", "_style_palette_button",
            "_refresh_derived_palette_buttons", "_resize_painter_workspace_panel",
        }:
            return "reviewed_ui_layout_or_preview_only_policy_not_artwork_claim"
        if function in {
            "_color_control_palette_colors", "_set_painter_numeric_color", "_color_from_mixer",
            "_paint_color_power_window", "_color_window_hit_test",
            "_set_brush_pressure_calibration", "tabletEvent", "mousePressEvent",
            "mouseReleaseEvent", "_handle_canvas_zoom_request", "_fill_document",
        }:
            return "reviewed_explicit_color_input_view_or_tool_product_domain"
        if any(token in text for token in (
            "layout", "widget", "panel", "toolbar", "body.width", "body.height",
            "font", "bubble", "sticker", "target_w", "target_h",
        )):
            return "reviewed_ui_layout_or_optional_overlay_policy_not_quality_claim"
        if any(token in text for token in (
            "brush", "bristle", "smudge", "material", "grid_size", "pressure",
        )):
            return "reviewed_shared_brush_material_or_grid_contract"
        if any(token in text for token in ("blockout", "camera", "pbr", "light", "depth")):
            return "reviewed_authored_optional_preview_model_not_physical_claim"
        if any(token in text for token in (
            "selection", "mask", "pixel", "raster", "opacity", "alpha", "color",
        )):
            return "reviewed_raster_alpha_color_or_selection_domain"
        if any(token in text for token in (
            "canvas", "zoom", "pan", "rotation", "view", "document",
        )):
            return "reviewed_canvas_view_or_document_product_domain"
    return "unreviewed"


def _classify_capacity_policy(row: dict[str, object]) -> str:
    path = str(row["path"]).casefold()
    text = str(row["text"]).casefold()
    if "painter_brush_dynamics.py" in path and any(
        token in text for token in (
            "max_materialized_dabs_per_stroke",
            "painter_dynamic_dab_budget",
        )
    ):
        return "declared_authored_dynamic_dab_workload_budget"
    if "painter_document_io.py" in path and any(
        token in text for token in ("_max_document_bytes", "_max_asset_bytes", "compresslevel")
    ):
        return "declared_authored_archive_resource_guard_not_format_limit"
    if "painter_action_contract.py" in path and "pbr_preview" in text:
        return "declared_authored_measured_pbr_preview_resource_policy"
    if "painter_action_contract.py" in path:
        return "declared_authored_atomic_action_payload_guard"
    if "painter_large_canvas.py" in path:
        return "declared_authored_resource_policy_with_runtime_telemetry"
    if "painter_3d_blockout.py" in path and "tile_size" in text:
        return "declared_authored_blockout_preview_grid_scale"
    if "painter_ai_study.py" in path and any(token in text for token in ("max_regions", "max_strokes")):
        return "declared_authored_reference_study_planner_capacity"
    if "painter_autosave.py" in path and any(
        token in text for token in ("max_workers=1", '"max_workers": 1')
    ):
        return "serialized_recovery_writer_concurrency_policy"
    if "painter_file_exchange.py" in path and "max_delta_lsb" in text:
        return "derived_8bit_one_lsb_per_visible_alpha_over_stage"
    if "painter_opengl.py" in path and "tile_size" in text:
        return "declared_shared_large_canvas_tile_policy"
    if "painter_opengl.py" in path and "max_zoom_percent" in text:
        return "declared_painter_zoom_product_capacity"
    if "painter_palette.py" in path and any(token in text for token in ("max_recent", "max_document")):
        return "declared_palette_history_and_document_capacity"
    if "painter_reference_board.py" in path and "max_colors" in text:
        return "caller_configured_palette_extraction_capacity"
    if "painter_stroke_geometry.py" in path:
        return "declared_authored_action_stroke_sampling_policy"
    if "painter_output.py" in path and "canvas_dimension_limit" in text:
        return "declared_tiger_runtime_capacity_not_format_limit"
    if "app/drawing.py" in path and any(
        token in text for token in ("tile_size", "tile_budget_mb", "undo_budget_mb")
    ):
        return "declared_authored_resource_policy_with_runtime_telemetry"
    if "app/drawing.py" in path and "max_workers=1" in text:
        return "declared_authored_resource_policy_with_runtime_telemetry"
    if "app/drawing.py" in path and "max_zoom_percent" in text:
        return "declared_painter_zoom_product_capacity"
    if "app/drawing.py" in path and "max_brush_size_px" in text:
        return "sourced_adobe_5000px_brush_size_reference"
    if "app/drawing.py" in path and "wet_canvas_preview_max_dimension" in text:
        return "declared_bounded_preview_resolution_not_export_capacity"
    if "app/drawing.py" in path and "max_colors" in text:
        return "caller_configured_palette_extraction_capacity"
    if "app/drawing.py" in path and "max_size" in text:
        return "declared_bounded_pbr_preview_resolution_not_export_capacity"
    return "unreviewed"


def _classify_numeric_literal_coverage(row: dict[str, object]) -> str:
    """Route AST-only literal sites without treating routing as evidence."""
    path = str(row.get("path") or "").casefold()
    function = str(row.get("function") or "").casefold()
    source_text = str(row.get("text") or "").casefold()
    compact = re.sub(r"\s+", "", source_text)
    has_numeric_literal = bool(re.search(r"\d", source_text))
    if (
        path.endswith("app/painter_action_contract.py")
        and function == "normalize_painter_numeric_color_components"
    ):
        return "candidate_explicit_ledger_numeric_color_three_component_runtime_literal_contract"
    if (
        path.endswith("app/painter_action_contract.py")
        and not function
        and compact.startswith("paint_action_pbr_")
    ):
        return "candidate_explicit_ledger_painter_pbr_preview_resource_literal_contract"
    if path.endswith("app/drawing.py") and function in {
        "_paint_textured_stroke",
        "_paint_tip_detail_stroke",
        "_paint_hardness_dab",
        "_paint_rotated_dab",
        "_paint_style_salt",
        "_paint_noise",
        "_sample_polyline_xy",
        "_offset_polyline_xy",
    }:
        return "candidate_explicit_ledger_authored_legacy_brush_renderer_literal_contract"
    if path.endswith("app/painter_legacy_brush.py"):
        return "candidate_explicit_ledger_authored_legacy_brush_geometry_literal_contract"
    if path.endswith("app/painter_brush_catalog.py"):
        return "candidate_explicit_ledger_authored_legacy_brush_preset_and_profile_contract"
    if path.endswith("app/painter_brush_engine_v2.py"):
        return "candidate_explicit_ledger_authored_bristle_stylization_literal_contract"
    if path.endswith("app/painter_material_paint.py"):
        return "candidate_explicit_ledger_authored_stylized_material_model_literal_contract"
    if path.endswith("app/drawing.py") and function in {
        "_current_stroke_snapshot",
        "_on_stroke_added",
        "_stroke_from_clipboard_dict",
    }:
        if "material_" in compact:
            return "candidate_explicit_ledger_authored_stylized_material_model_literal_contract"
        if any(
            token in compact
            for token in (
                "bristle_count",
                "brush_engine_version",
                "brush_seed",
                "point_pressure",
                "point_load",
            )
        ):
            return "candidate_explicit_ledger_authored_bristle_stylization_literal_contract"
    if path.endswith("app/painter_alpha_channel_exchange.py"):
        if "psd" in function or (not function and compact.startswith("psd_")):
            return "candidate_explicit_ledger_psd_extra_alpha_exchange_structure_contract"
        return "candidate_explicit_ledger_tiff_extra_samples_exchange_structure_contract"
    if (
        path.endswith("app/painter_file_exchange.py")
        and function == "inspect_flat_image"
        and (
            "exchange['samples_per_pixel']-3" in compact
            or "2inexchange[\"extra_samples\"]" in compact
        )
    ):
        return "candidate_explicit_ledger_tiff_extra_samples_inspection_structure_contract"
    if (
        path.endswith("app/drawing.py")
        and function == "import_saved_selection_channels_from_path"
    ):
        return "candidate_explicit_ledger_saved_selection_file_import_structure_contract"
    if (
        path.endswith("app/drawing.py")
        and function in {
            "_prompt_save_selection_channel",
            "_load_selected_selection_channel",
        }
        and "saved_selection_channel_serial+1" not in compact
    ):
        return "candidate_explicit_ledger_cross_document_chooser_identity_structure_contract"
    if (
        path.endswith("app/painter_open_documents.py")
        and function == "_document_size"
    ):
        return "candidate_explicit_ledger_cross_document_exact_pixel_dimension_structure_contract"
    if (
        path.endswith("app/painter_saved_selection_channels.py")
        and (
            function == "saved_selection_channel_view_image"
            or not function
            and "saved_selection_channel_default_overlay_opacity_percent" in compact
        )
        or path.endswith("app/drawing.py")
        and function == "_prompt_saved_selection_channel_options"
        or path.endswith("app/painter_document_io.py")
        and function == "_migrate_document"
        and "overlay_opacity_percent" in compact
    ):
        return "candidate_explicit_ledger_saved_selection_channel_options_contract"
    if (
        path.endswith("app/painter_saved_selection_channels.py")
        and function in {
            "saved_selection_channel_grayscale_value",
            "apply_saved_selection_channel_coverage",
            "saved_selection_channel_view_image",
        }
    ):
        return "candidate_explicit_ledger_saved_selection_channel_direct_edit_view_contract"
    if (
        path.endswith("app/drawing.py")
        and function in {
            "_apply_saved_selection_channel_stroke",
            "_saved_selection_channel_mask_after_stroke",
            "_sync_saved_selection_channel_view",
        }
    ):
        return "candidate_explicit_ledger_saved_selection_channel_direct_edit_view_contract"
    if (
        path.endswith("app/painter_saved_selection_channels.py")
        and function in {
            "rename_saved_selection_channel",
            "duplicate_saved_selection_channel",
            "reorder_saved_selection_channel",
            "delete_saved_selection_channel",
        }
    ):
        return "candidate_explicit_ledger_saved_selection_channel_lifecycle_contract"
    if (
        path.endswith("app/drawing.py")
        and function == "_sync_saved_selection_channel_controls"
    ):
        return "candidate_explicit_ledger_saved_selection_channel_lifecycle_contract"
    if path.endswith("app/painter_saved_selection_channels.py"):
        return "candidate_explicit_ledger_saved_selection_alpha8_channel_contract"
    if (
        path.endswith("app/painter_document_io.py")
        and function == "_migrate_document"
        and "saved_selection_channel_serial" in compact
    ):
        return "candidate_explicit_ledger_saved_selection_alpha8_channel_contract"
    if (
        path.endswith("app/drawing.py")
        and (
            function in {
                "__init__",
                "_snapshot_state",
                "_prompt_save_selection_channel",
                "_next_saved_selection_channel_id",
                "open_document_from_path",
            }
            and "saved_selection_channel" in compact
            or function == "_restore_state" and "snapshot[28]" in compact
        )
    ):
        return "candidate_explicit_ledger_saved_selection_alpha8_channel_contract"
    if (
        path.endswith("app/drawing.py")
        and function in {
            "_move_selected_selection_channel",
            "_rename_saved_selection_channel",
            "_duplicate_saved_selection_channel",
            "_reorder_saved_selection_channel",
            "_delete_saved_selection_channel",
        }
        and "saved_selection_channel" in compact
    ):
        return "candidate_explicit_ledger_saved_selection_channel_lifecycle_contract"
    if (
        path.endswith("app/actions/paint_namespace.py")
        and function == "register_paint_actions"
        and compact in {
            '{"channel":{"type":"string","minlength":1}},',
            '"channel_id":{"type":"string","minlength":1},',
            '"channel_id":{"type":"string","maxlength":0},',
            '"name":{"type":"string","maxlength":0},',
        }
    ):
        return "candidate_explicit_ledger_saved_selection_alpha8_channel_contract"
    if path.endswith("app/painter_quick_mask.py"):
        return "candidate_explicit_ledger_quick_mask_alpha8_and_overlay_contract"
    if function in {"_handle_m3_canvas_interaction", "hit_path_point"}:
        return "candidate_explicit_ledger_canvas_selection_mask_or_guide_geometry_literal_contract"
    if path.endswith("app/painter_zoom.py"):
        return "candidate_explicit_ledger_painter_zoom_literal_domain_contract"
    if path.endswith("app/painter_grid.py"):
        return "candidate_explicit_ledger_painter_grid_literal_domain_contract"
    if path.endswith("app/painter_brush_domains.py"):
        return "candidate_explicit_ledger_painter_brush_input_literal_domain_contract"
    if path.endswith("app/painter_catalog_indices.py"):
        return "candidate_explicit_ledger_custom_brush_catalog_literal_contract"
    if (
        path.endswith("app/painter_layer_contract.py")
        and not function
        and compact.startswith("painter_layer_")
    ):
        return "candidate_explicit_ledger_painter_action_layer_identity_literal_contract"
    if (
        path.endswith("app/painter_action_contract.py")
        and not function
        and compact.startswith(
            (
                "paint_action_path_min_points=",
                "paint_action_path_selection_min_points=",
                "paint_action_path_coordinate_min_norm=",
                "paint_action_path_coordinate_max_norm=",
            )
        )
    ):
        return "candidate_explicit_ledger_painter_action_path_create_literal_contract"
    if (
        path.endswith("app/painter_action_contract.py")
        and not function
        and compact.startswith(
            ("paint_action_path_index_min=", "paint_action_path_name_min_characters=")
        )
    ):
        return "candidate_explicit_ledger_painter_action_saved_path_mutation_literal_contract"
    if (
        path.endswith("app/painter_material_paint.py")
        and not function
        and compact.startswith("material_preview_")
    ):
        return "candidate_explicit_ledger_painter_action_material_preview_literal_contract"
    if (
        path.endswith("app/painter_reference_board.py")
        and not function
        and compact.startswith("reference_sample_default_coordinate=")
    ):
        return "candidate_explicit_ledger_reference_sample_literal_contract"
    if (
        path.endswith("app/painter_reference_board.py")
        and not function
        and compact.startswith("reference_")
    ):
        return "candidate_explicit_ledger_painter_action_reference_board_literal_contract"
    if (
        path.endswith("app/actions/editor_adapter_paint.py")
        and function in {
            "paint_reference_add",
            "paint_reference_update",
            "paint_reference_delete",
            "paint_reference_duplicate",
        }
    ):
        return "candidate_explicit_ledger_painter_action_reference_board_commit_literal_contract"
    if (
        path.endswith("app/painter_action_contract.py")
        and not function
        and compact.startswith("paint_action_brush_opacity_")
    ):
        return "candidate_explicit_ledger_painter_action_brush_literal_contract"
    if (
        path.endswith("app/painter_action_contract.py")
        and not function
        and compact.startswith("paint_action_qpoint_coordinate_")
    ):
        return "candidate_explicit_ledger_painter_action_view_pan_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and (
            (not function and compact.startswith("painter_layer_mask_"))
            or function in {
                "_validate_layer_mask_gradient_point",
                "validate_layer_mask_state_action",
                "validate_layer_mask_paint_action",
                "validate_layer_mask_gradient_action",
            }
        )
    ):
        return "candidate_explicit_ledger_painter_action_layer_mask_input_literal_contract"
    if (
        path.endswith("app/actions/editor_adapter_paint.py")
        and function in {
            "paint_layer_mask_state_set",
            "paint_layer_mask_paint",
            "paint_layer_mask_gradient",
        }
    ):
        return "candidate_explicit_ledger_painter_action_layer_mask_commit_literal_contract"
    if (
        path.endswith("app/actions/editor_adapter_paint.py")
        and function in {
            "_paint_positive_extent",
            "_paint_canvas_size",
            "_paint_export_size_for_owner",
        }
    ):
        return "candidate_explicit_ledger_painter_action_canvas_size_fallback_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function in {
            "validate_view_pan_action",
            "validate_view_pan_result_coordinate",
        }
    ):
        return "candidate_explicit_ledger_painter_action_view_pan_input_literal_contract"
    if (
        path.endswith("app/actions/editor_adapter_paint.py")
        and function == "paint_view_pan"
    ):
        return "candidate_explicit_ledger_painter_action_view_pan_commit_literal_contract"
    if (
        path.endswith("app/painter_action_contract.py")
        and not function
        and compact in {
            '"pressure":1.0,',
            '"tilt":0.5,',
            '"tilt_x":0.0,',
            '"tilt_y":0.0,',
            '"rotation":0.5,',
            '"tangential_pressure":0.0,',
            '"load":1.0,',
            '"load":0.0,',
            '"thickness":0.0,',
            '"wetness":0.0,',
            '"gloss":0.0,',
            '"roughness":0.56,',
            '"plow":0.0,',
            '"resaturation":0.0,',
        }
    ):
        return "candidate_explicit_ledger_painter_action_stroke_channel_default_literal_contract"
    if (
        path.endswith("app/painter_action_contract.py")
        and not function
        and compact.startswith(
            (
                "paint_action_blockout_preview_min_px=",
                "paint_action_blockout_preview_max_px=",
                "paint_action_blockout_preview_default_width_px=",
                "paint_action_blockout_preview_default_height_px=",
            )
        )
    ):
        return "candidate_explicit_ledger_painter_action_blockout_preview_literal_contract"
    if (
        path.endswith("app/painter_action_contract.py")
        and not function
        and compact.startswith(
            (
                "paint_action_stroke_default_",
                "paint_action_stroke_seed_index_factor=",
                "paint_action_stroke_seed_point_factor=",
            )
        )
    ):
        return "candidate_explicit_ledger_painter_action_stroke_default_literal_contract"
    if (
        path.endswith("app/painter_action_contract.py")
        and not function
        and compact.startswith("paint_action_stroke_")
    ):
        return "candidate_explicit_ledger_painter_action_stroke_literal_contract"
    if (
        path.endswith("app/painter_action_contract.py")
        and not function
        and compact.startswith("paint_action_editor_object_")
    ):
        return "candidate_explicit_ledger_painter_action_editor_object_literal_contract"
    if (
        path.endswith("app/painter_3d_blockout.py")
        and not function
        and compact.startswith("blockout_camera_")
        and not compact.startswith("blockout_camera_near_plane=")
    ):
        return "candidate_explicit_ledger_painter_action_blockout_camera_literal_contract"
    if (
        path.endswith("app/painter_3d_blockout.py")
        and not function
        and compact.startswith(("blockout_primitive_", "blockout_light_"))
    ):
        return "candidate_explicit_ledger_painter_action_blockout_scene_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and "painter_layer_opacity_" in compact
    ):
        return "candidate_explicit_ledger_painter_action_layer_opacity_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and "painter_selection_skew_" in compact
    ):
        return "candidate_explicit_ledger_painter_action_selection_transform_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and "painter_document_" in compact
    ):
        return "candidate_explicit_ledger_painter_action_document_export_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and (
            "painter_perspective_mode_" in compact
            or "painter_symmetry_axes" in compact
        )
    ):
        return "candidate_explicit_ledger_painter_action_guide_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "_strict_normalized_real"
    ):
        return "candidate_explicit_ledger_painter_action_normalized_input_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_pressure_calibration_action"
    ):
        return "candidate_explicit_ledger_painter_action_calibration_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function in {
            "validate_selection_bounds_action",
            "validate_selection_lasso_action",
        }
    ):
        return "candidate_explicit_ledger_painter_action_selection_geometry_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function in {"validate_zoom_area_action", "_strict_positive_unit_real"}
    ):
        return "candidate_explicit_ledger_painter_action_zoom_area_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_layer_opacity_action"
    ):
        return "candidate_explicit_ledger_painter_action_layer_opacity_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_selection_modify_action"
    ):
        return "candidate_explicit_ledger_painter_action_selection_modify_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_selection_transform_action"
    ):
        return "candidate_explicit_ledger_painter_action_selection_transform_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_document_export_action"
    ):
        return "candidate_explicit_ledger_painter_action_document_export_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function in {
            "validate_perspective_guide_action",
            "validate_symmetry_guide_action",
        }
    ):
        return "candidate_explicit_ledger_painter_action_guide_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_reference_palette_action"
    ):
        return "candidate_explicit_ledger_painter_action_reference_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_blockout_camera_action"
    ):
        return "candidate_explicit_ledger_painter_action_blockout_camera_input_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_paint_stroke_request"
    ):
        return "candidate_explicit_ledger_painter_action_stroke_input_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_brush_set_action"
    ):
        return "candidate_explicit_ledger_painter_action_brush_input_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function in {
            "validate_editor_objects_list_action",
            "validate_editor_object_locator_action",
            "validate_editor_object_import_geometry_action",
        }
    ):
        return "candidate_explicit_ledger_painter_action_editor_object_input_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function in {
            "validate_blockout_primitive_action",
            "validate_blockout_material_preview_action",
            "validate_blockout_camera_preset_action",
            "validate_blockout_duplicate_offset_action",
            "validate_blockout_primitive_id_action",
            "validate_blockout_snap_action",
            "validate_blockout_grid_step",
        }
    ):
        return "candidate_explicit_ledger_painter_action_blockout_scene_input_literal_contract"
    if (
        path.endswith("app/painter_wet_canvas.py")
        and function in {
            "validate_wet_canvas_settings_update",
            "validate_wet_canvas_advance_seconds",
        }
    ):
        return "candidate_explicit_ledger_painter_action_wet_canvas_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function in {
            "validate_path_anchor_action",
            "validate_path_reorder_action",
            "_strict_path_pair",
        }
    ):
        return "candidate_explicit_ledger_painter_action_saved_path_mutation_literal_contract"
    if (
        path.endswith("app/painter_action_inputs.py")
        and function == "validate_mirror_action"
    ):
        return "candidate_explicit_ledger_painter_action_mirror_literal_contract"
    if path.endswith("app/painter_action_inputs.py"):
        return "candidate_explicit_ledger_painter_action_input_literal_contract"
    if (
        path.endswith("app/actions/editor_adapter_paint.py")
        and function in {
            "_paint_object_payload",
            "_paint_editor_object_render_report",
        }
    ):
        return "candidate_explicit_ledger_painter_action_editor_object_fallback_literal_contract"
    if (
        path.endswith("app/actions/editor_adapter_paint.py")
        and function == "paint_editor_object_import"
    ):
        if "end_ms=-1" in compact:
            return "candidate_explicit_ledger_painter_action_editor_object_lifetime_literal_contract"
        return "candidate_explicit_ledger_painter_action_editor_object_commit_literal_contract"
    if (
        path.endswith("app/actions/editor_adapter_paint.py")
        and function == "paint_stroke_draw"
    ):
        if "opacity=int(round(" in compact:
            return "candidate_explicit_ledger_painter_action_stroke_opacity_conversion_literal_contract"
        if "material_" in compact:
            return "candidate_explicit_ledger_painter_action_material_stroke_projection_literal_contract"
        return "candidate_explicit_ledger_painter_action_stroke_construction_literal_contract"
    if (
        path.endswith("app/actions/editor_adapter_paint.py")
        and function == "paint_selection_transform"
    ):
        return "candidate_explicit_ledger_painter_action_selection_transform_default_literal_contract"
    if (
        path.endswith("app/actions/editor_adapter_paint.py")
        and function == "paint_brush_set"
        and "_pen_opacity=int(" in compact
    ):
        return "candidate_explicit_ledger_painter_action_brush_opacity_conversion_literal_contract"
    if (
        path.endswith("app/actions/editor_adapter_paint.py")
        and function == "paint_brush_set"
        and "style_combo_index<0" in compact
    ):
        return "candidate_explicit_ledger_painter_action_brush_style_lookup_literal_contract"
    if (
        path.endswith("app/painter_combo_selection.py")
        and function == "select_combo_data"
    ):
        return "candidate_explicit_ledger_combo_semantic_fallback_literal_contract"
    if (
        path.endswith("app/painter_output_guides.py")
        and function == "output_guide_geometry"
    ):
        return "candidate_explicit_ledger_output_guide_geometry_literal_contract"
    if (
        "painter_wet_canvas.py" in path
        and (
            (
                not function
                and compact.startswith(
                    (
                        "wet_canvas_drying_min_seconds=",
                        "wet_canvas_drying_max_seconds=",
                        "wet_canvas_drying_ui_minutes_min=",
                        "wet_canvas_drying_ui_minutes_max=",
                        "seconds_per_minute=",
                    )
                )
            )
            or function in {
                "drying_seconds_to_ui_minutes",
                "drying_ui_minutes_to_seconds",
            }
        )
    ):
        return "candidate_explicit_ledger_wet_canvas_drying_serialized_and_ui_domain_literal_contract"
    if (
        "app/drawing.py" in path
        and function in {
            "_apply_stroke_history_command",
            "_reorder_path",
            "_update_history_list",
        }
    ):
        return "candidate_explicit_ledger_history_and_reorder_literal_boundary_contract"
    if (
        "painter_file_exchange.py" in path
        and function in {"_write_tiff16", "_write_tiff16_gray"}
        and "(34675,1,len(icc),icc)" in compact
    ):
        return "unreviewed_tiff_icc_profile_tag_uses_byte_instead_of_undefined_type"
    if (
        "painter_file_exchange.py" in path
        and function in {"_write_tiff16", "_write_tiff16_gray"}
        and (
            "tags.extend(" in compact
            or "tags.append(" in compact
            or compact.startswith("(256,")
            or compact.startswith("(259,")
            or compact.startswith("(277,")
            or compact.startswith("(282,")
            or compact.startswith("count=len(tags);")
            or compact.startswith("data_offset=")
            or compact.startswith("iftag==273:")
            or compact.startswith("entries+=")
            or compact.startswith("while(data_offset+")
            or compact.startswith("pixel_offset=")
            or compact.startswith("ifpixel_offset%2:")
            or compact.startswith("external+=b")
            or compact.startswith("entries[strip_entry_offset:")
            or compact.startswith("path.write_bytes(b\"ii*\\0\"")
        )
    ):
        return "candidate_explicit_ledger_tiff_writer_ifd_and_baseline_tag_contract"
    if (
        "painter_file_exchange.py" in path
        and function in {"_write_png16", "_write_png16_gray"}
        and (
            "_png_chunk(b\"ihdr\",struct.pack(\">iibbbbb\"" in compact
            or "_png_chunk(b\"phys\",struct.pack(\">iib\"" in compact
        )
    ):
        return "candidate_explicit_ledger_png16_ihdr_and_physical_pixel_contract"
    if (
        "painter_file_exchange.py" in path
        and function == "inspect_flat_image"
        and (
            "source.read_bytes()[:25]" in compact
            or "bits=int(header[24])" in compact
            or "image.tag_v2.get(258)" in compact
        )
    ):
        return "candidate_explicit_ledger_flat_image_bit_depth_metadata_contract"
    if "painter_output.py" in path and compact == "mm_per_inch=25.4":
        return "candidate_explicit_ledger_exact_international_inch_conversion_contract"
    if (
        "painter_color_management.py" in path
        and function == "inspect_icc_profile"
        and (
            "version_majornotin{2,4}" in compact
            or "require_v4andversion_major!=4" in compact
        )
    ):
        return "candidate_explicit_ledger_icc_v2_v4_profile_version_contract"
    if (
        "painter_color_management.py" in path
        and function in {"transform_rgba_profile", "soft_proof_rgba"}
        and compact in {"rendering_intent:int=1,", "proof_intent:int=1,"}
    ):
        return "candidate_explicit_ledger_relative_colorimetric_default_product_contract"
    if (
        "painter_document_io.py" in path
        and not function
        and (
            compact == "painter_document_version=5"
            or compact.startswith('"tigerstudio.painter.document.v1":1')
            or compact.startswith('"tigerstudio.painter.document.v2":2')
            or compact.startswith('"tigerstudio.painter.document.v3":3')
            or compact.startswith('"tigerstudio.painter.document.v4":4')
        )
    ):
        return "candidate_explicit_ledger_tspaint_v1_v2_v3_v4_v5_migration_contract"
    if (
        "painter_document_io.py" in path
        and function == "_resolve_asset_uris"
        and compact == "returnmapping.get(value[8:],value)"
    ):
        return "candidate_explicit_ledger_tspaint_asset_uri_prefix_contract"
    if (
        path.endswith("app/painter_document_io.py")
        and function == "save_painter_document"
        and "saved_selection_channel_serial" in compact
    ):
        return "candidate_explicit_ledger_tspaint_v5_saved_channel_structure_literal_contract"
    if (
        "painter_file_exchange.py" in path
        and function == "_rgba16_values"
        and "values=np.uint16(np.clip(values,0,65535))" in compact
    ):
        return "unreviewed_uint8_ndarray_is_not_scaled_to_uint16_full_range"
    if (
        "painter_file_exchange.py" in path
        and function == "_rgba16_to_rgba8"
    ):
        return "candidate_explicit_ledger_uint16_to_uint8_linear_rescaling_contract"
    if (
        "painter_file_exchange.py" in path
        and (
            function == "_rgba16_values"
            or (
                function in {"_write_png16_gray", "_write_tiff16_gray"}
                and (
                    "np.uint16(np.clip(" in compact
                    or "gray.ndim!=2" in compact
                )
            )
        )
    ):
        return "candidate_explicit_ledger_uint16_channel_conversion_and_shape_contract"
    if (
        "painter_file_exchange.py" in path
        and function in {"_write_png16", "_write_png16_gray"}
        and "zlib.compress(raw,6)" in compact
    ):
        return "candidate_explicit_ledger_png16_zlib_encoding_policy_contract"
    if (
        "painter_file_exchange.py" in path
        and (
            (
                function in {"_write_png16", "_write_tiff16"}
                and "height,width=rgba.shape[:2]" in compact
            )
            or (
                function in {"_write_png16_gray", "_write_tiff16_gray"}
                and "np.repeat(gray[...,none],3,axis=2)" in compact
            )
        )
    ):
        return "candidate_explicit_ledger_flat_writer_array_shape_contract"
    if (
        "painter_file_exchange.py" in path
        and (
            (not function and compact == "bit_depths={8,16}")
            or (
                function == "exchange_preflight"
                and (
                    compact == "bit_depth:int=8,"
                    or compact == "depth=int(bit_depthor8)"
                    or "ifdepth==16andfmtnotin" in compact
                )
            )
            or (
                function == "export_flat_image"
                and (
                    compact == "bit_depth:int=8,"
                    or compact == "ifint(bit_depth)==16:"
                    or '"source_precision_bits":16ifhigh_precisionelse8,' in compact
                )
            )
            or (
                function == "export_height_map16"
                and compact == '"bit_depth":16,'
            )
        )
    ):
        return "candidate_explicit_ledger_flat_export_8_16_bit_product_contract"
    if (
        "painter_file_exchange.py" in path
        and function == "export_layered_psd"
        and (
            "expected_pm[...," in compact
            or "rendered_pm[...," in compact
            or compact == ")//255"
        )
    ):
        return "candidate_explicit_ledger_psd_premultiplied_8bit_comparison_contract"
    if (
        "painter_file_exchange.py" in path
        and function == "inspect_layered_psd"
        and (
            "raw[:4]!=b\"8bps\"" in compact
            or "versionnotin{1,2}" in compact
        )
    ):
        return "candidate_explicit_ledger_psd_header_signature_or_version_contract"
    if "painter_advanced_brush.py" in path:
        return "candidate_explicit_ledger_advanced_brush_product_integration_contract"
    if "painter_soak_baseline.py" in path:
        return "candidate_explicit_ledger_repeated_soak_baseline_structure_contract"
    if "painter_soak_series.py" in path:
        return "candidate_explicit_ledger_three_run_soak_retention_review_contract"
    if (
        "painter_runtime_metrics.py" in path
        and function == "windows_process_resources"
    ):
        return "candidate_explicit_ledger_windows_process_resource_api_contract"
    if "painter_runtime_metrics.py" in path:
        return "candidate_explicit_ledger_runtime_measurement_statistics_contract"
    if "painter_interop_evidence.py" in path and function == "sha256_file":
        return "candidate_explicit_ledger_external_evidence_hash_streaming_policy_contract"
    if (
        "painter_product_readiness.py" in path
        and function == "painting_support_matrix"
    ):
        return "candidate_explicit_ledger_product_readiness_flat_export_matrix_contract"
    if "painter_raster_layers.py" in path and function == "raster_has_pixels":
        return "candidate_explicit_ledger_qt_argb32_windows_alpha_byte_contract"
    if "painter_product_reapproval.py" in path:
        return "candidate_explicit_ledger_product_reapproval_aggregation_structure_contract"
    if (
        "painter_file_exchange.py" in path
        and function in {"_png_chunk", "_png_integrity"}
    ):
        return "candidate_explicit_ledger_png_chunk_structure_and_crc_contract"
    if (
        "painter_file_exchange.py" in path
        and function == "_tiff_integrity"
    ):
        return "candidate_explicit_ledger_tiff_header_and_ifd_structure_contract"
    if path.endswith("app/painter_output.py") and has_numeric_literal:
        return "candidate_explicit_ledger_print_output_model_literal_contract"
    if path.endswith("app/painter_autosave.py") and has_numeric_literal:
        return "candidate_explicit_ledger_recovery_snapshot_integrity_and_retention_literal_contract"
    if path.endswith("app/painter_document_io.py") and has_numeric_literal:
        return "candidate_explicit_ledger_tspaint_archive_integrity_and_asset_literal_contract"
    if path.endswith("app/painter_recovery_dialog.py") and has_numeric_literal:
        return "candidate_explicit_ledger_recovery_dialog_product_policy_literal_contract"
    if path.endswith("app/painter_file_exchange.py") and has_numeric_literal:
        if function == "print_geometry":
            return "candidate_explicit_ledger_print_output_model_literal_contract"
        if function in {"export_layered_psd", "inspect_layered_psd", "import_layered_psd"}:
            return "candidate_explicit_ledger_psd_exchange_policy_literal_contract"
        if function in {"_write_tiff16", "_write_tiff16_gray"}:
            return "candidate_explicit_ledger_tiff_writer_ifd_and_baseline_tag_contract"
        return "candidate_explicit_ledger_flat_export_and_inspection_policy_literal_contract"
    # Every remaining AST numeric site is routed by its Painting subsystem,
    # but remains unresolved until an exact count/hash entry exists in the
    # decision ledger.  This avoids both a catch-all approval and the former
    # misleading implication that a path/function match is itself evidence.
    if path.endswith("app/drawing.py"):
        return "candidate_explicit_ledger_painting_canvas_runtime_residual_numeric_literal_contract"
    if path.endswith("app/actions/paint_namespace.py") or path.endswith(
        "app/painter_action_contract.py"
    ):
        return "candidate_explicit_ledger_painting_action_schema_residual_numeric_literal_contract"
    if path.endswith("app/actions/editor_adapter_paint.py"):
        return "candidate_explicit_ledger_painting_action_adapter_residual_numeric_literal_contract"
    if any(path.endswith(f"app/{name}") for name in (
        "painter_3d_blockout.py", "painter_opengl.py", "painter_large_canvas.py",
    )):
        return "candidate_explicit_ledger_painting_gpu_blockout_resource_residual_numeric_literal_contract"
    if any(path.endswith(f"app/{name}") for name in (
        "painter_ai_study.py", "painter_brush_dynamics.py",
        "painter_media_response.py", "painter_wet_canvas.py",
    )):
        return "candidate_explicit_ledger_painting_authored_model_residual_numeric_literal_contract"
    if any(path.endswith(f"app/{name}") for name in (
        "painter_color_boards.py", "painter_palette.py",
        "painter_adjustments.py", "painter_reference_board.py",
    )):
        return "candidate_explicit_ledger_painting_color_palette_reference_residual_numeric_literal_contract"
    if any(path.endswith(f"app/{name}") for name in (
        "painter_bezier_path.py", "painter_layer_masks.py",
        "painter_stroke_geometry.py", "painter_perspective_snap.py",
        "painter_pixel_transform.py", "painter_selection_mask.py",
        "painter_stylus.py", "painter_wheel_controls.py",
        "painter_layer_compositor.py", "painter_tablet_capture.py",
    )):
        return "candidate_explicit_ledger_painting_geometry_selection_input_residual_numeric_literal_contract"
    if path.endswith("app/painter_soak_acceptance.py"):
        return "candidate_explicit_ledger_painting_soak_acceptance_residual_numeric_literal_contract"
    if path.endswith("app/painter_export_transaction.py"):
        return "candidate_explicit_ledger_painting_export_transaction_residual_numeric_literal_contract"
    if path.endswith("app/painter_i18n.py"):
        return "candidate_explicit_ledger_painting_i18n_residual_numeric_literal_contract"
    return "candidate_numeric_literal_site_requires_routing"


def _classify_semantic_shortcut(row: dict[str, object]) -> str:
    """Classify language that can conceal a simulated or narrowed product path."""
    path = str(row["path"]).casefold()
    text = str(row["text"]).casefold()
    function = str(row.get("function") or "").casefold()
    if (
        "app/drawing.py" in path
        and function in {"create_blank_paint_pixmap", "_validated_paint_background"}
        and "isvalid" in text
    ):
        return "explicit_invalid_canvas_color_rejected"
    if (
        path.endswith("app/painter_quick_mask.py")
        and function == "quick_mask_grayscale_value"
        and "isvalid" in text
    ):
        return "explicit_invalid_quick_mask_color_rejected"
    if (
        path.endswith("app/painter_saved_selection_channels.py")
        and function == "saved_selection_channel_grayscale_value"
        and "isvalid" in text
    ):
        return "explicit_invalid_saved_selection_channel_color_rejected"
    if (
        path.endswith("app/painter_saved_selection_channels.py")
        and function == "normalize_saved_selection_channel_overlay_color"
        and "isvalid" in text
    ):
        return "explicit_invalid_saved_selection_channel_overlay_color_rejected"
    if (
        path.endswith("app/drawing.py")
        and function == "_prompt_saved_selection_channel_options"
        and "isvalid" in text
    ):
        return "explicit_qcolor_dialog_cancel_or_invalid_selection_guard"
    if "app/drawing.py" in path and function == "_fill_document" and "isvalid" in text:
        return "explicit_invalid_fill_color_rejected"
    if "editor_adapter_paint.py" in path and function == "paint_stroke_draw" and "isvalid" in text:
        return "explicit_invalid_action_color_rejected"
    if "app/drawing.py" in path and function in {
        "_pick_background_color", "_pick_custom_color",
    } and "isvalid" in text:
        return "explicit_qcolor_dialog_cancel_or_invalid_selection_guard"
    if any(name in path for name in (
        "painter_evidence_contract.py",
        "painter_legacy_brush.py",
        "painter_native_environment.py",
        "painter_product_readiness.py",
        "painter_tablet_capture.py",
    )):
        return "declared_evidence_boundary_not_product_substitute"
    if "painter_media_response.py" in path and "synthetic" in text:
        return "declared_fixed_synthetic_metamorphic_corpus"
    if "painter_brush_engine_v2.py" in path and "synthetic" in text:
        return "declared_tiger_authored_visual_stylization"
    if "painter_file_exchange.py" in path and "not implemented" in text and "cmyk conversion" in text:
        return "explicit_blocked_preflight_for_unimplemented_color_conversion"
    if "painter_i18n.py" in path:
        return "localized_user_facing_vocabulary_not_runtime_claim"
    if "app/drawing.py" in path and "placeholder" in text:
        return "explicit_user_visible_placeholder_or_decode_failure_state"
    if "app/drawing.py" in path and "reserved for" in text:
        return "explicit_disabled_unimplemented_brush_control_not_product_claim"
    if "painter_opengl.py" in path and "best_effort_gl_cleanup" in text:
        return "reviewed_gl_cleanup_failure_telemetry_and_primary_error_preservation"
    return "unreviewed"


def _classify_localized_error_string_decision(row: dict[str, object]) -> str:
    path = str(row["path"]).casefold()
    function = str(row.get("function") or "")
    if "audit_painter_painting_evidence.py" in path and function == "main":
        return "audit_search_pattern_not_runtime_decision"
    if path.startswith("tests/"):
        return "declared_localized_error_fixture_not_runtime_decision"
    if "qa_painter_disk_full.py" in path and function == "_is_disk_full_exception":
        return "exception_message_fallback_after_numeric_errno_or_winerror_classifier"
    return "unreviewed_locale_dependent_error_state_decision"


def _suppressed_exception_contract_candidate(row: dict[str, object]) -> str:
    path = str(row["path"]).casefold()
    function = str(row["function"])
    if "painter_export_transaction.py" in path and function in {
        "transactional_directory_export",
        "transactional_file_export",
        "_rollback_export",
    }:
        return "transactional_export_primary_failure_and_rollback_diagnostics"
    if "painter_large_canvas.py" in path and function in {
        "clear", "remove_layer", "_evict", "_delete_gpu_handle",
        "_synchronize_gpu_fallback", "close",
    }:
        return "best_effort_gpu_resource_cleanup_after_fallback"
    if "painter_large_canvas.py" in path and function == "_finish":
        return "structured_async_worker_failure_telemetry"
    if "painter_opengl.py" in path and function in {
        "__init__", "_best_effort_gl_cleanup",
        "render_blockout_scene_opengl_qimage", "render_canvas_strokes_opengl_qimage",
    }:
        return "best_effort_gl_resource_cleanup_before_error_or_fallback"
    if "painter_material_paint.py" in path and function in {
        "_draw_polyline", "_draw_weighted_segment",
    }:
        return "declared_optional_opencv_to_pillow_raster_fallback"
    if "painter_material_paint.py" in path and function == "_blur":
        return "declared_optional_opencv_to_numpy_gaussian_blur_fallback"
    if "painter_3d_blockout.py" in path and function == "_primitive_index":
        return "invalid_structural_identifier_defaults_to_unsorted_index"
    if "painter_reference_board.py" in path and function in {
        "_reference_index", "_normalize_rotation",
    }:
        return "invalid_serialized_scalar_normalization_boundary"
    if "painter_brush_dynamics.py" in path and function == "_captured_dab_image":
        return "invalid_embedded_dab_falls_through_to_durable_path_or_missing_resource_diagnostic"
    if "painter_color_management.py" in path and function == "inspect_icc_profile":
        return "invalid_icc_reported_as_validation_error"
    if "painter_file_exchange.py" in path and function in {
        "inspect_flat_image", "inspect_layered_psd",
    }:
        return "decode_failure_reported_in_preflight_errors"
    if "painter_large_canvas.py" in path and function in {
        "update_layer", "render_layer_image", "composite_normal_layers",
    }:
        return "gpu_failure_recorded_in_telemetry_before_cpu_fallback"
    if "painter_opengl.py" in path and function in {
        "painter_opengl_status", "painter_canvas_opengl_status",
    }:
        return "opengl_unavailability_reported_in_status_contract"
    if "painter_opengl.py" in path and function == "_hex_to_rgba":
        return "invalid_optional_preview_color_uses_declared_visual_default"
    if "painter_product_reapproval.py" in path and function == "aggregate_product_reapproval":
        return "source_load_or_validation_failure_appended_to_aggregation_errors"
    if "painter_wet_canvas.py" in path and function == "render_wet_layer_qimage":
        return "diffusion_failure_exposed_by_diffusion_applied_false"
    if "app/drawing.py" in path and function in {
        "_configure_initial_painter_window_size", "configure_painter_large_canvas",
        "_open_pbr_texture_lab_window", "_create_cutout_sticker",
    }:
        return "best_effort_parent_or_resource_cleanup_with_primary_error_path_preserved"
    if "app/drawing.py" in path and function in {
        "paintEvent", "mouseDoubleClickEvent", "mouseReleaseEvent",
        "_update_color_window_drag", "mousePressEvent", "mouseMoveEvent",
        "eventFilter",
    }:
        return "optional_extension_callback_failure_isolated_from_core_canvas"
    if "app/drawing.py" in path and function in {
        "_poll_wet_canvas_future",
        "_sample_selected_reference_color",
        "_extract_selected_reference_palette",
        "_render_3d_blockout_pixmap",
        "_pbr_preview_generated_maps",
        "_refresh_pbr_texture_preview",
        "_sync_canvas_layer_view",
        "_observe_painter_recovery_writer",
        "_apply_brush_library_preset",
    }:
        return "structured_optional_feature_failure_telemetry"
    if "app/drawing.py" in path and function in {
        "_system_clipboard_has_paint_payload",
        "_system_clipboard_has_image_payload",
        "_write_payload_to_system_clipboard",
        "_payload_from_system_clipboard",
        "_system_clipboard_image",
        "_write_clipboard_image_asset",
    }:
        return "clipboard_failure_recorded_in_operational_state"
    if "app/drawing.py" in path and function in {
        "compose_pil_frame_with_overlays",
        "render_bubble_to_png",
        "compose_pil_bubbles",
        "_open_sticker_pil",
        "render_sticker_to_png",
    }:
        return "overlay_font_fallback_or_asset_failure_result_contract"
    if "app/drawing.py" in path and function in {
        "set_color_power_window_editor", "_paint_color_power_window",
        "_color_window_rect", "_normalise_path_points", "_pbr_slider_value",
    }:
        return "invalid_optional_serialized_value_rejected_or_reported"
    if "app/drawing.py" in path and function in {
        "_display_background_pixmap", "painter_action_state",
    }:
        return "qt_or_opengl_capability_failure_uses_declared_status_fallback"
    if "app/drawing.py" in path and function in {
        "_write_reference_image_asset", "_clipboard_image_path_from_text",
    }:
        return "filesystem_probe_or_asset_write_failure_returns_no_asset"
    if "app/drawing.py" in path and function == "_set_brush_dynamics_mode":
        return "invalid_embedded_dab_falls_through_to_durable_path_or_missing_resource_diagnostic"
    if "app/drawing.py" in path and function in {
        "_handle_channel_list_event", "_handle_layer_list_event",
    }:
        return "invalid_optional_qt_event_rejected_without_state_change"
    if "app/drawing.py" in path and function == "_point_in_canvas_host":
        return "qt_coordinate_mapping_failure_uses_input_point_fallback"
    if "app/drawing.py" in path and function in {
        "_paint_strokes_with_gpu_cache",
        "_painter_large_canvas_runtime_instance",
    }:
        return "gpu_failure_recorded_in_canvas_status_before_cpu_fallback"
    if "app/drawing.py" in path and function in {
        "_prompt_save_painter_document",
        "_prompt_open_painter_document",
        "_prompt_export_painter_document",
        "_prompt_import_layered_psd",
        "_prompt_import_image_as_paint_layer",
        "_import_custom_brush_bundle",
        "_export_custom_brush_bundle",
        "_export_pbr_texture_maps", "_export_png_to_file",
        "_import_editor_object", "_place_editor_object_sticker",
    }:
        return "user_visible_operation_failure_without_success_claim"
    if "editor_adapter_paint.py" in path and function in {
        "paint_editor_object_import", "_store_paint_3d_blockout_scene",
        "_store_paint_reference_board",
    }:
        return "action_data_committed_before_optional_ui_refresh"
    return "unreviewed"


def _classify_suppressed_exception(row: dict[str, object]) -> str:
    """Keep exception catches unresolved until an exact handler contract is frozen.

    Function names are useful for routing review, but they are not evidence that
    a catch preserves the primary result, records the failure, or is limited to
    cleanup.  Prefix every routed contract as a ledger candidate so
    ``_decision_basis`` cannot silently approve it from naming alone.
    """

    candidate = _suppressed_exception_contract_candidate(row)
    if candidate == "unreviewed":
        return candidate
    return "candidate_explicit_ledger_exception_" + candidate


def main() -> int:
    app_files = [
        path
        for path in _files("app", "painter_*.py")
        if not path.name.startswith("painter_ui_")
    ] + [
        ROOT / "app" / "drawing.py",
        ROOT / "app" / "actions" / "paint_namespace.py",
        ROOT / "app" / "actions" / "editor_adapter_paint.py",
    ]
    test_files = [
        path
        for path in _files("tests", "test_painter_*.py")
        if not path.name.startswith("test_painter_ui")
    ]
    qa_files = [
        path
        for path in _files("tools", "*painter*.py")
        if "painter_ui" not in path.name
    ]
    qa_producers = [
        path for path in qa_files
        if path.name != "audit_painter_painting_evidence.py"
    ]
    docs = [
        ROOT / "docs" / name for name in (
            "PAINTER_EVIDENCE_AUDIT_AND_CORRECTION_MILESTONES_KO.md",
            "PAINTER_PAINTING_FULL_AUDIT_CHANGE_LIST_KO.md",
            "PAINTER_PAINTING_MILESTONES_KO.md",
            "PAINTER_PHOTOSHOP_PARITY_AUDIT.md",
            "PAINTER_PRODUCTION_ART_WORKSPACE_PLAN.md",
            "SPEC_PAINTER_DOCUMENT_FORMAT.md",
            "SPEC_PAINTER_MATERIAL_PAINT.md",
        )
    ] + [ROOT / "SPEC.md"]
    all_code = app_files + test_files + qa_files
    verification_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in test_files + qa_files
    )
    module_static_references = []
    for path in app_files:
        module_name = path.stem
        module_static_references.append({
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "module": module_name,
            "mentioned_by_test_or_qa": module_name in verification_text,
        })
    advanced_brush_product_references = _advanced_brush_product_reference_matrix(
        app_files
    )
    test_functions = _scan(test_files, r"^def\s+test_")
    offscreen = _scan(test_files + qa_files, r"QT_QPA_PLATFORM.+offscreen")
    numeric_scale_rows = _scan(
        app_files,
        r"\*\s*2\.55|/\s*100(?:\.0)?\s*\*|size\s*>\s*99|return\s+64\b|return\s*\(\s*1920\s*,\s*1080\s*\)|(?:fallback|frame_size):\s*tuple\[int,\s*int\]\s*=\s*\(1920,\s*1080\)|def\s+paint_(?:document_new|image_resize|canvas_resize)[^#\n]*1920[^#\n]*1080|int\((?:width\s+or\s+1920|height\s+or\s+1080)\)|int\(request\.get\([\"'](?:width|height)[\"']\)\s+or\s+(?:1920|1080)\)|document\.get\([\"'](?:width|height)[\"'],\s*(?:1920|1080)\)|getattr\([^#\n]*[\"']_canvas_document_size[\"'][^#\n]*\(1920,\s*1080\)\)|background_pixmap[^#\n]*else\s+(?:1920|1080)|[\"']maximum[\"']\s*:\s*60\b|len\(set\([^)]*\)\)\s*>\s*1|rotation_degrees\s*/\s*360|_event_value\(event,\s*[\"'](?:pressure|rotation)[\"']|pressure:\s*float\s*=\s*0\.82|point\.get\([\"']pressure[\"'],\s*0\.82|\([\"']pressure[\"'],\s*0\.82\)|normalize_curve\([^#\n]*point_pressure[^#\n]*0\.82|_clipboard_float\(value,\s*0\.82|^\s*0\.68\s*$",
    )
    for row in numeric_scale_rows:
        text = str(row["text"]).casefold()
        if _is_ui_design_function(row.get("function")):
            status = "ui_design_mode_numeric_control_excluded_from_painting_scope"
        elif "opacity" in text and "2.55" in text:
            status = "declared_percent_to_8bit_alpha"
        elif ("saturation" in text or "value" in text) and "2.55" in text:
            status = "declared_hsb_percent_to_8bit_channel"
        elif ("cfg[" in text or "transfer_flow" in text) and "/ 100" in text:
            status = "declared_brush_percent_to_unit_interval"
        elif "rotation_degrees" in text and "/ 360" in text:
            status = "unreviewed_qt_rotation_zero_mapped_to_non_neutral_internal"
        elif (
            str(row.get("path") or "").endswith("app/painter_stylus.py")
            and str(row.get("function") or "") == "tablet_stylus_sample"
            and "pressure" in text
            and "0.0" in text
        ):
            status = "sourced_qt_tablet_pressure_zero_neutral_input"
        elif (
            str(row.get("path") or "").endswith("app/painter_stylus.py")
            and str(row.get("function") or "") == "tablet_stylus_sample"
            and "rotation" in text
            and "0.0" in text
        ):
            status = "sourced_qt_tablet_rotation_degrees_neutral_input"
        elif "_event_value" in text and "pressure" in text and "0.82" in text:
            status = "unreviewed_missing_qt_pressure_fabricates_eighty_two_percent"
        elif "pressure:" in text and "0.82" in text:
            status = "unreviewed_default_stylus_sample_fabricates_eighty_two_percent"
        elif "point.get" in text and "pressure" in text and "0.82" in text:
            status = "unreviewed_missing_action_pressure_fabricates_eighty_two_percent"
        elif str(row.get("function") or "") == "_normalized_point" and "pressure" in text and "0.82" in text:
            status = "unreviewed_action_smoothing_fabricates_eighty_two_percent_pressure"
        elif "normalize_curve" in text and "point_pressure" in text and "0.82" in text:
            status = "unreviewed_missing_bristle_pressure_fabricates_eighty_two_percent"
        elif "_clipboard_float" in text and "0.82" in text:
            status = "unreviewed_missing_clipboard_pressure_fabricates_eighty_two_percent"
        elif str(row.get("function") or "") == "_on_stroke_added" and text == "0.68":
            status = "unreviewed_missing_material_pressure_fabricates_sine_curve"
        elif "return (1920, 1080)" in text:
            status = "unreviewed_action_canvas_size_fabricates_full_hd_document"
        elif "fallback:" in text and "(1920, 1080)" in text:
            status = "unreviewed_export_helper_fabricates_full_hd_document"
        elif "frame_size:" in text and "(1920, 1080)" in text:
            status = "unreviewed_compositor_fabricates_full_hd_document"
        elif (
            str(row.get("path") or "").endswith("app/actions/paint_namespace.py")
            and '"maximum": 60' in text
        ):
            status = "unreviewed_action_schema_truncates_published_five_thousand_pixel_brush_domain"
        elif str(row.get("function") or "") == "paint_document_new" and "def paint_document_new" in text:
            status = "declared_tiger_new_canvas_full_hd_starting_preset"
        elif "def paint_image_resize" in text or "def paint_canvas_resize" in text:
            status = "unreviewed_required_resize_method_has_hidden_full_hd_default"
        elif "int(width or 1920)" in text or "int(height or 1080)" in text:
            status = "unreviewed_invalid_canvas_dimension_silently_replaced_with_full_hd"
        elif "document.get" in text and ("width" in text or "height" in text):
            status = "unreviewed_document_loader_fabricates_missing_canvas_dimension"
        elif "background_pixmap" in text and "else" in text:
            status = "unreviewed_paint_dialog_constructor_fabricates_full_hd_document"
        elif "request.get" in text and ("width" in text or "height" in text):
            status = "unreviewed_validated_new_canvas_request_still_has_full_hd_fallback"
        elif "_canvas_document_size" in text and "(1920, 1080)" in text:
            status = "unreviewed_internal_document_state_fabricates_full_hd_when_missing"
        elif "_event_value" in text and "rotation" in text and "180.0" in text:
            status = "unreviewed_missing_qt_rotation_fabricates_one_eighty_degrees"
        else:
            status = "unreviewed"
        row["review_status"] = status
    quality_threshold_rows = _scan(
        app_files + test_files
        + [path for path in qa_files if path.resolve() != Path(__file__).resolve()],
        r"(?:elapsed|latency|delta|max_delta|max_channel|mean_absolute_error|correlation|edge_f1|score|quality|coverage|variance|std|ptp|count_nonzero|sample_count|duration|stroke_count|np\.min|np\.max|np\.sum)[^#\n]{0,100}(?:<=|>=|<|>)\s*-?\d",
    )
    for row in quality_threshold_rows:
        path = str(row["path"]).casefold()
        text = str(row["text"]).casefold()
        if "painter_file_exchange.py" in path and "max_delta_lsb" in text:
            status = "derived_8bit_one_lsb_per_visible_alpha_over_stage"
        elif any(
            name in path
            for name in (
                "measure_painter_legacy_brush.py",
                "measure_painter_bristle_material.py",
                "test_painter_bristle_material_measurement.py",
            )
        ) and ("max_delta" in text or "preview_export_delta" in text):
            status = "derived_8bit_one_lsb_qt_premultiplied_export_boundary"
        elif any(name in path for name in (
            "qa_painter_large_canvas_runtime.py",
            "qa_painter_native_environment.py",
            "qa_painter_photoshop_interop.py",
            "qa_painter_painting_m6.py",
        )) and ("delta" in text or "parity" in text):
            status = "declared_8bit_pixel_parity_bound"
        elif "qa_painter_soak.py" in path and "7200" in text:
            status = "declared_two_hour_milestone_duration"
        elif "painter_soak_acceptance.py" in path:
            status = "declared_measurement_completeness_contract"
        elif "painter_ai_study.py" in path and "pixel_error > 0.0" in text:
            status = "observed_nonzero_mismatch_candidate_admission"
        elif "painter_material_paint.py" in path and "1.0 / 255.0" in text:
            status = "declared_8bit_one_lsb_preview_quantization_bound"
        elif "painter_material_paint.py" in path and "np.min(signed_height)" in text and "< 0.0" in text:
            status = "exact_negative_relief_functionality_detection"
        elif "painter_media_response.py" in path and any(token in text for token in (
            "total > 0.0", "np.min(negative_depth", "np.max(negative_depth", "np.min(positive_depth",
        )):
            status = "exact_nonzero_sign_or_denominator_functionality_boundary"
        elif "painter_wet_canvas.py" in path and "np.max(incoming_alpha)" in text:
            status = "exact_transparent_input_boundary"
        elif "qa_painter_long_soak_acceptance.py" in path and "7200" in text:
            status = "declared_two_hour_milestone_report_selection"
        elif "app/drawing.py" in path and (
            "start_x" in text or "start_y" in text or "wheel_delta" in text
            or "if delta > 0" in text or "elif delta < 0" in text
        ):
            status = "input_or_geometry_sign_routing_not_quality_threshold"
        elif "tests/" in path and "stroke_count" in text and "> 0" in text:
            status = "functional_nonempty_output_assertion"
        elif "tests/test_painter_ai_study_actions.py" in path and "mean_absolute_error" in text:
            status = "mathematical_nonnegative_error_domain"
        elif "tests/test_painter_ai_study_actions.py" in path and "luminance_correlation" in text:
            status = "mathematical_correlation_domain_minus_one_to_one"
        elif "tests/test_painter_file_exchange.py" in path and "visible_pixel_layer_stages" in text:
            status = "derived_8bit_one_lsb_per_visible_alpha_over_stage"
        elif "tests/test_painter_brush_dynamics.py" in path and "<= 1" in text:
            status = "declared_8bit_one_lsb_live_committed_parity"
        elif "tests/" in path and any(token in text for token in (
            "> 0.0", "< 0.0", "np.ptp", "count_nonzero",
        )):
            status = "exact_nonzero_sign_or_nonuniform_functionality_assertion"
        elif "tests/test_painter_material_paint.py" in path and "< 0.5" in text:
            status = "declared_signed_height_neutral_encoding_boundary"
        else:
            status = "unreviewed"
        row["review_status"] = status
    numeric_control_rows = _scan(
        app_files,
        (
            r"(?:if|elif|while)\b[^#\n]*(?:<=|>=|<|>)\s*-?(?:\d+(?:\.\d*)?|\.\d+)"
            r"|(?:min|max)\s*\([^#\n]*?(?:\d+(?:\.\d*)?|\.\d+)[^#\n]*?\)"
        ),
    )
    numeric_control_rows.extend(
        _scan_paint_action_schema_numeric_domains(ROOT / "app" / "actions" / "paint_namespace.py")
    )
    # A source decision found by the explicit scale/fabrication scan must not
    # be counted again as a generic clamp or schema candidate.
    numeric_scale_locations = {
        (str(row.get("path") or ""), int(row.get("line") or 0))
        for row in numeric_scale_rows
    }
    numeric_control_rows = [
        row for row in numeric_control_rows
        if (str(row.get("path") or ""), int(row.get("line") or 0))
        not in numeric_scale_locations
    ]
    for row in numeric_control_rows:
        status = _classify_numeric_control(row)
        # A path/function pattern is useful for routing a human review, but it
        # is not evidence that the literal itself was reviewed.  Earlier
        # versions accidentally promoted every broad ``reviewed_*`` bucket to
        # a Tiger product decision.  Keep those matches unresolved until an
        # explicit source/policy ledger entry covers the exact contract.
        if status.startswith("reviewed_"):
            status = "candidate_explicit_ledger_" + status.removeprefix("reviewed_")
        elif status in AUTO_ROUTED_NUMERIC_STATUSES:
            status = "candidate_explicit_ledger_" + status
        row["review_status"] = status
    numeric_ledger_status = _apply_decision_ledger(numeric_control_rows)
    capacity_policy_rows = _scan(
        app_files,
        r"(?:_max_document_bytes|_max_asset_bytes|default_tile_size|default_tile_budget_mb|default_undo_budget_mb|max_tasks|max_results|max_points|max_regions|max_strokes|max_workers|max_colors|max_size|max_zoom_percent|max_brush_size_px|wet_canvas_preview_max_dimension|max_materialized_dabs_per_stroke|painter_dynamic_dab_budget|tile_size|tile_budget_mb|undo_budget_mb|samples_per_segment|compresslevel)[^#\n]{0,100}(?:=|:)[^#\n]{0,100}\d",
    )
    for row in capacity_policy_rows:
        status = _classify_capacity_policy(row)
        if _decision_basis(status) == "explicit_tiger_product_policy_no_external_parity_claim":
            status = "candidate_explicit_ledger_capacity_" + status
        row["review_status"] = status
    capacity_ledger_status = _apply_decision_ledger(capacity_policy_rows)
    semantic_shortcut_rows = _scan(
        app_files,
        r"heuristic|approx(?:imate|imation)?|simulat(?:ed|ion)?|synthetic|mock|fake|proxy|placeholder|stub|workaround|best.?effort|assum(?:e|ption)|future work|later work|not implemented|reserved for|simple_relief|(?:color|base|accent)\.isValid\(\)",
    )
    for row in semantic_shortcut_rows:
        row["review_status"] = _classify_semantic_shortcut(row)
    # QA producers are part of the evidence chain: a swallowed exception there
    # can manufacture a PASS even when product code correctly reports failure.
    suppressed_exception_rows = _scan_suppressed_exceptions(app_files + qa_files)
    for row in suppressed_exception_rows:
        row["review_status"] = _classify_suppressed_exception(row)
    gl_cleanup_rows, direct_gl_cleanup_rows = _scan_gl_cleanup_contract(app_files)
    suppressed_exception_rows.extend(gl_cleanup_rows)
    suppressed_exception_rows.extend(direct_gl_cleanup_rows)
    exception_ledger_status = _apply_decision_ledger(
        suppressed_exception_rows,
        ledger_path=EXCEPTION_LEDGER_PATH,
        candidate_prefix="candidate_explicit_ledger_exception_",
    )
    localized_error_string_rows = _scan(
        qa_files + test_files,
        r"disk full|no space left|not enough space|access denied|read.?only|out of memory",
    )
    for row in localized_error_string_rows:
        row["review_status"] = _classify_localized_error_string_decision(row)
    covered_numeric_locations = {
        (str(row.get("path") or ""), int(row.get("line") or 0))
        for rows in (
            numeric_scale_rows,
            quality_threshold_rows,
            numeric_control_rows,
            capacity_policy_rows,
        )
        for row in rows
    }
    all_numeric_literal_site_rows = _scan_uncovered_numeric_literal_sites(
        app_files,
        set(),
    )
    numeric_literal_coverage_rows = [
        row for row in all_numeric_literal_site_rows
        if (str(row.get("path") or ""), int(row.get("line") or 0))
        not in covered_numeric_locations
    ]
    for row in numeric_literal_coverage_rows:
        row["review_status"] = _classify_numeric_literal_coverage(row)
    numeric_literal_ledger_status = _apply_decision_ledger(
        numeric_literal_coverage_rows,
    )
    unresolved_numeric_literal_rows = [
        row for row in numeric_literal_coverage_rows
        if str(row.get("review_status") or "").startswith(("candidate_", "unreviewed"))
    ]
    reviewed_groups = (
        numeric_scale_rows,
        quality_threshold_rows,
        numeric_control_rows,
        capacity_policy_rows,
        numeric_literal_coverage_rows,
        semantic_shortcut_rows,
        suppressed_exception_rows,
        localized_error_string_rows,
    )
    for rows in reviewed_groups:
        _attach_decision_basis(rows)
    decision_basis_counts = collections.Counter(
        str(row["decision_basis"])
        for rows in reviewed_groups
        for row in rows
    )
    unresolved_rows = [
        row
        for rows in reviewed_groups
        for row in rows
        if str(row.get("decision_basis") or "") == "unresolved"
    ]
    unresolved_candidate_count = sum(
        str(row.get("review_status") or "").startswith("candidate_")
        for row in unresolved_rows
    )
    unreviewed_defect_sites = {
        (str(row.get("path") or ""), int(row.get("line") or 0))
        for row in unresolved_rows
        if not str(row.get("review_status") or "").startswith("candidate_")
    }
    report = {
        "schema": "tigerstudio.painter.evidence-source-audit.v2",
        "scope": "painting_only_ui_design_excluded",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_inventory": _source_inventory_provenance(
            app_files
            + test_files
            + qa_files
            + docs
            + [Path(__file__), NUMERIC_LEDGER_PATH, EXCEPTION_LEDGER_PATH]
        ),
        "inventory": {
            "app_files": len(app_files),
            "test_files": len(test_files),
            "qa_files": len(qa_files),
            "documents": len(docs),
            "test_functions": len(test_functions),
            "numeric_literal_site_count": len(all_numeric_literal_site_rows),
            "numeric_literal_routed_scanner_gap_count": len(numeric_literal_coverage_rows),
            "unresolved_numeric_literal_site_count": len(unresolved_numeric_literal_rows),
            "decision_basis_counts": dict(sorted(decision_basis_counts.items())),
            "unresolved_candidate_count": unresolved_candidate_count,
            "unreviewed_defect_site_count": len(unreviewed_defect_sites),
            "numeric_decision_ledger": numeric_ledger_status,
            "numeric_literal_decision_ledger": numeric_literal_ledger_status,
            "capacity_decision_ledger": capacity_ledger_status,
            "exception_decision_ledger": exception_ledger_status,
        },
        "findings": {
            "offscreen_test_or_qa_files": sorted({row["path"] for row in offscreen}),
            "real_qtablet_event_constructors": _scan(test_files + qa_files, r"QTabletEvent\s*\("),
            "synthetic_tablet_objects": _scan(test_files + qa_files, r"class\s+_?TabletEvent|StylusSample\s*\("),
            "simulated_high_dpi": _scan(test_files + qa_files, r"QT_SCALE_FACTOR"),
            # Unit tests intentionally pass booleans as fixtures.  Only QA
            # producers can improperly elevate such a literal to evidence.
            "hardcoded_readiness_pass": _scan(
                qa_producers,
                r"(?:passed|ready|success|tests_passed|release_claim_passed)\s*=\s*True|[\"'](?:passed|ready|success|tests_passed|release_claim_passed)[\"']\s*:\s*True",
            ),
            "synthetic_gpu": _scan(test_files + qa_files, r"fake_render|gpu_uploader\s*=|def\s+upload\("),
            "micro_stress_thresholds": _scan(qa_files, r"elapsed_ms\s*<|stroke_ms\s*<|tile_stress_ms\s*<|range\(240\)"),
            "semantic_shortcut_markers": semantic_shortcut_rows,
            "suppressed_exception_sites": suppressed_exception_rows,
            "localized_error_string_decisions": localized_error_string_rows,
            "numeric_scale_conversions": numeric_scale_rows,
            "quality_decision_thresholds": quality_threshold_rows,
            "numeric_control_literals": numeric_control_rows,
            "uncovered_numeric_literal_sites": unresolved_numeric_literal_rows,
            "capacity_policy_literals": capacity_policy_rows,
            "historical_claim_mentions": _scan(
                docs,
                r"bounding-region approximation|tests_passed\s*=\s*True|product acceptance|release[_ -]ready\s*=\s*true",
            ),
            "official_source_urls": _scan(docs, r"https?://"),
            "module_static_references": module_static_references,
            "advanced_brush_product_references": advanced_brush_product_references,
        },
    }
    report["assessment"] = {
        "has_real_qtablet_event_test": bool(report["findings"]["real_qtablet_event_constructors"]),
        "has_native_high_dpi_probe": bool(_scan(qa_files, r"native_high_dpi")),
        "has_non_hardcoded_readiness": not bool(report["findings"]["hardcoded_readiness_pass"]),
        "all_app_modules_statically_referenced": all(row["mentioned_by_test_or_qa"] for row in module_static_references),
        "advanced_brush_product_integrated": all(
            row["product_paths"] for row in advanced_brush_product_references
        ),
        "unreferenced_app_modules": [row["path"] for row in module_static_references if not row["mentioned_by_test_or_qa"]],
        "unreviewed_numeric_scale_conversions": [
            row for row in numeric_scale_rows
            if str(row["review_status"]).startswith("unreviewed")
        ],
        "unreviewed_quality_decision_thresholds": [row for row in quality_threshold_rows if row["review_status"] == "unreviewed"],
        "unreviewed_numeric_control_literals": [
            row for row in numeric_control_rows
            if str(row["review_status"]).startswith(("unreviewed", "candidate_"))
        ],
        "unreviewed_numeric_literal_coverage_gaps": unresolved_numeric_literal_rows,
        "unreviewed_capacity_policy_literals": [
            row for row in capacity_policy_rows
            if row["review_status"] == "unreviewed"
        ],
        "unreviewed_semantic_shortcut_markers": [
            row for row in semantic_shortcut_rows
            if row["review_status"] == "unreviewed"
        ],
        "unreviewed_suppressed_exception_sites": [
            row for row in suppressed_exception_rows
            if row["review_status"] == "unreviewed"
        ],
        "unreviewed_localized_error_string_decisions": [
            row for row in localized_error_string_rows
            if str(row["review_status"]).startswith("unreviewed")
        ],
        "unresolved_decision_basis_rows": [
            row
            for rows in reviewed_groups
            for row in rows
            if row["decision_basis"] == "unresolved"
        ],
        "classification": "source_and_synthetic_audit_not_release_certification",
    }
    destination = ROOT / "debugCapture" / "painter" / "evidence_audit" / "report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "path": str(destination),
        **report["inventory"],
        "has_real_qtablet_event_test": report["assessment"]["has_real_qtablet_event_test"],
        "has_native_high_dpi_probe": report["assessment"]["has_native_high_dpi_probe"],
        "has_non_hardcoded_readiness": report["assessment"]["has_non_hardcoded_readiness"],
        "all_app_modules_statically_referenced": report["assessment"]["all_app_modules_statically_referenced"],
        "unresolved_decision_basis_count": len(report["assessment"]["unresolved_decision_basis_rows"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
