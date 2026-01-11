<script lang="ts">
  import { player } from '$lib/stores/player.svelte';

  function formatTime(seconds: number): string {
    if (isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  function handleSeek(e: Event) {
    const input = e.target as HTMLInputElement;
    player.seek(parseFloat(input.value));
  }

  function handleArtworkClick() {
    player.expand();
  }
</script>

{#if player.currentEpisode && !player.isExpanded}
  <div class="mini-player">
    <button
      class="mini-player__artwork-btn"
      onclick={handleArtworkClick}
      aria-label="Expand player"
    >
      <img
        src={player.currentEpisode.artworkUrl || '/placeholder.png'}
        alt=""
        class="mini-player__artwork"
      />
    </button>

    <div class="mini-player__info">
      <div class="mini-player__title">{player.currentEpisode.title}</div>
      <div class="mini-player__podcast">{player.currentEpisode.podcastTitle}</div>
    </div>

    <div class="mini-player__controls">
      <button
        class="mini-player__btn"
        onclick={() => player.skipBackward(15)}
        aria-label="Rewind 15 seconds"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/>
        </svg>
      </button>

      <button
        class="mini-player__btn mini-player__btn--play"
        onclick={() => player.togglePlay()}
        aria-label={player.isPlaying ? 'Pause' : 'Play'}
      >
        {#if player.isBuffering}
          <div class="spinner"></div>
        {:else if player.isPlaying}
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
          </svg>
        {:else}
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M8 5v14l11-7z"/>
          </svg>
        {/if}
      </button>

      <button
        class="mini-player__btn"
        onclick={() => player.skipForward(30)}
        aria-label="Forward 30 seconds"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 5V1l5 5-5 5V7c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6h2c0 4.42-3.58 8-8 8s-8-3.58-8-8 3.58-8 8-8z"/>
        </svg>
      </button>
    </div>

    <div class="mini-player__progress">
      <span class="mini-player__time">{formatTime(player.currentTime)}</span>
      <input
        type="range"
        class="mini-player__slider"
        min="0"
        max={player.duration || 100}
        value={player.currentTime}
        oninput={handleSeek}
        aria-label="Seek"
      />
      <span class="mini-player__time">{formatTime(player.duration)}</span>
    </div>
  </div>
{/if}

<style>
  .mini-player {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 80px;
    background: var(--bg-secondary);
    border-top: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: var(--space-4);
    padding: 0 var(--space-4);
    z-index: 100;
  }

  .mini-player__artwork-btn {
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    flex-shrink: 0;
  }

  .mini-player__artwork {
    width: 56px;
    height: 56px;
    border-radius: var(--radius-md);
    object-fit: cover;
  }

  .mini-player__info {
    flex: 1;
    min-width: 0;
    overflow: hidden;
  }

  .mini-player__title {
    font-size: var(--text-sm);
    font-weight: var(--font-medium);
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .mini-player__podcast {
    font-size: var(--text-xs);
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .mini-player__controls {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .mini-player__btn {
    background: none;
    border: none;
    color: var(--text-primary);
    cursor: pointer;
    padding: var(--space-2);
    border-radius: var(--radius-full);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background-color 0.15s;
  }

  .mini-player__btn:hover {
    background: var(--bg-elevated);
  }

  .mini-player__btn--play {
    background: var(--accent);
    color: white;
    width: 44px;
    height: 44px;
  }

  .mini-player__btn--play:hover {
    background: var(--accent);
    opacity: 0.9;
  }

  .mini-player__progress {
    display: none;
    align-items: center;
    gap: var(--space-2);
    flex: 1;
    max-width: 300px;
  }

  @media (min-width: 768px) {
    .mini-player__progress {
      display: flex;
    }
  }

  .mini-player__time {
    font-size: var(--text-xs);
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
    min-width: 40px;
  }

  .mini-player__slider {
    flex: 1;
    height: 4px;
    -webkit-appearance: none;
    appearance: none;
    background: var(--bg-elevated);
    border-radius: 2px;
    cursor: pointer;
  }

  .mini-player__slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 12px;
    height: 12px;
    background: var(--accent);
    border-radius: 50%;
    cursor: pointer;
  }

  .spinner {
    width: 24px;
    height: 24px;
    border: 2px solid transparent;
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
