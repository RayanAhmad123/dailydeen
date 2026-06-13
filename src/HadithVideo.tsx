import { AbsoluteFill, Audio, Sequence, staticFile, useVideoConfig } from "remotion";
import { Background } from "./components/Background";
import { SceneLayer } from "./components/SceneLayer";
import { Header } from "./components/Header";
import { Hook } from "./components/Hook";
import { Captions } from "./components/Captions";
import { Reference } from "./components/Reference";
import { Outro } from "./components/Outro";
import { ProgressBar } from "./components/ProgressBar";
import { VideoData } from "./types";

const AUDIO_START_SEC = 0.4; // minimal lead-in — the first seconds decide retention

export const HadithVideo: React.FC<VideoData> = (data) => {
  const { fps } = useVideoConfig();
  const audioStartFrame = Math.round(AUDIO_START_SEC * fps);

  const hookEnd = data.hook.words.length
    ? data.hook.words[data.hook.words.length - 1].end
    : 0;
  const bodyStartFrame = Math.round((AUDIO_START_SEC + hookEnd + 0.3) * fps);

  return (
    <AbsoluteFill>
      <Background />
      {data.scenes && data.scenes.length > 0 && <SceneLayer scenes={data.scenes} />}
      <Header category={data.category} />

      <Sequence from={audioStartFrame}>
        <Audio src={staticFile(data.audioFile)} />
      </Sequence>

      {/* Hook phase */}
      <Sequence durationInFrames={bodyStartFrame}>
        <Hook
          text={data.hook.text}
          words={data.hook.words}
          audioStartSec={AUDIO_START_SEC}
        />
      </Sequence>

      {/* Body karaoke phase */}
      <Captions words={data.body.words} audioStartSec={AUDIO_START_SEC} />

      {/* Reference card */}
      <Reference
        text={data.reference.text}
        startSec={AUDIO_START_SEC + data.reference.startSec}
      />

      {/* Follow CTA once the voiceover has finished */}
      <Outro startSec={AUDIO_START_SEC + data.durationSec + 0.4} />

      <ProgressBar />
    </AbsoluteFill>
  );
};
