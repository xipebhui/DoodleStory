import assert from "node:assert/strict";
import test from "node:test";

import {
  clearNativeAgentPublishingResources,
  filterNativeAgentResources,
  nativeAgentResourceId,
  removeNativeAgentResource,
  selectNativeAgentResource,
  type NativeAgentResource,
} from "../src/nativeAgentResources.ts";

function resource(
  kind: NativeAgentResource["kind"],
  id: string,
  displayName = id,
  secondaryText = "",
): NativeAgentResource {
  return {
    kind,
    id,
    displayName,
    secondaryText,
    searchText: `${displayName} ${secondaryText}`,
  };
}

test("创作账号和直接 Style 保持互斥", () => {
  const skill = resource("skill", "skill-1");
  const style = resource("style", "style-1");
  const channel = resource("creation_channel", "channel-1");

  const withStyle = selectNativeAgentResource([skill], style);
  assert.equal(nativeAgentResourceId(withStyle, "style"), "style-1");

  const withChannel = selectNativeAgentResource(withStyle, channel);
  assert.equal(nativeAgentResourceId(withChannel, "style"), "");
  assert.equal(
    nativeAgentResourceId(withChannel, "creation_channel"),
    "channel-1",
  );

  const replacedAgain = selectNativeAgentResource(withChannel, style);
  assert.equal(nativeAgentResourceId(replacedAgain, "creation_channel"), "");
  assert.equal(nativeAgentResourceId(replacedAgain, "style"), "style-1");
});

test("同类资源会替换，发布频道变化会清除审核视频", () => {
  const channelOne = resource("youtube_channel", "youtube-1");
  const channelTwo = resource("youtube_channel", "youtube-2");
  const video = resource("publishable_video", "video-1");

  const selected = selectNativeAgentResource(
    selectNativeAgentResource([channelOne], video),
    channelTwo,
  );

  assert.equal(nativeAgentResourceId(selected, "youtube_channel"), "youtube-2");
  assert.equal(nativeAgentResourceId(selected, "publishable_video"), "");
});

test("移除发布频道时一并移除审核视频", () => {
  const channel = resource("youtube_channel", "youtube-1");
  const video = resource("publishable_video", "video-1");
  const skill = resource("skill", "skill-1");
  const selected = [skill, channel, video];

  assert.deepEqual(removeNativeAgentResource(selected, channel), [skill]);
});

test("禁用资源不会进入选择结果", () => {
  const skill = resource("skill", "skill-1");
  const disabledChannel = {
    ...resource("creation_channel", "channel-1"),
    disabledReason: "尚未绑定风格",
  };

  assert.deepEqual(selectNativeAgentResource([skill], disabledChannel), [skill]);
});

test("资源搜索同时匹配名称、说明和搜索别名", () => {
  const resources = [
    {
      ...resource("creation_channel", "channel-1", "中国文明长纪录片", "创作账号"),
      searchText: "@history china",
    },
    resource("style", "style-1", "黑白档案", "9:16"),
  ];

  assert.deepEqual(
    filterNativeAgentResources(resources, "history").map((item) => item.id),
    ["channel-1"],
  );
  assert.deepEqual(
    filterNativeAgentResources(resources, "档案").map((item) => item.id),
    ["style-1"],
  );
});

test("提交成功后只清除一次性发布资源", () => {
  const resources = [
    resource("skill", "skill-1"),
    resource("creation_channel", "channel-1"),
    resource("youtube_channel", "youtube-1"),
    resource("publishable_video", "video-1"),
  ];

  assert.deepEqual(
    clearNativeAgentPublishingResources(resources).map((item) => item.kind),
    ["skill", "creation_channel"],
  );
});
