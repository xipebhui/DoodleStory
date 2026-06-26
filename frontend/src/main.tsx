import { StrictMode, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertCircle,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Coins,
  Download,
  Eye,
  Film,
  FileText,
  Filter,
  Images,
  LogOut,
  Loader2,
  MessageCircle,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Search,
  Settings,
  Sparkles,
  Ticket,
  Trash2,
  Upload,
  UserRound,
  Users,
  Volume2,
  X,
} from "lucide-react";
import {
  API_BASE_URL,
  api,
  type ActivationCode,
  type ActivationCodeCreated,
  type AdminCreditTransaction,
  type AdminCreditUsage,
  type AdminUserCreditDetail,
  type AdminUserCreditSummary,
  type AudioReference,
  type ContentExtraction,
  type ContentExtractionHealth,
  type ContentExtractionMedia,
  type ContentExtractionSummary,
  type CreditOverview,
  type CreditTransaction,
  type CreditTransactionFilter,
  type CreditUsagePoint,
  type FileAsset,
  type Style,
  type StyleOption,
  type StyleSelectOption,
  type StyleTest,
  type StoryCharacterBinding,
  type Task,
  type TaskPanelDebug,
  type TaskSummary,
  type User,
  type UserCharacter,
  type VideoTask,
  type VideoTaskStatus,
  type VideoTaskSummary,
} from "./api/client";
import "./styles/app.css";

type View = "tasks" | "videoTasks" | "audioReferences" | "content" | "styles" | "characters" | "users" | "creditUsage" | "settings";
const TASK_ROW_IMAGE_PREVIEW_LIMIT = 4;
const CONTACT_WECHAT_QR_SRC = "/wechat-contact-qr.png";
const aspectRatioOptions = ["1:1", "3:4", "4:3", "9:16", "16:9"];
const imageModelNamePlaceholder = "生图模型名，例如 gpt-image-2";
const styleReferenceModeLabels: Record<Style["style_reference_mode"], string> = {
  prompt: "Prompt 参考",
  image: "参考图参考",
};
const viewRoutes: Record<View, string> = {
  tasks: "/tasks",
  videoTasks: "/video-tasks",
  audioReferences: "/audio-references",
  content: "/content-extractions",
  styles: "/styles",
  characters: "/characters",
  users: "/users",
  creditUsage: "/credit-usage",
  settings: "/settings",
};

function normalizedPathname(pathname: string) {
  return pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
}

function viewFromPathname(pathname: string): View | null {
  const path = normalizedPathname(pathname);
  if (path === "/" || path === viewRoutes.tasks || path.startsWith(`${viewRoutes.tasks}/`)) return "tasks";
  if (path === viewRoutes.videoTasks || path.startsWith(`${viewRoutes.videoTasks}/`)) return "videoTasks";
  if (path === viewRoutes.audioReferences) return "audioReferences";
  if (path === viewRoutes.content) return "content";
  if (path === viewRoutes.styles) return "styles";
  if (path === viewRoutes.characters) return "characters";
  if (path === viewRoutes.users) return "users";
  if (path === viewRoutes.creditUsage) return "creditUsage";
  if (path === viewRoutes.settings) return "settings";
  return null;
}

function taskIdFromPathname(pathname: string): string | null {
  const path = normalizedPathname(pathname);
  const prefix = `${viewRoutes.tasks}/`;
  if (!path.startsWith(prefix)) return null;
  const rawTaskId = path.slice(prefix.length).split("/")[0];
  return rawTaskId ? decodeURIComponent(rawTaskId) : null;
}

function videoTaskIdFromPathname(pathname: string): string | null {
  const path = normalizedPathname(pathname);
  const prefix = `${viewRoutes.videoTasks}/`;
  if (!path.startsWith(prefix)) return null;
  const rawTaskId = path.slice(prefix.length).split("/")[0];
  return rawTaskId ? decodeURIComponent(rawTaskId) : null;
}

type ImageTextPayload = {
  title?: string | null;
  narration?: string | null;
  dialogue?: string | null;
  inner_os?: string | null;
  emphasis?: string | null;
};

const CONTENT_EXTRACTION_TASK_DRAFT_KEY = "doodlestory.contentExtractionTaskDraft";
const DOUYIN_SHARE_URL_PATTERN =
  /https?:\/\/(?:v\.douyin\.com\/[A-Za-z0-9_.~%-]+\/?|www\.douyin\.com\/(?:video|note)\/[A-Za-z0-9_.~%-]+(?:\?[^\s，,。！!？?；;]*)?)/;
type CreateInputMode = Task["story_input_mode"] | "dy_replicate";
type CharacterCreateTarget = { sourceName: string; allowMerge: boolean } | null;
type ManualRoleTarget = { allowMerge: boolean } | null;

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function containsDouyinShareUrl(value: string) {
  return DOUYIN_SHARE_URL_PATTERN.test(value);
}

function parseImageText(value: string | null | undefined): ImageTextPayload | null {
  if (!value) return null;
  try {
    const parsed = JSON.parse(value) as ImageTextPayload;
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

function imageTextSummary(value: string | null | undefined) {
  const parsed = parseImageText(value);
  if (!parsed) return "";
  return [
    parsed.title ? `标题：${parsed.title}` : "",
    parsed.narration ? `旁白：${parsed.narration}` : "",
    parsed.dialogue ? `对白：${parsed.dialogue}` : "",
    parsed.inner_os ? `内心OS：${parsed.inner_os}` : "",
    parsed.emphasis ? `强调：${parsed.emphasis}` : "",
  ]
    .filter(Boolean)
    .join(" / ");
}

function LazyAssetImage({
  asset,
  assetId,
  alt,
  className,
  eager = false,
  variant = "thumbnail",
}: {
  asset?: FileAsset | null;
  assetId: string;
  alt: string;
  className?: string;
  eager?: boolean;
  variant?: "original" | "thumbnail";
}) {
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [shouldLoad, setShouldLoad] = useState(eager);
  const [loadState, setLoadState] = useState<"idle" | "loading" | "loaded" | "error">(eager ? "loading" : "idle");
  const resolvedSrc = asset ? assetUrl(asset, variant) : api.assetContentUrl(assetId, "original");

  useEffect(() => {
    if (eager) {
      setShouldLoad(true);
      return;
    }

    setShouldLoad(false);
    const image = imageRef.current;
    if (!image) return;
    if (!("IntersectionObserver" in window)) {
      setShouldLoad(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setShouldLoad(true);
          observer.disconnect();
        }
      },
      { rootMargin: "160px 0px" },
    );
    observer.observe(image);
    return () => observer.disconnect();
  }, [assetId, eager]);

  useEffect(() => {
    setLoadState(shouldLoad ? "loading" : "idle");
  }, [resolvedSrc, shouldLoad]);

  return (
    <img
      key={shouldLoad ? resolvedSrc : `${assetId}-${variant}-pending`}
      ref={imageRef}
      className={["lazy-asset-image", `is-${loadState}`, className].filter(Boolean).join(" ")}
      src={shouldLoad ? resolvedSrc : undefined}
      alt={alt}
      loading={eager ? "eager" : "lazy"}
      decoding="async"
      onLoad={() => setLoadState("loaded")}
      onError={() => setLoadState("error")}
    />
  );
}

function absoluteAssetUrl(value: string): string {
  if (value.startsWith("http://") || value.startsWith("https://") || value.startsWith("data:")) {
    return value;
  }
  return `${API_BASE_URL}${value.startsWith("/") ? "" : "/"}${value}`;
}

function assetUrl(asset: FileAsset, variant: "original" | "thumbnail" = "original"): string {
  void variant;
  const value = asset.content_url || asset.thumbnail_url;
  return absoluteAssetUrl(value || api.assetContentUrl(asset.id, "original"));
}

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [creditOverview, setCreditOverview] = useState<CreditOverview | null>(null);
  const [creditError, setCreditError] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [pathname, setPathname] = useState(() => window.location.pathname);
  const [loading, setLoading] = useState(true);
  const view = viewFromPathname(pathname);
  const routeTaskId = taskIdFromPathname(pathname);
  const routeVideoTaskId = videoTaskIdFromPathname(pathname);

  useEffect(() => {
    api
      .me()
      .then((result) => setUser(result.user))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  async function refreshCredits() {
    if (!user) return null;
    try {
      const overview = await api.myCredits();
      setCreditOverview(overview);
      setCreditError("");
      return overview;
    } catch (error) {
      setCreditError(error instanceof Error ? error.message : "积分加载失败");
      return null;
    }
  }

  useEffect(() => {
    if (!user) {
      setCreditOverview(null);
      setCreditError("");
      return;
    }
    void refreshCredits();
    const timer = window.setInterval(() => {
      void refreshCredits();
    }, 12000);
    return () => window.clearInterval(timer);
  }, [user?.id]);

  useEffect(() => {
    function handlePopState() {
      setPathname(window.location.pathname);
    }
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    if (!loading && user && normalizedPathname(pathname) === "/") {
      window.history.replaceState(null, "", viewRoutes.tasks);
      setPathname(viewRoutes.tasks);
    }
  }, [loading, pathname, user]);

  function navigateToPath(nextPath: string, options: { replace?: boolean } = {}) {
    if (normalizedPathname(window.location.pathname) !== nextPath) {
      if (options.replace) {
        window.history.replaceState(null, "", nextPath);
      } else {
        window.history.pushState(null, "", nextPath);
      }
    }
    setPathname(nextPath);
  }

  function navigateToView(nextView: View) {
    navigateToPath(viewRoutes[nextView]);
  }

  if (loading) {
    return <div className="center">加载中</div>;
  }

  if (!user) {
    return (
      <AuthScreen
        mode={authMode}
        setMode={setAuthMode}
        onAuthed={(nextUser) => {
          setUser(nextUser);
          setCreditOverview(null);
        }}
      />
    );
  }

  if (!view) {
    return (
      <Shell
        user={user}
        view={null}
        creditOverview={creditOverview}
        creditError={creditError}
        onNavigate={navigateToView}
        onLogout={() => setUser(null)}
      >
        <NotFoundView />
      </Shell>
    );
  }

  return (
    <Shell
      user={user}
      view={view}
      creditOverview={creditOverview}
      creditError={creditError}
      onNavigate={navigateToView}
      onLogout={() => setUser(null)}
    >
      {view === "tasks" ? <TasksView user={user} routeTaskId={routeTaskId} onNavigatePath={navigateToPath} /> : null}
      {view === "videoTasks" ? <VideoTasksView user={user} routeVideoTaskId={routeVideoTaskId} onNavigatePath={navigateToPath} /> : null}
      {view === "audioReferences" ? <AudioReferencesView user={user} /> : null}
      {view === "content" ? <ContentExtractionView user={user} onNavigatePath={navigateToPath} /> : null}
      {view === "styles" ? <StylesView user={user} onCreditsChanged={refreshCredits} /> : null}
      {view === "characters" ? <CharactersView /> : null}
      {view === "users" ? <UsersView user={user} onCreditsChanged={refreshCredits} /> : null}
      {view === "creditUsage" ? <AdminCreditUsageView user={user} /> : null}
      {view === "settings" ? (
        <SettingsView
          user={user}
          creditOverview={creditOverview}
          onCreditsChanged={(overview) => {
            if (overview) {
              setCreditOverview(overview);
              setCreditError("");
            } else {
              void refreshCredits();
            }
          }}
          onLogout={() => setUser(null)}
        />
      ) : null}
    </Shell>
  );
}

function AuthScreen({
  mode,
  setMode,
  onAuthed,
}: {
  mode: "login" | "register";
  setMode: (mode: "login" | "register") => void;
  onAuthed: (user: User) => void;
}) {
  const [message, setMessage] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const email = String(formData.get("email") ?? "");
    const password = String(formData.get("password") ?? "");
    const display_name = String(formData.get("display_name") ?? "");

    try {
      const result =
        mode === "login"
          ? await api.login({ email, password })
          : await api.register({ email, password, display_name });
      onAuthed(result.user);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "请求失败");
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="brand">
          <span className="brand-mark">
            <img className="brand-icon" src="/doodlestory-icon.svg" alt="" />
          </span>
          <div>
            <strong>DoodleStory</strong>
            <span>故事生图工作台</span>
          </div>
        </div>
        <h1>{mode === "login" ? "登录" : "创建账号"}</h1>
        <form onSubmit={submit} className="form">
          {mode === "register" ? <input name="display_name" placeholder="昵称" /> : null}
          <input name="email" type="email" placeholder="邮箱" autoComplete="email" required />
          <input
            name="password"
            type="password"
            placeholder="密码"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
            minLength={8}
          />
          {message ? <p className="error">{message}</p> : null}
          <button type="submit">{mode === "login" ? "登录" : "注册"}</button>
        </form>
        <button className="link-button" onClick={() => setMode(mode === "login" ? "register" : "login")}>
          {mode === "login" ? "还没有账号，去注册" : "已有账号，去登录"}
        </button>
      </section>
    </main>
  );
}

function Shell({
  user,
  view,
  creditOverview,
  creditError,
  onNavigate,
  onLogout,
  children,
}: {
  user: User;
  view: View | null;
  creditOverview: CreditOverview | null;
  creditError: string;
  onNavigate: (view: View) => void;
  onLogout: () => void;
  children: React.ReactNode;
}) {
  const items = [
    { key: "tasks" as const, label: "任务", icon: Images, path: viewRoutes.tasks },
    { key: "videoTasks" as const, label: "视频任务", icon: Film, path: viewRoutes.videoTasks },
    { key: "audioReferences" as const, label: "音频管理", icon: Volume2, path: viewRoutes.audioReferences },
    { key: "content" as const, label: "内容提取", icon: FileText, path: viewRoutes.content },
    { key: "styles" as const, label: "风格", icon: Sparkles, path: viewRoutes.styles },
    { key: "characters" as const, label: "角色管理", icon: UserRound, path: viewRoutes.characters },
    ...(user.role === "admin" ? [{ key: "users" as const, label: "用户管理", icon: Users, path: viewRoutes.users }] : []),
    ...(user.role === "admin" ? [{ key: "creditUsage" as const, label: "积分消耗", icon: BarChart3, path: viewRoutes.creditUsage }] : []),
    { key: "settings" as const, label: "设置", icon: Settings, path: viewRoutes.settings },
  ];

  async function logout() {
    await api.logout();
    onLogout();
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <img className="brand-icon" src="/doodlestory-icon.svg" alt="" />
          </span>
	          <div>
	            <strong>DoodleStory</strong>
	            <span>故事漫画生成</span>
	          </div>
        </div>
        <nav>
          {items.map((item) => (
            <a
              key={item.key}
              className={view === item.key ? "active" : ""}
              href={item.path}
              onClick={(event) => {
                event.preventDefault();
                onNavigate(item.key);
              }}
            >
              <item.icon size={18} />
              {item.label}
            </a>
          ))}
        </nav>
        <div className="user-box">
          <div className="sidebar-credit">
            <Coins size={18} />
            <div>
              <strong>{creditOverview ? `${creditOverview.account.balance} 积分` : creditError ? "积分不可用" : "积分加载中"}</strong>
              <span>
                {creditOverview
                  ? creditOverview.account.reserved_balance > 0
                    ? `占用 ${creditOverview.account.reserved_balance}`
                    : "成功出图扣 1 分"
                  : creditError || "正在读取余额"}
              </span>
            </div>
          </div>
          <strong>{user.display_name || user.email}</strong>
          <span>{user.role === "admin" ? "管理员" : "普通用户"}</span>
          <div className="contact-hover">
            <button type="button" className="contact-hover-trigger" aria-label="联系我们">
              <MessageCircle size={17} />
              联系微信
            </button>
            <div className="contact-hover-popover" role="tooltip">
              <strong>使用微信扫一扫</strong>
              <img src={CONTACT_WECHAT_QR_SRC} alt="微信二维码" />
            </div>
          </div>
          <button onClick={logout}>
            <LogOut size={16} />
            退出
          </button>
        </div>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}

function NotFoundView() {
  return (
    <section className="page">
      <header className="page-header">
        <div>
          <h1>页面不存在</h1>
          <p>这个地址没有对应的 DoodleStory 工作台页面。</p>
        </div>
      </header>
      <div className="empty">请从左侧导航进入任务、内容提取、风格或设置页面。</div>
    </section>
  );
}

const taskStatusOptions: Array<{ value: Task["status"] | "all"; label: string }> = [
  { value: "all", label: "全部状态" },
  { value: "queued", label: "排队中" },
  { value: "running", label: "生成中" },
  { value: "succeeded", label: "已完成" },
  { value: "partial_succeeded", label: "部分完成" },
  { value: "failed", label: "失败" },
  { value: "cancel_requested", label: "取消中" },
  { value: "cancelled", label: "已取消" },
  { value: "retrying", label: "重试中" },
];

const stepLabels: Record<string, string> = {
  adapt_story: "分镜规划",
  segment_story: "故事切分",
  extract_characters: "人物识别",
  generate_character_references: "人物参考图",
  generate_panel_prompts: "画面提示词",
  generate_images: "图片生成",
  package_download: "下载打包",
};

function taskStatusLabel(status: Task["status"]) {
  return taskStatusOptions.find((item) => item.value === status)?.label ?? status;
}

const videoTaskStatusOptions: Array<{ value: VideoTaskStatus | "all"; label: string }> = [
  { value: "all", label: "全部状态" },
  { value: "waiting_for_images", label: "等待图片" },
  { value: "ready_for_audio", label: "待生成音频" },
  { value: "audio_generating", label: "音频生成中" },
  { value: "audio_ready", label: "音频已就绪" },
  { value: "video_generating", label: "视频生成中" },
  { value: "succeeded", label: "已完成" },
  { value: "failed", label: "失败" },
  { value: "cancel_requested", label: "取消中" },
  { value: "cancelled", label: "已取消" },
];

function videoTaskStatusLabel(status: VideoTaskStatus) {
  return videoTaskStatusOptions.find((item) => item.value === status)?.label ?? status;
}

function videoTaskStepLabel(step: VideoTask["current_step"]) {
  const labels: Record<VideoTask["current_step"], string> = {
    generate_source_images: "生成上游图片",
    generate_narration_audio: "生成旁白音频",
    submit_video: "提交图文视频",
    download_video: "保存视频资产",
  };
  return labels[step] ?? step;
}

function storyInputModeLabel(mode: Task["story_input_mode"]) {
  if (mode === "adapted") return "故事方案";
  if (mode === "extracted_storyboard") return "提取分镜";
  return "完整故事";
}

function visibleTaskSteps(task: Task) {
  if (task.story_input_mode !== "extracted_storyboard") return task.steps;
  return task.steps.filter((step) => !["segment_story", "generate_panel_prompts"].includes(step.step_name));
}

function currentStepLabel(task: Task) {
  if (
    task.story_input_mode === "extracted_storyboard" &&
    task.current_step &&
    ["segment_story", "generate_panel_prompts"].includes(task.current_step)
  ) {
    return "分镜规划";
  }
  return task.current_step ? stepLabels[task.current_step] ?? task.current_step : "等待任务";
}

function imageStatusLabel(status: string) {
  const labels: Record<string, string> = {
    queued: "排队中",
    running: "生成中",
    succeeded: "已生成",
    failed: "失败",
    cancelled: "已取消",
  };
  return labels[status] ?? status;
}

function imageSourceLabel(source: string) {
  const labels: Record<string, string> = {
    initial: "初始生成",
    user_edit: "用户修改",
    retry: "任务重试",
  };
  return labels[source] ?? source;
}

function imageWorkflowLabel(step: string | null) {
  const labels: Record<string, string> = {
    rewrite_prompt: "LLM 改写提示词",
    generate_image: "图片生成",
  };
  return step ? labels[step] ?? step : "等待处理";
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "暂无";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function isActiveTask(task: Task | TaskSummary | null | undefined) {
  return Boolean(task && ["queued", "running", "retrying", "cancel_requested"].includes(task.status));
}

function hasActivePanelEdit(task: Task | null | undefined) {
  return Boolean(
    task?.generated_images.some(
      (image) => image.source_type === "user_edit" && (image.status === "queued" || image.status === "running"),
    ),
  );
}

function taskProgress(task: Task | TaskSummary) {
  if (task.progress_total <= 0) return 0;
  return Math.min(100, Math.round((task.progress_current / task.progress_total) * 100));
}

function sortedPanels(task: Task | null | undefined) {
  return [...(task?.panels ?? [])].sort((a, b) => a.panel_order - b.panel_order);
}

function imagesByPanel(task: Task | null | undefined) {
  const map = new Map<string, Task["generated_images"][number]>();
  const groups = new Map<string, Task["generated_images"]>();
  const canShowActiveImages = isActiveTask(task);
  task?.generated_images.forEach((image) => {
    groups.set(image.panel_id, [...(groups.get(image.panel_id) ?? []), image]);
  });
  groups.forEach((images, panelId) => {
    const active = images
      .filter(
        (image) =>
          (image.status === "queued" || image.status === "running") &&
          (canShowActiveImages || image.source_type === "user_edit"),
      )
      .sort((a, b) => b.generation_number - a.generation_number)[0];
    const current = images
      .filter((image) => image.is_current)
      .sort((a, b) => b.generation_number - a.generation_number)[0];
    const latest = [...images].sort((a, b) => b.generation_number - a.generation_number)[0];
    if (active || current || latest) {
      map.set(panelId, active ?? current ?? latest);
    }
  });
  return map;
}

function succeededImages(task: Task | null | undefined) {
  const panelMap = new Map(sortedPanels(task).map((panel) => [panel.id, panel.panel_order]));
  return [...(task?.generated_images ?? [])]
    .filter((image) => image.is_current && image.status === "succeeded" && image.asset)
    .sort((a, b) => (panelMap.get(a.panel_id) ?? 0) - (panelMap.get(b.panel_id) ?? 0));
}

function hasAllPanelImages(task: Task | null | undefined) {
  const panelCount = sortedPanels(task).length;
  return Boolean(task && task.status === "succeeded" && panelCount > 0 && succeededImages(task).length === panelCount);
}

function panelImageVersions(task: Task | null | undefined, panelId: string) {
  return [...(task?.generated_images ?? [])]
    .filter((image) => image.panel_id === panelId)
    .sort((a, b) => b.generation_number - a.generation_number);
}

function shortId(value: string) {
  return value.slice(0, 8);
}

function stylePreviewAssets(style: Style | StyleOption) {
  if ("preview_asset" in style) {
    return style.preview_asset ? [style.preview_asset] : [];
  }
  const assets = style.reference_images.map((reference) => reference.asset);
  if (style.cover_asset && !assets.some((asset) => asset.id === style.cover_asset?.id)) {
    return [style.cover_asset, ...assets];
  }
  return assets;
}

function styleCover(style: Style | StyleOption) {
  if ("preview_asset" in style) return style.preview_asset;
  return style.cover_asset ?? style.reference_images[0]?.asset ?? null;
}

function TasksView({
  user,
  routeTaskId,
  onNavigatePath,
}: {
  user: User;
  routeTaskId: string | null;
  onNavigatePath: (path: string, options?: { replace?: boolean }) => void;
}) {
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [styleFilterOptions, setStyleFilterOptions] = useState<StyleSelectOption[]>([]);
  const [createStyles, setCreateStyles] = useState<StyleOption[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<Task["status"] | "all">("all");
  const [styleFilter, setStyleFilter] = useState("");
  const [taskUserFilter, setTaskUserFilter] = useState("");
  const [taskUserOptions, setTaskUserOptions] = useState<AdminUserCreditSummary[]>([]);
  const [loadingTaskUsers, setLoadingTaskUsers] = useState(false);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const [pageInfo, setPageInfo] = useState<{ next_cursor: string | null; has_more: boolean } | null>(null);
  const [loadingTasks, setLoadingTasks] = useState(true);
  const [loadingStyleFilterOptions, setLoadingStyleFilterOptions] = useState(false);
  const [loadingCreateStyles, setLoadingCreateStyles] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [stylePickerOpen, setStylePickerOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createStyleId, setCreateStyleId] = useState("");
  const [countMode, setCountMode] = useState<"auto" | "fixed">("auto");
  const [lastPanelRealPhoto, setLastPanelRealPhoto] = useState(false);
  const [storyInputMode, setStoryInputMode] = useState<CreateInputMode>("original");
  const [createOriginalText, setCreateOriginalText] = useState("");
  const [userCharacters, setUserCharacters] = useState<UserCharacter[]>([]);
  const [loadingCharacters, setLoadingCharacters] = useState(false);
  const [fixedRoleFlowEnabled, setFixedRoleFlowEnabled] = useState(false);
  const [characterExtractionCompletedForText, setCharacterExtractionCompletedForText] = useState("");
  const [extractedCharacterNames, setExtractedCharacterNames] = useState<string[]>([]);
  const [manualCharacterNames, setManualCharacterNames] = useState<string[]>([]);
  const [createCharacterBindings, setCreateCharacterBindings] = useState<Record<string, string>>({});
  const [extractingCharacters, setExtractingCharacters] = useState(false);
  const [characterPickTarget, setCharacterPickTarget] = useState<string | null>(null);
  const [manualRoleTarget, setManualRoleTarget] = useState<ManualRoleTarget>(null);
  const [characterCreateTarget, setCharacterCreateTarget] = useState<CharacterCreateTarget>(null);
  const [creatingCharacter, setCreatingCharacter] = useState(false);
  const [quickCharacterPreviewUrl, setQuickCharacterPreviewUrl] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [previewImageId, setPreviewImageId] = useState<string | null>(null);
  const [previewReferenceId, setPreviewReferenceId] = useState<string | null>(null);
  const [promptPreview, setPromptPreview] = useState<{ title: string; text: string } | null>(null);
  const [panelEditInputs, setPanelEditInputs] = useState<Record<string, string>>({});
  const [editingPanelId, setEditingPanelId] = useState<string | null>(null);
  const [panelDebugById, setPanelDebugById] = useState<Record<string, TaskPanelDebug>>({});
  const [panelDebugError, setPanelDebugError] = useState<Record<string, string>>({});
  const [loadingPanelDebugId, setLoadingPanelDebugId] = useState<string | null>(null);
  const [downloadingTaskId, setDownloadingTaskId] = useState<string | null>(null);
  const previewCloseRef = useRef<HTMLButtonElement | null>(null);

  const taskForDetail = selectedTask;
  const taskStepsForDetail = useMemo(() => (taskForDetail ? visibleTaskSteps(taskForDetail) : []), [taskForDetail]);
  const panelImageMap = useMemo(() => imagesByPanel(taskForDetail), [taskForDetail]);
  const previewItems = useMemo(() => succeededImages(taskForDetail), [taskForDetail]);
  const previewIndex = previewItems.findIndex((image) => image.id === previewImageId);
  const previewImage = previewIndex >= 0 ? previewItems[previewIndex] : null;
  const previewPanel = previewImage ? taskForDetail?.panels.find((panel) => panel.id === previewImage.panel_id) : null;
  const previewPanelDebug = previewImage ? panelDebugById[previewImage.panel_id] : undefined;
  const previewImageDebug = previewImage ? previewPanelDebug?.images.find((image) => image.id === previewImage.id) : undefined;
  const previewPromptText = previewImageDebug?.final_prompt ?? previewImageDebug?.image_prompt ?? "";
  const referencePreviewItems = taskForDetail?.character_references ?? [];
  const referencePreviewIndex = referencePreviewItems.findIndex((reference) => reference.id === previewReferenceId);
  const previewReference = referencePreviewIndex >= 0 ? referencePreviewItems[referencePreviewIndex] : null;
  const activeTaskSignature = tasks.map((task) => `${task.id}:${task.status}:${task.updated_at}`).join("|");
  const selectedImageSignature =
    selectedTask?.generated_images
      .map((image) =>
        [
          image.id,
          image.status,
          image.workflow_step ?? "",
          image.is_current ? "1" : "0",
          image.generation_number,
          image.updated_at,
        ].join(":"),
      )
      .join("|") ?? "";
  const createStylePreviewLimit = 3;
  const visibleCreateStyles = useMemo(() => {
    const previewStyles = createStyles.slice(0, createStylePreviewLimit);
    if (!createStyleId || previewStyles.some((style) => style.id === createStyleId)) {
      return previewStyles;
    }
    const selectedStyle = createStyles.find((style) => style.id === createStyleId);
    return selectedStyle ? [...previewStyles.slice(0, createStylePreviewLimit - 1), selectedStyle] : previewStyles;
  }, [createStyles, createStyleId]);
  const canExpandCreateStyles = createStyles.length > 0;
  const createRoleNames = useMemo(() => {
    const names: string[] = [];
    for (const name of [...extractedCharacterNames, ...manualCharacterNames]) {
      const cleaned = name.trim();
      if (cleaned && !names.includes(cleaned)) names.push(cleaned);
    }
    return names;
  }, [extractedCharacterNames, manualCharacterNames]);
  const boundRoleCount = createRoleNames.filter((name) => createCharacterBindings[name]).length;
  const createTextForCharacterExtraction = createOriginalText.trim();
  const fixedRoleExtractionReady =
    fixedRoleFlowEnabled &&
    Boolean(createTextForCharacterExtraction) &&
    characterExtractionCompletedForText === createTextForCharacterExtraction;
  const hasTaskFilters = Boolean(query || statusFilter !== "all" || styleFilter || (user.role === "admin" && taskUserFilter));

  useEffect(() => {
    refresh(undefined, { quiet: false });
  }, [query, statusFilter, styleFilter, taskUserFilter, cursor]);

  useEffect(() => {
    void refreshStyleFilterOptions();
  }, []);

  useEffect(() => {
    if (!createOpen) return;
    void refreshCreateStyles();
  }, [createOpen]);

  useEffect(() => {
    if (user.role !== "admin") {
      setTaskUserOptions([]);
      setTaskUserFilter("");
      return;
    }
    let cancelled = false;
    async function loadTaskUsers() {
      try {
        setLoadingTaskUsers(true);
        const result = await api.adminUsers({ limit: 100 });
        if (!cancelled) setTaskUserOptions(result.items);
      } catch (error) {
        if (!cancelled) setMessage(error instanceof Error ? error.message : "用户列表加载失败");
      } finally {
        if (!cancelled) setLoadingTaskUsers(false);
      }
    }
    void loadTaskUsers();
    return () => {
      cancelled = true;
    };
  }, [user.role]);

  useEffect(() => {
    if (!createOpen) return;
    let cancelled = false;
    async function loadCharacters() {
      try {
        setLoadingCharacters(true);
        const result = await api.characters({ limit: 80 });
        if (!cancelled) setUserCharacters(result.items);
      } catch (error) {
        if (!cancelled) setMessage(error instanceof Error ? error.message : "角色列表加载失败");
      } finally {
        if (!cancelled) setLoadingCharacters(false);
      }
    }
    void loadCharacters();
    return () => {
      cancelled = true;
    };
  }, [createOpen]);

  useEffect(() => {
    setExtractedCharacterNames([]);
    setManualCharacterNames([]);
    setCreateCharacterBindings({});
  }, [storyInputMode]);

  useEffect(() => {
    if (!quickCharacterPreviewUrl) return;
    return () => URL.revokeObjectURL(quickCharacterPreviewUrl);
  }, [quickCharacterPreviewUrl]);

  useEffect(() => {
    let cancelled = false;

    async function loadRouteTask(taskId: string) {
      setSelectedId(taskId);
      setDetailOpen(true);
      setSelectedTask(null);
      setPreviewImageId(null);
      setPreviewReferenceId(null);
      setPromptPreview(null);
      setPanelDebugById({});
      setPanelDebugError({});
      setLoadingPanelDebugId(null);
      try {
        const task = await api.task(taskId);
        if (cancelled) return;
        setSelectedTask(task);
        setError("");
      } catch (err) {
        if (cancelled) return;
        setSelectedTask(null);
        setError(err instanceof Error ? err.message : "任务详情加载失败");
      }
    }

    if (!routeTaskId) {
      setDetailOpen(false);
      setSelectedId("");
      setSelectedTask(null);
      setPreviewImageId(null);
      setPreviewReferenceId(null);
      setPromptPreview(null);
      setPanelDebugById({});
      setPanelDebugError({});
      setLoadingPanelDebugId(null);
      return () => {
        cancelled = true;
      };
    }

    loadRouteTask(routeTaskId);
    return () => {
      cancelled = true;
    };
  }, [routeTaskId]);

  useEffect(() => {
    if (!isActiveTask(selectedTask) && !hasActivePanelEdit(selectedTask) && !tasks.some(isActiveTask)) return;
    const timer = window.setInterval(() => refresh(selectedId, { quiet: true }), 6000);
    return () => window.clearInterval(timer);
  }, [activeTaskSignature, selectedId, selectedTask?.status, selectedTask?.updated_at, selectedImageSignature]);

  useEffect(() => {
    if (!previewImageId) return;
    previewCloseRef.current?.focus();
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setPreviewImageId(null);
      }
      if (event.key === "ArrowLeft") {
        showPreviewOffset(-1);
      }
      if (event.key === "ArrowRight") {
        showPreviewOffset(1);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [previewImageId, previewItems]);

  useEffect(() => {
    if (!previewReferenceId) return;
    previewCloseRef.current?.focus();
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setPreviewReferenceId(null);
      }
      if (event.key === "ArrowLeft") {
        showReferencePreviewOffset(-1);
      }
      if (event.key === "ArrowRight") {
        showReferencePreviewOffset(1);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [previewReferenceId, referencePreviewItems]);

  useEffect(() => {
    if (!promptPreview) return;
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setPromptPreview(null);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [promptPreview]);

  useEffect(() => {
    if (!detailOpen) return;
    function handleKey(event: KeyboardEvent) {
	      if (event.key === "Escape" && !previewImageId && !previewReferenceId && !promptPreview) {
	        closeTaskDetail();
	      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [detailOpen, previewImageId, previewReferenceId, promptPreview]);

  useEffect(() => {
    if (createOpen && !createStyleId && createStyles[0]) {
      setCreateStyleId(createStyles[0].id);
    }
  }, [createOpen, createStyleId, createStyles]);

  useEffect(() => {
    const rawDraft = window.sessionStorage.getItem(CONTENT_EXTRACTION_TASK_DRAFT_KEY);
    if (!rawDraft) return;
    window.sessionStorage.removeItem(CONTENT_EXTRACTION_TASK_DRAFT_KEY);
    try {
      const draft = JSON.parse(rawDraft) as { original_text?: string };
      if (draft.original_text?.trim()) {
        setCreateOriginalText(draft.original_text);
        setStoryInputMode("extracted_storyboard");
        setCountMode("auto");
        setCreateOpen(true);
        setMessage("已从内容提取带入提取分镜任务");
      }
    } catch {
      setMessage("内容提取任务草稿读取失败");
    }
  }, []);

  useEffect(() => {
    if (!createOpen) return;
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        if (stylePickerOpen) {
          setStylePickerOpen(false);
          return;
        }
        setCreateOpen(false);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [createOpen, stylePickerOpen]);

  async function refresh(preferredTaskId = selectedId, options: { quiet?: boolean } = {}) {
    try {
      if (options.quiet) {
        setRefreshing(true);
      } else {
        setLoadingTasks(true);
      }
      const taskResult = await api.tasks({
        query,
        status: statusFilter,
        style_id: styleFilter,
        user_id: user.role === "admin" ? taskUserFilter || null : null,
        cursor,
        limit: 10,
      });
      setTasks(taskResult.items);
      setPageInfo(taskResult.page);
      setError("");
      const nextSelectedId = preferredTaskId || routeTaskId || selectedId;
      if (nextSelectedId && (detailOpen || routeTaskId)) {
        setSelectedId(nextSelectedId);
        setSelectedTask(await api.task(nextSelectedId));
      } else {
        setSelectedId(nextSelectedId);
        setSelectedTask(null);
      }
      setLastRefreshedAt(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoadingTasks(false);
      setRefreshing(false);
    }
  }

  async function refreshStyleFilterOptions() {
    try {
      setLoadingStyleFilterOptions(true);
      const styleResult = await api.styleSelectOptions({ status: "active", limit: 100 });
      setStyleFilterOptions(styleResult.items);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "风格列表加载失败");
    } finally {
      setLoadingStyleFilterOptions(false);
    }
  }

  async function refreshCreateStyles() {
    try {
      setLoadingCreateStyles(true);
      const styleResult = await api.styleOptions({ status: "active", limit: 100 });
      setCreateStyles(styleResult.items);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "风格列表加载失败");
    } finally {
      setLoadingCreateStyles(false);
    }
  }

  async function loadPanelDebug(panelId: string): Promise<TaskPanelDebug | null> {
    if (!taskForDetail) return null;
    if (panelDebugById[panelId]) return panelDebugById[panelId];
    try {
      setLoadingPanelDebugId(panelId);
      const debug = await api.taskPanelDebug(taskForDetail.id, panelId);
      setPanelDebugById((items) => ({ ...items, [panelId]: debug }));
      setPanelDebugError((items) => {
        const next = { ...items };
        delete next[panelId];
        return next;
      });
      return debug;
    } catch (err) {
      setPanelDebugError((items) => ({
        ...items,
        [panelId]: err instanceof Error ? err.message : "分镜调试信息加载失败",
      }));
      return null;
    } finally {
      setLoadingPanelDebugId(null);
    }
  }

  async function selectTask(taskId: string) {
    setSelectedId(taskId);
    setDetailOpen(true);
    setSelectedTask(null);
    setPreviewImageId(null);
    setPreviewReferenceId(null);
    setPromptPreview(null);
    setPanelDebugById({});
    setPanelDebugError({});
    setLoadingPanelDebugId(null);
    onNavigatePath(`${viewRoutes.tasks}/${encodeURIComponent(taskId)}`);
  }

  function closeTaskDetail() {
    setDetailOpen(false);
    setSelectedId("");
    setSelectedTask(null);
    setPreviewImageId(null);
    setPreviewReferenceId(null);
    setPromptPreview(null);
    setPanelDebugById({});
    setPanelDebugError({});
    setLoadingPanelDebugId(null);
    onNavigatePath(viewRoutes.tasks);
  }

  function applyFilters(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCursor(null);
    setCursorStack([]);
    setQuery(queryInput.trim());
  }

  function clearFilters() {
    setQueryInput("");
    setQuery("");
    setStatusFilter("all");
    setStyleFilter("");
    setTaskUserFilter("");
    setCursor(null);
    setCursorStack([]);
  }

  function updateTaskUserFilter(value: string) {
    setTaskUserFilter(value);
    setCursor(null);
    setCursorStack([]);
  }

  function goNextPage() {
    if (!pageInfo?.next_cursor) return;
    setCursorStack((items) => [...items, cursor ?? ""]);
    setCursor(pageInfo.next_cursor);
  }

  function goPreviousPage() {
    setCursorStack((items) => {
      const next = [...items];
      const previous = next.pop() ?? "";
      setCursor(previous || null);
      return next;
    });
  }

  function resetCreateForm() {
    setCreateOriginalText("");
    setCountMode("auto");
    setLastPanelRealPhoto(false);
    setStoryInputMode("original");
    setCreateStyleId(createStyles[0]?.id ?? "");
    setFixedRoleFlowEnabled(false);
    setCharacterExtractionCompletedForText("");
    setExtractedCharacterNames([]);
    setManualCharacterNames([]);
    setCreateCharacterBindings({});
    setCharacterPickTarget(null);
    setManualRoleTarget(null);
    setCharacterCreateTarget(null);
    setQuickCharacterPreviewUrl("");
  }

  function updateCreateOriginalText(value: string) {
    setCreateOriginalText(value);
    if (characterExtractionCompletedForText && value.trim() !== characterExtractionCompletedForText) {
      setCharacterExtractionCompletedForText("");
      setExtractedCharacterNames([]);
      setManualCharacterNames([]);
      setCreateCharacterBindings({});
      setCharacterPickTarget(null);
      setManualRoleTarget(null);
    }
  }

  function toggleFixedRoleFlow(enabled: boolean) {
    setFixedRoleFlowEnabled(enabled);
    if (!enabled) {
      setCharacterExtractionCompletedForText("");
      setExtractedCharacterNames([]);
      setManualCharacterNames([]);
      setCreateCharacterBindings({});
      setCharacterPickTarget(null);
      setManualRoleTarget(null);
      setCharacterCreateTarget(null);
      setQuickCharacterPreviewUrl("");
    }
  }

  function bindCreateRole(sourceName: string, userCharacterId: string) {
    setCreateCharacterBindings((items) => {
      const next = { ...items };
      if (userCharacterId) {
        next[sourceName] = userCharacterId;
      } else {
        delete next[sourceName];
      }
      return next;
    });
  }

  async function extractRolesForCreate() {
    const text = createOriginalText.trim();
    if (!text) {
      setMessage("请输入故事内容后再提取角色");
      return;
    }
    try {
      setExtractingCharacters(true);
      const result = await api.extractCharacterNames({ text });
      setExtractedCharacterNames(result.names);
      setCharacterExtractionCompletedForText(text);
      setCreateCharacterBindings((items) => {
        const validNames = new Set([...result.names, ...manualCharacterNames]);
        return Object.fromEntries(Object.entries(items).filter(([name]) => validNames.has(name)));
      });
      setMessage(result.names.length ? `已提取 ${result.names.length} 个角色名` : "没有提取到明确角色名，可手动添加");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "角色提取失败");
    } finally {
      setExtractingCharacters(false);
    }
  }

  function removeCreateRole(sourceName: string) {
    setExtractedCharacterNames((items) => items.filter((name) => name !== sourceName));
    setManualCharacterNames((items) => items.filter((name) => name !== sourceName));
    setCreateCharacterBindings((items) => {
      const next = { ...items };
      delete next[sourceName];
      return next;
    });
    if (characterPickTarget === sourceName) {
      setCharacterPickTarget(null);
    }
  }

  function addManualRole(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const sourceName = String(formData.get("source_name") ?? "").trim();
    if (!sourceName) {
      setMessage("请输入角色名称");
      return;
    }
    setManualCharacterNames((items) => (items.includes(sourceName) ? items : [...items, sourceName]));
    setManualRoleTarget(null);
    setMessage("角色名称已添加，可继续绑定形象");
  }

  async function createAndBindCharacter(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!characterCreateTarget) return;
    const formData = new FormData(event.currentTarget);
    const sourceName = String(formData.get("source_name") ?? "").trim();
    const name = String(formData.get("name") ?? "").trim();
    const description = String(formData.get("description") ?? "").trim();
    const file = formData.get("file");
    const mergeIntoStory = formData.get("merge_into_story") === "on";
    if (!sourceName || !name) {
      setMessage("请输入角色名字");
      return;
    }
    if (!(file instanceof File) || file.size === 0) {
      setMessage("请上传角色参考图");
      return;
    }
    try {
      setCreatingCharacter(true);
      const character = await api.createCharacter({ name, description, file });
      setUserCharacters((items) => [character, ...items]);
      setManualCharacterNames((items) => (items.includes(sourceName) ? items : [...items, sourceName]));
      bindCreateRole(sourceName, character.id);
      if (mergeIntoStory) {
        const merged = await api.mergeCharacterIntoStory({
          story_text: createOriginalText,
          character_name: name,
          character_description: description || null,
        });
        setCreateOriginalText(merged.story_text);
        setMessage(merged.change_summary);
      } else {
        setMessage(description ? "角色已创建并绑定到本次任务" : "角色已创建并绑定，外观描述会在后台识别后自动补充");
      }
      setCharacterCreateTarget(null);
      setQuickCharacterPreviewUrl("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "角色创建失败");
    } finally {
      setCreatingCharacter(false);
    }
  }

  function describeQuickCharacterFile(file: File | undefined) {
    setQuickCharacterPreviewUrl(file ? URL.createObjectURL(file) : "");
    if (file) setMessage("参考图已选择，保存后会在后台识别外观描述");
  }

  async function createTask(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const requested = Number(formData.get("requested_image_count"));
    const originalText = createOriginalText.trim();
    if (!createStyleId) {
      setMessage("请选择一个风格");
      return;
    }
    if (!originalText) {
      setMessage("请输入任务内容");
      return;
    }
    const shouldUseDouyinReplicate = storyInputMode === "dy_replicate" || containsDouyinShareUrl(originalText);
    if (!shouldUseDouyinReplicate && fixedRoleFlowEnabled && !fixedRoleExtractionReady) {
      await extractRolesForCreate();
      return;
    }
    try {
      setCreating(true);
      const storyCharacters: StoryCharacterBinding[] = fixedRoleFlowEnabled
        ? createRoleNames
            .map((sourceName) => ({
              source_name: sourceName,
              user_character_id: createCharacterBindings[sourceName],
            }))
            .filter((item) => Boolean(item.user_character_id))
        : [];
      if (shouldUseDouyinReplicate) {
        const content = await api.replicateContentAsTask({
          raw_input: originalText,
          image_count_mode: countMode,
          requested_image_count: countMode === "fixed" ? requested : null,
          style_id: createStyleId,
          use_character_references: true,
          last_panel_real_photo: lastPanelRealPhoto,
        });
        resetCreateForm();
        setCreateOpen(false);
        setStylePickerOpen(false);
        setMessage(
          storyInputMode === "dy_replicate"
            ? "DY 爆款复刻已提交，正在提取内容并自动创建生图任务"
            : "检测到抖音分享链接，已按 DY 爆款复刻提交，正在提取内容",
        );
        void monitorReplicateTask(content.id);
        return;
      }
      const task = await api.createTask({
        original_text: originalText,
        story_input_mode: storyInputMode,
        image_count_mode: countMode,
        requested_image_count: countMode === "fixed" ? requested : null,
        style_id: createStyleId,
        use_character_references: true,
        last_panel_real_photo: lastPanelRealPhoto,
        story_characters: storyCharacters,
      });
      resetCreateForm();
      setCreateOpen(false);
      setStylePickerOpen(false);
      setMessage("任务已进入队列");
      onNavigatePath(`${viewRoutes.tasks}/${encodeURIComponent(task.id)}`);
      await refresh(task.id);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "创建失败");
    } finally {
      setCreating(false);
    }
  }

  async function monitorReplicateTask(contentExtractionId: string) {
    for (let attempt = 0; attempt < 160; attempt += 1) {
      await wait(3000);
      try {
        const content = await api.contentExtraction(contentExtractionId);
        if (content.linked_task_id) {
          setMessage("内容提取完成，已自动创建生图任务");
          onNavigatePath(`${viewRoutes.tasks}/${encodeURIComponent(content.linked_task_id)}`);
          await refresh(content.linked_task_id);
          return;
        }
        if (content.processing_status === "failed") {
          setMessage(content.processing_error_message || "DY 爆款复刻内容提取失败");
          return;
        }
        if (content.task_create_status === "failed") {
          setMessage(content.task_create_error_message || "内容已提取，但自动创建生图任务失败");
          return;
        }
        setMessage("DY 爆款复刻处理中：正在下载素材、提取内容或创建任务");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "DY 爆款复刻状态查询失败");
        return;
      }
    }
    setMessage("DY 爆款复刻仍在处理中，可稍后到内容提取列表查看状态");
  }

  async function cancelSelectedTask() {
    if (!selectedTask) return;
    try {
      const result = await api.cancelTask(selectedTask.id);
      setSelectedTask(result);
      setMessage("已提交取消请求");
      await refresh(result.id);
    } catch (err) {
      await refresh(selectedTask.id);
      setMessage(err instanceof Error ? err.message : "取消失败");
    }
  }

  async function retrySelectedTask() {
    if (!selectedTask) return;
    try {
      const result = await api.retryTask(selectedTask.id);
      setSelectedTask(result);
      setMessage("失败图片已重新进入生成队列");
      await refresh(result.id);
    } catch (err) {
      await refresh(selectedTask.id);
      setMessage(err instanceof Error ? err.message : "重试失败");
    }
  }

  async function editPanelImage(panelId: string) {
    if (!taskForDetail) return;
    const userInstruction = (panelEditInputs[panelId] ?? "").trim();
    if (!userInstruction) {
      setMessage("请输入这次要修改的画面方向");
      return;
    }
    try {
      setEditingPanelId(panelId);
      const result = await api.editPanelImage(taskForDetail.id, panelId, { user_instruction: userInstruction });
      setSelectedTask(result);
      setPanelEditInputs((items) => ({ ...items, [panelId]: "" }));
      setMessage("单分镜修改已进入队列");
      await refresh(result.id, { quiet: true });
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "提交修改失败");
    } finally {
      setEditingPanelId(null);
    }
  }

  function showPreviewOffset(offset: number) {
    if (!previewItems.length) return;
    const current = Math.max(0, previewIndex);
    const nextIndex = (current + offset + previewItems.length) % previewItems.length;
    setPreviewImageId(previewItems[nextIndex].id);
  }

  function showReferencePreviewOffset(offset: number) {
    if (!referencePreviewItems.length) return;
    const current = Math.max(0, referencePreviewIndex);
    const nextIndex = (current + offset + referencePreviewItems.length) % referencePreviewItems.length;
    setPreviewReferenceId(referencePreviewItems[nextIndex].id);
  }

  function downloadPreviewImage() {
    if (!previewImage?.asset) return;
    window.location.href = assetUrl(previewImage.asset, "original");
  }

  function openPreviewImage() {
    if (!previewImage?.asset) return;
    window.open(assetUrl(previewImage.asset, "original"), "_blank", "noopener,noreferrer");
  }

  function downloadPreviewReference() {
    if (!previewReference?.asset) return;
    window.location.href = assetUrl(previewReference.asset, "original");
  }

  function openPreviewReference() {
    if (!previewReference?.asset) return;
    window.open(assetUrl(previewReference.asset, "original"), "_blank", "noopener,noreferrer");
  }

  async function openImagePromptPreview(panelId: string, imageId: string, title: string) {
    const debug = panelDebugById[panelId] ?? (await loadPanelDebug(panelId));
    const imageDebug = debug?.images.find((item) => item.id === imageId);
    const promptText = imageDebug?.final_prompt ?? imageDebug?.image_prompt ?? debug?.generated_prompt ?? "";
    if (!promptText) {
      setMessage("当前图片还没有可查看的生图提示词");
      return;
    }
    setPromptPreview({ title, text: promptText });
  }

  async function downloadSelectedTask() {
    if (!selectedTask) return;
    if (!hasAllPanelImages(taskForDetail)) {
      setMessage("所有分镜图片生成成功后才能下载");
      return;
    }
    try {
      setDownloadingTaskId(selectedTask.id);
      const result = await api.createTaskDownload(selectedTask.id);
      if (result.status === "ready" && result.asset) {
        window.location.href = assetUrl(result.asset, "original");
      } else {
        setMessage(result.error_message ?? "下载包未就绪");
      }
      await refresh(selectedTask.id, { quiet: true });
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "打包下载失败");
    } finally {
      setDownloadingTaskId(null);
    }
  }

  const canCancel =
    taskForDetail?.status === "queued" || taskForDetail?.status === "running" || taskForDetail?.status === "retrying";
  const canDownload = Boolean(hasAllPanelImages(taskForDetail) && taskForDetail?.id !== downloadingTaskId);
  const isDownloadingSelectedTask = Boolean(taskForDetail?.id && taskForDetail.id === downloadingTaskId);
  const canRetry = taskForDetail?.status === "failed" || taskForDetail?.status === "partial_succeeded";

  return (
    <section className="page tasks-workspace">
      <header className="page-header">
        <div>
          <h1>任务</h1>
          <p>用影像项目列表追踪故事、分镜、生成进度和下载结果。</p>
        </div>
        <div className="header-actions">
          <button className="secondary-button" onClick={() => refresh(selectedId)}>
            <RefreshCw size={18} className={refreshing ? "spin" : ""} />
            刷新
          </button>
          <button onClick={() => setCreateOpen(true)}>
            <Plus size={18} />
            创建任务
          </button>
        </div>
      </header>

      <form className={`task-toolbar ${user.role === "admin" ? "with-user-filter" : ""}`} onSubmit={applyFilters}>
        <label className="search-box">
          <Search size={18} />
          <input
            value={queryInput}
            onChange={(event) => setQueryInput(event.target.value)}
            placeholder="搜索故事或任务"
          />
        </label>
        <label>
          <Filter size={16} />
          <select
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value as Task["status"] | "all");
              setCursor(null);
              setCursorStack([]);
            }}
          >
            {taskStatusOptions.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <Sparkles size={16} />
          <select
            value={styleFilter}
            disabled={loadingStyleFilterOptions}
            onChange={(event) => {
              setStyleFilter(event.target.value);
              setCursor(null);
              setCursorStack([]);
            }}
          >
            <option value="">{loadingStyleFilterOptions ? "风格加载中" : "全部风格"}</option>
            {styleFilterOptions.map((style) => (
              <option key={style.id} value={style.id}>
                {style.name}
              </option>
            ))}
          </select>
        </label>
        {user.role === "admin" ? (
          <label>
            <Users size={16} />
            <select value={taskUserFilter} onChange={(event) => updateTaskUserFilter(event.target.value)} disabled={loadingTaskUsers}>
              <option value="">{loadingTaskUsers ? "用户加载中" : "全部用户"}</option>
              {taskUserOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.display_name || item.email}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <button type="submit" className="secondary-button">
          筛选
        </button>
        <button type="button" className="ghost-button" onClick={clearFilters}>
          清空
        </button>
      </form>

      <div className="task-meta-bar">
        <span>共显示 {tasks.length} 个任务</span>
        <span>{lastRefreshedAt ? `上次刷新 ${formatDateTime(lastRefreshedAt.toISOString())}` : "等待刷新"}</span>
      </div>

      {error ? <div className="error">{error}</div> : null}

      <div className="task-cinema-layout">
        <section className="task-project-list">
          <div className="task-list-head">
            <span>故事</span>
            <span>分镜预览</span>
            <span>风格</span>
            <span>状态</span>
            <span>图片</span>
            <span>创建</span>
            <span>操作</span>
          </div>
          {loadingTasks ? <div className="empty">正在加载任务</div> : null}
          {!loadingTasks && tasks.length === 0 ? (
            <div className="empty">
              <div>
                <strong>{hasTaskFilters ? "没有匹配的任务" : "还没有任务"}</strong>
                <p>{hasTaskFilters ? "调整筛选条件后再试。" : "创建第一条故事生成任务。"}</p>
                <button type="button" onClick={() => setCreateOpen(true)}>
                  <Plus size={18} />
                  创建任务
                </button>
              </div>
            </div>
          ) : null}
          {tasks.map((task) => {
            const rowImages = task.preview_images;
            const imageCount = task.image_count;
            return (
              <button
                type="button"
	                className={`task-project-row ${selectedId === task.id ? "selected" : ""}`}
                key={task.id}
                aria-haspopup="dialog"
	                aria-expanded={detailOpen && selectedId === task.id}
                onClick={() => selectTask(task.id)}
              >
                <div className="task-story-cell">
                  <span className={`task-dot ${task.status}`} />
                  <div>
                    <strong>{task.display_title}</strong>
                    <p>{task.original_text_preview}</p>
	                    {user.role === "admin" ? (
	                      <small>{task.owner_display_name || task.owner_email || shortId(task.owner_user_id)}</small>
	                    ) : null}
	                  </div>
                </div>
                <div className="thumb-strip">
	                  {rowImages.slice(0, TASK_ROW_IMAGE_PREVIEW_LIMIT).map((image) => (
	                    <LazyAssetImage key={image.id} asset={image.asset} assetId={image.asset.id} alt={task.display_title} />
	                  ))}
                  {rowImages.length === 0 ? <span className="thumb-empty">等待图片</span> : null}
	                  {imageCount > TASK_ROW_IMAGE_PREVIEW_LIMIT ? (
	                    <span className="thumb-more">+{imageCount - TASK_ROW_IMAGE_PREVIEW_LIMIT}</span>
                  ) : null}
                </div>
                <div className="task-row-side">
                  <div className="task-style-cell">
                    <strong>{task.style_name_snapshot}</strong>
                    <small>
                      {storyInputModeLabel(task.story_input_mode)}
                      {" · "}
                      {task.image_count_mode === "auto" ? "自动数量" : `${task.requested_image_count ?? 0} 张`}
                      {" · "}
                      {task.last_panel_real_photo ? "最后一张真人 · " : ""}
                      {task.style_aspect_ratio_snapshot}
                    </small>
                  </div>
                  <div className="task-status-cell">
                    <span className={`status-pill ${task.status}`}>{taskStatusLabel(task.status)}</span>
                    <div className="progress-line">
                      <span style={{ width: `${taskProgress(task)}%` }} />
                    </div>
                    <small>
                      {task.progress_current}/{task.progress_total}
                    </small>
                  </div>
                  <div className="task-row-foot">
                    <span>{imageCount} 张</span>
                    <span>{formatDateTime(task.created_at)}</span>
                    <span className="row-actions">
                      {task.status === "succeeded" && rowImages.length > 0 ? (
                        <span className="mini-action">
                          <Download size={15} />
                        </span>
                      ) : (
                        <span className="muted">-</span>
                      )}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
          <div className="pagination-bar">
            <button className="icon-button" aria-label="上一页" disabled={cursorStack.length === 0} onClick={goPreviousPage}>
              <ChevronLeft size={16} />
            </button>
            <span>{cursor ? `第 ${Math.floor(Number(cursor) / 10) + 1} 页` : "第 1 页"}</span>
            <button className="icon-button" aria-label="下一页" disabled={!pageInfo?.has_more} onClick={goNextPage}>
              <ChevronRight size={16} />
            </button>
          </div>
        </section>

      </div>

	      {detailOpen && taskForDetail ? (
	        <div className="task-detail-backdrop" onClick={closeTaskDetail}>
          <aside
            className="task-detail-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="task-detail-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="detail-drawer-head">
              <div>
                <span>任务详情</span>
                <strong>{taskForDetail.display_title}</strong>
              </div>
	              <button type="button" className="icon-button" aria-label="关闭任务详情" onClick={closeTaskDetail}>
                <X size={18} />
              </button>
            </div>
            <div className="task-inspector">
              <section className="detail-head">
                <div>
                  <span className={`status-pill ${taskForDetail.status}`}>{taskStatusLabel(taskForDetail.status)}</span>
                  <h2 id="task-detail-title">{taskForDetail.display_title}</h2>
                  <p>
                        {taskForDetail.style_name_snapshot} · 创建于 {formatDateTime(taskForDetail.created_at)}
                        <br />
                        模型 {taskForDetail.image_model_name_snapshot} · 比例 {taskForDetail.style_aspect_ratio_snapshot}
                  </p>
                </div>
                <div className="detail-actions">
                  <button type="button" className="secondary-button" disabled={!canDownload} onClick={downloadSelectedTask}>
                    {isDownloadingSelectedTask ? <Loader2 size={16} className="spin" /> : <Download size={16} />}
                    {isDownloadingSelectedTask ? "打包中" : "下载图片"}
                  </button>
                  <button type="button" className="secondary-button" disabled={!canRetry} onClick={retrySelectedTask}>
                    <RefreshCw size={16} />
                    重新生成
                  </button>
                  <button type="button" className="ghost-button" disabled={!canCancel} onClick={cancelSelectedTask}>
                    <X size={16} />
                    取消生成
                  </button>
                </div>
                {taskForDetail.error_message ? <p className="error">{taskForDetail.error_message}</p> : null}
              </section>

              <section className="progress-panel">
                <div>
                  <strong>{currentStepLabel(taskForDetail)}</strong>
                  <span>{taskProgress(taskForDetail)}%</span>
                </div>
                <div className="progress-line large">
                  <span style={{ width: `${taskProgress(taskForDetail)}%` }} />
                </div>
              </section>

              {taskStepsForDetail.length > 0 ? (
                <section className="step-strip">
                  {taskStepsForDetail.map((step) => (
                    <div key={step.id} className={`step-chip ${step.status}`}>
                      {step.status === "succeeded" ? <CheckCircle2 size={17} /> : null}
                      {step.status === "running" ? <Loader2 size={17} className="spin" /> : null}
                      {step.status === "failed" ? <AlertCircle size={17} /> : null}
                      {!["succeeded", "running", "failed"].includes(step.status) ? <Clock3 size={17} /> : null}
                      <strong>{stepLabels[step.step_name] ?? step.step_name}</strong>
                      <span>{step.status}</span>
                    </div>
                  ))}
                </section>
              ) : null}

              {taskForDetail.use_character_references ? (
                <section className="character-reference-panel">
                  <div className="editor-title">
                    <div>
                      <h2>人物参考</h2>
                      <p>任务会优先使用这些人物参考图保持主要人物一致。</p>
                    </div>
                  </div>
                  {taskForDetail.character_references.length > 0 ? (
                    <div className="character-reference-grid">
                      {taskForDetail.character_references.map((reference) => (
                        <figure key={reference.id} className="character-reference-card">
                          <button
                            type="button"
                            className="character-reference-image-button"
                            aria-label={`放大查看${reference.name}参考图`}
                            onClick={() => setPreviewReferenceId(reference.id)}
                          >
                            <LazyAssetImage asset={reference.asset} assetId={reference.asset.id} alt={reference.name} />
                            <Eye size={17} />
                          </button>
                          <figcaption>
                            <strong>{reference.name}</strong>
                            {reference.age_stage ? <span>{reference.age_stage}</span> : null}
                            {reference.reference_prompt ? (
                              <button
                                type="button"
                                className="inline-prompt-button character-reference-prompt-button"
                                onClick={() =>
                                  setPromptPreview({
                                    title: `${reference.name} 人物参考图提示词`,
                                    text: reference.reference_prompt ?? "",
                                  })
                                }
                              >
                                <FileText size={14} />
                                查看提示词
                              </button>
                            ) : null}
                          </figcaption>
                        </figure>
                      ))}
                    </div>
                  ) : (
                    <div className="empty mini">人物参考图生成中</div>
                  )}
                </section>
              ) : null}

              {taskForDetail.last_panel_real_photo ? (
                <section className="story-panel compact-info-panel">
                  <h2>真人结尾</h2>
                  <p>最后一张启用真人照片风格，不携带漫画风格参考图或人物参考图。</p>
                </section>
              ) : null}

              <section className="story-panel">
                <h2>原始文本</h2>
                <p>{taskForDetail.original_text}</p>
              </section>

              {taskForDetail.story_input_mode !== "original" ? (
                <section className="story-panel adapted-story-panel">
                  <h2>{taskForDetail.story_input_mode === "extracted_storyboard" ? "提取分镜概要" : "增强故事"}</h2>
                  {taskForDetail.adapted_story_title ? <strong>{taskForDetail.adapted_story_title}</strong> : null}
                  {taskForDetail.adapted_story_hook ? <small>{taskForDetail.adapted_story_hook}</small> : null}
                  <p>{taskForDetail.adapted_story_text ?? (taskForDetail.story_input_mode === "extracted_storyboard" ? "等待内容提取分镜结构化" : "等待 LLM 故事增强")}</p>
                </section>
              ) : null}

              <section className="panel-wall">
                <div className="editor-title">
                  <div>
                    <h2>分镜与图片</h2>
                    <p>每个 panel 对应一张图片，比例由风格模板控制。</p>
                  </div>
                </div>
                <div className="task-image-grid">
                  {taskForDetail.panels.length === 0 ? <div className="empty mini">等待故事切分</div> : null}
                  {sortedPanels(taskForDetail).map((panel) => {
                    const image = panelImageMap.get(panel.id);
                    const versions = panelImageVersions(taskForDetail, panel.id);
                    const activeVersion = versions.find((item) => item.status === "queued" || item.status === "running");
                    const canEditPanel = panel.prompt_status === "generated" && !activeVersion;
                    const panelDebug = panelDebugById[panel.id];
                    const imageDebug = image ? panelDebug?.images.find((item) => item.id === image.id) : undefined;
                    const imageText = imageTextSummary(imageDebug?.image_text_json ?? panelDebug?.image_text_json);
                    const textLayout = imageDebug?.text_layout ?? panelDebug?.text_layout;
                    const promptText = imageDebug?.final_prompt ?? imageDebug?.image_prompt ?? panelDebug?.generated_prompt ?? "";
                    const currentImageIsUserEdit = image?.source_type === "user_edit";
                    return (
                      <article key={panel.id} className="panel-card">
                        <div className="poster">
                          {image?.asset ? (
                            <button
                              type="button"
                              className="image-button"
                              onClick={() => setPreviewImageId(image.id)}
                            >
                              <LazyAssetImage asset={image.asset} assetId={image.asset.id} alt={`分镜 ${panel.panel_order}`} />
                              <Eye size={18} />
                            </button>
                          ) : (
                            <span>{imageStatusLabel(image?.status ?? panel.prompt_status)}</span>
                          )}
                        </div>
                        <strong>Panel {panel.panel_order}</strong>
                        {image?.workflow_step && image.status !== "succeeded" ? (
                          <small className="process-note">
                            {imageWorkflowLabel(image.workflow_step)} · {imageStatusLabel(image.status)}
                          </small>
                        ) : null}
                        {currentImageIsUserEdit && image?.user_instruction ? <small>修改方向：{image.user_instruction}</small> : null}
                        {currentImageIsUserEdit && image?.prompt_change_summary ? <small>修改摘要：{image.prompt_change_summary}</small> : null}
                        {image?.error_message ? <small className="error">{image.error_message}</small> : null}
                        <div className="panel-debug-actions">
                          <button
                            type="button"
                            className="ghost-button"
                            disabled={loadingPanelDebugId === panel.id}
                            onClick={() => loadPanelDebug(panel.id)}
                          >
                            {loadingPanelDebugId === panel.id ? <Loader2 size={15} className="spin" /> : <FileText size={15} />}
                            {panelDebug ? "已加载分镜文本" : "查看图片文字和 Prompt"}
                          </button>
                          {image ? (
                            <button
                              type="button"
                              className="ghost-button"
                              disabled={loadingPanelDebugId === panel.id}
                              onClick={() => openImagePromptPreview(panel.id, image.id, `Panel ${panel.panel_order} 生图提示词`)}
                            >
                              {loadingPanelDebugId === panel.id ? <Loader2 size={15} className="spin" /> : <FileText size={15} />}
                              查看生图提示词
                            </button>
                          ) : null}
                        </div>
                        {panelDebugError[panel.id] ? <small className="error">{panelDebugError[panel.id]}</small> : null}
                        {panelDebug ? (
                          <div className="panel-debug-box">
                            <p>{panelDebug.original_text_segment}</p>
                            {panelDebug.narration_text ? <small>旁白：{panelDebug.narration_text}</small> : null}
                            {panelDebug.dialogue_text ? <small>对白：{panelDebug.dialogue_text}</small> : null}
                            {imageText ? <small>图片文字：{imageText}</small> : null}
                            {textLayout ? <small>文字布局：{textLayout}</small> : null}
                            {promptText ? (
                              <button
                                type="button"
                                className="inline-prompt-button"
                                onClick={() => setPromptPreview({ title: `Panel ${panel.panel_order} 生图提示词`, text: promptText })}
                              >
                                <FileText size={14} />
                                打开完整生图提示词
                              </button>
                            ) : null}
                            {imageDebug?.previous_prompt ? (
                              <button
                                type="button"
                                className="inline-prompt-button"
                                onClick={() =>
                                  setPromptPreview({
                                    title: `Panel ${panel.panel_order} 上一版 Prompt`,
                                    text: imageDebug.previous_prompt ?? "",
                                  })
                                }
                              >
                                <FileText size={14} />
                                打开上一版 Prompt
                              </button>
                            ) : null}
                          </div>
                        ) : null}
                        <div className="panel-edit-box">
                          <textarea
                            value={panelEditInputs[panel.id] ?? ""}
                            onChange={(event) =>
                              setPanelEditInputs((items) => ({ ...items, [panel.id]: event.target.value }))
                            }
                            placeholder="描述要调整的画面方向，例如：人物更紧张，背景改成雨夜街头"
                            disabled={!canEditPanel || editingPanelId === panel.id}
                          />
                          <button
                            type="button"
                            className="secondary-button"
                            disabled={!canEditPanel || editingPanelId === panel.id}
                            onClick={() => editPanelImage(panel.id)}
                          >
                            {editingPanelId === panel.id ? <Loader2 size={15} className="spin" /> : <Sparkles size={15} />}
                            修改画面
                          </button>
                        </div>
                        {versions.length > 0 ? (
                          <div className="panel-version-list">
                            {versions.slice(0, 4).map((version) => {
                              const versionIsUserEdit = version.source_type === "user_edit";
                              return (
                                <div key={version.id} className={`panel-version-item ${version.status}`}>
                                  <span>v{version.generation_number}</span>
                                  <strong>{imageSourceLabel(version.source_type)}</strong>
                                  <em>{imageWorkflowLabel(version.workflow_step)}</em>
                                  <small>{imageStatusLabel(version.status)}{version.is_current ? " · 当前" : ""}</small>
                                  {versionIsUserEdit && version.user_instruction ? <small>修改方向：{version.user_instruction}</small> : null}
                                  {versionIsUserEdit && version.prompt_change_summary ? <small>修改摘要：{version.prompt_change_summary}</small> : null}
                                </div>
                              );
                            })}
                          </div>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              </section>
            </div>
          </aside>
        </div>
      ) : null}

      {createOpen ? (
        <div className="task-create-backdrop" onClick={() => setCreateOpen(false)}>
          <section
            className="task-create-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="task-create-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="drawer-head">
              <div>
                <h2 id="task-create-title">创建任务</h2>
                <p>选择输入方式、图片数量和风格后，任务会进入生成队列。</p>
              </div>
              <button type="button" className="icon-button" aria-label="关闭创建任务" onClick={() => setCreateOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <form className="task-create-form" onSubmit={createTask}>
              <div className="mode-choice-grid" role="group" aria-label="选择故事输入方式">
                <button
                  type="button"
                  className={storyInputMode === "original" ? "mode-choice active" : "mode-choice"}
                  aria-pressed={storyInputMode === "original"}
                  onClick={() => setStoryInputMode("original")}
                >
                  <strong>完整故事</strong>
                  <span>保持故事不变，只按原文切分；请只提交故事本身，不要加入说明、标签或额外要求。</span>
                </button>
                <button
                  type="button"
                  className={storyInputMode === "adapted" ? "mode-choice active" : "mode-choice"}
                  aria-pressed={storyInputMode === "adapted"}
                  onClick={() => setStoryInputMode("adapted")}
                >
                  <strong>故事方案</strong>
                  <span>可以提交故事设计、人物设定、画面要求或简化想法，系统会规划连续分镜。</span>
                </button>
                <button
                  type="button"
                  className={storyInputMode === "extracted_storyboard" ? "mode-choice active" : "mode-choice"}
                  aria-pressed={storyInputMode === "extracted_storyboard"}
                  onClick={() => setStoryInputMode("extracted_storyboard")}
                >
                  <strong>提取分镜</strong>
                  <span>适合从内容提取结果直接生图，保留页序、旁白、对白、内心 OS 和分格布局。</span>
                </button>
                <button
                  type="button"
                  className={storyInputMode === "dy_replicate" ? "mode-choice active" : "mode-choice"}
                  aria-pressed={storyInputMode === "dy_replicate"}
                  onClick={() => setStoryInputMode("dy_replicate")}
                >
                  <strong>DY爆款复刻</strong>
                  <span>粘贴抖音分享文本，系统先提取逐页内容，再自动创建提取分镜生图任务。</span>
                </button>
              </div>
              <label>
                {storyInputMode === "adapted"
                  ? "故事方案或要求"
                  : storyInputMode === "extracted_storyboard"
                    ? "提取分镜内容"
                    : storyInputMode === "dy_replicate"
                      ? "抖音分享文本或链接"
                      : "完整故事正文"}
                <textarea
                  name="original_text"
                  value={createOriginalText}
                  onChange={(event) => updateCreateOriginalText(event.target.value)}
                  placeholder={
                    storyInputMode === "adapted"
                      ? "输入故事设定、简短梗概、人物关系、画面要求或其他创作方向"
                      : storyInputMode === "extracted_storyboard"
                        ? "粘贴或编辑内容提取结果，例如第1页、第2页、画面、旁白、对话、内心OS和分格信息"
                        : storyInputMode === "dy_replicate"
                          ? "粘贴完整抖音分享文本或链接，例如 https://v.douyin.com/..."
                          : "只粘贴故事正文。不要加入标题说明、图片数量、标签、总结或其他要求"
                  }
                  required
                  autoFocus
                />
                {storyInputMode === "adapted" ? (
                  <small>原始输入会保留，系统会直接根据方案规划图文分镜；所有图片都按同一套分镜逻辑生成。</small>
                ) : storyInputMode === "extracted_storyboard" ? (
                  <small>系统只做分镜结构化，不扩写、不总结、不合并页；会把旁白、对白和内心 OS 区分成不同画面呈现形式。</small>
                ) : storyInputMode === "dy_replicate" ? (
                  <small>提交后会先创建内容提取记录；提取成功后自动创建提取分镜任务并跳转到任务详情。</small>
                ) : (
                  <small>完整故事模式会保持文本不变，所有 panel 拼接后必须逐字等于你提交的故事正文。</small>
                )}
              </label>
              <section className="create-section">
                <div className="section-label">图片数量</div>
                <div className="segmented-control">
                  <button type="button" className={countMode === "auto" ? "active" : ""} onClick={() => setCountMode("auto")}>
                    自动判断
                  </button>
                  <button type="button" className={countMode === "fixed" ? "active" : ""} onClick={() => setCountMode("fixed")}>
                    固定数量
                  </button>
                </div>
                {countMode === "fixed" ? (
                  <label>
                    图片数量
                    <input name="requested_image_count" type="number" min="1" max="80" placeholder="例如 8" required />
                    {storyInputMode === "adapted" ? <small>固定数量就是最终图片张数，系统不会额外插入图片。</small> : null}
                    {storyInputMode === "extracted_storyboard" ? <small>固定数量必须和提取分镜页数一致，不会自动合并或补页。</small> : null}
                    {storyInputMode === "dy_replicate" ? <small>固定数量必须和提取出的页数一致；内容提取完成后不会自动合并或补页。</small> : null}
                  </label>
                ) : (
                  <p className="field-hint">系统会根据故事长度和内容密度决定图片张数。</p>
                )}
              </section>
              <section className="create-section">
                <label className="character-reference-toggle real-photo-toggle">
                  <input
                    type="checkbox"
                    checked={lastPanelRealPhoto}
                    onChange={(event) => setLastPanelRealPhoto(event.target.checked)}
                  />
                  <span>
                    <strong>最后一张真人图片</strong>
                    <small>默认关闭；勾选后最后一个分镜按真实摄影/自拍照片生成，不跟随当前漫画风格。</small>
                  </span>
                </label>
              </section>
              <fieldset className="style-picker">
                <legend>选择风格</legend>
                <div className="style-picker-head">
                  <div>
                    <p>按风格内设置的参考方式生成图片，提交后会使用该风格绑定的模型名。</p>
                  </div>
                  {canExpandCreateStyles ? (
                    <button type="button" className="secondary-button" onClick={() => setStylePickerOpen(true)}>
                      <Images size={16} />
                      展开更多风格
                    </button>
                  ) : null}
                </div>
                {loadingCreateStyles ? <div className="empty mini">风格加载中</div> : null}
                {!loadingCreateStyles && createStyles.length === 0 ? <div className="empty mini">暂无启用风格</div> : null}
                <div className="style-picker-grid compact">
                  {visibleCreateStyles.map((style) => {
                    const assets = stylePreviewAssets(style);
                    return (
                      <button
                        type="button"
                        key={style.id}
                        className={`style-pick-card ${createStyleId === style.id ? "selected" : ""}`}
                        aria-pressed={createStyleId === style.id}
                        onClick={() => setCreateStyleId(style.id)}
                      >
                        <div className="style-pick-images">
                          {assets.slice(0, 1).map((asset) => (
                            <LazyAssetImage key={asset.id} asset={asset} assetId={asset.id} alt={style.name} />
                          ))}
                          {assets.length === 0 ? <span>无图片</span> : null}
                        </div>
                        <div>
                          <strong>{style.name}</strong>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </fieldset>
              {message ? <p className="form-message">{message}</p> : null}
              {storyInputMode !== "dy_replicate" && fixedRoleFlowEnabled ? (
                <section className="create-section character-quick-section">
                  <p className="field-hint">勾选后需先提取角色名，再选择要绑定的固定角色。已绑定 {boundRoleCount} 个。</p>
                  {fixedRoleExtractionReady ? (
                    <div className="quick-character-grid">
                      {createRoleNames.map((name) => {
                        const boundCharacter = userCharacters.find((character) => character.id === createCharacterBindings[name]);
                        return (
                          <div key={name} className={`quick-character-card ${boundCharacter ? "bound" : ""}`}>
                            <button
                              type="button"
                              className="quick-character-remove"
                              aria-label={`移除 ${name}`}
                              onClick={() => removeCreateRole(name)}
                            >
                              <X size={14} />
                            </button>
                            {boundCharacter ? (
                              <LazyAssetImage
                                asset={boundCharacter.reference_asset}
                                assetId={boundCharacter.reference_asset.id}
                                alt={boundCharacter.name}
                              />
                            ) : (
                              <button
                                type="button"
                                className="quick-character-plus"
                                aria-label={`设置 ${name} 的角色形象`}
                                onClick={() => setCharacterPickTarget(name)}
                              >
                                <Plus size={22} />
                              </button>
                            )}
                            <strong>{name}</strong>
                            {boundCharacter ? <small>{boundCharacter.name}</small> : <small>未设置形象</small>}
                            <select
                              value={createCharacterBindings[name] ?? ""}
                              onChange={(event) => bindCreateRole(name, event.target.value)}
                              aria-label={`绑定 ${name} 到我的角色`}
                            >
                              <option value="">不绑定</option>
                              {userCharacters.map((character) => (
                                <option key={character.id} value={character.id}>
                                  {character.name}
                                </option>
                              ))}
                            </select>
                          </div>
                        );
                      })}
                      <button
                        type="button"
                        className="quick-character-card add-card"
                        onClick={() => setManualRoleTarget({ allowMerge: true })}
                      >
                        <span className="quick-character-plus">
                          <Plus size={22} />
                        </span>
                        <strong>添加角色</strong>
                        <small>只填写角色名称</small>
                      </button>
                    </div>
                  ) : (
                    <div className="character-extraction-waiting">
                      <Search size={17} />
                      <span>点击底部“提取角色”后，会显示可绑定的角色列表。</span>
                    </div>
                  )}
                  {loadingCharacters ? <small className="field-hint">正在读取我的角色库</small> : null}
                </section>
              ) : null}
              <div className="task-create-footer">
                {storyInputMode !== "dy_replicate" ? (
                  <label className="character-reference-toggle fixed-role-toggle footer-role-toggle">
                    <input
                      type="checkbox"
                      checked={fixedRoleFlowEnabled}
                      onChange={(event) => toggleFixedRoleFlow(event.target.checked)}
                    />
                    <span>
                      <strong>使用固定角色</strong>
                      <small>勾选后底部按钮会先提取角色；不勾选会直接创建任务。</small>
                    </span>
                  </label>
                ) : null}
                <div className="drawer-actions">
                  <button type="button" className="ghost-button" onClick={() => setCreateOpen(false)}>
                    取消
                  </button>
                  <button type="submit" disabled={creating || extractingCharacters}>
                    {creating || extractingCharacters ? (
                      <Loader2 size={17} className="spin" />
                    ) : fixedRoleFlowEnabled && !fixedRoleExtractionReady && storyInputMode !== "dy_replicate" ? (
                      <Search size={17} />
                    ) : (
                      <Plus size={17} />
                    )}
                    {storyInputMode === "dy_replicate"
                      ? "开始复刻"
                      : fixedRoleFlowEnabled && !fixedRoleExtractionReady
                        ? "提取角色"
                        : "创建任务"}
                  </button>
                </div>
              </div>
            </form>
          </section>
          {manualRoleTarget ? (
            <div
              className="style-picker-backdrop"
              onClick={(event) => {
                event.stopPropagation();
                setManualRoleTarget(null);
              }}
            >
              <section
                className="character-create-modal small"
                role="dialog"
                aria-modal="true"
                aria-labelledby="manual-role-title"
                onClick={(event) => event.stopPropagation()}
              >
                <div className="drawer-head">
                  <div>
                    <h2 id="manual-role-title">添加角色</h2>
                    <p>这里只添加角色名称，之后可以点加号绑定已有角色形象。</p>
                  </div>
                  <button type="button" className="icon-button" aria-label="关闭添加角色" onClick={() => setManualRoleTarget(null)}>
                    <X size={18} />
                  </button>
                </div>
                <form className="form compact-form" onSubmit={addManualRole}>
                  <label>
                    角色名称
                    <input name="source_name" placeholder="例如 女主、男友、小猫" required autoFocus />
                  </label>
                  <div className="drawer-actions">
                    <button type="button" className="ghost-button" onClick={() => setManualRoleTarget(null)}>
                      取消
                    </button>
                    <button type="submit">
                      <Plus size={17} />
                      添加
                    </button>
                  </div>
                </form>
              </section>
            </div>
          ) : null}
          {characterPickTarget ? (
            <div
              className="style-picker-backdrop"
              onClick={(event) => {
                event.stopPropagation();
                setCharacterPickTarget(null);
              }}
            >
              <section
                className="character-picker-modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="character-picker-title"
                onClick={(event) => event.stopPropagation()}
              >
                <div className="drawer-head">
                  <div>
                    <h2 id="character-picker-title">绑定角色形象</h2>
                    <p>为「{characterPickTarget}」选择你的角色库图片。</p>
                  </div>
                  <button type="button" className="icon-button" aria-label="关闭角色选择" onClick={() => setCharacterPickTarget(null)}>
                    <X size={18} />
                  </button>
                </div>
                {userCharacters.length === 0 ? (
                  <div className="empty mini">角色库暂无角色，可以新建一个角色形象。</div>
                ) : (
                  <div className="character-picker-list">
                    {userCharacters.map((character) => (
                      <button
                        type="button"
                        key={character.id}
                        className={`character-picker-row ${createCharacterBindings[characterPickTarget] === character.id ? "selected" : ""}`}
                        onClick={() => {
                          bindCreateRole(characterPickTarget, character.id);
                          setCharacterPickTarget(null);
                        }}
                      >
                        <LazyAssetImage
                          asset={character.reference_asset}
                          assetId={character.reference_asset.id}
                          alt={character.name}
                        />
                        <span>
                          <strong>{character.name}</strong>
                          <small>{character.description || "暂无描述"}</small>
                        </span>
                      </button>
                    ))}
                  </div>
                )}
                <div className="drawer-actions">
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => {
                      setCharacterCreateTarget({ sourceName: characterPickTarget, allowMerge: false });
                      setCharacterPickTarget(null);
                    }}
                  >
                    <Plus size={17} />
                    新建角色形象
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => {
                      bindCreateRole(characterPickTarget, "");
                      setCharacterPickTarget(null);
                    }}
                  >
                    不绑定
                  </button>
                </div>
              </section>
            </div>
          ) : null}
          {characterCreateTarget ? (
            <div
              className="style-picker-backdrop"
              onClick={(event) => {
                event.stopPropagation();
                setCharacterCreateTarget(null);
              }}
            >
              <section
                className="character-create-modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="character-create-title"
                onClick={(event) => event.stopPropagation()}
              >
                <div className="drawer-head">
                  <div>
                    <h2 id="character-create-title">设置角色形象</h2>
                    <p>参考图只保存在你的角色库，本次任务会使用快照。</p>
                  </div>
                  <button type="button" className="icon-button" aria-label="关闭角色设置" onClick={() => setCharacterCreateTarget(null)}>
                    <X size={18} />
                  </button>
                </div>
                <form className="form compact-form" onSubmit={createAndBindCharacter}>
                  <label>
                    故事里的角色名
                    <input
                      name="source_name"
                      defaultValue={characterCreateTarget.sourceName}
                      placeholder="例如 三只小猪"
                      required
                    />
                  </label>
                  <label>
                    保存到角色库的名字
                    <input
                      name="name"
                      defaultValue={characterCreateTarget.sourceName}
                      placeholder="例如 三只小猪设定"
                      required
                    />
                  </label>
                  <label>
                    形象描述
                    <textarea
                      name="description"
                      placeholder="可手动填写；留空时保存后会在后台自动识别"
                    />
                    <small>这段描述会保存到角色库；留空时不会阻塞保存，系统会后台识别并自动补充。</small>
                  </label>
                  <label>
                    参考图
                    <input
                      name="file"
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      required
                      onChange={(event) => describeQuickCharacterFile(event.currentTarget.files?.[0])}
                    />
                  </label>
                  {quickCharacterPreviewUrl ? (
                    <div className="upload-preview-frame">
                      <img src={quickCharacterPreviewUrl} alt="上传预览" />
                    </div>
                  ) : null}
                  {characterCreateTarget.allowMerge ? (
                    <label className="character-reference-toggle">
                      <input name="merge_into_story" type="checkbox" />
                      <span>
                        <strong>融入故事文本</strong>
                        <small>这是显式 LLM 操作，会把新增角色自然写入当前故事。</small>
                      </span>
                    </label>
                  ) : null}
                  <div className="drawer-actions">
                    <button type="button" className="ghost-button" onClick={() => setCharacterCreateTarget(null)}>
                      取消
                    </button>
                    <button type="submit" disabled={creatingCharacter}>
                      {creatingCharacter ? <Loader2 size={17} className="spin" /> : <Save size={17} />}
                      保存并绑定
                    </button>
                  </div>
                </form>
              </section>
            </div>
          ) : null}
          {stylePickerOpen ? (
            <div
              className="style-picker-backdrop"
              onClick={(event) => {
                event.stopPropagation();
                setStylePickerOpen(false);
              }}
            >
              <section
                className="style-picker-modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="style-picker-title"
                onClick={(event) => event.stopPropagation()}
              >
                <div className="drawer-head">
                  <div>
                    <h2 id="style-picker-title">选择风格</h2>
                  </div>
                  <button type="button" className="icon-button" aria-label="关闭风格选择" onClick={() => setStylePickerOpen(false)}>
                    <X size={18} />
                  </button>
                </div>
                <div className="style-picker-grid expanded">
                  {createStyles.map((style) => {
                    const assets = stylePreviewAssets(style);
                    return (
                      <button
                        type="button"
                        key={style.id}
                        className={`style-pick-card ${createStyleId === style.id ? "selected" : ""}`}
                        aria-pressed={createStyleId === style.id}
                        onClick={() => {
                          setCreateStyleId(style.id);
                          setStylePickerOpen(false);
                        }}
                      >
                        <div className="style-pick-images">
                          {assets.slice(0, 1).map((asset) => (
                            <LazyAssetImage key={asset.id} asset={asset} assetId={asset.id} alt={style.name} />
                          ))}
                          {assets.length === 0 ? <span>无图片</span> : null}
                        </div>
                        <div>
                          <strong>{style.name}</strong>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </section>
            </div>
          ) : null}
        </div>
      ) : null}

      {previewImage?.asset ? (
        <div className="image-modal" onClick={() => setPreviewImageId(null)}>
          <button ref={previewCloseRef} type="button" className="modal-close" aria-label="关闭预览" onClick={() => setPreviewImageId(null)}>
            <X size={18} />
          </button>
          <button type="button" className="modal-nav left" aria-label="上一张图片" disabled={previewItems.length <= 1} onClick={(event) => { event.stopPropagation(); showPreviewOffset(-1); }}>
            <ChevronLeft size={22} />
          </button>
          <figure className="image-preview-frame" onClick={(event) => event.stopPropagation()}>
	            <LazyAssetImage asset={previewImage.asset} assetId={previewImage.asset.id} alt="生成图预览" eager variant="original" />
            <figcaption>
              <div>
                <strong>Panel {previewPanel?.panel_order ?? previewIndex + 1}</strong>
                {previewImage ? (
                  <div className="preview-meta-actions">
                    <button
                      type="button"
                      className="ghost-button"
                      disabled={loadingPanelDebugId === previewImage.panel_id}
                      onClick={() =>
                        openImagePromptPreview(
                          previewImage.panel_id,
                          previewImage.id,
                          `Panel ${previewPanel?.panel_order ?? previewIndex + 1} 生图提示词`,
                        )
                      }
                    >
                      {loadingPanelDebugId === previewImage.panel_id ? <Loader2 size={15} className="spin" /> : <FileText size={15} />}
                      查看生图提示词
                    </button>
                    {previewPromptText ? <p>提示词已加载，可点击查看完整内容。</p> : null}
                  </div>
                ) : null}
              </div>
              <div className="preview-actions">
                <button type="button" className="secondary-button" onClick={downloadPreviewImage}>
                  <Download size={16} />
                  下载单图
                </button>
                <button type="button" className="secondary-button" onClick={openPreviewImage}>
                  <ArrowUpRight size={16} />
                  打开原图
                </button>
              </div>
            </figcaption>
          </figure>
          <button type="button" className="modal-nav right" aria-label="下一张图片" disabled={previewItems.length <= 1} onClick={(event) => { event.stopPropagation(); showPreviewOffset(1); }}>
            <ChevronRight size={22} />
          </button>
        </div>
      ) : null}

      {previewReference ? (
        <div className="image-modal" onClick={() => setPreviewReferenceId(null)}>
          <button ref={previewCloseRef} type="button" className="modal-close" aria-label="关闭参考图预览" onClick={() => setPreviewReferenceId(null)}>
            <X size={18} />
          </button>
          <button type="button" className="modal-nav left" aria-label="上一张参考图" disabled={referencePreviewItems.length <= 1} onClick={(event) => { event.stopPropagation(); showReferencePreviewOffset(-1); }}>
            <ChevronLeft size={22} />
          </button>
          <figure className="image-preview-frame reference-preview-frame" onClick={(event) => event.stopPropagation()}>
            <LazyAssetImage asset={previewReference.asset} assetId={previewReference.asset.id} alt={`${previewReference.name}参考图预览`} eager variant="original" />
            <figcaption>
              <div>
                <strong>{previewReference.name}</strong>
                {previewReference.age_stage ? <p>{previewReference.age_stage}</p> : null}
              </div>
              <div className="preview-actions">
                <button type="button" className="secondary-button" onClick={downloadPreviewReference}>
                  <Download size={16} />
                  下载参考图
                </button>
                <button type="button" className="secondary-button" onClick={openPreviewReference}>
                  <ArrowUpRight size={16} />
                  打开原图
                </button>
              </div>
            </figcaption>
          </figure>
          <button type="button" className="modal-nav right" aria-label="下一张参考图" disabled={referencePreviewItems.length <= 1} onClick={(event) => { event.stopPropagation(); showReferencePreviewOffset(1); }}>
            <ChevronRight size={22} />
          </button>
        </div>
      ) : null}

      {promptPreview ? (
        <div className="prompt-modal-backdrop" onClick={() => setPromptPreview(null)}>
          <section className="prompt-modal" role="dialog" aria-modal="true" aria-labelledby="prompt-preview-title" onClick={(event) => event.stopPropagation()}>
            <div className="prompt-modal-head">
              <div>
                <span>生图提示词</span>
                <h2 id="prompt-preview-title">{promptPreview.title}</h2>
              </div>
              <button type="button" className="icon-button" aria-label="关闭提示词" onClick={() => setPromptPreview(null)}>
                <X size={18} />
              </button>
            </div>
            <pre>{promptPreview.text}</pre>
          </section>
        </div>
      ) : null}
    </section>
  );
}

function AudioReferencesView({ user }: { user: User }) {
  const [items, setItems] = useState<AudioReference[]>([]);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const [pageInfo, setPageInfo] = useState<{ next_cursor: string | null; has_more: boolean } | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [selectedAudioFile, setSelectedAudioFile] = useState<File | null>(null);
  const [transcribing, setTranscribing] = useState(false);
  const [transcribedText, setTranscribedText] = useState("");
  const [transcriptionError, setTranscriptionError] = useState("");

  async function refresh(nextCursor = cursor) {
    setLoading(true);
    try {
      const result = await api.audioReferences({ query, cursor: nextCursor, limit: 10 });
      setItems(result.items);
      setPageInfo(result.page);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "音频参考加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh(null);
  }, []);

  async function submitSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCursor(null);
    setCursorStack([]);
    await refresh(null);
  }

  async function createAudioReference(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (!selectedAudioFile || selectedAudioFile.size <= 0) {
      setMessage("请选择音频文件");
      return;
    }
    if (!transcribedText.trim()) {
      setMessage("请等待本地转写完成后再保存");
      return;
    }
    try {
      setCreating(true);
      await api.createAudioReference({
        name: String(form.get("name") || "").trim(),
        description: String(form.get("description") || "").trim(),
        reference_text: transcribedText.trim(),
        file: selectedAudioFile,
      });
      closeCreateAudioReference();
      setCursor(null);
      setCursorStack([]);
      setMessage("音频参考已保存");
      await refresh(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "音频参考保存失败");
    } finally {
      setCreating(false);
    }
  }

  function closeCreateAudioReference() {
    setCreateOpen(false);
    setSelectedAudioFile(null);
    setTranscribedText("");
    setTranscriptionError("");
    setTranscribing(false);
  }

  function openCreateAudioReference() {
    setSelectedAudioFile(null);
    setTranscribedText("");
    setTranscriptionError("");
    setTranscribing(false);
    setCreateOpen(true);
  }

  async function transcribeSelectedAudio(file: File) {
    setSelectedAudioFile(file);
    setTranscribedText("");
    setTranscriptionError("");
    if (file.size <= 0) {
      setTranscriptionError("文件内容不能为空");
      return;
    }
    try {
      setTranscribing(true);
      const result = await api.transcribeAudioReference(file);
      setTranscribedText(result.text);
      setTranscriptionError("");
    } catch (error) {
      setTranscriptionError(error instanceof Error ? error.message : "本地转写失败");
    } finally {
      setTranscribing(false);
    }
  }

  async function deleteAudioReference(id: string) {
    try {
      await api.deleteAudioReference(id);
      setMessage("音频参考已删除");
      await refresh(cursor);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "音频参考删除失败");
    }
  }

  function nextPage() {
    if (!pageInfo?.next_cursor) return;
    setCursorStack((current) => [...current, cursor ?? ""]);
    setCursor(pageInfo.next_cursor);
    void refresh(pageInfo.next_cursor);
  }

  function previousPage() {
    const previous = cursorStack[cursorStack.length - 1];
    setCursorStack((current) => current.slice(0, -1));
    setCursor(previous || null);
    void refresh(previous || null);
  }

  return (
    <section className="page tasks-workspace">
      <header className="page-header">
        <div>
          <h1>音频管理</h1>
          <p>管理视频任务可选择的参考音频。</p>
        </div>
        <button type="button" onClick={openCreateAudioReference}>
          <Plus size={18} />
          上传音频
        </button>
      </header>

      <form className="task-toolbar" onSubmit={submitSearch}>
        <label>
          <Search size={16} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索名称或描述" />
        </label>
        <button type="submit" className="secondary-button">搜索</button>
      </form>
      {message ? <div className={message.includes("失败") ? "error" : "form-message"}>{message}</div> : null}

      <section className="task-project-list single-column-list">
        <div className="task-list-head audio-list-head">
          <span>音频</span>
          <span>归属</span>
          <span>创建</span>
          <span>操作</span>
        </div>
        {loading ? <div className="empty">正在加载音频参考</div> : null}
        {!loading && items.length === 0 ? <div className="empty">还没有音频参考。</div> : null}
        {items.map((item) => (
          <article key={item.id} className="task-project-row audio-reference-row">
            <div className="task-story-cell">
              <Volume2 size={18} />
              <div>
                <strong>{item.name}</strong>
                <p>{item.description || item.asset.original_filename || "未填写描述"}</p>
                <audio src={assetUrl(item.asset)} controls />
              </div>
            </div>
            <span>{user.role === "admin" ? item.owner_display_name || item.owner_email || shortId(item.owner_user_id) : "我的音频"}</span>
            <span>{formatDateTime(item.created_at)}</span>
            <span className="row-actions">
              <button type="button" className="ghost-button" onClick={() => deleteAudioReference(item.id)}>
                <Trash2 size={15} />
                删除
              </button>
            </span>
          </article>
        ))}
        <div className="pagination-bar">
          <button className="icon-button" aria-label="上一页" disabled={cursorStack.length === 0} onClick={previousPage}>
            <ChevronLeft size={16} />
          </button>
          <span>{cursor ? `第 ${Math.floor(Number(cursor) / 10) + 1} 页` : "第 1 页"}</span>
          <button className="icon-button" aria-label="下一页" disabled={!pageInfo?.has_more} onClick={nextPage}>
            <ChevronRight size={16} />
          </button>
        </div>
      </section>

      {createOpen ? (
        <div className="task-create-backdrop" onClick={closeCreateAudioReference}>
          <section className="task-create-modal compact-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="drawer-head">
              <div>
                <h2>上传音频参考</h2>
                <p>保存后可在创建视频任务时选择。</p>
              </div>
              <button type="button" className="icon-button" aria-label="关闭" onClick={closeCreateAudioReference}>
                <X size={18} />
              </button>
            </div>
            <form className="task-create-form" onSubmit={createAudioReference}>
              <label>名称<input name="name" required maxLength={120} placeholder="例如 温柔女声参考" /></label>
              <label>描述<textarea name="description" maxLength={500} placeholder="音色、语速或适用内容" /></label>
              <label>
                音频文件
                <input
                  name="file"
                  type="file"
                  accept="audio/*,video/mp4"
                  required
                  onChange={(event) => {
                    const file = event.currentTarget.files?.[0];
                    if (file) void transcribeSelectedAudio(file);
                  }}
                />
              </label>
              {transcribing ? (
                <div className="form-message inline-status"><Loader2 size={16} className="spin" />正在本地转写参考文本</div>
              ) : null}
              {transcriptionError ? <div className="error">{transcriptionError}</div> : null}
              {transcribedText ? (
                <label>
                  自动识别文本
                  <textarea value={transcribedText} readOnly rows={4} />
                </label>
              ) : null}
              <div className="drawer-actions">
                <button type="button" className="ghost-button" onClick={closeCreateAudioReference}>取消</button>
                <button type="submit" disabled={creating || transcribing || !transcribedText.trim()}>
                  {creating ? <Loader2 size={17} className="spin" /> : <Upload size={17} />}
                  保存音频
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </section>
  );
}

function VideoTasksView({
  user,
  routeVideoTaskId,
  onNavigatePath,
}: {
  user: User;
  routeVideoTaskId: string | null;
  onNavigatePath: (path: string, options?: { replace?: boolean }) => void;
}) {
  const [items, setItems] = useState<VideoTaskSummary[]>([]);
  const [selected, setSelected] = useState<VideoTask | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<VideoTaskStatus | "all">("all");
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const [pageInfo, setPageInfo] = useState<{ next_cursor: string | null; has_more: boolean } | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [styles, setStyles] = useState<Style[]>([]);
  const [audioReferences, setAudioReferences] = useState<AudioReference[]>([]);
  const [countMode, setCountMode] = useState<"auto" | "fixed">("auto");

  async function refresh(nextCursor = cursor) {
    setLoading(true);
    try {
      const result = await api.videoTasks({ query, status, cursor: nextCursor, limit: 10 });
      setItems(result.items);
      setPageInfo(result.page);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "视频任务加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadCreateOptions() {
    const [styleResult, audioResult] = await Promise.all([
      api.styles({ status: "active" }),
      api.audioReferences({ limit: 100 }),
    ]);
    setStyles(styleResult.items);
    setAudioReferences(audioResult.items);
  }

  useEffect(() => {
    void refresh(null);
    void loadCreateOptions().catch((error) => setMessage(error instanceof Error ? error.message : "创建选项加载失败"));
  }, []);

  useEffect(() => {
    if (!routeVideoTaskId) {
      setSelected(null);
      return;
    }
    api
      .videoTask(routeVideoTaskId)
      .then(setSelected)
      .catch((error) => setMessage(error instanceof Error ? error.message : "视频任务详情加载失败"));
  }, [routeVideoTaskId]);

  async function submitSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCursor(null);
    setCursorStack([]);
    await refresh(null);
  }

  async function createVideoTask(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const originalText = String(form.get("original_text") || "").trim();
    const styleId = String(form.get("style_id") || "").trim();
    const audioReferenceId = String(form.get("audio_reference_id") || "").trim();
    const requested = Number(form.get("requested_image_count"));
    if (!originalText || !styleId || !audioReferenceId) {
      setMessage("请填写故事，并选择风格和参考音频");
      return;
    }
    try {
      setCreating(true);
      const task = await api.createVideoTask({
        original_text: originalText,
        image_count_mode: countMode,
        requested_image_count: countMode === "fixed" ? requested : null,
        style_id: styleId,
        audio_reference_id: audioReferenceId,
        use_character_references: true,
        last_panel_real_photo: false,
      });
      setCreateOpen(false);
      setMessage("视频任务已创建，正在生成上游图片");
      onNavigatePath(`${viewRoutes.videoTasks}/${encodeURIComponent(task.id)}`);
      await refresh(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "视频任务创建失败");
    } finally {
      setCreating(false);
    }
  }

  function selectVideoTask(id: string) {
    onNavigatePath(`${viewRoutes.videoTasks}/${encodeURIComponent(id)}`);
  }

  function closeDetail() {
    setSelected(null);
    onNavigatePath(viewRoutes.videoTasks);
  }

  function nextPage() {
    if (!pageInfo?.next_cursor) return;
    setCursorStack((current) => [...current, cursor ?? ""]);
    setCursor(pageInfo.next_cursor);
    void refresh(pageInfo.next_cursor);
  }

  function previousPage() {
    const previous = cursorStack[cursorStack.length - 1];
    setCursorStack((current) => current.slice(0, -1));
    setCursor(previous || null);
    void refresh(previous || null);
  }

  return (
    <section className="page tasks-workspace">
      <header className="page-header">
        <div>
          <h1>视频任务</h1>
          <p>输入故事，复用现有图片任务生成分镜图片，再承接旁白音频和图文视频生成。</p>
        </div>
        <button type="button" onClick={() => setCreateOpen(true)}>
          <Plus size={18} />
          创建视频任务
        </button>
      </header>

      <form className="task-toolbar" onSubmit={submitSearch}>
        <label>
          <Search size={16} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索故事" />
        </label>
        <label>
          <Filter size={16} />
          <select value={status} onChange={(event) => setStatus(event.target.value as VideoTaskStatus | "all")}>
            {videoTaskStatusOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <button type="submit" className="secondary-button">筛选</button>
      </form>
      {message ? <div className={message.includes("失败") ? "error" : "form-message"}>{message}</div> : null}

      <section className="task-project-list">
        <div className="task-list-head video-list-head">
          <span>故事</span>
          <span>上游图片</span>
          <span>音频</span>
          <span>状态</span>
          <span>创建</span>
        </div>
        {loading ? <div className="empty">正在加载视频任务</div> : null}
        {!loading && items.length === 0 ? <div className="empty">还没有视频任务。</div> : null}
        {items.map((item) => (
          <button type="button" key={item.id} className={`task-project-row video-task-row ${selected?.id === item.id ? "selected" : ""}`} onClick={() => selectVideoTask(item.id)}>
            <div className="task-story-cell">
              <span className={`task-dot ${item.status}`} />
              <div>
                <strong>{item.display_title}</strong>
                <p>{item.original_text_preview}</p>
                {user.role === "admin" ? <small>{item.owner_display_name || item.owner_email || shortId(item.owner_user_id)}</small> : null}
              </div>
            </div>
            <div className="thumb-strip">
              {item.source_task.preview_images.map((image) => (
                <LazyAssetImage key={image.id} asset={image.asset} assetId={image.asset.id} alt={item.display_title} />
              ))}
              {item.source_task.preview_images.length === 0 ? <span className="thumb-empty">等待图片</span> : null}
            </div>
            <div className="task-style-cell">
              <strong>{item.audio_reference_name_snapshot}</strong>
              <small>{item.source_task.style_name_snapshot} · {item.source_task.style_aspect_ratio_snapshot}</small>
            </div>
            <div className="task-status-cell">
              <span className={`status-pill ${item.status}`}>{videoTaskStatusLabel(item.status)}</span>
              <small>{videoTaskStepLabel(item.current_step)} · 图片任务 {taskStatusLabel(item.source_task.status)}{item.video_provider_status ? ` · 渲染 ${item.video_provider_status}` : ""}</small>
            </div>
            <span>{formatDateTime(item.created_at)}</span>
          </button>
        ))}
        <div className="pagination-bar">
          <button className="icon-button" aria-label="上一页" disabled={cursorStack.length === 0} onClick={previousPage}><ChevronLeft size={16} /></button>
          <span>{cursor ? `第 ${Math.floor(Number(cursor) / 10) + 1} 页` : "第 1 页"}</span>
          <button className="icon-button" aria-label="下一页" disabled={!pageInfo?.has_more} onClick={nextPage}><ChevronRight size={16} /></button>
        </div>
      </section>

      {selected ? (
        <div className="task-detail-backdrop" onClick={closeDetail}>
          <aside className="task-detail-drawer" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="detail-drawer-head">
              <div>
                <span>视频任务详情</span>
                <strong>{selected.display_title}</strong>
              </div>
              <button type="button" className="icon-button" aria-label="关闭详情" onClick={closeDetail}><X size={18} /></button>
            </div>
            <div className="task-inspector">
              <section className="detail-head">
                <div>
                  <span className={`status-pill ${selected.status}`}>{videoTaskStatusLabel(selected.status)}</span>
                  <h2>{selected.display_title}</h2>
                  <p>{videoTaskStepLabel(selected.current_step)} · 创建于 {formatDateTime(selected.created_at)}</p>
                </div>
                {selected.error_message ? <p className="error">{selected.error_message}</p> : null}
              </section>
              <section className="story-panel">
                <h2>原始故事</h2>
                <p>{selected.original_text}</p>
              </section>
              <section className="story-panel">
                <h2>参考音频</h2>
                <p>{selected.audio_reference_name_snapshot}</p>
                <audio src={assetUrl(selected.audio_reference_asset)} controls />
                {selected.voice_provider_snapshot || selected.voice_model_snapshot ? (
                  <small>{selected.voice_provider_snapshot || "voice"} · {selected.voice_model_snapshot || "默认模型"}</small>
                ) : null}
              </section>
              <section className="story-panel">
                <h2>旁白音频</h2>
                {selected.audio_segments.length === 0 ? <p>等待生成旁白音频。</p> : null}
                <div className="audio-segment-list">
                  {selected.audio_segments.map((segment) => (
                    <article key={segment.id} className="audio-segment-row">
                      <div>
                        <strong>第 {segment.panel_order} 段</strong>
                        <p>{segment.narration_text}</p>
                      </div>
                      <audio src={assetUrl(segment.asset)} controls />
                    </article>
                  ))}
                </div>
              </section>
              <section className="story-panel">
                <h2>最终视频</h2>
                {selected.output_video_asset ? (
                  <video src={assetUrl(selected.output_video_asset)} controls className="video-output-player" />
                ) : (
                  <p>{selected.video_provider_job_id ? `渲染任务 ${selected.video_provider_job_id}：${selected.video_provider_status || "处理中"}` : "等待提交图文视频生成服务。"}</p>
                )}
              </section>
              <section className="progress-panel">
                <div>
                  <strong>上游图片任务：{taskStatusLabel(selected.source_task.status)}</strong>
                  <span>{selected.source_task.progress_current}/{selected.source_task.progress_total}</span>
                </div>
                <div className="progress-line large">
                  <span style={{ width: `${selected.source_task.progress_total ? Math.round((selected.source_task.progress_current / selected.source_task.progress_total) * 100) : 0}%` }} />
                </div>
                {selected.source_task.error_message ? <p className="error">{selected.source_task.error_message}</p> : null}
              </section>
              <section className="panel-wall">
                <div className="editor-title">
                  <div>
                    <h2>已生成图片</h2>
                    <p>视频任务使用这些上游图片和对应旁白继续生成音频与视频。</p>
                  </div>
                  <button type="button" className="secondary-button" onClick={() => onNavigatePath(`${viewRoutes.tasks}/${encodeURIComponent(selected.source_task.id)}`)}>
                    <ArrowUpRight size={16} />
                    打开图片任务
                  </button>
                </div>
                <div className="task-image-grid">
                  {selected.source_task.preview_images.length === 0 ? <div className="empty mini">等待上游图片生成</div> : null}
                  {selected.source_task.preview_images.map((image) => (
                    <article key={image.id} className="panel-card">
                      <div className="poster">
                        <LazyAssetImage asset={image.asset} assetId={image.asset.id} alt={selected.display_title} />
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            </div>
          </aside>
        </div>
      ) : null}

      {createOpen ? (
        <div className="task-create-backdrop" onClick={() => setCreateOpen(false)}>
          <section className="task-create-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="drawer-head">
              <div>
                <h2>创建视频任务</h2>
                <p>视频任务会先创建一个真实图片任务，等待图片成功后再进入音频和视频阶段。</p>
              </div>
              <button type="button" className="icon-button" aria-label="关闭" onClick={() => setCreateOpen(false)}><X size={18} /></button>
            </div>
            <form className="task-create-form" onSubmit={createVideoTask}>
              <label>故事正文<textarea name="original_text" required autoFocus placeholder="只输入故事正文" /></label>
              <section className="create-section">
                <div className="section-label">图片数量</div>
                <div className="segmented-control">
                  <button type="button" className={countMode === "auto" ? "active" : ""} onClick={() => setCountMode("auto")}>自动判断</button>
                  <button type="button" className={countMode === "fixed" ? "active" : ""} onClick={() => setCountMode("fixed")}>固定数量</button>
                </div>
                {countMode === "fixed" ? <label>图片数量<input name="requested_image_count" type="number" min="1" max="80" required /></label> : null}
              </section>
              <label>画风<select name="style_id" required defaultValue="">
                <option value="">选择画风</option>
                {styles.map((style) => <option key={style.id} value={style.id}>{style.name}</option>)}
              </select></label>
              <label>参考音频<select name="audio_reference_id" required defaultValue="">
                <option value="">选择参考音频</option>
                {audioReferences.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select></label>
              {audioReferences.length === 0 ? <p className="field-hint">还没有音频参考，请先到音频管理上传。</p> : null}
              <div className="drawer-actions">
                <button type="button" className="ghost-button" onClick={() => setCreateOpen(false)}>取消</button>
                <button type="submit" disabled={creating || styles.length === 0 || audioReferences.length === 0}>
                  {creating ? <Loader2 size={17} className="spin" /> : <Plus size={17} />}
                  创建视频任务
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </section>
  );
}

function ContentExtractionView({
  user,
  onNavigatePath,
}: {
  user: User;
  onNavigatePath: (path: string, options?: { replace?: boolean }) => void;
}) {
  const [rawInput, setRawInput] = useState("");
  const [current, setCurrent] = useState<ContentExtraction | null>(null);
  const [records, setRecords] = useState<ContentExtractionSummary[]>([]);
  const [health, setHealth] = useState<ContentExtractionHealth | null>(null);
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [mediaTypeFilter, setMediaTypeFilter] = useState("");
  const [resultStatusFilter, setResultStatusFilter] = useState("");
  const [message, setMessage] = useState("");
  const [loadingRecords, setLoadingRecords] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [mediaExpanded, setMediaExpanded] = useState(false);
  const [previewMediaId, setPreviewMediaId] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const [pageInfo, setPageInfo] = useState<{ next_cursor: string | null; has_more: boolean } | null>(null);
  const previewCloseRef = useRef<HTMLButtonElement | null>(null);

  const sourceMedia = useMemo(
    () => (current?.media ?? []).filter((item) => item.media_kind === "image" || item.media_kind === "video"),
    [current],
  );
  const imageMedia = useMemo(
    () => sourceMedia.filter((item): item is ContentExtractionMedia & { media_kind: "image" } => item.media_kind === "image"),
    [sourceMedia],
  );
  const audioMedia = useMemo(() => (current?.media ?? []).filter((item) => item.media_kind === "audio"), [current]);
  const visibleMedia = mediaExpanded ? sourceMedia : sourceMedia.slice(0, 3);
  const previewIndex = imageMedia.findIndex((item) => item.id === previewMediaId);
  const previewMedia = previewIndex >= 0 ? imageMedia[previewIndex] : null;
  const isGallery = current?.media_type === "gallery" || imageMedia.length > 0;
  const isVideo = current?.media_type === "video" || sourceMedia.some((item) => item.media_kind === "video");
  const currentProcessing = current?.processing_status === "processing";
  const currentFailed = current?.processing_status === "failed";

  useEffect(() => {
    refreshRecords();
  }, [query, cursor, mediaTypeFilter, resultStatusFilter]);

  useEffect(() => {
    if (!records.some((record) => record.processing_status === "processing" || record.task_create_status === "pending")) return;
    const timer = window.setTimeout(() => {
      refreshRecords();
    }, 3500);
    return () => window.clearTimeout(timer);
  }, [records, query, cursor, mediaTypeFilter, resultStatusFilter]);

  useEffect(() => {
    if (!current || (current.processing_status !== "processing" && current.task_create_status !== "pending")) return;
    const timer = window.setTimeout(async () => {
      try {
        const result = await api.contentExtraction(current.id);
        setCurrent(result);
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "内容提取详情刷新失败");
      }
    }, 3500);
    return () => window.clearTimeout(timer);
  }, [current?.id, current?.processing_status, current?.task_create_status, current?.updated_at]);

  useEffect(() => {
    api
      .contentExtractionHealth()
      .then(setHealth)
      .catch((error) => setMessage(error instanceof Error ? error.message : "抖音下载服务不可用"));
  }, []);

  useEffect(() => {
    if (!previewMediaId) return;
    if (!imageMedia.some((item) => item.id === previewMediaId)) {
      setPreviewMediaId(null);
    }
  }, [imageMedia, previewMediaId]);

  useEffect(() => {
    if (!previewMediaId) return;
    previewCloseRef.current?.focus();

    function handlePreviewKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setPreviewMediaId(null);
      }
      if (event.key === "ArrowLeft") {
        showPreviewOffset(-1);
      }
      if (event.key === "ArrowRight") {
        showPreviewOffset(1);
      }
    }

    window.addEventListener("keydown", handlePreviewKey);
    return () => window.removeEventListener("keydown", handlePreviewKey);
  }, [previewMediaId, imageMedia, previewIndex]);

  async function refreshRecords() {
    try {
      setLoadingRecords(true);
      const result = await api.contentExtractions({
        query,
        cursor,
        limit: 10,
        media_type: mediaTypeFilter || undefined,
        result_status: resultStatusFilter || undefined,
      });
      setRecords(result.items);
      setPageInfo(result.page);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "内容提取记录加载失败");
    } finally {
      setLoadingRecords(false);
    }
  }

  async function processContent(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = rawInput.trim();
    if (!value) {
      setMessage("请输入抖音分享文本或链接");
      return;
    }
    try {
      setProcessing(true);
      setMessage("任务已提交，正在解析下载并按图片顺序提取漫画内容...");
      setCreateOpen(false);
      await api.processContentExtraction({ raw_input: value });
      setCursor(null);
      setCursorStack([]);
      setRawInput("");
      setMessage("任务已提交，可在列表查看处理状态");
      const result = await api.contentExtractions({
        query,
        cursor: null,
        limit: 10,
        media_type: mediaTypeFilter || undefined,
        result_status: resultStatusFilter || undefined,
      });
      setRecords(result.items);
      setPageInfo(result.page);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "提交内容提取任务失败");
    } finally {
      setProcessing(false);
    }
  }

  async function extractText() {
    if (!current) {
      setMessage("请先解析并下载内容");
      return;
    }
    try {
      setExtracting(true);
      setMessage("正在按图片顺序提交给 AI 提取漫画内容，请稍候...");
      const result = await api.extractContentText(current.id);
      setCurrent(result);
      setMessage("内容提取完成");
      await refreshRecords();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "提取文案失败");
    } finally {
      setExtracting(false);
    }
  }

  async function selectRecord(id: string) {
    try {
      setLoadingDetail(true);
      const result = await api.contentExtraction(id);
      setCurrent(result);
      setRawInput(result.raw_input);
      setDetailOpen(true);
      setMediaExpanded(false);
      setPreviewMediaId(null);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "记录加载失败");
    } finally {
      setLoadingDetail(false);
    }
  }

  async function copyExtractedText() {
    if (!current?.extracted_text) return;
    await navigator.clipboard.writeText(current.extracted_text);
    setMessage("内容提取结果已复制");
  }

  function submitExtractedAsTask() {
    if (!current?.extracted_text?.trim()) {
      setMessage("暂无内容提取结果可提交");
      return;
    }
    window.sessionStorage.setItem(
      CONTENT_EXTRACTION_TASK_DRAFT_KEY,
      JSON.stringify({
        content_extraction_id: current.id,
        original_text: current.extracted_text,
      }),
    );
    onNavigatePath(viewRoutes.tasks);
  }

  function openLinkedTask(taskId: string) {
    setDetailOpen(false);
    onNavigatePath(`${viewRoutes.tasks}/${encodeURIComponent(taskId)}`);
  }

  function applyRecordSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCursor(null);
    setCursorStack([]);
    setQuery(queryInput.trim());
  }

  function goNextPage() {
    if (!pageInfo?.next_cursor) return;
    setCursorStack((items) => [...items, cursor ?? ""]);
    setCursor(pageInfo.next_cursor);
  }

  function goPreviousPage() {
    setCursorStack((items) => {
      const next = [...items];
      const previous = next.pop() ?? "";
      setCursor(previous || null);
      return next;
    });
  }

  function showPreviewOffset(offset: number) {
    if (!imageMedia.length) return;
    const currentIndex = Math.max(0, previewIndex);
    const nextIndex = (currentIndex + offset + imageMedia.length) % imageMedia.length;
    setPreviewMediaId(imageMedia[nextIndex].id);
  }

  function downloadPreviewMedia() {
    if (!previewMedia) return;
    window.location.href = assetUrl(previewMedia.asset, "original");
  }

  function openPreviewMedia() {
    if (!previewMedia) return;
    window.open(assetUrl(previewMedia.asset, "original"), "_blank", "noopener,noreferrer");
  }

  function resetFilters() {
    setQueryInput("");
    setQuery("");
    setMediaTypeFilter("");
    setResultStatusFilter("");
    setCursor(null);
    setCursorStack([]);
  }

  function recordStatusLabel(record: ContentExtractionSummary) {
    if (record.processing_status === "processing") return "处理中";
    if (record.processing_status === "failed") return "失败";
    if (record.has_extracted_text) return "已提取";
    return "已下载";
  }

  function recordStatusClass(record: ContentExtractionSummary) {
    if (record.processing_status === "processing") return "running";
    if (record.processing_status === "failed") return "failed";
    if (record.has_extracted_text) return "active";
    return "";
  }

  return (
    <section className="page content-extraction-page">
      <header className="page-header">
        <div>
          <h1>内容提取</h1>
          <p>列表查看历史任务，创建时一键完成解析下载，并把图文图片按顺序提交给 AI 提取连续漫画内容。</p>
        </div>
        <div className="content-header-actions">
          <div className={`health-pill ${health?.ok ? "ok" : ""}`}>
            <span />
            {health?.ok ? `下载服务可用 · ${health.service_base_url}` : "下载服务待检查"}
          </div>
          <button type="button" onClick={() => setCreateOpen(true)}>
            <Plus size={16} />
            创建任务
          </button>
        </div>
      </header>

      {message ? <p className="form-message">{message}</p> : null}

      <section className="panel content-list-panel">
        <form className="content-list-toolbar" onSubmit={applyRecordSearch}>
          <div className="content-search-control">
            <Search size={16} />
            <input value={queryInput} onChange={(event) => setQueryInput(event.target.value)} placeholder="搜索链接、原始分享文本或内容提取结果" />
          </div>
          <select value={mediaTypeFilter} onChange={(event) => { setCursor(null); setCursorStack([]); setMediaTypeFilter(event.target.value); }}>
            <option value="">全部类型</option>
            <option value="gallery">图文</option>
            <option value="video">视频</option>
          </select>
          <select value={resultStatusFilter} onChange={(event) => { setCursor(null); setCursorStack([]); setResultStatusFilter(event.target.value); }}>
            <option value="">全部结果</option>
            <option value="processing">处理中</option>
            <option value="failed">失败</option>
            <option value="extracted">已提取</option>
            <option value="downloaded">仅下载</option>
          </select>
          <button type="submit" className="secondary-button">
            <Filter size={16} />
            筛选
          </button>
          <button type="button" className="secondary-button" onClick={resetFilters}>
            <RefreshCw size={16} />
            重置
          </button>
        </form>

        <div className="content-list-table">
          <div className="content-list-row header">
            <span>来源</span>
            <span>结果摘要</span>
            <span>媒体</span>
            <span>状态</span>
            <span>更新时间</span>
          </div>
          {loadingRecords ? <div className="empty mini">正在加载内容提取任务</div> : null}
          {!loadingRecords && records.length === 0 ? <div className="empty mini">暂无内容提取任务</div> : null}
          {records.map((record) => (
            <button
              type="button"
              key={record.id}
              className={`content-list-row ${current?.id === record.id ? "selected" : ""}`}
              onClick={() => selectRecord(record.id)}
              disabled={loadingDetail}
            >
              <span>
                <strong>{record.source_url}</strong>
                <em>{record.raw_input_preview || record.aweme_id || "未记录分享文本"}</em>
              </span>
              <span>
                <strong>
                  {record.processing_status === "processing"
                    ? "正在处理，完成后可打开详情"
	                      : record.processing_status === "failed"
	                        ? record.processing_error_message || "处理失败"
	                      : record.linked_task_id
	                        ? `已创建生图任务 ${shortId(record.linked_task_id)}`
	                        : record.task_create_status === "failed"
	                          ? record.task_create_error_message || "内容已提取，自动创建任务失败"
	                          : record.extracted_text_preview || "暂无结果摘要"}
	                </strong>
	                <em>{record.task_create_status === "pending" ? "正在自动创建生图任务" : "打开详情查看完整内容"}</em>
	              </span>
              <span>{record.media_type === "pending" ? "待识别" : record.media_type === "gallery" ? "图文" : record.media_type === "video" ? "视频" : record.media_type}</span>
              <span>
                <b className={`content-status-badge ${recordStatusClass(record)}`}>
                  {recordStatusLabel(record)}
                </b>
                <em>{record.media_count} 个媒体</em>
              </span>
              <span>{formatDateTime(record.updated_at)}</span>
            </button>
          ))}
        </div>

        <div className="pagination-bar compact">
          <button className="icon-button" type="button" aria-label="上一页" disabled={cursorStack.length === 0} onClick={goPreviousPage}>
            <ChevronLeft size={16} />
          </button>
          <span>{cursor ? `第 ${Math.floor(Number(cursor) / 10) + 1} 页` : "第 1 页"}</span>
          <button className="icon-button" type="button" aria-label="下一页" disabled={!pageInfo?.has_more} onClick={goNextPage}>
            <ChevronRight size={16} />
          </button>
        </div>
      </section>

      {createOpen ? (
        <div className="content-modal-backdrop" onClick={() => setCreateOpen(false)}>
          <section className="content-modal create" onClick={(event) => event.stopPropagation()}>
            <header className="content-modal-header">
              <div>
                <h2>创建内容提取任务</h2>
                <p>粘贴完整抖音分享文本或链接，后端会识别其中真实 URL。</p>
              </div>
              <button type="button" className="icon-button" aria-label="关闭创建任务" onClick={() => setCreateOpen(false)}>
                <X size={18} />
              </button>
            </header>
            <form onSubmit={processContent} className="content-download-form">
              <textarea
                value={rawInput}
                onChange={(event) => setRawInput(event.target.value)}
                placeholder="粘贴抖音分享文本或链接，例如 https://v.douyin.com/..."
                disabled={processing}
              />
              <div className="content-action-row">
                <button type="submit" disabled={processing}>
                  {processing ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
                  一键解析下载并提取内容
                </button>
                <span>下载完成后会先显示媒体；图文会整组按顺序提交给 AI，输出连贯的逐页内容。</span>
              </div>
            </form>
          </section>
        </div>
      ) : null}

      {detailOpen && current ? (
        <div className="content-modal-backdrop detail-backdrop" onClick={() => setDetailOpen(false)}>
          <section className="content-modal detail" onClick={(event) => event.stopPropagation()}>
            <header className="content-modal-header">
              <div>
                <h2>内容提取详情</h2>
                <p>{current.source_url}</p>
              </div>
              <div className="content-detail-actions">
                <button type="button" className="secondary-button" disabled={currentProcessing || extracting} onClick={extractText}>
                  {extracting ? <Loader2 size={16} className="spin" /> : <FileText size={16} />}
                  重新提取
                </button>
                <button type="button" className="icon-button" aria-label="关闭详情" onClick={() => setDetailOpen(false)}>
                  <X size={18} />
                </button>
              </div>
            </header>

            <div className="content-detail-grid">
              <section className="content-detail-main">
                <div className="content-section-title">
                  <h3>内容提取</h3>
                  <div className="content-detail-actions">
                    <button type="button" className="secondary-button" disabled={!current.extracted_text} onClick={copyExtractedText}>
                      复制内容
                    </button>
	                    <button type="button" disabled={!current.extracted_text} onClick={submitExtractedAsTask}>
	                      <Plus size={16} />
	                      提交任务
	                    </button>
	                    {current.linked_task_id ? (
	                      <button type="button" className="secondary-button" onClick={() => openLinkedTask(current.linked_task_id!)}>
	                        <ArrowUpRight size={16} />
	                        查看生图任务
	                      </button>
	                    ) : null}
	                  </div>
                </div>
                <div className="extracted-text-box detail">
                  {current.extracted_text ? (
                    <p>{current.extracted_text}</p>
                  ) : (
                    <div className="empty mini">
                      {currentProcessing ? "任务正在处理，完成后会显示内容提取结果" : currentFailed ? current.processing_error_message || "任务处理失败" : "暂无内容提取结果"}
                    </div>
                  )}
                </div>
              </section>

              <aside className="content-detail-side">
                <section>
                  <h3>任务信息</h3>
                  <div className="content-summary-grid detail">
                    <div>
                      <span>作品 ID</span>
                      <strong>{current.aweme_id ? shortId(current.aweme_id) : "暂无"}</strong>
                    </div>
                    <div>
                      <span>媒体类型</span>
                      <strong>{isGallery ? "图文" : isVideo ? "视频" : current.media_type}</strong>
                    </div>
                    <div>
                      <span>媒体数量</span>
                      <strong>{sourceMedia.length} 个</strong>
                    </div>
                    <div>
                      <span>音频</span>
                      <strong>{audioMedia.length ? "已生成" : "无"}</strong>
                    </div>
	                    <div>
	                      <span>处理状态</span>
	                      <strong>{current.processing_status === "processing" ? "处理中" : current.processing_status === "failed" ? "失败" : "已完成"}</strong>
	                    </div>
	                    <div>
	                      <span>自动任务</span>
	                      <strong>
	                        {current.linked_task_id
	                          ? `已创建 ${shortId(current.linked_task_id)}`
	                          : current.task_create_status === "pending"
	                            ? "创建中"
	                            : current.task_create_status === "failed"
	                              ? "创建失败"
	                              : "未启用"}
	                      </strong>
	                    </div>
	                  </div>
	                  {current.task_create_status === "failed" && current.task_create_error_message ? (
	                    <p className="form-message">{current.task_create_error_message}</p>
	                  ) : null}
	                </section>

                <section>
                  <div className="content-section-title compact">
                    <h3>下载媒体</h3>
                    <button type="button" className="secondary-button" disabled={sourceMedia.length <= 3} onClick={() => setMediaExpanded((value) => !value)}>
                      {mediaExpanded ? "收起" : "展开"}
                    </button>
                  </div>
                  <div className="content-media-preview">
                    {visibleMedia.length === 0 ? <div className="empty mini">暂无下载媒体</div> : null}
                    {visibleMedia.map((media) => (
                      <figure key={media.id} className={`content-media-card ${media.media_kind}`}>
                        {media.media_kind === "image" ? (
                          <button
                            type="button"
                            className="content-media-button"
                            aria-label={`放大预览媒体 ${media.display_order}`}
                            onClick={() => setPreviewMediaId(media.id)}
                          >
                            <LazyAssetImage asset={media.asset} assetId={media.asset.id} alt={`媒体 ${media.display_order}`} />
                            <Eye size={17} />
                          </button>
                        ) : (
                          <video src={assetUrl(media.asset, "original")} controls preload="metadata" />
                        )}
                        <figcaption>{media.display_order}</figcaption>
                      </figure>
                    ))}
                  </div>
                  {sourceMedia.length > visibleMedia.length ? (
                    <div className="content-fold-note">默认折叠 · 还有 {sourceMedia.length - visibleMedia.length} 个媒体</div>
                  ) : null}
                </section>

                <section>
                  <h3>原始输入</h3>
                  <div className="raw-input-box">{current.raw_input}</div>
                  <div className="content-result-meta">
                    <span>创建于 {formatDateTime(current.created_at)}</span>
                    <span>更新于 {formatDateTime(current.updated_at)}</span>
                  </div>
                </section>
              </aside>
            </div>
          </section>
        </div>
      ) : null}
      {previewMedia ? (
        <div className="image-modal" onClick={() => setPreviewMediaId(null)}>
          <button ref={previewCloseRef} type="button" className="modal-close" aria-label="关闭媒体预览" onClick={() => setPreviewMediaId(null)}>
            <X size={18} />
          </button>
          <button type="button" className="modal-nav left" aria-label="上一张图片" disabled={imageMedia.length <= 1} onClick={(event) => { event.stopPropagation(); showPreviewOffset(-1); }}>
            <ChevronLeft size={22} />
          </button>
          <figure className="image-preview-frame content-preview-frame" onClick={(event) => event.stopPropagation()}>
            <LazyAssetImage asset={previewMedia.asset} assetId={previewMedia.asset.id} alt={`媒体 ${previewMedia.display_order} 放大预览`} eager variant="original" />
            <figcaption>
              <div>
                <strong>媒体 {previewMedia.display_order}</strong>
                <p>{previewMedia.extracted_text || current?.source_url || ""}</p>
              </div>
              <div className="preview-actions">
                <button type="button" className="secondary-button" onClick={downloadPreviewMedia}>
                  <Download size={16} />
                  下载图片
                </button>
                <button type="button" className="secondary-button" onClick={openPreviewMedia}>
                  <ArrowUpRight size={16} />
                  打开原图
                </button>
              </div>
            </figcaption>
          </figure>
          <button type="button" className="modal-nav right" aria-label="下一张图片" disabled={imageMedia.length <= 1} onClick={(event) => { event.stopPropagation(); showPreviewOffset(1); }}>
            <ChevronRight size={22} />
          </button>
        </div>
      ) : null}
    </section>
  );
}

function CharactersView() {
  const [characters, setCharacters] = useState<UserCharacter[]>([]);
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [editingCharacter, setEditingCharacter] = useState<UserCharacter | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formPreviewUrl, setFormPreviewUrl] = useState("");

  async function loadCharacters() {
    try {
      setLoading(true);
      const result = await api.characters({ query, limit: 80 });
      setCharacters(result.items);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "角色加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadCharacters();
  }, [query]);

  useEffect(() => {
    if (!formPreviewUrl) return;
    return () => URL.revokeObjectURL(formPreviewUrl);
  }, [formPreviewUrl]);

  function closeCharacterForm() {
    setCreateOpen(false);
    setEditingCharacter(null);
    setFormPreviewUrl("");
  }

  function applyCharacterSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQuery(queryInput.trim());
  }

  async function saveCharacter(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    const description = String(form.get("description") ?? "").trim();
    const fileValue = form.get("file");
    const file = fileValue instanceof File && fileValue.size > 0 ? fileValue : null;
    if (!name) {
      setMessage("请输入角色名字");
      return;
    }
    if (!editingCharacter && !file) {
      setMessage("创建角色需要上传参考图");
      return;
    }
    try {
      setSaving(true);
      if (editingCharacter) {
        await api.updateCharacter(editingCharacter.id, { name, description, file });
        setMessage(description || !file ? "角色已更新" : "角色已更新，外观描述会在后台识别后自动补充");
      } else if (file) {
        await api.createCharacter({ name, description, file });
        setMessage(description ? "角色已创建" : "角色已创建，外观描述会在后台识别后自动补充");
      }
      setEditingCharacter(null);
      setCreateOpen(false);
      setFormPreviewUrl("");
      await loadCharacters();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  function describeCharacterFile(file: File | undefined) {
    setFormPreviewUrl(file ? URL.createObjectURL(file) : "");
    if (file) setMessage("参考图已选择，保存后会在后台识别外观描述");
  }

  async function deleteCharacter(character: UserCharacter) {
    if (!window.confirm(`删除角色「${character.name}」？历史任务会继续使用已保存快照。`)) return;
    try {
      await api.deleteCharacter(character.id);
      setMessage("角色已删除");
      await loadCharacters();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败");
    }
  }

  const formCharacter = editingCharacter;

  return (
    <section className="page characters-page">
      <header className="page-header">
        <div>
          <h1>角色管理</h1>
          <p>维护自己的固定角色形象。角色和参考图只对当前账号可见。</p>
        </div>
        <button onClick={() => setCreateOpen(true)}>
          <Plus size={18} />
          新建角色
        </button>
      </header>

      <form className="task-toolbar" onSubmit={applyCharacterSearch}>
        <label className="search-box">
          <Search size={18} />
          <input value={queryInput} onChange={(event) => setQueryInput(event.target.value)} placeholder="搜索角色名字或描述" />
        </label>
        <button type="submit" className="secondary-button">搜索</button>
        <button type="button" className="ghost-button" onClick={() => { setQueryInput(""); setQuery(""); }}>
          清空
        </button>
      </form>
      {message ? <p className="form-message">{message}</p> : null}
      {loading ? <div className="empty mini">正在加载角色</div> : null}
      {!loading && characters.length === 0 ? (
        <div className="empty">
          <div>
            <strong>{query ? "没有匹配的角色" : "还没有角色"}</strong>
            <p>{query ? "换个关键词再试。" : "创建一个角色后，可以在任务创建时快速绑定参考图。"}</p>
            <button type="button" onClick={() => setCreateOpen(true)}>
              <Plus size={18} />
              新建角色
            </button>
          </div>
        </div>
      ) : null}
      <div className="character-library-grid">
        {characters.map((character) => (
          <article key={character.id} className="character-library-card">
            <button type="button" className="character-library-image" onClick={() => setEditingCharacter(character)}>
              <LazyAssetImage
                asset={character.reference_asset}
                assetId={character.reference_asset.id}
                alt={character.name}
              />
            </button>
            <div>
              <strong>{character.name}</strong>
              <p>{character.description || "暂无描述"}</p>
              <small>更新于 {formatDateTime(character.updated_at)}</small>
            </div>
            <div className="row-actions">
              <button type="button" className="secondary-button" onClick={() => setEditingCharacter(character)}>
                <Pencil size={15} />
                编辑
              </button>
              <button type="button" className="ghost-button danger" onClick={() => deleteCharacter(character)}>
                <Trash2 size={15} />
                删除
              </button>
            </div>
          </article>
        ))}
      </div>

      {createOpen || editingCharacter ? (
        <div className="task-create-backdrop" onClick={closeCharacterForm}>
          <section className="character-create-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="drawer-head">
              <div>
                <h2>{formCharacter ? "编辑角色" : "新建角色"}</h2>
                <p>{formCharacter ? "更新后只影响之后创建的新任务。" : "上传一张参考图，之后创建任务时可以直接绑定。"}</p>
              </div>
              <button type="button" className="icon-button" aria-label="关闭角色表单" onClick={closeCharacterForm}>
                <X size={18} />
              </button>
            </div>
            <form className="form compact-form" onSubmit={saveCharacter}>
              <label>
                名字
                <input name="name" defaultValue={formCharacter?.name ?? ""} required />
              </label>
              <label>
                角色外观描述
                <textarea
                  name="description"
                  defaultValue={formCharacter?.description ?? ""}
                  placeholder="可手动填写；留空时保存后会在后台自动识别"
                />
                <small>这段描述会作为固定角色身份锚点保存；留空时不会阻塞保存，系统会后台识别并自动补充。</small>
              </label>
              {formCharacter ? (
                <div className="selected-style-preview compact">
                  <div className="selected-style-poster">
                    <LazyAssetImage
                      asset={formCharacter.reference_asset}
                      assetId={formCharacter.reference_asset.id}
                      alt={formCharacter.name}
                    />
                  </div>
                  <div>
                    <strong>当前参考图</strong>
                    <small>重新上传会替换后续任务使用的角色图。</small>
                  </div>
                </div>
              ) : null}
              <label>
                参考图
                <input
                  name="file"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  required={!formCharacter}
                  onChange={(event) => describeCharacterFile(event.currentTarget.files?.[0])}
                />
              </label>
              {formPreviewUrl ? (
                <div className="upload-preview-frame">
                  <img src={formPreviewUrl} alt="上传预览" />
                </div>
              ) : null}
              <div className="drawer-actions">
                <button type="button" className="ghost-button" onClick={closeCharacterForm}>
                  取消
                </button>
                <button type="submit" disabled={saving}>
                  {saving ? <Loader2 size={17} className="spin" /> : <Save size={17} />}
                  保存角色
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </section>
  );
}

function StylesView({ user, onCreditsChanged }: { user: User; onCreditsChanged: () => Promise<CreditOverview | null> }) {
  const [styles, setStyles] = useState<Style[]>([]);
  const [message, setMessage] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<Style["status"] | "all">("active");
  const [styleDrawerOpen, setStyleDrawerOpen] = useState(false);
  const [styleFormMode, setStyleFormMode] = useState<"create" | "edit">("create");
  const [editingStyleId, setEditingStyleId] = useState("");
  const [pendingReferenceFiles, setPendingReferenceFiles] = useState<File[]>([]);
  const [savingStyle, setSavingStyle] = useState(false);
  const [styleSavePhase, setStyleSavePhase] = useState("");
  const [uploadingStyleReferences, setUploadingStyleReferences] = useState(false);
  const [styleUploadPhase, setStyleUploadPhase] = useState("");
  const [stylePage, setStylePage] = useState<"library" | "test">("library");
  const [testingStyleId, setTestingStyleId] = useState("");
  const [styleTest, setStyleTest] = useState<StyleTest | null>(null);
  const [styleTestRunning, setStyleTestRunning] = useState(false);
  const activeCount = useMemo(() => styles.filter((style) => style.status === "active").length, [styles]);
  const editingStyle = useMemo(() => styles.find((style) => style.id === editingStyleId) ?? null, [editingStyleId, styles]);
  const testingStyle = useMemo(
    () => styles.find((style) => style.id === testingStyleId) ?? styles[0] ?? null,
    [testingStyleId, styles],
  );
  const styleBusy = savingStyle || uploadingStyleReferences;

  useEffect(() => {
    refresh();
  }, []);

  async function refresh(preferredStyleId?: string) {
    const result = await api.styles({ query, status });
    setStyles(result.items);
    if (preferredStyleId) {
      setEditingStyleId(preferredStyleId);
      setTestingStyleId(preferredStyleId);
      return;
    }
    if (!editingStyleId && result.items[0]) {
      setEditingStyleId(result.items[0].id);
    }
    if (!testingStyleId && result.items[0]) {
      setTestingStyleId(result.items[0].id);
    }
  }

  function startCreate() {
    if (styleBusy) return;
    setStyleFormMode("create");
    setEditingStyleId("");
    setPendingReferenceFiles([]);
    setMessage("");
    setStyleDrawerOpen(true);
  }

  function startEdit(style: Style) {
    if (styleBusy) return;
    setEditingStyleId(style.id);
    setStyleFormMode("edit");
    setPendingReferenceFiles([]);
    setMessage("");
    setStyleDrawerOpen(true);
  }

  function closeStyleDrawer() {
    if (styleBusy) {
      setMessage(styleSavePhase || styleUploadPhase || "正在保存或上传参考图，请等待完成");
      return;
    }
    setStyleDrawerOpen(false);
  }

  function openStyleTest(style: Style) {
    setTestingStyleId(style.id);
    setStyleTest(null);
    setStyleTestRunning(false);
    setMessage("");
    setStylePage("test");
  }

  async function createStyle(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const payload: Partial<Style> = {
      name: String(formData.get("name") ?? ""),
      status: String(formData.get("status") ?? "draft") as Style["status"],
      image_model_name: String(formData.get("image_model_name") ?? ""),
      aspect_ratio: String(formData.get("aspect_ratio") ?? "9:16"),
      style_reference_mode: String(formData.get("style_reference_mode") ?? "prompt") as Style["style_reference_mode"],
      style_prompt: String(formData.get("style_prompt") ?? ""),
      description: String(formData.get("description") ?? ""),
    };

    const selectedReferenceFiles = [...pendingReferenceFiles];
    const isEditMode = styleFormMode === "edit" && Boolean(editingStyle);

    try {
      setSavingStyle(true);
      setStyleSavePhase(isEditMode ? "正在保存风格..." : "正在创建风格...");
      const saved =
        isEditMode && editingStyle
          ? await api.updateStyle(editingStyle.id, payload)
          : await api.createStyle(payload);
      setEditingStyleId(saved.id);
      setTestingStyleId(saved.id);
      setStyleFormMode("edit");
      if (!isEditMode && selectedReferenceFiles.length > 0) {
        try {
          for (const [index, file] of selectedReferenceFiles.entries()) {
            setStyleSavePhase(`正在上传参考图 ${index + 1}/${selectedReferenceFiles.length}...`);
            await api.uploadStyleReferenceImage(saved.id, file);
          }
          setPendingReferenceFiles([]);
        } catch (uploadError) {
          await refresh(saved.id);
          setStyleDrawerOpen(true);
          setMessage(
            `风格已创建，但参考图上传失败：${uploadError instanceof Error ? uploadError.message : "上传失败"}`,
          );
          return;
        }
      }
      setStyleDrawerOpen(false);
      setMessage(
        isEditMode
          ? "风格已保存"
          : selectedReferenceFiles.length > 0
            ? "风格已创建，参考图已上传"
            : "风格已创建",
      );
      await refresh(saved.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSavingStyle(false);
      setStyleSavePhase("");
    }
  }

  async function deleteStyle(style: Style) {
    if (styleBusy) return;
    if (!window.confirm(`删除风格「${style.name}」？历史任务会保留已保存的风格快照。`)) {
      return;
    }
    try {
      await api.deleteStyle(style.id);
      setEditingStyleId("");
      if (testingStyleId === style.id) {
        setTestingStyleId("");
        setStylePage("library");
      }
      setStyleDrawerOpen(false);
      setMessage("风格已删除");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败");
    }
  }

  async function uploadReferences(event: React.ChangeEvent<HTMLInputElement>) {
    if (styleBusy) {
      event.currentTarget.value = "";
      return;
    }
    if (styleFormMode === "create") {
      setPendingReferenceFiles(Array.from(event.target.files ?? []));
      event.target.value = "";
      return;
    }
    if (!editingStyle || !event.target.files?.length) {
      return;
    }
    const input = event.currentTarget;
    const files = Array.from(input.files ?? []);
    if (files.length === 0) {
      input.value = "";
      return;
    }
    try {
      setUploadingStyleReferences(true);
      setMessage("");
      for (const [index, file] of files.entries()) {
        setStyleUploadPhase(`正在上传参考图 ${index + 1}/${files.length}...`);
        await api.uploadStyleReferenceImage(editingStyle.id, file);
      }
      setMessage(files.length > 1 ? `已上传 ${files.length} 张参考图` : "参考图已上传");
      await refresh(editingStyle.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "上传失败");
    } finally {
      setUploadingStyleReferences(false);
      setStyleUploadPhase("");
      input.value = "";
    }
  }

  async function deleteReference(referenceId: string) {
    if (styleBusy) return;
    if (!editingStyle) return;
    try {
      await api.deleteStyleReferenceImage(editingStyle.id, referenceId);
      setMessage("参考图已移除");
      await refresh(editingStyle.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除参考图失败");
    }
  }

  async function runStyleTest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!testingStyle || styleTestRunning) return;
    const formData = new FormData(event.currentTarget);
    setStyleTestRunning(true);
    setStyleTest(null);
    setMessage("测试图正在生成，请稍候...");
    try {
      const result = await api.createStyleTest(testingStyle.id, {
        test_text: String(formData.get("test_text") ?? ""),
      });
      setStyleTest(result);
      await onCreditsChanged();
      setMessage(result.status === "succeeded" ? "风格测试已完成" : result.error_message ?? "风格测试未成功");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "风格测试失败");
    } finally {
      setStyleTestRunning(false);
    }
  }

  const formStyle = styleFormMode === "edit" ? editingStyle : null;
  const pendingReferenceNames = pendingReferenceFiles.map((file) => file.name).join("、");

  if (stylePage === "test") {
    return (
      <section className="page style-test-page">
        <header className="page-header">
          <div>
            <button type="button" className="ghost-button back-button" onClick={() => setStylePage("library")}>
              <ChevronLeft size={16} />
              返回风格库
            </button>
            <h1>测试风格</h1>
            <p>{testingStyle ? `使用「${testingStyle.name}」生成一张测试图，比例由风格模板控制。` : "请选择一个风格后再测试。"}</p>
          </div>
        </header>

        {message ? <p className="form-message">{message}</p> : null}

        {testingStyle ? (
          <div className="style-test-layout">
            <section className="panel style-test-control">
              <div className="editor-title">
                <div>
                  <h2>{testingStyle.name}</h2>
                  <p>{testingStyle.description || "暂无描述"}</p>
                </div>
                <span className={`status-pill ${testingStyle.status}`}>{testingStyle.status}</span>
              </div>
              <div className="test-reference-strip">
                {stylePreviewAssets(testingStyle)
                  .slice(0, 6)
                  .map((asset) => (
                    <LazyAssetImage key={asset.id} asset={asset} assetId={asset.id} alt={testingStyle.name} />
                  ))}
                {testingStyle.reference_images.length === 0 ? <span>暂无参考图</span> : null}
              </div>
              <form className="test-form" onSubmit={runStyleTest}>
                <textarea name="test_text" placeholder="输入要测试的画面文本" required disabled={styleTestRunning} />
                <button type="submit" disabled={styleTestRunning}>
                  {styleTestRunning ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
                  {styleTestRunning ? "生成中..." : "生成测试图"}
                </button>
              </form>
            </section>

            <section className="panel style-test-output">
              <div className="editor-title">
                <div>
                  <h2>测试结果</h2>
                  <p>测试图使用当前风格参考方式，结果应与正式任务的风格输入保持一致。</p>
                </div>
                {styleTest ? <span className={`status-pill ${styleTest.status}`}>{styleTest.status}</span> : null}
              </div>
              {styleTestRunning ? (
                <div className="empty mini">
                  <Loader2 size={20} className="spin" />
                  正在生成测试图
                </div>
              ) : styleTest?.output_asset ? (
                <LazyAssetImage asset={styleTest.output_asset} assetId={styleTest.output_asset.id} alt="风格测试结果" eager variant="original" />
              ) : (
                <div className="empty mini">{styleTest?.error_message || "还没有测试结果"}</div>
              )}
            </section>
          </div>
        ) : (
          <div className="empty">暂无可测试风格。</div>
        )}
      </section>
    );
  }

  return (
    <section className="page style-workspace">
      <header className="page-header">
        <div>
          <h1>风格</h1>
          <p>共 {styles.length} 个风格，{activeCount} 个启用。每个风格可选择使用 Prompt 或参考图作为生图风格参考。</p>
        </div>
        <button onClick={startCreate}>
          <Plus size={18} />
          新建风格
        </button>
      </header>

      <div className="toolbar">
        <label className="search-box">
          <Search size={16} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索风格名称或描述" />
        </label>
        <select value={status} onChange={(event) => setStatus(event.target.value as Style["status"] | "all")}>
          <option value="all">全部状态</option>
          <option value="draft">草稿</option>
          <option value="active">启用</option>
          <option value="disabled">停用</option>
        </select>
        <button type="button" onClick={() => refresh()}>筛选</button>
      </div>

      {message ? <p className="form-message">{message}</p> : null}

      <div className="style-gallery">
        {styles.length === 0 ? <div className="empty">还没有风格。</div> : null}
        {styles.map((style) => {
          const cover = styleCover(style);
          const assets = stylePreviewAssets(style);
          return (
            <article className="style-card" key={style.id}>
              <div className="poster">
                {cover ? <LazyAssetImage asset={cover} assetId={cover.id} alt={style.name} /> : <span>模板比例</span>}
              </div>
              <div className="style-card-copy">
                <div className="style-row-title">
                  <div className="style-row-name">
                    <strong>{style.name}</strong>
                    <span className={`status-pill ${style.status}`}>{style.status}</span>
                  </div>
                  <button type="button" className="secondary-button style-inline-edit" onClick={() => startEdit(style)}>
                    <Pencil size={14} />
                    编辑模板
                  </button>
                </div>
                <p>{style.description || "暂无描述"}</p>
                <small>{styleReferenceModeLabels[style.style_reference_mode]} · {style.reference_images.length} 张参考图 · 比例 {style.aspect_ratio} · 模型 {style.image_model_name} · {style.last_tested_at ? `最近测试 ${formatDateTime(style.last_tested_at)}` : "未测试"}</small>
              </div>
              <div className="style-row-strip">
                {assets.slice(0, 5).map((asset) => (
                  <LazyAssetImage key={asset.id} asset={asset} assetId={asset.id} alt={style.name} />
                ))}
                {assets.length === 0 ? <span>无参考图</span> : null}
              </div>
              <div className="style-card-actions">
                <button type="button" onClick={() => openStyleTest(style)}>
                  测试
                </button>
              </div>
            </article>
          );
        })}
      </div>

      {styleDrawerOpen ? (
        <div className="drawer-backdrop" role="presentation" onMouseDown={closeStyleDrawer}>
          <aside className="task-create-drawer style-form-drawer" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <div className="drawer-head">
              <div>
                <h2>{styleFormMode === "edit" && formStyle ? "编辑风格" : "新建风格"}</h2>
                <p>{styleFormMode === "edit" && formStyle ? formStyle.name : "创建一个可复用的生图风格资产"}</p>
              </div>
              <button className="icon-button" type="button" onClick={closeStyleDrawer} disabled={styleBusy} aria-label="关闭">
                <X size={18} />
              </button>
            </div>
            <form key={`${styleFormMode}-${formStyle?.id ?? "new"}`} className="form-grid" onSubmit={createStyle}>
            <div className="editor-title">
              <div>
                <h2>基础信息</h2>
                <p>选择 Prompt 或参考图作为正式生图的风格参考来源。</p>
              </div>
              {styleFormMode === "edit" && formStyle ? (
                <button type="button" className="danger-button" onClick={() => deleteStyle(formStyle)} disabled={styleBusy}>
                  <Trash2 size={16} />
                </button>
              ) : null}
            </div>
            <input name="name" placeholder="风格名称" defaultValue={formStyle?.name ?? ""} required />
            <label className="form-field">
              <span>图片模型</span>
              <input name="image_model_name" placeholder={imageModelNamePlaceholder} defaultValue={formStyle?.image_model_name ?? ""} required />
              <small>手动输入模型名，不使用下拉选择。</small>
            </label>
            <select name="aspect_ratio" defaultValue={formStyle?.aspect_ratio ?? "9:16"} required>
              {aspectRatioOptions.map((ratio) => (
                <option key={ratio} value={ratio}>
                  画面比例 {ratio}
                </option>
              ))}
            </select>
            <div className="form-field style-reference-mode-field">
              <span>参考方式</span>
              <div className="style-reference-mode-options">
                <label>
                  <input
                    type="radio"
                    name="style_reference_mode"
                    value="prompt"
                    defaultChecked={(formStyle?.style_reference_mode ?? "prompt") === "prompt"}
                  />
                  <span>
                    <strong>Prompt 参考</strong>
                    <small>最终生图 prompt 会直接拼接风格提示词。</small>
                  </span>
                </label>
                <label>
                  <input
                    type="radio"
                    name="style_reference_mode"
                    value="image"
                    defaultChecked={formStyle?.style_reference_mode === "image"}
                  />
                  <span>
                    <strong>参考图参考</strong>
                    <small>生图请求会传入风格参考图，参考图需有公网 URL。</small>
                  </span>
                </label>
              </div>
            </div>
            <select name="status" defaultValue={formStyle?.status ?? "draft"}>
              <option value="draft">草稿</option>
              <option value="active">启用</option>
              <option value="disabled">停用</option>
            </select>
            <textarea name="description" placeholder="描述" defaultValue={formStyle?.description ?? ""} />
            <textarea name="style_prompt" placeholder="风格提示词" defaultValue={formStyle?.style_prompt ?? ""} required />
            {message ? <p className="form-message">{message}</p> : null}
            <button type="submit" disabled={styleBusy}>
              {savingStyle ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
              {savingStyle ? styleSavePhase || "保存中..." : styleFormMode === "edit" ? "保存风格" : "创建风格"}
            </button>
          </form>

          <section className="panel reference-panel">
              <div className="editor-title">
                <div>
                  <h2>参考图</h2>
                  <p>{formStyle ? "当参考方式为参考图参考时，这些图片会作为生图模型输入。" : "创建时选择的参考图会在风格创建成功后自动上传。"}</p>
                </div>
                {formStyle ? (
                  <label className={`upload-button ${styleBusy ? "disabled" : ""}`}>
                    {uploadingStyleReferences ? <Loader2 size={16} className="spin" /> : <Upload size={16} />}
                    {uploadingStyleReferences ? "上传中" : "上传"}
                    <input type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={uploadReferences} disabled={styleBusy} />
                  </label>
                ) : null}
              </div>
              {styleUploadPhase ? <p className="form-message">{styleUploadPhase}</p> : null}
              <div className="reference-grid">
                {!formStyle ? (
                  <label className={`reference-dropzone ${pendingReferenceFiles.length > 0 ? "has-files" : ""}`}>
                    <Upload size={22} />
                    <strong>{pendingReferenceFiles.length > 0 ? `已选择 ${pendingReferenceFiles.length} 张参考图` : "点击这里上传参考图"}</strong>
                    <span>{pendingReferenceFiles.length > 0 ? pendingReferenceNames : "支持 PNG、JPEG、WebP，可多选"}</span>
                    <input type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={uploadReferences} disabled={styleBusy} />
                  </label>
                ) : null}
                {formStyle && formStyle.reference_images.length === 0 ? <div className="empty mini">暂无参考图</div> : null}
                {formStyle?.reference_images.map((reference) => (
                  <figure key={reference.id} className="reference-item">
                    <LazyAssetImage asset={reference.asset} assetId={reference.asset.id} alt={reference.asset.original_filename ?? "参考图"} />
                    <button type="button" onClick={() => deleteReference(reference.id)} disabled={styleBusy}>
                      <Trash2 size={14} />
                    </button>
                  </figure>
                ))}
              </div>
            </section>
          </aside>
        </div>
      ) : null}
    </section>
  );
}

const creditTransactionLabels: Record<CreditTransaction["transaction_type"], string> = {
  initial_grant: "初始赠送",
  admin_adjustment: "管理员调整",
  activation_code_redeem: "激活码兑换",
  image_generation_reserve: "生图占用",
  image_generation_charge: "成功扣费",
  image_generation_release: "失败释放",
};

const creditTransactionFilterLabels: Record<CreditTransactionFilter, string> = {
  all: "全部流水",
  spent: "消耗积分",
  reset: "重置积分",
};

function SettingsView({
  user,
  creditOverview,
  onCreditsChanged,
  onLogout,
}: {
  user: User;
  creditOverview: CreditOverview | null;
  onCreditsChanged: (overview: CreditOverview | null) => void;
  onLogout: () => void;
}) {
  const [message, setMessage] = useState("");
  const [usageDays, setUsageDays] = useState<1 | 7 | 30>(7);
  const [usagePoints, setUsagePoints] = useState<CreditUsagePoint[]>([]);
  const [usageLoading, setUsageLoading] = useState(false);
  const [transactionsOpen, setTransactionsOpen] = useState(false);
  const [transactions, setTransactions] = useState<CreditTransaction[]>([]);
  const [transactionsLoading, setTransactionsLoading] = useState(false);
  const [transactionFilter, setTransactionFilter] = useState<CreditTransactionFilter>("all");
  const [transactionCursor, setTransactionCursor] = useState<string | null>(null);
  const [transactionCursorStack, setTransactionCursorStack] = useState<string[]>([]);
  const [transactionPageInfo, setTransactionPageInfo] = useState<{ next_cursor: string | null; has_more: boolean } | null>(null);

  async function logout() {
    await api.logout();
    onLogout();
  }

  async function refreshUsage(days = usageDays) {
    setUsageLoading(true);
    try {
      setUsagePoints(await api.creditUsage({ days }));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "积分消耗趋势加载失败");
    } finally {
      setUsageLoading(false);
    }
  }

  useEffect(() => {
    void refreshUsage(usageDays);
  }, [usageDays]);

  async function refreshTransactions(nextCursor = transactionCursor, nextFilter = transactionFilter) {
    setTransactionsLoading(true);
    try {
      const result = await api.creditTransactions({
        filter: nextFilter,
        cursor: nextCursor,
        limit: 10,
      });
      setTransactions(result.items);
      setTransactionPageInfo({ next_cursor: result.page.next_cursor, has_more: result.page.has_more });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "积分流水加载失败");
    } finally {
      setTransactionsLoading(false);
    }
  }

  useEffect(() => {
    if (!transactionsOpen) return;
    void refreshTransactions(transactionCursor, transactionFilter);
  }, [transactionsOpen, transactionCursor, transactionFilter]);

  function openTransactions() {
    setTransactionsOpen(true);
    setTransactionCursor(null);
    setTransactionCursorStack([]);
  }

  function selectTransactionFilter(nextFilter: CreditTransactionFilter) {
    setTransactionFilter(nextFilter);
    setTransactionCursor(null);
    setTransactionCursorStack([]);
  }

  async function redeemCode(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    try {
      const overview = await api.redeemCreditCode({ code: String(formData.get("code") ?? "") });
      onCreditsChanged(overview);
      if (transactionsOpen) {
        setTransactionCursor(null);
        setTransactionCursorStack([]);
        void refreshTransactions(null, transactionFilter);
      }
      setMessage("激活码已兑换");
      event.currentTarget.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "兑换失败");
    }
  }

  const account = creditOverview?.account;

  return (
    <section className="page settings-page">
      <header className="page-header">
        <div>
          <h1>设置</h1>
          <p>管理账号、积分兑换和个人积分消耗趋势。</p>
        </div>
      </header>

      {message ? <p className="form-message">{message}</p> : null}

      <div className="settings-layout single-column-settings">
        <div className="settings-stack">
          <section className="settings-section account-section">
            <div className="section-title">
              <UserRound size={22} />
              <div>
                <h2>账号信息</h2>
                <p>当前登录身份和基础账号资料。</p>
              </div>
            </div>
            <div className="account-card">
              <div className="avatar-orb">{(user.display_name || user.email).slice(0, 1).toUpperCase()}</div>
              <div>
                <strong>{user.display_name || "未设置昵称"}</strong>
                <span>{user.email}</span>
                <small>{user.role === "admin" ? "管理员" : "普通用户"}</small>
              </div>
              <div className="account-actions">
                <button type="button" className="danger-button text-danger-button" onClick={logout}>
                  <LogOut size={16} />
                  退出登录
                </button>
              </div>
            </div>
          </section>

          <section className="settings-section credit-section">
            <div className="section-title">
              <Coins size={22} />
              <div>
                <h2>我的积分</h2>
                <p>所有模型同价，成功产出一张图片扣 1 积分。</p>
              </div>
            </div>
            <div className="credit-summary-grid">
              <div>
                <span>可用积分</span>
                <strong>{account ? account.balance : "-"}</strong>
              </div>
              <div>
                <span>生成中占用</span>
                <strong>{account ? account.reserved_balance : "-"}</strong>
              </div>
              <div>
                <span>当前 API</span>
                <strong>{API_BASE_URL || "同源"}</strong>
              </div>
            </div>
            <form className="redeem-form" onSubmit={redeemCode}>
              <label>
                激活码
                <input name="code" placeholder="输入管理员发放的激活码" required />
              </label>
              <button type="submit">
                <Ticket size={16} />
                兑换积分
              </button>
            </form>
          </section>

          <section className="settings-section">
            <div className="section-title">
              <Clock3 size={22} />
              <div>
                <h2>积分消耗趋势</h2>
                <p>查看最近 1 天、7 天或 30 天的成功出图积分消耗。</p>
              </div>
            </div>
            <div className="segmented-control usage-range-control">
              {[1, 7, 30].map((days) => (
                <button
                  key={days}
                  type="button"
                  className={usageDays === days ? "active" : ""}
                  onClick={() => setUsageDays(days as 1 | 7 | 30)}
                >
                  {days === 1 ? "1 天" : `${days} 天`}
                </button>
              ))}
            </div>
            <CreditUsageChart points={usagePoints} loading={usageLoading} />
          </section>

          <section className="settings-section">
            <div className="section-title">
              <Clock3 size={22} />
              <div>
                <h2>最近积分流水</h2>
                <p>默认不加载明细，点击后分页查看占用、扣费、释放和调整记录。</p>
              </div>
            </div>
            {!transactionsOpen ? (
              <div className="transaction-lazy-panel">
                <span>流水明细会按需加载，避免进入设置页时拉取完整记录。</span>
                <button type="button" onClick={openTransactions}>
                  查看明细
                </button>
              </div>
            ) : (
              <>
                <div className="transaction-detail-toolbar">
                  <div className="segmented-control transaction-filter-control">
                    {(["all", "spent", "reset"] as CreditTransactionFilter[]).map((filter) => (
                      <button
                        key={filter}
                        type="button"
                        className={transactionFilter === filter ? "active" : ""}
                        onClick={() => selectTransactionFilter(filter)}
                      >
                        {creditTransactionFilterLabels[filter]}
                      </button>
                    ))}
                  </div>
                  <button type="button" className="secondary-button" disabled={transactionsLoading} onClick={() => refreshTransactions()}>
                    刷新
                  </button>
                </div>
                <TransactionList transactions={transactions} loading={transactionsLoading} />
                <div className="pagination-actions">
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={transactionCursorStack.length === 0 || transactionsLoading}
                    onClick={() => {
                      const previous = transactionCursorStack[transactionCursorStack.length - 1] ?? null;
                      setTransactionCursorStack((stack) => stack.slice(0, -1));
                      setTransactionCursor(previous);
                    }}
                  >
                    上一页
                  </button>
                  <button
                    type="button"
                    disabled={!transactionPageInfo?.has_more || transactionsLoading}
                    onClick={() => {
                      setTransactionCursorStack((stack) => [...stack, transactionCursor ?? ""]);
                      setTransactionCursor(transactionPageInfo?.next_cursor ?? null);
                    }}
                  >
                    下一页
                  </button>
                </div>
              </>
            )}
          </section>
        </div>
      </div>
    </section>
  );
}

function CreditUsageChart({ points, loading }: { points: CreditUsagePoint[]; loading: boolean }) {
  const width = 720;
  const height = 220;
  const padding = 28;
  const maxSpent = Math.max(1, ...points.map((point) => point.spent_credits));
  const path = points
    .map((point, index) => {
      const x = points.length <= 1 ? padding : padding + (index / (points.length - 1)) * (width - padding * 2);
      const y = height - padding - (point.spent_credits / maxSpent) * (height - padding * 2);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
  const total = points.reduce((sum, point) => sum + point.spent_credits, 0);

  return (
    <div className="credit-chart">
      <div className="credit-chart-summary">
        <strong>{total}</strong>
        <span>{loading ? "正在加载" : "本周期消耗积分"}</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="积分消耗折线图">
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} />
        {path ? <path d={path} /> : null}
        {points.map((point, index) => {
          const x = points.length <= 1 ? padding : padding + (index / (points.length - 1)) * (width - padding * 2);
          const y = height - padding - (point.spent_credits / maxSpent) * (height - padding * 2);
          const showLabel = points.length <= 8 || index === 0 || index === points.length - 1 || index % 5 === 0;
          return (
            <g key={`${point.started_at}-${point.label}`}>
              <circle cx={x} cy={y} r={4} />
              {showLabel ? <text x={x} y={height - 7}>{point.label}</text> : null}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function CreditUsageBarChart({ points, loading }: { points: CreditUsagePoint[]; loading: boolean }) {
  const width = 780;
  const height = 260;
  const paddingX = 34;
  const paddingY = 30;
  const maxSpent = Math.max(1, ...points.map((point) => point.spent_credits));
  const plotWidth = width - paddingX * 2;
  const plotHeight = height - paddingY * 2;
  const gap = points.length > 14 ? 5 : 10;
  const barWidth = points.length ? Math.max(5, (plotWidth - gap * (points.length - 1)) / points.length) : 0;

  return (
    <div className="usage-bar-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="管理员积分消耗柱状图">
        <line x1={paddingX} y1={height - paddingY} x2={width - paddingX} y2={height - paddingY} />
        <line x1={paddingX} y1={paddingY} x2={paddingX} y2={height - paddingY} />
        {points.map((point, index) => {
          const x = paddingX + index * (barWidth + gap);
          const barHeight = (point.spent_credits / maxSpent) * plotHeight;
          const y = height - paddingY - barHeight;
          const showLabel = points.length <= 10 || index === 0 || index === points.length - 1 || index % 5 === 0;
          return (
            <g key={`${point.started_at}-${point.label}`}>
              <rect x={x} y={y} width={barWidth} height={barHeight || 2} rx={3} />
              {point.spent_credits > 0 ? <text className="bar-value" x={x + barWidth / 2} y={Math.max(14, y - 6)}>{point.spent_credits}</text> : null}
              {showLabel ? <text x={x + barWidth / 2} y={height - 8}>{point.label}</text> : null}
            </g>
          );
        })}
      </svg>
      {loading ? <div className="chart-loading">正在加载积分消耗数据</div> : null}
    </div>
  );
}

function AdminCreditUsageView({ user }: { user: User }) {
  const [message, setMessage] = useState("");
  const [days, setDays] = useState<1 | 7 | 30>(7);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [userQueryInput, setUserQueryInput] = useState("");
  const [userQuery, setUserQuery] = useState("");
  const [userOptions, setUserOptions] = useState<AdminUserCreditSummary[]>([]);
  const [usage, setUsage] = useState<AdminCreditUsage | null>(null);
  const [usageLoading, setUsageLoading] = useState(false);
  const [transactions, setTransactions] = useState<AdminCreditTransaction[]>([]);
  const [transactionsLoading, setTransactionsLoading] = useState(false);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const [pageInfo, setPageInfo] = useState<{ next_cursor: string | null; has_more: boolean } | null>(null);

  async function refreshUserOptions(query = userQuery) {
    if (user.role !== "admin") return;
    try {
      const result = await api.adminUsers({ query: query.trim() || undefined, limit: 100 });
      setUserOptions(result.items);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "用户筛选列表加载失败");
    }
  }

  async function refreshUsage(nextDays = days, nextUserId = selectedUserId) {
    if (user.role !== "admin") return;
    setUsageLoading(true);
    try {
      setUsage(await api.adminCreditUsage({ days: nextDays, user_id: nextUserId || null }));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "积分消耗大盘加载失败");
    } finally {
      setUsageLoading(false);
    }
  }

  async function refreshTransactions(nextCursor = cursor, nextUserId = selectedUserId) {
    if (user.role !== "admin") return;
    setTransactionsLoading(true);
    try {
      const result = await api.adminCreditTransactions({
        user_id: nextUserId || null,
        cursor: nextCursor,
        limit: 10,
      });
      setTransactions(result.items);
      setPageInfo({ next_cursor: result.page.next_cursor, has_more: result.page.has_more });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "积分消耗明细加载失败");
    } finally {
      setTransactionsLoading(false);
    }
  }

  useEffect(() => {
    void refreshUserOptions(userQuery);
  }, [userQuery, user.role]);

  useEffect(() => {
    void refreshUsage(days, selectedUserId);
  }, [days, selectedUserId, user.role]);

  useEffect(() => {
    void refreshTransactions(cursor, selectedUserId);
  }, [cursor, selectedUserId, user.role]);

  function submitUserSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSelectedUserId("");
    setCursor(null);
    setCursorStack([]);
    setUserQuery(userQueryInput);
  }

  function selectUsageUser(userId: string) {
    setSelectedUserId(userId);
    setCursor(null);
    setCursorStack([]);
  }

  if (user.role !== "admin") {
    return (
      <section className="page">
        <header className="page-header">
          <div>
            <h1>积分消耗</h1>
            <p>当前账号没有访问积分消耗大盘的权限。</p>
          </div>
        </header>
      </section>
    );
  }

  const selectedUser = userOptions.find((option) => option.id === selectedUserId) ?? null;
  const summary = usage?.summary;

  return (
    <section className="page credit-usage-page">
      <header className="page-header">
        <div>
          <h1>积分消耗</h1>
          <p>查看全站成功出图扣费趋势，也可以按用户筛选消耗明细。</p>
        </div>
      </header>

      {message ? <p className="form-message">{message}</p> : null}

      <section className="settings-section">
        <div className="admin-usage-controls">
          <div className="segmented-control usage-range-control">
            {([1, 7, 30] as const).map((value) => (
              <button key={value} type="button" className={days === value ? "active" : ""} onClick={() => setDays(value)}>
                {value === 1 ? "最近 24 小时" : `最近 ${value} 天`}
              </button>
            ))}
          </div>
          <form className="admin-search usage-user-search" onSubmit={submitUserSearch}>
            <input value={userQueryInput} onChange={(event) => setUserQueryInput(event.target.value)} placeholder="搜索用户邮箱或昵称" />
            <button type="submit">
              <Search size={16} />
              搜索用户
            </button>
          </form>
          <label className="usage-user-select">
            用户
            <select value={selectedUserId} onChange={(event) => selectUsageUser(event.target.value)}>
              <option value="">全部用户</option>
              {userOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.display_name || option.email}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="usage-dashboard-grid">
          <div>
            <span>{selectedUser ? "筛选用户" : "统计范围"}</span>
            <strong>{selectedUser ? selectedUser.display_name || selectedUser.email : "全部用户"}</strong>
          </div>
          <div>
            <span>消耗积分</span>
            <strong>{summary ? summary.total_spent_credits : "-"}</strong>
          </div>
          <div>
            <span>扣费次数</span>
            <strong>{summary ? summary.transaction_count : "-"}</strong>
          </div>
          <div>
            <span>消耗用户数</span>
            <strong>{summary ? summary.active_user_count : "-"}</strong>
          </div>
        </div>
        <CreditUsageBarChart points={usage?.points ?? []} loading={usageLoading} />
      </section>

      <section className="settings-section">
        <div className="section-title">
          <Coins size={22} />
          <div>
            <h2>消耗明细</h2>
            <p>只展示成功出图扣费流水，按时间倒序分页。</p>
          </div>
        </div>
        <AdminCreditTransactionTable transactions={transactions} loading={transactionsLoading} />
        <div className="pagination-actions">
          <button
            type="button"
            className="secondary-button"
            disabled={cursorStack.length === 0 || transactionsLoading}
            onClick={() => {
              const previous = cursorStack[cursorStack.length - 1] ?? null;
              setCursorStack((stack) => stack.slice(0, -1));
              setCursor(previous);
            }}
          >
            上一页
          </button>
          <button
            type="button"
            disabled={!pageInfo?.has_more || transactionsLoading}
            onClick={() => {
              setCursorStack((stack) => [...stack, cursor ?? ""]);
              setCursor(pageInfo?.next_cursor ?? null);
            }}
          >
            下一页
          </button>
        </div>
      </section>
    </section>
  );
}

function AdminCreditTransactionTable({ transactions, loading }: { transactions: AdminCreditTransaction[]; loading: boolean }) {
  if (loading) {
    return <div className="empty mini">正在加载积分消耗明细</div>;
  }
  if (transactions.length === 0) {
    return <div className="empty mini">暂无积分消耗明细</div>;
  }
  return (
    <div className="admin-credit-transaction-table">
      <div className="admin-credit-transaction-head">
        <span>时间</span>
        <span>用户</span>
        <span>积分</span>
        <span>关联</span>
      </div>
      {transactions.map((transaction) => (
        <div key={transaction.id} className="admin-credit-transaction-row">
          <span>{formatDateTime(transaction.created_at)}</span>
          <span>
            <strong>{transaction.user_display_name || transaction.user_email}</strong>
            <small>{transaction.user_email}</small>
          </span>
          <b>{transaction.amount}</b>
          <span>{transaction.task_id ? `任务 ${shortId(transaction.task_id)}` : transaction.note || "成功扣费"}</span>
        </div>
      ))}
    </div>
  );
}

function UsersView({ user, onCreditsChanged }: { user: User; onCreditsChanged: () => Promise<CreditOverview | null> }) {
  const [message, setMessage] = useState("");
  const [adminUsers, setAdminUsers] = useState<AdminUserCreditSummary[]>([]);
  const [adminUsersLoading, setAdminUsersLoading] = useState(false);
  const [adminQueryInput, setAdminQueryInput] = useState("");
  const [adminQuery, setAdminQuery] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const [pageInfo, setPageInfo] = useState<{ next_cursor: string | null; has_more: boolean } | null>(null);
  const [selectedUser, setSelectedUser] = useState<AdminUserCreditDetail | null>(null);
  const [activationCodes, setActivationCodes] = useState<ActivationCode[]>([]);
  const [createdCodes, setCreatedCodes] = useState<ActivationCodeCreated[]>([]);

  async function refreshUsers(nextCursor = cursor, query = adminQuery) {
    if (user.role !== "admin") return;
    setAdminUsersLoading(true);
    try {
      const result = await api.adminUsers({
        query: query.trim() || undefined,
        cursor: nextCursor,
        limit: 10,
      });
      setAdminUsers(result.items);
      setPageInfo({ next_cursor: result.page.next_cursor, has_more: result.page.has_more });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "用户列表加载失败");
    } finally {
      setAdminUsersLoading(false);
    }
  }

  async function refreshActivationCodes() {
    if (user.role !== "admin") return;
    try {
      const result = await api.activationCodes({ limit: 20 });
      setActivationCodes(result.items);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "激活码列表加载失败");
    }
  }

  useEffect(() => {
    void refreshUsers(cursor, adminQuery);
  }, [cursor, adminQuery, user.role]);

  useEffect(() => {
    void refreshActivationCodes();
  }, [user.role]);

  async function openUserDetail(userId: string) {
    try {
      setSelectedUser(await api.adminUserDetail(userId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "用户详情加载失败");
    }
  }

  async function adjustCredits(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedUser) return;
    const formData = new FormData(event.currentTarget);
    const amount = Number(formData.get("amount") ?? 0);
    const note = String(formData.get("note") ?? "");
    try {
      const detail = await api.adjustAdminUserCredits(selectedUser.user.id, { amount, note });
      setSelectedUser(detail);
      await refreshUsers(cursor, adminQuery);
      if (detail.user.id === user.id) {
        await onCreditsChanged();
      }
      setMessage("积分已调整");
      event.currentTarget.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "积分调整失败");
    }
  }

  async function createCodes(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const expiresAt = String(formData.get("expires_at") ?? "");
    try {
      const codes = await api.createActivationCodes({
        credit_amount: Number(formData.get("credit_amount") ?? 0),
        count: Number(formData.get("count") ?? 1),
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
        note: String(formData.get("note") ?? "") || null,
      });
      setCreatedCodes(codes);
      await refreshActivationCodes();
      setMessage("激活码已生成，明文只显示本次");
      event.currentTarget.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "激活码生成失败");
    }
  }

  function submitSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCursorStack([]);
    setCursor(null);
    setAdminQuery(adminQueryInput);
  }

  if (user.role !== "admin") {
    return (
      <section className="page">
        <header className="page-header">
          <div>
            <h1>用户管理</h1>
            <p>当前账号没有访问用户管理的权限。</p>
          </div>
        </header>
      </section>
    );
  }

  return (
    <section className="page users-page">
      <header className="page-header">
        <div>
          <h1>用户管理</h1>
          <p>分页查看用户积分、使用情况，并生成可发放给用户的激活码。</p>
        </div>
      </header>

      {message ? <p className="form-message">{message}</p> : null}

      <div className="users-management-layout">
        <section className="settings-section">
          <div className="section-title">
            <Users size={22} />
            <div>
              <h2>用户列表</h2>
              <p>每页显示 10 个用户，支持按邮箱或昵称搜索。</p>
            </div>
          </div>
          <form className="admin-search" onSubmit={submitSearch}>
            <input value={adminQueryInput} onChange={(event) => setAdminQueryInput(event.target.value)} placeholder="搜索邮箱或昵称" />
            <button type="submit" disabled={adminUsersLoading}>
              <Search size={16} />
              搜索
            </button>
          </form>
          <div className="admin-user-table">
            <div className="admin-user-table-head">
              <span>用户</span>
              <span>积分</span>
              <span>任务</span>
              <span>成功图</span>
              <span>已消耗</span>
            </div>
            {adminUsers.map((item) => (
              <button type="button" key={item.id} className="admin-user-table-row" onClick={() => openUserDetail(item.id)}>
                <span>
                  <strong>{item.display_name || item.email}</strong>
                  <small>{item.email}</small>
                </span>
                <b>{item.balance}</b>
                <span>{item.task_count}</span>
                <span>{item.succeeded_image_count}</span>
                <span>{item.spent_credits}</span>
              </button>
            ))}
            {adminUsers.length === 0 ? <div className="empty mini">暂无用户</div> : null}
          </div>
          <div className="pagination-actions">
            <button
              type="button"
              className="secondary-button"
              disabled={cursorStack.length === 0 || adminUsersLoading}
              onClick={() => {
                const previous = cursorStack[cursorStack.length - 1] ?? null;
                setCursorStack((stack) => stack.slice(0, -1));
                setCursor(previous);
              }}
            >
              上一页
            </button>
            <button
              type="button"
              disabled={!pageInfo?.has_more || adminUsersLoading}
              onClick={() => {
                setCursorStack((stack) => [...stack, cursor ?? ""]);
                setCursor(pageInfo?.next_cursor ?? null);
              }}
            >
              下一页
            </button>
          </div>
        </section>

        <aside className="admin-settings-column">
          <section className="settings-section activation-code-manager">
            <div className="section-title">
              <Ticket size={22} />
              <div>
                <h2>生成激活码</h2>
                <p>生成后把明文码发给用户；数据库只保留哈希。</p>
              </div>
            </div>
            <form className="activation-form" onSubmit={createCodes}>
              <input name="credit_amount" type="number" min={1} max={100000} placeholder="每个码的积分" required />
              <input name="count" type="number" min={1} max={200} defaultValue={1} placeholder="数量" required />
              <input name="expires_at" type="datetime-local" />
              <input name="note" placeholder="备注" />
              <button type="submit">
                <Plus size={16} />
                生成激活码
              </button>
            </form>
            {createdCodes.length > 0 ? (
              <div className="generated-code-list">
                {createdCodes.map((code) => (
                  <code key={code.id}>{code.code}</code>
                ))}
              </div>
            ) : null}
            <div className="activation-code-list">
              {activationCodes.map((code) => (
                <div key={code.id}>
                  <strong>{code.code_prefix}...</strong>
                  <span>{code.credit_amount} 分 · {code.redeemed_at ? "已兑换" : code.disabled_at ? "已禁用" : "可用"}</span>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </div>

      {selectedUser ? (
        <div className="drawer-backdrop" role="presentation" onMouseDown={() => setSelectedUser(null)}>
          <aside className="task-create-drawer admin-user-drawer" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <div className="drawer-head">
              <div>
                <h2>{selectedUser.user.display_name || selectedUser.user.email}</h2>
                <p>{selectedUser.user.email}</p>
              </div>
              <button className="icon-button" type="button" onClick={() => setSelectedUser(null)} aria-label="关闭">
                <X size={18} />
              </button>
            </div>
            <div className="credit-summary-grid compact">
              <div>
                <span>可用积分</span>
                <strong>{selectedUser.user.balance}</strong>
              </div>
              <div>
                <span>消耗积分</span>
                <strong>{selectedUser.user.spent_credits}</strong>
              </div>
              <div>
                <span>成功图片</span>
                <strong>{selectedUser.user.succeeded_image_count}</strong>
              </div>
            </div>
            <form className="activation-form" onSubmit={adjustCredits}>
              <input name="amount" type="number" placeholder="增减积分，例如 100 或 -20" required />
              <input name="note" placeholder="调整原因" required />
              <button type="submit">
                <Save size={16} />
                调整积分
              </button>
            </form>
            <TransactionList transactions={selectedUser.recent_transactions} />
          </aside>
        </div>
      ) : null}
    </section>
  );
}

function TransactionList({ transactions, loading = false }: { transactions: CreditTransaction[]; loading?: boolean }) {
  if (loading) {
    return <div className="empty mini">正在加载积分流水</div>;
  }
  if (transactions.length === 0) {
    return <div className="empty mini">暂无积分流水</div>;
  }
  return (
    <div className="transaction-list">
      {transactions.map((transaction) => (
        <div key={transaction.id} className="transaction-row">
          <span>
            <strong>{creditTransactionLabels[transaction.transaction_type]}</strong>
            <small>{transaction.note || formatDateTime(transaction.created_at)}</small>
          </span>
          <b className={transaction.amount > 0 ? "positive" : "negative"}>
            {transaction.amount > 0 ? "+" : ""}
            {transaction.amount}
          </b>
          <small>余额 {transaction.balance_after} · 占用 {transaction.reserved_balance_after}</small>
        </div>
      ))}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
