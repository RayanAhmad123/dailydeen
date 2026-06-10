import { AbsoluteFill, Audio, Sequence, staticFile, useVideoConfig } from "remotion";
import { Background } from "./components/Background";
import { Header } from "./components/Header";
import { Hook } from "./components/Hook";
import { Captions } from "./components/Captions";
import { Reference } from "./components/Reference";
import { VideoData } from "./types";

const AUDIO_START_SEC = 1; // brief lead-in before the voiceover begins

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
      <Header chapter={data.chapter} />

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
    </AbsoluteFill>
  );
};
