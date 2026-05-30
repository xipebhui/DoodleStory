import { StrictMode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BookImage,
  Download,
  Eye,
  Images,
  LogOut,
  Plus,
  RefreshCw,
  Save,
  Search,
  Settings,
  Sparkles,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { api, type Style, type StyleTest, type Task, type User } from "./api/client";
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
      {view === "styles" ? <StylesView user={user} /> : null}
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
  const [styles, setStyles] = useState<Style[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [countMode, setCountMode] = useState<"auto" | "fixed">("auto");
  const [selectedId, setSelectedId] = useState("");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [previewAssetId, setPreviewAssetId] = useState<string | null>(null);

  const previewImage = useMemo(
    () => selectedTask?.generated_images.find((image) => image.asset?.id === previewAssetId) ?? null,
    [previewAssetId, selectedTask],
  );
  const selectedTaskFromList = useMemo(
    () => tasks.find((task) => task.id === selectedId) ?? tasks[0] ?? null,
    [selectedId, tasks],
  );

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    try {
      const [taskResult, styleResult] = await Promise.all([api.tasks(), api.styles({ status: "active" })]);
      setTasks(taskResult.items);
      setStyles(styleResult.items);
      const nextSelectedId = selectedId || taskResult.items[0]?.id || "";
      if (nextSelectedId) {
        setSelectedId(nextSelectedId);
        setSelectedTask(await api.task(nextSelectedId));
      } else {
        setSelectedTask(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    }
  }

  async function selectTask(taskId: string) {
    setSelectedId(taskId);
    setSelectedTask(await api.task(taskId));
    setPreviewAssetId(null);
  }

  async function createTask(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const requested = Number(formData.get("requested_image_count"));
    try {
      await api.createTask({
        original_text: String(formData.get("original_text") ?? ""),
        image_count_mode: countMode,
        requested_image_count: countMode === "fixed" ? requested : null,
        style_id: String(formData.get("style_id") ?? ""),
      });
      event.currentTarget.reset();
      setCountMode("auto");
      setMessage("任务已进入队列");
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "创建失败");
    }
  }

  async function cancelSelectedTask() {
    if (!selectedTask) return;
    try {
      const result = await api.cancelTask(selectedTask.id);
      setSelectedTask(result);
      setMessage("已提交取消请求");
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "取消失败");
    }
  }

  async function downloadSelectedTask() {
    if (!selectedTask) return;
    try {
      const result = await api.createTaskDownload(selectedTask.id);
      if (result.status === "ready" && result.asset) {
        window.location.href = api.assetContentUrl(result.asset.id);
      } else {
        setMessage(result.error_message ?? "下载包未就绪");
      }
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "打包下载失败");
    }
  }

  const taskForDetail = selectedTask ?? selectedTaskFromList;
  const imagesByPanelId = useMemo(() => {
    const map = new Map<string, Task["generated_images"][number]>();
    taskForDetail?.generated_images.forEach((image) => map.set(image.panel_id, image));
    return map;
  }, [taskForDetail]);
  const canCancel =
    taskForDetail?.status === "queued" || taskForDetail?.status === "running" || taskForDetail?.status === "retrying";
  const canDownload = Boolean(
    taskForDetail?.generated_images.some((image) => image.status === "succeeded" && image.asset),
  );

  return (
    <section className="page tasks-workspace">
      <header className="page-header">
        <div>
          <h1>任务</h1>
          <p>用户原文会原样保存，后续由队列执行切分、提示词和 9:16 生图。</p>
        </div>
        <button onClick={refresh}>
          <RefreshCw size={18} />
          刷新
        </button>
      </header>
      <form className="panel task-create-form" onSubmit={createTask}>
        <textarea name="original_text" placeholder="输入原始故事文本，系统会原样保存" required />
        <select name="style_id" required>
          <option value="">选择启用风格</option>
          {styles.map((style) => (
            <option key={style.id} value={style.id}>
              {style.name}
            </option>
          ))}
        </select>
        <select value={countMode} onChange={(event) => setCountMode(event.target.value as "auto" | "fixed")}>
          <option value="auto">自动判断图片数量</option>
          <option value="fixed">固定图片数量</option>
        </select>
        {countMode === "fixed" ? (
          <input name="requested_image_count" type="number" min="1" max="80" placeholder="图片数量" required />
        ) : null}
        {message ? <p className="form-message">{message}</p> : null}
        <button type="submit">提交任务</button>
      </form>
      {error ? <div className="error">{error}</div> : null}
      <div className="task-layout">
        <div className="task-list">
          {tasks.length === 0 ? <div className="empty">还没有任务。</div> : null}
          {tasks.map((task) => (
            <button
              type="button"
              className={`task-row ${taskForDetail?.id === task.id ? "selected" : ""}`}
              key={task.id}
              onClick={() => selectTask(task.id)}
            >
              <div>
                <strong>{task.display_title}</strong>
                <p>{task.style_name_snapshot}</p>
              </div>
              <span className={`status-pill ${task.status}`}>{task.status}</span>
              <small>
                {task.progress_current}/{task.progress_total}
              </small>
            </button>
          ))}
        </div>

        <aside className="task-detail">
          {taskForDetail ? (
            <>
              <section className="panel detail-head">
                <div>
                  <span className={`status-pill ${taskForDetail.status}`}>{taskForDetail.status}</span>
                  <h2>{taskForDetail.display_title}</h2>
                  <p>{taskForDetail.style_name_snapshot}</p>
                </div>
                <div className="detail-actions">
                  <button type="button" disabled={!canDownload} onClick={downloadSelectedTask}>
                    <Download size={16} />
                    下载
                  </button>
                  <button type="button" disabled={!canCancel} onClick={cancelSelectedTask}>
                    <X size={16} />
                    取消
                  </button>
                </div>
                {taskForDetail.error_message ? <p className="error">{taskForDetail.error_message}</p> : null}
              </section>

              {taskForDetail.steps.length > 0 ? (
                <section className="panel step-strip">
                  {taskForDetail.steps.map((step) => (
                    <div key={step.id} className={`step-chip ${step.status}`}>
                      <strong>{step.step_name}</strong>
                      <span>{step.status}</span>
                    </div>
                  ))}
                </section>
              ) : null}

              <section className="panel story-panel">
                <h2>原始文本</h2>
                <p>{taskForDetail.original_text}</p>
              </section>

              <section className="panel panel-wall">
                <div className="editor-title">
                  <div>
                    <h2>分镜与图片</h2>
                    <p>每个 panel 对应一张 9:16 图片。</p>
                  </div>
                </div>
                <div className="task-image-grid">
                  {taskForDetail.panels.length === 0 ? <div className="empty mini">等待故事切分</div> : null}
                  {taskForDetail.panels.map((panel) => {
                    const image = imagesByPanelId.get(panel.id);
                    return (
                      <article key={panel.id} className="panel-card">
                        <div className="poster">
                          {image?.asset ? (
                            <button
                              type="button"
                              className="image-button"
                              onClick={() => setPreviewAssetId(image.asset?.id ?? null)}
                            >
                              <img src={api.assetContentUrl(image.asset.id)} alt={`分镜 ${panel.panel_order}`} />
                              <Eye size={18} />
                            </button>
                          ) : (
                            <span>{image?.status ?? panel.prompt_status}</span>
                          )}
                        </div>
                        <strong>Panel {panel.panel_order}</strong>
                        <p>{panel.original_text_segment}</p>
                        {panel.generated_prompt ? <small>{panel.generated_prompt}</small> : null}
                        {image?.error_message ? <small className="error">{image.error_message}</small> : null}
                      </article>
                    );
                  })}
                </div>
              </section>
            </>
          ) : (
            <div className="empty">选择一个任务查看详情。</div>
          )}
        </aside>
      </div>
      {previewImage?.asset ? (
        <div className="image-modal" onClick={() => setPreviewAssetId(null)}>
          <button type="button" className="modal-close" onClick={() => setPreviewAssetId(null)}>
            <X size={18} />
          </button>
          <img src={api.assetContentUrl(previewImage.asset.id)} alt="生成图预览" />
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
  const [selectedId, setSelectedId] = useState("");
  const [mode, setMode] = useState<"create" | "edit">("create");
  const [styleTest, setStyleTest] = useState<StyleTest | null>(null);
  const activeCount = useMemo(() => styles.filter((style) => style.status === "active").length, [styles]);
  const selectedStyle = useMemo(
    () => styles.find((style) => style.id === selectedId) ?? styles[0] ?? null,
    [selectedId, styles],
  );

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    const result = await api.styles({ query, status });
    setStyles(result.items);
    if (!selectedId && result.items[0]) {
      setSelectedId(result.items[0].id);
    }
  }

  function startCreate() {
    setMode("create");
    setMessage("");
    setStyleTest(null);
  }

  function startEdit(style: Style) {
    setSelectedId(style.id);
    setMode("edit");
    setMessage("");
    setStyleTest(null);
  }

  async function createStyle(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const payload: Partial<Style> = {
      name: String(formData.get("name") ?? ""),
      status: String(formData.get("status") ?? "draft") as Style["status"],
      style_prompt: String(formData.get("style_prompt") ?? ""),
      description: String(formData.get("description") ?? ""),
    };
    if (user.role === "admin") {
      payload.generation_profile_key = String(formData.get("generation_profile_key") ?? "");
    }

    try {
      const saved =
        mode === "edit" && selectedStyle
          ? await api.updateStyle(selectedStyle.id, payload)
          : await api.createStyle(payload);
      setSelectedId(saved.id);
      setMode("edit");
      setMessage(mode === "edit" ? "风格已保存" : "风格已创建");
      await refresh();
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
      setSelectedId("");
      setMode("create");
      setMessage("风格已删除");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败");
    }
  }

  async function uploadReferences(event: React.ChangeEvent<HTMLInputElement>) {
    if (!selectedStyle || !event.target.files?.length) {
      return;
    }
    try {
      for (const file of Array.from(event.target.files)) {
        await api.uploadStyleReferenceImage(selectedStyle.id, file);
      }
      setMessage("参考图已上传");
      event.target.value = "";
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "上传失败");
    }
  }

  async function deleteReference(referenceId: string) {
    if (!selectedStyle) return;
    try {
      await api.deleteStyleReferenceImage(selectedStyle.id, referenceId);
      setMessage("参考图已移除");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除参考图失败");
    }
  }

  async function runStyleTest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedStyle) return;
    const formData = new FormData(event.currentTarget);
    try {
      const result = await api.createStyleTest(selectedStyle.id, {
        test_text: String(formData.get("test_text") ?? ""),
      });
      setStyleTest(result);
      setMessage(result.status === "succeeded" ? "风格测试已完成" : result.error_message ?? "风格测试未成功");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "风格测试失败");
    }
  }

  const formStyle = mode === "edit" ? selectedStyle : null;

  return (
    <section className="page style-workspace">
      <header className="page-header">
        <div>
          <h1>风格</h1>
          <p>共 {styles.length} 个风格，{activeCount} 个启用。参考图会作为后续 9:16 生图的视觉锚点。</p>
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
        <button onClick={refresh}>筛选</button>
      </div>

      <div className="style-layout">
        <div className="style-gallery">
          {styles.length === 0 ? <div className="empty">还没有风格。</div> : null}
          {styles.map((style) => {
            const cover = style.cover_asset ?? style.reference_images[0]?.asset;
            return (
              <button
                type="button"
                className={`style-card ${selectedStyle?.id === style.id ? "selected" : ""}`}
                key={style.id}
                onClick={() => startEdit(style)}
              >
                <div className="poster">
                  {cover ? <img src={api.assetContentUrl(cover.id)} alt={style.name} /> : <span>9:16</span>}
                </div>
                <div className="style-card-copy">
                  <span className={`status-pill ${style.status}`}>{style.status}</span>
                  <strong>{style.name}</strong>
                  <small>{style.reference_images.length} 张参考图</small>
                </div>
              </button>
            );
          })}
        </div>

        <aside className="style-editor">
          <form key={`${mode}-${formStyle?.id ?? "new"}`} className="panel form-grid" onSubmit={createStyle}>
            <div className="editor-title">
              <div>
                <h2>{mode === "edit" && formStyle ? "编辑风格" : "新建风格"}</h2>
                <p>{mode === "edit" && formStyle ? formStyle.name : "创建一个可复用的生图风格资产"}</p>
              </div>
              {mode === "edit" && formStyle ? (
                <button type="button" className="danger-button" onClick={() => deleteStyle(formStyle)}>
                  <Trash2 size={16} />
                </button>
              ) : null}
            </div>
            <input name="name" placeholder="风格名称" defaultValue={formStyle?.name ?? ""} required />
            <select name="status" defaultValue={formStyle?.status ?? "draft"}>
              <option value="draft">草稿</option>
              <option value="active">启用</option>
              <option value="disabled">停用</option>
            </select>
            {user.role === "admin" ? (
              <input
                name="generation_profile_key"
                placeholder="管理员生成配置 Key"
                defaultValue={formStyle?.generation_profile_key ?? ""}
              />
            ) : (
              <div className="profile-state">
                {formStyle?.generation_profile_configured ? "已绑定后台生成配置" : "未绑定后台生成配置"}
              </div>
            )}
            <textarea name="description" placeholder="描述" defaultValue={formStyle?.description ?? ""} />
            <textarea name="style_prompt" placeholder="风格提示词" defaultValue={formStyle?.style_prompt ?? ""} required />
            {message ? <p className="form-message">{message}</p> : null}
            <button type="submit">
              <Save size={16} />
              {mode === "edit" ? "保存风格" : "创建风格"}
            </button>
          </form>

          {selectedStyle ? (
            <section className="panel reference-panel">
              <div className="editor-title">
                <div>
                  <h2>参考图</h2>
                  <p>图片按 9:16 容器展示，后续会作为图生图参考。</p>
                </div>
                <label className="upload-button">
                  <Upload size={16} />
                  上传
                  <input type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={uploadReferences} />
                </label>
              </div>
              <div className="reference-grid">
                {selectedStyle.reference_images.length === 0 ? <div className="empty mini">暂无参考图</div> : null}
                {selectedStyle.reference_images.map((reference) => (
                  <figure key={reference.id} className="reference-item">
                    <img src={api.assetContentUrl(reference.asset.id)} alt={reference.asset.original_filename ?? "参考图"} />
                    <button type="button" onClick={() => deleteReference(reference.id)}>
                      <Trash2 size={14} />
                    </button>
                  </figure>
                ))}
              </div>
            </section>
          ) : null}

          {selectedStyle ? (
            <section className="panel reference-panel">
              <div className="editor-title">
                <div>
                  <h2>测试风格</h2>
                  <p>使用当前风格提示词和参考图生成一张 9:16 测试图。</p>
                </div>
              </div>
              <form className="test-form" onSubmit={runStyleTest}>
                <textarea name="test_text" placeholder="输入要测试的画面文本" required />
                <button type="submit">生成测试图</button>
              </form>
              {styleTest ? (
                <div className="test-result">
                  <span className={`status-pill ${styleTest.status}`}>{styleTest.status}</span>
                  {styleTest.output_asset ? (
                    <img src={api.assetContentUrl(styleTest.output_asset.id)} alt="风格测试结果" />
                  ) : (
                    <p>{styleTest.error_message || "暂无测试图"}</p>
                  )}
                </div>
              ) : null}
            </section>
          ) : null}
        </aside>
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
