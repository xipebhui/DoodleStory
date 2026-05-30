export type User = {
  id: string;
  email: string;
  display_name: string | null;
  role: "user" | "admin";
};

export type Style = {
  id: string;
  name: string;
  description: string | null;
  status: "draft" | "active" | "disabled";
  generation_profile_key: string | null;
  style_prompt: string;
  last_tested_at: string | null;
  reference_images: { id: string; asset: { id: string; original_filename: string | null } }[];
  created_at: string;
  updated_at: string;
};

export type Task = {
  id: string;
  display_title: string;
  original_text: string;
  status: string;
  style_name_snapshot: string;
  progress_current: number;
  progress_total: number;
  created_at: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    credentials: "include",
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    throw new Error(body?.detail ?? body?.error?.message ?? "请求失败");
  }

  return body as T;
}

export const api = {
  me: () => request<{ user: User }>("/auth/me"),
  login: (payload: { email: string; password: string }) =>
    request<{ user: User }>("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  register: (payload: { email: string; password: string; display_name?: string }) =>
    request<{ user: User }>("/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  styles: () => request<{ data: Style[] }>("/styles"),
  createStyle: (payload: Partial<Style>) =>
    request<{ data: Style }>("/styles", { method: "POST", body: JSON.stringify(payload) }),
  tasks: () => request<{ data: Task[] }>("/tasks"),
};
