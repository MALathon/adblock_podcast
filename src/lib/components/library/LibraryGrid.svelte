<script lang="ts">
  import type { Subscription } from '$lib/types';
  import PodcastCard from './PodcastCard.svelte';

  interface Props {
    subscriptions: Subscription[];
  }

  let { subscriptions }: Props = $props();
</script>

{#if subscriptions.length > 0}
  <div class="library-grid">
    {#each subscriptions as subscription (subscription.podcastId)}
      <PodcastCard {subscription} />
    {/each}
  </div>
{:else}
  <div class="library-empty">
    <div class="library-empty__icon">
      <svg width="64" height="64" viewBox="0 0 24 24" fill="currentColor" opacity="0.3">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
      </svg>
    </div>
    <h3 class="library-empty__title">No podcasts yet</h3>
    <p class="library-empty__text">Search to find podcasts and subscribe to them.</p>
    <a href="/search" class="library-empty__btn">Find Podcasts</a>
  </div>
{/if}

<style>
  .library-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: var(--space-6);
  }

  @media (min-width: 640px) {
    .library-grid {
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    }
  }

  .library-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: var(--space-12) var(--space-6);
    min-height: 400px;
  }

  .library-empty__icon {
    margin-bottom: var(--space-4);
    color: var(--text-muted);
  }

  .library-empty__title {
    font-size: var(--text-xl);
    font-weight: var(--font-semibold);
    color: var(--text-primary);
    margin: 0 0 var(--space-2);
  }

  .library-empty__text {
    font-size: var(--text-base);
    color: var(--text-secondary);
    margin: 0 0 var(--space-6);
    max-width: 300px;
  }

  .library-empty__btn {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    background: var(--accent);
    color: white;
    padding: var(--space-3) var(--space-6);
    border-radius: var(--radius-full);
    font-size: var(--text-sm);
    font-weight: var(--font-medium);
    text-decoration: none;
    transition: opacity 0.15s;
  }

  .library-empty__btn:hover {
    opacity: 0.9;
  }
</style>
