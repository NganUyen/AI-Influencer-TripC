# Telegram → Backend → Skill/Workflow → OpenClaw → Callback (E2E)

Last verified: 2026-03-26 (UTC)

This sequence reflects the **actual runtime path** in the current codebase after wiring fixes.

```mermaid
sequenceDiagram
    autonumber
    participant TG as Telegram
    participant WH as Backend Webhook (/api/webhooks/telegram)
    participant DISP as SkillDispatcher
    participant SK as Skill (weekly-planner / video-ai)
    participant API as Backend API routes
    participant TEMP as Temporal Workflow
    participant ACT as Activities
    participant OC as OpenClaw Gateway
    participant TS as TelegramService (approval state)

    TG->>WH: message/callback_query update
    WH->>WH: verify X-Telegram-Bot-Api-Secret-Token

    alt Menu-driven skill path (/media)
        WH->>DISP: start_skill / handle_text / handle_option / handle_action
        DISP->>SK: execute(session)
        SK->>API: POST /api/workflows/start-weekly or /start-video
        API->>TEMP: start workflow

        TEMP->>ACT: generate_weekly_strategy (or video activities)
        ACT->>OC: execute_task(task_type, prompt)
        OC-->>ACT: strategy/output

        TEMP->>ACT: send_telegram_approval_request
        ACT->>TS: send message + inline buttons (Approve/Reject)
        TS-->>ACT: request_id
        ACT-->>TEMP: request_id

        TG->>WH: callback_query (approve_*/reject_*)
        WH->>TS: apply_callback_payload(request_id, callback_data)
        TS-->>WH: status updated (Redis/memory)

        TEMP->>ACT: wait_for_approval(request_id)
        ACT->>TS: poll approval state
        TS-->>ACT: approved/rejected
        ACT-->>TEMP: approval decision

        alt approved
            TEMP->>ACT: continue media generation/distribution
        else rejected/timeout
            TEMP-->>API: rejected/timed_out result
        end
    else Daily story path
        TEMP->>ACT: send_story_for_approval
        ACT->>TG: Post to TikTok / Post to Shorts / Skip Today
        TG->>WH: callback_query (post_tiktok_* / post_shorts_* / skip_*)
        WH->>TEMP: signal story_decision(action, chat_id)
        TEMP->>ACT: publish_to_platforms (if not skipped)
    end
```

## Wiring Order Guarantees

1. Webhook authentication and payload parsing happen before any skill/workflow action.
2. Skill sessions are persisted between Telegram steps via `TelegramSkillSessionStore`.
3. Workflow launch happens only after required skill parameters are collected.
4. OpenClaw execution happens inside activities after workflow start, not directly from Telegram handlers.
5. Approval callbacks update `TelegramService` state first; workflows then consume that state through `wait_for_approval`.
6. Story callbacks use Temporal signal (`story_decision`) and remain separate from skill approval callbacks.

## Main Code Paths

- Webhook router: `Project/python_services/api/telegram_webhook.py`
- Skill routing: `Project/python_services/services/skill_dispatcher.py`
- Skills: `Project/python_services/skills/`
- Weekly workflow: `Project/python_services/workflows/weekly_marketing_workflow.py`
- Daily story workflow: `Project/python_services/workflows/daily_story_workflow.py`
- Approval activities: `Project/python_services/activities/approval_activities.py`
- OpenClaw adapter: `Project/python_services/services/openclaw_service.py`
- Telegram approval state: `Project/python_services/services/telegram_service.py`
