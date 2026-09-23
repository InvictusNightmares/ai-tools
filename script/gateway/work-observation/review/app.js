(() => {
  "use strict";

  const state = {
    reviews: [],
    selected: null,
    selectedKey: null,
    detailRequestId: 0,
    view: "review",
    page: 1,
    pageSize: 50,
    total: 0,
    pages: 0,
    start: 0,
    end: 0,
    hasPrev: false,
    hasMore: false,
    loading: false,
    queuedRefresh: null,
    refreshTimer: null,
  };

  const $ = (id) => document.getElementById(id);
  const text = (value, fallback = "—") => {
    if (value === null || value === undefined || value === "") return fallback;
    return String(value);
  };
  const escapeHTML = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
  const formatNumber = (value) => Number(value || 0).toLocaleString("zh-CN");
  const formatTime = (value) => {
    if (!value) return "时间未知";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? text(value) : date.toLocaleString("zh-CN", { hour12: false });
  };
  const regionName = (region, formalIngress) => `${region === "tokyo" ? "Tokyo" : region === "us" ? "US West" : text(region)} ${formalIngress || (region === "tokyo" ? "4000" : region === "us" ? "4001" : "")}`.trim();
  const grayLane = (region) => region === "tokyo" ? "4004" : region === "us" ? "4005" : "—";
  const lanePair = (region, formalIngress) => `${regionName(region, formalIngress)} → 灰度 ${grayLane(region)}`;
  const statusName = (status) => ({ complete: "已完成", pending: "待分析", running: "分析中", unavailable: "技术失败·待重试", deferred: "已暂停重试", failed: "源记录失败", unreviewed: "未分析" }[status] || text(status));
  const decisionName = (decision) => ({ allow: "放行", block: "拦截", unavailable: "不可用" }[decision] || "未运行");
  const stateName = (value) => ({ complete: "已完成", pending: "待分析", running: "分析中", unavailable: "技术不可用", blocked: "被拒绝", http_error: "HTTP失败", invalid: "无有效结果", deferred: "已暂停重试", unreviewed: "未分析", not_run: "未运行" }[value] || text(value, "未分析"));
  const humanStatusName = (value) => ({ needs_review: "待人工处理", reviewed: "已人工处理", skipped: "已跳过" }[value] || "未人工处理");
  const reviewKey = (region, eventId) => `${region}\u0000${eventId}`;
  const labelName = (label) => ({
    correct_allow: "当前放行正确", correct_block: "当前拦截正确", should_allow: "应该放行", should_block: "应该拦截", uncertain: "不确定",
    good_choice: "模型选择合理", wrong_model: "模型不合适", too_strong: "模型过强", too_weak: "模型过弱",
  }[label] || label || "未标注");
  const viewNames = {
    review: { title: "Guard 拦截待复核", eyebrow: "Guard blocks", hint: "这里只显示 Guard 明确拦截且尚未人工处理的任务；已处理历史可用人工状态筛选查看。Guard 技术失败单独放在“技术失败”。", empty: "当前没有待人工处理的 Guard 拦截" },
    auto: { title: "Auto 已返回", eyebrow: "Offline Auto results", hint: "这里只显示离线 Auto 已返回模型或拒绝结果的任务；模型是离线候选结果，不能当作线上已执行。", empty: "当前还没有 Auto 返回结果" },
    technical: { title: "技术失败", eyebrow: "Technical failures", hint: "Guard / Auto 不可用、HTTP失败、无有效结论或源记录失败；这些记录不作为安全标签。", empty: "当前没有技术失败记录" },
    backlog: { title: "待分析积压", eyebrow: "Analysis backlog", hint: "这里只看采集成功但还没有跑 Guard / Auto 的任务，不进入人工复核队列。", empty: "当前没有待分析任务" },
    diagnostic: { title: "诊断集 200", eyebrow: "Diagnostic set", hint: "固定的 200 条代表性样本：Tokyo 100 条、US 100 条。清单只保存元数据；打开单条结果时才校验并读取源记录。", empty: "诊断集尚未生成或源记录不可用" },
  };

  async function request(path, options = {}) {
    const response = await fetch(path, { cache: "no-store", ...options });
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* the error below is enough */ }
    if (!response.ok) throw new Error(payload?.error || `HTTP ${response.status}`);
    return payload;
  }

  function setConnection(online, message) {
    const node = $("connection-state");
    node.textContent = message || (online ? "分析索引已连接" : "分析索引不可用");
    node.previousElementSibling?.classList.toggle("offline", !online);
  }

  function toast(message, error = false) {
    const node = $("toast");
    node.textContent = message;
    node.classList.toggle("error", error);
    node.classList.add("visible");
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(() => node.classList.remove("visible"), 3200);
  }

  function clearSelection() {
    state.detailRequestId += 1;
    state.selected = null;
    state.selectedKey = null;
    $("detail-content").hidden = true;
    $("detail-empty").hidden = false;
  }

  function selectedIndex() {
    if (!state.selectedKey) return -1;
    return state.reviews.findIndex((item) => reviewKey(item.region, item.event_id) === state.selectedKey);
  }

  function updateDetailNavigation() {
    const index = selectedIndex();
    const position = $("detail-position");
    const previous = $("detail-prev");
    const next = $("detail-next");
    if (!position || !previous || !next) return;
    if (index < 0) {
      position.textContent = "未选择结果";
      previous.disabled = true;
      next.disabled = true;
      return;
    }
    position.textContent = `本页第 ${index + 1} / ${state.reviews.length} 条`;
    previous.disabled = index === 0 && !state.hasPrev;
    next.disabled = index === state.reviews.length - 1 && !state.hasMore;
  }

  function renderSummary(summary) {
    const complete = Number(summary.complete_reviews || 0);
    const pending = Number(summary.pending_jobs || 0);
    const guard = summary.guard_decisions || {};
    const guardTotal = Object.entries(guard).reduce((sum, [key, value]) => key !== "not_run" ? sum + Number(value || 0) : sum, 0);
    const blocks = Number(guard.block || 0);
    const reviewTotal = Number(summary.guard_review_total ?? blocks);
    const labels = Number(summary.human_labels || 0);
    $("metric-complete").textContent = formatNumber(complete);
    $("metric-pending").textContent = formatNumber(pending);
    $("metric-blocks").textContent = formatNumber(reviewTotal);
    $("metric-labeled").textContent = formatNumber(labels);
    $("metric-block-rate").textContent = guardTotal ? `明确拦截 ${formatNumber(blocks)} · 技术失败 ${formatNumber(summary.guard_technical || 0)}` : "等待 Guard 结果";
    $("metric-label-rate").textContent = complete ? `已覆盖 ${(labels / complete * 100).toFixed(1)}% · 人工结论独立保存` : "等待样本";
    $("last-updated").textContent = summary.latest_run?.at ? `最近批次 ${formatTime(summary.latest_run.at)}` : (summary.last_reviewed_at ? `最近结果 ${formatTime(summary.last_reviewed_at)}` : "尚未执行灰度复核");
    const analysisNote = $("analysis-note");
    if (analysisNote) {
      analysisNote.textContent = `待分析 ${formatNumber(pending)} · Auto 已返回 ${formatNumber(summary.auto_attempted || summary.auto_full_total || 0)} · 已选模型 ${formatNumber(summary.auto_with_model || 0)} · Auto 技术失败 ${formatNumber(summary.auto_technical || summary.auto_unavailable || 0)}`;
    }
    $("view-count-review").textContent = formatNumber(reviewTotal);
    $("view-count-auto").textContent = formatNumber(summary.auto_full_total || summary.semantic_reviews_total || 0);
    $("view-count-technical").textContent = formatNumber(summary.technical_total || 0);
    $("view-count-backlog").textContent = formatNumber(pending);
    $("view-count-diagnostic").textContent = formatNumber(summary.diagnostic_set?.counts?.total || 0);
    renderModels(summary.auto_models || {});
    renderLatestRun(summary.latest_run);
  }

  function renderModels(models) {
    const entries = Object.entries(models).filter(([name]) => name !== "not_run").slice(0, 8);
    const node = $("model-bars");
    if (!entries.length) {
      node.innerHTML = '<div class="model-empty">还没有离线 Auto 选型结果；分析批次执行后会在这里出现。</div>';
      return;
    }
    const max = Math.max(...entries.map(([, count]) => Number(count || 0)), 1);
    node.innerHTML = entries.map(([name, count]) => `<div class="model-bar-item">
      <div class="model-bar-track"><div class="model-bar-fill" style="width:${Math.max(4, Number(count || 0) / max * 100)}%"></div></div>
      <span class="model-bar-name" title="${escapeHTML(name)}">${escapeHTML(name)} <b class="model-bar-count">${formatNumber(count)}</b></span>
    </div>`).join("");
  }

  function renderLatestRun(run) {
    const node = $("latest-run");
    if (!node) return;
    if (!run) {
      node.textContent = "尚未执行批次";
      return;
    }
    const status = run.status === "ok" ? "完成" : text(run.status);
    node.innerHTML = `<span class="run-chip ${run.status === "ok" ? "ok" : "warn"}">${escapeHTML(status)}</span> 第 ${escapeHTML(text(run.run_id, "—"))} 批 · 扫描 ${formatNumber(run.scanned || 0)} · 新增任务 ${formatNumber(run.review_jobs_added || 0)} · 已完成 ${formatNumber(run.semantic_reviewed || 0)}`;
  }

  function renderQueue() {
    const node = $("queue-body");
    const view = viewNames[state.view] || viewNames.review;
    $("queue-heading").textContent = view.title;
    $("queue-hint").textContent = view.hint;
    $("queue-count").textContent = state.total ? `${formatNumber(state.start)}–${formatNumber(state.end)} / ${formatNumber(state.total)} 条` : "0 条";
    document.querySelectorAll(".queue-view").forEach((button) => {
      const active = button.dataset.view === state.view;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    $("pagination").hidden = !state.total;
    $("page-status").textContent = state.total ? `第 ${formatNumber(state.page)} / ${formatNumber(state.pages)} 页 · 当前 ${formatNumber(state.start)}–${formatNumber(state.end)} 条，共 ${formatNumber(state.total)} 条` : "第 0 / 0 页";
    $("page-input").value = state.total ? String(state.page) : "";
    $("page-input").max = String(state.pages || 1);
    $("page-size").value = String(state.pageSize);
    $("page-prev").disabled = !state.hasPrev || state.loading;
    $("page-next").disabled = !state.hasMore || state.loading;
    if (state.loading && !state.reviews.length) {
      node.innerHTML = '<tr><td colspan="5" class="loading-cell">正在读取复核队列…</td></tr>';
      updateDetailNavigation();
      return;
    }
    if (!state.reviews.length) {
      node.innerHTML = `<tr><td colspan="5" class="empty-cell">${escapeHTML(view.empty)}</td></tr>`;
      updateDetailNavigation();
      return;
    }
    node.innerHTML = state.reviews.map((item) => {
      const selected = state.selectedKey === reviewKey(item.region, item.event_id);
      const title = item.task_preview || item.event_id;
      const autoText = item.auto?.display || item.auto?.model || "Auto 未运行";
      const autoClass = item.auto?.state || "not_run";
      const guard = item.guard?.decision;
      const guardText = item.guard?.display || decisionName(guard);
      const guardClass = guard || (item.guard?.state || "not_run");
      const humanStatus = item.human_status || "needs_review";
      const diagnostic = item.diagnostic;
      const diagnosticMeta = diagnostic ? ` · 诊断${diagnostic.rank || ""} · ${diagnostic.selection_bucket || "样本"}` : "";
      return `<tr class="queue-row${selected ? " selected" : ""}" data-region="${escapeHTML(item.region)}" data-event="${escapeHTML(item.event_id)}">
        <td><div class="task-title" title="${escapeHTML(title)}">${escapeHTML(title)}</div><div class="task-meta">${escapeHTML(lanePair(item.region, item.formal_ingress))} · ${escapeHTML(text(item.client, "client unknown"))} · ${escapeHTML(formatTime(item.at))}${escapeHTML(diagnosticMeta)}</div><div class="human-meta human-${escapeHTML(humanStatus)}">${escapeHTML(humanStatusName(humanStatus))}</div></td>
        <td><span class="model-name model-${escapeHTML(autoClass)}" title="${escapeHTML(autoText)}">${escapeHTML(autoText)}</span>${item.auto?.model && item.auto?.effort ? `<div class="cell-submeta">离线 · ${escapeHTML(item.auto.effort)} effort</div>` : item.auto?.offline_label ? `<div class="cell-submeta">${escapeHTML(item.auto.offline_label)}</div>` : ""}</td>
        <td><span class="decision ${escapeHTML(guardClass)}">${escapeHTML(guardText)}</span></td>
        <td><span class="state-label ${escapeHTML(item.status)}">${escapeHTML(item.status_label || statusName(item.status))}</span></td>
        <td class="arrow-cell">›</td>
      </tr>`;
    }).join("");
    // Delegate once on the stable tbody so a refresh cannot leave stale row
    // handlers behind or make a newly-rendered row appear non-clickable.
    node.onclick = (event) => {
      const row = event.target.closest(".queue-row");
      if (row && node.contains(row)) selectReview(row.dataset.region, row.dataset.event);
    };
    updateDetailNavigation();
  }

  function detailHTML(item) {
    const human = item.human || {};
    const guard = item.guard || {};
    const auto = item.auto || {};
    const integrity = item.integrity || {};
    const messages = item.messages || [];
    const messageHTML = messages.length ? messages.map((message) => `<div class="message ${escapeHTML(message.role)}"><div class="message-role">${escapeHTML(message.role)}</div><div class="message-content">${escapeHTML(message.content)}</div></div>`).join("") : '<div class="empty-inline">没有可展示的完整消息</div>';
    const categories = (guard.categories || []).map(escapeHTML).join(" · ") || "无分类";
    const reasons = (guard.reason_codes || []).map(escapeHTML).join(" · ") || "无原因码";
    const classification = Object.entries(auto.classification || {}).map(([key, value]) => `<span>${escapeHTML(key)}=${escapeHTML(value)}</span>`).join(" ") || "无分类明细";
    const integrityHTML = integrity.verified ? "" : `<div class="integrity-warning">源记录未能通过完整性读取：${escapeHTML(integrity.reason || "unknown")}。当前结论只能作为待复核状态。</div>`;
    const guardDisplay = guard.display || decisionName(guard.decision);
    const autoDisplay = auto.display || auto.model || "Auto 未运行";
    const onlineAutoLabel = {
      selected: "线上会执行（Guard 放行）",
      blocked: "线上会执行但被 Auto 拒绝",
      technical_failure: "线上路径待技术重试",
      not_run_guard_block: "线上未执行：Guard 已拦截",
      not_run_guard_unavailable: "线上未执行：Guard 无结论",
      not_run: "线上未执行：没有 Auto 结果",
    }[auto.online_status] || text(auto.online_status, "未说明");
    const diagnosticHTML = item.diagnostic ? `<div class="diagnostic-badge">诊断集第 ${escapeHTML(item.diagnostic.rank)} 条 · ${escapeHTML(item.diagnostic.selection_bucket || "代表性样本")} · ${escapeHTML(item.diagnostic.selection_reason || "")}</div>` : "";
    return `<div class="detail-header"><div class="section-kicker">${escapeHTML(lanePair(item.region, item.formal_ingress))}</div><h3>${escapeHTML(item.task_preview || item.event_id)}</h3>${diagnosticHTML}<div class="detail-meta"><span>${escapeHTML(item.event_id)}</span><span>${escapeHTML(text(item.protocol))}</span><span>${escapeHTML(formatTime(item.at))}</span><span>尝试 ${escapeHTML(item.attempts || 0)}</span><span class="detail-human-status">${escapeHTML(humanStatusName(item.human_status))}</span></div><div class="detail-navigation"><button class="button detail-nav-button" id="detail-prev" type="button" aria-label="上一条">‹ 上一条</button><span id="detail-position">本页结果</span><button class="button detail-nav-button" id="detail-next" type="button" aria-label="下一条">下一条 ›</button></div></div>
      <div class="detail-body">${integrityHTML}
        <p class="subheading">任务上下文</p><div class="conversation">${messageHTML}</div>
        <div class="candidate-grid"><article class="candidate-card guard"><div class="candidate-label">GUARD · 灰度预检</div><div class="candidate-main">${escapeHTML(guardDisplay)}</div><div class="candidate-detail"><span>状态</span> ${escapeHTML(stateName(guard.state))}<br><span>HTTP</span> ${escapeHTML(text(guard.http_status, "未请求"))}<br><span>风险</span> ${escapeHTML(text(guard.risk_level, "未返回"))}<br><span>分类</span> ${categories}<br><span>原因</span> ${reasons}</div></article>
          <article class="candidate-card auto"><div class="candidate-label">AUTO · 离线路由选择</div><div class="candidate-main">${escapeHTML(autoDisplay)}</div><div class="candidate-detail"><span>离线状态</span> ${escapeHTML(text(auto.offline_label, stateName(auto.state)))}<br><span>线上路径</span> ${escapeHTML(onlineAutoLabel)}<br><span>HTTP</span> ${escapeHTML(text(auto.http_status, "未请求"))}<br><span>effort</span> ${escapeHTML(text(auto.effort, "未返回"))}<br><span>动作</span> ${escapeHTML(text(auto.action, "未返回"))}<br><span>理由</span> ${escapeHTML(text(auto.reason, "未返回"))}<br>${classification}</div></article></div>
        <div class="detail-facts"><span>原请求模型</span><b>${escapeHTML(text(item.requested_model || item.model))}</b><span>可见回复模型</span><b>${escapeHTML(text(item.reported_model))}</b><span>业务结果</span><b>${escapeHTML(text(item.outcome))}</b></div>
        <form class="review-form" id="review-form"><p class="subheading">人工结论</p><div class="form-row"><label for="guard-label">Guard 判断</label><select id="guard-label"><option value="">暂不判断</option><option value="correct_allow">当前放行正确</option><option value="correct_block">当前拦截正确</option><option value="should_allow">应该放行</option><option value="should_block">应该拦截</option><option value="uncertain">不确定</option></select></div><div class="form-row"><label for="auto-label">Auto 判断</label><select id="auto-label"><option value="">暂不判断</option><option value="good_choice">模型选择合理</option><option value="wrong_model">模型不合适</option><option value="too_strong">模型过强</option><option value="too_weak">模型过弱</option><option value="uncertain">不确定</option></select></div><div class="form-row"><label for="review-notes">备注</label><textarea id="review-notes" maxlength="4000" placeholder="记录误拦、漏拦、模型过强/过弱的依据…"></textarea></div><div class="save-row"><span class="save-status" id="save-status">${human.updated_at ? `上次保存 ${escapeHTML(formatTime(human.updated_at))}` : "标签独立保存，不改变线上请求"}</span><div class="save-actions"><button class="button button-skip" id="skip-next" type="button">跳过并下一条</button><button class="button button-save-secondary" type="submit" data-advance="true">保存并下一条</button><button class="button button-save" type="submit">保存人工结论</button></div></div></form>
      </div>`;
  }

  async function selectReview(region, eventId) {
    const key = reviewKey(region, eventId);
    const requestId = ++state.detailRequestId;
    state.selectedKey = key;
    state.selected = null;
    renderQueue();
    const content = $("detail-content");
    $("detail-empty").hidden = true;
    content.hidden = false;
    content.innerHTML = '<div class="detail-loading"><div class="empty-orbit">…</div><h3>正在读取这条结果</h3><p>正在校验源记录并加载 Guard / Auto 状态。</p></div>';
    try {
      const item = await request(`/api/reviews/${encodeURIComponent(region)}/${encodeURIComponent(eventId)}`);
      if (requestId !== state.detailRequestId || state.selectedKey !== key) return;
      state.selected = item;
      content.hidden = false;
      content.innerHTML = detailHTML(item);
      const human = item.human || {};
      $("guard-label").value = human.guard_label || "";
      $("auto-label").value = human.auto_label || "";
      $("review-notes").value = human.notes || "";
      $("review-form").addEventListener("submit", (event) => saveLabel(event, item));
      $("detail-prev").addEventListener("click", () => selectNeighbor(-1));
      $("detail-next").addEventListener("click", () => selectNeighbor(1));
      $("skip-next").addEventListener("click", () => saveLabel(null, item, { advance: true, skip: true }));
      renderQueue();
    } catch (error) {
      if (requestId !== state.detailRequestId || state.selectedKey !== key) return;
      content.innerHTML = `<div class="detail-error"><div class="empty-orbit">!</div><h3>这条结果暂时无法读取</h3><p>${escapeHTML(error.message)}。请稍后重试。</p><button class="button" type="button" id="retry-detail">重试读取</button></div>`;
      $("retry-detail").addEventListener("click", () => selectReview(region, eventId));
      toast(`读取任务失败：${error.message}`, true);
    }
  }

  async function selectNeighbor(delta) {
    if (!state.selectedKey || state.loading) return;
    let index = selectedIndex();
    if (index < 0) return;
    let targetPage = state.page;
    let targetIndex = index + delta;
    if (targetIndex < 0 && state.hasPrev) {
      targetPage -= 1;
      targetIndex = state.pageSize - 1;
    } else if (targetIndex >= state.reviews.length && state.hasMore) {
      targetPage += 1;
      targetIndex = 0;
    }
    if (targetPage !== state.page) {
      state.page = targetPage;
      await refreshQueue(false);
      if (!state.reviews.length) return;
      targetIndex = Math.min(Math.max(targetIndex, 0), state.reviews.length - 1);
    }
    const target = state.reviews[targetIndex];
    if (target) await selectReview(target.region, target.event_id);
  }

  async function advanceAfterMutation(item) {
    const oldIndex = Math.max(selectedIndex(), 0);
    const mutatedKey = reviewKey(item.region, item.event_id);
    clearSelection();
    await refreshQueue(false);
    if (!state.reviews.length && state.page > 1) {
      state.page -= 1;
      await refreshQueue(false);
    }
    if (!state.reviews.length) {
      toast("这组队列已经处理完了");
      return;
    }
    // In historical views the just-labelled row remains visible. Skip it so
    // “保存并下一条” never opens the same result again.
    let nextIndex = Math.min(oldIndex, state.reviews.length - 1);
    if (reviewKey(state.reviews[nextIndex].region, state.reviews[nextIndex].event_id) === mutatedKey) {
      nextIndex += 1;
    }
    if (nextIndex >= state.reviews.length && state.hasMore) {
      state.page += 1;
      await refreshQueue(false);
      nextIndex = 0;
    }
    const next = state.reviews[nextIndex];
    if (next) await selectReview(next.region, next.event_id);
    else toast("已保存；当前没有下一条结果");
  }

  async function saveLabel(event, item, options = {}) {
    if (event) event.preventDefault();
    const form = $("review-form");
    const submitter = event?.submitter;
    const advance = Boolean(options.advance || submitter?.dataset.advance === "true");
    const skip = Boolean(options.skip);
    const button = options.skip ? $("skip-next") : (submitter || form?.querySelector("button[type=submit]"));
    if (!item || !button || button.disabled) return;
    button.disabled = true;
    if (form) form.querySelectorAll("button").forEach((control) => { control.disabled = true; });
    try {
      const payload = { status: skip ? "skipped" : "reviewed", guard_label: skip ? null : $("guard-label").value || null, auto_label: skip ? null : $("auto-label").value || null, notes: skip ? "" : $("review-notes").value, reviewer: "local" };
      const updated = await request(`/api/reviews/${encodeURIComponent(item.region)}/${encodeURIComponent(item.event_id)}/label`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      state.selected = updated;
      $("detail-content").innerHTML = detailHTML(updated);
      $("guard-label").value = updated.human?.guard_label || "";
      $("auto-label").value = updated.human?.auto_label || "";
      $("review-notes").value = updated.human?.notes || "";
      $("review-form").addEventListener("submit", (next) => saveLabel(next, updated));
      $("detail-prev").addEventListener("click", () => selectNeighbor(-1));
      $("detail-next").addEventListener("click", () => selectNeighbor(1));
      $("skip-next").addEventListener("click", () => saveLabel(null, updated, { advance: true, skip: true }));
      toast(skip ? "已跳过，继续下一条" : (advance ? "人工结论已保存，继续下一条" : "人工结论已保存"));
      await refreshSummary();
      if (advance) {
        await advanceAfterMutation(item);
      } else {
        // A reviewed Guard block leaves the default queue immediately.  Reload
        // the current page so the count, range and selected row stay truthful.
        await refreshQueue(false);
      }
    } catch (error) {
      toast(`保存失败：${error.message}`, true);
    } finally {
      if (form) form.querySelectorAll("button").forEach((control) => { control.disabled = false; });
    }
  }

  function queryParams() {
    const params = new URLSearchParams({ limit: String(state.pageSize), page: String(state.page), view: state.view });
    const status = $("status-filter").value;
    const region = $("region-filter").value;
    const query = $("search-input").value.trim();
    const humanStatus = $("human-status-filter").value;
    if (status && status !== "all") params.set("status", status);
    if (region) params.set("region", region);
    if (query) params.set("q", query);
    if (humanStatus && humanStatus !== "all") params.set("human_status", humanStatus);
    return params;
  }

  async function refreshSummary() {
    const summary = await request("/api/summary");
    renderSummary(summary);
  }

  async function refreshQueue(reset = true) {
    if (state.loading) {
      // Keep the latest filter/page intent instead of silently dropping a
      // change made while the previous request is still in flight.
      state.queuedRefresh = state.queuedRefresh === null ? reset : (state.queuedRefresh || reset);
      return;
    }
    state.loading = true;
    if (reset) { state.page = 1; state.reviews = []; }
    renderQueue();
    try {
      let result = await request(`/api/reviews?${queryParams().toString()}`);
      // A continuously ingesting queue can shrink between page clicks. Move
      // back to the last valid page instead of showing an apparently blank
      // page after a refresh.
      if (result.pages && result.page > result.pages) {
        state.page = result.pages;
        result = await request(`/api/reviews?${queryParams().toString()}`);
      } else if (!result.pages && state.page !== 1) {
        state.page = 1;
        result = await request(`/api/reviews?${queryParams().toString()}`);
      }
      state.reviews = result.reviews;
      state.total = Number(result.total || 0);
      state.page = Number(result.page || state.page || 1);
      state.pages = Number(result.pages || 0);
      state.start = Number(result.start || 0);
      state.end = Number(result.end || 0);
      state.hasPrev = Boolean(result.has_prev);
      state.hasMore = Boolean(result.has_more);
      state.humanStatus = result.human_status || $("human-status-filter").value;
      const selectedVisible = state.selectedKey && state.reviews.some((item) => reviewKey(item.region, item.event_id) === state.selectedKey);
      if (state.selectedKey && !selectedVisible) clearSelection();
      setConnection(true);
    } catch (error) {
      setConnection(false, "分析索引不可用");
      $("queue-body").innerHTML = `<tr><td colspan="5" class="empty-cell">无法读取分析索引：${escapeHTML(error.message)}</td></tr>`;
    } finally {
      state.loading = false;
      renderQueue();
      if (state.queuedRefresh !== null) {
        const nextReset = state.queuedRefresh;
        state.queuedRefresh = null;
        void refreshQueue(nextReset);
      }
    }
  }

  async function refreshAll() {
    try { await Promise.all([refreshSummary(), refreshQueue(false)]); } catch (error) { setConnection(false); toast(`刷新失败：${error.message}`, true); }
  }

  let filterTimer;
  function scheduleFilter() { window.clearTimeout(filterTimer); filterTimer = window.setTimeout(() => refreshQueue(true), 180); }

  $("refresh-button").addEventListener("click", () => { refreshAll(); });
  $("page-prev").addEventListener("click", () => { if (state.hasPrev && !state.loading) { state.page -= 1; refreshQueue(false); } });
  $("page-next").addEventListener("click", () => { if (state.hasMore && !state.loading) { state.page += 1; refreshQueue(false); } });
  $("page-first").addEventListener("click", () => { if (state.hasPrev && !state.loading) { state.page = 1; refreshQueue(false); } });
  $("page-last").addEventListener("click", () => { if (state.hasMore && !state.loading && state.pages) { state.page = state.pages; refreshQueue(false); } });
  $("page-go").addEventListener("click", () => {
    const requested = Number.parseInt($("page-input").value, 10);
    if (!Number.isFinite(requested) || requested < 1 || !state.pages) return;
    state.page = Math.min(requested, state.pages);
    refreshQueue(false);
  });
  $("page-size").addEventListener("change", () => {
    const requested = Number.parseInt($("page-size").value, 10);
    state.pageSize = [50, 100].includes(requested) ? requested : 50;
    state.page = 1;
    clearSelection();
    refreshQueue(false);
  });
  $("page-input").addEventListener("keydown", (event) => { if (event.key === "Enter") $("page-go").click(); });
  document.querySelectorAll(".queue-view").forEach((button) => button.addEventListener("click", () => {
    if (button.dataset.view === state.view) return;
    state.view = button.dataset.view;
    clearSelection();
    if (button.dataset.view !== "review" && $("human-status-filter").value === "needs_review") $("human-status-filter").value = "all";
    if (button.dataset.view === "review" && $("human-status-filter").value === "all") $("human-status-filter").value = "needs_review";
    refreshQueue(true);
  }));
  $("status-filter").addEventListener("change", scheduleFilter);
  $("region-filter").addEventListener("change", scheduleFilter);
  $("human-status-filter").addEventListener("change", scheduleFilter);
  $("search-input").addEventListener("input", scheduleFilter);
  document.addEventListener("keydown", (event) => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) return;
    const key = event.key.toLowerCase();
    if (key === "r") refreshAll();
    if (key === "j") selectNeighbor(1);
    if (key === "k") selectNeighbor(-1);
  });
  window.setInterval(() => { if (!document.hidden) refreshAll(); }, 60_000);
  refreshQueue(true).catch((error) => { setConnection(false); toast(`刷新失败：${error.message}`, true); });
  refreshSummary().catch((error) => { setConnection(false); toast(`刷新失败：${error.message}`, true); });
})();
