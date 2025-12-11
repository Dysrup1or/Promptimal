# Stripe Integration Setup Guide

## Overview

Promptly now supports Stripe subscription billing for Pro tier upgrades ($9.99/month).

## ⚠️ IMPORTANT: Webhook Deployment

The Stripe webhook endpoint (`/api/stripe/webhook`) runs on the FastAPI server (`api_server.py`), which is **separate** from the Streamlit app. For production with webhooks, you have two options:

### Option A: Two Railway Services (Recommended)
1. Deploy the main Streamlit app (existing service)
2. Create a second Railway service for the API server:
   - Use `uvicorn api_server:app --host 0.0.0.0 --port $PORT`
   - Set webhook URL to this service's domain

### Option B: Single Service with Both (Advanced)
Use `start_services.py` which runs both services, but note that Railway only exposes one port externally. You'd need an internal service mesh or reverse proxy.

### Option C: Use Stripe Checkout Without Webhooks (Simplest)
The checkout flow works without webhooks - users are redirected back with `?upgrade=success`. You can manually sync tiers via admin CLI until webhooks are configured.

## Required Environment Variables

Add these to your Railway project (or `.env` for local testing):

```bash
# Stripe API Keys (from your Stripe Dashboard)
STRIPE_SECRET_KEY=sk_live_xxx          # Your Stripe secret key
STRIPE_PUBLISHABLE_KEY=pk_live_xxx     # Your Stripe publishable key

# Stripe Product Configuration
STRIPE_PRO_PRICE_ID=price_xxx          # Price ID for Pro plan (see below)

# Stripe Webhook Secret (generated when setting up webhook)
STRIPE_WEBHOOK_SECRET=whsec_xxx        # Webhook signing secret

# App URL (for redirect after checkout)
APP_URL=https://your-app.railway.app   # Your production URL
```

## Step 1: Create a Product and Price in Stripe

1. Go to [Stripe Dashboard](https://dashboard.stripe.com) → Products
2. Click **+ Add Product**
3. Fill in:
   - **Name:** Promptly Pro
   - **Description:** 500 optimizations/month, priority processing
4. Under Pricing:
   - Select **Recurring**
   - Price: `$9.99`
   - Billing period: **Monthly**
5. Click **Save product**
6. Copy the **Price ID** (starts with `price_`) → Set as `STRIPE_PRO_PRICE_ID`

## Step 2: Configure the Customer Portal

1. Go to [Stripe Dashboard](https://dashboard.stripe.com) → Settings → Customer Portal
2. Enable the following features:
   - ✅ Customers can update their payment methods
   - ✅ Customers can cancel subscriptions
   - ✅ Show billing history
3. Set the default return URL to your app URL
4. Save changes

## Step 3: Set Up Webhooks

1. Go to [Stripe Dashboard](https://dashboard.stripe.com) → Developers → Webhooks
2. Click **+ Add endpoint**
3. Enter your endpoint URL: `https://your-app.railway.app/api/stripe/webhook`
4. Select events to listen for:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
5. Click **Add endpoint**
6. Copy the **Signing secret** (starts with `whsec_`) → Set as `STRIPE_WEBHOOK_SECRET`

## Step 4: Deploy with Environment Variables

### Railway Deployment

1. Go to your Railway project → Variables
2. Add each environment variable:
   - `STRIPE_SECRET_KEY`
   - `STRIPE_PUBLISHABLE_KEY`
   - `STRIPE_PRO_PRICE_ID`
   - `STRIPE_WEBHOOK_SECRET`
   - `APP_URL` (your Railway public domain)
3. Redeploy

### Local Testing

1. Create a `.env` file:
```bash
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_PUBLISHABLE_KEY=pk_test_xxx
STRIPE_PRO_PRICE_ID=price_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
APP_URL=http://localhost:8501
```

2. For local webhook testing, use [Stripe CLI](https://stripe.com/docs/stripe-cli):
```bash
stripe listen --forward-to localhost:8000/api/stripe/webhook
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stripe/webhook` | POST | Stripe webhook receiver |
| `/api/stripe/create-checkout-session` | POST | Create checkout session |
| `/api/stripe/create-portal-session` | POST | Create customer portal session |
| `/api/stripe/subscription-status/{user_id}` | GET | Get subscription status |

## Database Tables

Two new tables are created automatically:

### `stripe_customers`
- `user_id` - Reference to users table
- `stripe_customer_id` - Stripe customer ID

### `subscriptions`
- `user_id` - Reference to users table
- `stripe_subscription_id` - Stripe subscription ID
- `status` - active, canceled, past_due, etc.
- `plan` - pro, enterprise
- `current_period_end` - When current period ends
- `cancel_at_period_end` - If scheduled to cancel

## How It Works

1. **User clicks "Subscribe Now"** in the upgrade dialog
2. **Checkout session created** via `create_checkout_session()`
3. **User completes payment** on Stripe's hosted checkout page
4. **Stripe sends webhook** to `/api/stripe/webhook`
5. **`checkout.session.completed`** event triggers tier upgrade
6. **User redirected back** with `?upgrade=success` parameter
7. **App refreshes user data** to show Pro tier

## Tier Limits

| Tier | Monthly Limit | Cost |
|------|---------------|------|
| Free | 50 requests | $0 |
| Pro | 500 requests | $9.99/month |
| Enterprise | Unlimited | Contact sales |

## Troubleshooting

### "Stripe is not configured" error
- Check that `STRIPE_SECRET_KEY` and `STRIPE_PRO_PRICE_ID` are set
- Verify the API key is valid (test with `stripe customers list`)

### Webhook not working
- Verify the webhook URL is publicly accessible
- Check the webhook secret matches
- Look at Stripe Dashboard → Developers → Webhooks → Logs

### User tier not updating
- Check webhook logs for errors
- Verify `stripe_customers` table has the user mapping
- Check `subscriptions` table for status

## Security Notes

⚠️ **NEVER commit API keys to version control**
- Use environment variables only
- The `.env` file is gitignored
- Railway stores variables securely
