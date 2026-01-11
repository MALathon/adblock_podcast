<script lang="ts">
  import type { Subscription } from '$lib/types';

  interface Props {
    subscription: Subscription;
  }

  let { subscription }: Props = $props();
</script>

<a href="/podcast/{subscription.podcastId}" class="podcast-card">
  <img
    src={subscription.artworkUrl}
    alt=""
    class="podcast-card__artwork"
    loading="lazy"
  />
  <div class="podcast-card__info">
    <h3 class="podcast-card__title">{subscription.title}</h3>
    <p class="podcast-card__artist">{subscription.artist}</p>
  </div>
</a>

<style>
  .podcast-card {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    text-decoration: none;
    color: inherit;
    transition: transform 0.15s;
  }

  .podcast-card:hover {
    transform: scale(1.02);
  }

  .podcast-card__artwork {
    width: 100%;
    aspect-ratio: 1;
    border-radius: var(--radius-lg);
    object-fit: cover;
    background: var(--bg-elevated);
  }

  .podcast-card__info {
    min-width: 0;
  }

  .podcast-card__title {
    font-size: var(--text-sm);
    font-weight: var(--font-medium);
    color: var(--text-primary);
    margin: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .podcast-card__artist {
    font-size: var(--text-xs);
    color: var(--text-secondary);
    margin: var(--space-1) 0 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
