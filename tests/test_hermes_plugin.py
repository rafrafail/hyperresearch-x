"""Portable Hermes plugin package contract tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"


def _read_json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_portable_plugin_manifest_has_required_v1_contract() -> None:
    manifest = _read_json("plugin.json")

    assert manifest["$schema"] == PLUGIN_SCHEMA
    assert manifest["name"] == "hyperresearch"
    assert manifest["version"]
    assert manifest["description"]
    assert manifest["license"] == "MIT"
    assert manifest["repository"] == "https://github.com/jordan-gibbs/hyperresearch"
    assert all("token" not in key.lower() and "secret" not in key.lower() for key in manifest)


def test_portable_mcp_manifest_starts_read_only_server() -> None:
    mcp = _read_json("mcp.json")

    assert mcp["$schema"] == MCP_SCHEMA
    assert set(mcp["mcpServers"]) == {"hyperresearch"}
    server = mcp["mcpServers"]["hyperresearch"]
    assert server == {
        "type": "stdio",
        "command": "hyperresearch",
        "args": ["mcp", "--read-only"],
    }


def test_deep_research_skill_includes_hermes_adapter_without_dropping_other_agents() -> None:
    skill = (ROOT / "skills/deep-research/SKILL.md").read_text(encoding="utf-8")

    assert "## 3C. Hermes Agent" in skill
    assert "canonical query" in skill
    assert "run manifest" in skill
    assert "resume" in skill
    assert "Claude Code" in skill
    assert "OpenAI Codex" in skill
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "### Hermes Agent" in readme
    assert "hermes plugins doctor" in readme
    assert "hyperresearch mcp --read-only" in readme


def _mcp_tool_names(read_only: bool) -> set[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    if read_only:
        env["HYPERRESEARCH_MCP_READ_ONLY"] = "1"
    else:
        env.pop("HYPERRESEARCH_MCP_READ_ONLY", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from hyperresearch.mcp.server import server; "
            "import json; print(json.dumps(sorted(server._tool_manager._tools)))",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return set(json.loads(result.stdout))


def test_read_only_mcp_hides_mutating_tools() -> None:
    names = _mcp_tool_names(read_only=True)

    assert {"search_notes", "read_note", "read_many", "list_notes", "vault_status"} <= names
    assert {"fetch_url", "create_note", "update_note"}.isdisjoint(names)


def test_default_mcp_keeps_upstream_write_tools() -> None:
    names = _mcp_tool_names(read_only=False)

    assert {"fetch_url", "create_note", "update_note"} <= names
