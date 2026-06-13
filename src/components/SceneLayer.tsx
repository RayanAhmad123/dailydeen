import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig, interpolate } from "remotion";

type Props = {
  scenes: string[];
};

const CROSSFADE_SEC = 0.9;

/**
 * AI story illustrations behind the captions. Scenes split the video evenly,
 * crossfade into each other, and each gets Ken Burns motion (alternating
 * zoom-in/zoom-out with a drifting pan) so nothing is ever static.
 */
export const SceneLayer: React.FC<Props> = ({ scenes }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  if (!scenes.length) return null;

  const total = durationInFrames;
  const per = total / scenes.length;
  const fade = CROSSFADE_SEC * fps;

  return (
    <AbsoluteFill>
      {scenes.map((src, i) => {
        const start = i * per;
        const end = start + per;
        // Render a bit beyond the slot so crossfades overlap
        if (frame < start - fade || frame > end + fade) return null;

        const opacity =
          interpolate(frame, [start - fade, start], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }) *
          interpolate(frame, [end, end + fade], [1, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });

        // Ken Burns: alternate zoom direction, vary pan per scene index
        const p = (frame - start) / per;
        const zoomIn = i % 2 === 0;
        const scale = zoomIn ? 1.06 + p * 0.12 : 1.18 - p * 0.12;
        const panX = Math.sin(i * 2.4) * 30 * (p - 0.5) * 2;
        const panY = Math.cos(i * 1.7) * 22 * (p - 0.5) * 2;

        return (
          <AbsoluteFill key={i} style={{ opacity }}>
            <Img
              src={staticFile(src)}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                transform: `scale(${scale}) translate(${panX}px, ${panY}px)`,
              }}
            />
          </AbsoluteFill>
        );
      })}
      {/* Scrim: keeps gold captions readable over any artwork */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(8,16,25,0.72) 0%, rgba(8,16,25,0.38) 30%, rgba(8,16,25,0.45) 55%, rgba(8,16,25,0.78) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
