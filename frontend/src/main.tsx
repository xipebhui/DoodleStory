import { StrictMode, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertCircle,
  ArrowUpRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Download,
  Eye,
  Filter,
  FolderOpen,
  Images,
  KeyRound,
  LogOut,
  Loader2,
  Monitor,
  Plus,
  RefreshCw,
  Save,
  Search,
  Settings,
  Shield,
  Sparkles,
  Trash2,
  Upload,
  UserRound,
  X,
} from "lucide-react";
import { API_BASE_URL, api, type FileAsset, type Style, type StyleTest, type Task, type TaskSummary, type User } from "./api/client";
import "./styles/app.css";

type View = "tasks" | "styles" | "settings";
const TASK_ROW_IMAGE_PREVIEW_LIMIT = 4;
const aspectRatioOptions = ["1:1", "3:4", "4:3", "9:16", "16:9"];

type ImageTextPayload = {
  title?: string | null;
  narration?: string | null;
  dialogue?: string | null;
  emphasis?: string | null;
};

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

  const resolvedSrc = asset ? assetUrl(asset, variant) : api.assetContentUrl(assetId, variant);

  return (
    <img
      ref={imageRef}
      className={["lazy-asset-image", className].filter(Boolean).join(" ")}
      src={shouldLoad ? resolvedSrc : undefined}
      alt={alt}
      loading={eager ? "eager" : "lazy"}
      decoding="async"
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
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [view, setView] = useState<View>("tasks");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .me()
      .then((result) => setUser(result.user))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="center">加载中</div>;
  }

  if (!user) {
    return <AuthScreen mode={authMode} setMode={setAuthMode} onAuthed={setUser} />;
  }

  return (
    <Shell user={user} view={view} setView={setView} onLogout={() => setUser(null)}>
      {view === "tasks" ? <TasksView user={user} /> : null}
      {view === "styles" ? <StylesView user={user} /> : null}
      {view === "settings" ? <SettingsView user={user} onLogout={() => setUser(null)} /> : null}
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
  setView,
  onLogout,
  children,
}: {
  user: User;
  view: View;
  setView: (view: View) => void;
  onLogout: () => void;
  children: React.ReactNode;
}) {
  const items = [
    { key: "tasks" as const, label: "任务", icon: Images },
    { key: "styles" as const, label: "风格", icon: Sparkles },
    { key: "settings" as const, label: "设置", icon: Settings },
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
            <button key={item.key} className={view === item.key ? "active" : ""} onClick={() => setView(item.key)}>
              <item.icon size={18} />
              {item.label}
            </button>
          ))}
        </nav>
        <div className="user-box">
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
  adapt_story: "故事增强",
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
  return Boolean(task?.generated_images.some((image) => image.status === "queued" || image.status === "running"));
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
  task?.generated_images.forEach((image) => {
    groups.set(image.panel_id, [...(groups.get(image.panel_id) ?? []), image]);
  });
  groups.forEach((images, panelId) => {
    const active = images
      .filter((image) => image.status === "queued" || image.status === "running")
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

function TasksView({ user }: { user: User }) {
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
  const [creating, setCreating] = useState(false);
  const [createStyleId, setCreateStyleId] = useState("");
  const [countMode, setCountMode] = useState<"auto" | "fixed">("auto");
  const [storyInputMode, setStoryInputMode] = useState<"original" | "adapted">("original");
  const [selectedId, setSelectedId] = useState("");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [previewImageId, setPreviewImageId] = useState<string | null>(null);
  const [panelEditInputs, setPanelEditInputs] = useState<Record<string, string>>({});
  const [editingPanelId, setEditingPanelId] = useState<string | null>(null);
  const previewCloseRef = useRef<HTMLButtonElement | null>(null);

  const taskForDetail = selectedTask;
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

  useEffect(() => {
    refresh(undefined, { quiet: false });
  }, [query, statusFilter, styleFilter, cursor]);

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
	        setDetailOpen(false);
	        setSelectedTask(null);
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
      const nextSelectedId = preferredTaskId || selectedId;
      if (nextSelectedId && detailOpen) {
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
    setSelectedTask(await api.task(taskId));
    setDetailOpen(true);
    setPreviewImageId(null);
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
    const form = event.currentTarget;
    const formData = new FormData(event.currentTarget);
    const requested = Number(formData.get("requested_image_count"));
    if (!createStyleId) {
      setMessage("请选择一个风格");
      return;
    }
    try {
      setCreating(true);
      const task = await api.createTask({
        original_text: String(formData.get("original_text") ?? ""),
        story_input_mode: storyInputMode,
        image_count_mode: countMode,
        requested_image_count: countMode === "fixed" ? requested : null,
        style_id: createStyleId,
        use_character_references: formData.get("use_character_references") === "on",
      });
      form.reset();
      setCountMode("auto");
      setStoryInputMode("original");
      setCreateStyleId(styles[0]?.id ?? "");
      setCreateOpen(false);
      setMessage("任务已进入队列");
      await refresh(task.id);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "创建失败");
    } finally {
      setCreating(false);
    }
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
    try {
      const result = await api.createTaskDownload(selectedTask.id);
      if (result.status === "ready" && result.asset) {
        window.location.href = assetUrl(result.asset, "original");
      } else {
        setMessage(result.error_message ?? "下载包未就绪");
      }
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "打包下载失败");
    }
  }

  const canCancel =
    taskForDetail?.status === "queued" || taskForDetail?.status === "running" || taskForDetail?.status === "retrying";
  const canDownload = Boolean(
    succeededImages(taskForDetail).length,
  );
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
                      {task.story_input_mode === "adapted" ? "故事增强" : "完整故事"}
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
	                      {rowImages.length > 0 ? (
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
	        <div className="task-detail-backdrop" onClick={() => { setDetailOpen(false); setSelectedTask(null); }}>
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
	              <button type="button" className="icon-button" aria-label="关闭任务详情" onClick={() => { setDetailOpen(false); setSelectedTask(null); }}>
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
                    <Download size={16} />
                    下载图片
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
                  <strong>{taskForDetail.current_step ? stepLabels[taskForDetail.current_step] ?? taskForDetail.current_step : "等待任务"}</strong>
                  <span>{taskProgress(taskForDetail)}%</span>
                </div>
                <div className="progress-line large">
                  <span style={{ width: `${taskProgress(taskForDetail)}%` }} />
                </div>
              </section>

              {taskForDetail.steps.length > 0 ? (
                <section className="step-strip">
                  {taskForDetail.steps.map((step) => (
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

              {taskForDetail.story_input_mode === "adapted" ? (
                <section className="story-panel adapted-story-panel">
                  <h2>增强故事</h2>
                  {taskForDetail.adapted_story_title ? <strong>{taskForDetail.adapted_story_title}</strong> : null}
                  {taskForDetail.adapted_story_hook ? <small>{taskForDetail.adapted_story_hook}</small> : null}
                  <p>{taskForDetail.adapted_story_text ?? "等待 LLM 故事增强"}</p>
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
                        {image?.image_prompt || panel.generated_prompt ? <small>{image?.image_prompt ?? panel.generated_prompt}</small> : null}
                        {image?.user_instruction ? <small>修改方向：{image.user_instruction}</small> : null}
                        {image?.prompt_change_summary ? <small>修改摘要：{image.prompt_change_summary}</small> : null}
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
                            {versions.slice(0, 4).map((version) => (
                              <div key={version.id} className={`panel-version-item ${version.status}`}>
                                <span>v{version.generation_number}</span>
                                <strong>{imageSourceLabel(version.source_type)}</strong>
                                <em>{imageWorkflowLabel(version.workflow_step)}</em>
                                <small>{imageStatusLabel(version.status)}{version.is_current ? " · 当前" : ""}</small>
                              </div>
                            ))}
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
        <div className="drawer-backdrop" onClick={() => setCreateOpen(false)}>
          <aside className="task-create-drawer" onClick={(event) => event.stopPropagation()}>
            <div className="drawer-head">
              <div>
                <h2>创建任务</h2>
                <p>原文会原样保存，提交后进入生成队列。</p>
              </div>
              <button type="button" className="icon-button" aria-label="关闭创建任务" onClick={() => setCreateOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <form className="task-create-form" onSubmit={createTask}>
              <div className="segmented-control">
                <button
                  type="button"
                  className={storyInputMode === "original" ? "active" : ""}
                  onClick={() => setStoryInputMode("original")}
                >
                  完整故事
                </button>
                <button
                  type="button"
                  className={storyInputMode === "adapted" ? "active" : ""}
                  onClick={() => setStoryInputMode("adapted")}
                >
                  故事方案
                </button>
              </div>
              <label>
                {storyInputMode === "adapted" ? "故事方案或简化故事" : "原始文本"}
                <textarea
                  name="original_text"
                  placeholder={
                    storyInputMode === "adapted"
                      ? "输入故事设定、简短梗概或想法，系统会先整理成更抓人的故事"
                      : "输入原始故事文本，系统会原样保存"
                  }
                  required
                  autoFocus
                />
                {storyInputMode === "adapted" ? (
                  <small>原始输入会保留，生成前会新增一步 LLM 故事增强，并自动生成封面。</small>
                ) : null}
              </label>
              <fieldset className="style-picker">
                <legend>选择风格</legend>
                <p>通过参考图判断视觉方向，提交后会使用该风格绑定的模型名生成图片。</p>
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
                      <small>{selectedCreateStyle.reference_images.length} 张参考图 · 比例 {selectedCreateStyle.aspect_ratio} · {selectedCreateStyle.image_model_name}</small>
                    </div>
                  </div>
                ) : null}
                <div className="style-picker-grid">
                  {styles.map((style) => {
                    const assets = stylePreviewAssets(style);
                    return (
                      <button
                        type="button"
                        key={style.id}
                        className={`style-pick-card ${createStyleId === style.id ? "selected" : ""}`}
                        onClick={() => setCreateStyleId(style.id)}
                      >
                        <div className="style-pick-images">
                          {assets.slice(0, 4).map((asset) => (
                            <LazyAssetImage key={asset.id} asset={asset} assetId={asset.id} alt={style.name} />
                          ))}
                          {assets.length === 0 ? <span>模板比例</span> : null}
                        </div>
                        <div>
                          <strong>{style.name}</strong>
                          <small>{style.description || `${style.reference_images.length} 张参考图`} · 比例 {style.aspect_ratio} · {style.image_model_name}</small>
                        </div>
                        <span className={`status-pill ${style.status}`}>{style.status === "active" ? "启用" : style.status}</span>
                      </button>
                    );
                  })}
                </div>
              </fieldset>
              <div className="segmented-control">
                <button type="button" className={countMode === "auto" ? "active" : ""} onClick={() => setCountMode("auto")}>
                  自动
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
                </label>
              ) : null}
              <label className="character-reference-toggle">
                <input name="use_character_references" type="checkbox" />
                <span>
                  <strong>使用参考人物</strong>
                  <small>开启后会先识别主要人物并生成人物参考图，再用于后续分镜生图。</small>
                </span>
              </label>
              {message ? <p className="form-message">{message}</p> : null}
              <div className="drawer-actions">
                <button type="button" className="ghost-button" onClick={() => setCreateOpen(false)}>
                  取消
                </button>
                <button type="submit" disabled={creating}>
                  {creating ? <Loader2 size={17} className="spin" /> : <Plus size={17} />}
                  创建任务
                </button>
              </div>
            </form>
          </aside>
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
                <p>{previewImage.final_prompt ?? previewImage.image_prompt ?? ""}</p>
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

function StylesView({ user }: { user: User }) {
  const [styles, setStyles] = useState<Style[]>([]);
  const [message, setMessage] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<Style["status"] | "all">("all");
  const [styleDrawerOpen, setStyleDrawerOpen] = useState(false);
  const [styleFormMode, setStyleFormMode] = useState<"create" | "edit">("create");
  const [editingStyleId, setEditingStyleId] = useState("");
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
    setMessage("");
    setStyleDrawerOpen(true);
  }

  function startEdit(style: Style) {
    setEditingStyleId(style.id);
    setStyleFormMode("edit");
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
      style_prompt: String(formData.get("style_prompt") ?? ""),
      description: String(formData.get("description") ?? ""),
    };

    try {
      const saved =
        styleFormMode === "edit" && editingStyle
          ? await api.updateStyle(editingStyle.id, payload)
          : await api.createStyle(payload);
      setEditingStyleId(saved.id);
      setTestingStyleId(saved.id);
      setStyleFormMode("edit");
      setStyleDrawerOpen(false);
      setMessage(styleFormMode === "edit" ? "风格已保存" : "风格已创建");
      await refresh(saved.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    }
  }

  async function deleteStyle(style: Style) {
    if (!window.confirm(`删除风格「${style.name}」？已被任务引用的风格会被后端拒绝删除。`)) {
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
      setMessage(result.status === "succeeded" ? "风格测试已完成" : result.error_message ?? "风格测试未成功");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "风格测试失败");
    } finally {
      setStyleTestRunning(false);
    }
  }

  const formStyle = styleFormMode === "edit" ? editingStyle : null;

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
                  <p>测试图仅用于校准风格提示词和参考图方向。</p>
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
          <p>共 {styles.length} 个风格，{activeCount} 个启用。参考图会作为后续生图的视觉锚点，比例由风格模板控制。</p>
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
                  <strong>{style.name}</strong>
                  <span className={`status-pill ${style.status}`}>{style.status}</span>
                </div>
                <p>{style.description || "暂无描述"}</p>
                <small>{style.reference_images.length} 张参考图 · 比例 {style.aspect_ratio} · 模型 {style.image_model_name} · {style.last_tested_at ? `最近测试 ${formatDateTime(style.last_tested_at)}` : "未测试"}</small>
              </div>
              <div className="style-row-strip">
                {assets.slice(0, 5).map((asset) => (
                  <LazyAssetImage key={asset.id} asset={asset} assetId={asset.id} alt={style.name} />
                ))}
                {assets.length === 0 ? <span>无参考图</span> : null}
              </div>
              <div className="style-card-actions">
                <button type="button" className="secondary-button" onClick={() => startEdit(style)}>
                  编辑
                </button>
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
                <p>风格提示词、描述和参考图会用于任务生图。</p>
              </div>
              {styleFormMode === "edit" && formStyle ? (
                <button type="button" className="danger-button" onClick={() => deleteStyle(formStyle)}>
                  <Trash2 size={16} />
                </button>
              ) : null}
            </div>
            <input name="name" placeholder="风格名称" defaultValue={formStyle?.name ?? ""} required />
            <input name="image_model_name" placeholder="生图模型名，例如 gpt-image-2" defaultValue={formStyle?.image_model_name ?? ""} required />
            <select name="aspect_ratio" defaultValue={formStyle?.aspect_ratio ?? "9:16"} required>
              {aspectRatioOptions.map((ratio) => (
                <option key={ratio} value={ratio}>
                  画面比例 {ratio}
                </option>
              ))}
            </select>
            <select name="status" defaultValue={formStyle?.status ?? "draft"}>
              <option value="draft">草稿</option>
              <option value="active">启用</option>
              <option value="disabled">停用</option>
            </select>
            <textarea name="description" placeholder="描述" defaultValue={formStyle?.description ?? ""} />
            <textarea name="style_prompt" placeholder="风格提示词" defaultValue={formStyle?.style_prompt ?? ""} required />
            {message ? <p className="form-message">{message}</p> : null}
            <button type="submit">
              <Save size={16} />
              {styleFormMode === "edit" ? "保存风格" : "创建风格"}
            </button>
          </form>

          {formStyle ? (
            <section className="panel reference-panel">
              <div className="editor-title">
                <div>
                  <h2>参考图</h2>
                  <p>参考图会作为图生图参考，生成比例由风格模板控制。</p>
                </div>
                <label className="upload-button">
                  <Upload size={16} />
                  上传
                  <input type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={uploadReferences} />
                </label>
              </div>
              <div className="reference-grid">
                {formStyle.reference_images.length === 0 ? <div className="empty mini">暂无参考图</div> : null}
                {formStyle.reference_images.map((reference) => (
                  <figure key={reference.id} className="reference-item">
                    <LazyAssetImage asset={reference.asset} assetId={reference.asset.id} alt={reference.asset.original_filename ?? "参考图"} />
                    <button type="button" onClick={() => deleteReference(reference.id)}>
                      <Trash2 size={14} />
                    </button>
                  </figure>
                ))}
              </div>
            </section>
          ) : null}
          </aside>
        </div>
      ) : null}
    </section>
  );
}

function SettingsView({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [displayMode, setDisplayMode] = useState<"system" | "light" | "dark">("dark");
  const [archiveName, setArchiveName] = useState("doodlestory-task-{task_id}.zip");
  const apiBaseUrl = API_BASE_URL;

  async function logout() {
    await api.logout();
    onLogout();
  }

  return (
    <section className="page settings-page">
      <header className="page-header">
        <div>
          <h1>设置</h1>
          <p>管理账号、显示偏好、本地存储和下载规则。</p>
        </div>
      </header>

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
                <button type="button" className="secondary-button" disabled>
                  修改昵称
                </button>
                <button type="button" className="ghost-button" disabled>
                  修改密码
                </button>
                <button type="button" className="danger-button text-danger-button" onClick={logout}>
                  <LogOut size={16} />
                  退出登录
                </button>
              </div>
            </div>
          </section>

          <section className="settings-section setting-row">
            <div className="section-title">
              <Monitor size={22} />
              <div>
                <h2>显示模式</h2>
                <p>选择界面外观模式。</p>
              </div>
            </div>
            <div className="segmented-control setting-segment">
              <button type="button" className={displayMode === "system" ? "active" : ""} onClick={() => setDisplayMode("system")}>
                跟随系统
              </button>
              <button type="button" className={displayMode === "light" ? "active" : ""} onClick={() => setDisplayMode("light")}>
                浅色
              </button>
              <button type="button" className={displayMode === "dark" ? "active" : ""} onClick={() => setDisplayMode("dark")}>
                深色
              </button>
            </div>
          </section>

          <section className="settings-section">
            <div className="section-title">
              <FolderOpen size={22} />
              <div>
                <h2>本地存储说明</h2>
                <p>生成图和下载包由后端保存到本地磁盘。</p>
              </div>
            </div>
            <div className="info-lines">
              <div>
                <strong>存储位置</strong>
                <span>由服务端 DOODLESTORY_STORAGE_ROOT 控制，默认项目目录下 storage/。</span>
              </div>
              <div>
                <strong>访问方式</strong>
                <span>前端通过资产接口读取，不直接暴露本地文件路径。</span>
              </div>
              <div>
                <strong>当前 API</strong>
                <span>{apiBaseUrl}</span>
              </div>
            </div>
          </section>

          <section className="settings-section">
            <div className="section-title">
              <Download size={22} />
              <div>
                <h2>下载偏好</h2>
                <p>设置批量下载文件的命名展示。</p>
              </div>
            </div>
            <div className="download-preference">
              <label>
                压缩包文件名格式
                <input value={archiveName} onChange={(event) => setArchiveName(event.target.value)} />
              </label>
              <button type="button" className="secondary-button" onClick={() => setArchiveName("doodlestory-task-{task_id}.zip")}>
                恢复默认
              </button>
            </div>
            <div className="info-lines compact">
              <div>
                <strong>包含内容</strong>
                <span>仅包含成功生成的图片，不包含原文、日志或内部 prompt。</span>
              </div>
            </div>
          </section>

          <section className="settings-section">
            <div className="section-title">
              <Shield size={22} />
              <div>
                <h2>安全</h2>
                <p>密码、登录记录和帮助入口。</p>
              </div>
            </div>
            <div className="security-list">
              <div>
                <strong>密码与登录</strong>
                <span>密码修改和找回密码会在账号安全能力接入后开放。</span>
                <button type="button" className="secondary-button" disabled>
                  管理密码
                </button>
              </div>
              <div>
                <strong>最近登录记录</strong>
                <span>用于查看近期登录设备和时间。</span>
                <button type="button" className="ghost-button" disabled>
                  查看记录
                </button>
              </div>
            </div>
          </section>
        </div>

        <aside className="auth-preview-column">
          <section className="auth-preview-card">
            <div className="section-title">
              <KeyRound size={20} />
              <div>
                <h2>登录表单预览</h2>
                <p>账号相关操作的视觉基线。</p>
              </div>
            </div>
            <div className="mini-auth-form">
              <input value={user.email} readOnly aria-label="预览邮箱" />
              <input value="••••••••••••" readOnly aria-label="预览密码" />
              <label className="checkline">
                <input type="checkbox" />
                记住我
              </label>
              <button type="button">登录</button>
              <button type="button" className="link-button">
                还没有账号？立即注册
              </button>
            </div>
          </section>

          <section className="auth-preview-card">
            <h2>找回密码</h2>
            <p>输入注册邮箱后发送重置链接。邮件服务接入前保持禁用状态。</p>
            <div className="mini-auth-form">
              <input value={user.email} readOnly aria-label="找回密码邮箱" />
              <button type="button" disabled>
                发送重置链接
              </button>
            </div>
          </section>
        </aside>
      </div>
    </section>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
