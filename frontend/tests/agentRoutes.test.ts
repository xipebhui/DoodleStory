import assert from "node:assert/strict";
import test from "node:test";

import { parseAgentRoute } from "../src/agentRoutes.ts";

test("parses the Agent root and conversation routes", () => {
  assert.deepEqual(parseAgentRoute("/agent"), {
    conversationId: null,
    taskId: null,
    skillPage: null,
  });
  assert.deepEqual(parseAgentRoute("/agent/conversation-1/"), {
    conversationId: "conversation-1",
    taskId: null,
    skillPage: null,
  });
});

test("parses the Agent task inspector route", () => {
  assert.deepEqual(parseAgentRoute("/agent/conversation%201/tasks/task%202"), {
    conversationId: "conversation 1",
    taskId: "task 2",
    skillPage: null,
  });
});

test("parses skill management routes before conversation ids", () => {
  assert.deepEqual(parseAgentRoute("/agent/skills"), {
    conversationId: null,
    taskId: null,
    skillPage: { mode: "list" },
  });
  assert.deepEqual(parseAgentRoute("/agent/skills/new"), {
    conversationId: null,
    taskId: null,
    skillPage: { mode: "new" },
  });
  assert.deepEqual(parseAgentRoute("/agent/skills/skill-1"), {
    conversationId: null,
    taskId: null,
    skillPage: { mode: "detail", skillId: "skill-1" },
  });
  assert.deepEqual(parseAgentRoute("/agent/skills/skill-1/versions/version-2"), {
    conversationId: null,
    taskId: null,
    skillPage: {
      mode: "version",
      skillId: "skill-1",
      versionId: "version-2",
    },
  });
});

test("rejects incomplete and unrelated Agent routes", () => {
  assert.equal(parseAgentRoute("/agent/conversation-1/tasks"), null);
  assert.equal(parseAgentRoute("/agent/conversation-1/tasks/task-1/edit"), null);
  assert.equal(parseAgentRoute("/tasks/task-1"), null);
});
