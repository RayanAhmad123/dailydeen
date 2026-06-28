export type Word = {
  word: string;
  start: number; // seconds, relative to audio start
  end: number;
};

export type VideoData = {
  id: string;
  category: string;
  hook: { text: string; words: Word[] };
  body: { words: Word[] };
  reference: { text: string; startSec: number };
  audioFile: string; // relative to public/, e.g. "audio/hadith_1.wav"
  durationSec: number;
  scenes?: string[]; // AI story illustrations, relative to public/, shown behind captions
};

// ReflectionVideo: real footage (muted) + an on-screen Islamic quote, rendered
// SILENT — a Quran recitation is added from the platform audio library at post time.
export type ReflectionData = {
  id: string;
  quote: string;
  source: string; // attribution shown on screen, e.g. "Quran 94:6"
  clipFile?: string | null; // trimmed 9:16 clip, relative to public/, e.g. "reflection/r1.mp4"
  durationSec: number;
};
