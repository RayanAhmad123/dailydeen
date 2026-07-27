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
export const AyahVideo: React.FC<AyahData> = ({ arabic, translation, reference, clipFile, audioFile, segments }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const sequenced = !!segments && segments.length > 0;

  // Long single-ayah texts (e.g. Ayat al-Kursi, 2:255) can't be split into
  // segments — auto-fit the static layout instead. Texts at or below the sizes
  // every published video used (≤190 Arabic / ≤250 translation chars) render
  // exactly as before; longer ones scale down smoothly.
  const arFit = Math.min(1, Math.pow(190 / arabic.length, 0.6));
  const arSize = Math.max(48, Math.round(92 * arFit));
  const arLineHeight = arSize < 75 ? 1.55 : 1.7;
  const enFit = Math.min(1, Math.pow(250 / translation.length, 0.6));
  const enSize = Math.max(28, Math.round(50 * enFit));
  const enLineHeight = enSize < 42 ? 1.28 : 1.32;

  const scale = interpolate(frame, [0, durationInFrames], [1.04, 1.14]);
  const arEnter = spring({ frame: frame - Math.round(0.5 * fps), fps, config: { damping: 18, mass: 0.8 } });
  const enEnter = spring({ frame: frame - Math.round(1.4 * fps), fps, config: { damping: 18, mass: 0.8 } });
  const outFade = interpolate(
    frame,
    [durationInFrames - Math.round(0.8 * fps), durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  // Share CTA crossfades in over the handle for the final seconds
  const ctaIn = interpolate(
    frame,
    [durationInFrames - Math.round(2.6 * fps), durationInFrames - Math.round(1.8 * fps)],
    [0, 1],
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

      {sequenced ? (
        <>
          {/* One ayah at a time, timed to its slice of the recitation */}
          {segments!.map((seg, i) => {
            const startF = Math.round(seg.startSec * fps);
            const endF = Math.round(seg.endSec * fps);
            const isLast = i === segments!.length - 1;
            if (frame < startF || (!isLast && frame >= endF)) return null;
            const enter = spring({ frame: frame - startF, fps, config: { damping: 18, mass: 0.8 } });
            const trEnter = spring({ frame: frame - startF - Math.round(0.25 * fps), fps, config: { damping: 18, mass: 0.8 } });
            const exit = isLast
              ? 1
              : interpolate(frame, [endF - Math.round(0.3 * fps), endF], [1, 0], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                });
            return (
              <AbsoluteFill
                key={i}
                style={{ justifyContent: "center", alignItems: "center", padding: "0 96px", opacity: exit * outFade }}
              >
                <div
                  style={{
                    opacity: enter,
                    transform: `translateY(${(1 - enter) * 30}px)`,
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
                  {seg.arabic}
                </div>

                <div style={{ margin: "36px 0 24px", opacity: trEnter }}>
                  <Ornament />
                </div>

                <div
                  style={{
                    opacity: trEnter,
                    transform: `translateY(${(1 - trEnter) * 24}px)`,
                    fontFamily: serifFamily,
                    fontWeight: 600,
                    fontSize: 50,
                    lineHeight: 1.32,
                    color: theme.ivory,
                    textAlign: "center",
                    textShadow: "0 3px 20px rgba(0,0,0,0.8)",
                  }}
                >
                  {seg.translation}
                </div>
              </AbsoluteFill>
            );
          })}

          {/* Reference — persistent while the ayat rotate */}
          <div
            style={{
              position: "absolute",
              bottom: 148,
              left: 0,
              right: 0,
              textAlign: "center",
              fontFamily: sansFamily,
              fontWeight: 500,
              fontSize: 30,
              letterSpacing: 4,
              textTransform: "uppercase",
              color: theme.gold,
              textShadow: "0 2px 14px rgba(0,0,0,0.85)",
              opacity: enEnter * outFade,
            }}
          >
            {reference}
          </div>
        </>
      ) : (
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 96px", opacity: outFade }}>
        {/* Arabic ayah — the hero */}
        <div
          style={{
            opacity: arEnter,
            transform: `translateY(${(1 - arEnter) * 30}px)`,
            fontFamily: arabicFamily,
            direction: "rtl",
            fontWeight: 400,
            fontSize: arSize,
            lineHeight: arLineHeight,
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
            fontSize: enSize,
            lineHeight: enLineHeight,
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
      )}

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
          opacity: outFade * (1 - ctaIn),
        }}
      >
        @DailyDeen
      </div>
      <div
        style={{
          position: "absolute",
          bottom: 64,
          left: 0,
          right: 0,
          textAlign: "center",
          fontFamily: sansFamily,
          fontSize: 26,
          letterSpacing: 4,
          textTransform: "uppercase",
          color: theme.gold,
          textShadow: "0 2px 14px rgba(0,0,0,0.85)",
          opacity: outFade * ctaIn,
        }}
      >
        Send this to someone who needs it
      </div>
    </AbsoluteFill>
  );
};
