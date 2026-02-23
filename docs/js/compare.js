(function () {
  function getDataPath(path) {
    var base = document.querySelector("base") && document.querySelector("base").getAttribute("href") || "";
    return (base + path).replace(/\/+/g, "/");
  }

  function escapeHtml(s) {
    if (s == null) return "";
    var div = document.createElement("div");
    div.textContent = String(s);
    return div.innerHTML;
  }

  function formatTs(ts) {
    if (!ts) return "—";
    try {
      var d = new Date(ts);
      return isNaN(d.getTime()) ? ts : d.toLocaleString();
    } catch (_) { return ts; }
  }

  function renderTaskDetails(task) {
    if (!task || !task.user_scenario || !task.user_scenario.instructions)
      return "<p>No task details.</p>";
    var i = task.user_scenario.instructions;
    return "<dl>" +
      "<dt>Reason for call</dt><dd>" + escapeHtml(i.reason_for_call || "—") + "</dd>" +
      "<dt>Known info</dt><dd>" + escapeHtml(i.known_info || "—") + "</dd>" +
      "<dt>Unknown info</dt><dd>" + escapeHtml(i.unknown_info || "—") + "</dd>" +
      "<dt>Task instructions</dt><dd>" + escapeHtml(i.task_instructions || "—") + "</dd>" +
      "</dl>";
  }

  function renderRunInfo(run) {
    if (!run) return "";
    return "<span>Duration: " + (run.duration_sec != null ? run.duration_sec + "s" : "—") + "</span>" +
      "<span>End: " + escapeHtml(formatTs(run.timestamp)) + "</span>" +
      "<span>Termination: " + escapeHtml(run.termination_reason || "—") + "</span>" +
      "<span>Agent cost: " + (run.agent_cost != null ? run.agent_cost.toFixed(4) : "—") + "</span>" +
      "<span>User cost: " + (run.user_cost != null ? run.user_cost.toFixed(4) : "—") + "</span>";
  }

  function renderEval(ri) {
    if (!ri) return "<p>No evaluation.</p>";
    var reward = ri.reward != null ? ri.reward : 0;
    var pass = reward === 1.0;
    var breakdown = ri.reward_breakdown || {};
    var breakdownStr = Object.keys(breakdown).length
      ? Object.entries(breakdown).map(function (e) { return e[0] + ": " + (e[1] === 1 ? "✓" : "✗"); }).join(" · ")
      : "";
    var html = '<div class="eval-card">' +
      '<div class="eval-overview">' +
      '<span class="reward-box ' + (pass ? "pass" : "fail") + '">Reward: ' + reward + '</span>' +
      (breakdownStr ? '<span class="breakdown">' + escapeHtml(breakdownStr) + '</span>' : "") + "</div>";
    var db = ri.db_check;
    if (db)
      html += '<p><strong>DB state:</strong> ' +
        (db.db_match ? '<span class="reward-badge pass">Match</span>' : '<span class="reward-badge fail">Mismatch</span>') + "</p>";
    var actions = ri.action_checks || [];
    if (actions.length) {
      html += '<div class="action-checks"><strong>Action checks</strong>';
      actions.forEach(function (c) {
        var a = c.action || {};
        var match = c.action_match;
        var detail = '<div class="check-detail"><div class="name">' + escapeHtml(a.name || "—") + "</div>" +
          (a.arguments && Object.keys(a.arguments).length ? '<div class="args">Expected: ' + escapeHtml(JSON.stringify(a.arguments, null, 2)) + "</div>" : "");
        if (!match && (c.mismatch_reason || c.actual_arguments != null)) {
          if (c.mismatch_reason === "not_called") {
            detail += '<div class="mismatch-reason">Tool was not called.</div>';
          } else if (c.mismatch_reason === "arguments_mismatch" && c.actual_arguments != null) {
            detail += '<div class="mismatch-reason">Same tool was called but arguments differ. Actual: </div>';
            detail += '<div class="args actual-args">' + escapeHtml(JSON.stringify(c.actual_arguments, null, 2)) + "</div>";
          } else if (c.mismatch_reason) {
            detail += '<div class="mismatch-reason">' + escapeHtml(c.mismatch_reason) + "</div>";
          }
        }
        detail += "</div>";
        html += '<div class="action-check">' + '<span class="check-icon ' + (match ? "pass" : "fail") + '">' + (match ? "✓" : "✗") + "</span>" + detail + "</div>";
      });
      html += "</div>";
    }
    var comm = ri.communicate_checks || [];
    if (comm.length) {
      html += '<div class="communicate-checks"><strong>Communicate checks</strong>';
      comm.forEach(function (c) {
        var met = c.met;
        html += '<div class="communicate-check">' + '<span class="check-icon ' + (met ? "pass" : "fail") + '">' + (met ? "✓" : "✗") + "</span>" +
          '<div class="check-detail">' + (c.info != null ? "<strong>Expected: " + escapeHtml(String(c.info)) + "</strong>" : "") +
          (c.justification ? '<div class="justification">' + escapeHtml(c.justification) + "</div>" : "") + "</div></div>";
      });
      html += "</div>";
    }
    html += "</div>";
    return html;
  }

  function getReasoningText(m) {
    if (m.reasoning_content && typeof m.reasoning_content === "string") return m.reasoning_content;
    var raw = m.raw_data && m.raw_data.message;
    if (!raw) return "";
    if (raw.reasoning_content && typeof raw.reasoning_content === "string") return raw.reasoning_content;
    var blocks = raw.thinking_blocks;
    if (Array.isArray(blocks) && blocks.length) {
      return blocks.map(function (b) { return b.thinking || b.content || ""; }).filter(Boolean).join("\n\n");
    }
    return "";
  }

  function prettyFormatToolOutput(content) {
    var str = typeof content === "string" ? content : JSON.stringify(content);
    try {
      var parsed = JSON.parse(str);
      return JSON.stringify(parsed, null, 2);
    } catch (_) {
      return str;
    }
  }

  function renderMessages(messages) {
    if (!Array.isArray(messages) || !messages.length) return "<p>No messages.</p>";
    var html = "";
    for (var i = 0; i < messages.length; i++) {
      var m = messages[i];
      var role = m.role || "unknown";
      var cls = role === "user" ? "user" : role === "tool" ? "tool" : "assistant";
      var header = '<div class="msg-header"><span>' + escapeHtml(role) + "</span>" +
        (m.turn_idx != null ? "<span>Turn " + m.turn_idx + "</span>" : "") +
        (m.timestamp ? "<span>" + escapeHtml(m.timestamp) + "</span>" : "") + "</div>";
      if (m.role === "tool") {
        var formatted = prettyFormatToolOutput(m.content);
        html += '<div class="msg-block tool">' + header +
          '<details class="tool-output-details"><summary class="tool-output-summary">Tool output</summary>' +
          '<pre class="msg-body tool-result">' + escapeHtml(formatted) + "</pre></details></div>";
        continue;
      }
      var body = "";
      var reasoning = getReasoningText(m);
      if (reasoning) {
        body += '<details class="reasoning-details"><summary class="reasoning-summary">Reasoning</summary>' +
          '<pre class="reasoning-body">' + escapeHtml(reasoning) + "</pre></details>";
      }
      if (m.tool_calls && m.tool_calls.length) {
        body += '<div class="tool-calls-list">';
        m.tool_calls.forEach(function (tc) {
          var args = tc.arguments && typeof tc.arguments === "object" ? JSON.stringify(tc.arguments, null, 2) : String(tc.arguments || "");
          body += '<div class="tool-call-item">';
          body += '<div class="tool-name">' + escapeHtml(tc.name || "\u2014") + '</div>';
          body += '<div class="tool-args">' + escapeHtml(args) + '</div></div>';
        });
        body += "</div>";
      }
      if (m.content) body += '<div class="msg-body">' + escapeHtml(m.content) + "</div>";
      if (!body) body = '<div class="msg-body"><em>No content</em></div>';
      html += '<div class="msg-block ' + cls + '">' + header + body + "</div>";
    }
    return html;
  }

  function renderPanelContent(data) {
    return (
      '<section class="viewer-section"><h2>Task details</h2><div class="task-details">' + renderTaskDetails(data.task) + '</div></section>' +
      '<section class="viewer-section"><h2>Run info</h2><div class="run-info">' + renderRunInfo(data.run_info) + '</div></section>' +
      '<section class="viewer-section"><h2>Evaluation</h2><div id="eval-content">' + renderEval(data.reward_info) + '</div></section>' +
      '<section class="viewer-section"><h2>Conversation</h2><div class="timeline">' + renderMessages(data.messages) + '</div></section>'
    );
  }

  var runs = [];
  var runSelect1 = document.getElementById("run-1");
  var runSelect2 = document.getElementById("run-2");
  var domainHint = document.getElementById("domain-hint");
  var compareTableWrap = document.getElementById("compare-table-wrap");
  var compareJoinTbody = document.getElementById("compare-join-tbody");
  var thRun1 = document.getElementById("th-run1");
  var thRun2 = document.getElementById("th-run2");
  var diffOnlyCheckbox = document.getElementById("diff-only");
  var compareDetailWrap = document.getElementById("compare-detail-wrap");
  var taskSelectSingle = document.getElementById("task-select-single");
  var panelLeft = document.getElementById("panel-left");
  var panelRight = document.getElementById("panel-right");
  var headLeft = document.getElementById("head-left");
  var headRight = document.getElementById("head-right");
  var bodyLeft = document.getElementById("body-left");
  var bodyRight = document.getElementById("body-right");

  var joinRows = [];
  var run1Id = "";
  var run2Id = "";
  var run1Label = "";
  var run2Label = "";

  function getRunById(id) {
    for (var i = 0; i < runs.length; i++) {
      if (runs[i].id === id) return runs[i];
    }
    return null;
  }

  function getRunDomain(r) {
    if (r && r.domain) return r.domain;
    if (r && r.id) {
      var parts = r.id.split("_");
      if (parts.length >= 2) return parts[1];
    }
    return null;
  }

  function addRunOptions(sel, filterDomain) {
    sel.innerHTML = "";
    var empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "\u2014 Select run \u2014";
    sel.appendChild(empty);
    runs.forEach(function (r) {
      if (filterDomain != null && getRunDomain(r) !== filterDomain) return;
      var opt = document.createElement("option");
      opt.value = r.id;
      opt.textContent = r.label + " (" + (r.num_passed != null ? r.num_passed + "/" + r.num_tasks : r.num_tasks) + ")";
      sel.appendChild(opt);
    });
  }

  function loadIndex(runId) {
    return fetch(getDataPath("data/" + runId + "/index.json"))
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) { return data && data.tasks ? data.tasks : []; });
  }

  function buildJoin(tasks1, tasks2) {
    var byId1 = {};
    var byId2 = {};
    var allIds = new Set();
    tasks1.forEach(function (t) { byId1[t.task_id] = t; allIds.add(t.task_id); });
    tasks2.forEach(function (t) { byId2[t.task_id] = t; allIds.add(t.task_id); });
    var ids = Array.from(allIds).sort(function (a, b) {
      var na = parseInt(a, 10);
      var nb = parseInt(b, 10);
      if (!isNaN(na) && !isNaN(nb)) return na - nb;
      return String(a).localeCompare(String(b));
    });
    return ids.map(function (taskId) {
      var t1 = byId1[taskId];
      var t2 = byId2[taskId];
      var r1 = t1 ? (t1.reward === 1.0 ? "pass" : "fail") : null;
      var r2 = t2 ? (t2.reward === 1.0 ? "pass" : "fail") : null;
      var isDiff = (r1 !== null && r2 !== null && r1 !== r2);
      return { taskId: taskId, r1: r1, r2: r2, isDiff: isDiff };
    });
  }

  function renderJoinTable() {
    var diffOnly = diffOnlyCheckbox && diffOnlyCheckbox.checked;
    thRun1.textContent = "Run 1" + (run1Label ? " (" + run1Label + ")" : "");
    thRun2.textContent = "Run 2" + (run2Label ? " (" + run2Label + ")" : "");
    compareJoinTbody.innerHTML = "";
    joinRows.forEach(function (row) {
      if (diffOnly && !row.isDiff) return;
      var tr = document.createElement("tr");
      var tdId = document.createElement("td");
      tdId.className = "task-id";
      tdId.textContent = row.taskId;
      tr.appendChild(tdId);
      var td1 = document.createElement("td");
      if (row.r1 === "pass") {
        td1.innerHTML = '<span class="reward-badge pass">Pass</span>';
      } else if (row.r1 === "fail") {
        td1.innerHTML = '<span class="reward-badge fail">Fail</span>';
      } else {
        td1.textContent = "NA";
        td1.classList.add("compare-na");
      }
      tr.appendChild(td1);
      var td2 = document.createElement("td");
      if (row.r2 === "pass") {
        td2.innerHTML = '<span class="reward-badge pass">Pass</span>';
      } else if (row.r2 === "fail") {
        td2.innerHTML = '<span class="reward-badge fail">Fail</span>';
      } else {
        td2.textContent = "NA";
        td2.classList.add("compare-na");
      }
      tr.appendChild(td2);
      var tdBtn = document.createElement("td");
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "compare-row-btn";
      btn.textContent = "Compare";
      btn.dataset.taskId = row.taskId;
      btn.addEventListener("click", function () {
        openCompareTask(row.taskId);
      });
      tdBtn.appendChild(btn);
      tr.appendChild(tdBtn);
      compareJoinTbody.appendChild(tr);
    });
  }

  function openCompareTask(taskId) {
    compareDetailWrap.style.display = "block";
    taskSelectSingle.value = taskId;
    populateTaskDropdown();
    loadBothTasks(taskId);
    compareDetailWrap.scrollIntoView({ behavior: "smooth" });
  }

  function populateTaskDropdown() {
    taskSelectSingle.innerHTML = "";
    var diffOnly = diffOnlyCheckbox && diffOnlyCheckbox.checked;
    joinRows.forEach(function (row) {
      if (diffOnly && !row.isDiff) return;
      var opt = document.createElement("option");
      opt.value = row.taskId;
      opt.textContent = "Task " + row.taskId;
      if (row.isDiff) {
        opt.classList.add(row.r2 === "pass" ? "opt-right-won" : "opt-left-won");
      }
      taskSelectSingle.appendChild(opt);
    });
    if (taskSelectSingle.options.length) {
      var cur = taskSelectSingle.value;
      if (cur && Array.prototype.some.call(taskSelectSingle.options, function (o) { return o.value === cur; }))
        taskSelectSingle.value = cur;
      else
        taskSelectSingle.selectedIndex = 0;
    }
  }

  function loadBothTasks(taskId) {
    if (!taskId) {
      bodyLeft.innerHTML = '<p class="compare-placeholder">Select task above.</p>';
      bodyRight.innerHTML = '<p class="compare-placeholder">Select task above.</p>';
      panelLeft.classList.remove("compare-panel-fail", "compare-panel-pass");
      panelRight.classList.remove("compare-panel-fail", "compare-panel-pass");
      return;
    }
    var row = joinRows.filter(function (r) { return r.taskId === taskId; })[0];
    if (row) {
      panelLeft.classList.toggle("compare-panel-fail", row.r1 === "fail");
      panelLeft.classList.toggle("compare-panel-pass", row.r1 === "pass");
      panelRight.classList.toggle("compare-panel-fail", row.r2 === "fail");
      panelRight.classList.toggle("compare-panel-pass", row.r2 === "pass");
    }
    headLeft.querySelector(".compare-panel-label").textContent = "Run 1" + (run1Label ? ": " + run1Label : "");
    headRight.querySelector(".compare-panel-label").textContent = "Run 2" + (run2Label ? ": " + run2Label : "");

    bodyLeft.innerHTML = '<p class="loading">Loading…</p>';
    bodyRight.innerHTML = '<p class="loading">Loading…</p>';

    var safeId = taskId.replace(/[^\w\-]/g, "_");
    var url1 = run1Id ? getDataPath("data/" + run1Id + "/task_" + safeId + ".json") : null;
    var url2 = run2Id ? getDataPath("data/" + run2Id + "/task_" + safeId + ".json") : null;

    function loadOne(url, bodyEl) {
      if (!url) {
        bodyEl.innerHTML = '<p class="compare-placeholder">No data for this run.</p>';
        return Promise.resolve();
      }
      return fetch(url)
        .then(function (r) {
          if (!r.ok) throw new Error("Task not found");
          return r.json();
        })
        .then(function (data) {
          bodyEl.innerHTML = renderPanelContent(data);
        })
        .catch(function () {
          bodyEl.innerHTML = '<p class="error-msg">Failed to load task.</p>';
        });
    }

    Promise.all([loadOne(url1, bodyLeft), loadOne(url2, bodyRight)]);
  }

  function onRun1Change() {
    run1Id = runSelect1.value;
    run2Id = "";
    runSelect2.value = "";
    var r1 = getRunById(run1Id);
    addRunOptions(runSelect2, r1 ? r1.domain : null);
    domainHint.textContent = r1
      ? "Run 2 options are limited to the same domain (" + (getRunDomain(r1) || "unknown") + ")."
      : "Select two runs from the same domain to compare.";
    compareTableWrap.style.display = "none";
    compareDetailWrap.style.display = "none";
  }

  function onRun2Change() {
    run2Id = runSelect2.value;
    if (!run1Id || !run2Id) {
      compareTableWrap.style.display = "none";
      compareDetailWrap.style.display = "none";
      return;
    }
    var r1 = getRunById(run1Id);
    var r2 = getRunById(run2Id);
    run1Label = r1 ? r1.label : "";
    run2Label = r2 ? r2.label : "";
    domainHint.textContent = "Comparing runs from same domain. Select a task and click Compare to see details.";
    Promise.all([loadIndex(run1Id), loadIndex(run2Id)]).then(function (res) {
      joinRows = buildJoin(res[0], res[1]);
      renderJoinTable();
      compareTableWrap.style.display = "block";
      populateTaskDropdown();
    });
  }

  runSelect1.addEventListener("change", onRun1Change);
  runSelect2.addEventListener("change", onRun2Change);
  if (diffOnlyCheckbox) diffOnlyCheckbox.addEventListener("change", function () { renderJoinTable(); populateTaskDropdown(); });
  taskSelectSingle.addEventListener("change", function () { loadBothTasks(taskSelectSingle.value); });

  fetch(getDataPath("data/runs.json"))
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (data) {
      if (!data || !data.runs || !data.runs.length) {
        domainHint.textContent = "No runs. Export trajectories first.";
        return;
      }
      runs = data.runs;
      addRunOptions(runSelect1, null);
      addRunOptions(runSelect2, null);
    })
    .catch(function () {
      domainHint.textContent = "Could not load runs. Serve the docs folder (e.g. with a local server) so data/runs.json can be loaded.";
    });
})();
