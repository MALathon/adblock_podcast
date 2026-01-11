<script lang="ts">
  import type { Podcast } from '$lib/types';
  import { library } from '$lib/stores/library.svelte';

  let searchQuery = $state('');
  let podcasts = $state<Podcast[]>([]);
  let isSearching = $state(false);
  let searchTimeout: ReturnType<typeof setTimeout> | null = null;

  async function search() {
    if (!searchQuery.trim()) {
      podcasts = [];
      return;
    }

    isSearching = true;
    try {
      const response = await fetch(`/api/search?q=${encodeURIComponent(searchQuery)}`);
      if (response.ok) {
        podcasts = await response.json();
      }
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      isSearching = false;
    }
  }

  function handleInput(e: Event) {
    const input = e.target as HTMLInputElement;
    searchQuery = input.value;

    if (searchTimeout) clearTimeout(searchTimeout);
    searchTimeout = setTimeout(search, 300);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      if (searchTimeout) clearTimeout(searchTimeout);
      search();
    }
  }

  async function subscribeToPodcast(podcast: Podcast) {
    await library.subscribe(podcast);
  }
</script>

<div class="search-header">
  <a href="/" class="back-link" aria-label="Back to library">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
      <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
    </svg>
  </a>
  <h1 class="search-title">Search</h1>
</div>

<div class="search-container">
  <svg class="search-icon" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
    <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
  </svg>
  <input
    type="search"
    class="search-input"
    placeholder="Podcasts, hosts, topics..."
    value={searchQuery}
    oninput={handleInput}
    onkeydown={handleKeydown}
    autofocus
  />
  {#if isSearching}
    <div class="search-spinner">
      <div class="spinner"></div>
    </div>
  {/if}
</div>

{#if podcasts.length > 0}
  <div class="results">
    {#each podcasts as podcast (podcast.id)}
      <div class="result-card">
        <a href="/podcast/{podcast.id}" class="result-card__link">
          <img
            src={podcast.artworkUrl}
            alt=""
            class="result-card__artwork"
            loading="lazy"
          />
          <div class="result-card__info">
            <div class="result-card__title">{podcast.title}</div>
            <div class="result-card__artist">{podcast.artist}</div>
            {#if podcast.genre}
              <div class="result-card__genre">{podcast.genre}</div>
            {/if}
          </div>
        </a>
        <button
          class="result-card__subscribe"
          onclick={() => subscribeToPodcast(podcast)}
          disabled={library.isSubscribed(podcast.id)}
        >
          {#if library.isSubscribed(podcast.id)}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
            </svg>
          {:else}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
            </svg>
          {/if}
        </button>
      </div>
    {/each}
  </div>
{:else if searchQuery && !isSearching}
  <div class="empty-state">
    <p>No podcasts found for "{searchQuery}"</p>
  </div>
{:else if !searchQuery}
  <div class="empty-state">
    <p class="empty-state__hint">Search for podcasts to subscribe</p>
  </div>
{/if}

<style>
  .search-header {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }

  .back-link {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    border-radius: var(--radius-full);
    color: var(--text-primary);
    text-decoration: none;
    transition: background-color 0.15s;
  }

  .back-link:hover {
    background: var(--bg-secondary);
  }

  .search-title {
    font-size: var(--text-2xl);
    font-weight: var(--font-bold);
    color: var(--text-primary);
    margin: 0;
  }

  .search-container {
    position: relative;
    margin-bottom: var(--space-6);
  }

  .search-icon {
    position: absolute;
    left: var(--space-4);
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted);
    pointer-events: none;
  }

  .search-input {
    width: 100%;
    height: 48px;
    padding: 0 var(--space-4) 0 var(--space-11);
    background: var(--bg-secondary);
    border: none;
    border-radius: var(--radius-lg);
    font-size: var(--text-base);
    color: var(--text-primary);
    outline: none;
  }

  .search-input::placeholder {
    color: var(--text-muted);
  }

  .search-input:focus {
    box-shadow: 0 0 0 2px var(--accent);
  }

  .search-spinner {
    position: absolute;
    right: var(--space-4);
    top: 50%;
    transform: translateY(-50%);
  }

  .results {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .result-card {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3);
    background: var(--bg-secondary);
    border-radius: var(--radius-lg);
  }

  .result-card__link {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex: 1;
    min-width: 0;
    text-decoration: none;
    color: inherit;
  }

  .result-card__artwork {
    width: 64px;
    height: 64px;
    border-radius: var(--radius-md);
    object-fit: cover;
    flex-shrink: 0;
  }

  .result-card__info {
    flex: 1;
    min-width: 0;
  }

  .result-card__title {
    font-size: var(--text-base);
    font-weight: var(--font-medium);
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .result-card__artist {
    font-size: var(--text-sm);
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .result-card__genre {
    font-size: var(--text-xs);
    color: var(--text-muted);
    margin-top: var(--space-1);
  }

  .result-card__subscribe {
    width: 44px;
    height: 44px;
    border-radius: var(--radius-full);
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

  .result-card__subscribe:hover:not(:disabled) {
    opacity: 0.9;
  }

  .result-card__subscribe:disabled {
    background: var(--success);
    cursor: default;
  }

  .empty-state {
    text-align: center;
    padding: var(--space-12);
    color: var(--text-secondary);
  }

  .empty-state__hint {
    color: var(--text-muted);
  }

  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid var(--bg-elevated);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
