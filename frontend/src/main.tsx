import { StrictMode, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertCircle,
  Archive,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  Box,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Coins,
  Copy,
  Download,
  Eye,
  Film,
  FileText,
  Filter,
  History,
  Images,
  LogOut,
  Loader2,
  MessageCircle,
  MoreHorizontal,
  Pencil,
  Play,
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
  agentEventStreamUrl,
  api,
  nativeAgentRunEventStreamUrl,
  type ActivationCode,
  type ActivationCodeCreated,
  type AgentConversation,
  type AgentConversationDetail,
  type AgentArtifact,
  type AgentPublicEvent,
  type AgentResourceOption,
  type AgentResourceRef,
  type AgentSkillAuthoringSuggestion,
  type AgentSkillDetail,
  type AgentSkillStatus,
  type AgentSkillSummary,
  type AgentSkillTool,
  type AgentSkillVersionDetail,
  type AgentSkillVersionSummary,
  type AgentRunStatus,
  type AgentRunSummary,
  type AgentTaskCard,
  type AgentTaskInspector,
  type NativeAgentConversation,
  type NativeAgentConversationDetail,
  type NativeAgentEvent,
  type NativeAgentRun,
  type PublishableVideo,
  type YoutubeChannelDetail,
  type YoutubeChannelSummary,
  type YoutubeUploadedVideo,
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
import { parseAgentRoute } from "./agentRoutes";
import "./styles/app.css";

type View = "agent" | "tasks" | "videoTasks" | "audioReferences" | "content" | "styles" | "characters" | "users" | "creditUsage" | "settings";
const TASK_ROW_IMAGE_PREVIEW_LIMIT = 4;
const CONTACT_WECHAT_QR_SRC = "/wechat-contact-qr.png";
const aspectRatioOptions = ["1:1", "3:4", "4:3", "9:16", "16:9"];
const imageModelNamePlaceholder = "生图模型名，例如 gpt-image-2";
const styleReferenceModeLabels: Record<Style["style_reference_mode"], string> = {
  prompt: "Prompt 参考",
  image: "参考图参考",
};
const viewRoutes: Record<View, string> = {
  agent: "/agent",
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
const lastAgentConversationKey = "doodlestory.agentLastConversationId";
const adminOnlyViews = new Set<View>(["videoTasks", "audioReferences", "users", "creditUsage"]);

function normalizedPathname(pathname: string) {
  return pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
}

function viewFromPathname(pathname: string): View | null {
  const path = normalizedPathname(pathname);
  if (parseAgentRoute(path)) return "agent";
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
  const agentRoute = parseAgentRoute(pathname);
  const routeAgentConversationId = agentRoute?.conversationId ?? null;
  const routeAgentSkillPage = agentRoute?.skillPage ?? null;
  const routeAgentChannelPage = agentRoute?.channelPage ?? null;
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
        onNavigatePath={navigateToPath}
        onLogout={() => setUser(null)}
      >
        <NotFoundView />
      </Shell>
    );
  }

  if (adminOnlyViews.has(view) && user.role !== "admin") {
    return (
      <Shell
        user={user}
        view={null}
        creditOverview={creditOverview}
        creditError={creditError}
        onNavigatePath={navigateToPath}
        onLogout={() => setUser(null)}
      >
        <NotFoundView />
      </Shell>
    );
  }

  if (view === "agent") {
    return (
      <main className="agent-module-shell">
        {routeAgentChannelPage ? (
          <YoutubeChannelManagementView
            user={user}
            creditOverview={creditOverview}
            creditError={creditError}
            route={routeAgentChannelPage}
            onNavigatePath={navigateToPath}
            onLogout={async () => {
              await api.logout();
              setUser(null);
            }}
          />
        ) : routeAgentSkillPage ? (
          <AgentSkillManagementView
            user={user}
            creditOverview={creditOverview}
            creditError={creditError}
            route={routeAgentSkillPage}
            onNavigatePath={navigateToPath}
            onLogout={async () => {
              await api.logout();
              setUser(null);
            }}
          />
        ) : (
          <NativeAgentView
            user={user}
            creditOverview={creditOverview}
            creditError={creditError}
            routeConversationId={routeAgentConversationId}
            onNavigatePath={navigateToPath}
            onLogout={async () => {
              await api.logout();
              setUser(null);
            }}
          />
        )}
      </main>
    );
  }

  return (
    <Shell
      user={user}
      view={view}
      creditOverview={creditOverview}
      creditError={creditError}
      onNavigatePath={navigateToPath}
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
            minLength={mode === "login" ? 1 : 8}
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
  onNavigatePath,
  onLogout,
  children,
}: {
  user: User;
  view: View | null;
  creditOverview: CreditOverview | null;
  creditError: string;
  onNavigatePath: (path: string) => void;
  onLogout: () => void;
  children: React.ReactNode;
}) {
  const items = [
    { key: "tasks" as const, label: "图文任务", icon: Images, path: viewRoutes.tasks },
    { key: "agent" as const, label: "Skill 管理", icon: Box, path: `${viewRoutes.agent}/skills` },
    ...(user.role === "admin" ? [{ key: "videoTasks" as const, label: "视频任务", icon: Film, path: viewRoutes.videoTasks }] : []),
    ...(user.role === "admin"
      ? [{ key: "audioReferences" as const, label: "音频管理", icon: Volume2, path: viewRoutes.audioReferences }]
      : []),
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
              className={view === item.key || (item.key === "tasks" && view === "agent") ? "active" : ""}
              href={item.path}
              onClick={(event) => {
                event.preventDefault();
                onNavigatePath(item.path);
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

function CreationModeSwitch({
  active,
  onNavigatePath,
}: {
  active: "tasks" | "agent";
  onNavigatePath: (path: string, options?: { replace?: boolean }) => void;
}) {
  const lastConversationId = window.sessionStorage.getItem(lastAgentConversationKey);
  const agentPath = lastConversationId ? `${viewRoutes.agent}/${encodeURIComponent(lastConversationId)}` : viewRoutes.agent;
  return (
    <nav className="creation-mode-switch" aria-label="图文创作方式">
      <a
        href={viewRoutes.tasks}
        className={active === "tasks" ? "active" : ""}
        aria-current={active === "tasks" ? "page" : undefined}
        onClick={(event) => {
          event.preventDefault();
          onNavigatePath(viewRoutes.tasks);
        }}
      >
        传统构建
      </a>
      <a
        href={agentPath}
        className={active === "agent" ? "active" : ""}
        aria-current={active === "agent" ? "page" : undefined}
        onClick={(event) => {
          event.preventDefault();
          onNavigatePath(agentPath);
        }}
      >
        AI 构建
      </a>
    </nav>
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
      <div className="empty">请从左侧导航进入图文任务、内容提取、风格或设置页面。</div>
    </section>
  );
}

const activeAgentRunStatuses = new Set<AgentRunStatus>([
  "queued",
  "running",
  "waiting_for_tool",
  "retrying",
  "waiting_for_input",
  "cancel_requested",
]);

function agentRunStatusLabel(status: AgentRunStatus) {
  const labels: Record<AgentRunStatus, string> = {
    queued: "等待导演处理",
    running: "正在整理漫画方案",
    waiting_for_tool: "正在生成真实图片",
    waiting_for_input: "等待你确认方案",
    paused: "已暂停",
    retrying: "模型线路重试中",
    succeeded: "本轮已完成",
    failed: "本轮失败",
    cancel_requested: "取消中",
    cancelled: "已取消",
  };
  return labels[status];
}

function agentTaskStatusLabel(status: AgentTaskCard["status"]) {
  if (status === "succeeded") return "漫画已完成";
  if (status === "partial_succeeded") return "部分图片失败";
  if (status === "failed") return "生成失败";
  if (status === "cancel_requested") return "取消中";
  if (status === "cancelled") return "已取消";
  return "图片生成中";
}

function AgentTaskCardView({
  card,
  runStatus,
  onOpenTask,
  onReferenceTask,
}: {
  card: AgentTaskCard;
  runStatus: AgentRunStatus | null;
  onOpenTask: (taskId: string, trigger: HTMLButtonElement) => void;
  onReferenceTask: (card: AgentTaskCard) => void;
}) {
  const progressPercent =
    card.progress_total > 0
      ? Math.min(100, Math.round((card.progress_current / card.progress_total) * 100))
      : 0;
  return (
    <article className="agent-task-card">
      <header>
        <div>
          <span className="agent-eyebrow">漫画任务 · {card.panels.length} 个 Panel</span>
          <h3>{card.title}</h3>
        </div>
        <span className={`status ${card.status}`}>{agentTaskStatusLabel(card.status)}</span>
      </header>
      <div className="agent-task-progress" aria-label={`任务进度 ${card.progress_current}/${card.progress_total}`}>
        <span style={{ width: `${progressPercent}%` }} />
      </div>
      <div className="agent-task-summary">
        <span>{card.progress_current}/{card.progress_total || card.panels.length} 已完成</span>
        <span>{runStatus ? agentRunStatusLabel(runStatus) : agentTaskStatusLabel(card.status)}</span>
      </div>
      <div className="agent-panel-strip" aria-label="任务 Panel 预览">
        {card.panels.map((panel) => (
          <section className="agent-panel-compact" key={panel.id}>
            <div className="agent-panel-thumbnail">
              {panel.image?.status === "succeeded" && panel.image.asset_id ? (
                <LazyAssetImage
                  assetId={panel.image.asset_id}
                  alt={`第 ${panel.panel_order} 格：${panel.story_beat}`}
                  variant="original"
                />
              ) : panel.image?.status === "failed" || panel.image?.status === "cancelled" ? (
                <div className="agent-panel-state is-error">
                  <AlertCircle size={16} />
                </div>
              ) : (
                <div className="agent-panel-state">
                  <Loader2 className="spin" size={16} />
                </div>
              )}
            </div>
            <div>
              <strong>Panel {panel.panel_order}</strong>
              <span>{panel.story_beat}</span>
              <small>
                {panel.image?.status === "succeeded"
                  ? "当前图片"
                  : panel.image?.status === "failed"
                    ? "生成失败"
                    : panel.image?.status === "running"
                      ? "生成中"
                      : "等待生成"}
              </small>
            </div>
          </section>
        ))}
      </div>
      {card.error_message ? <p className="error agent-card-error">{card.error_message}</p> : null}
      <footer className="agent-task-card-footer">
        <span title={card.task_id}>任务 ID · {card.task_id}</span>
        <button
          type="button"
          className="ghost-button"
          onClick={() => onReferenceTask(card)}
        >
          在对话中引用
        </button>
        <button
          type="button"
          className="secondary-button"
          onClick={(event) => onOpenTask(card.task_id, event.currentTarget)}
        >
          查看任务
          <ArrowUpRight size={16} />
        </button>
      </footer>
    </article>
  );
}

function agentDraftKey(conversationId: string, field: "idea" | "resources") {
  return `doodlestory.agentDraft.${conversationId}.${field}`;
}

const newAgentDraftId = "new";

const agentResourceKindLabels: Record<AgentResourceRef["kind"], string> = {
  skill: "Skill",
  style: "风格",
  character: "角色",
  task: "任务",
  panel: "Panel",
  image_version: "图片版本",
};

function parseAgentDraftResources(raw: string | null): AgentResourceRef[] {
  if (!raw) return [];
  const value = JSON.parse(raw) as unknown;
  if (
    !Array.isArray(value) ||
    value.some(
      (item) =>
        typeof item !== "object" ||
        item === null ||
        !["skill", "style", "character", "task", "panel", "image_version"].includes(
          String((item as Record<string, unknown>).kind),
        ) ||
        typeof (item as Record<string, unknown>).id !== "string",
    )
  ) {
    throw new Error("当前会话保存的资源草稿无法读取，请移除后重新选择");
  }
  return value.map((item) => {
    const ref = item as Record<string, unknown>;
    return {
      kind: ref.kind as AgentResourceRef["kind"],
      id: String(ref.id),
      display_name: typeof ref.display_name === "string" ? ref.display_name : null,
    };
  });
}

const chinaTimeZone = "Asia/Shanghai";
const chinaDateKeyFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: chinaTimeZone,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

function chinaDateNumber(value: Date) {
  const parts = chinaDateKeyFormatter.formatToParts(value);
  const year = Number(parts.find((part) => part.type === "year")?.value);
  const month = Number(parts.find((part) => part.type === "month")?.value);
  const day = Number(parts.find((part) => part.type === "day")?.value);
  return Date.UTC(year, month - 1, day);
}

function agentConversationGroupLabel(value: string) {
  const dayOffset = Math.round(
    (chinaDateNumber(new Date()) - chinaDateNumber(new Date(value))) / 86_400_000,
  );
  if (dayOffset === 0) return "今天";
  if (dayOffset === 1) return "昨天";
  if (dayOffset < 7) return "最近 7 天";
  return "更早";
}

function agentConversationTime(value: string) {
  const date = new Date(value);
  const group = agentConversationGroupLabel(value);
  if (group === "今天") {
    return date.toLocaleTimeString("zh-CN", {
      timeZone: chinaTimeZone,
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  if (group === "昨天") return "昨天";
  return date.toLocaleDateString("zh-CN", {
    timeZone: chinaTimeZone,
    month: "numeric",
    day: "numeric",
  });
}

function agentConversationSummary(conversation: AgentConversation, detail: AgentConversationDetail | null) {
  if (detail?.id === conversation.id) {
    const message = [...detail.messages].reverse().find((item) => item.role !== "task_card");
    if (message?.content) return message.content;
  }
  return conversation.status === "archived" ? "已归档的历史对话" : "继续上次创作";
}

function agentImageStatusLabel(
  status: NonNullable<AgentTaskCard["panels"][number]["image"]>["status"],
) {
  const labels = {
    queued: "等待生成",
    running: "生成中",
    succeeded: "已完成",
    failed: "生成失败",
    cancelled: "已取消",
  };
  return labels[status];
}

function AgentTaskInspectorDialog({
  inspector,
  loading,
  error,
  selectedPanelId,
  onSelectPanel,
  onReferenceTask,
  onReferencePanel,
  onReferenceImage,
  run,
  onRegenerate,
  onAcceptVersion,
  onRestoreVersion,
  onPauseRun,
  onResumeRun,
  onRetry,
  onClose,
}: {
  inspector: AgentTaskInspector | null;
  loading: boolean;
  error: string;
  selectedPanelId: string;
  onSelectPanel: (panelId: string) => void;
  onReferenceTask: (inspector: AgentTaskInspector) => void;
  onReferencePanel: (
    inspector: AgentTaskInspector,
    panel: AgentTaskInspector["panels"][number],
  ) => void;
  onReferenceImage: (
    inspector: AgentTaskInspector,
    panel: AgentTaskInspector["panels"][number],
    image: AgentTaskInspector["panels"][number]["versions"][number],
  ) => void;
  run: AgentRunSummary | null;
  onRegenerate: (
    panel: AgentTaskInspector["panels"][number],
    instruction: string,
    allowAutoRevision: boolean,
  ) => Promise<boolean>;
  onAcceptVersion: (
    panel: AgentTaskInspector["panels"][number],
    image: AgentTaskInspector["panels"][number]["versions"][number],
  ) => Promise<void>;
  onRestoreVersion: (
    panel: AgentTaskInspector["panels"][number],
    image: AgentTaskInspector["panels"][number]["versions"][number],
  ) => Promise<void>;
  onPauseRun: (runId: string) => Promise<void>;
  onResumeRun: (runId: string) => Promise<void>;
  onRetry: () => void;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const [revisionInstruction, setRevisionInstruction] = useState("");
  const [allowAutoRevision, setAllowAutoRevision] = useState(false);
  const [busyAction, setBusyAction] = useState("");
  const selectedPanel =
    inspector?.panels.find((panel) => panel.id === selectedPanelId) ||
    inspector?.panels[0] ||
    null;

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="agent-inspector-backdrop">
      <div
        ref={dialogRef}
        className="agent-task-inspector"
        role="dialog"
        aria-modal="true"
        aria-labelledby="agent-inspector-title"
      >
        <header className="agent-inspector-header">
          <div>
            <span className="agent-eyebrow">AI 任务检查器 · 版本操作</span>
            <h2 id="agent-inspector-title">{inspector?.title || "任务详情"}</h2>
            {inspector ? (
              <p>
                {agentTaskStatusLabel(inspector.status)} · 进度 {inspector.progress_current}/
                {inspector.progress_total || inspector.panels.length} · {inspector.panels.length} Panels
              </p>
            ) : null}
          </div>
          <div className="agent-inspector-header-actions">
            {run && ["queued", "running", "retrying", "waiting_for_tool"].includes(run.status) ? (
              <button
                type="button"
                disabled={Boolean(busyAction)}
                onClick={async () => {
                  setBusyAction("pause");
                  try {
                    await onPauseRun(run.id);
                  } finally {
                    setBusyAction("");
                  }
                }}
              >
                {busyAction === "pause" ? <Loader2 className="spin" size={15} /> : null}
                暂停后续步骤
              </button>
            ) : run?.status === "paused" ? (
              <button
                type="button"
                disabled={Boolean(busyAction)}
                onClick={async () => {
                  setBusyAction("resume");
                  try {
                    await onResumeRun(run.id);
                  } finally {
                    setBusyAction("");
                  }
                }}
              >
                {busyAction === "resume" ? <Loader2 className="spin" size={15} /> : null}
                继续运行
              </button>
            ) : null}
            {inspector ? (
              <button type="button" onClick={() => onReferenceTask(inspector)}>
                在对话中引用任务
              </button>
            ) : null}
            <button type="button" aria-label="关闭任务检查器" onClick={onClose} autoFocus>
              <X size={19} />
            </button>
          </div>
        </header>

        {loading ? (
          <div className="agent-inspector-state">
            <Loader2 className="spin" size={22} />
            <span>正在读取真实任务数据…</span>
          </div>
        ) : error && !inspector ? (
          <div className="agent-inspector-state is-error">
            <AlertCircle size={22} />
            <strong>任务读取失败</strong>
            <span>{error}</span>
            <button type="button" className="secondary-button" onClick={onRetry}>
              <RefreshCw size={15} />
              重新读取
            </button>
          </div>
        ) : inspector && inspector.panels.length === 0 ? (
          <div className="agent-inspector-state">
            <Images size={22} />
            <span>这个任务还没有生成 Panel。</span>
          </div>
        ) : inspector && selectedPanel ? (
          <div className="agent-inspector-body">
            {error ? <div className="error agent-inspector-action-error">{error}</div> : null}
            <aside className="agent-inspector-panel-list" aria-label="Panel 列表">
              {inspector.panels.map((panel) => (
                <button
                  type="button"
                  key={panel.id}
                  className={panel.id === selectedPanel.id ? "active" : ""}
                  aria-pressed={panel.id === selectedPanel.id}
                  onClick={() => onSelectPanel(panel.id)}
                >
                  <span className="agent-inspector-panel-thumb">
                    {panel.current_image?.status === "succeeded" && panel.current_image.asset_id ? (
                      <LazyAssetImage
                        assetId={panel.current_image.asset_id}
                        alt={`Panel ${panel.panel_order}`}
                        variant="original"
                      />
                    ) : panel.status === "failed" || panel.status === "cancelled" ? (
                      <AlertCircle size={16} />
                    ) : (
                      <Loader2 className={panel.status === "running" ? "spin" : ""} size={16} />
                    )}
                  </span>
                  <span>
                    <strong>Panel {panel.panel_order}</strong>
                    <small>{panel.status ? agentImageStatusLabel(panel.status) : "等待图片"}</small>
                  </span>
                </button>
              ))}
            </aside>

            <section className="agent-inspector-detail">
              <div className="agent-inspector-image">
                {selectedPanel.current_image?.status === "succeeded" &&
                selectedPanel.current_image.asset_id ? (
                  <LazyAssetImage
                    assetId={selectedPanel.current_image.asset_id}
                    alt={`Panel ${selectedPanel.panel_order} 当前图片`}
                    variant="original"
                    eager
                  />
                ) : selectedPanel.current_image?.status === "failed" ||
                  selectedPanel.current_image?.status === "cancelled" ? (
                  <div className="agent-inspector-image-state is-error">
                    <AlertCircle size={24} />
                    <span>
                      {selectedPanel.current_image.error_message ||
                        selectedPanel.error_message ||
                        "当前图片生成失败"}
                    </span>
                  </div>
                ) : (
                  <div className="agent-inspector-image-state">
                    <Loader2
                      className={selectedPanel.current_image?.status === "running" ? "spin" : ""}
                      size={24}
                    />
                    <span>
                      {selectedPanel.current_image?.status === "running"
                        ? "当前图片生成中"
                        : "当前 Panel 暂无图片"}
                    </span>
                  </div>
                )}
              </div>

              <div className="agent-inspector-copy">
                <div>
                  <span>当前选择</span>
                  <strong>Panel {selectedPanel.panel_order}</strong>
                </div>
                <div>
                  <span>当前版本</span>
                  <strong>
                    {selectedPanel.current_image
                      ? `v${selectedPanel.current_image.generation_number}`
                      : "尚无版本"}
                  </strong>
                </div>
                <section>
                  <span>剧情目标</span>
                  <p>{selectedPanel.story_beat}</p>
                </section>
                {selectedPanel.visual_goal ? (
                  <section>
                    <span>画面目标</span>
                    <p>{selectedPanel.visual_goal}</p>
                  </section>
                ) : null}
                {selectedPanel.error_message ? (
                  <section className="is-error">
                    <span>错误信息</span>
                    <p>{selectedPanel.error_message}</p>
                  </section>
                ) : null}
                {selectedPanel.current_image?.inspection ? (
                  <section className="agent-inspection-summary">
                    <span>真实 VL 检查</span>
                    <p>
                      结论：{selectedPanel.current_image.inspection.verdict} ·{" "}
                      {Object.entries(selectedPanel.current_image.inspection.scores)
                        .map(([key, score]) => `${key} ${Math.round(score * 100)}`)
                        .join(" / ")}
                    </p>
                    {selectedPanel.current_image.inspection.issues.map((issue) => (
                      <p key={`${issue.code}-${issue.message}`}>
                        {issue.message}
                        {issue.suggested_change ? `；建议：${issue.suggested_change}` : ""}
                      </p>
                    ))}
                  </section>
                ) : null}
                {selectedPanel.current_image?.status === "succeeded" ? (
                  <section className="agent-panel-revision">
                    <label htmlFor={`agent-revision-${selectedPanel.id}`}>
                      再生成一个版本
                    </label>
                    <textarea
                      id={`agent-revision-${selectedPanel.id}`}
                      value={revisionInstruction}
                      onChange={(event) => setRevisionInstruction(event.target.value)}
                      placeholder="例如：表情更紧张，衣服、构图和场景不变"
                    />
                    <label className="agent-inline-check">
                      <input
                        type="checkbox"
                        checked={allowAutoRevision}
                        onChange={(event) => setAllowAutoRevision(event.target.checked)}
                      />
                      VL 建议修改时，授权本轮最多自动再生成 1 个版本
                    </label>
                    <button
                      type="button"
                      disabled={!revisionInstruction.trim() || Boolean(busyAction)}
                      onClick={async () => {
                        const confirmed = window.confirm(
                          "将复用当前任务的风格、比例、角色参考与当前 Prompt，创建并保留一个新版本。成功产出预计扣 1 积分，旧版本不会删除。是否继续？",
                        );
                        if (!confirmed) return;
                        setBusyAction("regenerate");
                        try {
                          const succeeded = await onRegenerate(
                            selectedPanel,
                            revisionInstruction.trim(),
                            allowAutoRevision,
                          );
                          if (succeeded) setRevisionInstruction("");
                        } finally {
                          setBusyAction("");
                        }
                      }}
                    >
                      {busyAction === "regenerate" ? <Loader2 className="spin" size={15} /> : <Sparkles size={15} />}
                      创建新版本（预计 1 积分）
                    </button>
                  </section>
                ) : null}
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => onReferencePanel(inspector, selectedPanel)}
                >
                  引用 Panel {selectedPanel.panel_order} 并继续对话
                </button>
              </div>

              <section className="agent-version-summary">
                <header>
                  <strong>图片版本</strong>
                  <span>最多显示最近 20 个版本</span>
                </header>
                {selectedPanel.versions.length > 0 ? (
                  <ol>
                    {selectedPanel.versions.map((version) => (
                      <li key={version.id}>
                        <strong>v{version.generation_number}</strong>
                        <span>{agentImageStatusLabel(version.status)}</span>
                        {version.is_current ? <small>当前</small> : null}
                        {version.accepted_at ? <small>已接受</small> : null}
                        <time>
                          {new Date(version.created_at).toLocaleString("zh-CN", {
                            timeZone: chinaTimeZone,
                          })}
                        </time>
                        <button
                          type="button"
                          onClick={() => onReferenceImage(inspector, selectedPanel, version)}
                        >
                          引用
                        </button>
                        {version.status === "succeeded" && version.is_current && !version.accepted_at ? (
                          <button
                            type="button"
                            disabled={Boolean(busyAction)}
                            onClick={async () => {
                              setBusyAction(`accept-${version.id}`);
                              try {
                                await onAcceptVersion(selectedPanel, version);
                              } finally {
                                setBusyAction("");
                              }
                            }}
                          >
                            接受当前版本
                          </button>
                        ) : null}
                        {version.status === "succeeded" && !version.is_current ? (
                          <button
                            type="button"
                            disabled={Boolean(busyAction)}
                            onClick={async () => {
                              setBusyAction(`restore-${version.id}`);
                              try {
                                await onRestoreVersion(selectedPanel, version);
                              } finally {
                                setBusyAction("");
                              }
                            }}
                          >
                            恢复此版本
                          </button>
                        ) : null}
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p>暂无图片版本。</p>
                )}
              </section>
            </section>
          </div>
        ) : null}
      </div>
    </div>
  );
}

const agentSkillTemplate = `# 目标
说明这个 Skill 要完成什么。

# 输入
说明需要理解哪些用户要求和资源。

# 方法
按自然语言描述推荐步骤和判断方式。

# 用户确认
说明哪些动作前需要把什么内容交给用户确认。

# 质量门槛
说明什么结果才算合格。

# 完成条件
说明何时停止并向用户汇报。`;

const agentSkillStatusLabels: Record<AgentSkillStatus, string> = {
  draft: "草稿",
  published: "已发布",
  archived: "已归档",
};

const agentToolDisplayNames: Record<string, string> = {
  capture_wechat_article: "微信公众号文章",
  generate_image: "生成图片",
  inspect_image: "检查图片",
  generate_speech: "生成语音",
  generate_subtitles: "生成字幕",
  render_story_video: "生成故事视频",
  publish_youtube_video: "发布 YouTube 视频",
};

function agentToolDisplayName(toolName: string) {
  return agentToolDisplayNames[toolName] || toolName;
}

function skillTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    timeZone: chinaTimeZone,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function AgentStudioSidebar({
  user,
  creditOverview,
  creditError,
  activeSkills,
  activeChannels = false,
  onNavigatePath,
  onLogout,
}: {
  user: User;
  creditOverview: CreditOverview | null;
  creditError: string;
  activeSkills: boolean;
  activeChannels?: boolean;
  onNavigatePath: (path: string, options?: { replace?: boolean }) => void;
  onLogout: () => Promise<void>;
}) {
  const [conversations, setConversations] = useState<NativeAgentConversation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .nativeAgentConversations(8)
      .then((result) => setConversations(result.items))
      .catch(() => setConversations([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <aside className="agent-skill-sidebar">
      <div className="agent-module-brand">
        <span className="brand-mark">
          <img className="brand-icon" src="/doodlestory-icon.svg" alt="" />
        </span>
        <div>
          <strong>DoodleStory</strong>
          <span>Agent Studio</span>
        </div>
      </div>
      <nav className="agent-studio-primary-nav" aria-label="Agent Studio">
        <button type="button" onClick={() => onNavigatePath("/agent")}>
          <Plus size={17} />
          新对话
        </button>
        <button
          type="button"
          className={activeSkills ? "active" : ""}
          aria-current={activeSkills ? "page" : undefined}
          onClick={() => onNavigatePath("/agent/skills")}
        >
          <Box size={17} />
          Skill 管理
        </button>
        {user.role === "admin" ? (
          <button
            type="button"
            className={activeChannels ? "active" : ""}
            aria-current={activeChannels ? "page" : undefined}
            onClick={() => onNavigatePath("/agent/channels")}
          >
            <BarChart3 size={17} />
            频道账号
          </button>
        ) : null}
        <button type="button" onClick={() => onNavigatePath("/agent")}>
          <Search size={17} />
          搜索对话
        </button>
        <a
          href={viewRoutes.tasks}
          onClick={(event) => {
            event.preventDefault();
            onNavigatePath(viewRoutes.tasks);
          }}
        >
          <Images size={17} />
          返回传统工作台
        </a>
      </nav>
      <div className="agent-studio-history">
        <span>最近对话</span>
        {loading ? <p>加载中…</p> : null}
        {!loading && conversations.length === 0 ? <p>暂无历史对话</p> : null}
        {conversations.map((conversation) => (
          <button
            type="button"
            key={conversation.id}
            onClick={() =>
              onNavigatePath(`/agent/${encodeURIComponent(conversation.id)}`)
            }
          >
            <i />
            <span>
              <strong>{conversation.title}</strong>
              <small>{agentConversationTime(conversation.last_message_at)}</small>
            </span>
          </button>
        ))}
      </div>
      <div className="agent-account-panel">
        <div className="agent-account-credit">
          <Coins size={16} />
          <span>
            <strong>
              {creditOverview
                ? `${creditOverview.account.balance} 积分`
                : creditError
                  ? "积分不可用"
                  : "积分加载中"}
            </strong>
            <small>{creditError || "成功出图扣 1 分"}</small>
          </span>
        </div>
        <div className="agent-account-user">
          <span>{(user.display_name || user.email).slice(0, 1).toUpperCase()}</span>
          <div>
            <strong>{user.display_name || user.email}</strong>
            <small>个人工作区</small>
          </div>
          <button type="button" aria-label="退出登录" onClick={() => void onLogout()}>
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  );
}

function AgentSkillListView({
  onNavigatePath,
}: {
  onNavigatePath: (path: string) => void;
}) {
  const storedScope = window.sessionStorage.getItem("doodlestory.agentSkillScope");
  const [scope, setScope] = useState<"mine" | "system">(
    storedScope === "system" ? "system" : "mine",
  );
  const [query, setQuery] = useState(
    () => window.sessionStorage.getItem("doodlestory.agentSkillQuery") || "",
  );
  const [statusFilter, setStatusFilter] = useState<AgentSkillStatus | "">(
    () =>
      (window.sessionStorage.getItem("doodlestory.agentSkillStatus") as
        | AgentSkillStatus
        | "") || "",
  );
  const [page, setPage] = useState(
    () => Number(window.sessionStorage.getItem("doodlestory.agentSkillPage") || "1"),
  );
  const [result, setResult] = useState<{
    items: AgentSkillSummary[];
    total: number;
    has_more: boolean;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    window.sessionStorage.setItem("doodlestory.agentSkillScope", scope);
    window.sessionStorage.setItem("doodlestory.agentSkillQuery", query);
    window.sessionStorage.setItem("doodlestory.agentSkillStatus", statusFilter);
    window.sessionStorage.setItem("doodlestory.agentSkillPage", String(page));
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError("");
      api
        .agentSkills({
          scope,
          status: statusFilter,
          query,
          page,
          page_size: 10,
        })
        .then((data) =>
          setResult({
            items: data.items,
            total: data.total,
            has_more: data.has_more,
          }),
        )
        .catch((loadError) =>
          setError(loadError instanceof Error ? loadError.message : "Skill 加载失败"),
        )
        .finally(() => setLoading(false));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [scope, query, statusFilter, page, reloadToken]);

  function changeScope(next: "mine" | "system") {
    setScope(next);
    setPage(1);
    setStatusFilter("");
  }

  return (
    <section className="agent-skill-list-page">
      <header className="agent-skill-page-header">
        <div>
          <h1>Skill 管理</h1>
          <p>把你的创作方法保存为可复用的 Agent 能力</p>
        </div>
        <button type="button" onClick={() => onNavigatePath("/agent/skills/new")}>
          <Plus size={17} />
          创建 Skill
        </button>
      </header>
      <div className="agent-skill-list-toolbar">
        <div className="agent-skill-scope-tabs" role="tablist" aria-label="Skill 范围">
          <button
            type="button"
            role="tab"
            aria-selected={scope === "mine"}
            className={scope === "mine" ? "active" : ""}
            onClick={() => changeScope("mine")}
          >
            我的 Skill
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={scope === "system"}
            className={scope === "system" ? "active" : ""}
            onClick={() => changeScope("system")}
          >
            系统 Skill
          </button>
        </div>
        <label className="agent-skill-search">
          <Search size={17} />
          <input
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder="搜索名称或适用场景"
          />
        </label>
        {scope === "mine" ? (
          <label className="agent-skill-status-filter">
            <Filter size={16} />
            <select
              aria-label="Skill 状态"
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value as AgentSkillStatus | "");
                setPage(1);
              }}
            >
              <option value="">可用状态</option>
              <option value="draft">草稿</option>
              <option value="published">已发布</option>
              <option value="archived">已归档</option>
            </select>
          </label>
        ) : null}
      </div>
      <div className="agent-skill-table-head" aria-hidden="true">
        <span>名称 / 描述</span>
        <span>状态</span>
        <span>版本</span>
        <span>Tools</span>
        <span>更新时间</span>
        <span>操作</span>
      </div>
      <div className="agent-skill-rows" aria-live="polite">
        {loading ? (
          <div className="agent-skill-state">
            <Loader2 className="spin" size={20} />
            正在加载 Skill…
          </div>
        ) : null}
        {error ? (
          <div className="agent-skill-state is-error">
            <AlertCircle size={20} />
            <span>{error}</span>
            <button type="button" onClick={() => setReloadToken((value) => value + 1)}>
              重试
            </button>
          </div>
        ) : null}
        {!loading && !error && result?.items.length === 0 ? (
          <div className="agent-skill-state">
            <BookOpen size={24} />
            <strong>{query ? "没有匹配的 Skill" : scope === "mine" ? "还没有个人 Skill" : "暂无系统 Skill"}</strong>
            <span>{query ? "尝试更换搜索词或状态筛选。" : "从一个清楚的创作方法开始。"}</span>
          </div>
        ) : null}
        {!loading &&
          !error &&
          result?.items.map((skill, index) => (
            <article
              key={skill.id}
              className={skill.status === "archived" ? "archived" : ""}
            >
              <span className="agent-skill-index">{(page - 1) * 10 + index + 1}</span>
              <div className="agent-skill-name-cell">
                <strong>{skill.name}</strong>
                <p>{skill.description}</p>
              </div>
              <span className={`agent-skill-status is-${skill.status}`}>
                {agentSkillStatusLabels[skill.status]}
              </span>
              <span>
                {skill.active_version
                  ? `v${skill.active_version.version}${skill.active_version.is_active ? " · 当前" : ""}`
                  : "尚未发布"}
              </span>
              <span className="agent-skill-tools">
                {skill.tool_names.length
                  ? skill.tool_names.map((tool) => (
                      <i key={tool}>{agentToolDisplayName(tool)}</i>
                    ))
                  : "无创作 Tool"}
              </span>
              <time>{skillTime(skill.updated_at)}</time>
              <div className="agent-skill-row-actions">
                <button
                  type="button"
                  className="agent-skill-row-action"
                  onClick={() => onNavigatePath(`/agent/skills/${encodeURIComponent(skill.id)}`)}
                >
                  <Eye size={15} />
                  查看详情
                </button>
                {skill.scope === "mine" && skill.status !== "archived" ? (
                  <button
                    type="button"
                    className="agent-skill-row-action"
                    onClick={() =>
                      onNavigatePath(`/agent/skills/${encodeURIComponent(skill.id)}/edit`)
                    }
                  >
                    <Pencil size={15} />
                    编辑
                  </button>
                ) : null}
              </div>
              <MoreHorizontal size={17} aria-hidden="true" />
            </article>
          ))}
      </div>
      <footer className="agent-skill-list-footer">
        <span>共 {result?.total || 0} 项</span>
        <div>
          <button
            type="button"
            aria-label="上一页"
            disabled={page <= 1 || loading}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
          >
            <ChevronLeft size={17} />
          </button>
          <strong>{page}</strong>
          <button
            type="button"
            aria-label="下一页"
            disabled={!result?.has_more || loading}
            onClick={() => setPage((value) => value + 1)}
          >
            <ChevronRight size={17} />
          </button>
        </div>
      </footer>
    </section>
  );
}

type AgentSkillFormState = {
  name: string;
  description: string;
  instructions: string;
  toolNames: string[];
};

function AgentSkillDetailView({
  skillId,
  onNavigatePath,
}: {
  skillId: string;
  onNavigatePath: (path: string) => void;
}) {
  const [skill, setSkill] = useState<AgentSkillDetail | null>(null);
  const [tools, setTools] = useState<AgentSkillTool[]>([]);
  const [versions, setVersions] = useState<AgentSkillVersionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [cloning, setCloning] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    Promise.all([
      api.agentSkill(skillId),
      api.agentSkillTools(),
      api.agentSkillVersions(skillId),
    ])
      .then(([detail, toolCatalog, versionPage]) => {
        if (cancelled) return;
        setSkill(detail);
        setTools(toolCatalog);
        setVersions(versionPage.items);
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Skill 详情加载失败");
        }
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [skillId]);

  if (loading) {
    return (
      <div className="agent-skill-state page">
        <Loader2 className="spin" size={22} />
        正在加载 Skill 详情…
      </div>
    );
  }
  if (!skill) {
    return (
      <div className="agent-skill-state page is-error">
        <AlertCircle size={22} />
        <strong>{error || "Skill 不存在"}</strong>
        <button type="button" onClick={() => onNavigatePath("/agent/skills")}>
          返回 Skill 管理
        </button>
      </div>
    );
  }

  const toolLabels = new Map(tools.map((tool) => [tool.name, tool.display_name]));
  const canEdit = !skill.is_read_only && skill.status !== "archived";

  return (
    <section className="agent-skill-detail-page">
      <header className="agent-skill-page-header">
        <div>
          <span>Skill 管理 / 详情</span>
          <h1>{skill.name}</h1>
          <p>{skill.description}</p>
        </div>
        <div className="agent-skill-detail-header-actions">
          <button
            type="button"
            className="secondary"
            onClick={() => onNavigatePath("/agent/skills")}
          >
            <ChevronLeft size={16} />
            返回列表
          </button>
          {canEdit ? (
            <button
              type="button"
              onClick={() =>
                onNavigatePath(`/agent/skills/${encodeURIComponent(skill.id)}/edit`)
              }
            >
              <Pencil size={16} />
              编辑 Skill
            </button>
          ) : null}
          {!skill.is_read_only && skill.status === "archived" ? (
            <button
              type="button"
              disabled={restoring}
              onClick={async () => {
                if (!window.confirm(`恢复“${skill.name}”？恢复后可以继续编辑。`)) return;
                setRestoring(true);
                setError("");
                try {
                  setSkill(await api.restoreAgentSkill(skill.id));
                } catch (restoreError) {
                  setError(
                    restoreError instanceof Error ? restoreError.message : "恢复 Skill 失败",
                  );
                } finally {
                  setRestoring(false);
                }
              }}
            >
              {restoring ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
              恢复 Skill
            </button>
          ) : null}
          {skill.is_read_only ? (
            <button
              type="button"
              disabled={cloning}
              onClick={async () => {
                setCloning(true);
                setError("");
                try {
                  const cloned = await api.cloneAgentSkill(skill.id);
                  onNavigatePath(`/agent/skills/${encodeURIComponent(cloned.id)}`);
                } catch (cloneError) {
                  setError(cloneError instanceof Error ? cloneError.message : "复制失败");
                } finally {
                  setCloning(false);
                }
              }}
            >
              {cloning ? <Loader2 className="spin" size={16} /> : <Copy size={16} />}
              复制为我的 Skill
            </button>
          ) : null}
        </div>
      </header>
      {error ? (
        <div className="agent-skill-inline-error">
          <AlertCircle size={16} />
          {error}
        </div>
      ) : null}
      <div className="agent-skill-detail-layout">
        <article>
          <section>
            <h2>Skill 正文</h2>
            <p>Agent 在选中这个 Skill 后会读取以下完整指导。</p>
            <pre>{skill.instructions}</pre>
          </section>
        </article>
        <aside>
          <section>
            <h2>状态与权限</h2>
            <dl>
              <div>
                <dt>状态</dt>
                <dd>
                  <span className={`agent-skill-status is-${skill.status}`}>
                    {agentSkillStatusLabels[skill.status]}
                  </span>
                </dd>
              </div>
              <div>
                <dt>范围</dt>
                <dd>{skill.scope === "system" ? "系统 Skill · 只读" : "我的 Skill"}</dd>
              </div>
              <div>
                <dt>草稿 revision</dt>
                <dd>{skill.draft_revision}</dd>
              </div>
              <div>
                <dt>更新时间</dt>
                <dd>{skillTime(skill.updated_at)}</dd>
              </div>
            </dl>
          </section>
          <section>
            <h2>允许使用的 Tools</h2>
            {skill.tool_names.length ? (
              <ul className="agent-skill-detail-tools">
                {skill.tool_names.map((toolName) => (
                  <li key={toolName}>
                    <Box size={15} />
                    <span>
                      <strong>{toolLabels.get(toolName) || toolName}</strong>
                      <small>{toolName}</small>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p>此 Skill 不调用创作 Tool。</p>
            )}
          </section>
          <section className="agent-skill-version-summary">
            <h2>版本信息</h2>
            {skill.active_version ? (
              <button
                type="button"
                onClick={() =>
                  onNavigatePath(
                    `/agent/skills/${encodeURIComponent(skill.id)}/versions/${encodeURIComponent(skill.active_version!.id)}`,
                  )
                }
              >
                <History size={17} />
                当前启用 v{skill.active_version.version}
                <ChevronRight size={16} />
              </button>
            ) : (
              <p>尚未发布版本</p>
            )}
            {versions.length > 0 ? (
              <button
                type="button"
                onClick={() =>
                  onNavigatePath(
                    `/agent/skills/${encodeURIComponent(skill.id)}/versions/${encodeURIComponent(versions[0].id)}`,
                  )
                }
              >
                查看全部 {versions.length} 个版本
                <ChevronRight size={16} />
              </button>
            ) : null}
          </section>
          {skill.status === "archived" && !skill.is_read_only ? (
            <p className="agent-skill-detail-note">
              已归档 Skill 只能查看。恢复后才可继续编辑或发布。
            </p>
          ) : null}
        </aside>
      </div>
    </section>
  );
}

function AgentSkillEditorView({
  mode,
  skillId,
  onNavigatePath,
}: {
  mode: "new" | "edit";
  skillId?: string;
  onNavigatePath: (path: string) => void;
}) {
  const [skill, setSkill] = useState<AgentSkillDetail | null>(null);
  const [tools, setTools] = useState<AgentSkillTool[]>([]);
  const [versions, setVersions] = useState<AgentSkillVersionSummary[]>([]);
  const [form, setForm] = useState<AgentSkillFormState>({
    name: "",
    description: "",
    instructions: agentSkillTemplate,
    toolNames: [],
  });
  const [baseline, setBaseline] = useState<AgentSkillFormState | null>(
    mode === "new"
      ? { name: "", description: "", instructions: agentSkillTemplate, toolNames: [] }
      : null,
  );
  const [loading, setLoading] = useState(mode === "edit");
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [authoring, setAuthoring] = useState(false);
  const [error, setError] = useState("");
  const [savedMessage, setSavedMessage] = useState("");
  const [suggestion, setSuggestion] = useState<AgentSkillAuthoringSuggestion | null>(null);
  const [goal, setGoal] = useState("");
  const [confirmAction, setConfirmAction] = useState<"publish" | "archive" | "restore" | "delete" | null>(null);

  const dirty = baseline !== null && JSON.stringify(form) !== JSON.stringify(baseline);
  const readOnly = Boolean(skill?.is_read_only || skill?.status === "archived");

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);

  useEffect(() => {
    let cancelled = false;
    setLoading(mode === "edit");
    setError("");
    const requests: Promise<unknown>[] = [
      api.agentSkillTools().then((data) => {
        if (!cancelled) setTools(data);
      }),
    ];
    if (mode === "edit" && skillId) {
      requests.push(
        api.agentSkill(skillId).then((data) => {
          if (cancelled) return;
          const next = {
            name: data.name,
            description: data.description,
            instructions: data.instructions,
            toolNames: data.tool_names,
          };
          setSkill(data);
          setForm(next);
          setBaseline(next);
        }),
        api.agentSkillVersions(skillId).then((data) => {
          if (!cancelled) setVersions(data.items);
        }),
      );
    }
    Promise.all(requests)
      .catch((loadError) =>
        !cancelled &&
        setError(loadError instanceof Error ? loadError.message : "Skill 加载失败"),
      )
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [mode, skillId]);

  function updateField<Key extends keyof AgentSkillFormState>(
    key: Key,
    value: AgentSkillFormState[Key],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
    setSavedMessage("");
  }

  function navigateWithGuard(path: string) {
    if (dirty && !window.confirm("当前有未保存修改，确定离开吗？")) return;
    onNavigatePath(path);
  }

  async function saveDraft(navigateAfterCreate = true) {
    if (readOnly) return skill;
    setSaving(true);
    setError("");
    try {
      const updated =
        mode === "new"
          ? await api.createAgentSkill({
              name: form.name,
              description: form.description,
              instructions: form.instructions,
              tool_names: form.toolNames,
            })
          : await api.updateAgentSkill(skillId!, {
              name: form.name,
              description: form.description,
              instructions: form.instructions,
              tool_names: form.toolNames,
              expected_draft_revision: skill!.draft_revision,
            });
      const next = {
        name: updated.name,
        description: updated.description,
        instructions: updated.instructions,
        toolNames: updated.tool_names,
      };
      setSkill(updated);
      setForm(next);
      setBaseline(next);
      setSavedMessage("草稿已保存");
      if (navigateAfterCreate) {
        onNavigatePath(`/agent/skills/${encodeURIComponent(updated.id)}`);
      }
      return updated;
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存草稿失败");
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function publish() {
    setConfirmAction(null);
    setPublishing(true);
    setError("");
    try {
      const current = dirty || mode === "new" ? await saveDraft(false) : skill;
      if (!current) return;
      const version = await api.publishAgentSkill(current.id, {
        expected_draft_revision: current.draft_revision,
        idempotency_key: crypto.randomUUID(),
      });
      const refreshed = await api.agentSkill(current.id);
      const history = await api.agentSkillVersions(current.id);
      setSkill(refreshed);
      setVersions(history.items);
      setSavedMessage(`v${version.version} 已发布并设为当前版本`);
      onNavigatePath(`/agent/skills/${encodeURIComponent(current.id)}`);
    } catch (publishError) {
      setError(publishError instanceof Error ? publishError.message : "发布失败");
    } finally {
      setPublishing(false);
    }
  }

  async function requestSuggestion() {
    if (!goal.trim()) {
      setError("请先填写希望 AI 帮你整理的创作目标");
      return;
    }
    setAuthoring(true);
    setError("");
    try {
      const data = await api.authorAgentSkill({
        goal,
        current_instructions: form.instructions || null,
        selected_tool_names: form.toolNames,
      });
      setSuggestion(data);
    } catch (authorError) {
      setError(authorError instanceof Error ? authorError.message : "AI 建议生成失败");
    } finally {
      setAuthoring(false);
    }
  }

  async function handleDestructiveAction() {
    if (!skill || !confirmAction) return;
    setError("");
    try {
      if (confirmAction === "archive") {
        setSkill(await api.archiveAgentSkill(skill.id));
      } else if (confirmAction === "restore") {
        setSkill(await api.restoreAgentSkill(skill.id));
      } else if (confirmAction === "delete") {
        await api.deleteAgentSkill(skill.id);
        onNavigatePath("/agent/skills");
        return;
      }
      setConfirmAction(null);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "操作失败");
      setConfirmAction(null);
    }
  }

  if (loading) {
    return <div className="agent-skill-state page"><Loader2 className="spin" size={22} />正在加载编辑器…</div>;
  }
  if (error && mode === "edit" && !skill) {
    return (
      <div className="agent-skill-state page is-error">
        <AlertCircle size={22} />
        <strong>{error}</strong>
        <button type="button" onClick={() => window.location.reload()}>重试</button>
      </div>
    );
  }

  return (
    <section className="agent-skill-editor-page">
      <header>
        <div>
          <button
            type="button"
            onClick={() =>
              navigateWithGuard(
                skill ? `/agent/skills/${encodeURIComponent(skill.id)}` : "/agent/skills",
              )
            }
          >
            {skill ? "Skill 详情" : "Skill 管理"}
          </button>
          <span>/</span>
          <strong>{mode === "new" ? "创建 Skill" : `编辑 ${skill?.name || ""}`}</strong>
        </div>
        <div className="agent-skill-editor-title">
          <h1>{mode === "new" ? "创建 Skill" : `编辑 ${skill?.name || ""}`}</h1>
          <span className={dirty ? "unsaved" : "saved"}>
            {dirty
              ? "有未保存修改"
              : savedMessage || (mode === "new" ? "尚未保存" : "草稿已保存")}
          </span>
        </div>
      </header>
      {error ? <div className="agent-skill-inline-error"><AlertCircle size={16} />{error}</div> : null}
      <div className="agent-skill-editor-grid">
        <div className="agent-skill-form">
          <label>
            <span>Skill 名称</span>
            <input
              value={form.name}
              maxLength={120}
              disabled={readOnly}
              onChange={(event) => updateField("name", event.target.value)}
              placeholder="例如：四格反转漫画"
            />
          </label>
          <label>
            <span>什么时候使用</span>
            <textarea
              value={form.description}
              maxLength={500}
              disabled={readOnly}
              onChange={(event) => updateField("description", event.target.value)}
              placeholder="说明这个 Skill 适合解决什么创作任务"
              rows={3}
            />
          </label>
          <label className="agent-skill-instructions-field">
            <span>Skill 正文</span>
            <textarea
              value={form.instructions}
              maxLength={65536}
              disabled={readOnly}
              onChange={(event) => updateField("instructions", event.target.value)}
              rows={24}
            />
            <small>{new TextEncoder().encode(form.instructions).length.toLocaleString()} / 65,536 bytes</small>
          </label>
        </div>
        <aside className="agent-skill-editor-aside">
          <section>
            <h2>相关 Tools（可选）</h2>
            <p>发布后，Native Agent 只会向模型暴露此版本勾选的 Runtime Tools。</p>
            {tools.map((tool) => {
              const checked = form.toolNames.includes(tool.name);
              return (
                <label key={tool.name} className="agent-skill-tool-option">
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={readOnly}
                    onChange={() =>
                      updateField(
                        "toolNames",
                        checked
                          ? form.toolNames.filter((name) => name !== tool.name)
                          : [...form.toolNames, tool.name].sort(),
                      )
                    }
                  />
                  <span>
                    <strong>{tool.display_name}</strong>
                    <small>{tool.description}</small>
                  </span>
                </label>
              );
            })}
            {tools.length === 0 ? <p>没有可供用户 Skill 选择的 Tool。</p> : null}
          </section>
          <section>
            <h2>编写指南</h2>
            <ul>
              <li>先描述目标与输出预期。</li>
              <li>清晰定义输入信息与可选内容。</li>
              <li>把方法拆成可执行步骤，并在必要时指定 Tool。</li>
              <li>设定质量门槛与完成条件。</li>
            </ul>
          </section>
          {!readOnly ? (
            <section className="agent-skill-ai-box">
              <h2>AI 帮我生成 / 优化</h2>
              <textarea
                value={goal}
                onChange={(event) => setGoal(event.target.value)}
                rows={3}
                placeholder="描述你希望这个 Skill 完成什么"
              />
              <button type="button" disabled={authoring} onClick={() => void requestSuggestion()}>
                {authoring ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
                {authoring ? "正在生成建议" : "生成建议预览"}
              </button>
            </section>
          ) : null}
          <section className="agent-skill-version-summary">
            <h2>版本信息</h2>
            {skill?.active_version ? (
              <button
                type="button"
                onClick={() =>
                  onNavigatePath(
                    `/agent/skills/${encodeURIComponent(skill.id)}/versions/${encodeURIComponent(skill.active_version!.id)}`,
                  )
                }
              >
                <History size={17} />
                当前启用 v{skill.active_version.version}
                <ChevronRight size={16} />
              </button>
            ) : (
              <p>尚未发布版本</p>
            )}
            {skill && versions.length > 0 ? (
              <button
                type="button"
                onClick={() =>
                  onNavigatePath(
                    `/agent/skills/${encodeURIComponent(skill.id)}/versions/${encodeURIComponent(versions[0].id)}`,
                  )
                }
              >
                查看全部 {versions.length} 个版本
              </button>
            ) : null}
          </section>
          {skill?.is_read_only ? (
            <button
              type="button"
              className="agent-skill-clone-button"
              onClick={async () => {
                setError("");
                try {
                  const cloned = await api.cloneAgentSkill(skill.id);
                  onNavigatePath(`/agent/skills/${encodeURIComponent(cloned.id)}`);
                } catch (cloneError) {
                  setError(cloneError instanceof Error ? cloneError.message : "复制失败");
                }
              }}
            >
              <Copy size={16} />
              复制为我的 Skill
            </button>
          ) : null}
        </aside>
      </div>
      <footer className="agent-skill-editor-actions">
        <div>
          {skill && !skill.is_read_only ? (
            skill.status === "archived" ? (
              <button type="button" onClick={() => setConfirmAction("restore")}>
                恢复 Skill
              </button>
            ) : (
              <>
                <button type="button" onClick={() => setConfirmAction("archive")}>
                  <Archive size={16} />
                  归档
                </button>
                {!skill.active_version ? (
                  <button type="button" onClick={() => setConfirmAction("delete")}>
                    <Trash2 size={16} />
                    删除草稿
                  </button>
                ) : null}
              </>
            )
          ) : null}
        </div>
        <div>
          {!readOnly ? (
            <>
              <button
                type="button"
                className="secondary"
                disabled={saving || publishing || !dirty}
                onClick={() => void saveDraft()}
              >
                {saving ? <Loader2 className="spin" size={16} /> : <Save size={16} />}
                {mode === "new" ? "保存草稿" : "保存修改"}
              </button>
              <button
                type="button"
                disabled={saving || publishing}
                onClick={() => setConfirmAction("publish")}
              >
                {publishing ? <Loader2 className="spin" size={16} /> : <ArrowUpRight size={16} />}
                发布 v{(skill?.active_version?.version || 0) + 1}
              </button>
            </>
          ) : null}
        </div>
      </footer>
      {suggestion ? (
        <div className="agent-skill-dialog-backdrop" role="presentation">
          <section role="dialog" aria-modal="true" aria-labelledby="skill-suggestion-title" className="agent-skill-suggestion-dialog">
            <header>
              <div>
                <h2 id="skill-suggestion-title">AI 建议预览</h2>
                <p>只有点击“应用建议”才会修改当前表单，且不会自动保存或发布。</p>
              </div>
              <button type="button" aria-label="关闭建议" onClick={() => setSuggestion(null)}><X size={18} /></button>
            </header>
            <dl>
              <div><dt>名称</dt><dd>{suggestion.suggested_name}</dd></div>
              <div><dt>适用场景</dt><dd>{suggestion.suggested_description}</dd></div>
              <div><dt>Tools</dt><dd>{suggestion.suggested_tool_names.join("、") || "无"}</dd></div>
            </dl>
            <pre>{suggestion.suggested_instructions}</pre>
            {suggestion.notes.length ? <ul>{suggestion.notes.map((note) => <li key={note}>{note}</li>)}</ul> : null}
            <footer>
              <button type="button" className="secondary" onClick={() => setSuggestion(null)}>取消</button>
              <button
                type="button"
                onClick={() => {
                  setForm({
                    name: suggestion.suggested_name,
                    description: suggestion.suggested_description,
                    instructions: suggestion.suggested_instructions,
                    toolNames: suggestion.suggested_tool_names,
                  });
                  setSuggestion(null);
                }}
              >
                应用建议
              </button>
            </footer>
          </section>
        </div>
      ) : null}
      {confirmAction ? (
        <div className="agent-skill-dialog-backdrop" role="presentation">
          <section role="alertdialog" aria-modal="true" aria-labelledby="skill-confirm-title" className="agent-skill-confirm-dialog">
            <AlertCircle size={24} />
            <h2 id="skill-confirm-title">
              {confirmAction === "publish"
                ? `发布 v${(skill?.active_version?.version || 0) + 1}？`
                : confirmAction === "archive"
                  ? "归档这个 Skill？"
                  : confirmAction === "restore"
                    ? "恢复这个 Skill？"
                    : "永久删除未发布草稿？"}
            </h2>
            <p>
              {confirmAction === "publish"
                ? `将创建不可修改的新版本；允许的 Tools：${form.toolNames.join("、") || "无"}。`
                : confirmAction === "archive"
                  ? "归档后不会出现在新的 @Skill 菜单，已经开始的任务不受影响。"
                  : confirmAction === "restore"
                    ? "恢复后，有启用版本的 Skill 会重新用于新对话。"
                    : "这个操作只适用于从未发布且未被引用的草稿。"}
            </p>
            <footer>
              <button type="button" className="secondary" onClick={() => setConfirmAction(null)}>取消</button>
              <button
                type="button"
                onClick={() =>
                  confirmAction === "publish"
                    ? void publish()
                    : void handleDestructiveAction()
                }
              >
                确认
              </button>
            </footer>
          </section>
        </div>
      ) : null}
    </section>
  );
}

function AgentSkillVersionView({
  skillId,
  versionId,
  onNavigatePath,
}: {
  skillId: string;
  versionId: string;
  onNavigatePath: (path: string) => void;
}) {
  const [skill, setSkill] = useState<AgentSkillDetail | null>(null);
  const [versions, setVersions] = useState<AgentSkillVersionSummary[]>([]);
  const [version, setVersion] = useState<AgentSkillVersionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activating, setActivating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    Promise.all([
      api.agentSkill(skillId),
      api.agentSkillVersions(skillId),
      api.agentSkillVersion(skillId, versionId),
    ])
      .then(([nextSkill, history, selected]) => {
        if (cancelled) return;
        setSkill(nextSkill);
        setVersions(history.items);
        setVersion(selected);
      })
      .catch((loadError) =>
        !cancelled &&
        setError(loadError instanceof Error ? loadError.message : "版本加载失败"),
      )
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [skillId, versionId]);

  if (loading) {
    return <div className="agent-skill-state page"><Loader2 className="spin" size={22} />正在加载版本…</div>;
  }
  if (error || !skill || !version) {
    return <div className="agent-skill-state page is-error"><AlertCircle size={22} />{error || "版本不存在"}</div>;
  }

  async function activateVersion() {
    if (skill!.is_read_only || version!.is_active) return;
    if (
      !window.confirm(
        `切换到 v${version!.version}？\n新对话将使用所选版本；正在运行和等待确认的任务仍继续使用原版本。`,
      )
    ) return;
    setActivating(true);
    setError("");
    try {
      const updated = await api.activateAgentSkillVersion(skill!.id, version!.id);
      setSkill(updated);
      setVersion((current) => (current ? { ...current, is_active: true } : current));
      setVersions((current) =>
        current.map((item) => ({ ...item, is_active: item.id === version!.id })),
      );
    } catch (activateError) {
      setError(activateError instanceof Error ? activateError.message : "切换版本失败");
    } finally {
      setActivating(false);
    }
  }

  return (
    <section className="agent-skill-version-page">
      <header className="agent-skill-page-header">
        <div>
          <span>Skill 管理 / {skill.name}</span>
          <h1>版本历史</h1>
          <p>已发布版本不可修改，运行中的任务始终使用创建时版本</p>
        </div>
        <button type="button" className="secondary" onClick={() => onNavigatePath(`/agent/skills/${encodeURIComponent(skill.id)}`)}>
          <ChevronLeft size={16} />
          返回详情
        </button>
      </header>
      {error ? <div className="agent-skill-inline-error">{error}</div> : null}
      <div className="agent-skill-version-layout">
        <aside>
          <h2>版本</h2>
          <div className="agent-skill-version-draft">
            <i />
            <span><strong>当前草稿</strong><small>revision {skill.draft_revision}</small></span>
            <em>草稿</em>
          </div>
          {versions.map((item) => (
            <button
              type="button"
              key={item.id}
              className={item.id === version.id ? "active" : ""}
              onClick={() =>
                onNavigatePath(
                  `/agent/skills/${encodeURIComponent(skill.id)}/versions/${encodeURIComponent(item.id)}`,
                )
              }
            >
              <i />
              <span>
                <strong>v{item.version}{item.is_active ? " · 当前启用" : ""}</strong>
                <small>{skillTime(item.published_at)}</small>
                <small>{item.tool_names.join("、") || "无 Tool"}</small>
              </span>
              <em>{item.is_active ? "当前" : "已发布"}</em>
            </button>
          ))}
        </aside>
        <article>
          <header>
            <div>
              <h2>v{version.version}</h2>
              <span>{version.is_active ? "当前启用" : "已发布"}</span>
              <p>
                发布于 {skillTime(version.published_at)} · {version.tool_names.join("、") || "无 Tool"} · {version.content_hash.slice(0, 18)}…
              </p>
            </div>
            <div>
              {!skill.is_read_only ? (
                <button
                  type="button"
                  className="secondary"
                  onClick={async () => {
                    try {
                      const cloned = await api.cloneAgentSkill(skill.id, version.id);
                      onNavigatePath(`/agent/skills/${encodeURIComponent(cloned.id)}`);
                    } catch (cloneError) {
                      setError(cloneError instanceof Error ? cloneError.message : "复制失败");
                    }
                  }}
                >
                  <Copy size={16} />
                  复制到新草稿
                </button>
              ) : null}
              {!skill.is_read_only ? (
                <button type="button" disabled={version.is_active || activating} onClick={() => void activateVersion()}>
                  {activating ? <Loader2 className="spin" size={16} /> : null}
                  {version.is_active ? "当前启用" : "设为当前版本"}
                </button>
              ) : null}
            </div>
          </header>
          <section>
            <h3>名称与适用场景</h3>
            <strong>{version.name}</strong>
            <p>{version.description}</p>
          </section>
          <section>
            <h3>Skill 正文（只读）</h3>
            <pre>{version.instructions}</pre>
          </section>
        </article>
      </div>
    </section>
  );
}

function AgentSkillManagementView({
  user,
  creditOverview,
  creditError,
  route,
  onNavigatePath,
  onLogout,
}: {
  user: User;
  creditOverview: CreditOverview | null;
  creditError: string;
  route:
    | { mode: "list" }
    | { mode: "new" }
    | { mode: "detail"; skillId: string }
    | { mode: "edit"; skillId: string }
    | { mode: "version"; skillId: string; versionId: string };
  onNavigatePath: (path: string, options?: { replace?: boolean }) => void;
  onLogout: () => Promise<void>;
}) {
  return (
    <section className="agent-skill-workspace">
      <AgentStudioSidebar
        user={user}
        creditOverview={creditOverview}
        creditError={creditError}
        activeSkills
        onNavigatePath={onNavigatePath}
        onLogout={onLogout}
      />
      <main>
        {route.mode === "list" ? <AgentSkillListView onNavigatePath={onNavigatePath} /> : null}
        {route.mode === "new" ? <AgentSkillEditorView mode="new" onNavigatePath={onNavigatePath} /> : null}
        {route.mode === "detail" ? (
          <AgentSkillDetailView skillId={route.skillId} onNavigatePath={onNavigatePath} />
        ) : null}
        {route.mode === "edit" ? (
          <AgentSkillEditorView mode="edit" skillId={route.skillId} onNavigatePath={onNavigatePath} />
        ) : null}
        {route.mode === "version" ? (
          <AgentSkillVersionView
            skillId={route.skillId}
            versionId={route.versionId}
            onNavigatePath={onNavigatePath}
          />
        ) : null}
      </main>
    </section>
  );
}

function youtubeMetric(value: number | null, suffix = "") {
  if (value === null) return "—";
  return `${new Intl.NumberFormat("zh-CN", { notation: value >= 10000 ? "compact" : "standard", maximumFractionDigits: 1 }).format(value)}${suffix}`;
}

function youtubePublishStatus(status: string) {
  const labels: Record<string, string> = {
    submitting: "正在提交",
    pending: "等待发布",
    running: "正在上传",
    succeeded: "发布成功",
    failed: "发布失败",
    cancelled: "用户取消",
    outcome_unknown: "结果不明确",
  };
  return labels[status] || status;
}

const YOUTUBE_LIST_PAGE_SIZE = 10;

function YoutubePagination({
  page,
  total,
  loading,
  onPageChange,
}: {
  page: number;
  total: number;
  loading: boolean;
  onPageChange: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / YOUTUBE_LIST_PAGE_SIZE));
  if (total === 0) return null;
  return (
    <nav className="youtube-pagination" aria-label="列表分页">
      <span>共 {total} 条</span>
      <div>
        <button
          className="secondary-button"
          type="button"
          disabled={loading || page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          上一页
        </button>
        <strong>第 {page} / {totalPages} 页</strong>
        <button
          className="secondary-button"
          type="button"
          disabled={loading || page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          下一页
        </button>
      </div>
    </nav>
  );
}

function YoutubeChannelListView({
  onNavigatePath,
}: {
  onNavigatePath: (path: string) => void;
}) {
  const [channels, setChannels] = useState<YoutubeChannelSummary[]>([]);
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");
  const [total, setTotal] = useState(0);

  async function loadChannels(targetPage = page) {
    setLoading(true);
    try {
      const result = await api.youtubeChannels({
        q: appliedQuery || undefined,
        remote_status: statusFilter || undefined,
        cursor: targetPage > 1
          ? String((targetPage - 1) * YOUTUBE_LIST_PAGE_SIZE)
          : undefined,
        limit: YOUTUBE_LIST_PAGE_SIZE,
      });
      setChannels(result.items);
      setTotal(result.page.total ?? result.items.length);
      setError("");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "频道加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadChannels();
  }, [appliedQuery, page, statusFilter]);

  async function syncChannels() {
    setSyncing(true);
    try {
      await api.syncYoutubeChannels();
      await loadChannels();
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : "频道同步失败");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <section className="youtube-channel-page">
      <header className="youtube-page-header">
        <div>
          <h1>频道账号</h1>
          <p>管理 YouTube 频道、账号定位与发布数据</p>
        </div>
        <button className="primary-button" type="button" disabled={syncing} onClick={() => void syncChannels()}>
          <RefreshCw className={syncing ? "spin" : ""} size={16} />
          {syncing ? "正在同步" : "同步频道"}
        </button>
      </header>
      <div className="youtube-channel-toolbar">
        <div className="youtube-segments">
          <button className={!statusFilter ? "active" : ""} type="button" onClick={() => { setPage(1); setStatusFilter(""); }}>
            全部频道
          </button>
          <button className={statusFilter === "normal" ? "active" : ""} type="button" onClick={() => { setPage(1); setStatusFilter("normal"); }}>
            正常频道
          </button>
        </div>
        <form
          className="youtube-search"
          onSubmit={(event) => {
            event.preventDefault();
            setPage(1);
            setAppliedQuery(query.trim());
          }}
        >
          <Search size={16} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索别名、频道名或 Handle" />
        </form>
        <select value={statusFilter} onChange={(event) => { setPage(1); setStatusFilter(event.target.value); }} aria-label="频道状态">
          <option value="">全部状态</option>
          <option value="normal">正常</option>
          <option value="manual">手动</option>
          <option value="banned">封禁</option>
          <option value="unknown">未知</option>
        </select>
      </div>
      {error ? <div className="youtube-inline-error"><AlertCircle size={16} />{error}</div> : null}
      {loading ? <div className="youtube-empty"><Loader2 className="spin" />正在加载频道…</div> : null}
      {!loading && channels.length === 0 ? (
        <div className="youtube-empty">
          <BarChart3 size={24} />
          <strong>{appliedQuery || statusFilter ? "没有符合条件的频道" : "还没有频道"}</strong>
          <span>{appliedQuery || statusFilter ? "调整搜索词或状态筛选后再试。" : "点击“同步频道”从发布系统读取账号。"}</span>
        </div>
      ) : null}
      {!loading && channels.length > 0 ? (
        <div className="youtube-channel-table">
          <div className="youtube-channel-row youtube-channel-head">
            <span>频道 / 别名</span><span>状态</span><span>账号定位</span><span>频道数据</span><span>最近同步</span><span>操作</span>
          </div>
          {channels.map((channel) => (
            <div className="youtube-channel-row" key={channel.id}>
              <div className="youtube-channel-identity">
                <span className="youtube-channel-avatar">
                  {channel.avatar_url ? <img src={channel.avatar_url} alt="" /> : (channel.alias || channel.title).slice(0, 1)}
                </span>
                <span>
                  <strong>{channel.alias || channel.title}</strong>
                  {channel.alias ? <small>{channel.title}</small> : null}
                  <small>{channel.handle ? `@${channel.handle.replace(/^@/, "")}` : channel.channel_id}</small>
                </span>
              </div>
              <span><i className={`youtube-status is-${channel.remote_status}`}>{channel.remote_status === "normal" ? "正常" : channel.remote_status === "manual" ? "手动" : "需检查"}</i></span>
              <span className="youtube-positioning">{channel.account_positioning || "尚未定义账号定位"}</span>
              <span className="youtube-data">{youtubeMetric(channel.total_subscribers)} 订阅 · {youtubeMetric(channel.total_views)} 观看 · {youtubeMetric(channel.total_videos)} 视频</span>
              <span className="youtube-sync-time">
                {channel.last_sync_success_at ? formatDateTime(channel.last_sync_success_at) : "尚未同步分析"}
                {channel.last_sync_error ? <small><AlertCircle size={12} />{channel.last_sync_error}</small> : null}
              </span>
              <button className="youtube-text-action" type="button" onClick={() => onNavigatePath(`/agent/channels/${encodeURIComponent(channel.id)}`)}>查看</button>
            </div>
          ))}
        </div>
      ) : null}
      <YoutubePagination
        page={page}
        total={total}
        loading={loading}
        onPageChange={setPage}
      />
    </section>
  );
}

type YoutubeDetailTab = "overview" | "profile" | "tasks" | "videos" | "benchmarks";

function YoutubeChannelDetailView({
  channelId,
  onNavigatePath,
}: {
  channelId: string;
  onNavigatePath: (path: string) => void;
}) {
  const [channel, setChannel] = useState<YoutubeChannelDetail | null>(null);
  const [tab, setTab] = useState<YoutubeDetailTab>("overview");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [profile, setProfile] = useState({ alias: "", account_positioning: "", target_audience: "", stage_goal: "", ai_definition: "", operation_notes: "" });
  const [benchmark, setBenchmark] = useState({ name: "", profile_url: "", notes: "" });
  const [publishableVideos, setPublishableVideos] = useState<PublishableVideo[]>([]);
  const [uploadedVideos, setUploadedVideos] = useState<YoutubeUploadedVideo[]>([]);
  const [videoPage, setVideoPage] = useState(1);
  const [videoTotal, setVideoTotal] = useState(0);
  const [videoLoading, setVideoLoading] = useState(false);
  const [showPublishDialog, setShowPublishDialog] = useState(false);
  const [publishForm, setPublishForm] = useState({
    publishable_video_id: "",
    visibility: "public" as "public" | "private" | "unlisted",
    planned_publish_at: "",
    notify_subscribers: true,
  });

  async function loadChannel() {
    try {
      const result = await api.youtubeChannel(channelId);
      setChannel(result);
      setProfile({
        alias: result.alias || "",
        account_positioning: result.account_positioning || "",
        target_audience: result.target_audience || "",
        stage_goal: result.stage_goal || "",
        ai_definition: result.ai_definition || "",
        operation_notes: result.operation_notes || "",
      });
      setError("");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "频道加载失败");
    }
  }

  async function loadUploadedVideos(targetPage = videoPage) {
    setVideoLoading(true);
    try {
      const result = await api.youtubeChannelVideos(channelId, {
        cursor: targetPage > 1
          ? String((targetPage - 1) * YOUTUBE_LIST_PAGE_SIZE)
          : undefined,
        limit: YOUTUBE_LIST_PAGE_SIZE,
      });
      setUploadedVideos(result.items);
      setVideoTotal(result.page.total ?? result.items.length);
      setError("");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "已发布视频加载失败");
    } finally {
      setVideoLoading(false);
    }
  }

  useEffect(() => {
    void loadChannel();
    void api.youtubePublishableVideos("approved")
      .then((result) => setPublishableVideos(result.items))
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : "可发布视频加载失败");
      });
  }, [channelId]);

  useEffect(() => {
    if (tab === "videos") {
      void loadUploadedVideos();
    }
  }, [channelId, tab, videoPage]);

  async function runAction(name: string, action: () => Promise<YoutubeChannelDetail>) {
    setBusy(name);
    try {
      setChannel(await action());
      setError("");
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "操作失败");
    } finally {
      setBusy("");
    }
  }

  async function syncUploadedVideos() {
    setBusy("videos");
    try {
      setChannel(await api.syncYoutubeChannelVideos(channelId));
      if (videoPage === 1) {
        await loadUploadedVideos(1);
      } else {
        setVideoPage(1);
      }
      setError("");
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "视频同步失败");
    } finally {
      setBusy("");
    }
  }

  if (!channel) {
    return <div className="youtube-empty">{error || "正在加载频道…"}</div>;
  }

  return (
    <section className="youtube-channel-page youtube-channel-detail">
      <button className="youtube-breadcrumb" type="button" onClick={() => onNavigatePath("/agent/channels")}>频道账号</button>
      <header className="youtube-detail-header">
        <span className="youtube-detail-avatar">{channel.avatar_url ? <img src={channel.avatar_url} alt="" /> : (channel.alias || channel.title).slice(0, 1)}</span>
        <div>
          <div className="youtube-detail-title"><h1>{channel.alias || channel.title}</h1><i className={`youtube-status is-${channel.remote_status}`}>{channel.remote_status === "normal" ? "正常" : channel.remote_status}</i></div>
          <p>{channel.title}{channel.handle ? ` · @${channel.handle.replace(/^@/, "")}` : ""}</p>
        </div>
        <div className="youtube-detail-actions">
          <button className="secondary-button" type="button" onClick={() => setTab("profile")}>编辑账号定义</button>
          <button className="primary-button" type="button" disabled={Boolean(busy)} onClick={() => void runAction("analytics", () => api.syncYoutubeChannelAnalytics(channel.id))}>
            <RefreshCw className={busy === "analytics" ? "spin" : ""} size={16} />同步频道
          </button>
          <small>最近同步：{channel.last_sync_success_at ? formatDateTime(channel.last_sync_success_at) : "暂无"}</small>
        </div>
      </header>
      <div className="youtube-metric-strip">
        <span><small>订阅者</small><strong>{youtubeMetric(channel.total_subscribers)}</strong></span>
        <span><small>总观看量</small><strong>{youtubeMetric(channel.total_views)}</strong></span>
        <span><small>观看时长</small><strong>{youtubeMetric(channel.total_watch_time_hours, " 小时")}</strong></span>
        <span><small>已发布视频</small><strong>{youtubeMetric(channel.total_videos)}</strong></span>
      </div>
      <nav className="youtube-detail-tabs">
        {([["overview", "概览"], ["profile", "账号定义"], ["tasks", "发布任务"], ["videos", "已发布视频"], ["benchmarks", "对标账号"]] as const).map(([value, label]) => (
          <button className={tab === value ? "active" : ""} type="button" key={value} onClick={() => setTab(value)}>{label}</button>
        ))}
      </nav>
      {error ? <div className="youtube-inline-error"><AlertCircle size={16} />{error}</div> : null}
      {tab === "overview" ? (
        <div className="youtube-overview-grid">
          <section><span>账号定位</span><p>{channel.account_positioning || "尚未填写"}</p></section>
          <section><span>目标受众</span><p>{channel.target_audience || "尚未填写"}</p></section>
          <section><span>阶段目标</span><p>{channel.stage_goal || "尚未填写"}</p></section>
          <section><span>AI 账号定义</span><p>{channel.ai_definition || "尚未填写"}</p></section>
        </div>
      ) : null}
      {tab === "profile" ? (
        <form className="youtube-profile-form" onSubmit={(event) => {
          event.preventDefault();
          void runAction("profile", () => api.updateYoutubeChannelProfile(channel.id, Object.fromEntries(Object.entries(profile).map(([key, value]) => [key, value.trim() || null])) as Parameters<typeof api.updateYoutubeChannelProfile>[1]));
        }}>
          <label>频道别名<input value={profile.alias} onChange={(event) => setProfile({ ...profile, alias: event.target.value })} placeholder="例如：英文动画主号" /></label>
          <label>账号定位<textarea value={profile.account_positioning} onChange={(event) => setProfile({ ...profile, account_positioning: event.target.value })} /></label>
          <label>目标受众<textarea value={profile.target_audience} onChange={(event) => setProfile({ ...profile, target_audience: event.target.value })} /></label>
          <label>阶段目标<textarea value={profile.stage_goal} onChange={(event) => setProfile({ ...profile, stage_goal: event.target.value })} /></label>
          <label className="wide">AI 账号定义<textarea value={profile.ai_definition} onChange={(event) => setProfile({ ...profile, ai_definition: event.target.value })} /></label>
          <label className="wide">运营备注<textarea value={profile.operation_notes} onChange={(event) => setProfile({ ...profile, operation_notes: event.target.value })} /></label>
          <div className="youtube-form-actions"><button className="primary-button" disabled={busy === "profile"}>保存账号定义</button></div>
        </form>
      ) : null}
      {tab === "tasks" ? (
        <section className="youtube-publish-section">
          <header>
            <div>
              <h2>发布任务</h2>
              <p>提交后不会自动轮询；需要时手动获取单条任务状态。</p>
            </div>
            <button
              className="primary-button"
              type="button"
              disabled={channel.remote_status !== "normal" || publishableVideos.length === 0}
              onClick={() => {
                setPublishForm((current) => ({
                  ...current,
                  publishable_video_id: current.publishable_video_id || publishableVideos[0]?.id || "",
                }));
                setShowPublishDialog(true);
              }}
            >
              <Upload size={15} />创建发布任务
            </button>
          </header>
          {publishableVideos.length === 0 ? (
            <div className="youtube-empty">
              <Film size={24} />
              <strong>没有审核通过的可发布视频</strong>
              <span>先把 Native Agent 生成视频登记并审核通过，再创建发布任务。</span>
            </div>
          ) : null}
          {channel.publish_tasks.length > 0 ? (
            <div className="youtube-publish-table">
              <div className="youtube-publish-row youtube-video-head">
                <span>视频 / 追踪 ID</span><span>状态</span><span>可见性</span><span>计划时间</span><span>操作</span>
              </div>
              {channel.publish_tasks.map((task) => (
                <div className="youtube-publish-row" key={task.id}>
                  <span>
                    <strong>{task.title}</strong>
                    <small>Agent {task.source_native_agent_video_id}</small>
                    <small>Task {task.id}{task.youtube_video_id ? ` · YouTube ${task.youtube_video_id}` : ""}</small>
                  </span>
                  <span>
                    <i className={`youtube-task-status is-${task.status}`}>{youtubePublishStatus(task.status)}</i>
                    {task.error_message ? <small className="youtube-task-error">{task.error_message}</small> : null}
                  </span>
                  <span>{task.visibility}</span>
                  <span>{formatDateTime(task.planned_publish_at)}</span>
                  <span className="youtube-task-actions">
                    {task.youtube_url ? <a href={task.youtube_url} target="_blank" rel="noreferrer">查看视频</a> : null}
                    <button
                      className="youtube-text-action"
                      type="button"
                      disabled={busy === `task-${task.id}` || !task.remote_task_id}
                      onClick={async () => {
                        setBusy(`task-${task.id}`);
                        try {
                          await api.refreshYoutubePublishTask(channel.id, task.id);
                          await loadChannel();
                        } catch (refreshError) {
                          setError(refreshError instanceof Error ? refreshError.message : "任务状态获取失败");
                        } finally {
                          setBusy("");
                        }
                      }}
                    >
                      <RefreshCw className={busy === `task-${task.id}` ? "spin" : ""} size={14} />
                      获取状态
                    </button>
                  </span>
                </div>
              ))}
            </div>
          ) : publishableVideos.length > 0 ? (
            <div className="youtube-empty"><Clock3 size={24} /><strong>还没有发布任务</strong><span>选择一个审核通过的视频开始发布。</span></div>
          ) : null}
        </section>
      ) : null}
      {tab === "videos" ? (
        <section className="youtube-videos-section">
          <header><div><h2>已发布视频</h2><p>仅同步当前频道的数据，每页显示 {YOUTUBE_LIST_PAGE_SIZE} 条。</p></div><button className="secondary-button" disabled={Boolean(busy)} type="button" onClick={() => void syncUploadedVideos()}><RefreshCw className={busy === "videos" ? "spin" : ""} size={15} />同步视频</button></header>
          {videoLoading ? <div className="youtube-empty"><Loader2 className="spin" />正在加载视频…</div> : null}
          {!videoLoading && uploadedVideos.length > 0 ? (
            <div className="youtube-video-table">
              <div className="youtube-video-row youtube-video-head"><span>视频</span><span>可见性</span><span>观看</span><span>点赞</span><span>发布时间</span></div>
              {uploadedVideos.map((video) => <div className="youtube-video-row" key={video.id}><span><strong>{video.title || "未命名视频"}</strong><small>{video.youtube_video_id}</small></span><span>{video.visibility || "—"}</span><span>{youtubeMetric(video.views)}</span><span>{youtubeMetric(video.likes)}</span><span>{formatDateTime(video.uploaded_at)}</span></div>)}
            </div>
          ) : null}
          {!videoLoading && uploadedVideos.length === 0 ? <div className="youtube-empty">尚未同步已发布视频</div> : null}
          <YoutubePagination
            page={videoPage}
            total={videoTotal}
            loading={videoLoading}
            onPageChange={setVideoPage}
          />
        </section>
      ) : null}
      {tab === "benchmarks" ? (
        <section className="youtube-benchmarks">
          <form onSubmit={async (event) => {
            event.preventDefault();
            setBusy("benchmark");
            try {
              await api.addYoutubeBenchmark(channel.id, { platform: "youtube", name: benchmark.name, profile_url: benchmark.profile_url, notes: benchmark.notes || null, platform_account_id: null });
              setBenchmark({ name: "", profile_url: "", notes: "" });
              await loadChannel();
            } catch (benchmarkError) {
              setError(benchmarkError instanceof Error ? benchmarkError.message : "对标账号添加失败");
            } finally {
              setBusy("");
            }
          }}>
            <input required value={benchmark.name} onChange={(event) => setBenchmark({ ...benchmark, name: event.target.value })} placeholder="对标账号名称" />
            <input required type="url" value={benchmark.profile_url} onChange={(event) => setBenchmark({ ...benchmark, profile_url: event.target.value })} placeholder="YouTube 主页 URL" />
            <input value={benchmark.notes} onChange={(event) => setBenchmark({ ...benchmark, notes: event.target.value })} placeholder="备注（可选）" />
            <button className="primary-button" disabled={busy === "benchmark"}>添加对标账号</button>
          </form>
          {channel.benchmarks.map((item) => <article key={item.id}><div><strong>{item.name}</strong><a href={item.profile_url} target="_blank" rel="noreferrer">{item.profile_url}</a><small>{item.notes}</small></div><button type="button" aria-label={`删除 ${item.name}`} onClick={async () => { await api.deleteYoutubeBenchmark(channel.id, item.id); await loadChannel(); }}><Trash2 size={15} /></button></article>)}
        </section>
      ) : null}
      {showPublishDialog ? (
        <div className="youtube-publish-overlay" role="presentation" onMouseDown={() => setShowPublishDialog(false)}>
          <form
            className="youtube-publish-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="youtube-publish-title"
            onMouseDown={(event) => event.stopPropagation()}
            onSubmit={async (event) => {
              event.preventDefault();
              const selected = publishableVideos.find((item) => item.id === publishForm.publishable_video_id);
              if (!selected) return;
              setBusy("publish");
              try {
                await api.createYoutubePublishTask(channel.id, {
                  publishable_video_id: selected.id,
                  visibility: publishForm.visibility,
                  planned_publish_at: publishForm.planned_publish_at
                    ? new Date(publishForm.planned_publish_at).toISOString()
                    : null,
                  notify_subscribers: publishForm.notify_subscribers,
                  confirmed: true,
                  idempotency_key: crypto.randomUUID(),
                });
                setShowPublishDialog(false);
                setTab("tasks");
                await loadChannel();
              } catch (publishError) {
                setError(publishError instanceof Error ? publishError.message : "发布任务创建失败");
              } finally {
                setBusy("");
              }
            }}
          >
            <header>
              <span><Upload size={18} /></span>
              <div>
                <h2 id="youtube-publish-title">确认发布到 {channel.alias || channel.title}</h2>
                <p>确认后会创建真实 YouTube 异步上传任务，不能通过重复提交来恢复。</p>
              </div>
            </header>
            <label>
              审核通过的视频
              <select required value={publishForm.publishable_video_id} onChange={(event) => setPublishForm({ ...publishForm, publishable_video_id: event.target.value })}>
                {publishableVideos.map((video) => <option value={video.id} key={video.id}>{video.title} · Agent {video.source_native_agent_video_id}</option>)}
              </select>
            </label>
            <div className="youtube-publish-fields">
              <label>
                可见性
                <select value={publishForm.visibility} onChange={(event) => setPublishForm({ ...publishForm, visibility: event.target.value as typeof publishForm.visibility })}>
                  <option value="public">公开</option>
                  <option value="unlisted">不公开列出</option>
                  <option value="private">私密</option>
                </select>
              </label>
              <label>
                计划时间（上海时区）
                <input type="datetime-local" value={publishForm.planned_publish_at} onChange={(event) => setPublishForm({ ...publishForm, planned_publish_at: event.target.value })} />
              </label>
            </div>
            <label className="youtube-publish-check">
              <input type="checkbox" checked={publishForm.notify_subscribers} onChange={(event) => setPublishForm({ ...publishForm, notify_subscribers: event.target.checked })} />
              发布时通知频道订阅者
            </label>
            <footer>
              <button className="secondary-button" type="button" disabled={busy === "publish"} onClick={() => setShowPublishDialog(false)}>暂不发布</button>
              <button className="primary-button" disabled={busy === "publish"}>
                {busy === "publish" ? <Loader2 className="spin" size={15} /> : <Upload size={15} />}
                确认并创建发布任务
              </button>
            </footer>
          </form>
        </div>
      ) : null}
    </section>
  );
}

function YoutubeChannelManagementView({
  user,
  creditOverview,
  creditError,
  route,
  onNavigatePath,
  onLogout,
}: {
  user: User;
  creditOverview: CreditOverview | null;
  creditError: string;
  route: { mode: "list" } | { mode: "detail"; channelId: string };
  onNavigatePath: (path: string, options?: { replace?: boolean }) => void;
  onLogout: () => Promise<void>;
}) {
  return (
    <section className="agent-skill-workspace">
      <AgentStudioSidebar user={user} creditOverview={creditOverview} creditError={creditError} activeSkills={false} activeChannels onNavigatePath={onNavigatePath} onLogout={onLogout} />
      <main>{route.mode === "list" ? <YoutubeChannelListView onNavigatePath={onNavigatePath} /> : <YoutubeChannelDetailView channelId={route.channelId} onNavigatePath={onNavigatePath} />}</main>
    </section>
  );
}

function NativeAgentSidebar({
  user,
  conversations,
  creditOverview,
  creditError,
  onNavigatePath,
  onLogout,
}: {
  user: User;
  conversations: NativeAgentConversation[];
  creditOverview: CreditOverview | null;
  creditError: string;
  onNavigatePath: (path: string) => void;
  onLogout: () => Promise<void>;
}) {
  return (
    <aside className="agent-skill-sidebar">
      <div className="agent-module-brand">
        <span className="brand-mark">
          <img className="brand-icon" src="/doodlestory-icon.svg" alt="" />
        </span>
        <div>
          <strong>DoodleStory</strong>
          <span>Simple Agent Loop</span>
        </div>
      </div>
      <nav className="agent-studio-primary-nav" aria-label="Simple Agent Loop">
        <button type="button" className="active" onClick={() => onNavigatePath("/agent")}>
          <Plus size={17} />
          新对话
        </button>
        <button type="button" onClick={() => onNavigatePath("/agent/skills")}>
          <Box size={17} />
          Skill 管理
        </button>
        {user.role === "admin" ? (
          <button type="button" onClick={() => onNavigatePath("/agent/channels")}>
            <BarChart3 size={17} />
            频道账号
          </button>
        ) : null}
        <a
          href={viewRoutes.tasks}
          onClick={(event) => {
            event.preventDefault();
            onNavigatePath(viewRoutes.tasks);
          }}
        >
          <Images size={17} />
          返回传统工作台
        </a>
      </nav>
      <div className="agent-studio-history">
        <span>最小 Loop 对话</span>
        {conversations.length === 0 ? <p>暂无对话</p> : null}
        {conversations.map((conversation) => (
          <button
            type="button"
            key={conversation.id}
            onClick={() => onNavigatePath(`/agent/${encodeURIComponent(conversation.id)}`)}
          >
            <i />
            <span>
              <strong>{conversation.title}</strong>
              <small>{agentConversationTime(conversation.last_message_at)}</small>
            </span>
          </button>
        ))}
      </div>
      <div className="agent-account-panel">
        <div className="agent-account-credit">
          <Sparkles size={16} />
          <span>
            <strong>Skill 驱动真实 Tools</strong>
            <small>generate_image · generate_speech · generate_subtitles · render_story_video · publish_youtube_video</small>
          </span>
        </div>
        <div className="agent-account-credit">
          <Coins size={16} />
          <span>
            <strong>
              {creditOverview
                ? `${creditOverview.account.balance} 积分`
                : creditError || "积分加载中"}
            </strong>
            <small>本 Sprint 暂未接入新 Loop 结算</small>
          </span>
        </div>
        <div className="agent-account-user">
          <span>{(user.display_name || user.email).slice(0, 1).toUpperCase()}</span>
          <div>
            <strong>{user.display_name || user.email}</strong>
            <small>个人工作区</small>
          </div>
          <button type="button" aria-label="退出登录" onClick={() => void onLogout()}>
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  );
}

type NativeFunctionCallProjection = {
  itemId: string;
  toolCallId: string;
  name: string;
  argumentsText: string;
  argumentsComplete: boolean;
  toolStatus: "pending" | "prepared" | "running" | "completed" | "failed" | "cancelled" | "unknown" | "reused";
  toolResult: Record<string, unknown> | null;
};

type NativeResponseProjection = {
  responseId: string;
  modelCallCount: number;
  status: "running" | "completed";
  text: string;
  functionCalls: NativeFunctionCallProjection[];
};

function nativeAgentResponseProjection(events: NativeAgentEvent[]): NativeResponseProjection[] {
  const responses: NativeResponseProjection[] = [];
  const responseById = new Map<string, NativeResponseProjection>();
  const callById = new Map<string, NativeFunctionCallProjection>();
  let currentResponse: NativeResponseProjection | null = null;

  const ensureResponse = (responseId: string, modelCallCount = 0) => {
    const existing = responseById.get(responseId);
    if (existing) return existing;
    const response: NativeResponseProjection = {
      responseId,
      modelCallCount: modelCallCount || responses.length + 1,
      status: "running",
      text: "",
      functionCalls: [],
    };
    responses.push(response);
    responseById.set(responseId, response);
    return response;
  };

  for (const event of [...events].sort((left, right) => left.sequence - right.sequence)) {
    const payload = event.payload;
    const responseId = String(payload.response_id || "");
    if (event.event_type === "response.started") {
      currentResponse = ensureResponse(
        responseId,
        Number(payload.model_call_count || 0),
      );
      continue;
    }
    if (event.event_type === "response.output_text.delta") {
      currentResponse = ensureResponse(responseId || currentResponse?.responseId || `response-${event.sequence}`);
      currentResponse.text += String(payload.delta || "");
      continue;
    }
    if (event.event_type === "response.function_call.started") {
      currentResponse = ensureResponse(responseId || currentResponse?.responseId || `response-${event.sequence}`);
      const call: NativeFunctionCallProjection = {
        itemId: String(payload.item_id || ""),
        toolCallId: String(payload.tool_call_id || ""),
        name: String(payload.name || "function"),
        argumentsText: "",
        argumentsComplete: false,
        toolStatus: "pending",
        toolResult: null,
      };
      currentResponse.functionCalls.push(call);
      if (call.itemId) callById.set(call.itemId, call);
      if (call.toolCallId) callById.set(call.toolCallId, call);
      continue;
    }
    if (
      event.event_type === "response.function_call.arguments.delta"
      || event.event_type === "response.function_call.arguments.done"
    ) {
      const call = callById.get(String(payload.item_id || ""))
        || callById.get(String(payload.tool_call_id || ""));
      if (call) {
        if (event.event_type.endsWith(".delta")) {
          call.argumentsText += String(payload.delta || "");
        } else {
          call.argumentsText = String(payload.arguments || call.argumentsText);
          call.argumentsComplete = true;
        }
      }
      continue;
    }
    if (event.event_type.startsWith("tool.")) {
      const call = callById.get(String(payload.tool_call_id || ""));
      if (!call) continue;
      const statusByEvent: Record<string, NativeFunctionCallProjection["toolStatus"]> = {
        "tool.prepared": "prepared",
        "tool.started": "running",
        "tool.completed": "completed",
        "tool.failed": "failed",
        "tool.cancelled": "cancelled",
        "tool.unknown": "unknown",
        "tool.reused": "reused",
      };
      call.toolStatus = statusByEvent[event.event_type] || call.toolStatus;
      call.toolResult = payload;
      continue;
    }
    if (event.event_type === "response.completed") {
      currentResponse = responseById.get(responseId) || currentResponse;
      if (currentResponse) currentResponse.status = "completed";
    }
  }

  return responses;
}

function formattedFunctionArguments(value: string) {
  if (!value) return "";
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}

function NativeAgentView({
  user,
  creditOverview,
  creditError,
  routeConversationId,
  onNavigatePath,
  onLogout,
}: {
  user: User;
  creditOverview: CreditOverview | null;
  creditError: string;
  routeConversationId: string | null;
  onNavigatePath: (path: string) => void;
  onLogout: () => Promise<void>;
}) {
  const [conversations, setConversations] = useState<NativeAgentConversation[]>([]);
  const [detail, setDetail] = useState<NativeAgentConversationDetail | null>(null);
  const [skills, setSkills] = useState<AgentResourceOption[]>([]);
  const [styles, setStyles] = useState<AgentResourceOption[]>([]);
  const [youtubeChannels, setYoutubeChannels] = useState<YoutubeChannelSummary[]>([]);
  const [publishableVideos, setPublishableVideos] = useState<PublishableVideo[]>([]);
  const [skillVersionId, setSkillVersionId] = useState("");
  const [styleId, setStyleId] = useState("");
  const [youtubeChannelId, setYoutubeChannelId] = useState("");
  const [youtubePublishableVideoId, setYoutubePublishableVideoId] = useState("");
  const [youtubeVisibility, setYoutubeVisibility] = useState<"public" | "private" | "unlisted">("public");
  const [youtubePlannedAt, setYoutubePlannedAt] = useState("");
  const [registeringVideoId, setRegisteringVideoId] = useState<string | null>(null);
  const [registeringVideo, setRegisteringVideo] = useState(false);
  const [registerForm, setRegisterForm] = useState({
    title: "",
    description: "",
    tags: "",
    thumbnail_url: "",
  });
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [cancellingRunId, setCancellingRunId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [eventConnectionError, setEventConnectionError] = useState("");
  const [previewImageId, setPreviewImageId] = useState<string | null>(null);
  const threadRef = useRef<HTMLElement | null>(null);
  const previewCloseRef = useRef<HTMLButtonElement | null>(null);
  const previewTriggerRef = useRef<HTMLButtonElement | null>(null);

  async function loadConversations() {
    const result = await api.nativeAgentConversations(50);
    setConversations(result.items);
  }

  async function loadDetail(conversationId: string) {
    setLoading(true);
    try {
      setDetail(await api.nativeAgentConversation(conversationId));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.nativeAgentConversations(50),
      api.nativeAgentSkills(),
      api.nativeAgentStyles(),
    ])
      .then(([conversationResult, skillResult, styleResult]) => {
        setConversations(conversationResult.items);
        setSkills(skillResult.items);
        setStyles(styleResult.items);
        setError("");
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : "最小 Agent 加载失败");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (user.role !== "admin") return;
    Promise.all([
      api.youtubeChannels({ remote_status: "normal", limit: 100 }),
      api.youtubePublishableVideos("approved"),
    ])
      .then(([channelResult, videoResult]) => {
        setYoutubeChannels(channelResult.items);
        setPublishableVideos(videoResult.items);
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : "YouTube 发布选项加载失败");
      });
  }, [user.role]);

  useEffect(() => {
    if (!routeConversationId) {
      setDetail(null);
      return;
    }
    void loadDetail(routeConversationId).catch((loadError) => {
      setError(loadError instanceof Error ? loadError.message : "会话加载失败");
    });
  }, [routeConversationId]);

  const activeRun =
    [...(detail?.runs || [])]
      .reverse()
      .find((run) => activeAgentRunStatuses.has(run.status)) || null;
  const cancellationPending = Boolean(
    activeRun
    && (
      activeRun.status === "cancel_requested"
      || cancellingRunId === activeRun.id
    ),
  );

  useEffect(() => {
    if (
      cancellingRunId
      && !detail?.runs.some(
        (run) =>
          run.id === cancellingRunId
          && activeAgentRunStatuses.has(run.status),
      )
    ) {
      setCancellingRunId(null);
    }
  }, [cancellingRunId, detail?.runs]);

  useEffect(() => {
    if (!activeRun) {
      setEventConnectionError("");
      return;
    }
    const source = new EventSource(
      nativeAgentRunEventStreamUrl(activeRun.id),
      { withCredentials: true },
    );
    const handleNativeEvent = (event: MessageEvent<string>) => {
      try {
        const nextEvent = JSON.parse(event.data) as NativeAgentEvent;
        setDetail((current) => {
          if (!current) return current;
          const runs = current.runs.map((run) => {
            if (run.id !== activeRun.id) return run;
            if (run.events.some((item) => item.id === nextEvent.id)) return run;
            return {
              ...run,
              events: [...run.events, nextEvent].sort(
                (left, right) => left.sequence - right.sequence,
              ),
            };
          });
          return { ...current, runs };
        });
        setEventConnectionError("");
      } catch {
        setEventConnectionError("实时事件内容无法读取，请刷新页面恢复当前状态");
      }
    };
    const handleUpdate = (event: MessageEvent<string>) => {
      try {
        const nextRun = JSON.parse(event.data) as NativeAgentRun;
        setDetail((current) => {
          if (!current || current.id !== nextRun.conversation_id) return current;
          const existingIndex = current.runs.findIndex((run) => run.id === nextRun.id);
          const runs =
            existingIndex === -1
              ? [...current.runs, nextRun]
              : current.runs.map((run) => (run.id === nextRun.id ? nextRun : run));
          return { ...current, runs };
        });
        setEventConnectionError("");
        if (!activeAgentRunStatuses.has(nextRun.status)) {
          source.close();
          void loadConversations().catch((loadError) => {
            setError(loadError instanceof Error ? loadError.message : "会话列表刷新失败");
          });
        }
      } catch {
        setEventConnectionError("实时事件内容无法读取，请刷新页面恢复当前状态");
      }
    };
    source.addEventListener("native.event", handleNativeEvent as EventListener);
    source.addEventListener("run.updated", handleUpdate as EventListener);
    source.onerror = () => {
      setEventConnectionError("实时连接已断开，浏览器正在自动重连");
    };
    return () => {
      source.removeEventListener("native.event", handleNativeEvent as EventListener);
      source.removeEventListener("run.updated", handleUpdate as EventListener);
      source.close();
    };
  }, [activeRun?.id]);

  const threadSignature = detail?.runs
    .map(
      (run) =>
        `${run.id}:${run.status}:${run.items.length}:${run.images.length}:${run.audios.length}:${run.videos.length}:${run.external_contents.length}:${run.events.length}`,
    )
    .join("|");
  const previewImage = detail?.runs
    .flatMap((run) => run.images)
    .find((image) => image.id === previewImageId) || null;
  const videoToRegister = detail?.runs
    .flatMap((run) => run.videos)
    .find((video) => video.id === registeringVideoId) || null;

  useEffect(() => {
    if (!threadRef.current || !threadSignature) return;
    const frame = window.requestAnimationFrame(() => {
      threadRef.current?.scrollTo({
        top: threadRef.current.scrollHeight,
        behavior: "smooth",
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [threadSignature]);

  useEffect(() => {
    if (!previewImageId) return;
    previewCloseRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPreviewImageId(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("keydown", closeOnEscape);
      previewTriggerRef.current?.focus();
    };
  }, [previewImageId]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const retryingLatestRun = content.trim() === "重试";
    if (
      !content.trim()
      || (!retryingLatestRun && !skillVersionId)
      || sending
      || activeRun
    ) return;
    if (retryingLatestRun && !detail) {
      setError("当前会话还没有可重试的任务");
      return;
    }
    const selectedYoutubeChannel = youtubeChannels.find((item) => item.id === youtubeChannelId);
    const selectedPublishableVideo = publishableVideos.find((item) => item.id === youtubePublishableVideoId);
    if (youtubeChannelId && !selectedPublishableVideo) {
      setError("选择 @频道后，还需要选择一个审核通过的视频");
      return;
    }
    if (selectedYoutubeChannel && selectedPublishableVideo) {
      const confirmed = window.confirm(
        [
          `确认创建真实 YouTube 发布请求？`,
          `频道：${selectedYoutubeChannel.alias || selectedYoutubeChannel.title}`,
          `视频：${selectedPublishableVideo.title}`,
          `Agent 视频 ID：${selectedPublishableVideo.source_native_agent_video_id}`,
          `可见性：${youtubeVisibility}`,
          `时间：${youtubePlannedAt ? formatDateTime(new Date(youtubePlannedAt).toISOString()) : "立即发布"}`,
          "提交后 Agent 只返回异步任务 ID，不会等待上传完成。",
        ].join("\n"),
      );
      if (!confirmed) return;
    }
    setSending(true);
    setError("");
    try {
      const conversation =
        detail ||
        (await api.createNativeAgentConversation({
          title: content.trim().slice(0, 40),
        }));
      const run = retryingLatestRun
        ? await api.retryLatestNativeAgentRun(conversation.id)
        : await api.createNativeAgentRun(conversation.id, {
            content,
            skill_version_id: skillVersionId,
            style_id: styleId || null,
            youtube_channel_id: selectedYoutubeChannel?.id || null,
            youtube_publishable_video_id: selectedPublishableVideo?.id || null,
            youtube_publish_confirmation:
              selectedYoutubeChannel && selectedPublishableVideo
                ? {
                    visibility: youtubeVisibility,
                    planned_publish_at: youtubePlannedAt
                      ? new Date(youtubePlannedAt).toISOString()
                      : null,
                    notify_subscribers: true,
                    confirmed: true,
                  }
                : null,
          });
      setContent("");
      setYoutubeChannelId("");
      setYoutubePublishableVideoId("");
      setYoutubePlannedAt("");
      setDetail((current) =>
        current?.id === conversation.id
          ? {
              ...current,
              runs: retryingLatestRun
                ? current.runs.map((existingRun) =>
                    existingRun.id === run.id ? run : existingRun
                  )
                : [...current.runs, run],
            }
          : current,
      );
      void loadConversations().catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : "会话列表刷新失败");
      });
      if (routeConversationId !== conversation.id) {
        onNavigatePath(`/agent/${encodeURIComponent(conversation.id)}`);
      }
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Agent Loop 执行失败");
    } finally {
      setSending(false);
    }
  }

  async function cancelActiveRun() {
    if (!activeRun || cancellationPending) return;
    setCancellingRunId(activeRun.id);
    setError("");
    try {
      const nextRun = await api.cancelNativeAgentRun(activeRun.id);
      setDetail((current) => {
        if (!current) return current;
        return {
          ...current,
          runs: current.runs.map((run) =>
            run.id === nextRun.id ? nextRun : run
          ),
        };
      });
    } catch (cancelError) {
      setCancellingRunId(null);
      setError(
        cancelError instanceof Error
          ? cancelError.message
          : "终止 Native Agent 任务失败",
      );
    }
  }

  return (
    <section className="native-agent-layout">
      <NativeAgentSidebar
        user={user}
        conversations={conversations}
        creditOverview={creditOverview}
        creditError={creditError}
        onNavigatePath={onNavigatePath}
        onLogout={onLogout}
      />
      <main className="native-agent-workspace">
        <header className="native-agent-header">
          <div>
            <span>Agents SDK 原生 Loop</span>
            <h1>{detail?.title || "从一个简单 Loop 开始"}</h1>
          </div>
          <code>model → Skill tools → persisted assets → model</code>
        </header>

        <section className="native-agent-thread" aria-live="polite" ref={threadRef}>
          {loading ? (
            <div className="native-agent-empty"><Loader2 className="spin" size={24} />正在加载…</div>
          ) : null}
          {!loading && !detail ? (
            <div className="native-agent-empty">
              <Sparkles size={30} />
              <h2>Skill 决定创作流程，Runtime 不写漫画分支</h2>
              <p>故事改写、分镜、Prompt 和生图 Review 都在同一个模型 Loop 内完成。</p>
            </div>
          ) : null}
          {detail?.runs.map((run) => {
            const userItem = run.items.find((item) => item.item_type === "user_input");
            const responses = nativeAgentResponseProjection(run.events);
            const runActive = activeAgentRunStatuses.has(run.status);
            const finalOutputAlreadyShown = Boolean(
              run.final_output
              && responses.some(
                (response) => response.text.trim() === run.final_output?.trim(),
              ),
            );
            return (
              <article className="native-agent-run" key={run.id}>
                <div className="native-agent-user-message">
                  {String(userItem?.payload.content || "")}
                </div>
                <div className="native-agent-run-meta">
                  <span>{run.skill_name} · v{run.skill_version}</span>
                  <span>{run.style_name}</span>
                  {run.youtube_channel_id ? <span>@{run.youtube_channel_name}</span> : null}
                  {run.youtube_publishable_video_id ? <span>发布：{run.youtube_publishable_video_title}</span> : null}
                  <span>
                    {runActive && run.model_call_count === 0
                      ? "模型 Loop 运行中"
                      : `${run.model_call_count} 次模型调用`}
                  </span>
                  <span>{run.image_call_count} 次生图</span>
                  <span>{run.speech_call_count} 次语音生成</span>
                  <span>{run.subtitle_call_count} 次字幕生成</span>
                  <span>{run.video_call_count} 次视频生成</span>
                </div>
                <div className="native-agent-responses" aria-label="Agent Response 与工具调用">
                  {responses.map((response, responseIndex) => (
                    <section className="native-agent-response" key={response.responseId}>
                      <header>
                        <span>Response {response.modelCallCount || responseIndex + 1}</span>
                        {response.status === "running" ? (
                          <Loader2 className="spin" size={14} />
                        ) : (
                          <CheckCircle2 size={14} />
                        )}
                      </header>
                      {response.text ? (
                        <div className="native-agent-response-text">{response.text}</div>
                      ) : null}
                      {response.functionCalls.map((call) => {
                        const failed = call.toolStatus === "failed"
                          || call.toolStatus === "cancelled"
                          || call.toolStatus === "unknown";
                        const active = call.toolStatus === "pending"
                          || call.toolStatus === "prepared"
                          || call.toolStatus === "running";
                        const toolStatusLabel: Record<NativeFunctionCallProjection["toolStatus"], string> = {
                          pending: "等待执行",
                          prepared: "已准备",
                          running: "执行中",
                          completed: "已完成",
                          failed: "执行失败",
                          cancelled: "已终止",
                          unknown: "结果不确定",
                          reused: "复用已有结果",
                        };
                        return (
                          <section className="native-agent-function-call" key={call.itemId || call.toolCallId}>
                            <header>
                              <span>Function Call · <code>{call.name}</code></span>
                              <span className={failed ? "is-error" : active ? "is-running" : "is-complete"}>
                                {active ? <Loader2 className="spin" size={13} /> : failed ? <AlertCircle size={13} /> : <CheckCircle2 size={13} />}
                                {toolStatusLabel[call.toolStatus]}
                              </span>
                            </header>
                            {call.argumentsText ? (
                              <div>
                                <strong>Arguments{call.argumentsComplete ? "" : "（接收中）"}</strong>
                                <pre>{formattedFunctionArguments(call.argumentsText)}</pre>
                              </div>
                            ) : null}
                            {call.toolResult ? (
                              <div>
                                <strong>
                                  {call.toolStatus === "completed" || call.toolStatus === "reused"
                                    ? "Tool Result"
                                    : "Tool Execution"}
                                </strong>
                                <pre>{JSON.stringify(call.toolResult, null, 2)}</pre>
                              </div>
                            ) : null}
                          </section>
                        );
                      })}
                    </section>
                  ))}
                  {runActive && responses.length === 0 ? (
                    <div className="native-agent-response-waiting">
                      <Loader2 className="spin" size={15} />
                      <span>等待第一个 Response</span>
                    </div>
                  ) : null}
                </div>
                {run.images.length > 0 ? (
                  <div className="native-agent-image-grid">
                    {run.images.map((image) => (
                      <figure key={image.id}>
                        <button
                          type="button"
                          className="native-agent-image-button"
                          aria-label="放大查看 Agent 生成图片"
                          onClick={(event) => {
                            previewTriggerRef.current = event.currentTarget;
                            setPreviewImageId(image.id);
                          }}
                        >
                          <LazyAssetImage
                            assetId={image.asset_id}
                            alt="Agent 生成结果"
                            eager
                            variant="original"
                          />
                          <Eye size={18} aria-hidden="true" />
                        </button>
                        <figcaption>{image.image_model} · {image.aspect_ratio}</figcaption>
                      </figure>
                    ))}
                  </div>
                ) : null}
                {run.external_contents.length > 0 ? (
                  <div className="native-agent-external-content-list">
                    {run.external_contents.map((content) => (
                      <article key={content.id}>
                        <div>
                          <FileText size={19} aria-hidden="true" />
                          <span>
                            <small>微信公众号文章</small>
                            <strong>{content.title || "未命名公众号文章"}</strong>
                          </span>
                        </div>
                        <p>
                          {[content.author_name, content.publish_time].filter(Boolean).join(" · ")
                            || "来源信息未提供"}
                        </p>
                        <div className="native-agent-external-content-actions">
                          <a href={content.source_url} target="_blank" rel="noreferrer">
                            查看原文 <ArrowUpRight size={13} />
                          </a>
                          <a
                            href={api.assetContentUrl(content.content_asset_id)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            打开 Markdown <FileText size={13} />
                          </a>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : null}
                {run.audios.length > 0 ? (
                  <div className="native-agent-audio-list">
                    {run.audios.map((audio) => (
                      <figure key={audio.id}>
                        <div>
                          <Volume2 size={18} aria-hidden="true" />
                          <span>
                            <strong>生成语音</strong>
                            <small>
                              {audio.model} · {audio.sample_rate / 1000} kHz
                              {audio.duration_ms !== null
                                ? ` · ${(audio.duration_ms / 1000).toFixed(1)} 秒`
                                : ""}
                            </small>
                          </span>
                        </div>
                        <audio
                          controls
                          preload="metadata"
                          src={api.assetContentUrl(audio.asset_id)}
                        >
                          当前浏览器不支持音频播放。
                        </audio>
                        <figcaption>{audio.text}</figcaption>
                      </figure>
                    ))}
                  </div>
                ) : null}
                {run.videos.length > 0 ? (
                  <div className="native-agent-video-list">
                    {run.videos.map((video) => (
                      <figure key={video.id}>
                        <video
                          controls
                          preload="metadata"
                          src={api.assetContentUrl(video.asset_id)}
                        >
                          当前浏览器不支持视频播放。
                        </video>
                        <figcaption>
                          <span>
                            {video.template_id} · {video.width}×{video.height}
                            {" · "}{(video.duration_ms / 1000).toFixed(1)} 秒
                          </span>
                          {user.role === "admin" ? (
                            publishableVideos.some((item) => item.source_native_agent_video_id === video.id) ? (
                              <small className="native-video-registered"><CheckCircle2 size={13} />已审核登记</small>
                            ) : (
                              <button
                                type="button"
                                className="youtube-text-action"
                                onClick={() => {
                                  setRegisteringVideoId(video.id);
                                  setRegisterForm({
                                    title: detail?.title || "Agent 生成视频",
                                    description: "",
                                    tags: "",
                                    thumbnail_url: "",
                                  });
                                }}
                              >
                                <Upload size={13} />审核并登记发布
                              </button>
                            )
                          ) : null}
                        </figcaption>
                      </figure>
                    ))}
                  </div>
                ) : null}
                {run.final_output && !finalOutputAlreadyShown ? (
                  <div className="native-agent-assistant-message">{run.final_output}</div>
                ) : null}
                {run.error_message ? (
                  <div className="native-agent-run-error">
                    <AlertCircle size={16} />
                    {run.error_message}
                  </div>
                ) : null}
              </article>
            );
          })}
          {eventConnectionError ? (
            <div className="native-agent-stream-warning">
              <AlertCircle size={15} />
              {eventConnectionError}
            </div>
          ) : null}
        </section>

        <form className="native-agent-composer" onSubmit={submit}>
          <div className="native-agent-context-controls">
            <label>
              <span>Skill</span>
              <select
                value={skillVersionId}
                onChange={(event) => setSkillVersionId(event.target.value)}
                disabled={sending || Boolean(activeRun)}
                required={content.trim() !== "重试"}
              >
                <option value="">选择已发布的 Skill</option>
                {skills.map((skill) => (
                  <option value={skill.id} key={skill.id}>{skill.display_name}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Style</span>
              <select
                value={styleId}
                onChange={(event) => setStyleId(event.target.value)}
                disabled={sending || Boolean(activeRun)}
              >
                <option value="">不使用 Style（仅生图 Tool 需要）</option>
                {styles.map((style) => (
                  <option value={style.id} key={style.id}>{style.display_name}</option>
                ))}
              </select>
            </label>
            {user.role === "admin" ? (
              <label>
                <span>@频道</span>
                <select
                  value={youtubeChannelId}
                  onChange={(event) => {
                    setYoutubeChannelId(event.target.value);
                    if (!event.target.value) setYoutubePublishableVideoId("");
                  }}
                  disabled={sending || Boolean(activeRun)}
                >
                  <option value="">不发布到 YouTube</option>
                  {youtubeChannels.map((channel) => (
                    <option value={channel.id} key={channel.id}>
                      @{channel.alias || channel.title} · {channel.title}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {user.role === "admin" && youtubeChannelId ? (
              <>
                <label>
                  <span>审核视频</span>
                  <select
                    value={youtubePublishableVideoId}
                    onChange={(event) => setYoutubePublishableVideoId(event.target.value)}
                    disabled={sending || Boolean(activeRun)}
                    required
                  >
                    <option value="">选择审核通过的视频</option>
                    {publishableVideos.map((video) => (
                      <option value={video.id} key={video.id}>
                        {video.title} · {video.source_native_agent_video_id}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>可见性</span>
                  <select value={youtubeVisibility} onChange={(event) => setYoutubeVisibility(event.target.value as typeof youtubeVisibility)} disabled={sending || Boolean(activeRun)}>
                    <option value="public">公开</option>
                    <option value="unlisted">不公开列出</option>
                    <option value="private">私密</option>
                  </select>
                </label>
                <label>
                  <span>计划时间（上海时区）</span>
                  <input type="datetime-local" value={youtubePlannedAt} onChange={(event) => setYoutubePlannedAt(event.target.value)} disabled={sending || Boolean(activeRun)} />
                </label>
              </>
            ) : null}
          </div>
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="输入故事或图片创作目标…"
            disabled={sending || Boolean(activeRun)}
          />
          <div className="native-agent-composer-footer">
            <span>
              {activeRun
                ? "终止后不会再启动新的 Tool；已被 Provider 接收的请求可能仍会计费。"
                : content.trim() === "重试"
                  ? "将继续最近一次 Run，并复用该 Run 固定的 Skill、Style 和成功资产；当前选择不会生效。"
                  : youtubeChannelId
                    ? "已选择结构化 @频道；运行前会再次展示频道、视频、可见性和时间供你确认。"
                    : "Tool 由发布版 Skill 决定；语音结果会保存并可直接播放。"}
            </span>
            <button
              type={activeRun ? "button" : "submit"}
              className={activeRun ? "is-cancel" : undefined}
              onClick={activeRun ? () => void cancelActiveRun() : undefined}
              disabled={activeRun
                ? cancellationPending
                : !content.trim()
                  || (content.trim() !== "重试" && !skillVersionId)
                  || sending}
            >
              {sending || cancellationPending
                ? <Loader2 className="spin" size={17} />
                : activeRun
                  ? <X size={17} />
                  : <Sparkles size={17} />}
              {sending
                ? "正在提交…"
                : cancellationPending
                  ? "正在终止…"
                  : activeRun
                    ? "终止任务"
                    : "运行 Agent"}
            </button>
          </div>
          {error ? <div className="native-agent-run-error"><AlertCircle size={16} />{error}</div> : null}
        </form>
        {previewImage ? (
          <div
            className="image-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Agent 生成图片预览"
            onClick={() => setPreviewImageId(null)}
          >
            <button
              ref={previewCloseRef}
              type="button"
              className="modal-close"
              aria-label="关闭 Agent 图片预览"
              onClick={() => setPreviewImageId(null)}
            >
              <X size={18} />
            </button>
            <div onClick={(event) => event.stopPropagation()}>
              <LazyAssetImage
                assetId={previewImage.asset_id}
                alt="Agent 生成图片放大预览"
                eager
                variant="original"
              />
            </div>
          </div>
        ) : null}
        {videoToRegister ? (
          <div className="youtube-publish-overlay" role="presentation" onMouseDown={() => setRegisteringVideoId(null)}>
            <form
              className="youtube-publish-dialog"
              role="alertdialog"
              aria-modal="true"
              aria-labelledby="register-video-title"
              onMouseDown={(event) => event.stopPropagation()}
              onSubmit={async (event) => {
                event.preventDefault();
                setRegisteringVideo(true);
                try {
                  const created = await api.createYoutubePublishableVideo({
                    source_native_agent_video_id: videoToRegister.id,
                    thumbnail_url: registerForm.thumbnail_url.trim() || null,
                    title: registerForm.title.trim(),
                    description: registerForm.description.trim(),
                    tags: registerForm.tags.split(/[,，]/).map((item) => item.trim()).filter(Boolean),
                    planned_publish_at: null,
                    contains_synthetic_media: true,
                    review_status: "approved",
                  });
                  setPublishableVideos((current) => [created, ...current]);
                  setYoutubePublishableVideoId(created.id);
                  setRegisteringVideoId(null);
                  setError("");
                } catch (registerError) {
                  setError(registerError instanceof Error ? registerError.message : "视频登记失败");
                } finally {
                  setRegisteringVideo(false);
                }
              }}
            >
              <header>
                <span><Film size={18} /></span>
                <div>
                  <h2 id="register-video-title">审核并登记 Agent 视频</h2>
                  <p>登记后保留 Agent 视频 ID；“审核通过”表示它可以进入真实发布确认。</p>
                </div>
              </header>
              <label>标题<input required maxLength={200} value={registerForm.title} onChange={(event) => setRegisterForm({ ...registerForm, title: event.target.value })} /></label>
              <label>描述<textarea maxLength={10000} value={registerForm.description} onChange={(event) => setRegisterForm({ ...registerForm, description: event.target.value })} /></label>
              <label>标签<input value={registerForm.tags} onChange={(event) => setRegisterForm({ ...registerForm, tags: event.target.value })} placeholder="用逗号分隔" /></label>
              <label>封面 URL（可选）<input type="url" value={registerForm.thumbnail_url} onChange={(event) => setRegisterForm({ ...registerForm, thumbnail_url: event.target.value })} /></label>
              <div className="youtube-register-trace">Agent 视频 ID <code>{videoToRegister.id}</code></div>
              <footer>
                <button className="secondary-button" type="button" disabled={registeringVideo} onClick={() => setRegisteringVideoId(null)}>取消</button>
                <button className="primary-button" disabled={registeringVideo || !registerForm.title.trim()}>
                  {registeringVideo ? <Loader2 className="spin" size={15} /> : <CheckCircle2 size={15} />}
                  审核通过并登记
                </button>
              </footer>
            </form>
          </div>
        ) : null}
      </main>
    </section>
  );
}

function agentEventText(event: AgentPublicEvent) {
  const panel = typeof event.payload.panel_key === "string" ? event.payload.panel_key.replace("panel-", "Panel ") : "";
  const labels: Record<string, string> = {
    "run.started": "Agent 开始整理这次创作",
    "skill.selected": `已选择 ${String(event.payload.name || "Skill")} v${String(event.payload.version || "")}`,
    "skill.version_pinned": `本轮已固定 ${String(event.payload.name || "Skill")} v${String(event.payload.version || "")}`,
    "skill.loaded": `已加载 ${String(event.payload.name || "Skill")} v${String(event.payload.version || "")}`,
    "skill.waiting_for_confirmation": `${String(event.payload.name || "Skill")} 的方案等待确认`,
    "artifact.created": `已生成漫画方案 v${String(event.payload.version || "")}`,
    "approval.requested": "漫画方案等待你的确认",
    "approval.resolved": event.payload.decision === "approve" ? "方案已批准，准备生成图片" : "已收到修改意见，正在生成新方案",
    "tool.started": `开始生成 ${panel}`,
    "tool.progress": `${panel} 已进入图片生成队列`,
    "tool.completed": `${panel} 已生成`,
    "tool.failed": `${panel} 生成失败`,
    "assistant.message": "Agent 已汇总本轮结果",
    "run.completed": "本轮创作已完成",
    "run.failed": "本轮创作失败",
    "panel.revision_requested": "已提交 Panel 局部修改",
    "image.version_created": "已创建并保留新的图片版本",
    "image.inspection_started": "正在用真实 VL 检查新版本",
    "image.inspection_completed": `VL 检查完成：${String(event.payload.verdict || event.payload.status || "")}`,
    "image.version_accepted": "已接受当前图片版本",
    "image.version_restored": "已恢复历史图片版本",
    "run.paused": "已暂停后续 Agent 步骤",
    "run.resumed": "已继续 Agent 运行",
  };
  return labels[event.event_type] || "创作状态已更新";
}

function AgentView({
  user,
  creditOverview,
  creditError,
  routeConversationId,
  routeTaskId,
  onNavigatePath,
  onCreditsChanged,
  onLogout,
}: {
  user: User;
  creditOverview: CreditOverview | null;
  creditError: string;
  routeConversationId: string | null;
  routeTaskId: string | null;
  onNavigatePath: (path: string, options?: { replace?: boolean }) => void;
  onCreditsChanged: () => Promise<CreditOverview | null>;
  onLogout: () => Promise<void>;
}) {
  const [conversations, setConversations] = useState<AgentConversation[]>([]);
  const [detail, setDetail] = useState<AgentConversationDetail | null>(null);
  const [styleResources, setStyleResources] = useState<AgentResourceOption[]>([]);
  const [skillResources, setSkillResources] = useState<AgentResourceOption[]>([]);
  const [characterResources, setCharacterResources] = useState<AgentResourceOption[]>([]);
  const [taskResources, setTaskResources] = useState<AgentResourceOption[]>([]);
  const [panelResources, setPanelResources] = useState<AgentResourceOption[]>([]);
  const [imageResources, setImageResources] = useState<AgentResourceOption[]>([]);
  const [selectedResources, setSelectedResources] = useState<AgentResourceRef[]>([]);
  const [resourceLoading, setResourceLoading] = useState(false);
  const [resourceError, setResourceError] = useState("");
  const [artifacts, setArtifacts] = useState<AgentArtifact[]>([]);
  const [events, setEvents] = useState<AgentPublicEvent[]>([]);
  const [eventConnectionError, setEventConnectionError] = useState("");
  const [eventReconnectToken, setEventReconnectToken] = useState(0);
  const [approvalFeedback, setApprovalFeedback] = useState<Record<string, string>>({});
  const [decidingApprovalId, setDecidingApprovalId] = useState("");
  const [idea, setIdea] = useState("");
  const [search, setSearch] = useState("");
  const [resourceSearch, setResourceSearch] = useState("");
  const [resourceMenuOpen, setResourceMenuOpen] = useState(false);
  const [conversationMetadata, setConversationMetadata] = useState<Record<string, { summary: string; runStatus: AgentRunStatus | null }>>({});
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [creatingConversation, setCreatingConversation] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [inspector, setInspector] = useState<AgentTaskInspector | null>(null);
  const [inspectorLoading, setInspectorLoading] = useState(false);
  const [inspectorError, setInspectorError] = useState("");
  const [selectedInspectorPanelId, setSelectedInspectorPanelId] = useState("");
  const routeConversationIdRef = useRef(routeConversationId);
  const routeTaskIdRef = useRef(routeTaskId);
  const previousRouteTaskIdRef = useRef<string | null>(routeTaskId);
  const inspectorTriggerRef = useRef<HTMLButtonElement | null>(null);
  const ideaInputRef = useRef<HTMLTextAreaElement | null>(null);
  const lastEventIdRef = useRef<string | null>(null);

  function persistSelectedResources(resources: AgentResourceRef[], draftId = routeConversationId || newAgentDraftId) {
    setSelectedResources(resources);
    if (resources.length === 0) {
      window.sessionStorage.removeItem(agentDraftKey(draftId, "resources"));
    } else {
      window.sessionStorage.setItem(
        agentDraftKey(draftId, "resources"),
        JSON.stringify(resources),
      );
    }
  }

  function restoreDraftResources(draftId: string) {
    try {
      setSelectedResources(
        parseAgentDraftResources(
          window.sessionStorage.getItem(agentDraftKey(draftId, "resources")),
        ),
      );
      setResourceError("");
    } catch (draftError) {
      setSelectedResources([]);
      setResourceError(
        draftError instanceof Error ? draftError.message : "资源草稿读取失败",
      );
    }
  }

  const selectedStyleRef = selectedResources.find((ref) => ref.kind === "style") || null;
  const selectedTaskRef = selectedResources.find((ref) => ref.kind === "task") || null;
  const selectedPanelRef = selectedResources.find((ref) => ref.kind === "panel") || null;

  useEffect(() => {
    routeConversationIdRef.current = routeConversationId;
    if (routeConversationId) window.sessionStorage.setItem(lastAgentConversationKey, routeConversationId);
  }, [routeConversationId]);

  useEffect(() => {
    if (!resourceMenuOpen) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setResourceLoading(true);
      setResourceError("");
      void Promise.all([
        api.agentSkillResources({ query: resourceSearch, limit: 20 }),
        api.agentStyleResources({ query: resourceSearch, limit: 20 }),
        api.agentCharacterResources({ query: resourceSearch, limit: 20 }),
        api.agentTaskResources({ query: resourceSearch, limit: 20 }),
      ])
        .then(([skills, styles, characters, tasks]) => {
          if (cancelled) return;
          setSkillResources(skills.items);
          setStyleResources(styles.items);
          setCharacterResources(characters.items);
          setTaskResources(tasks.items);
        })
        .catch((loadError) => {
          if (!cancelled) {
            setResourceError(
              loadError instanceof Error ? loadError.message : "资源搜索失败",
            );
          }
        })
        .finally(() => {
          if (!cancelled) setResourceLoading(false);
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [resourceMenuOpen, resourceSearch]);

  useEffect(() => {
    if (!resourceMenuOpen || !selectedTaskRef) {
      setPanelResources([]);
      return;
    }
    let cancelled = false;
    setResourceLoading(true);
    void api
      .agentTaskPanelResources(selectedTaskRef.id)
      .then((result) => {
        if (!cancelled) setPanelResources(result.items);
      })
      .catch((loadError) => {
        if (!cancelled) {
          setResourceError(
            loadError instanceof Error ? loadError.message : "Panel 加载失败",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setResourceLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [resourceMenuOpen, selectedTaskRef?.id]);

  useEffect(() => {
    if (!resourceMenuOpen || !selectedPanelRef) {
      setImageResources([]);
      return;
    }
    let cancelled = false;
    setResourceLoading(true);
    void api
      .agentPanelImageResources(selectedPanelRef.id, 20)
      .then((result) => {
        if (!cancelled) setImageResources(result.items);
      })
      .catch((loadError) => {
        if (!cancelled) {
          setResourceError(
            loadError instanceof Error ? loadError.message : "图片版本加载失败",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setResourceLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [resourceMenuOpen, selectedPanelRef?.id]);

  useEffect(() => {
    routeTaskIdRef.current = routeTaskId;
  }, [routeTaskId]);

  async function loadConversations(hydrateMetadata = false) {
    try {
      const result = await api.agentConversations({ limit: 100 });
      setConversations(result.items);
      if (hydrateMetadata) void hydrateConversationMetadata(result.items.slice(0, 12));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "会话列表加载失败");
    } finally {
      setLoadingList(false);
    }
  }

  async function hydrateConversationMetadata(items: AgentConversation[]) {
    try {
      const details = await Promise.all(items.map((conversation) => api.agentConversation(conversation.id)));
      setConversationMetadata((current) => {
        const next = { ...current };
        details.forEach((conversation) => {
          const message = [...conversation.messages].reverse().find((item) => item.role !== "task_card");
          next[conversation.id] = {
            summary: message?.content || (conversation.status === "archived" ? "已归档的历史对话" : "继续上次创作"),
            runStatus: conversation.runs[0]?.status || null,
          };
        });
        return next;
      });
    } catch (metadataError) {
      setError(metadataError instanceof Error ? metadataError.message : "部分会话状态加载失败");
    }
  }

  async function loadDetail(conversationId: string, quiet = false) {
    if (!quiet) setLoadingDetail(true);
    try {
      const result = await api.agentConversation(conversationId);
      if (routeConversationIdRef.current !== conversationId) return null;
      setDetail(result);
      const artifactResult = await api.agentArtifacts(conversationId);
      if (routeConversationIdRef.current !== conversationId) return null;
      setArtifacts(artifactResult.items);
      const message = [...result.messages].reverse().find((item) => item.role !== "task_card");
      setConversationMetadata((current) => ({
        ...current,
        [conversationId]: {
          summary: message?.content || (result.status === "archived" ? "已归档的历史对话" : "继续上次创作"),
          runStatus: result.runs[0]?.status || null,
        },
      }));
      setError("");
      return result;
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "会话加载失败");
      return null;
    } finally {
      if (!quiet) setLoadingDetail(false);
    }
  }

  async function loadInspector(conversationId: string, taskId: string) {
    setInspectorLoading(true);
    setInspectorError("");
    try {
      const result = await api.agentConversationTask(conversationId, taskId);
      if (
        routeConversationIdRef.current !== conversationId ||
        routeTaskIdRef.current !== taskId
      ) {
        return;
      }
      setInspector(result);
      setSelectedInspectorPanelId((current) =>
        result.panels.some((panel) => panel.id === current)
          ? current
          : result.panels[0]?.id || "",
      );
    } catch (loadError) {
      if (
        routeConversationIdRef.current === conversationId &&
        routeTaskIdRef.current === taskId
      ) {
        setInspector(null);
        setInspectorError(loadError instanceof Error ? loadError.message : "任务读取失败");
      }
    } finally {
      if (
        routeConversationIdRef.current === conversationId &&
        routeTaskIdRef.current === taskId
      ) {
        setInspectorLoading(false);
      }
    }
  }

  useEffect(() => {
    void loadConversations(true);
    api
      .agentStyleResources({ limit: 20 })
      .then((result) => {
        setStyleResources(result.items);
      })
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "风格加载失败"));
  }, []);

  useEffect(() => {
    setEvents([]);
    lastEventIdRef.current = null;
    setEventConnectionError("");
    if (!routeConversationId) {
      setDetail(null);
      setArtifacts([]);
      setIdea(window.sessionStorage.getItem(agentDraftKey(newAgentDraftId, "idea")) || "");
      restoreDraftResources(newAgentDraftId);
      return;
    }
    setDetail(null);
    setIdea(window.sessionStorage.getItem(agentDraftKey(routeConversationId, "idea")) || "");
    restoreDraftResources(routeConversationId);
    setResourceMenuOpen(false);
    void loadDetail(routeConversationId);
  }, [routeConversationId]);

  useEffect(() => {
    if (!routeConversationId) return;
    setEventConnectionError("");
    const source = new EventSource(
      agentEventStreamUrl(routeConversationId, lastEventIdRef.current),
      { withCredentials: true },
    );
    const eventTypes = [
      "run.started", "skill.selected", "skill.version_pinned", "skill.loaded",
      "skill.waiting_for_confirmation", "artifact.created", "approval.requested",
      "approval.resolved", "tool.started", "tool.progress", "tool.completed",
      "tool.failed", "assistant.message", "run.completed", "run.failed",
      "panel.revision_requested", "image.version_created", "image.inspection_started",
      "image.inspection_completed", "image.version_accepted", "image.version_restored",
      "run.paused", "run.resumed",
    ];
    const receive = (raw: Event) => {
      const message = raw as MessageEvent<string>;
      try {
        const parsed = JSON.parse(message.data) as Omit<AgentPublicEvent, "id" | "event_type">;
        const next: AgentPublicEvent = {
          ...parsed,
          id: message.lastEventId,
          event_type: message.type,
        };
        lastEventIdRef.current = next.id;
        setEvents((current) => current.some((item) => item.id === next.id) ? current : [...current, next]);
        if (["artifact.created", "approval.resolved", "tool.completed", "tool.failed", "run.completed", "run.failed"].includes(next.event_type)) {
          void loadDetail(routeConversationId, true);
          void loadConversations();
        }
        if (
          next.event_type.startsWith("image.") ||
          next.event_type === "panel.revision_requested" ||
          next.event_type === "run.paused" ||
          next.event_type === "run.resumed"
        ) {
          const currentTaskId = routeTaskIdRef.current;
          if (currentTaskId) void loadInspector(routeConversationId, currentTaskId);
          void loadDetail(routeConversationId, true);
        }
      } catch {
        setEventConnectionError("活动流返回了无法读取的数据");
      }
    };
    eventTypes.forEach((type) => source.addEventListener(type, receive));
    source.onopen = () => setEventConnectionError("");
    source.onerror = () => {
      source.close();
      setEventConnectionError("活动流连接已断开，方案和任务不会重复执行。");
    };
    return () => {
      eventTypes.forEach((type) => source.removeEventListener(type, receive));
      source.close();
    };
  }, [routeConversationId, eventReconnectToken]);

  useEffect(() => {
    const previousTaskId = previousRouteTaskIdRef.current;
    previousRouteTaskIdRef.current = routeTaskId;
    if (!routeConversationId || !routeTaskId) {
      setInspector(null);
      setInspectorError("");
      setSelectedInspectorPanelId("");
      if (previousTaskId && inspectorTriggerRef.current) {
        window.setTimeout(() => inspectorTriggerRef.current?.focus(), 0);
      }
      return;
    }
    setInspector(null);
    void loadInspector(routeConversationId, routeTaskId);
  }, [routeConversationId, routeTaskId]);

  const hasActiveWork = Boolean(
    detail?.runs.some((run) => activeAgentRunStatuses.has(run.status)) ||
      detail?.task_cards.some((card) => ["queued", "running", "retrying"].includes(card.status)),
  );

  useEffect(() => {
    if (detail?.runs[0]?.status === "succeeded" || detail?.runs[0]?.status === "failed") {
      void onCreditsChanged();
    }
  }, [detail?.runs[0]?.status]);

  function startNewConversation() {
    window.sessionStorage.removeItem(lastAgentConversationKey);
    if (routeConversationId) onNavigatePath(viewRoutes.agent);
    window.setTimeout(() => ideaInputRef.current?.focus(), 0);
  }

  function openTaskInspector(taskId: string, trigger: HTMLButtonElement) {
    if (!routeConversationId) return;
    inspectorTriggerRef.current = trigger;
    onNavigatePath(
      `${viewRoutes.agent}/${encodeURIComponent(routeConversationId)}/tasks/${encodeURIComponent(taskId)}`,
    );
  }

  function closeTaskInspector() {
    if (!routeConversationId) return;
    onNavigatePath(`${viewRoutes.agent}/${encodeURIComponent(routeConversationId)}`, {
      replace: true,
    });
  }

  async function regenerateInspectorPanel(
    panel: AgentTaskInspector["panels"][number],
    instruction: string,
    allowAutoRevision: boolean,
  ) {
    if (!routeConversationId || !routeTaskId || !panel.current_image) return false;
    setInspectorError("");
    try {
      await api.regenerateAgentPanel(
        routeConversationId,
        routeTaskId,
        panel.id,
        {
          instruction,
          source_image_version_id: panel.current_image.id,
          expected_credit_cost: 1,
          allow_auto_revision: allowAutoRevision,
        },
      );
      await Promise.all([
        loadInspector(routeConversationId, routeTaskId),
        loadDetail(routeConversationId, true),
      ]);
      return true;
    } catch (actionError) {
      setInspectorError(
        actionError instanceof Error ? actionError.message : "创建 Panel 新版本失败",
      );
      return false;
    }
  }

  async function acceptInspectorVersion(
    panel: AgentTaskInspector["panels"][number],
    image: AgentTaskInspector["panels"][number]["versions"][number],
  ) {
    if (!routeConversationId || !routeTaskId) return;
    setInspectorError("");
    try {
      await api.acceptAgentImageVersion(
        routeConversationId,
        routeTaskId,
        panel.id,
        image.id,
      );
      await loadInspector(routeConversationId, routeTaskId);
    } catch (actionError) {
      setInspectorError(actionError instanceof Error ? actionError.message : "接受版本失败");
    }
  }

  async function restoreInspectorVersion(
    panel: AgentTaskInspector["panels"][number],
    image: AgentTaskInspector["panels"][number]["versions"][number],
  ) {
    if (!routeConversationId || !routeTaskId) return;
    setInspectorError("");
    try {
      await api.restoreAgentImageVersion(
        routeConversationId,
        routeTaskId,
        panel.id,
        image.id,
      );
      await loadInspector(routeConversationId, routeTaskId);
    } catch (actionError) {
      setInspectorError(actionError instanceof Error ? actionError.message : "恢复版本失败");
    }
  }

  async function pauseInspectorRun(runId: string) {
    setInspectorError("");
    try {
      await api.pauseAgentRun(runId);
      if (routeConversationId) await loadDetail(routeConversationId, true);
    } catch (actionError) {
      setInspectorError(actionError instanceof Error ? actionError.message : "暂停失败");
    }
  }

  async function resumeInspectorRun(runId: string) {
    setInspectorError("");
    try {
      await api.resumeAgentRun(runId);
      if (routeConversationId) await loadDetail(routeConversationId, true);
    } catch (actionError) {
      setInspectorError(actionError instanceof Error ? actionError.message : "继续失败");
    }
  }

  async function sendMessage(event: React.FormEvent) {
    event.preventDefault();
    if (!idea.trim() || hasActiveWork) return;
    setSending(true);
    setCreatingConversation(!routeConversationId);
    setError("");
    try {
      const conversationId = routeConversationId || (await api.createAgentConversation({ title: "新漫画创作" })).id;
      await api.sendAgentMessage(conversationId, {
        content: idea,
        resource_refs: selectedResources,
      });
      setIdea("");
      const draftId = routeConversationId || newAgentDraftId;
      window.sessionStorage.removeItem(agentDraftKey(draftId, "idea"));
      if (!routeConversationId) {
        if (selectedResources.length > 0) {
          window.sessionStorage.setItem(
            agentDraftKey(conversationId, "resources"),
            JSON.stringify(selectedResources),
          );
        }
        window.sessionStorage.removeItem(agentDraftKey(newAgentDraftId, "resources"));
        onNavigatePath(`${viewRoutes.agent}/${encodeURIComponent(conversationId)}`);
      } else {
        await loadDetail(conversationId, true);
      }
      await loadConversations();
    } catch (sendError) {
      setError(sendError instanceof Error ? sendError.message : "消息发送失败");
    } finally {
      setSending(false);
      setCreatingConversation(false);
    }
  }

  async function decideApproval(
    artifact: AgentArtifact,
    decision: "approve" | "request_changes",
  ) {
    if (!artifact.approval) return;
    const feedback = approvalFeedback[artifact.id]?.trim();
    if (decision === "request_changes" && !feedback) {
      setError("请先填写希望修改的内容");
      return;
    }
    setDecidingApprovalId(artifact.approval.id);
    setError("");
    try {
      await api.decideAgentApproval(artifact.approval.id, {
        decision,
        ...(feedback ? { feedback } : {}),
      });
      if (routeConversationId) await loadDetail(routeConversationId, true);
    } catch (decisionError) {
      setError(decisionError instanceof Error ? decisionError.message : "方案确认失败");
    } finally {
      setDecidingApprovalId("");
    }
  }

  function addResource(option: AgentResourceOption) {
    const existing = selectedResources.find(
      (ref) => ref.kind === option.kind && ref.id === option.id,
    );
    if (existing) return;
    let next = [...selectedResources];
    if (option.kind === "skill") {
      if (next.some((ref) => ref.kind === "skill")) {
        setResourceError("每次运行只能使用一个 Skill，已替换原 Skill");
      }
      next = next.filter((ref) => ref.kind !== "skill");
    } else if (option.kind === "style") {
      next = next.filter((ref) => ref.kind !== "style");
    } else if (option.kind === "character") {
      const characterCount = next.filter((ref) => ref.kind === "character").length;
      if (characterCount >= 3) {
        setResourceError("新任务最多引用 3 个角色");
        return;
      }
    } else if (option.kind === "task") {
      const currentTask = next.find((ref) => ref.kind === "task");
      if (currentTask && currentTask.id !== option.id) {
        setResourceError("每条消息只能引用一个任务，请先移除当前任务");
        return;
      }
    } else if (option.kind === "panel") {
      if (!selectedTaskRef || option.parent_id !== selectedTaskRef.id) {
        setResourceError("Panel 必须属于当前选中的任务");
        return;
      }
      next = next.filter(
        (ref) => ref.kind !== "panel" && ref.kind !== "image_version",
      );
    } else if (option.kind === "image_version") {
      if (!selectedPanelRef || option.parent_id !== selectedPanelRef.id) {
        setResourceError("图片版本必须属于当前选中的 Panel");
        return;
      }
      next = next.filter((ref) => ref.kind !== "image_version");
    }
    next.push({
      kind: option.kind,
      id: option.id,
      display_name: option.display_name,
    });
    persistSelectedResources(next);
    setResourceError("");
    if (option.kind !== "task") {
      window.setTimeout(() => ideaInputRef.current?.focus(), 0);
    }
  }

  function removeSelectedResource(ref: AgentResourceRef) {
    let next = selectedResources.filter(
      (item) => !(item.kind === ref.kind && item.id === ref.id),
    );
    if (ref.kind === "task") {
      next = next.filter(
        (item) => item.kind !== "panel" && item.kind !== "image_version",
      );
    } else if (ref.kind === "panel") {
      next = next.filter((item) => item.kind !== "image_version");
    }
    persistSelectedResources(next);
  }

  function referenceTask(task: { task_id: string; title: string }) {
    const next = selectedResources.filter(
      (ref) => !["task", "panel", "image_version"].includes(ref.kind),
    );
    next.push({
      kind: "task",
      id: task.task_id,
      display_name: task.title,
    });
    persistSelectedResources(next);
    closeTaskInspector();
    window.setTimeout(() => ideaInputRef.current?.focus(), 0);
  }

  function referencePanel(
    task: { task_id: string; title: string },
    panel: { id: string; panel_order: number },
  ) {
    const next = selectedResources.filter(
      (ref) => !["task", "panel", "image_version"].includes(ref.kind),
    );
    next.push(
      { kind: "task", id: task.task_id, display_name: task.title },
      { kind: "panel", id: panel.id, display_name: `Panel ${panel.panel_order}` },
    );
    persistSelectedResources(next);
    closeTaskInspector();
    window.setTimeout(() => ideaInputRef.current?.focus(), 0);
  }

  function referenceImage(
    task: { task_id: string; title: string },
    panel: { id: string; panel_order: number },
    image: { id: string; generation_number: number },
  ) {
    const next = selectedResources.filter(
      (ref) => !["task", "panel", "image_version"].includes(ref.kind),
    );
    next.push(
      { kind: "task", id: task.task_id, display_name: task.title },
      { kind: "panel", id: panel.id, display_name: `Panel ${panel.panel_order}` },
      {
        kind: "image_version",
        id: image.id,
        display_name: `Panel ${panel.panel_order} · v${image.generation_number}`,
      },
    );
    persistSelectedResources(next);
    closeTaskInspector();
    window.setTimeout(() => ideaInputRef.current?.focus(), 0);
  }

  function fillStarter(value: string) {
    setIdea(value);
    window.sessionStorage.setItem(agentDraftKey(routeConversationId || newAgentDraftId, "idea"), value);
    window.setTimeout(() => ideaInputRef.current?.focus(), 0);
  }

  const filteredConversations = conversations.filter((conversation) => {
    const query = search.trim().toLowerCase();
    const summary = conversationMetadata[conversation.id]?.summary || agentConversationSummary(conversation, detail);
    return !query || `${conversation.title} ${summary}`.toLowerCase().includes(query);
  });
  const conversationGroups = [...new Set(filteredConversations.map((conversation) => agentConversationGroupLabel(conversation.last_message_at)))];
  const selectedStyleName =
    selectedStyleRef?.display_name ||
    styleResources.find((style) => style.id === selectedStyleRef?.id)?.display_name ||
    null;
  const visibleMessages = detail?.messages.filter((message) => message.role !== "task_card") || [];
  const latestRun = detail?.runs[0] || null;

  return (
    <section className="agent-creation-page">
      <section className="agent-workspace">
      <aside className="agent-conversation-list">
        <div className="agent-module-brand">
          <span className="brand-mark">
            <img className="brand-icon" src="/doodlestory-icon.svg" alt="" />
          </span>
          <div>
            <strong>DoodleStory</strong>
            <span>Agent 创作空间</span>
          </div>
        </div>
        <div className="agent-list-heading">
          <div><span className="agent-eyebrow">Conversation</span><h1>创作对话</h1></div>
          <button type="button" aria-label="新建对话" onClick={startNewConversation}>
            <Plus size={18} />
          </button>
        </div>
        <button className="agent-new-chat" type="button" onClick={startNewConversation}>
          <Plus size={16} />
          新对话
        </button>
        <label className="search-box agent-search">
          <Search size={16} />
          <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索对话" />
        </label>
        <nav className="agent-conversation-scroll" aria-label="历史对话">
          {loadingList ? <div className="agent-list-state">加载会话中…</div> : null}
          {!loadingList && filteredConversations.length === 0 ? (
            <div className="agent-list-state">没有匹配的历史对话。</div>
          ) : null}
          {conversationGroups.map((group) => (
            <div className="agent-conversation-group" key={group}>
              <span className="agent-conversation-group-label">{group}</span>
              {filteredConversations.filter((conversation) => agentConversationGroupLabel(conversation.last_message_at) === group).map((conversation) => {
                const isActive = routeConversationId === conversation.id;
                const runStatus = conversationMetadata[conversation.id]?.runStatus || (isActive ? latestRun?.status : null);
                const summary = conversationMetadata[conversation.id]?.summary || agentConversationSummary(conversation, detail);
                const status = runStatus ? agentRunStatusLabel(runStatus) : conversation.status === "archived" ? "已归档" : "可继续";
                return (
                  <button
                    type="button"
                    key={conversation.id}
                    className={isActive ? "active" : ""}
                    aria-current={isActive ? "page" : undefined}
                    onClick={() => onNavigatePath(`${viewRoutes.agent}/${encodeURIComponent(conversation.id)}`)}
                  >
                    <span className="agent-conversation-item-head">
                      <i className={runStatus && activeAgentRunStatuses.has(runStatus) ? "running" : conversation.status} />
                      <strong>{conversation.title}</strong>
                      <time>{agentConversationTime(conversation.last_message_at)}</time>
                    </span>
                    <span className="agent-conversation-summary">{summary}</span>
                    <small>{status}</small>
                  </button>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="agent-account-panel">
          <div className="agent-account-credit">
            <Coins size={16} />
            <span>
              <strong>
                {creditOverview
                  ? `${creditOverview.account.balance} 积分`
                  : creditError
                    ? "积分不可用"
                    : "积分加载中"}
              </strong>
              <small>
                {creditOverview?.account.reserved_balance
                  ? `占用 ${creditOverview.account.reserved_balance}`
                  : creditError || "成功出图扣 1 分"}
              </small>
            </span>
          </div>
          <div className="agent-account-user">
            <UserRound size={16} />
            <span>
              <strong>{user.display_name || user.email}</strong>
              <small>{user.role === "admin" ? "管理员" : "普通用户"}</small>
            </span>
          </div>
          <a
            href={viewRoutes.tasks}
            onClick={(event) => {
              event.preventDefault();
              onNavigatePath(viewRoutes.tasks);
            }}
          >
            <Images size={15} />
            返回传统工作台
          </a>
          <button type="button" onClick={() => void onLogout()}>
            <LogOut size={15} />
            退出登录
          </button>
        </div>
      </aside>

      <div className="agent-chat">
        <header className="agent-chat-header">
          <div>
            <h2>{detail?.title || "新对话"}</h2>
            <p>{detail ? "真实会话 · 方案确认后生成" : "从一个想法开始，资源可以稍后添加"}</p>
          </div>
          {latestRun ? (
            <span className={`agent-run-state ${latestRun.status}`}>
              {activeAgentRunStatuses.has(latestRun.status) ? <Loader2 className="spin" size={14} /> : null}
              {agentRunStatusLabel(latestRun.status)}
            </span>
          ) : null}
        </header>

        <div className="agent-message-scroll" aria-live="polite">
          {loadingDetail && !detail ? (
            <div className="agent-loading-state"><Loader2 className="spin" />加载对话中…</div>
          ) : visibleMessages.length === 0 ? (
            <div className="agent-welcome">
              <span className="agent-welcome-mark">画</span>
              <h2>今天想创作什么？</h2>
              <p>从一个 idea、一段故事，或者一个想重新设计的情节开始。</p>
              <div className="agent-starters">
                <button type="button" onClick={() => fillStarter("我有一个很简单的 idea，帮我把它发展成连续漫画。")}>从一个 idea 开始 <span>→</span></button>
                <button type="button" onClick={() => fillStarter("我有一段完整故事，帮我设计成连续漫画。")}>把故事做成漫画 <span>→</span></button>
                <button type="button" onClick={() => fillStarter("我想重新设计一个故事的人物关系和结局。")}>重新设计人物和结局 <span>→</span></button>
              </div>
              {styleResources.length > 0 ? (
                <div className="agent-common-resources">
                  <div><span>常用风格</span><button type="button" onClick={() => setResourceMenuOpen(true)}>查看全部</button></div>
                  <div className="agent-resource-shortcuts">
                    {styleResources.slice(0, 3).map((style) => (
                      <button type="button" key={style.id} onClick={() => addResource(style)}>
                        <span className="agent-resource-swatch" />
                        <span><strong>{style.display_name}</strong><small>风格</small></span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="agent-thread-inner">
              {visibleMessages.map((message) => (
                <div key={message.id} className={`agent-message ${message.role}`}>
                  <span>{message.role === "user" ? "你" : message.role === "assistant" ? "DoodleStory Agent" : "系统"}</span>
                  <p>{message.content}</p>
                  {message.resource_refs.map((ref) => (
                    <small key={`${ref.kind}-${ref.id}`}>
                      @{agentResourceKindLabels[ref.kind]} · {ref.display_name || ref.id}
                    </small>
                  ))}
                </div>
              ))}
              {artifacts.map((artifact) => {
                const plan = artifact.content;
                const pending = artifact.approval?.status === "pending";
                const styleName = styleResources.find((style) => style.id === plan.style_ref_id)?.display_name || "已选风格";
                return (
                  <article className={`agent-plan-card ${artifact.status}`} key={artifact.id}>
                    <header>
                      <div>
                        <span className="agent-eyebrow">漫画方案 · v{artifact.version}</span>
                        <h3>{plan.title}</h3>
                      </div>
                      <span>{artifact.status === "awaiting_approval" ? "等待确认" : artifact.status === "approved" ? "已批准" : artifact.status === "superseded" ? "已被新版本替代" : artifact.status === "rejected" ? "修改中" : "草稿"}</span>
                    </header>
                    <p className="agent-plan-summary">{plan.story_summary}</p>
                    <div className="agent-plan-meta">
                      <span>{styleName}</span>
                      <span>{plan.aspect_ratio}</span>
                      <span>{plan.panels.length} 张图片</span>
                      <span>{plan.estimated_image_credits} 积分</span>
                    </div>
                    <ol>
                      {plan.panels.map((panel) => (
                        <li key={panel.panel_key}>
                          <strong>{panel.panel_key.replace("panel-", "Panel ")}</strong>
                          <span>{panel.story_beat}</span>
                          <small>{panel.visual_goal}</small>
                          {panel.required_text.length ? <em>图片文字：{panel.required_text.join(" / ")}</em> : null}
                        </li>
                      ))}
                    </ol>
                    {pending ? (
                      <div className="agent-plan-actions">
                        <button
                          type="button"
                          disabled={decidingApprovalId === artifact.approval?.id}
                          onClick={() => void decideApproval(artifact, "approve")}
                        >
                          {decidingApprovalId === artifact.approval?.id ? <Loader2 className="spin" size={14} /> : <CheckCircle2 size={14} />}
                          确认并生成 {plan.panels.length} 张图（{plan.estimated_image_credits} 积分）
                        </button>
                        <label>
                          <span>提出修改</span>
                          <textarea
                            value={approvalFeedback[artifact.id] || ""}
                            onChange={(event) => setApprovalFeedback((current) => ({ ...current, [artifact.id]: event.target.value }))}
                            placeholder="例如：结尾不要和解，改成主角独自开始新生活。"
                            rows={2}
                          />
                        </label>
                        <button
                          className="secondary"
                          type="button"
                          disabled={decidingApprovalId === artifact.approval?.id}
                          onClick={() => void decideApproval(artifact, "request_changes")}
                        >
                          提交修改意见
                        </button>
                      </div>
                    ) : null}
                  </article>
                );
              })}
              {events.length > 0 || eventConnectionError ? (
                <section className="agent-activity">
                  <header>
                    <strong>创作活动</strong>
                    <span>{eventConnectionError ? "连接中断" : "实时更新"}</span>
                  </header>
                  {events.slice(-12).map((event) => (
                    <div key={event.id}>
                      <i />
                      <span>{agentEventText(event)}</span>
                      <time>
                        {new Date(event.created_at).toLocaleTimeString("zh-CN", {
                          timeZone: chinaTimeZone,
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </time>
                    </div>
                  ))}
                  {eventConnectionError ? (
                    <p>
                      {eventConnectionError}
                      <button type="button" onClick={() => setEventReconnectToken((value) => value + 1)}>
                        手动重连
                      </button>
                    </p>
                  ) : null}
                </section>
              ) : null}
              {detail?.task_cards.map((card) => (
                <AgentTaskCardView
                  key={card.task_id}
                  card={card}
                  runStatus={
                    detail.runs.find((run) => run.id === card.run_id)?.status || null
                  }
                  onOpenTask={openTaskInspector}
                  onReferenceTask={referenceTask}
                />
              ))}
              {latestRun?.status === "failed" && !latestRun.task_id ? (
                <div className="agent-run-error"><AlertCircle size={18} />{latestRun.error_message || "本轮执行失败"}</div>
              ) : null}
            </div>
          )}
        </div>

        <footer className="agent-composer-shell">
          {selectedResources.length > 0 ? (
            <div className="agent-context-row">
              {selectedResources.map((ref) => (
                <span key={`${ref.kind}-${ref.id}`}>
                  @{agentResourceKindLabels[ref.kind]} · {ref.display_name || ref.id}
                  <button
                    type="button"
                    aria-label={`移除${agentResourceKindLabels[ref.kind]} ${ref.display_name || ref.id}`}
                    onClick={() => removeSelectedResource(ref)}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          ) : null}
          <form className="agent-composer" onSubmit={sendMessage}>
            <div className="agent-resource-menu-wrap">
              <button
                className="agent-composer-tool"
                type="button"
                aria-label="添加创作资源"
                aria-haspopup="menu"
                aria-expanded={resourceMenuOpen}
                onClick={() => setResourceMenuOpen((open) => !open)}
              >
                <Plus size={19} />
              </button>
              {resourceMenuOpen ? (
                <div className="agent-resource-menu" role="menu">
                  <div className="agent-resource-menu-head">
                    <strong>加入创作上下文</strong>
                    <small>风格、角色与已有任务均来自真实资源</small>
                  </div>
                  <label>
                    <Search size={15} />
                    <input
                      autoFocus
                      type="search"
                      value={resourceSearch}
                      onChange={(event) => setResourceSearch(event.target.value)}
                      placeholder="搜索 Skill、风格、角色或任务"
                    />
                  </label>
                  {resourceLoading ? (
                    <p className="agent-resource-state"><Loader2 className="spin" size={15} />正在搜索资源…</p>
                  ) : null}
                  {resourceError ? (
                    <p className="agent-resource-state is-error">{resourceError}</p>
                  ) : null}
                  <span className="agent-resource-group-label">Skill</span>
                  {skillResources.map((skill) => (
                    <button type="button" role="menuitem" key={skill.id} onClick={() => addResource(skill)}>
                      <Sparkles size={17} />
                      <span><strong>{skill.display_name}</strong><small>{skill.secondary_text || "已发布创作方法"}</small></span>
                    </button>
                  ))}
                  {skillResources.length === 0 && !resourceLoading ? <p>没有匹配的 Skill</p> : null}
                  <span className="agent-resource-group-label">风格</span>
                  {styleResources.map((style) => (
                    <button type="button" role="menuitem" key={style.id} onClick={() => addResource(style)}>
                      <span className="agent-resource-swatch" />
                      <span><strong>{style.display_name}</strong><small>{style.secondary_text || "可用于新漫画"}</small></span>
                    </button>
                  ))}
                  {styleResources.length === 0 && !resourceLoading ? <p>没有匹配的风格</p> : null}
                  <span className="agent-resource-group-label">我的角色</span>
                  {characterResources.map((character) => {
                    const selected = selectedResources.some((ref) => ref.kind === "character" && ref.id === character.id);
                    const characterLimitReached = selectedResources.filter((ref) => ref.kind === "character").length >= 3;
                    return (
                      <button
                        type="button"
                        role="menuitem"
                        key={character.id}
                        disabled={!selected && characterLimitReached}
                        title={!selected && characterLimitReached ? "每条新任务最多引用 3 个角色" : undefined}
                        onClick={() => addResource(character)}
                      >
                        <UserRound size={17} />
                        <span><strong>{character.display_name}</strong><small>{character.secondary_text || "固定角色参考"}</small></span>
                      </button>
                    );
                  })}
                  {characterResources.length === 0 && !resourceLoading ? <p>没有匹配的角色</p> : null}
                  <span className="agent-resource-group-label">我的任务</span>
                  {taskResources.map((task) => {
                    const disabled = Boolean(selectedTaskRef && selectedTaskRef.id !== task.id);
                    return (
                      <button
                        type="button"
                        role="menuitem"
                        key={task.id}
                        disabled={disabled}
                        title={disabled ? "每条消息只能引用一个任务" : undefined}
                        onClick={() => addResource(task)}
                      >
                        <Images size={17} />
                        <span><strong>{task.display_name}</strong><small>{task.status || task.secondary_text}</small></span>
                      </button>
                    );
                  })}
                  {taskResources.length === 0 && !resourceLoading ? <p>没有匹配的任务</p> : null}
                  {selectedTaskRef ? (
                    <>
                      <span className="agent-resource-group-label">所选任务的 Panel</span>
                      {panelResources.map((panel) => (
                        <button type="button" role="menuitem" key={panel.id} onClick={() => addResource(panel)}>
                          <FileText size={17} />
                          <span><strong>{panel.display_name}</strong><small>{panel.secondary_text}</small></span>
                        </button>
                      ))}
                      {panelResources.length === 0 && !resourceLoading ? <p>这个任务还没有 Panel</p> : null}
                    </>
                  ) : null}
                  {selectedPanelRef ? (
                    <>
                      <span className="agent-resource-group-label">所选 Panel 的图片版本</span>
                      {imageResources.map((image) => (
                        <button type="button" role="menuitem" key={image.id} onClick={() => addResource(image)}>
                          <Eye size={17} />
                          <span><strong>{image.display_name}</strong><small>{image.secondary_text || image.status}</small></span>
                        </button>
                      ))}
                      {imageResources.length === 0 && !resourceLoading ? <p>这个 Panel 还没有图片版本</p> : null}
                    </>
                  ) : null}
                </div>
              ) : null}
            </div>
            <textarea
              ref={ideaInputRef}
              aria-label="告诉 Agent 你想创作什么"
              value={idea}
              onChange={(event) => {
                const nextIdea = event.target.value;
                setIdea(nextIdea);
                window.sessionStorage.setItem(agentDraftKey(routeConversationId || newAgentDraftId, "idea"), nextIdea);
                if (nextIdea.endsWith("@")) setResourceMenuOpen(true);
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") setResourceMenuOpen(false);
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder="告诉 Agent 你想创作什么，或输入 @ 引用资源"
              rows={1}
              disabled={sending}
            />
            <button className="agent-send-button" type="submit" aria-label="发送消息" disabled={sending || hasActiveWork || !idea.trim()}>
              {sending || creatingConversation ? <Loader2 className="spin" size={18} /> : <ArrowUpRight size={18} />}
            </button>
          </form>
          <div className="agent-composer-note">
            <span>Enter 发送 · Shift + Enter 换行</span>
            <span>
              {hasActiveWork
                ? "Agent 正在执行当前任务，你可以继续准备下一条草稿"
                : selectedTaskRef
                  ? "已进入同一任务续作上下文；本阶段只读并提供修改建议"
                  : selectedStyleName
                    ? `将使用真实风格：${selectedStyleName}`
                    : selectedResources.length > 0
                      ? "未选择风格，将只讨论已引用资源，不会生成图片"
                      : "无资源时进行普通创作讨论，不会生成图片"}
            </span>
          </div>
          {error ? <p className="error agent-composer-error">{error}</p> : null}
        </footer>
      </div>
      </section>
      {routeConversationId && routeTaskId ? (
        <AgentTaskInspectorDialog
          inspector={inspector}
          loading={inspectorLoading}
          error={inspectorError}
          selectedPanelId={selectedInspectorPanelId}
          onSelectPanel={setSelectedInspectorPanelId}
          onReferenceTask={referenceTask}
          onReferencePanel={referencePanel}
          onReferenceImage={referenceImage}
          run={
            detail?.runs.find((run) => run.task_id === routeTaskId) || null
          }
          onRegenerate={regenerateInspectorPanel}
          onAcceptVersion={acceptInspectorVersion}
          onRestoreVersion={restoreInspectorVersion}
          onPauseRun={pauseInspectorRun}
          onResumeRun={resumeInspectorRun}
          onRetry={() => void loadInspector(routeConversationId, routeTaskId)}
          onClose={closeTaskInspector}
        />
      ) : null}
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
  if (mode === "knowledge_plan") return "知识方案";
  return "完整故事";
}

function isPlanningOnlyInputMode(mode: Task["story_input_mode"]) {
  return mode === "extracted_storyboard" || mode === "knowledge_plan";
}

function visibleTaskSteps(task: Task) {
  if (!isPlanningOnlyInputMode(task.story_input_mode)) return task.steps;
  return task.steps.filter((step) => !["segment_story", "generate_panel_prompts"].includes(step.step_name));
}

function currentStepLabel(task: Task) {
  if (
    isPlanningOnlyInputMode(task.story_input_mode) &&
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
    timeZone: chinaTimeZone,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function styleTestStatusLabel(status: StyleTest["status"]) {
  const labels: Record<StyleTest["status"], string> = {
    queued: "排队中",
    running: "生成中",
    succeeded: "已完成",
    failed: "失败",
    cancel_requested: "取消中",
    cancelled: "已取消",
    retrying: "重试中",
  };
  return labels[status] ?? status;
}

function isActiveStyleTestStatus(status: StyleTest["status"]) {
  return status === "queued" || status === "running" || status === "retrying";
}

function isActiveTask(task: Task | TaskSummary | null | undefined) {
  return Boolean(task && ["queued", "running", "retrying", "cancel_requested"].includes(task.status));
}

function canCancelTask(task: Task | null | undefined) {
  return Boolean(task && ["queued", "running", "retrying", "cancel_requested", "cancelled"].includes(task.status));
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
    if (storyInputMode === "knowledge_plan") {
      setFixedRoleFlowEnabled(false);
      setCharacterExtractionCompletedForText("");
    }
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
    const shouldUseFixedRoleFlow = fixedRoleFlowEnabled && storyInputMode !== "knowledge_plan";
    if (!shouldUseDouyinReplicate && shouldUseFixedRoleFlow && !fixedRoleExtractionReady) {
      await extractRolesForCreate();
      return;
    }
    try {
      setCreating(true);
      const lastPanelRealPhoto = formData.get("last_panel_real_photo") === "on";
      const storyCharacters: StoryCharacterBinding[] = shouldUseFixedRoleFlow
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
          remove_image_text: false,
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
        use_character_references: storyInputMode === "knowledge_plan" ? false : true,
        last_panel_real_photo: lastPanelRealPhoto,
        remove_image_text: false,
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
      setMessage(selectedTask.status === "cancelled" ? "已重新执行取消清理" : "已提交取消请求");
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

  const canCancel = canCancelTask(taskForDetail);
  const canDownload = Boolean(hasAllPanelImages(taskForDetail) && taskForDetail?.id !== downloadingTaskId);
  const isDownloadingSelectedTask = Boolean(taskForDetail?.id && taskForDetail.id === downloadingTaskId);
  const canRetry = taskForDetail?.status === "failed" || taskForDetail?.status === "partial_succeeded";

  return (
    <section className="page tasks-workspace">
      <CreationModeSwitch active="tasks" onNavigatePath={onNavigatePath} />
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
	                    <small>任务 ID · {task.id}</small>
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
                      {task.remove_image_text ? "无文字 · " : ""}
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
                    {taskForDetail?.status === "cancelled" ? "再次取消" : "取消生成"}
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

              {taskForDetail.remove_image_text ? (
                <section className="story-panel compact-info-panel">
                  <h2>无文字画面</h2>
                  <p>最终生图提示词最前面会加入最高指令，要求图片中不能包含任何文字。</p>
                </section>
              ) : null}

              <section className="story-panel">
                <h2>原始文本</h2>
                <p>{taskForDetail.original_text}</p>
              </section>

              {taskForDetail.story_input_mode !== "original" ? (
                <section className="story-panel adapted-story-panel">
                  <h2>
                    {taskForDetail.story_input_mode === "extracted_storyboard"
                      ? "提取分镜概要"
                      : taskForDetail.story_input_mode === "knowledge_plan"
                        ? "知识方案概要"
                        : "增强故事"}
                  </h2>
                  {taskForDetail.adapted_story_title ? <strong>{taskForDetail.adapted_story_title}</strong> : null}
                  {taskForDetail.adapted_story_hook ? <small>{taskForDetail.adapted_story_hook}</small> : null}
                  <p>
                    {taskForDetail.adapted_story_text ??
                      (taskForDetail.story_input_mode === "extracted_storyboard"
                        ? "等待内容提取分镜结构化"
                        : taskForDetail.story_input_mode === "knowledge_plan"
                          ? "等待知识方案拆页"
                          : "等待 LLM 故事增强")}
                  </p>
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
                  className={storyInputMode === "knowledge_plan" ? "mode-choice active" : "mode-choice"}
                  aria-pressed={storyInputMode === "knowledge_plan"}
                  onClick={() => setStoryInputMode("knowledge_plan")}
                >
                  <strong>知识方案</strong>
                  <span>适合知识卡片、图鉴、清单和方法论，系统会按知识结构自动拆成连续内容页。</span>
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
                    : storyInputMode === "knowledge_plan"
                      ? "知识图文方案"
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
                        : storyInputMode === "knowledge_plan"
                          ? "输入完整知识图文方案，例如主题、版式、每条内容、正文/副文字、插图要求、作者栏和禁止事项；系统会按知识条目自动拆页"
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
                ) : storyInputMode === "knowledge_plan" ? (
                  <small>系统会按知识条目、空行块和收尾金句拆成内容页；如果要全部内容放在一张图里，请明确写“单页”。</small>
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
                    {storyInputMode === "knowledge_plan" ? <small>系统会按你设置的数量把知识方案拆成对应页数。</small> : null}
                    {storyInputMode === "dy_replicate" ? <small>固定数量必须和提取出的页数一致；内容提取完成后不会自动合并或补页。</small> : null}
                  </label>
                ) : (
                  <p className="field-hint">
                    {storyInputMode === "knowledge_plan" ? "系统会根据知识条目、章节、空行块和收尾金句自动判断图片张数。" : "系统会根据故事长度和内容密度决定图片张数。"}
                  </p>
                )}
              </section>
              <section className="create-section">
                <label className="character-reference-toggle">
                  <input name="last_panel_real_photo" type="checkbox" />
                  <span>
                    <strong>最后一张真人图片</strong>
                    <small>默认关闭；勾选后最后一张按真实摄影/真人自拍质感生成，不跟随当前漫画风格。</small>
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
              {storyInputMode !== "dy_replicate" && storyInputMode !== "knowledge_plan" && fixedRoleFlowEnabled ? (
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
                {storyInputMode !== "dy_replicate" && storyInputMode !== "knowledge_plan" ? (
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
                    ) : fixedRoleFlowEnabled &&
                      !fixedRoleExtractionReady &&
                      storyInputMode !== "dy_replicate" &&
                      storyInputMode !== "knowledge_plan" ? (
                      <Search size={17} />
                    ) : (
                      <Plus size={17} />
                    )}
                    {storyInputMode === "dy_replicate"
                      ? "开始复刻"
                      : fixedRoleFlowEnabled && !fixedRoleExtractionReady && storyInputMode !== "knowledge_plan"
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
  const [editTarget, setEditTarget] = useState<AudioReference | null>(null);
  const [updating, setUpdating] = useState(false);
  const [testTarget, setTestTarget] = useState<AudioReference | null>(null);
  const [testText, setTestText] = useState("");
  const [testing, setTesting] = useState(false);
  const [testAudioUrl, setTestAudioUrl] = useState<string | null>(null);

  useEffect(() => () => {
    if (testAudioUrl) URL.revokeObjectURL(testAudioUrl);
  }, [testAudioUrl]);

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
    const speechSpeed = Number(form.get("speech_speed") || "1");
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
        speech_speed: speechSpeed,
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

  function openEditAudioReference(item: AudioReference) {
    setEditTarget(item);
    setMessage("");
  }

  function closeEditAudioReference() {
    setEditTarget(null);
    setUpdating(false);
  }

  async function updateAudioReference(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editTarget) return;
    const form = new FormData(event.currentTarget);
    try {
      setUpdating(true);
      await api.updateAudioReference(editTarget.id, {
        name: String(form.get("name") || "").trim(),
        description: String(form.get("description") || "").trim(),
        speech_speed: Number(form.get("speech_speed") || "1"),
      });
      closeEditAudioReference();
      setMessage("音频参考已更新");
      await refresh(cursor);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "音频参考更新失败");
    } finally {
      setUpdating(false);
    }
  }

  function openTestAudioReference(item: AudioReference) {
    if (testAudioUrl) URL.revokeObjectURL(testAudioUrl);
    setTestAudioUrl(null);
    setTestTarget(item);
    setTestText("");
    setMessage("");
  }

  function closeTestAudioReference() {
    if (testAudioUrl) URL.revokeObjectURL(testAudioUrl);
    setTestAudioUrl(null);
    setTestTarget(null);
    setTestText("");
    setTesting(false);
  }

  async function testAudioReference(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!testTarget) return;
    if (testAudioUrl) URL.revokeObjectURL(testAudioUrl);
    setTestAudioUrl(null);
    try {
      setTesting(true);
      const blob = await api.testAudioReference(testTarget.id, { text: testText.trim() });
      setTestAudioUrl(URL.createObjectURL(blob));
      setMessage("测试音频已生成");
      await refresh(cursor);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "测试音频生成失败");
    } finally {
      setTesting(false);
    }
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
                <div className="audio-reference-title-line">
                  <strong>{item.name}</strong>
                  <span>{item.speech_speed.toFixed(2)}x</span>
                  <a href={assetUrl(item.asset)} target="_blank" rel="noreferrer">原音</a>
                </div>
                <p>{item.description || item.asset.original_filename || "未填写描述"}</p>
              </div>
            </div>
            <span>{user.role === "admin" ? item.owner_display_name || item.owner_email || shortId(item.owner_user_id) : "我的音频"}</span>
            <span>{formatDateTime(item.created_at)}</span>
            <span className="row-actions">
              <button type="button" className="ghost-button" onClick={() => openTestAudioReference(item)}>
                <Play size={15} />
                测试
              </button>
              <button type="button" className="ghost-button" onClick={() => openEditAudioReference(item)}>
                <Pencil size={15} />
                编辑
              </button>
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
                产出语速
                <input name="speech_speed" type="number" min="0.5" max="2" step="0.05" defaultValue="1" required />
              </label>
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

      {editTarget ? (
        <div className="task-create-backdrop" onClick={closeEditAudioReference}>
          <section className="task-create-modal compact-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="drawer-head">
              <div>
                <h2>编辑音频参考</h2>
                <p>参考音频文件不可替换。</p>
              </div>
              <button type="button" className="icon-button" aria-label="关闭" onClick={closeEditAudioReference}>
                <X size={18} />
              </button>
            </div>
            <form className="task-create-form" onSubmit={updateAudioReference}>
              <label>名称<input name="name" required maxLength={120} defaultValue={editTarget.name} /></label>
              <label>描述<textarea name="description" maxLength={500} defaultValue={editTarget.description || ""} /></label>
              <label>
                产出语速
                <input name="speech_speed" type="number" min="0.5" max="2" step="0.05" defaultValue={editTarget.speech_speed} required />
              </label>
              <div className="readonly-asset-line">
                <Volume2 size={16} />
                <span>{editTarget.asset.original_filename || "已上传参考音频"}</span>
              </div>
              <div className="drawer-actions">
                <button type="button" className="ghost-button" onClick={closeEditAudioReference}>取消</button>
                <button type="submit" disabled={updating}>
                  {updating ? <Loader2 size={17} className="spin" /> : <Save size={17} />}
                  保存修改
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}

      {testTarget ? (
        <div className="task-create-backdrop" onClick={closeTestAudioReference}>
          <section className="task-create-modal compact-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="drawer-head">
              <div>
                <h2>测试参考音频</h2>
                <p>{testTarget.name} · {testTarget.speech_speed.toFixed(2)}x</p>
              </div>
              <button type="button" className="icon-button" aria-label="关闭" onClick={closeTestAudioReference}>
                <X size={18} />
              </button>
            </div>
            <form className="task-create-form" onSubmit={testAudioReference}>
              <label>
                测试文本
                <textarea value={testText} onChange={(event) => setTestText(event.target.value)} maxLength={2000} required rows={5} />
              </label>
              {testAudioUrl ? (
                <div className="test-audio-preview">
                  <span>参考音频输出</span>
                  <audio src={testAudioUrl} controls autoPlay />
                </div>
              ) : null}
              <div className="drawer-actions">
                <button type="button" className="ghost-button" onClick={closeTestAudioReference}>关闭</button>
                <button type="submit" disabled={testing || !testText.trim()}>
                  {testing ? <Loader2 size={17} className="spin" /> : <Play size={17} />}
                  生成试听
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
  const [retryingVideoTaskId, setRetryingVideoTaskId] = useState<string | null>(null);
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

  async function retrySelectedVideoTask() {
    if (!selected) return;
    try {
      setRetryingVideoTaskId(selected.id);
      const task = await api.retryVideoTask(selected.id);
      setSelected(task);
      setMessage("视频任务已重新进入生成队列");
      await refresh(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "视频任务重试失败");
    } finally {
      setRetryingVideoTaskId(null);
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
                <div className="detail-actions">
                  <button type="button" className="secondary-button" disabled={selected.status !== "failed" || retryingVideoTaskId === selected.id} onClick={retrySelectedVideoTask}>
                    {retryingVideoTaskId === selected.id ? <Loader2 size={16} className="spin" /> : <RefreshCw size={16} />}
                    {retryingVideoTaskId === selected.id ? "重试中" : "重试视频"}
                  </button>
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
  const [extractingStylePrompt, setExtractingStylePrompt] = useState(false);
  const [stylePromptDraft, setStylePromptDraft] = useState("");
  const [stylePage, setStylePage] = useState<"library" | "test">("library");
  const [testingStyleId, setTestingStyleId] = useState("");
  const [styleTests, setStyleTests] = useState<StyleTest[]>([]);
  const [loadingStyleTests, setLoadingStyleTests] = useState(false);
  const [styleTestRunning, setStyleTestRunning] = useState(false);
  const activeCount = useMemo(() => styles.filter((style) => style.status === "active").length, [styles]);
  const editingStyle = useMemo(() => styles.find((style) => style.id === editingStyleId) ?? null, [editingStyleId, styles]);
  const testingStyle = useMemo(
    () => styles.find((style) => style.id === testingStyleId) ?? styles[0] ?? null,
    [testingStyleId, styles],
  );
  const styleBusy = savingStyle || uploadingStyleReferences || extractingStylePrompt;

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (stylePage !== "test" || !testingStyleId) return;
    void refreshStyleTests(testingStyleId);
  }, [stylePage, testingStyleId]);

  useEffect(() => {
    if (stylePage !== "test" || !testingStyleId) return;
    const hasActiveStyleTest = styleTests.some((test) => isActiveStyleTestStatus(test.status));
    if (!hasActiveStyleTest) return;
    const timer = window.setInterval(() => {
      void refreshStyleTests(testingStyleId, { silent: true });
    }, 3000);
    return () => window.clearInterval(timer);
  }, [stylePage, testingStyleId, styleTests]);

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
    setStylePromptDraft("");
    setMessage("");
    setStyleDrawerOpen(true);
  }

  function startEdit(style: Style) {
    if (styleBusy) return;
    setEditingStyleId(style.id);
    setStyleFormMode("edit");
    setPendingReferenceFiles([]);
    setStylePromptDraft(style.style_prompt);
    setMessage("");
    setStyleDrawerOpen(true);
  }

  function closeStyleDrawer() {
    if (styleBusy) {
      setMessage(styleSavePhase || styleUploadPhase || "正在保存、上传或提取风格提示词，请等待完成");
      return;
    }
    setStyleDrawerOpen(false);
  }

  function openStyleTest(style: Style) {
    if (style.id !== testingStyleId) {
      setStyleTests([]);
    }
    setTestingStyleId(style.id);
    setStyleTestRunning(false);
    setMessage("");
    setStylePage("test");
  }

  async function refreshStyleTests(styleId = testingStyleId, options?: { silent?: boolean }) {
    if (!styleId) return;
    try {
      if (!options?.silent) setLoadingStyleTests(true);
      const result = await api.styleTests(styleId, { limit: 30 });
      setStyleTests((previous) => {
        const previousStatusById = new Map(previous.map((test) => [test.id, test.status]));
        const hasFinishedActiveTest = result.items.some((test) => {
          const previousStatus = previousStatusById.get(test.id);
          return Boolean(previousStatus && isActiveStyleTestStatus(previousStatus) && !isActiveStyleTestStatus(test.status));
        });
        if (hasFinishedActiveTest) {
          void onCreditsChanged();
        }
        return result.items;
      });
    } catch (error) {
      if (!options?.silent) setMessage(error instanceof Error ? error.message : "风格测试历史加载失败");
    } finally {
      if (!options?.silent) setLoadingStyleTests(false);
    }
  }

  async function requestStylePromptExtraction(selectedReferenceFiles: File[]) {
    const isEditMode = styleFormMode === "edit" && Boolean(editingStyle);
    const referenceCount = isEditMode ? editingStyle?.reference_images.length ?? 0 : selectedReferenceFiles.length;
    if (referenceCount < 3) {
      throw new Error("请先提供至少 3 张风格参考图，再生成风格提示词");
    }
    return isEditMode && editingStyle
      ? api.extractStylePromptFromStyle(editingStyle.id)
      : api.extractStylePromptFromFiles(selectedReferenceFiles);
  }

  async function createStyle(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const selectedReferenceFiles = [...pendingReferenceFiles];
    const isEditMode = styleFormMode === "edit" && Boolean(editingStyle);

    try {
      setSavingStyle(true);
      let resolvedStylePrompt = stylePromptDraft.trim();
      if (!resolvedStylePrompt) {
        setStyleSavePhase("正在根据参考图生成风格提示词...");
        const extracted = await requestStylePromptExtraction(selectedReferenceFiles);
        resolvedStylePrompt = extracted.style_prompt.trim();
        setStylePromptDraft(resolvedStylePrompt);
      }
      const payload: Partial<Style> = {
        name: String(formData.get("name") ?? ""),
        status: String(formData.get("status") ?? "draft") as Style["status"],
        image_model_name: String(formData.get("image_model_name") ?? ""),
        aspect_ratio: String(formData.get("aspect_ratio") ?? "9:16"),
        style_reference_mode: String(formData.get("style_reference_mode") ?? "prompt") as Style["style_reference_mode"],
        style_prompt: resolvedStylePrompt,
        description: String(formData.get("description") ?? ""),
      };
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

  async function extractStylePrompt() {
    if (styleBusy) return;
    try {
      setExtractingStylePrompt(true);
      setMessage("正在使用 gpt-5.4 提取风格提示词...");
      const result = await requestStylePromptExtraction(pendingReferenceFiles);
      setStylePromptDraft(result.style_prompt);
      setMessage(`已从 ${result.reference_image_count} 张参考图提取风格提示词`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "风格提示词提取失败");
    } finally {
      setExtractingStylePrompt(false);
    }
  }

  async function runStyleTest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!testingStyle || styleTestRunning) return;
    const form = event.currentTarget;
    const formData = new FormData(event.currentTarget);
    setStyleTestRunning(true);
    setMessage("风格测试已提交，正在后台生成...");
    try {
      await api.createStyleTest(testingStyle.id, {
        test_text: String(formData.get("test_text") ?? ""),
      });
      form.reset();
      await refreshStyleTests(testingStyle.id, { silent: true });
      await onCreditsChanged();
      setMessage("风格测试已进入后台生成，可在历史列表查看进度");
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
                  {styleTestRunning ? "提交中..." : "提交测试"}
                </button>
              </form>
            </section>

            <section className="panel style-test-output">
              <div className="editor-title">
                <div>
                  <h2>测试历史</h2>
                  <p>当前风格下的测试会持续保留，可随时回来查看进度、结果图和失败原因。</p>
                </div>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => refreshStyleTests(testingStyle.id)}
                  disabled={loadingStyleTests}
                >
                  {loadingStyleTests ? <Loader2 size={16} className="spin" /> : <RefreshCw size={16} />}
                  刷新
                </button>
              </div>
              {loadingStyleTests && styleTests.length === 0 ? (
                <div className="empty mini">
                  <Loader2 size={20} className="spin" />
                  正在读取测试历史
                </div>
              ) : null}
              {!loadingStyleTests && styleTests.length === 0 ? <div className="empty mini">还没有测试记录</div> : null}
              {styleTests.length > 0 ? (
                <div className="style-test-history">
                  {styleTests.map((test) => (
                    <article key={test.id} className="style-test-history-item">
                      <div className="style-test-history-head">
                        <div>
                          <strong>{test.test_text}</strong>
                          <small>
                            {formatDateTime(test.created_at)}
                            {test.finished_at ? ` 完成于 ${formatDateTime(test.finished_at)}` : ""}
                          </small>
                        </div>
                        <span className={`status-pill ${test.status}`}>{styleTestStatusLabel(test.status)}</span>
                      </div>
                      {isActiveStyleTestStatus(test.status) ? (
                        <div className="empty mini">
                          <Loader2 size={20} className="spin" />
                          {test.status === "queued" ? "等待生成" : "正在生成测试图"}
                        </div>
                      ) : test.output_asset ? (
                        <LazyAssetImage
                          asset={test.output_asset}
                          assetId={test.output_asset.id}
                          alt="风格测试结果"
                          eager
                          variant="original"
                        />
                      ) : (
                        <div className="empty mini">{test.error_message || "没有生成结果"}</div>
                      )}
                    </article>
                  ))}
                </div>
              ) : null}
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
            <div className="form-field style-prompt-field">
              <div className="style-prompt-field-head">
                <span>风格提示词</span>
                <button type="button" className="secondary-button" onClick={extractStylePrompt} disabled={styleBusy}>
                  {extractingStylePrompt ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
                  {extractingStylePrompt ? "提取中" : "从参考图提取"}
                </button>
              </div>
              <textarea
                name="style_prompt"
                placeholder="风格提示词"
                value={stylePromptDraft}
                onChange={(event) => setStylePromptDraft(event.target.value)}
              />
              <small>可留空保存，系统会先从至少 3 张参考图生成；生成后仍可手动编辑。</small>
            </div>
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
