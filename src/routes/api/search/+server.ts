import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import type { Podcast } from '$lib/types';

/**
 * Search iTunes Podcast API
 * GET /api/search?q=<query>
 */
export const GET: RequestHandler = async ({ url }) => {
  const query = url.searchParams.get('q');

  if (!query || query.trim().length === 0) {
    return json([]);
  }

  try {
    const searchUrl = new URL('https://itunes.apple.com/search');
    searchUrl.searchParams.set('term', query);
    searchUrl.searchParams.set('media', 'podcast');
    searchUrl.searchParams.set('limit', '20');

    const response = await fetch(searchUrl.toString());

    if (!response.ok) {
      console.error('iTunes API error:', response.status);
      return json([], { status: 500 });
    }

    const data = await response.json();

    const podcasts: Podcast[] = data.results.map((result: ITunesResult) => ({
      id: result.collectionId.toString(),
      title: result.collectionName,
      artist: result.artistName,
      artworkUrl: result.artworkUrl600 || result.artworkUrl100,
      feedUrl: result.feedUrl,
      description: result.collectionViewUrl,
      genre: result.primaryGenreName
    }));

    return json(podcasts);
  } catch (error) {
    console.error('Search error:', error);
    return json([], { status: 500 });
  }
};

interface ITunesResult {
  collectionId: number;
  collectionName: string;
  artistName: string;
  artworkUrl100: string;
  artworkUrl600?: string;
  feedUrl: string;
  collectionViewUrl: string;
  primaryGenreName: string;
}
