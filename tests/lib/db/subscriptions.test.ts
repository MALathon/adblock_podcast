import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import Database from 'better-sqlite3';
import type { Subscription, Podcast } from '$lib/types';

// Test database
let testDb: Database.Database;

// Recreate subscription functions with test database
function createSubscriptionFunctions(db: Database.Database) {
  const getAllSubscriptions = (): Subscription[] => {
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
  };

  const getSubscription = (podcastId: string): Subscription | null => {
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
  };

  const isSubscribed = (podcastId: string): boolean => {
    const stmt = db.prepare('SELECT 1 FROM subscriptions WHERE podcast_id = ?');
    return stmt.get(podcastId) !== undefined;
  };

  const subscribe = (podcast: Podcast): Subscription => {
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
  };

  const unsubscribe = (podcastId: string): boolean => {
    const stmt = db.prepare('DELETE FROM subscriptions WHERE podcast_id = ?');
    const result = stmt.run(podcastId);
    return result.changes > 0;
  };

  const updateLastRefreshed = (podcastId: string): void => {
    const stmt = db.prepare(`
      UPDATE subscriptions SET last_refreshed = ? WHERE podcast_id = ?
    `);
    stmt.run(new Date().toISOString(), podcastId);
  };

  return { subscribe, unsubscribe, isSubscribed, getAllSubscriptions, getSubscription, updateLastRefreshed };
}

let subFns: ReturnType<typeof createSubscriptionFunctions>;

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
  `);

  subFns = createSubscriptionFunctions(testDb);
});

afterEach(() => {
  if (testDb) {
    testDb.close();
  }
});

describe('subscribe', () => {
  it('should insert new subscription with all fields', () => {
    // Arrange
    const podcast: Podcast = {
      id: 'pod1',
      title: 'Test Podcast',
      artist: 'Test Artist',
      artworkUrl: 'http://test.com/art.jpg',
      feedUrl: 'http://test.com/feed.xml',
      description: 'Test description',
      genre: 'Technology'
    };

    // Act
    const result = subFns.subscribe(podcast);

    // Assert
    expect(result.podcastId).toBe('pod1');
    expect(result.title).toBe('Test Podcast');
    expect(result.artist).toBe('Test Artist');
    expect(result.artworkUrl).toBe('http://test.com/art.jpg');
    expect(result.feedUrl).toBe('http://test.com/feed.xml');
    expect(result.description).toBe('Test description');
    expect(result.genre).toBe('Technology');
    expect(result.subscribedAt).toBeDefined();
    expect(result.lastRefreshed).toBeNull();
  });

  it('should handle optional fields as null', () => {
    // Arrange
    const podcast: Podcast = {
      id: 'pod1',
      title: 'Test Podcast',
      artist: 'Test Artist',
      artworkUrl: 'http://test.com/art.jpg',
      feedUrl: 'http://test.com/feed.xml'
    };

    // Act
    const result = subFns.subscribe(podcast);

    // Assert
    expect(result.description).toBeUndefined();
    expect(result.genre).toBeUndefined();
  });

  it('should persist subscription to database', () => {
    // Arrange
    const podcast: Podcast = {
      id: 'pod1',
      title: 'Test Podcast',
      artist: 'Test Artist',
      artworkUrl: 'http://test.com/art.jpg',
      feedUrl: 'http://test.com/feed.xml'
    };

    // Act
    subFns.subscribe(podcast);

    // Assert
    const row = testDb.prepare('SELECT * FROM subscriptions WHERE podcast_id = ?').get('pod1') as any;
    expect(row).toBeDefined();
    expect(row.title).toBe('Test Podcast');
  });

  it('should set subscribedAt to current time', () => {
    // Arrange
    const podcast: Podcast = {
      id: 'pod1',
      title: 'Test Podcast',
      artist: 'Test Artist',
      artworkUrl: 'http://test.com/art.jpg',
      feedUrl: 'http://test.com/feed.xml'
    };
    const beforeTime = new Date().toISOString();

    // Act
    const result = subFns.subscribe(podcast);

    // Assert
    const afterTime = new Date().toISOString();
    expect(result.subscribedAt).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(result.subscribedAt >= beforeTime).toBe(true);
    expect(result.subscribedAt <= afterTime).toBe(true);
  });
});

describe('unsubscribe', () => {
  it('should remove subscription when it exists', () => {
    // Arrange
    testDb.prepare(`
      INSERT INTO subscriptions (podcast_id, title, artist, feed_url, subscribed_at)
      VALUES ('pod1', 'Test Podcast', 'Test Artist', 'http://test.com/feed', '2024-01-01T00:00:00Z')
    `).run();

    // Act
    const result = subFns.unsubscribe('pod1');

    // Assert
    expect(result).toBe(true);
    const row = testDb.prepare('SELECT * FROM subscriptions WHERE podcast_id = ?').get('pod1');
    expect(row).toBeUndefined();
  });

  it('should return false when subscription does not exist', () => {
    // Act
    const result = subFns.unsubscribe('nonexistent');

    // Assert
    expect(result).toBe(false);
  });

  it('should only remove specified subscription', () => {
    // Arrange
    testDb.prepare(`
      INSERT INTO subscriptions (podcast_id, title, artist, feed_url, subscribed_at)
      VALUES
        ('pod1', 'Podcast 1', 'Artist 1', 'http://test.com/feed1', '2024-01-01T00:00:00Z'),
        ('pod2', 'Podcast 2', 'Artist 2', 'http://test.com/feed2', '2024-01-01T00:00:00Z')
    `).run();

    // Act
    subFns.unsubscribe('pod1');

    // Assert
    const remaining = testDb.prepare('SELECT COUNT(*) as count FROM subscriptions').get() as any;
    expect(remaining.count).toBe(1);
    const pod2 = testDb.prepare('SELECT * FROM subscriptions WHERE podcast_id = ?').get('pod2');
    expect(pod2).toBeDefined();
  });
});

describe('isSubscribed', () => {
  it('should return true when podcast is subscribed', () => {
    // Arrange
    testDb.prepare(`
      INSERT INTO subscriptions (podcast_id, title, artist, feed_url, subscribed_at)
      VALUES ('pod1', 'Test Podcast', 'Test Artist', 'http://test.com/feed', '2024-01-01T00:00:00Z')
    `).run();

    // Act
    const result = subFns.isSubscribed('pod1');

    // Assert
    expect(result).toBe(true);
  });

  it('should return false when podcast is not subscribed', () => {
    // Act
    const result = subFns.isSubscribed('pod1');

    // Assert
    expect(result).toBe(false);
  });

  it('should return false after unsubscribing', () => {
    // Arrange
    testDb.prepare(`
      INSERT INTO subscriptions (podcast_id, title, artist, feed_url, subscribed_at)
      VALUES ('pod1', 'Test Podcast', 'Test Artist', 'http://test.com/feed', '2024-01-01T00:00:00Z')
    `).run();
    subFns.unsubscribe('pod1');

    // Act
    const result = subFns.isSubscribed('pod1');

    // Assert
    expect(result).toBe(false);
  });
});

describe('getAllSubscriptions', () => {
  it('should return empty array when no subscriptions exist', () => {
    // Act
    const result = subFns.getAllSubscriptions();

    // Assert
    expect(result).toEqual([]);
  });

  it('should return all subscriptions ordered by title', () => {
    // Arrange
    testDb.prepare(`
      INSERT INTO subscriptions (podcast_id, title, artist, feed_url, subscribed_at)
      VALUES
        ('pod1', 'Zebra Podcast', 'Artist 1', 'http://test.com/feed1', '2024-01-01T00:00:00Z'),
        ('pod2', 'Alpha Podcast', 'Artist 2', 'http://test.com/feed2', '2024-01-02T00:00:00Z'),
        ('pod3', 'Middle Podcast', 'Artist 3', 'http://test.com/feed3', '2024-01-03T00:00:00Z')
    `).run();

    // Act
    const result = subFns.getAllSubscriptions();

    // Assert
    expect(result).toHaveLength(3);
    expect(result[0].title).toBe('Alpha Podcast');
    expect(result[1].title).toBe('Middle Podcast');
    expect(result[2].title).toBe('Zebra Podcast');
  });

  it('should map database fields to camelCase', () => {
    // Arrange
    testDb.prepare(`
      INSERT INTO subscriptions (podcast_id, title, artist, artwork_url, feed_url, subscribed_at, last_refreshed)
      VALUES ('pod1', 'Test', 'Artist', 'http://art.jpg', 'http://feed.xml', '2024-01-01T00:00:00Z', '2024-01-02T00:00:00Z')
    `).run();

    // Act
    const result = subFns.getAllSubscriptions();

    // Assert
    expect(result[0]).toMatchObject({
      podcastId: 'pod1',
      artworkUrl: 'http://art.jpg',
      feedUrl: 'http://feed.xml',
      subscribedAt: '2024-01-01T00:00:00Z',
      lastRefreshed: '2024-01-02T00:00:00Z'
    });
  });
});

describe('getSubscription', () => {
  it('should return subscription when it exists', () => {
    // Arrange
    testDb.prepare(`
      INSERT INTO subscriptions (podcast_id, title, artist, feed_url, subscribed_at)
      VALUES ('pod1', 'Test Podcast', 'Test Artist', 'http://test.com/feed', '2024-01-01T00:00:00Z')
    `).run();

    // Act
    const result = subFns.getSubscription('pod1');

    // Assert
    expect(result).toBeDefined();
    expect(result?.podcastId).toBe('pod1');
    expect(result?.title).toBe('Test Podcast');
  });

  it('should return null when subscription does not exist', () => {
    // Act
    const result = subFns.getSubscription('nonexistent');

    // Assert
    expect(result).toBeUndefined();
  });

  it('should include all subscription fields', () => {
    // Arrange
    testDb.prepare(`
      INSERT INTO subscriptions (
        podcast_id, title, artist, artwork_url, feed_url,
        description, genre, subscribed_at, last_refreshed
      )
      VALUES (
        'pod1', 'Test Podcast', 'Test Artist', 'http://art.jpg', 'http://feed.xml',
        'Description', 'Tech', '2024-01-01T00:00:00Z', '2024-01-02T00:00:00Z'
      )
    `).run();

    // Act
    const result = subFns.getSubscription('pod1');

    // Assert
    expect(result).toMatchObject({
      podcastId: 'pod1',
      title: 'Test Podcast',
      artist: 'Test Artist',
      artworkUrl: 'http://art.jpg',
      feedUrl: 'http://feed.xml',
      description: 'Description',
      genre: 'Tech',
      subscribedAt: '2024-01-01T00:00:00Z',
      lastRefreshed: '2024-01-02T00:00:00Z'
    });
  });
});

describe('updateLastRefreshed', () => {
  it('should update last_refreshed timestamp', () => {
    // Arrange
    testDb.prepare(`
      INSERT INTO subscriptions (podcast_id, title, artist, feed_url, subscribed_at)
      VALUES ('pod1', 'Test Podcast', 'Test Artist', 'http://test.com/feed', '2024-01-01T00:00:00Z')
    `).run();
    const beforeTime = new Date().toISOString();

    // Act
    subFns.updateLastRefreshed('pod1');

    // Assert
    const afterTime = new Date().toISOString();
    const row = testDb.prepare('SELECT last_refreshed FROM subscriptions WHERE podcast_id = ?').get('pod1') as any;
    expect(row.last_refreshed).toBeDefined();
    expect(row.last_refreshed >= beforeTime).toBe(true);
    expect(row.last_refreshed <= afterTime).toBe(true);
  });

  it('should only update specified subscription', () => {
    // Arrange
    testDb.prepare(`
      INSERT INTO subscriptions (podcast_id, title, artist, feed_url, subscribed_at)
      VALUES
        ('pod1', 'Podcast 1', 'Artist 1', 'http://test.com/feed1', '2024-01-01T00:00:00Z'),
        ('pod2', 'Podcast 2', 'Artist 2', 'http://test.com/feed2', '2024-01-01T00:00:00Z')
    `).run();

    // Act
    subFns.updateLastRefreshed('pod1');

    // Assert
    const pod1 = testDb.prepare('SELECT last_refreshed FROM subscriptions WHERE podcast_id = ?').get('pod1') as any;
    const pod2 = testDb.prepare('SELECT last_refreshed FROM subscriptions WHERE podcast_id = ?').get('pod2') as any;
    expect(pod1.last_refreshed).toBeDefined();
    expect(pod2.last_refreshed).toBeNull();
  });
});
