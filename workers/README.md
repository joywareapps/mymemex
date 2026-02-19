# MyMemex Subscribe Worker

Cloudflare Worker for handling email signups on mymemex.io.

## Features

- ✅ Email validation
- ✅ Cloudflare Turnstile bot protection
- ✅ Stores emails in Cloudflare KV (optional)
- ✅ Sends notification via Mailchannels (free)
- ✅ CORS support

## Quick Start

### 1. Install Wrangler

```bash
npm install -g wrangler
```

### 2. Login to Cloudflare

```bash
wrangler login
```

### 3. Create KV Namespace (optional but recommended)

```bash
cd ~/code/mymemex/workers
wrangler kv:namespace create SUBSCRIBERS
```

Copy the `id` from the output and update `wrangler.toml`:

```toml
[[kv_namespaces]]
binding = "SUBSCRIBERS"
id = "your-kv-namespace-id-here"
```

### 4. Set Secrets

```bash
# Your email to receive notifications
wrangler secret put NOTIFICATION_EMAIL
# Enter: your-email@example.com

# From email (must be verified on your domain)
wrangler secret put FROM_EMAIL
# Enter: noreply@mymemex.io

# Turnstile secret key (get from Cloudflare dashboard)
wrangler secret put TURNSTILE_SECRET_KEY
# Enter: 0x4AAAAAAA...
```

### 5. Get Turnstile Keys

1. Go to https://dash.cloudflare.com/?to=/:account/turnstile
2. Add a site: `mymemex.io`
3. Copy:
   - **Site Key** → Update in `index.astro` (data-sitekey)
   - **Secret Key** → Set as `TURNSTILE_SECRET_KEY`

### 6. Deploy

```bash
wrangler deploy
```

### 7. Configure Route

After deployment, add the route in Cloudflare dashboard:

1. Go to your domain → Workers Routes
2. Add route: `mymemex.io/api/subscribe*`
3. Select worker: `mymemex-subscribe`

Or add to `wrangler.toml`:

```toml
routes = [
  { pattern = "mymemex.io/api/subscribe", zone_name = "mymemex.io" }
]
```

Then deploy again.

## Update Website

After deploying the worker:

1. Get your Turnstile **Site Key** from Cloudflare dashboard
2. Update `website/src/pages/index.astro`:
   ```html
   <div class="cf-turnstile" data-sitekey="YOUR_SITE_KEY" data-theme="dark"></div>
   ```
3. Rebuild and deploy website:
   ```bash
   cd ~/code/mymemex/website
   ./update-website-mymemex.sh
   ```

## Testing

### Local Development

```bash
wrangler dev
```

Then test with curl:

```bash
curl -X POST http://localhost:8787 \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","turnstileToken":"test"}'
```

### Production Test

```bash
curl -X POST https://mymemex.io/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com"}'
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NOTIFICATION_EMAIL` | Yes | Email to receive signup notifications |
| `FROM_EMAIL` | Yes | Sender email (must be verified) |
| `TURNSTILE_SECRET_KEY` | Recommended | Turnstile secret for bot protection |
| `ALLOWED_ORIGIN` | No | CORS origin (default: https://mymemex.io) |

## KV Storage

If KV is configured, emails are stored with key format:
- Key: `email:bob@example.com`
- Value: `{"email":"bob@example.com","timestamp":"2026-02-18T...","source":"mymemex.io"}`

View stored emails:
```bash
wrangler kv:key list --namespace-id=SUBSCRIBERS
```

## Mailchannels Setup

Mailchannels is free for Cloudflare domains. Requirements:

1. Add SPF record to your domain:
   ```
   v=spf1 include:relay.mailchannels.net ~all
   ```

2. Add domain lock:
   ```
   _mailchannels.mymemex.io TXT "v=mc1 cfid=YOUR_CF_ID"
   ```

See: https://support.mailchannels.com/hc/en-us/articles/200262610-SPF-Records

## Troubleshooting

### "Bot verification failed"
- Check TURNSTILE_SECRET_KEY is set correctly
- Verify Site Key in website matches Cloudflare

### CORS errors
- Check ALLOWED_ORIGIN matches your domain
- Verify route is configured correctly

### Email not sending
- Check Mailchannels SPF/DNS records
- Verify FROM_EMAIL is correct
- Check Cloudflare logs: `wrangler tail`

## Files

```
workers/
├── subscribe.js      # Worker code
├── wrangler.toml     # Configuration
└── README.md         # This file
```
