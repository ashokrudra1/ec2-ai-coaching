# PHASE 4: WEBHOOK & EXTERNAL API LAYER - IMPLEMENTATION SUMMARY

## Overview
Phase 4 implements robust webhook handlers for Telegram and Strava with comprehensive security features, error handling, and non-blocking architecture.

## Components Implemented

### 1. TelegramWebhookHandler (backend/webhook.py)
**Purpose**: Securely receive and process Telegram updates

**Features**:
- ✅ Secret token validation (CSRF/spoofing protection)
- ✅ Message type classification:
  - Text messages → chat_critical queue
  - Callback queries → Button click handling
  - Document uploads (PDF) → Medical insights extraction
- ✅ Non-blocking Celery task dispatch
- ✅ Graceful error handling with automatic Telegram ACK
- ✅ Rate limiting (60 per minute by default)

**Implementation Details**:
```python
class TelegramWebhookHandler:
    - validate_secret(token) → bool
    - parse_message(body) → (is_valid, message_type)
```

**Message Types**:
| Type | Handler | Output |
|------|---------|--------|
| text | trigger_durable_webhook_handler | Coach response |
| callback | Button click → coach_persona/rpe/sync | State update + message |
| document | PDF extraction → medical insights | Stored in user.medical_insights |

### 2. StravaWebhookHandler (backend/strava_webhooks.py)
**Purpose**: Securely receive and process Strava activity events

**Features**:
- ✅ HMAC-SHA256 signature validation
- ✅ Duplicate activity detection
- ✅ Event filtering (only create/update activity events)
- ✅ Non-blocking background task queue
- ✅ Rate limiting
- ✅ Comprehensive logging

**Security**:
- Validates `X-Strava-Hook-Signature` header using `STRAVA_SIGNING_SECRET`
- Prevents replay attacks and tampering
- Returns 200 OK even on errors (prevents Strava retries)

**Implementation Details**:
```python
def validate_strava_signature(body: bytes, signature: str) -> bool:
    # HMAC-SHA256 validation against STRAVA_SIGNING_SECRET
```

### 3. PDF Utils Enhancement (backend/pdf_utils.py)
**Purpose**: Extract and clean medical document text

**Functions**:
```python
extract_text_from_pdf_bytes(pdf_bytes, max_pages=None) → str
    # Full PDF extraction with page limits

clean_extracted_text(text) → str
    # Remove control chars, normalize whitespace, fix formatting

validate_pdf_bytes(pdf_bytes) → (is_valid: bool, error_msg: str)
    # Validate PDF format before processing

extract_medical_keywords(text) → list[str]
    # Extract medical terms for document classification
```

**Processing Pipeline**:
1. Receive PDF bytes from Telegram
2. Validate PDF format
3. Extract text (with page limits)
4. Clean whitespace and formatting
5. Pass to LLM for medical insights extraction
6. Store in user.medical_insights

### 4. Strava OAuth Enhancement (backend/strava_auth.py)
**Purpose**: Secure OAuth 2.0 implementation with PKCE support

**Features**:
- ✅ OAuth state validation (CSRF protection)
- ✅ PKCE support (Proof Key for Authorization Code Exchange)
- ✅ Secure token exchange with Strava
- ✅ Comprehensive error handling
- ✅ Automatic onboarding backfill trigger

**Security Implementation**:
```python
class PKCEHelper:
    - generate_code_verifier() → str (43-128 chars)
    - generate_code_challenge(verifier) → str (SHA256)

validate_oauth_state(state, expected_chat_id) → bool
    # CSRF protection via state parameter
```

**OAuth Flow**:
1. User clicks "Connect Strava" from Telegram
2. Generate auth link with state=chat_id
3. User authorizes on Strava
4. Strava redirects to /auth/callback?code=XXX&state=chat_id
5. Validate state parameter matches chat_id
6. Exchange code for access/refresh tokens
7. Store tokens in StravaToken table
8. Trigger automatic activity backfill

**Error Handling**:
- Missing chat_id → 400 Bad Request
- Invalid state → Security error page
- Token exchange failure → User-friendly error
- Database error → Rollback + error message
- Strava API error → Descriptive error page

### 5. Rate Limiting
**Configuration**: 
- Telegram webhook: 60 per minute (per IP)
- Strava webhook: 60 per minute (per IP)
- Uses slowapi with get_remote_address()

**Implementation**:
```python
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@router.post("/webhook/telegram")
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def telegram_webhook(request: Request):
    ...
```

## Database Schema Support

### Activity Model (Existing)
```python
class Activity:
    strava_id: BigInteger (unique, indexed)
    user_id: Integer (foreign key)
    name: String
    type: String
    distance_km: Float
    # ... other fields
```

Duplicate detection:
```sql
SELECT * FROM activities 
WHERE user_id = ? AND strava_id = ?
```

### StravaToken Model (Existing)
```python
class StravaToken:
    user_id: Integer (foreign key)
    access_token: String
    refresh_token: String
    expires_at: Integer (unix timestamp)
    athlete_id: Integer
```

### User Model (Existing)
```python
class User:
    telegram_chat_id: String (unique)
    strava_athlete_id: String
    medical_insights: Text (stores extracted medical boundaries)
```

## Error Handling & Resilience

### Telegram Webhook
```
Missing Secret Token → 403 Forbidden
Invalid Secret Token → 403 Forbidden
Parse Error → Log + 200 OK (ack to telegram)
Celery Queue Failure → Log + 200 OK (prevent telegram retry loop)
```

### Strava Webhook
```
Invalid Signature → Log + 200 OK (prevent replay attacks)
Missing Fields → Log + 200 OK
Non-Activity Event → Log + 200 OK (ignore)
Processing Error → Log + 200 OK (background processing)
```

### OAuth
```
Missing Parameters → User-friendly HTML error
Invalid State (CSRF) → Security warning page
Token Exchange Failure → Strava error details + retry link
Database Error → Rollback + error message
Timeout → Timeout error + retry message
```

## Security Checklist

- ✅ Telegram secret token validation (prevents spoofing)
- ✅ Strava signature validation (HMAC-SHA256)
- ✅ OAuth state validation (CSRF protection)
- ✅ PKCE support (optional additional layer)
- ✅ Rate limiting (DDoS mitigation)
- ✅ Non-blocking processing (timeout protection)
- ✅ Secure error messages (no data leaks)
- ✅ Database transaction rollback on failure
- ✅ Graceful degradation (500 errors → 200 OK)

## Testing

**Test File**: tests/test_webhooks_phase4.py

**Test Coverage**:
- ✅ TelegramWebhookHandler message parsing (text, callback, document)
- ✅ StravaWebhookHandler signature validation
- ✅ PDF extraction and cleaning
- ✅ PKCE implementation
- ✅ OAuth state validation
- ✅ Medical keyword extraction
- ✅ Webhook endpoint integration

**Running Tests**:
```bash
pytest tests/test_webhooks_phase4.py -v
```

## Configuration

**Required Environment Variables**:
```
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_SECRET_TOKEN=<webhook_secret>
STRAVA_CLIENT_ID=<id>
STRAVA_CLIENT_SECRET=<secret>
STRAVA_SIGNING_SECRET=<webhook_signing_secret>
STRAVA_REDIRECT_URI=<callback_url>
```

**Settings (backend/config/settings.py)**:
```python
TELEGRAM_SECRET_TOKEN: str
STRAVA_SIGNING_SECRET: str
STRAVA_REDIRECT_URI: str
DEFAULT_RATE_LIMIT: str = "60 per minute"
```

## API Endpoints

### Telegram Webhook
```
POST /webhook/telegram
Headers: X-Telegram-Bot-Api-Secret-Token: {TELEGRAM_SECRET_TOKEN}
Body: Telegram Update JSON
Response: {"ok": true}
```

### Strava Webhook Validation
```
GET /webhook/strava?hub.challenge={challenge}
Response: {"hub.challenge": "{challenge}"}
```

### Strava Webhook Event
```
POST /webhook/strava
Headers: X-Strava-Hook-Signature: {signature}
Body: Strava Webhook JSON
Response: {"status": "received"}
```

### Strava OAuth Callback
```
GET /auth/callback?code={code}&state={chat_id}&error={error}
Response: HTML success/error page
```

### Strava OAuth Initiate (New)
```
GET /auth/strava?chat_id={chat_id}
Response: {"auth_url": "https://..."}
```

## Message Flow Diagrams

### Telegram Text Message Flow
```
User sends message
    ↓
Telegram API → POST /webhook/telegram
    ↓
Validate secret token
    ↓
Parse message (type: "text")
    ↓
Queue trigger_durable_webhook_handler
    ↓
Return 200 OK immediately
    ↓
[Async] Celery worker processes message
    ↓
Coach generates response
    ↓
Send response back to Telegram
```

### Strava Activity Event Flow
```
User uploads activity on Strava app
    ↓
Strava API → POST /webhook/strava
    ↓
Validate HMAC signature
    ↓
Check activity type and aspect (create/update)
    ↓
Check for duplicates (by strava_id)
    ↓
Queue strava_manager.handle_webhook
    ↓
Return 200 OK immediately
    ↓
[Async] Background task downloads activity data
    ↓
Store in database
    ↓
Update fitness metrics
    ↓
Generate coaching insights
```

### Strava OAuth Flow
```
User clicks "Connect Strava" in Telegram
    ↓
Telegram bot sends Strava auth link
    ↓
User authorizes on Strava (browser)
    ↓
Strava redirects to /auth/callback?code=X&state=chat_id
    ↓
Validate state parameter (CSRF check)
    ↓
Exchange code for tokens (token endpoint)
    ↓
Store tokens in StravaToken table
    ↓
Return success page to user
    ↓
[Async] Trigger trigger_onboarding_backfill
    ↓
Sync historical activities
```

### PDF Document Upload Flow
```
User uploads PDF via Telegram
    ↓
POST /webhook/telegram with document
    ↓
Validate secret token
    ↓
Parse message (type: "document")
    ↓
Download PDF from Telegram servers
    ↓
Extract text from PDF bytes
    ↓
Clean text (normalize formatting)
    ↓
Pass to LLM for medical insights
    ↓
Store in user.medical_insights
    ↓
Send confirmation to user
```

## Monitoring & Observability

**Logging**:
- All webhook requests logged with update_id/event_id
- Security violations logged with details
- Processing errors logged with full traceback
- Rate limit hits logged per IP

**Metrics to Track**:
- Webhook request count (by type: telegram/strava)
- Security validation failures
- Processing latency
- Rate limit violations
- Duplicate activity detection

**Alerts**:
- Repeated signature validation failures (possible attack)
- High error rate on webhook processing
- Rate limit exhaustion

## Production Deployment

### Verification Checklist
- ✅ Telegram webhook secret configured in .env
- ✅ Strava webhook signing secret configured
- ✅ Redis running for Celery queue
- ✅ Celery workers started
- ✅ Database migrations applied
- ✅ Rate limiting middleware enabled
- ✅ Sentry error tracking configured (optional)

### Health Check Endpoint
```
GET /health
Response includes: postgres, redis, celery_workers, openai status
```

### Webhook Registration

**Telegram** (via bot command):
```python
# Register webhook with Telegram API
POST https://api.telegram.org/bot{token}/setWebhook
  url: https://vedaactivewellness.xyz/webhook/telegram
  secret_token: {TELEGRAM_SECRET_TOKEN}
```

**Strava** (manual):
```
1. Go to Strava settings → My API Application
2. Add webhook subscription:
   URL: https://vedaactivewellness.xyz/webhook/strava
   Events: activity
```

## Known Limitations & Future Enhancements

### Current Limitations
- PKCE not yet enabled by default (commented out)
- PDF extraction limited to text-based PDFs (no image-based scans)
- Rate limiting per IP (not per user)
- No webhook retry logic on processing failure

### Future Enhancements
- [ ] Enable PKCE by default (requires server-side storage)
- [ ] Add OCR support for image-based PDFs
- [ ] Per-user rate limiting with Redis
- [ ] Webhook retry queue with exponential backoff
- [ ] Signature validation caching
- [ ] Metrics export to Prometheus
- [ ] Webhook delivery status dashboard
- [ ] Signature key rotation support

## Troubleshooting

### "Invalid Telegram webhook token"
- Verify TELEGRAM_SECRET_TOKEN in .env matches Telegram configuration
- Check webhook registration with Telegram API

### "Invalid Strava signature"
- Verify STRAVA_SIGNING_SECRET in .env matches Strava app settings
- Check that webhook body is not modified before validation

### "OAuth state validation failed"
- Ensure state parameter in callback matches original chat_id
- Check for URL encoding issues in redirect

### "Duplicate activity detected"
- Expected behavior for Strava "update" events
- Check that strava_id is correctly stored

## References

- [Telegram Bot API Webhook Documentation](https://core.telegram.org/bots/api)
- [Strava Developer API](https://developers.strava.com/)
- [OAuth 2.0 PKCE (RFC 7636)](https://tools.ietf.org/html/rfc7636)
- [HMAC-SHA256 Implementation](https://tools.ietf.org/html/rfc2104)

---

**Phase 4 Status**: ✅ COMPLETE
**Last Updated**: 2025-01-11
**Version**: 4.1.0
