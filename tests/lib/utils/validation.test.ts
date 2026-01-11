import { describe, it, expect } from 'vitest';
import {
  validateString,
  validateUrl,
  validateInteger,
  ValidationError,
  isValidationError
} from '$lib/utils/validation';

describe('validateString', () => {
  it('returns empty string for undefined when not required', () => {
    expect(validateString(undefined, 'test')).toBe('');
  });

  it('returns empty string for null when not required', () => {
    expect(validateString(null, 'test')).toBe('');
  });

  it('returns empty string for empty string when not required', () => {
    expect(validateString('', 'test')).toBe('');
  });

  it('throws when undefined and required', () => {
    expect(() => validateString(undefined, 'test', { required: true }))
      .toThrow('test is required');
  });

  it('throws for non-string types', () => {
    expect(() => validateString(123, 'test')).toThrow('test must be a string');
    expect(() => validateString({}, 'test')).toThrow('test must be a string');
    expect(() => validateString([], 'test')).toThrow('test must be a string');
  });

  it('throws when exceeding max length', () => {
    const longString = 'a'.repeat(101);
    expect(() => validateString(longString, 'test', { maxLength: 100 }))
      .toThrow('test exceeds maximum length of 100');
  });

  it('trims whitespace', () => {
    expect(validateString('  hello  ', 'test')).toBe('hello');
  });

  it('returns valid string', () => {
    expect(validateString('hello', 'test')).toBe('hello');
  });
});

describe('validateUrl', () => {
  it('returns empty string for undefined when not required', () => {
    expect(validateUrl(undefined, 'url')).toBe('');
  });

  it('throws when required and undefined', () => {
    expect(() => validateUrl(undefined, 'url', { required: true }))
      .toThrow('url is required');
  });

  it('validates http URLs', () => {
    expect(validateUrl('http://example.com', 'url')).toBe('http://example.com');
  });

  it('validates https URLs', () => {
    expect(validateUrl('https://example.com/path', 'url')).toBe('https://example.com/path');
  });

  it('rejects non-http protocols', () => {
    expect(() => validateUrl('ftp://example.com', 'url'))
      .toThrow('url must use http or https protocol');
    expect(() => validateUrl('file:///etc/passwd', 'url'))
      .toThrow('url must use http or https protocol');
  });

  it('rejects invalid URLs', () => {
    expect(() => validateUrl('not-a-url', 'url'))
      .toThrow('url is not a valid URL');
  });

  describe('SSRF prevention', () => {
    it('blocks localhost', () => {
      expect(() => validateUrl('http://localhost/api', 'url'))
        .toThrow('url cannot target local or private addresses');
    });

    it('blocks 127.x.x.x', () => {
      expect(() => validateUrl('http://127.0.0.1/api', 'url'))
        .toThrow('url cannot target local or private addresses');
      expect(() => validateUrl('http://127.1.2.3/api', 'url'))
        .toThrow('url cannot target local or private addresses');
    });

    it('blocks 10.x.x.x private range', () => {
      expect(() => validateUrl('http://10.0.0.1/api', 'url'))
        .toThrow('url cannot target local or private addresses');
      expect(() => validateUrl('http://10.255.255.255/api', 'url'))
        .toThrow('url cannot target local or private addresses');
    });

    it('blocks 172.16-31.x.x private range', () => {
      expect(() => validateUrl('http://172.16.0.1/api', 'url'))
        .toThrow('url cannot target local or private addresses');
      expect(() => validateUrl('http://172.31.255.255/api', 'url'))
        .toThrow('url cannot target local or private addresses');
    });

    it('allows 172.32+ (not private)', () => {
      expect(validateUrl('http://172.32.0.1/api', 'url')).toBe('http://172.32.0.1/api');
    });

    it('blocks 192.168.x.x private range', () => {
      expect(() => validateUrl('http://192.168.0.1/api', 'url'))
        .toThrow('url cannot target local or private addresses');
      expect(() => validateUrl('http://192.168.1.100/api', 'url'))
        .toThrow('url cannot target local or private addresses');
    });

    it('blocks 0.0.0.0', () => {
      expect(() => validateUrl('http://0.0.0.0/api', 'url'))
        .toThrow('url cannot target local or private addresses');
    });

    it('blocks link-local addresses', () => {
      expect(() => validateUrl('http://169.254.0.1/api', 'url'))
        .toThrow('url cannot target local or private addresses');
    });

    it('blocks IPv6 localhost', () => {
      expect(() => validateUrl('http://[::1]/api', 'url'))
        .toThrow('url cannot target local or private addresses');
    });
  });
});

describe('validateInteger', () => {
  it('returns undefined for undefined when not required', () => {
    expect(validateInteger(undefined, 'num')).toBeUndefined();
  });

  it('returns undefined for null when not required', () => {
    expect(validateInteger(null, 'num')).toBeUndefined();
  });

  it('throws when required and undefined', () => {
    expect(() => validateInteger(undefined, 'num', { required: true }))
      .toThrow('num is required');
  });

  it('validates integer numbers', () => {
    expect(validateInteger(42, 'num')).toBe(42);
    expect(validateInteger(0, 'num')).toBe(0);
  });

  it('parses string integers', () => {
    expect(validateInteger('42', 'num')).toBe(42);
    expect(validateInteger('100', 'num')).toBe(100);
  });

  it('throws for non-integer values', () => {
    expect(() => validateInteger('abc', 'num')).toThrow('num must be an integer');
    expect(() => validateInteger(3.14, 'num')).toThrow('num must be an integer');
  });

  it('validates min constraint', () => {
    expect(() => validateInteger(5, 'num', { min: 10 }))
      .toThrow('num must be between 10 and');
  });

  it('validates max constraint', () => {
    expect(() => validateInteger(100, 'num', { max: 50 }))
      .toThrow('num must be between 0 and 50');
  });

  it('validates within range', () => {
    expect(validateInteger(25, 'num', { min: 10, max: 50 })).toBe(25);
  });
});

describe('ValidationError', () => {
  it('creates error with correct name', () => {
    const error = new ValidationError('test message');
    expect(error.name).toBe('ValidationError');
    expect(error.message).toBe('test message');
  });

  it('is instanceof Error', () => {
    const error = new ValidationError('test');
    expect(error instanceof Error).toBe(true);
    expect(error instanceof ValidationError).toBe(true);
  });
});

describe('isValidationError', () => {
  it('returns true for ValidationError', () => {
    expect(isValidationError(new ValidationError('test'))).toBe(true);
  });

  it('returns false for regular Error', () => {
    expect(isValidationError(new Error('test'))).toBe(false);
  });

  it('returns false for non-errors', () => {
    expect(isValidationError('string')).toBe(false);
    expect(isValidationError(null)).toBe(false);
    expect(isValidationError(undefined)).toBe(false);
    expect(isValidationError({})).toBe(false);
  });
});
