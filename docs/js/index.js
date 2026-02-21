(function () {
  const taskList = document.getElementById("task-list");
  const filterBtns = document.querySelectorAll(".filter-btn[data-filter]");

  function getDataPath(path) {
    const base = document.querySelector('base')?.getAttribute('href') || '';
    return (base + path).replace(/\/+/g, '/');
  }

  function renderRow(t) {
    const pass = t.reward === 1.0;
    const rewardClass = pass ? "pass" : "fail";
    const rewardLabel = pass ? "Pass" : "Fail";
    const scenario = (t.scenario_preview || "").trim() || "—";
    const viewUrl = "viewer.html?task=" + encodeURIComponent(t.task_id);
    return (
      '<tr data-pass="' + pass + '">' +
      '<td class="task-id">' + escapeHtml(t.task_id) + '</td>' +
      '<td><span class="reward-badge ' + rewardClass + '">' + rewardLabel + '</span></td>' +
      '<td>' + (t.duration_sec != null ? t.duration_sec + 's' : '—') + '</td>' +
      '<td><span class="scenario-preview" title="' + escapeHtml(scenario) + '">' + escapeHtml(scenario) + '</span></td>' +
      '<td><a href="' + escapeHtml(viewUrl) + '" class="view-link">View trajectory</a></td>' +
      '</tr>'
    );
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function applyFilter(filter) {
    const rows = taskList.querySelectorAll("tr");
    rows.forEach(function (row) {
      const pass = row.getAttribute("data-pass") === "true";
      const show =
        filter === "all" ||
        (filter === "pass" && pass) ||
        (filter === "fail" && !pass);
      row.style.display = show ? "" : "none";
    });
    filterBtns.forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-filter") === filter);
    });
  }

  fetch(getDataPath("data/index.json"))
    .then(function (r) {
      if (!r.ok) throw new Error("Failed to load index");
      return r.json();
    })
    .then(function (data) {
      const tasks = data.tasks || [];
      taskList.innerHTML = tasks.map(renderRow).join("");
      applyFilter("all");
    })
    .catch(function (err) {
      taskList.innerHTML =
        '<tr><td colspan="5" class="error-msg">Could not load task index. Run <code>python3 scripts/export_trajectories_for_pages.py</code> from tau2-bench.</td></tr>';
    });

  filterBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      applyFilter(btn.getAttribute("data-filter"));
    });
  });
})();
