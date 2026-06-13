import { AbsoluteFill, useCurrentFrame } from "remotion";
import React from "react";
import { theme } from "../theme";

/**
 * Subtle 8-pointed star (khatam) tile pattern — classic Islamic geometry.
 * Rendered at very low opacity with an extremely slow drift.
 */
const Star: React.FC<{ cx: number; cy: number; r: number }> = ({ cx, cy, r }) => {
  const points: string[] = [];
  for (let i = 0; i < 16; i++) {
    const angle = (Math.PI / 8) * i - Math.PI / 2;
    const radius = i % 2 === 0 ? r : r * 0.42;
    points.push(`${cx + radius * Math.cos(angle)},${cy + radius * Math.sin(angle)}`);
  }
  return (
    <polygon
      points={points.join(" ")}
      fill="none"
      stroke={theme.gold}
      strokeWidth={1.5}
    />
  );
};

export const GeometricPattern: React.FC = () => {
  const frame = useCurrentFrame();
  const drift = frame * 0.12; // slow downward drift
  const rotate = frame * 0.008; // barely-perceptible rotation for life

  const tile = 270;
  const stars: React.ReactNode[] = [];
  for (let row = -1; row < 9; row++) {
    for (let col = -1; col < 6; col++) {
      const offset = row % 2 === 0 ? 0 : tile / 2;
      stars.push(
        <Star
          key={`${row}-${col}`}
          cx={col * tile + offset + tile / 2}
          cy={row * tile + tile / 2}
          r={92}
        />
      );
    }
  }

  return (
    <AbsoluteFill style={{ opacity: 0.055 }}>
      <svg
        width={1080}
        height={2200}
        viewBox="0 0 1080 2200"
        style={{ transform: `translateY(${-140 + (drift % tile)}px) rotate(${rotate}deg)`, transformOrigin: "540px 960px" }}
      >
        {stars}
      </svg>
    </AbsoluteFill>
  );
};
