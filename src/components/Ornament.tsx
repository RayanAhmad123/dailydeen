import React from "react";
import { theme } from "../theme";

/** Thin gold rule with a central diamond — used as a divider ornament. */
export const Ornament: React.FC<{ width?: number; opacity?: number }> = ({
  width = 360,
  opacity = 1,
}) => (
  <svg width={width} height={24} viewBox={`0 0 ${width} 24`} style={{ opacity }}>
    <line x1={0} y1={12} x2={width / 2 - 26} y2={12} stroke={theme.gold} strokeWidth={1.5} />
    <line x1={width / 2 + 26} y1={12} x2={width} y2={12} stroke={theme.gold} strokeWidth={1.5} />
    <rect
      x={width / 2 - 8}
      y={4}
      width={16}
      height={16}
      fill="none"
      stroke={theme.gold}
      strokeWidth={1.5}
      transform={`rotate(45 ${width / 2} 12)`}
    />
  </svg>
);
