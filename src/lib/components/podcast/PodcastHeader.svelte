<script lang="ts">
  import type { Podcast } from '$lib/types';
  import Icon from '$lib/components/common/Icon.svelte';

  interface Props {
    podcast: Podcast;
    isSubscribed: boolean;
    feedUrl: string;
    onSubscriptionToggle: () => void;
  }

  let { podcast, isSubscribed, feedUrl, onSubscriptionToggle }: Props = $props();
  let showFeedUrl = $state(false);

  function copyFeedUrl() {
    navigator.clipboard.writeText(feedUrl);
  }
</script>

<header class="podcast-header">
  <img src={podcast.artworkUrl} alt="" class="podcast-header__artwork" />

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
        onclick={onSubscriptionToggle}
      >
        {isSubscribed ? 'Subscribed' : 'Subscribe'}
      </button>

      {#if isSubscribed}
        <button class="podcast-header__feed-btn" onclick={() => (showFeedUrl = !showFeedUrl)}>
          <Icon name="rss" size={20} />
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

<style>
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
</style>
