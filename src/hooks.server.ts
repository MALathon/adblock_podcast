/**
 * Server Hooks
 *
 * Initializes the background worker on server startup and adds security headers.
 */

import type { Handle } from '@sveltejs/kit';
import { startWorker } from '$lib/worker/processor';

// Start background worker when server initializes
let workerStarted = false;

if (!workerStarted) {
  console.log('[Hooks] Initializing server...');
  startWorker();
  workerStarted = true;
}

/**
 * Security headers to protect against common web vulnerabilities
 */
const securityHeaders: Record<string, string> = {
  // Prevent clickjacking by disallowing framing
  'X-Frame-Options': 'DENY',

  // Prevent MIME type sniffing
  'X-Content-Type-Options': 'nosniff',

  // Enable XSS filter in older browsers
  'X-XSS-Protection': '1; mode=block',

  // Control referrer information sent with requests
  'Referrer-Policy': 'strict-origin-when-cross-origin',

  // Restrict browser features and APIs
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), interest-cohort=()',

  // Content Security Policy - restrictive default with necessary exceptions
  'Content-Security-Policy': [
    "default-src 'self'",
    // Allow inline styles for Svelte (style-src) - consider using nonces in production
    "style-src 'self' 'unsafe-inline'",
    // Allow scripts from self only
    "script-src 'self'",
    // Allow images from self and https (for podcast artwork)
    "img-src 'self' https: data:",
    // Allow audio from self and https (for podcast audio)
    "media-src 'self' https:",
    // Allow fonts from self
    "font-src 'self'",
    // Allow connections to self and backend API
    "connect-src 'self'",
    // Prevent form submissions to external sites
    "form-action 'self'",
    // Prevent embedding in frames
    "frame-ancestors 'none'",
    // Block all object/embed/applet elements
    "object-src 'none'",
    // Require HTTPS for all resources in production (upgrade insecure requests)
    "upgrade-insecure-requests",
    // Define base URI
    "base-uri 'self'"
  ].join('; ')
};

export const handle: Handle = async ({ event, resolve }) => {
  const response = await resolve(event);

  // Add security headers to all responses
  for (const [header, value] of Object.entries(securityHeaders)) {
    response.headers.set(header, value);
  }

  return response;
};
