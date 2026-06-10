import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { theme } from "../theme";
import { sansFamily } from "../fonts";

/** Small persistent brand mark at the top. */
export const Header: React.FC<{ chapter: string }> = ({ chapter }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const opacity = interpolate(frame, [0, fps], [0, 1], { extrapolateRight: "clamp" });

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
        gap: 14,
        opacity,
      }}
    >
      <div
        style={{
          fontFamily: sansFamily,
          fontSize: 30,
          letterSpacing: 9,
          textTransform: "uppercase",
          color: theme.gold,
        }}
      >
        Daily Hadith
      </div>
      <div
        style={{
          fontFamily: sansFamily,
          fontSize: 26,
          letterSpacing: 3,
          color: theme.ivoryDim,
        }}
      >
        {chapter}
      </div>
    </div>
  );
};
