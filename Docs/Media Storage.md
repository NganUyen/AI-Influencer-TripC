# Media Storage Integration

Tài liệu này tổng hợp tình trạng tích hợp Supabase Media Storage vào AI-Influencer TripC, mức độ sẵn sàng cho Production (Ready to Production) và giải thích chi tiết về `campaign_id`.

## 1. Tình trạng hiện tại (Đủ và Thiếu)

### Đã hoàn thiện (Đủ)
- **Hệ thống Upload tự động**: Toàn bộ luồng tạo ảnh (`generate_image`, `generate_scene_images`) và video (`generate_video`, `build_split_screen_video`) đều đã được gắn hook để tự động đồng bộ tải file lên Supabase Storage bucket `media` (kéo từ URL nhà cung cấp fal.ai về lưu trữ ổn định tại Supabase).
- **Phân loại thư mục tự động**: Asset được tự động nhận dạng MIME type và đẩy vào `media/image/YYYY-MM/` hoặc `media/video/YYYY-MM/`.
- **Không chặn tiến trình (Non-blocking)**: Hàm lưu trữ sử dụng `asyncio.create_task` (fire-and-forget). Cho nên tiến trình upload và insert Database chạy ngầm song song, Pipeline chính không bị khựng lại hay chết yểu kể cả khi mạng chập chờn hay API REST Supabase phản hồi chậm. Cốt lõi pipeline vẫn an toàn.
- **Tích hợp sâu chuỗi Database (media_assets)**: Flow tạo chiến dịch định kỳ (Weekly Marketing Workflow) từ Web App hiện đã liên kết thành công biến `campaign_id` từ `generate_content_strategy` thả xuống các function sinh hình/video nhỏ lẻ. Nếu tìm thấy khóa `campaign_id`, dữ liệu sẽ được INSERT chính xác vào bảng `media_assets`.
- **Slide-show Flow hoàn hảo**: Các file ảnh sinh ra cho video dạng slideshow sẽ tạo public URL thẳng từ Supabase, sau đó cung cấp cho module `build_split_screen_video` sử dụng, mọi thứ khép kín trong quy trình.

### Còn khuyết / Cần lưu ý (Thiếu)
- **Lưu trữ Metadata trong cơ sở dữ liệu khi dùng qua Telegram**: Khi User thao tác qua Telegram Bot (`ShortVideoWorkflow`), thông tin đầu vào chỉ có `persona_id` và `topic`, NHƯNG KHÔNG TẠO RA VÀ KHÔNG CÓ `campaign_id`. Do thiết kế của bạn, bảng `media_assets` bắt buộc (NOT NULL) có `campaign_id`. Vì vậy nếu chạy qua Telegram, hàm DB Hook sẽ cảnh báo Warning và bỏ qua bước Insert vào bảng `media_assets`. 
*(Lưu ý: Mặc dù dòng Database bị bỏ qua, File vật lý gốc CỦA TELEGRAM FLOW vẫn được Upload lên Storage Bucket `media` bình thường giúp bảo toàn tài sản tĩnh).*


## 2. Hệ thống đã "Ready to Production" chưa?

**Kết luận: CÓ THỂ ĐƯA Lên PRODUCTION ngay cho luồng Web App.**

**Tại sao đánh giá là Ready to Production?**
1. **Safety (Tính Cứng Cáp)**: File `media_storage_service.py` được thiết kế cực kỳ bọc lót. Tất cả Exception ở level Storage và SQL Database Request đều được try-catch và Error Logging đầy đủ. Nếu tiến trình upload của Supabase lỗi (do Network hay Quota giới hạn), hệ thống vẫn trả về asset của provider AI để tiến trình lên bài không bị gián đoạn.
2. **Backwards Compatibility**: Code không xâm lấn logic cốt lõi. Tôi chỉ bọc kết quả Output bằng một lời gọi hàm độc lập lưu hậu cảnh.
3. **Hiệu năng**: Không giam giữ Temporal Worker chờ đợi I/O File Transfer.

**Giải pháp để Đạt 100% Production Coverage (Cho cả luồng Telegram):**
Giới hạn duy nhất hiện nay là việc Flow Telegram thiếu `campaign_id` đang bị trật ràng buộc Database. Để xử lý dứt điểm cho Production vẹn toàn, nhà phát triển có thể làm 1 trong 2 cách sau:
- **Tùy chọn A**: Sử dụng file Migration hoặc vào thẳng giao diện Supabase tắt ràng buộc NOT NULL của cột `campaign_id` trong table `media_assets`, và chuyển thành chuỗi tuỳ chọn.
- **Tùy chọn B**: Trong code của `ShortVideoWorkflow` ở Telegram, hãy viết thêm logic tự sinh ra một "Draft Campaign" / "Telegram Campaign" ảo và lấy ID truyền xuống bên dưới.


## 3. Bản chất của vấn đề "campaign_id" trong luồng Generator

Sự khác nhau căn bản về `campaign_id` giữa 2 loại quy trình:

1. **Qua Web App (WeeklyMarketingWorkflow)**: Workflow này được trigger khi user nhấn tạo campaign tren web. Trong `customer_campaign_service.py`, user khởi tạo bảng `public.campaigns` nhận được chuỗi `campaign_id`, ID này sẽ được cài đè vào object `brand_config` -> truyền sang `generate_media_prompts` rồi đi khắp mọi luồng Media (ảnh / video). Chó nên hook Storage luôn đọc được và lưu thành công.
2. **Qua Telegram (ShortVideoWorkflow)**: Bot trigger trực tiếp việc sinh video từ thông số Persona và Chủ đề ngắn. Vì không có thao tác lập kế hoạch tuần, nó không hề Record chiến dịch (ví dụ như cột `campaign_id` trong SQL=null). Hook DB bắt buột phải kiểm tra: NẾU không có `campaign_id`, để tránh gây exception Postgres phá hỏng Pipeline, Hook DB sẽ tự động return mà không gọi câu lệnh Execute SQL `insert media_assets` nữa.

**Trả lời câu hỏi: "Lấy ảnh type slideshow trong storage để dùng cho quá trình ghép video được không?"**
- **Hoàn toàn Được**. Hàm API trả về hình ghép `generate_scene_images` đã được cập nhật nên Public URL trả ra sau này NẰM Ở CHÍNH SUPABASE CỦA BẠN. Nên khi chạy xuống bước `build_split_screen_video` nó vẫn tự lấy những public URLs public trong dự án này download về bằng cỗ máy FFmpeg và render mượt mà. Đảm bảo file cuối cùng là thành phẩm "All in Home".
