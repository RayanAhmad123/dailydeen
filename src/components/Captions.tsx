import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";
import { useMemo } from "react";
import { theme } from "../theme";
import { Word } from "../types";
import { serifFamily } from "../fonts";

type Props = {
  words: Word[];
  audioStartSec: number;
};

type Page = { words: Word[]; start: number; end: number; index: number };

const MAX_WORDS_PER_PAGE = 7;

/** Group words into readable pages, breaking at punctuation where possible. */
const paginate = (words: Word[]): Page[] => {
  const pages: Page[] = [];
  let current: Word[] = [];
  for (const w of words) {
    current.push(w);
    const endsClause = /[.!?,;:]$/.test(w.word.trim());
    if ((endsClause && current.length >= 4) || current.length >= MAX_WORDS_PER_PAGE) {
      pages.push({
        words: current,
        start: current[0].start,
        end: current[current.length - 1].end,
        index: pages.length,
      });
      current = [];
    }
  }
  if (current.length) {
    pages.push({
      words: current,
      start: current[0].start,
      end: current[current.length - 1].end,
      index: pages.length,
    });
  }
  return pages;
};

/** Karaoke captions: pages spring in, the active word pops in gold with a glow. */
export const Captions: React.FC<Props> = ({ words, audioStartSec }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps - audioStartSec;

  const pages = useMemo(() => paginate(words), [words]);
  const page = pages.find((p) => t >= p.start - 0.18 && t <= p.end + 0.35);
  if (!page) return null;

  // Page entrance: spring slide-up with a slight scale settle
  const pageFrame = Math.round((audioStartSec + page.start - 0.18) * fps);
  const enter = spring({
    frame: frame - pageFrame,
    fps,
    config: { damping: 15, stiffness: 160, mass: 0.7 },
  });

  // Alternate the slide direction per page for variety
  const fromY = page.index % 2 === 0 ? 46 : -46;

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 85px" }}>
      <div
        style={{
          fontFamily: serifFamily,
          fontSize: 76,
          lineHeight: 1.4,
          fontWeight: 600,
          textAlign: "center",
          color: theme.ivory,
          opacity: enter,
          transform: `translateY(${(1 - enter) * fromY}px) scale(${0.94 + enter * 0.06})`,
          textShadow: "0 4px 28px rgba(0,0,0,0.55)",
        }}
      >
        {page.words.map((w, i) => {
          const wordFrame = Math.round((audioStartSec + w.start) * fps);
          const pop = spring({
            frame: frame - wordFrame,
            fps,
            config: { damping: 12, stiffness: 240, mass: 0.45 },
          });
          const active = t >= w.start && t <= w.end + 0.08;
          const spoken = t > w.end + 0.08;
          // Pop overshoots on hit, then settles slightly above 1 while active
          const scale = active ? 1 + pop * 0.08 : spoken ? 1.01 : 1;
          return (
            <span
              key={i}
              style={{
                color: active ? theme.gold : spoken ? theme.ivory : theme.ivoryDim,
                display: "inline-block",
                transform: `scale(${scale}) translateY(${active ? -(pop * 4) : 0}px)`,
                textShadow: active
                  ? `0 0 46px rgba(201, 168, 92, 0.75), 0 4px 28px rgba(0,0,0,0.55)`
                  : "0 4px 28px rgba(0,0,0,0.55)",
                margin: "0 13px",
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
