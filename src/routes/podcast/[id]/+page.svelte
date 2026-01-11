<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { library } from '$lib/stores/library.svelte';
  import EpisodeRow from '$lib/components/podcast/EpisodeRow.svelte';
  import type { Podcast, Episode } from '$lib/types';

  let podcast = $state<Podcast | null>(null);
  let episodes = $state<Episode[]>([]);
  let isLoading = $state(true);
  let error = $state<string | null>(null);
  let showFeedUrl = $state(false);
  let selectedEpisodes = $state<Set<string>>(new Set());
  let isQueueing = $state(false);
  let selectedSeason = $state<string>('');  // Filter by season

  const podcastId = $derived($page.params.id ?? '');
  const isSubscribed = $derived(podcastId ? library.isSubscribed(podcastId) : false);
  const feedUrl = $derived(
    typeof window !== 'undefined' && podcastId
      ? `${window.location.protocol}//${window.location.host}/feed/${podcastId}.xml`
      : ''
  );

  // Group episodes by processing status
  const readyEpisodes = $derived(episodes.filter(e => e.processingStatus === 'ready'));
  const processingEpisodes = $derived(episodes.filter(e => e.processingStatus === 'processing'));
  const queuedEpisodes = $derived(episodes.filter(e => e.processingStatus === 'queued'));
  const errorEpisodes = $derived(episodes.filter(e => e.processingStatus === 'error'));
  const otherEpisodes = $derived(episodes.filter(e => !e.processingStatus || e.processingStatus === 'none'));

  // Helper to get season from episode title
  function getEpisodeSeason(title: string): string | null {
    const match = title.match(/S(\d+)|Season\s*(\d+)/i);
    return match ? (match[1] || match[2]) : null;
  }

  // Detect seasons from episode titles (e.g., "S1 Ep. 5", "Season 2 Episode 3")
  const seasons = $derived(() => {
    const seasonSet = new Set<string>();
    for (const ep of otherEpisodes) {
      const season = getEpisodeSeason(ep.title);
      if (season) {
        seasonSet.add(season);
      }
    }
    return Array.from(seasonSet).sort((a, b) => parseInt(a) - parseInt(b));
  });

  // Filter episodes by selected season
  const filteredEpisodes = $derived(
    selectedSeason
      ? otherEpisodes.filter(e => getEpisodeSeason(e.title) === selectedSeason)
      : otherEpisodes
  );

  // Selectable episodes = filtered episodes (visible ones) + error episodes (for retry)
  const selectableEpisodes = $derived([...filteredEpisodes, ...errorEpisodes]);
  const selectedCount = $derived(selectedEpisodes.size);
  const allSelected = $derived(selectableEpisodes.length > 0 && selectedEpisodes.size === selectableEpisodes.length);

  onMount(async () => {
    await library.load();
    fetchPodcast();
  });

  async function fetchPodcast() {
    if (!podcastId) return;

    isLoading = true;
    error = null;

    try {
      // Always try subscriptions API first (has processing status)
      const subResponse = await fetch(`/api/subscriptions/${podcastId}`);
      if (subResponse.ok) {
        const data = await subResponse.json();
        podcast = {
          id: data.subscription.podcastId,
          title: data.subscription.title,
          artist: data.subscription.artist,
          artworkUrl: data.subscription.artworkUrl,
          feedUrl: data.subscription.feedUrl,
          description: data.subscription.description,
          genre: data.subscription.genre
        };
        episodes = data.episodes;
        isLoading = false;
        return;
      }

      // Fallback to iTunes API for non-subscribed podcasts
      const response = await fetch(`/api/podcast/${podcastId}`);
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

  async function toggleSubscription() {
    if (!podcast || !podcastId) return;

    if (isSubscribed) {
      await library.unsubscribe(podcastId);
    } else {
      await library.subscribe(podcast);
      // Refresh to get episode processing status
      fetchPodcast();
    }
  }

  function copyFeedUrl() {
    navigator.clipboard.writeText(feedUrl);
  }

  function toggleEpisodeSelection(episodeId: string) {
    const newSet = new Set(selectedEpisodes);
    if (newSet.has(episodeId)) {
      newSet.delete(episodeId);
    } else {
      newSet.add(episodeId);
    }
    selectedEpisodes = newSet;
  }

  function selectAll() {
    selectedEpisodes = new Set(selectableEpisodes.map(e => e.id));
  }

  function deselectAll() {
    selectedEpisodes = new Set();
  }

  function filterBySeason(season: string) {
    selectedSeason = season;
    // Clear selection when changing filter
    selectedEpisodes = new Set();
  }

  async function queueSelected() {
    if (selectedEpisodes.size === 0) return;

    isQueueing = true;
    try {
      // Queue each selected episode
      for (const episodeId of selectedEpisodes) {
        await fetch('/api/queue', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ episodeId })
        });
      }
      // Clear selection and refresh
      selectedEpisodes = new Set();
      await fetchPodcast();
    } catch (e) {
      console.error('Failed to queue episodes:', e);
    } finally {
      isQueueing = false;
    }
  }

  async function retryEpisode(episodeId: string) {
    try {
      await fetch('/api/queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ episodeId, retry: true })
      });
      await fetchPodcast();
    } catch (e) {
      console.error('Failed to retry episode:', e);
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
    <a href="/" class="btn">Back to Library</a>
  </div>
{:else if podcast}
  <div class="podcast-page">
    <a href="/" class="back-link">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
      </svg>
      Library
    </a>

    <header class="podcast-header">
      <img
        src={podcast.artworkUrl}
        alt=""
        class="podcast-header__artwork"
      />
      <div class="podcast-header__info">
        <h1 class="podcast-header__title">{podcast.title}</h1>
        <p class="podcast-header__artist">{podcast.artist}</p>
        {#if podcast.genre}
          <span class="podcast-header__genre">{podcast.genre}</span>
        {/if}

        <div class="podcast-header__actions">
          <button
            class="podcast-header__subscribe"
            class:podcast-header__subscribe--subscribed={isSubscribed}
            onclick={toggleSubscription}
          >
            {isSubscribed ? 'Subscribed' : 'Subscribe'}
          </button>

          {#if isSubscribed}
            <button
              class="podcast-header__feed-btn"
              onclick={() => showFeedUrl = !showFeedUrl}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M6.18 15.64a2.18 2.18 0 0 1 2.18 2.18C8.36 19 7.38 20 6.18 20C5 20 4 19 4 17.82a2.18 2.18 0 0 1 2.18-2.18M4 4.44A15.56 15.56 0 0 1 19.56 20h-2.83A12.73 12.73 0 0 0 4 7.27V4.44m0 5.66a9.9 9.9 0 0 1 9.9 9.9h-2.83A7.07 7.07 0 0 0 4 12.93V10.1z"/>
              </svg>
              RSS Feed
            </button>
          {/if}
        </div>

        {#if showFeedUrl && isSubscribed}
          <div class="feed-url-panel">
            <p class="feed-url-label">Add this URL to your podcast app:</p>
            <div class="feed-url-container">
              <code class="feed-url">{feedUrl}</code>
              <button class="feed-url-copy" onclick={copyFeedUrl}>Copy</button>
            </div>
          </div>
        {/if}
      </div>
    </header>

    <section class="episodes-section">
      <div class="episodes-header">
        <h2>Episodes</h2>
        <span class="episode-count">{episodes.length} episodes</span>
      </div>

      {#if readyEpisodes.length > 0}
        <div class="episode-group">
          <h3 class="episode-group__title episode-group__title--ready">
            <span class="episode-group__icon">✓</span>
            Ad-Free ({readyEpisodes.length})
          </h3>
          <div class="episode-list">
            {#each readyEpisodes as episode (episode.id)}
              <EpisodeRow {episode} />
            {/each}
          </div>
        </div>
      {/if}

      {#if processingEpisodes.length > 0}
        <div class="episode-group">
          <h3 class="episode-group__title episode-group__title--processing">
            <span class="episode-group__spinner"></span>
            Processing ({processingEpisodes.length})
          </h3>
          <div class="episode-list">
            {#each processingEpisodes as episode (episode.id)}
              <EpisodeRow {episode} />
            {/each}
          </div>
        </div>
      {/if}

      {#if queuedEpisodes.length > 0}
        <div class="episode-group">
          <h3 class="episode-group__title episode-group__title--queued">
            <span class="episode-group__icon">⏳</span>
            Queued ({queuedEpisodes.length})
          </h3>
          <div class="episode-list">
            {#each queuedEpisodes as episode (episode.id)}
              <EpisodeRow {episode} />
            {/each}
          </div>
        </div>
      {/if}

      {#if errorEpisodes.length > 0}
        <div class="episode-group">
          <h3 class="episode-group__title episode-group__title--error">
            <span class="episode-group__icon">✗</span>
            Failed ({errorEpisodes.length})
          </h3>
          <div class="episode-list">
            {#each errorEpisodes as episode (episode.id)}
              <div class="episode-row-wrapper">
                {#if isSubscribed}
                  <label class="episode-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedEpisodes.has(episode.id)}
                      onchange={() => toggleEpisodeSelection(episode.id)}
                    />
                    <span class="checkmark"></span>
                  </label>
                {/if}
                <EpisodeRow {episode} onRetry={retryEpisode} />
              </div>
            {/each}
          </div>
        </div>
      {/if}

      {#if otherEpisodes.length > 0}
        <div class="episode-group">
          <div class="episode-group__header">
            <h3 class="episode-group__title">
              Available Episodes ({selectedSeason ? `Season ${selectedSeason}: ${filteredEpisodes.length}` : otherEpisodes.length})
            </h3>
            {#if isSubscribed}
              <div class="selection-controls">
                {#if seasons().length > 0}
                  <select class="season-select" bind:value={selectedSeason} onchange={(e) => filterBySeason(e.currentTarget.value)}>
                    <option value="">All Seasons</option>
                    {#each seasons() as season}
                      <option value={season}>Season {season}</option>
                    {/each}
                  </select>
                {/if}
                <button class="select-btn" onclick={allSelected ? deselectAll : selectAll}>
                  {allSelected ? 'Deselect All' : 'Select All'}
                </button>
                {#if selectedCount > 0}
                  <button class="queue-btn" onclick={queueSelected} disabled={isQueueing}>
                    {isQueueing ? 'Queueing...' : `Queue ${selectedCount} Episode${selectedCount > 1 ? 's' : ''}`}
                  </button>
                {/if}
              </div>
            {/if}
          </div>
          <div class="episode-list">
            {#each filteredEpisodes as episode (episode.id)}
              <div class="episode-row-wrapper">
                {#if isSubscribed}
                  <label class="episode-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedEpisodes.has(episode.id)}
                      onchange={() => toggleEpisodeSelection(episode.id)}
                    />
                    <span class="checkmark"></span>
                  </label>
                {/if}
                <EpisodeRow {episode} />
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </section>
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

  .btn {
    display: inline-block;
    margin-top: var(--space-4);
    padding: var(--space-2) var(--space-4);
    background: var(--bg-secondary);
    color: var(--text-primary);
    text-decoration: none;
    border-radius: var(--radius-md);
  }

  .back-link {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    color: var(--accent);
    text-decoration: none;
    font-size: var(--text-sm);
    margin-bottom: var(--space-6);
  }

  .back-link:hover {
    text-decoration: underline;
  }

  .podcast-header {
    display: flex;
    gap: var(--space-6);
    margin-bottom: var(--space-8);
  }

  @media (max-width: 640px) {
    .podcast-header {
      flex-direction: column;
      align-items: center;
      text-align: center;
    }
  }

  .podcast-header__artwork {
    width: 200px;
    height: 200px;
    border-radius: var(--radius-lg);
    object-fit: cover;
    flex-shrink: 0;
  }

  @media (max-width: 640px) {
    .podcast-header__artwork {
      width: 180px;
      height: 180px;
    }
  }

  .podcast-header__info {
    flex: 1;
    min-width: 0;
  }

  .podcast-header__title {
    font-size: var(--text-2xl);
    font-weight: var(--font-bold);
    color: var(--text-primary);
    margin: 0 0 var(--space-2);
  }

  .podcast-header__artist {
    font-size: var(--text-lg);
    color: var(--text-secondary);
    margin: 0 0 var(--space-3);
  }

  .podcast-header__genre {
    display: inline-block;
    padding: var(--space-1) var(--space-3);
    background: var(--bg-elevated);
    border-radius: var(--radius-md);
    font-size: var(--text-xs);
    color: var(--text-secondary);
  }

  .podcast-header__actions {
    display: flex;
    gap: var(--space-3);
    margin-top: var(--space-4);
  }

  @media (max-width: 640px) {
    .podcast-header__actions {
      justify-content: center;
    }
  }

  .podcast-header__subscribe {
    padding: var(--space-2) var(--space-6);
    background: var(--accent);
    color: white;
    border: none;
    border-radius: var(--radius-full);
    font-size: var(--text-sm);
    font-weight: var(--font-medium);
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .podcast-header__subscribe:hover {
    opacity: 0.9;
  }

  .podcast-header__subscribe--subscribed {
    background: var(--success);
  }

  .podcast-header__feed-btn {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-4);
    background: var(--bg-secondary);
    color: var(--text-primary);
    border: none;
    border-radius: var(--radius-full);
    font-size: var(--text-sm);
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .podcast-header__feed-btn:hover {
    background: var(--bg-elevated);
  }

  .feed-url-panel {
    margin-top: var(--space-4);
    padding: var(--space-4);
    background: var(--bg-secondary);
    border-radius: var(--radius-lg);
  }

  .feed-url-label {
    font-size: var(--text-sm);
    color: var(--text-secondary);
    margin: 0 0 var(--space-2);
  }

  .feed-url-container {
    display: flex;
    gap: var(--space-2);
  }

  .feed-url {
    flex: 1;
    padding: var(--space-2) var(--space-3);
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .feed-url-copy {
    padding: var(--space-2) var(--space-3);
    background: var(--accent);
    color: white;
    border: none;
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    cursor: pointer;
  }

  .episodes-section {
    border-top: 1px solid var(--border);
    padding-top: var(--space-6);
  }

  .episodes-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-4);
  }

  .episodes-header h2 {
    font-size: var(--text-xl);
    font-weight: var(--font-semibold);
    margin: 0;
  }

  .episode-count {
    font-size: var(--text-sm);
    color: var(--text-muted);
  }

  .episode-list {
    display: flex;
    flex-direction: column;
  }

  .episode-group {
    margin-bottom: var(--space-6);
  }

  .episode-group__title {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    font-weight: var(--font-semibold);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    margin: 0 0 var(--space-3);
    padding: var(--space-2) 0;
    border-bottom: 1px solid var(--border);
  }

  .episode-group__title--ready {
    color: var(--success);
  }

  .episode-group__title--processing {
    color: var(--warning);
  }

  .episode-group__title--queued {
    color: var(--text-muted);
  }

  .episode-group__title--error {
    color: var(--error);
  }

  .episode-group__icon {
    font-size: var(--text-base);
  }

  .episode-group__spinner {
    width: 14px;
    height: 14px;
    border: 2px solid transparent;
    border-top-color: var(--warning);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--bg-elevated);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .episode-group__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
    padding: var(--space-2) 0;
    border-bottom: 1px solid var(--border);
  }

  .selection-controls {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .season-select {
    padding: var(--space-1) var(--space-2);
    background: var(--bg-secondary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    font-size: var(--text-xs);
    cursor: pointer;
  }

  .select-btn {
    padding: var(--space-1) var(--space-3);
    background: var(--bg-secondary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    font-size: var(--text-xs);
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .select-btn:hover {
    background: var(--bg-elevated);
  }

  .queue-btn {
    padding: var(--space-1) var(--space-3);
    background: var(--accent);
    color: white;
    border: none;
    border-radius: var(--radius-md);
    font-size: var(--text-xs);
    font-weight: var(--font-medium);
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .queue-btn:hover:not(:disabled) {
    opacity: 0.9;
  }

  .queue-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .episode-row-wrapper {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
  }

  .episode-checkbox {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    margin-top: var(--space-3);
    cursor: pointer;
  }

  .episode-checkbox input {
    position: absolute;
    opacity: 0;
    cursor: pointer;
    height: 0;
    width: 0;
  }

  .checkmark {
    width: 20px;
    height: 20px;
    background: var(--bg-secondary);
    border: 2px solid var(--border);
    border-radius: var(--radius-sm);
    transition: all 0.15s;
  }

  .episode-checkbox:hover .checkmark {
    border-color: var(--accent);
  }

  .episode-checkbox input:checked ~ .checkmark {
    background: var(--accent);
    border-color: var(--accent);
  }

  .episode-checkbox input:checked ~ .checkmark::after {
    content: '';
    position: absolute;
    left: 7px;
    top: 3px;
    width: 5px;
    height: 10px;
    border: solid white;
    border-width: 0 2px 2px 0;
    transform: rotate(45deg);
  }

  .episode-row-wrapper :global(.episode-row) {
    flex: 1;
  }
</style>
