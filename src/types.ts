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
