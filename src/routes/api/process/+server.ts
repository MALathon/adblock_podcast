import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

// Backend URL (will be configurable via environment variable)
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Process episode to remove ads
 * POST /api/process
 *
 * For now, this proxies to the Python FastAPI backend.
 * If the backend is unavailable, it returns the original audio URL.
 */
export const POST: RequestHandler = async ({ request }) => {
  try {
    const body = await request.json();
    const { episodeId, audioUrl, title, podcastTitle } = body;

    if (!audioUrl) {
      return json({ error: 'audioUrl is required' }, { status: 400 });
    }

    // Try to call the Python backend
    try {
      const response = await fetch(`${BACKEND_URL}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          episode_id: episodeId,
          audio_url: audioUrl,
          title,
          podcast_title: podcastTitle
        })
      });

      if (response.ok) {
        const result = await response.json();
        return json({
          processedAudioUrl: result.processed_audio_url,
          adsRemoved: result.ads_removed,
          duration: result.duration
        });
      }
    } catch (backendError) {
      console.log('Backend not available, returning original audio');
    }

    // Fallback: return original audio URL
    return json({
      processedAudioUrl: audioUrl,
      adsRemoved: 0,
      duration: 0,
      note: 'Backend not available - playing original audio'
    });
  } catch (error) {
    console.error('Process error:', error);
    return json({ error: 'Processing failed' }, { status: 500 });
  }
};

/**
 * Get processing status
 * GET /api/process?episodeId=xxx
 */
export const GET: RequestHandler = async ({ url }) => {
  const episodeId = url.searchParams.get('episodeId');

  if (!episodeId) {
    return json({ error: 'episodeId is required' }, { status: 400 });
  }

  try {
    const response = await fetch(`${BACKEND_URL}/status/${episodeId}`);

    if (response.ok) {
      return json(await response.json());
    }
  } catch {
    // Backend not available
  }

  return json({
    status: 'unknown',
    progress: 0
  });
};
