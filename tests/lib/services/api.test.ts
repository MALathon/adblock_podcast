import { describe, it, expect } from 'vitest';
import {
  success,
  created,
  badRequest,
  notFound,
  conflict,
  serverError,
  xmlResponse,
  audioResponse
} from '$lib/services/api';

describe('API Response Helpers', () => {
  describe('success', () => {
    it('returns 200 status by default', async () => {
      const response = success({ data: 'test' });
      expect(response.status).toBe(200);
    });

    it('allows custom status', async () => {
      const response = success({ data: 'test' }, 202);
      expect(response.status).toBe(202);
    });

    it('returns JSON content type', async () => {
      const response = success({ message: 'ok' });
      expect(response.headers.get('content-type')).toContain('application/json');
    });

    it('serializes data as JSON', async () => {
      const response = success({ foo: 'bar' });
      const data = await response.json();
      expect(data).toEqual({ foo: 'bar' });
    });
  });

  describe('created', () => {
    it('returns 201 status', async () => {
      const response = created({ id: '123' });
      expect(response.status).toBe(201);
    });

    it('serializes data as JSON', async () => {
      const response = created({ id: '123', name: 'New Item' });
      const data = await response.json();
      expect(data).toEqual({ id: '123', name: 'New Item' });
    });
  });

  describe('badRequest', () => {
    it('returns 400 status', async () => {
      const response = badRequest('Invalid input');
      expect(response.status).toBe(400);
    });

    it('includes error message in body', async () => {
      const response = badRequest('Missing field');
      const data = await response.json();
      expect(data).toEqual({ error: 'Missing field' });
    });
  });

  describe('notFound', () => {
    it('returns 404 status', async () => {
      const response = notFound('Item not found');
      expect(response.status).toBe(404);
    });

    it('uses default message', async () => {
      const response = notFound();
      const data = await response.json();
      expect(data).toEqual({ error: 'Resource not found' });
    });

    it('allows custom message', async () => {
      const response = notFound('User not found');
      const data = await response.json();
      expect(data).toEqual({ error: 'User not found' });
    });
  });

  describe('conflict', () => {
    it('returns 409 status', async () => {
      const response = conflict('Already exists');
      expect(response.status).toBe(409);
    });

    it('includes error message in body', async () => {
      const response = conflict('Duplicate entry');
      const data = await response.json();
      expect(data).toEqual({ error: 'Duplicate entry' });
    });
  });

  describe('serverError', () => {
    it('returns 500 status', async () => {
      const response = serverError('Database error');
      expect(response.status).toBe(500);
    });

    it('uses default message', async () => {
      const response = serverError();
      const data = await response.json();
      expect(data).toEqual({ error: 'Internal server error' });
    });
  });

  describe('xmlResponse', () => {
    it('returns RSS XML content type', () => {
      const response = xmlResponse('<rss></rss>');
      expect(response.headers.get('content-type')).toBe('application/rss+xml; charset=utf-8');
    });

    it('sets cache control header', () => {
      const response = xmlResponse('<rss></rss>', 600);
      expect(response.headers.get('cache-control')).toBe('public, max-age=600');
    });

    it('uses default cache duration of 300 seconds', () => {
      const response = xmlResponse('<rss></rss>');
      expect(response.headers.get('cache-control')).toBe('public, max-age=300');
    });
  });

  describe('audioResponse', () => {
    it('returns audio/mpeg content type', () => {
      const stream = new ReadableStream();
      const response = audioResponse(stream, { size: 1000 });
      expect(response.headers.get('content-type')).toBe('audio/mpeg');
    });

    it('sets accept-ranges header', () => {
      const stream = new ReadableStream();
      const response = audioResponse(stream, { size: 1000 });
      expect(response.headers.get('accept-ranges')).toBe('bytes');
    });

    it('sets content-length for full response', () => {
      const stream = new ReadableStream();
      const response = audioResponse(stream, { size: 5000 });
      expect(response.headers.get('content-length')).toBe('5000');
      expect(response.status).toBe(200);
    });

    it('returns 206 for range request', () => {
      const stream = new ReadableStream();
      const response = audioResponse(stream, {
        size: 10000,
        start: 0,
        end: 999,
        isRange: true
      });
      expect(response.status).toBe(206);
      expect(response.headers.get('content-range')).toBe('bytes 0-999/10000');
      expect(response.headers.get('content-length')).toBe('1000');
    });

    it('calculates correct content-length for range', () => {
      const stream = new ReadableStream();
      const response = audioResponse(stream, {
        size: 10000,
        start: 500,
        end: 1499,
        isRange: true
      });
      expect(response.headers.get('content-length')).toBe('1000');
    });

    it('sets long cache duration', () => {
      const stream = new ReadableStream();
      const response = audioResponse(stream, { size: 1000 });
      expect(response.headers.get('cache-control')).toBe('public, max-age=31536000');
    });
  });
});
