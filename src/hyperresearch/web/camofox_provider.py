"""Camofox browser fallback for public pages blocked by direct HTTP.

Camofox is used only after a normal provider reports a 403/429 or a non-CAPTCHA
bot wall. It does not handle credentials, solve CAPTCHAs, or bypass paywalls.
The self-hosted REST endpoint is opt-in through ``[fetch].camofox_url``; an
optional bearer key stays in ``CAMOFOX_API_KEY`` and is never read from config.
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import UTC, datetime

import httpx

from hyperresearch.core.config import FetchSettings
from hyperresearch.web.base import WebResult
from hyperresearch.web.safe_http import check_url


class CamofoxProvider:
    """Fetch public rendered text through a configured Camofox REST service."""

    name = "camofox"

    def __init__(self, settings: FetchSettings | None = None):
        self._settings = settings or FetchSettings()
        self._base_url = self._settings.camofox_url.rstrip("/")
        if not self._base_url:
            raise ValueError(
                "Camofox is not configured; set fetch.camofox_url in "
                ".hyperresearch/config.toml"
            )

    def _headers(self) -> dict[str, str]:
        api_key = os.environ.get("CAMOFOX_API_KEY", "").strip()
        return {"Authorization": f"Bearer {api_key}"} if api_key else {}

    @staticmethod
    def _snapshot_to_text(snapshot: str) -> tuple[str, str]:
        """Make a stable readable record from Camofox's accessibility snapshot."""
        lines = [line.strip() for line in snapshot.splitlines() if line.strip()]
        text = "\n".join(lines)
        title = ""
        for line in lines:
            match = re.search(r"(?:heading|document)\s+['\"]?(.+?)['\"]?(?:\s+\[|$)", line, re.I)
            if match:
                title = match.group(1).strip(" '\"")
                break
        return title, text

    def fetch(self, url: str) -> WebResult:
        # The browser is a separate network client, so enforce the same SSRF
        # boundary before handing it a URL.
        check_url(url, self._settings.allow_private_hosts)
        user_id = f"hyperresearch_{uuid.uuid4().hex}"
        timeout = httpx.Timeout(self._settings.camofox_timeout_s)
        session_created = False
        try:
            with httpx.Client(timeout=timeout, headers=self._headers(), follow_redirects=False) as client:
                health = client.get(f"{self._base_url}/health")
                health.raise_for_status()
                created = client.post(
                    f"{self._base_url}/tabs",
                    json={"userId": user_id, "listItemId": user_id, "url": url},
                )
                created.raise_for_status()
                tab_id = created.json().get("tabId")
                if not isinstance(tab_id, str) or not tab_id:
                    raise RuntimeError("Camofox did not return a tabId")
                session_created = True
                snapshot_response = client.get(
                    f"{self._base_url}/tabs/{tab_id}/snapshot",
                    params={"userId": user_id},
                )
                snapshot_response.raise_for_status()
                snapshot = snapshot_response.json().get("snapshot", "")
                if not isinstance(snapshot, str) or not snapshot.strip():
                    raise RuntimeError("Camofox returned an empty accessibility snapshot")
                title, content = self._snapshot_to_text(snapshot)
                return WebResult(
                    url=url,
                    title=title,
                    content=content,
                    fetched_at=datetime.now(UTC),
                    metadata={"provider": self.name, "camofox_snapshot": True},
                )
        finally:
            if session_created:
                try:
                    with httpx.Client(timeout=timeout, headers=self._headers()) as client:
                        client.delete(f"{self._base_url}/sessions/{user_id}")
                except httpx.HTTPError:
                    # A cleanup failure must not hide the source result; Camofox
                    # can garbage-collect this short-lived anonymous session.
                    pass

    def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        raise NotImplementedError(
            "Camofox is a fetch fallback, not a search engine. Search with the "
            "agent or scholarly providers, then fetch selected URLs."
        )
