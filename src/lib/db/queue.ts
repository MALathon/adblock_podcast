/**
 * Processing queue operations
 */
import { db } from './index';
import type { QueueItem, Episode } from '$lib/types';

export function addToQueue(episodeId: string, priority: number = 0, retry: boolean = false): void {
  const now = new Date().toISOString();

  if (retry) {
    // For retry: reset error status, clear error message and processed_path
    db.prepare(`
      UPDATE processed_episodes
      SET status = 'queued',
          error = NULL,
          processed_path = NULL,
          queued_at = ?,
          started_at = NULL,
          completed_at = NULL
      WHERE episode_id = ? AND status = 'error'
    `).run(now, episodeId);
  }

  // Ensure processed_episodes row exists with 'queued' status
  db.prepare(`
    INSERT INTO processed_episodes (episode_id, status, queued_at)
    VALUES (?, 'queued', ?)
    ON CONFLICT(episode_id) DO UPDATE SET
      status = CASE WHEN status IN ('none', 'error') THEN 'queued' ELSE status END,
      queued_at = CASE WHEN status IN ('none', 'error') THEN ? ELSE queued_at END
  `).run(episodeId, now, now);

  db.prepare(`
    INSERT INTO queue (episode_id, priority, created_at)
    VALUES (?, ?, ?)
    ON CONFLICT(episode_id) DO UPDATE SET priority = MAX(priority, excluded.priority)
  `).run(episodeId, priority, now);
}

export function addAllEpisodesToQueue(podcastId: string, priority: number = 0): number {
  const episodes = db.prepare(`
    SELECT e.episode_id
    FROM episodes e
    LEFT JOIN processed_episodes pe ON e.episode_id = pe.episode_id
    WHERE e.podcast_id = ?
      AND (pe.status IS NULL OR pe.status IN ('none', 'error'))
  `).all(podcastId) as { episode_id: string }[];

  const addMany = db.transaction((eps: { episode_id: string }[]) => {
    for (const ep of eps) {
      addToQueue(ep.episode_id, priority);
    }
    return eps.length;
  });

  return addMany(episodes);
}

export function removeFromQueue(episodeId: string): void {
  db.prepare('DELETE FROM queue WHERE episode_id = ?').run(episodeId);
}

export function getNextInQueue(): QueueItem | null {
  // Order by priority DESC, then oldest episodes first (pub_date ASC)
  const stmt = db.prepare(`
    SELECT
      q.id,
      q.episode_id as episodeId,
      q.priority,
      q.created_at as createdAt,
      e.title as episodeTitle,
      e.original_url as audioUrl,
      e.pub_date as pubDate,
      s.title as podcastTitle,
      s.podcast_id as podcastId
    FROM queue q
    JOIN episodes e ON q.episode_id = e.episode_id
    JOIN subscriptions s ON e.podcast_id = s.podcast_id
    ORDER BY q.priority DESC, e.pub_date ASC
    LIMIT 1
  `);
  return stmt.get() as QueueItem | null;
}

export function getNextBatchFromQueue(limit: number = 4): QueueItem[] {
  // Get multiple items for parallel processing, excluding currently processing
  // Dates stored in ISO 8601 format sort correctly as strings
  const stmt = db.prepare(`
    SELECT
      q.id,
      q.episode_id as episodeId,
      q.priority,
      q.created_at as createdAt,
      e.title as episodeTitle,
      e.original_url as audioUrl,
      e.pub_date as pubDate,
      s.title as podcastTitle,
      s.podcast_id as podcastId
    FROM queue q
    JOIN episodes e ON q.episode_id = e.episode_id
    JOIN subscriptions s ON e.podcast_id = s.podcast_id
    LEFT JOIN processed_episodes pe ON q.episode_id = pe.episode_id
    WHERE pe.status IS NULL OR pe.status NOT IN ('processing', 'ready')
    ORDER BY q.priority DESC, e.pub_date ASC
    LIMIT ?
  `);
  return stmt.all(limit) as QueueItem[];
}

export function getQueueStatus(): {
  total: number;
  processing: number;
  items: QueueItem[];
} {
  const total = (db.prepare('SELECT COUNT(*) as count FROM queue').get() as { count: number }).count;

  const processing = (db.prepare(`
    SELECT COUNT(*) as count FROM processed_episodes WHERE status = 'processing'
  `).get() as { count: number }).count;

  const items = db.prepare(`
    SELECT
      q.id,
      q.episode_id as episodeId,
      q.priority,
      q.created_at as createdAt,
      e.title as episodeTitle,
      e.pub_date as pubDate,
      s.title as podcastTitle,
      pe.status
    FROM queue q
    JOIN episodes e ON q.episode_id = e.episode_id
    JOIN subscriptions s ON e.podcast_id = s.podcast_id
    LEFT JOIN processed_episodes pe ON q.episode_id = pe.episode_id
    ORDER BY q.priority DESC, e.pub_date ASC
    LIMIT 20
  `).all() as QueueItem[];

  return { total, processing, items };
}

export function clearQueue(): void {
  db.prepare('DELETE FROM queue').run();
}

export function isInQueue(episodeId: string): boolean {
  const stmt = db.prepare('SELECT 1 FROM queue WHERE episode_id = ?');
  return stmt.get(episodeId) !== undefined;
}
