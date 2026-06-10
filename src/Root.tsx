import { Composition } from "remotion";
import { HadithVideo } from "./HadithVideo";
import defaultData from "./videoData.json";
import { VideoData } from "./types";

export const FPS = 30;

export const Root: React.FC = () => {
  return (
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
  );
};
