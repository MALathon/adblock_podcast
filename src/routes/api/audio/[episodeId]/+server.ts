/**
 * Audio streaming API
 * GET /api/audio/[episodeId] - Stream processed audio file
 */
import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getProcessedEpisode, getEpisode } from '$lib/db/episodes';
import { createReadStream, statSync, existsSync } from 'fs';
import { join, resolve, normalize } from 'path';

// Define allowed base directory for processed audio files
const ALLOWED_BASE_DIR = resolve(process.cwd(), 'processed');

/**
 * Validate that a file path is within the allowed directory
 * Prevents path traversal attacks (e.g., ../../../etc/passwd)
 */
function isPathWithinAllowedDir(filePath: string): boolean {
  const normalizedPath = normalize(resolve(filePath));
  const normalizedBase = normalize(ALLOWED_BASE_DIR);

  // Ensure the resolved path starts with the allowed base directory
  return normalizedPath.startsWith(normalizedBase + '/') || normalizedPath === normalizedBase;
}

export const GET: RequestHandler = async ({ params, request }) => {
  const { episodeId } = params;

  // Get processed episode info
  const processed = getProcessedEpisode(episodeId);

  if (!processed || processed.status !== 'ready' || !processed.processedPath) {
    // Fall back to original audio URL
    const episode = getEpisode(episodeId);
    if (!episode) {
      throw error(404, 'Episode not found');
    }

    // Redirect to original audio
    return new Response(null, {
      status: 302,
      headers: {
        'Location': episode.audioUrl
      }
    });
  }

  // Construct and validate file path
  const filePath = resolve(process.cwd(), processed.processedPath);

  // Security check: Ensure path is within allowed directory
  if (!isPathWithinAllowedDir(filePath)) {
    console.error(`[Audio] Path traversal attempt blocked: ${processed.processedPath}`);
    throw error(403, 'Access denied');
  }

  if (!existsSync(filePath)) {
    throw error(404, 'Processed audio file not found');
  }

  const stat = statSync(filePath);
  const fileSize = stat.size;

  // Handle range requests for seeking
  const range = request.headers.get('range');

  if (range) {
    const parts = range.replace(/bytes=/, '').split('-');
    const start = parseInt(parts[0], 10);
    const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
    const chunkSize = end - start + 1;

    const stream = createReadStream(filePath, { start, end });

    return new Response(stream as unknown as ReadableStream, {
      status: 206,
      headers: {
        'Content-Range': `bytes ${start}-${end}/${fileSize}`,
        'Accept-Ranges': 'bytes',
        'Content-Length': chunkSize.toString(),
        'Content-Type': 'audio/mpeg',
        'Cache-Control': 'public, max-age=31536000'
      }
    });
  }

  const stream = createReadStream(filePath);

  return new Response(stream as unknown as ReadableStream, {
    status: 200,
    headers: {
      'Content-Length': fileSize.toString(),
      'Content-Type': 'audio/mpeg',
      'Accept-Ranges': 'bytes',
      'Cache-Control': 'public, max-age=31536000'
    }
  });
};
