# Persona / Media / Video Pipeline Issues

Ngày cập nhật: 2026-03-27

## Tóm tắt

Hiện tại pipeline tạo video dọc 9:16 đang bị lỗi từ tầng `persona`.

Vấn đề chính không nằm ở bước ghép video trước, mà nằm ở việc persona và avatar media của persona không được lưu bền vững như hệ thống kỳ vọng. Vì vậy:

- bot có thể báo tạo persona thành công
- preview avatar có thể vẫn hiển thị
- nhưng persona thực tế chưa đủ điều kiện để dùng cho video pipeline
- video sẽ không chạy ổn định vì không resolve được persona media cần thiết

Nói ngắn gọn: `storage`, `persona persistence`, và `video readiness` hiện đang lệch nhau.

## Triệu chứng đã thấy

- Bot báo persona đã được tạo hoặc preview đã sẵn sàng.
- Log readiness lại báo:

```text
Missing avatar_media_asset_id. Save persona media first.
```

- Kiểm tra Supabase bucket `media` không thấy file như mong đợi.
- `persona-inspector` chạy xong nhưng không hiện đầy đủ chi tiết persona trong Telegram UI.
- Khi persona không có media asset bền vững, pipeline video không thể dùng persona đó để đi tiếp một cách chuẩn.

## Phạm vi phân tích và mapping tên skill

Trong quá trình kiểm tra, có một điểm quan trọng:

- tên thao tác mà operator gọi trong chat không khớp hoàn toàn với tên implementation đang active trong repo
- vì vậy cần map đúng để debug chính xác

Mapping đang dùng cho phân tích này:

- `/fal-ai`
  tương ứng chủ yếu với:
  - `Project/python_services/services/fal_service.py`
  - `Project/python_services/services/image_generation_service.py`
  - `Project/python_services/activities/media_activities.py`
- `/heygen-avatar-lite`
  hiện không thấy là một active skill hoàn chỉnh trong `SKILL_REGISTRY`
  nhưng logic tương ứng nằm ở:
  - `Project/python_services/services/heygen_service.py`
  - `Project/python_services/scripts/setup_persona.py`
  - phần khai báo `persona-setup` trong cấu hình Telegram skill
- `/ai-video-gen`
  tương ứng với luồng:
  - `Project/python_services/skills/video_ai.py`
  - `Project/python_services/api/workflows.py`
  - `Project/python_services/workflows/short_video_workflow.py`
  - `Project/python_services/activities/video_activities.py`

Kết luận:

- `fal-ai` có implementation sống
- `video-ai` có implementation sống
- phần `heygen avatar setup` mới chỉ hiện diện một phần, chưa được nối trọn vẹn vào live Telegram skill flow

## Lỗi cốt lõi

### 1. Persona có thể "trông như đã tạo xong" nhưng thực ra chưa được lưu hoàn chỉnh

Flow tạo persona trong Telegram có thể trả về trạng thái thành công và hiển thị preview, dù bước đồng bộ avatar/profile gặp lỗi.

Điều này tạo ra cảm giác là persona đã xong, nhưng thực tế chưa chắc đã có:

- `avatar_media_asset_id`
- media record trong `public.media_assets`
- object thật trong Supabase Storage

Kết quả là persona tồn tại ở mức preview/UI, nhưng chưa đủ dữ liệu để pipeline video sử dụng.

### 2. Storage có cơ chế fallback nên che mất lỗi persistence

Pipeline ảnh đang cho phép fallback sang `source_only` khi lưu storage thất bại.

Điều đó có nghĩa là:

- ảnh từ provider vẫn có URL để preview
- nhưng media asset nội bộ có thể không được tạo
- `media_asset_id` có thể là `None`

Vì vậy hệ thống vẫn nhìn giống như "đã có avatar", nhưng readiness chính thức vẫn fail vì không có `avatar_media_asset_id`.

### 3. Readiness ở persona và trải nghiệm Telegram đang không đồng nhất

Ở lớp Telegram/preview, người dùng có thể thấy thông báo kiểu "Persona Created Successfully".

Nhưng lớp readiness chuẩn của registry lại chặn tiếp vì persona thiếu avatar asset đã lưu.

Đây là mismatch quan trọng:

- UI nói gần như thành công
- backend readiness nói chưa đủ điều kiện

### 4. Persona DB có degraded fallback nên có thể xuất hiện trạng thái "thành công ảo"

Nếu DB write hoặc update lỗi, service hiện có nhánh fallback sang memory.

Điều này nguy hiểm cho pipeline vì:

- trong phiên hiện tại có thể vẫn nhìn thấy persona
- nhưng dữ liệu không bền vững
- sau đó inspector, readiness, hoặc workflow khác có thể không lấy lại được persona đúng cách

Nói cách khác: persona có thể "có trong session", nhưng không thực sự có trong hệ thống lưu trữ cần thiết cho pipeline video.

### 5. `persona-inspector` lấy dữ liệu có thật, nhưng Telegram renderer không show đủ

Inspector hiện gọi được API persona và readiness, nhưng phần render trên Telegram chỉ show thông tin rất ngắn.

Vì vậy khi kiểm tra persona, người dùng không nhìn thấy đầy đủ:

- avatar media asset
- readiness checks
- trạng thái lưu storage
- các field quan trọng để biết chính xác persona đang thiếu gì

## Phân tích sâu theo từng lane

### Lane 1. `fal-ai` đang tạo preview được, nhưng không đảm bảo tạo được persona asset bền vững

Đây là lane sinh ảnh avatar hoặc scene image.

Trạng thái hiện tại:

- fal.ai có thể trả ảnh thành công
- ảnh có thể hiện ở preview
- nhưng bước persist sang storage nội bộ có thể fail âm thầm
- khi đó hệ thống fallback sang `source_only`

Điều này tạo ra khoảng lệch rất lớn giữa:

- cái người dùng nhìn thấy
- và cái pipeline thật sự cần

Pipeline thật sự cần:

- file được lưu vào storage của hệ thống
- có row trong `public.media_assets`
- có `media_asset_id`
- persona giữ được `avatar_media_asset_id`

Nhưng lane `fal-ai` hiện cho phép trường hợp:

- `url` có
- `storage_url` không có
- `media_asset_id` là `None`
- flow vẫn tiếp tục

Kết quả:

- preview avatar nhìn như ổn
- nhưng readiness persona vẫn fail
- video pipeline không dùng được persona này theo contract chính thức

### Lane 2. `heygen-avatar-lite` thực tế chưa có live path hoàn chỉnh trong skill layer

Đây là lỗi rất quan trọng.

Ở mức product/UX:

- persona muốn dùng cho AI influencer video phải có `heygen_avatar_id`
- readiness canonical cũng yêu cầu `heygen_avatar_id`

Nhưng ở mức implementation:

- `PersonaCreatorSkill` không hề gọi `HeyGenService.create_avatar()`
- `SKILL_REGISTRY` active không có skill `persona-setup`
- cấu hình Telegram skill có nhắc `register_heygen` và `persona-setup`, nhưng phần wiring live chưa hoàn tất

Điều đó dẫn tới tình trạng:

- bot cho tạo persona preview
- bot cho save persona
- nhưng persona vẫn thường không có `heygen_avatar_id`

Nói ngắn gọn:

- UI ngụ ý rằng pipeline persona gần hoàn chỉnh
- nhưng live code path chưa thực hiện được bước setup avatar cho HeyGen

### Lane 3. Script `setup_persona.py` đang stale và không thể coi là đường setup chuẩn

Repo hiện có `scripts/setup_persona.py`, nhưng script này không đại diện cho live product path.

Các vấn đề lớn:

1. script dùng `DEMO_PERSONAS` in-memory
   - không đọc persona thật từ registry/database đang chạy
   - không phản ánh dữ liệu thật trong production flow

2. script dùng field `avatar_status`
   - trong khi service persona chính dùng `status`
   - điều này làm logic readiness/registry và script bị lệch model dữ liệu

3. `HeyGenService.create_avatar()` trả về `str`
   - nhưng script lại xử lý như `dict` và gọi `.get("avatar_id")`
   - đây là bug code-level trực tiếp

4. script chỉ in cảnh báo "lưu heygen_avatar_id vào Supabase personas table"
   - nghĩa là bước persist cuối còn chưa được tích hợp trọn vẹn

Kết quả:

- script này không thể xem là giải pháp vận hành ổn định để cứu live flow
- kể cả chạy script, operator vẫn phải tự nối thêm bước lưu DB đúng contract

### Lane 4. `ai-video-gen` chấp nhận persona ở trạng thái chưa đồng nhất với readiness canonical

Đây là bug contract ở tầng workflow entrypoint.

Readiness canonical trong `PersonaRegistryService` yêu cầu:

- `status == ready`
- có `tts_voice`
- có `avatar_media_asset_id`
- có `heygen_avatar_id`

Nhưng `/api/workflows/start-video` lại chỉ check:

- persona có tồn tại
- `status == ready`
- có `tts_voice`

Nó không chặn cứng ở API layer khi thiếu:

- `avatar_media_asset_id`
- `heygen_avatar_id`

Sau đó `VideoAISkill` lại có thêm logic fallback:

- nếu thiếu `heygen_avatar_id` nhưng vẫn đủ vài check khác
- skill vẫn cho start workflow với `talking_head_optional = True`

Điều này làm contract trở nên không đồng nhất:

- một chỗ nói persona chưa ready
- chỗ khác vẫn cho start video

### Lane 5. `ShortVideoWorkflow` tiếp tục hợp thức hóa trạng thái fallback

Trong workflow:

- nếu thiếu `heygen_avatar_id`
- hệ thống không fail ngay
- mà chuyển sang fallback slideshow + audio

Về mặt sản phẩm, điều này có thể chấp nhận được nếu chủ đích là “cho ra video dù không có talking head”.

Nhưng với use case hiện tại của bạn:

- bạn đang muốn AI influencer split-screen thật sự
- nửa dưới là talking head / HeyGen

Vậy fallback này tạo ra hiểu nhầm:

- user nghĩ đang chạy AI influencer full lane
- nhưng hệ thống có thể silently downgrade thành slideshow-only lane

Nói cách khác:

- workflow có thể “thành công”
- nhưng không phải thành công đúng loại video mà operator mong đợi

### Lane 6. Video/talking-head assets vẫn có nguy cơ bị mất DB tracking sau khi upload

Sau khi talking-head video hoặc final video được upload lên storage chính, việc ghi record vào `media_assets` đang chạy theo kiểu fire-and-forget bằng `asyncio.create_task(...)`.

Điều này có nghĩa:

- upload file có thể thành công
- nhưng insert DB record có thể fail ở background
- và flow hiện tại không đảm bảo operator sẽ thấy lỗi đó

Đây là một dạng bug “artifact exists but registry is incomplete”.

Nó rất giống kiểu lỗi đang xảy ra ở persona avatar:

- có URL
- có thể có file
- nhưng metadata/registry không đủ
- các bước sau không thể resolve asset theo contract chuẩn

## Ma trận lỗi theo use case

### Use case A. Tạo persona từ bot

Kỳ vọng:

- tạo persona
- sinh avatar
- lưu avatar vào storage
- tạo media asset record
- nếu cần AI influencer talking head thì tạo/attach `heygen_avatar_id`
- save persona về trạng thái ready thật

Thực tế hiện tại:

- create persona có thể thành công ở mức draft
- avatar preview có thể có
- persist avatar có thể fail và bị fallback
- `heygen_avatar_id` thường không được setup live
- UI vẫn có thể báo gần như thành công

### Use case B. Inspect persona

Kỳ vọng:

- thấy đầy đủ persona state
- biết thiếu `avatar_media_asset_id` hay `heygen_avatar_id`
- biết persona có thực sự ready cho split-screen hay không

Thực tế hiện tại:

- inspector fetch được data
- nhưng renderer Telegram không hiển thị đủ
- operator thiếu thông tin để chẩn đoán trực tiếp từ chat

### Use case C. Tạo AI influencer split-screen 9:16

Kỳ vọng:

- persona đã persist đầy đủ
- có `tts_voice`
- có `avatar_media_asset_id`
- có `heygen_avatar_id`
- workflow chạy đúng talking-head + slideshow

Thực tế hiện tại:

- nếu persona lỗi persistence thì readiness fail ngay
- nếu API layer hoặc skill layer fallback thì workflow vẫn có thể chạy
- nhưng có thể bị downgrade sang slideshow-only
- kết quả không phản ánh đúng mong muốn “AI influencer split-screen”

## Bug quan trọng nhất theo thứ tự ưu tiên

### Priority 1. Chưa có đường live hoàn chỉnh để persona sinh và lưu đủ 2 định danh quan trọng

Hai field quan trọng nhất đang làm nghẽn toàn bộ pipeline:

- `avatar_media_asset_id`
- `heygen_avatar_id`

Nếu thiếu một trong hai:

- readiness canonical không pass
- split-screen persona-driven không thể coi là sẵn sàng thật

### Priority 2. Product đang báo thành công sớm hơn trạng thái persistence thật

Đây là lỗi UX + control flow:

- bot báo thành công
- user tin là persona usable
- nhưng dữ liệu thật chưa đủ

Lỗi này làm việc debug và vận hành rất khó vì tạo cảm giác hệ thống “nói một đằng, backend làm một nẻo”.

### Priority 3. Contract giữa persona readiness và video entrypoint chưa thống nhất

Nếu hệ thống muốn cho phép fallback slideshow-only, cần tách rất rõ:

- persona ready cho full split-screen
- persona chỉ đủ cho slideshow fallback

Hiện tại hai trạng thái này đang bị trộn lẫn.

### Priority 4. Inspector chưa đủ chi tiết để operator tự chẩn đoán

Cho tới khi inspector hiển thị rõ:

- `status`
- `tts_voice`
- `avatar_media_asset_id`
- `heygen_avatar_id`
- readiness checks
- blocking reason

thì operator vẫn phải soi log/code để biết persona đang thiếu gì.

## Kết luận kỹ thuật chi tiết

Vấn đề không phải chỉ là “bucket Supabase đang trống”.

Đúng hơn, đây là tổ hợp của nhiều lỗi nối chuỗi:

- lane `fal-ai` cho phép fallback preview mà không bắt buộc persistence
- lane `heygen avatar` chưa được wire live đầy đủ
- script bootstrap HeyGen hiện đang stale
- persona readiness canonical chặt hơn UI/create flow
- video entrypoint và workflow lại cho một số fallback không phản ánh đúng kỳ vọng split-screen
- video/media asset tracking còn có nhánh fire-and-forget nên registry có thể thiếu dù file có tồn tại

Do đó:

- bug gốc đang nằm ở contract giữa `persona`, `storage`, `media registry`, `HeyGen setup`, và `video workflow`
- chừng nào các tầng này chưa thống nhất một định nghĩa chung về “persona ready”, pipeline vẫn còn fail hoặc tạo ra kết quả sai loại

## Ảnh hưởng tới video pipeline

Hiện tại lỗi persona làm block trực tiếp pipeline video.

Lý do:

1. Video flow cần persona tồn tại và lấy lại được từ registry.
2. Persona cần ở trạng thái `ready`.
3. Persona cần có `tts_voice`.
4. Persona cần có `avatar_media_asset_id` đã lưu.
5. Nếu không có asset persona đã persist, backend không coi persona là sẵn sàng để chạy video pipeline chuẩn.

Vì vậy, nếu persona không được lưu đúng vào DB/storage thì bước tạo video sẽ không thể chạy ổn định, hoặc sẽ bị chặn ngay từ readiness check.

Nói ngắn gọn:

- không lưu được persona media
- không có `avatar_media_asset_id`
- không resolve được persona readiness
- pipeline video không thể dùng persona đó để tạo video hoàn chỉnh

## Ảnh hưởng tới split-screen 9:16

Use case hiện tại là video 9:16 với:

- nửa bot là talking head / HeyGen
- nửa còn lại là slideshow / promotion

Flow này cần persona làm đầu vào quan trọng. Nếu persona không persist đúng thì:

- không đảm bảo lấy được avatar media của persona
- không đảm bảo persona được coi là `ready`
- talking-head lane không có đầu vào persona ổn định
- toàn bộ flow video trở nên không đáng tin cậy

Ngay cả khi slideshow lane còn có thể tạo asset riêng, pipeline persona-driven vẫn đang bị lỗi ở phần persona/storage trước khi thành phẩm video được xem là hợp lệ.

## Kết luận hiện tại

Tình trạng hiện tại nên được xem là:

- storage đang có vấn đề ở nhánh persona/media persistence
- persona creation chưa đáng tin cậy ở mức "created completely"
- persona-inspector chưa đủ rõ để debug trực tiếp từ Telegram
- video pipeline vẫn chưa thể coi là hoạt động ổn định vì persona là đầu vào đang lỗi

Kết luận vận hành:

Hiện tại chưa nên tin rằng persona đã sẵn sàng chỉ vì bot báo tạo thành công hoặc có preview avatar. Cho tới khi persona media được lưu thật vào storage + DB và readiness pass, pipeline video vẫn có thể fail hoặc bị block.

## Tham chiếu code liên quan

- `Project/python_services/skills/persona_creator.py`
- `Project/python_services/services/persona_registry_service.py`
- `Project/python_services/services/media_storage_service.py`
- `Project/python_services/services/image_generation_service.py`
- `Project/python_services/services/fal_service.py`
- `Project/python_services/services/heygen_service.py`
- `Project/python_services/services/skill_dispatcher.py`
- `Project/python_services/skills/persona_inspector.py`
- `Project/python_services/services/telegram_renderer.py`
- `Project/python_services/api/workflows.py`
- `Project/python_services/skills/video_ai.py`
- `Project/python_services/activities/media_activities.py`
- `Project/python_services/activities/video_activities.py`
- `Project/python_services/workflows/short_video_workflow.py`
- `Project/python_services/scripts/setup_persona.py`
