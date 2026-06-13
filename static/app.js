const CHAT_STORAGE_KEY = "knowledgeqa_chat_v1";
const BRAND_STORAGE_KEY = "knowledgeqa_brand_v1";
const USER_LLM_STORAGE_KEY = "knowledgeqa_user_llm_v1";
const SESSION_STORAGE_KEY = "knowledgeqa_session_v1";
const WELCOME_SEEN_KEY = "knowledgeqa_welcome_seen_v1";
const RETRIEVAL_NOTICE_DISMISSED_KEY = "knowledgeqa_retrieval_notice_dismissed_v1";
const DEFAULT_BRAND_ICON = "/static/assets/logo.png";
const MAX_BRAND_ICON_BYTES = 256 * 1024;

const state = {
  workspaces: [],
  currentId: null,
  sending: false,
  chatHistory: loadChatHistory(),
  documents: [],
  scopedDocuments: [],
  modeInfo: null,
};

let activeChatController = null;

const brandIconBtn = document.getElementById("brand-icon-btn");
const brandIconImg = document.getElementById("brand-icon-img");
const brandIconFallback = document.getElementById("brand-icon-fallback");
const brandIconInput = document.getElementById("brand-icon-input");
const brandNameEl = document.getElementById("brand-name");
const brandNameInput = document.getElementById("brand-name-input");
const workspaceList = document.getElementById("workspace-list");
const documentList = document.getElementById("document-list");
const chatPanel = document.getElementById("chat-panel");
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const heroTitle = document.getElementById("hero-title");
const composerSendBtn = document.querySelector(".composer-send");
const chatInput = document.getElementById("chat-input");
const scopeChips = document.getElementById("scope-chips");
const mentionPicker = document.getElementById("mention-picker");
const uploadOpenBtn = document.getElementById("upload-open-btn");
const uploadDialog = document.getElementById("upload-dialog");
const uploadDialogClose = document.getElementById("upload-dialog-close");
const uploadDropzone = document.getElementById("upload-dropzone");
const uploadQueue = document.getElementById("upload-queue");
const uploadSummary = document.getElementById("upload-summary");
const fileInput = document.getElementById("file-input");

const ACCEPTED_EXTENSIONS = [
  ".txt", ".md", ".markdown", ".pdf", ".doc", ".docx",
  ".ppt", ".pptx", ".xls", ".xlsx", ".html", ".htm", ".csv", ".json", ".xml",
];

const uploadState = {
  items: [],
  running: false,
};
const llmMode = document.getElementById("llm-mode");
const clearChatBtn = document.getElementById("clear-chat-btn");
const currentWorkspaceName = document.getElementById("current-workspace-name");
const currentWorkspaceDesc = document.getElementById("current-workspace-desc");
const settingsDialog = document.getElementById("settings-dialog");
const settingsForm = document.getElementById("settings-form");
const settingsClose = document.getElementById("settings-close");
const cfgApiKey = document.getElementById("cfg-api-key");
const cfgApiKeyHint = document.getElementById("cfg-api-key-hint");
const cfgBaseUrl = document.getElementById("cfg-base-url");
const cfgModel = document.getElementById("cfg-model");
const cfgOllamaUrl = document.getElementById("cfg-ollama-url");
const cfgOllamaModel = document.getElementById("cfg-ollama-model");
const cfgClearKey = document.getElementById("cfg-clear-key");
const cfgValidateKey = document.getElementById("cfg-validate-key");
const modeBadge = document.getElementById("mode-badge");
const retrievalNotice = document.getElementById("retrieval-notice");
const retrievalNoticeBody = document.getElementById("retrieval-notice-body");
const retrievalNoticeConfig = document.getElementById("retrieval-notice-config");
const retrievalNoticeDismiss = document.getElementById("retrieval-notice-dismiss");
const demoQuotaBar = document.getElementById("demo-quota-bar");
const demoQuotaLeft = document.getElementById("demo-quota-left");
const demoQuotaText = document.getElementById("demo-quota-text");
const demoUpgradeBtn = document.getElementById("demo-upgrade-btn");
const demoPrompts = document.getElementById("demo-prompts");
const demoPromptsList = document.getElementById("demo-prompts-list");
const welcomeDialog = document.getElementById("welcome-dialog");
const welcomeTryDemo = document.getElementById("welcome-try-demo");
const welcomeConfigKey = document.getElementById("welcome-config-key");
const settingsOllamaSection = document.getElementById("settings-ollama-section");
const chunksDialog = document.getElementById("chunks-dialog");
const chunksDialogTitle = document.getElementById("chunks-dialog-title");
const chunksDialogHint = document.getElementById("chunks-dialog-hint");
const chunksList = document.getElementById("chunks-list");
const chunksClose = document.getElementById("chunks-close");
const retrievePreviewBtn = document.getElementById("retrieve-preview-btn");
const addWorkspaceBtn = document.getElementById("add-workspace-btn");
const workspaceDialog = document.getElementById("workspace-dialog");
const workspaceForm = document.getElementById("workspace-form");
const workspaceDialogTitle = document.getElementById("workspace-dialog-title");
const workspaceDialogClose = document.getElementById("workspace-dialog-close");
const wsNameInput = document.getElementById("ws-name-input");
const wsDescInput = document.getElementById("ws-desc-input");
const confirmDialog = document.getElementById("confirm-dialog");
const confirmDialogTitle = document.getElementById("confirm-dialog-title");
const confirmDialogMessage = document.getElementById("confirm-dialog-message");
const confirmDialogOk = document.getElementById("confirm-dialog-ok");
const confirmDialogCancel = document.getElementById("confirm-dialog-cancel");
const sidebar = document.getElementById("sidebar");
const sidebarBackdrop = document.getElementById("sidebar-backdrop");
const mobileMenuBtn = document.getElementById("mobile-menu-btn");
const mobileHeaderBrand = document.getElementById("mobile-header-brand");
const mobileHeaderBrandImg = document.getElementById("mobile-header-brand-img");
const sidebarRetrievePreviewBtn = document.getElementById("sidebar-retrieve-preview-btn");
const sidebarClearChatBtn = document.getElementById("sidebar-clear-chat-btn");

let confirmResolver = null;

const MOBILE_LAYOUT_QUERY = window.matchMedia("(max-width: 768px)");

function isMobileLayout() {
  return MOBILE_LAYOUT_QUERY.matches;
}

function openMobileSidebar() {
  if (!isMobileLayout() || !sidebar) return;
  sidebar.classList.add("is-open");
  if (sidebarBackdrop) {
    sidebarBackdrop.hidden = false;
    sidebarBackdrop.classList.add("is-visible");
    sidebarBackdrop.setAttribute("aria-hidden", "false");
  }
  document.body.classList.add("sidebar-open");
}

function closeMobileSidebar() {
  if (!sidebar) return;
  sidebar.classList.remove("is-open");
  if (sidebarBackdrop) {
    sidebarBackdrop.classList.remove("is-visible");
    sidebarBackdrop.setAttribute("aria-hidden", "true");
    window.setTimeout(() => {
      if (!sidebar.classList.contains("is-open")) {
        sidebarBackdrop.hidden = true;
      }
    }, 260);
  }
  document.body.classList.remove("sidebar-open");
}

function syncMobileHeaderBrand() {
  if (!mobileHeaderBrandImg || !brandIconImg) return;
  const src = brandIconImg.getAttribute("src");
  if (src) mobileHeaderBrandImg.src = src;
}

let workspaceDialogMode = { action: "create", workspaceId: null };

const mentionState = {
  active: false,
  query: "",
  start: 0,
  end: 0,
  selectedIndex: 0,
  matches: [],
};

function loadChatHistory() {
  try {
    return JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function loadBrandSettings() {
  try {
    return JSON.parse(localStorage.getItem(BRAND_STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveBrandSettings(settings) {
  localStorage.setItem(BRAND_STORAGE_KEY, JSON.stringify(settings));
}

function applyBrandSettings() {
  const settings = loadBrandSettings();
  const name = (settings.name || "知识库").trim() || "知识库";
  brandNameEl.textContent = name;
  document.title = name;

  brandIconImg.src = settings.iconDataUrl || DEFAULT_BRAND_ICON;
  brandIconImg.hidden = false;
  syncMobileHeaderBrand();
  brandIconFallback.hidden = true;
  brandIconBtn.classList.add("has-icon");
}

function startBrandNameEdit() {
  brandNameInput.value = brandNameEl.textContent.trim();
  brandNameEl.hidden = true;
  brandNameInput.hidden = false;
  brandNameInput.focus();
  brandNameInput.select();
}

function finishBrandNameEdit() {
  const name = brandNameInput.value.trim() || "知识库";
  const settings = loadBrandSettings();
  settings.name = name;
  saveBrandSettings(settings);
  brandNameInput.hidden = true;
  brandNameEl.hidden = false;
  applyBrandSettings();
}

async function handleBrandIconUpload(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    alert("请选择图片文件");
    return;
  }
  if (file.size > MAX_BRAND_ICON_BYTES) {
    alert("图标不能超过 256KB");
    return;
  }

  const reader = new FileReader();
  reader.onload = () => {
    const settings = loadBrandSettings();
    settings.iconDataUrl = reader.result;
    saveBrandSettings(settings);
    applyBrandSettings();
  };
  reader.onerror = () => alert("读取图标失败");
  reader.readAsDataURL(file);
}

function showConfirm({
  title = "确认",
  message = "",
  confirmText = "确定",
  cancelText = "取消",
  danger = false,
  alertOnly = false,
}) {
  return new Promise((resolve) => {
    confirmDialogTitle.textContent = title;
    confirmDialogMessage.textContent = message;
    confirmDialogOk.textContent = confirmText;
    confirmDialogCancel.textContent = cancelText;
    confirmDialogCancel.hidden = alertOnly;
    confirmDialogOk.classList.toggle("danger-btn", danger);
    confirmResolver = resolve;
    confirmDialog.showModal();
  });
}

function closeConfirm(result) {
  confirmDialog.close();
  if (confirmResolver) {
    confirmResolver(result);
    confirmResolver = null;
  }
}

function initConfirmDialog() {
  confirmDialogOk.addEventListener("click", () => closeConfirm(true));
  confirmDialogCancel.addEventListener("click", () => closeConfirm(false));
  confirmDialog.addEventListener("cancel", (e) => {
    e.preventDefault();
    closeConfirm(false);
  });
}

function initBrandSettings() {
  applyBrandSettings();
  brandNameEl.addEventListener("click", startBrandNameEdit);
  brandNameInput.addEventListener("blur", finishBrandNameEdit);
  brandNameInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      brandNameInput.blur();
    } else if (e.key === "Escape") {
      brandNameInput.value = brandNameEl.textContent;
      brandNameInput.blur();
    }
  });
  brandIconBtn.addEventListener("click", () => brandIconInput.click());
  brandIconInput.addEventListener("change", handleBrandIconUpload);
}

function chatHistoryEnabled() {
  return state.modeInfo?.features?.chat_history !== false;
}

function saveChatHistory() {
  if (!chatHistoryEnabled()) return;
  localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(state.chatHistory));
}

function getSessionId() {
  let id = localStorage.getItem(SESSION_STORAGE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(SESSION_STORAGE_KEY, id);
  }
  return id;
}

function loadUserLLM() {
  try {
    return JSON.parse(localStorage.getItem(USER_LLM_STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveUserLLM(config) {
  localStorage.setItem(USER_LLM_STORAGE_KEY, JSON.stringify(config));
}

function getApiHeaders(extra = {}) {
  const headers = { ...extra };
  headers["X-Session-Id"] = getSessionId();
  const user = loadUserLLM();
  if (user.apiKey) {
    headers["X-User-Api-Key"] = user.apiKey;
    if (user.baseUrl) headers["X-User-Base-Url"] = user.baseUrl;
    if (user.model) headers["X-User-Model"] = user.model;
  }
  return headers;
}

function getMessages(workspaceId = state.currentId) {
  if (!workspaceId) return [];
  return state.chatHistory[workspaceId] || [];
}

function getConversationCount(workspaceId) {
  return getMessages(workspaceId).filter((m) => m.role === "user").length;
}

function pushMessage(
  role,
  text,
  sources = null,
  mode = null,
  scopedDocument = null,
  extra = {},
  workspaceId = state.currentId
) {
  if (!workspaceId) return;
  if (!state.chatHistory[workspaceId]) {
    state.chatHistory[workspaceId] = [];
  }
  state.chatHistory[workspaceId].push({
    role,
    text,
    sources,
    mode,
    scopedDocument,
    ...extra,
  });
  saveChatHistory();
}

function abortActiveChat() {
  if (activeChatController) {
    activeChatController.abort();
    activeChatController = null;
  }
}

async function api(path, options = {}) {
  const resp = await fetch(path, {
    ...options,
    headers: getApiHeaders(options.headers || {}),
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const data = await resp.json();
      detail = data.detail || data.message || JSON.stringify(data);
    } catch (_) {}
    if (resp.status === 502) {
      detail = "服务暂时无响应（502），可能正在加载模型或内存不足，请稍后刷新";
    }
    throw new Error(detail);
  }
  return resp;
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function docFileUrl(documentId) {
  return `/api/workspaces/${state.currentId}/documents/${documentId}/file`;
}

function getChatScrollContainer() {
  return chatLog;
}

function scrollChatToBottom(instant = false) {
  const container = getChatScrollContainer();
  const scroll = () => {
    container.scrollTop = container.scrollHeight;
  };
  if (instant) {
    container.classList.add("no-smooth");
    scroll();
    requestAnimationFrame(() => {
      scroll();
      container.classList.remove("no-smooth");
    });
    return;
  }
  requestAnimationFrame(scroll);
}

function formatSnippet(snippet) {
  const clean = String(snippet).replace(/\s+/g, " ").trim();
  if (clean.length <= 160) return clean;
  return `${clean.slice(0, 160)}…`;
}

function cleanSnippetForDisplay(snippet, maxChars = 280) {
  let text = String(snippet || "").trim();
  if (!text) return "";

  text = text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1");

  const lines = [];
  for (const rawLine of text.split("\n")) {
    let line = rawLine.trim();
    if (!line || /^[-|:\s]+$/.test(line)) continue;
    if ((line.match(/\|/g) || []).length >= 2) continue;
    if (line.startsWith("#")) line = `• ${line.replace(/^#+\s*/, "")}`;
    else if (/^[-*+]\s+/.test(line)) line = `  • ${line.replace(/^[-*+]\s+/, "")}`;
    else if (/^\d+\.\s+/.test(line)) line = `  • ${line.replace(/^\d+\.\s+/, "")}`;
    lines.push(line);
  }

  let result = lines.join("\n");
  if (result.length > maxChars) {
    result = `${result.slice(0, maxChars).trim()}…`;
  }
  return result || formatSnippet(snippet);
}

function renderMarkdown(text) {
  const source = String(text || "");
  if (!source) return "";

  if (typeof marked === "undefined") {
    return escapeHtml(source).replaceAll("\n", "<br>");
  }

  marked.setOptions({
    breaks: true,
    gfm: true,
  });

  let html = marked.parse(source);
  html = html.replace(/\[(\d+)\]/g, '<sup class="citation">[$1]</sup>');
  if (typeof DOMPurify !== "undefined") {
    return DOMPurify.sanitize(html, { ADD_TAGS: ["sup"] });
  }
  return html;
}

function setMessageBody(bodyEl, text, role, mode = null) {
  if (role === "bot") {
    if (mode === "retrieval") {
      bodyEl.classList.remove("markdown-body");
      bodyEl.classList.add("retrieval-body");
      bodyEl.textContent = text;
    } else {
      bodyEl.classList.remove("retrieval-body");
      bodyEl.classList.add("markdown-body");
      bodyEl.innerHTML = renderMarkdown(text);
    }
  } else {
    bodyEl.classList.remove("markdown-body", "retrieval-body");
    bodyEl.textContent = text;
  }
}

function closeChunksDialog() {
  if (chunksDialog.open) {
    chunksDialog.close();
  }
}

function scrollToChunk(chunkIndex) {
  const target = document.getElementById(`chunk-${chunkIndex}`);
  if (!target) return;
  chunksList.querySelectorAll(".chunk-card").forEach((card) => card.classList.remove("highlight"));
  target.classList.add("highlight");
  target.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderChunkCards(chunks, options = {}) {
  const { highlightIndex = null, titlePrefix = "片段", onChunkClick = null } = options;
  chunksList.innerHTML = "";

  if (!chunks.length) {
    chunksList.innerHTML = `<div class="meta">暂无片段</div>`;
    return;
  }

  chunks.forEach((chunk) => {
    const text = chunk.text ?? chunk.snippet ?? "";
    const card = document.createElement("article");
    card.className = "chunk-card";
    if (highlightIndex !== null && Number(chunk.chunk_index) === Number(highlightIndex)) {
      card.classList.add("highlight");
    }
    card.id = `chunk-${chunk.chunk_index}`;

    const head = document.createElement("div");
    head.className = "chunk-card-head";
    const path = chunk.heading_path ? `<div class="chunk-path">${escapeHtml(chunk.heading_path)}</div>` : "";
    const summary = chunk.summary ? `<div class="chunk-summary">${escapeHtml(chunk.summary)}</div>` : "";
    head.innerHTML = `
      <div class="chunk-card-title">
        <strong>${titlePrefix} #${chunk.chunk_index + 1}</strong>
        ${path}
        ${summary}
      </div>
      <span class="chunk-card-meta muted">${chunk.char_count || text.length} 字</span>
    `;
    head.onclick = () => scrollToChunk(chunk.chunk_index);

    const body = document.createElement("div");
    body.className = "chunk-card-body";
    body.textContent = text || "（该片段暂无文本内容）";
    body.onclick = () => {
      scrollToChunk(chunk.chunk_index);
      if (onChunkClick) onChunkClick(chunk);
    };

    card.appendChild(head);
    card.appendChild(body);
    chunksList.appendChild(card);
  });

  if (highlightIndex !== null) {
    requestAnimationFrame(() => scrollToChunk(highlightIndex));
  } else {
    chunksList.scrollTop = 0;
  }
}

async function openDocumentChunks(documentId, filename, highlightIndex = null) {
  const resp = await api(`/api/workspaces/${state.currentId}/documents/${documentId}/chunks`);
  const chunks = await resp.json();
  chunksDialogTitle.textContent = `《${filename}》`;
  chunksDialogHint.textContent = `共 ${chunks.length} 个片段 · 含章节路径与 AI 摘要 · 点击片段可定位`;
  renderChunkCards(chunks, { highlightIndex });
  if (!chunksDialog.open) {
    chunksDialog.showModal();
  }
  if (highlightIndex !== null) {
    requestAnimationFrame(() => scrollToChunk(highlightIndex));
  }
}

async function openRetrievePreview(query, documentIds = null) {
  const resp = await api(`/api/workspaces/${state.currentId}/retrieve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, document_ids: documentIds }),
  });
  const data = await resp.json();
  chunksDialogTitle.textContent = "检索预览";
  chunksDialogHint.textContent = `问题：${data.query} · 命中 ${data.hits.length} 个片段（模型实际参考这些文本）`;

  const chunks = data.hits.map((hit, idx) => ({
    chunk_index: hit.chunk_index,
    char_count: hit.snippet.length,
    text: `[命中 ${idx + 1}] ${hit.relevance}\n综合 ${Math.round(hit.score * 100)}% · 向量 ${Math.round((hit.semantic_score || 0) * 100)}% · 关键词 ${Math.round((hit.keyword_score || 0) * 100)}%${hit.rerank_score != null ? ` · 重排 ${Math.round(hit.rerank_score * 100)}%` : ""}\n章节: ${hit.heading_path || "无"}\n摘要: ${hit.summary || "无"}\n《${hit.document}》片段 #${hit.chunk_index + 1}\n\n${hit.snippet}`,
    document_id: hit.document_id,
    filename: hit.document,
  }));
  renderChunkCards(chunks, {
    titlePrefix: "命中片段",
    onChunkClick: (chunk) => {
      if (chunk.document_id) {
        openDocumentChunks(chunk.document_id, chunk.filename, chunk.chunk_index);
      }
    },
  });
  if (!chunksDialog.open) {
    chunksDialog.showModal();
  }
}

function extractCitedSourceIndices(text) {
  const indices = new Set();
  if (!text) return indices;

  for (const match of text.matchAll(/资料\s*(\d+)/g)) {
    indices.add(Number.parseInt(match[1], 10));
  }
  for (const match of text.matchAll(/\[(\d+)\]/g)) {
    indices.add(Number.parseInt(match[1], 10));
  }
  return indices;
}

function filterCitedSources(sources, answerText) {
  if (!sources?.length) return [];
  const cited = extractCitedSourceIndices(answerText);
  if (!cited.size) return [];

  return sources
    .map((src, idx) => ({ ...src, sourceIndex: src.sourceIndex ?? idx + 1 }))
    .filter((src) => cited.has(src.sourceIndex));
}

function resolveDisplayedSources(sources, answerText, mode) {
  if (!sources?.length) return [];
  if (mode === "retrieval") {
    return sources.map((src, idx) => ({ ...src, sourceIndex: idx + 1 }));
  }
  return filterCitedSources(sources, answerText);
}

function buildSourceBlock(sources) {
  const block = document.createElement("div");
  block.className = "sources";
  block.innerHTML = "<h4>引用来源</h4>";

  (sources || []).forEach((src) => {
    const displayIndex = src.sourceIndex ?? 0;
    const item = document.createElement("div");
    item.className = "source-item";

    const chunkNo = Number.isInteger(src.chunk_index) ? src.chunk_index + 1 : "?";
    const relevance = src.relevance || "相关";
    const jumpToChunk = src.document_id
      ? () => openDocumentChunks(src.document_id, src.document, src.chunk_index)
      : null;

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "source-toggle";
    toggle.innerHTML = `<span class="source-chevron">▸</span><span class="source-brief">[${displayIndex}] ${escapeHtml(src.document)} · 片段 #${chunkNo}</span>`;

    const details = document.createElement("div");
    details.className = "source-details";
    details.hidden = true;

    const meta = document.createElement("div");
    meta.className = "source-meta-line" + (relevance === "低相关" ? " low" : "");
    const sem = src.semantic_score != null ? `向量 ${Math.round(src.semantic_score * 100)}%` : "";
    const kw = src.keyword_score != null ? `关键词 ${Math.round(src.keyword_score * 100)}%` : "";
    const rr = src.rerank_score != null ? `重排 ${Math.round(src.rerank_score * 100)}%` : "";
    meta.textContent = [relevance, `综合 ${Math.round((src.score || 0) * 100)}%`, sem, kw, rr].filter(Boolean).join(" · ");
    details.appendChild(meta);

    if (src.heading_path) {
      const pathLine = document.createElement("div");
      pathLine.className = "source-path";
      pathLine.textContent = `章节: ${src.heading_path}`;
      details.appendChild(pathLine);
    }
    if (src.summary) {
      const sumLine = document.createElement("div");
      sumLine.className = "source-summary";
      sumLine.textContent = `摘要: ${src.summary}`;
      details.appendChild(sumLine);
    }

    const excerpt = document.createElement("div");
    excerpt.className = "source-excerpt";
    excerpt.textContent = cleanSnippetForDisplay(src.snippet);
    details.appendChild(excerpt);

    if (jumpToChunk) {
      const jumpBtn = document.createElement("button");
      jumpBtn.type = "button";
      jumpBtn.className = "linkish-btn source-jump-btn";
      jumpBtn.textContent = "查看片段";
      jumpBtn.onclick = (e) => {
        e.stopPropagation();
        jumpToChunk();
      };
      details.appendChild(jumpBtn);
    }

    toggle.onclick = () => {
      const opening = details.hidden;
      details.hidden = !opening;
      item.classList.toggle("expanded", opening);
      toggle.querySelector(".source-chevron").textContent = opening ? "▾" : "▸";
    };

    item.appendChild(toggle);
    item.appendChild(details);
    block.appendChild(item);
  });

  return block;
}

function renderMessage(msg) {
  const div = document.createElement("div");
  div.className = `message ${msg.role}`;

  if (msg.role === "user" && msg.scopedDocument) {
    const scopeTag = document.createElement("div");
    scopeTag.className = "msg-scope-tag";
    scopeTag.textContent = `@ ${msg.scopedDocument}`;
    div.appendChild(scopeTag);
  }

  const body = document.createElement("div");
  body.className = "message-body";
  setMessageBody(body, msg.text, msg.role, msg.mode);
  div.appendChild(body);

  if (msg.role === "bot" && msg.sources && msg.sources.length) {
    const cited = resolveDisplayedSources(msg.sources, msg.text, msg.mode);
    if (cited.length) {
      div.appendChild(buildSourceBlock(cited));
    }
  }

  if (msg.role === "bot" && msg.demoTip) {
    div.appendChild(buildDemoUpgradeTip());
  }

  chatLog.appendChild(div);
}

function buildDemoUpgradeTip() {
  const tip = document.createElement("div");
  tip.className = "demo-upgrade-tip";
  tip.innerHTML =
    '演示模式响应较慢、功能受限。<button type="button" class="text-btn demo-tip-upgrade">配置 API Key</button>可获得更快速度与完整功能。';
  tip.querySelector(".demo-tip-upgrade").onclick = openSettings;
  return tip;
}

function updateHeroTitle() {
  const hasMessages = getMessages().length > 0 || state.sending;
  if (hasMessages) return;

  const ws = state.workspaces.find((w) => w.id === state.currentId);
  heroTitle.textContent = ws
    ? `我们应该从「${ws.name}」了解什么？`
    : "我们应该了解什么？";
}

function updateChatLayout() {
  const hasMessages = getMessages().length > 0 || state.sending;
  chatPanel.classList.toggle("chat-empty", !hasMessages);
  chatPanel.classList.toggle("chat-active", hasMessages);

  if (!hasMessages) {
    chatPanel.scrollTop = 0;
    updateHeroTitle();
  }
}

function renderChatLog(options = {}) {
  const { instantScroll = false } = options;
  chatLog.innerHTML = "";
  getMessages().forEach(renderMessage);
  updateChatLayout();
  if (getMessages().length > 0 || state.sending) {
    scrollChatToBottom(instantScroll);
  }
}

function setComposerDisabled(disabled) {
  if (composerSendBtn) composerSendBtn.disabled = disabled;
}

function addDocumentScope(documentId, filename) {
  if (state.scopedDocuments.some((doc) => doc.id === documentId)) return;
  state.scopedDocuments.push({ id: documentId, filename });
  updateScopeChips();
  chatInput.focus();
}

function removeDocumentScope(documentId) {
  state.scopedDocuments = state.scopedDocuments.filter((doc) => doc.id !== documentId);
  updateScopeChips();
}

function clearDocumentScope() {
  state.scopedDocuments = [];
  updateScopeChips();
}

function updateScopeChips() {
  scopeChips.innerHTML = "";
  if (!state.scopedDocuments.length) {
    scopeChips.hidden = true;
    if (state.documents.length) renderDocuments(state.documents);
    return;
  }

  scopeChips.hidden = false;
  const label = document.createElement("span");
  label.className = "scope-chips-label";
  label.textContent = "仅提问";
  scopeChips.appendChild(label);

  state.scopedDocuments.forEach((doc) => {
    const chip = document.createElement("span");
    chip.className = "scope-chip";
    const name = document.createElement("strong");
    name.textContent = doc.filename;
    name.title = doc.filename;
    const clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "scope-chip-clear";
    clearBtn.title = "移除";
    clearBtn.textContent = "✕";
    clearBtn.onclick = () => removeDocumentScope(doc.id);
    chip.appendChild(name);
    chip.appendChild(clearBtn);
    scopeChips.appendChild(chip);
  });
  if (state.documents.length) renderDocuments(state.documents);
}

function resolveScopedQuestion(text) {
  const documentIds = state.scopedDocuments.map((doc) => doc.id);
  const documentNames = state.scopedDocuments.map((doc) => doc.filename).join("、");
  return {
    documentIds: documentIds.length ? documentIds : null,
    documentNames: documentNames || null,
    displayText: text,
    question: text,
  };
}

function getMentionContext() {
  const value = chatInput.value;
  const cursor = chatInput.selectionStart ?? value.length;
  const before = value.slice(0, cursor);
  const at = before.lastIndexOf("@");
  if (at < 0) return null;
  const between = before.slice(at + 1);
  if (/\s/.test(between)) return null;
  return { start: at, end: cursor, query: between };
}

function hideMentionPicker() {
  mentionState.active = false;
  mentionState.matches = [];
  mentionPicker.hidden = true;
  mentionPicker.innerHTML = "";
}

function filterMentionDocuments(query) {
  const selected = new Set(state.scopedDocuments.map((doc) => doc.id));
  const available = state.documents.filter((doc) => !selected.has(doc.id));
  const q = query.toLowerCase();
  if (!q) return available.slice(0, 8);
  return available
    .filter((doc) => doc.filename.toLowerCase().includes(q))
    .slice(0, 8);
}

function renderMentionPicker() {
  if (!mentionState.active || !mentionState.matches.length) {
    hideMentionPicker();
    return;
  }

  mentionPicker.innerHTML = "";
  mentionState.matches.forEach((doc, idx) => {
    const li = document.createElement("li");
    li.className = idx === mentionState.selectedIndex ? "active" : "";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.innerHTML = `${escapeHtml(doc.filename)}<span class="mention-meta">${formatSize(doc.size)} · ${doc.chunk_count} 片段</span>`;
    btn.onclick = () => applyMentionSelection(doc);
    li.appendChild(btn);
    mentionPicker.appendChild(li);
  });
  mentionPicker.hidden = false;
}

function applyMentionSelection(doc) {
  const value = chatInput.value;
  const before = value.slice(0, mentionState.start);
  const after = value.slice(mentionState.end);
  chatInput.value = `${before}${after}`;
  const cursor = before.length;
  chatInput.setSelectionRange(cursor, cursor);
  addDocumentScope(doc.id, doc.filename);
  hideMentionPicker();
  chatInput.focus();
}

function updateMentionPicker() {
  const ctx = getMentionContext();
  if (!ctx || !state.documents.length) {
    hideMentionPicker();
    return;
  }

  mentionState.active = true;
  mentionState.query = ctx.query;
  mentionState.start = ctx.start;
  mentionState.end = ctx.end;
  mentionState.matches = filterMentionDocuments(ctx.query);
  mentionState.selectedIndex = 0;
  renderMentionPicker();
}

function handleChatInputKeydown(event) {
  const mentionOpen =
    mentionState.active && !mentionPicker.hidden && mentionState.matches.length > 0;

  if (mentionOpen) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      mentionState.selectedIndex = (mentionState.selectedIndex + 1) % mentionState.matches.length;
      renderMentionPicker();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      mentionState.selectedIndex =
        (mentionState.selectedIndex - 1 + mentionState.matches.length) % mentionState.matches.length;
      renderMentionPicker();
    } else if (event.key === "Enter" || event.key === "Tab") {
      event.preventDefault();
      const doc = mentionState.matches[mentionState.selectedIndex];
      if (doc) applyMentionSelection(doc);
    } else if (event.key === "Escape") {
      event.preventDefault();
      hideMentionPicker();
    }
    return;
  }

  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
}

function openWorkspaceDialog(action, workspace = null) {
  workspaceDialogMode = { action, workspaceId: workspace?.id || null };
  workspaceDialogTitle.textContent = action === "create" ? "新建资料库" : "重命名资料库";
  wsNameInput.value = workspace?.name || "";
  wsDescInput.value = workspace?.description || "";
  workspaceDialog.showModal();
  wsNameInput.focus();
}

async function saveWorkspaceDialog(event) {
  event.preventDefault();
  const name = wsNameInput.value.trim();
  const description = wsDescInput.value.trim();
  if (!name) return;

  try {
    if (workspaceDialogMode.action === "create") {
      const resp = await api("/api/workspaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description }),
      });
      const ws = await resp.json();
      state.currentId = ws.id;
    } else {
      await api(`/api/workspaces/${workspaceDialogMode.workspaceId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description }),
      });
    }
    workspaceDialog.close();
    await loadWorkspaces();
  } catch (err) {
    alert(`保存失败: ${err.message}`);
  }
}

async function removeWorkspace(workspaceId) {
  const ws = state.workspaces.find((w) => w.id === workspaceId);
  if (!ws) return;

  const ok = await showConfirm({
    title: "删除资料库",
    message: `确定删除资料库「${ws.name}」？其中的文档和向量数据将一并删除。`,
    confirmText: "删除",
    cancelText: "取消",
    danger: true,
  });
  if (!ok) return;

  try {
    await api(`/api/workspaces/${workspaceId}`, { method: "DELETE" });
    delete state.chatHistory[workspaceId];
    saveChatHistory();
    if (state.currentId === workspaceId) {
      state.currentId = null;
    }
    await loadWorkspaces();
  } catch (err) {
    await showConfirm({
      title: "删除失败",
      message: err.message,
      confirmText: "知道了",
      alertOnly: true,
    });
  }
}

function renderWorkspaces() {
  workspaceList.innerHTML = "";
  if (!state.workspaces.length) {
    workspaceList.innerHTML = `<div class="meta workspace-empty">暂无资料库，点击右上角 + 新建</div>`;
    return;
  }

  state.workspaces.forEach((ws) => {
    const row = document.createElement("div");
    row.className = "workspace-row" + (ws.id === state.currentId ? " active" : "");

    const item = document.createElement("div");
    item.className = "workspace-item";

    const main = document.createElement("button");
    main.type = "button";
    main.className = "workspace-main";
    const msgCount = getConversationCount(ws.id);
    main.innerHTML = `
      <div class="name">${escapeHtml(ws.name)}</div>
      <div class="meta">${ws.document_count || 0} 文档 · ${msgCount} 对话</div>
    `;
    main.onclick = () => {
      if (ws.id !== state.currentId) {
        selectWorkspace(ws.id);
      }
      closeMobileSidebar();
    };

    const actions = document.createElement("div");
    actions.className = "workspace-actions";

    const renameBtn = document.createElement("button");
    renameBtn.type = "button";
    renameBtn.className = "icon-btn workspace-action-btn";
    renameBtn.title = "重命名";
    renameBtn.textContent = "✎";
    renameBtn.onclick = (e) => {
      e.stopPropagation();
      openWorkspaceDialog("rename", ws);
    };

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "icon-btn workspace-action-btn danger";
    deleteBtn.title = "删除";
    deleteBtn.textContent = "✕";
    deleteBtn.onclick = (e) => {
      e.stopPropagation();
      removeWorkspace(ws.id);
    };

    actions.appendChild(renameBtn);
    actions.appendChild(deleteBtn);
    item.appendChild(main);
    item.appendChild(actions);
    row.appendChild(item);
    workspaceList.appendChild(row);
  });
}

function fileTypeLabel(filename) {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  if (["pdf"].includes(ext)) return "PDF";
  if (["doc", "docx"].includes(ext)) return "DOC";
  if (["ppt", "pptx"].includes(ext)) return "PPT";
  if (["xls", "xlsx"].includes(ext)) return "XLS";
  if (["md", "markdown"].includes(ext)) return "MD";
  return ext.toUpperCase().slice(0, 3) || "FILE";
}

function renderDocuments(docs) {
  state.documents = docs;
  documentList.innerHTML = "";
  if (!docs.length) {
    const li = document.createElement("li");
    li.className = "project-empty";
    li.textContent = "暂无文件，点击 + 上传文档";
    documentList.appendChild(li);
    return;
  }

  const scopedIds = new Set(state.scopedDocuments.map((d) => d.id));

  docs.forEach((doc) => {
    const li = document.createElement("li");
    li.className = "project-item" + (scopedIds.has(doc.id) ? " active-scope" : "");

    const icon = document.createElement("span");
    icon.className = "project-icon";
    icon.textContent = fileTypeLabel(doc.filename);

    const body = document.createElement("div");
    body.className = "project-body";

    const nameBtn = document.createElement("button");
    nameBtn.type = "button";
    nameBtn.className = "project-name";
    nameBtn.textContent = doc.filename;
    nameBtn.title = "查看片段";
    nameBtn.onclick = () => {
      if (doc.status === "processing") {
        showConfirm({
          title: "处理中",
          message: "文档正在后台解析与向量化，请稍候再查看片段。",
          confirmText: "知道了",
          alertOnly: true,
        });
        return;
      }
      if (doc.status === "error") {
        showConfirm({
          title: "入库失败",
          message: doc.error_message || "文档未能成功入库，请删除后重新上传。",
          confirmText: "知道了",
          alertOnly: true,
        });
        return;
      }
      openDocumentChunks(doc.id, doc.filename);
    };

    const meta = document.createElement("div");
    meta.className = "project-meta";
    if (doc.status === "processing") {
      meta.textContent = `${formatSize(doc.size)} · 处理中…`;
    } else if (doc.status === "error") {
      meta.textContent = `${formatSize(doc.size)} · 入库失败`;
      meta.title = doc.error_message || "入库失败";
    } else {
      meta.textContent = `${formatSize(doc.size)} · ${doc.chunk_count} 片段`;
    }

    body.appendChild(nameBtn);
    body.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "project-actions";

    const askBtn = document.createElement("button");
    askBtn.type = "button";
    askBtn.className = "project-action-btn";
    askBtn.title = "@ 提问";
    askBtn.textContent = "@";
    askBtn.onclick = () => {
      addDocumentScope(doc.id, doc.filename);
      renderDocuments(state.documents);
      chatInput.focus();
    };

    const downloadBtn = document.createElement("button");
    downloadBtn.type = "button";
    downloadBtn.className = "project-action-btn";
    downloadBtn.title = "下载原文件";
    downloadBtn.textContent = "↓";
    downloadBtn.onclick = () => {
      const a = document.createElement("a");
      a.href = docFileUrl(doc.id);
      a.download = doc.filename;
      a.target = "_blank";
      a.rel = "noopener";
      a.click();
    };

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "project-action-btn";
    delBtn.title = "删除";
    delBtn.textContent = "✕";
    delBtn.onclick = () => removeDocument(doc.id);

    actions.appendChild(askBtn);
    actions.appendChild(downloadBtn);
    actions.appendChild(delBtn);

    li.appendChild(icon);
    li.appendChild(body);
    li.appendChild(actions);
    documentList.appendChild(li);
  });
}

function isKeywordEmbeddingBackend(info) {
  return String(info?.embedding_backend || "").includes("关键词");
}

function buildRetrievalNoticeHtml(info) {
  const reason = info?.retrieval_reason;
  const keyword = isKeywordEmbeddingBackend(info);
  const parts = [];

  if (reason === "no_demo_key") {
    parts.push(
      "<p><strong>为什么点了「免费试用」仍是检索模式？</strong></p>",
      "<p>欢迎页按钮只会加载示例资料库，<strong>不会自动开启演示 AI</strong>。需要管理员在服务器配置 <code>DEMO_API_KEY</code> 并重新部署后，访客才会自动进入演示模式。</p>"
    );
  } else {
    parts.push(
      "<p>当前没有可用的大模型 Key（服务端演示与本机 Key 均未生效），因此只能展示检索结果。</p>"
    );
  }

  parts.push(
    "<p><strong>为什么回答难以阅读？</strong></p>",
    "<ul>",
    "<li>检索模式<strong>不调用大模型</strong>，只把匹配到的原文片段拼在一起，没有自然语言总结</li>"
  );
  if (keyword) {
    parts.push(
      "<li>当前部署使用<strong>轻量关键词检索</strong>（为节省内存），语义理解弱，匹配可能不精准</li>"
    );
  }
  parts.push(
    "<li>片段来自 Markdown 文档，已做简化排版，但仍不如 AI 整理后的回答易读</li>",
    "</ul>",
    "<p><strong>如何获得完整体验？</strong> 点击「配置 API Key」使用自己的 Key；或请管理员在 Railway Variables 设置 <code>DEMO_API_KEY</code> 后 Redeploy。</p>"
  );

  return parts.join("");
}

function updateRetrievalNotice(info) {
  if (!retrievalNotice || !retrievalNoticeBody) return;
  const show =
    info?.tier === "retrieval" &&
    !info?.has_user_api_key &&
    localStorage.getItem(RETRIEVAL_NOTICE_DISMISSED_KEY) !== "1";
  retrievalNotice.hidden = !show;
  if (show) {
    retrievalNoticeBody.innerHTML = buildRetrievalNoticeHtml(info);
  }
}

function updateModeUI() {
  const info = state.modeInfo;
  if (!info) return;

  const quota = info.demo_quota;
  const label = info.provider_label || info.tier;
  llmMode.title = `当前：${label} · 点击配置`;

  const footerLabel = llmMode.querySelector(".footer-btn-label");
  if (footerLabel) {
    if (info.tier === "full") footerLabel.textContent = "完整模式";
    else if (info.tier === "demo") {
      if (info.demo_blocked) footerLabel.textContent = "演示模式 · 今日已用完";
      else footerLabel.textContent = quota ? `演示模式 · 余${quota.remaining}次` : "演示模式";
    } else footerLabel.textContent = "检索模式";
  }

  if (modeBadge) {
    if (info.tier === "demo") {
      modeBadge.hidden = false;
      modeBadge.textContent = info.demo_blocked ? "演示已用完" : "演示模式";
      modeBadge.className = "mode-badge" + (info.demo_blocked ? " mode-exhausted" : "");
    } else if (info.tier === "full") {
      modeBadge.hidden = false;
      modeBadge.textContent = "完整模式";
      modeBadge.className = "mode-badge mode-full";
    } else {
      modeBadge.hidden = false;
      modeBadge.textContent = "检索模式";
      modeBadge.className = "mode-badge mode-retrieval";
    }
  }

  const showQuota = !!quota && !info.has_user_api_key && info.tier === "demo";
  if (demoQuotaBar) {
    demoQuotaBar.hidden = !showQuota;
    demoQuotaBar.style.display = showQuota ? "" : "none";
    demoQuotaBar.classList.toggle("demo-quota-exhausted", !!info.demo_blocked);
  }
  if (showQuota && demoQuotaText) {
    if (info.demo_blocked) {
      demoQuotaText.textContent = `今日演示次数已用完（${quota.daily_limit} 次/天），提问将无法调用 AI`;
    } else {
      demoQuotaText.innerHTML = `您今日还可试用 <strong id="demo-quota-left">${quota.remaining}</strong> 次`;
    }
  }

  updateRetrievalNotice(info);

  if (info.startup_ready === false) {
    chatInput.placeholder = "系统正在加载嵌入模型，请稍候再提问或上传…";
    if (uploadOpenBtn) uploadOpenBtn.disabled = true;
  } else if (uploadOpenBtn) {
    uploadOpenBtn.disabled = false;
  }

  const canPreview = info.features?.retrieve_preview !== false;
  retrievePreviewBtn.disabled = !canPreview;
  retrievePreviewBtn.classList.toggle("locked-feature", !canPreview);
  retrievePreviewBtn.title = canPreview
    ? "检索预览"
    : "演示模式不可用，配置 API Key 解锁";

  const maxChars = info.tier === "demo" ? info.limits?.demo_max_chars : null;
  if (maxChars) {
    chatInput.maxLength = maxChars;
    chatInput.placeholder = `输入内容（演示模式最多 ${maxChars} 字），@ 可指定文档`;
  } else {
    chatInput.removeAttribute("maxlength");
    chatInput.placeholder = "输入内容，@ 可指定文档";
  }

  if (settingsOllamaSection) {
    settingsOllamaSection.hidden = info.tier !== "full";
  }

  if (demoPrompts) {
    const showPrompts =
      info.tier === "demo" && !getMessages().length && !state.sending;
    demoPrompts.hidden = !showPrompts;
    if (showPrompts) {
      renderDemoPrompts();
    }
  }
}

function renderDemoPrompts() {
  if (!demoPromptsList) return;
  const catalog = state.modeInfo?.demo_catalog;
  const prompts = catalog?.prompts || [];
  demoPromptsList.innerHTML = "";
  prompts.forEach((prompt) => {
    const ws = state.workspaces.find((w) => w.id === prompt.workspace_id);
    const wsName = ws?.name || "资料库";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "demo-prompt-btn";
    const label = prompt.label || prompt.question;
    btn.textContent = label;
    btn.title = `${wsName}：${prompt.question}`;
    btn.onclick = () => applyDemoPrompt(prompt);
    demoPromptsList.appendChild(btn);
  });
}

async function applyDemoPrompt(prompt) {
  if (!prompt?.question) return;
  if (state.sending) return;
  if (prompt.workspace_id && prompt.workspace_id !== state.currentId) {
    await selectWorkspace(prompt.workspace_id);
  }
  chatInput.value = prompt.question;
  hideMentionPicker();
  updateModeUI();
  chatInput.focus();
}

async function setupDemoExperience() {
  if (state.modeInfo?.tier !== "demo") return;

  const resp = await api("/api/demo/ensure", { method: "POST" });
  const data = await resp.json();
  if (data.catalog) {
    state.modeInfo.demo_catalog = data.catalog;
  }

  const targetId = data.default_workspace_id || "ws_tech";
  await loadWorkspaces();

  if (targetId && state.currentId !== targetId) {
    await selectWorkspace(targetId);
  } else {
    await loadDocuments();
    updateHeader();
  }

  if (!getMessages().length && !chatInput.value.trim()) {
    chatInput.value = data.default_question || "系统使用什么向量数据库？";
  }

  renderDemoPrompts();
  updateModeUI();
  chatInput.focus();
}

async function loadModeInfo() {
  const resp = await api("/api/mode");
  state.modeInfo = await resp.json();
  updateModeUI();
  return state.modeInfo;
}

async function loadHealth() {
  await loadModeInfo();
}

async function openSettings() {
  closeMobileSidebar();
  const resp = await api("/api/settings");
  const serverDefaults = await resp.json();
  const user = loadUserLLM();

  cfgApiKey.value = user.apiKey || "";
  cfgApiKey.placeholder = user.apiKey ? "已保存在本机，可修改" : "sk-...";
  const tier = state.modeInfo?.tier;
  const tierHint =
    tier === "full"
      ? "完整模式（本机 Key）"
      : tier === "demo"
        ? "演示模式（未配置本机 Key）"
        : "检索模式";
  cfgApiKeyHint.textContent = user.apiKey
    ? `本机已配置 Key（${maskKey(user.apiKey)}）· ${tierHint}`
    : `未配置本机 Key · 当前：${tierHint}`;
  cfgApiKeyHint.style.color = "";
  cfgBaseUrl.value = user.baseUrl || serverDefaults.openai_base_url || "";
  cfgModel.value = user.model || serverDefaults.openai_model || "";
  cfgOllamaUrl.value = serverDefaults.ollama_base_url || "";
  cfgOllamaModel.value = serverDefaults.ollama_model || "";
  settingsDialog.showModal();
}

function maskKey(key) {
  if (!key || key.length <= 8) return "****";
  return `${key.slice(0, 4)}****${key.slice(-4)}`;
}

async function validateUserKey() {
  const apiKey = cfgApiKey.value.trim();
  if (!apiKey) {
    await showConfirm({
      title: "提示",
      message: "请先输入 API Key",
      confirmText: "知道了",
      alertOnly: true,
    });
    return;
  }
  cfgValidateKey.disabled = true;
  cfgValidateKey.textContent = "验证中…";
  try {
    const resp = await api("/api/settings/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: apiKey,
        base_url: cfgBaseUrl.value.trim() || "https://api.deepseek.com/v1",
        model: cfgModel.value.trim() || "deepseek-chat",
      }),
    });
    const data = await resp.json();
    cfgApiKeyHint.textContent = data.message;
    cfgApiKeyHint.style.color = data.ok ? "var(--accent-green)" : "var(--danger)";
  } catch (err) {
    cfgApiKeyHint.textContent = err.message;
    cfgApiKeyHint.style.color = "var(--danger)";
  } finally {
    cfgValidateKey.disabled = false;
    cfgValidateKey.textContent = "验证 Key";
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const apiKey = cfgApiKey.value.trim();
  const config = {
    apiKey,
    baseUrl: cfgBaseUrl.value.trim() || "https://api.deepseek.com/v1",
    model: cfgModel.value.trim() || "deepseek-chat",
  };

  if (!apiKey) {
    await showConfirm({
      title: "提示",
      message: "请输入 API Key，或点击「清除 Key」使用演示模式",
      confirmText: "知道了",
      alertOnly: true,
    });
    return;
  }

  cfgValidateKey.disabled = true;
  cfgValidateKey.textContent = "验证中…";
  let validated = false;
  try {
    const valResp = await fetch("/api/settings/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: apiKey,
        base_url: config.baseUrl,
        model: config.model,
      }),
    });
    const valData = await valResp.json();
    if (!valData.ok) {
      cfgApiKeyHint.textContent = valData.message;
      cfgApiKeyHint.style.color = "var(--danger)";
      await showConfirm({
        title: "Key 验证失败",
        message: valData.message || "请检查 API Key、Base URL 与模型名称",
        confirmText: "知道了",
        alertOnly: true,
      });
      return;
    }
    validated = true;
  } catch (err) {
    await showConfirm({
      title: "验证失败",
      message: err.message,
      confirmText: "知道了",
      alertOnly: true,
    });
    return;
  } finally {
    cfgValidateKey.disabled = false;
    cfgValidateKey.textContent = "验证 Key";
  }
  if (!validated) return;

  saveUserLLM(config);
  localStorage.setItem(WELCOME_SEEN_KEY, "1");
  settingsDialog.close();
  await loadModeInfo();
  updateModeUI();
  await showConfirm({
    title: "已保存",
    message: "API Key 已保存到本机浏览器。完整模式已启用。",
    confirmText: "好的",
    alertOnly: true,
  });
}

async function clearApiKey() {
  const ok = await showConfirm({
    title: "清除 API Key",
    message: "确定清除本机保存的 API Key？清除后将回退到演示模式或检索模式。",
    confirmText: "清除",
    cancelText: "取消",
    danger: true,
  });
  if (!ok) return;
  saveUserLLM({});
  cfgApiKey.value = "";
  cfgApiKey.placeholder = "sk-...";
  cfgApiKeyHint.textContent = "API Key 已清除";
  cfgApiKeyHint.style.color = "";
  await loadModeInfo();
  updateModeUI();
  if (state.modeInfo?.tier === "demo") {
    await setupDemoExperience();
  }
  await showConfirm({
    title: "已清除",
    message: state.modeInfo?.tier === "demo"
      ? "已清除本机 Key，当前为演示模式。"
      : "已清除本机 Key，当前为检索模式。可点击「免费试用」或重新配置 Key。",
    confirmText: "知道了",
    alertOnly: true,
  });
}

async function ensureDemoExperienceIfNeeded() {
  if (loadUserLLM().apiKey) return;
  await loadModeInfo();
  if (state.modeInfo?.tier === "demo") {
    await setupDemoExperience();
  }
}

function maybeShowWelcome() {
  if (localStorage.getItem(WELCOME_SEEN_KEY)) return;
  const user = loadUserLLM();
  if (user.apiKey) {
    localStorage.setItem(WELCOME_SEEN_KEY, "1");
    return;
  }
  if (!state.modeInfo?.demo_available && state.modeInfo?.tier === "full") {
    localStorage.setItem(WELCOME_SEEN_KEY, "1");
    return;
  }
  welcomeDialog.showModal();
}

async function loadWorkspaces() {
  const resp = await api("/api/workspaces");
  state.workspaces = await resp.json();
  const currentExists = state.workspaces.some((w) => w.id === state.currentId);
  if (!state.currentId || !currentExists) {
    state.currentId = state.workspaces.length ? state.workspaces[0].id : null;
  }
  renderWorkspaces();
  if (state.currentId) {
    await loadDocuments();
  } else {
    state.documents = [];
    renderDocuments([]);
    clearDocumentScope();
  }
  updateHeader();
  renderChatLog({ instantScroll: true });
}

function updateHeader() {
  const ws = state.workspaces.find((w) => w.id === state.currentId);
  if (!ws) {
    currentWorkspaceName.textContent = "选择资料库";
    currentWorkspaceDesc.textContent = "";
    updateHeroTitle();
    return;
  }
  currentWorkspaceName.textContent = ws.name;
  currentWorkspaceDesc.textContent = ws.description || "上传文档到左侧项目列表，然后在此提问";
  updateHeroTitle();
}

async function selectWorkspace(id) {
  if (id === state.currentId) return;
  state.currentId = id;
  clearDocumentScope();
  hideMentionPicker();
  renderWorkspaces();
  updateHeader();
  await loadDocuments();
  renderChatLog({ instantScroll: true });
  updateModeUI();
}

let documentPollTimer = null;

function scheduleDocumentPoll() {
  if (documentPollTimer) return;
  documentPollTimer = setInterval(async () => {
    if (!state.currentId) return;
    const hasProcessing = state.documents.some((doc) => doc.status === "processing");
    if (!hasProcessing) {
      clearInterval(documentPollTimer);
      documentPollTimer = null;
      return;
    }
    await loadDocuments({ silent: true });
  }, 2500);
}

async function loadDocuments(options = {}) {
  if (!state.currentId) return;
  try {
    const resp = await api(`/api/workspaces/${state.currentId}/documents`);
    const docs = await resp.json();
    renderDocuments(docs);
    const ws = state.workspaces.find((w) => w.id === state.currentId);
    if (ws) ws.document_count = docs.length;
    renderWorkspaces();
    if (docs.some((doc) => doc.status === "processing")) {
      scheduleDocumentPoll();
    }
  } catch (err) {
    if (!options.silent) {
      console.error(err);
    }
  }
}

function isAcceptedFile(file) {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

function uploadStatusLabel(item) {
  if (item.status === "waiting") return "等待中";
  if (item.status === "uploading") return `上传中 ${item.percent}%`;
  if (item.status === "processing") return `解析入库中 ${item.percent}%`;
  if (item.status === "done") return "完成";
  if (item.status === "error") return item.error || "失败";
  return "";
}

function renderUploadQueue() {
  uploadQueue.innerHTML = "";
  uploadState.items.forEach((item) => {
    const li = document.createElement("li");
    li.className = `upload-item ${item.status}`;
    li.innerHTML = `
      <div class="upload-item-head">
        <span class="upload-item-name">${escapeHtml(item.file.name)}</span>
        <span class="upload-item-status ${escapeHtml(item.status)}">${escapeHtml(uploadStatusLabel(item))}</span>
      </div>
      <div class="upload-item-progress">
        <div class="upload-item-bar" style="width: ${item.percent}%"></div>
      </div>
      <div class="upload-item-meta">${formatSize(item.file.size)}${item.detail ? ` · ${escapeHtml(item.detail)}` : ""}</div>
    `;
    uploadQueue.appendChild(li);
  });

  const doneCount = uploadState.items.filter((i) => i.status === "done").length;
  const errorCount = uploadState.items.filter((i) => i.status === "error").length;
  const activeCount = uploadState.items.filter((i) =>
    ["waiting", "uploading", "processing"].includes(i.status)
  ).length;

  if (!uploadState.items.length) {
    uploadSummary.hidden = true;
    uploadSummary.textContent = "";
  } else if (activeCount > 0) {
    uploadSummary.hidden = false;
    uploadSummary.textContent = `正在导入 ${activeCount} / ${uploadState.items.length} 个文件…`;
  } else {
    uploadSummary.hidden = false;
    uploadSummary.textContent =
      errorCount > 0
        ? `完成 ${doneCount} 个，失败 ${errorCount} 个`
        : `全部 ${doneCount} 个文件导入完成`;
  }
}

function updateUploadItem(item, patch) {
  Object.assign(item, patch);
  renderUploadQueue();
}

async function uploadFileWithProgress(file, onProgress) {
  const form = new FormData();
  form.append("file", file);
  let processingTimer = null;

  const clearProcessingTimer = () => {
    if (processingTimer) {
      clearInterval(processingTimer);
      processingTimer = null;
    }
  };

  const startProcessingAnimation = () => {
    if (processingTimer) return;
    let percent = 62;
    onProgress({ status: "processing", percent });
    processingTimer = setInterval(() => {
      percent = Math.min(percent + 2, 92);
      onProgress({ status: "processing", percent });
    }, 450);
  };

  onProgress({ status: "uploading", percent: 20 });
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 600000);

  try {
    const resp = await fetch(`/api/workspaces/${state.currentId}/documents`, {
      method: "POST",
      body: form,
      signal: controller.signal,
    });
    startProcessingAnimation();
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(data.detail || `上传失败 (${resp.status})`);
    }
    onProgress({ status: "done", percent: 100, detail: data.message });
    return data;
  } catch (err) {
    if (err.name === "AbortError") {
      throw new Error("上传超时，请稍后刷新文档列表查看是否仍在处理");
    }
    if (err instanceof TypeError || /failed to fetch|networkerror|http2/i.test(err.message)) {
      throw new Error(
        "连接中断 (ERR_HTTP2)。Railway 请挂载 /app/data 持久卷，并等待启动完成后再上传；可先试小 txt 文件。"
      );
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
    clearProcessingTimer();
  }
}

async function openUploadDialog() {
  closeMobileSidebar();
  if (state.modeInfo?.startup_ready === false) {
    await showConfirm({
      title: "系统加载中",
      message: "嵌入模型仍在加载，请稍候 1～2 分钟后再上传文档。",
      confirmText: "知道了",
      alertOnly: true,
    });
    return;
  }
  if (!state.currentId) {
    await showConfirm({
      title: "提示",
      message: "请先选择一个资料库",
      confirmText: "知道了",
      alertOnly: true,
    });
    return;
  }
  uploadState.items = uploadState.items.filter((item) =>
    ["waiting", "uploading", "processing"].includes(item.status)
  );
  renderUploadQueue();
  uploadDialog.showModal();
  uploadDropzone.focus();
}

function enqueueUploadFiles(fileList) {
  const files = Array.from(fileList || []);
  if (!files.length) return;

  const accepted = [];
  const rejected = [];
  files.forEach((file) => {
    if (isAcceptedFile(file)) accepted.push(file);
    else rejected.push(file.name);
  });

  if (rejected.length) {
    alert(`以下文件类型不支持，已跳过：\n${rejected.join("\n")}`);
  }
  if (!accepted.length) return;

  let batch = accepted;
  if (state.modeInfo?.features?.batch_upload === false && accepted.length > 1) {
    batch = [accepted[0]];
    showConfirm({
      title: "演示模式",
      message: "演示模式每次仅支持上传 1 个文件。已为你选择第一个文件，配置 API Key 可解锁批量上传。",
      confirmText: "知道了",
      alertOnly: true,
    });
  }

  batch.forEach((file) => {
    uploadState.items.push({
      id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      file,
      status: "waiting",
      percent: 0,
      detail: "",
      error: "",
    });
  });

  renderUploadQueue();
  processUploadQueue();
}

async function processUploadQueue() {
  if (uploadState.running) return;
  uploadState.running = true;

  let shouldReload = false;
  while (true) {
    const item = uploadState.items.find((entry) => entry.status === "waiting");
    if (!item) break;

    try {
      await uploadFileWithProgress(item.file, (patch) => updateUploadItem(item, patch));
      shouldReload = true;
    } catch (err) {
      updateUploadItem(item, {
        status: "error",
        percent: 100,
        error: err.message,
      });
    }
  }

  if (shouldReload) {
    await loadWorkspaces();
    await loadDocuments();
  }

  uploadState.running = false;
  renderUploadQueue();
}

function closeUploadDialog() {
  const active = uploadState.items.some((item) =>
    ["waiting", "uploading", "processing"].includes(item.status)
  );
  if (!active) {
    uploadState.items = [];
    renderUploadQueue();
  }
  uploadDialog.close();
}

async function removeDocument(documentId) {
  const ok = await showConfirm({
    title: "删除文档",
    message: "确定删除该文档？删除后无法恢复。",
    confirmText: "删除",
    cancelText: "取消",
    danger: true,
  });
  if (!ok) return;
  await api(`/api/workspaces/${state.currentId}/documents/${documentId}`, {
    method: "DELETE",
  });
  if (state.scopedDocuments.some((doc) => doc.id === documentId)) {
    removeDocumentScope(documentId);
  }
  await loadWorkspaces();
  await loadDocuments();
}

async function clearChat() {
  if (!state.currentId) return;
  if (!getMessages().length) return;
  const ok = await showConfirm({
    title: "清空对话",
    message: "确定清空当前资料库的全部对话？",
    confirmText: "清空",
    cancelText: "取消",
    danger: true,
  });
  if (!ok) return;
  state.chatHistory[state.currentId] = [];
  saveChatHistory();
  renderChatLog({ instantScroll: true });
  renderWorkspaces();
  updateModeUI();
  chatInput.focus();
}

async function sendMessage(text) {
  const scoped = resolveScopedQuestion(text);
  if (!scoped.question.trim()) {
    alert("请输入问题");
    return;
  }

  const workspaceId = state.currentId;
  if (!workspaceId) return;

  abortActiveChat();
  const controller = new AbortController();
  activeChatController = controller;

  state.sending = true;
  setComposerDisabled(true);
  updateChatLayout();
  updateModeUI();
  pushMessage("user", scoped.displayText, null, null, scoped.documentNames, {}, workspaceId);

  let botDiv = null;
  let botBody = null;
  if (state.currentId === workspaceId) {
    renderChatLog();
    botDiv = document.createElement("div");
    botDiv.className = "message bot";
    botBody = document.createElement("div");
    botBody.className = "message-body";
    botDiv.appendChild(botBody);
    chatLog.appendChild(botDiv);
  }

  let sources = [];
  let answerText = "";
  let answerMode = null;

  try {
    const resp = await fetch(`/api/workspaces/${workspaceId}/chat/stream`, {
      method: "POST",
      headers: getApiHeaders({ "Content-Type": "application/json" }),
      signal: controller.signal,
      body: JSON.stringify({
        message: scoped.question,
        stream: true,
        document_ids: scoped.documentIds,
      }),
    });
    if (!resp.ok) {
      let detail = await resp.text();
      try {
        const data = JSON.parse(detail);
        detail = data.detail || detail;
      } catch (_) {}
      throw new Error(detail);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data: ")) continue;
        const payload = JSON.parse(line.slice(6));
        if (payload.type === "meta") {
          sources = payload.sources || [];
          answerMode = payload.mode || null;
          if (payload.tier && state.modeInfo) {
            state.modeInfo.tier = payload.tier;
          }
          if (
            state.modeInfo?.tier === "demo" &&
            payload.demo_remaining != null &&
            state.modeInfo?.demo_quota
          ) {
            state.modeInfo.demo_quota.remaining = payload.demo_remaining;
          }
          updateModeUI();
        } else if (payload.type === "token") {
          answerText += payload.content;
          if (state.currentId === workspaceId && botBody) {
            setMessageBody(botBody, answerText, "bot", answerMode);
            scrollChatToBottom();
          }
        }
      }
    }

    if (answerText.trim()) {
      pushMessage(
        "bot",
        answerText,
        sources,
        answerMode,
        null,
        { demoTip: state.modeInfo?.tier === "demo" },
        workspaceId
      );
    }
    if (state.currentId === workspaceId) {
      renderChatLog();
    }
  } catch (err) {
    if (err.name === "AbortError") {
      if (answerText.trim()) {
        pushMessage("bot", answerText, sources, answerMode, null, {}, workspaceId);
      }
      if (state.currentId === workspaceId) {
        renderChatLog();
      }
      return;
    } else {
      const errText = `出错了: ${err.message}`;
      pushMessage("bot", errText, null, null, null, {}, workspaceId);
      if (state.currentId === workspaceId) {
        renderChatLog();
      }
    }
  } finally {
    if (activeChatController === controller) {
      activeChatController = null;
    }
    state.sending = false;
    setComposerDisabled(false);
    updateChatLayout();
    updateModeUI();
    renderWorkspaces();
    await loadModeInfo();
  }
}

uploadOpenBtn.addEventListener("click", openUploadDialog);
uploadDialogClose.addEventListener("click", closeUploadDialog);
uploadDialog.addEventListener("cancel", (e) => {
  e.preventDefault();
  closeUploadDialog();
});
uploadDialog.addEventListener("close", () => {
  fileInput.value = "";
});

uploadDropzone.addEventListener("click", () => fileInput.click());
uploadDropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});
uploadDropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  uploadDropzone.classList.add("dragover");
});
uploadDropzone.addEventListener("dragleave", () => {
  uploadDropzone.classList.remove("dragover");
});
uploadDropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  uploadDropzone.classList.remove("dragover");
  enqueueUploadFiles(e.dataTransfer?.files);
});

fileInput.addEventListener("change", (e) => {
  enqueueUploadFiles(e.target.files);
  fileInput.value = "";
});

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = chatInput.value.trim();
  if (!text || !state.currentId || state.sending) return;
  if (!state.documents.length) {
    await showConfirm({
      title: "提示",
      message: "请先上传文档",
      confirmText: "知道了",
      alertOnly: true,
    });
    return;
  }
  if (
    state.modeInfo?.tier === "demo" &&
    state.modeInfo?.demo_quota &&
    state.modeInfo.demo_quota.remaining <= 0
  ) {
    const goConfig = await showConfirm({
      title: "试用次数已用完",
      message: "演示模式今日试用次数已用完。请配置 API Key 解锁完整功能。",
      confirmText: "去配置",
      cancelText: "取消",
    });
    if (goConfig) openSettings();
    return;
  }
  chatInput.value = "";
  hideMentionPicker();
  await sendMessage(text);
});

chatInput.addEventListener("input", updateMentionPicker);
chatInput.addEventListener("click", updateMentionPicker);
chatInput.addEventListener("keyup", updateMentionPicker);
chatInput.addEventListener("keydown", handleChatInputKeydown);

async function handleRetrievePreview() {
  if (state.modeInfo?.features?.retrieve_preview === false) {
    const goConfig = await showConfirm({
      title: "功能锁定",
      message: "演示模式不支持检索预览。配置 API Key 可解锁完整功能。",
      confirmText: "去配置",
      cancelText: "取消",
    });
    if (goConfig) openSettings();
    return;
  }
  const scoped = resolveScopedQuestion(chatInput.value.trim());
  if (!scoped.question) {
    await showConfirm({
      title: "提示",
      message: "请先在输入框填写要预览的问题",
      confirmText: "知道了",
      alertOnly: true,
    });
    chatInput.focus();
    return;
  }
  try {
    await openRetrievePreview(scoped.question, scoped.documentIds);
  } catch (err) {
    await showConfirm({
      title: "检索预览失败",
      message: err.message,
      confirmText: "知道了",
      alertOnly: true,
    });
  }
}

clearChatBtn.addEventListener("click", clearChat);
retrievePreviewBtn.addEventListener("click", handleRetrievePreview);
if (sidebarRetrievePreviewBtn) {
  sidebarRetrievePreviewBtn.addEventListener("click", () => {
    closeMobileSidebar();
    handleRetrievePreview();
  });
}
if (sidebarClearChatBtn) {
  sidebarClearChatBtn.addEventListener("click", () => {
    closeMobileSidebar();
    clearChat();
  });
}
if (mobileMenuBtn) mobileMenuBtn.addEventListener("click", openMobileSidebar);
if (currentWorkspaceName) {
  currentWorkspaceName.addEventListener("click", () => {
    if (isMobileLayout()) openMobileSidebar();
  });
}
if (mobileHeaderBrand) mobileHeaderBrand.addEventListener("click", openMobileSidebar);
if (sidebarBackdrop) {
  sidebarBackdrop.addEventListener("click", closeMobileSidebar);
}
MOBILE_LAYOUT_QUERY.addEventListener("change", () => {
  if (!isMobileLayout()) closeMobileSidebar();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeMobileSidebar();
});
chunksClose.addEventListener("click", (e) => {
  e.preventDefault();
  e.stopPropagation();
  closeChunksDialog();
});
chunksDialog.addEventListener("click", (e) => {
  if (e.target === chunksDialog) closeChunksDialog();
});
chunksDialog.addEventListener("cancel", (e) => {
  e.preventDefault();
  closeChunksDialog();
});
llmMode.addEventListener("click", openSettings);
settingsForm.addEventListener("submit", saveSettings);
settingsClose.addEventListener("click", () => settingsDialog.close());
cfgClearKey.addEventListener("click", clearApiKey);
cfgValidateKey.addEventListener("click", validateUserKey);
demoUpgradeBtn.addEventListener("click", openSettings);
if (retrievalNoticeConfig) retrievalNoticeConfig.addEventListener("click", openSettings);
if (retrievalNoticeDismiss) {
  retrievalNoticeDismiss.addEventListener("click", () => {
    localStorage.setItem(RETRIEVAL_NOTICE_DISMISSED_KEY, "1");
    if (retrievalNotice) retrievalNotice.hidden = true;
  });
}
welcomeTryDemo.addEventListener("click", async () => {
  localStorage.setItem(WELCOME_SEEN_KEY, "1");
  welcomeDialog.close();
  await loadModeInfo();
  if (state.modeInfo?.tier === "demo") {
    if (state.modeInfo.demo_blocked) {
      await showConfirm({
        title: "今日试用次数已用完",
        message: `演示模式每日限 ${state.modeInfo.demo_quota?.daily_limit || 10} 次，今日额度已耗尽。可配置自己的 API Key 继续使用，或明天再试。`,
        confirmText: "去配置 Key",
        cancelText: "知道了",
      }).then((go) => {
        if (go) openSettings();
      });
      return;
    }
    await setupDemoExperience();
    return;
  }
  localStorage.removeItem(RETRIEVAL_NOTICE_DISMISSED_KEY);
  updateRetrievalNotice(state.modeInfo);
  await showConfirm({
    title: "演示 AI 未开启",
    message:
      "服务端尚未配置 DEMO_API_KEY，因此无法进入演示模式。已为你加载示例资料库，但问答仍只能是检索摘录。\n\n请让管理员在 Railway 配置 DEMO_API_KEY 并 Redeploy，或点击「配置 API Key」使用自己的 Key。",
    confirmText: "去配置 Key",
    cancelText: "知道了",
    alertOnly: false,
  }).then((go) => {
    if (go) openSettings();
  });
});
welcomeConfigKey.addEventListener("click", () => {
  localStorage.setItem(WELCOME_SEEN_KEY, "1");
  welcomeDialog.close();
  openSettings();
});
welcomeDialog.addEventListener("close", () => {
  ensureDemoExperienceIfNeeded();
});
settingsDialog.addEventListener("close", () => {
  ensureDemoExperienceIfNeeded();
});
addWorkspaceBtn.addEventListener("click", () => openWorkspaceDialog("create"));
workspaceForm.addEventListener("submit", saveWorkspaceDialog);
workspaceDialogClose.addEventListener("click", () => workspaceDialog.close());

initConfirmDialog();
initBrandSettings();

(async function init() {
  try {
    await loadHealth();
    maybeShowWelcome();
    await loadWorkspaces();
    if (state.modeInfo?.tier === "demo") {
      await setupDemoExperience();
    }
  } catch (err) {
    pushMessage("bot", `初始化失败: ${err.message}`);
    renderChatLog();
  }
})();
