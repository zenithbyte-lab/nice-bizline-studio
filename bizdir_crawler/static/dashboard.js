(() => {
  const root = document.querySelector("[data-dashboard]");
  if (!root) return;

  const jobId = root.dataset.jobId;
  const areaFilter = document.getElementById("area-filter");
  const selectAllButton = document.getElementById("select-all-areas");
  const clearAreasButton = document.getElementById("clear-areas");
  const selectedAreaCount = document.getElementById("selected-area-count");
  const areaRows = Array.from(document.querySelectorAll(".area-row"));
  const areaInputs = areaRows
    .map((row) => row.querySelector('input[name="area_ids"]'))
    .filter(Boolean);
  const statusEl = document.getElementById("metric-status");
  const areasEl = document.getElementById("metric-areas");
  const foundEl = document.getElementById("metric-found");
  const savedEl = document.getElementById("metric-saved");
  const logList = document.getElementById("log-list");
  const downloadLink = document.getElementById("download-link");

  function setText(node, value) {
    if (node) node.textContent = value;
  }

  function updateAreaCount() {
    const count = areaInputs.filter((input) => input.checked).length;
    setText(selectedAreaCount, String(count));
  }

  function getVisibleRows() {
    return areaRows.filter((row) => !row.classList.contains("is-hidden-row"));
  }

  function applyAreaFilter() {
    const query = (areaFilter?.value || "").trim().toLowerCase();
    areaRows.forEach((row) => {
      const name = row.dataset.areaName || "";
      const matches = !query || name.includes(query);
      row.classList.toggle("is-hidden-row", !matches);
    });
  }

  function renderLogs(events) {
    if (!logList) return;
    if (!events.length) {
      logList.innerHTML = '<li class="log-item">任务已创建，等待日志...</li>';
      return;
    }
    logList.innerHTML = events
      .map(
        (event) =>
          `<li class="log-item"><time>${event.created_at.replace("T", " ")}</time><span>${event.message}</span></li>`
      )
      .join("");
  }

  if (areaFilter) {
    areaFilter.addEventListener("input", () => {
      applyAreaFilter();
    });
  }

  if (selectAllButton) {
    selectAllButton.addEventListener("click", () => {
      getVisibleRows().forEach((row) => {
        const input = row.querySelector('input[name="area_ids"]');
        if (input) input.checked = true;
      });
      updateAreaCount();
    });
  }

  if (clearAreasButton) {
    clearAreasButton.addEventListener("click", () => {
      areaInputs.forEach((input) => {
        input.checked = false;
      });
      updateAreaCount();
    });
  }

  areaInputs.forEach((input) => {
    input.addEventListener("change", updateAreaCount);
  });

  applyAreaFilter();
  updateAreaCount();

  async function refresh() {
    if (!jobId) return;
    const response = await fetch(`/api/jobs/${jobId}`, { headers: { Accept: "application/json" } });
    if (!response.ok) return;
    const payload = await response.json();
    const job = payload.job;
    setText(statusEl, job.status);
    setText(areasEl, `${job.processed_count}/${job.selected_count}`);
    setText(foundEl, String(job.discovered_count));
    setText(savedEl, String(job.saved_count));
    renderLogs(payload.events || []);
    if (downloadLink) {
      downloadLink.href = payload.download_url;
      downloadLink.classList.remove("is-hidden");
    }
    if (!["queued", "running"].includes(job.status)) {
      clearInterval(timer);
    }
  }

  if (!jobId) return;
  const timer = setInterval(refresh, 2000);
  refresh().catch(() => {});
})();
