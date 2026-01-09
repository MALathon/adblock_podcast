/**
 * Podcast and Episode types
 */

export interface Podcast {
  id: string;
  title: string;
  artist: string;
  artworkUrl: string;
  feedUrl: string;
  description?: string;
  genre?: string;
}

export interface Episode {
  id: string;
  title: string;
  description?: string;
  pubDate: string;
  duration?: number;
  audioUrl: string;
  artworkUrl?: string;
  podcastId: string;
  podcastTitle: string;
}

export interface ProcessingJob {
  id: string;
  episodeId: string;
  status: 'queued' | 'downloading' | 'transcribing' | 'analyzing' | 'cutting' | 'complete' | 'error';
  progress: number;
  error?: string;
  processedAudioUrl?: string;
}
