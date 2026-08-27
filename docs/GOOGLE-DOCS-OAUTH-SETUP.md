# Google Docs OAuth Setup Guide

> **Status:** vivo · **Autoridade sobre:** Setup do OAuth do Google Docs para minutas.
> **Última verificação:** 2026-07-21 (último commit que tocou este arquivo).
> Índice: [docs/INDEX.md](INDEX.md) · precedência: código > `CLAUDE.md` > este doc.


## Overview

This guide covers setting up Google Docs OAuth2 authentication for Aprimora-py. Users can authorize their Google account to create and edit documents directly in Google Docs from the platform.

## Prerequisites

- Google Cloud account (free tier OK)
- VPS access (for production deployment)
- Docker Compose (for local development)

## Local Development Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project: "aprimora-dev" (or similar)
3. Wait for project creation

### 2. Enable APIs

1. In Cloud Console, search for "Google Docs API"
   - Click **ENABLE**
2. Search for "Google Drive API"
   - Click **ENABLE**

### 3. Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **OAuth client ID**
3. Choose application type: **Desktop application**
4. Click **Create**
5. Download JSON file (save as `backend/keys/google-credentials.json`)

### 4. Configure Redirect URI

1. Go back to Credentials
2. Click the newly created credential (OAuth 2.0 Client ID)
3. Under **Authorized redirect URIs**, click **Add URI**
4. Add: `http://localhost:8000/api/v2/auth/google/callback`
5. Click **Save**

### 5. Set Environment Variables

Copy `backend/.env.example` → `backend/.env`:

```bash
# Extract from downloaded JSON:
GOOGLE_OAUTH_CLIENT_ID=<client_id>.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=<client_secret>
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/v2/auth/google/callback
GOOGLE_CREDENTIALS_FILE=/app/keys/google-credentials.json
```

### 6. Start Development Containers

```bash
docker compose up -d
```

### 7. Test OAuth Locally

1. Navigate to: `http://localhost:3100/processos/123?tab=documentos`
2. Click "Redigir documento"
3. Select "Google Docs"
4. Click "Conectar agora"
5. Authorize in Google consent screen
6. You should be redirected to Google Docs editor ✓

## Production Deployment (VPS)

### 1. Create Google Cloud Project for Production

Use a separate Google Cloud project (lower risk if credentials compromise).

### 2. Create OAuth Credentials for Production

Follow steps 1-3 above, but name the project "aprimora-prod".

### 3. Add Production Redirect URI

When creating the OAuth credential, add redirect URI:
```
https://aprimora.tld/api/v2/auth/google/callback
```
(Replace `aprimora.tld` with your actual domain)

### 4. Deploy to VPS

1. SSH into VPS (103.230.142.69)
2. Pull latest code from main branch
3. Update `.env` on VPS:
   ```bash
   GOOGLE_OAUTH_CLIENT_ID=<prod_client_id>
   GOOGLE_OAUTH_CLIENT_SECRET=<prod_client_secret>
   GOOGLE_OAUTH_REDIRECT_URI=https://aprimora.tld/api/v2/auth/google/callback
   GOOGLE_CREDENTIALS_FILE=/app/keys/google-credentials.json
   ```
4. Place Google credentials JSON at `/app/keys/google-credentials.json`
5. Restart containers: `docker compose restart`

## Troubleshooting

### "State expired"
- Error: User took >5 minutes on Google consent screen
- Solution: Increase Redis TTL in `GoogleOAuthFlow.generate_oauth_url()` if needed

### "Invalid code" / "Google negou"
- Error: Authorization code invalid or rejected
- Cause: Redirect URI mismatch or credentials expired
- Solution: Verify redirect URI in Google Cloud Console matches app config

### "Sessão expirou"
- Error: State parameter not found in Redis
- Cause: Redis connection lost or TTL expired
- Solution: Verify Redis running, check TTL settings

### CORS Errors
- Error: API call blocked by browser CORS
- Cause: nginx not properly routing /api/v2/auth/*
- Solution: Check nginx config allows auth routes (should be transparent proxy)

## API Endpoints (Reference)

**User-facing:**
- `GET /api/v2/auth/google?minuta_id=X&processo_id=Y` — Initiate OAuth flow
- `GET /api/v2/auth/google/callback?code=CODE&state=STATE` — Handle callback

**Admin-facing (checking credential status):**
- `GET /api/v2/users/me/google-credential` — Returns 200 or 404 (credential status)

## Security Notes

- Access tokens are encrypted with Fernet before storage
- State parameter protected against CSRF (Redis + 5min TTL)
- Credentials are per-user, per-tenant (RLS policies enforce isolation)
- Old credentials are revoked when user connects new account
- All requests require authentication + tenant context

## Support

For issues, check:
1. Google Cloud Console → APIs & Services → Credentials (valid client ID/secret)
2. Redirect URI matches exactly (trailing slash matters)
3. Redis running: `redis-cli ping` should return PONG
4. Backend logs: `docker logs aprimora-py-backend`
