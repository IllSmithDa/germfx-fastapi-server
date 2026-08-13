# GermFx Paddle Billing + Webhook Setup Guide

This document explains how to test Paddle Billing locally with Cloudflare Tunnel, how to configure Paddle sandbox webhooks, and how production should work when the FastAPI server is hosted on Render.

## 1. Overview

GermFx uses a provider-agnostic subscription model.

The payment provider can be:

```txt
paddle
stripe
google_play
app_store
manual
```

The app should not care where the subscription came from. The app should only care about the backend entitlement result from:

```txt
GET /api/auth/me
```

Expected subscription shape:

```json
{
  "subscription": {
    "plan": "plus",
    "status": "active",
    "provider": "paddle",
    "is_plus": true,
    "is_active_paid": true,
    "current_period_start": "2026-06-18T00:00:00+00:00",
    "current_period_end": "2026-07-18T00:00:00+00:00",
    "cancel_at_period_end": false
  },
  "is_plus": true,
  "subscription_plan": "plus",
  "subscription_status": "active"
}
```

The payment flow is:

```txt
User clicks Subscribe on Next.js pricing page
→ Next.js calls FastAPI /api/billing/checkout
→ FastAPI creates Paddle checkout transaction
→ User completes Paddle checkout
→ Paddle sends webhook to FastAPI
→ FastAPI verifies Paddle-Signature
→ FastAPI updates user_subscriptions
→ /auth/me returns is_plus: true
```

## 2. Why Cloudflare Tunnel is needed locally

Paddle cannot call your local machine directly.

This does not work from Paddle:

```txt
http://localhost:8000/api/billing/webhook/paddle
```

From Paddle’s server, `localhost` means Paddle’s own machine, not your laptop.

Cloudflare Tunnel gives Paddle a temporary public HTTPS URL that forwards traffic to your local FastAPI server:

```txt
Paddle
→ https://random-name.trycloudflare.com/api/billing/webhook/paddle
→ localhost:8000/api/billing/webhook/paddle
```

A tunnel is only needed when testing against your public HTTPS URL that forwards traffic to your local FastAPI server:

```txt
Paddle
→ https://random-name.trycloudflare.com/api/billing/webhook/paddle
→ localhost:8000/api/billing/webhook/paddle
```

A tunnel is only needed when testing against your local computer.

For production, you do not need Cloudflare Tunnel if your backend is already hosted publicly on Render.

## 3. Local testing architecture

Local testing should look like this:

```txt
Next.js frontend:
http://localhost:3000

FastAPI backend:
http://localhost:8000

Cloudflare Tunnel:
https://random-name.trycloudflare.com

Paddle sandbox webhook URL:
https://random-name.trycloudflare.com/api/billing/webhook/paddle
```

## 4. Production architecture

Production should look like this:

```txt
Next.js frontend:
https://your-nextjs-site.com

FastAPI backend on Render:
https://your-render-api.onrender.com

Paddle live webhook URL:
https://your-render-api.onrender.com/api/billing/webhook/paddle
```

Or, if you later use a custom API domain:

```txt
https://api.GermFx.app/api/billing/webhook/paddle
```

In production, Paddle sends webhooks directly to the public Render API route. No tunnel is needed.

## 5. Paddle information you need

Create these in Paddle Sandbox first:

```txt
1. Sandbox account
2. Product: GermFx Plus
3. Recurring monthly price for GermFx Plus
4. Paddle sandbox API key
5. Paddle sandbox price ID
6. Paddle notification destination
7. Paddle webhook endpoint secret
```

You will need these values:

```env
PADDLE_API_KEY=pdl_sdbx_...
PADDLE_PLUS_PRICE_ID=pri_...
PADDLE_WEBHOOK_SECRET=...
```

The webhook secret is specific to the notification destination. Sandbox and live Paddle environments are separate, so sandbox keys, products, prices, customers, and webhook secrets are not shared with live mode.

## 6. Suggested Paddle app description

Use this for Paddle or payment-provider product/service description fields:

```txt
GermFx is a health-tracking application that helps users track medications, log symptoms, review medication details, monitor recalls, save health-related items, and generate reports. Paid subscriptions provide access to expanded tracking, advanced reports, exports, and premium account features.
```

## 7. Backend environment variables for local sandbox testing

Use this in your FastAPI `.env` during local Paddle sandbox testing:

```env
BILLING_PROVIDER=paddle

HOST_URL=http://localhost:3000
API_BASE_URL=http://localhost:8000

PADDLE_ENVIRONMENT=sandbox
PADDLE_API_KEY=pdl_sdbx_your_api_key_here
PADDLE_PLUS_PRICE_ID=pri_your_sandbox_price_id_here
PADDLE_CHECKOUT_URL=http://localhost:3000/billing/success
PADDLE_WEBHOOK_SECRET=your_paddle_notification_destination_secret_here
PADDLE_WEBHOOK_TOLERANCE_SECONDS=300
```

Notes:

```txt
HOST_URL
→ where the user returns after checkout

API_BASE_URL
→ your API base URL

PADDLE_ENVIRONMENT=sandbox
→ uses Paddle sandbox API

PADDLE_API_KEY
→ Paddle sandbox API key

PADDLE_PLUS_PRICE_ID
→ Paddle sandbox recurring price ID

PADDLE_WEBHOOK_SECRET
→ secret key from the Paddle sandbox notification destination
```

## 8. Backend environment variables for production on Render

Use this in Render production environment variables:

```env
BILLING_PROVIDER=paddle

HOST_URL=https://your-nextjs-site.com
API_BASE_URL=https://your-render-api.onrender.com

PADDLE_ENVIRONMENT=production
PADDLE_API_KEY=pdl_live_your_api_key_here
PADDLE_PLUS_PRICE_ID=pri_your_live_price_id_here
PADDLE_CHECKOUT_URL=https://your-nextjs-site.com/billing/success
PADDLE_WEBHOOK_SECRET=your_live_paddle_notification_destination_secret_here
PADDLE_WEBHOOK_TOLERANCE_SECONDS=300
```

Important:

```txt
Do not mix sandbox and live values.

Sandbox API key + sandbox price ID + sandbox webhook secret
→ local or staging only

Live API key + live price ID + live webhook secret
→ production only
```

## 9. Local test setup commands

Open three separate terminals.

### Terminal 1: run FastAPI

```powershell
cd C:\Users\thebl\OneDrive\Documents\Projects\side-fx-fastserver

uvicorn app.main:app --reload --port 8000
```

Confirm the backend is available:

```txt
http://localhost:8000
```

### Terminal 2: run Next.js

```powershell
cd C:\Users\thebl\OneDrive\Documents\Projects\your-nextjs-app

npm run dev
```

Confirm the frontend is available:

```txt
http://localhost:3000
```

### Terminal 3: run Cloudflare Tunnel

Run this in standalone PowerShell if VS Code terminal does not recognize `cloudflared`:

```powershell
cloudflared tunnel --url http://localhost:8000
```

Cloudflare will print a public URL like:

```txt
https://random-name.trycloudflare.com
```

Your Paddle sandbox webhook URL becomes:

```txt
https://random-name.trycloudflare.com/api/billing/webhook/paddle
```

Keep this terminal open while testing. If you close it, the tunnel stops. If you restart it, the URL may change.

## 10. If VS Code cannot find cloudflared

If this works in standalone PowerShell but not VS Code, it is likely a PATH issue.

Check whether WinGet installed the command:

```powershell
winget list Cloudflare.cloudflared
```

If it is installed but not found:

```powershell
where.exe cloudflared
Get-Command cloudflared
```

If those fail, run the tunnel from standalone PowerShell for now.

You can also check WinGet links:

```powershell
$wingetLinks = "$env:LOCALAPPDATA\Microsoft\WinGet\Links"

Test-Path "$wingetLinks\cloudflared.exe"
```

If it returns `True`, run directly:

```powershell
& "$env:LOCALAPPDATA\Microsoft\WinGet\Links\cloudflared.exe" tunnel --url http://localhost:8000
```

To add WinGet links to user PATH:

```powershell
$wingetLinks = "$env:LOCALAPPDATA\Microsoft\WinGet\Links"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")

if ($userPath -notlike "*$wingetLinks*") {
  [Environment]::SetEnvironmentVariable(
    "Path",
    "$userPath;$wingetLinks",
    "User"
  )
}
```

Then fully close and reopen VS Code.

## 11. Paddle sandbox notification destination setup

In Paddle Sandbox:

```txt
1. Go to Developer Tools.
2. Open Notifications.
3. Create a new notification destination.
4. Set destination type to URL.
5. Use the Cloudflare Tunnel webhook URL.
```

Example local webhook URL:

```txt
https://random-name.trycloudflare.com/api/billing/webhook/paddle
```

Subscribe to these events for the first version:

```txt
subscription.created
subscription.activated
subscription.updated
subscription.canceled
subscription.past_due
subscription.paused
subscription.resumed
subscription.trialing
transaction.completed
transaction.paid
transaction.payment_failed
```

After creating the notification destination, copy its secret key and set:

```env
PADDLE_WEBHOOK_SECRET=your_destination_secret_here
```

Restart FastAPI after updating `.env`.

## 12. Backend route expectations

Your FastAPI billing routes should be mounted like this:

```txt
POST /api/billing/checkout
POST /api/billing/webhook/paddle
```

The checkout route should require authentication.

The Paddle webhook route should not require your app auth because Paddle is calling it. It should verify the Paddle webhook signature instead.

Expected checkout request:

```http
POST /api/billing/checkout
Content-Type: application/json
Authorization: Bearer ACCESS_TOKEN
```

Body:

```json
{
  "plan": "plus",
  "provider": "paddle"
}
```

Expected response:

```json
{
  "provider": "paddle",
  "plan": "plus",
  "checkout_url": "https://..."
}
```

## 13. Paddle webhook security requirements

The webhook route must verify that the request came from Paddle.

The server should:

```txt
1. Read the raw request body.
2. Read the Paddle-Signature header.
3. Verify the signature using PADDLE_WEBHOOK_SECRET.
4. Only parse JSON after signature verification.
5. Reject invalid signatures.
```

Do not modify, reformat, or parse the request body before verification.

## 14. How to test the full local checkout flow

Start all three local terminals:

```txt
1. FastAPI on localhost:8000
2. Next.js on localhost:3000
3. Cloudflare Tunnel forwarding to localhost:8000
```

Then:

```txt
1. Update Paddle sandbox notification destination with the current tunnel URL.
2. Restart FastAPI after setting PADDLE_WEBHOOK_SECRET.
3. Log into GermFx locally.
4. Open the pricing page.
5. Click Subscribe.
6. Confirm the app calls /api/billing/checkout.
7. Confirm Paddle checkout opens.
8. Complete sandbox checkout.
9. Watch FastAPI logs for POST /api/billing/webhook/paddle.
10. Confirm user_subscriptions updates.
11. Call /api/auth/me and verify is_plus is true.
```

## 15. Database checks

After checkout and webhook delivery, check:

```sql
SELECT
  user_id,
  plan,
  status,
  provider,
  provider_customer_id,
  provider_subscription_id,
  provider_transaction_id,
  current_period_start,
  current_period_end,
  cancel_at_period_end,
  updated_at
FROM user_subscriptions
ORDER BY updated_at DESC;
```

Expected successful result:

```txt
plan = plus
status = active
provider = paddle
```

Also check webhook event idempotency table if you added it:

```sql
SELECT
  provider,
  event_id,
  event_type,
  processed_at
FROM billing_webhook_events
ORDER BY processed_at DESC;
```

## 16. Confirm /auth/me subscription status

Call:

```txt
GET /api/auth/me
```

Expected:

```json
{
  "subscription": {
    "plan": "plus",
    "status": "active",
    "provider": "paddle",
    "is_plus": true,
    "is_active_paid": true
  },
  "is_plus": true,
  "subscription_plan": "plus",
  "subscription_status": "active"
}
```

If this still returns `is_plus: false`, check:

```txt
1. Did Paddle send the webhook?
2. Did the webhook pass signature verification?
3. Did user_subscriptions update?
4. Does the User model have subscription relationship?
5. Does user_has_plus check plan and status correctly?
```

## 17. Common local errors

### Paddle webhook returns 404

Likely wrong URL.

Confirm Paddle uses:

```txt
https://random-name.trycloudflare.com/api/billing/webhook/paddle
```

not:

```txt
https://random-name.trycloudflare.com/billing/webhook/paddle
```

Also confirm FastAPI mounted the billing router under `/api/billing`.

### No request appears in FastAPI logs

Likely causes:

```txt
Cloudflare Tunnel terminal is closed.
Paddle notification destination still has an old tunnel URL.
Tunnel points to the wrong port.
FastAPI is not running.
```

### Tunnel points to Next.js instead of FastAPI

Wrong:

```powershell
cloudflared tunnel --url http://localhost:3000
```

Correct:

```powershell
cloudflared tunnel --url http://localhost:8000
```

Paddle webhook must hit FastAPI, not Next.js.

### Invalid Paddle signature

Likely causes:

```txt
PADDLE_WEBHOOK_SECRET is wrong.
Using live secret for sandbox webhook.
Using sandbox secret for live webhook.
The server parsed or modified the body before verification.
The Paddle-Signature header is missing.
```

### Webhook timestamp outside tolerance

Likely causes:

```txt
Computer clock is wrong.
PADDLE_WEBHOOK_TOLERANCE_SECONDS is too strict.
Webhook replay is too old.
```

For local testing, use:

```env
PADDLE_WEBHOOK_TOLERANCE_SECONDS=300
```

### Checkout creates pending subscription but never active

Likely causes:

```txt
Checkout route worked, but webhook did not.
Paddle notification destination is misconfigured.
Webhook failed signature verification.
Webhook event did not include user_id custom_data.
Webhook handler did not map event type to active status.
```

## 18. Can Render be used for testing instead of a tunnel?

Yes.

A tunnel is only needed when Paddle must reach your laptop.

You can also test using a Render backend if:

```txt
1. Render has Paddle sandbox environment variables.
2. Render points to a test/staging database.
3. Paddle sandbox notification destination points to Render.
```

Example sandbox Render webhook URL:

```txt
https://your-render-test-api.onrender.com/api/billing/webhook/paddle
```

This is closer to production, but slower to debug because each backend code change requires redeploying.

Recommended development flow:

```txt
Local code debugging:
Cloudflare Tunnel → local FastAPI

Staging/sandbox test:
Paddle sandbox → Render staging API

Production:
Paddle live → Render production API
```

## 19. Production Paddle setup with Render

In production, do not use the temporary Cloudflare tunnel.

Use the public Render API route.

Example:

```txt
https://side-fx-fastserver.onrender.com/api/billing/webhook/paddle
```

In Paddle live mode:

```txt
1. Create live Product: GermFx Plus.
2. Create live recurring monthly Price.
3. Create live API key.
4. Create live notification destination.
5. Set destination URL to Render webhook URL.
6. Copy live notification destination secret.
7. Set Render production env vars.
8. Redeploy FastAPI.
```

Render production env vars:

```env
BILLING_PROVIDER=paddle

HOST_URL=https://your-nextjs-site.com
API_BASE_URL=https://side-fx-fastserver.onrender.com

PADDLE_ENVIRONMENT=production
PADDLE_API_KEY=pdl_live_your_api_key_here
PADDLE_PLUS_PRICE_ID=pri_your_live_price_id_here
PADDLE_CHECKOUT_URL=https://your-nextjs-site.com/billing/success
PADDLE_WEBHOOK_SECRET=your_live_destination_secret_here
PADDLE_WEBHOOK_TOLERANCE_SECONDS=300
```

## 20. Important production reminders

Keep sandbox and live separate:

```txt
Sandbox:
PADDLE_ENVIRONMENT=sandbox
pdl_sdbx API key
sandbox price ID
sandbox webhook secret
test/staging DB

Production:
PADDLE_ENVIRONMENT=production
pdl_live API key
live price ID
live webhook secret
production DB
```

Do not require JWT auth on the webhook route. Paddle cannot log into your app.

Do verify Paddle-Signature on every webhook request.

Do make webhook handling idempotent so duplicate Paddle delivery does not cause duplicate state changes.

Do not mark a user as subscribed just because they returned to `/billing/success`. The webhook should be the source of truth.

## 21. Recommended next implementation steps

```txt
1. Confirm UserSubscription model has provider-agnostic fields.
2. Confirm /auth/me returns subscription and is_plus.
3. Confirm /api/billing/checkout creates Paddle checkout URL.
4. Configure Paddle sandbox notification destination with Cloudflare tunnel URL.
5. Complete sandbox checkout.
6. Confirm webhook updates user_subscriptions.
7. Confirm account page shows Plus active.
8. Deploy to Render staging or production.
9. Replace Paddle webhook URL with Render API URL.
10. Switch to live Paddle keys only when ready for real payments.
```

## 22. Quick command summary

Run local backend:

```powershell
uvicorn app.main:app --reload --port 8000
```

Run frontend:

```powershell
npm run dev
```

Run tunnel:

```powershell
cloudflared tunnel --url http:/localhost:8000
```

Paddle sandbox webhook URL:

```txt
https://random-name.trycloudflare.com/api/billing/webhook/paddle
```

Production Paddle webhook URL on Render:

```txt
https://side-fx-fastserver.onrender.com/api/billing/webhook/paddle
```
