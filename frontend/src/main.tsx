import { StrictMode, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertCircle,
  ArrowUpRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Coins,
  Download,
  Eye,
  FileText,
  Filter,
  Images,
  LogOut,
  Loader2,
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
  X,
} from "lucide-react";
import {
  API_BASE_URL,
  api,
  type ActivationCode,
  type ActivationCodeCreated,
  type AdminUserCreditDetail,
  type AdminUserCreditSummary,
  type ContentExtraction,
  type ContentExtractionHealth,
  type ContentExtractionMedia,
  type ContentExtractionSummary,
  type CreditOverview,
  type CreditTransaction,
  type FileAsset,
  type Style,
  type StyleTest,
  type Task,
  type TaskSummary,
  type User,
} from "./api/client";
import "./styles/app.css";

type View = "tasks" | "content" | "styles" | "settings";
const TASK_ROW_IMAGE_PREVIEW_LIMIT = 4;
const aspectRatioOptions = ["1:1", "3:4", "4:3", "9:16", "16:9"];
const imageModelNamePlaceholder = "生图模型名，例如 gpt-image-2";
const styleReferenceModeLabels: Record<Style["style_reference_mode"], string> = {
  prompt: "Prompt 参考",
  image: "参考图参考",
};
const viewRoutes: Record<View, string> = {
  tasks: "/tasks",
  content: "/content-extractions",
  styles: "/styles",
  settings: "/settings",
};

function normalizedPathname(pathname: string) {
  return pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
}

function viewFromPathname(pathname: string): View | null {
  const path = normalizedPathname(pathname);
  if (path === "/" || path === viewRoutes.tasks || path.startsWith(`${viewRoutes.tasks}/`)) return "tasks";
  if (path === viewRoutes.content) return "content";
  if (path === viewRoutes.styles) return "styles";
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

type ImageTextPayload = {
  title?: string | null;
  narration?: string | null;
  dialogue?: string | null;
  inner_os?: string | null;
  emphasis?: string | null;
};

const CONTENT_EXTRACTION_TASK_DRAFT_KEY = "doodlestory.contentExtractionTaskDraft";
type CreateInputMode = Task["story_input_mode"] | "dy_replicate";

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
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
  const resolvedSrc = asset ? assetUrl(asset, variant) : api.assetContentUrl(assetId, variant);

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
      { rootMargin: "640px 0px" },
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
  const value = variant === "thumbnail" ? asset.thumbnail_url : asset.content_url;
  return absoluteAssetUrl(value || api.assetContentUrl(asset.id, variant));
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
      {view === "content" ? <ContentExtractionView user={user} onNavigatePath={navigateToPath} /> : null}
      {view === "styles" ? <StylesView user={user} onCreditsChanged={refreshCredits} /> : null}
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
    { key: "content" as const, label: "内容提取", icon: FileText, path: viewRoutes.content },
    { key: "styles" as const, label: "风格", icon: Sparkles, path: viewRoutes.styles },
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
            <span>FastAPI + React</span>
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

function stylePreviewAssets(style: Style) {
  const assets = style.reference_images.map((reference) => reference.asset);
  if (style.cover_asset && !assets.some((asset) => asset.id === style.cover_asset?.id)) {
    return [style.cover_asset, ...assets];
  }
  return assets;
}

function styleCover(style: Style) {
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
  const [styles, setStyles] = useState<Style[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<Task["status"] | "all">("all");
  const [styleFilter, setStyleFilter] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const [pageInfo, setPageInfo] = useState<{ next_cursor: string | null; has_more: boolean } | null>(null);
  const [loadingTasks, setLoadingTasks] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [stylePickerOpen, setStylePickerOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createStyleId, setCreateStyleId] = useState("");
  const [countMode, setCountMode] = useState<"auto" | "fixed">("auto");
  const [storyInputMode, setStoryInputMode] = useState<CreateInputMode>("original");
  const [createOriginalText, setCreateOriginalText] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [previewImageId, setPreviewImageId] = useState<string | null>(null);
  const [panelEditInputs, setPanelEditInputs] = useState<Record<string, string>>({});
  const [editingPanelId, setEditingPanelId] = useState<string | null>(null);
  const [downloadingTaskId, setDownloadingTaskId] = useState<string | null>(null);
  const previewCloseRef = useRef<HTMLButtonElement | null>(null);

  const taskForDetail = selectedTask;
  const taskStepsForDetail = useMemo(() => (taskForDetail ? visibleTaskSteps(taskForDetail) : []), [taskForDetail]);
  const panelImageMap = useMemo(() => imagesByPanel(taskForDetail), [taskForDetail]);
  const previewItems = useMemo(() => succeededImages(taskForDetail), [taskForDetail]);
  const previewIndex = previewItems.findIndex((image) => image.id === previewImageId);
  const previewImage = previewIndex >= 0 ? previewItems[previewIndex] : null;
  const previewPanel = previewImage ? taskForDetail?.panels.find((panel) => panel.id === previewImage.panel_id) : null;
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
  const selectedCreateStyle = styles.find((style) => style.id === createStyleId) ?? styles[0] ?? null;
  const createStylePreviewLimit = 8;
  const visibleCreateStyles = styles.slice(0, createStylePreviewLimit);
  const canExpandCreateStyles = styles.length > 0;

  useEffect(() => {
    refresh(undefined, { quiet: false });
  }, [query, statusFilter, styleFilter, cursor]);

  useEffect(() => {
    let cancelled = false;

    async function loadRouteTask(taskId: string) {
      setSelectedId(taskId);
      setDetailOpen(true);
      setSelectedTask(null);
      setPreviewImageId(null);
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
    if (!detailOpen) return;
    function handleKey(event: KeyboardEvent) {
	      if (event.key === "Escape" && !previewImageId) {
	        closeTaskDetail();
	      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [detailOpen, previewImageId]);

  useEffect(() => {
    if (createOpen && !createStyleId && styles[0]) {
      setCreateStyleId(styles[0].id);
    }
  }, [createOpen, createStyleId, styles]);

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
      const [taskResult, styleResult] = await Promise.all([
        api.tasks({
          query,
          status: statusFilter,
          style_id: styleFilter,
          cursor,
          limit: 10,
        }),
        api.styles({ status: "active" }),
      ]);
      setTasks(taskResult.items);
      setPageInfo(taskResult.page);
      setStyles(styleResult.items);
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

  async function selectTask(taskId: string) {
    setSelectedId(taskId);
    setDetailOpen(true);
    setSelectedTask(null);
    setPreviewImageId(null);
    onNavigatePath(`${viewRoutes.tasks}/${encodeURIComponent(taskId)}`);
  }

  function closeTaskDetail() {
    setDetailOpen(false);
    setSelectedId("");
    setSelectedTask(null);
    setPreviewImageId(null);
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
    try {
      setCreating(true);
      if (storyInputMode === "dy_replicate") {
        const content = await api.replicateContentAsTask({
          raw_input: originalText,
          image_count_mode: countMode,
          requested_image_count: countMode === "fixed" ? requested : null,
          style_id: createStyleId,
          use_character_references: formData.get("use_character_references") === "on",
        });
        setCreateOriginalText("");
        setCountMode("auto");
        setStoryInputMode("original");
        setCreateStyleId(styles[0]?.id ?? "");
        setCreateOpen(false);
        setStylePickerOpen(false);
        setMessage("DY 爆款复刻已提交，正在提取内容并自动创建生图任务");
        void monitorReplicateTask(content.id);
        return;
      }
      const task = await api.createTask({
        original_text: originalText,
        story_input_mode: storyInputMode,
        image_count_mode: countMode,
        requested_image_count: countMode === "fixed" ? requested : null,
        style_id: createStyleId,
        use_character_references: formData.get("use_character_references") === "on",
      });
      setCreateOriginalText("");
      setCountMode("auto");
      setStoryInputMode("original");
      setCreateStyleId(styles[0]?.id ?? "");
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

  function downloadPreviewImage() {
    if (!previewImage?.asset) return;
    window.location.href = assetUrl(previewImage.asset, "original");
  }

  function openPreviewImage() {
    if (!previewImage?.asset) return;
    window.open(assetUrl(previewImage.asset, "original"), "_blank", "noopener,noreferrer");
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

      <form className="task-toolbar" onSubmit={applyFilters}>
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
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as Task["status"] | "all")}>
            {taskStatusOptions.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <Sparkles size={16} />
          <select value={styleFilter} onChange={(event) => setStyleFilter(event.target.value)}>
            <option value="">全部风格</option>
            {styles.map((style) => (
              <option key={style.id} value={style.id}>
                {style.name}
              </option>
            ))}
          </select>
        </label>
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
                <strong>{query || statusFilter !== "all" || styleFilter ? "没有匹配的任务" : "还没有任务"}</strong>
                <p>{query || statusFilter !== "all" || styleFilter ? "调整筛选条件后再试。" : "创建第一条故事生成任务。"}</p>
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
                    {user.role === "admin" ? <small>Owner {shortId(task.owner_user_id)}</small> : null}
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
                          <LazyAssetImage asset={reference.asset} assetId={reference.asset.id} alt={reference.name} />
                          <figcaption>
                            <strong>{reference.name}</strong>
                            {reference.age_stage ? <span>{reference.age_stage}</span> : null}
                          </figcaption>
                        </figure>
                      ))}
                    </div>
                  ) : (
                    <div className="empty mini">人物参考图生成中</div>
                  )}
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
                    const canEditPanel = Boolean(panel.generated_prompt) && !activeVersion;
                    const imageText = imageTextSummary(image?.image_text_json ?? panel.image_text_json);
                    const textLayout = image?.text_layout ?? panel.text_layout;
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
                        <strong>{panel.panel_type === "cover" ? "封面" : `Panel ${panel.panel_order}`}</strong>
                        <p>{panel.original_text_segment}</p>
                        {panel.narration_text ? <small>旁白：{panel.narration_text}</small> : null}
                        {panel.dialogue_text ? <small>对白：{panel.dialogue_text}</small> : null}
                        {imageText ? <small>图片文字：{imageText}</small> : null}
                        {textLayout ? <small>文字布局：{textLayout}</small> : null}
                        {image?.workflow_step && image.status !== "succeeded" ? (
                          <small className="process-note">
                            {imageWorkflowLabel(image.workflow_step)} · {imageStatusLabel(image.status)}
                          </small>
                        ) : null}
                        {image?.image_prompt || panel.generated_prompt ? (
                          <small className="panel-generated-prompt">{image?.image_prompt ?? panel.generated_prompt}</small>
                        ) : null}
                        {currentImageIsUserEdit && image?.user_instruction ? <small>修改方向：{image.user_instruction}</small> : null}
                        {currentImageIsUserEdit && image?.prompt_change_summary ? <small>修改摘要：{image.prompt_change_summary}</small> : null}
                        {image?.error_message ? <small className="error">{image.error_message}</small> : null}
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
                  <span>可以提交故事设计、人物设定、画面要求或简化想法，系统会规划封面和分镜。</span>
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
                  onChange={(event) => setCreateOriginalText(event.target.value)}
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
                  <small>原始输入会保留，系统会直接根据方案规划图文分镜并自动生成封面。</small>
                ) : storyInputMode === "extracted_storyboard" ? (
                  <small>系统只做分镜结构化，不扩写、不总结、不合并页；会把旁白、对白和内心 OS 区分成不同画面呈现形式。</small>
                ) : storyInputMode === "dy_replicate" ? (
                  <small>提交后会先创建内容提取记录；提取成功后自动创建提取分镜任务并跳转到任务详情。</small>
                ) : (
                  <small>完整故事模式会保持文本不变，所有 panel 拼接后必须逐字等于你提交的故事正文。</small>
                )}
              </label>
              <label className="character-reference-toggle">
                <input name="use_character_references" type="checkbox" defaultChecked />
                <span>
                  <strong>使用参考人物</strong>
                  <small>默认开启。系统会先识别主要人物并生成人物参考图，再用于后续分镜生图。</small>
                </span>
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
                    {storyInputMode === "adapted" ? <small>固定数量包含封面，例如 8 张 = 1 张封面 + 7 张剧情图。</small> : null}
                    {storyInputMode === "extracted_storyboard" ? <small>固定数量必须和提取分镜页数一致，不会自动合并或补页。</small> : null}
                    {storyInputMode === "dy_replicate" ? <small>固定数量必须和提取出的页数一致；内容提取完成后不会自动合并或补页。</small> : null}
                  </label>
                ) : (
                  <p className="field-hint">系统会根据故事长度和内容密度决定图片张数。</p>
                )}
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
                {styles.length === 0 ? <div className="empty mini">暂无启用风格</div> : null}
                {selectedCreateStyle ? (
                  <div className="selected-style-preview">
                    <div className="selected-style-poster">
                      {styleCover(selectedCreateStyle) ? (
                        <LazyAssetImage
                          asset={styleCover(selectedCreateStyle)}
                          assetId={styleCover(selectedCreateStyle)!.id}
                          alt={selectedCreateStyle.name}
                        />
                      ) : (
                        <span>比例由模板控制</span>
                      )}
                    </div>
                    <div>
                      <span className={`status-pill ${selectedCreateStyle.status}`}>
                        {selectedCreateStyle.status === "active" ? "启用" : selectedCreateStyle.status}
                      </span>
                      <strong>{selectedCreateStyle.name}</strong>
                      <p>{selectedCreateStyle.description || "暂无描述"}</p>
                      <small>{styleReferenceModeLabels[selectedCreateStyle.style_reference_mode]} · {selectedCreateStyle.reference_images.length} 张参考图 · 比例 {selectedCreateStyle.aspect_ratio} · {selectedCreateStyle.image_model_name}</small>
                    </div>
                  </div>
                ) : null}
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
                          {assets.slice(0, 2).map((asset) => (
                            <LazyAssetImage key={asset.id} asset={asset} assetId={asset.id} alt={style.name} />
                          ))}
                          {assets.length === 0 ? <span>模板比例</span> : null}
                        </div>
                        <div>
                          <strong>{style.name}</strong>
                          <small>{style.description || `${style.reference_images.length} 张参考图`} · {styleReferenceModeLabels[style.style_reference_mode]} · 比例 {style.aspect_ratio} · {style.image_model_name}</small>
                        </div>
                        <span className={`status-pill ${style.status}`}>{style.status === "active" ? "启用" : style.status}</span>
                      </button>
                    );
                  })}
                </div>
              </fieldset>
              {message ? <p className="form-message">{message}</p> : null}
              <div className="drawer-actions">
                <button type="button" className="ghost-button" onClick={() => setCreateOpen(false)}>
                  取消
                </button>
                <button type="submit" disabled={creating}>
                  {creating ? <Loader2 size={17} className="spin" /> : <Plus size={17} />}
                  {storyInputMode === "dy_replicate" ? "开始复刻" : "创建任务"}
                </button>
              </div>
            </form>
          </section>
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
                    <p>从全部启用风格中选择一个作为本次任务的视觉模板。</p>
                  </div>
                  <button type="button" className="icon-button" aria-label="关闭风格选择" onClick={() => setStylePickerOpen(false)}>
                    <X size={18} />
                  </button>
                </div>
                <div className="style-picker-grid expanded">
                  {styles.map((style) => {
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
                          {assets.slice(0, 3).map((asset) => (
                            <LazyAssetImage key={asset.id} asset={asset} assetId={asset.id} alt={style.name} />
                          ))}
                          {assets.length === 0 ? <span>模板比例</span> : null}
                        </div>
                        <div>
                          <strong>{style.name}</strong>
                          <small>{style.description || `${style.reference_images.length} 张参考图`} · {styleReferenceModeLabels[style.style_reference_mode]} · 比例 {style.aspect_ratio} · {style.image_model_name}</small>
                        </div>
                        <span className={`status-pill ${style.status}`}>{style.status === "active" ? "启用" : style.status}</span>
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
                <p className="preview-prompt">{previewImage.final_prompt ?? previewImage.image_prompt ?? ""}</p>
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
    setStyleFormMode("create");
    setEditingStyleId("");
    setPendingReferenceFiles([]);
    setMessage("");
    setStyleDrawerOpen(true);
  }

  function startEdit(style: Style) {
    setEditingStyleId(style.id);
    setStyleFormMode("edit");
    setPendingReferenceFiles([]);
    setMessage("");
    setStyleDrawerOpen(true);
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
      const saved =
        isEditMode && editingStyle
          ? await api.updateStyle(editingStyle.id, payload)
          : await api.createStyle(payload);
      setEditingStyleId(saved.id);
      setTestingStyleId(saved.id);
      setStyleFormMode("edit");
      if (!isEditMode && selectedReferenceFiles.length > 0) {
        try {
          for (const file of selectedReferenceFiles) {
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
    }
  }

  async function deleteStyle(style: Style) {
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
    if (styleFormMode === "create") {
      setPendingReferenceFiles(Array.from(event.target.files ?? []));
      event.target.value = "";
      return;
    }
    if (!editingStyle || !event.target.files?.length) {
      return;
    }
    try {
      for (const file of Array.from(event.target.files)) {
        await api.uploadStyleReferenceImage(editingStyle.id, file);
      }
      setMessage("参考图已上传");
      event.target.value = "";
      await refresh(editingStyle.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "上传失败");
    }
  }

  async function deleteReference(referenceId: string) {
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
        <div className="drawer-backdrop" role="presentation" onMouseDown={() => setStyleDrawerOpen(false)}>
          <aside className="task-create-drawer style-form-drawer" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <div className="drawer-head">
              <div>
                <h2>{styleFormMode === "edit" && formStyle ? "编辑风格" : "新建风格"}</h2>
                <p>{styleFormMode === "edit" && formStyle ? formStyle.name : "创建一个可复用的生图风格资产"}</p>
              </div>
              <button className="icon-button" type="button" onClick={() => setStyleDrawerOpen(false)} aria-label="关闭">
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
                <button type="button" className="danger-button" onClick={() => deleteStyle(formStyle)}>
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
            <button type="submit" disabled={savingStyle}>
              {savingStyle ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
              {savingStyle ? "保存中..." : styleFormMode === "edit" ? "保存风格" : "创建风格"}
            </button>
          </form>

          <section className="panel reference-panel">
              <div className="editor-title">
                <div>
                  <h2>参考图</h2>
                  <p>{formStyle ? "当参考方式为参考图参考时，这些图片会作为生图模型输入。" : "创建时选择的参考图会在风格创建成功后自动上传。"}</p>
                </div>
                {formStyle ? (
                  <label className="upload-button">
                    <Upload size={16} />
                    上传
                    <input type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={uploadReferences} />
                  </label>
                ) : null}
              </div>
              <div className="reference-grid">
                {!formStyle ? (
                  <label className={`reference-dropzone ${pendingReferenceFiles.length > 0 ? "has-files" : ""}`}>
                    <Upload size={22} />
                    <strong>{pendingReferenceFiles.length > 0 ? `已选择 ${pendingReferenceFiles.length} 张参考图` : "点击这里上传参考图"}</strong>
                    <span>{pendingReferenceFiles.length > 0 ? pendingReferenceNames : "支持 PNG、JPEG、WebP，可多选"}</span>
                    <input type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={uploadReferences} />
                  </label>
                ) : null}
                {formStyle && formStyle.reference_images.length === 0 ? <div className="empty mini">暂无参考图</div> : null}
                {formStyle?.reference_images.map((reference) => (
                  <figure key={reference.id} className="reference-item">
                    <LazyAssetImage asset={reference.asset} assetId={reference.asset.id} alt={reference.asset.original_filename ?? "参考图"} />
                    <button type="button" onClick={() => deleteReference(reference.id)}>
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
  const [adminUsers, setAdminUsers] = useState<AdminUserCreditSummary[]>([]);
  const [adminUsersLoading, setAdminUsersLoading] = useState(false);
  const [adminQuery, setAdminQuery] = useState("");
  const [selectedUser, setSelectedUser] = useState<AdminUserCreditDetail | null>(null);
  const [activationCodes, setActivationCodes] = useState<ActivationCode[]>([]);
  const [createdCodes, setCreatedCodes] = useState<ActivationCodeCreated[]>([]);

  useEffect(() => {
    if (user.role !== "admin") return;
    void refreshAdminData();
  }, [user.role]);

  async function logout() {
    await api.logout();
    onLogout();
  }

  async function refreshAdminData(query = adminQuery) {
    if (user.role !== "admin") return;
    setAdminUsersLoading(true);
    try {
      const [usersResult, codesResult] = await Promise.all([
        api.adminUsers({ query: query.trim() || undefined, limit: 20 }),
        api.activationCodes({ limit: 20 }),
      ]);
      setAdminUsers(usersResult.items);
      setActivationCodes(codesResult.items);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "管理员数据加载失败");
    } finally {
      setAdminUsersLoading(false);
    }
  }

  async function redeemCode(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    try {
      const overview = await api.redeemCreditCode({ code: String(formData.get("code") ?? "") });
      onCreditsChanged(overview);
      setMessage("激活码已兑换");
      event.currentTarget.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "兑换失败");
    }
  }

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
      await refreshAdminData();
      if (detail.user.id === user.id) {
        onCreditsChanged(null);
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
      await refreshAdminData();
      setMessage("激活码已生成，明文只显示本次");
      event.currentTarget.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "激活码生成失败");
    }
  }

  const account = creditOverview?.account;

  return (
    <section className="page settings-page">
      <header className="page-header">
        <div>
          <h1>设置</h1>
          <p>管理账号、积分、激活码和管理员用户操作。</p>
        </div>
      </header>

      {message ? <p className="form-message">{message}</p> : null}

      <div className="settings-layout">
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
                <h2>最近积分流水</h2>
                <p>占用、成功扣费、失败释放和人工调整都会记录。</p>
              </div>
            </div>
            <TransactionList transactions={creditOverview?.recent_transactions ?? []} />
          </section>
        </div>

        {user.role === "admin" ? (
          <aside className="admin-settings-column">
            <section className="settings-section">
              <div className="section-title">
                <Users size={22} />
                <div>
                  <h2>用户管理</h2>
                  <p>查看用户积分、任务和成功图片数量。</p>
                </div>
              </div>
              <form
                className="admin-search"
                onSubmit={(event) => {
                  event.preventDefault();
                  void refreshAdminData(adminQuery);
                }}
              >
                <input value={adminQuery} onChange={(event) => setAdminQuery(event.target.value)} placeholder="搜索邮箱或昵称" />
                <button type="submit" disabled={adminUsersLoading}>
                  <Search size={16} />
                  搜索
                </button>
              </form>
              <div className="admin-user-list">
                {adminUsers.map((item) => (
                  <button type="button" key={item.id} className="admin-user-row" onClick={() => openUserDetail(item.id)}>
                    <span>
                      <strong>{item.display_name || item.email}</strong>
                      <small>{item.email}</small>
                    </span>
                    <b>{item.balance}</b>
                    <small>{item.task_count} 任务 · {item.succeeded_image_count} 图</small>
                  </button>
                ))}
                {adminUsers.length === 0 ? <div className="empty mini">暂无用户</div> : null}
              </div>
            </section>

            <section className="settings-section">
              <div className="section-title">
                <Ticket size={22} />
                <div>
                  <h2>生成激活码</h2>
                  <p>明文激活码只在生成后显示一次。</p>
                </div>
              </div>
              <form className="activation-form" onSubmit={createCodes}>
                <input name="credit_amount" type="number" min={1} max={100000} placeholder="每个码的积分" required />
                <input name="count" type="number" min={1} max={200} defaultValue={1} placeholder="数量" required />
                <input name="expires_at" type="datetime-local" />
                <input name="note" placeholder="备注" />
                <button type="submit">
                  <Plus size={16} />
                  生成
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
        ) : null}
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

function TransactionList({ transactions }: { transactions: CreditTransaction[] }) {
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
