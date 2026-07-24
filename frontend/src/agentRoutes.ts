export type AgentRoute = {
  conversationId: string | null;
  taskId: string | null;
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
    return { conversationId: null, taskId: null };
  }
  if (parts.length === 2 && parts[0] === "agent") {
    const conversationId = decodeRoutePart(parts[1]);
    return conversationId ? { conversationId, taskId: null } : null;
  }
  if (parts.length === 4 && parts[0] === "agent" && parts[2] === "tasks") {
    const conversationId = decodeRoutePart(parts[1]);
    const taskId = decodeRoutePart(parts[3]);
    return conversationId && taskId ? { conversationId, taskId } : null;
  }
  return null;
}
