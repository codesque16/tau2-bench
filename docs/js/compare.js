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
        html += '<div class="action-check">' + '<span class="check-icon ' + (match ? "pass" : "fail") + '">' + (match ? "✓" : "✗") + "</span>" +
          '<div class="check-detail"><div class="name">' + escapeHtml(a.name || "—") + "</div>" +
          (a.arguments && Object.keys(a.arguments).length ? '<div class="args">' + escapeHtml(JSON.stringify(a.arguments, null, 2)) + "</div>" : "") + "</div></div>";
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
        var content = typeof m.content === "string" ? m.content : JSON.stringify(m.content);
        if (content.length > 2000) content = content.slice(0, 2000) + "\n… (truncated)";
        html += '<div class="msg-block tool">' + header + '<div class="msg-body tool-result">' + escapeHtml(content) + "</div></div>";
        continue;
      }
      var body = "";
      if (m.tool_calls && m.tool_calls.length) {
        body += '<div class="tool-calls-list">';
        m.tool_calls.forEach(function (tc) {
          var args = tc.arguments && typeof tc.arguments === "object" ? JSON.stringify(tc.arguments, null, 2) : String(tc.arguments || "");
          body += '<div class="tool-call-item"><div class="tool-name">' + escapeHtml(tc.name || "—") + "</div><div class="tool-args">" + escapeHtml(args) + "</div></div>";
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
  var runSelectLeft = document.getElementById("run-left");
  var runSelectRight = document.getElementById("run-right");
  var taskSelectLeft = document.getElementById("task-left");
  var taskSelectRight = document.getElementById("task-right");
  var bodyLeft = document.getElementById("body-left");
  var bodyRight = document.getElementById("body-right");

  function loadTaskList(runId, selectEl) {
    selectEl.innerHTML = '<option value="">— Select task —</option>';
    if (!runId) return;
    fetch(getDataPath("data/" + runId + "/index.json"))
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.tasks) return;
        data.tasks.forEach(function (t) {
          var opt = document.createElement("option");
          opt.value = t.task_id;
          opt.textContent = "Task " + t.task_id + (t.reward === 1.0 ? " ✓" : " ✗");
          selectEl.appendChild(opt);
        });
      });
  }

  function loadTask(runId, taskId, bodyEl) {
    if (!taskId) {
      bodyEl.innerHTML = '<p class="compare-placeholder">Select run and task.</p>';
      return;
    }
    bodyEl.innerHTML = '<p class="loading">Loading…</p>';
    var safeId = taskId.replace(/[^\w\-]/g, "_");
    var url = runId
      ? getDataPath("data/" + runId + "/task_" + safeId + ".json")
      : getDataPath("data/task_" + safeId + ".json");
    fetch(url)
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

  runSelectLeft.addEventListener("change", function () {
    var id = runSelectLeft.value;
    loadTaskList(id, taskSelectLeft);
    taskSelectLeft.value = "";
    bodyLeft.innerHTML = '<p class="compare-placeholder">Select task.</p>';
  });
  runSelectRight.addEventListener("change", function () {
    var id = runSelectRight.value;
    loadTaskList(id, taskSelectRight);
    taskSelectRight.value = "";
    bodyRight.innerHTML = '<p class="compare-placeholder">Select task.</p>';
  });
  taskSelectLeft.addEventListener("change", function () {
    loadTask(runSelectLeft.value, taskSelectLeft.value, bodyLeft);
  });
  taskSelectRight.addEventListener("change", function () {
    loadTask(runSelectRight.value, taskSelectRight.value, bodyRight);
  });

  fetch(getDataPath("data/runs.json"))
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (data) {
      if (!data || !data.runs || !data.runs.length) {
        bodyLeft.innerHTML = '<p class="error-msg">No runs. Export trajectories first.</p>';
        return;
      }
      runs = data.runs;
      runs.forEach(function (r) {
        var label = r.label + " (" + (r.num_passed != null ? r.num_passed + "/" + r.num_tasks : r.num_tasks) + ")";
        [runSelectLeft, runSelectRight].forEach(function (sel) {
          var opt = document.createElement("option");
          opt.value = r.id;
          opt.textContent = label;
          sel.appendChild(opt);
        });
      });
    })
    .catch(function () {
      bodyLeft.innerHTML = '<p class="error-msg">Could not load runs.</p>';
    });
})();
