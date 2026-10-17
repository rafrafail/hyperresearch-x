"""Read-only MCP boundary tests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Generator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hyperresearch.cli import app

mcp = pytest.importorskip("hyperresearch.mcp.server")

runner = CliRunner()


@pytest.fixture
def vault_with_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    vault_dir = tmp_path / "vault"
    result = runner.invoke(app, ["init", str(vault_dir)])
    assert result.exit_code == 0, result.output
    monkeypatch.chdir(vault_dir)
    result = runner.invoke(app, ["note", "new", "Boundary Note"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0, result.output
    mcp._vault = None
    yield vault_dir
    mcp._vault = None


def _notes_digest(root: Path) -> dict[str, str]:
    notes_dir = root / "research/notes"
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(notes_dir.rglob("*.md"))
    }


def test_traversal_shaped_note_id_is_not_a_filesystem_read(vault_with_note: Path) -> None:
    before = _notes_digest(vault_with_note)

    result = json.loads(mcp.read_note("../../outside"))

    assert result == {"error": "Note not found: ../../outside"}
    assert _notes_digest(vault_with_note) == before


def test_read_many_returns_missing_ids_without_mutating_vault(vault_with_note: Path) -> None:
    before = _notes_digest(vault_with_note)

    result = json.loads(mcp.read_many("boundary-note,../../outside"))

    assert [note["id"] for note in result["notes"]] == ["boundary-note"]
    assert result["not_found"] == ["../../outside"]
    assert _notes_digest(vault_with_note) == before
