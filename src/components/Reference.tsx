import { useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";
import { theme } from "../theme";
import { Ornament } from "./Ornament";
import { sansFamily } from "../fonts";

type Props = {
  text: string;
  startSec: number; // timeline-absolute time to fade in
};

/** Bottom reference card: springs up with a soft gold halo when the reference is spoken. */
export const Reference: React.FC<Props> = ({ text, startSec }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const startFrame = Math.round(startSec * fps);
  const rise = spring({
    frame: frame - startFrame,
    fps,
    config: { damping: 14, stiffness: 130, mass: 0.8 },
  });
  const tracking = interpolate(rise, [0, 1], [12, 5]);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 180,
        left: 0,
        right: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 22,
        opacity: rise,
        transform: `translateY(${(1 - rise) * 60}px)`,
      }}
    >
      {/* Soft halo behind the card */}
      <div
        style={{
          position: "absolute",
          inset: "-60px 120px",
          background: `radial-gradient(ellipse 100% 100% at 50% 50%, ${theme.glow}, transparent 70%)`,
          opacity: rise,
        }}
      />
      <Ornament width={260} opacity={0.9} draw />
      <div
        style={{
          fontFamily: sansFamily,
          fontSize: 34,
          letterSpacing: tracking,
          textTransform: "uppercase",
          color: theme.goldSoft,
          textAlign: "center",
          padding: "0 80px",
          textShadow: "0 0 36px rgba(201, 168, 92, 0.45)",
        }}
      >
        {text}
      </div>
    </div>
  );
};
