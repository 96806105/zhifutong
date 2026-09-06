/* 智服通 - 前端聊天逻辑（原生 JS + SSE 流式） */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const els = {
    scroll: $("#chat-scroll"),
    inner: $("#chat-inner"),
    empty: $("#chat-empty"),
    textarea: $("#composer-input"),
    sendBtn: $("#send-btn"),
    composer: $("#composer"),
    list: $("#side-list"),
    sidePanel: $("#sidebar"),
    overlay: $("#side-overlay"),
    toast: $("#toast"),
    rowCount: $("#row-count"),
  };

  let sessionId = null;
  let streaming = false;

  const LABELS = {
    greeting: "问候",
    transfer: "已转人工",
    fallback: "未命中",
    human: "人工客服",
    none: "",
  };

  /* ── 工具 ── */
  function toast(text) {
    els.toast.textContent = text;
    els.toast.classList.add("show");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => els.toast.classList.remove("show"), 2400);
  }

  function esc(s) {
    return s.replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function fmtTime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const p = (n) => String(n).padStart(2, "0");
    return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }

  async function api(url, opts) {
    const res = await fetch(url, opts);
    if (!res.ok) {
      let msg = "请求失败";
      try {
        const j = await res.json();
        msg = j.error?.message || msg;
      } catch (_) {}
      throw new Error(msg);
    }
    return res;
  }

  function scrollBottom(smooth) {
    els.scroll.scrollTo({ top: els.scroll.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  }

  /* ── SSE 流式解析 ── */
  async function streamChat(message) {
    sessionId = sessionId || (await startSession()).session_id;
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
    });
    if (!res.ok || !res.body) throw new Error("连接中断，请重试");

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    const bot = addBotBubble("");

    let buffer = "";
    let meta = null;
    let reply = "";
    let hasDelta = false;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let idx;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const chunk = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const data = chunk
          .split("\n")
          .filter((l) => l.startsWith("data:"))
          .map((l) => l.slice(5).trim())
          .join("\n");
        if (!data) continue;
        let ev;
        try { ev = JSON.parse(data); } catch (_) { continue; }

        if (ev.type === "session") {
          sessionId = ev.data.session_id;
          refreshSidebar();
        } else if (ev.type === "delta") {
          hasDelta = true;
          reply += ev.data;
          setBotText(bot, reply);
          scrollBottom(true);
        } else if (ev.type === "meta") {
          meta = ev.data;
        }
      }
    }

    if (meta) {
      const finalReply = meta.reply || reply;
      setBotText(bot, finalReply);
      appendMeta(bot, meta.action, meta.confidence, meta.sources, meta.ticket_id);
      if (meta.action === "transfer" && meta.ticket_id) {
        toast(`已转人工，工单号 ${meta.ticket_id}`);
        startHumanPolling(sessionId);
      }
      reply = finalReply;
    } else if (!hasDelta && !reply) {
      setBotText(bot, "抱歉，服务暂时无响应，请稍后重试。");
    }

    refreshSidebar();
  }

  /* ── 人工回复轮询（转人工后监听） ── */
  let pollTimer = null;
  let polledLastId = 0;

  function startHumanPolling(sid) {
    stopHumanPolling();
    polledLastId = 0;
    let polls = 0;
    pollTimer = setInterval(async () => {
      if (!sid) return;
      polls += 1;
      if (polls > 60) { stopHumanPolling(); return; }  // 最多轮询 3 分钟
      try {
        const res = await fetch("/api/history?session_id=" + encodeURIComponent(sid));
        const j = await res.json();
        const msgs = j.messages || [];
        // 找到比已展示更新且属于人工助手（action==human）的消息
        const humanMsgs = msgs.filter(
          (m) => m.action === "human" && m.content && msgs.indexOf(m) > polledLastId
        );
        humanMsgs.forEach((m) => {
          const bot = addBotBubble(m.content);
          bot.querySelector(".msg-avatar").classList.add("avatar-human");
          bot.querySelector(".msg-avatar").textContent = "人";
          const tag = document.createElement("span");
          tag.className = "act-tag human";
          tag.textContent = "人工回复";
          bot.querySelector(".msg-meta").appendChild(tag);
        });
        if (msgs.length) polledLastId = msgs.length - 1;
        if (humanMsgs.length) stopHumanPolling();
      } catch (_) { /* 网络抖动忽略 */ }
    }, 3000);
  }

  function stopHumanPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  /* ── 消息渲染 ── */
  function addBotBubble(text) {
    const msg = document.createElement("div");
    msg.className = "msg msg-bot";
    msg.innerHTML = `
      <div class="msg-avatar avatar-bot">智</div>
      <div class="msg-body">
        <div class="bubble"></div>
        <div class="msg-meta"></div>
      </div>`;
    els.inner.appendChild(msg);
    if (text) setBotText(msg.querySelector(".bubble"), text);
    scrollBottom(true);
    return msg;
  }

  function addUserBubble(text) {
    const msg = document.createElement("div");
    msg.className = "msg msg-user";
    msg.innerHTML = `
      <div class="msg-avatar avatar-user">我</div>
      <div class="msg-body">
        <div class="bubble"></div>
      </div>`;
    const bubble = msg.querySelector(".bubble");
    bubble.textContent = text;
    els.inner.appendChild(msg);
    scrollBottom(true);
  }

  function setBotText(msg, text) {
    msg.innerHTML = esc(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>");
  }

  function appendMeta(msg, action, confidence, sources, ticketId) {
    const box = msg.querySelector(".msg-meta");
    if (!box) return;

    const frag = document.createDocumentFragment();

    if (action && LABELS[action]) {
      const t = document.createElement("span");
      t.className = "act-tag" + (action === "transfer" ? " transfer" : action === "fallback" ? " fallback" : "");
      t.textContent = LABELS[action];
      frag.appendChild(t);
    }
    if (Array.isArray(sources) && sources.length) {
      sources.forEach((s) => {
        const tag = document.createElement("span");
        tag.className = "src-tag";
        tag.textContent = s.category || s.source || "知识库";
        frag.appendChild(tag);
      });
    }
    if (typeof confidence === "number" && confidence > 0) {
      const c = document.createElement("span");
      c.className = "conf-tag";
      c.textContent = "可信度 " + (confidence * 100).toFixed(0) + "%";
      frag.appendChild(c);
    }
    if (box) box.appendChild(frag);
  }

  /* ── 发送 ── */
  async function send() {
    const text = els.textarea.value.trim();
    if (!text || streaming) return;

    // 校验后清空
    els.textarea.value = "";
    autoResize();
    addUserBubble(text);
    hideEmpty();

    const typing = document.createElement("div");
    typing.className = "msg msg-bot typing";
    typing.innerHTML = `
      <div class="msg-avatar avatar-bot">智</div>
      <div class="msg-body"><div class="bubble">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
      </div></div>`;
    els.inner.appendChild(typing);
    scrollBottom(true);

    setStreaming(true);
    try {
      await streamChat(text);
      typing.remove();
    } catch (err) {
      typing.remove();
      const e = document.createElement("div");
      e.className = "err-banner";
      e.textContent = "⚠ " + (err.message || "网络异常，请重试");
      els.inner.appendChild(e);
    } finally {
      setStreaming(false);
      scrollBottom(true);
    }
  }

  function setStreaming(v) {
    streaming = v;
    els.sendBtn.disabled = v;
    els.sendBtn.innerHTML = v
      ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="6" y1="6" x2="18" y2="18" stroke-linecap="round"/><line x1="18" y1="6" x2="6" y2="18" stroke-linecap="round"/></svg>'
      : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>';
  }

  function autoResize() {
    els.textarea.style.height = "auto";
    els.textarea.style.height = Math.min(els.textarea.scrollHeight, 140) + "px";
  }

  function hideEmpty() {
    if (els.empty) els.empty.style.display = "none";
  }

  function showEmptyLoading() {
    elHide();
  }

  function elHide() { }

  /* ── 会话管理 ── */
  async function startSession() {
    const res = await api("/api/session", { method: "POST" });
    const j = await res.json();
    return j;
  }

  async function resetChat() {
    stopHumanPolling();
    showEmptyLoading();
    const j = await startSession();
    sessionId = j.session_id;
    els.inner.innerHTML = "";
    renderEmpty();
    refreshSidebar();
  }

  function renderEmpty() {
    els.inner.innerHTML = `
      <div id="chat-empty" class="empty">
        <div class="empty-mark">智</div>
        <h1>智服通 · 企业 IT 技术支持</h1>
        <p>账号密码、网络连接、软件安装、硬件故障、安全权限…… 直接在下方提问，我会基于企业知识库为您解答。</p>
        <div class="suggest">
          <button data-q="如何修改我的登录密码？">忘记密码怎么办</button>
          <button data-q="公司内部的 WiFi 怎么连接？">WiFi 无法连接</button>
          <button data-q="如何安装公司指定的办公软件？">安装软件</button>
          <button data-q="笔记本风扇声音很大怎么办？">硬件故障</button>
        </div>
      </div>`;
    els.empty = $("#chat-empty");
    $$(".suggest button").forEach((b) =>
      b.addEventListener("click", () => {
        els.textarea.value = b.dataset.q;
        send();
      })
    );
  }

  async function openSession(id) {
    try {
      const res = await api("/api/history?session_id=" + encodeURIComponent(id));
      const j = await res.json();
      sessionId = id;
      els.inner.innerHTML = "";
      $$("#side-list .side-item").forEach((x) => x.classList.toggle("active", x.dataset.id === id));
      if (!j.messages || !j.messages.length) {
        renderEmpty();
      } else {
        j.messages.forEach((m) => {
          if (m.role === "user") addUserBubble(m.content);
          else {
            const bot = addBotBubble(m.content);
            let sources;
            if (typeof m.sources === "string") {
              try { sources = JSON.parse(m.sources); } catch (_) { sources = []; }
            } else { sources = m.sources; }
            appendMeta(bot, m.action, m.confidence, sources, null);
          }
        });
        scrollBottom();
      }
      closeSidebar();
    } catch (err) {
      toast(err.message || "加载会话失败");
    }
  }

  async function refreshSidebar() {
    try {
      const res = await api("/api/sessions?limit=20");
      const j = await res.json();
      els.list.innerHTML = "";
      if (els.rowCount) els.rowCount.textContent = j.sessions.length;

      j.sessions.forEach((s) => {
        const btn = document.createElement("button");
        btn.className = "side-item";
        btn.dataset.id = s.id;
        if (s.id === sessionId) btn.classList.add("active");
        btn.innerHTML = `
          <div class="side-item-title">${esc(s.user_name || s.id.slice(0, 8))}</div>
          <div class="side-item-meta">${fmtTime(s.updated_at)} · ${s.status === "transferred" ? "已转人工" : "进行中"}</div>`;
        btn.addEventListener("click", () => openSession(s.id));
        els.list.appendChild(btn);
      });
    } catch (_) { /* 侧栏失败不阻塞聊天 */ }
  }

  /* ── 侧栏 ── */
  function openSidebar() {
    els.sidePanel.classList.add("open");
    els.overlay.classList.add("show");
  }
  function closeSidebar() {
    els.sidePanel.classList.remove("open");
    els.overlay.classList.remove("show");
  }

  /* ── 导航玻璃滚动态 ── */
  const topbar = $("#topbar");
  if (topbar) {
    document.addEventListener("scroll", () => {
      topbar.classList.toggle("glass-scrolled", window.scrollY > 8);
    }, { passive: true });
  }

  /* ── 事件绑定 ── */
  function init() {
    renderEmpty();

    els.sendBtn.addEventListener("click", send);
    els.textarea.addEventListener("input", autoResize);
    els.textarea.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    });
    els.composer?.addEventListener("submit", (e) => e.preventDefault());

    $("#new-chat-btn")?.addEventListener("click", resetChat);
    $("#side-open")?.addEventListener("click", openSidebar);
    els.overlay.addEventListener("click", closeSidebar);

    // 启动即建会话
    startSession().then((j) => {
      sessionId = j.session_id;
      refreshSidebar();
    }).catch((err) => toast(err.message));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();