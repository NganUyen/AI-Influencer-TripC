# Bug Report: Telegram Bot Không Phản Hồi

**Severity:** High — auth flow bị broken hoàn toàn

**Root cause:** Python backend trên production đang down

```
Webhook URL: https://ai-influencer.tripc.ai/backend/api/webhooks/telegram
Last error:  502 Bad Gateway
Error time:  2026-03-29 (hôm nay)
```

## Evidence

```json
{
  "url": "https://ai-influencer.tripc.ai/backend/api/webhooks/telegram",
  "last_error_message": "Wrong response from the webhook: 502 Bad Gateway",
  "pending_update_count": 0
}
```

## Flow bị ảnh hưởng

1. User bấm "Open Telegram & Sign In"
2. Telegram mở, user gửi `/start`
3. Bot không phản hồi vì webhook call về server trả 502
4. Frontend không nhận callback → hiện "Invalid Telegram hash"

## Code đã verified hoạt động đúng

- `telegram_webhook.py` — parse token, validate DB, reply đúng
- `telegram_link_service.py` — tạo token thật, lưu DB thành công
- Next.js API routes — 200 OK, token thật từ DB

## Việc DevOps cần làm

- Kiểm tra Python backend service có đang chạy không (`docker ps`, `pm2 list`, hoặc `systemctl status`)
- Restart service nếu down
- Confirm webhook nhận được request sau khi restart: `last_error_message` phải biến mất

---

**Không cần sửa code gì.** Chỉ cần restart backend service trên server.
