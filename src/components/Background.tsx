import { AbsoluteFill, useCurrentFrame, interpolate } from "remotion";
import { theme } from "../theme";
import { GeometricPattern } from "./GeometricPattern";

export const Background: React.FC = () => {
  const frame = useCurrentFrame();
  // Slow "breathing" of the gradient — subtle, not distracting
  const breathe = Math.sin(frame / 90) * 0.5 + 0.5;
  const glowOpacity = interpolate(breathe, [0, 1], [0.1, 0.2]);

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(168deg, ${theme.bgTop} 0%, ${theme.bgBottom} 70%)`,
      }}
    >
      {/* Warm gold glow from the top */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse 90% 45% at 50% -5%, ${theme.glow}, transparent 70%)`,
          opacity: glowOpacity / 0.14,
        }}
      />
      <GeometricPattern />
      {/* Vignette for focus and contrast */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse 120% 90% at 50% 50%, transparent 55%, rgba(0,0,0,0.55) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
