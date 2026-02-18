# Email Signup for MyMemex Website

## Architecture

```
mymemex.io (static Astro)
    ↓ POST /api/subscribe
Cloudflare Worker
    ↓
Zoho Mail (SMTP or API)
    ↓
Email to: your-email@example.com
```

---

## Option A: Cloudflare Worker (Recommended)

### 1. Create Worker

**File: `workers/subscribe.js`**

```javascript
export default {
  async fetch(request, env) {
    // Only allow POST
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
    }

    // CORS headers
    const corsHeaders = {
      'Access-Control-Allow-Origin': 'https://mymemex.io',
      'Access-Control-Allow-Methods': 'POST',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    // Handle preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      const { email } = await request.json();

      // Validate email
      if (!email || !email.includes('@')) {
        return new Response(
          JSON.stringify({ error: 'Invalid email' }),
          { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }

      // Cloudflare Turnstile verification (bot protection)
      const turnstileToken = request.headers.get('cf-turnstile-response');
      if (env.TURNSTILE_SECRET_KEY) {
        const turnstileValid = await verifyTurnstile(turnstileToken, env.TURNSTILE_SECRET_KEY);
        if (!turnstileValid) {
          return new Response(
            JSON.stringify({ error: 'Bot verification failed' }),
            { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
          );
        }
      }

      // Send email via Zoho
      await sendEmail({
        to: env.NOTIFICATION_EMAIL,
        from: env.FROM_EMAIL,
        subject: 'New MyMemex Signup',
        body: `New signup: ${email}`,
        smtp: {
          host: 'smtp.zoho.com',
          port: 587,
          user: env.ZOHO_USER,
          pass: env.ZOHO_PASSWORD,
        }
      });

      // Also could store in KV for later
      if (env.SUBSCRIBERS) {
        await env.SUBSCRIBERS.put(`email:${Date.now()}`, email);
      }

      return new Response(
        JSON.stringify({ success: true, message: 'Thanks for signing up!' }),
        { status: 200, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );

    } catch (error) {
      console.error('Error:', error);
      return new Response(
        JSON.stringify({ error: 'Something went wrong' }),
        { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }
  }
};

async function verifyTurnstile(token, secret) {
  const response = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `secret=${secret}&response=${token}`,
  });
  const data = await response.json();
  return data.success;
}

async function sendEmail({ to, from, subject, body, smtp }) {
  // Use Mailchannels (free on Cloudflare) or external service
  // Option 1: Mailchannels (free for Cloudflare domains)
  const response = await fetch('https://api.mailchannels.net/tx/v1/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      personalizations: [{ to: [{ email: to }] }],
      from: { email: from },
      subject,
      content: [{ type: 'text/plain', value: body }],
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to send email');
  }
}
```

### 2. Deploy Worker

```bash
# Install Wrangler
npm install -g wrangler

# Login to Cloudflare
wrangler login

# Create worker
cd ~/code/mymemex-worker
wrangler init subscribe

# Copy the code above to src/index.js

# Set secrets
wrangler secret put NOTIFICATION_EMAIL
wrangler secret put FROM_EMAIL
wrangler secret put TURNSTILE_SECRET_KEY

# Deploy
wrangler deploy
```

### 3. Update Website Form

**Add Turnstile widget:**

```html
<!-- In <head> -->
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>

<!-- In form -->
<div class="cf-turnstile" data-sitekey="YOUR_SITE_KEY"></div>
```

**Update form action:**

```html
<form id="signup-form">
  <input type="email" name="email" required placeholder="your@email.com" />
  <div class="cf-turnstile" data-sitekey="YOUR_SITE_KEY"></div>
  <button type="submit">Notify Me</button>
</form>

<script>
document.getElementById('signup-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = e.target.email.value;
  const turnstileResponse = document.querySelector('[name="cf-turnstile-response"]')?.value;

  const response = await fetch('https://subscribe.YOUR-SUBDOMAIN.workers.dev', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });

  const data = await response.json();
  if (data.success) {
    alert('Thanks for signing up!');
    e.target.reset();
  } else {
    alert(data.error || 'Something went wrong');
  }
});
</script>
```

---

## Option B: Node.js Server

If you prefer Node.js:

### 1. Create Server

**File: `server.js`**

```javascript
import express from 'express';
import nodemailer from 'nodemailer';
import { fileURLToPath } from 'url';
import { join, dirname } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const app = express();

// Middleware
app.use(express.json());
app.use(express.static(join(__dirname, 'dist')));

// Email transporter (Zoho SMTP)
const transporter = nodemailer.createTransport({
  host: 'smtp.zoho.com',
  port: 587,
  secure: false,
  auth: {
    user: process.env.ZOHO_USER,
    pass: process.env.ZOHO_PASSWORD,
  },
});

// Subscribe endpoint
app.post('/api/subscribe', async (req, res) => {
  const { email } = req.body;

  if (!email || !email.includes('@')) {
    return res.status(400).json({ error: 'Invalid email' });
  }

  try {
    // Send notification email
    await transporter.sendMail({
      from: process.env.FROM_EMAIL,
      to: process.env.NOTIFICATION_EMAIL,
      subject: 'New MyMemex Signup',
      text: `New signup: ${email}`,
      html: `<p>New signup: <strong>${email}</strong></p>`,
    });

    // Send confirmation to user (optional)
    await transporter.sendMail({
      from: process.env.FROM_EMAIL,
      to: email,
      subject: 'Welcome to MyMemex!',
      text: 'Thanks for signing up! We\'ll let you know when MyMemex launches.',
    });

    res.json({ success: true, message: 'Thanks for signing up!' });
  } catch (error) {
    console.error('Email error:', error);
    res.status(500).json({ error: 'Something went wrong' });
  }
});

// Serve Astro static files
app.get('*', (req, res) => {
  res.sendFile(join(__dirname, 'dist', 'index.html'));
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
```

### 2. Deploy Options

| Platform | Free Tier | Notes |
|----------|-----------|-------|
| Railway | $5 credit/mo | Easy deploy |
| Render | 750 hrs/mo | Free tier available |
| Fly.io | 3 VMs free | Good for small apps |
| Your server | Free | You already have server-tiny-1 |

### 3. Dockerfile

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --production
COPY dist ./dist
COPY server.js .
EXPOSE 3000
CMD ["node", "server.js"]
```

---

## Recommendation

**Go with Option A (Cloudflare Worker)** because:

1. You already use Cloudflare for the domain
2. Free tier is generous (100k requests/day)
3. No server to maintain
4. Turnstile is built-in bot protection
5. Can store emails in Cloudflare KV

**But Option B (Node.js)** is good if:
- You want full control
- You already have a server
- You want to add more features later

---

## Files to Create

Choose one:

### Option A:
- `workers/subscribe.js` - Cloudflare Worker
- Update `index.astro` - Add Turnstile, update form

### Option B:
- `server.js` - Express server
- `package.json` - Add dependencies
- `Dockerfile` - Container

---

Which option do you prefer?
