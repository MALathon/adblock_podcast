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
 * Includes protection against DNS rebinding, IPv6 mapped addresses, and cloud metadata endpoints
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

    // IPv4 patterns to block
    const blockedIPv4Patterns = [
      /^localhost$/i,
      /^127\.\d+\.\d+\.\d+$/,           // Loopback
      /^10\.\d+\.\d+\.\d+$/,            // Private Class A
      /^172\.(1[6-9]|2\d|3[01])\.\d+\.\d+$/, // Private Class B
      /^192\.168\.\d+\.\d+$/,           // Private Class C
      /^0\.0\.0\.0$/,                   // All interfaces
      /^169\.254\.\d+\.\d+$/,           // Link-local
      /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+$/, // Carrier-grade NAT
      /^192\.0\.0\.\d+$/,               // IETF protocol assignments
      /^192\.0\.2\.\d+$/,               // TEST-NET-1
      /^198\.51\.100\.\d+$/,            // TEST-NET-2
      /^203\.0\.113\.\d+$/,             // TEST-NET-3
      /^224\.\d+\.\d+\.\d+$/,           // Multicast
      /^240\.\d+\.\d+\.\d+$/,           // Reserved
      /^255\.255\.255\.255$/            // Broadcast
    ];

    // IPv6 patterns to block
    const blockedIPv6Patterns = [
      /^\[::1\]$/,                      // IPv6 localhost
      /^::1$/,
      /^\[::ffff:\d+\.\d+\.\d+\.\d+\]$/i, // IPv6-mapped IPv4 addresses
      /^::ffff:\d+\.\d+\.\d+\.\d+$/i,     // IPv6-mapped IPv4 (without brackets)
      /^\[fe80:/i,                      // IPv6 link-local
      /^fe80:/i,
      /^\[fc00:/i,                      // IPv6 unique local
      /^fc00:/i,
      /^\[fd00:/i,                      // IPv6 unique local
      /^fd00:/i,
      /^\[::\]$/,                       // IPv6 unspecified
      /^::$/
    ];

    // Cloud metadata endpoints to block (DNS rebinding protection)
    const blockedHostnames = [
      'metadata.google.internal',       // GCP
      'metadata.goog',                  // GCP alternative
      'metadata',                       // Generic cloud metadata
      '169.254.169.254',               // AWS/Azure/GCP metadata IP
      'instance-data',                  // AWS
      'instance-data.ec2.internal',    // AWS
      'fd00:ec2::254',                 // AWS IPv6 metadata
      '169.254.170.2',                 // ECS container metadata
      'kubernetes.default',             // Kubernetes
      'kubernetes.default.svc',         // Kubernetes
      'kubernetes.default.svc.cluster.local', // Kubernetes
    ];

    // Check IPv4 patterns
    if (blockedIPv4Patterns.some((pattern) => pattern.test(hostname))) {
      throw new ValidationError(`${name} cannot target local or private addresses`);
    }

    // Check IPv6 patterns
    if (blockedIPv6Patterns.some((pattern) => pattern.test(hostname))) {
      throw new ValidationError(`${name} cannot target local or private IPv6 addresses`);
    }

    // Check cloud metadata endpoints
    if (blockedHostnames.some((blocked) => hostname === blocked.toLowerCase())) {
      throw new ValidationError(`${name} cannot target cloud metadata endpoints`);
    }

    // Block hostnames ending with internal TLDs or cloud metadata domains
    const blockedSuffixes = [
      '.internal',
      '.local',
      '.localhost',
      '.localdomain',
      '.home.arpa',
      '.corp',
      '.lan',
      '.intranet'
    ];

    if (blockedSuffixes.some((suffix) => hostname.endsWith(suffix))) {
      throw new ValidationError(`${name} cannot target internal network addresses`);
    }

    // Additional check: Block decimal IP notation (e.g., 2130706433 = 127.0.0.1)
    if (/^\d+$/.test(hostname)) {
      throw new ValidationError(`${name} cannot use decimal IP notation`);
    }

    // Block octal IP notation (e.g., 0177.0.0.1 = 127.0.0.1)
    if (/^0[0-7]+\./.test(hostname)) {
      throw new ValidationError(`${name} cannot use octal IP notation`);
    }

    // Block hex IP notation (e.g., 0x7f.0.0.1 = 127.0.0.1)
    if (/^0x[0-9a-f]+\./i.test(hostname)) {
      throw new ValidationError(`${name} cannot use hexadecimal IP notation`);
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
 * Validate a boolean value
 */
export function validateBoolean(
  value: unknown,
  name: string,
  options: { required?: boolean } = {}
): boolean | undefined {
  const { required = false } = options;

  if (value === undefined || value === null) {
    if (required) {
      throw new ValidationError(`${name} is required`);
    }
    return undefined;
  }

  if (typeof value !== 'boolean') {
    throw new ValidationError(`${name} must be a boolean`);
  }

  return value;
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
