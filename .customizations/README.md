# Autotech AI Customizations to Open WebUI

This directory contains patches and documentation of all customizations made to the
upstream Open WebUI codebase. Use these to re-apply changes after pulling updates.

## Quick Reference

**Last synced with upstream:** January 2026  
**Upstream repo:** https://github.com/open-webui/open-webui

---

## NEW FILES (Safe - won't be overwritten)

These files are entirely new and won't conflict with upstream updates:

### Backend
| File | Purpose |
|------|---------|
| `backend/open_webui/models/billing.py` | Token billing system models |
| `backend/open_webui/routers/billing.py` | Billing API endpoints |
| `backend/open_webui/routers/google.py` | Google API integration |
| `backend/open_webui/routers/mitchell.py` | Mitchell/ShopKeyPro agent integration |
| `backend/langchain_classic/` | LangChain compatibility shims |
| `backend/langchain_community/` | LangChain compatibility shims |
| `backend/langchain_core/` | LangChain compatibility shims |

### Frontend
| File | Purpose |
|------|---------|
| `src/lib/apis/billing/index.ts` | Billing API client |
| `src/lib/apis/billing/usage.ts` | Usage tracking |
| `src/lib/apis/google/index.ts` | Google API client |
| `src/lib/components/admin/Billing.svelte` | Billing admin component |
| `src/routes/(app)/admin/billing/+page.svelte` | Billing admin page |

### Database Migrations
- `add_billing_tables.py` - Billing tables
- `add_token_purchase_tables.py` - Token purchase tracking
- `add_token_purchase_stripe_fields.py` - Stripe integration
- `af5b9d7c1a2a_add_phone_and_address_to_user.py` - User contact fields

---

## MODIFIED FILES (Will need re-applying after update)

### Critical Changes

#### 1. User Model (`backend/open_webui/models/users.py`)
**Patch:** `users_model.patch`

Added fields:
```python
phone = Column(String, nullable=True)
address = Column(Text, nullable=True)
```

#### 2. User Permissions (`backend/open_webui/routers/users.py`)
**Patch:** `users_router.patch`

Removed permissions:
- `memories: bool = True` (removed from FeaturesPermissions)
- `SettingsPermissions` class (removed entirely)
- `settings` field from UserPermissions

Changed database session handling from `db: Session = Depends(get_session)` to simpler pattern.

#### 3. Main Application (`backend/open_webui/main.py`)
**Patch:** `main_py.patch`

Added router imports:
```python
from open_webui.routers import google, mitchell
```

Added billing router dynamic import with debug logging.

Added to lifespan:
```python
await ensure_billing_router_registered()
```

#### 4. Config (`backend/open_webui/config.py`)
**Patch:** `config.patch`

Added:
- `ENABLE_GOOGLE_API`
- `GOOGLE_API_BASE_URLS`
- `GOOGLE_API_KEYS`
- `MODEL_PROVIDER_CREDENTIALS`
- `BILLING_TOKEN_USD_RATE`

Removed:
- `ENABLE_MEMORIES`
- `ENABLE_USER_STATUS`
- `FIRECRAWL_TIMEOUT`
- `CHUNK_MIN_SIZE_TARGET`
- `ENABLE_MARKDOWN_HEADER_TEXT_SPLITTER`
- `JINA_API_BASE_URL`
- `DDGS_BACKEND`
- `FOLDER_MAX_FILE_COUNT`

#### 5. Environment (`backend/open_webui/env.py`)
**Patch:** `env.patch`

Removed:
- `WEBUI_ADMIN_EMAIL`
- `WEBUI_ADMIN_PASSWORD`
- `WEBUI_ADMIN_NAME`

#### 6. Database (`backend/open_webui/internal/db.py`)
**Patch:** `db.patch`

Changed session handling pattern (removed `get_session` dependency injection).

#### 7. Auth Page (`src/routes/auth/+page.svelte`)
**Patch:** `auth_page.patch`

Added:
- Service worker unregistration on login
- Cache clearing on login
- Login telemetry beacon to `/_debug/client-login`

Removed:
- Timezone update on login

#### 8. App Layout (`src/routes/(app)/+layout.svelte`)
**Patch:** `app_layout.patch`

Added:
- Stripe checkout session confirmation
- `billing:balance-updated` custom event dispatch

---

## How to Re-apply After Update

### Option 1: Apply All Patches (Recommended)
```bash
# After pulling upstream changes
cd /home/drawson/autotech_ai

# Try to apply the master patch
git apply --check .customizations/all_changes.patch
git apply .customizations/all_changes.patch

# If conflicts, apply individual patches
git apply --3way .customizations/main_py.patch
git apply --3way .customizations/users_model.patch
# ... etc
```

### Option 2: Manual Re-apply
1. Copy new files from `new_files.txt` (they should still exist)
2. Review each patch file and manually apply changes
3. Run database migrations

### Option 3: Cherry-pick Commits
If you've been committing your changes separately:
```bash
git log --oneline | grep -i "billing\|mitchell\|google\|phone\|address"
# Then cherry-pick specific commits
```

---

## Files List

- `modified_files.txt` - All files modified from upstream
- `new_files.txt` - All new files added
- `all_changes.patch` - Master patch with all changes
- Individual `.patch` files for each major component

---

## After Updating

1. **Run migrations:** `alembic upgrade head`
2. **Rebuild frontend:** `npm run build`
3. **Test billing:** Check `/admin/billing` works
4. **Test Mitchell:** Verify tool still functions
5. **Test login:** Confirm auth flow works

---

## Notes

- The upstream removed `db: Session = Depends(get_session)` pattern - your code uses the older pattern
- Many model functions changed signature (removed `db=db` parameter)
- If update fails, you may need to adapt your code to new upstream patterns
