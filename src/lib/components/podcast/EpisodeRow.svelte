<script lang="ts">
  import type { Episode } from '$lib/types';
  import { player } from '$lib/stores/player.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import { formatDuration, formatDate } from '$lib/utils/format';

  interface Props {
    episode: Episode;
    onRetry?: (episodeId: string) => void;
  }

  let { episode, onRetry }: Props = $props();
  let isRetrying = $state(false);

  async function retryProcessing() {
    if (!onRetry) return;
    isRetrying = true;
    try {
      await onRetry(episode.id);
    } finally {
      isRetrying = false;
    }
  }

  function playEpisode() {
    // Use processed audio if ready, otherwise original
    const audioUrl = episode.processingStatus === 'ready' && episode.processedPath
      ? `/api/audio/${encodeURIComponent(episode.id)}`
      : episode.audioUrl;

    player.play({
      id: episode.id,
      title: episode.title,
      podcastTitle: episode.podcastTitle,
      audioUrl,
      artworkUrl: episode.artworkUrl,
      podcastId: episode.podcastId
    });
  }

  const isCurrentEpisode = $derived(player.currentEpisode?.id === episode.id);
</script>

<div class="episode-row" class:episode-row--playing={isCurrentEpisode}>
  <button class="episode-row__play" onclick={playEpisode} aria-label="Play episode">
    {#if isCurrentEpisode && player.isPlaying}
      <Icon name="pause" size={20} />
    {:else}
      <Icon name="play" size={20} />
    {/if}
  </button>

  <div class="episode-row__info">
    <div class="episode-row__title">{episode.title}</div>
    <div class="episode-row__meta">
      {formatDate(episode.pubDate)}
      {#if episode.duration}
        <span class="episode-row__dot"></span>
        {formatDuration(episode.duration)}
      {/if}
      {#if episode.processingStatus && episode.processingStatus !== 'none'}
        <span class="episode-row__dot"></span>
        <StatusBadge status={episode.processingStatus} />
      {/if}
    </div>
    {#if episode.processingStatus === 'error'}
      <div class="episode-row__error">
        {#if episode.processingError}
          <span class="episode-row__error-msg">{episode.processingError}</span>
        {/if}
        {#if onRetry}
          <button class="episode-row__retry" onclick={retryProcessing} disabled={isRetrying}>
            {isRetrying ? 'Retrying...' : 'Retry'}
          </button>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .episode-row {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-4) 0;
    border-bottom: 1px solid var(--border);
  }

  .episode-row--playing {
    background: var(--bg-elevated);
    margin: 0 calc(-1 * var(--space-4));
    padding: var(--space-4);
    border-radius: var(--radius-md);
    border-bottom: none;
  }

  .episode-row__play {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: var(--accent);
    color: white;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: opacity 0.15s;
  }

  .episode-row__play:hover {
    opacity: 0.9;
  }

  .episode-row__info {
    flex: 1;
    min-width: 0;
  }

  .episode-row__title {
    font-size: var(--text-base);
    font-weight: var(--font-medium);
    color: var(--text-primary);
    margin-bottom: var(--space-1);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .episode-row__meta {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }

  .episode-row__dot {
    width: 3px;
    height: 3px;
    border-radius: 50%;
    background: var(--text-muted);
  }

  .episode-row__error {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-top: var(--space-1);
  }

  .episode-row__error-msg {
    font-size: var(--text-xs);
    color: var(--error);
    flex: 1;
  }

  .episode-row__retry {
    padding: var(--space-1) var(--space-2);
    background: var(--error);
    color: white;
    border: none;
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .episode-row__retry:hover:not(:disabled) {
    opacity: 0.9;
  }

  .episode-row__retry:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
