<script lang="ts">
  import { onMount } from 'svelte';
  import { library } from '$lib/stores/library.svelte';
  import LibraryGrid from '$lib/components/library/LibraryGrid.svelte';

  onMount(() => {
    library.load();
  });
</script>

<div class="library-header">
  <h1 class="library-title">Library</h1>
  <a href="/search" class="library-search-btn" aria-label="Search">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
      <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
    </svg>
  </a>
</div>

{#if library.isLoading}
  <div class="loading">
    <div class="spinner"></div>
  </div>
{:else if library.error}
  <div class="error">
    <p>{library.error}</p>
    <button onclick={() => library.load()}>Try again</button>
  </div>
{:else}
  <LibraryGrid subscriptions={library.subscriptions} />
{/if}

<style>
  .library-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-6);
  }

  .library-title {
    font-size: var(--text-2xl);
    font-weight: var(--font-bold);
    color: var(--text-primary);
    margin: 0;
  }

  .library-search-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    border-radius: var(--radius-full);
    background: var(--bg-secondary);
    color: var(--text-primary);
    text-decoration: none;
    transition: background-color 0.15s;
  }

  .library-search-btn:hover {
    background: var(--bg-elevated);
  }

  .loading {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-12);
  }

  .error {
    text-align: center;
    padding: var(--space-8);
    color: var(--error);
  }

  .error button {
    margin-top: var(--space-4);
    background: var(--bg-secondary);
    border: none;
    color: var(--text-primary);
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-md);
    cursor: pointer;
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--bg-elevated);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
