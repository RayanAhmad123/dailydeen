import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";
import { theme } from "../theme";
import { Ornament } from "./Ornament";
import { Word } from "../types";
import { serifFamily } from "../fonts";

type Props = {
  text: string;
  words: Word[];
  audioStartSec: number; // when audio begins on the timeline
};

/** Full-screen hook card shown while the hook sentence is spoken. */
export const Hook: React.FC<Props> = ({ words, audioStartSec }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps - audioStartSec; // seconds into the audio

  const entrance = spring({ frame, fps, config: { damping: 200 }, durationInFrames: 25 });
  const hookEnd = words.length ? words[words.length - 1].end : 2.5;
  const exit = interpolate(t, [hookEnd, hookEnd + 0.4], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        padding: "0 110px",
        opacity: exit,
      }}
    >
      <div
        style={{
          transform: `translateY(${(1 - entrance) * 40}px)`,
          opacity: entrance,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 44,
        }}
      >
        <Ornament width={300} opacity={0.85} />
        <div
          style={{
            fontFamily: serifFamily,
            fontSize: 78,
            lineHeight: 1.3,
            color: theme.ivory,
            textAlign: "center",
            fontWeight: 600,
            textShadow: "0 4px 30px rgba(0,0,0,0.5)",
          }}
        >
          {words.map((w, i) => {
            const active = t >= w.start;
            return (
              <span
                key={i}
                style={{
                  color: active ? theme.goldSoft : theme.ivoryDim,
                  transition: "none",
                }}
              >
                {w.word}{" "}
              </span>
            );
          })}
        </div>
        <Ornament width={300} opacity={0.85} />
      </div>
    </AbsoluteFill>
  );
};
