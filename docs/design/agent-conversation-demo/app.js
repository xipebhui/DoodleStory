const conversations = [
  {
    id: "draft-welcome",
    title: "新对话",
    preview: "还没有发送消息",
    group: "今天",
    time: "现在",
    status: "draft",
    subtitle: "从一个想法开始，资源可以稍后添加",
    messages: [],
    task: null,
    draft: "",
    contexts: [],
  },
  {
    id: "street-artist",
    title: "被裁员的第七天",
    preview: "第 4 张正在进行人物一致性检查",
    group: "今天",
    time: "刚刚",
    status: "running",
    subtitle: "五格漫画 · 暖灰铅笔电影感",
    messages: [
      {
        id: "m1",
        role: "user",
        text: "把这个 idea 做成五格漫画：一个女孩被裁员后，每天假装上班，最后在街角靠画画接到了第一笔订单。主角用林夏，整体不要太煽情。",
        resources: ["角色 · 林夏", "风格 · 暖灰铅笔"],
        time: "10:24",
      },
      {
        id: "m2",
        role: "agent",
        text: "我会把重点放在她从隐藏失业到重新获得掌控感的变化上。先按五个连续时刻推进，保留克制的情绪，让橘白流浪猫成为贯穿画面的陪伴线索。",
        time: "10:24",
      },
      {
        id: "m3",
        role: "agent",
        text: "故事和角色设定已经稳定，我创建了一个五格漫画任务。你可以离开这个对话，任务仍会继续；之后从左侧重新进入，就能接着修改。",
        time: "10:25",
        taskId: "task-104",
      },
    ],
    task: {
      id: "task-104",
      title: "被裁员的第七天，我开始在街角画画",
      status: "生成中",
      completed: 3,
      total: 5,
      progress: 68,
      selectedPanel: 3,
      panels: [
        { order: 1, status: "已接受", className: "done", version: "v1", text: "早高峰，她逆着人群走出地铁。", review: "人物与场景连续性正常。" },
        { order: 2, status: "已接受", className: "done", version: "v1", text: "她在街角第一次展开速写本。", review: "构图与故事节奏符合预期。" },
        { order: 3, status: "待决定", className: "review", version: "v2", text: "家人的消息让她强忍住情绪。", review: "人物和场景连续性正常，但表情过于平静，没有表现出紧张和愧疚。" },
        { order: 4, status: "检查中", className: "running", version: "v1", text: "陌生女孩举起手机记录她画画。", review: "正在检查人物外观与前序画面的连续性。" },
        { order: 5, status: "等待生成", className: "waiting", version: "—", text: "雨停后，她收到第一笔订单。", review: "将在 Panel 4 检查完成后开始生成。" },
      ],
      activities: [
        { text: "故事和五格分镜已确定", time: "10:25" },
        { text: "Panel 1–3 已生成", time: "10:27" },
        { text: "正在检查 Panel 4 人物一致性", time: "现在", current: true },
      ],
    },
  },
  {
    id: "old-camera",
    title: "父亲留下的旧相机",
    preview: "四格漫画已完成，可以继续修改",
    group: "今天",
    time: "09:12",
    status: "done",
    subtitle: "四格漫画 · 黑白纪实",
    messages: [
      { id: "c2m1", role: "user", text: "把父亲留下的一台旧相机改成一个四格漫画。", time: "09:02" },
      { id: "c2m2", role: "agent", text: "我把它处理成一次迟到的告别：女儿整理遗物时发现相机里还留着最后一卷没有冲洗的胶片。", time: "09:03" },
      { id: "c2m3", role: "agent", text: "四格漫画已经完成。你可以点开任务查看每张图片，也可以直接告诉我修改哪一张。", time: "09:12", taskId: "task-088" },
    ],
    task: {
      id: "task-088",
      title: "父亲留下的旧相机",
      status: "已完成",
      completed: 4,
      total: 4,
      progress: 100,
      selectedPanel: 1,
      panels: [
        { order: 1, status: "已完成", className: "done", text: "她在纸箱里发现旧相机。" },
        { order: 2, status: "已完成", className: "done", text: "相机里还有一卷没有冲洗的胶片。" },
        { order: 3, status: "已完成", className: "done", text: "照片里是父亲最后一次看向她。" },
        { order: 4, status: "已完成", className: "done", text: "她把相机重新放回肩上。" },
      ],
      activities: [
        { text: "四格分镜已确定", time: "09:04" },
        { text: "全部图片已生成并检查", time: "09:12" },
      ],
    },
  },
  {
    id: "douyin-remix",
    title: "抖音参考改编",
    preview: "Agent 正在等待你确认改编方向",
    group: "昨天",
    time: "昨天",
    status: "waiting",
    subtitle: "参考作品 · 等待确认",
    messages: [
      { id: "c3m1", role: "user", text: "参考这个抖音作品，但把人物关系改成母女。", resources: ["参考作品 · 抖音图文"], time: "昨天 21:40" },
      { id: "c3m2", role: "agent", text: "我识别到原作的核心是“误解被一个迟来的动作化解”。如果改成母女关系，可以保留三段式推进，但结尾需要重新设计。你希望结尾更温暖，还是保留克制？", time: "昨天 21:42" },
    ],
    task: null,
  },
];

const state = {
  activeConversationId: "draft-welcome",
  inspectorOpen: false,
  query: "",
  toastTimer: null,
  pendingRegeneration: null,
};

const shell = document.querySelector("#demo-shell");
const nav = document.querySelector("#conversation-nav");
const thread = document.querySelector("#thread");
const title = document.querySelector("#conversation-title");
const subtitle = document.querySelector("#conversation-subtitle");
const conversationState = document.querySelector("#conversation-state");
const openCurrentTask = document.querySelector("#open-current-task");
const inspector = document.querySelector("#task-inspector");
const inspectorTitle = document.querySelector("#inspector-title");
const inspectorContent = document.querySelector("#inspector-content");
const messageInput = document.querySelector("#message-input");
const contextRow = document.querySelector("#context-row");
const resourceButton = document.querySelector("#resource-button");
const resourceMenu = document.querySelector("#resource-menu");
const resourceSearch = document.querySelector("#resource-search");
const resourceEmpty = document.querySelector("#resource-empty");
const backdrop = document.querySelector("#mobile-backdrop");
const regenerateDialog = document.querySelector("#regenerate-dialog");
const regenerateDialogDescription = document.querySelector("#regenerate-dialog-description");
const regenerateDialogContext = document.querySelector("#regenerate-dialog-context");
const confirmRegenerate = document.querySelector("#confirm-regenerate");

function activeConversation() {
  return conversations.find((conversation) => conversation.id === state.activeConversationId);
}

function activeContexts() {
  const conversation = activeConversation();
  if (!conversation) return [];
  if (!conversation.contexts) conversation.contexts = [];
  return conversation.contexts;
}

function saveActiveDraft() {
  const conversation = activeConversation();
  if (conversation) conversation.draft = messageInput.value;
}

function restoreActiveDraft() {
  const conversation = activeConversation();
  messageInput.value = conversation?.draft || "";
  resizeInput();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function statusLabel(status) {
  if (status === "running") return "生成中";
  if (status === "done") return "已完成";
  if (status === "waiting") return "等待回复";
  if (status === "paused") return "已暂停";
  return "新对话";
}

function renderNavigation() {
  const filtered = conversations.filter((conversation) => {
    if (conversation.status === "draft" && !conversation.messages.length) return false;
    const query = state.query.trim().toLowerCase();
    return !query || `${conversation.title} ${conversation.preview}`.toLowerCase().includes(query);
  });
  const groups = [...new Set(filtered.map((conversation) => conversation.group))];
  nav.innerHTML = groups
    .map(
      (group) => `
        <div class="conversation-group-label">${escapeHtml(group)}</div>
        ${filtered
          .filter((conversation) => conversation.group === group)
          .map(
            (conversation) => `
              <button class="conversation-item ${conversation.id === state.activeConversationId ? "active" : ""}" type="button" data-conversation-id="${conversation.id}">
                <span class="conversation-item-head">
                  <span class="conversation-status-dot ${conversation.status}"></span>
                  <strong>${escapeHtml(conversation.title)}</strong>
                  <time>${escapeHtml(conversation.time)}</time>
                </span>
                <p>${escapeHtml(conversation.preview)}</p>
              </button>
            `,
          )
          .join("")}
      `,
    )
    .join("");

  nav.querySelectorAll("[data-conversation-id]").forEach((button) => {
    button.addEventListener("click", () => selectConversation(button.dataset.conversationId));
  });
}

function renderTaskCard(task) {
  const currentActivity = [...task.activities].reverse().find((activity) => activity.current) || task.activities.at(-1);
  const activityIconClass = task.status === "已暂停" ? "activity-pause" : currentActivity?.current ? "activity-spinner" : "activity-check";
  return `
    <article class="task-card" data-task-card="${task.id}">
      <div class="task-card-main">
        <div class="task-card-head">
          <span class="task-card-icon">▦</span>
          <span class="task-card-title">
            <strong>${escapeHtml(task.title)}</strong>
            <small>漫画任务 · ${task.total} 个 Panel</small>
          </span>
          <span class="status-text">${escapeHtml(task.status)}</span>
        </div>
        <div class="task-progress"><span style="width: ${task.progress}%"></span></div>
        <div class="task-card-meta">
          <span>${task.completed}/${task.total} 张已完成</span>
          <span>${task.status === "已完成" ? "可以继续修改" : task.status === "已暂停" ? "继续任务后恢复" : "离开对话后仍会继续"}</span>
        </div>
        <div class="mini-panel-strip" aria-label="任务分镜">
          ${task.panels
            .map((panel) => `<button class="mini-panel ${panel.className}" type="button" data-task-panel="${panel.order}" data-order="${panel.order}" aria-label="打开 Panel ${panel.order}，${escapeHtml(panel.generatingVersion ? `正在生成 ${panel.generatingVersion}` : panel.status)}"></button>`)
            .join("")}
        </div>
        <div class="task-current-activity"><span class="${activityIconClass}"></span>${escapeHtml(currentActivity?.text || "等待下一步")}</div>
      </div>
      <footer class="task-card-footer">
        <button class="task-link-button" type="button" data-task-action="mention" data-task-id="${task.id}">在对话中引用</button>
        <button class="task-link-button" type="button" data-task-action="open" data-task-id="${task.id}">查看任务 →</button>
      </footer>
    </article>
  `;
}

function renderMessage(message, conversation) {
  const resources = message.resources?.length
    ? `<div class="inline-resource-list">${message.resources.map((resource) => `<span class="inline-resource">@${escapeHtml(resource)}</span>`).join("")}</div>`
    : "";
  const task = message.taskId && conversation.task?.id === message.taskId ? renderTaskCard(conversation.task) : "";
  const activity = message.activity
    ? `<div class="activity-line"><span class="activity-spinner"></span>${escapeHtml(message.activity)}</div>`
    : "";
  return `
    <article class="message ${message.role}">
      <span class="message-avatar">${message.role === "user" ? "你" : "DS"}</span>
      <div class="message-content">
        <div class="message-name">${message.role === "user" ? "你" : "DoodleStory Agent"}<time>${escapeHtml(message.time || "现在")}</time></div>
        <p>${escapeHtml(message.text)}</p>
        ${resources}
        ${task}
        ${activity}
      </div>
    </article>
  `;
}

function renderConversation() {
  const conversation = activeConversation();
  if (!conversation) return;
  title.textContent = conversation.title;
  subtitle.textContent = conversation.subtitle || "在对话中创建和继续漫画任务";
  conversationState.textContent = statusLabel(conversation.status);
  conversationState.hidden = conversation.status === "draft";
  openCurrentTask.hidden = !conversation.task;
  openCurrentTask.lastChild.textContent = state.inspectorOpen ? " 收起任务" : " 查看任务";

  if (!conversation.messages.length) {
    thread.innerHTML = `
      <div class="thread-inner empty-conversation">
        <div class="empty-inner">
          <div class="empty-mark">画</div>
          <h2>今天想创作什么？</h2>
          <p>从一个 idea、一段故事，或者一个想改编的作品开始。</p>
          <div class="starter-list">
            <button class="starter-button" type="button" data-starter="我有一个很简单的 idea，帮我把它发展成五格漫画。"><span>从一个 idea 开始</span><span>→</span></button>
            <button class="starter-button" type="button" data-starter="我有一段完整故事，帮我设计成连续漫画。"><span>把故事做成漫画</span><span>→</span></button>
            <button class="starter-button" type="button" data-starter="我想参考一个作品，重新改编人物和结局。"><span>参考作品进行改编</span><span>→</span></button>
          </div>
          <div class="available-resources">
            <div class="available-resources-head">
              <span>你的常用资源</span>
              <button type="button" data-open-resources>查看全部</button>
            </div>
            <div class="resource-shortcuts">
              <button type="button" data-quick-resource="角色 · 林夏"><span class="resource-avatar">林</span><span><strong>林夏</strong><small>角色</small></span></button>
              <button type="button" data-quick-resource="风格 · 暖灰铅笔电影感"><span class="resource-swatch style-swatch"></span><span><strong>暖灰铅笔</strong><small>风格</small></span></button>
              <button type="button" data-quick-resource="角色 · 阿布"><span class="resource-avatar cat-avatar">阿</span><span><strong>阿布</strong><small>角色</small></span></button>
            </div>
          </div>
        </div>
      </div>
    `;
    thread.querySelectorAll("[data-starter]").forEach((button) => {
      button.addEventListener("click", () => {
        messageInput.value = button.dataset.starter;
        conversation.draft = messageInput.value;
        resizeInput();
        messageInput.focus();
      });
    });
    thread.querySelectorAll("[data-quick-resource]").forEach((button) => {
      button.addEventListener("click", () => {
        addContext(button.dataset.quickResource);
        messageInput.focus();
      });
    });
    thread.querySelector("[data-open-resources]")?.addEventListener("click", (event) => {
      event.stopPropagation();
      openResourceMenu(true);
    });
  } else {
    thread.innerHTML = `<div class="thread-inner">${conversation.messages.map((message) => renderMessage(message, conversation)).join("")}</div>`;
    bindTaskCardActions();
    requestAnimationFrame(() => {
      thread.scrollTop = thread.scrollHeight;
    });
  }
}

function renderContexts() {
  const contexts = activeContexts();
  contextRow.innerHTML = contexts
    .map((context, index) => `<span class="context-chip">@${escapeHtml(context)}<button type="button" data-remove-context="${index}" aria-label="移除 ${escapeHtml(context)}">×</button></span>`)
    .join("");
  contextRow.querySelectorAll("[data-remove-context]").forEach((button) => {
    button.addEventListener("click", () => {
      contexts.splice(Number(button.dataset.removeContext), 1);
      renderContexts();
    });
  });
}

function selectConversation(id) {
  saveActiveDraft();
  state.activeConversationId = id;
  closeInspector();
  shell.classList.remove("sidebar-open");
  backdrop.hidden = true;
  renderNavigation();
  renderConversation();
  renderContexts();
  restoreActiveDraft();
}

function createConversation() {
  saveActiveDraft();
  const current = activeConversation();
  if (current?.status === "draft" && !current.messages.length && !current.draft) {
    closeInspector();
    current.contexts = [];
    renderContexts();
    messageInput.focus();
    return;
  }
  const conversation = {
    id: `draft-${Date.now()}`,
    title: "未命名对话",
    preview: "从一个 idea 开始",
    group: "今天",
    time: "现在",
    status: "draft",
    subtitle: "新对话 · 还没有创建任务",
    messages: [],
    task: null,
    draft: "",
    contexts: [],
  };
  conversations.unshift(conversation);
  selectConversation(conversation.id);
  messageInput.focus();
}

function bindTaskCardActions() {
  thread.querySelectorAll("[data-task-action]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const conversation = activeConversation();
      if (!conversation?.task) return;
      if (button.dataset.taskAction === "mention") {
        addContext(`任务 · ${conversation.task.title}`);
        messageInput.focus();
        showToast("任务已经加入本轮对话上下文");
      } else {
        openInspector();
      }
    });
  });
  thread.querySelectorAll("[data-task-card]").forEach((card) => {
    card.addEventListener("dblclick", openInspector);
  });
  thread.querySelectorAll("[data-task-panel]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const conversation = activeConversation();
      if (!conversation?.task) return;
      conversation.task.selectedPanel = Number(button.dataset.taskPanel);
      openInspector();
    });
  });
}

function addContext(context) {
  const contexts = activeContexts();
  if (!contexts.includes(context)) contexts.push(context);
  renderContexts();
}

function openInspector() {
  const conversation = activeConversation();
  if (!conversation?.task) return;
  state.inspectorOpen = true;
  shell.classList.add("inspector-open");
  inspector.setAttribute("aria-hidden", "false");
  if (window.innerWidth <= 900) backdrop.hidden = false;
  renderInspector();
  renderConversation();
}

function closeInspector() {
  state.inspectorOpen = false;
  shell.classList.remove("inspector-open");
  inspector.setAttribute("aria-hidden", "true");
  backdrop.hidden = true;
  renderConversation();
}

function openResourceMenu(focusSearch = false) {
  resourceMenu.hidden = false;
  resourceButton.setAttribute("aria-expanded", "true");
  resourceSearch.value = "";
  filterResources("");
  if (focusSearch) resourceSearch.focus();
}

function closeResourceMenu() {
  resourceMenu.hidden = true;
  resourceButton.setAttribute("aria-expanded", "false");
}

function filterResources(query) {
  const normalizedQuery = query.trim().toLowerCase();
  let visibleCount = 0;
  resourceMenu.querySelectorAll("[data-resource]").forEach((button) => {
    const matches = !normalizedQuery || button.textContent.toLowerCase().includes(normalizedQuery);
    button.hidden = !matches;
    if (matches) visibleCount += 1;
  });
  resourceEmpty.hidden = visibleCount > 0;
}

function renderInspector() {
  const conversation = activeConversation();
  const task = conversation?.task;
  if (!task) return;
  inspectorTitle.textContent = task.title;
  const selected = task.panels.find((panel) => panel.order === task.selectedPanel) || task.panels[0];
  const selectedVersion = selected.version || (selected.className === "waiting" ? "—" : "v1");
  const selectedStatus = selected.generatingVersion ? `正在生成 ${selected.generatingVersion}` : selected.status;
  const selectedReview = selected.generatingVersion
    ? `正在复用 ${selectedVersion} 的最终提示词、风格和角色参考资源生成 ${selected.generatingVersion}。当前版本不会被覆盖。`
    : selected.review || (selected.className === "done" ? "当前版本已经完成，可以继续接受或提出修改。" : "正在等待 Agent 更新检查结论。");
  inspectorContent.innerHTML = `
    <div class="inspector-status-row">
      <strong>${task.completed}/${task.total} 张</strong>
      <div class="inspector-task-controls">
        <span class="status-pill">${escapeHtml(task.status)}</span>
        ${task.status === "已完成" ? "" : `<button class="task-control-button" type="button" id="pause-task-action">${task.status === "已暂停" ? "继续任务" : "暂停任务"}</button>`}
      </div>
    </div>
    <p class="inspector-description">任务属于当前对话。关闭详情后仍可继续聊天，之后也可以从左侧历史对话重新进入。</p>
    <div class="task-progress"><span style="width: ${task.progress}%"></span></div>
    <p class="task-control-note">${task.status === "已完成" ? "任务已经完成；你仍可以选择任一 Panel 继续创建新版本。" : task.status === "已暂停" ? "已暂停：不会启动新的 Panel 或 Agent 步骤；已经提交的图片仍会完成并保存。" : "暂停只会阻止后续 Panel 和 Agent 步骤；已经提交给图片模型的请求仍会完成并保存。"}</p>

    <section class="inspector-section">
      <div class="inspector-section-head"><h3>分镜</h3><span>选择要检查的画面</span></div>
      <div class="panel-grid">
        ${task.panels
          .map(
            (panel) => `
              <button class="panel-button ${panel.className} ${panel.order === task.selectedPanel ? "selected" : ""}" type="button" data-panel-order="${panel.order}">
                <span class="panel-thumb" data-panel-art="${panel.order}">${panel.order}</span>
                <small>${panel.order}. ${escapeHtml(panel.generatingVersion ? `生成 ${panel.generatingVersion}` : panel.status)}</small>
              </button>
            `,
          )
          .join("")}
      </div>
      <div class="selected-panel-preview" data-panel-art="${selected.order}">
        <span>Panel ${selected.order}</span>
        <strong>${escapeHtml(selectedVersion)}</strong>
      </div>
      <div class="selected-panel-detail">
        <div><strong>Panel ${selected.order} · ${escapeHtml(selectedVersion)}</strong><span class="panel-state ${selected.className}">${escapeHtml(selectedStatus)}</span></div>
        <p>${escapeHtml(selected.text)}</p>
        <div class="review-note"><span>Agent 检查</span><p>${escapeHtml(selectedReview)}</p></div>
      </div>
    </section>

    <section class="inspector-section activity-section">
      <div class="inspector-section-head"><h3>Agent 行动</h3><button class="text-action" type="button" id="toggle-activity">查看轨迹</button></div>
      <div class="activity-list" id="activity-list" hidden>
        ${task.activities
          .map((activity) => `<div class="activity-item ${activity.current ? "current" : ""}"><span>${escapeHtml(activity.text)}</span><time>${escapeHtml(activity.time)}</time></div>`)
          .join("")}
      </div>
    </section>

    <section class="inspector-section">
      <div class="inspector-section-head"><h3>继续操作</h3><span>当前对象：Panel ${selected.order}</span></div>
      <div class="inspector-actions">
        <button class="primary-action" type="button" id="mention-panel-action">引用 Panel ${selected.order} 并修改</button>
        <button class="secondary-action" type="button" id="accept-panel-action" ${selected.className === "waiting" || selected.className === "running" ? "disabled" : ""}>接受 ${escapeHtml(selectedVersion)}</button>
      </div>
      <div class="secondary-action-row">
        <button class="text-action" type="button" id="retry-panel-action" ${selectedVersion === "—" || selected.className === "running" || task.status === "已暂停" ? "disabled" : ""}>再生成一个版本</button>
        <button class="text-action" type="button" id="restore-panel-action" ${selectedVersion === "v1" || selectedVersion === "—" ? "disabled" : ""}>恢复上一版</button>
      </div>
    </section>
  `;

  inspectorContent.querySelectorAll("[data-panel-order]").forEach((button) => {
    button.addEventListener("click", () => {
      task.selectedPanel = Number(button.dataset.panelOrder);
      renderInspector();
    });
  });
  inspectorContent.querySelector("#mention-panel-action").addEventListener("click", () => {
    addContext(`Panel ${task.selectedPanel}`);
    if (selectedVersion !== "—") addContext(`当前图片 ${selectedVersion}`);
    closeInspector();
    messageInput.focus();
  });
  inspectorContent.querySelector("#toggle-activity").addEventListener("click", (event) => {
    const list = inspectorContent.querySelector("#activity-list");
    list.hidden = !list.hidden;
    event.currentTarget.textContent = list.hidden ? "查看轨迹" : "收起轨迹";
  });
  inspectorContent.querySelector("#accept-panel-action").addEventListener("click", () => {
    selected.status = "已接受";
    selected.className = "done";
    selected.version = selectedVersion;
    task.activities.push({ text: `Panel ${selected.order} 的 ${selectedVersion} 已被接受`, time: "现在" });
    renderConversation();
    renderInspector();
    showToast(`Panel ${selected.order} 已接受（设计演示）`);
  });
  inspectorContent.querySelector("#retry-panel-action").addEventListener("click", () => {
    const versionNumber = Number.parseInt(selectedVersion.replace(/^v/, ""), 10);
    const nextVersion = `v${Number.isFinite(versionNumber) ? versionNumber + 1 : 1}`;
    state.pendingRegeneration = {
      conversationId: conversation.id,
      taskId: task.id,
      panelOrder: selected.order,
      sourceVersion: selectedVersion,
      nextVersion,
    };
    regenerateDialogDescription.textContent = `将使用 Panel ${selected.order} 当前版本 ${selectedVersion} 已保存的最终提示词和参考资源，生成 ${nextVersion}。原版本会继续保留。`;
    regenerateDialogContext.innerHTML = `<span>相同 Prompt</span><span>相同风格与角色参考</span><span>正式功能预计消耗 1 积分</span>`;
    regenerateDialog.showModal();
  });
  inspectorContent.querySelector("#restore-panel-action").addEventListener("click", () => {
    selected.version = "v1";
    selected.status = "待决定";
    selected.className = "review";
    selected.review = "已恢复上一版本，请确认是否接受。";
    renderConversation();
    renderInspector();
    showToast(`Panel ${selected.order} 已恢复 v1（设计演示）`);
  });
  inspectorContent.querySelector("#pause-task-action")?.addEventListener("click", () => {
    const wasPaused = task.status === "已暂停";
    task.status = wasPaused ? "生成中" : "已暂停";
    conversation.status = wasPaused ? "running" : "paused";
    conversation.preview = wasPaused ? "任务已继续，将从未完成步骤恢复" : "任务已暂停，已提交的图片仍会完成";
    task.activities.forEach((activity) => { activity.current = false; });
    task.activities.push({
      text: wasPaused ? "任务已继续，将从下一个未完成步骤恢复" : "任务已暂停，不再启动新的 Panel",
      time: "现在",
      current: wasPaused,
    });
    renderNavigation();
    renderConversation();
    renderInspector();
    showToast(wasPaused ? "任务已继续（设计演示）" : "任务已暂停（设计演示）");
  });
}

confirmRegenerate.addEventListener("click", () => {
  const pending = state.pendingRegeneration;
  if (!pending) return;
  const conversation = conversations.find((item) => item.id === pending.conversationId);
  const task = conversation?.task?.id === pending.taskId ? conversation.task : null;
  const panel = task?.panels.find((item) => item.order === pending.panelOrder);
  if (!conversation || !task || !panel) return;

  panel.generatingVersion = pending.nextVersion;
  panel.className = "running";
  task.activities.forEach((activity) => { activity.current = false; });
  task.activities.push({ text: `正在使用 ${pending.sourceVersion} 的生成配置创建 Panel ${panel.order} · ${pending.nextVersion}`, time: "现在", current: true });
  regenerateDialog.close();
  state.pendingRegeneration = null;
  renderNavigation();
  renderConversation();
  if (state.inspectorOpen && state.activeConversationId === conversation.id) renderInspector();
  showToast(`正在生成 Panel ${panel.order} · ${pending.nextVersion}（设计演示）`);

  window.setTimeout(() => {
    panel.version = pending.nextVersion;
    panel.generatingVersion = null;
    panel.status = "待决定";
    panel.className = "review";
    panel.review = "新版本已经生成。请比较当前结果，决定接受、继续修改或恢复上一版。";
    task.activities.forEach((activity) => { activity.current = false; });
    task.activities.push({ text: `Panel ${panel.order} · ${pending.nextVersion} 已生成，等待用户决定`, time: "现在" });
    renderNavigation();
    if (state.activeConversationId === conversation.id) {
      renderConversation();
      if (state.inspectorOpen) renderInspector();
    }
  }, 1200);
});

regenerateDialog.addEventListener("close", () => {
  state.pendingRegeneration = null;
});

function submitMessage(event) {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;
  const conversation = activeConversation();
  if (!conversation) return;
  const attachedContexts = [...activeContexts()];
  conversation.messages.push({ id: `user-${Date.now()}`, role: "user", text, resources: attachedContexts, time: "现在" });
  if (conversation.status === "draft") {
    conversation.title = text.slice(0, 16) + (text.length > 16 ? "…" : "");
    conversation.preview = "Agent 正在理解你的创作目标";
    conversation.subtitle = "新漫画项目 · 正在建立上下文";
  }
  conversation.status = "running";
  conversation.contexts = [];
  conversation.draft = "";
  messageInput.value = "";
  resizeInput();
  renderContexts();
  renderNavigation();
  renderConversation();

  window.setTimeout(() => {
    conversation.messages.push({
      id: `agent-${Date.now()}`,
      role: "agent",
      text: attachedContexts.some((context) => context.includes("Panel"))
        ? "我已经锁定你选中的分镜。接下来只修改这一张，其他已完成图片不会变化。"
        : "我先整理故事目标、角色和画面节奏，然后会在这个对话中创建一张可持续更新的漫画任务卡片。",
      time: "现在",
      activity: attachedContexts.some((context) => context.includes("Panel")) ? "正在准备单张重试" : "正在整理创作方向",
    });
    conversation.preview = attachedContexts.some((context) => context.includes("Panel")) ? "正在准备单张重试" : "正在整理创作方向";
    renderNavigation();
    renderConversation();
  }, 650);

  if (!conversation.task) {
    window.setTimeout(() => {
      conversation.task = createDemoTask(text);
      conversation.messages.push({
        id: `task-${Date.now()}`,
        role: "agent",
        text: "我已经创建漫画任务。你可以继续留在这里看进度，也可以切换到其他对话；回来后任务卡片和上下文都会保留。",
        time: "现在",
        taskId: conversation.task.id,
      });
      conversation.preview = "漫画任务已经创建，正在生成第 1 张";
      conversation.subtitle = "五格漫画 · 设计演示任务";
      renderNavigation();
      renderConversation();
    }, 1550);
  }
}

function createDemoTask(text) {
  return {
    id: `task-${Date.now()}`,
    title: text.slice(0, 22) + (text.length > 22 ? "…" : ""),
    status: "生成中",
    completed: 0,
    total: 5,
    progress: 14,
    selectedPanel: 1,
    panels: [1, 2, 3, 4, 5].map((order) => ({
      order,
      status: order === 1 ? "生成中" : "等待",
      className: order === 1 ? "running" : "waiting",
      text: order === 1 ? "Agent 正在设计第一张分镜。" : "等待前序分镜完成。",
      version: order === 1 ? "v1" : "—",
      review: order === 1 ? "正在生成画面。" : "等待前序分镜完成后开始。",
    })),
    activities: [{ text: "正在整理故事和角色上下文", time: "现在", current: true }],
  };
}

function resizeInput() {
  messageInput.style.height = "auto";
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 140)}px`;
}

function showToast(message) {
  const toast = document.querySelector("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(state.toastTimer);
  state.toastTimer = window.setTimeout(() => toast.classList.remove("show"), 1800);
}

document.querySelector("#new-chat-button").addEventListener("click", createConversation);
document.querySelector("#composer").addEventListener("submit", submitMessage);
document.querySelector("#close-inspector").addEventListener("click", closeInspector);
openCurrentTask.addEventListener("click", () => {
  if (state.inspectorOpen) closeInspector();
  else openInspector();
});

document.querySelector("#conversation-search").addEventListener("input", (event) => {
  state.query = event.target.value;
  renderNavigation();
});

messageInput.addEventListener("input", () => {
  resizeInput();
  const conversation = activeConversation();
  if (conversation) conversation.draft = messageInput.value;
  if (messageInput.value.endsWith("@")) openResourceMenu(false);
});
messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    document.querySelector("#composer").requestSubmit();
  }
});

resourceButton.addEventListener("click", () => {
  const isOpen = !resourceMenu.hidden;
  if (isOpen) closeResourceMenu();
  else openResourceMenu(true);
});

resourceSearch.addEventListener("input", () => filterResources(resourceSearch.value));
resourceSearch.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    event.stopPropagation();
    closeResourceMenu();
    messageInput.focus();
  }
});

resourceMenu.querySelectorAll("[data-resource]").forEach((button) => {
  button.addEventListener("click", () => {
    addContext(button.dataset.resource);
    closeResourceMenu();
    messageInput.focus();
  });
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".resource-menu-wrap")) {
    closeResourceMenu();
  }
});

document.querySelector("#mobile-sidebar-button").addEventListener("click", () => {
  shell.classList.add("sidebar-open");
  backdrop.hidden = false;
});

backdrop.addEventListener("click", () => {
  shell.classList.remove("sidebar-open");
  closeInspector();
});

document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    createConversation();
  }
  if (event.key === "Escape") {
    closeResourceMenu();
    shell.classList.remove("sidebar-open");
    if (state.inspectorOpen) closeInspector();
  }
});

renderNavigation();
renderConversation();
renderContexts();
restoreActiveDraft();
