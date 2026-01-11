import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import Database from 'better-sqlite3';
import type { QueueItem } from '$lib/types';

// Test database and functions
let testDb: Database.Database;

// Recreate queue functions with test database
function createQueueFunctions(db: Database.Database) {
  const addToQueue = (episodeId: string, priority: number = 0, retry: boolean = false): void => {
    const now = new Date().toISOString();

    if (retry) {
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
  };

  const removeFromQueue = (episodeId: string): void => {
    db.prepare('DELETE FROM queue WHERE episode_id = ?').run(episodeId);
  };

  const getNextBatchFromQueue = (limit: number = 4): QueueItem[] => {
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
  };

  const getQueueStatus = (): { total: number; processing: number; items: QueueItem[] } => {
    const total = (db.prepare('SELECT COUNT(*) as count FROM queue').get() as { count: number }).count;
    const processing = (db.prepare(`SELECT COUNT(*) as count FROM processed_episodes WHERE status = 'processing'`).get() as { count: number }).count;

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
  };

  const clearQueue = (): void => {
    db.prepare('DELETE FROM queue').run();
  };

  const isInQueue = (episodeId: string): boolean => {
    const stmt = db.prepare('SELECT 1 FROM queue WHERE episode_id = ?');
    return stmt.get(episodeId) !== undefined;
  };

  return { addToQueue, removeFromQueue, getNextBatchFromQueue, getQueueStatus, clearQueue, isInQueue };
}

let queueFns: ReturnType<typeof createQueueFunctions>;

beforeEach(() => {
  testDb = new Database(':memory:');

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
      artwork_url TEXT
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
      completed_at TEXT
    );

    CREATE TABLE queue (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      episode_id TEXT UNIQUE NOT NULL,
      priority INTEGER DEFAULT 0,
      created_at TEXT NOT NULL
    );

    CREATE INDEX idx_episodes_podcast ON episodes(podcast_id);
    CREATE INDEX idx_processed_status ON processed_episodes(status);
    CREATE INDEX idx_queue_priority ON queue(priority DESC, created_at ASC);
  `);

  // Insert test data
  testDb.prepare(`
    INSERT INTO subscriptions (podcast_id, title, artist, feed_url, subscribed_at)
    VALUES ('pod1', 'Test Podcast', 'Test Artist', 'http://test.com/feed', '2024-01-01T00:00:00Z')
  `).run();

  testDb.prepare(`
    INSERT INTO episodes (episode_id, podcast_id, title, original_url, pub_date)
    VALUES
      ('ep1', 'pod1', 'Episode 1', 'http://test.com/ep1.mp3', '2024-01-01T00:00:00Z'),
      ('ep2', 'pod1', 'Episode 2', 'http://test.com/ep2.mp3', '2024-01-02T00:00:00Z'),
      ('ep3', 'pod1', 'Episode 3', 'http://test.com/ep3.mp3', '2024-01-03T00:00:00Z')
  `).run();

  queueFns = createQueueFunctions(testDb);
});

afterEach(() => {
  if (testDb) {
    testDb.close();
  }
});

describe('addToQueue', () => {
  it('should add episode to queue when episode exists', () => {
    // Act
    queueFns.addToQueue('ep1', 0);

    // Assert
    const result = testDb.prepare('SELECT * FROM queue WHERE episode_id = ?').get('ep1') as any;
    expect(result).toBeDefined();
    expect(result.episode_id).toBe('ep1');
    expect(result.priority).toBe(0);
  });

  it('should create processed_episodes entry with queued status', () => {
    // Act
    queueFns.addToQueue('ep1', 0);

    // Assert
    const result = testDb.prepare('SELECT * FROM processed_episodes WHERE episode_id = ?').get('ep1') as any;
    expect(result).toBeDefined();
    expect(result.status).toBe('queued');
    expect(result.queued_at).toBeDefined();
  });

  it('should set custom priority when provided', () => {
    // Act
    queueFns.addToQueue('ep1', 10);

    // Assert
    const result = testDb.prepare('SELECT priority FROM queue WHERE episode_id = ?').get('ep1') as any;
    expect(result.priority).toBe(10);
  });

  it('should update priority to higher value on conflict', () => {
    // Arrange
    queueFns.addToQueue('ep1', 5);

    // Act
    queueFns.addToQueue('ep1', 10);

    // Assert
    const result = testDb.prepare('SELECT priority FROM queue WHERE episode_id = ?').get('ep1') as any;
    expect(result.priority).toBe(10);
  });

  it('should not downgrade priority on conflict', () => {
    // Arrange
    queueFns.addToQueue('ep1', 10);

    // Act
    queueFns.addToQueue('ep1', 5);

    // Assert
    const result = testDb.prepare('SELECT priority FROM queue WHERE episode_id = ?').get('ep1') as any;
    expect(result.priority).toBe(10);
  });

  it('should reset error status when retry is true', () => {
    // Arrange
    testDb.prepare(`
      INSERT INTO processed_episodes (episode_id, status, error)
      VALUES ('ep1', 'error', 'Test error')
    `).run();

    // Act
    queueFns.addToQueue('ep1', 0, true);

    // Assert
    const result = testDb.prepare('SELECT * FROM processed_episodes WHERE episode_id = ?').get('ep1') as any;
    expect(result.status).toBe('queued');
    expect(result.error).toBeNull();
    expect(result.processed_path).toBeNull();
  });
});

describe('removeFromQueue', () => {
  it('should remove episode from queue when it exists', () => {
    // Arrange
    queueFns.addToQueue('ep1', 0);

    // Act
    queueFns.removeFromQueue('ep1');

    // Assert
    const result = testDb.prepare('SELECT * FROM queue WHERE episode_id = ?').get('ep1');
    expect(result).toBeUndefined();
  });

  it('should not throw error when episode not in queue', () => {
    // Act & Assert
    expect(() => queueFns.removeFromQueue('nonexistent')).not.toThrow();
  });
});

describe('getNextBatchFromQueue', () => {
  it('should return empty array when queue is empty', () => {
    // Act
    const result = queueFns.getNextBatchFromQueue(4);

    // Assert
    expect(result).toEqual([]);
  });

  it('should return queued items ordered by priority desc', () => {
    // Arrange
    queueFns.addToQueue('ep1', 5);
    queueFns.addToQueue('ep2', 10);
    queueFns.addToQueue('ep3', 1);

    // Act
    const result = queueFns.getNextBatchFromQueue(10);

    // Assert
    expect(result).toHaveLength(3);
    expect(result[0].priority).toBe(10);
    expect(result[1].priority).toBe(5);
    expect(result[2].priority).toBe(1);
  });

  it('should respect limit parameter', () => {
    // Arrange
    queueFns.addToQueue('ep1', 0);
    queueFns.addToQueue('ep2', 0);
    queueFns.addToQueue('ep3', 0);

    // Act
    const result = queueFns.getNextBatchFromQueue(2);

    // Assert
    expect(result).toHaveLength(2);
  });

  it('should default to limit of 4 when not specified', () => {
    // Arrange
    for (let i = 1; i <= 10; i++) {
      const epId = `ep${i}`;
      if (i > 3) {
        testDb.prepare(`
          INSERT INTO episodes (episode_id, podcast_id, title, original_url, pub_date)
          VALUES (?, 'pod1', ?, 'http://test.com/audio.mp3', '2024-01-01T00:00:00Z')
        `).run(epId, `Episode ${i}`);
      }
      queueFns.addToQueue(epId, 0);
    }

    // Act
    const result = queueFns.getNextBatchFromQueue();

    // Assert
    expect(result).toHaveLength(4);
  });

  it('should exclude episodes with processing status', () => {
    // Arrange
    queueFns.addToQueue('ep1', 0);
    queueFns.addToQueue('ep2', 0);

    testDb.prepare(`
      UPDATE processed_episodes SET status = 'processing' WHERE episode_id = 'ep1'
    `).run();

    // Act
    const result = queueFns.getNextBatchFromQueue(10);

    // Assert
    expect(result).toHaveLength(1);
    expect(result[0].episodeId).toBe('ep2');
  });

  it('should exclude episodes with ready status', () => {
    // Arrange
    queueFns.addToQueue('ep1', 0);
    queueFns.addToQueue('ep2', 0);

    testDb.prepare(`
      UPDATE processed_episodes SET status = 'ready' WHERE episode_id = 'ep1'
    `).run();

    // Act
    const result = queueFns.getNextBatchFromQueue(10);

    // Assert
    expect(result).toHaveLength(1);
    expect(result[0].episodeId).toBe('ep2');
  });

  it('should include episode metadata in result', () => {
    // Arrange
    queueFns.addToQueue('ep1', 5);

    // Act
    const result = queueFns.getNextBatchFromQueue(1);

    // Assert
    expect(result[0]).toMatchObject({
      episodeId: 'ep1',
      episodeTitle: 'Episode 1',
      podcastTitle: 'Test Podcast',
      podcastId: 'pod1',
      audioUrl: 'http://test.com/ep1.mp3',
      priority: 5
    });
  });
});

describe('getQueueStatus', () => {
  it('should return zero counts when queue is empty', () => {
    // Act
    const result = queueFns.getQueueStatus();

    // Assert
    expect(result.total).toBe(0);
    expect(result.processing).toBe(0);
    expect(result.items).toEqual([]);
  });

  it('should count total queue items correctly', () => {
    // Arrange
    queueFns.addToQueue('ep1', 0);
    queueFns.addToQueue('ep2', 0);
    queueFns.addToQueue('ep3', 0);

    // Act
    const result = queueFns.getQueueStatus();

    // Assert
    expect(result.total).toBe(3);
  });

  it('should count processing episodes correctly', () => {
    // Arrange
    queueFns.addToQueue('ep1', 0);
    queueFns.addToQueue('ep2', 0);

    testDb.prepare(`
      UPDATE processed_episodes SET status = 'processing' WHERE episode_id = 'ep1'
    `).run();

    // Act
    const result = queueFns.getQueueStatus();

    // Assert
    expect(result.processing).toBe(1);
  });

  it('should return queue items with status', () => {
    // Arrange
    queueFns.addToQueue('ep1', 5);
    testDb.prepare(`
      UPDATE processed_episodes SET status = 'processing' WHERE episode_id = 'ep1'
    `).run();

    // Act
    const result = queueFns.getQueueStatus();

    // Assert
    expect(result.items).toHaveLength(1);
    expect(result.items[0].status).toBe('processing');
    expect(result.items[0].priority).toBe(5);
  });

  it('should limit results to 20 items', () => {
    // Arrange
    for (let i = 1; i <= 30; i++) {
      const epId = `ep${i}`;
      if (i > 3) {
        testDb.prepare(`
          INSERT INTO episodes (episode_id, podcast_id, title, original_url, pub_date)
          VALUES (?, 'pod1', ?, 'http://test.com/audio.mp3', '2024-01-01T00:00:00Z')
        `).run(epId, `Episode ${i}`);
      }
      queueFns.addToQueue(epId, 0);
    }

    // Act
    const result = queueFns.getQueueStatus();

    // Assert
    expect(result.total).toBe(30);
    expect(result.items).toHaveLength(20);
  });
});

describe('clearQueue', () => {
  it('should remove all items from queue', () => {
    // Arrange
    queueFns.addToQueue('ep1', 0);
    queueFns.addToQueue('ep2', 0);
    queueFns.addToQueue('ep3', 0);

    // Act
    queueFns.clearQueue();

    // Assert
    const count = (testDb.prepare('SELECT COUNT(*) as count FROM queue').get() as any).count;
    expect(count).toBe(0);
  });
});

describe('isInQueue', () => {
  it('should return true when episode is in queue', () => {
    // Arrange
    queueFns.addToQueue('ep1', 0);

    // Act
    const result = queueFns.isInQueue('ep1');

    // Assert
    expect(result).toBe(true);
  });

  it('should return false when episode is not in queue', () => {
    // Act
    const result = queueFns.isInQueue('ep1');

    // Assert
    expect(result).toBe(false);
  });

  it('should return false after episode is removed from queue', () => {
    // Arrange
    queueFns.addToQueue('ep1', 0);
    queueFns.removeFromQueue('ep1');

    // Act
    const result = queueFns.isInQueue('ep1');

    // Assert
    expect(result).toBe(false);
  });
});
