import { useCurrentFrame, useVideoConfig } from "remotion";
import { theme } from "../theme";

/** Thin gold progress bar along the bottom edge. */
export const ProgressBar: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const pct = (frame / (durationInFrames - 1)) * 100;

  return (
    <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 10 }}>
      <div
        style={{
          width: `${pct}%`,
          height: "100%",
          background: `linear-gradient(90deg, ${theme.gold}, ${theme.goldSoft})`,
          boxShadow: `0 0 18px 2px ${theme.glow}`,
        }}
      />
    </div>
  );
};
