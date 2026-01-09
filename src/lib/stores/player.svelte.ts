/**
 * Audio player store using Svelte 5 runes
 */

export interface Episode {
  id: string;
  title: string;
  podcastTitle: string;
  audioUrl: string;
  artworkUrl?: string;
  duration?: number;
}

interface PlayerState {
  currentEpisode: Episode | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  isProcessing: boolean;
}

function createPlayer() {
  let state = $state<PlayerState>({
    currentEpisode: null,
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    volume: 1,
    isProcessing: false
  });

  let audioElement: HTMLAudioElement | null = null;

  // Initialize audio element on client
  if (typeof window !== 'undefined') {
    audioElement = new Audio();

    audioElement.addEventListener('timeupdate', () => {
      state.currentTime = audioElement?.currentTime || 0;
    });

    audioElement.addEventListener('durationchange', () => {
      state.duration = audioElement?.duration || 0;
    });

    audioElement.addEventListener('ended', () => {
      state.isPlaying = false;
    });

    audioElement.addEventListener('play', () => {
      state.isPlaying = true;
    });

    audioElement.addEventListener('pause', () => {
      state.isPlaying = false;
    });
  }

  return {
    get currentEpisode() { return state.currentEpisode; },
    get isPlaying() { return state.isPlaying; },
    get currentTime() { return state.currentTime; },
    get duration() { return state.duration; },
    get volume() { return state.volume; },
    get isProcessing() { return state.isProcessing; },

    play(episode: Episode) {
      if (!audioElement) return;

      state.currentEpisode = episode;
      audioElement.src = episode.audioUrl;
      audioElement.play();
    },

    togglePlay() {
      if (!audioElement) return;

      if (state.isPlaying) {
        audioElement.pause();
      } else {
        audioElement.play();
      }
    },

    pause() {
      audioElement?.pause();
    },

    seek(time: number) {
      if (!audioElement) return;
      audioElement.currentTime = Math.max(0, Math.min(time, state.duration));
    },

    setVolume(volume: number) {
      if (!audioElement) return;
      const v = Math.max(0, Math.min(1, volume));
      audioElement.volume = v;
      state.volume = v;
    },

    setProcessing(isProcessing: boolean) {
      state.isProcessing = isProcessing;
    },

    stop() {
      if (!audioElement) return;
      audioElement.pause();
      audioElement.currentTime = 0;
      state.currentEpisode = null;
    }
  };
}

export const player = createPlayer();
