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

/** Full-screen hook card: each word pops in with spring physics as it is spoken. */
export const Hook: React.FC<Props> = ({ words, audioStartSec }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps - audioStartSec; // seconds into the audio

  const entrance = spring({ frame, fps, config: { damping: 16, stiffness: 130, mass: 0.8 } });
  const hookEnd = words.length ? words[words.length - 1].end : 2.5;

  // Punchy exit: scale up slightly while fading, like a camera push-through
  const exitT = interpolate(t, [hookEnd + 0.1, hookEnd + 0.45], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const exitScale = 1 + exitT * 0.12;

  // Gentle continuous growth while the hook is on screen, for energy
  const live = interpolate(t, [0, hookEnd], [1, 1.05], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        padding: "0 90px",
        opacity: 1 - exitT,
      }}
    >
      <div
        style={{
          transform: `translateY(${(1 - entrance) * 60}px) scale(${(0.9 + entrance * 0.1) * live * exitScale})`,
          opacity: entrance,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 48,
        }}
      >
        <Ornament width={300} opacity={0.85} draw />
        <div
          style={{
            fontFamily: serifFamily,
            fontSize: 88,
            lineHeight: 1.25,
            color: theme.ivory,
            textAlign: "center",
            fontWeight: 700,
            textShadow: "0 4px 30px rgba(0,0,0,0.5)",
          }}
        >
          {words.map((w, i) => {
            // Full hook is readable from frame one (dimmed); each word ignites
            // to gold with a spring pop the moment it is spoken.
            const wordFrame = Math.round((audioStartSec + w.start) * fps);
            const pop = spring({
              frame: frame - wordFrame,
              fps,
              config: { damping: 11, stiffness: 220, mass: 0.5 },
            });
            const isLast = i === words.length - 1;
            const litColor = isLast ? theme.gold : theme.goldSoft;
            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  opacity: 0.45 + pop * 0.55,
                  transform: `scale(${0.97 + pop * 0.06}) translateY(${(1 - pop) * 6}px)`,
                  color: pop > 0.01 ? litColor : theme.ivoryDim,
                  textShadow:
                    pop > 0.01
                      ? isLast
                        ? `0 0 60px rgba(201, 168, 92, ${0.65 * pop}), 0 4px 30px rgba(0,0,0,0.5)`
                        : `0 0 40px rgba(232, 213, 163, ${0.3 * pop}), 0 4px 30px rgba(0,0,0,0.5)`
                      : "0 4px 30px rgba(0,0,0,0.5)",
                  margin: "0 11px",
                }}
              >
                {w.word}
              </span>
            );
          })}
        </div>
        <Ornament width={300} opacity={0.85} draw />
      </div>
    </AbsoluteFill>
  );
};
