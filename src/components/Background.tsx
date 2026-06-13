import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { theme } from "../theme";
import { GeometricPattern } from "./GeometricPattern";
import { Particles } from "./Particles";

export const Background: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Slow "breathing" of the gradient — subtle, not distracting
  const breathe = Math.sin(frame / 90) * 0.5 + 0.5;
  const glowOpacity = interpolate(breathe, [0, 1], [0.7, 1.4]);

  // Continuous cinematic push-in across the whole video
  const zoom = interpolate(frame, [0, durationInFrames], [1, 1.12]);

  // A soft light ray that sweeps across very slowly
  const sweep = interpolate(frame, [0, durationInFrames], [-30, 130]);

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(168deg, ${theme.bgTop} 0%, ${theme.bgBottom} 70%)`,
      }}
    >
      <AbsoluteFill style={{ transform: `scale(${zoom})` }}>
        {/* Warm gold glow from the top */}
        <AbsoluteFill
          style={{
            background: `radial-gradient(ellipse 90% 45% at 50% -5%, ${theme.glow}, transparent 70%)`,
            opacity: glowOpacity,
          }}
        />
        {/* Cool counter-glow rising from the bottom */}
        <AbsoluteFill
          style={{
            background:
              "radial-gradient(ellipse 80% 35% at 50% 105%, rgba(36, 99, 86, 0.22), transparent 70%)",
            opacity: 2 - glowOpacity,
          }}
        />
        {/* Slow diagonal light sweep */}
        <AbsoluteFill
          style={{
            background: `linear-gradient(115deg, transparent ${sweep - 18}%, rgba(232, 213, 163, 0.05) ${sweep}%, transparent ${sweep + 18}%)`,
          }}
        />
        <GeometricPattern />
        <Particles />
      </AbsoluteFill>
      {/* Vignette for focus and contrast — outside the zoom so edges stay dark */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse 120% 90% at 50% 50%, transparent 55%, rgba(0,0,0,0.55) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
