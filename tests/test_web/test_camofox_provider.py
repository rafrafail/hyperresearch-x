from __future__ import annotations

from typing import ClassVar

import pytest

from hyperresearch.core.config import FetchSettings
from hyperresearch.web.camofox_provider import CamofoxProvider


class _Response:
    def __init__(self, payload: dict | None = None):
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _Client:
    calls: ClassVar[list[tuple[str, str, dict | None]]] = []

    def __init__(self, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, url: str, params: dict | None = None):
        self.calls.append(("get", url, params))
        if url.endswith("/health"):
            return _Response({"ok": True})
        return _Response({"snapshot": '- heading "Rendered company page"\n- text "Large-format printing"'})

    def post(self, url: str, json: dict):
        self.calls.append(("post", url, json))
        return _Response({"tabId": "tab-1"})

    def delete(self, url: str):
        self.calls.append(("delete", url, None))
        return _Response({"ok": True})


def test_camofox_requires_explicit_endpoint() -> None:
    with pytest.raises(ValueError, match="camofox_url"):
        CamofoxProvider()


def test_camofox_fetch_uses_ssrf_gate_and_cleans_up(monkeypatch: pytest.MonkeyPatch) -> None:
    from hyperresearch.web import camofox_provider

    _Client.calls = []
    checked: list[tuple[str, tuple[str, ...]]] = []
    monkeypatch.setattr(camofox_provider.httpx, "Client", _Client)
    monkeypatch.setattr(
        camofox_provider,
        "check_url",
        lambda url, allowed: checked.append((url, allowed)),
    )
    provider = CamofoxProvider(
        FetchSettings(camofox_url="http://camofox.test:9377", allow_private_hosts=("mirror.local",))
    )

    result = provider.fetch("https://example.com/company")

    assert checked == [("https://example.com/company", ("mirror.local",))]
    assert result.title == "Rendered company page"
    assert "Large-format printing" in result.content
    assert result.metadata == {"provider": "camofox", "camofox_snapshot": True}
    assert any(method == "delete" and "/sessions/hyperresearch_" in url for method, url, _ in _Client.calls)


def test_camofox_is_registered_in_provider_factory() -> None:
    from hyperresearch.web.base import get_provider

    provider = get_provider("camofox", settings=FetchSettings(camofox_url="http://camofox.test:9377"))

    assert isinstance(provider, CamofoxProvider)
