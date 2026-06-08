const state = {
  snapshot: null,
  refreshTimer: null,
  loading: false,
  view: "overview",
  selectedGpuIndex: null,
  selectedLogId: null,
};

const $ = (selector) => document.querySelector(selector);
const APP_ASCII = String.raw`██╗      █████╗ ██████╗ ███╗   ███╗ ██████╗ ███╗   ██╗
██║     ██╔══██╗██╔══██╗████╗ ████║██╔═══██╗████╗  ██║
██║     ███████║██████╔╝██╔████╔██║██║   ██║██╔██╗ ██║
██║     ██╔══██║██╔══██╗██║╚██╔╝██║██║   ██║██║╚██╗██║
███████╗██║  ██║██████╔╝██║ ╚═╝ ██║╚██████╔╝██║ ╚████║
╚══════╝╚═╝  ╚═╝╚═════╝ ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝`;

const SMALL_ASCII = String.raw`██╗      █████╗ ██████╗
██║     ██╔══██╗██╔══██╗
██║     ███████║██████╔╝
██║     ██╔══██║██╔══██╗
███████╗██║  ██║██████╔╝
╚══════╝╚═╝  ╚═╝╚═════╝`;

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function clampPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(100, number));
}

function formatTime(timestampSeconds) {
  if (!timestampSeconds) return "未知";
  return new Date(timestampSeconds * 1000).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatRuntime(seconds) {
  if (!Number.isFinite(Number(seconds))) return "未知";
  const value = Math.max(0, Number(seconds));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function formatMib(value) {
  const number = Number(value || 0);
  if (number >= 1024) return `${(number / 1024).toFixed(1)}G`;
  return `${Math.round(number)}M`;
}

function gpuMemoryPercent(gpu) {
  return gpu.memory_total_mib ? (gpu.memory_used_mib / gpu.memory_total_mib) * 100 : 0;
}

function gpuSeverity(gpu) {
  const memoryPercent = gpuMemoryPercent(gpu);
  const hasProcesses = (gpu.processes || []).length > 0;
  if ((gpu.temperature_c || 0) >= 78) return "hot";
  if ((gpu.temperature_c || 0) >= 68 || memoryPercent >= 90) return "warm";
  if (!hasProcesses && gpu.utilization_gpu < 20) return "free";
  return "busy";
}

function severityLabel(severity) {
  return {
    free: "无进程",
    busy: "active",
    warm: "hot load",
    hot: "alert",
  }[severity] || "active";
}

function severityClass(severity) {
  if (severity === "free") return "green";
  if (severity === "warm" || severity === "hot") return "amber";
  return "";
}

function gpuOwners(gpu) {
  const owners = [...new Set((gpu.processes || []).map((process) => process.username).filter(Boolean))];
  return owners.length ? owners.join(", ") : "none";
}

function gpuPrimaryTask(gpu) {
  const process = (gpu.processes || [])[0];
  if (process) return process.command || `PID ${process.pid}`;
  return `no compute process, cache ${formatMib(gpu.memory_used_mib)}`;
}

function compareGpuForPicking(left, right) {
  const leftSeverity = gpuSeverity(left);
  const rightSeverity = gpuSeverity(right);
  const rank = { free: 0, busy: 1, warm: 2, hot: 3 };
  const severityDelta = rank[leftSeverity] - rank[rightSeverity];
  if (severityDelta !== 0) return severityDelta;
  const processDelta = (left.processes || []).length - (right.processes || []).length;
  if (processDelta !== 0) return processDelta;
  const utilDelta = (left.utilization_gpu || 0) - (right.utilization_gpu || 0);
  if (utilDelta !== 0) return utilDelta;
  return (left.memory_used_mib || 0) - (right.memory_used_mib || 0);
}

function sortedGpus(gpus) {
  return [...gpus].sort(compareGpuForPicking);
}

function orderedGpus(gpus) {
  return [...gpus].sort((left, right) => Number(left.index) - Number(right.index));
}

function selectedGpu(gpus) {
  if (!gpus.length) return null;
  if (state.selectedGpuIndex !== null) {
    const found = gpus.find((gpu) => String(gpu.index) === String(state.selectedGpuIndex));
    if (found) return found;
  }
  return sortedGpus(gpus)[0];
}

function selectedOverviewGpu(gpus) {
  if (!gpus.length) return null;
  if (state.selectedGpuIndex !== null) {
    const found = gpus.find((gpu) => String(gpu.index) === String(state.selectedGpuIndex));
    if (found) return found;
  }
  return orderedGpus(gpus)[0];
}

function selectedLog(logs) {
  if (!logs.length) return null;
  if (state.selectedLogId) {
    const found = logs.find((log) => log.id === state.selectedLogId);
    if (found) return found;
  }
  return logs[0];
}

async function fetchJson(url, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), options.timeout || 8000);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
      },
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      const message = payload.detail?.message || payload.message || `HTTP ${response.status}`;
      throw new Error(message);
    }
    return await response.json();
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("请求超时，请检查服务是否还在运行");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

async function loadSnapshot() {
  if (state.loading) return;
  state.loading = true;
  try {
    state.snapshot = await fetchJson("/api/snapshot");
    renderSnapshot(state.snapshot);
    scheduleRefresh(state.snapshot.host?.refresh_seconds || 1);
  } catch (error) {
    renderWarnings([error.message]);
  } finally {
    state.loading = false;
  }
}

function scheduleRefresh(seconds) {
  if (state.refreshTimer) window.clearInterval(state.refreshTimer);
  const interval = Math.max(0.25, Number(seconds) || 1) * 1000;
  state.refreshTimer = window.setInterval(loadSnapshot, interval);
}

function setView(view) {
  state.view = view;
  renderActiveNav();
  if (state.snapshot) renderActiveView();
}

function selectGpu(index) {
  state.selectedGpuIndex = index;
  setView("gpu");
}

function selectLog(logId) {
  state.selectedLogId = logId;
  setView("logs");
}

function renderSnapshot(snapshot) {
  const generatedAt = new Date(snapshot.generated_at * 1000);
  $("#host-label").textContent = snapshot.host.hostname;
  $("#mode-label").textContent = snapshot.host.mode === "demo" ? "demo" : "server";
  $("#updated-label").textContent = generatedAt.toLocaleTimeString("zh-CN");
  renderWarnings(snapshot.warnings || []);
  renderActiveNav();
  renderActiveView();
}

function renderActiveNav() {
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === state.view);
  });
}

function renderWarnings(warnings) {
  $("#warning-region").innerHTML = warnings
    .slice(0, 4)
    .map((warning) => `<div class="warning">${escapeHtml(warning)}</div>`)
    .join("");
}

function renderActiveView() {
  const snapshot = state.snapshot;
  if (!snapshot) {
    $("#app-view").innerHTML = `<section class="panel empty">正在连接 LabMon...</section>`;
    return;
  }
  const renderers = {
    overview: renderOverview,
    gpu: renderGpuView,
    logs: renderLogsView,
    host: renderHostView,
  };
  $("#app-view").innerHTML = (renderers[state.view] || renderOverview)(snapshot);
}

function renderOverview(snapshot) {
  const gpus = snapshot.gpus || [];
  const ordered = orderedGpus(gpus);
  const selected = selectedOverviewGpu(ordered);
  if (selected) state.selectedGpuIndex = selected.index;

  return `
    <section class="hero-grid overview-hero">
      <div>
        <pre class="ascii">${escapeHtml(APP_ASCII)}</pre>
        <div class="command">
          <code>$ labmon watch --slots ordered --select gpu:${selected ? escapeHtml(selected.index) : "0"}</code>
          <button class="solid-button" type="button" data-action="refresh">refresh</button>
        </div>
      </div>
    </section>

    ${renderSelectedOverviewGpu(selected)}

    <section class="panel overview-table">
      <div class="panel-head">
        <h2>GPU Slots</h2>
        <span class="muted">ordered by index</span>
      </div>
      ${renderGpuSlots(ordered, selected)}
    </section>
  `;
}

function renderSelectedOverviewGpu(gpu) {
  if (!gpu) {
    return `<section class="panel empty">没有 GPU 数据。</section>`;
  }
  const severity = gpuSeverity(gpu);
  const processCount = (gpu.processes || []).length;
  return `
    <section class="panel selected-gpu-panel">
      <div class="panel-head">
        <h2>Selected GPU</h2>
        <span class="badge ${severityClass(severity)}">${escapeHtml(severityLabel(severity))}</span>
      </div>
      <div class="selected-gpu-body">
        <div class="selected-gpu-main">
          <span class="muted">gpu:${escapeHtml(gpu.index)}</span>
          <strong>GPU ${escapeHtml(gpu.index)} / ${escapeHtml(gpu.name || "GPU")}</strong>
          <p class="truncate" title="${escapeHtml(gpuPrimaryTask(gpu))}">${escapeHtml(gpuPrimaryTask(gpu))}</p>
        </div>
        <div class="selected-metrics">
          <div><span>owner</span><strong>${escapeHtml(gpuOwners(gpu))}</strong></div>
          <div><span>util</span><strong>${clampPercent(gpu.utilization_gpu).toFixed(0)}%</strong></div>
          <div><span>memory</span><strong>${formatMib(gpu.memory_used_mib)} / ${formatMib(gpu.memory_total_mib)}</strong></div>
          <div><span>temp</span><strong>${gpu.temperature_c ?? "unknown"} C</strong></div>
          <div><span>power</span><strong>${gpu.power_draw_w == null ? "unknown" : `${Math.round(gpu.power_draw_w)} W`}</strong></div>
          <div><span>processes</span><strong>${processCount}</strong></div>
        </div>
      </div>
    </section>
  `;
}

function renderHostSummary(host, freeCount, gpuCount) {
  return `
    <aside class="panel status-box">
      <h2>Host</h2>
      ${statLine("cpu", host.cpu_percent, `${Math.round(host.cpu_percent || 0)}%`)}
      ${statLine("memory", host.memory.percent, `${host.memory.used_gib}G`)}
      ${statLine("disk", host.disk.percent, `${host.disk.used_gib}G`, "green")}
      ${statLine("free gpu", gpuCount ? (freeCount / gpuCount) * 100 : 0, `${freeCount} / ${gpuCount}`, "green")}
    </aside>
  `;
}

function statLine(label, percent, value, tone = "") {
  return `
    <div class="stat-line">
      <span>${escapeHtml(label)}</span>
      <div class="bar"><div class="fill ${tone}" style="--value: ${clampPercent(percent)}%"></div></div>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function renderGpuSlots(gpus, selected) {
  if (!gpus.length) {
    return `<div class="empty">没有读取到 GPU。demo 模式请设置 LABMON_DEMO=1，服务器模式请检查 nvidia-smi。</div>`;
  }
  const rows = gpus
    .map((gpu) => {
      const severity = gpuSeverity(gpu);
      const isSelected = selected && String(gpu.index) === String(selected.index);
      const rowClass = isSelected ? "is-selected" : severity === "warm" || severity === "hot" ? "is-hot" : "";
      const badgeClass = severityClass(severity);
      return `
        <tr class="${rowClass}" data-select-gpu-index="${escapeHtml(gpu.index)}">
          <td class="rank-col">${escapeHtml(gpu.index)}</td>
          <td class="gpu-col">
            <strong>GPU ${escapeHtml(gpu.index)}</strong>
            <div class="task" title="${escapeHtml(gpuPrimaryTask(gpu))}">${escapeHtml(gpuPrimaryTask(gpu))}</div>
          </td>
          <td class="owner-col">${escapeHtml(gpuOwners(gpu))}</td>
          <td class="num-col">${clampPercent(gpu.utilization_gpu).toFixed(0)}%</td>
          <td class="num-col">${formatMib(gpu.memory_used_mib)}</td>
          <td><span class="badge ${badgeClass}">${escapeHtml(severityLabel(severity))}</span></td>
          <td class="action-col"><button class="ghost-button" type="button" data-select-gpu-index="${escapeHtml(gpu.index)}">${isSelected ? "selected" : "select"}</button></td>
        </tr>
      `;
    })
    .join("");
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th class="rank-col">Slot</th>
            <th class="gpu-col">GPU</th>
            <th class="owner-col">Owner</th>
            <th class="num-col">Util</th>
            <th class="num-col">Memory</th>
            <th>Status</th>
            <th class="action-col"></th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderRecommendation(gpu) {
  if (!gpu) {
    return `<section class="panel directory"><div class="empty">没有可推荐的 GPU。</div></section>`;
  }
  const severity = gpuSeverity(gpu);
  const reason = severity === "free" ? "无 compute 进程" : "负载最低";
  return `
    <section class="panel directory">
      <div class="directory-row"><span>pick</span><strong>GPU ${escapeHtml(gpu.index)}</strong><span class="badge ${severityClass(severity)}">${escapeHtml(severity === "free" ? "free" : reason)}</span></div>
      <div class="directory-row"><span>owner</span><strong>${escapeHtml(gpuOwners(gpu))}</strong><span>${escapeHtml(severityLabel(severity))}</span></div>
      <div class="directory-row"><span>memory</span><strong>${formatMib(gpu.memory_used_mib)} / ${formatMib(gpu.memory_total_mib)}</strong><span>${clampPercent(gpuMemoryPercent(gpu)).toFixed(0)}%</span></div>
      <div class="directory-row"><span>temp</span><strong>${gpu.temperature_c ?? "unknown"} C</strong><span>${gpu.power_draw_w == null ? "unknown" : `${Math.round(gpu.power_draw_w)}W`}</span></div>
    </section>
  `;
}

function renderLogSummary(log) {
  if (!log) {
    return `<section class="panel directory"><div class="empty">没有发现日志。可通过 LABMON_LOG_ROOTS 配置扫描目录。</div></section>`;
  }
  const progress = log.progress || {};
  return `
    <section class="panel directory">
      <div class="directory-row"><span>logs</span><strong class="truncate">${escapeHtml(log.name)}</strong><button class="ghost-button" type="button" data-log-id="${escapeHtml(log.id)}">tail</button></div>
      <div class="directory-row"><span>step</span><strong>${escapeHtml(progress.step || progress.epoch || "-")}</strong><span>moving</span></div>
      <div class="directory-row"><span>reward</span><strong>${escapeHtml(progress.reward || progress.loss || "-")}</strong><span>${progress.reward ? "latest" : "loss"}</span></div>
      <div class="directory-row"><span>eta</span><strong>${escapeHtml(progress.eta || "-")}</strong><span>recent</span></div>
    </section>
  `;
}

function renderGpuView(snapshot) {
  const gpus = snapshot.gpus || [];
  const ordered = orderedGpus(gpus);
  const gpu = selectedOverviewGpu(ordered);
  if (!gpu) return `<section class="panel empty">没有 GPU 数据。</section>`;
  state.selectedGpuIndex = gpu.index;
  const severity = gpuSeverity(gpu);
  const log = selectedLog(snapshot.logs || []);
  return `
    <section class="gpu-page">
      <div class="command gpu-command">
        <code>$ labmon inspect gpu:${escapeHtml(gpu.index)} --processes --logs latest</code>
        <button class="solid-button" type="button" data-action="refresh">refresh</button>
      </div>

      ${renderSelectedOverviewGpu(gpu)}

      <section class="panel overview-table gpu-slots-panel">
        <div class="panel-head">
          <h2>GPU Slots</h2>
          <span class="muted">ordered by index</span>
        </div>
        ${renderGpuSlots(ordered, gpu)}
      </section>

      <section class="panel process-list">
        <div class="panel-head">
          <h2>Processes on GPU ${escapeHtml(gpu.index)}</h2>
          <span class="badge ${severityClass(severity)}">${escapeHtml(severityLabel(severity))}</span>
        </div>
        ${renderProcessLines(gpu)}
      </section>

      ${renderDetailLog(log)}
    </section>
  `;
}

function renderGpuSidebarItem(gpu, activeIndex) {
  const severity = gpuSeverity(gpu);
  const owner = gpuOwners(gpu);
  const label = severity === "free" ? "pick" : `${clampPercent(gpu.utilization_gpu).toFixed(0)}%`;
  return `
    <button class="sidebar-item ${String(gpu.index) === String(activeIndex) ? "is-active" : ""}" type="button" data-gpu-index="${escapeHtml(gpu.index)}">
      <span>${escapeHtml(gpu.index)}</span>
      <strong class="truncate">${escapeHtml(owner === "none" ? "no process" : owner)}</strong>
      <span class="${severity === "free" ? "badge green" : ""}">${escapeHtml(label)}</span>
    </button>
  `;
}

function gpuSummarySentence(gpu) {
  const processCount = (gpu.processes || []).length;
  if (processCount === 0) return `No compute process. Memory cache ${formatMib(gpu.memory_used_mib)}.`;
  return `${processCount} compute process${processCount > 1 ? "es" : ""}, ${formatMib(gpu.memory_used_mib)} memory used.`;
}

function renderGpuKv(gpu) {
  const runtime = (gpu.processes || []).length
    ? formatRuntime(Math.max(...gpu.processes.map((process) => process.runtime_seconds || 0)))
    : "-";
  return `
    <aside class="panel kv">
      <div><span>owner</span><strong>${escapeHtml(gpuOwners(gpu))}</strong></div>
      <div><span>memory</span><strong>${formatMib(gpu.memory_used_mib)} / ${formatMib(gpu.memory_total_mib)}</strong></div>
      <div><span>temp</span><strong>${gpu.temperature_c ?? "unknown"} C</strong></div>
      <div><span>power</span><strong>${gpu.power_draw_w == null ? "unknown" : `${Math.round(gpu.power_draw_w)} W`}</strong></div>
      <div><span>runtime</span><strong>${escapeHtml(runtime)}</strong></div>
    </aside>
  `;
}

function renderProcessLines(gpu) {
  const processes = gpu.processes || [];
  if (!processes.length) {
    return `<div class="empty">当前没有 compute 进程。仍建议留意显存缓存和短任务。</div>`;
  }
  return processes
    .map(
      (process) => `
        <div class="process-line">
          <strong>${escapeHtml(process.username)}</strong>
          <code>${escapeHtml(process.command)}</code>
          <strong>${formatMib(process.gpu_memory_mib)}</strong>
        </div>
      `,
    )
    .join("");
}

function renderDetailLog(log) {
  if (!log) {
    return `<section class="panel log-large"><div class="panel-head"><h2>Logs</h2></div><div class="empty">没有发现日志。</div></section>`;
  }
  return `
    <section class="panel log-large">
      <div class="panel-head">
        <h2>${escapeHtml(log.name)}</h2>
        <button class="ghost-button" type="button" data-log-id="${escapeHtml(log.id)}">tail</button>
      </div>
      <pre class="terminal">$ tail -f ${escapeHtml(log.name)}

${escapeHtml(log.last_line || "没有内容")}

$ parsed
${renderProgressText(log.progress || {})}</pre>
    </section>
  `;
}

function renderProgressText(progress) {
  const entries = Object.entries(progress);
  if (!entries.length) return "未识别进度";
  return entries.map(([key, value]) => `${key} ${value}`).join("\n");
}

function renderLogsView(snapshot) {
  const logs = snapshot.logs || [];
  const log = selectedLog(logs);
  if (log) state.selectedLogId = log.id;
  return `
    <section class="logs-layout">
      <section class="panel">
        <div class="panel-head">
          <h2>Logs</h2>
          <span class="muted">${logs.length} files</span>
        </div>
        <div class="log-list">
          ${
            logs.length
              ? logs.map((item) => renderLogRow(item, log?.id)).join("")
              : `<div class="empty">没有发现日志。可通过 LABMON_LOG_ROOTS 配置扫描目录。</div>`
          }
        </div>
      </section>
      ${renderLogInspector(log)}
    </section>
  `;
}

function renderLogRow(log, activeId) {
  const progress = log.progress || {};
  const chips = Object.entries(progress)
    .slice(0, 4)
    .map(([key, value]) => `<span class="metric-chip">${escapeHtml(key)} ${escapeHtml(value)}</span>`)
    .join("");
  return `
    <button class="log-row ${log.id === activeId ? "is-active" : ""}" type="button" data-select-log-id="${escapeHtml(log.id)}">
      <span>
        <strong>${escapeHtml(log.name)}</strong>
        <span class="task" title="${escapeHtml(log.path)}">${escapeHtml(log.path)}</span>
        <span class="chip-row">${chips || `<span class="metric-chip">未识别进度</span>`}</span>
      </span>
      <span class="muted">${escapeHtml(formatTime(log.modified_at))}</span>
    </button>
  `;
}

function renderLogInspector(log) {
  if (!log) {
    return `<section class="panel"><div class="panel-head"><h2>tail</h2></div><div class="empty">选择一个日志文件。</div></section>`;
  }
  return `
    <section class="panel log-large">
      <div class="panel-head">
        <h2>${escapeHtml(log.name)}</h2>
        <button class="ghost-button" type="button" data-log-id="${escapeHtml(log.id)}">open tail</button>
      </div>
      <pre class="terminal">$ tail -n 3 ${escapeHtml(log.name)}
${escapeHtml(log.last_line || "没有内容")}

$ parsed
${renderProgressText(log.progress || {})}</pre>
    </section>
  `;
}

function renderHostView(snapshot) {
  const host = snapshot.host;
  const freeCount = (snapshot.gpus || []).filter((gpu) => gpuSeverity(gpu) === "free").length;
  return `
    <section class="host-grid">
      <section class="panel">
        <div class="panel-head">
          <h2>Server</h2>
          <span class="muted">${escapeHtml(host.hostname)}</span>
        </div>
        <div class="host-meters">
          ${hostMeter("cpu", host.cpu_percent, `${Math.round(host.cpu_percent || 0)}%`, host.cpu_percent > 85 ? "amber" : "")}
          ${hostMeter("memory", host.memory.percent, `${host.memory.used_gib} / ${host.memory.total_gib} GiB`, host.memory.percent > 85 ? "amber" : "")}
          ${hostMeter("disk", host.disk.percent, `${host.disk.used_gib} / ${host.disk.total_gib} GiB`, host.disk.percent > 85 ? "amber" : "green")}
          ${hostMeter("free gpu", snapshot.gpus.length ? (freeCount / snapshot.gpus.length) * 100 : 0, `${freeCount} / ${snapshot.gpus.length}`, "green")}
        </div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>server status</h2>
          <span class="badge">${escapeHtml(host.mode)}</span>
        </div>
        <pre class="server-status-output">$ labmon status
hostname ${escapeHtml(host.hostname)}
platform ${escapeHtml(host.platform)}
refresh ${escapeHtml(host.refresh_seconds)}s
load ${escapeHtml(Array.isArray(host.load_average) ? host.load_average.join(" / ") : "unavailable")}
warnings ${escapeHtml((snapshot.warnings || []).length)}</pre>
      </section>
    </section>
  `;
}

function hostMeter(label, percent, value, tone = "") {
  return `
    <div class="host-meter">
      <div class="host-meter__row">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>
      <div class="bar"><div class="fill ${tone}" style="--value: ${clampPercent(percent)}%"></div></div>
    </div>
  `;
}

async function openLog(logId) {
  const dialog = $("#log-dialog");
  $("#dialog-title").textContent = "读取日志";
  $("#dialog-path").textContent = logId;
  $("#log-content").textContent = "加载中...";
  dialog.showModal();

  try {
    const payload = await fetchJson(`/api/logs/${encodeURIComponent(logId)}?lines=240`);
    $("#dialog-title").textContent = payload.entry.name;
    $("#dialog-path").textContent = payload.entry.path;
    $("#log-content").textContent = payload.lines.join("\n");
  } catch (error) {
    $("#dialog-title").textContent = "日志读取失败";
    $("#log-content").textContent = error.message;
  }
}

$("#refresh-button").addEventListener("click", loadSnapshot);
$("#close-dialog").addEventListener("click", () => $("#log-dialog").close());
document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});
$("#app-view").addEventListener("click", (event) => {
  const refresh = event.target.closest("[data-action='refresh']");
  if (refresh) {
    loadSnapshot();
    return;
  }
  const selectGpuButton = event.target.closest("[data-select-gpu-index]");
  if (selectGpuButton) {
    state.selectedGpuIndex = selectGpuButton.dataset.selectGpuIndex;
    renderActiveView();
    return;
  }
  const gpuButton = event.target.closest("[data-gpu-index]");
  if (gpuButton) {
    selectGpu(gpuButton.dataset.gpuIndex);
    return;
  }
  const selectLogButton = event.target.closest("[data-select-log-id]");
  if (selectLogButton) {
    state.selectedLogId = selectLogButton.dataset.selectLogId;
    renderActiveView();
    return;
  }
  const logButton = event.target.closest("[data-log-id]");
  if (logButton) {
    openLog(logButton.dataset.logId);
  }
});

loadSnapshot();
