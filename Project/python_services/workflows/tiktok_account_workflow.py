from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities.tiktok_account_activities import (
        bootstrap_tiktok_account,
        refresh_tiktok_account_session,
    )


@workflow.defn
class TikTokAccountBootstrapWorkflow:
    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await workflow.execute_activity(
            bootstrap_tiktok_account,
            args=[payload],
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(
                maximum_attempts=2,
                initial_interval=timedelta(seconds=15),
                backoff_coefficient=2.0,
            ),
        )


@workflow.defn
class TikTokAccountRefreshWorkflow:
    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await workflow.execute_activity(
            refresh_tiktok_account_session,
            args=[payload],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                maximum_attempts=2,
                initial_interval=timedelta(seconds=10),
                backoff_coefficient=2.0,
            ),
        )
