# Runbook: Video Generation Pipeline Alerts

This runbook covers operational alerts and troubleshooting for the video generation pipeline.

## Overview

The pipeline flow:
```
approved_package → script_service → media_activities → video_activities → final video
```

Each section below covers one alert type with: trigger condition, likely causes, investigation steps (with log queries), and resolution steps.

---

## ALERT: SceneAssetMismatchError

### Trigger

`SceneAssetMismatchError` appears in Temporal workflow logs with message:
```
Scene asset count mismatch: X scenes, Y assets. Failed scenes: [...]
```

### Likely Causes

1. **Browser capture timed out for one or more scenes** (most common)
2. **AI image generation quota exceeded** — provider returned error
3. **Storage upload failed mid-way** — check for orphan records
4. **Network connectivity issues** between worker and external services

### Investigation

```bash
# Find which scenes failed — look for CP3 logs with url=None
grep "Scene asset resolved" logs | grep "url=None"

# Check if browser capture was attempted but source_ref was missing
grep "CP2" logs | grep "source_ref=None"

# Check fallback rate for this workflow
grep "fallback_triggered=True" logs | wc -l

# Get full scene list from the mismatch error
grep "SceneAssetMismatchError" logs | grep -o "Failed scenes: \[.*\]"

# Check Temporal activity history for failed activities
temporal workflow show -w <workflow_id> | grep -i "failed\|error"
```

### Resolution

1. **If browser capture timeout:**
   - Verify target URL is publicly accessible: `curl -I <source_ref_url>`
   - Check if page requires authentication or has geo-restrictions
   - Consider increasing capture timeout if pages are legitimately slow

2. **If AI quota exceeded:**
   - Check provider dashboard (OpenAI/Stability/etc.) for quota status
   - Rotate API key if current one is rate-limited
   - Consider implementing backoff/retry for AI generation

3. **If storage upload failed:**
   - Check bucket permissions: `aws s3 ls s3://<bucket>/`
   - Verify disk space on upload worker
   - Check for orphan records in database: `SELECT * FROM media_assets WHERE url IS NULL`

4. **Requeue the job:**
   - From Temporal UI: find workflow, click "Reset" to retry from failed activity
   - Or programmatically: `temporal workflow reset -w <workflow_id> --reason "Retry after fixing <issue>"`

---

## ALERT: Workflow status=failed, no Telegram sent

### Trigger

Workflow returns `{status: "failed"}` in Temporal but `send_telegram_error_notification` activity also failed (visible in Temporal activity logs).

### Likely Causes

1. **Telegram bot token expired or revoked**
2. **User chat_id invalid** — user blocked the bot or deleted account
3. **Telegram API rate limit** — too many messages sent recently
4. **Network timeout** — worker couldn't reach Telegram servers

### Investigation

```bash
# Check if notification activity was attempted
grep "send_telegram_error_notification" temporal_activity_logs

# Check Telegram API errors
grep "telegram" logs | grep -i "error\|failed\|401\|403\|429"

# Verify bot token works
curl "https://api.telegram.org/bot<TOKEN>/getMe"

# Check user chat validity
curl "https://api.telegram.org/bot<TOKEN>/getChat?chat_id=<USER_CHAT_ID>"
```

### Resolution

1. **If token expired:**
   - Generate new token via @BotFather on Telegram
   - Update `TELEGRAM_BOT_TOKEN` environment variable
   - Restart workers to pick up new token

2. **If user blocked bot:**
   - This is expected behavior — user chose not to receive messages
   - Mark user's notification preference as "disabled" in database
   - No further action needed

3. **If rate limited:**
   - Implement exponential backoff in notification activity
   - Consider batching notifications for same user
   - Check if multiple workflows are failing simultaneously (root cause)

4. **If network issue:**
   - Check worker network connectivity
   - Verify Telegram API endpoint is reachable from worker subnet
   - Consider retry with longer timeout

---

## ALERT: Video duration wrong / scenes cut too short

### Trigger

User reports video content mismatched to audio narration:
- Scene visuals don't align with voiceover
- Video cuts off early
- Wrong images shown at wrong times

### Investigation

```bash
# Check CP6 logs for duration assignments
grep "Assembly scene" logs | awk -F'|' '{print $1, $3, $5}'

# Look for the mismatch warning that SHOULD have triggered error
grep "MISMATCH duration/image" logs

# Verify scene count from script stage
grep "ScriptContract built" logs | grep -o "scenes=[0-9]*"

# Compare to asset count from media stage
grep "Scene asset resolved" logs | grep -v "url=None" | wc -l

# Check if old code path was used (pre-fix)
grep "SceneAssetMismatchError" logs
```

### Resolution

This issue should now raise `SceneAssetMismatchError` before assembly. If a corrupted video reaches production:

1. **Verify fix is deployed:**
   - Check `short_video_workflow.py` has the mismatch guard at line 265-304
   - Confirm worker is running latest code version

2. **If guard was bypassed:**
   - Check if workflow was started before deployment
   - Review any custom workflow parameters that might skip validation

3. **Regenerate the video:**
   - Get original `approved_package` from workflow input
   - Trigger new workflow with same parameters
   - Verify new video has correct duration alignment

4. **Notify user:**
   - Apologize for corrupted video
   - Provide new video link when regeneration completes

---

## ALERT: Video top-half shows AI image instead of expected page capture

### Trigger

User or QA reports wrong visual type in top half of video:
- Expected: Screenshot/recording of a specific webpage
- Actual: AI-generated image (generic visual)

### Investigation

```bash
# Check if capture was attempted for the scene
grep "CP2" logs | grep "<scene_id>"

# Check if capture failed and fell back to AI
grep "Scene asset resolved" logs | grep "<scene_id>" | grep "fallback_triggered"

# Verify source_ref was provided in beat data
grep "Creating scene contract" logs | grep "<scene_id>" | grep "source_ref"

# Check URL detection result
grep "CP5" logs | grep "<scene_id>"
```

### Resolution

1. **If `source_ref` was missing:**
   - This is an upstream data issue in the approved beat package
   - Fix the beat data to include `source_ref` URL
   - Re-run content planning workflow to regenerate beats

2. **If capture was attempted but failed:**
   - Check target URL accessibility: `curl -I <source_ref_url>`
   - Review browser automation logs for specific error
   - If page requires auth, consider switching to `authenticated_capture_later` type

3. **If presigned URL detection was wrong:**
   - Check CP5 log: should show `is_video=True` for `.webm`/`.mp4` URLs
   - If showing `is_video=False` for a video URL, verify `_is_video_url()` fix is deployed
   - Extension detection uses `urlparse().path`, not raw URL

4. **If capture succeeded but wasn't used:**
   - Check `top_half_source_type` in scene contract — must be `public_page_capture`
   - If type is `ai_visual_fallback`, the routing was intentional
   - Review beat planning logic for why capture wasn't selected

---

## ALERT: High browser capture failure rate

### Trigger

Monitoring shows `fallback_triggered=True` rate exceeds 30% over 1 hour.

### Investigation

```bash
# Get capture success/failure counts
grep "Scene asset resolved" logs | grep -c "fallback_triggered=False"
grep "Scene asset resolved" logs | grep -c "fallback_triggered=True"

# Find which source URLs are failing most
grep "Browser capture failed" logs | grep -o "source_ref=[^ ]*" | sort | uniq -c | sort -rn | head

# Check for common error patterns
grep "Browser capture failed" logs | grep -o "error: [^|]*" | sort | uniq -c | sort -rn

# Check worker health
grep "playwright\|browser" logs | grep -i "crash\|timeout\|memory"
```

### Resolution

1. **If specific URLs failing:**
   - Blocklist problematic domains temporarily
   - Switch affected beats to `ai_visual_fallback` in content planning

2. **If all URLs failing (infrastructure issue):**
   - Restart browser workers
   - Check Playwright installation: `npx playwright install`
   - Verify worker has enough memory for browser sessions

3. **If timeout issues:**
   - Increase `page.goto()` timeout in `browser_automation.py`
   - Check network latency between worker and target sites
   - Consider geographic distribution of workers

---

## Checkpoint Log Reference

| Checkpoint | File | Line | Content |
|------------|------|------|---------|
| CP1 | `script_service.py` | 243 | SceneContract dump after build |
| CP2 | `media_activities.py` | 641 | Warning: `public_page_capture` missing `source_ref` |
| CP3 | `media_activities.py` | 617, 660 | Full asset trace per scene |
| CP5 | `video_activities.py` | 128 | URL type detection result |
| CP6 | `video_activities.py` | 178 | Per-scene assembly details |
| CP7 | `video_activities.py` | 345 | Slideshow fallback indicator |

### Example Log Queries

```bash
# Full pipeline trace for a workflow
grep "<workflow_id>" logs | grep "CP[0-9]"

# All warnings across pipeline
grep "<workflow_id>" logs | grep "WARNING"

# Assembly decisions
grep "<workflow_id>" logs | grep -E "CP5|CP6|CP7"
```

---

## Escalation

If an issue persists after following this runbook:

1. **Gather logs:** Collect all logs for the affected workflow ID
2. **Check recent changes:** Review commits in last 24 hours
3. **Escalate with context:**
   - Workflow ID
   - Timestamp of failure
   - Which checkpoint logs are present/missing
   - Error messages
4. **Contact:** #video-pipeline-oncall Slack channel
