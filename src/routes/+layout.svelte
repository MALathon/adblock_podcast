<script lang="ts">
  import '../app.css';
  import MiniPlayer from '$lib/components/player/MiniPlayer.svelte';
  import FullPlayer from '$lib/components/player/FullPlayer.svelte';
  import { player } from '$lib/stores/player.svelte';

  let { children } = $props();

  // Add padding when player is visible
  const hasPlayer = $derived(player.currentEpisode !== null);
</script>

<svelte:head>
  <title>Ad-Free Podcasts</title>
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
</svelte:head>

<div class="app" class:app--with-player={hasPlayer}>
  <main class="main">
    {@render children()}
  </main>

  <MiniPlayer />
  <FullPlayer />
</div>

<style>
  .app {
    min-height: 100vh;
    background: var(--bg-primary);
  }

  .app--with-player {
    padding-bottom: 80px;
  }

  .main {
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--space-6);
  }

  @media (min-width: 768px) {
    .main {
      padding: var(--space-8);
    }
  }
</style>
