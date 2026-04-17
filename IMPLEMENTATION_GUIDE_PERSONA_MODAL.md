# Implementation Guide: Fix Persona Selection Modal Flow

**Objective:** Refactor LiveFeedTab.tsx to move persona selection to AFTER URL validation, shown in a modal dialog.

## Current Problem

Frontend sends URL + personas together in one call, violating architecture that requires:
1. User enters URL
2. URL validated (shows analysis)
3. Modal appears for persona selection (AFTER seeing validation results)
4. User selects personas in modal
5. Create jobs with URL + selected personas

## Solution Overview

### Step 1: Remove initialPersonaIds Prop

**Current Code (LiveFeedTab.tsx line 34):**
Remove the initialPersonaIds?: string[] prop from LiveFeedTabProps interface.

Also Remove:
- Line 76: initialPersonaIds = [] from destructuring
- Lines 117-123: The entire useEffect that initializes from initialPersonaIds

### Step 2: Keep URL Validation Logic (Already Works)

Lines 145-165: handleValidate() is CORRECT. The function validates URL and shows results in right panel.

Change: Add setShowPersonaModal(true) after successful validation

### Step 3: Add Modal State

Add to state initialization (around line 85-93):
const [showPersonaModal, setShowPersonaModal] = useState(false);
const [modalPersonaIds, setModalPersonaIds] = useState<string[]>([]);

### Step 4: Make Persona Grid Conditional

Currently (Lines 471-624): Always visible

Change: Wrap in condition to only show after URL validation:
if (validationResult) { show persona grid }

### Step 5: Create Modal Component

New file: PersonaSelectionModal.tsx in components/dashboard/

This component should:
- Show when isOpen is true
- Display validation results (page title, detected features)
- Show persona grid with checkboxes
- Have Confirm/Cancel buttons
- Track local selection state
- Call onConfirm with selected IDs

### Step 6: Update LiveFeedTab to Use Modal

Update handleValidate to show modal:
setShowPersonaModal(true) after validation succeeds

Update handleGenerate:
Personas already selected in state from modal
Just send URL + selectedPersonas to backend

Replace persona grid section with conditional that shows modal after validation

## Testing Checklist

- [ ] Remove initialPersonaIds prop and verify LiveFeedTab still renders
- [ ] Enter URL, click Validate URL, modal should appear
- [ ] Modal shows validation results and persona grid
- [ ] Can select/deselect personas in modal
- [ ] Confirm button disabled if no personas selected
- [ ] Confirm button sends correct data to backend
- [ ] Cancel button closes modal without changing selection
- [ ] Backend receives correct payload with URL + personas
- [ ] Jobs are created successfully with selected personas

## Related Files Already Correct

These files do not need changes:
- video_ai.py - Already enforces correct sequence
- video_planner.py - Already enforces correct sequence
- customer.py API - Already designed correctly
- VIDEO_CREATION_V2_ARCHITECTURE.md - Correctly documents intended flow
