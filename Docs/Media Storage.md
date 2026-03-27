# Media Storage Integration

Tài liệu này tổng hợp tình trạng tích hợp Supabase Media Storage vào AI-Influencer TripC, mức độ sẵn sàng cho Production (Ready to Production) và giải thích chi tiết về `campaign_id`.

## 1. Tình trạng hiện tại (Đủ và Thiếu)

### Đã hoàn thiện (Đủ)
- **Hệ thống Upload tự động**: Toàn bộ luồng tạo ảnh (`generate_image`, `generate_scene_images`) và video (`generate_video`, `build_split_screen_video`) đều đã được gắn hook để tự động đồng bộ tải file lên Supabase Storage bucket `media`.
- **Phân loại thư mục theo owner/persona**: Asset được lưu theo layout chuẩn `users/<user_id>/personas/<persona_id>/<asset_type>/<yyyy-mm>/<file>`. Cách này giúp gom toàn bộ media của một persona về đúng owner thay vì chỉ tách theo loại file.
- **Không chặn tiến trình (Non-blocking)**: Hàm lưu trữ sử dụng `asyncio.create_task` (fire-and-forget). Cho nên tiến trình upload và insert Database chạy ngầm song song, Pipeline chính không bị khựng lại hay chết yểu kể cả khi mạng chập chờn hay API REST Supabase phản hồi chậm. Cốt lõi pipeline vẫn an toàn.
- **Tích hợp sâu chuỗi Database (media_assets)**: `public.media_assets` giờ lưu first-class các cột `persona_id`, `owner_key`, `bucket_name`, `storage_path`, `source_url`, `provider_job_id` ngoài `metadata`. Nghĩa là có thể query media theo persona trực tiếp mà không cần bóc JSON metadata.
- **Slide-show Flow hoàn hảo**: Các file ảnh sinh ra cho video dạng slideshow sẽ tạo public URL thẳng từ Supabase, sau đó cung cấp cho module `build_split_screen_video` sử dụng, mọi thứ khép kín trong quy trình.

### Còn khuyết / Cần lưu ý (Thiếu)
- **Thiếu hoặc sai owner context sẽ làm giảm chất lượng ownership mapping**: `media_assets` được scope theo `user_id`, đồng thời ghi thêm `persona_id` và `owner_key`. Nếu một flow không truyền được `user_id` hoặc `owner_key`, file vẫn có thể được upload nhưng DB record có thể bị skip để tránh ghi sai owner.
- **Một số legacy flow vẫn dùng provider URL làm fallback**: Khi lưu vào storage thất bại, pipeline vẫn trả về URL từ provider để không làm hỏng workflow. Đây là degraded mode hợp lệ, nhưng không phải đường lý tưởng cho production lâu dài.


## 2. Hệ thống đã "Ready to Production" chưa?

**Kết luận: CÓ THỂ ĐƯA Lên PRODUCTION ngay cho luồng Web App.**

**Tại sao đánh giá là Ready to Production?**
1. **Safety (Tính Cứng Cáp)**: File `media_storage_service.py` được thiết kế cực kỳ bọc lót. Tất cả Exception ở level Storage và SQL Database Request đều được try-catch và Error Logging đầy đủ. Nếu tiến trình upload của Supabase lỗi (do Network hay Quota giới hạn), hệ thống vẫn trả về asset của provider AI để tiến trình lên bài không bị gián đoạn.
2. **Backwards Compatibility**: Code không xâm lấn logic cốt lõi. Tôi chỉ bọc kết quả Output bằng một lời gọi hàm độc lập lưu hậu cảnh.
3. **Hiệu năng**: Không giam giữ Temporal Worker chờ đợi I/O File Transfer.

**Giải pháp để Đạt 100% Production Coverage (Cho cả luồng Telegram):**
Giới hạn chính hiện nay không còn là `campaign_id`, mà là chất lượng owner context của từng flow:
- Ưu tiên luôn truyền `user_id` nếu flow đã biết customer thực.
- Nếu flow khởi nguồn từ Telegram/OpenClaw, truyền `owner_key=telegram:<chat_id>` và `persona_id` khi có để asset được lưu đúng vùng owner/persona.
- Với degraded mode storage, nên theo dõi log để phát hiện lúc pipeline chỉ trả provider URL thay vì stable project-owned URL.


## 3. Bản chất của vấn đề "campaign_id" trong luồng Generator

Sự khác nhau căn bản về `campaign_id` giữa 2 loại quy trình:

1. **Qua Web App (WeeklyMarketingWorkflow)**: Workflow này thường đã có `user_id`, và đôi khi có thêm `campaign_id` trong metadata. Asset được lưu ổn định vào storage trước rồi mới đi tiếp xuống scheduling/distribution.
2. **Qua Telegram (ShortVideoWorkflow)**: Bot trigger trực tiếp việc sinh media từ `persona_id`, `topic`, và `telegram_chat_id`. Flow không cần `campaign_id` để lưu asset nữa; thay vào đó nó dựa vào `owner_key=telegram:<chat_id>` và `persona_id` để xác định đúng vùng owner/persona trong storage + DB columns.

**Trả lời câu hỏi: "Lấy ảnh type slideshow trong storage để dùng cho quá trình ghép video được không?"**
- **Hoàn toàn Được**. Hàm API trả về hình ghép `generate_scene_images` đã được cập nhật nên Public URL trả ra sau này NẰM Ở CHÍNH SUPABASE CỦA BẠN. Nên khi chạy xuống bước `build_split_screen_video` nó vẫn tự lấy những public URLs public trong dự án này download về bằng cỗ máy FFmpeg và render mượt mà. Đảm bảo file cuối cùng là thành phẩm "All in Home".
