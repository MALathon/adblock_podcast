/**
 * XML parsing utilities for RSS feeds
 */

/**
 * Extract value from XML tag (handles CDATA and plain text)
 */
export function extractXmlValue(xml: string, tag: string): string {
  // Try CDATA first
  const cdataRegex = new RegExp(`<${tag}[^>]*><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tag}>`, 'i');
  const cdataMatch = xml.match(cdataRegex);
  if (cdataMatch) return cdataMatch[1].trim();

  // Fall back to plain text
  const regex = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i');
  const match = xml.match(regex);
  return match ? match[1].trim() : '';
}

/**
 * Extract attribute value from XML tag
 */
export function extractXmlAttribute(xml: string, tag: string, attribute: string): string {
  const regex = new RegExp(`<${tag}[^>]*${attribute}="([^"]*)"[^>]*>`, 'i');
  const match = xml.match(regex);
  return match ? match[1] : '';
}

/**
 * Clean HTML entities and tags from text
 */
export function cleanHtml(text: string): string {
  if (!text) return '';
  return text
    .replace(/<[^>]*>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .trim();
}

/**
 * Escape text for XML output
 */
export function escapeXml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Parse duration string to seconds
 * Handles formats: "3600", "1:00:00", "60:00"
 */
export function parseDuration(duration: string): number {
  if (!duration) return 0;

  // Pure seconds
  if (/^\d+$/.test(duration)) {
    return parseInt(duration, 10);
  }

  // HH:MM:SS or MM:SS
  const parts = duration.split(':').map(p => parseInt(p, 10));
  if (parts.some(isNaN)) return 0;

  if (parts.length === 3) {
    return parts[0] * 3600 + parts[1] * 60 + parts[2];
  }
  if (parts.length === 2) {
    return parts[0] * 60 + parts[1];
  }
  return 0;
}
