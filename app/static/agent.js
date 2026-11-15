/* Taxot demo UI: the "Tasks" tab (agentic Workflows 1-3).
 * Start a task (upload PDFs or pick a sample taxpayer), watch the agents work, answer questions,
 * approve key steps, and read the verified result. Talks to src/api/agent_routes.py.
 * Plain ES2017, no framework, same helpers as app.js (window.TS).
 */
(function () {
  "use strict";
  var TS = window.TS;
  var $ = TS.$, $$ = TS.$$, esc = TS.esc, inr = TS.inr, icon = TS.icon;
  var POLL_MS = 1200;

  var WORKFLOWS = [
    { id: "document_check", title: "Check my documents", sub: "Find mismatches between Form 16, salary slips and interest certificates before you file.", ico: "file" },
    { id: "filing_prep", title: "Prepare my return", sub: "Right ITR form, the cheaper regime and a filing-ready checklist.", ico: "check" },
    { id: "tax_saving", title: "Save tax legally", sub: "Simulate 80C, NPS and health-insurance options and rank them by saving.", ico: "calc" },
  ];
  var STEP_LABEL = {
    documents: "Check documents", facts: "Gather missing facts", figures: "Confirm your figures", itr_form: "Pick the ITR form",
    escalation: "Complexity check", gst: "GST check", regime: "Compare regimes", savings: "Find savings",
    verify: "Verify every claim", checklist: "Filing checklist",
  };
  var NODE_LABEL = {
    plan: "Orchestrator planned the task", documents: "Document agent", facts: "Orchestrator", ask_facts: "You answered",
    figures: "Figures built", approve_figures: "You reviewed the figures", itr_form: "Income tax agent",
    escalation: "Escalation check", gst: "GST agent", regime: "Calculator agent", approve_regime: "You chose a regime",
    savings: "Tax-saving agent", verify: "Verifier agent", approve_plan: "You reviewed the plan",
    checklist: "Checklist built", approve_checklist: "You reviewed the checklist", finalize: "Task complete",
  };
  var FIG_ROWS = [
    ["gross_salary", "Salary (or freelance receipts)", "salary"], ["other_income", "Interest income", "interest"],
    ["deductions_80c", "80C (PF + investments)", "80c"], ["deductions_80d", "80D health insurance", "80d"],
    ["deductions_80d_parents", "80D for parents", null], ["nps_80ccd1b", "NPS 80CCD(1B)", "80ccd1b"],
    ["home_loan_interest", "Home-loan interest 24(b)", "home_loan_interest"], ["hra_exemption", "HRA exemption", "hra_exemption"],
    ["other_deductions", "80TTA / 80TTB on interest", "80tta_80ttb"],
  ];
  var EDIT_FIELDS = [
    ["salary_without_form16", "Salary not in any Form 16", "₹ per year"], ["other_interest", "Other interest not in certificates", "₹ per year"],
    ["epf_annual", "Employee PF for the year", "₹ per year"], ["other_80c", "Other 80C investments (PPF, ELSS…)", "₹ per year"],
    ["health_80d", "Health insurance, self/family", "₹ per year"], ["health_80d_parents", "Health insurance, parents", "₹ per year"],
    ["nps_80ccd1b", "Own NPS contribution", "₹ per year"], ["home_loan_interest", "Home-loan interest", "₹ per year"],
    ["rent_monthly", "Rent", "₹ per month"],
  ];
  var NOT_RUPEES = { age: 1, house_properties: 1 };
  var FINDING_NAME = {
    interest_not_in_form16: "interest missing from Form 16", slips_total_mismatch: "salary slips vs Form 16",
    form16_tds_inconsistent: "TDS not fully deposited", deduction_over_cap: "deduction above its limit",
    pan_mismatch: "PAN mismatch", multiple_employers: "two employers", injection_detected: "a planted AI instruction",
  };

  var S = { task: null, st: null, timer: null, files: [], workflow: "filing_prep", sample: null, samples: null,
            started: 0, inited: false, busy: false, showEdit: false,
            sig: "", seen: 0, cardKey: "", clock: null };

  /* ------------------------------------------------------------------ boot */
  TS.onView("tasks", function () {
    if (!S.inited) { S.inited = true; bindOnce(); if (resume()) return; }
    if (S.task) render(); else renderStart();
  });

  // The task lives on the server; keep its id for this browser tab so a reload picks it back up.
  var KEY = "taxot_task";
  function remember(id, extra) { try { sessionStorage.setItem(KEY, JSON.stringify(Object.assign({ id: id }, extra || {}))); } catch (e) { /* storage blocked */ } }
  function forget() { try { sessionStorage.removeItem(KEY); } catch (e) { /* storage blocked */ } }
  function resume() {
    var saved = null;
    try { saved = JSON.parse(sessionStorage.getItem(KEY) || "null"); } catch (e) { saved = null; }
    if (!saved || !saved.id || !live()) return false;
    S.task = saved.id; S.sample = saved.sample || null; S.started = saved.started || 0;
    $("#tkHead").hidden = true;
    $("#tasksBody").innerHTML = '<div class="panel tk-working"><span class="tk-spin" aria-hidden="true"></span><div><b>Reopening your task…</b></div></div>';
    http("/tasks/" + S.task).then(function (st) { S.st = st; render(); if (st.status === "running" || st.status === "new") poll(); })
      .catch(function () { forget(); S.task = null; renderStart(); });
    return true;
  }

  function bindOnce() {
    var body = $("#tasksBody");
    body.addEventListener("click", onClick);
    body.addEventListener("submit", onSubmit);
    body.addEventListener("change", onChange);
    ["dragenter", "dragover"].forEach(function (ev) {
      body.addEventListener(ev, function (e) { var z = e.target.closest(".tk-drop"); if (z) { e.preventDefault(); z.classList.add("over"); } });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      body.addEventListener(ev, function (e) {
        var z = e.target.closest(".tk-drop"); if (!z) return;
        e.preventDefault(); z.classList.remove("over");
        if (ev === "drop" && e.dataTransfer) addFiles(e.dataTransfer.files);
      });
    });
  }

  function live() { return !(TS.state && TS.state.mock); }

  function http(path, opts) {
    // TS.api only speaks JSON and falls back to sample data on 404; tasks need the real server.
    opts = opts || {};
    return fetch(path, { method: opts.method || (opts.body || opts.form ? "POST" : "GET"),
      headers: opts.form ? undefined : { "Content-Type": "application/json", Accept: "application/json" },
      body: opts.form || (opts.body ? JSON.stringify(opts.body) : undefined) })
      .then(function (r) {
        return r.text().then(function (t) {
          var d; try { d = t ? JSON.parse(t) : {}; } catch (e) { d = { detail: t.slice(0, 300) }; }
          if (!r.ok) { var err = new Error(typeof d.detail === "string" ? d.detail : "HTTP " + r.status); err.status = r.status; throw err; }
          return d;
        });
      }, function () { throw new Error("Couldn't reach the Taxot server."); });
  }

  /* ------------------------------------------------------------------ start screen */
  function renderStart() {
    stopPoll();
    $("#tkHead").hidden = false;
    var body = $("#tasksBody");
    var wf = WORKFLOWS.map(function (w, i) {
      var on = S.workflow === w.id;
      return '<button type="button" class="tk-wf' + (on ? " on" : "") + '" data-wf="' + w.id + '" role="radio" aria-checked="' + on +
        '" style="--i:' + i + '"><span class="tk-wf-ico">' + icon(w.ico) + '</span><span class="tk-wf-t">' + esc(w.title) +
        '</span><span class="tk-wf-s">' + esc(w.sub) + "</span></button>";
    }).join("");
    var files = S.files.map(function (f, i) {
      return '<li class="tk-file">' + icon("file") + '<span class="tk-file-n">' + esc(f.name) + '</span><span class="muted small">' +
        Math.max(1, Math.round(f.size / 1024)) + ' KB</span><button type="button" class="icon-btn xs" data-rm="' + i +
        '" aria-label="Remove ' + esc(f.name) + '">' + icon("x") + "</button></li>";
    }).join("");
    body.innerHTML =
      (live() ? "" : '<div class="panel tk-note warn">' + icon("info") + "<span>Agent tasks need the live Taxot server. You are in offline demo mode.</span></div>") +
      '<form class="tk-start" id="tkStart" autocomplete="off">' +
        '<div class="tk-wfs" role="radiogroup" aria-label="What should Taxot do?">' + wf + "</div>" +
        '<div class="panel tk-upload">' +
          '<label class="tk-drop" for="tkFiles">' + icon("file") +
            "<span><b>Drop PDFs here</b> or browse</span><small>Form 16, salary slips, bank interest certificates · up to 10 MB each</small>" +
            '<input type="file" id="tkFiles" accept="application/pdf,.pdf" multiple class="sr-only" /></label>' +
          (files ? '<ul class="tk-files">' + files + "</ul>" : "") +
          '<label class="tk-label" for="tkNote">Anything else we should know? <span class="muted">(optional)</span></label>' +
          '<textarea id="tkNote" rows="2" placeholder="e.g. I also sold some mutual funds this year, or I\'m a freelance designer"></textarea>' +
          '<div class="tk-start-foot"><p class="tk-privacy">' + icon("check") +
            "Documents stay in memory and are deleted when you finish. PAN, Aadhaar, names and account numbers are masked before any AI model sees them.</p>" +
            '<button class="btn btn-primary" type="submit" id="tkGo"' + (live() ? "" : " disabled") + ">Start" + icon("arrowRight") + "</button></div>" +
        "</div>" +
      "</form>" +
      '<div class="tk-samples"><p class="eyebrow">Or try a sample taxpayer <span class="muted">(fictitious documents)</span></p><div class="tk-sample-row" id="tkSamples">' +
        '<div class="skeleton tk-sk"></div><div class="skeleton tk-sk"></div><div class="skeleton tk-sk"></div></div></div>';
    loadSamples();
  }

  function loadSamples() {
    if (!live()) { $("#tkSamples").innerHTML = '<p class="muted small">Samples need the live server.</p>'; return; }
    var draw = function () {
      var wfName = {}; WORKFLOWS.forEach(function (w) { wfName[w.id] = w.title; });
      $("#tkSamples").innerHTML = S.samples.map(function (s, i) {
        return '<button type="button" class="tk-sample" data-sample="' + esc(s.id) + '" style="--i:' + i + '"><span class="tk-sample-wf">' +
          esc(wfName[s.workflow] || s.workflow) + '</span><span class="tk-sample-t">' + esc(s.label) + '</span><span class="tk-sample-d">' +
          icon("file") + s.documents.length + " document" + (s.documents.length === 1 ? "" : "s") + (s.user_says ? " · has a note" : "") + "</span></button>";
      }).join("");
    };
    if (S.samples) return draw();
    http("/samples").then(function (d) { S.samples = d.samples; draw(); })
      .catch(function (e) { $("#tkSamples").innerHTML = '<p class="muted small">' + esc(e.message) + "</p>"; });
  }

  function addFiles(list) {
    Array.prototype.forEach.call(list || [], function (f) {
      if (!/\.pdf$/i.test(f.name)) { TS.toast(f.name + " is not a PDF", "warn"); return; }
      if (f.size > 10 * 1024 * 1024) { TS.toast(f.name + " is larger than 10 MB", "warn"); return; }
      if (!S.files.some(function (g) { return g.name === f.name && g.size === f.size; })) S.files.push(f);
    });
    var note = $("#tkNote") ? $("#tkNote").value : "";
    renderStart();
    if (note && $("#tkNote")) $("#tkNote").value = note;
  }

  function startTask(sample) {
    if (S.busy) return;
    S.busy = true;
    var go = $("#tkGo"); if (go) go.disabled = true;
    var note = $("#tkNote") ? $("#tkNote").value.trim() : "";
    var wf = sample ? (S.samples.filter(function (s) { return s.id === sample; })[0] || {}).workflow : S.workflow;
    if (!sample && !S.files.length && wf === "document_check") { TS.toast("Add at least one PDF to check", "warn"); S.busy = false; if (go) go.disabled = false; return; }
    var goal = sample ? "" : (WORKFLOWS.filter(function (w) { return w.id === wf; })[0].sub + (note ? " " + note : ""));
    S.sample = sample || null;
    http("/tasks", { body: { workflow: wf, goal: goal, sample: sample || null } })
      .then(function (d) {
        S.task = d.task_id;
        return S.files.reduce(function (p, f) {
          return p.then(function () { var fd = new FormData(); fd.append("file", f, f.name); return http("/tasks/" + S.task + "/documents", { form: fd }); });
        }, Promise.resolve());
      })
      .then(function () {
        S.files = []; S.started = Date.now();
        remember(S.task, { sample: S.sample, started: S.started });
        return http("/tasks/" + S.task + "/start", { method: "POST" });
      })
      .then(function (st) { S.st = st; render(); poll(); })
      .catch(function (e) { TS.toast(e.message, "warn"); if (S.task) { http("/tasks/" + S.task, { method: "DELETE" }).catch(function () {}); S.task = null; } })
      .then(function () { S.busy = false; var g = $("#tkGo"); if (g) g.disabled = false; });
  }

  /* ------------------------------------------------------------------ polling */
  function poll() {
    stopPoll();
    S.timer = setTimeout(function () {
      if (!S.task) return;
      http("/tasks/" + S.task).then(function (st) {
        S.st = st;
        if (document.body.getAttribute("data-view") === "tasks" && signature(st) !== S.sig) render();
        if (st.status === "running" || st.status === "new") poll();
      }).catch(function (e) {
        if (e.status === 404) { TS.toast("This task expired. Start a new one.", "warn"); reset(); return; }
        poll();
      });
    }, POLL_MS);
  }
  function stopPoll() { clearTimeout(S.timer); S.timer = null; }

  // What the screen shows; the page is only redrawn when this changes (no flicker while agents work).
  function signature(st) {
    var u = st.usage || {};
    return [st.status, (st.trace || []).length, (st.plan || []).map(function (p) { return p.status; }).join(""),
            st.interrupt ? (st.interrupt.step || st.interrupt.type) : "", u.calls, u.tool_calls, S.showEdit].join("|");
  }

  function tickClock() {
    clearInterval(S.clock);
    S.clock = setInterval(function () {
      var el = $("#tkClock");
      if (!el || !S.started) return;
      el.textContent = fmtSecs(Math.round((Date.now() - S.started) / 1000));
      if (!S.st || S.st.status !== "running") clearInterval(S.clock);
    }, 1000);
  }

  function reset() {
    stopPoll(); clearInterval(S.clock);
    S.task = null; S.st = null; S.sample = null; S.showEdit = false; S.sig = ""; S.seen = 0; S.cardKey = "";
    forget();
    renderStart();
  }

  /* ------------------------------------------------------------------ task screen */
  function render() {
    var st = S.st; if (!st) return;
    $("#tkHead").hidden = true;
    var body = $("#tasksBody");
    var keepNote = $("#tkAnsText") ? $("#tkAnsText").value : null;
    var cardKey = st.status + ":" + (st.interrupt ? (st.interrupt.step || st.interrupt.type) : "") + ":" + S.showEdit;
    var freshCard = cardKey !== S.cardKey;
    body.innerHTML = '<div class="tk-task">' + sidebar(st) + '<div class="tk-main">' + header(st) + feed(st) +
      '<div class="tk-action' + (freshCard ? " fresh" : "") + '">' + action(st) + "</div></div></div>";
    if (keepNote != null && $("#tkAnsText")) $("#tkAnsText").value = keepNote;
    var f = $(".tk-feed"); if (f) f.scrollTop = f.scrollHeight;
    S.sig = signature(st); S.cardKey = cardKey; S.seen = (st.trace || []).length;
    if (st.status === "running") tickClock();
  }

  function currentStep(st) {
    var p = (st.plan || []).filter(function (x) { return x.status === "pending"; })[0];
    return p ? p.step : null;
  }

  function sidebar(st) {
    var cur = st.status === "running" ? currentStep(st) : null;
    var waitingStep = st.status === "waiting" ? currentStep(st) : null;
    var steps = (st.plan || []).map(function (p) {
      var cls = p.status === "done" ? "done" : p.status === "skipped" ? "skipped" : p.step === cur ? "now" : p.step === waitingStep ? "wait" : "";
      var mark = p.status === "done" ? icon("check") : p.status === "skipped" ? "–" : "";
      return '<li class="tk-step ' + cls + '"><span class="tk-step-dot">' + mark + '</span><span class="tk-step-t">' + esc(STEP_LABEL[p.step] || p.step) +
        (p.status === "skipped" && p.note ? '<small>' + esc(p.note) + "</small>" : "") + "</span></li>";
    }).join("") || '<li class="tk-step now"><span class="tk-step-dot"></span><span class="tk-step-t">Planning…</span></li>';
    var u = st.usage || {};
    var secs = S.started ? Math.round((Date.now() - S.started) / 1000) : null;
    return '<aside class="panel tk-side"><p class="eyebrow">Plan</p><ol class="tk-steps">' + steps + "</ol>" +
      '<div class="tk-meter"><div class="tk-meter-row"><span>Tool calls</span><b class="num">' + (u.tool_calls || 0) + " / " + (u.tool_budget || 15) +
      '</b></div><div class="tk-bar"><i style="width:' + Math.min(100, 100 * (u.tool_calls || 0) / (u.tool_budget || 15)) + '%"></i></div>' +
      '<div class="tk-meter-row"><span>AI calls</span><b class="num">' + (u.calls || 0) + "</b></div>" +
      (secs != null ? '<div class="tk-meter-row"><span>Time</span><b class="num" id="tkClock">' + fmtSecs(secs) + "</b></div>" : "") +
      "</div><p class=\"tk-side-note\">Hard limit of 15 tool calls per task. Taxot prepares and explains; it never files, pays or logs in for you.</p></aside>";
  }

  function header(st) {
    var docs = (st.documents || []).map(function (d) { return '<span class="tk-chip">' + icon("file") + esc(d.filename) + "</span>"; }).join("");
    return '<div class="tk-top"><div><p class="eyebrow">Your task</p><h2 class="tk-goal">' + esc(st.goal || "") + "</h2>" +
      (docs ? '<div class="tk-chips">' + docs + "</div>" : "") + '</div><button type="button" class="btn btn-secondary btn-sm" data-act="end">' +
      (st.status === "done" ? "Start a new task" : "Cancel") + "</button></div>";
  }

  function feed(st) {
    var items = (st.trace || []).filter(function (t) { return t.node !== "finalize"; }).map(function (t, i) {
      return '<li class="tk-ev' + (i >= S.seen ? " fresh" : "") + '"><span class="tk-ev-dot"></span><div><b>' + esc(NODE_LABEL[t.node] || t.node) + "</b><span>" +
        esc(friendly(t)) + '</span></div><span class="tk-ev-ms num">' + (t.ms > 400 ? TS.fmtMs(t.ms) : "") + "</span></li>";
    }).join("");
    if (st.status === "running") {
      var cur = currentStep(st);
      items += '<li class="tk-ev live"><span class="tk-ev-dot"></span><div><b>' + esc(cur ? (STEP_LABEL[cur] || cur) : "Planning") +
        "</b><span>Agents are working…</span></div></li>";
    }
    return items ? '<ol class="tk-feed" aria-live="polite">' + items + "</ol>" : "";
  }

  function friendly(t) {
    var s = String(t.summary || "");
    if (t.node === "plan") { var m = /workflow=(\w+)/.exec(s); return m ? "Workflow: " + m[1].replace(/_/g, " ") : s; }
    if (t.node === "facts" && /^need/.test(s)) return "Some details are missing, so you'll be asked.";
    if (t.node === "ask_facts") return "Details recorded.";
    if (t.node === "facts" && /all facts known/.test(s)) return "All the details needed are in.";
    if (t.node === "facts" && /assumed/.test(s)) return "Some details are still missing, so safe defaults were assumed (shown at the end).";
    if (/^approve_/.test(t.node)) return cap(s);
    if (t.node === "escalation") {
      var m2 = /escalate: \[(.*?)\]/.exec(s);
      return m2 ? "Needs a Chartered Accountant: " + m2[1].replace(/'/g, "").replace(/_/g, " ") : "Not needed: Taxot can handle this case.";
    }
    if (t.node === "itr_form") return "File " + s;
    if (t.node === "figures") return s.replace(/^income/, "Total income");
    if (t.node === "verify") return /^0 claims/.test(s) ? "Nothing needed checking" : s.replace(/;/g, " ·");
    if (t.node === "documents") {
      return s.replace(/findings \[(.*)\]/, function (_, list) {
        var names = list.split(",").map(function (x) { return FINDING_NAME[x.replace(/['\s]/g, "")] || x.replace(/['_]/g, " ").trim(); });
        return "found: " + names.join(", ");
      }).replace(/findings none/, "nothing to fix");
    }
    return s;
  }

  /* ------------------------------------------------------------------ action area */
  function action(st) {
    if (st.status === "running" || st.status === "new") return '<div class="panel tk-working"><span class="tk-spin" aria-hidden="true"></span><div><b>Working on it</b><span class="muted">Free AI models can take a minute or two. You can leave this tab open.</span></div></div>';
    if (st.status === "error") return '<div class="panel tk-note err">' + icon("alert") + "<div><b>Something went wrong</b><span>" + esc(st.error || "") +
      '</span><span class="muted small">Often the free AI providers are busy. Start the task again in a minute.</span></div></div>';
    if (st.status === "waiting" && st.interrupt) return interruptCard(st.interrupt, st);
    if (st.status === "done" && st.final) return results(st.final, st);
    return "";
  }

  function interruptCard(it, st) {
    if (it.type === "ask_user") return factsCard(it);
    if (it.step === "figures") return figuresCard(it, st);
    if (it.step === "regime") return regimeCard(it);
    if (it.step === "checklist") return checklistCard(it.checklist, true);
    if (it.step === "savings_plan") return savingsCard(it, true);
    return '<div class="panel tk-card"><p>' + esc(it.question || "") + '</p><div class="tk-btns"><button class="btn btn-primary" data-ans="approve">Approve</button></div></div>';
  }

  function factsCard(it) {
    var fields = (it.fields || []).map(function (f) {
      var t = String(f.type || ""), label = esc(cap(f.description || f.name.replace(/_/g, " ")));
      var lit = /Literal\[(.*)\]/.exec(t);
      if (lit) {
        var opts = lit[1].split(",").map(function (o) { return o.replace(/['"\s\]]/g, ""); });
        return '<label class="tk-f"><span>' + label + '</span><select data-fact="' + esc(f.name) + '"><option value="">—</option>' +
          opts.map(function (o) { return '<option value="' + esc(o) + '">' + esc(o.replace(/_/g, " ")) + "</option>"; }).join("") + "</select></label>";
      }
      if (/bool/.test(t)) {
        return '<div class="tk-f"><span>' + label + '</span><div class="tk-yn" role="radiogroup"><button type="button" data-yn="' + esc(f.name) +
          '" data-v="true">Yes</button><button type="button" data-yn="' + esc(f.name) + '" data-v="false">No</button></div></div>';
      }
      var money = !NOT_RUPEES[f.name];
      return '<label class="tk-f"><span>' + label + '</span><span class="tk-in">' + (money ? "<i>₹</i>" : "") +
        '<input type="text" inputmode="numeric" data-fact="' + esc(f.name) + '" placeholder="' + (money ? "0" : "") + '" /></span></label>';
    }).join("");
    return '<form class="panel tk-card tk-facts" id="tkFacts">' +
      '<div class="tk-card-h"><span class="tk-badge">' + icon("info") + 'Question</span><h3>' + esc(it.question) + "</h3>" +
        (it.hint ? '<p class="muted">' + esc(it.hint) + "</p>" : "") + "</div>" +
      '<label class="tk-label" for="tkAnsText">Answer in your own words</label>' +
      '<textarea id="tkAnsText" rows="3" placeholder="e.g. I\'m 34, I pay ₹30,000 rent in Mumbai, ₹50,000 in PPF, no capital gains…"></textarea>' +
      (S.sample ? '<button type="button" class="text-btn tk-fill" data-act="fill">' + icon("refresh") + "Fill in the sample taxpayer's answer</button>" : "") +
      '<details class="tk-fields"><summary>Or fill in the fields (' + (it.fields || []).length + ")</summary><div class=\"tk-grid\">" + fields + "</div></details>" +
      '<div class="tk-btns"><button class="btn btn-primary" type="submit">Send answer' + icon("arrowRight") + "</button></div></form>";
  }

  function figuresCard(it, st) {
    var f = it.figures || {}, prov = it.provenance || {};
    var rows = FIG_ROWS.filter(function (r) { return f[r[0]]; }).map(function (r) {
      return "<tr><td>" + esc(r[1]) + (r[2] && prov[r[2]] ? "<small>" + esc(prov[r[2]]) + "</small>" : "") + '</td><td class="num">' + inr(f[r[0]]) + "</td></tr>";
    }).join("");
    var tds = it.tds || {};
    var edit = S.showEdit ? editForm(st.facts || {}) : "";
    return '<div class="panel tk-card">' +
      '<div class="tk-card-h"><span class="tk-badge">' + icon("check") + "Approval 1</span><h3>Are these figures right?</h3>" +
      '<p class="muted">Taken from your documents and answers. Deductions only matter for the old regime.</p></div>' +
      '<table class="tk-table">' + rows + '<tr class="tot"><td>TDS already credited<small>Form 16 Part A + TDS on interest</small></td><td class="num">' + inr(tds.credited || 0) + "</td></tr></table>" +
      (it.notes && it.notes.length ? '<ul class="tk-warn">' + it.notes.map(function (n) { return "<li>" + icon("info") + esc(n) + "</li>"; }).join("") + "</ul>" : "") +
      (S.showEdit ? edit : '<div class="tk-btns"><button class="btn btn-primary" data-ans="approve">Looks right' + icon("check") + '</button><button class="btn btn-secondary" data-act="edit">Fix something</button></div>') +
      "</div>";
  }

  function editForm(facts) {
    return '<form class="tk-edit" id="tkEdit"><p class="tk-label">Correct what\'s wrong. Leave the rest as it is.</p><div class="tk-grid">' +
      EDIT_FIELDS.map(function (e) {
        var v = facts[e[0]];
        return '<label class="tk-f"><span>' + esc(e[1]) + ' <small class="muted">' + esc(e[2]) + '</small></span><span class="tk-in"><i>₹</i><input type="text" inputmode="numeric" data-edit="' +
          e[0] + '" data-orig="' + (v == null ? "" : v) + '" value="' + (v == null ? "" : inr(v, { noSymbol: true })) + '" /></span></label>';
      }).join("") + '</div><div class="tk-btns"><button class="btn btn-primary" type="submit">Recalculate</button><button type="button" class="btn btn-secondary" data-act="noedit">Cancel</button></div></form>';
  }

  function regimeCard(it) {
    var rec = it.recommended_regime, other = rec === "new" ? "old" : "new";
    return '<div class="panel tk-card"><div class="tk-card-h"><span class="tk-badge">' + icon("check") + "Approval 2</span><h3>" + esc(cap(rec)) + " regime is cheaper for you</h3>" +
      '<p class="muted">' + esc(it.explanation || "") + "</p></div>" + bars(it.old_total, it.new_total, rec) +
      (it.notes && it.notes.length ? '<details class="tk-more"><summary>How it was calculated</summary><ul>' + it.notes.map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("") + "</ul></details>" : "") +
      '<div class="tk-btns"><button class="btn btn-primary" data-ans="approve">Go with the ' + rec + " regime</button>" +
      '<button class="btn btn-secondary" data-ans="other" data-regime="' + other + '">Use the ' + other + " regime instead</button></div></div>";
  }

  function bars(oldT, newT, rec) {
    var max = Math.max(oldT || 0, newT || 0, 1);
    var bar = function (k, v) {
      return '<div class="tk-reg' + (k === rec ? " best" : "") + '"><span class="tk-reg-k">' + cap(k) + ' regime</span><span class="tk-reg-bar"><i style="width:' +
        Math.max(2, 100 * (v || 0) / max) + '%"></i></span><b class="num">' + inr(v) + "</b></div>";
    };
    return '<div class="tk-regs">' + bar("old", oldT) + bar("new", newT) + "</div>";
  }

  function checklistCard(cl, approval) {
    if (!cl) return "";
    var items = (cl.items || []).map(function (x, i) {
      return '<li><label><input type="checkbox" class="tk-check" /><span><b>' + esc(x.item) + "</b>" + (x.detail ? "<small>" + esc(x.detail) + "</small>" : "") + "</span></label></li>";
    }).join("");
    return '<div class="panel tk-card"><div class="tk-card-h">' + (approval ? '<span class="tk-badge">' + icon("check") + "Approval 3</span>" : "") +
      "<h3>Filing checklist" + (cl.itr_form ? " · " + esc(cl.itr_form) : "") + "</h3>" +
      (cl.balance != null ? '<p class="tk-bal ' + (cl.balance > 0 ? "pay" : "refund") + '">' + (cl.balance > 0 ? "Tax still to pay: " + inr(cl.balance) : cl.balance < 0 ? "Expected refund: " + inr(-cl.balance) : "No balance tax due") + "</p>" : "") +
      '</div><ol class="tk-cl">' + items + "</ol>" +
      (approval ? '<div class="tk-btns"><button class="btn btn-primary" data-ans="approve">Approve and finish</button></div><p class="muted small">Taxot never files your return; you file it on the income-tax portal.</p>' : "") + "</div>";
  }

  function savingsCard(sv, approval) {
    var recs = sv.recommendations || [];
    var list = recs.map(function (r, i) {
      return '<li class="tk-opt' + (i === 0 ? " best" : "") + '"><div class="tk-opt-h"><b>' + esc(r.label) + '</b><span class="tk-save num">saves ' + inr(r.saving) +
        "</span></div><p>" + esc(r.explanation || "") + '</p><span class="muted small">Invest ' + inr(r.extra_investment) + " more · tax becomes " + inr(r.tax_after) + " in the " + esc(r.regime_after) + " regime</span></li>";
    }).join("");
    return '<div class="panel tk-card"><div class="tk-card-h">' + (approval ? '<span class="tk-badge">' + icon("check") + "Approval</span>" : "") +
      "<h3>" + (recs.length ? "Ways to save, best first" : "Nothing will lower your tax this year") + "</h3>" +
      '<p class="muted">Your tax now: <b class="num">' + inr(sv.base_tax) + "</b>" + (sv.summary ? " · " + esc(sv.summary) : "") + "</p></div>" +
      (list ? '<ol class="tk-opts">' + list + "</ol>" : "") +
      (approval ? '<div class="tk-btns"><button class="btn btn-primary" data-ans="approve">Approve plan</button></div>' : "") + "</div>";
  }

  /* ------------------------------------------------------------------ results */
  function results(fin, st) {
    var out = [];
    var v = fin.verification;
    out.push('<div class="tk-done"><span class="tk-done-mark">' + icon("check") + "</span><div><h3>Done</h3><p class=\"muted\">" +
      (v ? esc(v.claims_checked + " statements checked against official sources" + (v.revised_texts ? ", " + v.revised_texts + " corrected" : "") +
        (v.final_failing ? ", " + v.final_failing + " removed as unverifiable" : "")) : "Results below.") + "</p></div></div>");
    var esc_ = fin.escalation;
    if (esc_ && esc_.escalate) {
      out.push('<div class="panel tk-card tk-ca">' + TS.illo("ca") + '<div class="tk-card-h"><h3>This needs a Chartered Accountant</h3><p>' +
        esc(esc_.note || "Parts of your case are outside what Taxot can safely prepare.") + "</p></div>" +
        (esc_.ca_summary ? '<details class="tk-more" open><summary>Case summary for your CA</summary><div class="tk-md">' + md(esc_.ca_summary) + "</div></details>" : "") +
        '<div class="tk-btns"><a class="btn btn-amber" href="/tasks/' + esc(S.task) + '/ca_summary.md" download>' + icon("file") + "Download summary</a></div></div>");
    }
    if (fin.documents) out.push(docsCard(fin.documents));
    if (fin.itr && fin.itr.form) {
      out.push('<div class="panel tk-card tk-itr"><div class="tk-big">' + esc(fin.itr.form) + '</div><div><h3>File ' + esc(fin.itr.form) + "</h3><ul>" +
        (fin.itr.reasons || []).map(function (r) { return "<li>" + esc(r) + "</li>"; }).join("") + "</ul>" +
        (fin.itr.due_date ? '<p class="muted small">' + icon("calendar") + " Due " + esc(fin.itr.due_date) + "</p>" : "") + cites(fin.itr.citations) + "</div></div>");
    }
    if (fin.regime && fin.regime.old_total != null) {
      var ch = fin.regime.chosen_regime || fin.regime.recommended_regime;
      out.push('<div class="panel tk-card"><div class="tk-card-h"><h3>' + esc(cap(ch)) + " regime" + (fin.regime.saving ? " · saves " + inr(fin.regime.saving) : "") +
        '</h3><p class="muted">' + esc(fin.regime.explanation || "") + "</p></div>" + bars(fin.regime.old_total, fin.regime.new_total, ch) + "</div>");
    }
    if (fin.gst) {
      out.push('<div class="panel tk-card"><div class="tk-card-h"><h3>GST registration: ' + (fin.gst.registration_required ? "required" : "not required") +
        '</h3><p class="muted">' + esc(fin.gst.explanation || "") + "</p></div>" + cites(fin.gst.citations) + "</div>");
    }
    if (fin.savings) out.push(savingsCard(fin.savings, false));
    if (fin.checklist) out.push(checklistCard(fin.checklist, false));
    if (fin.assumptions && fin.assumptions.length) {
      out.push('<div class="panel tk-note warn">' + icon("info") + "<div><b>Assumptions made</b><span>" + esc(fin.assumptions.join("; ")) + "</span></div></div>");
    }
    out.push('<div class="tk-final-foot"><p class="muted small">' + esc(fin.disclaimer || "") + '</p><button class="btn btn-secondary btn-sm" data-act="end">' +
      icon("x") + "Delete my data and start over</button></div>");
    return out.join("");
  }

  function docsCard(rep) {
    var fs = rep.findings || [];
    var cards = fs.map(function (f) {
      var hi = f.code === "injection_detected" || /pan|tds|cap/.test(f.code);
      return '<li class="tk-find' + (hi ? " hi" : "") + '"><div class="tk-find-h">' + icon(hi ? "alert" : "info") + "<b>" + esc(f.title || f.code) + "</b>" +
        (f.amount ? '<span class="num">' + inr(f.amount) + "</span>" : "") + "</div><p>" + esc(f.explanation || "") + "</p>" +
        (f.action ? '<p class="tk-act">' + icon("arrowRight") + esc(f.action) + "</p>" : "") + cites(f.citations) + "</li>";
    }).join("");
    return '<div class="panel tk-card"><div class="tk-card-h"><h3>' + (fs.length ? "Document check: " + fs.length + " thing" + (fs.length === 1 ? "" : "s") + " to fix" : "Document check: all clear") +
      "</h3>" + (rep.summary ? '<p class="muted">' + esc(rep.summary) + "</p>" : "") + "</div>" + (cards ? '<ul class="tk-finds">' + cards + "</ul>" : "") + "</div>";
  }

  function cites(c) {
    if (!c || !c.length) return "";
    return '<div class="tk-cites">' + c.map(function (x) { return '<span class="tk-cite">' + esc(x) + "</span>"; }).join("") + "</div>";
  }

  // Minimal Markdown for the CA summary (headings, bold/italic, lists, tables, rules)
  function md(src) {
    var lines = String(src).split("\n"), html = [], list = null, table = [];
    // italics only for _whole phrases_ (not underscores inside file names like form16_acme_ltd.pdf)
    var inline = function (s) {
      return esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(^|[\s(])_([^_]+?)_(?=$|[\s.,;:)])/g, "$1<i>$2</i>");
    };
    var flush = function () {
      if (list) { html.push("</" + list + ">"); list = null; }
      if (table.length) {
        var rows = table.filter(function (r) { return !/^\|\s*-/.test(r); }).map(function (r, i) {
          var cells = r.replace(/^\||\|$/g, "").split("|");
          return "<tr>" + cells.map(function (c) { return (i ? "<td>" : "<th>") + inline(c.trim()) + (i ? "</td>" : "</th>"); }).join("") + "</tr>";
        });
        html.push('<table class="tk-table">' + rows.join("") + "</table>"); table = [];
      }
    };
    lines.forEach(function (l) {
      if (/^\|/.test(l)) { if (list) { html.push("</" + list + ">"); list = null; } table.push(l); return; }
      if (table.length) flush();
      var m;
      if ((m = /^(#{1,3})\s+(.*)/.exec(l))) { flush(); html.push("<h4>" + inline(m[2]) + "</h4>"); }
      else if ((m = /^[-*]\s+(.*)/.exec(l))) { if (list !== "ul") { flush(); html.push("<ul>"); list = "ul"; } html.push("<li>" + inline(m[1]) + "</li>"); }
      else if ((m = /^\d+\.\s+(.*)/.exec(l))) { if (list !== "ol") { flush(); html.push("<ol>"); list = "ol"; } html.push("<li>" + inline(m[1]) + "</li>"); }
      else if (/^---/.test(l)) { flush(); html.push("<hr>"); }
      else if (l.trim()) { flush(); html.push("<p>" + inline(l) + "</p>"); }
    });
    flush();
    return html.join("");
  }

  /* ------------------------------------------------------------------ events */
  function onClick(e) {
    var t;
    if ((t = e.target.closest("[data-wf]"))) { S.workflow = t.getAttribute("data-wf"); $$("[data-wf]").forEach(function (b) { var on = b === t; b.classList.toggle("on", on); b.setAttribute("aria-checked", on); }); return; }
    if ((t = e.target.closest("[data-rm]"))) { S.files.splice(+t.getAttribute("data-rm"), 1); renderStart(); return; }
    if ((t = e.target.closest("[data-sample]"))) { startTask(t.getAttribute("data-sample")); return; }
    if ((t = e.target.closest("[data-yn]"))) {
      $$('[data-yn="' + t.getAttribute("data-yn") + '"]').forEach(function (b) { b.classList.toggle("on", b === t); });
      return;
    }
    if ((t = e.target.closest("[data-ans]"))) {
      var a = t.getAttribute("data-ans");
      if (a === "approve") send({ approved: true });
      else if (a === "other") send({ approved: false, edits: { regime: t.getAttribute("data-regime") }, note: "use " + t.getAttribute("data-regime") });
      return;
    }
    if ((t = e.target.closest("[data-act]"))) {
      var act = t.getAttribute("data-act");
      if (act === "edit") { S.showEdit = true; render(); }
      else if (act === "noedit") { S.showEdit = false; render(); }
      else if (act === "fill") fillSample(t);
      else if (act === "end") endTask();
    }
  }

  function onChange(e) { if (e.target.id === "tkFiles") addFiles(e.target.files); }

  function onSubmit(e) {
    if (e.target.id === "tkStart") { e.preventDefault(); startTask(null); return; }
    if (e.target.id === "tkFacts") {
      e.preventDefault();
      var text = ($("#tkAnsText").value || "").trim(), facts = {};
      $$("[data-fact]", e.target).forEach(function (inp) {
        var v = inp.value.trim(); if (!v) return;
        var n = Number(v.replace(/[,₹\s]/g, ""));
        facts[inp.getAttribute("data-fact")] = inp.tagName === "SELECT" || !isFinite(n) ? v : n;
      });
      $$("[data-yn].on", e.target).forEach(function (b) { facts[b.getAttribute("data-yn")] = b.getAttribute("data-v") === "true"; });
      if (!text && !Object.keys(facts).length) { TS.toast("Type an answer or fill in a field", "warn"); return; }
      if (text) {
        var extra = Object.keys(facts).map(function (k) { return k.replace(/_/g, " ") + ": " + facts[k]; }).join("; ");
        send({ text: text + (extra ? "\nAlso: " + extra : "") });
      } else send({ facts: facts });
      return;
    }
    if (e.target.id === "tkEdit") {
      e.preventDefault();
      var edits = {};
      $$("[data-edit]", e.target).forEach(function (inp) {
        var raw = inp.value.replace(/[,₹\s]/g, ""), orig = inp.getAttribute("data-orig");
        if (raw === "" || raw === orig) return;
        if (isFinite(Number(raw))) edits[inp.getAttribute("data-edit")] = Number(raw);
      });
      if (!Object.keys(edits).length) { S.showEdit = false; render(); return; }
      S.showEdit = false;
      send({ approved: false, edits: edits });
    }
  }

  function send(answer) {
    if (S.busy || !S.task) return;
    S.busy = true;
    $$("#tasksBody .tk-btns .btn").forEach(function (b) { b.disabled = true; });
    http("/tasks/" + S.task + "/answer", { body: { answer: answer } })
      .then(function (st) { S.st = st; render(); poll(); })
      .catch(function (e) { TS.toast(e.message, "warn"); $$("#tasksBody .tk-btns .btn").forEach(function (b) { b.disabled = false; }); })
      .then(function () { S.busy = false; });
  }

  function fillSample(btn) {
    var it = S.st && S.st.interrupt; if (!it || !S.sample) return;
    btn.disabled = true;
    http("/samples/" + S.sample + "/answer", { body: { fields: (it.fields || []).map(function (f) { return f.name; }) } })
      .then(function (d) { $("#tkAnsText").value = d.text; $("#tkAnsText").focus(); })
      .catch(function (e) { TS.toast(e.message, "warn"); })
      .then(function () { btn.disabled = false; });
  }

  function endTask() {
    var id = S.task;
    if (!id) return reset();
    var working = S.st && S.st.status === "running";
    var btn = $('#tasksBody [data-act="end"]');
    if (working && btn && !btn.classList.contains("armed")) {   // two clicks instead of a blocking confirm()
      btn.classList.add("armed"); btn.textContent = "Click again to cancel";
      setTimeout(function () { if (btn.isConnected) { btn.classList.remove("armed"); btn.textContent = "Cancel"; } }, 4000);
      return;
    }
    http("/tasks/" + id, { method: "DELETE" }).catch(function () {}).then(function () { TS.toast("Task closed and your documents deleted", "ok"); reset(); });
  }

  // Development hook: render a given task status without the server (used for visual checks and the offline replay).
  TS.tasksPreview = function (st, task) {
    stopPoll(); S.task = task || "preview"; S.st = st; S.sig = ""; S.cardKey = ""; S.seen = 0; S.started = S.started || Date.now() - 64000;
    render();
  };

  /* ------------------------------------------------------------------ helpers */
  function cap(s) { s = String(s || ""); return s.charAt(0).toUpperCase() + s.slice(1); }
  function fmtSecs(s) { return s < 60 ? s + " s" : Math.floor(s / 60) + " min " + (s % 60) + " s"; }
})();
