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


def check_provider(label: str, base_url_var: str, key_var: str, path: str) -> None:
    base_url = (os.environ.get(base_url_var) or "").rstrip("/")
    if not base_url:
        raise SystemExit(f"{label}: {base_url_var} is not configured")

    api_key = (os.environ.get(key_var) or "").strip()
    if not api_key:
        raise SystemExit(f"{label}: {key_var} is not configured")

    request = urllib.request.Request(
        f"{base_url}{path}",
        headers={
            "Accept": "application/json",
            "Authorization": api_key,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = response.getcode()
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read()
        content_type = exc.headers.get("Content-Type", "")
    except Exception as exc:  # pragma: no cover - shell smoke path
        raise SystemExit(f"{label}: API check failed: {exc}") from exc

    if status not in (200, 401):
        raise SystemExit(f"{label}: API returned unhealthy status {status}")

    if status == 200:
        text = body.decode("utf-8", errors="ignore")
        try:
            json.loads(text)
        except ValueError as exc:
            preview = text.strip()[:160]
            if "text/html" in content_type.lower() or preview.startswith("<"):
                raise SystemExit(
                    f"{label}: API returned HTML instead of JSON"
                ) from exc
            raise SystemExit(
                f"{label}: API returned invalid JSON"
            ) from exc

    suffix = " (API key/bootstrap still needs attention)" if status == 401 else ""
    print(f"{label}: API reachable with status {status}{suffix}")


check_provider("Postiz", "POSTIZ_API_URL", "POSTIZ_API_KEY", "/api/public/v1/integrations")
check_provider("GrowChief", "GROWCHIEF_API_URL", "GROWCHIEF_API_KEY", "/api/public/workflows")
PY
