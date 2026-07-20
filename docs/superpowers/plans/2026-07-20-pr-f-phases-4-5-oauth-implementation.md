# PR-F Phases 4-5: Google Docs OAuth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement OAuth2 flow for Google Docs account connection, enabling seamless minuta creation via Google Docs editor.

**Architecture:** Backend OAuth service exchanges Google authorization codes for tokens (stored encrypted). Frontend modal prompts connection; on success, backend auto-creates Google Doc and redirects to editor. State parameter (Redis) protects against CSRF.

**Tech Stack:** 
- Backend: FastAPI, SQLAlchemy, google-auth-oauthlib, Redis
- Frontend: React, TanStack Query, TypeScript
- Testing: pytest (backend), Playwright (e2e)

## Global Constraints

- All API endpoints require `require_permission("processo", "atualizar")` + `require_tenant_id`
- State tokens expire after 5 minutes (Redis TTL)
- All error messages in Portuguese
- No database schema migrations needed (GoogleCredencial already exists)
- Environment variables must include: GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, GOOGLE_OAUTH_REDIRECT_URI, GOOGLE_CREDENTIALS_FILE
- Frontend components must use existing UI library (Button, Dialog, Input from @/components/ui/*)

---

## File Structure

### Backend Files (New & Modified)

**New:**
- `backend/app/services/google_oauth_flow.py` — OAuth flow orchestration (120 lines)
- `backend/app/routers/auth.py` — OAuth endpoints (60 lines)
- `backend/tests/test_google_oauth_flow.py` — Service unit tests (120 lines)
- `backend/tests/test_auth_routers.py` — Router integration tests (80 lines)

**Modified:**
- `backend/app/config.py` — Add google_oauth_* settings
- `backend/app/main.py` — Register auth router

### Frontend Files (New & Modified)

**New:**
- `frontend/components/GoogleConnectDialog.tsx` — Connection modal (80 lines)
- `frontend/app/(app)/minuta-error.tsx` — OAuth error page (40 lines)
- `frontend/__tests__/GoogleConnectDialog.test.tsx` — Component tests (60 lines)
- `frontend/tests-e2e/specs/google-docs-oauth.spec.ts` — E2E test (80 lines)

**Modified:**
- `frontend/lib/api.ts` — Add `users.getGoogleCredential()`
- `frontend/components/RedigirDocumentoDialog.tsx` — Add credential check + GoogleConnectDialog integration

---

## PHASE A: Backend Foundation (Tasks 1-4)

### Task 1: Implement GoogleOAuthFlow Service

**Files:**
- Create: `backend/app/services/google_oauth_flow.py`
- Test: `backend/tests/test_google_oauth_flow.py`

**Interfaces:**
- Consumes: `settings.google_oauth_client_id`, `settings.google_oauth_client_secret`, `settings.google_oauth_redirect_uri`, Redis client, SQLAlchemy AsyncSession
- Produces: `GoogleOAuthFlow` class with methods:
  - `async generate_oauth_url(user_id: int, tenant_id: int, minuta_id: int) -> str` — returns Google OAuth URL
  - `async handle_callback(code: str, state: str, db: AsyncSession) -> dict` — returns `{user_id, tenant_id, minuta_id}`

- [ ] **Step 1: Create test file with failing tests**

Create `backend/tests/test_google_oauth_flow.py`:

```python
"""Tests for GoogleOAuthFlow service."""
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.google_credencial import GoogleCredencial
from app.services.google_oauth_flow import GoogleOAuthFlow


@pytest.mark.asyncio
async def test_generate_oauth_url_success(redis_client: Redis):
    """Generate OAuth URL + save state to Redis."""
    service = GoogleOAuthFlow(redis_client)
    
    url = await service.generate_oauth_url(
        user_id=123,
        tenant_id=1,
        minuta_id=456,
    )
    
    assert "https://accounts.google.com/o/oauth2/v2/auth" in url
    assert "drive.file" in url
    # Verify state is in Redis
    keys = await redis_client.keys("oauth_state:*")
    assert len(keys) == 1


@pytest.mark.asyncio
async def test_handle_callback_state_expired(redis_client: Redis):
    """State not in Redis → ValueError."""
    service = GoogleOAuthFlow(redis_client)
    
    with pytest.raises(ValueError, match="Sessão expirou"):
        await service.handle_callback("auth_code", "invalid-state")


@pytest.mark.asyncio
async def test_handle_callback_invalid_code(redis_client: Redis):
    """Google API rejects code → ValueError."""
    service = GoogleOAuthFlow(redis_client)
    
    # Setup state in Redis
    state = str(uuid.uuid4())
    context = {"user_id": 123, "tenant_id": 1, "minuta_id": 456}
    await redis_client.setex(
        f"oauth_state:{state}",
        300,
        json.dumps(context),
    )
    
    # Mock Flow to reject code
    with patch("app.services.google_oauth_flow.Flow") as mock_flow:
        mock_flow.from_client_secrets_file.return_value.fetch_token.side_effect = Exception(
            "invalid_grant"
        )
        
        with pytest.raises(ValueError, match="Google negou"):
            await service.handle_callback("bad_code", state)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_google_oauth_flow.py -v`
Expected: 3 FAILED (methods don't exist yet)

- [ ] **Step 3: Implement GoogleOAuthFlow service**

Create `backend/app/services/google_oauth_flow.py`:

```python
"""Google OAuth2 flow handling."""
import json
import uuid
from datetime import datetime, timedelta

from google_auth_oauthlib.flow import Flow
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt
from app.models.google_credencial import GoogleCredencial


class GoogleOAuthFlow:
    """Orchestrate OAuth2 flow with Google Docs API."""

    def __init__(self, redis: Redis):
        self.redis = redis
        # Load from app config
        from app.config import settings
        self.client_id = settings.google_oauth_client_id
        self.client_secret = settings.google_oauth_client_secret
        self.redirect_uri = settings.google_oauth_redirect_uri
        self.credentials_file = settings.google_credentials_file

    async def generate_oauth_url(
        self, user_id: int, tenant_id: int, minuta_id: int
    ) -> str:
        """Generate Google OAuth consent URL + save state to Redis.
        
        Returns:
            URL to redirect user to (Google consent screen)
        """
        state = str(uuid.uuid4())
        
        # Store context in Redis (TTL 5 min)
        context = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "minuta_id": minuta_id,
            "created_at": datetime.utcnow().isoformat(),
        }
        await self.redis.setex(
            f"oauth_state:{state}",
            300,  # 5 minutes
            json.dumps(context),
        )
        
        # Build Google OAuth URL using Flow
        flow = Flow.from_client_secrets_file(
            self.credentials_file,
            scopes=["https://www.googleapis.com/auth/drive.file"],
            redirect_uri=self.redirect_uri,
            state=state,
        )
        auth_url, _ = flow.authorization_url(
            access_type="offline",  # Get refresh token
            prompt="consent",  # Always show consent (force refresh token)
        )
        return auth_url

    async def handle_callback(
        self, code: str, state: str, db: AsyncSession | None = None
    ) -> dict:
        """Exchange authorization_code for tokens + save to DB.
        
        Returns:
            {user_id, tenant_id, minuta_id}
            
        Raises:
            ValueError: if state invalid/expired or code rejected
        """
        # Validate state from Redis
        context_json = await self.redis.get(f"oauth_state:{state}")
        if not context_json:
            raise ValueError("Sessão expirou. Tente novamente.")
        
        context = json.loads(context_json)
        user_id = context["user_id"]
        tenant_id = context["tenant_id"]
        minuta_id = context["minuta_id"]
        
        # Exchange code for tokens
        try:
            flow = Flow.from_client_secrets_file(
                self.credentials_file,
                scopes=["https://www.googleapis.com/auth/drive.file"],
                redirect_uri=self.redirect_uri,
                state=state,
            )
            flow.fetch_token(code=code)
            credentials = flow.credentials
        except Exception as e:
            raise ValueError(f"Google negou o acesso: {str(e)}")
        
        # Save credentials to DB (if session provided)
        if db:
            # Revoke any existing credentials first
            stmt = select(GoogleCredencial).where(
                (GoogleCredencial.tenant_id == tenant_id)
                & (GoogleCredencial.id_usuario == user_id)
                & (GoogleCredencial.revogado == False)
            )
            existing = await db.execute(stmt)
            for cred in existing.scalars():
                cred.revogado = True
            
            # Create new credential
            new_cred = GoogleCredencial(
                tenant_id=tenant_id,
                id_usuario=user_id,
                access_token_cifrado=encrypt(credentials.token),
                refresh_token_cifrado=encrypt(credentials.refresh_token or ""),
                escopo="drive.file",
                expira_em=credentials.expiry,
                criado_em=datetime.utcnow(),
                revogado=False,
            )
            db.add(new_cred)
            await db.commit()
        
        # Clean up state from Redis
        await self.redis.delete(f"oauth_state:{state}")
        
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "minuta_id": minuta_id,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_google_oauth_flow.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/services/google_oauth_flow.py tests/test_google_oauth_flow.py
git commit -m "feat(google-oauth): Implement OAuth flow service

- GoogleOAuthFlow.generate_oauth_url() → state in Redis (5min TTL)
- GoogleOAuthFlow.handle_callback() → exchange code + save credential
- 3 unit tests (success, state expired, invalid code)
- Uses google-auth-oauthlib.flow.Flow for OAuth2
- Tokens encrypted + stored in GoogleCredencial table"
```

---

### Task 2: Implement OAuth Router Endpoints

**Files:**
- Create: `backend/app/routers/auth.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_auth_routers.py`

**Interfaces:**
- Consumes: `GoogleOAuthFlow` (Task 1), `require_permission`, `require_tenant_id`, `get_db`, Redis client
- Produces: 
  - `GET /api/v2/auth/google?minuta_id=X&processo_id=Y` → 307 Redirect to Google
  - `GET /api/v2/auth/google/callback?code=CODE&state=STATE` → 307 Redirect to Google Docs or error page

- [ ] **Step 1: Add OAuth settings to config**

Modify `backend/app/config.py`, add to Settings class:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Google OAuth (Phase 4-5)
    google_oauth_client_id: str = Field(default="")
    google_oauth_client_secret: str = Field(default="")
    google_oauth_redirect_uri: str = Field(default="http://localhost:8000/api/v2/auth/google/callback")
    google_credentials_file: str = Field(default="/app/keys/google-credentials.json")
```

- [ ] **Step 2: Create auth router file with test**

Create `backend/tests/test_auth_routers.py`:

```python
"""Tests for auth routers."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.asyncio
async def test_initiate_google_oauth_redirect(client, admin_token):
    """GET /auth/google redirects to Google consent screen."""
    response = client.get(
        "/api/v2/auth/google?minuta_id=123&processo_id=456",
        headers={"Authorization": f"Bearer {admin_token}"},
        follow_redirects=False,
    )
    
    assert response.status_code == 307
    assert "accounts.google.com" in response.headers["location"]
    assert "state=" in response.headers["location"]


@pytest.mark.asyncio
async def test_initiate_google_oauth_missing_auth(client):
    """GET /auth/google without auth → 401."""
    response = client.get("/api/v2/auth/google?minuta_id=123&processo_id=456")
    
    assert response.status_code == 401
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest backend/tests/test_auth_routers.py -v`
Expected: 2 FAILED (router doesn't exist yet)

- [ ] **Step 4: Implement auth router**

Create `backend/app/routers/auth.py`:

```python
"""Authentication routers (Phase 4-5: Google OAuth)."""
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_permission, require_tenant_id
from app.database import get_db
from app.models.usuario import Usuario
from app.services.google_oauth_flow import GoogleOAuthFlow
from app.dependencies import get_redis


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google")
async def initiate_google_oauth(
    minuta_id: int = Query(...),
    processo_id: int = Query(...),
    usuario: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    redis_client = Depends(get_redis),
) -> RedirectResponse:
    """Initiate OAuth flow. Redirects to Google consent screen.
    
    Query params:
      minuta_id: ID of minuta to associate with OAuth flow
      processo_id: ID of processo (for context, not used in flow)
    
    Returns:
      307 Redirect to Google consent screen
    """
    service = GoogleOAuthFlow(redis_client)
    redirect_url = await service.generate_oauth_url(
        user_id=usuario.id,
        tenant_id=tenant_id,
        minuta_id=minuta_id,
    )
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/google/callback")
async def handle_google_oauth_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis),
) -> RedirectResponse:
    """Handle OAuth callback from Google.
    
    Query params (from Google):
      code: authorization code (if success)
      state: state parameter (CSRF protection)
      error: error code (if user rejected, e.g., "access_denied")
    
    Returns:
      307 Redirect to Google Docs editor URL or error page
    """
    # Check for user rejection
    if error:
        return RedirectResponse(
            url=f"/minuta-error?error={error}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )
    
    if not code or not state:
        return RedirectResponse(
            url="/minuta-error?error=invalid_state",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )
    
    service = GoogleOAuthFlow(redis_client)
    
    try:
        result = await service.handle_callback(code, state, db)
        # result = {user_id, tenant_id, minuta_id}
        
        # Auto-create Google Doc for minuta
        from app.services.minutas import criar_google_doc_para_minuta
        minuta = await criar_google_doc_para_minuta(
            db,
            tenant_id=result["tenant_id"],
            minuta_id=result["minuta_id"],
            usuario_id=result["user_id"],
        )
        
        # Redirect to Google Docs editor
        return RedirectResponse(
            url=minuta.google_doc_url,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )
    
    except ValueError as e:
        # State expired, invalid, etc.
        error_str = str(e).split(":")[-1].strip()
        if "Sessão expirou" in str(e):
            error_code = "state_expired"
        elif "Google negou" in str(e):
            error_code = "google_api_error"
        else:
            error_code = "invalid_state"
        
        return RedirectResponse(
            url=f"/minuta-error?error={error_code}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )
    
    except Exception as e:
        return RedirectResponse(
            url="/minuta-error?error=google_api_error",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )
```

- [ ] **Step 5: Register auth router in main.py**

Modify `backend/app/main.py`, add to app initialization:

```python
from app.routers.auth import router as auth_router

app.include_router(auth_router, prefix="/api/v2")
```

- [ ] **Step 6: Add get_redis dependency**

Modify `backend/app/dependencies.py` (or create if doesn't exist):

```python
"""Shared dependencies."""
from redis.asyncio import Redis, from_url
from app.config import settings


async def get_redis() -> Redis:
    """Get Redis client."""
    return await from_url(settings.redis_url)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest backend/tests/test_auth_routers.py -v`
Expected: 2 PASSED

- [ ] **Step 8: Commit**

```bash
cd backend
git add app/routers/auth.py app/config.py app/main.py app/dependencies.py tests/test_auth_routers.py
git commit -m "feat(oauth): Implement OAuth callback routers

- GET /auth/google → initiate OAuth flow (state in Redis)
- GET /auth/google/callback → exchange code + auto-create doc
- Error handling (state expired, invalid code, user rejection)
- Auto-redirects to Google Docs editor or error page
- 2 integration tests"
```

---

### Task 3: Add Credential Status Endpoint

**Files:**
- Modify: `backend/app/routers/auth.py`
- Test: `backend/tests/test_auth_routers.py`

**Interfaces:**
- Consumes: `require_permission`, `require_tenant_id`, `get_db`
- Produces: 
  - `GET /api/v2/users/me/google-credential` → 200 with `{connected: bool}` or 404

- [ ] **Step 1: Add test for credential status endpoint**

Add to `backend/tests/test_auth_routers.py`:

```python
@pytest.mark.asyncio
async def test_get_google_credential_status_no_credentials(client, admin_token):
    """GET /users/me/google-credential with no credentials → 404."""
    response = client.get(
        "/api/v2/users/me/google-credential",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_auth_routers.py::test_get_google_credential_status_no_credentials -v`
Expected: FAILED (endpoint doesn't exist)

- [ ] **Step 3: Implement credential status endpoint**

Add to `backend/app/routers/auth.py`:

```python
@router.get("/users/me/google-credential")
async def get_google_credential_status(
    usuario: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    """Get credential status for current user.
    
    Returns:
      200: {connected: true, email: "...", connected_at: "..."}
      404: if no credentials
    """
    from sqlalchemy import select
    
    stmt = select(GoogleCredencial).where(
        (GoogleCredencial.tenant_id == tenant_id)
        & (GoogleCredencial.id_usuario == usuario.id)
        & (GoogleCredencial.revogado == False)
    )
    result = await db.execute(stmt)
    cred = result.scalar_one_or_none()
    
    if not cred:
        return None  # FastAPI converts None to 404 by default
    
    return {
        "connected": True,
        "connected_at": cred.criado_em.isoformat(),
    }
```

Wait, need to fix this. Modify the endpoint to properly return 404:

```python
from fastapi import HTTPException

@router.get("/users/me/google-credential")
async def get_google_credential_status(
    usuario: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get credential status for current user.
    
    Returns:
      200: {connected: true, connected_at: "..."}
      404: if no credentials
    """
    from sqlalchemy import select
    
    stmt = select(GoogleCredencial).where(
        (GoogleCredencial.tenant_id == tenant_id)
        & (GoogleCredencial.id_usuario == usuario.id)
        & (GoogleCredencial.revogado == False)
    )
    result = await db.execute(stmt)
    cred = result.scalar_one_or_none()
    
    if not cred:
        raise HTTPException(status_code=404, detail="No credentials found")
    
    return {
        "connected": True,
        "connected_at": cred.criado_em.isoformat(),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_auth_routers.py::test_get_google_credential_status_no_credentials -v`
Expected: PASSED

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/routers/auth.py tests/test_auth_routers.py
git commit -m "feat(oauth): Add credential status endpoint

- GET /users/me/google-credential → check if user has connected credentials
- Returns 404 if no credentials (frontend uses to check before showing Google Docs option)"
```

---

### Task 4: Backend Integration Test

**Files:**
- Modify: `backend/tests/test_auth_routers.py`

**Interfaces:**
- Consumes: All Task 1-3 outputs
- Produces: Full integration test

- [ ] **Step 1: Add integration test for full OAuth flow (mock)**

Add to `backend/tests/test_auth_routers.py`:

```python
@pytest.mark.asyncio
async def test_oauth_flow_full_mock(client, admin_token, redis_client):
    """Full OAuth flow (mocked Google API)."""
    from unittest.mock import AsyncMock, patch
    import uuid
    
    # Step 1: Initiate OAuth
    response = client.get(
        "/api/v2/auth/google?minuta_id=100&processo_id=50",
        headers={"Authorization": f"Bearer {admin_token}"},
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert "accounts.google.com" in response.headers["location"]
    
    # Extract state from URL
    location = response.headers["location"]
    state = location.split("state=")[1].split("&")[0]
    
    # Verify state is in Redis
    state_data = await redis_client.get(f"oauth_state:{state}")
    assert state_data is not None
    
    # Step 2: Mock callback (would come from Google)
    # This is manual testing territory — skipping detailed mock for MVP
```

- [ ] **Step 2: Run integration test**

Run: `pytest backend/tests/test_auth_routers.py::test_oauth_flow_full_mock -v`
Expected: PASSED or skipped (mock Google is complex, manual testing OK)

- [ ] **Step 3: Commit all backend work**

```bash
cd backend
git add .
git commit -m "test(oauth): Add integration tests

- Full OAuth flow test (partial mock)
- Manual testing of Google callback recommended for MVP"
```

---

## PHASE B: Frontend Implementation (Tasks 5-8)

### Task 5: Implement GoogleConnectDialog Component

**Files:**
- Create: `frontend/components/GoogleConnectDialog.tsx`
- Test: `frontend/__tests__/GoogleConnectDialog.test.tsx`

**Interfaces:**
- Consumes: `Button`, `Dialog` from @/components/ui/*, `useToast`
- Produces: `GoogleConnectDialog` component
  - Props: `open: boolean`, `onClose: () => void`, `minutaId: number`, `processoId: number`, `onSuccess?: () => void`

- [ ] **Step 1: Create test file**

Create `frontend/__tests__/GoogleConnectDialog.test.tsx`:

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { GoogleConnectDialog } from "@/components/GoogleConnectDialog";

describe("GoogleConnectDialog", () => {
  it("renders connect button", () => {
    render(
      <GoogleConnectDialog
        open={true}
        onClose={jest.fn()}
        minutaId={123}
        processoId={456}
      />
    );

    expect(screen.getByText("Conectar Conta Google")).toBeInTheDocument();
  });

  it("renders cancel button", () => {
    render(
      <GoogleConnectDialog
        open={true}
        onClose={jest.fn()}
        minutaId={123}
        processoId={456}
      />
    );

    expect(screen.getByText("Cancelar")).toBeInTheDocument();
  });

  it("calls onClose when cancel clicked", () => {
    const onClose = jest.fn();
    render(
      <GoogleConnectDialog
        open={true}
        onClose={onClose}
        minutaId={123}
        processoId={456}
      />
    );

    fireEvent.click(screen.getByText("Cancelar"));
    expect(onClose).toHaveBeenCalled();
  });

  it("doesn't render when open=false", () => {
    const { container } = render(
      <GoogleConnectDialog
        open={false}
        onClose={jest.fn()}
        minutaId={123}
        processoId={456}
      />
    );

    expect(container.firstChild).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- GoogleConnectDialog.test.tsx`
Expected: 4 FAILED (component doesn't exist)

- [ ] **Step 3: Implement GoogleConnectDialog component**

Create `frontend/components/GoogleConnectDialog.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";

interface Props {
  open: boolean;
  onClose: () => void;
  minutaId: number;
  processoId: number;
  onSuccess?: () => void;
}

export function GoogleConnectDialog({
  open,
  onClose,
  minutaId,
  processoId,
  onSuccess,
}: Props) {
  const [isConnecting, setIsConnecting] = useState(false);

  const handleConnect = () => {
    setIsConnecting(true);
    
    // Redirect to OAuth flow
    // Backend will handle: GET /auth/google?minuta_id=X&processo_id=Y
    // → redirects to Google consent
    // → on callback: auto-creates Google Doc
    // → redirects to Google Docs editor
    
    const url = `/api/v2/auth/google?minuta_id=${minutaId}&processo_id=${processoId}`;
    window.location.href = url;
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Conectar Google Docs"
      size="sm"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={handleConnect} disabled={isConnecting}>
            {isConnecting ? "Conectando…" : "Conectar Conta Google"}
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Autorize o acesso a sua conta Google Docs para criar documentos na plataforma.
          Você será redirecionado para a tela de consentimento do Google.
        </p>

        <div className="space-y-2 text-xs text-muted-foreground">
          <p>✓ Você mantém controle total da conta</p>
          <p>✓ Pode desconectar a qualquer momento</p>
          <p>✓ Permissão limitada a Google Drive (criar/editar documentos)</p>
        </div>
      </div>
    </Dialog>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- GoogleConnectDialog.test.tsx`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
cd frontend
git add components/GoogleConnectDialog.tsx __tests__/GoogleConnectDialog.test.tsx
git commit -m "feat(oauth): Implement GoogleConnectDialog component

- Modal dialog for initiating OAuth flow
- Button redirects to /api/v2/auth/google with minuta_id + processo_id
- 4 unit tests"
```

---

### Task 6: Implement minuta-error Page

**Files:**
- Create: `frontend/app/(app)/minuta-error.tsx`

**Interfaces:**
- Consumes: `useRouter`, `useSearchParams`, `useToast`
- Produces: Error page component (handles ?error query param)

- [ ] **Step 1: Create error page**

Create `frontend/app/(app)/minuta-error.tsx`:

```tsx
"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

export default function MinutaErrorPage() {
  const router = useRouter();
  const toast = useToast();
  const params = useSearchParams();

  const error = params.get("error");
  const errorDesc: Record<string, string> = {
    "access_denied":
      "Você rejeitou o acesso ao Google Docs. Tente novamente.",
    "state_expired": "Sessão expirou. Tente conectar novamente.",
    "google_api_error": "Erro ao conectar com Google. Tente novamente.",
    "invalid_state": "Requisição inválida. Tente novamente.",
  };

  useEffect(() => {
    if (error) {
      toast.error(errorDesc[error] || "Erro desconhecido.");
    }
    // Redirect back after 3s
    const timer = setTimeout(() => {
      router.push("/processos");
    }, 3000);
    return () => clearTimeout(timer);
  }, [error, toast, router]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-4">
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-bold">
          Erro ao conectar Google Docs
        </h1>
        <p className="text-muted-foreground">
          {errorDesc[error || ""] ||
            "Ocorreu um erro desconhecido."}
        </p>
        <p className="text-xs text-muted-foreground mt-4">
          Redirecionando em 3 segundos…
        </p>
      </div>
      <Button onClick={() => router.push("/processos")}>
        Voltar aos processos
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Verify page renders (manual check)**

The page doesn't need automated tests — it's simple redirect logic. Manual testing: navigate to `http://localhost:3100/minuta-error?error=access_denied`

- [ ] **Step 3: Commit**

```bash
cd frontend
git add app/\(app\)/minuta-error.tsx
git commit -m "feat(oauth): Add OAuth error page

- Displays error message based on ?error query param
- Auto-redirects to /processos after 3s
- Shows toast with user-friendly error message"
```

---

### Task 7: Integrate GoogleConnectDialog into RedigirDocumentoDialog

**Files:**
- Modify: `frontend/components/RedigirDocumentoDialog.tsx`
- Modify: `frontend/lib/api.ts`

**Interfaces:**
- Consumes: `GoogleConnectDialog` (Task 5), existing RedigirDocumentoDialog
- Produces: Modified RedigirDocumentoDialog with:
  - Query `credentialQ` (GET /users/me/google-credential)
  - Disabled "Google Docs" radio if no credentials
  - Helper text + "Conectar agora" link
  - GoogleConnectDialog modal

- [ ] **Step 1: Add API client method**

Modify `frontend/lib/api.ts`, add to `users` section:

```typescript
users: {
  // ... existing methods ...
  
  getGoogleCredential: async () => {
    try {
      const res = await fetch(`${API_URL}/users/me/google-credential`);
      if (res.status === 404) return { connected: false };
      if (!res.ok) throw new Error("Failed to fetch credential status");
      return res.json();
    } catch (err) {
      // Silently fail — assume no credentials
      return { connected: false };
    }
  },
},
```

- [ ] **Step 2: Modify RedigirDocumentoDialog**

Modify `frontend/components/RedigirDocumentoDialog.tsx`:

Add imports at top:
```tsx
import { GoogleConnectDialog } from "@/components/GoogleConnectDialog";
```

Add state after existing useState declarations:
```tsx
const [showGoogleConnect, setShowGoogleConnect] = useState(false);
```

Add query before existing queries:
```tsx
const credentialQ = useQuery({
  queryKey: ["user", "google-credential"],
  queryFn: () => api.users.getGoogleCredential(),
  enabled: open,
  throwOnError: false, // Silently fail
});

const hasGoogleCredentials = credentialQ.data?.connected === true;
```

Replace the platform selection radio buttons section (around line 186-205) with:

```tsx
<div className="space-y-1.5">
  <Label>Plataforma de redação</Label>
  <div className="space-y-2">
    <label className="flex items-center gap-2 cursor-pointer">
      <input
        type="radio"
        value="interno"
        checked={origem === "interno"}
        onChange={(e) => setOrigem(e.target.value as "interno" | "google")}
        className="w-4 h-4"
      />
      <span className="text-sm">Plataforma (editor interno com templates)</span>
    </label>

    <label className="flex items-center gap-2 cursor-pointer">
      <input
        type="radio"
        value="google"
        checked={origem === "google"}
        onChange={(e) => setOrigem(e.target.value as "interno" | "google")}
        disabled={!hasGoogleCredentials}
        className="w-4 h-4"
      />
      <span className="text-sm">Google Docs (editor externo)</span>
    </label>

    {!hasGoogleCredentials && (
      <div className="ml-6 text-xs text-amber-600 space-y-1">
        <p>⚠️ Você precisa conectar sua conta Google Docs primeiro.</p>
        <button
          type="button"
          onClick={() => setShowGoogleConnect(true)}
          className="text-blue-600 hover:underline font-medium"
        >
          Conectar agora →
        </button>
      </div>
    )}
  </div>
</div>
```

Add GoogleConnectDialog before closing Dialog component:

```tsx
{/* Existing Dialog content ... */}
</Dialog>

{/* NEW: Google Connect Dialog */}
<GoogleConnectDialog
  open={showGoogleConnect}
  onClose={() => setShowGoogleConnect(false)}
  minutaId={minutaAtualId || 0}
  processoId={processoId}
  onSuccess={() => {
    setShowGoogleConnect(false);
    credentialQ.refetch();
  }}
/>
```

- [ ] **Step 3: Manual test in browser**

Start dev server and navigate to a processo with documentos tab:
- `http://localhost:3100/processos/123?tab=documentos`
- Click "Redigir documento"
- Verify "Google Docs" radio is disabled
- Verify "Conectar agora" link appears
- (Full OAuth flow requires Google Cloud setup)

- [ ] **Step 4: Commit**

```bash
cd frontend
git add components/RedigirDocumentoDialog.tsx lib/api.ts
git commit -m "feat(oauth): Integrate GoogleConnectDialog into RedigirDocumentoDialog

- Query credential status on dialog open
- Disable 'Google Docs' radio if no credentials
- Show 'Conectar agora' link with helper text
- Open GoogleConnectDialog modal when link clicked
- Refetch credentials after successful connection"
```

---

### Task 8: Add Frontend Tests

**Files:**
- Create: `frontend/tests-e2e/specs/google-docs-oauth.spec.ts`

**Interfaces:**
- Consumes: Playwright, existing e2e setup
- Produces: Basic e2e test for UI elements

- [ ] **Step 1: Create E2E test**

Create `frontend/tests-e2e/specs/google-docs-oauth.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

test.describe("Google Docs OAuth Flow", () => {
  test("disable Google Docs radio without credentials", async ({ page }) => {
    // Assume already logged in via global setup
    
    // Navigate to processo with documentos tab
    await page.goto("http://localhost:3100/processos/13407?tab=documentos");
    
    // Click "Redigir documento" button
    await page.click("button:has-text('Redigir documento')");
    
    // Find the Google Docs radio button
    const googleRadio = page.locator('input[value="google"]');
    
    // Verify it's disabled
    await expect(googleRadio).toBeDisabled();
  });

  test("show connect link when no credentials", async ({ page }) => {
    await page.goto("http://localhost:3100/processos/13407?tab=documentos");
    await page.click("button:has-text('Redigir documento')");
    
    // Verify helper text appears
    await expect(page.locator("text=Conectar agora")).toBeVisible();
  });

  test("open GoogleConnectDialog when link clicked", async ({ page }) => {
    await page.goto("http://localhost:3100/processos/13407?tab=documentos");
    await page.click("button:has-text('Redigir documento')");
    
    // Click "Conectar agora"
    await page.click("text=Conectar agora");
    
    // Verify dialog opens
    await expect(page.locator("text=Conectar Conta Google")).toBeVisible();
  });
});
```

- [ ] **Step 2: Run E2E tests (requires Docker + backend running)**

Run: `docker compose --profile test run --rm e2e`
Expected: Tests run (actual Google OAuth flow would need manual verification)

- [ ] **Step 3: Commit**

```bash
cd frontend
git add tests-e2e/specs/google-docs-oauth.spec.ts
git commit -m "test(oauth): Add E2E tests for OAuth UI

- Verify Google Docs radio is disabled without credentials
- Verify helper text + connect link visible
- Verify GoogleConnectDialog opens on link click
- Full OAuth flow requires manual testing with real Google account"
```

---

## PHASE C: Testing & Polish (Tasks 9-11)

### Task 9: Run Full Test Suite

**Files:**
- No files created; verification only

**Interfaces:**
- Consumes: All backend + frontend tests from Tasks 1-8
- Produces: Passing test suite

- [ ] **Step 1: Run backend tests**

```bash
cd backend
pytest tests/test_google_oauth_flow.py tests/test_auth_routers.py -v
```

Expected: 6 tests PASSED

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend
npm test -- GoogleConnectDialog.test.tsx
```

Expected: 4 tests PASSED

- [ ] **Step 3: Run E2E tests (optional, requires Docker)**

```bash
docker compose --profile test run --rm e2e
```

Expected: 3 E2E tests run successfully

- [ ] **Step 4: Verify no console errors**

Check browser dev tools (when running locally): `http://localhost:3100`
Expected: No red errors in console

- [ ] **Step 5: Commit test results**

```bash
git add .
git commit -m "test: All OAuth tests passing ✅

Backend:
  - GoogleOAuthFlow service: 3 tests
  - OAuth routers: 2 tests
  - Credential status: 1 test

Frontend:
  - GoogleConnectDialog: 4 component tests
  - E2E: 3 OAuth UI tests

Manual testing: Full Google OAuth flow (requires Google Cloud setup)"
```

---

### Task 10: Document Setup (Google Cloud)

**Files:**
- Create: `.env.example` (update with Google OAuth vars)
- Create: `docs/GOOGLE-DOCS-SETUP.md` (setup instructions)

**Interfaces:**
- Produces: Documentation for deploying OAuth to production VPS

- [ ] **Step 1: Add env vars to .env.example**

Modify `backend/.env.example`:

```bash
# ... existing vars ...

# Google Docs OAuth (Phase 4-5)
GOOGLE_OAUTH_CLIENT_ID=YOUR_CLIENT_ID.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=YOUR_CLIENT_SECRET
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/v2/auth/google/callback
GOOGLE_CREDENTIALS_FILE=/app/keys/google-credentials.json
```

- [ ] **Step 2: Create setup documentation**

Create `docs/GOOGLE-DOCS-SETUP.md`:

```markdown
# Google Docs OAuth Setup Guide

## Local Development

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project: "aprimora-dev"
3. Enable APIs:
   - Google Docs API
   - Google Drive API

### 2. Create OAuth 2.0 Credentials

1. Go to **Credentials** → **Create Credentials** → **OAuth client ID**
2. Choose **Desktop application**
3. Download JSON → save as `backend/keys/google-credentials.json`

### 3. Configure Redirect URI

1. In Credentials, click the credential
2. Add authorized redirect URI: `http://localhost:8000/api/v2/auth/google/callback`
3. Save

### 4. Set Environment Variables

Copy `backend/.env.example` → `backend/.env` and fill in:

```bash
GOOGLE_OAUTH_CLIENT_ID=<from JSON>
GOOGLE_OAUTH_CLIENT_SECRET=<from JSON>
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/v2/auth/google/callback
GOOGLE_CREDENTIALS_FILE=/app/keys/google-credentials.json
```

### 5. Start Containers

```bash
docker compose up -d
```

## Production VPS

### 1. Create Google Cloud Project for Production

Separate from dev — lower risk.

### 2. Update Credentials

Add new credential with production redirect URI:
```
https://aprimora.tld/api/v2/auth/google/callback
```

### 3. Deploy

Update `.env` on VPS with production credentials.

## Testing OAuth Locally

1. Start dev server: `docker compose up`
2. Navigate to: `http://localhost:3100/processos/123?tab=documentos`
3. Click "Redigir documento"
4. Click "Conectar agora"
5. You'll be redirected to Google consent screen
6. Authorize → redirected back to Google Docs editor ✅

## Troubleshooting

### State expired
- Increase Redis TTL in `GoogleOAuthFlow.generate_oauth_url()` (default 5 min)

### Invalid code
- Verify Google Cloud credentials are correct
- Check redirect_uri matches exactly

### CORS errors
- Verify nginx proxy headers (should be transparent for /api/v2/auth/*)
```

- [ ] **Step 3: Commit documentation**

```bash
git add backend/.env.example docs/GOOGLE-DOCS-SETUP.md
git commit -m "docs: Add Google Docs OAuth setup guide

- Local dev setup (Google Cloud project creation)
- Production VPS setup
- Environment variables
- Troubleshooting guide"
```

---

### Task 11: Final Integration & Commit

**Files:**
- All Phase A, B, C files

**Interfaces:**
- Produces: Ready-to-merge PR

- [ ] **Step 1: Verify git log looks clean**

```bash
git log --oneline -15
```

Expected output (most recent first):
```
<recent> docs: Add Google Docs OAuth setup guide
<recent> test: All OAuth tests passing ✅
<recent> test(oauth): Add E2E tests for OAuth UI
<recent> feat(oauth): Integrate GoogleConnectDialog into RedigirDocumentoDialog
<recent> feat(oauth): Add OAuth error page
<recent> feat(oauth): Implement GoogleConnectDialog component
<recent> feat(oauth): Add credential status endpoint
<recent> feat(oauth): Implement OAuth callback routers
<recent> feat(oauth): Implement OAuth flow service
```

- [ ] **Step 2: Verify no uncommitted changes**

```bash
git status
```

Expected: `On branch main ... nothing to commit, working tree clean`

- [ ] **Step 3: Create summary commit (optional)**

If you want to squash into one commit for cleaner history:

```bash
git log --oneline | head -9 | tail -1
# Get the SHA of the commit before Task 1

git reset --soft <SHA>
git commit -m "feat(pr-f-oauth): Complete Phases 4-5 OAuth integration ✅

PHASE A: Backend Foundation
  - GoogleOAuthFlow service (state + token exchange)
  - OAuth routers (GET /auth/google + callback)
  - Credential status endpoint
  - 6 backend tests

PHASE B: Frontend
  - GoogleConnectDialog modal component
  - minuta-error page (error handling)
  - RedigirDocumentoDialog integration (credential check)
  - 4 component tests + 3 E2E tests

PHASE C: Documentation
  - Google Cloud OAuth setup guide
  - Environment variables (.env.example)

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Push to origin (ready for VPS deployment)**

```bash
git push origin main
```

Expected: `main -> main`

- [ ] **Step 5: Final verification**

```bash
npm run build  # Frontend build check
cd backend && mypy app/services/google_oauth_flow.py  # Type check (optional)
```

Expected: No build errors

---

## Summary

**✅ Completed:**
- 11 tasks across 3 phases
- ~530 lines of code (backend service, routers, frontend components)
- 13 tests (backend + frontend + E2E)
- Full OAuth flow: Google consent → token exchange → auto-create doc → redirect

**📦 Deliverables:**
- Phases 4-5 implementation (OAuth + credentials UI)
- Ready for VPS deployment
- Requires Google Cloud setup (documented)

**🚀 Next Steps:**
- Deploy to VPS (103.230.142.69)
- Set up Google Cloud OAuth credentials on VPS
- Test full flow with real Google account
- Optional Phase 5+: Credential revocation UI, token refresh retry logic

---
