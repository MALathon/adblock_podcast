/**
 * Test database setup utility
 * Creates in-memory database and mocks the db module
 */
import Database from 'better-sqlite3';
import { vi } from 'vitest';

export function createTestDb(): Database.Database {
  const testDb = new Database(':memory:');

  // Initialize schema
  testDb.exec(`
    CREATE TABLE subscriptions (
      podcast_id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      artist TEXT,
      artwork_url TEXT,
      feed_url TEXT NOT NULL,
      description TEXT,
      genre TEXT,
      subscribed_at TEXT NOT NULL,
      last_refreshed TEXT
    );

    CREATE TABLE episodes (
      episode_id TEXT PRIMARY KEY,
      podcast_id TEXT NOT NULL,
      title TEXT NOT NULL,
      description TEXT,
      pub_date TEXT,
      duration INTEGER,
      original_url TEXT NOT NULL,
      artwork_url TEXT,
      FOREIGN KEY (podcast_id) REFERENCES subscriptions(podcast_id) ON DELETE CASCADE
    );

    CREATE TABLE processed_episodes (
      episode_id TEXT PRIMARY KEY,
      processed_path TEXT,
      status TEXT DEFAULT 'pending',
      original_duration INTEGER,
      processed_duration INTEGER,
      ads_removed_seconds REAL,
      error TEXT,
      queued_at TEXT,
      started_at TEXT,
      completed_at TEXT,
      FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
    );

    CREATE TABLE queue (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      episode_id TEXT UNIQUE NOT NULL,
      priority INTEGER DEFAULT 0,
      created_at TEXT NOT NULL,
      FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
    );

    CREATE INDEX idx_episodes_podcast ON episodes(podcast_id);
    CREATE INDEX idx_processed_status ON processed_episodes(status);
    CREATE INDEX idx_queue_priority ON queue(priority DESC, created_at ASC);
  `);

  return testDb;
}

export function mockDbModule(testDb: Database.Database) {
  vi.doMock('$lib/db/index', () => ({
    db: testDb
  }));
}

export function insertTestData(testDb: Database.Database) {
  // Insert test subscription
  testDb.prepare(`
    INSERT INTO subscriptions (podcast_id, title, artist, feed_url, subscribed_at)
    VALUES ('pod1', 'Test Podcast', 'Test Artist', 'http://test.com/feed', '2024-01-01T00:00:00Z')
  `).run();

  // Insert test episodes
  testDb.prepare(`
    INSERT INTO episodes (episode_id, podcast_id, title, original_url, pub_date)
    VALUES
      ('ep1', 'pod1', 'Episode 1', 'http://test.com/ep1.mp3', '2024-01-01T00:00:00Z'),
      ('ep2', 'pod1', 'Episode 2', 'http://test.com/ep2.mp3', '2024-01-02T00:00:00Z'),
      ('ep3', 'pod1', 'Episode 3', 'http://test.com/ep3.mp3', '2024-01-03T00:00:00Z')
  `).run();
}
