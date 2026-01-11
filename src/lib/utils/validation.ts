/**
 * Input validation utilities
 */

const MAX_STRING_LENGTH = 10000;
const MAX_URL_LENGTH = 2048;

/**
 * Validate a string input
 */
export function validateString(
  value: unknown,
  name: string,
  options: { maxLength?: number; required?: boolean } = {}
): string {
  const { maxLength = MAX_STRING_LENGTH, required = false } = options;

  if (value === undefined || value === null || value === '') {
    if (required) {
      throw new ValidationError(`${name} is required`);
    }
    return '';
  }

  if (typeof value !== 'string') {
    throw new ValidationError(`${name} must be a string`);
  }

  if (value.length > maxLength) {
    throw new ValidationError(`${name} exceeds maximum length of ${maxLength}`);
  }

  return value.trim();
}

/**
 * Validate a URL to prevent SSRF attacks
 * Only allows http/https protocols and blocks private/local addresses
 */
export function validateUrl(value: unknown, name: string, options: { required?: boolean } = {}): string {
  const str = validateString(value, name, { maxLength: MAX_URL_LENGTH, required: options.required });

  if (!str) return '';

  try {
    const url = new URL(str);

    // Only allow http and https
    if (!['http:', 'https:'].includes(url.protocol)) {
      throw new ValidationError(`${name} must use http or https protocol`);
    }

    // Block private/local addresses (SSRF prevention)
    const hostname = url.hostname.toLowerCase();
    const blockedPatterns = [
      /^localhost$/,
      /^127\.\d+\.\d+\.\d+$/,
      /^10\.\d+\.\d+\.\d+$/,
      /^172\.(1[6-9]|2\d|3[01])\.\d+\.\d+$/,
      /^192\.168\.\d+\.\d+$/,
      /^0\.0\.0\.0$/,
      /^169\.254\.\d+\.\d+$/, // link-local
      /^\[::1\]$/, // IPv6 localhost
      /^::1$/
    ];

    if (blockedPatterns.some((pattern) => pattern.test(hostname))) {
      throw new ValidationError(`${name} cannot target local or private addresses`);
    }

    return str;
  } catch (e) {
    if (e instanceof ValidationError) throw e;
    throw new ValidationError(`${name} is not a valid URL`);
  }
}

/**
 * Validate a positive integer
 */
export function validateInteger(
  value: unknown,
  name: string,
  options: { min?: number; max?: number; required?: boolean } = {}
): number | undefined {
  const { min = 0, max = Number.MAX_SAFE_INTEGER, required = false } = options;

  if (value === undefined || value === null) {
    if (required) {
      throw new ValidationError(`${name} is required`);
    }
    return undefined;
  }

  const num = typeof value === 'string' ? parseInt(value, 10) : value;

  if (typeof num !== 'number' || isNaN(num) || !Number.isInteger(num)) {
    throw new ValidationError(`${name} must be an integer`);
  }

  if (num < min || num > max) {
    throw new ValidationError(`${name} must be between ${min} and ${max}`);
  }

  return num;
}

/**
 * Validation error class
 */
export class ValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ValidationError';
  }
}

/**
 * Check if an error is a validation error
 */
export function isValidationError(error: unknown): error is ValidationError {
  return error instanceof ValidationError;
}
