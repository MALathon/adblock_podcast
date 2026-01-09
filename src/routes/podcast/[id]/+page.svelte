<script lang="ts">
  import { page } from '$app/stores';
  import { player } from '$lib/stores/player.svelte';
  import type { Podcast, Episode } from '$lib/types';

  let podcast = $state<Podcast | null>(null);
  let episodes = $state<Episode[]>([]);
  let isLoading = $state(true);
  let error = $state<string | null>(null);
  let processingEpisodes = $state<Set<string>>(new Set());

  // Fetch podcast data on mount
  $effect(() => {
    const id = $page.params.id;
    fetchPodcast(id);
  });

  async function fetchPodcast(id: string) {
    isLoading = true;
    error = null;

    try {
      const response = await fetch(`/api/podcast/${id}`);
      if (!response.ok) throw new Error('Failed to fetch podcast');

      const data = await response.json();
      podcast = data.podcast;
      episodes = data.episodes;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unknown error';
    } finally {
      isLoading = false;
    }
  }

  function formatDuration(seconds: number): string {
    if (!seconds) return '';
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${mins}m`;
    }
    return `${mins} min`;
  }

  function formatDate(dateStr: string): string {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      });
    } catch {
      return '';
    }
  }

  function playEpisode(episode: Episode) {
    player.play({
      id: episode.id,
      title: episode.title,
      podcastTitle: episode.podcastTitle,
      audioUrl: episode.audioUrl,
      artworkUrl: episode.artworkUrl
    });
  }

  async function processAndPlay(episode: Episode) {
    // Mark episode as processing
    processingEpisodes = new Set([...processingEpisodes, episode.id]);

    try {
      // Call the processing API
      const response = await fetch('/api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          episodeId: episode.id,
          audioUrl: episode.audioUrl,
          title: episode.title,
          podcastTitle: episode.podcastTitle
        })
      });

      if (!response.ok) {
        throw new Error('Processing failed');
      }

      const result = await response.json();

      // Play the processed audio
      player.play({
        id: episode.id,
        title: episode.title,
        podcastTitle: episode.podcastTitle,
        audioUrl: result.processedAudioUrl || episode.audioUrl,
        artworkUrl: episode.artworkUrl
      });
    } catch (e) {
      console.error('Processing error:', e);
      // Fallback to playing original
      playEpisode(episode);
    } finally {
      processingEpisodes = new Set([...processingEpisodes].filter(id => id !== episode.id));
    }
  }
</script>

{#if isLoading}
  <div class="loading">
    <div class="spinner"></div>
    <p>Loading podcast...</p>
  </div>
{:else if error}
  <div class="error-state">
    <p>Error: {error}</p>
    <a href="/" class="btn btn--secondary">Back to search</a>
  </div>
{:else if podcast}
  <div class="podcast-header">
    <a href="/" class="back-link">← Back</a>

    <div class="podcast-info">
      <img
        src={podcast.artworkUrl}
        alt=""
        class="podcast-artwork"
      />
      <div class="podcast-details">
        <h1 class="podcast-title">{podcast.title}</h1>
        <p class="podcast-artist">{podcast.artist}</p>
        {#if podcast.genre}
          <span class="podcast-genre">{podcast.genre}</span>
        {/if}
      </div>
    </div>
  </div>

  <div class="episodes-header">
    <h2>Episodes</h2>
    <span class="episode-count">{episodes.length} episodes</span>
  </div>

  <div class="episode-list">
    {#each episodes as episode (episode.id)}
      <div class="episode-item">
        <button
          class="episode-item__play"
          onclick={() => playEpisode(episode)}
          disabled={processingEpisodes.has(episode.id)}
          aria-label="Play episode"
        >
          {#if processingEpisodes.has(episode.id)}
            <div class="spinner"></div>
          {:else}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
            </svg>
          {/if}
        </button>

        <div class="episode-item__info">
          <div class="episode-item__title">{episode.title}</div>
          <div class="episode-item__meta">
            {formatDate(episode.pubDate)}
            {#if episode.duration}
              <span>•</span>
              {formatDuration(episode.duration)}
            {/if}
          </div>
        </div>

        <div class="episode-item__actions">
          <button
            class="btn btn--secondary btn--small"
            onclick={() => processAndPlay(episode)}
            disabled={processingEpisodes.has(episode.id)}
          >
            {#if processingEpisodes.has(episode.id)}
              Processing...
            {:else}
              Remove Ads
            {/if}
          </button>
        </div>
      </div>
    {/each}
  </div>
{/if}

<style>
  .loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-12);
    gap: var(--space-4);
    color: var(--text-secondary);
  }

  .error-state {
    text-align: center;
    padding: var(--space-12);
    color: var(--text-secondary);
  }

  .back-link {
    display: inline-block;
    color: var(--accent);
    text-decoration: none;
    font-size: var(--text-sm);
    margin-bottom: var(--space-6);
  }

  .back-link:hover {
    text-decoration: underline;
  }

  .podcast-header {
    margin-bottom: var(--space-8);
  }

  .podcast-info {
    display: flex;
    gap: var(--space-6);
    align-items: flex-start;
  }

  .podcast-artwork {
    width: 180px;
    height: 180px;
    border-radius: var(--radius-lg);
    object-fit: cover;
    flex-shrink: 0;
  }

  .podcast-details {
    flex: 1;
    min-width: 0;
  }

  .podcast-title {
    font-size: var(--text-2xl);
    font-weight: var(--font-semibold);
    color: var(--text-primary);
    margin-bottom: var(--space-2);
  }

  .podcast-artist {
    font-size: var(--text-lg);
    color: var(--text-secondary);
    margin-bottom: var(--space-3);
  }

  .podcast-genre {
    display: inline-block;
    padding: var(--space-1) var(--space-3);
    background: var(--bg-elevated);
    border-radius: var(--radius-md);
    font-size: var(--text-xs);
    color: var(--text-secondary);
  }

  .episodes-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-4);
    padding-bottom: var(--space-4);
    border-bottom: 1px solid var(--border);
  }

  .episodes-header h2 {
    font-size: var(--text-lg);
    font-weight: var(--font-semibold);
  }

  .episode-count {
    font-size: var(--text-sm);
    color: var(--text-muted);
  }

  .btn--small {
    padding: var(--space-1) var(--space-3);
    font-size: var(--text-xs);
  }

  .episode-item__play:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
</style>
