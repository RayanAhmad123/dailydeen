import { AbsoluteFill, useCurrentFrame } from "remotion";
import React from "react";
import { theme } from "../theme";

const COUNT = 26;

/** Deterministic pseudo-random in [0, 1) from an integer seed. */
const rand = (seed: number) => {
  const x = Math.sin(seed * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};

/** Slowly rising gold dust. All motion is derived from the frame, so renders are deterministic. */
export const Particles: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill>
      {Array.from({ length: COUNT }, (_, i) => {
        const x = rand(i) * 1080;
        const size = 2 + rand(i + 100) * 4.5;
        const speed = 0.35 + rand(i + 200) * 0.55;
        const phase = rand(i + 300) * Math.PI * 2;
        const startY = rand(i + 400) * 2120;

        const y = (((startY - frame * speed) % 2120) + 2120) % 2120 - 100;
        const drift = Math.sin(frame / 50 + phase) * 14;
        const twinkle = 0.25 + (Math.sin(frame / 22 + phase * 3) * 0.5 + 0.5) * 0.55;

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x + drift,
              top: y,
              width: size,
              height: size,
              borderRadius: "50%",
              background: theme.goldSoft,
              opacity: twinkle * 0.5,
              boxShadow: `0 0 ${size * 3}px ${size * 0.8}px ${theme.glow}`,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};
