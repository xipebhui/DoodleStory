import React from "react";
import {Composition, type CalculateMetadataFunction} from "remotion";

import {NarratedPanels} from "./NarratedPanels";
import {
  PaynesCreekPilot,
  PAYNES_CREEK_TEMPLATE_ID,
  paynesCreekDurationInFrames,
  type PaynesCreekPilotProps,
} from "./PaynesCreekPilot";
import {
  PaynesCreekGrokShort,
  PAYNES_CREEK_GROK_SHORT_TEMPLATE_ID,
  paynesCreekGrokShortDurationInFrames,
  type PaynesCreekGrokShortProps,
} from "./PaynesCreekGrokShort";
import {
  compositionDurationInFrames,
  DEFAULT_HEIGHT,
  DEFAULT_WIDTH,
  FPS,
  TEMPLATE_ID,
  type NarratedPanelsProps,
} from "./types";

const defaultProps: NarratedPanelsProps = {
  scenes: [
    {
      id: "preview",
      image: "preview.png",
      audio: "preview.mp3",
      subtitle: "DoodleStory 固定旁白视频模板",
      captions: [],
      durationMs: 3000,
      motion: "zoom_in",
    },
  ],
  bgm: null,
  width: DEFAULT_WIDTH,
  height: DEFAULT_HEIGHT,
};

const calculateMetadata: CalculateMetadataFunction<NarratedPanelsProps> = ({
  props,
}) => ({
  durationInFrames: compositionDurationInFrames(props),
  width: props.width,
  height: props.height,
  props,
  defaultCodec: "h264",
  defaultAudioCodec: "aac",
  defaultVideoImageFormat: "jpeg",
  defaultPixelFormat: "yuv420p",
});

const paynesCreekDefaultProps: PaynesCreekPilotProps = {
  scenes: [{
    id: "S01",
    title: "预览",
    narration: "Paynes Creek 确定性矢量样片。",
    evidence: "解释",
    durationInFrames: 90,
  }],
  narrationAudio: "preview.mp3",
  width: 1920,
  height: 1080,
};

const calculatePaynesCreekMetadata: CalculateMetadataFunction<PaynesCreekPilotProps> = ({props}) => ({
  durationInFrames: paynesCreekDurationInFrames(props),
  width: props.width,
  height: props.height,
  props,
  defaultCodec: "h264",
  defaultAudioCodec: "aac",
  defaultVideoImageFormat: "jpeg",
  defaultPixelFormat: "yuv420p",
});

const paynesCreekGrokShortDefaultProps: PaynesCreekGrokShortProps = {
  title: "Paynes Creek Grok AI 样片",
  locale: "zh-CN",
  editMode: "classic",
  presentationMode: "review",
  showFooter: true,
  footer: "PAYNES CREEK · AI VISUAL PILOT",
  scenes: [{
    id: "S01",
    title: "预览",
    narration: "Paynes Creek Grok AI 五镜短片。",
    evidence: "解释",
    video: "preview.mp4",
    durationInFrames: 270,
    playbackRate: 1,
    captions: [{text: "Paynes Creek Grok AI 五镜短片。", startFrame: 0, endFrame: 270}],
    motion: "none",
    visualTreatment: "none",
    hook: null,
  }],
  narrationAudio: "preview.mp3",
  width: 1920,
  height: 1080,
};

const calculatePaynesCreekGrokShortMetadata: CalculateMetadataFunction<PaynesCreekGrokShortProps> = ({props}) => ({
  durationInFrames: paynesCreekGrokShortDurationInFrames(props),
  width: props.width,
  height: props.height,
  props,
  defaultCodec: "h264",
  defaultAudioCodec: "aac",
  defaultVideoImageFormat: "jpeg",
  defaultPixelFormat: "yuv420p",
});

export const RemotionRoot: React.FC = () => <>
  <Composition
      id={TEMPLATE_ID}
      component={NarratedPanels}
      durationInFrames={90}
      fps={FPS}
      width={DEFAULT_WIDTH}
      height={DEFAULT_HEIGHT}
      defaultProps={defaultProps}
      calculateMetadata={calculateMetadata}
    />
  <Composition
    id={PAYNES_CREEK_TEMPLATE_ID}
    component={PaynesCreekPilot}
    durationInFrames={90}
    fps={FPS}
    width={1920}
    height={1080}
    defaultProps={paynesCreekDefaultProps}
    calculateMetadata={calculatePaynesCreekMetadata}
  />
  <Composition
    id={PAYNES_CREEK_GROK_SHORT_TEMPLATE_ID}
    component={PaynesCreekGrokShort}
    durationInFrames={270}
    fps={30}
    width={1920}
    height={1080}
    defaultProps={paynesCreekGrokShortDefaultProps}
    calculateMetadata={calculatePaynesCreekGrokShortMetadata}
  />
</>;
