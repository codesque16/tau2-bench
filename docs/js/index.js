(function () {
  const taskList = document.getElementById("task-list");
  const filterBtns = document.querySelectorAll(".filter-btn[data-filter]");
  const runSelectWrap = document.getElementById("run-select-wrap");
  const runSelect = document.getElementById("run-select");
  const subtitleEl = document.getElementById("subtitle");

  function getDataPath(path) {
    const base = document.querySelector('base')?.getAttribute('href') || '';
    return (base + path).replace(/\/+/g, '/');
  }

  function getRunFromUrl() {
    const params = new URLSearchParams(document.location.search);
    return params.get("run") || "";
  }

  function setRunInUrl(runId) {
    const url = new URL(document.location.href);
    if (runId) url.searchParams.set("run", runId);
    else url.searchParams.delete("run");
    window.history.replaceState({}, "", url.pathname + url.search);
  }

  function renderRow(t, runId) {
    const pass = t.reward === 1.0;
    const rewardClass = pass ? "pass" : "fail";
    const rewardLabel = pass ? "Pass" : "Fail";
    const scenario = (t.scenario_preview || "").trim() || "—";
    
    // We want the viewer to show the original task_id, but load the file by sim_id
    let viewUrl = "viewer.html?task=" + encodeURIComponent(t.task_id);
    if (t.sim_id && t.sim_id !== t.task_id) {
      viewUrl += "&sim=" + encodeURIComponent(t.sim_id);
    }
    if (runId) {
      viewUrl += "&run=" + encodeURIComponent(runId);
    }
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

  function loadTaskIndex(indexUrl, runId) {
    fetch(getDataPath(indexUrl))
      .then(function (r) {
        if (!r.ok) throw new Error("Failed to load index");
        return r.json();
      })
      .then(function (data) {
        const tasks = data.tasks || [];
        taskList.innerHTML = tasks.map(function (t) { return renderRow(t, runId); }).join("");
        applyFilter("all");
      })
      .catch(function (err) {
        taskList.innerHTML =
          '<tr><td colspan="5" class="error-msg">Could not load task index for this run.</td></tr>';
      });
  }

  function showError(msg) {
    taskList.innerHTML = '<tr><td colspan="5" class="error-msg">' + escapeHtml(msg) + '</td></tr>';
  }

  // Try runs.json first (multi-run mode)
  fetch(getDataPath("data/runs.json"))
    .then(function (r) {
      if (!r.ok) {
        runSelectWrap.style.display = "none";
        loadTaskIndex("data/index.json", null);
        return null;
      }
      return r.json();
    })
    .then(function (data) {
      if (!data || !data.runs || !data.runs.length) {
        runSelectWrap.style.display = "none";
        return loadTaskIndex("data/index.json", null);
      }

      const runs = data.runs;
      function runSummary(r) {
        var acc = r.accuracy != null ? r.accuracy : (r.num_tasks ? Math.round(100 * (r.num_passed || 0) / r.num_tasks) : 0);
        return (r.num_passed != null ? r.num_passed + "/" + r.num_tasks + " passed" : r.num_tasks + " tasks") + " · " + acc + "%";
      }
      function accuracyClass(acc) {
        if (acc >= 70) return "high";
        if (acc >= 40) return "mid";
        return "low";
      }
      runSelectWrap.style.display = "flex";
      var indexActionsTop = document.getElementById("index-actions-top");
      if (indexActionsTop) indexActionsTop.style.display = "flex";
      runSelect.innerHTML = runs.map(function (r) {
        return '<option value="' + escapeHtml(r.id) + '">' + escapeHtml(r.label) + " — " + runSummary(r) + "</option>";
      }).join("");

      var runId = getRunFromUrl();
      if (!runId || !runs.some(function (r) { return r.id === runId; })) {
        runId = runs[0].id;
        setRunInUrl(runId);
      }
      runSelect.value = runId;
      function setSubtitle(run) {
        if (!run) return;
        var acc = run.accuracy != null ? run.accuracy : (run.num_tasks ? Math.round(100 * (run.num_passed || 0) / run.num_tasks) : 0);
        var badge = '<span class="accuracy-badge ' + accuracyClass(acc) + '">' + (run.num_passed != null ? run.num_passed + "/" + run.num_tasks : run.num_tasks) + " passed · " + acc + "%</span>";
        subtitleEl.innerHTML = "Select a task to view trajectory.";

        var simInfoWrap = document.getElementById("sim-info-wrap");
        if (simInfoWrap) {
          if (run.sim_info) {
            simInfoWrap.style.display = "grid";
            var si = run.sim_info;
            var extractLlm = function (info) {
              if (!info) return "Unknown";
              var llm = info.llm || info.implementation || "Unknown";
              if (llm.startsWith("gemini/")) llm = llm.substring(7);
              return llm;
            };
            var agent = extractLlm(si.agent_info);
            var sim = extractLlm(si.user_info);
            var commit = si.git_commit ? si.git_commit.substring(0, 7) : "N/A";
            var seed = si.seed != null ? si.seed : "N/A";

            var policyKey = "policy_" + run.id;
            var guideKey = "guide_" + run.id;
            window._dialogTexts = window._dialogTexts || {};
            window._dialogTexts[policyKey] = si.environment_info?.policy || "";
            window._dialogTexts[guideKey] = si.user_info?.global_simulation_guidelines || "";

            simInfoWrap.innerHTML =
              '<div class="sim-info-section">' +
              '<h3>General</h3>' +
              '<div class="sim-info-item"><span class="sim-info-label">Domain:</span> <span class="sim-info-val">' + escapeHtml(si.environment_info?.domain_name || run.domain || "N/A") + '</span></div>' +
              '<div class="sim-info-item"><span class="sim-info-label">Commit:</span> <span class="sim-info-val font-mono">' + escapeHtml(commit) + '</span></div>' +
              '<div class="sim-info-item"><span class="sim-info-label">Seed:</span> <span class="sim-info-val font-mono">' + escapeHtml(String(seed)) + '</span></div>' +
              '<div class="sim-info-item"><span class="sim-info-label">Max Steps:</span> <span class="sim-info-val">' + escapeHtml(String(si.max_steps)) + '</span></div>' +
              '<div class="sim-info-item pt-1">' + badge + '</div>' +
              '</div>' +
              '<div class="sim-info-section">' +
              '<h3>Agent Info</h3>' +
              '<div class="sim-info-item"><span class="sim-info-label">Impl:</span> <span class="sim-info-val">' + escapeHtml(si.agent_info?.implementation || "N/A") + '</span></div>' +
              '<div class="sim-info-item"><span class="sim-info-label">LLM:</span> <span class="sim-info-val">' + escapeHtml(agent) + '</span></div>' +
              '<div class="sim-info-item"><span class="sim-info-label">Args:</span> <span class="sim-info-val">' + escapeHtml(JSON.stringify(si.agent_info?.llm_args || {})) + '</span></div>' +
              (si.total_agent_cost != null ? '<div class="sim-info-item"><span class="sim-info-label">Cost:</span> <span class="sim-info-val font-mono">$' + escapeHtml(Number(si.total_agent_cost).toFixed(4)) + '</span></div>' : '') +
              (window._dialogTexts[policyKey] ? '<div class="sim-info-item mt-1"><button class="view-text-btn" data-title="Agent Policy" data-key="' + policyKey + '">View Policy</button></div>' : '') +
              '</div>' +
              '<div class="sim-info-section">' +
              '<h3>User Info</h3>' +
              '<div class="sim-info-item"><span class="sim-info-label">Impl:</span> <span class="sim-info-val">' + escapeHtml(si.user_info?.implementation || "N/A") + '</span></div>' +
              '<div class="sim-info-item"><span class="sim-info-label">LLM:</span> <span class="sim-info-val">' + escapeHtml(sim) + '</span></div>' +
              '<div class="sim-info-item"><span class="sim-info-label">Args:</span> <span class="sim-info-val">' + escapeHtml(JSON.stringify(si.user_info?.llm_args || {})) + '</span></div>' +
              (si.total_user_cost != null ? '<div class="sim-info-item"><span class="sim-info-label">Cost:</span> <span class="sim-info-val font-mono">$' + escapeHtml(Number(si.total_user_cost).toFixed(4)) + '</span></div>' : '') +
              (window._dialogTexts[guideKey] ? '<div class="sim-info-item mt-1"><button class="view-text-btn" data-title="User Guidelines" data-key="' + guideKey + '">View Guidelines</button></div>' : '') +
              '</div>';

            var textBtns = simInfoWrap.querySelectorAll(".view-text-btn");
            textBtns.forEach(function (btn) {
              btn.addEventListener("click", function () {
                var dialog = document.getElementById("info-dialog");
                var titleEl = document.getElementById("dialog-title");
                var textEl = document.getElementById("dialog-text");
                if (dialog && titleEl && textEl) {
                  titleEl.textContent = btn.getAttribute("data-title");
                  textEl.textContent = window._dialogTexts[btn.getAttribute("data-key")] || "";
                  dialog.showModal();
                }
              });
            });
          } else {
            simInfoWrap.style.display = "none";
          }
        }
      }
      var currentRun = runs.find(function (r) { return r.id === runId; });
      setSubtitle(currentRun || { id: runId, label: runId, num_tasks: 0, num_passed: 0, accuracy: 0 });
      loadTaskIndex("data/" + runId + "/index.json", runId);

      runSelect.addEventListener("change", function () {
        var id = runSelect.value;
        setRunInUrl(id);
        var run = runs.find(function (r) { return r.id === id; });
        setSubtitle(run || { id: id, label: id, num_tasks: 0, num_passed: 0, accuracy: 0 });
        loadTaskIndex("data/" + id + "/index.json", id);
      });
    })
    .catch(function () {
      // Network error or invalid JSON: try legacy single index
      runSelectWrap.style.display = "none";
      loadTaskIndex("data/index.json", null);
    });

  filterBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      applyFilter(btn.getAttribute("data-filter"));
    });
  });
})();
