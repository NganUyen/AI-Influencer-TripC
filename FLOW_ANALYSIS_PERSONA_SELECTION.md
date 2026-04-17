# Video Creation Flow Analysis: Persona Selection Issue

**Date:** April 17, 2026  
**Issue:** Personas are being selected PRE-URL-validation and sent together in a single API call, instead of being selected AFTER URL validation in a modal dialog, as documented in the architecture.

## Executive Summary

The current frontend implementation violates the documented video creation architecture by:

1. **Pre-populating personas before URL entry** - Uses initialPersonaIds prop to pre-select personas on component mount
2. **Showing persona grid on page load** - Displays full persona selection interface without waiting for URL validation
3. **Sending personas with URL in single API call** - Both URL and persona IDs sent together in POST /api/customer/review-engine/jobs
4. **No modal confirmation** - No separate step where user validates URL, sees analysis, then gets modal to select persona

The backend skills (ideo_ai.py and ideo_planner.py) correctly enforce the sequence:
- Collect objective ? Collect URL ? Validate URL ? **THEN** Pick persona

This creates a mismatch where the frontend bypasses URL validation before asking for persona selection.

## Current Flow (INCORRECT)

### Frontend: LiveFeedTab.tsx

Component Mount
    ? useEffect initializes selectedPersonas from initialPersonaIds (lines 117-123)
    ? Render persona grid immediately (NOT in modal) (lines 471-624)
    ? User enters URL (optional - not enforced before persona grid appears)
    ? User selects personas from grid
    ? Generate button enabled when: selectedPersonas.length > 0 && sourceUrl.trim() (line 393)
    ? handleGenerate() sends SINGLE API call (lines 180-189):

`
POST /api/customer/review-engine/jobs
{
    source_url: sourceUrl,
    objective: objective,
    target_personas: selectedPersonas,  ? Personas selected BEFORE validation
    input_mode: inputMode,
    publish_to_tiktok: publishToTiktok
}
`

**Key Problems:**
- Line 34: initialPersonaIds?: string[] prop enables pre-selection
- Line 76: Destructured in function parameter
- Line 85: selectedPersonas state initialized to empty
- Lines 117-123: On mount, if initialPersonaIds provided, use them (overrides user choice)
- Lines 471-624: Full persona grid visible on initial render with all personas (8 default selected if none provided)
- Line 393: Button requires selectedPersonas.length > 0 (forces persona selection BEFORE URL submit)
- Line 185: 	arget_personas: selectedPersonas sent in request with URL

## Correct Flow (FROM DOCUMENTATION)

### Architecture: VIDEO_CREATION_V2_ARCHITECTURE.md Lines 89-105

PHASE 1: PLANNING (new flow)
- User provides objective
- User provides target URL
- WebsiteReviewService analyzes URL          ? URL VALIDATED HERE
- User selects persona                        ? PERSONA SELECTED AFTER validation
- User selects execution_mode
- User confirms plan

## Backend Correctly Enforces Sequence

### video_ai.py _missing_step() Method (Lines 417-495)

The method is a state machine that determines what should be asked next:

SEQUENTIAL ENFORCEMENT:
1. if not objective: return  collect_objective
2. if not target_url: return collect_target_url
3. if not page_review: return website_review           ? URL VALIDATION
4. if not persona_id: return pick_persona              ? AFTER #3
5. if not execution_mode: return choose_execution_mode

This proves the backend expects this sequence. Frontend violates it by pre-selecting personas before step #3 completes.

## Code-Level Evidence

### LiveFeedTab.tsx (D:\coding\AI-Influencer-TripC\Project\components\dashboard\LiveFeedTab.tsx)

| Line(s) | Problem | Details |
|---------|---------|---------|
| 34 | initialPersonaIds prop exists | Enables passing pre-selected persona IDs from parent |
| 76 | Parameter destructured | initialPersonaIds = [] in function signature |
| 85 | State initialized empty | const [selectedPersonas, setSelectedPersonas] = useState<string[]>([]) |
| 117-123 | useEffect bypasses user choice | If initialPersonaIds provided, immediately sets selectedPersonas to those values without user interaction |
| 393 | Button disabled without personas | disabled={... selectedPersonas.length === 0 ...} forces persona selection |
| 471-624 | Persona grid always visible | Full persona selection grid rendered on page load, NOT conditionally shown after URL validation |
| 185 | Sent with URL in one call | target_personas: selectedPersonas included in POST request body with source_url |

## Conclusion

The user's observation is **CORRECT**. 

Personas should NOT be sent pre-selected with the URL. The issue is entirely in the frontend component (LiveFeedTab.tsx) which:

1. Accepts initialPersonaIds prop that pre-selects personas
2. Displays persona grid on page load before URL validation
3. Sends both URL and personas in a single API call

The backend skills already expect and enforce the correct sequence: URL validation BEFORE persona selection. The frontend needs to be fixed to match this expected behavior by implementing a modal-based persona selection step that only appears after URL validation succeeds.
