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
  skill_version_id: string | null;
  skill_name: string | null;
  skill_version_number: number | null;
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

export type AgentResourceRef = {
  kind: "skill" | "style" | "character" | "task" | "panel" | "image_version";
  id: string;
  display_name: string | null;
  safe_summary?: Record<string, unknown> | null;
};

export type AgentResourceOption = {
  kind: AgentResourceRef["kind"];
  id: string;
  display_name: string;
  secondary_text: string | null;
  parent_id: string | null;
  status: string | null;
};

export type AgentSkillStatus = "draft" | "published" | "archived";

export type AgentSkillTool = {
  name: string;
  display_name: string;
  description: string;
  has_side_effects: boolean;
  may_wait: boolean;
};

export type AgentSkillVersionSummary = {
  id: string;
  version: number;
  name: string;
  description: string;
  tool_names: string[];
  content_hash: string;
  published_at: string;
  is_active: boolean;
};

export type AgentSkillSummary = {
  id: string;
  scope: "mine" | "system";
  name: string;
  description: string;
  status: AgentSkillStatus;
  tool_names: string[];
  draft_revision: number;
  active_version: AgentSkillVersionSummary | null;
  created_at: string;
  updated_at: string;
};

export type AgentSkillDetail = AgentSkillSummary & {
  instructions: string;
  archived_at: string | null;
  is_read_only: boolean;
};

export type AgentSkillVersionDetail = AgentSkillVersionSummary & {
  skill_id: string;
  instructions: string;
};

export type AgentSkillListPage = {
  items: AgentSkillSummary[];
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
};

export type AgentSkillVersionListPage = {
  items: AgentSkillVersionSummary[];
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
};

export type AgentSkillAuthoringSuggestion = {
  suggested_name: string;
  suggested_description: string;
  suggested_instructions: string;
  suggested_tool_names: string[];
  notes: string[];
};

export type AgentConversation = {
  id: string;
  title: string;
  status: "active" | "archived";
  last_message_at: string;
  created_at: string;
  updated_at: string;
};

export type AgentMessage = {
  id: string;
  conversation_id: string;
  turn_id: string | null;
  role: "user" | "assistant" | "system_event" | "task_card";
  content: string;
  resource_refs: AgentResourceRef[];
  sequence: number;
  created_at: string;
};

export type ComicPlan = {
  schema_version: 1;
  title: string;
  story_summary: string;
  aspect_ratio: string;
  style_ref_id: string;
  panels: Array<{
    panel_key: string;
    story_beat: string;
    visual_goal: string;
    required_text: string[];
    image_prompt: string;
  }>;
  estimated_image_credits: number;
};

export type AgentApproval = {
  id: string;
  artifact_id: string;
  status: "pending" | "approved" | "changes_requested" | "cancelled";
  artifact_hash: string;
  feedback: string | null;
  requested_at: string;
  resolved_at: string | null;
};

export type AgentArtifact = {
  id: string;
  conversation_id: string;
  run_id: string;
  artifact_type: "comic_plan";
  version: number;
  status: "draft" | "awaiting_approval" | "approved" | "rejected" | "superseded";
  content_hash: string;
  content: ComicPlan;
  approval: AgentApproval | null;
  created_at: string;
  updated_at: string;
};

export type AgentPublicEvent = {
  id: string;
  event_type: string;
  run_id: string;
  sequence: number;
  payload: Record<string, unknown>;
  created_at: string;
};

export type AgentRunStatus =
  | "queued"
  | "running"
  | "waiting_for_tool"
  | "waiting_for_input"
  | "paused"
  | "retrying"
  | "succeeded"
  | "failed"
  | "cancel_requested"
  | "cancelled";

export type AgentRunSummary = {
  id: string;
  turn_id: string;
  task_id: string | null;
  status: AgentRunStatus;
  model_call_count: number;
  image_call_count: number;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type AgentTaskCardImage = {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  asset_id: string | null;
  width: number | null;
  height: number | null;
  error_code: string | null;
  error_message: string | null;
};

export type AgentTaskCard = {
  task_id: string;
  run_id: string;
  title: string;
  status: Task["status"];
  progress_current: number;
  progress_total: number;
  error_code: string | null;
  error_message: string | null;
  panels: Array<{
    id: string;
    panel_order: number;
    story_beat: string;
    visual_goal: string | null;
    image: AgentTaskCardImage | null;
  }>;
};

export type AgentConversationDetail = AgentConversation & {
  messages: AgentMessage[];
  message_page: PageInfo;
  task_cards: AgentTaskCard[];
  runs: AgentRunSummary[];
};

export type AgentTaskInspectorImage = {
  id: string;
  generation_number: number;
  status: AgentTaskCardImage["status"];
  is_current: boolean;
  source_type: "initial" | "user_edit" | "retry";
  asset_id: string | null;
  width: number | null;
  height: number | null;
  error_code: string | null;
  error_message: string | null;
  accepted_at: string | null;
  accepted_by_current_user: boolean;
  inspection: {
    verdict: "accept" | "revise" | "ask_user" | "blocked";
    scores: Record<string, number>;
    issues: Array<{
      code: string;
      message: string;
      suggested_change?: string | null;
    }>;
    provider: string;
    model: string;
    inspected_at: string;
  } | null;
  created_at: string;
};

export type AgentTaskInspector = {
  conversation_id: string;
  task_id: string;
  title: string;
  status: Task["status"];
  progress_current: number;
  progress_total: number;
  error_code: string | null;
  error_message: string | null;
  panels: Array<{
    id: string;
    panel_order: number;
    story_beat: string;
    visual_goal: string | null;
    status: AgentTaskCardImage["status"] | null;
    error_code: string | null;
    error_message: string | null;
    current_image: AgentTaskInspectorImage | null;
    versions: AgentTaskInspectorImage[];
  }>;
};

export type AgentRun = AgentRunSummary & {
  conversation_id: string;
  current_step_sequence: number;
  started_at: string | null;
  finished_at: string | null;
  steps: Array<{
    id: string;
    step_type: "model_call" | "tool_call" | "tool_result" | "wait" | "final";
    status: "pending" | "running" | "succeeded" | "failed" | "cancelled";
    provider: string | null;
    model: string | null;
    error_code: string | null;
    error_message: string | null;
  }>;
};

export type NativeAgentItem = {
  id: string;
  sequence: number;
  item_type: "user_input" | "tool_call" | "tool_result" | "assistant_output" | "error";
  payload: Record<string, unknown>;
  created_at: string;
};

export type NativeAgentImage = {
  id: string;
  asset_id: string;
  prompt: string;
  provider: string;
  image_model: string;
  aspect_ratio: string;
  width: number | null;
  height: number | null;
  created_at: string;
};

export type NativeAgentAudio = {
  id: string;
  asset_id: string;
  text: string;
  provider: string;
  resource_id: string;
  model: string;
  speaker: string;
  response_format: string;
  sample_rate: number;
  duration_ms: number | null;
  speed: number;
  speech_rate: number;
  created_at: string;
};

export type NativeAgentSubtitle = {
  id: string;
  audio_id: string;
  asset_id: string;
  provider: string;
  model: string;
  language: string;
  text: string;
  cues: Array<Record<string, unknown>>;
  duration_ms: number;
  created_at: string;
};

export type NativeAgentStep = {
  id: string;
  sequence: number;
  step_type: "model_call" | "tool_call" | "final";
  status: "prepared" | "running" | "succeeded" | "failed" | "cancelled" | "unknown";
  name: string;
  tool_call_id: string | null;
  attempts: number;
  started_at: string | null;
  finished_at: string | null;
  error_code: string | null;
  error_message: string | null;
};

export type NativeAgentEvent = {
  id: string;
  sequence: number;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type NativeAgentVideo = {
  id: string;
  asset_id: string;
  bgm_asset_id: string | null;
  template_id: string;
  renderer_version: string;
  scenes: Array<Record<string, unknown>>;
  duration_ms: number;
  duration_in_frames: number;
  fps: number;
  width: number;
  height: number;
  created_at: string;
};

export type NativeAgentExternalContent = {
  id: string;
  content_asset_id: string;
  platform: string;
  content_type: string | null;
  source_url: string;
  resolved_url: string;
  source_content_id: string | null;
  title: string | null;
  description: string | null;
  author_name: string | null;
  publish_time: string | null;
  publish_timestamp: number | null;
  tags: string[];
  metrics: Record<string, unknown>;
  excerpt: string;
  created_at: string;
};

export type YoutubeChannelSummary = {
  id: string;
  channel_id: string;
  title: string;
  handle: string | null;
  avatar_url: string | null;
  remote_status: string;
  alias: string | null;
  account_positioning: string | null;
  bound_style: {
    id: string;
    name: string;
    status: string;
    aspect_ratio: string;
    image_model_name: string;
  } | null;
  style_bound_at: string | null;
  total_subscribers: number | null;
  total_views: number | null;
  total_watch_time_hours: number | null;
  total_videos: number | null;
  last_sync_success_at: string | null;
  last_sync_error: string | null;
};

export type YoutubeBenchmark = {
  id: string;
  platform: string;
  name: string;
  platform_account_id: string | null;
  profile_url: string;
  notes: string | null;
  created_at: string;
};

export type YoutubeUploadedVideo = {
  id: string;
  youtube_video_id: string;
  publish_task_id: string | null;
  source_native_agent_video_id: string | null;
  title: string | null;
  visibility: string | null;
  views: number | null;
  likes: number | null;
  uploaded_at: string;
  remote_last_sync_at: string | null;
  last_sync_error: string | null;
};

export type YoutubePublishTask = {
  id: string;
  channel_id: string;
  publishable_video_id: string;
  source_native_agent_video_id: string;
  remote_task_id: string | null;
  status: string;
  remote_status: string | null;
  title: string;
  thumbnail_url: string | null;
  video_url: string;
  visibility: string;
  planned_publish_at: string;
  confirmed_at: string;
  last_status_checked_at: string | null;
  completed_at: string | null;
  youtube_video_id: string | null;
  youtube_url: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
};

export type PublishableVideo = {
  id: string;
  source_native_agent_video_id: string;
  video_url: string;
  thumbnail_url: string | null;
  title: string;
  description: string;
  tags: string[];
  planned_publish_at: string | null;
  contains_synthetic_media: boolean;
  review_status: "draft" | "approved";
  created_at: string;
};

export type YoutubeChannelDetail = YoutubeChannelSummary & {
  account_email: string | null;
  target_audience: string | null;
  stage_goal: string | null;
  ai_definition: string | null;
  operation_notes: string | null;
  analytics: Record<string, unknown> | null;
  benchmarks: YoutubeBenchmark[];
  publish_tasks: YoutubePublishTask[];
};

export type NativeAgentRun = {
  id: string;
  conversation_id: string;
  skill_version_id: string;
  skill_name: string;
  skill_version: number;
  style_id: string | null;
  style_name: string | null;
  creation_channel_id: string | null;
  creation_channel_name: string | null;
  youtube_channel_id: string | null;
  youtube_channel_name: string | null;
  youtube_publishable_video_id: string | null;
  youtube_publishable_video_title: string | null;
  youtube_publish_confirmation: Record<string, unknown> | null;
  status: AgentRunStatus;
  model: string;
  model_call_count: number;
  image_call_count: number;
  speech_call_count: number;
  subtitle_call_count: number;
  video_call_count: number;
  workflow_phase: string | null;
  workflow_revision: number;
  workflow_checkpoint: Record<string, unknown> | null;
  final_output: string | null;
  error_code: string | null;
  error_message: string | null;
  items: NativeAgentItem[];
  images: NativeAgentImage[];
  audios: NativeAgentAudio[];
  subtitles: NativeAgentSubtitle[];
  videos: NativeAgentVideo[];
  external_contents: NativeAgentExternalContent[];
  steps: NativeAgentStep[];
  events: NativeAgentEvent[];
  artifacts: NativeAgentArtifact[];
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type NativeAgentArticleApproval = {
  id: string;
  status: "pending" | "approved" | "changes_requested" | "cancelled";
  feedback: string | null;
  requested_at: string;
  resolved_at: string | null;
};

export type NativeAgentArtifact = {
  id: string;
  artifact_type: "article_draft" | "article_review" | "final_article";
  schema_version: number;
  version: number;
  status: "completed" | "awaiting_approval" | "approved" | "rejected" | "superseded";
  producer_role: string;
  content: Record<string, unknown>;
  content_hash: string;
  approval: NativeAgentArticleApproval | null;
  created_at: string;
  updated_at: string;
};

export type NativeAgentConversation = {
  id: string;
  title: string;
  last_message_at: string;
  created_at: string;
  updated_at: string;
};

export type NativeAgentConversationDetail = NativeAgentConversation & {
  runs: NativeAgentRun[];
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

export type StylePromptExtraction = {
  style_prompt: string;
  model: string;
  reference_image_count: number;
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
  provider_request_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type Task = {
  id: string;
  owner_user_id: string;
  display_title: string;
  original_text: string;
  story_input_mode: "original" | "adapted" | "extracted_storyboard" | "knowledge_plan";
  adapted_story_title: string | null;
  adapted_story_hook: string | null;
  adapted_story_text: string | null;
  image_count_mode: "auto" | "fixed";
  requested_image_count: number | null;
  use_character_references: boolean;
  last_panel_real_photo: boolean;
  remove_image_text: boolean;
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
  remove_image_text: boolean;
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
  speech_speed: number;
  deleted_at?: string | null;
  asset: FileAsset;
  created_at: string;
  updated_at: string;
};

export type AudioReferenceTranscription = {
  text: string;
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

export type VideoTaskAudioSegment = {
  id: string;
  panel_id: string;
  panel_order: number;
  narration_text: string;
  duration_ms: number | null;
  asset: FileAsset;
  created_at: string;
  updated_at: string;
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
  voice_provider_snapshot: string | null;
  voice_model_snapshot: string | null;
  voice_name_snapshot: string | null;
  voice_speed_snapshot: number;
  narration_audio_asset: FileAsset | null;
  audio_segments: VideoTaskAudioSegment[];
  output_video_asset: FileAsset | null;
  video_provider_job_id: string | null;
  video_provider_status: string | null;
  video_provider_output_url: string | null;
  source_task: VideoTaskSourceTask;
  created_at: string;
  updated_at: string;
};

export type VideoTaskSummary = Omit<
  VideoTask,
  | "original_text"
  | "started_at"
  | "finished_at"
  | "audio_reference_id"
  | "audio_reference_text_snapshot"
  | "audio_reference_asset"
  | "voice_provider_snapshot"
  | "voice_model_snapshot"
  | "voice_name_snapshot"
  | "voice_speed_snapshot"
  | "narration_audio_asset"
  | "audio_segments"
  | "video_provider_output_url"
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
  total?: number | null;
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

async function requestBlob(path: string, init?: RequestInit): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    credentials: "include",
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const body = await response.json();
      throw new Error(body?.error?.message ?? body?.detail ?? "请求失败");
    }
    throw new Error("请求失败");
  }

  return response.blob();
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
  agentConversations: (params?: { cursor?: string | null; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.cursor) search.set("cursor", params.cursor);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<AgentConversation>>(`/agent/conversations${suffix}`);
  },
  nativeAgentConversations: (limit = 30) =>
    request<ApiList<NativeAgentConversation>>(
      `/agent-loop/conversations?limit=${limit}`,
    ),
  createNativeAgentConversation: (payload: { title: string }) =>
    request<ApiData<NativeAgentConversation>>("/agent-loop/conversations", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  nativeAgentConversation: (conversationId: string) =>
    request<ApiData<NativeAgentConversationDetail>>(
      `/agent-loop/conversations/${encodeURIComponent(conversationId)}`,
    ).then((result) => result.data),
  nativeAgentSkills: () =>
    request<ApiList<AgentResourceOption>>("/agent-loop/skills"),
  nativeAgentStyles: () =>
    request<ApiList<AgentResourceOption>>("/agent-loop/styles"),
  createNativeAgentRun: (
    conversationId: string,
    payload: {
      content: string;
      skill_version_id: string;
      style_id: string | null;
      creation_channel_id: string | null;
      youtube_channel_id: string | null;
      youtube_publishable_video_id: string | null;
      youtube_publish_confirmation: {
        visibility: "public" | "private" | "unlisted";
        planned_publish_at: string | null;
        notify_subscribers: boolean;
        confirmed: boolean;
      } | null;
    },
  ) =>
    request<ApiData<NativeAgentRun>>(
      `/agent-loop/conversations/${encodeURIComponent(conversationId)}/runs`,
      { method: "POST", body: JSON.stringify(payload) },
    ).then((result) => result.data),
  retryLatestNativeAgentRun: (conversationId: string) =>
    request<ApiData<NativeAgentRun>>(
      `/agent-loop/conversations/${encodeURIComponent(conversationId)}/retry-latest`,
      { method: "POST" },
    ).then((result) => result.data),
  decideNativeArticleApproval: (
    approvalId: string,
    payload: {
      decision: "approve" | "changes_requested";
      feedback: string | null;
    },
  ) =>
    request<ApiData<NativeAgentRun>>(
      `/agent-loop/article-approvals/${encodeURIComponent(approvalId)}/decision`,
      { method: "POST", body: JSON.stringify(payload) },
    ).then((result) => result.data),
  cancelNativeAgentRun: (runId: string) =>
    request<ApiData<NativeAgentRun>>(
      `/agent-loop/runs/${encodeURIComponent(runId)}/cancel`,
      { method: "POST" },
    ).then((result) => result.data),
  youtubeChannels: (params?: { q?: string; remote_status?: string; cursor?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.q) search.set("q", params.q);
    if (params?.remote_status) search.set("remote_status", params.remote_status);
    if (params?.cursor) search.set("cursor", params.cursor);
    search.set("limit", String(params?.limit ?? 10));
    return request<ApiList<YoutubeChannelSummary>>(`/youtube/channels?${search.toString()}`);
  },
  syncYoutubeChannels: () =>
    request<ApiData<{ total: number; created: number; updated: number }>>("/youtube/channels/sync", {
      method: "POST",
    }).then((result) => result.data),
  youtubeChannel: (channelId: string) =>
    request<ApiData<YoutubeChannelDetail>>(`/youtube/channels/${encodeURIComponent(channelId)}`).then(
      (result) => result.data,
    ),
  updateYoutubeChannelProfile: (
    channelId: string,
    payload: {
      alias: string | null;
      account_positioning: string | null;
      target_audience: string | null;
      stage_goal: string | null;
      ai_definition: string | null;
      operation_notes: string | null;
    },
  ) =>
    request<ApiData<YoutubeChannelDetail>>(
      `/youtube/channels/${encodeURIComponent(channelId)}/profile`,
      { method: "PATCH", body: JSON.stringify(payload) },
    ).then((result) => result.data),
  updateYoutubeChannelStyleBinding: (
    channelId: string,
    styleId: string,
  ) =>
    request<ApiData<YoutubeChannelDetail>>(
      `/youtube/channels/${encodeURIComponent(channelId)}/style-binding`,
      { method: "PUT", body: JSON.stringify({ style_id: styleId }) },
    ).then((result) => result.data),
  syncYoutubeChannelAnalytics: (channelId: string) =>
    request<ApiData<YoutubeChannelDetail>>(
      `/youtube/channels/${encodeURIComponent(channelId)}/analytics/sync`,
      { method: "POST" },
    ).then((result) => result.data),
  syncYoutubeChannelVideos: (channelId: string) =>
    request<ApiData<YoutubeChannelDetail>>(
      `/youtube/channels/${encodeURIComponent(channelId)}/videos/sync`,
      { method: "POST" },
    ).then((result) => result.data),
  youtubeChannelVideos: (
    channelId: string,
    params?: { cursor?: string; limit?: number },
  ) => {
    const search = new URLSearchParams();
    if (params?.cursor) search.set("cursor", params.cursor);
    search.set("limit", String(params?.limit ?? 10));
    return request<ApiList<YoutubeUploadedVideo>>(
      `/youtube/channels/${encodeURIComponent(channelId)}/videos?${search.toString()}`,
    );
  },
  addYoutubeBenchmark: (
    channelId: string,
    payload: { platform: string; name: string; platform_account_id: string | null; profile_url: string; notes: string | null },
  ) =>
    request<ApiData<YoutubeBenchmark>>(
      `/youtube/channels/${encodeURIComponent(channelId)}/benchmarks`,
      { method: "POST", body: JSON.stringify(payload) },
    ).then((result) => result.data),
  deleteYoutubeBenchmark: (channelId: string, benchmarkId: string) =>
    request<void>(
      `/youtube/channels/${encodeURIComponent(channelId)}/benchmarks/${encodeURIComponent(benchmarkId)}`,
      { method: "DELETE" },
    ),
  youtubePublishableVideos: (reviewStatus?: "draft" | "approved") => {
    const search = new URLSearchParams({ limit: "100" });
    if (reviewStatus) search.set("review_status", reviewStatus);
    return request<ApiList<PublishableVideo>>(
      `/youtube/publishable-videos?${search.toString()}`,
    );
  },
  createYoutubePublishableVideo: (payload: {
    source_native_agent_video_id: string;
    thumbnail_url: string | null;
    title: string;
    description: string;
    tags: string[];
    planned_publish_at: string | null;
    contains_synthetic_media: boolean;
    review_status: "draft" | "approved";
  }) =>
    request<ApiData<PublishableVideo>>("/youtube/publishable-videos", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  createYoutubePublishTask: (
    channelId: string,
    payload: {
      publishable_video_id: string;
      visibility: "public" | "private" | "unlisted";
      planned_publish_at: string | null;
      notify_subscribers: boolean;
      confirmed: boolean;
      idempotency_key: string;
    },
  ) =>
    request<ApiData<YoutubePublishTask>>(
      `/youtube/channels/${encodeURIComponent(channelId)}/publish-tasks`,
      { method: "POST", body: JSON.stringify(payload) },
    ).then((result) => result.data),
  refreshYoutubePublishTask: (channelId: string, taskId: string) =>
    request<ApiData<YoutubePublishTask>>(
      `/youtube/channels/${encodeURIComponent(channelId)}/publish-tasks/${encodeURIComponent(taskId)}/refresh`,
      { method: "POST" },
    ).then((result) => result.data),
  agentSkills: (params?: {
    scope?: "mine" | "system";
    status?: AgentSkillStatus | "";
    query?: string;
    page?: number;
    page_size?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.scope) search.set("scope", params.scope);
    if (params?.status) search.set("status", params.status);
    if (params?.query) search.set("query", params.query);
    if (params?.page) search.set("page", String(params.page));
    if (params?.page_size) search.set("page_size", String(params.page_size));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiData<AgentSkillListPage>>(`/agent/skills${suffix}`).then(
      (result) => result.data,
    );
  },
  agentSkill: (skillId: string) =>
    request<ApiData<AgentSkillDetail>>(
      `/agent/skills/${encodeURIComponent(skillId)}`,
    ).then((result) => result.data),
  agentSkillTools: () =>
    request<ApiData<AgentSkillTool[]>>("/agent/skills/tool-catalog").then(
      (result) => result.data,
    ),
  createAgentSkill: (payload: {
    name: string;
    description: string;
    instructions: string;
    tool_names: string[];
  }) =>
    request<ApiData<AgentSkillDetail>>("/agent/skills", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  updateAgentSkill: (
    skillId: string,
    payload: {
      name: string;
      description: string;
      instructions: string;
      tool_names: string[];
      expected_draft_revision: number;
    },
  ) =>
    request<ApiData<AgentSkillDetail>>(
      `/agent/skills/${encodeURIComponent(skillId)}`,
      { method: "PATCH", body: JSON.stringify(payload) },
    ).then((result) => result.data),
  publishAgentSkill: (
    skillId: string,
    payload: { expected_draft_revision: number; idempotency_key: string },
  ) =>
    request<ApiData<AgentSkillVersionDetail>>(
      `/agent/skills/${encodeURIComponent(skillId)}/publish`,
      { method: "POST", body: JSON.stringify(payload) },
    ).then((result) => result.data),
  agentSkillVersions: (skillId: string, page = 1, pageSize = 50) =>
    request<ApiData<AgentSkillVersionListPage>>(
      `/agent/skills/${encodeURIComponent(skillId)}/versions?page=${page}&page_size=${pageSize}`,
    ).then((result) => result.data),
  agentSkillVersion: (skillId: string, versionId: string) =>
    request<ApiData<AgentSkillVersionDetail>>(
      `/agent/skills/${encodeURIComponent(skillId)}/versions/${encodeURIComponent(versionId)}`,
    ).then((result) => result.data),
  activateAgentSkillVersion: (skillId: string, versionId: string) =>
    request<ApiData<AgentSkillDetail>>(
      `/agent/skills/${encodeURIComponent(skillId)}/versions/${encodeURIComponent(versionId)}/activate`,
      { method: "POST" },
    ).then((result) => result.data),
  archiveAgentSkill: (skillId: string) =>
    request<ApiData<AgentSkillDetail>>(
      `/agent/skills/${encodeURIComponent(skillId)}/archive`,
      { method: "POST" },
    ).then((result) => result.data),
  restoreAgentSkill: (skillId: string) =>
    request<ApiData<AgentSkillDetail>>(
      `/agent/skills/${encodeURIComponent(skillId)}/restore`,
      { method: "POST" },
    ).then((result) => result.data),
  deleteAgentSkill: (skillId: string) =>
    request<void>(`/agent/skills/${encodeURIComponent(skillId)}`, {
      method: "DELETE",
    }),
  cloneAgentSkill: (skillId: string, versionId?: string | null) =>
    request<ApiData<AgentSkillDetail>>(
      `/agent/skills/${encodeURIComponent(skillId)}/clone`,
      {
        method: "POST",
        body: JSON.stringify({ version_id: versionId || null }),
      },
    ).then((result) => result.data),
  authorAgentSkill: (payload: {
    goal: string;
    current_instructions: string | null;
    selected_tool_names: string[];
  }) =>
    request<ApiData<AgentSkillAuthoringSuggestion>>(
      "/agent/skills/authoring-assistance",
      { method: "POST", body: JSON.stringify(payload) },
    ).then((result) => result.data),
  createAgentConversation: (payload: { title: string }) =>
    request<ApiData<AgentConversation>>("/agent/conversations", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  agentStyleResources: (params?: { query?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.query) search.set("query", params.query);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<AgentResourceOption>>(`/agent/resources/styles${suffix}`);
  },
  agentSkillResources: (params?: { query?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.query) search.set("query", params.query);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<AgentResourceOption>>(`/agent/resources/skills${suffix}`);
  },
  agentCharacterResources: (params?: { query?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.query) search.set("query", params.query);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<AgentResourceOption>>(`/agent/resources/characters${suffix}`);
  },
  agentTaskResources: (params?: { query?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.query) search.set("query", params.query);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<AgentResourceOption>>(`/agent/resources/tasks${suffix}`);
  },
  agentTaskPanelResources: (taskId: string) =>
    request<ApiList<AgentResourceOption>>(
      `/agent/resources/tasks/${encodeURIComponent(taskId)}/panels`,
    ),
  agentPanelImageResources: (panelId: string, limit = 20) =>
    request<ApiList<AgentResourceOption>>(
      `/agent/resources/panels/${encodeURIComponent(panelId)}/image-versions?limit=${limit}`,
    ),
  agentConversation: (conversationId: string) =>
    request<ApiData<AgentConversationDetail>>(`/agent/conversations/${conversationId}?message_limit=100`).then(
      (result) => result.data,
    ),
  agentConversationTask: (conversationId: string, taskId: string) =>
    request<ApiData<AgentTaskInspector>>(
      `/agent/conversations/${encodeURIComponent(conversationId)}/tasks/${encodeURIComponent(taskId)}`,
    ).then((result) => result.data),
  agentArtifacts: (conversationId: string) =>
    request<ApiList<AgentArtifact>>(
      `/agent/conversations/${encodeURIComponent(conversationId)}/artifacts?limit=100`,
    ),
  decideAgentApproval: (
    approvalId: string,
    payload: { decision: "approve" | "request_changes"; feedback?: string },
  ) =>
    request<ApiData<AgentApproval>>(
      `/agent/approvals/${encodeURIComponent(approvalId)}/decisions`,
      { method: "POST", body: JSON.stringify(payload) },
    ).then((result) => result.data),
  sendAgentMessage: (conversationId: string, payload: { content: string; resource_refs: AgentResourceRef[] }) =>
    request<ApiData<{ message: AgentMessage; run: AgentRun }>>(`/agent/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  agentRun: (runId: string) => request<ApiData<AgentRun>>(`/agent/runs/${runId}`).then((result) => result.data),
  regenerateAgentPanel: (
    conversationId: string,
    taskId: string,
    panelId: string,
    payload: {
      instruction: string;
      source_image_version_id: string;
      expected_credit_cost: 1;
      allow_auto_revision: boolean;
    },
  ) =>
    request<ApiData<AgentRun>>(
      `/agent/conversations/${encodeURIComponent(conversationId)}/tasks/${encodeURIComponent(taskId)}/panels/${encodeURIComponent(panelId)}/regenerations`,
      { method: "POST", body: JSON.stringify(payload) },
    ).then((result) => result.data),
  acceptAgentImageVersion: (
    conversationId: string,
    taskId: string,
    panelId: string,
    imageId: string,
  ) =>
    request<ApiData<AgentTaskInspectorImage>>(
      `/agent/conversations/${encodeURIComponent(conversationId)}/tasks/${encodeURIComponent(taskId)}/panels/${encodeURIComponent(panelId)}/versions/${encodeURIComponent(imageId)}/accept`,
      { method: "POST" },
    ).then((result) => result.data),
  restoreAgentImageVersion: (
    conversationId: string,
    taskId: string,
    panelId: string,
    imageId: string,
  ) =>
    request<ApiData<AgentTaskInspectorImage>>(
      `/agent/conversations/${encodeURIComponent(conversationId)}/tasks/${encodeURIComponent(taskId)}/panels/${encodeURIComponent(panelId)}/versions/${encodeURIComponent(imageId)}/restore`,
      { method: "POST" },
    ).then((result) => result.data),
  pauseAgentRun: (runId: string) =>
    request<ApiData<AgentRun>>(`/agent/runs/${encodeURIComponent(runId)}/pause`, {
      method: "POST",
    }).then((result) => result.data),
  resumeAgentRun: (runId: string) =>
    request<ApiData<AgentRun>>(`/agent/runs/${encodeURIComponent(runId)}/resume`, {
      method: "POST",
    }).then((result) => result.data),
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
  extractStylePromptFromFiles: (files: File[]) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    return request<ApiData<StylePromptExtraction>>("/styles/style-prompt/extract", {
      method: "POST",
      body: form,
    }).then((result) => result.data);
  },
  extractStylePromptFromStyle: (styleId: string) =>
    request<ApiData<StylePromptExtraction>>(`/styles/${styleId}/style-prompt/extract`, {
      method: "POST",
    }).then((result) => result.data),
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
  styleTests: (styleId: string, params?: { limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<ApiList<StyleTest>>(`/styles/${styleId}/tests${suffix}`);
  },
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
    speech_speed: number;
    file: File;
  }) => {
    const form = new FormData();
    form.append("name", payload.name);
    form.append("description", payload.description ?? "");
    form.append("reference_text", payload.reference_text ?? "");
    form.append("speech_speed", String(payload.speech_speed));
    form.append("file", payload.file);
    return request<ApiData<AudioReference>>("/audio-references", { method: "POST", body: form }).then((result) => result.data);
  },
  updateAudioReference: (id: string, payload: { name: string; description?: string | null; speech_speed: number }) =>
    request<ApiData<AudioReference>>(`/audio-references/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }).then((result) => result.data),
  testAudioReference: (id: string, payload: { text: string }) =>
    requestBlob(`/audio-references/${id}/test`, { method: "POST", body: JSON.stringify(payload) }),
  transcribeAudioReference: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ApiData<AudioReferenceTranscription>>("/audio-references/transcribe", {
      method: "POST",
      body: form,
    }).then((result) => result.data);
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
  retryVideoTask: (id: string) =>
    request<ApiData<VideoTask>>(`/video-tasks/${id}/retry`, { method: "POST" }).then((result) => result.data),
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
    remove_image_text?: boolean;
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
    remove_image_text?: boolean;
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

export function agentEventStreamUrl(conversationId: string, after?: string | null) {
  const query = after ? `?after=${encodeURIComponent(after)}` : "";
  return `${API_BASE_URL}/api/v1/agent/conversations/${encodeURIComponent(conversationId)}/events${query}`;
}

export function nativeAgentRunEventStreamUrl(runId: string) {
  return `${API_BASE_URL}/api/v1/agent-loop/runs/${encodeURIComponent(runId)}/events`;
}
