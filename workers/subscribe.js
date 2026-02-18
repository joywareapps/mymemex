/**
 * MyMemex Email Signup Worker
 * Handles newsletter signups from mymemex.io
 * 
 * Deploy: wrangler deploy
 * Secrets: wrangler secret put TURNSTILE_SECRET_KEY
 *          wrangler secret put NOTIFICATION_EMAIL
 */

export default {
  async fetch(request, env, ctx) {
    // CORS headers - adjust origin for production
    const corsHeaders = {
      'Access-Control-Allow-Origin': env.ALLOWED_ORIGIN || 'https://mymemex.io',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    // Handle preflight request
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    // Only allow POST
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
    }

    try {
      const body = await request.json();
      const { email, turnstileToken } = body;

      // Validate email
      if (!email || !isValidEmail(email)) {
        return jsonResponse(
          { success: false, error: 'Please enter a valid email address' },
          400,
          corsHeaders
        );
      }

      // Verify Turnstile (bot protection)
      if (env.TURNSTILE_SECRET_KEY) {
        const turnstileValid = await verifyTurnstile(turnstileToken, env.TURNSTILE_SECRET_KEY, request);
        if (!turnstileValid) {
          return jsonResponse(
            { success: false, error: 'Bot verification failed. Please try again.' },
            400,
            corsHeaders
          );
        }
      }

      // Check for duplicate (if KV is bound)
      if (env.SUBSCRIBERS) {
        const existing = await env.SUBSCRIBERS.get(`email:${email}`);
        if (existing) {
          return jsonResponse(
            { success: true, message: 'You\'re already signed up! We\'ll keep you updated.' },
            200,
            corsHeaders
          );
        }
      }

      // Store in KV (if available)
      if (env.SUBSCRIBERS) {
        const timestamp = new Date().toISOString();
        await env.SUBSCRIBERS.put(`email:${email}`, JSON.stringify({
          email,
          timestamp,
          source: 'mymemex.io'
        }));
      }

      // Send notification email
      if (env.NOTIFICATION_EMAIL) {
        await sendNotification(email, env);
      }

      // Success response
      return jsonResponse(
        { 
          success: true, 
          message: 'Thanks for signing up! We\'ll notify you when MyMemex launches.' 
        },
        200,
        corsHeaders
      );

    } catch (error) {
      console.error('Signup error:', error);
      return jsonResponse(
        { success: false, error: 'Something went wrong. Please try again later.' },
        500,
        corsHeaders
      );
    }
  }
};

/**
 * Validate email format
 */
function isValidEmail(email) {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Verify Cloudflare Turnstile token
 */
async function verifyTurnstile(token, secret, request) {
  if (!token) return false;
  
  try {
    const formData = new URLSearchParams();
    formData.append('secret', secret);
    formData.append('response', token);
    formData.append('remoteip', request.headers.get('CF-Connecting-IP') || '');

    const response = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
      method: 'POST',
      body: formData,
    });

    const result = await response.json();
    return result.success === true;
  } catch (error) {
    console.error('Turnstile verification error:', error);
    return false;
  }
}

/**
 * Send notification email using Mailchannels (free for Cloudflare domains)
 */
async function sendNotification(subscriberEmail, env) {
  const notificationEmail = env.NOTIFICATION_EMAIL;
  const fromEmail = env.FROM_EMAIL || 'noreply@mymemex.io';
  
  const emailData = {
    personalizations: [
      {
        to: [{ email: notificationEmail }],
        subject: 'New MyMemex Signup',
      }
    ],
    from: { email: fromEmail, name: 'MyMemex' },
    content: [
      {
        type: 'text/plain',
        value: `New subscriber: ${subscriberEmail}\n\nTime: ${new Date().toISOString()}\nSource: mymemex.io`
      },
      {
        type: 'text/html',
        value: `
          <h2>New MyMemex Signup</h2>
          <p><strong>Email:</strong> ${subscriberEmail}</p>
          <p><strong>Time:</strong> ${new Date().toISOString()}</p>
          <p><strong>Source:</strong> mymemex.io</p>
        `
      }
    ],
  };

  try {
    const response = await fetch('https://api.mailchannels.net/tx/v1/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(emailData),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Mailchannels error:', errorText);
      // Don't throw - we still want to return success to the user
    }
  } catch (error) {
    console.error('Email send error:', error);
    // Don't throw - we still want to return success to the user
  }
}

/**
 * JSON response helper
 */
function jsonResponse(data, status, headers) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      ...headers,
      'Content-Type': 'application/json',
    },
  });
}
