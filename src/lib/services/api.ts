/**
 * API response helpers
 *
 * Provides consistent JSON response creation for API endpoints.
 */

import { json, error as svelteError } from '@sveltejs/kit';

/**
 * Create a successful JSON response
 */
export function success<T>(data: T, status = 200): Response {
  return json(data, { status });
}

/**
 * Create a 201 Created response
 */
export function created<T>(data: T): Response {
  return json(data, { status: 201 });
}

/**
 * Create a 400 Bad Request response
 */
export function badRequest(message: string): Response {
  return json({ error: message }, { status: 400 });
}

/**
 * Create a 404 Not Found response
 */
export function notFound(message = 'Resource not found'): Response {
  return json({ error: message }, { status: 404 });
}

/**
 * Create a 409 Conflict response
 */
export function conflict(message: string): Response {
  return json({ error: message }, { status: 409 });
}

/**
 * Create a 500 Internal Server Error response
 */
export function serverError(message = 'Internal server error'): Response {
  return json({ error: message }, { status: 500 });
}

/**
 * Throw a SvelteKit error (for non-JSON responses)
 */
export function throwError(status: number, message: string): never {
  throw svelteError(status, message);
}

/**
 * Create an RSS/XML response
 */
export function xmlResponse(content: string, cacheSeconds = 300): Response {
  return new Response(content, {
    headers: {
      'Content-Type': 'application/rss+xml; charset=utf-8',
      'Cache-Control': `public, max-age=${cacheSeconds}`
    }
  });
}

/**
 * Create an audio streaming response
 */
export function audioResponse(
  stream: ReadableStream,
  options: {
    size: number;
    start?: number;
    end?: number;
    isRange?: boolean;
  }
): Response {
  const { size, start, end, isRange } = options;

  const headers: Record<string, string> = {
    'Content-Type': 'audio/mpeg',
    'Accept-Ranges': 'bytes',
    'Cache-Control': 'public, max-age=31536000'
  };

  if (isRange && start !== undefined && end !== undefined) {
    headers['Content-Range'] = `bytes ${start}-${end}/${size}`;
    headers['Content-Length'] = (end - start + 1).toString();
    return new Response(stream, { status: 206, headers });
  }

  headers['Content-Length'] = size.toString();
  return new Response(stream, { status: 200, headers });
}
