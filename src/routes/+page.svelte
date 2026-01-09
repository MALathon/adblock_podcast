<script lang="ts">
  import type { Podcast } from '$lib/types';

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

    // Debounce search
    if (searchTimeout) clearTimeout(searchTimeout);
    searchTimeout = setTimeout(search, 300);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      if (searchTimeout) clearTimeout(searchTimeout);
      search();
    }
  }
</script>

<div class="page-header">
  <h1 class="page-title">Ad-Free Podcasts</h1>
  <p class="page-subtitle">Search, download, and listen without interruptions</p>
</div>

<div class="search-container">
  <input
    type="search"
    class="search-input"
    placeholder="Search podcasts..."
    value={searchQuery}
    oninput={handleInput}
    onkeydown={handleKeydown}
  />
  {#if isSearching}
    <div class="search-spinner">
      <div class="spinner"></div>
    </div>
  {/if}
</div>

{#if podcasts.length > 0}
  <div class="podcast-grid">
    {#each podcasts as podcast (podcast.id)}
      <a href="/podcast/{podcast.id}" class="podcast-card">
        <img
          src={podcast.artworkUrl || '/placeholder.png'}
          alt=""
          class="podcast-card__image"
          loading="lazy"
        />
        <div class="podcast-card__info">
          <div class="podcast-card__title">{podcast.title}</div>
          <div class="podcast-card__artist">{podcast.artist}</div>
        </div>
      </a>
    {/each}
  </div>
{:else if searchQuery && !isSearching}
  <div class="empty-state">
    <div class="empty-state__icon">🎙️</div>
    <div class="empty-state__title">No podcasts found</div>
    <p>Try a different search term</p>
  </div>
{:else if !searchQuery}
  <div class="empty-state">
    <div class="empty-state__icon">🔍</div>
    <div class="empty-state__title">Search for podcasts</div>
    <p>Find your favorite shows and listen ad-free</p>
  </div>
{/if}

<style>
  .search-container {
    position: relative;
    max-width: 500px;
  }

  .search-spinner {
    position: absolute;
    right: var(--space-4);
    top: 50%;
    transform: translateY(-50%);
  }
</style>
