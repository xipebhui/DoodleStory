import assert from "node:assert/strict";
import test from "node:test";

import {
  NATIVE_AGENT_FOLLOW_THRESHOLD_PX,
  shouldFollowNativeAgentThread,
} from "../src/nativeAgentScroll.ts";

test("会话位于底部时继续跟随新内容", () => {
  assert.equal(
    shouldFollowNativeAgentThread({
      scrollHeight: 1_000,
      scrollTop: 600,
      clientHeight: 400,
    }),
    true,
  );
});

test("会话接近底部时继续跟随新内容", () => {
  assert.equal(
    shouldFollowNativeAgentThread({
      scrollHeight: 1_000,
      scrollTop: 600 - NATIVE_AGENT_FOLLOW_THRESHOLD_PX,
      clientHeight: 400,
    }),
    true,
  );
});

test("用户向上翻阅后停止跟随新内容", () => {
  assert.equal(
    shouldFollowNativeAgentThread({
      scrollHeight: 1_000,
      scrollTop: 600 - NATIVE_AGENT_FOLLOW_THRESHOLD_PX - 1,
      clientHeight: 400,
    }),
    false,
  );
});
