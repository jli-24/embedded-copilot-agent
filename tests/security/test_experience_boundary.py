from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
PACKAGE_ROOT = ROOT / "src" / "embedded_copilot"
WEB_ROOT = ROOT / "web" / "copilot"
TARGETS = (PACKAGE_ROOT / "experience", WEB_ROOT)
TARGET_FILES = (
    PACKAGE_ROOT / "api" / "experience_models.py",
    PACKAGE_ROOT / "api" / "experience_routes.py",
    PACKAGE_ROOT / "services" / "experience_runtime.py",
)
EXISTING_CONTRACT_ADAPTER = PACKAGE_ROOT / "experience" / "existing_contracts.py"
EXPERIENCE_RUNTIME = PACKAGE_ROOT / "services" / "experience_runtime.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "embedded_copilot.hardware_design.artifact",
    "embedded_copilot.hardware_design.evidence",
    "embedded_copilot.hardware_design.decision",
    "embedded_copilot.hardware_design.approval",
    "embedded_copilot.intelligence.gateway",
    "embedded_copilot.knowledge.manager",
    "embedded_copilot.search.provider",
    "embedded_copilot.rag",
    "embedded_copilot.agents",
    "embedded_copilot.supervisor",
    "langgraph",
    "openai",
    "chromadb",
    "sqlite3",
    "sqlalchemy",
    "shelve",
)
FORBIDDEN_FIELDS = {
    "gpio",
    "component",
    "components",
    "connection",
    "connections",
    "voltage",
    "current",
    "artifact_update",
}
FORBIDDEN_SESSION_KEYS = {
    "artifact",
    "artifact_instance",
    "model_response",
    "reasoning_chain",
    "documents",
    "file_content",
}
ALLOWED_SESSION_KEYS = {
    "session_id",
    "answer_summary",
    "handoff",
    "review_receipt",
}


def _python_files() -> tuple[Path, ...]:
    files = tuple(
        sorted(
            (
                path
                for target in TARGETS
                if target.is_dir()
                for path in target.rglob("*.py")
            ),
        )
    ) + tuple(path for path in TARGET_FILES if path.is_file())
    assert files, "Experience Layer sources are missing"
    return files


def _name(value: ast.expr) -> str | None:
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return value.attr
    return None


def test_experience_has_no_forbidden_dependencies() -> None:
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    not alias.name.startswith(FORBIDDEN_IMPORT_PREFIXES)
                    for alias in node.names
                ), path
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(FORBIDDEN_IMPORT_PREFIXES), path
                if module.startswith("embedded_copilot.copilot"):
                    assert path in {
                        EXISTING_CONTRACT_ADAPTER,
                        EXPERIENCE_RUNTIME,
                    }, path
                if path.is_relative_to(WEB_ROOT):
                    assert not module.startswith("embedded_copilot"), path
                assert not (
                    module == "embedded_copilot.hardware_design.artifact"
                    and any(alias.name == "*" for alias in node.names)
                ), path


def test_experience_has_no_lifecycle_calls_or_dynamic_bypass() -> None:
    forbidden_calls = {
        ("artifact", "create"),
        ("artifact", "update"),
        ("artifact", "delete"),
        ("decision", "create"),
        ("decision", "update"),
        ("approval", "transition"),
    }
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            assert _name(node.func) not in {
                "getattr",
                "__import__",
                "import_module",
            }, path
            if isinstance(node.func, ast.Attribute):
                assert (
                    _name(node.func.value),
                    node.func.attr,
                ) not in forbidden_calls, path


def test_experience_defines_no_engineering_owned_fields() -> None:
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign):
                assert _name(node.target) not in FORBIDDEN_FIELDS, path
            elif isinstance(node, ast.Assign):
                assert all(
                    _name(target) not in FORBIDDEN_FIELDS for target in node.targets
                ), path
            elif isinstance(node, ast.keyword) and node.arg is not None:
                assert node.arg not in FORBIDDEN_FIELDS, path


def test_browser_session_state_does_not_store_forbidden_objects() -> None:
    for path in _python_files():
        if not path.is_relative_to(WEB_ROOT):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript):
                continue
            if not (
                isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "st"
                and node.value.attr == "session_state"
            ):
                continue
            if isinstance(node.slice, ast.Constant) and isinstance(
                node.slice.value, str
            ):
                assert node.slice.value not in FORBIDDEN_SESSION_KEYS, path


def test_browser_session_state_keys_are_allowlisted() -> None:
    state_path = WEB_ROOT / "state.py"
    tree = ast.parse(state_path.read_text(encoding="utf-8"), filename=str(state_path))
    declared_keys = {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id.endswith("_KEY")
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }

    assert set(declared_keys.values()) == ALLOWED_SESSION_KEYS

    for path in WEB_ROOT.rglob("*.py"):
        page_tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(page_tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if not (
                        isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Attribute)
                        and isinstance(target.value.value, ast.Name)
                        and target.value.value.id == "st"
                        and target.value.attr == "session_state"
                    ):
                        continue
                    if isinstance(target.slice, ast.Constant):
                        key = target.slice.value
                    elif isinstance(target.slice, ast.Name):
                        key = declared_keys.get(target.slice.id)
                    else:
                        key = None
                    assert key in ALLOWED_SESSION_KEYS, path
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if (
                    keyword.arg == "key"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    assert keyword.value.value in ALLOWED_SESSION_KEYS, path


def test_backend_has_no_reverse_dependency_on_experience_ui() -> None:
    for path in PACKAGE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    not alias.name.startswith("web.copilot") for alias in node.names
                ), path
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("web.copilot"), path


def test_reasoning_page_only_uses_the_copilot_client_boundary() -> None:
    path = WEB_ROOT / "app_pages" / "reasoning_intelligence.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden_imports = {
        "embedded_copilot",
        "pathlib",
        "os",
        "io",
        "pypdf",
        "fitz",
    }
    forbidden_calls = {
        "open",
        "file_uploader",
        "download_button",
        "write_text",
        "write_bytes",
        "read_text",
        "read_bytes",
        "run",
        "execute",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                alias.name.split(".", maxsplit=1)[0] not in forbidden_imports
                for alias in node.names
            ), path
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", maxsplit=1)[0]
            assert root not in forbidden_imports, path
        elif isinstance(node, ast.Call):
            assert _name(node.func) not in forbidden_calls, path
