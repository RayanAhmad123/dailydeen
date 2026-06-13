import React from "react";
import { useCurrentFrame, useVideoConfig, spring } from "remotion";
import { theme } from "../theme";

type Props = { width?: number; opacity?: number; draw?: boolean };

/** Thin gold rule with a central diamond. With `draw`, the lines grow outward and the diamond spins in. */
export const Ornament: React.FC<Props> = ({ width = 360, opacity = 1, draw = false }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = draw
    ? spring({ frame, fps, config: { damping: 15, stiffness: 110, mass: 0.8 } })
    : 1;

  const half = width / 2;
  const lineLen = (half - 26) * p;
  const rotation = 45 + (1 - p) * 135;

  return (
    <svg width={width} height={24} viewBox={`0 0 ${width} 24`} style={{ opacity }}>
      <line x1={half - 26 - lineLen} y1={12} x2={half - 26} y2={12} stroke={theme.gold} strokeWidth={1.5} />
      <line x1={half + 26} y1={12} x2={half + 26 + lineLen} y2={12} stroke={theme.gold} strokeWidth={1.5} />
      <rect
        x={half - 8}
        y={4}
        width={16}
        height={16}
        fill="none"
        stroke={theme.gold}
        strokeWidth={1.5}
        transform={`rotate(${rotation} ${half} 12) scale(${0.4 + p * 0.6})`}
        style={{ transformOrigin: `${half}px 12px` }}
      />
    </svg>
  );
};
