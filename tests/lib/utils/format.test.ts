import { describe, it, expect } from 'vitest';
import {
  formatDuration,
  formatTime,
  formatDate,
  formatDateFull,
  toISODate,
  formatFileSize
} from '$lib/utils/format';

describe('formatDuration', () => {
  it('returns empty string for undefined', () => {
    expect(formatDuration(undefined)).toBe('');
  });

  it('returns empty string for NaN', () => {
    expect(formatDuration(NaN)).toBe('');
  });

  it('returns empty string for 0', () => {
    expect(formatDuration(0)).toBe('');
  });

  it('formats minutes correctly', () => {
    expect(formatDuration(60)).toBe('1 min');
    expect(formatDuration(1800)).toBe('30 min');
  });

  it('formats hours and minutes correctly', () => {
    expect(formatDuration(3600)).toBe('1h 0m');
    expect(formatDuration(5400)).toBe('1h 30m');
    expect(formatDuration(7260)).toBe('2h 1m');
  });
});

describe('formatTime', () => {
  it('returns 0:00 for NaN', () => {
    expect(formatTime(NaN)).toBe('0:00');
  });

  it('returns 0:00 for negative values', () => {
    expect(formatTime(-1)).toBe('0:00');
  });

  it('formats seconds correctly', () => {
    expect(formatTime(0)).toBe('0:00');
    expect(formatTime(5)).toBe('0:05');
    expect(formatTime(65)).toBe('1:05');
  });

  it('formats minutes correctly', () => {
    expect(formatTime(60)).toBe('1:00');
    expect(formatTime(125)).toBe('2:05');
    expect(formatTime(599)).toBe('9:59');
  });

  it('formats hours correctly', () => {
    expect(formatTime(3600)).toBe('1:00:00');
    expect(formatTime(3665)).toBe('1:01:05');
    expect(formatTime(7200)).toBe('2:00:00');
  });

  it('pads minutes and seconds correctly', () => {
    expect(formatTime(3661)).toBe('1:01:01');
    expect(formatTime(3605)).toBe('1:00:05');
  });
});

describe('formatDate', () => {
  it('returns empty string for undefined', () => {
    expect(formatDate(undefined)).toBe('');
  });

  it('returns empty string for empty string', () => {
    expect(formatDate('')).toBe('');
  });

  it('returns empty string for invalid date', () => {
    expect(formatDate('not-a-date')).toBe('');
  });

  it('formats ISO date correctly', () => {
    const result = formatDate('2024-01-15T12:00:00Z');
    expect(result).toMatch(/Jan 15/);
  });
});

describe('formatDateFull', () => {
  it('returns empty string for undefined', () => {
    expect(formatDateFull(undefined)).toBe('');
  });

  it('returns empty string for invalid date', () => {
    expect(formatDateFull('invalid')).toBe('');
  });

  it('formats date with full month and year', () => {
    const result = formatDateFull('2024-01-15T12:00:00Z');
    expect(result).toMatch(/January 15, 2024/);
  });
});

describe('toISODate', () => {
  it('returns null for undefined', () => {
    expect(toISODate(undefined)).toBeNull();
  });

  it('converts RFC 2822 date to ISO', () => {
    const result = toISODate('Mon, 15 Jan 2024 12:00:00 GMT');
    expect(result).toContain('2024-01-15');
  });

  it('returns original string for unparseable date', () => {
    expect(toISODate('invalid')).toBe('invalid');
  });
});

describe('formatFileSize', () => {
  it('returns 0 B for 0 bytes', () => {
    expect(formatFileSize(0)).toBe('0 B');
  });

  it('formats bytes correctly', () => {
    expect(formatFileSize(100)).toBe('100 B');
    expect(formatFileSize(1000)).toBe('1000 B');
  });

  it('formats kilobytes correctly', () => {
    expect(formatFileSize(1024)).toBe('1 KB');
    expect(formatFileSize(1536)).toBe('1.5 KB');
  });

  it('formats megabytes correctly', () => {
    expect(formatFileSize(1048576)).toBe('1 MB');
    expect(formatFileSize(5242880)).toBe('5 MB');
  });

  it('formats gigabytes correctly', () => {
    expect(formatFileSize(1073741824)).toBe('1 GB');
  });
});
