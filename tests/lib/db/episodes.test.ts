import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import Database from 'better-sqlite3';
import type { Episode, ProcessedEpisode, EpisodeStatus } from '$lib/types';

// Create in-memory database for testing
let testDb: Database.Database;

// Recreate episode functions with test database
function createEpisodeFunctions(db: Database.Database) {
  const toISODate = (dateStr: string | undefined): string | null => {
    if (!dateStr) return null;
    try {
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return dateStr;
      return date.toISOString().split('T')[0];
    } catch {
      return dateStr;
    }
  };

  const upsertEpisode = (episode: Episode): void => {
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
  };

  const getProcessedEpisode = (episodeId: string): ProcessedEpisode | null => {
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
  };

  const setProcessingStatus = (
    episodeId: string,
    status: EpisodeStatus,
    extra?: Partial<ProcessedEpisode>
  ): void => {
    const now = new Date().toISOString();

    const existing = getProcessedEpisode(episodeId);
    if (!existing) {
      db.prepare(`
        INSERT INTO processed_episodes (episode_id, status, queued_at)
        VALUES (?, ?, ?)
      `).run(episodeId, status, now);
    }

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
  };

  const getEpisode = (episodeId: string): Episode | null => {
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
  };

  const getEpisodesForPodcast = (podcastId: string): Episode[] => {
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
  };

  return { upsertEpisode, setProcessingStatus, getProcessedEpisode, getEpisode, getEpisodesForPodcast };
}

let episodeFns: ReturnType<typeof createEpisodeFunctions>;

beforeEach(() => {
  // Create fresh in-memory database for each test
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

    CREATE INDEX idx_episodes_podcast ON episodes(podcast_id);
    CREATE INDEX idx_processed_status ON processed_episodes(status);
  `);

  // Insert test subscription
  testDb.prepare(`
    INSERT INTO subscriptions (podcast_id, title, artist, feed_url, subscribed_at)
    VALUES ('pod1', 'Test Podcast', 'Test Artist', 'http://test.com/feed', '2024-01-01T00:00:00Z')
  `).run();

  episodeFns = createEpisodeFunctions(testDb);
});

afterEach(() => {
  if (testDb) {
    testDb.close();
  }
});

describe('upsertEpisode', () => {
  it('should insert new episode with all fields', () => {
    // Arrange
    const episode: Episode = {
      id: 'ep1',
      podcastId: 'pod1',
      podcastTitle: 'Test Podcast',
      title: 'Episode 1',
      description: 'Test description',
      pubDate: '2024-01-15T12:00:00Z',
      duration: 3600,
      audioUrl: 'http://test.com/ep1.mp3',
      artworkUrl: 'http://test.com/art1.jpg'
    };

    // Act
    episodeFns.upsertEpisode(episode);

    // Assert
    const row = testDb.prepare('SELECT * FROM episodes WHERE episode_id = ?').get('ep1') as any;
    expect(row).toBeDefined();
    expect(row.episode_id).toBe('ep1');
    expect(row.podcast_id).toBe('pod1');
    expect(row.title).toBe('Episode 1');
    expect(row.description).toBe('Test description');
    expect(row.pub_date).toBe('2024-01-15');
    expect(row.duration).toBe(3600);
    expect(row.original_url).toBe('http://test.com/ep1.mp3');
    expect(row.artwork_url).toBe('http://test.com/art1.jpg');
  });

  it('should handle optional fields as null', () => {
    // Arrange
    const episode: Episode = {
      id: 'ep1',
      podcastId: 'pod1',
      podcastTitle: 'Test Podcast',
      title: 'Episode 1',
      pubDate: '2024-01-15T12:00:00Z',
      audioUrl: 'http://test.com/ep1.mp3'
    };

    // Act
    episodeFns.upsertEpisode(episode);

    // Assert
    const row = testDb.prepare('SELECT * FROM episodes WHERE episode_id = ?').get('ep1') as any;
    expect(row.description).toBeNull();
    expect(row.duration).toBeNull();
    expect(row.artwork_url).toBeNull();
  });

  it('should update existing episode on conflict', () => {
    // Arrange
    const episode1: Episode = {
      id: 'ep1',
      podcastId: 'pod1',
      podcastTitle: 'Test Podcast',
      title: 'Original Title',
      pubDate: '2024-01-15T12:00:00Z',
      audioUrl: 'http://test.com/ep1.mp3'
    };
    episodeFns.upsertEpisode(episode1);

    const episode2: Episode = {
      id: 'ep1',
      podcastId: 'pod1',
      podcastTitle: 'Test Podcast',
      title: 'Updated Title',
      description: 'New description',
      pubDate: '2024-01-15T12:00:00Z',
      duration: 1800,
      audioUrl: 'http://test.com/ep1-updated.mp3'
    };

    // Act
    episodeFns.upsertEpisode(episode2);

    // Assert
    const count = (testDb.prepare('SELECT COUNT(*) as count FROM episodes WHERE episode_id = ?').get('ep1') as any).count;
    expect(count).toBe(1);

    const row = testDb.prepare('SELECT * FROM episodes WHERE episode_id = ?').get('ep1') as any;
    expect(row.title).toBe('Updated Title');
    expect(row.description).toBe('New description');
    expect(row.duration).toBe(1800);
    expect(row.original_url).toBe('http://test.com/ep1-updated.mp3');
  });

  it('should convert RFC 2822 date to ISO date', () => {
    // Arrange
    const episode: Episode = {
      id: 'ep1',
      podcastId: 'pod1',
      podcastTitle: 'Test Podcast',
      title: 'Episode 1',
      pubDate: 'Mon, 15 Jan 2024 12:00:00 GMT',
      audioUrl: 'http://test.com/ep1.mp3'
    };

    // Act
    episodeFns.upsertEpisode(episode);

    // Assert
    const row = testDb.prepare('SELECT pub_date FROM episodes WHERE episode_id = ?').get('ep1') as any;
    expect(row.pub_date).toBe('2024-01-15');
  });
});

describe('setProcessingStatus', () => {
  beforeEach(() => {
    // Insert test episode
    const episode: Episode = {
      id: 'ep1',
      podcastId: 'pod1',
      podcastTitle: 'Test Podcast',
      title: 'Episode 1',
      pubDate: '2024-01-15T12:00:00Z',
      audioUrl: 'http://test.com/ep1.mp3'
    };
    episodeFns.upsertEpisode(episode);
  });

  it('should create processed_episodes entry if not exists', () => {
    // Act
    episodeFns.setProcessingStatus('ep1', 'queued');

    // Assert
    const row = testDb.prepare('SELECT * FROM processed_episodes WHERE episode_id = ?').get('ep1') as any;
    expect(row).toBeDefined();
    expect(row.status).toBe('queued');
    expect(row.queued_at).toBeDefined();
  });

  it('should update status to processing with started_at timestamp', () => {
    // Arrange
    episodeFns.setProcessingStatus('ep1', 'queued');
    const beforeTime = new Date().toISOString();

    // Act
    episodeFns.setProcessingStatus('ep1', 'processing');

    // Assert
    const afterTime = new Date().toISOString();
    const row = testDb.prepare('SELECT * FROM processed_episodes WHERE episode_id = ?').get('ep1') as any;
    expect(row.status).toBe('processing');
    expect(row.started_at).toBeDefined();
    expect(row.started_at >= beforeTime).toBe(true);
    expect(row.started_at <= afterTime).toBe(true);
  });

  it('should update status to ready with processing details', () => {
    // Arrange
    episodeFns.setProcessingStatus('ep1', 'queued');
    episodeFns.setProcessingStatus('ep1', 'processing');
    const beforeTime = new Date().toISOString();

    // Act
    episodeFns.setProcessingStatus('ep1', 'ready', {
      processedPath: '/path/to/processed.mp3',
      originalDuration: 3600,
      processedDuration: 3000,
      adsRemovedSeconds: 600
    });

    // Assert
    const afterTime = new Date().toISOString();
    const row = testDb.prepare('SELECT * FROM processed_episodes WHERE episode_id = ?').get('ep1') as any;
    expect(row.status).toBe('ready');
    expect(row.processed_path).toBe('/path/to/processed.mp3');
    expect(row.original_duration).toBe(3600);
    expect(row.processed_duration).toBe(3000);
    expect(row.ads_removed_seconds).toBe(600);
    expect(row.completed_at).toBeDefined();
    expect(row.completed_at >= beforeTime).toBe(true);
    expect(row.completed_at <= afterTime).toBe(true);
  });

  it('should update status to error with error message', () => {
    // Arrange
    episodeFns.setProcessingStatus('ep1', 'queued');
    episodeFns.setProcessingStatus('ep1', 'processing');
    const beforeTime = new Date().toISOString();

    // Act
    episodeFns.setProcessingStatus('ep1', 'error', {
      error: 'Download failed'
    });

    // Assert
    const afterTime = new Date().toISOString();
    const row = testDb.prepare('SELECT * FROM processed_episodes WHERE episode_id = ?').get('ep1') as any;
    expect(row.status).toBe('error');
    expect(row.error).toBe('Download failed');
    expect(row.completed_at).toBeDefined();
    expect(row.completed_at >= beforeTime).toBe(true);
    expect(row.completed_at <= afterTime).toBe(true);
  });

  it('should handle null extra fields gracefully', () => {
    // Arrange
    episodeFns.setProcessingStatus('ep1', 'queued');

    // Act
    episodeFns.setProcessingStatus('ep1', 'ready', {
      processedPath: '/path/to/file.mp3'
    });

    // Assert
    const row = testDb.prepare('SELECT * FROM processed_episodes WHERE episode_id = ?').get('ep1') as any;
    expect(row.status).toBe('ready');
    expect(row.processed_path).toBe('/path/to/file.mp3');
    expect(row.original_duration).toBeNull();
    expect(row.processed_duration).toBeNull();
    expect(row.ads_removed_seconds).toBeNull();
  });

  it('should update status without extra fields', () => {
    // Arrange
    episodeFns.setProcessingStatus('ep1', 'queued');

    // Act
    episodeFns.setProcessingStatus('ep1', 'none');

    // Assert
    const row = testDb.prepare('SELECT * FROM processed_episodes WHERE episode_id = ?').get('ep1') as any;
    expect(row.status).toBe('none');
  });
});

describe('getProcessedEpisode', () => {
  beforeEach(() => {
    // Insert test episode
    const episode: Episode = {
      id: 'ep1',
      podcastId: 'pod1',
      podcastTitle: 'Test Podcast',
      title: 'Episode 1',
      pubDate: '2024-01-15T12:00:00Z',
      audioUrl: 'http://test.com/ep1.mp3'
    };
    episodeFns.upsertEpisode(episode);
  });

  it('should return null when no processed episode exists', () => {
    // Act
    const result = episodeFns.getProcessedEpisode('ep1');

    // Assert
    expect(result).toBeUndefined();
  });

  it('should return processed episode with all fields', () => {
    // Arrange
    episodeFns.setProcessingStatus('ep1', 'queued');
    episodeFns.setProcessingStatus('ep1', 'processing');
    episodeFns.setProcessingStatus('ep1', 'ready', {
      processedPath: '/path/to/file.mp3',
      originalDuration: 3600,
      processedDuration: 3000,
      adsRemovedSeconds: 600
    });

    // Act
    const result = episodeFns.getProcessedEpisode('ep1');

    // Assert
    expect(result).toBeDefined();
    expect(result?.episodeId).toBe('ep1');
    expect(result?.status).toBe('ready');
    expect(result?.processedPath).toBe('/path/to/file.mp3');
    expect(result?.originalDuration).toBe(3600);
    expect(result?.processedDuration).toBe(3000);
    expect(result?.adsRemovedSeconds).toBe(600);
    expect(result?.queuedAt).toBeDefined();
    expect(result?.startedAt).toBeDefined();
    expect(result?.completedAt).toBeDefined();
  });

  it('should map database fields to camelCase', () => {
    // Arrange
    episodeFns.setProcessingStatus('ep1', 'ready', {
      processedPath: '/path/file.mp3',
      originalDuration: 3600,
      processedDuration: 3000,
      adsRemovedSeconds: 600
    });

    // Act
    const result = episodeFns.getProcessedEpisode('ep1');

    // Assert
    expect(result).toHaveProperty('episodeId');
    expect(result).toHaveProperty('processedPath');
    expect(result).toHaveProperty('originalDuration');
    expect(result).toHaveProperty('processedDuration');
    expect(result).toHaveProperty('adsRemovedSeconds');
  });

  it('should return error information when status is error', () => {
    // Arrange
    episodeFns.setProcessingStatus('ep1', 'error', {
      error: 'Network timeout'
    });

    // Act
    const result = episodeFns.getProcessedEpisode('ep1');

    // Assert
    expect(result?.status).toBe('error');
    expect(result?.error).toBe('Network timeout');
  });
});

describe('getEpisode', () => {
  it('should return null when episode does not exist', () => {
    // Act
    const result = episodeFns.getEpisode('nonexistent');

    // Assert
    expect(result).toBeUndefined();
  });

  it('should return episode with podcast information', () => {
    // Arrange
    const episode: Episode = {
      id: 'ep1',
      podcastId: 'pod1',
      podcastTitle: 'Test Podcast',
      title: 'Episode 1',
      description: 'Test description',
      pubDate: '2024-01-15T12:00:00Z',
      duration: 3600,
      audioUrl: 'http://test.com/ep1.mp3',
      artworkUrl: 'http://test.com/art.jpg'
    };
    episodeFns.upsertEpisode(episode);

    // Act
    const result = episodeFns.getEpisode('ep1');

    // Assert
    expect(result).toBeDefined();
    expect(result?.id).toBe('ep1');
    expect(result?.podcastId).toBe('pod1');
    expect(result?.podcastTitle).toBe('Test Podcast');
    expect(result?.title).toBe('Episode 1');
    expect(result?.description).toBe('Test description');
    expect(result?.duration).toBe(3600);
    expect(result?.audioUrl).toBe('http://test.com/ep1.mp3');
    expect(result?.artworkUrl).toBe('http://test.com/art.jpg');
  });
});

describe('getEpisodesForPodcast', () => {
  it('should return empty array when no episodes exist', () => {
    // Act
    const result = episodeFns.getEpisodesForPodcast('pod1');

    // Assert
    expect(result).toEqual([]);
  });

  it('should return episodes ordered by pub_date descending', () => {
    // Arrange
    const ep1: Episode = {
      id: 'ep1',
      podcastId: 'pod1',
      podcastTitle: 'Test Podcast',
      title: 'Episode 1',
      pubDate: '2024-01-01T00:00:00Z',
      audioUrl: 'http://test.com/ep1.mp3'
    };
    const ep2: Episode = {
      id: 'ep2',
      podcastId: 'pod1',
      podcastTitle: 'Test Podcast',
      title: 'Episode 2',
      pubDate: '2024-01-03T00:00:00Z',
      audioUrl: 'http://test.com/ep2.mp3'
    };
    const ep3: Episode = {
      id: 'ep3',
      podcastId: 'pod1',
      podcastTitle: 'Test Podcast',
      title: 'Episode 3',
      pubDate: '2024-01-02T00:00:00Z',
      audioUrl: 'http://test.com/ep3.mp3'
    };
    episodeFns.upsertEpisode(ep1);
    episodeFns.upsertEpisode(ep2);
    episodeFns.upsertEpisode(ep3);

    // Act
    const result = episodeFns.getEpisodesForPodcast('pod1');

    // Assert
    expect(result).toHaveLength(3);
    expect(result[0].id).toBe('ep2'); // 2024-01-03
    expect(result[1].id).toBe('ep3'); // 2024-01-02
    expect(result[2].id).toBe('ep1'); // 2024-01-01
  });

  it('should include processing status when available', () => {
    // Arrange
    const episode: Episode = {
      id: 'ep1',
      podcastId: 'pod1',
      podcastTitle: 'Test Podcast',
      title: 'Episode 1',
      pubDate: '2024-01-15T12:00:00Z',
      audioUrl: 'http://test.com/ep1.mp3'
    };
    episodeFns.upsertEpisode(episode);
    episodeFns.setProcessingStatus('ep1', 'ready', {
      processedPath: '/path/file.mp3'
    });

    // Act
    const result = episodeFns.getEpisodesForPodcast('pod1');

    // Assert
    expect(result[0].processingStatus).toBe('ready');
    expect(result[0].processedPath).toBe('/path/file.mp3');
  });

  it('should default processing status to none when not set', () => {
    // Arrange
    const episode: Episode = {
      id: 'ep1',
      podcastId: 'pod1',
      podcastTitle: 'Test Podcast',
      title: 'Episode 1',
      pubDate: '2024-01-15T12:00:00Z',
      audioUrl: 'http://test.com/ep1.mp3'
    };
    episodeFns.upsertEpisode(episode);

    // Act
    const result = episodeFns.getEpisodesForPodcast('pod1');

    // Assert
    expect(result[0].processingStatus).toBe('none');
  });

  it('should only return episodes for specified podcast', () => {
    // Arrange
    testDb.prepare(`
      INSERT INTO subscriptions (podcast_id, title, artist, feed_url, subscribed_at)
      VALUES ('pod2', 'Other Podcast', 'Other Artist', 'http://test.com/feed2', '2024-01-01T00:00:00Z')
    `).run();

    const ep1: Episode = {
      id: 'ep1',
      podcastId: 'pod1',
      podcastTitle: 'Test Podcast',
      title: 'Episode 1',
      pubDate: '2024-01-15T12:00:00Z',
      audioUrl: 'http://test.com/ep1.mp3'
    };
    const ep2: Episode = {
      id: 'ep2',
      podcastId: 'pod2',
      podcastTitle: 'Other Podcast',
      title: 'Episode 2',
      pubDate: '2024-01-16T12:00:00Z',
      audioUrl: 'http://test.com/ep2.mp3'
    };
    episodeFns.upsertEpisode(ep1);
    episodeFns.upsertEpisode(ep2);

    // Act
    const result = episodeFns.getEpisodesForPodcast('pod1');

    // Assert
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('ep1');
  });
});
