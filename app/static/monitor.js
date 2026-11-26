/* Taxot — Monitor tab (M5 monitoring dashboard). Reads GET /monitoring, which aggregates logs/*.jsonl. */
(function () {
  "use strict";
  var TS = window.TS;
  if (!TS || !TS.onView) return;
  var $ = TS.$, esc = TS.esc, pct = TS.pct;

  function ms(v) { return v == null ? "—" : TS.fmtMs(v); }
  function num(v) { return v == null ? "—" : Number(v).toLocaleString("en-IN"); }
  function when(ts) {
    if (!ts) return "";
    var d = new Date(ts);
    return isNaN(d) ? "" : d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  }

  function kpi(i, v, label, sub) {
    return '<div class="kpi" style="--i:' + i + '"><span class="kpi-label">' + esc(label) + '</span><span class="kpi-v num">' + v +
      '</span><span class="kpi-sub">' + esc(sub) + "</span></div>";
  }

  function bars(series) {
    if (!series.length) return '<p class="muted small">No questions logged yet.</p>';
    var max = Math.max.apply(null, series.map(function (d) { return d.queries; }).concat([1]));
    return '<div class="mon-bars" role="img" aria-label="Questions per day">' + series.map(function (d) {
      var h = d.queries / max, r = d.queries ? d.refused / d.queries : 0;
      var lbl = d.day.slice(5).replace("-", "/");
      return '<div class="mon-bar" title="' + esc(d.day + ": " + d.queries + " questions, " + d.refused + " refused") + '">' +
        '<span class="mon-col" style="--h:' + h.toFixed(3) + '"><i class="mon-ref" style="--r:' + r.toFixed(3) + '"></i></span>' +
        '<span class="mon-n">' + (d.queries || "") + '</span><span class="mon-d">' + esc(lbl) + "</span></div>";
    }).join("") + '</div><p class="muted small mon-legend"><i class="sw sw-q"></i>answered <i class="sw sw-r"></i>refused</p>';
  }

  function dist(obj) {
    var keys = Object.keys(obj || {});
    if (!keys.length) return '<p class="muted small">—</p>';
    var tot = keys.reduce(function (a, k) { return a + obj[k]; }, 0);
    return '<ul class="mon-dist">' + keys.sort(function (a, b) { return obj[b] - obj[a]; }).map(function (k) {
      var f = obj[k] / tot;
      return '<li><span class="md-k">' + esc(k.replace(/_/g, " ")) + '</span><span class="md-bar"><i style="--f:' + f.toFixed(3) + '"></i></span><span class="md-v num">' + obj[k] + "</span></li>";
    }).join("") + "</ul>";
  }

  function relabel(obj, names) {
    var o = {};
    Object.keys(obj || {}).forEach(function (k) { var n = names[k] || k; o[n] = (o[n] || 0) + obj[k]; });
    return o;
  }

  function list(rows, right, empty) {
    if (!rows.length) return '<p class="muted small">' + esc(empty) + "</p>";
    return '<ul class="mon-list">' + rows.map(function (r) {
      return '<li><span class="ml-q">' + esc(r.question || "") + '</span><span class="ml-r">' + right(r) + "</span></li>";
    }).join("") + "</ul>";
  }

  function panel(title, sub, body) {
    return '<section class="panel mon-panel"><div class="panel-head"><div><h3>' + esc(title) + "</h3>" +
      (sub ? '<p class="muted small">' + esc(sub) + "</p>" : "") + "</div></div>" + body + "</section>";
  }

  function render(d) {
    var q = d.queries || {}, f = d.feedback || {}, l = d.llm || {};
    var votes = (f.up || 0) + (f.down || 0);
    $("#monMeta").innerHTML = '<span class="muted small">' + (d.mock ? "Demo mode: no live server logs. " : "") +
      "Updated " + esc(when(d.generated_at)) + ' · <button type="button" class="btn btn-ghost btn-sm" id="monRefresh">Refresh</button></span>';
    $("#monRefresh").onclick = load;

    var html = '<div class="kpis">' +
      kpi(0, num(q.total), "Questions answered", num(q.last_24h) + " in the last 24 hours") +
      kpi(1, pct(q.refusal_rate), "Refused or sent to a CA", "out of scope or weak evidence") +
      kpi(2, ms(q.latency_p50_ms), "Median answer time", "p95 " + ms(q.latency_p95_ms)) +
      kpi(3, votes ? pct((f.up || 0) / votes) : "—", "Thumbs up", votes + " votes (" + (f.down || 0) + " down)") +
      "</div>";

    html += '<div class="mon-grid">';
    html += panel("Questions per day", "Last " + (q.per_day || []).length + " days. The darker part was refused.", bars(q.per_day || []));
    html += panel("Why questions were refused", "Watch for a rise: it means users ask about things we don't cover.", dist(q.refusal_reasons));
    html += panel("Possible gaps in the library", (q.near_gate_count || 0) + " answered questions scored close to the refusal gate (θ = " +
      (d.threshold == null ? "—" : d.threshold.toFixed(2)) + "). These are the first to check.",
      list(q.near_gate || [], function (r) { return '<span class="num">' + r.top_score.toFixed(2) + "</span>"; }, "None yet."));
    html += panel("Recent thumbs-down", "Read these first when improving answers.",
      list(f.recent_down || [], function (r) { return esc(when(r.ts)); }, "No negative feedback yet."));
    html += panel("Recently refused", "Masked before logging: PAN, Aadhaar, phone and e-mail never reach the log.",
      list(q.recent_refused || [], function (r) { return esc((r.reason || "").replace(/_/g, " ")); }, "Nothing refused yet."));
    html += panel("Question types", "From the intent classifier, and the language detected.", dist(q.intents) + '<p class="muted small mon-sub">Language</p>' + dist(relabel(q.languages, { en: "English", hinglish: "Hinglish", hi: "Hindi" })));
    html += "</div>";

    var prov = l.providers || [];
    html += panel("AI providers", num(l.calls) + " calls · " + pct(l.ok_rate) + " succeeded. Failed calls fall back to the next provider, then to an answer built from the sources.",
      prov.length ? '<div class="table-scroll"><table class="exp-table"><thead><tr><th class="sticky" scope="col">Provider</th><th class="num" scope="col">Calls</th><th class="num" scope="col">Succeeded</th><th class="num" scope="col">Median time</th><th class="num" scope="col">Tokens in</th><th class="num" scope="col">Tokens out</th></tr></thead><tbody>' +
        prov.map(function (p) {
          return '<tr><td class="sticky">' + esc(p.provider === "*" ? "none free (all busy)" : p.provider) + '</td><td class="num">' + num(p.calls) + '</td><td class="num">' + pct(p.ok_rate) +
            '</td><td class="num">' + ms(p.p50_ms) + '</td><td class="num">' + num(p.input_tokens) + '</td><td class="num">' + num(p.output_tokens) + "</td></tr>";
        }).join("") + "</tbody></table></div>" : '<p class="muted small">No AI calls logged yet.</p>');

    $("#monBody").innerHTML = html;
    if (TS.reveal) TS.reveal(document.querySelectorAll("#monBody .kpi, #monBody .panel"), { step: 50, cap: 400 });
  }

  function load() {
    TS.api("/monitoring", { timeout: 30000 }).then(render).catch(function (e) {
      $("#monBody").innerHTML = '<div class="notice error-card"><div><p class="notice-title">Couldn\'t load the monitoring data</p><p class="notice-detail">' +
        esc(e.message) + '</p><div class="notice-actions"><button type="button" class="btn btn-secondary btn-sm" id="monRetry">Retry</button></div></div></div>';
      $("#monRetry").onclick = load;
    });
  }

  TS.onView("monitor", load);
  if (document.body.getAttribute("data-view") === "monitor") load();
})();
