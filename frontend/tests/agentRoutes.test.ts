import assert from "node:assert/strict";
import test from "node:test";

import { parseAgentRoute } from "../src/agentRoutes.ts";

test("parses the Agent root and conversation routes", () => {
  assert.deepEqual(parseAgentRoute("/agent"), {
    conversationId: null,
    taskId: null,
    skillPage: null,
    channelPage: null,
  });
  assert.deepEqual(parseAgentRoute("/agent/conversation-1/"), {
    conversationId: "conversation-1",
    taskId: null,
    skillPage: null,
    channelPage: null,
  });
});

test("parses the Agent task inspector route", () => {
  assert.deepEqual(parseAgentRoute("/agent/conversation%201/tasks/task%202"), {
    conversationId: "conversation 1",
    taskId: "task 2",
    skillPage: null,
    channelPage: null,
  });
});

test("parses channel management routes before conversation ids", () => {
  assert.deepEqual(parseAgentRoute("/agent/channels"), {
    conversationId: null,
    taskId: null,
    skillPage: null,
    channelPage: { mode: "list" },
  });
  assert.deepEqual(parseAgentRoute("/agent/channels/channel%201"), {
    conversationId: null,
    taskId: null,
    skillPage: null,
    channelPage: { mode: "detail", channelId: "channel 1" },
  });
});

test("parses skill management routes before conversation ids", () => {
  assert.deepEqual(parseAgentRoute("/agent/skills"), {
    conversationId: null,
    taskId: null,
    skillPage: { mode: "list" },
    channelPage: null,
  });
  assert.deepEqual(parseAgentRoute("/agent/skills/new"), {
    conversationId: null,
    taskId: null,
    skillPage: { mode: "new" },
    channelPage: null,
  });
  assert.deepEqual(parseAgentRoute("/agent/skills/skill-1"), {
    conversationId: null,
    taskId: null,
    skillPage: { mode: "detail", skillId: "skill-1" },
    channelPage: null,
  });
  assert.deepEqual(parseAgentRoute("/agent/skills/skill%201/edit"), {
    conversationId: null,
    taskId: null,
    skillPage: { mode: "edit", skillId: "skill 1" },
    channelPage: null,
  });
  assert.deepEqual(parseAgentRoute("/agent/skills/skill-1/versions/version-2"), {
    conversationId: null,
    taskId: null,
    skillPage: {
      mode: "version",
      skillId: "skill-1",
      versionId: "version-2",
    },
    channelPage: null,
  });
});

test("rejects incomplete and unrelated Agent routes", () => {
  assert.equal(parseAgentRoute("/agent/conversation-1/tasks"), null);
  assert.equal(parseAgentRoute("/agent/conversation-1/tasks/task-1/edit"), null);
  assert.equal(parseAgentRoute("/agent/skills/skill-1/edit/extra"), null);
  assert.equal(parseAgentRoute("/tasks/task-1"), null);
});
