# End-to-End Video Production Pipeline: Top-Half & HeyGen Integration
**Date**: March 28, 2026

## 1. Overview
Hệ thống AI Influencer đã được nâng cấp hoàn thiện để hỗ trợ tự động hóa 100% quy trình sản xuất video dọc (cấu trúc Split-screen/Màn hình chia đôi). 

Luồng sản xuất giờ đây có thể chạy khép kín từ một **ý tưởng thô (Idea) + Link Website** ban đầu, thông qua AI Đạo diễn (Creative Director) để lên kịch bản, tự động mở trình duyệt quay lại thao tác trên web (Top-half), tạo âm thanh/giọng nói, render MC ảo từ HeyGen (Bottom-half) và cuối cùng sử dụng FFMPEG để mix tất cả lại thành một thành phẩm Video MP4 hoàn hảo, sẵn sàng để đăng tải.

---

## 2. Các Thành Phần Chi Tiết (Component Breakdown)

### A. Pre-production & Scripting (Chuẩn bị kịch bản)
* **`CreativeDirectorService`**: Đóng vai trò là đạo diễn. Nhận đầu vào là ý tưởng, xuất ra `ConceptBrief` (định hướng) và `BeatSheet` (nhịp kịch bản). Đặc biệt, hệ thống sẽ tự động gán nhãn `top_half_source_type` (VD: `public_page_capture` hoặc `ai_visual_fallback`) cho từng nhịp (beat).
* **`ScriptService`**: Bổ sung hàm `generate_script_from_package()`. Chuyển đổi trực tiếp các nhịp kịch bản (`BeatSheet`) thành danh sách các cảnh quay (`SceneContract`) với đầy đủ metadata web mà không cần người dùng duyệt tay.

### B. Màn hình trên (Top-Half Capture: Web Recording & Image AI)
* Nằm tại `activities/media_activities.py` (`generate_scene_images`).
* **Web Recording:** Bổ sung vào `BrowserAutomationService` (dùng Playwright/Camoufox) tính năng `record_video_for_tutorial()`. Khi gặp nhãn `public_page_capture`, hệ thống mở web, tự động cuộn trang (scroll) mượt mà như người dùng thật và ghi hình lại dưới định dạng `.webm`, sau đó đẩy lên Cloud Storage.
* **AI Fallback:** Nếu kịch bản yêu cầu minh họa chung chung (`ai_visual_fallback`), hệ thống vẫn gọi Fal.ai để sinh ảnh như cũ.

### C. Màn hình dưới (Bottom-Half: HeyGen Avatar)
* Đã được tích hợp sẵn nguyên bản trong pipeline `short_video_workflow.py`.
* Quy trình: Khi kịch bản đã chốt -> Dịch Text sang Audio qua TTS -> Gửi Audio URL + \`heygen_avatar_id\` lên API của HeyGen thông qua activity `create_talking_head_video`.
* Kết quả trả về là một video có nền trong suốt / hoặc phông xanh với MC đang nhép miệng chuẩn xác theo âm thanh.

### D. Ghép nối Video (FFMPEG Assembly)
* Nằm tại `activities/video_activities.py` (`build_split_screen_video`).
* **Xử lý linh hoạt hình & video tĩnh:** Hệ thống tự động nhận diện tài nguyên đầu vào của phân nửa trên là hình ảnh tĩnh (`.jpg`) hay video (`.mp4`, `.webm`). Tất cả sẽ được ép khung về chuẩn `1080x960 25fps` trước khi thực hiện nối chuỗi (`concat`).
* **Mix Vertical Stack (`vstack`):** FFMPEG sẽ gộp video nửa trên (`1080x960`) và video HeyGen nửa dưới (`1080x960`) thành một chuẩn 9:16 (`1080x1920`). Kèm theo một đường ranh giới màu cam ở ngay giữa chia cắt hai nửa màn hình. Hệ thống add text overlay (Caption) vào nửa trên.

---

## 3. Các Luồng Workflow Temporal Tích Hợp

Đã thiết lập 2 luồng Workflow chính phục vụ cho tiến trình này:

1. **`CreativeToVideoWorkflow` (Luồng MỚI - Tự động E2E)**:
   - Tham số đầu vào cực ngắn gọn: `idea` và `reference_url`.
   - Tự gọi Activity để sinh gói Kịch bản (`ApprovedProductionPackage`).
   - Tự spawn `ShortVideoWorkflow` ở chế độ bỏ qua duyệt (Bypass Approval).

2. **`ShortVideoWorkflow` (Đã nâng cấp)**:
   - Tự động nhận dạng `payload["approved_package"]`.
   - Bỏ qua các bước `wait_for_script_approval` (Gửi Telegram chờ duyệt) nếu đã nhận được pre-approved package.
   - Gọi song song 2 nhánh: Thu thập tài nguyên Top-Half, Gen Audio -> Gửi Audio làm Bottom-Half -> Chờ xong -> FFMPEG Lắp ráp. Cực kỳ tối ưu thời gian.

---

## 4. Kiểm Thử (Testing & Stability)

Toàn bộ logic mới được Sandbox chặt chẽ để không phá vỡ bất kì pipeline cũ nào.
- 176/176 Unit Tests Pass toàn bộ xanh (Bao gồm các test mới).
- **`test_script_service_top_half.py`**: Chạy thử việc convert pre-production package thành `SceneContract` hợp lệ.
- **`test_media_activities_top_half.py`**: Giả lập Playwright, Storage bucket và khẳng định luồng code sẽ rẽ đúng hướng quay màn hình khi gặp nhãn `public_page_capture`.

=> **Trạng thái:** Sẵn sàng 100% cho Production. Có thể submit test run trực tiếp lên con worker!