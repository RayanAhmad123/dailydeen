import { useCurrentFrame, useVideoConfig, spring } from "remotion";
import { theme } from "../theme";
import { sansFamily } from "../fonts";

type Props = {
  startSec: number; // when the audio has finished
};

/** Follow CTA shown during the outro hold, after the voiceover ends. */
export const Outro: React.FC<Props> = ({ startSec }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const startFrame = Math.round(startSec * fps);
  const enter = spring({
    frame: frame - startFrame,
    fps,
    config: { damping: 13, stiffness: 140, mass: 0.7 },
  });
  if (frame < startFrame) return null;

  const pulse = 1 + Math.sin((frame - startFrame) / 9) * 0.02;

  return (
    <div
      style={{
        position: "absolute",
        bottom: 380,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity: enter,
        transform: `translateY(${(1 - enter) * 50}px)`,
      }}
    >
      <div
        style={{
          fontFamily: sansFamily,
          fontSize: 32,
          letterSpacing: 4,
          textTransform: "uppercase",
          color: theme.bgBottom,
          background: `linear-gradient(120deg, ${theme.gold}, ${theme.goldSoft})`,
          padding: "26px 64px",
          borderRadius: 999,
          fontWeight: 500,
          transform: `scale(${pulse})`,
          boxShadow: `0 10px 50px rgba(201, 168, 92, 0.35)`,
        }}
      >
        Follow for Daily Wisdom
      </div>
    </div>
  );
};
