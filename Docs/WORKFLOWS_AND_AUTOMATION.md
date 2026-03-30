# Workflows And Automation

Last verified: 2026-03-30 (UTC)

Temporal is the orchestration backbone for long-running approval, publishing, and content-generation flows.

## Worker Runtime

The worker lives in `Project/python_services/worker.py`.

It registers:

- `WeeklyMarketingWorkflow`
- `PostPublishingWorkflow`
- `EngagementSyndicateWorkflow`
- `ShortVideoWorkflow`
- `DailyStoryWorkflow`

It uses:

- `TEMPORAL_ADDRESS`
- `TEMPORAL_NAMESPACE`
- `TEMPORAL_TASK_QUEUE`
- `WORKER_CONCURRENCY`

## Main Workflows

### WeeklyMarketingWorkflow

Defined in `workflows/weekly_marketing_workflow.py`.

Primary flow:

1. generate weekly strategy
2. optionally wait for approval
3. generate media prompts
4. generate images, video, and audio in parallel
5. upload assets to object storage
6. schedule posts
7. start child publishing workflows

Important notes:

- approval can be skipped when the web app already completed review
- Telegram remains the in-workflow approval channel when review is not skipped
- the workflow exposes a signal for approval and a query for status

### PostPublishingWorkflow

Child workflow that:

1. waits until the scheduled time
2. publishes through provider integrations
3. starts the engagement syndicate child workflow

### EngagementSyndicateWorkflow

Child workflow that:

1. waits a delay before engagement actions
2. tracks engagement
3. returns engagement results

### ShortVideoWorkflow

Defined in `workflows/short_video_workflow.py`.

Primary flow:

1. accept a validated start payload from `/api/workflows/start-video`
2. either:
   - generate and send a script for Telegram approval, then wait for approval
   - or consume an `approved_package` and bypass script approval
3. generate audio and scene assets in parallel
4. optionally generate a HeyGen talking-head clip
5. assemble the final split-screen video
6. send preview to Telegram
7. wait for final save or discard decision

Important notes:

- `/api/workflows/start-video` now passes `persona_snapshot`, `talking_head_optional`, and optional `approved_package`
- the approved-package production path is the current handoff used by the `video-ai` pre-production skill
- persona readiness/configuration errors are treated as non-retryable
- the workflow raises `SceneAssetMismatchError` before assembly when scene assets and scene timings diverge
- workflow failures trigger Telegram error notification through `send_telegram_error_notification`
- talking-head generation can fail over to a slideshow-plus-audio lane
- the workflow returns structured terminal payloads for completed, discarded, and failed exits

### DailyStoryWorkflow

Defined in `workflows/daily_story_workflow.py`.

Primary flow:

1. generate a daily story
2. fan it out to Telegram subscribers
3. wait for a story-decision signal
4. publish to the chosen platform or skip

Important notes:

- this flow is designed for cron-style invocation
- it supports explicit skip behavior and timeout skip behavior

## Activity Modules

### Strategy activities

`activities/strategy_activities.py` handles:

- weekly strategy generation
- media prompt generation
- daily content generation
- carousel strategy generation
- long-post strategy generation

### Approval activities

`activities/approval_activities.py` handles:

- Telegram strategy approval requests
- wait-for-approval loops
- approved-package to script conversion
- script approval requests and waits
- progress/error delivery to Telegram
- preview delivery
- publish decision waits

### Media activities

`activities/media_activities.py` handles:

- image generation
- video generation
- audio generation
- storage uploads
- scene image generation
- talking-head video generation
- top-half browser capture plus AI fallback routing
- slideshow and split-screen helper flows

### Distribution activities

`activities/distribution_activities.py` handles:

- post scheduling
- publishing to platforms
- engagement tracking

### Story and assembly activities

- `story_activities.py`: daily story generation and Telegram approval delivery
- `video_activities.py`: ffmpeg-based final video assembly

## Approval And Callback Channels

- workflow approvals can come from Telegram
- customer campaign approval also exists in the web app before workflow launch
- Telegram webhook callbacks are handled in `api/telegram_webhook.py`
- provider webhooks from Postiz and GrowChief arrive through `api/webhooks.py`

## Scripts And Operational Helpers

Useful scripts in `Project/python_services/scripts/`:

- `start_daily_story_cron.py`: start or cancel the daily story cron
- `register_telegram_webhook.py`: configure the Telegram webhook
- `check_telegram_webhook.py`: inspect webhook status
- `setup_persona.py`: validate and prepare persona data
- `check_persona.py`: inspect persona readiness
- `e2e_video_ai_pipeline.py`: smoke test the approved-package video path against a deployed API
- `smoke_strategies.py`, `smoke_script.py`, `smoke_storage.py`, `smoke_tts.py`, `smoke_heygen.py`, `smoke_assembly.py`: integration smoke helpers

## Failure And Retry Model

- the backend can be up while Temporal is down, but workflow actions will degrade
- activities use explicit retry policies in workflow definitions
- some persona-related failures are deliberately non-retryable
- the short-video lane fails closed before assembly when scene assets are incomplete or misaligned
- long-running flows depend on external providers, so real acceptance testing is still required after infra or credential changes
