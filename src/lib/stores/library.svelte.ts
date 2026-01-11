/**
 * Library store - manages subscriptions and their state
 */
import type { Subscription, Podcast } from '$lib/types';

interface LibraryState {
  subscriptions: Subscription[];
  isLoading: boolean;
  error: string | null;
}

function createLibrary() {
  let state = $state<LibraryState>({
    subscriptions: [],
    isLoading: false,
    error: null
  });

  return {
    get subscriptions() { return state.subscriptions; },
    get isLoading() { return state.isLoading; },
    get error() { return state.error; },

    async load() {
      state.isLoading = true;
      state.error = null;

      try {
        const response = await fetch('/api/subscriptions');
        if (!response.ok) throw new Error('Failed to load subscriptions');
        state.subscriptions = await response.json();
      } catch (e) {
        state.error = e instanceof Error ? e.message : 'Unknown error';
      } finally {
        state.isLoading = false;
      }
    },

    async subscribe(podcast: Podcast): Promise<boolean> {
      try {
        const response = await fetch('/api/subscriptions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(podcast)
        });

        if (!response.ok) {
          if (response.status === 409) {
            // Already subscribed
            return true;
          }
          throw new Error('Failed to subscribe');
        }

        const subscription = await response.json();
        state.subscriptions = [...state.subscriptions, subscription];
        return true;
      } catch (e) {
        state.error = e instanceof Error ? e.message : 'Unknown error';
        return false;
      }
    },

    async unsubscribe(podcastId: string): Promise<boolean> {
      try {
        const response = await fetch(`/api/subscriptions/${podcastId}`, {
          method: 'DELETE'
        });

        if (!response.ok) throw new Error('Failed to unsubscribe');

        state.subscriptions = state.subscriptions.filter(s => s.podcastId !== podcastId);
        return true;
      } catch (e) {
        state.error = e instanceof Error ? e.message : 'Unknown error';
        return false;
      }
    },

    isSubscribed(podcastId: string): boolean {
      return state.subscriptions.some(s => s.podcastId === podcastId);
    },

    clearError() {
      state.error = null;
    }
  };
}

export const library = createLibrary();
