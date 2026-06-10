import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { theme } from "../theme";
import { Ornament } from "./Ornament";
import { sansFamily } from "../fonts";

type Props = {
  text: string;
  startSec: number; // timeline-absolute time to fade in
};

/** Bottom reference card, fades in when the reference is spoken. */
export const Reference: React.FC<Props> = ({ text, startSec }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const opacity = interpolate(t, [startSec, startSec + 0.6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const rise = interpolate(t, [startSec, startSec + 0.6], [24, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

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
        opacity,
        transform: `translateY(${rise}px)`,
      }}
    >
      <Ornament width={260} opacity={0.9} />
      <div
        style={{
          fontFamily: sansFamily,
          fontSize: 34,
          letterSpacing: 5,
          textTransform: "uppercase",
          color: theme.goldSoft,
          textAlign: "center",
          padding: "0 80px",
        }}
      >
        {text}
      </div>
    </div>
  );
};
