import {
  AbsoluteFill,
  Audio,
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
import { serifFamily, sansFamily, arabicFamily } from "./fonts";
import { AyahData } from "./types";

/**
 * Footage (muted) + the ayah (Arabic + translation + reference) with the matching
 * Quran recitation baked in. Posts directly with sound — no in-app audio step.
 */
export const AyahVideo: React.FC<AyahData> = ({ arabic, translation, reference, clipFile, audioFile }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const scale = interpolate(frame, [0, durationInFrames], [1.04, 1.14]);
  const arEnter = spring({ frame: frame - Math.round(0.5 * fps), fps, config: { damping: 18, mass: 0.8 } });
  const enEnter = spring({ frame: frame - Math.round(1.4 * fps), fps, config: { damping: 18, mass: 0.8 } });
  const outFade = interpolate(
    frame,
    [durationInFrames - Math.round(0.8 * fps), durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill>
      <Background />

      {clipFile ? (
        <AbsoluteFill style={{ transform: `scale(${scale})` }}>
          <OffthreadVideo src={staticFile(clipFile)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        </AbsoluteFill>
      ) : null}

      {/* Recitation — baked into the render */}
      {audioFile ? <Audio src={staticFile(audioFile)} /> : null}

      {/* Legibility scrim + vignette */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(8,16,25,0.62) 0%, rgba(8,16,25,0.30) 38%, rgba(8,16,25,0.50) 66%, rgba(8,16,25,0.85) 100%)",
        }}
      />
      <AbsoluteFill
        style={{ background: "radial-gradient(ellipse 120% 85% at 50% 50%, transparent 48%, rgba(0,0,0,0.55) 100%)" }}
      />

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 96px", opacity: outFade }}>
        {/* Arabic ayah — the hero */}
        <div
          style={{
            opacity: arEnter,
            transform: `translateY(${(1 - arEnter) * 30}px)`,
            fontFamily: arabicFamily,
            direction: "rtl",
            fontWeight: 400,
            fontSize: 92,
            lineHeight: 1.7,
            color: theme.ivory,
            textAlign: "center",
            textShadow: "0 4px 30px rgba(0,0,0,0.85)",
          }}
        >
          {arabic}
        </div>

        <div style={{ margin: "40px 0 28px", opacity: enEnter }}>
          <Ornament />
        </div>

        {/* Translation */}
        <div
          style={{
            opacity: enEnter,
            transform: `translateY(${(1 - enEnter) * 24}px)`,
            fontFamily: serifFamily,
            fontWeight: 600,
            fontSize: 50,
            lineHeight: 1.32,
            color: theme.ivory,
            textAlign: "center",
            textShadow: "0 3px 20px rgba(0,0,0,0.8)",
          }}
        >
          {translation}
        </div>

        {/* Reference */}
        <div
          style={{
            opacity: enEnter,
            marginTop: 26,
            fontFamily: sansFamily,
            fontWeight: 500,
            fontSize: 30,
            letterSpacing: 4,
            textTransform: "uppercase",
            color: theme.gold,
            textShadow: "0 2px 14px rgba(0,0,0,0.85)",
          }}
        >
          {reference}
        </div>
      </AbsoluteFill>

      <div
        style={{
          position: "absolute",
          bottom: 64,
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
