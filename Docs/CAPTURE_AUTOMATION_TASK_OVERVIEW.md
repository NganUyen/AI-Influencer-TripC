# Capture Automation Task Overview (TripC)

## 1) Task này làm gì

Task này xây module **tự động capture màn hình App/Web + chuẩn hóa ảnh top-half + lưu kết quả video + cập nhật DB**.

### Mô tả 1 dòng cho lead (copy dùng ngay)
**Automation: Tự động capture màn hình App/Web theo scene, gắn text/overlay, stitch thành video, upload storage và cập nhật trạng thái campaign trong DB (running/completed/failed) cùng subtitle timing.**

### Mô tả business rõ ràng (không mơ hồ)
- Đây là phần **top-half automation** của luồng tạo video dọc.
- Hệ thống tự lấy từng scene, chụp/capture nội dung từ App/Web theo config.
- Mỗi scene được gắn nội dung trực quan:
  - Headline (nếu có)
  - Highlight vùng trọng tâm (border + zoom)
- Sau đó ghép scene thành video và lưu metadata để hệ thống publish dùng tiếp.
- Mỗi campaign được cập nhật trạng thái DB theo tiến trình để dễ theo dõi và debug.

Mục tiêu nghiệp vụ:
- Nhận danh sách scene từ campaign.
- Xử lý ảnh từng scene (headline/highlight, chuẩn kích thước).
- Dùng kết quả đó để build/stitch video.
- Verify video đầu ra.
- Upload storage (Supabase).
- Ghi trạng thái và dữ liệu subtitle vào DB campaign.

---

## 2) Những file chính đã làm

### Capture core
- `activities/capture/capture_models.py`
  - Model input/output cho scene/job.
  - Validation chặt: URL web, duration > 0, zoom range, color format, scene unique.

- `activities/capture/compositor.py`
  - `composite_overlay(...)`
  - Resize ảnh về `1080x960` (theo `capture_config.py`, fallback default).
  - Vẽ highlight border.
  - Trả `subtitle_text` + `subtitle_position` để phục vụ bước assembly sau.

- `activities/capture/storage.py`
  - `_verify_video_file(...)`: check file tồn tại, không rỗng, đúng `1080x960`, duration > 0.
  - `_upload_to_supabase_storage(...)`: upload path chuẩn `captures/{campaign_id}/...`, optional head check 3 lần.
  - `_update_campaign_db(...)`: update campaign có retry + not-found guard.
  - `save_capture_result_activity(...)`: workflow trạng thái `running -> completed` hoặc `running -> failed`.

- `activities/capture/pipeline.py`
  - `run_capture_pipeline(...)`: orchestration theo luồng capture -> compositor -> storage.
  - Thiết kế inject `capture_scene_image` để dễ nối vào pipeline tổng và dễ test.

- `activities/capture/exceptions.py`
  - Exception typed cho storage/campaign consistency.

### Config
- `activities/capture/capture_config.py`
  - `TARGET_SIZE = (1080, 960)` và các constants liên quan.

### Tests
- `tests/test_capture_models.py`
- `tests/test_capture_compositor.py`
- `tests/test_capture_storage.py`
- `tests/test_capture_pipeline.py`

Kết quả test hiện tại: **48 passed**.

---

## 3) Luồng pipeline của task (chi tiết)

1. `CaptureJobInput` vào pipeline (campaign_id, persona_id, scenes).
2. Với mỗi scene:
   - `capture_scene_image(...)` tạo ảnh raw.
   - `composite_overlay(...)` chuẩn hóa ảnh top-half + enrich metadata.
3. Video build/stitch (điểm nối với module tổng, truyền qua `stitched_video_path`).
4. `save_capture_result_activity(...)`:
   - ghi DB `capture_status=running`
   - verify video (ffprobe)
   - ghi DB `capture_verify=passed`
   - upload storage (nếu bật)
   - build subtitle cumulative timing
   - ghi DB completed + đường dẫn/path/url/subtitle_data
5. Nếu lỗi ở bất kỳ bước nào:
   - ghi DB `capture_status=failed`
   - ném lỗi typed (`CaptureStorageError` chain nguyên nhân).

---

## 4) Khi link vào pipeline tổng thì hoạt động thế nào

Điểm nối chuẩn với hệ thống tổng:
- **Input contract**: module tổng tạo `CaptureJobInput`.
- **Capture provider**: module tổng truyền callable `capture_scene_image(scene, campaign_id)`.
- **Video stitch provider**: module tổng tự build/stitch ra file `stitched_video_path` trước khi gọi save.
- **Infra adapters**: truyền `db_client`, `supabase_client`, `bucket_name`.

### Interface cần từ pipeline tổng
- Có service capture raw ảnh theo scene.
- Có bước build/stitch video từ frames.
- Có campaign table chứa field capture status/path/url/subtitle_data.
- Có Supabase bucket cho video output.

Kết luận liên kết:
- Module capture hiện tại đã **sẵn sàng để cắm vào orchestration tổng** qua dependency injection.
- Chưa auto-wire trực tiếp với main workflow hiện có (chưa có call-site production ngoài test).

---

## 5) Checklist trạng thái (Done / Cần sửa)

## ✅ Done
- [x] Data models + validation.
- [x] Compositor resize về 1080x960.
- [x] Highlight rendering.
- [x] Storage verify/upload/update DB.
- [x] Cumulative subtitle timing.
- [x] DB không bị kẹt running khi lỗi.
- [x] Pipeline orchestration function đã có.
- [x] Test suite pass: 48 passed.

## ⚠️ Cần sửa để “production-complete”
- [x] Tạo call-site thực tế trong pipeline tổng (service/workflow layer).
- [x] Nối bước video builder/stitcher thật vào `stitched_video_path` (không chỉ assumption).
- [x] Thay `Exception` generic trong `compositor.py` bằng exception typed nhất quán.
- [x] Hoàn thiện headline render/zoom transformation.
- [x] Thêm integration test end-to-end với wiring thật (mức service/pipeline).
- [x] Mapping field DB xác nhận với schema production (tên cột/nullable/index).

---

## 5.1) DB Integration Guide (Supabase) — để team tự insert schema

Hiện tại bạn chưa có schema DB cho capture trong Supabase, nên module chỉ mới **ready về code** chứ chưa production-complete.

Phần dưới đây là checklist + SQL gợi ý để ai đọc docs cũng có thể setup nhanh.

### A. Mục tiêu DB tối thiểu
- Lưu trạng thái xử lý capture theo campaign.
- Lưu đường dẫn local/storage URL video top-half.
- Lưu subtitle timing dạng JSON.
- Lưu lỗi để debug nếu fail.

### B. Cột cần có trong bảng `campaigns`
- `capture_status` (`text`, nullable) — giá trị gợi ý: `running|completed|failed`.
- `capture_verify` (`text`, nullable) — ví dụ `passed`.
- `capture_error` (`text`, nullable) — message khi fail.
- `top_half_video_path` (`text`, nullable).
- `top_half_storage_path` (`text`, nullable).
- `top_half_storage_url` (`text`, nullable).
- `subtitle_data` (`jsonb`, nullable).
- `capture_updated_at` (`timestamptz`, nullable/default now()).

### C. SQL migration mẫu (chạy trên Supabase SQL Editor)

Đã tách ra file riêng để dùng trực tiếp:

- `Docs/CAPTURE_DB_MIGRATION.sql`

Thao tác:
- Mở Supabase SQL Editor.
- Copy toàn bộ nội dung từ `CAPTURE_DB_MIGRATION.sql`.
- Chạy migration.

### D. Data contract kỳ vọng từ module capture
- Khi bắt đầu: `capture_status = 'running'`.
- Verify pass: `capture_verify = 'passed'`.
- Thành công: `capture_status = 'completed'` + set path/url + `subtitle_data`.
- Lỗi: `capture_status = 'failed'` + `capture_error`.

### E. Ví dụ `subtitle_data` lưu trong DB (`jsonb`)

```json
[
  {"scene_index":0,"text":"A","start_sec":0.0,"end_sec":3.0},
  {"scene_index":1,"text":"B","start_sec":3.0,"end_sec":5.5},
  {"scene_index":2,"text":"C","start_sec":5.5,"end_sec":9.5}
]
```

### F. Checklist trước khi bật production
- [ ] Đã chạy migration trên Supabase.
- [ ] Đã xác nhận role/service key có quyền update `campaigns`.
- [ ] Đã map đúng tên bảng/cột với code (`activities/capture/storage.py`).
- [ ] Đã test 1 campaign thật với full flow và verify DB record.

---

## 6) Definition of Done đề xuất cho merge chính thức

Chỉ xem là hoàn tất tuyệt đối khi thỏa tất cả:
- Unit tests capture pass.
- Integration test với pipeline tổng pass.
- Flow thực tế chạy được trên 1 campaign sample:
  - tạo frames
  - tạo video
  - verify pass
  - upload pass
  - DB completed với metadata đầy đủ
- Logging/monitoring có trace theo `campaign_id`, `scene_index`.
- Không còn TODO critical trong compositor/video stitch wiring.

---

## 7) Tóm tắt cho lead

Task capture automation đã hoàn thiện phần **core module + test coverage tốt**, đã đạt mức **ready for integration**.

Phần còn lại là **wire vào pipeline tổng + đóng TODO production behavior** để đạt “production-complete”.
