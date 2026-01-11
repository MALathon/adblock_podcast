/**
 * Centralized configuration for the application
 */

/** Backend API URL for ad removal processing */
export const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/** Directory for processed audio files */
export const PROCESSED_DIR = 'backend/processed';

/** Database file location */
export const DB_PATH = 'data/podcasts.db';

/** Worker configuration */
export const WORKER_CONFIG = {
  /** Polling interval in milliseconds */
  pollInterval: 10_000,
  /** Maximum concurrent processing jobs */
  maxConcurrent: 2,
  /** Maximum processing time before timeout (15 minutes) */
  maxProcessingTime: 15 * 60 * 1000,
  /** Status check interval in milliseconds */
  statusCheckInterval: 5_000
} as const;

/** API configuration */
export const API_CONFIG = {
  /** iTunes Search API endpoint */
  itunesSearchUrl: 'https://itunes.apple.com/search',
  /** iTunes Lookup API endpoint */
  itunesLookupUrl: 'https://itunes.apple.com/lookup',
  /** User agent for RSS feed requests */
  userAgent: 'AdBlockPodcast/1.0',
  /** Cache duration for RSS feed in seconds */
  feedCacheSeconds: 300
} as const;

/** Audio streaming configuration */
export const AUDIO_CONFIG = {
  /** Content type for MP3 audio */
  contentType: 'audio/mpeg',
  /** Cache duration for audio files (1 year) */
  cacheMaxAge: 31_536_000
} as const;
