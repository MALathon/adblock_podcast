/**
 * Subscription CRUD operations
 */
import { db } from './index';
import type { Subscription, Podcast } from '$lib/types';

export function getAllSubscriptions(): Subscription[] {
  const stmt = db.prepare(`
    SELECT
      podcast_id as podcastId,
      title,
      artist,
      artwork_url as artworkUrl,
      feed_url as feedUrl,
      description,
      genre,
      subscribed_at as subscribedAt,
      last_refreshed as lastRefreshed
    FROM subscriptions
    ORDER BY title ASC
  `);
  return stmt.all() as Subscription[];
}

export function getSubscription(podcastId: string): Subscription | null {
  const stmt = db.prepare(`
    SELECT
      podcast_id as podcastId,
      title,
      artist,
      artwork_url as artworkUrl,
      feed_url as feedUrl,
      description,
      genre,
      subscribed_at as subscribedAt,
      last_refreshed as lastRefreshed
    FROM subscriptions
    WHERE podcast_id = ?
  `);
  return stmt.get(podcastId) as Subscription | null;
}

export function isSubscribed(podcastId: string): boolean {
  const stmt = db.prepare('SELECT 1 FROM subscriptions WHERE podcast_id = ?');
  return stmt.get(podcastId) !== undefined;
}

export function subscribe(podcast: Podcast): Subscription {
  const now = new Date().toISOString();
  const stmt = db.prepare(`
    INSERT INTO subscriptions (
      podcast_id, title, artist, artwork_url, feed_url,
      description, genre, subscribed_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `);

  stmt.run(
    podcast.id,
    podcast.title,
    podcast.artist,
    podcast.artworkUrl,
    podcast.feedUrl,
    podcast.description || null,
    podcast.genre || null,
    now
  );

  return {
    podcastId: podcast.id,
    title: podcast.title,
    artist: podcast.artist,
    artworkUrl: podcast.artworkUrl,
    feedUrl: podcast.feedUrl,
    description: podcast.description,
    genre: podcast.genre,
    subscribedAt: now,
    lastRefreshed: null
  };
}

export function unsubscribe(podcastId: string): boolean {
  const stmt = db.prepare('DELETE FROM subscriptions WHERE podcast_id = ?');
  const result = stmt.run(podcastId);
  return result.changes > 0;
}

export function updateLastRefreshed(podcastId: string): void {
  const stmt = db.prepare(`
    UPDATE subscriptions SET last_refreshed = ? WHERE podcast_id = ?
  `);
  stmt.run(new Date().toISOString(), podcastId);
}
