<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { library } from '$lib/stores/library.svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import Spinner from '$lib/components/common/Spinner.svelte';
  import PodcastHeader from '$lib/components/podcast/PodcastHeader.svelte';
  import EpisodeGroup from '$lib/components/podcast/EpisodeGroup.svelte';
  import EpisodeRow from '$lib/components/podcast/EpisodeRow.svelte';
  import SelectionControls from '$lib/components/podcast/SelectionControls.svelte';
  import type { Podcast, Episode } from '$lib/types';

  let podcast = $state<Podcast | null>(null);
  let episodes = $state<Episode[]>([]);
  let isLoading = $state(true);
  let error = $state<string | null>(null);
  let selectedEpisodes = $state<Set<string>>(new Set());
  let isQueueing = $state(false);
  let selectedSeason = $state<string>('');

  const podcastId = $derived($page.params.id ?? '');
  const isSubscribed = $derived(podcastId ? library.isSubscribed(podcastId) : false);
  const feedUrl = $derived(
    typeof window !== 'undefined' && podcastId
      ? `${window.location.protocol}//${window.location.host}/feed/${podcastId}.xml`
      : ''
  );

  // Group episodes by processing status
  const readyEpisodes = $derived(episodes.filter((e) => e.processingStatus === 'ready'));
  const processingEpisodes = $derived(episodes.filter((e) => e.processingStatus === 'processing'));
  const queuedEpisodes = $derived(episodes.filter((e) => e.processingStatus === 'queued'));
  const errorEpisodes = $derived(episodes.filter((e) => e.processingStatus === 'error'));
  const otherEpisodes = $derived(
    episodes.filter((e) => !e.processingStatus || e.processingStatus === 'none')
  );

  // Helper to get season from episode title
  function getEpisodeSeason(title: string): string | null {
    const match = title.match(/S(\d+)|Season\s*(\d+)/i);
    return match ? match[1] || match[2] : null;
  }

  // Detect seasons from episode titles
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
      ? otherEpisodes.filter((e) => getEpisodeSeason(e.title) === selectedSeason)
      : otherEpisodes
  );

  // Selectable episodes = filtered episodes + error episodes
  const selectableEpisodes = $derived([...filteredEpisodes, ...errorEpisodes]);
  const selectedCount = $derived(selectedEpisodes.size);
  const allSelected = $derived(
    selectableEpisodes.length > 0 && selectedEpisodes.size === selectableEpisodes.length
  );

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
      fetchPodcast();
    }
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
    selectedEpisodes = new Set(selectableEpisodes.map((e) => e.id));
  }

  function deselectAll() {
    selectedEpisodes = new Set();
  }

  function filterBySeason(season: string) {
    selectedSeason = season;
    selectedEpisodes = new Set();
  }

  async function queueSelected() {
    if (selectedEpisodes.size === 0) return;

    isQueueing = true;
    try {
      // Batch all queue requests in parallel for better performance
      const queuePromises = Array.from(selectedEpisodes).map((episodeId) =>
        fetch('/api/queue', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ episodeId })
        })
      );
      await Promise.all(queuePromises);
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
    <Spinner size="lg" />
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
      <Icon name="arrow-left" size={20} />
      Library
    </a>

    <PodcastHeader {podcast} {isSubscribed} {feedUrl} onSubscriptionToggle={toggleSubscription} />

    <section class="episodes-section">
      <div class="episodes-header">
        <h2>Episodes</h2>
        <span class="episode-count">{episodes.length} episodes</span>
      </div>

      {#if readyEpisodes.length > 0}
        <EpisodeGroup title="Ad-Free" count={readyEpisodes.length} status="ready">
          {#each readyEpisodes as episode (episode.id)}
            <EpisodeRow {episode} />
          {/each}
        </EpisodeGroup>
      {/if}

      {#if processingEpisodes.length > 0}
        <EpisodeGroup title="Processing" count={processingEpisodes.length} status="processing">
          {#each processingEpisodes as episode (episode.id)}
            <EpisodeRow {episode} />
          {/each}
        </EpisodeGroup>
      {/if}

      {#if queuedEpisodes.length > 0}
        <EpisodeGroup title="Queued" count={queuedEpisodes.length} status="queued">
          {#each queuedEpisodes as episode (episode.id)}
            <EpisodeRow {episode} />
          {/each}
        </EpisodeGroup>
      {/if}

      {#if errorEpisodes.length > 0}
        <EpisodeGroup title="Failed" count={errorEpisodes.length} status="error">
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
        </EpisodeGroup>
      {/if}

      {#if otherEpisodes.length > 0}
        <EpisodeGroup
          title={selectedSeason
            ? `Season ${selectedSeason}`
            : 'Available Episodes'}
          count={selectedSeason ? filteredEpisodes.length : otherEpisodes.length}
        >
          {#snippet headerActions()}
            {#if isSubscribed}
              <SelectionControls
                seasons={seasons()}
                {selectedSeason}
                {selectedCount}
                {allSelected}
                {isQueueing}
                onSeasonChange={filterBySeason}
                onSelectAll={selectAll}
                onDeselectAll={deselectAll}
                onQueueSelected={queueSelected}
              />
            {/if}
          {/snippet}
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
        </EpisodeGroup>
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
