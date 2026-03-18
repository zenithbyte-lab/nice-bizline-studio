(() => {
  const root = document.querySelector("[data-dashboard]");
  if (!root) return;

  const jobIdsRaw = root.dataset.jobIds || "";
  const jobIds = jobIdsRaw.split(",").filter(Boolean);

  // --- Metrics ---
  const statusEl = document.getElementById("metric-status");
  const foundEl = document.getElementById("metric-found");
  const savedEl = document.getElementById("metric-saved");
  const logList = document.getElementById("log-list");
  const downloadLink = document.getElementById("download-link");

  // --- Source progress bars ---
  const sourceProgress = document.getElementById("source-progress");
  const bizdirStatusEl = document.getElementById("bizdir-status");
  const bizdirCountEl = document.getElementById("bizdir-count");
  const saraminStatusEl = document.getElementById("saramin-status");
  const saraminCountEl = document.getElementById("saramin-count");

  function setText(node, value) {
    if (node) node.textContent = value;
  }

  // --- Log rendering (filter noise, aggregate errors) ---
  function renderLogs(allEvents) {
    if (!logList) return;
    if (!allEvents.length) {
      logList.innerHTML = '<li class="log-line log-placeholder">任务已创建，等待日志…</li>';
      return;
    }

    const infoEvents = [];
    let warnCount = 0;
    let errorCount = 0;
    let skippedCount = 0;

    // Patterns for noisy messages to collapse
    const noisePatterns = [
      /: discovered 0 company url\(s\)$/,
      /: saved 0 row\(s\)$/,
      /: total 0 company URLs$/,
      /page \d+: found 0 companies$/,
      /→ https?:\/\//,  // Hide all URL lines
      /: discovered \d+ company url/,  // Hide "discovered N company url(s)"
      /: total \d+ company URL/,  // Hide "total N company URLs"
      /page \d+: found \d+ compan/,  // Hide "page N: found M companies"
      /Scanning (area|region|Saramin region)/,  // Hide "Scanning area/region X"
    ];

    allEvents.forEach((ev) => {
      const level = (ev.level || "info").toLowerCase();
      if (level === "error") {
        errorCount++;
        return;
      }
      if (level === "warn" || level === "warning") {
        warnCount++;
        return;
      }
      // Filter out noisy messages
      const msg = ev.message || "";
      if (noisePatterns.some((p) => p.test(msg))) {
        skippedCount++;
        return;
      }
      infoEvents.push(ev);
    });

    let html = infoEvents
      .map((ev) => {
        const ts = (ev.created_at || "").replace("T", " ").slice(0, 19);
        const msg = (ev.message || "").replace(/kor\.bizdirlib\.com/g, "www.nicebizline.com");
        return `<li class="log-line"><time>${ts}</time><span>${msg}</span></li>`;
      })
      .join("");

    // Summary line for suppressed messages
    const summaryParts = [];
    if (warnCount) summaryParts.push(`${warnCount} 个警告`);
    if (errorCount) summaryParts.push(`${errorCount} 个错误`);
    if (skippedCount) summaryParts.push(`${skippedCount} 条空结果已折叠`);
    if (summaryParts.length) {
      html += `<li class="log-line is-warn"><time>汇总</time><span>已静默 ${summaryParts.join("、")}（不影响正常抓取）</span></li>`;
    }

    logList.innerHTML = html;

    const pane = logList.closest(".log-pane");
    if (pane) pane.scrollTop = pane.scrollHeight;
  }

  // --- Multi-job polling ---
  const jobStates = {};

  async function fetchJob(jid) {
    const response = await fetch(`/api/jobs/${jid}`, { headers: { Accept: "application/json" } });
    if (!response.ok) return null;
    return response.json();
  }

  function mergeStatus(states) {
    const statuses = Object.values(states).map((s) => s.status);
    if (statuses.some((s) => s === "running")) return "running";
    if (statuses.some((s) => s === "queued")) return "queued";
    if (statuses.every((s) => s === "completed")) return "completed";
    if (statuses.some((s) => s === "failed")) return "failed";
    return statuses[0] || "idle";
  }

  async function refresh() {
    if (!jobIds.length) return;

    let totalFound = 0;
    let totalSaved = 0;
    let allEvents = [];
    let allRunning = false;
    let anyDownload = "";

    const results = await Promise.all(jobIds.map(fetchJob));

    results.forEach((payload, idx) => {
      if (!payload) return;
      const jid = jobIds[idx];
      const job = payload.job;
      jobStates[jid] = job;

      totalFound += job.discovered_count || 0;
      totalSaved += job.saved_count || 0;

      if (["queued", "running"].includes(job.status)) allRunning = true;
      if (!anyDownload && payload.download_url) anyDownload = payload.download_url;

      // Tag events with source
      const events = (payload.events || []).map((ev) => ({
        ...ev,
        _source: job.source === "saramin" ? "Saramin" : "BizDir",
      }));
      allEvents = allEvents.concat(events);

      // Update source-specific progress
      if (job.source === "bizdir" || job.source !== "saramin") {
        setText(bizdirStatusEl, job.status);
        setText(bizdirCountEl, String(job.saved_count || 0));
      }
      if (job.source === "saramin") {
        setText(saraminStatusEl, job.status);
        setText(saraminCountEl, String(job.saved_count || 0));
      }
    });

    // Show source progress if multi-job
    if (jobIds.length > 1 && sourceProgress) {
      sourceProgress.style.display = "";
    }

    setText(statusEl, mergeStatus(jobStates));
    setText(foundEl, String(totalFound));
    setText(savedEl, String(totalSaved));

    // Sort events by time
    allEvents.sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
    renderLogs(allEvents);

    if (downloadLink && anyDownload) {
      // For multi-job, link to first job's download
      downloadLink.href = anyDownload;
      downloadLink.classList.remove("is-hidden");
    }

    if (!allRunning) {
      clearInterval(timer);
    }
  }

  if (!jobIds.length) return;
  const timer = setInterval(refresh, 2000);
  refresh().catch(() => {});
})();
