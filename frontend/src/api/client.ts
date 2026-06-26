export type User = {
  id: string;
  email: string;
  display_name: string | null;
  role: "user" | "admin";
};

export type CreditTransaction = {
  id: string;
  user_id: string;
  transaction_type:
    | "initial_grant"
    | "admin_adjustment"
    | "activation_code_redeem"
    | "image_generation_reserve"
    | "image_generation_charge"
    | "image_generation_release";
  amount: number;
  balance_before: number;
  balance_after: number;
  reserved_balance_before: number;
  reserved_balance_after: number;
  admin_user_id: string | null;
  task_id: string | null;
  panel_id: string | null;
  generated_image_id: string | null;
  style_test_id: string | null;
  character_appearance_id: string | null;
  activation_code_id: string | null;
  note: string | null;
  created_at: string;
  updated_at: string;
};

export type CreditTransactionFilter = "all" | "spent" | "reset";

export type CreditAccount = {
  user_id: string;
  balance: number;
  reserved_balance: number;
  created_at: string;
  updated_at: string;
};

export type CreditOverview = {
  account: CreditAccount;
  recent_transactions: CreditTransaction[];
};

export type CreditUsagePoint = {
  label: string;
  spent_credits: number;
  started_at: string;
};

export type AdminUserCreditSummary = {
  id: string;
  email: string;
  display_name: string | null;
  role: "user" | "admin";
  balance: number;
  reserved_balance: number;
  task_count: number;
  succeeded_image_count: number;
  spent_credits: number;
  created_at: string;
  updated_at: string;
};

export type AdminUserCreditDetail = {
  user: AdminUserCreditSummary;
  recent_transactions: CreditTransaction[];
};

export type AdminCreditUsageSummary = {
  total_spent_credits: number;
  transaction_count: number;
  active_user_count: number;
};

export type AdminCreditUsage = {
  summary: AdminCreditUsageSummary;
  points: CreditUsagePoint[];
};

export type AdminCreditTransaction = CreditTransaction & {
  user_email: string;
  user_display_name: string | null;
};

export type ActivationCode = {
  id: string;
  code_prefix: string;
  credit_amount: number;
  note: string | null;
  expires_at: string | null;
  disabled_at: string | null;
  created_by_admin_id: string | null;
  redeemed_by_user_id: string | null;
  redeemed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ActivationCodeCreated = {
  id: string;
  code: string;
  credit_amount: number;
  expires_at: string | null;
  note: string | null;
};

export type Style = {
  id: string;
  name: string;
  description: string | null;
  status: "draft" | "active" | "disabled";
  image_model_name: string;
  aspect_ratio: string;
  style_reference_mode: "prompt" | "image";
  style_prompt: string;
  cover_asset: FileAsset | null;
  last_tested_at: string | null;
  reference_images: StyleReferenceImage[];
  created_at: string;
  updated_at: string;
};

export type StyleOption = {
  id: string;
  name: string;
  description: string | null;
  status: "draft" | "active" | "disabled";
  image_model_name: string;
  aspect_ratio: string;
  style_reference_mode: "prompt" | "image";
  preview_asset: FileAsset | null;
  last_tested_at: string | null;
  created_at: string;
  updated_at: string;
};

export type StyleSelectOption = {
  id: string;
  name: string;
};

export type FileAsset = {
  id: string;
  purpose: string;
  storage_backend: string;
  public_url: string | null;
  original_filename: string | null;
  content_type: string;
  byte_size: number;
  width: number | null;
  height: number | null;
  content_url: string;
  thumbnail_url: string;
  created_at: string;
  updated_at: string;
};

export type UserCharacter = {
  id: string;
  owner_user_id: string;
  name: string;
  description: string | null;
  reference_asset: FileAsset;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type StoryCharacterBinding = {
  source_name: string;
  user_character_id: string;
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
  style_reference_mode_snapshot: "prompt" | "image";
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
  story_input_mode: "original" | "adapted" | "extracted_storyboard";
  adapted_story_title: string | null;
  adapted_story_hook: string | null;
  adapted_story_text: string | null;
  image_count_mode: "auto" | "fixed";
  requested_image_count: number | null;
  use_character_references: boolean;
  last_panel_real_photo: boolean;
  style_id: string;
  style_name_snapshot: string;
  image_model_name_snapshot: string;
  style_aspect_ratio_snapshot: string;
  style_reference_mode_snapshot: "prompt" | "image";
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

export type TaskPreviewImage = {
  id: string;
  panel_id: string;
  asset: FileAsset;
};

export type TaskSummary = {
  id: string;
  owner_user_id: string;
  owner_display_name: string | null;
  owner_email: string | null;
  display_title: string;
  original_text_preview: string;
  story_input_mode: Task["story_input_mode"];
  image_count_mode: Task["image_count_mode"];
  requested_image_count: number | null;
  use_character_references: boolean;
  last_panel_real_photo: boolean;
  style_id: string;
  style_name_snapshot: string;
  image_model_name_snapshot: string;
  style_aspect_ratio_snapshot: string;
  style_reference_mode_snapshot: "prompt" | "image";
  status: Task["status"];
  progress_current: number;
  progress_total: number;
  error_code: string | null;
  error_message: string | null;
  current_step: string | null;
  image_count: number;
  preview_images: TaskPreviewImage[];
  created_at: string;
  updated_at: string;
};

export type AudioReference = {
  id: string;
  owner_user_id: string;
  owner_display_name: string | null;
  owner_email: string | null;
  name: string;
  description: string | null;
  reference_text?: string | null;
  voice_provider: string | null;
  voice_model: string | null;
  voice_name: string | null;
  deleted_at?: string | null;
  asset: FileAsset;
  created_at: string;
  updated_at: string;
};

export type VideoTaskStatus =
  | "waiting_for_images"
  | "ready_for_audio"
  | "audio_generating"
  | "audio_ready"
  | "video_generating"
  | "succeeded"
  | "failed"
  | "cancel_requested"
  | "cancelled";

export type VideoTaskSourceTask = {
  id: string;
  display_title: string;
  status: Task["status"];
  progress_current: number;
  progress_total: number;
  error_code: string | null;
  error_message: string | null;
  style_name_snapshot: string;
  style_aspect_ratio_snapshot: string;
  image_count: number;
  preview_images: TaskPreviewImage[];
};

export type VideoTask = {
  id: string;
  owner_user_id: string;
  owner_display_name: string | null;
  owner_email: string | null;
  display_title: string;
  original_text: string;
  original_text_preview?: string;
  status: VideoTaskStatus;
  current_step: "generate_source_images" | "generate_narration_audio" | "submit_video" | "download_video";
  progress_current: number;
  progress_total: number;
  started_at: string | null;
  finished_at: string | null;
  error_code: string | null;
  error_message: string | null;
  audio_reference_id: string;
  audio_reference_name_snapshot: string;
  audio_reference_text_snapshot: string | null;
  audio_reference_asset: FileAsset;
  narration_audio_asset: FileAsset | null;
  output_video_asset: FileAsset | null;
  source_task: VideoTaskSourceTask;
  created_at: string;
  updated_at: string;
};

export type VideoTaskSummary = Omit<
  VideoTask,
  "original_text" | "started_at" | "finished_at" | "audio_reference_id" | "audio_reference_text_snapshot" | "audio_reference_asset" | "narration_audio_asset"
> & {
  original_text_preview: string;
};

export type TaskCharacterReference = {
  id: string;
  name: string;
  age_stage: string | null;
  reference_prompt: string | null;
  asset: FileAsset;
};

export type TaskPanel = {
  id: string;
  panel_order: number;
  panel_type: "cover" | "scene";
  prompt_status: "pending" | "generated" | "failed";
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
  prompt_change_summary: string | null;
  asset: FileAsset | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type GeneratedImageDebug = {
  id: string;
  generation_number: number;
  is_current: boolean;
  source_type: GeneratedImage["source_type"];
  status: GeneratedImage["status"];
  user_instruction: string | null;
  prompt_change_summary: string | null;
  image_text_json: string | null;
  text_layout: string | null;
  previous_prompt: string | null;
  image_prompt: string | null;
  final_prompt: string | null;
  error_message: string | null;
};

export type TaskPanelDebug = {
  panel_id: string;
  panel_order: number;
  original_text_segment: string;
  narration_text: string | null;
  dialogue_text: string | null;
  image_text_json: string | null;
  text_layout: string | null;
  generated_prompt: string | null;
  images: GeneratedImageDebug[];
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

export type ContentExtractionMedia = {
  id: string;
  media_kind: "image" | "video" | "audio" | "metadata";
  display_order: number;
  asset: FileAsset;
  extracted_text: string | null;
  created_at: string;
  updated_at: string;
};

export type ContentExtraction = {
  id: string;
  owner_user_id: string;
  raw_input: string;
  source_url: string;
  media_type: string;
  aweme_id: string | null;
  source_title: string | null;
  source_description: string | null;
  source_tags: string[];
  processing_status: "processing" | "succeeded" | "failed" | string;
  processing_error_message: string | null;
  extracted_text: string | null;
  story_content: string | null;
  story_highlight: string | null;
  target_audience: string | null;
  story_summary_model: string | null;
  story_summarized_at: string | null;
  linked_task_id: string | null;
  task_create_status: string | null;
  task_create_error_message: string | null;
  media: ContentExtractionMedia[];
  created_at: string;
  updated_at: string;
};

export type ContentExtractionSummary = {
  id: string;
  owner_user_id: string;
  source_url: string;
  media_type: string;
  aweme_id: string | null;
  source_title: string | null;
  source_description: string | null;
  source_tags: string[];
  processing_status: "processing" | "succeeded" | "failed" | string;
  processing_error_message: string | null;
  raw_input_preview: string | null;
  extracted_text_preview: string | null;
  story_content_preview: string | null;
  story_highlight_preview: string | null;
  target_audience_preview: string | null;
  has_extracted_text: boolean;
  has_story_summary: boolean;
  media_count: number;
  linked_task_id: string | null;
  task_create_status: string | null;
  task_create_error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type ContentExtractionHealth = {
  ok: boolean;
  service_base_url: string;
  response: Record<string, unknown> | null;
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
    return trimTrailingSlash(configured);
  }

  if (isLoopbackHost(current.hostname)) {
    return "http://127.0.0.1:8000";
  }
  return "";
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
  myCredits: () => request<ApiData<CreditOverview>>("/credits/me").then((result) => result.data),
  redeemCreditCode: (payload: { code: string }) =>
    request<ApiData<CreditOverview>>("/credits/redeem", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  creditUsage: (params: { days: 1 | 7 | 30 }) =>
    request<ApiData<CreditUsagePoint[]>>(`/credits/usage?days=${params.days}`).then((result) => result.data),
  creditTransactions: (params?: { filter?: CreditTransactionFilter; cursor?: string | null; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.filter && params.filter !== "all") search.set("filter", params.filter);
    if (params?.cursor) search.set("cursor", params.cursor);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<CreditTransaction>>(`/credits/transactions${suffix}`);
  },
  adminUsers: (params?: { query?: string; cursor?: string | null; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.query) search.set("query", params.query);
    if (params?.cursor) search.set("cursor", params.cursor);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<AdminUserCreditSummary>>(`/admin/users${suffix}`);
  },
  adminUserDetail: (userId: string) =>
    request<ApiData<AdminUserCreditDetail>>(`/admin/users/${userId}`).then((result) => result.data),
  adminCreditUsage: (params?: { days?: 1 | 7 | 30; user_id?: string | null }) => {
    const search = new URLSearchParams();
    if (params?.days) search.set("days", String(params.days));
    if (params?.user_id) search.set("user_id", params.user_id);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiData<AdminCreditUsage>>(`/admin/credits/usage${suffix}`).then((result) => result.data);
  },
  adminCreditTransactions: (params?: { user_id?: string | null; cursor?: string | null; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.user_id) search.set("user_id", params.user_id);
    if (params?.cursor) search.set("cursor", params.cursor);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<AdminCreditTransaction>>(`/admin/credits/transactions${suffix}`);
  },
  adjustAdminUserCredits: (userId: string, payload: { amount: number; note: string }) =>
    request<ApiData<AdminUserCreditDetail>>(`/admin/users/${userId}/credits/adjust`, {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  createActivationCodes: (payload: { credit_amount: number; count: number; expires_at?: string | null; note?: string | null }) =>
    request<ApiData<ActivationCodeCreated[]>>("/admin/activation-codes", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  activationCodes: (params?: { cursor?: string | null; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.cursor) search.set("cursor", params.cursor);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<ActivationCode>>(`/admin/activation-codes${suffix}`);
  },
  styles: (params?: { query?: string; status?: Style["status"] | "all" }) => {
    const search = new URLSearchParams();
    if (params?.query) search.set("query", params.query);
    if (params?.status && params.status !== "all") search.set("status", params.status);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<Style>>(`/styles${suffix}`);
  },
  styleOptions: (params?: { query?: string; status?: Style["status"] | "all"; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.query) search.set("query", params.query);
    if (params?.status && params.status !== "all") search.set("status", params.status);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<StyleOption>>(`/styles/options${suffix}`);
  },
  styleSelectOptions: (params?: { query?: string; status?: Style["status"] | "all"; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.query) search.set("query", params.query);
    if (params?.status && params.status !== "all") search.set("status", params.status);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<StyleSelectOption>>(`/styles/select-options${suffix}`);
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
  assetContentUrl: (assetId: string, variant: "original" | "thumbnail" = "original") =>
    `${API_BASE_URL}/api/v1/assets/${assetId}/content${variant === "thumbnail" ? "?variant=thumbnail" : ""}`,
  audioReferences: (params?: { query?: string; cursor?: string | null; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.query) search.set("query", params.query);
    if (params?.cursor) search.set("cursor", params.cursor);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<AudioReference>>(`/audio-references${suffix}`);
  },
  audioReference: (id: string) =>
    request<ApiData<AudioReference>>(`/audio-references/${id}`).then((result) => result.data),
  createAudioReference: (payload: {
    name: string;
    description?: string | null;
    reference_text?: string | null;
    voice_provider?: string | null;
    voice_model?: string | null;
    voice_name?: string | null;
    file: File;
  }) => {
    const form = new FormData();
    form.append("name", payload.name);
    form.append("description", payload.description ?? "");
    form.append("reference_text", payload.reference_text ?? "");
    form.append("voice_provider", payload.voice_provider ?? "");
    form.append("voice_model", payload.voice_model ?? "");
    form.append("voice_name", payload.voice_name ?? "");
    form.append("file", payload.file);
    return request<ApiData<AudioReference>>("/audio-references", { method: "POST", body: form }).then((result) => result.data);
  },
  deleteAudioReference: (id: string) =>
    request<ApiData<{ deleted: boolean }>>(`/audio-references/${id}`, { method: "DELETE" }),
  videoTasks: (params?: { query?: string; status?: VideoTaskStatus | "all"; cursor?: string | null; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.query) search.set("query", params.query);
    if (params?.status && params.status !== "all") search.set("status", params.status);
    if (params?.cursor) search.set("cursor", params.cursor);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<VideoTaskSummary>>(`/video-tasks${suffix}`);
  },
  videoTask: (id: string) => request<ApiData<VideoTask>>(`/video-tasks/${id}`).then((result) => result.data),
  createVideoTask: (payload: {
    original_text: string;
    image_count_mode: "auto" | "fixed";
    requested_image_count?: number | null;
    style_id: string;
    audio_reference_id: string;
    use_character_references?: boolean;
    last_panel_real_photo?: boolean;
  }) =>
    request<ApiData<VideoTask>>("/video-tasks", { method: "POST", body: JSON.stringify(payload) }).then(
      (result) => result.data,
    ),
  tasks: (params?: {
    query?: string;
    status?: Task["status"] | "all";
    style_id?: string;
    user_id?: string | null;
    cursor?: string | null;
    limit?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.query) search.set("query", params.query);
    if (params?.status && params.status !== "all") search.set("status", params.status);
    if (params?.style_id) search.set("style_id", params.style_id);
    if (params?.user_id) search.set("user_id", params.user_id);
    if (params?.cursor) search.set("cursor", params.cursor);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<TaskSummary>>(`/tasks${suffix}`);
  },
  task: (id: string) => request<ApiData<Task>>(`/tasks/${id}`).then((result) => result.data),
  taskPanelDebug: (taskId: string, panelId: string) =>
    request<ApiData<TaskPanelDebug>>(`/tasks/${taskId}/panels/${panelId}/debug`).then((result) => result.data),
  createTask: (payload: {
    original_text: string;
    story_input_mode?: Task["story_input_mode"];
    image_count_mode: "auto" | "fixed";
    requested_image_count?: number | null;
    style_id: string;
    use_character_references?: boolean;
    last_panel_real_photo?: boolean;
    story_characters?: StoryCharacterBinding[];
  }) => request<ApiData<Task>>("/tasks", { method: "POST", body: JSON.stringify(payload) }).then((result) => result.data),
  extractCharacterNames: (payload: { text: string }) =>
    request<ApiData<{ names: string[] }>>("/tasks/extract-character-names", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  mergeCharacterIntoStory: (payload: {
    story_text: string;
    character_name: string;
    character_description?: string | null;
  }) =>
    request<ApiData<{ story_text: string; change_summary: string }>>("/tasks/merge-character-into-story", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  characters: (params?: { query?: string; cursor?: string | null; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.query) search.set("query", params.query);
    if (params?.cursor) search.set("cursor", params.cursor);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<UserCharacter>>(`/characters${suffix}`);
  },
  character: (id: string) => request<ApiData<UserCharacter>>(`/characters/${id}`).then((result) => result.data),
  createCharacter: (payload: { name: string; description?: string | null; file: File }) => {
    const form = new FormData();
    form.append("name", payload.name);
    form.append("description", payload.description ?? "");
    form.append("file", payload.file);
    return request<ApiData<UserCharacter>>("/characters", { method: "POST", body: form }).then((result) => result.data);
  },
  describeCharacterReference: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ApiData<{ description: string }>>("/characters/describe-reference", {
      method: "POST",
      body: form,
    }).then((result) => result.data);
  },
  updateCharacter: (id: string, payload: { name?: string; description?: string | null; file?: File | null }) => {
    const form = new FormData();
    if (payload.name !== undefined) form.append("name", payload.name);
    if (payload.description !== undefined) form.append("description", payload.description ?? "");
    if (payload.file) form.append("file", payload.file);
    return request<ApiData<UserCharacter>>(`/characters/${id}`, { method: "PATCH", body: form }).then((result) => result.data);
  },
  deleteCharacter: (id: string) => request<ApiData<{ deleted: boolean }>>(`/characters/${id}`, { method: "DELETE" }),
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
  contentExtractionHealth: () =>
    request<ApiData<ContentExtractionHealth>>("/content-extractions/douyin-health").then((result) => result.data),
  contentExtractions: (params?: {
    query?: string;
    cursor?: string | null;
    limit?: number;
    media_type?: string;
    result_status?: string;
  }) => {
    const search = new URLSearchParams();
    if (params?.query) search.set("query", params.query);
    if (params?.cursor) search.set("cursor", params.cursor);
    if (params?.limit) search.set("limit", String(params.limit));
    if (params?.media_type) search.set("media_type", params.media_type);
    if (params?.result_status) search.set("result_status", params.result_status);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<ContentExtractionSummary>>(`/content-extractions${suffix}`);
  },
  contentExtraction: (id: string) =>
    request<ApiData<ContentExtraction>>(`/content-extractions/${id}`).then((result) => result.data),
  downloadContentExtraction: (payload: { raw_input: string }) =>
    request<ApiData<ContentExtraction>>("/content-extractions/download", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  processContentExtraction: (payload: { raw_input: string }) =>
    request<ApiData<ContentExtraction>>("/content-extractions/process", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  replicateContentAsTask: (payload: {
    raw_input: string;
    image_count_mode: "auto" | "fixed";
    requested_image_count?: number | null;
    style_id: string;
    use_character_references?: boolean;
    last_panel_real_photo?: boolean;
  }) =>
    request<ApiData<ContentExtraction>>("/content-extractions/replicate-task", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  extractContentText: (id: string) =>
    request<ApiData<ContentExtraction>>(`/content-extractions/${id}/extract`, { method: "POST" }).then(
      (result) => result.data,
    ),
};
