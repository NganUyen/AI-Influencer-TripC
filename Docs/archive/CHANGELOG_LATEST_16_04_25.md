# AI Influencer Dashboard - Recent Changes Log

## 1. Multi-Region Review Engine Orchestration
**Objective**: Connect the frontend "Review Engine" to the correct backend services to fetch website validation and orchestrate script generation/campaign creation.

### Backend Updates
*   **`Project/python_services/api/customer.py`**
    *   **Refactored Models**: Updated `ReviewEngineJobRequest` to accurately accept `objective` and a list of `target_personas` alongside the `source_url`.
    *   **Source Validation**: Implemented `POST /review-engine/source/validate` to hit `WebsiteReviewService.review_url`, unlocking normalized URL data and visible page features.
    *   **Job Orchestration**: Implemented `POST /review-engine/jobs`. This acts as the control plane that iterates over target personas, generates scripts using `ScriptService.generate_script_from_review_plan`, and creates new `Campaign` draft records via `CustomerCampaignService`.

## 2. Native Website Persona Editing
**Objective**: Transition persona management away from external Telegram deep-linking and build a native inline editing experience directly inside the Web Dashboard.

### Backend Updates
*   **`Project/python_services/api/customer.py`**
    *   **Read Payload Updates**: Modified `list_customer_personas` to return the previously hidden `appearance_prompt_or_photo` so the UI can populate its editing forms.
    *   **Direct Field Updates**: Added a new `PATCH /api/personas/{persona_id}` endpoint. This accepts updates to `display_name`, `tts_voice`, and `appearance_prompt_or_photo` and commits them using `PersonaRegistryService.update_persona`.
    *   **Avatar Regeneration**: Added a new `POST /api/personas/{persona_id}/rebuild-avatar` route. It triggers `ImageGenerationService` to produce a new image from the prompt, and then hooks into `HeyGenService` to register and process the new animated avatar safely in the background.

### Frontend Updates
*   **`Project/components/dashboard/PersonasTab.tsx`**
    *   **State Management**: Implemented `isEditing`, `editForm`, `isSaving`, and `isRebuilding` hooks to handle the UI transition from viewing to editing.
    *   **Inline Editing UI**: When "Edit Core" is clicked, replaced the static statistics view with a fluid form containing inputs for Persona Name, TTS Voice (Google Cloud TTS format), and the descriptive appearance prompt.
    *   **API Wiring**: Hooked up the "Save Adjustments" button to trigger the new `PATCH` API and the "Rebuild Avatar" button to hit the `POST` rebuild-avatar backend. Both actions have graceful loading spinners (`Loader2` from `lucide-react`) and error handling built in.
