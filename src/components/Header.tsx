import { useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";
import { theme } from "../theme";
import { sansFamily } from "../fonts";

/** Persistent brand mark at the top: springs down, letter-spacing settles in. */
export const Header: React.FC<{ category: string }> = ({ category }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const drop = spring({ frame, fps, config: { damping: 14, stiffness: 120, mass: 0.8 } });
  const tracking = interpolate(drop, [0, 1], [22, 9]);
  const lineWidth = interpolate(drop, [0, 1], [0, 120]);

  return (
    <div
      style={{
        position: "absolute",
        top: 150,
        left: 0,
        right: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 16,
        opacity: drop,
        transform: `translateY(${(1 - drop) * -40}px)`,
      }}
    >
      <div
        style={{
          fontFamily: sansFamily,
          fontSize: 30,
          letterSpacing: tracking,
          textTransform: "uppercase",
          color: theme.gold,
          textShadow: "0 0 30px rgba(201, 168, 92, 0.4)",
        }}
      >
        Daily Islamic Wisdom
      </div>
      <div style={{ width: lineWidth, height: 1.5, background: theme.gold, opacity: 0.7 }} />
      <div
        style={{
          fontFamily: sansFamily,
          fontSize: 26,
          letterSpacing: 3,
          color: theme.ivoryDim,
        }}
      >
        {category}
      </div>
    </div>
  );
};
