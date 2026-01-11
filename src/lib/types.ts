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
  processingStatus?: EpisodeStatus;
  processedPath?: string;
  processingError?: string;
}

export interface ProcessingJob {
  id: string;
  episodeId: string;
  status: 'queued' | 'downloading' | 'transcribing' | 'analyzing' | 'cutting' | 'complete' | 'error';
  progress: number;
  error?: string;
  processedAudioUrl?: string;
}

/**
 * Subscription - a podcast the user has subscribed to
 */
export interface Subscription {
  podcastId: string;
  title: string;
  artist: string;
  artworkUrl: string;
  feedUrl: string;
  description?: string;
  genre?: string;
  subscribedAt: string;
  lastRefreshed: string | null;
}

/**
 * Episode processing status
 */
export type EpisodeStatus = 'none' | 'queued' | 'processing' | 'ready' | 'error';

/**
 * Processed episode record
 */
export interface ProcessedEpisode {
  episodeId: string;
  processedPath: string | null;
  status: EpisodeStatus;
  originalDuration: number | null;
  processedDuration: number | null;
  adsRemovedSeconds: number | null;
  error?: string;
  queuedAt?: string;
  startedAt?: string;
  completedAt?: string;
}

/**
 * Queue item for processing
 */
export interface QueueItem {
  id: number;
  episodeId: string;
  priority: number;
  createdAt: string;
  episodeTitle?: string;
  podcastTitle?: string;
  podcastId?: string;
  audioUrl?: string;
  status?: EpisodeStatus;
}

/**
 * RSS Feed types
 */
export interface FeedEpisode {
  guid: string;
  title: string;
  description: string;
  pubDate: string;
  audioUrl: string;
  duration: number;
  isProcessed: boolean;
}
