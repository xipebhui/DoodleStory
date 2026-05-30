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

export type PageInfo = {
  limit: number;
  next_cursor: string | null;
  has_more: boolean;
};

export type ApiData<T> = {
  data: T;
};

export type ApiList<T> = {
  items: T[];
  page: PageInfo;
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
    throw new Error(body?.error?.message ?? body?.detail ?? "请求失败");
  }

  return body as T;
}

export const api = {
  me: async () => (await request<ApiData<{ user: User }>>("/auth/me")).data,
  login: (payload: { email: string; password: string }) =>
    request<ApiData<{ user: User }>>("/auth/login", { method: "POST", body: JSON.stringify(payload) }).then(
      (result) => result.data,
    ),
  register: (payload: { email: string; password: string; display_name?: string }) =>
    request<ApiData<{ user: User }>>("/auth/register", { method: "POST", body: JSON.stringify(payload) }).then(
      (result) => result.data,
    ),
  logout: () => request<ApiData<{ ok: boolean }>>("/auth/logout", { method: "POST" }),
  styles: () => request<ApiList<Style>>("/styles"),
  createStyle: (payload: Partial<Style>) =>
    request<ApiData<Style>>("/styles", { method: "POST", body: JSON.stringify(payload) }),
  tasks: () => request<ApiList<Task>>("/tasks"),
};
