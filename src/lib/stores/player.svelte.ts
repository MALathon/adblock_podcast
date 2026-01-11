/**
 * Audio player store using Svelte 5 runes
 * Enhanced with expanded state for full-screen player
 */

export interface PlayerEpisode {
  id: string;
  title: string;
  podcastTitle: string;
  audioUrl: string;
  artworkUrl?: string;
  duration?: number;
  podcastId?: string;
}

interface PlayerState {
  currentEpisode: PlayerEpisode | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  isProcessing: boolean;
  isExpanded: boolean;
  playbackRate: number;
  isBuffering: boolean;
}

const PLAYBACK_RATES = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];

function createPlayer() {
  let state = $state<PlayerState>({
    currentEpisode: null,
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    volume: 1,
    isProcessing: false,
    isExpanded: false,
    playbackRate: 1,
    isBuffering: false
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
      state.isBuffering = false;
    });

    audioElement.addEventListener('pause', () => {
      state.isPlaying = false;
    });

    audioElement.addEventListener('waiting', () => {
      state.isBuffering = true;
    });

    audioElement.addEventListener('canplay', () => {
      state.isBuffering = false;
    });

    // Restore volume from localStorage
    const savedVolume = localStorage.getItem('player-volume');
    if (savedVolume) {
      const v = parseFloat(savedVolume);
      audioElement.volume = v;
      state.volume = v;
    }

    const savedRate = localStorage.getItem('player-rate');
    if (savedRate) {
      const r = parseFloat(savedRate);
      audioElement.playbackRate = r;
      state.playbackRate = r;
    }
  }

  return {
    get currentEpisode() { return state.currentEpisode; },
    get isPlaying() { return state.isPlaying; },
    get currentTime() { return state.currentTime; },
    get duration() { return state.duration; },
    get volume() { return state.volume; },
    get isProcessing() { return state.isProcessing; },
    get isExpanded() { return state.isExpanded; },
    get playbackRate() { return state.playbackRate; },
    get isBuffering() { return state.isBuffering; },

    play(episode: PlayerEpisode) {
      if (!audioElement) return;

      state.currentEpisode = episode;
      audioElement.src = episode.audioUrl;
      audioElement.playbackRate = state.playbackRate;
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

    skipBackward(seconds: number = 15) {
      if (!audioElement) return;
      audioElement.currentTime = Math.max(0, audioElement.currentTime - seconds);
    },

    skipForward(seconds: number = 30) {
      if (!audioElement) return;
      audioElement.currentTime = Math.min(state.duration, audioElement.currentTime + seconds);
    },

    setVolume(volume: number) {
      if (!audioElement) return;
      const v = Math.max(0, Math.min(1, volume));
      audioElement.volume = v;
      state.volume = v;
      localStorage.setItem('player-volume', v.toString());
    },

    setPlaybackRate(rate: number) {
      if (!audioElement) return;
      audioElement.playbackRate = rate;
      state.playbackRate = rate;
      localStorage.setItem('player-rate', rate.toString());
    },

    cyclePlaybackRate() {
      const currentIndex = PLAYBACK_RATES.indexOf(state.playbackRate);
      const nextIndex = (currentIndex + 1) % PLAYBACK_RATES.length;
      this.setPlaybackRate(PLAYBACK_RATES[nextIndex]);
    },

    setProcessing(isProcessing: boolean) {
      state.isProcessing = isProcessing;
    },

    expand() {
      state.isExpanded = true;
    },

    collapse() {
      state.isExpanded = false;
    },

    toggleExpanded() {
      state.isExpanded = !state.isExpanded;
    },

    stop() {
      if (!audioElement) return;
      audioElement.pause();
      audioElement.currentTime = 0;
      state.currentEpisode = null;
      state.isExpanded = false;
    }
  };
}

export const player = createPlayer();
