/**
 * Episode storage and processed episode tracking
 */
import { db } from './index';
import type { Episode, ProcessedEpisode, EpisodeStatus } from '$lib/types';
import { toISODate } from '$lib/utils/format';

// Store episodes from RSS feed
export function upsertEpisode(episode: Episode): void {
  const stmt = db.prepare(`
    INSERT INTO episodes (
      episode_id, podcast_id, title, description,
      pub_date, duration, original_url, artwork_url
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(episode_id) DO UPDATE SET
      title = excluded.title,
      description = excluded.description,
      pub_date = excluded.pub_date,
      duration = excluded.duration,
      original_url = excluded.original_url,
      artwork_url = excluded.artwork_url
  `);

  stmt.run(
    episode.id,
    episode.podcastId,
    episode.title,
    episode.description || null,
    toISODate(episode.pubDate),
    episode.duration || null,
    episode.audioUrl,
    episode.artworkUrl || null
  );
}

export function upsertEpisodes(episodes: Episode[]): void {
  const insertMany = db.transaction((eps: Episode[]) => {
    for (const ep of eps) {
      upsertEpisode(ep);
    }
  });
  insertMany(episodes);
}

export function getEpisodesForPodcast(podcastId: string): Episode[] {
  const stmt = db.prepare(`
    SELECT
      e.episode_id as id,
      e.podcast_id as podcastId,
      e.title,
      e.description,
      e.pub_date as pubDate,
      e.duration,
      e.original_url as audioUrl,
      e.artwork_url as artworkUrl,
      s.title as podcastTitle,
      COALESCE(p.status, 'none') as processingStatus,
      p.processed_path as processedPath,
      p.error as processingError
    FROM episodes e
    JOIN subscriptions s ON e.podcast_id = s.podcast_id
    LEFT JOIN processed_episodes p ON e.episode_id = p.episode_id
    WHERE e.podcast_id = ?
    ORDER BY e.pub_date DESC
  `);
  return stmt.all(podcastId) as Episode[];
}

export function getEpisode(episodeId: string): Episode | null {
  const stmt = db.prepare(`
    SELECT
      e.episode_id as id,
      e.podcast_id as podcastId,
      e.title,
      e.description,
      e.pub_date as pubDate,
      e.duration,
      e.original_url as audioUrl,
      e.artwork_url as artworkUrl,
      s.title as podcastTitle
    FROM episodes e
    JOIN subscriptions s ON e.podcast_id = s.podcast_id
    WHERE e.episode_id = ?
  `);
  return stmt.get(episodeId) as Episode | null;
}

// Processed episode tracking
export function getProcessedEpisode(episodeId: string): ProcessedEpisode | null {
  const stmt = db.prepare(`
    SELECT
      episode_id as episodeId,
      processed_path as processedPath,
      status,
      original_duration as originalDuration,
      processed_duration as processedDuration,
      ads_removed_seconds as adsRemovedSeconds,
      error,
      queued_at as queuedAt,
      started_at as startedAt,
      completed_at as completedAt
    FROM processed_episodes
    WHERE episode_id = ?
  `);
  return stmt.get(episodeId) as ProcessedEpisode | null;
}

export function setProcessingStatus(
  episodeId: string,
  status: EpisodeStatus,
  extra?: Partial<ProcessedEpisode>
): void {
  const now = new Date().toISOString();

  // First ensure row exists
  const existing = getProcessedEpisode(episodeId);
  if (!existing) {
    db.prepare(`
      INSERT INTO processed_episodes (episode_id, status, queued_at)
      VALUES (?, ?, ?)
    `).run(episodeId, status, now);
  }

  // Update with provided fields
  if (status === 'processing') {
    db.prepare(`
      UPDATE processed_episodes SET status = ?, started_at = ? WHERE episode_id = ?
    `).run(status, now, episodeId);
  } else if (status === 'ready' && extra) {
    db.prepare(`
      UPDATE processed_episodes
      SET status = ?,
          completed_at = ?,
          processed_path = ?,
          original_duration = ?,
          processed_duration = ?,
          ads_removed_seconds = ?
      WHERE episode_id = ?
    `).run(
      status,
      now,
      extra.processedPath || null,
      extra.originalDuration || null,
      extra.processedDuration || null,
      extra.adsRemovedSeconds || null,
      episodeId
    );
  } else if (status === 'error' && extra?.error) {
    db.prepare(`
      UPDATE processed_episodes SET status = ?, error = ?, completed_at = ? WHERE episode_id = ?
    `).run(status, extra.error, now, episodeId);
  } else {
    db.prepare(`
      UPDATE processed_episodes SET status = ? WHERE episode_id = ?
    `).run(status, episodeId);
  }
}

export function getProcessedEpisodesForPodcast(podcastId: string): ProcessedEpisode[] {
  const stmt = db.prepare(`
    SELECT
      pe.episode_id as episodeId,
      pe.processed_path as processedPath,
      pe.status,
      pe.original_duration as originalDuration,
      pe.processed_duration as processedDuration,
      pe.ads_removed_seconds as adsRemovedSeconds
    FROM processed_episodes pe
    JOIN episodes e ON pe.episode_id = e.episode_id
    WHERE e.podcast_id = ? AND pe.status = 'ready'
  `);
  return stmt.all(podcastId) as ProcessedEpisode[];
}

export function getAllReadyEpisodes(): (Episode & { processedPath: string })[] {
  const stmt = db.prepare(`
    SELECT
      e.episode_id as id,
      e.podcast_id as podcastId,
      e.title,
      e.description,
      e.pub_date as pubDate,
      e.duration,
      e.original_url as audioUrl,
      e.artwork_url as artworkUrl,
      s.title as podcastTitle,
      pe.processed_path as processedPath,
      pe.processed_duration as processedDuration
    FROM episodes e
    JOIN subscriptions s ON e.podcast_id = s.podcast_id
    JOIN processed_episodes pe ON e.episode_id = pe.episode_id
    WHERE pe.status = 'ready'
    ORDER BY e.pub_date DESC
  `);
  return stmt.all() as (Episode & { processedPath: string })[];
}

/**
 * Reset all processing episodes back to queued status
 */
export function resetProcessingEpisodes(): number {
  const result = db.prepare(`
    UPDATE processed_episodes
    SET status = 'queued', started_at = NULL
    WHERE status = 'processing'
  `).run();
  return result.changes;
}

/**
 * Convert all RFC 2822 dates to ISO 8601 format for proper sorting
 */
export function convertDatesToISO(): number {
  // Get all episodes with non-ISO dates
  const episodes = db.prepare(`
    SELECT episode_id, pub_date FROM episodes
    WHERE pub_date IS NOT NULL
      AND pub_date NOT LIKE '____-__-__T%'
  `).all() as { episode_id: string; pub_date: string }[];

  let converted = 0;
  const updateStmt = db.prepare(`
    UPDATE episodes SET pub_date = ? WHERE episode_id = ?
  `);

  for (const ep of episodes) {
    try {
      const date = new Date(ep.pub_date);
      if (!isNaN(date.getTime())) {
        updateStmt.run(date.toISOString(), ep.episode_id);
        converted++;
      }
    } catch {
      // Skip invalid dates
    }
  }

  return converted;
}
