/**
 * SQLite database connection and schema initialization
 */
import Database from 'better-sqlite3';
import { join } from 'path';

const DB_PATH = join(process.cwd(), 'data', 'podcasts.db');

// Ensure data directory exists
import { mkdirSync, existsSync } from 'fs';
const dataDir = join(process.cwd(), 'data');
if (!existsSync(dataDir)) {
  mkdirSync(dataDir, { recursive: true });
}

// Create database connection
export const db = new Database(DB_PATH);

// Enable WAL mode for better concurrent access
db.pragma('journal_mode = WAL');

// Initialize schema
db.exec(`
  CREATE TABLE IF NOT EXISTS subscriptions (
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

  CREATE TABLE IF NOT EXISTS episodes (
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

  CREATE TABLE IF NOT EXISTS processed_episodes (
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

  CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT UNIQUE NOT NULL,
    priority INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_episodes_podcast ON episodes(podcast_id);
  CREATE INDEX IF NOT EXISTS idx_processed_status ON processed_episodes(status);
  CREATE INDEX IF NOT EXISTS idx_queue_priority ON queue(priority DESC, created_at ASC);
`);

console.log('[DB] SQLite database initialized at', DB_PATH);
