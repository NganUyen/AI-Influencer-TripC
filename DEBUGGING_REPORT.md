# Create Video Pipeline - Systematic Debugging Report
**Date:** 2026-04-20  
**Focus:** Step 2 (Review Plan) → Step 3 (Render) → Output  
**Method:** Phase 1 - Root Cause Investigation

---

## Executive Summary

Pipeline architecture has **10 critical issues** spanning data synchronization, error handling, performance bottlenecks, and state management. None are simple typos—all are architectural patterns that can silently fail in production.

---

## CRITICAL ISSUES (High Impact)

### 🔴 ISSUE #1: Sequential Plan Approval Bottleneck
**Location:** `CreateVideoTab.tsx:558-568` in `goToStep3()`  
**Severity:** HIGH (Performance)

```typescript
// CURRENT (Sequential - N seconds delay)
for (const card of approvedCards) {
  try {
    await customerApiRequest(`/api/customer/review-engine/plans/${card.planId}/approve`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
    approvedPlanIds.push(String(card.planId || '').trim());
  } catch (error) {
    failedApprovals.push(card.personaName);
  }
}
```

**Problem:**
- If user selects 5 personas, each taking 1s to approve = **5 seconds total**
- Sequential execution blocks transition to Step 3
- No progress indication to user during approval loop
- Any network blip fails the entire batch

**Root Cause:** Loop structure waits for each `await` before starting next one

**Evidence:**
- No Promise.all() or parallel execution
- All approvals must complete before `refreshJobs()` call
- User sees frozen UI with "Approve and Continue →" button disabled

---

### 🔴 ISSUE #2: Race Condition in Plan State Sync
**Location:** `CreateVideoTab.tsx:416-457` (activeJobs memo + useEffect)  
**Severity:** HIGH (Data Corruption Risk)

**Flow:**
```
goToStep3() called
↓
setActivePlanIds(nextPlanIds) - State update queued
↓
refreshJobs() - Fetches jobs from backend
↓
activeJobs memo re-evaluates - Filters by NEW activePlanIds
↓
useEffect triggers - Builds planCards from activeJobs
↓
BUT: If refreshJobs() returns BEFORE state updates complete,
      activeJobs memo still has OLD activePlanIds
      → planCards built with stale data
      → UI shows wrong persona plans
```

**Root Cause:** Multiple state setters + memos race condition
- `setActivePlanIds()` is async state update
- `refreshJobs()` promise resolves independently
- `activeJobs` memo uses `activePlanIds` without synchronization guarantee

**Evidence in code:**
```typescript
// Line 574: Sets activePlanIds
setActivePlanIds(nextPlanIds);

// Line 575: Immediately calls refreshJobs - may resolve before state updated
const nextJobs = await refreshJobs();

// Line 576-578: Assumes activePlanIds are updated, but might not be
const refreshedActiveJobs = nextJobs.filter((job) =>
  nextPlanIds.includes(String(job.plan_id || '').trim()),
);
```

**Actual risk:**
- User approves 5 plans, system shows 3 in Step 3 → renders incomplete content
- User might re-approve same plans thinking they didn't take

---

### 🔴 ISSUE #3: Silent Partial Failures in Plan Approval
**Location:** `CreateVideoTab.tsx:555-587` in `goToStep3()`  
**Severity:** HIGH (Silent Data Loss)

```typescript
// If 3 of 5 approvals fail:
if (nextPlanIds.length === 0) {
  throw new Error('No approved plans could continue to production.');
}
// But if 2 succeed, it continues silently!
// User thinks all 5 were approved, only 2 continue
```

**Problem:**
- Loop catches individual errors but continues
- Only fails if ALL approvals fail
- If 4/5 succeed: User sees "Approved 4 plans" but doesn't know which 1 failed
- failedApprovals list shown in toast but dismissed quickly

**Evidence:**
```typescript
failedApprovals.push(card.personaName);  // Caught in loop
// ... later ...
if (failedApprovals.length > 0) {
  toast.error(`Some persona plans stayed on Step 2: ${failedApprovals.join(', ')}.`);
  // This toast appears AFTER "Approved X plans" toast
  // User already moved to Step 3, doesn't see the error
}
```

**Root Cause:**
- `for` loop continues on error instead of collecting all results first
- Should use `Promise.allSettled()` to wait for all, then report results together
- Error visibility is poor (toast order issue)

---

### 🔴 ISSUE #4: Missing Refresh After Plan Save
**Location:** `CreateVideoTab.tsx:523-540` in `savePlanEdits()`  
**Severity:** HIGH (Data Sync)

```typescript
const savePlanEdits = useCallback(async () => {
  // ...
  try {
    await persistPlanCards(planCards);
    setSharedContractDirty(false);
    await refreshJobs();  // ← Refreshes backend jobs
    // ...
  }
```

**But persistPlanCards doesn't return updated planIds:**

```typescript
const persistPlanCards = useCallback(async (cards: PersonaPlanCardViewModel[]) => {
  const editableCards = cards.filter((card) => card.planId);
  // ...
  await Promise.all(
    editableCards.map((card) =>
      customerApiRequest(`/api/customer/review-engine/plans/${card.planId}`, {
        method: 'PATCH',
        body: JSON.stringify({...})
      }),
    ),
  );
  // No return value!
  // No validation that all saves succeeded!
}, [setupState, sharedContractDraft]);
```

**Problem:**
- PATCH requests fire in parallel (good)
- But if 3 of 5 succeed and 2 fail, method completes without error
- `refreshJobs()` called anyway - frontend thinks all saved
- `setSharedContractDirty(false)` set before knowing if save actually worked
- If user edits again quickly, state is inconsistent

**Evidence:**
- No error handling in `Promise.all()` in persistPlanCards
- No return/verification of which plans were actually persisted
- Calling code assumes success because no exception thrown

---

### 🔴 ISSUE #5: Stale Shared Contract on State Transition
**Location:** `CreateVideoTab.tsx:726-732` state sync  
**Severity:** MEDIUM-HIGH (Content Risk)

**Scenario:**
1. User is on Step 2, loads shared contract: "Script A | Scene A"
2. User edits: "Script B | Scene B" → `sharedContractDirty = true`
3. User clicks "Approve and Continue"
4. `goToStep3()` calls `persistPlanCards()` to save edits
5. If save partially fails (2/3 plans saved):
   - System calls `refreshJobs()`
   - Jobs return with MIXED data (some have Script B, some have Script A)
   - `buildSharedContractDraft()` takes FIRST job's script
   - Step 3 shows Script A if first job didn't get saved, or Script B if it did
   - **User doesn't know state is inconsistent**

**Root Cause:**
- No transaction semantics for multi-plan saves
- No verification that all plans got same script before moving forward
- `refreshJobs()` used to "verify" but it just returns whatever backend has

---

## PERFORMANCE BOTTLENECKS

### 🟠 ISSUE #6: Fixed 5-Second Polling Without Backoff
**Location:** `CreateVideoTab.tsx:464-472`  
**Severity:** MEDIUM (Resource/UX)

```typescript
useEffect(() => {
  if (activePlanIds.length === 0 || currentStep < 3) {
    return;
  }
  void refreshJobs(true).catch(() => undefined);  // Silent failure
  const interval = window.setInterval(() => {
    void refreshJobs(true).catch(() => undefined);  // Every 5s, forever
  }, 5000);
  return () => window.clearInterval(interval);
}, [activePlanIds, currentStep, refreshJobs]);
```

**Problems:**
- Polls every 5 seconds with NO adaptive backoff
- If render takes 2 minutes, that's 24 requests, most returning "still rendering"
- If backend is slow, keeps hammering it
- On Step 4 (publish), same polling continues
- No exponential backoff or early exit when jobs complete

---

### 🟠 ISSUE #7: Blocking Upload Handler Pattern
**Location:** `CreateVideoTab.tsx:636-665`  
**Severity:** MEDIUM (UX)

```typescript
const handleUploadPlanVideo = useCallback(async (planId: string, file: File | null) => {
  if (!file) return;
  // ...
  setUploadingPlanIds((current) => [...current, planId]);
  try {
    const updatedJob = await customerApiRequest(
      `/api/customer/review-engine/jobs/${planId}/upload`,
      {
        method: 'POST',
        headers: { 'Content-Type': file.type || 'video/mp4' },
        body: file,  // Raw file upload
      },
    );
    // ...
  }
}, [onRefresh]);
```

**Problems:**
- Large video files block UI during upload
- No progress tracking (0% → 100%)
- No cancel/retry mechanism
- `uploadingPlanIds` array grows if user retries failed upload
  - First upload fails at 60%, user clicks upload again
  - `uploadingPlanIds` now has same planId twice
  - First one never gets removed from array (caught error, button shows "Uploading" forever)

---

## DATA FLOW & SYNC ISSUES

### 🟠 ISSUE #8: Job Key Ambiguity in Merge Logic
**Location:** `CreateVideoTab.tsx:46-68`  
**Severity:** MEDIUM (Data Loss Risk)

```typescript
function jobKey(job: ReviewEngineJob): string {
  return String(job.plan_id || job.job_id);  // ← Fallback chain!
}

function mergeJobs(existing: ReviewEngineJob[], incoming: ReviewEngineJob[]): ReviewEngineJob[] {
  const merged = new Map<string, ReviewEngineJob>();
  existing.forEach((job) => merged.set(jobKey(job), job));
  incoming.forEach((job) => merged.set(jobKey(job), job));  // ← Overwrites!
  return sortJobs(Array.from(merged.values()));
}
```

**Problem:**
- If a job has both `plan_id` and `job_id`, map key is `plan_id`
- If same job returned by backend but only with `job_id` (plan_id became null), it's treated as NEW
- Or, if two different jobs have same fallback ID, one silently overwrites the other
- Example:
  ```
  Job 1: plan_id='P123', job_id='J1'  → key='P123'
  Job 2: plan_id='P123', job_id='J2'  → key='P123'  (different job!)
  After merge: Only Job 2 exists, Job 1 lost
  ```

---

### 🟠 ISSUE #9: Missing Upload Status Tracking
**Location:** `CreateVideoReviewStep.tsx:144-147`  
**Severity:** MEDIUM (UX Confusion)

```typescript
const missingUploadCount = approvedCards.filter(
  (card) => card.requiresUpload && !card.outputReady,
).length;
const canContinue = approvedCount > 0 && missingUploadCount === 0;
```

**Problem:**
- Button disabled if ANY upload is pending
- But no visibility into WHICH uploads are pending
- If user uploads 3 videos for 3 approved plans, button still disabled
- User doesn't know:
  - Are 2 uploads stuck/failed?
  - Is 1 upload still in progress?
  - Did all uploads succeed but outputReady hasn't updated?
- No timestamp of last successful upload per plan

---

### 🟠 ISSUE #10: Implicit Shared Contract Sync Assumption
**Location:** `CreateVideoTab.tsx:126-136`  
**Severity:** MEDIUM (Logic Risk)

```typescript
function syncPlanCardsWithSharedDraft(
  cards: PersonaPlanCardViewModel[],
  draft: SharedContractDraft,
): PersonaPlanCardViewModel[] {
  const scenes = parseScenesFromEditor(draft.scenesText);
  return cards.map((card) => ({
    ...card,
    scriptPreview: draft.scriptText.trim() || card.scriptPreview,
    scenes: scenes.length > 0 ? scenes : card.scenes,
  }));
}
```

**Problem:**
- Called when user edits shared contract or when review contract resets
- Updates ONLY local planCards state, NOT backend yet
- If user edits scenes text to invalid format, `parseScenes()` might return empty array
  - `scenes.length > 0` is false
  - Falls back to `card.scenes` (old data)
  - User thinks new scenes saved, but they're the old ones
- No validation that parsed scenes are sensible

---

## VALIDATION & ERROR HANDLING GAPS

### 🟡 ISSUE #11: No Validation on Plan Deletion
**Location:** `CreateVideoTab.tsx:598-634`  
**Severity:** MEDIUM-LOW (Data Loss Prevention)

```typescript
const deleteReviewPlans = useCallback(async (planIds: string[]) => {
  const uniquePlanIds = Array.from(new Set(planIds.map(planId => planId.trim()).filter(Boolean)));
  if (uniquePlanIds.length === 0) {
    throw new Error('No plans were selected for deletion.');
  }

  // No confirmation of what plans are being deleted
  // No check if user has unsaved edits
  for (const planId of uniquePlanIds) {
    try {
      await customerApiRequest(`/api/customer/review-engine/plans/${planId}`, {
        method: 'DELETE',
      });
    } catch (error) {
      failures.push(planId);
    }
  }
```

**Problem:**
- If user edited shared contract but didn't save, clicking "Reject all" deletes everything
- No warning: "You have unsaved edits. Delete anyway?"
- Modal shows plan IDs in delete confirmation, but user can't see which PERSONAS those IDs represent
- If deletion of 1/3 plans fails, user doesn't know which one

---

## SUMMARY TABLE

| # | Issue | Location | Severity | Type | Impact |
|---|-------|----------|----------|------|--------|
| 1 | Sequential approval loop | goToStep3() | 🔴 HIGH | Performance | 5+ second delay per batch |
| 2 | Race condition in state sync | activeJobs memo | 🔴 HIGH | Data Sync | Wrong personas rendered |
| 3 | Silent partial approval failure | goToStep3() error handling | 🔴 HIGH | Error Handling | Missing plans continue |
| 4 | Save without verification | persistPlanCards() | 🔴 HIGH | Data Verification | Failed saves not detected |
| 5 | Stale shared contract on transition | State management | 🔴 HIGH | Content Risk | Inconsistent script/scenes |
| 6 | Fixed 5s polling | refreshJobs loop | 🟠 MEDIUM | Performance | 24+ requests for 2min render |
| 7 | No upload progress | handleUploadPlanVideo() | 🟠 MEDIUM | UX | Blocking large file uploads |
| 8 | Job key ambiguity | mergeJobs() | 🟠 MEDIUM | Data Loss | Jobs silently overwritten |
| 9 | Missing upload status details | canContinue logic | 🟠 MEDIUM | UX | User confusion on blocks |
| 10 | Invalid scene parsing fallback | syncPlanCardsWithSharedDraft() | 🟠 MEDIUM | Logic | Old data silently used |
| 11 | No delete confirmation context | deleteReviewPlans() | 🟡 MEDIUM-LOW | Safety | No unsaved edit warning |

---

## ROOT CAUSE PATTERNS

### Pattern 1: Async State + Effect Racing
Issues #2 affects multiple components. React state updates batch, but awaited promises resolve independently, creating windows where stale closures are captured.

### Pattern 2: Catch-and-Continue Loop
Issues #3, #4, #11 collect errors inside loops then silently continue. Should collect all results first with `Promise.allSettled()`, then decide on failure/retry.

### Pattern 3: Assumption of Atomic Operations
Issues #4, #5 assume PATCH/DELETE succeed silently. No transactional guarantee across multiple resources.

### Pattern 4: Polling Without Lifecycle
Issue #6 polls indefinitely. Should include: max retries, backoff, early exit on completion.

### Pattern 5: Implicit Data State
Issues #8, #10 rely on implicit assumptions about data shape. Missing explicit validation.

---

## NEXT STEPS (Phase 2-4 Investigation)

These require code patterns from working similar flows:
1. Compare with other multi-step async flows in codebase
2. Check if Redux/Context has transactional patterns
3. Review backend API contract for atomicity guarantees

**Recommendation:** Do NOT fix individually. These are architectural patterns. Fix one reveals the others are still broken elsewhere.
