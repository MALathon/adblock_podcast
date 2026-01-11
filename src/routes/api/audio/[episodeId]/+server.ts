/**
 * Audio streaming API
 * GET /api/audio/[episodeId] - Stream processed audio file
 */
import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getProcessedEpisode, getEpisode } from '$lib/db/episodes';
import { createReadStream, statSync, existsSync } from 'fs';
import { join } from 'path';

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

  // Serve processed file
  const filePath = join(process.cwd(), processed.processedPath);

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
