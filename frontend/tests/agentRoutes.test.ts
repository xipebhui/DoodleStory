import assert from "node:assert/strict";
import test from "node:test";

import { parseAgentRoute } from "../src/agentRoutes.ts";

test("parses the Agent root and conversation routes", () => {
  assert.deepEqual(parseAgentRoute("/agent"), {
    conversationId: null,
    taskId: null,
  });
  assert.deepEqual(parseAgentRoute("/agent/conversation-1/"), {
    conversationId: "conversation-1",
    taskId: null,
  });
});

test("parses the Agent task inspector route", () => {
  assert.deepEqual(parseAgentRoute("/agent/conversation%201/tasks/task%202"), {
    conversationId: "conversation 1",
    taskId: "task 2",
  });
});

test("rejects incomplete and unrelated Agent routes", () => {
  assert.equal(parseAgentRoute("/agent/conversation-1/tasks"), null);
  assert.equal(parseAgentRoute("/agent/conversation-1/tasks/task-1/edit"), null);
  assert.equal(parseAgentRoute("/tasks/task-1"), null);
});
