import {
  AbsoluteFill,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
} from "remotion";
import { Background } from "./components/Background";
import { Ornament } from "./components/Ornament";
import { theme } from "./theme";
import { serifFamily, sansFamily } from "./fonts";
import { ReflectionData } from "./types";

/**
 * Footage (muted) + an authentic Islamic quote on screen. Rendered SILENT —
 * a Quran recitation is added from the TikTok/YouTube audio library at post time.
 * If no clip is supplied it falls back to the themed Background so it always renders.
 */
export const ReflectionVideo: React.FC<ReflectionData> = ({ quote, source, clipFile }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Slow Ken Burns push-in on the footage so it never feels static
  const scale = interpolate(frame, [0, durationInFrames], [1.04, 1.14]);

  // Quote fades/rises in early; source follows; both ease out at the very end
  const enter = spring({ frame: frame - Math.round(0.6 * fps), fps, config: { damping: 18, mass: 0.8 } });
  const srcEnter = spring({ frame: frame - Math.round(1.3 * fps), fps, config: { damping: 18, mass: 0.8 } });
  const outFade = interpolate(
    frame,
    [durationInFrames - Math.round(0.8 * fps), durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill>
      {/* Base: themed background (also the fallback when there's no clip) */}
      <Background />

      {/* Footage layer (muted), cover-cropped to 9:16 with gentle motion */}
      {clipFile ? (
        <AbsoluteFill style={{ transform: `scale(${scale})` }}>
          <OffthreadVideo
            src={staticFile(clipFile)}
            muted
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </AbsoluteFill>
      ) : null}

      {/* Legibility scrim — darker top & bottom so the quote reads on any footage */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(8,16,25,0.55) 0%, rgba(8,16,25,0.20) 35%, rgba(8,16,25,0.45) 65%, rgba(8,16,25,0.82) 100%)",
        }}
      />
      {/* Vignette */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse 120% 85% at 50% 50%, transparent 50%, rgba(0,0,0,0.5) 100%)",
        }}
      />

      {/* Quote block, centered */}
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          padding: "0 110px",
          opacity: outFade,
        }}
      >
        <div style={{ opacity: enter, transform: `translateY(${(1 - enter) * 40}px)`, textAlign: "center" }}>
          <Ornament />
          <div
            style={{
              fontFamily: serifFamily,
              fontWeight: 700,
              fontSize: 72,
              lineHeight: 1.28,
              color: theme.ivory,
              textShadow: "0 4px 28px rgba(0,0,0,0.7)",
              margin: "44px 0",
            }}
          >
            &ldquo;{quote}&rdquo;
          </div>
        </div>

        <div
          style={{
            opacity: srcEnter,
            transform: `translateY(${(1 - srcEnter) * 24}px)`,
            fontFamily: sansFamily,
            fontWeight: 500,
            fontSize: 30,
            letterSpacing: 3,
            textTransform: "uppercase",
            color: theme.gold,
            textShadow: "0 2px 14px rgba(0,0,0,0.8)",
            marginTop: 8,
          }}
        >
          {source}
        </div>
      </AbsoluteFill>

      {/* Channel mark */}
      <div
        style={{
          position: "absolute",
          bottom: 70,
          left: 0,
          right: 0,
          textAlign: "center",
          fontFamily: sansFamily,
          fontSize: 26,
          letterSpacing: 6,
          textTransform: "uppercase",
          color: theme.ivoryDim,
          opacity: outFade,
        }}
      >
        @DailyDeen
      </div>
    </AbsoluteFill>
  );
};
