# Forgot Password With Resend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a public forgot-password flow where a user requests a reset email, receives a Resend-powered link, opens the web reset page, and sets a new password.

**Architecture:** Use one-time, hashed password reset tokens stored in PostgreSQL with expiry and consumed metadata. Keep routes thin under `/auth`, place token and email logic in services, send email through a small Resend client abstraction, and invalidate active refresh tokens after a successful password reset.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, bcrypt, httpx, Resend HTTP API, SvelteKit SPA, Svelte 5 runes, Vitest.

---

## Product Decisions

- Public endpoints:
  - `POST /api/v1/auth/forgot-password`
  - `POST /api/v1/auth/reset-password`
- The forgot-password endpoint always returns `204`, even when the email does not exist, to avoid account enumeration.
- Reset tokens are random 64-byte hex strings. The backend stores only `SHA256(raw_token)`.
- Reset links point to `${FRONTEND_URL}/reset-password?token=${raw_token}`.
- Tokens expire after 30 minutes and are single-use.
- Successful reset revokes all active refresh tokens for the user.
- Resend failures are logged and do not reveal whether the user exists. For existing users, a failed email send should return `503` so operators can detect configuration/provider problems.
- Frontend routes `/forgot-password` and `/reset-password` are public auth-bypass pages like `/login`.

## Configuration

Add backend env settings in `kasir-be/app/config.py`:

```python
resend_api_key: str | None = None
resend_from_email: str = "Kasir <no-reply@example.com>"
frontend_url: str = "http://localhost:5173"
password_reset_token_expire_minutes: int = 30
```

Add `httpx` to backend dependencies in `kasir-be/pyproject.toml` because the Resend API is called over HTTPS:

```toml
"httpx>=0.27.0",
```

Document required deployment env vars:

```bash
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL="Kasir <no-reply@yourdomain.com>"
FRONTEND_URL=https://your-kasir-web-domain.com
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=30
```

---

### Task 1: Add Backend Password Reset Token Model And Migration

**Files:**
- Create: `kasir-be/app/models/password_reset_token.py`
- Modify: `kasir-be/app/models/__init__.py`
- Create: `kasir-be/alembic/versions/<revision>_add_password_reset_tokens.py`
- Modify: `doc/db-schema.md`

**Step 1: Create model**

Create `kasir-be/app/models/password_reset_token.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class PasswordResetToken(Base, TimestampMixin):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()
```

**Step 2: Export model**

Update `kasir-be/app/models/__init__.py`:

```python
from app.models.password_reset_token import PasswordResetToken
```

Add `"PasswordResetToken"` to `__all__`.

**Step 3: Create migration**

Run:

```bash
cd kasir-be
uv run alembic revision --autogenerate -m "add password reset tokens"
```

Expected: a new migration appears in `kasir-be/alembic/versions/`.

Review and keep it equivalent to:

```python
op.create_table(
    "password_reset_tokens",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("user_id", sa.Uuid(), nullable=False),
    sa.Column("token_hash", sa.String(length=64), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id"),
)
op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True)
op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
```

**Step 4: Update schema docs**

In `doc/db-schema.md`, add:

```markdown
| `password_reset_tokens` | Hashed single-use password reset tokens, expiry, consumed timestamp |
```

**Step 5: Verify migration**

Run:

```bash
cd kasir-be
uv run alembic upgrade head
```

Expected: migration succeeds.

**Step 6: Commit**

```bash
git add kasir-be/app/models/password_reset_token.py kasir-be/app/models/__init__.py kasir-be/alembic/versions doc/db-schema.md
git commit -m "feat: add password reset token storage"
```

---

### Task 2: Add Resend Email Client

**Files:**
- Create: `kasir-be/app/services/email_service.py`
- Modify: `kasir-be/app/config.py`
- Modify: `kasir-be/pyproject.toml`

**Step 1: Write email service**

Create `kasir-be/app/services/email_service.py`:

```python
import httpx

from app.config import settings
from app.core.exceptions import BadRequestError


class EmailSendError(RuntimeError):
    pass


async def send_password_reset_email(email: str, reset_url: str) -> None:
    if not settings.resend_api_key:
        raise EmailSendError("RESEND_API_KEY is not configured")

    payload = {
        "from": settings.resend_from_email,
        "to": [email],
        "subject": "Reset your Kasir password",
        "html": (
            "<p>You requested a password reset for your Kasir account.</p>"
            f'<p><a href="{reset_url}">Reset your password</a></p>'
            "<p>This link expires in 30 minutes. If you did not request it, ignore this email.</p>"
        ),
        "text": (
            "You requested a password reset for your Kasir account.\n\n"
            f"Reset your password: {reset_url}\n\n"
            "This link expires in 30 minutes. If you did not request it, ignore this email."
        ),
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json=payload,
        )

    if response.status_code >= 400:
        raise EmailSendError(f"Resend failed with status {response.status_code}")
```

Remove `BadRequestError` if unused after implementation.

**Step 2: Add settings**

Update `kasir-be/app/config.py` with the fields listed in the configuration section.

**Step 3: Add dependency**

Update `kasir-be/pyproject.toml` dependencies:

```toml
"httpx>=0.27.0",
```

Run:

```bash
cd kasir-be
uv lock
```

Expected: `uv.lock` updates with `httpx` if it was not already present.

**Step 4: Commit**

```bash
git add kasir-be/app/services/email_service.py kasir-be/app/config.py kasir-be/pyproject.toml kasir-be/uv.lock
git commit -m "feat: add Resend email service"
```

---

### Task 3: Add Auth Schemas And Service Logic

**Files:**
- Modify: `kasir-be/app/core/security.py`
- Modify: `kasir-be/app/schemas/auth.py`
- Modify: `kasir-be/app/services/auth_service.py`

**Step 1: Add token helper**

In `kasir-be/app/core/security.py`:

```python
def create_password_reset_token() -> tuple[str, str]:
    raw = secrets.token_hex(64)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def hash_password_reset_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
```

**Step 2: Add schemas**

In `kasir-be/app/schemas/auth.py`:

```python
class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=32)
    password: str = Field(min_length=8)
```

**Step 3: Add forgot-password service**

In `kasir-be/app/services/auth_service.py`, add:

```python
from urllib.parse import urljoin

from app.models import PasswordResetToken
from app.services.email_service import send_password_reset_email
```

Add:

```python
async def request_password_reset(email: str, db: AsyncSession) -> bool:
    result = await db.execute(select(User).where(User.email == email, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if user is None:
        return False

    raw_token, token_hash = create_password_reset_token()
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.password_reset_token_expire_minutes),
    )
    db.add(token)
    await db.commit()

    reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password?token={raw_token}"
    await send_password_reset_email(user.email, reset_url)
    return True
```

**Step 4: Add reset-password service**

Add:

```python
async def reset_password(raw_token: str, password: str, db: AsyncSession) -> None:
    token_hash = hash_password_reset_token(raw_token)
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()
    now = datetime.now(UTC)

    if (
        token is None
        or token.consumed_at is not None
        or token.expires_at.replace(tzinfo=UTC) < now
    ):
        raise BadRequestError("Invalid or expired reset link")

    user_result = await db.execute(select(User).where(User.id == token.user_id, User.is_active.is_(True)))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise BadRequestError("Invalid or expired reset link")

    user.hashed_password = hash_password(password)
    token.consumed_at = now

    refresh_result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.is_revoked.is_(False),
        )
    )
    for refresh_token in refresh_result.scalars().all():
        refresh_token.is_revoked = True

    await db.commit()
```

**Step 5: Prefer transaction safety**

If implementation time permits, wrap the reset query in a transaction and lock the token row:

```python
select(PasswordResetToken)
.where(PasswordResetToken.token_hash == token_hash)
.with_for_update()
```

This prevents two simultaneous reset submissions from both succeeding.

**Step 6: Commit**

```bash
git add kasir-be/app/core/security.py kasir-be/app/schemas/auth.py kasir-be/app/services/auth_service.py
git commit -m "feat: add password reset auth service"
```

---

### Task 4: Add Public Auth Routes And Rate Limits

**Files:**
- Modify: `kasir-be/app/api/v1/auth.py`
- Modify: `doc/api-contracts.md`

**Step 1: Import schemas and error type**

Update `kasir-be/app/api/v1/auth.py` imports:

```python
from fastapi import APIRouter, Depends, Header, Request, status
from app.schemas.auth import (
    ForgotPasswordIn,
    LoginIn,
    RefreshIn,
    RegisterIn,
    ResetPasswordIn,
    TokenResponse,
    UserRead,
)
from app.services.email_service import EmailSendError
from app.core.exceptions import BadRequestError
```

Use the project’s existing exception style. If there is no service-unavailable exception, raise `HTTPException(status_code=503, detail="Password reset email could not be sent")`.

**Step 2: Add forgot-password route**

```python
@router.post("/forgot-password", status_code=204)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    payload: ForgotPasswordIn,
    db: AsyncSession = Depends(get_db),
):
    try:
        await auth_service.request_password_reset(payload.email, db)
    except EmailSendError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email could not be sent",
        )
```

**Step 3: Add reset-password route**

```python
@router.post("/reset-password", status_code=204)
@limiter.limit("10/minute")
async def reset_password(
    request: Request,
    payload: ResetPasswordIn,
    db: AsyncSession = Depends(get_db),
):
    await auth_service.reset_password(payload.token, payload.password, db)
```

**Step 4: Update API docs**

In `doc/api-contracts.md`, add:

```markdown
| POST | `/auth/forgot-password` | Public | Sends reset email when account exists; always 204 unless email provider fails |
| POST | `/auth/reset-password` | Public | Consumes reset token and updates password |
```

**Step 5: Commit**

```bash
git add kasir-be/app/api/v1/auth.py doc/api-contracts.md
git commit -m "feat: expose password reset auth endpoints"
```

---

### Task 5: Add Backend Tests

**Files:**
- Create: `kasir-be/tests/test_password_reset.py`
- Possibly create: `kasir-be/tests/conftest.py`

**Step 1: Add test fixtures if missing**

If the project has no API test fixtures, create minimal async fixtures using SQLite and FastAPI dependency overrides, or follow any existing hidden test pattern if available.

**Step 2: Test forgot-password does not enumerate users**

Test cases:

```python
async def test_forgot_password_unknown_email_returns_204(client):
    response = await client.post("/api/v1/auth/forgot-password", json={"email": "none@example.com"})
    assert response.status_code == 204
```

```python
async def test_forgot_password_existing_user_creates_token_and_sends_email(client, db, monkeypatch):
    sent = []

    async def fake_send(email: str, reset_url: str) -> None:
        sent.append((email, reset_url))

    monkeypatch.setattr("app.services.auth_service.send_password_reset_email", fake_send)

    response = await client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})

    assert response.status_code == 204
    assert sent
    assert "/reset-password?token=" in sent[0][1]
```

**Step 3: Test reset-password updates password and revokes sessions**

```python
async def test_reset_password_consumes_token_updates_password_and_revokes_refresh_tokens(client, db, user):
    raw_token, token_hash = create_password_reset_token()
    db.add(PasswordResetToken(...))
    db.add(RefreshToken(..., is_revoked=False))
    await db.commit()

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "password": "new-password-123"},
    )

    assert response.status_code == 204
    await db.refresh(user)
    assert verify_password("new-password-123", user.hashed_password)
```

**Step 4: Test invalid, expired, and consumed tokens**

Expected status: `400`.

**Step 5: Run tests**

```bash
cd kasir-be
uv run pytest tests/test_password_reset.py -v
uv run pytest -v
```

Expected: all tests pass.

**Step 6: Commit**

```bash
git add kasir-be/tests/test_password_reset.py kasir-be/tests/conftest.py
git commit -m "test: cover password reset flow"
```

---

### Task 6: Add Frontend Public Routes

**Files:**
- Modify: `kasir-fe/src/routes/+layout.svelte`
- Create: `kasir-fe/src/routes/forgot-password/+page.svelte`
- Create: `kasir-fe/src/routes/reset-password/+page.svelte`

**Step 1: Extend auth bypass**

In `kasir-fe/src/routes/+layout.svelte`, replace the login-only public check with:

```ts
let isPublicAuth = $derived(
  currentPath === '/login' ||
  currentPath === '/forgot-password' ||
  currentPath === '/reset-password'
);
```

Use `isPublicAuth` wherever `isLogin` is currently used.

**Step 2: Add link from login**

In `kasir-fe/src/routes/login/+page.svelte`, add a small link near the password field:

```svelte
<a class="text-sm font-semibold text-[var(--mid-brown)] hover:underline" href="/forgot-password">
  Forgot password?
</a>
```

**Step 3: Create forgot-password page**

Create `kasir-fe/src/routes/forgot-password/+page.svelte`:

```svelte
<script lang="ts">
  import { api } from '$lib/api/client';

  let email = $state('');
  let loading = $state(false);
  let sent = $state(false);
  let error = $state('');

  async function submit() {
    loading = true;
    error = '';
    try {
      await api.post('/auth/forgot-password', { email });
      sent = true;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to send reset email.';
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head><title>Forgot Password | Kasir</title></svelte:head>

<main class="flex min-h-screen items-center justify-center bg-[var(--cream)] p-6">
  <form class="card w-full max-w-md p-8" onsubmit={(event) => { event.preventDefault(); submit(); }}>
    <h1 class="display-font text-4xl font-bold text-[var(--espresso)]">Reset password</h1>
    <p class="mt-2 text-sm text-[var(--text-muted)]">
      Enter your email and we will send a reset link if the account exists.
    </p>

    {#if sent}
      <div class="mt-6 rounded-xl border border-green-200 bg-green-50 p-3 text-sm font-semibold text-green-700">
        Check your email for a password reset link.
      </div>
    {:else}
      {#if error}
        <div class="mt-6 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-700">{error}</div>
      {/if}

      <label class="mt-6 block text-sm font-bold text-[var(--espresso)]">
        Email
        <input class="field mt-2" type="email" bind:value={email} autocomplete="email" required />
      </label>

      <button class="btn-primary mt-6 w-full" disabled={loading}>
        {loading ? 'Sending...' : 'Send reset link'}
      </button>
    {/if}

    <a class="mt-6 inline-block text-sm font-semibold text-[var(--mid-brown)] hover:underline" href="/login">
      Back to login
    </a>
  </form>
</main>
```

**Step 4: Create reset-password page**

Create `kasir-fe/src/routes/reset-password/+page.svelte`:

```svelte
<script lang="ts">
  import { page } from '$app/state';
  import { api } from '$lib/api/client';

  let password = $state('');
  let confirmPassword = $state('');
  let loading = $state(false);
  let success = $state(false);
  let error = $state('');

  let token = $derived(page.url.searchParams.get('token') ?? '');

  async function submit() {
    error = '';
    if (!token) {
      error = 'Reset link is missing a token.';
      return;
    }
    if (password.length < 8) {
      error = 'Password must be at least 8 characters.';
      return;
    }
    if (password !== confirmPassword) {
      error = 'Passwords do not match.';
      return;
    }

    loading = true;
    try {
      await api.post('/auth/reset-password', { token, password });
      password = '';
      confirmPassword = '';
      success = true;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to reset password.';
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head><title>Reset Password | Kasir</title></svelte:head>

<main class="flex min-h-screen items-center justify-center bg-[var(--cream)] p-6">
  <form class="card w-full max-w-md p-8" onsubmit={(event) => { event.preventDefault(); submit(); }}>
    <h1 class="display-font text-4xl font-bold text-[var(--espresso)]">Choose new password</h1>

    {#if success}
      <div class="mt-6 rounded-xl border border-green-200 bg-green-50 p-3 text-sm font-semibold text-green-700">
        Password updated. You can sign in with your new password.
      </div>
      <a class="btn-primary mt-6 block text-center" href="/login">Go to login</a>
    {:else}
      {#if error}
        <div class="mt-6 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-700">{error}</div>
      {/if}

      <label class="mt-6 block text-sm font-bold text-[var(--espresso)]">
        New password
        <input class="field mt-2" type="password" bind:value={password} autocomplete="new-password" required />
      </label>

      <label class="mt-4 block text-sm font-bold text-[var(--espresso)]">
        Confirm password
        <input class="field mt-2" type="password" bind:value={confirmPassword} autocomplete="new-password" required />
      </label>

      <button class="btn-primary mt-6 w-full" disabled={loading || !token}>
        {loading ? 'Saving...' : 'Update password'}
      </button>
    {/if}
  </form>
</main>
```

**Step 5: Commit**

```bash
git add kasir-fe/src/routes/+layout.svelte kasir-fe/src/routes/login/+page.svelte kasir-fe/src/routes/forgot-password/+page.svelte kasir-fe/src/routes/reset-password/+page.svelte
git commit -m "feat: add password reset web pages"
```

---

### Task 7: Add Frontend Tests And Type Checks

**Files:**
- Create or modify frontend tests as practical under `kasir-fe/src/`

**Step 1: Add API helper tests if routes are wrapped**

If a dedicated API function is introduced, test it with Vitest. If pages call `api.post` directly, skip brittle page tests and rely on Svelte type checking.

**Step 2: Run frontend verification**

```bash
cd kasir-fe
npm run check
npm run test
npm run build
```

Expected: Svelte check, Vitest, and production build all pass.

**Step 3: Commit**

```bash
git add kasir-fe
git commit -m "test: verify password reset frontend"
```

---

### Task 8: End-To-End Manual Verification

**Files:**
- No source files unless defects are found.

**Step 1: Configure local env**

Set backend `.env`:

```bash
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL="Kasir <verified@yourdomain.com>"
FRONTEND_URL=http://localhost:5173
```

**Step 2: Start services**

```bash
cd kasir-be
uv run uvicorn app.main:app --reload
```

```bash
cd kasir-fe
npm run dev
```

**Step 3: Verify request email**

Open:

```text
http://kasir.test:5173/forgot-password
```

Submit a known user email.

Expected:

- UI shows "Check your email for a password reset link."
- Resend dashboard shows accepted email.
- Email contains a link to `/reset-password?token=...`.

**Step 4: Verify reset**

Open the reset link and set a new password.

Expected:

- UI shows success state.
- Login with old password fails.
- Login with new password succeeds.
- Previously issued refresh token cannot refresh after reset.

**Step 5: Verify token safety**

Use the same reset link again.

Expected:

- Backend returns `400`.
- UI shows invalid or expired reset link.

**Step 6: Final commit if fixes were needed**

```bash
git status --short
git add <changed-files>
git commit -m "fix: finalize password reset flow"
```

---

## Rollout Notes

- Resend requires a verified sending domain before production use.
- `FRONTEND_URL` must match the public web app origin, not the API origin.
- Do not log raw reset tokens.
- Consider periodic cleanup later: delete consumed or expired `password_reset_tokens` older than 7 days.
- The Android app can open this flow through the same SPA routes, but email reset links should target the public web origin unless deep linking is added separately.

## Final Verification Commands

Run all of these before considering the feature complete:

```bash
cd kasir-be
uv run ruff check .
uv run pytest -v
uv run alembic upgrade head
```

```bash
cd kasir-fe
npm run check
npm run test
npm run build
```

