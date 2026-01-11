import { describe, it, expect } from 'vitest';
import {
  extractXmlValue,
  extractXmlAttribute,
  cleanHtml,
  escapeXml,
  parseDuration
} from '$lib/utils/xml';

describe('extractXmlValue', () => {
  it('extracts plain text content', () => {
    const xml = '<title>Hello World</title>';
    expect(extractXmlValue(xml, 'title')).toBe('Hello World');
  });

  it('extracts CDATA content', () => {
    const xml = '<description><![CDATA[<p>HTML content</p>]]></description>';
    expect(extractXmlValue(xml, 'description')).toBe('<p>HTML content</p>');
  });

  it('trims whitespace', () => {
    const xml = '<title>  Padded Content  </title>';
    expect(extractXmlValue(xml, 'title')).toBe('Padded Content');
  });

  it('returns empty string for missing tag', () => {
    const xml = '<item><title>Test</title></item>';
    expect(extractXmlValue(xml, 'description')).toBe('');
  });

  it('handles tags with attributes', () => {
    const xml = '<title type="html">Attributed Title</title>';
    expect(extractXmlValue(xml, 'title')).toBe('Attributed Title');
  });

  it('handles multiline content', () => {
    const xml = `<description>Line 1
Line 2
Line 3</description>`;
    expect(extractXmlValue(xml, 'description')).toContain('Line 1');
    expect(extractXmlValue(xml, 'description')).toContain('Line 3');
  });

  it('is case insensitive', () => {
    const xml = '<TITLE>Uppercase</TITLE>';
    expect(extractXmlValue(xml, 'title')).toBe('Uppercase');
  });
});

describe('extractXmlAttribute', () => {
  it('extracts attribute value', () => {
    const xml = '<enclosure url="http://example.com/audio.mp3" type="audio/mpeg" />';
    expect(extractXmlAttribute(xml, 'enclosure', 'url')).toBe('http://example.com/audio.mp3');
    expect(extractXmlAttribute(xml, 'enclosure', 'type')).toBe('audio/mpeg');
  });

  it('returns empty string for missing attribute', () => {
    const xml = '<enclosure url="http://example.com" />';
    expect(extractXmlAttribute(xml, 'enclosure', 'length')).toBe('');
  });

  it('returns empty string for missing tag', () => {
    const xml = '<item><title>Test</title></item>';
    expect(extractXmlAttribute(xml, 'enclosure', 'url')).toBe('');
  });

  it('is case insensitive for tag names', () => {
    const xml = '<ENCLOSURE url="http://example.com" />';
    expect(extractXmlAttribute(xml, 'enclosure', 'url')).toBe('http://example.com');
  });
});

describe('cleanHtml', () => {
  it('removes HTML tags', () => {
    expect(cleanHtml('<p>Hello</p>')).toBe('Hello');
    expect(cleanHtml('<strong>Bold</strong> text')).toBe('Bold text');
  });

  it('decodes HTML entities', () => {
    expect(cleanHtml('&amp;')).toBe('&');
    expect(cleanHtml('&lt;tag&gt;')).toBe('<tag>');
    expect(cleanHtml('&quot;quoted&quot;')).toBe('"quoted"');
    expect(cleanHtml('&#39;single&#39;')).toBe("'single'");
    expect(cleanHtml('&nbsp;space&nbsp;')).toBe('space');
  });

  it('trims whitespace', () => {
    expect(cleanHtml('  spaced  ')).toBe('spaced');
  });

  it('returns empty string for empty input', () => {
    expect(cleanHtml('')).toBe('');
  });

  it('handles complex HTML', () => {
    const html = '<div class="content"><p>&lt;script&gt;</p></div>';
    expect(cleanHtml(html)).toBe('<script>');
  });
});

describe('escapeXml', () => {
  it('escapes ampersand', () => {
    expect(escapeXml('A & B')).toBe('A &amp; B');
  });

  it('escapes less than', () => {
    expect(escapeXml('a < b')).toBe('a &lt; b');
  });

  it('escapes greater than', () => {
    expect(escapeXml('a > b')).toBe('a &gt; b');
  });

  it('escapes double quotes', () => {
    expect(escapeXml('"quoted"')).toBe('&quot;quoted&quot;');
  });

  it('escapes single quotes', () => {
    expect(escapeXml("'single'")).toBe('&#39;single&#39;');
  });

  it('handles multiple characters', () => {
    expect(escapeXml('<script>alert("xss")</script>'))
      .toBe('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
  });
});

describe('parseDuration', () => {
  it('returns 0 for empty string', () => {
    expect(parseDuration('')).toBe(0);
  });

  it('parses pure seconds', () => {
    expect(parseDuration('3600')).toBe(3600);
    expect(parseDuration('60')).toBe(60);
    expect(parseDuration('45')).toBe(45);
  });

  it('parses MM:SS format', () => {
    expect(parseDuration('1:00')).toBe(60);
    expect(parseDuration('10:30')).toBe(630);
    expect(parseDuration('0:45')).toBe(45);
  });

  it('parses HH:MM:SS format', () => {
    expect(parseDuration('1:00:00')).toBe(3600);
    expect(parseDuration('1:30:00')).toBe(5400);
    expect(parseDuration('2:15:30')).toBe(8130);
  });

  it('returns 0 for invalid format', () => {
    expect(parseDuration('abc')).toBe(0);
    expect(parseDuration('1:2:3:4')).toBe(0);
  });

  it('returns 0 for NaN parts', () => {
    expect(parseDuration('a:b:c')).toBe(0);
    expect(parseDuration('1:abc')).toBe(0);
  });
});
