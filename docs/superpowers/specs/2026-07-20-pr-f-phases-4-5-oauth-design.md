# PR-F Phases 4-5: Google Docs OAuth Integration Design

**Date:** 2026-07-20  
**Author:** Jorge Alcoforado  
**Status:** Approved for Implementation  
**Scope:** OAuth flow + inline credential connection UI for PR-F (Google Docs integration)

---

## 1. Overview

**Goal:** Enable users to connect their Google Docs account and seamlessly create documents via Google Docs directly from the minuta creation dialog.

**Phases 1-3 Status:** ✅ Complete
- Backend service (GoogleDocsService)
- Database schema (GoogleCredencial)
- API endpoints for CRUD
- Frontend dialog with platform selection

**Phases 4-5 Status:** ❌ Missing (this design)
- OAuth authorization flow (Phase 4)
- Credentials UI (Phase 5)

**User Flow:**
1. User clicks "Google Docs" in RedigirDocumentoDialog
2. If no credentials → radio disabled + "Conectar agora" link
3. Click link → GoogleConnectDialog modal
4. Click "Conectar Conta Google" → redirects to Google consent screen
5. User authorizes → backend receives callback
6. Backend exchanges code → auto-creates Google Doc
7. User redirected to Google Docs editor ✅

---

## 2. Design Decisions

### 2.1 UX Flow: Inline + Blocking

**Decision:** Radio button "Google Docs" is disabled if no credentials; inline helper text + "Conectar agora" link opens modal.

**Rationale:**
- Prevents user from selecting unavailable option
- Clear visual feedback (disabled state)
- Fast path: no extra navigation required
- Modal is contained, returns focus to original dialog

**Alternative considered:** Settings page redirect (rejected — too many clicks)

### 2.2 OAuth Redirect Behavior: Auto-Create + Auto-Redirect

**Decision:** After successful callback, backend auto-creates Google Doc and redirects to editor.

**Rationale:**
- Seamless UX — user doesn't need to click "Criar" again
- Reduces friction (1 flow, not 2 steps)
- Aligns with user intent (clicked "Conectar" → expects document)

**Alternative considered:** Just save credentials, return to dialog (rejected — extra click)

### 2.3 State Protection: Redis with TTL

**Decision:** State parameter stored in Redis with 5-minute TTL.

**Rationale:**
- CSRF protection without session cookies (stateless design)
- Auto-cleanup via TTL (no manual cleanup)
- Redis already in stack (docker-compose.yml)
- Fast lookups

**Alternative considered:** 
- JWT state (rejected — more complex, harder to invalidate)
- Session cookies (rejected — session management needed)

### 2.4 Error Handling: Detailed Messages

**Decision:** Different error messages for different failure scenarios.

**Errors covered:**
- User rejection: "Você rejeitou o acesso ao Google Docs. Tente novamente."
- State expired: "Sessão expirou. Tente conectar novamente."
- Invalid code: "Google negou o acesso. Tente novamente."
- API error: "Erro ao conectar. Tente novamente."

**Rationale:** Users understand what went wrong; can retry appropriately

---

## 3. Architecture

### 3.1 Component Hierarchy

```
RedigirDocumentoDialog
├─ Credential status query (GET /users/me/google-credential)
├─ Radio button selection
│  └─ If Google + no credentials → show helper text + "Conectar agora" link
├─ GoogleConnectDialog (modal)
│  └─ "Conectar Conta Google" button → window.location.href = /auth/google
└─ On success → auto-creates doc → redirects to Google Docs editor
```

### 3.2 Backend OAuth Service

**GoogleOAuthFlow** (`backend/app/services/google_oauth_flow.py`)

Methods:
- `generate_oauth_url(user_id, tenant_id, minuta_id)` → URL + state in Redis
- `handle_callback(code, state)` → validates state + exchanges code + saves credential

Dependencies:
- `google-auth-oauthlib.flow.Flow` — OAuth2 library
- Redis client — state storage
- SQLAlchemy — credential persistence
- `app.core.crypto.encrypt` — token encryption

### 3.3 Backend Routers

**auth.py** — OAuth endpoints

Endpoints:
- `GET /auth/google?minuta_id=X&processo_id=Y` — initiate flow
- `GET /auth/google/callback?code=CODE&state=STATE` — handle callback

Both endpoints enforce `require_permission("processo", "atualizar")` + `require_tenant_id`.

### 3.4 Frontend Components

**GoogleConnectDialog** — Modal for connecting account
- Props: `open`, `onClose`, `minutaId`, `processoId`, `onSuccess`
- Renders: explanation text + "Conectar Conta Google" button
- On click: redirects to `/api/v2/auth/google?minuta_id=X`

**RedigirDocumentoDialog** — Modified to integrate
- Query: `credentialQ` (GET /users/me/google-credential)
- Show/hide "Conectar agora" link based on credential status
- Disable radio button if no credentials
- Open GoogleConnectDialog when clicked

### 3.5 Error Handling Page

**minuta-error.tsx** — Error page after OAuth failure

Displays:
- Error message (specific to error type)
- 3-second countdown
- Auto-redirects to /processos

Parameters: `?error=access_denied|state_expired|google_api_error|invalid_state`

---

## 4. Data Flow

### 4.1 Happy Path

```
1. User selects "Google Docs" + no credentials
   RedigirDocumentoDialog.credentialQ → GET /users/me/google-credential (404)
   
2. User clicks "Conectar agora" link
   setShowGoogleConnect(true)
   
3. GoogleConnectDialog renders
   User clicks "Conectar Conta Google"
   
4. window.location.href = `/api/v2/auth/google?minuta_id=123&processo_id=456`
   
5. Backend GET /auth/google
   ├─ Verify authorization + tenant
   ├─ Generate state UUID
   ├─ Store in Redis: oauth_state:{state} → JSON(user_id, tenant_id, minuta_id) (TTL 5min)
   └─ Build Google OAuth URL
   └─ RedirectResponse to Google consent screen
   
6. Google consent screen (browser)
   User authorizes → Google redirects to callback
   
7. Backend GET /auth/google/callback?code=AUTH_CODE&state=STATE
   ├─ Retrieve context from Redis using state
   ├─ Validate state exists (if expired → error)
   ├─ Exchange authorization_code → access_token + refresh_token
   ├─ Encrypt tokens + save GoogleCredencial
   ├─ Auto-call criar_google_doc_para_minuta()
   ├─ Get minuta with google_doc_url
   └─ RedirectResponse to Google Docs editor
   
8. Google Docs editor opens in user's browser ✅
```

### 4.2 Error Paths

| Error | Cause | User Message | Result |
|-------|-------|--------------|--------|
| `access_denied` | User rejected consent | "Você rejeitou o acesso..." | Redirect to /minuta-error, auto-back to /processos |
| `state_expired` | Redis TTL expired | "Sessão expirou..." | Same as above |
| `invalid_code` | Code invalid/expired | "Google negou o acesso..." | Same as above |
| `google_api_error` | Network/API error | "Erro ao conectar..." | Same as above |

### 4.3 Database Changes

**GoogleCredencial table** (already exists, no migration needed)
- Insert on successful callback: `INSERT INTO google_credencial (...)`
- Revoke old credentials if user connects again: `UPDATE google_credencial SET revogado=true WHERE ...`

**No schema changes required.**

---

## 5. API Contracts

### 5.1 Backend Endpoints

#### GET /auth/google
```
Query params:
  minuta_id: int (required)
  processo_id: int (required)

Headers:
  Authorization: Bearer {token}

Returns:
  307 Redirect
  Location: https://accounts.google.com/o/oauth2/v2/auth?...&state=UUID

Side effects:
  - Generate state UUID
  - Save to Redis: oauth_state:{state} (TTL 5min)
  - Redirect to Google consent screen
```

#### GET /auth/google/callback
```
Query params:
  code: str (authorization code from Google)
  state: str (state parameter for CSRF protection)
  error: str (optional, if user rejected: "access_denied")

Returns:
  307 Redirect
  Location: https://docs.google.com/document/d/{google_doc_id}/edit

Side effects on success:
  - Validate state from Redis
  - Exchange code → tokens
  - Encrypt + save GoogleCredencial
  - Auto-create Google Doc
  - Delete state from Redis

Side effects on error:
  - Delete state from Redis
  - Redirect to /minuta-error?error={error_type}
```

#### GET /users/me/google-credential (new endpoint)
```
Headers:
  Authorization: Bearer {token}

Returns 200:
  {
    "connected": true,
    "email": "user@gmail.com" (optional),
    "connected_at": "2026-07-20T14:30:00Z"
  }

Returns 404:
  (user has no connected credentials)
```

### 5.2 Frontend API Calls

```typescript
// Initiate OAuth
window.location.href = "/api/v2/auth/google?minuta_id=123&processo_id=456"

// Check credential status
GET /api/v2/users/me/google-credential

// Revoke credential (Phase 5, not in MVP)
DELETE /api/v2/users/me/google-credential
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

**Backend** (`backend/tests/test_google_oauth_flow.py`):
- Generate OAuth URL + state saved to Redis
- Exchange authorization_code → credential saved
- State expired scenario
- Invalid code scenario
- Google API error scenario

Count: ~5 tests

**Frontend** (`frontend/__tests__/GoogleConnectDialog.test.tsx`):
- Component renders
- Button click redirects to OAuth endpoint
- Error message displays

Count: ~3 tests

### 6.2 Integration Tests

**Backend** (`backend/tests/test_auth_routers.py`):
- GET /auth/google redirects to Google
- GET /auth/google/callback exchanges code + auto-creates doc
- Error handling (state mismatch, invalid code)

Count: ~4 tests

### 6.3 E2E Tests

**Frontend** (`frontend/tests-e2e/specs/google-docs-oauth.spec.ts`):
- Full flow: login → open dialog → click connect → verify Google editor

Manual testing acceptable for MVP (real Google OAuth involved).

### 6.4 Test Coverage

- GoogleOAuthFlow service: 100% (5 tests)
- OAuth routers: 80% (4 tests, some edge cases manual)
- GoogleConnectDialog: 80% (3 tests)
- RedigirDocumentoDialog integration: 70% (2 tests)
- E2E: 1 manual test (Google OAuth)

---

## 7. Implementation Sequence

### Phase A: Backend Foundation

1. `backend/app/services/google_oauth_flow.py` — OAuth service (120 lines)
2. `backend/app/routers/auth.py` — OAuth routers (60 lines)
3. `backend/tests/test_google_oauth_flow.py` — Service tests (120 lines)
4. `backend/tests/test_auth_routers.py` — Router tests (80 lines)

### Phase B: Frontend (depends on Phase A complete)

5. `frontend/components/GoogleConnectDialog.tsx` — Modal component (80 lines)
6. `frontend/app/(app)/minuta-error.tsx` — Error page (40 lines)
7. `frontend/lib/api.ts` — Add `users.getGoogleCredential()` (20 lines)
8. `frontend/components/RedigirDocumentoDialog.tsx` — Integrate credential check (50 lines modified)

### Phase C: Testing

9. `frontend/__tests__/GoogleConnectDialog.test.tsx` — Component tests (60 lines)
10. `frontend/tests-e2e/specs/google-docs-oauth.spec.ts` — E2E test (80 lines)

### Phase D: Documentation

11. This design doc (saved)

**Total effort:** ~6-8 hours for MVP  
**Critical path:** Phases A → B (sequential dependency)

---

## 8. Configuration Required

### 8.1 Environment Variables

Add to `.env`:
```bash
GOOGLE_OAUTH_CLIENT_ID=<app>.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=<secret>
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/v2/auth/google/callback
GOOGLE_CREDENTIALS_FILE=/app/keys/google-credentials.json
```

### 8.2 Google Cloud Setup (manual, out of scope)

1. Create OAuth 2.0 credentials in Google Cloud Console
2. Set authorized redirect URI: `http://localhost:8000/api/v2/auth/google/callback`
3. For production: update to `https://aprimora.tld/api/v2/auth/google/callback`
4. Download credentials JSON → save to `/app/keys/google-credentials.json`

---

## 9. Out of Scope (Phase 5+ future work)

- Credential revocation UI in settings
- Credential status display in user profile
- Token refresh retry logic + background job
- Multiple credentials per user
- DOCX ↔ HTML sync (currently placeholder)
- Audit logging for OAuth connections

---

## 10. Success Criteria

✅ **MVP Complete When:**
1. User can click "Conectar Conta Google" in RedigirDocumentoDialog
2. Redirected to Google consent screen (real Google OAuth)
3. User authorizes → backend receives callback + exchanges code
4. GoogleCredencial saved to database
5. Google Doc auto-created → user redirected to editor
6. User can edit in Google Docs
7. When done, can finalize → PDF attachment works

✅ **Testing Complete When:**
- All unit tests pass (11 tests)
- All integration tests pass (4 tests)
- E2E test runs successfully (manual OK for MVP)
- No console errors in browser

---

## 11. Dependencies & Prerequisites

### Backend
- `google-auth-oauthlib` library (already in requirements.txt?)
- Redis running (docker-compose.yml)
- PostgreSQL running (docker-compose.yml)
- Google Cloud OAuth credentials configured

### Frontend
- React Query (already in package.json)
- Existing UI components (Button, Dialog, etc.)

### Infrastructure
- Docker Compose with Redis + PostgreSQL
- nginx reverse proxy (for CORS if needed)

---

## 12. Rollback Plan

If OAuth integration breaks production:

1. Disable "Google Docs" radio option in RedigirDocumentoDialog (conditional render)
2. Revert backend routers/service
3. Keep GoogleCredencial table (data is safe)
4. Users can still use "Plataforma" (interno) to create documents

No database rollback needed (no schema changes).

---

## Appendix A: File Changes Summary

| File | Type | Lines | Change |
|------|------|-------|--------|
| backend/app/services/google_oauth_flow.py | NEW | 120 | OAuth service |
| backend/app/routers/auth.py | NEW | 60 | OAuth endpoints |
| backend/tests/test_google_oauth_flow.py | NEW | 120 | Service tests |
| backend/tests/test_auth_routers.py | NEW | 80 | Router tests |
| frontend/components/GoogleConnectDialog.tsx | NEW | 80 | Connect modal |
| frontend/app/(app)/minuta-error.tsx | NEW | 40 | Error page |
| frontend/components/RedigirDocumentoDialog.tsx | MODIFY | +50 | Add credential check |
| frontend/lib/api.ts | MODIFY | +20 | Add credential endpoint |
| frontend/__tests__/GoogleConnectDialog.test.tsx | NEW | 60 | Component tests |
| frontend/tests-e2e/specs/google-docs-oauth.spec.ts | NEW | 80 | E2E test |
| **TOTAL** | — | **~530** | — |

---

## Sign-Off

**Design approved by:** Jorge Alcoforado  
**Date:** 2026-07-20  
**Ready for implementation:** ✅ Yes

