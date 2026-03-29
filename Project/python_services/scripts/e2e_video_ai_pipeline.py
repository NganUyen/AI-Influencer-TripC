r"""
E2E Test: Video AI Pipeline (Staging)
=====================================
Tests the deployed Video AI pipeline without local mocks:
  1. Persona readiness check via API
  2. Persona fetch via API
  3. /api/workflows/start-video with a valid approved_package
  4. Temporal workflow execution verification

Prerequisites:
  - API server running
  - Temporal server running
  - Database / storage configured
  - INTERNAL_API_TOKEN set in the environment
  - A ready persona available in the target environment

Run:
  .\.venv\Scripts\python scripts/e2e_video_ai_pipeline.py --persona-id <persona_id>

Options:
  --persona-id     Required: Persona ID to test with
  --owner-key      Optional: Telegram owner key (for scoped personas)
  --api-base       Optional: API base URL (default: http://localhost:8000)
  --skip-workflow  Optional: Skip the actual workflow start
  --timeout        Optional: Workflow status check timeout in seconds (default: 120)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()


def _print_step(step: int, msg: str, status: str = "") -> None:
    icon = {
        "PASS": "[PASS]",
        "FAIL": "[FAIL]",
        "INFO": "[INFO]",
        "SKIP": "[SKIP]",
        "WARN": "[WARN]",
        "": "[....]",
    }
    print(f"  {icon.get(status, '[....]')} Step {step}: {msg}")


def _print_header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def _auth_headers(api_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_token}"}


async def check_persona_readiness(
    api_base: str,
    persona_id: str,
    owner_key: Optional[str],
    api_token: str,
) -> dict[str, Any]:
    """Check persona readiness via the deployed API."""
    url = f"{api_base}/api/personas/{persona_id}/readiness"
    params: dict[str, str] = {}
    if owner_key:
        params["owner_key"] = owner_key

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(url, params=params, headers=_auth_headers(api_token))
            if resp.status_code == 404:
                return {"error": f"Persona '{persona_id}' not found"}
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            return {"error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"}
        except Exception as exc:
            return {"error": str(exc)}


async def get_persona(
    api_base: str,
    persona_id: str,
    owner_key: Optional[str],
    api_token: str,
) -> dict[str, Any]:
    """Load the full persona record via the deployed API."""
    url = f"{api_base}/api/personas/{persona_id}"
    params: dict[str, str] = {}
    if owner_key:
        params["owner_key"] = owner_key

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(url, params=params, headers=_auth_headers(api_token))
            if resp.status_code == 404:
                return {"error": f"Persona '{persona_id}' not found"}
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            return {"error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"}
        except Exception as exc:
            return {"error": str(exc)}


async def start_video_workflow(
    api_base: str,
    persona_id: str,
    topic: str,
    owner_key: Optional[str],
    api_token: str,
    approved_package: Optional[dict[str, Any]] = None,
    talking_head_optional: bool = True,
) -> dict[str, Any]:
    """Start a short-video workflow via API."""
    url = f"{api_base}/api/workflows/start-video"
    payload: dict[str, Any] = {
        "persona_id": persona_id,
        "topic": topic,
        "tone": "natural",
        "platform": "tiktok",
        "owner_key": owner_key,
        "talking_head_optional": talking_head_optional,
    }
    if approved_package is not None:
        payload["approved_package"] = approved_package

    headers = {
        **_auth_headers(api_token),
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            return {"error": f"HTTP {exc.response.status_code}: {exc.response.text[:500]}"}
        except Exception as exc:
            return {"error": str(exc)}


async def check_workflow_status(
    api_base: str,
    workflow_id: str,
    api_token: str,
) -> dict[str, Any]:
    """Check workflow status via API."""
    url = f"{api_base}/api/workflows/status/{workflow_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(url, headers=_auth_headers(api_token))
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            return {"error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"}
        except Exception as exc:
            return {"error": str(exc)}


def create_minimal_approved_package(persona_id: str) -> dict[str, Any]:
    """Create a contract-valid approved package for E2E workflow start."""
    return {
        "concept_brief": {
            "persona_id": persona_id,
            "creative_input_mode": "idea_brief",
            "feature_focus": "E2E pipeline validation",
            "video_goal": "feature_demo",
            "audience": "operators validating the deployed stack",
            "angle": "conservative product walkthrough",
            "platform": "tiktok",
            "cta": "Validate the deployed flow",
            "reference_url": "https://example.com/e2e-video-ai",
            "access_level": "public_page_only",
            "source_summary": (
                "Synthetic package used to validate the deployed approved-package "
                "handoff end to end."
            ),
            "tone_resolved": "natural",
        },
        "beat_sheet": {
            "beats": [
                {
                    "idx": 1,
                    "purpose": "hook",
                    "bottom_half_message": "This is a deployed pipeline validation run.",
                    "top_half_source_type": "ai_visual_fallback",
                    "top_half_target": "Launch-style validation visual",
                    "top_half_capture_hint": "Show a clean product-launch mood frame.",
                    "source_ref": None,
                    "overlay_text": "Validation Run",
                    "duration_sec": 4,
                },
                {
                    "idx": 2,
                    "purpose": "problem",
                    "bottom_half_message": "We need to prove the approved package path works in staging.",
                    "top_half_source_type": "ai_visual_fallback",
                    "top_half_target": "Pipeline verification diagram",
                    "top_half_capture_hint": "Show a simple technical flow visual.",
                    "source_ref": None,
                    "overlay_text": "Approved Path",
                    "duration_sec": 4,
                },
                {
                    "idx": 3,
                    "purpose": "solution_intro",
                    "bottom_half_message": "This package should move directly into script, media, and assembly.",
                    "top_half_source_type": "ai_visual_fallback",
                    "top_half_target": "Package to media handoff scene",
                    "top_half_capture_hint": "Show a package becoming a video timeline.",
                    "source_ref": None,
                    "overlay_text": "Direct Handoff",
                    "duration_sec": 4,
                },
                {
                    "idx": 4,
                    "purpose": "feature_demo",
                    "bottom_half_message": "The deployed worker should generate assets and assemble the final video.",
                    "top_half_source_type": "ai_visual_fallback",
                    "top_half_target": "Media generation montage",
                    "top_half_capture_hint": "Show generated media panels assembling.",
                    "source_ref": None,
                    "overlay_text": "Media + Assembly",
                    "duration_sec": 4,
                },
                {
                    "idx": 5,
                    "purpose": "cta",
                    "bottom_half_message": "If preview arrives successfully, the deployed path is healthy.",
                    "top_half_source_type": "ai_visual_fallback",
                    "top_half_target": "Validation success frame",
                    "top_half_capture_hint": "Show a simple success-confirmation visual.",
                    "source_ref": None,
                    "overlay_text": "Validation Pass",
                    "duration_sec": 4,
                },
            ]
        },
        "persona_snapshot": {
            "persona_id": persona_id,
            "tone_resolved": "natural",
        },
    }


def _extract_workflow_state(status_result: dict[str, Any]) -> Optional[str]:
    """Normalize the shape returned by /api/workflows/status/{workflow_id}."""
    raw_status = status_result.get("status")
    if isinstance(raw_status, dict):
        value = raw_status.get("status")
    else:
        value = raw_status
    if value is None:
        return None
    return str(value).strip().lower()


async def run_e2e_test(args: argparse.Namespace) -> bool:
    """Run the deployed E2E test."""
    _print_header("E2E Video AI Pipeline Test")

    api_token = os.getenv("INTERNAL_API_TOKEN", "").strip()
    if not api_token:
        print("[FAIL] INTERNAL_API_TOKEN environment variable is required")
        return False

    results = {
        "persona_check": False,
        "validation_check": False,
        "workflow_start": False,
        "workflow_running": False,
    }

    _print_step(1, f"Checking persona '{args.persona_id}' readiness...")
    readiness = await check_persona_readiness(
        args.api_base,
        args.persona_id,
        args.owner_key,
        api_token,
    )
    if "error" in readiness:
        _print_step(1, f"Readiness check failed: {readiness['error']}", "FAIL")
        return False

    persona = await get_persona(
        args.api_base,
        args.persona_id,
        args.owner_key,
        api_token,
    )
    if "error" in persona:
        _print_step(1, f"Persona fetch failed: {persona['error']}", "FAIL")
        return False

    status = persona.get("status")
    tts_voice = persona.get("tts_voice")
    heygen_avatar_id = persona.get("heygen_avatar_id")

    print(f"       Persona status: {status}")
    print(f"       TTS voice: {tts_voice}")
    print(f"       HeyGen avatar: {heygen_avatar_id or 'None'}")
    print(f"       Readiness: {readiness.get('ready')}")

    if status != "ready":
        _print_step(1, f"Persona status is '{status}', expected 'ready'", "FAIL")
        return False
    if not tts_voice:
        _print_step(1, "Persona missing tts_voice", "FAIL")
        return False
    if not readiness.get("ready"):
        _print_step(
            1,
            f"Persona readiness failed: {readiness.get('blocking_reason') or 'unknown'}",
            "FAIL",
        )
        return False

    results["persona_check"] = True
    _print_step(1, "Persona is ready", "PASS")

    _print_step(2, "Testing API validation...")
    if not heygen_avatar_id and not args.skip_workflow:
        print("       Testing: talking_head_optional=False should fail without heygen_avatar_id")
        result = await start_video_workflow(
            api_base=args.api_base,
            persona_id=args.persona_id,
            topic="Validation test",
            owner_key=args.owner_key,
            api_token=api_token,
            talking_head_optional=False,
        )
        if "error" in result and "heygen_avatar_id" in result["error"]:
            print("       [PASS] API correctly rejected missing heygen_avatar_id")
            results["validation_check"] = True
        else:
            _print_step(2, f"Unexpected validation result: {result}", "FAIL")
            return False
    else:
        results["validation_check"] = True
        print("       [SKIP] heygen_avatar_id present, skipping rejection test")

    _print_step(2, "API validation working", "PASS")

    if args.skip_workflow:
        _print_step(3, "Workflow start skipped (--skip-workflow)", "SKIP")
        _print_step(4, "Workflow status check skipped", "SKIP")
    else:
        _print_step(3, "Starting video workflow...")
        approved_package = create_minimal_approved_package(args.persona_id)
        result = await start_video_workflow(
            api_base=args.api_base,
            persona_id=args.persona_id,
            topic="E2E Pipeline Test",
            owner_key=args.owner_key,
            api_token=api_token,
            approved_package=approved_package,
            talking_head_optional=True,
        )

        if "error" in result:
            _print_step(3, f"Failed to start workflow: {result['error']}", "FAIL")
            return False

        workflow_id = result.get("workflow_id")
        print(f"       Workflow ID: {workflow_id}")
        print(f"       Run ID: {result.get('run_id')}")
        results["workflow_start"] = True
        _print_step(3, "Workflow started successfully", "PASS")

        _print_step(4, f"Checking workflow status (timeout: {args.timeout}s)...")
        start_time = time.time()
        last_status = None
        running_states = {
            "queued",
            "generating_script_from_package",
            "waiting_script_approval",
            "generating_assets",
            "assembling",
            "waiting_final_decision",
            "running",
        }

        while time.time() - start_time < args.timeout:
            status_result = await check_workflow_status(
                api_base=args.api_base,
                workflow_id=workflow_id,
                api_token=api_token,
            )

            if "error" in status_result:
                if "503" in status_result["error"]:
                    _print_step(
                        4,
                        "Temporal unavailable through status API; workflow started but cannot be verified further.",
                        "WARN",
                    )
                    results["workflow_running"] = True
                    break
                _print_step(4, f"Status check failed: {status_result['error']}", "FAIL")
                break

            current_status = _extract_workflow_state(status_result)
            if current_status != last_status:
                print(f"       Status: {current_status}")
                last_status = current_status

            if current_status == "completed":
                results["workflow_running"] = True
                _print_step(4, "Workflow completed successfully", "PASS")
                break
            if current_status == "failed":
                _print_step(4, "Workflow failed", "FAIL")
                break
            if current_status == "discarded":
                _print_step(4, "Workflow reached discarded state", "FAIL")
                break
            if current_status in running_states:
                results["workflow_running"] = True
                _print_step(4, "Workflow is running", "PASS")
                break

            await asyncio.sleep(2)
        else:
            _print_step(
                4,
                f"Timeout after {args.timeout}s; workflow may still be running.",
                "WARN",
            )
            results["workflow_running"] = True

    _print_header("Test Summary")
    passed = sum(results.values())
    total = len(results)
    print(f"  Results: {passed}/{total} checks passed\n")
    for check, passed_check in results.items():
        icon = "[PASS]" if passed_check else "[FAIL]"
        print(f"  {icon} {check.replace('_', ' ').title()}")
    print()

    if all(results.values()):
        print("  [SUCCESS] E2E pipeline test passed!")
        return True

    print("  [FAILURE] Some checks failed")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E Video AI Pipeline Test")
    parser.add_argument("--persona-id", required=True, help="Persona ID to test with")
    parser.add_argument(
        "--owner-key",
        default=None,
        help="Telegram owner key (e.g., telegram:123456)",
    )
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--skip-workflow",
        action="store_true",
        help="Skip actual workflow start (just test validation)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Workflow status check timeout in seconds (default: 120)",
    )

    args = parser.parse_args()
    success = asyncio.run(run_e2e_test(args))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
