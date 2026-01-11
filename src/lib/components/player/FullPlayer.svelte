<script lang="ts">
  import { player } from '$lib/stores/player.svelte';

  function formatTime(seconds: number): string {
    if (isNaN(seconds)) return '0:00';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hrs > 0) {
      return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  function handleSeek(e: Event) {
    const input = e.target as HTMLInputElement;
    player.seek(parseFloat(input.value));
  }

  function handleCollapse() {
    player.collapse();
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      player.collapse();
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      player.collapse();
    }
  }
</script>

{#if player.currentEpisode && player.isExpanded}
  <div
    class="full-player"
    onclick={handleBackdropClick}
    onkeydown={handleKeydown}
    role="dialog"
    aria-modal="true"
    aria-label="Now playing"
    tabindex="-1"
  >
    <div class="full-player__content">
      <button
        class="full-player__collapse"
        onclick={handleCollapse}
        aria-label="Collapse player"
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
          <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/>
        </svg>
      </button>

      <div class="full-player__artwork-container">
        <img
          src={player.currentEpisode.artworkUrl || '/placeholder.png'}
          alt=""
          class="full-player__artwork"
        />
      </div>

      <div class="full-player__info">
        <h2 class="full-player__title">{player.currentEpisode.title}</h2>
        <p class="full-player__podcast">{player.currentEpisode.podcastTitle}</p>
      </div>

      <div class="full-player__progress">
        <input
          type="range"
          class="full-player__slider"
          min="0"
          max={player.duration || 100}
          value={player.currentTime}
          oninput={handleSeek}
          aria-label="Seek"
        />
        <div class="full-player__times">
          <span>{formatTime(player.currentTime)}</span>
          <span>-{formatTime(player.duration - player.currentTime)}</span>
        </div>
      </div>

      <div class="full-player__controls">
        <button
          class="full-player__skip-btn"
          onclick={() => player.skipBackward(15)}
          aria-label="Rewind 15 seconds"
        >
          <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/>
          </svg>
          <span class="full-player__skip-label">15</span>
        </button>

        <button
          class="full-player__play-btn"
          onclick={() => player.togglePlay()}
          aria-label={player.isPlaying ? 'Pause' : 'Play'}
        >
          {#if player.isBuffering}
            <div class="spinner"></div>
          {:else if player.isPlaying}
            <svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
            </svg>
          {:else}
            <svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
            </svg>
          {/if}
        </button>

        <button
          class="full-player__skip-btn"
          onclick={() => player.skipForward(30)}
          aria-label="Forward 30 seconds"
        >
          <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 5V1l5 5-5 5V7c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6h2c0 4.42-3.58 8-8 8s-8-3.58-8-8 3.58-8 8-8z"/>
          </svg>
          <span class="full-player__skip-label">30</span>
        </button>
      </div>

      <div class="full-player__actions">
        <button
          class="full-player__action-btn"
          onclick={() => player.cyclePlaybackRate()}
          aria-label="Playback speed"
        >
          {player.playbackRate}x
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .full-player {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.95);
    backdrop-filter: blur(20px);
    z-index: 200;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: fadeIn 0.2s ease-out;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .full-player__content {
    width: 100%;
    max-width: 400px;
    padding: var(--space-6);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-6);
  }

  .full-player__collapse {
    align-self: flex-start;
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    padding: var(--space-2);
    margin: calc(-1 * var(--space-2));
    border-radius: var(--radius-full);
    transition: color 0.15s;
  }

  .full-player__collapse:hover {
    color: var(--text-primary);
  }

  .full-player__artwork-container {
    width: 100%;
    max-width: 300px;
    aspect-ratio: 1;
  }

  .full-player__artwork {
    width: 100%;
    height: 100%;
    border-radius: var(--radius-lg);
    object-fit: cover;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  }

  .full-player__info {
    text-align: center;
    width: 100%;
  }

  .full-player__title {
    font-size: var(--text-xl);
    font-weight: var(--font-semibold);
    color: var(--text-primary);
    margin: 0 0 var(--space-1);
    line-height: 1.3;
  }

  .full-player__podcast {
    font-size: var(--text-base);
    color: var(--text-secondary);
    margin: 0;
  }

  .full-player__progress {
    width: 100%;
  }

  .full-player__slider {
    width: 100%;
    height: 6px;
    -webkit-appearance: none;
    appearance: none;
    background: var(--bg-elevated);
    border-radius: 3px;
    cursor: pointer;
  }

  .full-player__slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 16px;
    height: 16px;
    background: var(--text-primary);
    border-radius: 50%;
    cursor: pointer;
  }

  .full-player__times {
    display: flex;
    justify-content: space-between;
    font-size: var(--text-sm);
    color: var(--text-muted);
    margin-top: var(--space-2);
    font-variant-numeric: tabular-nums;
  }

  .full-player__controls {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-8);
  }

  .full-player__skip-btn {
    position: relative;
    background: none;
    border: none;
    color: var(--text-primary);
    cursor: pointer;
    padding: var(--space-2);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .full-player__skip-label {
    position: absolute;
    font-size: 10px;
    font-weight: var(--font-bold);
    color: var(--text-primary);
  }

  .full-player__play-btn {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    background: var(--text-primary);
    color: var(--bg-primary);
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.15s;
  }

  .full-player__play-btn:hover {
    transform: scale(1.05);
  }

  .full-player__play-btn:active {
    transform: scale(0.95);
  }

  .full-player__actions {
    display: flex;
    gap: var(--space-4);
  }

  .full-player__action-btn {
    background: var(--bg-elevated);
    border: none;
    color: var(--text-primary);
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    font-weight: var(--font-medium);
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .full-player__action-btn:hover {
    background: var(--bg-tertiary);
  }

  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid transparent;
    border-top-color: var(--bg-primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
