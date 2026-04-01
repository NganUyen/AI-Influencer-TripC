Đây là bản spec hoàn chỉnh:

---

# RECORDED DEMO VIDEO MODE SPEC
**Version 1.0 — Status: Requirement Level, Implementation Ready**

---

## 1. Mục tiêu

Thêm một input mode mới cho lane create video hiện tại. User upload video screen demo của app hoặc website. Hệ thống dùng video đó làm evidence để build pre-production package và dùng chính video đó làm top half footage trong split-screen video.

Feature này phải:
- Giữ nguyên pipeline core hiện tại
- Không rewrite bottom half lane
- Không dùng OpenClaw để parse raw video
- Tận dụng Telegram pre-production flow hiện có
- Output cuối vẫn là `ApprovedProductionPackage`
- Production vẫn đi vào `ShortVideoWorkflow`

---

## 2. Phạm vi phase đầu

Phase đầu support: user tự upload recorded demo video, official website hoặc app URL, goal kiểu promo/walkthrough/tutorial, audience, CTA, optional emphasis.

Phase đầu chưa support: external video URL (YouTube, TikTok), reuse third-party video làm footage, auto classify screen recording bằng model nặng, beat-by-beat editor, multimodal source merge từ nhiều video.

---

## 3. Kiến trúc tổng quát

Pipeline mới:
```
recorded_demo_video input
→ input quality gate
→ video analysis
→ video evidence build
→ web grounding with OpenClaw
→ user preview confirm
→ ConceptBrief
→ BeatSheet
→ ApprovedProductionPackage
→ existing production pipeline
```

Backbone không đổi:
```
evidence → concept → beats → approved_package → production
```

---

## 4. Quy tắc kiến trúc bắt buộc

### 4.1 Pipeline core không đổi

Không được tạo production pipeline mới chỉ vì input thay đổi. Giữ nguyên: script generation lane, TTS lane, HeyGen talking head lane, final split screen assembly, Telegram preview delivery, final save hoặc discard flow.

### 4.2 OpenClaw role

OpenClaw chỉ được dùng cho: official website grounding, official docs/feature page verification, naming verification cho feature, value proposition verification, optional browser verification của claim.

OpenClaw không được dùng cho: decode raw video, extract frames, OCR trên video frame, speech-to-text từ audio, segment detection, video trimming.

### 4.3 Video understanding rule

Không được generate script trực tiếp từ raw video. Bắt buộc đi qua:
```
video → evidence → concept → beats → script
```

### 4.4 Source of truth priority

Khi có conflict giữa các nguồn, ưu tiên theo thứ tự:
```
official site or docs
> user confirmation
> video evidence
> model inference
```

Rule này phải được bake vào prompt hoặc reasoning instruction của agent build ConceptBrief và BeatSheet.

---

## 5. Input mode mới

Thêm `creative_input_mode` mới: `idea_brief` (hiện tại) và `recorded_demo_video` (mode mới).

Mode mới chỉ thay pre-production path. Production output contract cuối vẫn tương thích với `ApprovedProductionPackage`.

---

## 6. Use cases được support ở phase đầu

Tối ưu cho: website feature walkthrough, dashboard flow demo, app onboarding flow, create post/publish flow, schedule flow, analytics dashboard walkthrough, UI-based product promo.

Không tối ưu cho phase đầu: game, animation heavy apps, video editor phức tạp, screen quá nhiều chuyển động liên tục, chat app nhảy liên tục, non-UI real world footage.

Các giới hạn này thể hiện trong Telegram onboarding copy và prompt instruction. Không cần hard block bằng code ở phase đầu.

---

## 7. Input contract

### 7.1 Required fields

```json
{
  "creative_input_mode": "recorded_demo_video",
  "persona_id": "string",
  "demo_video_asset": "string",
  "reference_url": "string",
  "video_goal": "promo | walkthrough | tutorial",
  "audience": "string",
  "cta": "string"
}
```

### 7.2 Optional fields

```json
{
  "project_name": "string",
  "feature_focus_optional": "string",
  "user_notes": "string",
  "must_keep_segments": [],
  "language_override": "string"
}
```

### 7.3 Input semantics

- `feature_focus_optional` không được treat như required field
- Nếu user bỏ qua, pipeline tự derive feature candidates từ evidence
- `reference_url` là official website hoặc official app related source
- `demo_video_asset` là media asset đã upload xong và truy xuất được

---

## 8. Video constraints

Duration: recommended dưới 90 giây, hard limit tối đa 3 phút (180 giây).

Nếu vượt hard limit: không chạy full analysis, bot yêu cầu user chọn đoạn chính hoặc reupload, không âm thầm cắt bừa video.

Format support tối thiểu: mp4, mov.

Chi tiết quality checks xem Section 9.

---

## 9. Quality gate spec

Quality gate phải chạy trước pipeline analysis nặng.

### 9.1 Required checks
`duration_sec`, `width`, `height`, orientation, file container readable, blur score cơ bản.

### 9.2 Thresholds

| Check | Warn | Reject |
|---|---|---|
| Duration | 90s < dur <= 180s | > 180s |
| Resolution | 480p–719p | < 480p |
| Blur score | Hơi thấp, vẫn usable | Quá nặng |
| File readable | — | Unreadable |

### 9.3 Reject path

Nếu reject, user phải có thể reupload mà không restart toàn bộ flow. Messages ví dụ:
- "Vui lòng cắt còn dưới 3 phút hoặc chọn đoạn chính."
- "Vui lòng upload lại bản rõ hơn (720p trở lên)."
- "Không đọc được file. Vui lòng kiểm tra định dạng mp4 hoặc mov."

### 9.4 Warn path

- Blur hơi thấp: "Hệ thống vẫn có thể thử nhưng kết quả có thể kém chính xác."
- Duration 90s–180s: "Khuyến nghị dưới 90s để kết quả tốt nhất. Vẫn tiếp tục?"

---

## 10. Video analysis pipeline

Video analysis phải là service riêng hoặc group activities riêng. Không để OpenClaw làm.

### 10.1 Video metadata probe
Dùng ffmpeg hoặc tương đương để lấy: duration, fps, width, height, orientation, codec info cơ bản.

### 10.2 Segmentation
Detect screen changes, detect major state changes, giảm số frame cần analyze. Không cần frame-perfect scene detection, chỉ cần đủ để gom step-level segments.

### 10.3 Keyframe extraction
Không được analyze mọi frame. Extract representative frames theo segment: frame đầu, frame giữa, frame cuối, hoặc frame informative nhất.

### 10.4 OCR
Chạy OCR trên keyframes để lấy: button labels, menu text, tab text, page title, form labels, toast/status text, call-to-action text.

### 10.5 Visual layout summary
Dùng vision model hoặc equivalent summary logic để hiểu screen type, action type, major layout, state change meaning. Ví dụ labels: dashboard screen, create post screen, scheduling modal, analytics panel, publish confirmation.

Fallback: nếu không có vision model, fallback sang OCR-only summary với label inference từ extracted UI text.

### 10.6 Timeline understanding
Từ segments và keyframes, build chuỗi step-level. Output phải trả lời được: đoạn nào diễn ra trước, user đang làm gì ở từng đoạn, đâu là transition step, đâu là potentially feature-relevant step.

---

## 11. Fallback rules cho video analysis

| Condition | Fallback action | Rule |
|---|---|---|
| OCR fail / yếu | Fallback sang visual layout summary | Auto, không hỏi user |
| OCR + visual đều yếu | Hỏi user mô tả flow ngắn | 1 câu ngắn, không fail cứng |
| Confidence thấp | Không được bịa feature names | Ask confirm hoặc degrade gracefully |

---

## 12. Internal evidence schema — RecordedDemoEvidence

Artifact nội bộ mới. Không expose raw JSON cho user trong Telegram.

### 12.1 Schema shape

```json
{
  "video_quality": {
    "duration_sec": 0,
    "width": 0,
    "height": 0,
    "orientation": "portrait|landscape",
    "blur_score": 0.0,
    "quality_status": "pass|warn|reject"
  },
  "timeline_summary": [
    {
      "idx": 1,
      "start_sec": 0.0,
      "end_sec": 5.0,
      "summary": "user lands on dashboard",
      "ocr_text": ["Dashboard", "Posts", "Analytics"],
      "visual_labels": ["dashboard", "navigation"],
      "analysis_confidence": 0.82
    }
  ],
  "feature_candidates": [
    {
      "name": "post creation",
      "description": "user creates a new post from dashboard",
      "evidence_segments": [2, 3],
      "grounding_sources": ["https://official-site/features"],
      "confidence": 0.88
    }
  ],
  "analysis_confidence_overall": "high|medium|low"
}
```

### 12.2 Tách 2 lớp bắt buộc

`timeline_summary` = chuyện gì xảy ra trong video (thứ tự các bước, mô tả per segment, OCR text và visual labels).

`feature_candidates` = thứ gì đáng đưa vào promo/narration (tên feature, evidence segments, grounding sources, confidence score).

Không được gộp thành một blob summary.

---

## 13. Analysis confidence tổng

### 13.1 Compute logic — không dùng model riêng

Aggregate từ: số segment có OCR usable, số feature candidate có grounding match, mức completeness của user input, consistency giữa video evidence và web grounding.

### 13.2 Routing theo level

| Level | Behavior | Note |
|---|---|---|
| high | Auto continue sang preview confirm | |
| medium | Continue nhưng preview confirm nhấn mạnh hơn | Bot hỏi xác nhận kỹ hơn |
| low | Bắt buộc hỏi thêm user trước khi build concept | Không được overclaim |

### 13.3 Timeout rule cho low confidence clarification

Nếu `analysis_confidence_overall = low` và user không reply trong 15 phút: abort pre-production attempt, notify user rõ ràng rằng flow đã dừng do thiếu xác nhận, cho phép user retry hoặc reupload. Không được để flow treo vô hạn.

---

## 14. OpenClaw grounding step

### 14.1 Inputs cho grounding
`reference_url`, `project_name` (nếu có), `timeline_summary`, `feature_candidates`, `video_goal`, `audience`, `cta`.

### 14.2 OpenClaw responsibilities
Mở official page, tìm feature/docs page, verify tên feature, verify claim có xuất hiện chính thức không, summarize official value prop ngắn gọn, attach source references nội bộ nếu cần.

### 14.3 Output và no-overclaim rule

Grounding step phải enrich hoặc correct: `feature_candidates`, naming, value proposition, official terminology.

Nếu official site không xác nhận được một feature: không được biến model inference thành fact, có thể giữ như tentative nếu user confirm, nếu không chắc thì ask user.

---

## 15. Preview confirm step

Bắt buộc có step này sau analysis + grounding, trước ConceptBrief.

### 15.1 Mục tiêu
Giảm drift sớm. User xác nhận hệ thống hiểu đúng trước khi tốn tài nguyên build concept.

### 15.2 User-visible summary
Telegram gửi summary ngắn kiểu:

> "Mình thấy video đang demo 3 bước chính: Tạo bài đăng, Chọn lịch đăng, Publish. Đúng không? Bạn có muốn nhấn mạnh phần nào thêm không?"

### 15.3 User actions
User có thể: confirm, sửa, nhấn mạnh lại phần muốn nói. Nếu user chỉnh, pipeline phải update evidence summary hoặc emphasis trước khi build ConceptBrief.

### 15.4 Timeout rule
Nếu user không reply confirm/sửa trong 15 phút: abort và notify user, cho phép retry mà không restart toàn bộ flow.

---

## 16. ConceptBrief generation rule

ConceptBrief phải build từ: `feature_candidates`, `timeline_summary`, `video_goal`, `audience`, `cta`, user confirmation, official grounding.

ConceptBrief không được drift khỏi: user confirmed direction, official verified terminology, actual demo flow trong video.

Nếu user đã nêu `feature_focus_optional`: dùng như emphasis nhưng vẫn verify against evidence, không dùng như override tuyệt đối.

---

## 17. BeatSheet generation rule

### 17.1 Fields bắt buộc mỗi beat

| Field | Description |
|---|---|
| `purpose` | hook / feature_demo / cta / etc. |
| `bottom_half_message` | Message AI influencer nói ở bottom half |
| `top_half_source_type` | `uploaded_demo_video` (canonical cho mode này) |
| `top_half_target` | Timestamp range HH:MM:SS-HH:MM:SS |
| `duration_sec` | Số giây của beat |
| `trim_confidence` | Float 0–1, confidence của trim selection |

### 17.2 top_half_target canonical format

Canonical storage format: `HH:MM:SS-HH:MM:SS`, ví dụ `00:00:12-00:00:18`.

`segment_id` có thể tồn tại nội bộ trong analysis nhưng không được dùng làm canonical `top_half_target` trong BeatSheet final.

### 17.3 BeatSheet example

```json
{
  "beats": [
    {
      "idx": 1,
      "purpose": "hook",
      "bottom_half_message": "Create and schedule content in one flow.",
      "top_half_source_type": "uploaded_demo_video",
      "top_half_target": "00:00:03-00:00:08",
      "duration_sec": 5,
      "trim_confidence": 0.91
    },
    {
      "idx": 2,
      "purpose": "feature_demo",
      "bottom_half_message": "Pick a date, set a time, done.",
      "top_half_source_type": "uploaded_demo_video",
      "top_half_target": "00:00:18-00:00:26",
      "duration_sec": 8,
      "trim_confidence": 0.85
    }
  ]
}
```

---

## 18. ApprovedProductionPackage compatibility

Không rewrite schema: `concept_brief`, `beat_sheet`, `persona_snapshot` giữ nguyên. Chỉ add fields hỗ trợ top half mapping nếu cần, không phá consumer hiện tại.

Backward compatibility scope — consumers hiện tại: `ShortVideoWorkflow`, package-to-script conversion path, `ScriptService` hoặc equivalent, Telegram package-ready summary path nếu đang đọc package fields.

---

## 19. Production behavior trong recorded demo mode

Top half: lấy từ video user upload, trim theo canonical timestamp mapping, tránh random recut nếu `trim_confidence` thấp.

Bottom half: giữ nguyên toàn bộ — script build, TTS, HeyGen/talking head, assembly logic.

---

## 20. Telegram flow spec

### 20.1 Entry → mode selection
```
User: Create Video
Bot: Idea Brief  |  Recorded Demo Video
```

### 20.2 Recorded demo mode — step by step

| # | Actor | Action |
|---|---|---|
| 1 | [user] | Chọn persona |
| 2 | [user] | Upload video |
| 3 | [user] | Nhập official URL |
| 4 | [user] | Chọn goal (promo / walkthrough / tutorial) |
| 5 | [user] | Nhập audience |
| 6 | [user] | Nhập CTA |
| 7 | [user] | (Optional) Nhập phần muốn nhấn mạnh |
| 8 | [system] | Chạy quality gate |
| 9 | [system] | Analyze video |
| 10 | [system] | Run OpenClaw grounding |
| 11 | [system] | Gửi preview confirm understanding |
| 12 | [user] | Confirm hoặc sửa |
| 13 | [system] | Generate ConceptBrief |
| 14 | [user] | Approve concept |
| 15 | [system] | Generate BeatSheet |
| 16 | [user] | Approve beats |
| 17 | [system] | Package ready |
| 18 | [system] | Start production / handoff theo product rule hiện tại |

`feature_focus` không được hỏi như required. Bot hỏi mềm: "Bạn có muốn nhấn mạnh phần nào không?"

Nếu user input clearly outside supported cases: warn nhẹ, vẫn có thể tiếp tục nếu evidence đủ, không hard block ở phase đầu.

---

## 21. Error handling và retry

Retryable: transient OCR failure, transient video frame extraction issues, temporary OpenClaw grounding issue, temporary web fetch problem.

Non-retryable: unreadable uploaded file, duration over hard limit và không có user trim, irrecoverably low quality, missing required reference URL sau prompt.

Nếu evidence thấp: hỏi user thêm 1 câu ngắn thay vì fail cứng.

---

## 22. Required implementation boundaries

Cần thêm hoặc sửa rõ ràng: recorded demo analysis service, Telegram step config updates cho mode selection và recorded demo flow, quality gate path, timestamp-mapped beat support, preview confirm step trước ConceptBrief, analysis confidence calculator.

Nên có: dedicated OCR helper/service, dedicated grounding activity abstraction, reusable timestamp trim utility cho top half extraction.

Không nên đụng mạnh: bottom half services, TTS services, HeyGen service, existing production workflow structure.

---

## 23. Agent verification checklist

**Input and flow**
- Có support `creative_input_mode = recorded_demo_video`
- Telegram flow có mode selection
- Recorded demo mode không hỏi feature_focus như required
- Có step preview confirm trước ConceptBrief

**Quality gate**
- Có metadata probe (ffmpeg)
- Có duration handling với recommended và hard limit
- Có resolution handling
- Có blur / basic quality handling
- Có early reject và warn path
- Reject path cho phép reupload mà không restart full flow

**Video analysis**
- Có segmentation
- Có keyframe extraction
- Không analyze toàn bộ frame
- Có OCR path
- Có visual summary path hoặc OCR-only fallback path
- Có timeline summary output
- Tách `timeline_summary` và `feature_candidates`

**Confidence**
- Có analysis confidence tổng
- Confidence được derive từ existing signals, không cần model mới
- `low` confidence có clarification timeout 15 phút

**Grounding**
- OpenClaw chỉ làm web grounding
- Không parse raw video
- Có source of truth priority rule baked vào agent prompt

**Pre-production**
- ConceptBrief build từ grounded evidence
- BeatSheet map tới real video timestamps canonical format
- Có `trim_confidence`
- Package ready vẫn compatible với current production handoff

**Production**
- Top half dùng uploaded demo video segments theo canonical timestamp range
- Bottom half không cần rewrite lớn
- Assembly path reuse hiện tại

**Error handling**
- OCR fail có fallback
- OCR + visual fail có ask user fallback
- `low` confidence không được overclaim
- Timeout clarification path abort rõ ràng và notify user

---

## 24. Acceptance criteria

**Happy path**
1. User có thể chọn recorded demo mode trong Telegram
2. User upload demo video và official URL
3. System pass quality gate
4. System tạo được `timeline_summary` và `feature_candidates` riêng biệt
5. OpenClaw verify được ít nhất một phần feature naming hoặc value proposition
6. User thấy preview understanding và confirm được
7. System generate được ConceptBrief grounded từ evidence
8. System generate được BeatSheet có canonical timestamp mapping và `trim_confidence`
9. `ApprovedProductionPackage` vẫn chạy vào production lane hiện tại
10. Final output dùng top half từ uploaded video và bottom half từ existing AI influencer lane

**Failure path**
11. Nếu video fail quality gate: user nhận reject message rõ ràng, có thể reupload mà không restart toàn bộ flow
12. Nếu `analysis_confidence_overall = low` và user không reply trong 15 phút: flow abort rõ ràng, user được notify, có thể retry

---

## 25. Một câu chốt cuối cùng

Feature này là mở rộng pre-production input cho create video, không phải tạo một pipeline video mới.

Input thay đổi. Backbone giữ nguyên. Video user upload vừa là evidence để build concept, vừa là footage cho top half. OpenClaw chỉ ground và verify trên official web sources, không xử lý raw video.