# Diagnostic Guide - Approve Plans Error

## Changes Made

Added `console.error()` logging to capture actual API errors instead of silently swallowing them.

**Files modified:**
- `CreateVideoTab.tsx` line 605, 658, 637

---

## How to Diagnose

### Step 1: Open Browser Console
```
Press: F12 (or Ctrl+Shift+I)
Go to: Console tab
```

### Step 2: Reproduce Error
1. Go to Create Video → Step 2 (Review Plan)
2. Click "Approve all" or "Approve and Continue"
3. Watch for error message and **check console**

### Step 3: Look for These Error Patterns

#### Pattern A: 401 Unauthorized (Authentication Failed)
```
[Approve Plan] Failed for PersonaName (planId-xxx):
Error: Unauthorized - ??
```
**Cause:** User not authenticated or session expired  
**Fix:** Re-login

---

#### Pattern B: 403 Forbidden (Permission Denied)
```
[Approve Plan] Failed for PersonaName (planId-xxx):
Error: Forbidden - User does not have permission to approve plans
```
**Cause:** User account doesn't have approve permission  
**Fix:** Check user role/permissions

---

#### Pattern C: 404 Not Found (Plan ID Invalid)
```
[Approve Plan] Failed for PersonaName (planId-xxx):
Error: Not Found - Plan planId-xxx does not exist
```
**Cause:** Plan ID is wrong or was deleted  
**Fix:** Regenerate plans from Step 1

---

#### Pattern D: 500 Server Error (Backend Issue)
```
[Approve Plan] Failed for PersonaName (planId-xxx):
Error: Internal Server Error - ...
```
**Cause:** Backend service error  
**Fix:** Backend team needs to investigate

---

#### Pattern E: Network/Timeout Error
```
[Approve Plan] Failed for PersonaName (planId-xxx):
Error: NetworkError when attempting to fetch resource.
```
**Cause:** Network disconnection or API timeout  
**Fix:** Check network, retry

---

#### Pattern F: 422 Validation Error (Plan Invalid)
```
[Approve Plan] Failed for PersonaName (planId-xxx):
Error: Unprocessable Entity - Plan must have approved status first
```
**Cause:** Plan state not ready for approval  
**Fix:** Need to check plan status first

---

## Expected Normal Logs (Success Case)

```
// When approval succeeds:
toast.success("Approved 5 persona plans and moved to Step 3.")

// When some fail:
[Approve Plan] Failed for PersonaA (plan-123): Error: 403 Forbidden
[Approve Plan] Failed for PersonaB (plan-456): Error: 403 Forbidden
[goToStep3] Approval process error: Error: All 5 plans failed to approve...
toast.error("Could not approve the selected persona plans: All 5 plans failed...")
```

---

## What to Report

When error occurs, copy and share:

```
1. Full error message from console (starting with [Approve Plan])
2. HTTP status code (if visible)
3. Full error details
4. Number of plans being approved
5. Were plans just generated or reviewed?
```

**Example:**
```
[Approve Plan] Failed for Alex (plan-7c4e9a2b):
Error: 403 Forbidden - User account 'user@example.com' is not authorized 
to approve plans. Contact administrator.

Happening for: All 3 plans
Plan age: Just generated
```

---

## Common Root Causes (in order of likelihood)

1. **Authentication expired** (401) → Need to re-login
2. **Permission issue** (403) → User doesn't have approve permission  
3. **Plan state invalid** (422) → Plans in wrong status
4. **Network timeout** → Check connection
5. **Backend error** (500) → Server issue

---

## Next Steps

1. **Test now** and check console
2. **Report console error** from Pattern A-F above
3. Then we can trace deeper based on which error pattern you see

