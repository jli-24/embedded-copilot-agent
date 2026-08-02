from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


_WORKTREE_SRC = (Path(__file__).resolve().parents[2] / "src").resolve()


def _virtualenv_site_packages() -> tuple[Path, ...]:
    paths: list[Path] = []
    for entry in sys.path:
        if not entry:
            continue
        candidate = Path(entry).resolve()
        if (
            candidate.name.casefold() != "site-packages"
            or ".venv" not in {part.casefold() for part in candidate.parts}
            or not candidate.is_dir()
            or candidate in paths
        ):
            continue
        paths.append(candidate)
    if not paths:
        raise RuntimeError("benchmark subprocess dependency root is unavailable")
    return tuple(paths)


def _environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = os.pathsep.join(
        str(path) for path in (_WORKTREE_SRC, *_virtualenv_site_packages())
    )
    return environment


def test_public_import_exports_only_runner_without_production_imports(tmp_path) -> None:
    script = """
import json
import sys
import embedded_copilot.benchmark as benchmark

forbidden = [
    "embedded_copilot.agents",
    "embedded_copilot.agents.registry",
    "embedded_copilot.agents.workflow",
    "embedded_copilot.api",
    "embedded_copilot.supervisor",
    "embedded_copilot.firmware",
    "embedded_copilot.hardware",
    "embedded_copilot.pcb",
    "embedded_copilot.debug",
    "embedded_copilot.knowledge",
    "embedded_copilot.core.capability",
    "embedded_copilot.benchmark.capability",
    "embedded_copilot.benchmark.datasets",
    "embedded_copilot.benchmark.run",
]
print(json.dumps({
    "all": benchmark.__all__,
    "forbidden": [name for name in forbidden if name in sys.modules],
}))
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=_environment(),
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(completed.stdout) == {
        "all": ["BenchmarkRunner"],
        "forbidden": [],
    }
    assert completed.stderr == ""
    assert list(tmp_path.iterdir()) == []


def test_cli_module_has_no_import_effect_and_reserved_command_returns_two(
    tmp_path,
) -> None:
    imported = subprocess.run(
        [sys.executable, "-c", "import embedded_copilot.benchmark.run"],
        cwd=tmp_path,
        env=_environment(),
        capture_output=True,
        text=True,
        check=True,
    )
    executed = subprocess.run(
        [sys.executable, "-m", "embedded_copilot.benchmark.run"],
        cwd=tmp_path,
        env=_environment(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert imported.stdout == imported.stderr == ""
    assert executed.returncode == 2
    assert executed.stdout == ""
    assert executed.stderr.strip() == "benchmark CLI is reserved and not implemented"
