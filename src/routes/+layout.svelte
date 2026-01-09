<script lang="ts">
  import '../app.css';
  import { player } from '$lib/stores/player.svelte';

  let { children } = $props();

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

  function handleVolumeChange(e: Event) {
    const input = e.target as HTMLInputElement;
    player.setVolume(parseFloat(input.value));
  }
</script>

<svelte:head>
  <title>Ad-Free Podcasts</title>
</svelte:head>

<div class="app-container">
  <main class="main-content">
    {@render children()}
  </main>

  {#if player.currentEpisode}
    <div class="audio-player">
      <div class="audio-player__info">
        <img
          src={player.currentEpisode.artworkUrl || '/placeholder.png'}
          alt=""
          class="audio-player__artwork"
        />
        <div class="audio-player__text">
          <div class="audio-player__title">{player.currentEpisode.title}</div>
          <div class="audio-player__podcast">{player.currentEpisode.podcastTitle}</div>
        </div>
      </div>

      <div class="audio-player__controls">
        <button
          class="audio-player__btn"
          onclick={() => player.seek(player.currentTime - 15)}
          aria-label="Rewind 15 seconds"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8zm-1.31 8.9l.25-2.17h2.39v.71h-1.7l-.11.92c.03-.02.07-.03.11-.05s.09-.04.15-.05.12-.03.18-.04.13-.02.2-.02c.21 0 .39.03.55.1s.3.16.41.28.2.27.25.45.09.38.09.6c0 .19-.03.37-.09.54s-.15.32-.27.45-.27.24-.45.31-.39.12-.64.12c-.18 0-.36-.03-.53-.08s-.32-.14-.46-.24-.24-.24-.32-.39-.13-.33-.13-.53h.84c.02.18.08.32.19.41s.25.15.42.15c.11 0 .2-.02.27-.06s.14-.1.18-.17.08-.15.11-.25.03-.2.03-.31-.01-.21-.04-.31-.07-.17-.13-.24-.13-.12-.21-.15-.19-.05-.3-.05c-.08 0-.15.01-.2.02s-.11.03-.15.05-.08.05-.12.07-.07.06-.1.09l-.67-.16z"/>
          </svg>
        </button>

        <button
          class="audio-player__btn audio-player__btn--play"
          onclick={() => player.togglePlay()}
          aria-label={player.isPlaying ? 'Pause' : 'Play'}
        >
          {#if player.isPlaying}
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
          class="audio-player__btn"
          onclick={() => player.seek(player.currentTime + 30)}
          aria-label="Forward 30 seconds"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 5V1l5 5-5 5V7c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6h2c0 4.42-3.58 8-8 8s-8-3.58-8-8 3.58-8 8-8zm2.56 8.99c.16.13.37.2.64.2.16 0 .3-.02.43-.07s.24-.12.33-.21.17-.2.22-.34.08-.29.08-.46c0-.14-.01-.27-.05-.39s-.08-.23-.15-.32-.15-.16-.25-.21-.22-.08-.35-.08c-.16 0-.29.04-.4.11s-.22.17-.31.29l-.64-.53.98-2.12h2.05v.71h-1.48l-.38.89c.06-.01.12-.03.18-.03s.12-.01.18-.01c.2 0 .38.03.54.1s.3.16.42.28.2.27.26.45.09.38.09.61c0 .22-.04.42-.11.6s-.18.34-.31.47-.3.23-.49.3-.4.11-.63.11c-.21 0-.4-.03-.57-.09s-.32-.15-.44-.26-.22-.25-.29-.41-.11-.34-.11-.54h.83c.01.18.07.32.18.41z"/>
          </svg>
        </button>
      </div>

      <div class="audio-player__progress">
        <span class="audio-player__time">{formatTime(player.currentTime)}</span>
        <input
          type="range"
          class="audio-player__slider"
          min="0"
          max={player.duration || 100}
          value={player.currentTime}
          oninput={handleSeek}
          aria-label="Seek"
        />
        <span class="audio-player__time">{formatTime(player.duration)}</span>
      </div>

      <div class="audio-player__volume">
        <button
          class="audio-player__btn"
          onclick={() => player.setVolume(player.volume === 0 ? 1 : 0)}
          aria-label={player.volume === 0 ? 'Unmute' : 'Mute'}
        >
          {#if player.volume === 0}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
            </svg>
          {:else}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
            </svg>
          {/if}
        </button>
        <input
          type="range"
          class="audio-player__slider"
          min="0"
          max="1"
          step="0.01"
          value={player.volume}
          oninput={handleVolumeChange}
          aria-label="Volume"
        />
      </div>
    </div>
  {/if}
</div>
