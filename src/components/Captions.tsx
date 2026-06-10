import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { useMemo } from "react";
import { theme } from "../theme";
import { Word } from "../types";
import { serifFamily } from "../fonts";

type Props = {
  words: Word[];
  audioStartSec: number;
};

type Page = { words: Word[]; start: number; end: number };

const MAX_WORDS_PER_PAGE = 8;

/** Group words into readable pages, breaking at punctuation where possible. */
const paginate = (words: Word[]): Page[] => {
  const pages: Page[] = [];
  let current: Word[] = [];
  for (const w of words) {
    current.push(w);
    const endsClause = /[.!?,;:]$/.test(w.word.trim());
    if ((endsClause && current.length >= 4) || current.length >= MAX_WORDS_PER_PAGE) {
      pages.push({ words: current, start: current[0].start, end: current[current.length - 1].end });
      current = [];
    }
  }
  if (current.length) {
    pages.push({ words: current, start: current[0].start, end: current[current.length - 1].end });
  }
  return pages;
};

/** Karaoke captions: one page of words at a time, active word in gold. */
export const Captions: React.FC<Props> = ({ words, audioStartSec }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps - audioStartSec;

  const pages = useMemo(() => paginate(words), [words]);
  const page = pages.find((p) => t >= p.start - 0.15 && t <= p.end + 0.35);
  if (!page) return null;

  const fadeIn = interpolate(t, [page.start - 0.15, page.start + 0.1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 95px" }}>
      <div
        style={{
          fontFamily: serifFamily,
          fontSize: 72,
          lineHeight: 1.42,
          fontWeight: 600,
          textAlign: "center",
          color: theme.ivory,
          opacity: fadeIn,
          textShadow: "0 4px 28px rgba(0,0,0,0.55)",
        }}
      >
        {page.words.map((w, i) => {
          const active = t >= w.start && t <= w.end + 0.08;
          const spoken = t > w.end + 0.08;
          return (
            <span
              key={i}
              style={{
                color: active ? theme.gold : spoken ? theme.ivory : theme.ivoryDim,
                display: "inline-block",
                transform: active ? "scale(1.06)" : "scale(1)",
                margin: "0 9px",
              }}
            >
              {w.word}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
