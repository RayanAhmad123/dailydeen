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

// One ayah of a multi-ayah passage, timed to its slice of the recitation.
export type AyahSegment = {
  arabic: string;
  translation: string;
  startSec: number; // relative to audio start
  endSec: number;
};

// AyahVideo: footage (muted) + on-screen ayah (Arabic + translation + reference)
// with the MATCHING Quran recitation baked in — posts directly, no in-app audio.
export type AyahData = {
  id: string;
  arabic: string;
  translation: string;
  reference: string; // e.g. "Quran 94:5-6"
  clipFile?: string | null; // trimmed 9:16 footage, relative to public/
  audioFile: string; // recitation, relative to public/, e.g. "recitation/ay_ease.mp3"
  durationSec: number;
  // Long passages (e.g. a full surah): show one ayah at a time, synced to the
  // recitation. When absent, the whole text is shown statically (short passages).
  segments?: AyahSegment[];
};
