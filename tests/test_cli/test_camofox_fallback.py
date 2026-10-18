"""Camofox fallback policy through the real fetch CLI, offline."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hyperresearch.cli import app
from hyperresearch.web.base import WebResult

runner = CliRunner()
URL = "https://example.com/public-company"


class _BlockedProvider:
    name = "builtin"

    def fetch(self, _url: str) -> WebResult:
        raise RuntimeError("HTTP 403 fetching https://example.com/public-company")


class _CamofoxProvider:
    name = "camofox"
    calls = 0

    def fetch(self, url: str) -> WebResult:
        type(self).calls += 1
        return WebResult(url=url, title="Company", content="Rendered public company details. " * 20)


@pytest.fixture
def vault_dir(tmp_path: Path) -> Path:
    result = runner.invoke(app, ["init", str(tmp_path / "kb"), "--name", "Camofox Test"])
    assert result.exit_code == 0
    root = tmp_path / "kb"
    cfg = root / ".hyperresearch" / "config.toml"
    cfg.write_text(
        cfg.read_text(encoding="utf-8").replace(
            'camofox_url = ""', 'camofox_url = "http://camofox.test:9377"'
        ),
        encoding="utf-8",
    )
    return root


def test_fetch_uses_camofox_after_public_403(vault_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hyperresearch.core import oa
    from hyperresearch.web import base

    _CamofoxProvider.calls = 0
    monkeypatch.setattr(oa, "rescue_full_text", lambda *_args, **_kwargs: (None, None))
    monkeypatch.setattr(
        base,
        "get_provider",
        lambda name=None, **_kwargs: _CamofoxProvider() if name == "camofox" else _BlockedProvider(),
    )
    os.chdir(vault_dir)

    result = runner.invoke(app, ["fetch", URL, "--json"])

    assert result.exit_code == 0
    assert _CamofoxProvider.calls == 1
    assert any((vault_dir / "research" / "notes").glob("*.md"))


def test_fetch_never_uses_camofox_for_captcha(vault_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hyperresearch.core import oa
    from hyperresearch.web import base

    class _CaptchaProvider:
        name = "builtin"

        def fetch(self, url: str) -> WebResult:
            return WebResult(url=url, title="CAPTCHA", content="Please verify you are human. " * 20)

    _CamofoxProvider.calls = 0
    monkeypatch.setattr(oa, "rescue_full_text", lambda *_args, **_kwargs: (None, None))
    monkeypatch.setattr(
        base,
        "get_provider",
        lambda name=None, **_kwargs: _CamofoxProvider() if name == "camofox" else _CaptchaProvider(),
    )
    os.chdir(vault_dir)

    result = runner.invoke(app, ["fetch", URL, "--json"])

    assert result.exit_code == 1
    assert _CamofoxProvider.calls == 0
