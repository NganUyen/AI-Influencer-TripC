#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.production.yml"
DEFAULT_ENV_FILE="${REPO_ROOT}/Project/.env.production"
ENV_FILE="${PROJECT_ENV_FILE:-${DEFAULT_ENV_FILE}}"

if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" exec -T backend python - <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request


def _http_json(method: str, url: str, headers: dict | None = None, payload: dict | None = None):
    body = None
    request_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    request = urllib.request.Request(url, method=method, data=body)
    for key, value in request_headers.items():
        request.add_header(key, value)

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except ValueError:
                parsed = {"raw": raw}
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except ValueError:
            parsed = {"raw": raw}
        return exc.code, parsed


def _failed_response_message(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None

    error = payload.get("error")
    status = str(payload.get("status") or "").strip().lower()
    if status != "failed" and not isinstance(error, dict):
        return None

    parts: list[str] = []
    response_id = str(payload.get("id") or "").strip()
    model = str(payload.get("model") or "").strip()
    if response_id:
        parts.append(f"id={response_id}")
    if model:
        parts.append(f"model={model}")
    if status:
        parts.append(f"status={status}")

    if isinstance(error, dict):
        code = str(error.get("code") or "").strip()
        message = str(error.get("message") or "").strip()
        if code:
            parts.append(f"code={code}")
        if message:
            parts.append(f"message={message}")

    return ", ".join(parts) if parts else "request failed"


def check_openclaw() -> None:
    base = (os.environ.get("OPENCLAW_API_URL") or "").rstrip("/")
    if not base:
        raise SystemExit("OpenClaw: OPENCLAW_API_URL is not configured")

    status, _ = _http_json("GET", f"{base}/healthz")
    if status != 200:
        raise SystemExit(f"OpenClaw: healthz returned {status}")

    print("OpenClaw: healthz reachable with status 200")

    api_key = (os.environ.get("OPENCLAW_API_KEY") or "").strip()
    agent_id = (os.environ.get("OPENCLAW_AGENT_ID") or "main").strip() or "main"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    probe_payload = {
        "model": f"openclaw:{agent_id}",
        "input": "Reply with plain text ok.",
        "user": "healthcheck:telegram-openclaw",
    }
    status, payload = _http_json(
        "POST",
        f"{base}/v1/responses",
        headers=headers,
        payload=probe_payload,
    )
    if status != 200:
        raise SystemExit(f"OpenClaw: /v1/responses returned {status} ({payload})")

    failed_message = _failed_response_message(payload)
    if failed_message:
        raise SystemExit(f"OpenClaw: /v1/responses failed ({failed_message})")

    print("OpenClaw: /v1/responses probe succeeded")


def check_telegram_webhook() -> None:
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        print("Telegram: TELEGRAM_BOT_TOKEN is not configured (skipped)")
        return

    backend_public_url = (os.environ.get("BACKEND_PUBLIC_URL") or "").strip().rstrip("/")
    expected_url = f"{backend_public_url}/api/webhooks/telegram" if backend_public_url else None
    status, payload = _http_json("GET", f"https://api.telegram.org/bot{token}/getWebhookInfo")

    if status != 200 or not isinstance(payload, dict) or not payload.get("ok"):
        raise SystemExit(f"Telegram: getWebhookInfo failed with status {status}")

    result = payload.get("result") or {}
    actual_url = str(result.get("url") or "")
    pending_updates = int(result.get("pending_update_count") or 0)
    last_error = str(result.get("last_error_message") or "").strip()

    if not actual_url:
        raise SystemExit("Telegram: webhook URL is empty; run register_telegram_webhook.py")

    if expected_url and actual_url != expected_url:
        raise SystemExit(
            f"Telegram: webhook URL mismatch (expected={expected_url}, actual={actual_url})"
        )

    print(f"Telegram: webhook configured at {actual_url}")
    print(f"Telegram: pending updates = {pending_updates}")

    if last_error:
        print(f"Telegram: last webhook error = {last_error}")


check_openclaw()
check_telegram_webhook()
print("Telegram/OpenClaw checks passed.")
PY
