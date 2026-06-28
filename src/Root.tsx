import { Composition } from "remotion";
import { HadithVideo } from "./HadithVideo";
import { ReflectionVideo } from "./ReflectionVideo";
import { AyahVideo } from "./AyahVideo";
import defaultData from "./videoData.json";
import reflectionData from "./reflectionData.json";
import ayahData from "./ayahData.json";
import { VideoData, ReflectionData, AyahData } from "./types";

export const FPS = 30;

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="HadithVideo"
        component={HadithVideo}
        width={1080}
        height={1920}
        fps={FPS}
        durationInFrames={30 * FPS}
        defaultProps={defaultData as VideoData}
        calculateMetadata={({ props }) => ({
          // 1s lead-in + audio + 2.5s outro hold
          durationInFrames: Math.ceil((1 + props.durationSec + 2.5) * FPS),
          props,
        })}
      />
      <Composition
        id="ReflectionVideo"
        component={ReflectionVideo}
        width={1080}
        height={1920}
        fps={FPS}
        durationInFrames={18 * FPS}
        defaultProps={reflectionData as ReflectionData}
        calculateMetadata={({ props }) => ({
          durationInFrames: Math.ceil(props.durationSec * FPS),
          props,
        })}
      />
      <Composition
        id="AyahVideo"
        component={AyahVideo}
        width={1080}
        height={1920}
        fps={FPS}
        durationInFrames={14 * FPS}
        defaultProps={ayahData as AyahData}
        calculateMetadata={({ props }) => ({
          durationInFrames: Math.ceil(props.durationSec * FPS),
          props,
        })}
      />
    </>
  );
};
