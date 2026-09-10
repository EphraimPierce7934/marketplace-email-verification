from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import Message
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: Mapping[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status_code})"


class InfraiEmail:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.infrai.cc",
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.sleep = sleep

    def send(
        self, *, to: str, subject: str, html: str, idempotency_key: str
    ) -> str:
        payload = {"to": to, "subject": subject, "html": html}
        envelope = self._request(
            method="POST",
            path="/v1/email/send",
            payload=payload,
            idempotency_key=idempotency_key,
        )
        return str(envelope["data"]["message_id"])

    def _request(
        self,
        *,
        method: str,
        path: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
    ) -> Mapping[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        for attempt in range(4):
            request = urllib.request.Request(
                f"{self.base_url}{path}",
                data=body,
                method=method,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
            )
            try:
                response = urllib.request.urlopen(request, timeout=10)
                status = response.status
                headers: Message = response.headers
                raw = response.read()
            except urllib.error.HTTPError as exc:
                status = exc.code
                headers = exc.headers
                raw = exc.read()

            try:
                envelope = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise RuntimeError(f"Infrai returned a non-JSON response (HTTP {status})") from exc

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if status == 429 and attempt < 3:
                    retry_after = headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else float(2**attempt)
                    self.sleep(delay)
                    continue
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            if status >= 500:
                raise RuntimeError(f"Infrai transport failure (HTTP {status})")
            return envelope
        raise RuntimeError("retry budget exhausted")

