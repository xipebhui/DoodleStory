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
  image_model_name: string;
  aspect_ratio: string;
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

export type StyleTest = {
  id: string;
  style_id: string;
  test_text: string;
  composed_prompt: string;
  aspect_ratio_snapshot: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancel_requested" | "cancelled" | "retrying";
  output_asset: FileAsset | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type Task = {
  id: string;
  owner_user_id: string;
  display_title: string;
  original_text: string;
  story_input_mode: "original" | "adapted";
  adapted_story_title: string | null;
  adapted_story_hook: string | null;
  adapted_story_text: string | null;
  image_count_mode: "auto" | "fixed";
  requested_image_count: number | null;
  use_character_references: boolean;
  style_id: string;
  style_name_snapshot: string;
  image_model_name_snapshot: string;
  style_aspect_ratio_snapshot: string;
  status:
    | "queued"
    | "running"
    | "succeeded"
    | "partial_succeeded"
    | "failed"
    | "cancel_requested"
    | "cancelled"
    | "retrying";
  progress_current: number;
  progress_total: number;
  error_code: string | null;
  error_message: string | null;
  current_step: string | null;
  panels: TaskPanel[];
  steps: GenerationStep[];
  generated_images: GeneratedImage[];
  character_references: TaskCharacterReference[];
  downloads: TaskDownload[];
  created_at: string;
  updated_at: string;
};

export type TaskCharacterReference = {
  id: string;
  name: string;
  age_stage: string | null;
  asset: FileAsset;
};

export type TaskPanel = {
  id: string;
  panel_order: number;
  panel_type: "cover" | "scene";
  original_text_segment: string;
  narration_text: string | null;
  dialogue_text: string | null;
  image_text_json: string | null;
  text_layout: string | null;
  prompt_status: "pending" | "generated" | "failed";
  generated_prompt: string | null;
  created_at: string;
  updated_at: string;
};

export type GenerationStep = {
  id: string;
  step_name: string;
  status: string;
  attempts: number;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type GeneratedImage = {
  id: string;
  panel_id: string;
  status: string;
  generation_number: number;
  is_current: boolean;
  source_type: "initial" | "user_edit" | "retry";
  workflow_step: "rewrite_prompt" | "generate_image" | null;
  user_instruction: string | null;
  previous_prompt: string | null;
  image_prompt: string | null;
  image_text_json: string | null;
  text_layout: string | null;
  prompt_change_summary: string | null;
  final_prompt: string | null;
  asset: FileAsset | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type TaskDownload = {
  id: string;
  status: "queued" | "running" | "ready" | "failed";
  image_count: number;
  filename: string;
  asset: FileAsset | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
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

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function isLoopbackHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "0.0.0.0" || hostname === "::1" || hostname.startsWith("127.");
}

function resolveApiBaseUrl(): string {
  const configured = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
  if (configured === "/" || configured === ".") {
    return "";
  }
  if (typeof window === "undefined") {
    return configured ? trimTrailingSlash(configured) : "http://127.0.0.1:8000";
  }

  const current = window.location;
  if (configured) {
    try {
      const configuredUrl = new URL(configured);
      if (isLoopbackHost(configuredUrl.hostname) && !isLoopbackHost(current.hostname)) {
        return `${current.protocol}//${current.hostname}:8000`;
      }
    } catch {
      return trimTrailingSlash(configured);
    }
    return trimTrailingSlash(configured);
  }

  if (isLoopbackHost(current.hostname)) {
    return "http://127.0.0.1:8000";
  }
  return `${current.protocol}//${current.hostname}:8000`;
}

export const API_BASE_URL = resolveApiBaseUrl();

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
  createStyleTest: (styleId: string, payload: { test_text: string }) =>
    request<ApiData<StyleTest>>(`/styles/${styleId}/tests`, {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  assetContentUrl: (assetId: string) => `${API_BASE_URL}/api/v1/assets/${assetId}/content`,
  tasks: (params?: {
    query?: string;
    status?: Task["status"] | "all";
    style_id?: string;
    cursor?: string | null;
    limit?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.query) search.set("query", params.query);
    if (params?.status && params.status !== "all") search.set("status", params.status);
    if (params?.style_id) search.set("style_id", params.style_id);
    if (params?.cursor) search.set("cursor", params.cursor);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<Task>>(`/tasks${suffix}`);
  },
  task: (id: string) => request<ApiData<Task>>(`/tasks/${id}`).then((result) => result.data),
  createTask: (payload: {
    original_text: string;
    story_input_mode?: "original" | "adapted";
    image_count_mode: "auto" | "fixed";
    requested_image_count?: number | null;
    style_id: string;
    use_character_references?: boolean;
  }) => request<ApiData<Task>>("/tasks", { method: "POST", body: JSON.stringify(payload) }).then((result) => result.data),
  cancelTask: (id: string) =>
    request<ApiData<Task>>(`/tasks/${id}/cancel`, { method: "POST" }).then((result) => result.data),
  retryTask: (id: string) =>
    request<ApiData<Task>>(`/tasks/${id}/retry`, { method: "POST" }).then((result) => result.data),
  editPanelImage: (taskId: string, panelId: string, payload: { user_instruction: string }) =>
    request<ApiData<Task>>(`/tasks/${taskId}/panels/${panelId}/edits`, {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  createTaskDownload: (id: string) =>
    request<ApiData<TaskDownload>>(`/tasks/${id}/downloads`, { method: "POST" }).then((result) => result.data),
};
