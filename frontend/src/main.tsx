import { StrictMode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { BookImage, Images, LogOut, Plus, Settings, Sparkles } from "lucide-react";
import { api, type Style, type Task, type User } from "./api/client";
import "./styles/app.css";

type View = "tasks" | "styles" | "settings";

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
      {view === "tasks" ? <TasksView /> : null}
      {view === "styles" ? <StylesView /> : null}
      {view === "settings" ? <SettingsView user={user} /> : null}
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
            <BookImage size={22} />
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
            <BookImage size={22} />
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

function TasksView() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.tasks().then((result) => setTasks(result.data)).catch((err) => setError(err.message));
  }, []);

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <h1>任务</h1>
          <p>用户原文会原样保存，后续由队列执行切分、提示词和 9:16 生图。</p>
        </div>
        <button disabled>
          <Plus size={18} />
          新建任务
        </button>
      </header>
      <div className="notice">图片生成 Provider 尚未接入，任务创建暂不开放。</div>
      {error ? <div className="error">{error}</div> : null}
      {tasks.length === 0 ? (
        <div className="empty">还没有任务。</div>
      ) : (
        tasks.map((task) => (
          <article className="row" key={task.id}>
            <strong>{task.display_title}</strong>
            <span>{task.status}</span>
          </article>
        ))
      )}
    </section>
  );
}

function StylesView() {
  const [styles, setStyles] = useState<Style[]>([]);
  const [message, setMessage] = useState("");
  const activeCount = useMemo(() => styles.filter((style) => style.status === "active").length, [styles]);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    const result = await api.styles();
    setStyles(result.data);
  }

  async function createStyle(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    try {
      await api.createStyle({
        name: String(formData.get("name") ?? ""),
        status: String(formData.get("status") ?? "draft") as Style["status"],
        generation_profile_key: String(formData.get("generation_profile_key") ?? ""),
        style_prompt: String(formData.get("style_prompt") ?? ""),
        description: String(formData.get("description") ?? ""),
      });
      event.currentTarget.reset();
      setMessage("风格已创建");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    }
  }

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <h1>风格</h1>
          <p>共 {styles.length} 个风格，{activeCount} 个启用。</p>
        </div>
      </header>
      <form className="panel form-grid" onSubmit={createStyle}>
        <input name="name" placeholder="风格名称" required />
        <select name="status" defaultValue="draft">
          <option value="draft">草稿</option>
          <option value="active">启用</option>
          <option value="disabled">停用</option>
        </select>
        <input name="generation_profile_key" placeholder="后台生成配置 Key" />
        <textarea name="description" placeholder="描述" />
        <textarea name="style_prompt" placeholder="风格提示词" required />
        {message ? <p>{message}</p> : null}
        <button type="submit">创建风格</button>
      </form>
      <div className="grid">
        {styles.map((style) => (
          <article className="card" key={style.id}>
            <span>{style.status}</span>
            <h2>{style.name}</h2>
            <p>{style.description || style.style_prompt}</p>
            <small>{style.generation_profile_key || "未配置生成配置 Key"}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function SettingsView({ user }: { user: User }) {
  return (
    <section className="page">
      <header className="page-header">
        <div>
          <h1>设置</h1>
          <p>当前为 React 前端 + FastAPI 后端架构。</p>
        </div>
      </header>
      <div className="panel">
        <p>邮箱：{user.email}</p>
        <p>角色：{user.role}</p>
        <p>API：{import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"}</p>
      </div>
    </section>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
