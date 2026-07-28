export type AgentRoute = {
  conversationId: string | null;
  taskId: string | null;
  skillPage:
    | { mode: "list" }
    | { mode: "new" }
    | { mode: "detail"; skillId: string }
    | { mode: "edit"; skillId: string }
    | { mode: "version"; skillId: string; versionId: string }
    | null;
  channelPage:
    | { mode: "list" }
    | { mode: "detail"; channelId: string }
    | null;
};

function decodeRoutePart(value: string): string | null {
  try {
    const decoded = decodeURIComponent(value);
    return decoded || null;
  } catch {
    return null;
  }
}

export function parseAgentRoute(pathname: string): AgentRoute | null {
  const normalized = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  const parts = normalized.split("/").filter(Boolean);
  if (parts.length === 1 && parts[0] === "agent") {
    return { conversationId: null, taskId: null, skillPage: null, channelPage: null };
  }
  if (parts.length === 2 && parts[0] === "agent" && parts[1] === "channels") {
    return { conversationId: null, taskId: null, skillPage: null, channelPage: { mode: "list" } };
  }
  if (parts.length === 3 && parts[0] === "agent" && parts[1] === "channels") {
    const channelId = decodeRoutePart(parts[2]);
    return channelId
      ? { conversationId: null, taskId: null, skillPage: null, channelPage: { mode: "detail", channelId } }
      : null;
  }
  if (parts.length === 2 && parts[0] === "agent" && parts[1] === "skills") {
    return { conversationId: null, taskId: null, skillPage: { mode: "list" }, channelPage: null };
  }
  if (parts.length === 3 && parts[0] === "agent" && parts[1] === "skills" && parts[2] === "new") {
    return { conversationId: null, taskId: null, skillPage: { mode: "new" }, channelPage: null };
  }
  if (parts.length === 3 && parts[0] === "agent" && parts[1] === "skills") {
    const skillId = decodeRoutePart(parts[2]);
    return skillId
      ? { conversationId: null, taskId: null, skillPage: { mode: "detail", skillId }, channelPage: null }
      : null;
  }
  if (
    parts.length === 4 &&
    parts[0] === "agent" &&
    parts[1] === "skills" &&
    parts[3] === "edit"
  ) {
    const skillId = decodeRoutePart(parts[2]);
    return skillId
      ? { conversationId: null, taskId: null, skillPage: { mode: "edit", skillId }, channelPage: null }
      : null;
  }
  if (
    parts.length === 5 &&
    parts[0] === "agent" &&
    parts[1] === "skills" &&
    parts[3] === "versions"
  ) {
    const skillId = decodeRoutePart(parts[2]);
    const versionId = decodeRoutePart(parts[4]);
    return skillId && versionId
      ? {
          conversationId: null,
          taskId: null,
          skillPage: { mode: "version", skillId, versionId },
          channelPage: null,
        }
      : null;
  }
  if (parts.length === 2 && parts[0] === "agent") {
    const conversationId = decodeRoutePart(parts[1]);
    return conversationId ? { conversationId, taskId: null, skillPage: null, channelPage: null } : null;
  }
  if (parts.length === 4 && parts[0] === "agent" && parts[2] === "tasks") {
    const conversationId = decodeRoutePart(parts[1]);
    const taskId = decodeRoutePart(parts[3]);
    return conversationId && taskId
      ? { conversationId, taskId, skillPage: null, channelPage: null }
      : null;
  }
  return null;
}
