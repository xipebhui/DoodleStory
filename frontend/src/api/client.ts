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
  generation_profile_configured: boolean;
  style_prompt: string;
  cover_asset: FileAsset | null;
  last_tested_at: string | null;
  reference_images: StyleReferenceImage[];
  created_at: string;
  updated_at: string;
};

export type FileAsset = {
  id: string;
  purpose: string;
  original_filename: string | null;
  content_type: string;
  byte_size: number;
  width: number | null;
  height: number | null;
  created_at: string;
  updated_at: string;
};

export type StyleReferenceImage = {
  id: string;
  display_order: number;
  created_at: string;
  asset: FileAsset;
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
  const isFormData = init?.body instanceof FormData;
  const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    credentials: "include",
    headers: {
      ...(isFormData ? {} : { "content-type": "application/json" }),
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
  styles: (params?: { query?: string; status?: Style["status"] | "all" }) => {
    const search = new URLSearchParams();
    if (params?.query) search.set("query", params.query);
    if (params?.status && params.status !== "all") search.set("status", params.status);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<Style>>(`/styles${suffix}`);
  },
  style: (id: string) => request<ApiData<Style>>(`/styles/${id}`).then((result) => result.data),
  createStyle: (payload: Partial<Style>) =>
    request<ApiData<Style>>("/styles", { method: "POST", body: JSON.stringify(payload) }).then((result) => result.data),
  updateStyle: (id: string, payload: Partial<Style>) =>
    request<ApiData<Style>>(`/styles/${id}`, { method: "PATCH", body: JSON.stringify(payload) }).then(
      (result) => result.data,
    ),
  deleteStyle: (id: string) => request<ApiData<{ deleted: boolean }>>(`/styles/${id}`, { method: "DELETE" }),
  uploadStyleReferenceImage: (styleId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ApiData<StyleReferenceImage>>(`/styles/${styleId}/reference-images`, {
      method: "POST",
      body: form,
    }).then((result) => result.data);
  },
  deleteStyleReferenceImage: (styleId: string, referenceId: string) =>
    request<ApiData<{ deleted: boolean }>>(`/styles/${styleId}/reference-images/${referenceId}`, {
      method: "DELETE",
    }),
  assetContentUrl: (assetId: string) => `${API_BASE_URL}/api/v1/assets/${assetId}/content`,
  tasks: () => request<ApiList<Task>>("/tasks"),
};
