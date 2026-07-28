import React from "react";
import {Composition, type CalculateMetadataFunction} from "remotion";

import {NarratedPanels} from "./NarratedPanels";
import {
  compositionDurationInFrames,
  FPS,
  HEIGHT,
  TEMPLATE_ID,
  type NarratedPanelsProps,
  WIDTH,
} from "./types";

const defaultProps: NarratedPanelsProps = {
  scenes: [
    {
      id: "preview",
      image: "preview.png",
      audio: "preview.mp3",
      subtitle: "DoodleStory 固定旁白视频模板",
      durationMs: 3000,
      motion: "zoom_in",
    },
  ],
  bgm: null,
};

const calculateMetadata: CalculateMetadataFunction<NarratedPanelsProps> = ({
  props,
}) => ({
  durationInFrames: compositionDurationInFrames(props),
  props,
  defaultCodec: "h264",
  defaultAudioCodec: "aac",
  defaultVideoImageFormat: "jpeg",
  defaultPixelFormat: "yuv420p",
});

export const RemotionRoot: React.FC = () => (
  <Composition
    id={TEMPLATE_ID}
    component={NarratedPanels}
    durationInFrames={90}
    fps={FPS}
    width={WIDTH}
    height={HEIGHT}
    defaultProps={defaultProps}
    calculateMetadata={calculateMetadata}
  />
);
