export type Word = {
  word: string;
  start: number; // seconds, relative to audio start
  end: number;
};

export type VideoData = {
  hadithNo: number;
  chapter: string;
  hook: { text: string; words: Word[] };
  body: { words: Word[] };
  reference: { text: string; startSec: number };
  audioFile: string; // relative to public/, e.g. "audio/hadith_1.wav"
  durationSec: number;
};
