(function () {
  function qs(name) {
    const params = new URLSearchParams(document.location.search);
    return params.get(name);
  }

  function getDataPath(path) {
    const base = document.querySelector("base")?.getAttribute("href") || "";
    return (base + path).replace(/\/+/g, "/");
  }

  function escapeHtml(s) {
    if (s == null) return "";
    const div = document.createElement("div");
    div.textContent = String(s);
    return div.innerHTML;
  }

  function formatTs(ts) {
    if (!ts) return "—";
    try {
      const d = new Date(ts);
      return isNaN(d.getTime()) ? ts : d.toLocaleString();
    } catch (_) {
      return ts;
    }
  }

  function renderTaskDetails(task) {
    if (!task || !task.user_scenario || !task.user_scenario.instructions) {
      return "<p>No task details.</p>";
    }
    const i = task.user_scenario.instructions;
    return (
      "<dl>" +
      "<dt>Reason for call</dt><dd>" + escapeHtml(i.reason_for_call || "—") + "</dd>" +
      "<dt>Known info</dt><dd>" + escapeHtml(i.known_info || "—") + "</dd>" +
      "<dt>Unknown info</dt><dd>" + escapeHtml(i.unknown_info || "—") + "</dd>" +
      "<dt>Task instructions</dt><dd>" + escapeHtml(i.task_instructions || "—") + "</dd>" +
      "</dl>"
    );
  }

  function renderRunInfo(run) {
    if (!run) return "";
    return (
      "<span>Duration: " + (run.duration_sec != null ? run.duration_sec + "s" : "—") + "</span>" +
      "<span>End: " + escapeHtml(formatTs(run.timestamp)) + "</span>" +
      "<span>Termination: " + escapeHtml(run.termination_reason || "—") + "</span>" +
      "<span>Agent cost: " + (run.agent_cost != null ? run.agent_cost.toFixed(4) : "—") + "</span>" +
      "<span>User cost: " + (run.user_cost != null ? run.user_cost.toFixed(4) : "—") + "</span>"
    );
  }

  function renderEval(ri) {
    if (!ri) return "<p>No evaluation.</p>";
    const reward = ri.reward != null ? ri.reward : 0;
    const pass = reward === 1.0;
    const breakdown = ri.reward_breakdown || {};
    const breakdownStr = Object.keys(breakdown).length
      ? Object.entries(breakdown)
          .map(function (e) {
            return e[0] + ": " + (e[1] === 1 ? "✓" : "✗");
          })
          .join(" · ")
      : "";

    let html =
      '<div class="eval-card">' +
      '<div class="eval-overview">' +
      '<span class="reward-box ' + (pass ? "pass" : "fail") + '">Reward: ' + reward + '</span>' +
      (breakdownStr ? '<span class="breakdown">' + escapeHtml(breakdownStr) + '</span>' : "") +
      "</div>";

    const db = ri.db_check;
    if (db) {
      html +=
        '<p><strong>DB state:</strong> ' +
        (db.db_match ? '<span class="reward-badge pass">Match</span>' : '<span class="reward-badge fail">Mismatch</span>') +
        "</p>";
    }

    const actions = ri.action_checks || [];
    if (actions.length) {
      html += '<div class="action-checks"><strong>Action checks</strong>';
      actions.forEach(function (c) {
        const a = c.action || {};
        const match = c.action_match;
        html +=
          '<div class="action-check">' +
          '<span class="check-icon ' + (match ? "pass" : "fail") + '">' + (match ? "✓" : "✗") + "</span>" +
          '<div class="check-detail">' +
          '<div class="name">' + escapeHtml(a.name || "—") + "</div>" +
          (a.arguments && Object.keys(a.arguments).length
            ? '<div class="args">' + escapeHtml(JSON.stringify(a.arguments, null, 2)) + "</div>"
            : "") +
          "</div></div>";
      });
      html += "</div>";
    }

    const comm = ri.communicate_checks || [];
    if (comm.length) {
      html += '<div class="communicate-checks"><strong>Communicate checks</strong>';
      comm.forEach(function (c) {
        const met = c.met;
        html +=
          '<div class="communicate-check">' +
          '<span class="check-icon ' + (met ? "pass" : "fail") + '">' + (met ? "✓" : "✗") + "</span>" +
          '<div class="check-detail">' +
          (c.info != null ? "<strong>Expected: " + escapeHtml(String(c.info)) + "</strong>" : "") +
          (c.justification ? '<div class="justification">' + escapeHtml(c.justification) + "</div>" : "") +
          "</div></div>";
      });
      html += "</div>";
    }

    html += "</div>";
    return html;
  }

  function renderMessages(messages) {
    if (!Array.isArray(messages) || !messages.length) {
      return "<p>No messages.</p>";
    }

    var html = "";
    for (var i = 0; i < messages.length; i++) {
      var m = messages[i];
      var role = m.role || "unknown";
      var cls = role === "user" ? "user" : role === "tool" ? "tool" : "assistant";
      var header =
        '<div class="msg-header">' +
        "<span>" + escapeHtml(role) + "</span>" +
        (m.turn_idx != null ? "<span>Turn " + m.turn_idx + "</span>" : "") +
        (m.timestamp ? "<span>" + escapeHtml(m.timestamp) + "</span>" : "") +
        "</div>";

      if (m.role === "tool") {
        var content = typeof m.content === "string" ? m.content : JSON.stringify(m.content);
        if (content.length > 2000) content = content.slice(0, 2000) + "\n… (truncated)";
        html +=
          '<div class="msg-block tool">' +
          header +
          '<div class="msg-body tool-result">' + escapeHtml(content) + "</div>" +
          "</div>";
        continue;
      }

      var body = "";
      if (m.tool_calls && m.tool_calls.length) {
        body += '<div class="tool-calls-list">';
        m.tool_calls.forEach(function (tc) {
          var args =
            tc.arguments && typeof tc.arguments === "object"
              ? JSON.stringify(tc.arguments, null, 2)
              : String(tc.arguments || "");
          body +=
            '<div class="tool-call-item">' +
            '<div class="tool-name">' + escapeHtml(tc.name || "—") + "</div>" +
            '<div class="tool-args">' + escapeHtml(args) + "</div>" +
            "</div>";
        });
        body += "</div>";
      }
      if (m.content) {
        body += '<div class="msg-body">' + escapeHtml(m.content) + "</div>";
      }
      if (!body) body = '<div class="msg-body"><em>No content</em></div>';

      html += '<div class="msg-block ' + cls + '">' + header + body + "</div>";
    }
    return html;
  }

  var taskId = qs("task");
  if (!taskId) {
    document.getElementById("loading").style.display = "none";
    document.getElementById("error").style.display = "block";
    document.getElementById("error").textContent = "Missing task id. Use ?task=1";
    return;
  }

  var safeId = taskId.replace(/[^\w\-]/g, "_");
  var url = getDataPath("data/task_" + safeId + ".json");

  fetch(url)
    .then(function (r) {
      if (!r.ok) throw new Error("Task not found: " + taskId);
      return r.json();
    })
    .then(function (data) {
      document.getElementById("loading").style.display = "none";
      document.getElementById("error").style.display = "none";
      document.getElementById("content").style.display = "block";

      document.getElementById("viewer-title").textContent = "Task " + taskId;

      document.getElementById("task-details").innerHTML = renderTaskDetails(data.task);
      document.getElementById("run-info").innerHTML = renderRunInfo(data.run_info);
      document.getElementById("eval-content").innerHTML = renderEval(data.reward_info);
      document.getElementById("conversation").innerHTML = renderMessages(data.messages);
    })
    .catch(function (err) {
      document.getElementById("loading").style.display = "none";
      document.getElementById("error").style.display = "block";
      document.getElementById("error").textContent = err.message || "Failed to load task.";
    });
})();
