/* TaxSaathi demo UI: Compare, Calculator, Results and How-it-works views. */
(function () {
  "use strict";
  var TS = window.TS;
  var $ = TS.$, $$ = TS.$$, esc = TS.esc, inr = TS.inr, icon = TS.icon;
  var SVGNS = "http://www.w3.org/2000/svg";

  /* ================================================================== */
  /* COMPARE                                                             */
  /* ================================================================== */
  // [chip label, full question]: questions where the law changed recently
  var PRESETS = [
    ["GST on an AC today", "What is the GST rate on air conditioners today?"],
    ["87A rebate limit now", "What is the 87A rebate limit now?"],
    ["GST on AC in Aug 2025", "What was GST on AC in August 2025?"],
  ];
  var cmp = { pending: false, seq: 0 };
  var T_START = Date.parse("2024-04-01"), T_END = Date.parse("2027-03-31");
  var EVENTS = [["2025-09-22", "GST 2.0", "22 Sep 2025", "GST 2.0"], ["2026-04-01", "Income-tax Act 2025", "1 Apr 2026", "New Act"]];

  function initCompare() {
    $("#comparePresets").innerHTML = PRESETS.map(function (p, i) { return '<button type="button" class="pill trap" style="--i:' + i + '" data-cq="' + esc(p[1]) + '" title="' + esc(p[1]) + '">' + esc(p[0]) + "</button>"; }).join("");
    $("#comparePresets").addEventListener("click", function (e) {
      var b = e.target.closest("[data-cq]"); if (!b || cmp.pending) return;
      $("#compareInput").value = b.getAttribute("data-cq");
      runCompare(b.getAttribute("data-cq"));
    });
    $("#compareForm").addEventListener("submit", function (e) {
      e.preventDefault();
      var q = $("#compareInput").value.trim();
      if (!q) { $("#compareInput").focus(); var bx = $(".cmp-box"); bx.classList.remove("nudge"); void bx.offsetWidth; bx.classList.add("nudge"); return; }
      if (!cmp.pending) runCompare(q);
    });
    $("#compareStage").addEventListener("click", function (e) {
      var pill = e.target.closest(".cite[data-cite]");
      if (pill) {
        var card = pill.closest(".cmp-card");
        var det = $(".cmp-full", card); if (det && !det.open) det.open = true;
        $$(".cite.active", card).forEach(function (p) { p.classList.remove("active"); });
        pill.classList.add("active");
        TS.focusCite(card, pill.getAttribute("data-cite"));
        return;
      }
      var cp = e.target.closest(".cite-calc");
      if (cp) { var mc = cp.closest(".cmp-card").querySelector(".calc-block"); if (mc) TS.flashEl(mc); return; }
      var oc = e.target.closest(".open-calc");
      if (oc && cmp.last && cmp.last.taxsaathi.calculation && TS.showCalc) { TS.showCalc(cmp.last.taxsaathi.calculation); return; }
      var tr = e.target.closest(".open-trace");
      if (tr && cmp.last && TS.injectAsk) TS.injectAsk(cmp.lastQ, cmp.last.taxsaathi);
    });
    renderCompareEmpty();
  }

  function renderCompareEmpty() {
    $("#compareStage").innerHTML = '<div class="cmp-empty">' + TS.illo("compare") + "<p>Pick a trap above. Both answer side by side.</p></div>";
  }

  function cardShell(kind, body) {
    var plain = kind === "plain";
    return '<article class="panel cmp-card ' + kind + '">' +
      '<header class="cc-head"><span class="cc-icon' + (plain ? "" : " accent") + '" aria-hidden="true">' + (plain ? '<svg viewBox="0 0 24 24"><path d="M20.5 11.5a8 8 0 0 1-11.9 7L4 19.8l1.3-4.3A8 8 0 1 1 20.5 11.5Z"/></svg>' : TS.markSvg()) + "</span>" +
      "<div><h2>" + (plain ? "Normal chatbot" : "TaxSaathi") + "</h2><p>" + (plain ? "Same AI, no documents" : "Checks the official law first") + '</p></div><span class="cc-lat"></span></header>' +
      '<div class="cc-body">' + body + "</div></article>";
  }

  function loadingHtml(text) {
    return '<div class="progress small"><div class="pg-line"><span class="pg-mark" aria-hidden="true">' + TS.markSvg("thinking") + '</span><span class="pg-text">' + esc(text) + '</span><span class="pg-time num">0s</span></div>' +
      '<div class="cmp-sk" aria-hidden="true"><span class="skeleton sk-pill"></span><span class="skeleton sk-num"></span><div class="sk-lines"><span class="skeleton"></span><span class="skeleton short"></span></div></div></div>';
  }

  function runCompare(q) {
    cmp.pending = true;
    var my = ++cmp.seq;
    $("#compareSend").disabled = true;
    document.body.classList.add("thinking");
    $$("#comparePresets .pill").forEach(function (p) { p.classList.toggle("on", p.getAttribute("data-cq") === q); });
    var stage = $("#compareStage");
    stage.innerHTML = '<div class="cmp-grid">' + cardShell("plain", loadingHtml("Asking the normal chatbot…")) + cardShell("ts", loadingHtml("Looking up the official law…")) + "</div>" +
      '<p class="cmp-wait">Both answers are written one after the other on a CPU server, so this takes 1–2 minutes.</p>';
    TS.reveal($$(".cmp-card", stage), { step: 80 });
    var steps = ["Looking up the official law…", "Checking which dates apply…", "Reading the best passages…", "Writing the answer…"];
    var t0 = performance.now();
    var clock = setInterval(function () {
      var t = performance.now() - t0;
      $$(".pg-time", stage).forEach(function (el) { el.textContent = Math.floor(t / 1000) + "s"; });
      var tt = $(".ts .pg-text", stage); if (tt) { var nt = steps[Math.min(steps.length - 1, Math.floor(t / 9000))]; if (tt.textContent !== nt) { tt.textContent = nt; tt.classList.remove("swap"); void tt.offsetWidth; tt.classList.add("swap"); } }
    }, 250);
    TS.api("/compare", { body: { question: q }, timeout: 300000 })
      .then(function (d) {
        if (my !== cmp.seq) return;
        cmp.last = { plain: TS.normalize(d.plain), taxsaathi: TS.normalize(d.taxsaathi) };
        cmp.lastQ = q;
        renderCompare(cmp.last);
        TS.markLanded();
      })
      .catch(function (e) {
        if (my !== cmp.seq) return;
        stage.innerHTML = '<div class="notice error-card"><span class="notice-illo">' + TS.illo("offline") + '</span><div><p class="notice-title">Comparison failed</p><p class="notice-detail">' + esc(e.message) + '</p><div class="notice-actions"><button type="button" class="btn btn-secondary btn-sm" id="cmpRetry">' + icon("refresh") + "Try again</button></div></div></div>";
        $("#cmpRetry").onclick = function () { runCompare(q); };
      })
      .then(function () { clearInterval(clock); if (my === cmp.seq) { cmp.pending = false; $("#compareSend").disabled = false; document.body.classList.remove("thinking"); } });
  }

  // Plain text of an answer without citation markers or markdown
  function plainText(t) { return String(t || "").replace(/\s*\[[A-Za-z0-9][^\]]{2,}\]/g, "").replace(/\*\*/g, "").replace(/\s+/g, " ").trim(); }
  function firstSentence(t) { var s = plainText(t); var m = /^(.{20,220}?[.!?])(\s|$)/.exec(s); return m ? m[1] : s.slice(0, 180); }
  // The number the answer is really about: bold first, then the first % or ₹ amount
  function keyNumber(t) {
    var src = String(t || "");
    // "Rs 50,000", "Rs. 50,000" and "INR 50,000" count as rupee amounts too (the plain model often writes them)
    src = src.replace(/\b(?:Rs\.?|INR)\s?(?=\d)/gi, "₹");
    var NUM = /(₹\s?[\d,]+(?:\.\d+)?(?:\s?(?:lakh|crore|L|Cr))?|\d+(?:\.\d+)?\s?%)/i;
    var bolds = src.match(/\*\*([^*]+)\*\*/g) || [];
    var hit = null;
    for (var i = 0; i < bolds.length && !hit; i++) { var m = NUM.exec(bolds[i]); if (m) hit = m[1]; }
    if (!hit) { var m2 = NUM.exec(plainText(src)); hit = m2 ? m2[1] : null; }
    if (!hit) return null;
    hit = hit.replace(/\s+/g, " ");
    // ₹12,00,000 reads better as ₹12 lakh (and matches how people say it)
    var n = /^₹ ?([\d,]+)$/.exec(hit);
    if (n) { var v = +n[1].replace(/,/g, ""); if (v >= 100000) return "₹" + TS.lakhWords(v); }
    return hit;
  }

  function renderCompare(last) {
    var p = last.plain, t = last.taxsaathi;
    var per = TS.stepData(t.trace, "period") || t.period || null;
    var gate = TS.stepData(t.trace, "gate"), cc = TS.stepData(t.trace, "citation_check"), df = TS.stepData(t.trace, "date_filter");
    var pk = keyNumber(p.answer), tk = t.refused ? null : keyNumber(t.answer);
    var differ = pk && tk && pk.replace(/\s/g, "") !== tk.replace(/\s/g, "");
    var lawFor = per && per.start ? (per.assumed_current ? "law in force today" : "law for " + TS.periodLabel(per)) : "law in force";

    var plainBody =
      '<div class="cc-verdict bad">' + icon("alert") + "<span>No source · may be outdated</span></div>" +
      keyBlock(pk, firstSentence(p.answer), differ, "plain") +
      '<ul class="cc-facts">' +
      "<li>" + icon("x") + "0 sources</li>" +
      "<li>" + icon("x") + "No date check</li>" +
      "<li>" + icon("x") + "No safety check</li></ul>" +
      fullAnswer('<div class="prose answer">' + TS.richText(p.answer || "(no answer)", [], "plain") + "</div>");

    var nCites = t.citations.length;
    var verdict = t.refused ? '<div class="cc-verdict warn">' + icon("briefcase") + "<span>Refused safely · suggests a CA</span></div>"
      : nCites ? '<div class="cc-verdict good">' + icon("check") + "<span>Cited · " + esc(lawFor) + "</span></div>"
      : '<div class="cc-verdict warn">' + icon("info") + "<span>No official source found</span></div>";
    var facts = [];
    facts.push(icon(nCites ? "check" : "x") + nCites + " source" + (nCites === 1 ? "" : "s") + (cc && cc.n_valid_tags != null ? " checked" : ""));
    if (per && per.start) facts.push(icon("calendar") + (per.assumed_current ? "Today's law" : TS.periodLabel(per)));
    if (df && df.removed && df.removed.length) facts.push(icon("x") + df.removed.length + " outdated passages dropped");
    else if (gate) facts.push(icon(gate.passed ? "check" : "briefcase") + (gate.passed ? "Safety check passed" : "Safety check: ask a CA"));
    var tsInner = "";
    if (t.refused) tsInner = '<div class="ca-card compact"><span class="ca-illo">' + TS.illo("ca") + '</span><div class="ca-main"><h3 class="ca-title">This needs a Chartered Accountant</h3>' + (t.refusal_reason ? '<p class="ca-why">' + esc(TS.reasonText(t.refusal_reason)) + "</p>" : "") + "</div></div>";
    else if (t.follow_up) tsInner = '<div class="followup"><p class="fu-label">One more detail needed</p><div class="fu-q">' + TS.richText(t.follow_up, [], "cmp") + "</div></div>";
    else tsInner = keyBlock(tk, firstSentence(t.answer), differ, "ts");
    var full = "";
    if (!t.refused && !t.follow_up) {
      if (TS.calcBlock && t.calculation && t.calculation.old) full += TS.calcBlock(t.calculation);
      full += '<div class="prose answer">' + TS.richText(t.answer, t.citations, "cmp") + "</div>";
    } else if (t.refused && t.answer) full += '<div class="prose answer">' + TS.richText(t.answer, t.citations, "cmp") + "</div>";
    if (nCites) full += '<div class="cc-sources"><p class="eyebrow">Sources · ' + nCites + "</p>" + t.citations.map(function (c, i) { return TS.citeCardHtml(c, i, "cmp"); }).join("") + "</div>";
    var tsBody = verdict + tsInner + '<ul class="cc-facts good">' + facts.map(function (f) { return "<li>" + f + "</li>"; }).join("") + "</ul>" +
      (full ? fullAnswer(full) : "") +
      '<div class="cc-foot"><button type="button" class="text-btn open-trace">' + icon("route") + "How this was found</button></div>";

    var stage = $("#compareStage");
    stage.innerHTML = '<div class="cmp-grid">' + cardShell("plain", plainBody) + cardShell("ts", tsBody) + "</div>" + timelineHtml(per, t);
    $(".plain .cc-lat", stage).innerHTML = TS.latencyBadge(p.latency_ms);
    $(".ts .cc-lat", stage).innerHTML = TS.latencyBadge(t.latency_ms);
    TS.wireCiteCards(stage);
    var units = [];
    $$(".cmp-card", stage).forEach(function (c) { units.push(c); $$(".cc-verdict, .cc-key, .cc-lead, .cc-facts li, .ca-card", c).forEach(function (x) { units.push(x); }); });
    units.push($(".cmp-tl", stage));
    TS.reveal(units.filter(Boolean), { step: 30, cap: 420 });
  }

  function keyBlock(k, lead, differ, kind) {
    return (k ? '<p class="cc-key num' + (differ ? " differ" : "") + '">' + esc(k) + "</p>" : "") + '<p class="cc-lead' + (k ? "" : " big") + '">' + esc(lead) + "</p>";
  }
  function fullAnswer(inner) {
    return '<details class="cmp-full"><summary>' + icon("chevDown", "chev") + "<span>Read full answer</span></summary><div class=\"cmp-full-body\">" + inner + "</div></details>";
  }

  // Which period of law each answer used, on one shared date axis
  function timelineHtml(per, t) {
    var span = T_END - T_START;
    var pos = function (iso) { return Math.max(0, Math.min(100, ((Date.parse(iso) - T_START) / span) * 100)); };
    var today = (TS.state.health && TS.state.health.today) || "2026-10-29";
    var years = ["2024-04-01", "2025-04-01", "2026-04-01"].map(function (y, i) {
      return '<span class="tl-year" style="left:' + pos(y) + '%">' + ["FY 24-25", "FY 25-26", "TY 26-27"][i] + "</span>";
    }).join("");
    var events = EVENTS.map(function (e, i) { return '<span class="tl-event lv' + (i % 2) + '" style="left:' + pos(e[0]) + '%"><b><span class="tl-long">' + esc(e[1]) + '</span><span class="tl-short">' + esc(e[3]) + "</span></b><small>" + esc(e[2]) + "</small></span>"; }).join("") +
      '<span class="tl-event today lv0" style="left:' + pos(today) + '%"><b>Today</b><small>' + esc(TS.fmtDate(today)) + "</small></span>";
    var tsRow = "";
    if (per && per.start) {
      var s = pos(per.start), e = pos(per.end || per.start);
      var w = Math.max(1.2, e - s);
      tsRow = '<span class="tl-win" style="left:' + s + "%;width:" + w + '%"></span><span class="tl-pin" style="left:' + (s + w / 2) + '%">' + esc(per.assumed_current ? "today's law" : TS.periodLabel(per)) + "</span>";
    }
    var cites = (t.citations || []).filter(function (c) { return c.effective_from; }).slice(0, 4).map(function (c, i) {
      var a = pos(c.effective_from), b = c.effective_to ? pos(c.effective_to) : 100;
      return '<span class="tl-cite" style="left:' + a + "%;width:" + Math.max(0.8, b - a) + "%;--k:" + i + '" title="' + esc((c.title || c.id) + ": " + TS.citePeriod(c).text) + '"></span>';
    }).join("");
    return '<section class="panel cmp-tl" aria-label="Which period of law each answer used">' +
      '<div class="tl-head"><h3>Which law did each answer use?</h3></div>' +
      '<div class="tl-grid">' +
      '<span class="tl-k"></span><div class="tl-axis">' + years + events + "</div>" +
      '<span class="tl-k">Normal chatbot</span><div class="tl-track"><span class="tl-fog"></span><span class="tl-fog-label">memory, date unknown</span></div>' +
      '<span class="tl-k ts">TaxSaathi</span><div class="tl-track ts">' + cites + tsRow + "</div>" +
      "</div></section>";
  }

  /* ================================================================== */
  /* CALCULATOR                                                          */
  /* ================================================================== */
  // Deductions, in plain words: [name, label, hint, max (for the "Max" shortcut) or 0]
  var DEDS = [
    ["deductions_80c", "Savings & investments", "PF, PPF, ELSS, LIC · 80C", 150000],
    ["deductions_80d", "Health insurance", "You & family · 80D", 25000],
    ["hra_exemption", "Rent (tax-free HRA)", "Exempt part of your HRA", 0],
    ["home_loan_interest", "Home-loan interest", "Own house · up to ₹2 L", 200000],
    ["deductions_80d_parents", "Parents' health insurance", "80D for parents", 25000],
    ["nps_80ccd1b", "Extra NPS (your own)", "80CCD(1B)", 50000],
    ["employer_nps", "Employer's NPS", "80CCD(2) · counts in both", 0],
    ["other_deductions", "Other deductions", "80E, 80G, 80TTA…", 0],
  ];
  var MAIN_LABEL = { salary: "What do you earn in a year?", professional_presumptive: "What do clients pay you in a year?" };
  var SAL_CHIPS = [600000, 800000, 1200000, 1500000, 2500000, 5000000];
  var CALC_PRESETS = [
    { label: "₹8 L fresher", v: { gross_salary: 800000 } },
    { label: "₹18 L with many savings", v: { gross_salary: 1800000, deductions_80c: 150000, deductions_80d: 25000, hra_exemption: 240000, home_loan_interest: 200000, nps_80ccd1b: 50000 } },
    { label: "₹24 L freelancer", v: { gross_salary: 2400000, income_type: "professional_presumptive" } },
    { label: "₹45 L, age 60+", v: { gross_salary: 4500000, deductions_80c: 150000, deductions_80d: 50000, age: "60to80" } },
  ];
  var calc = { age: "below60", year: "2026-27", type: "salary", seq: 0, ran: false, noIncomeType: false, parentsSenior: false };

  function parseNum(s) { var d = String(s || "").replace(/[^\d]/g, ""); return d ? parseInt(d.slice(0, 11), 10) : 0; }
  function shortL(v) { return "₹" + TS.lakhWords(v).replace(" lakh", " L").replace(" crore", " Cr").replace(" thousand", "k"); }

  function dedHtml(f) {
    return '<label class="ded field"><span class="ded-k">' + esc(f[1]) + '</span><span class="ded-h">' + esc(f[2]) + '</span>' +
      '<span class="ded-in"><span aria-hidden="true">₹</span><input class="num" type="text" inputmode="numeric" autocomplete="off" name="' + f[0] + '" id="f-' + f[0] + '" placeholder="0" aria-label="' + esc(f[1]) + '" />' +
      (f[3] ? '<button type="button" class="ded-max" data-max="' + f[3] + '" tabindex="-1" title="Fill the maximum">Max</button>' : "") + "</span>" +
      (f[0] === "deductions_80d_parents" ? '<span class="ded-check"><input type="checkbox" id="calcParentsSenior" /><label for="calcParentsSenior">Parents are 60+</label></span>' : "") +
      "</label>";
  }

  // Re-format with Indian commas while typing, keeping the caret after the same digit
  function liveFormat(inp) {
    var pos = inp.selectionStart == null ? inp.value.length : inp.selectionStart;
    var digitsBefore = inp.value.slice(0, pos).replace(/[^\d]/g, "").length;
    var v = parseNum(inp.value);
    var out = v ? inr(v, { noSymbol: true }) : "";
    inp.value = out;
    var p = 0, seen = 0;
    while (p < out.length && seen < digitsBefore) { if (/\d/.test(out[p])) seen++; p++; }
    try { inp.setSelectionRange(p, p); } catch (e) { /* not focused */ }
  }

  // Sliding thumb for every segmented control
  function segMove(seg) {
    var ind = $(".seg-ind", seg), b = $('button[aria-checked="true"]', seg);
    if (!ind || !b || !b.offsetWidth) return;
    ind.style.transform = "translateX(" + b.offsetLeft + "px)";
    ind.style.width = b.offsetWidth + "px";
    ind.classList.add("ready");
  }
  TS.segMove = segMove;
  function segInit(sel, cb) {
    var seg = $(sel);
    seg.addEventListener("click", function (e) {
      var b = e.target.closest("button[data-value]"); if (!b) return;
      segSet(seg, b.getAttribute("data-value")); cb(b.getAttribute("data-value"));
    });
    seg.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      e.preventDefault();
      var bs = $$("button[data-value]", seg), i = bs.indexOf(document.activeElement);
      var n = bs[(i + (e.key === "ArrowRight" ? 1 : bs.length - 1)) % bs.length];
      n.focus(); n.click();
    });
    segSet(seg, ($('button[aria-checked="true"]', seg) || $("button[data-value]", seg)).getAttribute("data-value"));
  }
  function segSet(seg, v) {
    $$("button[data-value]", seg).forEach(function (x) { var on = x.getAttribute("data-value") === v; x.setAttribute("aria-checked", on ? "true" : "false"); x.tabIndex = on ? 0 : -1; });
    segMove(seg);
  }

  function updateWords() {
    var v = parseNum($("#f-gross_salary").value);
    var w = $("#h-gross_salary");
    if (!v) { w.innerHTML = '<span class="muted">Type an amount, or pick one below</span>'; return; }
    var t = "₹" + esc(TS.lakhWords(v)) + " a year";
    if (calc.type === "professional_presumptive") t += ' <span class="cq-aside">· 50% is taxed as profit</span>';
    else t += ' <span class="cq-aside">· ≈ ' + esc(inr(v / 12)) + " a month</span>";
    w.innerHTML = t;
  }
  function updateBadges() {
    var n = 0, tot = 0;
    DEDS.forEach(function (f) { var v = parseNum($("#f-" + f[0]).value); if (v) { n++; tot += v; } });
    var b = $("#dedBadge");
    b.hidden = !n;
    if (n) b.textContent = n + " · " + shortL(tot);
    var ob = $("#optBadge");
    ob.hidden = calc.age === "below60";
    ob.textContent = calc.age === "60to80" ? "60–79" : calc.age === "above80" ? "80+" : "";
  }

  var autoCalc = TS.debounce(function () { if (parseNum($("#f-gross_salary").value)) runCalc(true); }, 280);

  function initCalc() {
    $("#calcFields").innerHTML = DEDS.map(dedHtml).join("");
    var main = $("#f-gross_salary");
    main.addEventListener("input", function () { liveFormat(main); updateWords(); markSal(); autoCalc(); });
    main.addEventListener("focus", function () { setTimeout(function () { try { main.select(); } catch (e) { /* ignore */ } }, 0); });
    $$("#calcFields input[inputmode]").forEach(function (inp) {
      inp.addEventListener("input", function () { liveFormat(inp); updateBadges(); autoCalc(); });
    });
    $("#calcFields").addEventListener("click", function (e) {
      var m = e.target.closest(".ded-max"); if (!m) return;
      e.preventDefault();
      var inp = $("input", m.parentNode); inp.value = inr(+m.getAttribute("data-max"), { noSymbol: true });
      inp.dispatchEvent(new Event("input"));
      TS.flashEl(inp.parentNode);
    });
    $("#salChips").innerHTML = SAL_CHIPS.map(function (v) { return '<button type="button" class="pill sm" data-sal="' + v + '">' + esc(shortL(v)) + "</button>"; }).join("");
    $("#salChips").addEventListener("click", function (e) {
      var b = e.target.closest("[data-sal]"); if (!b) return;
      main.value = inr(+b.getAttribute("data-sal"), { noSymbol: true }); main.dispatchEvent(new Event("input"));
    });
    segInit("#ageSeg", function (v) { calc.age = v; updateBadges(); autoCalc(); });
    segInit("#yearSeg", function (v) { calc.year = v; autoCalc(); });
    segInit("#typeSeg", function (v) { calc.type = v; setTypeLabel(); autoCalc(); });
    $("#calcParentsSenior").addEventListener("change", autoCalc);
    $$(".cq-more").forEach(function (d) { d.addEventListener("toggle", function () { if (d.open) $$(".seg", d).forEach(segMove); }); });
    $("#calcPresets").innerHTML = CALC_PRESETS.map(function (p, i) { return '<button type="button" class="pill sm" data-p="' + i + '">' + esc(p.label) + "</button>"; }).join("");
    $("#calcPresets").addEventListener("click", function (e) {
      var b = e.target.closest("[data-p]"); if (!b) return;
      fillForm(CALC_PRESETS[+b.getAttribute("data-p")].v);
      runCalc(false);
      if (window.innerWidth < 1000) $("#calcResults").scrollIntoView({ behavior: TS.reducedMotion() ? "auto" : "smooth", block: "start" });
    });
    $("#calcForm").addEventListener("submit", function (e) { e.preventDefault(); runCalc(false); });
    window.addEventListener("resize", TS.debounce(function () { $$("#view-calculator .seg").forEach(segMove); }, 100));
    updateWords(); markSal(); updateBadges();
  }

  function setTypeLabel() { $("#l-gross_salary").textContent = MAIN_LABEL[calc.type]; updateWords(); }

  function markSal() {
    var v = parseNum($("#f-gross_salary").value);
    $$("#salChips [data-sal]").forEach(function (b) { b.classList.toggle("on", +b.getAttribute("data-sal") === v); });
  }

  function fillForm(v) {
    $("#f-gross_salary").value = v.gross_salary ? inr(v.gross_salary, { noSymbol: true }) : "";
    var anyDed = false;
    DEDS.forEach(function (f) {
      var val = v[f[0]] || 0; if (val) anyDed = true;
      $("#f-" + f[0]).value = val ? inr(val, { noSymbol: true }) : "";
    });
    $("#dedBox").open = anyDed;
    calc.age = v.age || "below60"; segSet($("#ageSeg"), calc.age);
    if (calc.age !== "below60") $("#optBox").open = true;
    if (v.tax_year) { calc.year = v.tax_year; segSet($("#yearSeg"), calc.year); }
    var t = v.income_type || (v.salaried === false ? null : "salary");
    if (t && MAIN_LABEL[t]) { calc.type = t; segSet($("#typeSeg"), t); setTypeLabel(); }
    $("#calcParentsSenior").checked = !!v.parents_senior;
    updateWords(); markSal(); updateBadges();
  }

  function runCalc(auto) {
    var body = { gross_salary: parseNum($("#f-gross_salary").value) };
    DEDS.forEach(function (f) { body[f[0]] = parseNum($("#f-" + f[0]).value); });
    body.age = calc.age; body.tax_year = calc.year; body.salaried = calc.type === "salary";
    body.parents_senior = $("#calcParentsSenior").checked;
    if (!calc.noIncomeType) body.income_type = calc.type;
    var out = $("#calcResults");
    if (!body.gross_salary) {
      if (!auto) {
        var f = $(".cq-amount"); f.classList.remove("invalid"); void f.offsetWidth; f.classList.add("invalid");
        $("#f-gross_salary").focus();
      }
      return;
    }
    $(".cq-amount").classList.remove("invalid");
    var my = ++calc.seq;
    calc.ran = true;
    out.classList.add("loading");
    if (!out.querySelector(".verdict")) out.innerHTML = '<div class="panel verdict sk"><div class="skeleton sk-title"></div><div class="sk-lines"><span class="skeleton"></span><span class="skeleton short"></span></div><div class="skeleton sk-bars"></div></div>';
    var call = function (b) { return TS.api("/calculate", { body: b, timeout: 30000 }); };
    call(body)
      .catch(function (e) {
        // Very old backends reject the income_type field itself (a validation error): retry once without it.
        // A 422 with "escalate" is the presumptive-limit answer and must be shown, not retried.
        if (body.income_type && e && e.status === 422 && !(e.data && e.data.escalate) && /income_type/.test(e.message || "")) { calc.noIncomeType = true; delete body.income_type; return call(body); }
        throw e;
      })
      .then(function (d) { if (my === calc.seq) renderCalc(d); })
      .catch(function (e) {
        if (my !== calc.seq) return;
        if (e && e.data && e.data.escalate) { out.innerHTML = escalateHtml(e.data.detail || e.message); TS.reveal($$("#calcResults > *")); return; }
        out.innerHTML = '<div class="notice error-card"><span class="notice-illo">' + TS.illo("offline") + '</span><div><p class="notice-title">Calculation failed</p><p class="notice-detail">' + esc(e.message) + '</p><div class="notice-actions"><button type="button" class="btn btn-secondary btn-sm" id="calcRetry">' + icon("refresh") + "Try again</button></div></div></div>";
        $("#calcRetry").onclick = function () { runCalc(false); };
      })
      .then(function () { if (my === calc.seq) out.classList.remove("loading"); });
  }
  TS.calcDefault = function () { if (!calc.ran) runCalc(true); $$("#view-calculator .seg").forEach(segMove); };

  TS.showCalc = function (c) {
    TS.go("calculator");
    if (c.inputs) fillForm(c.inputs);
    calc.ran = true; calc.seq++;
    renderCalc(c);
    setTimeout(function () { $$("#view-calculator .seg").forEach(segMove); }, 30);
  };

  function escalateHtml(msg) {
    return '<div class="ca-card"><span class="ca-illo">' + TS.illo("ca") + '</span><div class="ca-main"><h3 class="ca-title">Above the presumptive limit: this needs a CA</h3><p class="ca-why">' + esc(msg) + '</p><div class="ca-next"><a class="btn btn-amber btn-sm" href="https://www.icai.org/" target="_blank" rel="noopener noreferrer">Find a CA on the ICAI website' + icon("arrowUpRight") + "</a></div></div></div>";
  }

  function tyLabel(ty) { return ty ? ((+String(ty).slice(0, 4) >= 2026 ? "Tax Year " : "FY ") + ty) : ""; }

  function renderCalc(d) {
    var out = $("#calcResults");
    var o = d.old || {}, n = d["new"] || {};
    var ot = Number(o.total) || 0, nt = Number(n.total) || 0;
    var better = d.better || (ot < nt ? "old" : nt < ot ? "new" : "same");
    var saving = d.saving != null ? Number(d.saving) : Math.abs(ot - nt);
    var bothZero = ot === 0 && nt === 0;
    var W = better === "new" ? "New" : "Old", winT = better === "new" ? nt : ot, loseT = better === "new" ? ot : nt;
    var card = $(".verdict:not(.sk)", out);
    var fresh = !card;
    if (fresh) {
      out.innerHTML =
        '<div class="panel verdict">' +
        '<p class="vc-eyebrow"></p>' +
        '<h2 class="vc-title"></h2>' +
        '<p class="vc-sub"></p>' +
        '<div class="vc-bars">' +
        '<div class="vb-row" data-k="old"><span class="vb-k">Old regime<span class="vb-tag">Lower</span></span><span class="vb-track"><span class="vb-fill"></span></span><span class="vb-v num" data-fmt="inr">₹0</span></div>' +
        '<div class="vb-row" data-k="new"><span class="vb-k">New regime<span class="vb-tag">Lower</span></span><span class="vb-track"><span class="vb-fill"></span></span><span class="vb-v num" data-fmt="inr">₹0</span></div>' +
        "</div>" +
        '<p class="vc-foot">' + icon("calc") + '<span>Exact code, not the AI</span><span class="vc-law"></span></p>' +
        "</div>" +
        '<details class="panel working-panel" id="calcWorking"><summary><span class="wk-ico" aria-hidden="true">' + icon("file") + '</span><span class="wk-t"><b>See the working</b><small>Slab by slab, deductions, rebate and cess</small></span>' + icon("chevDown", "chev") + '</summary><div class="wk-body"></div></details>';
      card = $(".verdict", out);
    }
    var vt = $(".vc-title", card), vs = $(".vc-sub", card);
    card.classList.toggle("zero", bothZero);
    $(".vc-eyebrow", card).textContent = [tyLabel(d.tax_year), d.income_type === "professional_presumptive" ? "Freelancer, presumptive" : "Salary"].filter(Boolean).join(" · ");
    $(".vc-law", card).textContent = d.law ? " · " + d.law : "";
    if (bothZero) {
      vt.innerHTML = "No tax in either regime";
      vs.textContent = "The rebate and standard deduction cover your income in both.";
    } else if (better === "same") {
      vt.innerHTML = 'Same tax either way: <span class="vc-amt num" data-fmt="inr"></span>';
      vs.textContent = "Pick whichever is simpler for you.";
    } else if (winT === 0) {
      vt.innerHTML = "No tax under the " + W.toLowerCase() + " regime";
      vs.innerHTML = 'You save <b class="num">' + esc(inr(saving)) + "</b> compared with the " + (better === "new" ? "old" : "new") + " regime.";
    } else {
      vt.innerHTML = W + ' regime saves you <span class="vc-amt num" data-fmt="inr"></span>';
      vs.innerHTML = "≈ " + esc(inr(saving / 12)) + " a month · you pay " + esc(inr(winT)) + " instead of " + esc(inr(loseT)) + ".";
    }
    var amt = $(".vc-amt", vt);
    if (amt) { amt._cv = card._saving || 0; TS.countUp(amt, better === "same" ? ot : saving, "inr"); }
    card._saving = better === "same" ? ot : saving;
    var max = Math.max(ot, nt, 1);
    [["old", ot], ["new", nt]].forEach(function (x) {
      var row = $('.vb-row[data-k="' + x[0] + '"]', card);
      row.classList.toggle("win", better === x[0] && !bothZero);
      var w = x[1] > 0 ? Math.max(2, (x[1] / max) * 100) : 0;
      var fill = $(".vb-fill", row);
      if (fresh && !TS.reducedMotion()) { fill.style.width = "0%"; requestAnimationFrame(function () { requestAnimationFrame(function () { fill.style.width = w.toFixed(1) + "%"; }); }); }
      else fill.style.width = w.toFixed(1) + "%";
      TS.countUp($(".vb-v", row), x[1], "inr");
    });
    if (fresh) TS.reveal([card, $("#calcWorking")], { step: 80 });
    else { card.classList.remove("bump"); void card.offsetWidth; card.classList.add("bump"); }
    $("#calcWorking .wk-body").innerHTML = workingHtml(d, o, n, better);
  }

  var DED_NAMES = { "80c": "Savings & investments (80C)", "80d": "Health insurance (80D)", "80d_parents": "Parents' health insurance", "80ccd1b": "Extra NPS 80CCD(1B)", home_loan_interest: "Home-loan interest", hra_exemption: "Rent (HRA)", other: "Other", employer_nps_80ccd2: "Employer NPS 80CCD(2)" };
  function workingHtml(d, o, n, better) {
    var html = '<div class="slab-vis">' + slabBar("Old regime", o, better === "old") + slabBar("New regime", n, better === "new") + "</div>";
    html += breakdownTable(o, n, better);
    if (d.notes && d.notes.length) html += '<ul class="notes">' + d.notes.map(function (x) { return "<li>" + icon("info") + "<span>" + esc(x) + "</span></li>"; }).join("") + "</ul>";
    return html;
  }

  // Taxable income poured into the slabs: each segment's width = income in that slab, darker = higher rate
  function slabBar(title, r, win) {
    var slabs = r.slabs || [], taxable = Number(r.taxable) || 0;
    if (!slabs.length || !taxable) return '<div class="sv-row"><div class="sv-head"><b>' + esc(title) + '</b><span class="num">' + esc(inr(r.total)) + "</span></div></div>";
    var segs = slabs.map(function (s) {
      var top = s.to == null ? taxable : Math.min(taxable, s.to);
      return { from: s.from, amt: Math.max(0, top - s.from), rate: s.rate || 0, tax: s.tax || 0, to: s.to };
    }).filter(function (x) { return x.amt > 0; });
    var maxRate = 30;
    return '<div class="sv-row' + (win ? " win" : "") + '"><div class="sv-head"><b>' + esc(title) + '</b><span class="muted">taxable ' + esc(inr(taxable)) + '</span><span class="num sv-tot">' + esc(inr(r.slab_tax)) + ' <small>before rebate & cess</small></span></div>' +
      '<div class="sv-bar">' + segs.map(function (x, i) {
        return '<span class="sv-seg" style="flex:' + x.amt + ";--r:" + (x.rate / maxRate).toFixed(2) + ";--i:" + i + '" title="' + esc(inr(x.from) + " – " + (x.to == null ? "above" : inr(x.to)) + " at " + x.rate + "%: " + inr(x.tax)) + '"><i>' + x.rate + "%</i></span>";
      }).join("") + "</div>" +
      '<div class="sv-legend">' + segs.map(function (x) { return '<span style="flex:' + x.amt + '">' + (x.tax ? esc(inr(x.tax)) : "₹0") + "</span>"; }).join("") + "</div></div>";
  }

  function breakdownTable(o, n, better) {
    var row = function (k, a, b, cls) { return '<tr class="' + (cls || "") + '"><th scope="row">' + k + '</th><td class="num">' + a + '</td><td class="num">' + b + "</td></tr>"; };
    var minus = function (v) { return v ? "− " + inr(v) : "—"; };
    var sub = "";
    var ob = o.deduction_breakdown || {}, nb = n.deduction_breakdown || {};
    Object.keys(DED_NAMES).forEach(function (k) {
      if (!ob[k] && !nb[k]) return;
      sub += row(esc(DED_NAMES[k]), ob[k] ? inr(ob[k]) : "—", nb[k] ? inr(nb[k]) : "not allowed", "sub");
    });
    return (
      '<div class="table-scroll"><table class="bd-table"><thead><tr><th scope="col"></th><th scope="col" class="num' + (better === "old" ? " win" : "") + '">Old</th><th scope="col" class="num' + (better === "new" ? " win" : "") + '">New</th></tr></thead><tbody>' +
      row(o.presumptive_income != null ? "Gross receipts" : "Gross income", inr(o.gross), inr(n.gross)) +
      (o.presumptive_income != null ? row("Taxed as profit (50%)", inr(o.presumptive_income), inr(n.presumptive_income)) : "") +
      row("Standard deduction", minus(o.std_deduction), minus(n.std_deduction)) +
      row("Deductions", minus(o.deductions), minus(n.deductions)) + sub +
      row("Taxable income", inr(o.taxable), inr(n.taxable), "strong") +
      row("Tax at slab rates", inr(o.slab_tax), inr(n.slab_tax)) +
      (o.rebate || n.rebate ? row("Rebate (87A / s.156)", minus(o.rebate), minus(n.rebate)) : "") +
      (o.surcharge || n.surcharge ? row("Surcharge", "+ " + inr(o.surcharge), "+ " + inr(n.surcharge)) : "") +
      row("Cess (4%)", "+ " + inr(o.cess), "+ " + inr(n.cess)) +
      "</tbody><tfoot>" + row("You pay", inr(o.total), inr(n.total), "total") + "</tfoot></table></div>"
    );
  }

  function svgEl(tag, attrs, text) {
    var e = document.createElementNS(SVGNS, tag);
    for (var k in attrs) if (attrs.hasOwnProperty(k)) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }

  /* ================================================================== */
  /* RESULTS (experiments)                                               */
  /* ================================================================== */
  var CAPTIONS = {
    B0: "Plain LLM. No documents, answers from memory",
    B1: "Look it up first with keyword search (BM25)",
    C1: "Meaning search (embeddings) instead of keywords",
    C2: "Both searches, rankings merged (RRF)",
    C3: "Add a reranker on the top 20, plus the safety gate",
    C4: "Add the date filter: only law in force for the period",
    C5: "Add Hinglish normalisation",
    C6: "Final: keep the hybrid order, reranker only as a confidence check",
  };
  var SHORT = { B0: "LLM only", B1: "keywords", C1: "meaning", C2: "hybrid", C3: "+ rerank", C4: "+ dates", C5: "+ Hinglish", C6: "final" };
  var CAT_NAMES = { income_tax: "Income tax", gst: "GST", time_trap: "Time trap", calculation: "Calculation", out_of_scope: "Out of scope", hinglish: "Hinglish" };
  // [key in results.json, column name, tooltip, group]. Older/alternative key spellings are mapped in ALIAS.
  var METRICS = [
    ["recall@5", "Recall@5", "Is a right passage in the top 5?", "ret"],
    ["mrr@10", "MRR@10", "How high does the first right passage rank?", "ret"],
    ["ndcg@5", "nDCG@5", "Ranking quality of the top 5", "ret"],
    ["refusal_accuracy", "Refusal acc.", "Refuses when it should, answers when it can", "guard"],
    ["oos_refusal_rate", "OOS refused", "Share of out-of-scope questions that were refused", "guard"],
    ["false_refusal_rate", "False refusals", "Share of answerable questions wrongly refused (lower is better)", "guard"],
    ["period_accuracy", "Period acc.", "Time-trap questions: top passage is from the right year", "ret"],
    ["calc_accuracy", "Calc acc.", "Calculation questions: the answer has the right numbers", "gen"],
    ["key_fact_accuracy", "Key-fact acc.", "Answer contains the must-have numbers/sections (needs a --generate run)", "gen"],
    ["citation_validity", "Citation validity", "Cited IDs exist and were retrieved (needs a --generate run)", "gen"],
    ["faithfulness", "Faithfulness", "Share of answer sentences that survive the citation check (needs a --generate run)", "gen"],
    ["fallback_rate", "Fallback rate", "How often the extractive fallback replaced the LLM answer (lower is better)", "gen"],
    ["latency_p50_ms", "Latency p50", "Median time per question (lower is better)", "time"],
    ["latency_p95_ms", "Latency p95", "95th-percentile time per question (lower is better)", "time"],
  ];
  var ALIAS = { recall_at_5: "recall@5", mrr: "mrr@10", mrr_at_10: "mrr@10", ndcg_at_5: "ndcg@5" };
  var LOWER_BETTER = /latency|_ms$|false_refusal|fallback/;
  var ALWAYS_SHOW = ["key_fact_accuracy", "citation_validity", "faithfulness"]; // generation metrics: "—" until generated
  var expLoaded = false;

  function loadExperiments() {
    if (expLoaded) return;
    expLoaded = true;
    TS.api("/experiments", { timeout: 30000 })
      .then(renderExperiments)
      .catch(function (e) {
        expLoaded = false;
        $("#expBody").innerHTML = '<div class="notice error-card">' + icon("alert", "notice-ico") + '<div><p class="notice-title">Couldn\'t load the results</p><p class="notice-detail">' + esc(e.message) + '</p><div class="notice-actions"><button type="button" class="btn btn-secondary btn-sm" id="expRetry">' + icon("refresh") + "Retry</button></div></div></div>";
        $("#expRetry").onclick = loadExperiments;
      });
  }

  function normMetrics(m) {
    var o = {};
    Object.keys(m || {}).forEach(function (k) { o[ALIAS[k] || k] = m[k]; });
    return o;
  }
  function mval(c, k) { var v = c && c.metrics ? c.metrics[k] : null; return v == null || v === "" || !isFinite(v) ? null : Number(v); }
  function fmtMetric(k, v) {
    if (v == null) return "—";
    if (/latency|_ms$/.test(k)) return TS.fmtMs(v);
    if (v > 1.0001) return String(+v.toFixed(2));
    return v.toFixed(2);
  }
  function prettyKey(k) {
    var m = METRICS.filter(function (x) { return x[0] === k; })[0];
    return m ? m[1] : k.replace(/_at_/g, "@").replace(/_/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  var PLAIN = { B0: "Plain AI, no search", B1: "Keyword search", C1: "Meaning search", C2: "Both, merged", C3: "+ Careful re-read", C4: "+ Date filter", C5: "+ Hinglish", C6: "Final, tuned" };
  var RATE = /recall|accuracy|rate|validity|faithfulness/; // shown as %
  function fmtShort(k, v) {
    if (v == null) return "—";
    if (/latency|_ms$/.test(k)) return TS.fmtMs(v);
    return RATE.test(k) ? Math.round(v * 100) + "%" : v.toFixed(2);
  }
  var res = { configs: [], metric: null };

  function renderExperiments(d) {
    d = d || {};
    var configs = (Array.isArray(d.configs) ? d.configs : Array.isArray(d) ? d : []).map(function (c) {
      var pc = {};
      Object.keys(c.per_category || {}).forEach(function (k) { var v = c.per_category[k]; pc[k] = v && typeof v === "object" ? normMetrics(v) : v; });
      return Object.assign({}, c, { metrics: normMetrics(c.metrics), per_category: pc });
    });
    // Answer-quality runs (with generation) may come separately: merge their metrics by config name
    var gen = Array.isArray(d.generation_configs) ? d.generation_configs : [];
    gen.forEach(function (g) {
      // The server may send just the names of the configs that ran with the LLM ("B0", "C6", ...)
      if (typeof g === "string") { configs.forEach(function (x) { if (x.name === g) x.generated = true; }); return; }
      if (!g || typeof g !== "object" || !g.name) return;
      var m = normMetrics(g.metrics || {});
      var c = configs.filter(function (x) { return x.name === g.name; })[0];
      if (c) { Object.keys(m).forEach(function (k) { if (c.metrics[k] == null) c.metrics[k] = m[k]; }); c.generated = c.generated || true; }
      else configs.push(Object.assign({}, g, { metrics: m, per_category: {}, generated: true, genOnly: true }));
    });
    var ORDER = ["B0", "B1", "C1", "C2", "C3", "C4", "C5", "C6"];
    configs.sort(function (x, y) { var a = ORDER.indexOf(x.name), b = ORDER.indexOf(y.name); return (a < 0 ? 99 : a) - (b < 0 ? 99 : b); });
    var generated = configs.some(function (c) { return c.generated; });
    var meta = [];
    var nq = configs.length && configs[0].metrics ? configs[0].metrics.n : null;
    if (d.split) meta.push("<span><b>" + esc(nq || d.dev_size || "") + "</b> " + esc(d.split) + " questions</span>");
    else if (d.dev_size != null) meta.push("<span><b>" + esc(d.dev_size) + "</b> dev questions</span>");
    if (d.test_size != null && d.split !== "test") meta.push("<span><b>" + esc(d.test_size) + "</b> held out for the test</span>");
    meta.push("<span>" + (generated ? "With answer generation" : "Retrieval run") + "</span>");
    if (d.generated_at) meta.push("<span>Run " + esc(TS.fmtDate(String(d.generated_at).slice(0, 10))) + "</span>");
    // In demo mode the real results recorded from the server are replayed (they carry generated_at)
    if (d.__sample || (TS.state.mock && !d.generated_at)) meta.push('<span class="sample-tag">Sample data</span>');
    else if (TS.state.mock) meta.push('<span class="sample-tag">Recorded from the live server</span>');
    $("#expMeta").innerHTML = meta.map(function (m) { return '<span class="meta-chip">' + m + "</span>"; }).join("");
    if (!configs.length) {
      $("#expBody").innerHTML = '<div class="res-empty">' + TS.illo("empty") + "<p>No experiment results yet.</p>" + (d.note ? '<p class="muted small">' + esc(d.note) + "</p>" : '<p class="muted small">Run <code>python -m experiments.run_experiments</code>.</p>') + "</div>";
      return;
    }
    res.configs = configs;
    var fin = configs.filter(function (c) { return c.name === "C6"; })[0] || configs[configs.length - 1];
    var firstRet = configs.filter(function (c) { return c.name !== "B0" && mval(c, "recall@5") != null; })[0];
    var b0 = configs.filter(function (c) { return c.name === "B0"; })[0];

    // ---- hero stats
    var heroes = [];
    var rc = mval(fin, "recall@5");
    if (rc != null) heroes.push({ k: "recall@5", v: rc, label: "Finds the right law", sub: "a correct passage in the top 5", delta: firstRet && firstRet !== fin ? [rc - mval(firstRet, "recall@5"), "vs " + (PLAIN[firstRet.name] || firstRet.name).toLowerCase()] : null });
    var pa = mval(fin, "period_accuracy");
    if (pa != null) heroes.push({ k: "period_accuracy", v: pa, label: "Uses the right year's law", sub: "on date-trap questions" });
    var ra = mval(fin, "refusal_accuracy");
    if (ra != null) heroes.push({ k: "refusal_accuracy", v: ra, label: "Knows when to say “ask a CA”", sub: mval(fin, "false_refusal_rate") != null ? "only " + Math.round(mval(fin, "false_refusal_rate") * 100) + "% wrongly refused" : "refuses when it should" });
    var kf = mval(fin, "key_fact_accuracy"), kb = b0 ? mval(b0, "key_fact_accuracy") : null;
    var ca = mval(fin, "calc_accuracy"), mr = mval(fin, "mrr@10");
    if (kf != null) heroes.push({ k: "key_fact_accuracy", v: kf, label: "Gets the key facts right", sub: kb != null ? "plain AI: " + Math.round(kb * 100) + "%" : "numbers & sections in the answer", vs: kb });
    else if (ca != null && ca >= 0.95) heroes.push({ k: "calc_accuracy", v: ca, label: "Calculations exactly right", sub: "done by code, not the AI" });
    else if (mr != null) heroes.push({ k: "mrr@10", v: mr, label: "Best passage ranks first", sub: "ranking quality (MRR@10)", delta: firstRet && firstRet !== fin && mval(firstRet, "mrr@10") != null ? [mr - mval(firstRet, "mrr@10"), "vs " + (PLAIN[firstRet.name] || firstRet.name).toLowerCase()] : null });
    else if (ca != null) heroes.push({ k: "calc_accuracy", v: ca, label: "Calculation questions right", sub: "intent + amounts read correctly" });

    var html = '<div class="kpis hero-kpis">' + heroes.slice(0, 4).map(function (h, i) {
      var pctMode = RATE.test(h.k);
      var spark = configs.map(function (c) { var v = mval(c, h.k); return '<i class="' + (c === fin ? "fin" : "") + '" style="--v:' + (v == null ? 0 : Math.max(0.04, v)).toFixed(3) + '" title="' + esc(c.name + ": " + fmtShort(h.k, v)) + '"></i>'; }).join("");
      var dl = h.delta && isFinite(h.delta[0]) ? '<span class="kpi-delta' + (h.delta[0] < 0 ? " neg" : "") + '">' + (h.delta[0] >= 0 ? "+" : "−") + (pctMode ? Math.abs(Math.round(h.delta[0] * 100)) + " pts " : Math.abs(h.delta[0]).toFixed(2) + " ") + esc(h.delta[1]) + "</span>" : "";
      return '<div class="kpi hero" style="--i:' + i + '"><span class="kpi-label">' + esc(h.label) + '</span><span class="kpi-v num">' +
        (pctMode ? '<span data-count="' + Math.round(h.v * 100) + '" data-fmt="int">' + Math.round(h.v * 100) + "</span><small>%</small>" : '<span data-count="' + h.v + '" data-fmt="dec2">' + h.v.toFixed(2) + "</span>") +
        '</span><span class="kpi-sub">' + esc(h.sub) + "</span>" + dl + '<span class="kpi-spark" aria-hidden="true">' + spark + "</span></div>";
    }).join("") + "</div>";

    // ---- ladder
    var ladderKeys = [["recall@5", "Finds right passage", "Recall@5"], ["mrr@10", "Ranks it first", "MRR@10"], ["ndcg@5", "Ranking quality", "nDCG@5"], ["period_accuracy", "Right year's law", "Period acc."], ["key_fact_accuracy", "Key facts right", "Key-fact acc."], ["refusal_accuracy", "Refuses correctly", "Refusal acc."]]
      .filter(function (m) { return configs.filter(function (c) { return mval(c, m[0]) != null; }).length >= 2; });
    res.metric = res.metric && ladderKeys.some(function (m) { return m[0] === res.metric; }) ? res.metric : ladderKeys.length ? ladderKeys[0][0] : null;
    if (ladderKeys.length) {
      html += '<section class="panel ladder-panel"><div class="panel-head"><div><h3>Each step, one bar</h3><p class="muted small">From the first search to the final system. Teal = what you use.</p></div>' +
        '<div class="seg seg-sm metric-seg" id="ladderSeg" role="radiogroup" aria-label="Metric"><span class="seg-ind" aria-hidden="true"></span>' +
        ladderKeys.map(function (m) { return '<button type="button" role="radio" data-value="' + esc(m[0]) + '" aria-checked="' + (m[0] === res.metric) + '" title="' + esc(m[2]) + '">' + esc(m[1]) + "</button>"; }).join("") +
        '</div></div><div class="ladder" id="ladder"></div></section>';
    }

    // ---- heat strip
    var cats = [];
    configs.forEach(function (c) { Object.keys(c.per_category || {}).forEach(function (k) { if (cats.indexOf(k) < 0) cats.push(k); }); });
    if (cats.length) html += '<section class="panel heat-panel"><div class="panel-head"><div><h3>By question type</h3><p class="muted small">Same metric as above. Darker = better.</p></div></div><div class="table-scroll" id="heatGrid"></div></section>';

    // ---- all numbers
    html += '<details class="panel all-numbers"><summary><span class="wk-ico" aria-hidden="true">' + icon("file") + '</span><span class="wk-t"><b>See all numbers</b><small>Every metric for every config</small></span>' + icon("chevDown", "chev") + "</summary>" + fullTable(configs, generated) + "</details>";

    $("#expBody").innerHTML = html;
    TS.reveal($$("#expBody .kpi, #expBody > section, #expBody > details"), { step: 60, cap: 400 });
    TS.animateNumbers($("#expBody .hero-kpis"));
    var seg = $("#ladderSeg");
    if (seg) {
      segInit("#ladderSeg", function (v) { res.metric = v; drawLadder(); drawHeat(); });
      setTimeout(function () { segMove(seg); }, 50);
    }
    drawLadder(); drawHeat();
  }

  function drawLadder() {
    var host = $("#ladder"); if (!host) return;
    var k = res.metric, configs = res.configs;
    var lowerBetter = LOWER_BETTER.test(k);
    var prev = null, rows = "";
    var fresh = !host.children.length;
    var vals = configs.map(function (c) { return mval(c, k); }).filter(function (v) { return v != null; });
    var max = RATE.test(k) ? 1 : Math.max.apply(null, vals.concat([1]));
    configs.forEach(function (c, i) {
      var v = mval(c, k);
      var fin = c.name === "C6";
      var delta = v != null && prev != null ? v - prev : null;
      var dl = delta == null ? "" : Math.abs(delta) < 0.005 ? '<span class="ld-delta same">±0</span>' : '<span class="ld-delta ' + ((delta > 0) !== lowerBetter ? "up" : "down") + '">' + (delta > 0 ? "+" : "−") + (RATE.test(k) ? Math.abs(Math.round(delta * 100)) : Math.abs(delta).toFixed(2)) + "</span>";
      rows += '<div class="ld-col' + (fin ? " fin" : "") + (v == null ? " na" : "") + '" style="--i:' + i + '">' +
        '<div class="ld-top"><span class="ld-v num">' + fmtShort(k, v) + "</span>" + dl + "</div>" +
        '<div class="ld-track"><span class="ld-bar" style="--h:' + (v == null ? 0 : Math.max(0.02, v / max)).toFixed(3) + '"></span></div>' +
        '<div class="ld-name"><b>' + esc(c.name) + "</b><span>" + esc(PLAIN[c.name] || c.description || "") + "</span></div></div>";
      if (v != null) prev = v;
    });
    if (fresh) { host.innerHTML = rows; host.classList.add("grow"); }
    else {
      // update in place so the bars glide to their new heights
      var tmp = document.createElement("div"); tmp.innerHTML = rows;
      $$(".ld-col", host).forEach(function (col, i) {
        var n = tmp.children[i]; if (!n) return;
        col.className = n.className;
        $(".ld-top", col).innerHTML = $(".ld-top", n).innerHTML;
        $(".ld-bar", col).style.setProperty("--h", $(".ld-bar", n).style.getPropertyValue("--h"));
      });
    }
  }

  function drawHeat() {
    var host = $("#heatGrid"); if (!host) return;
    var k = res.metric, configs = res.configs, cats = [];
    configs.forEach(function (c) { Object.keys(c.per_category || {}).forEach(function (x) { if (cats.indexOf(x) < 0) cats.push(x); }); });
    var cellVal = function (c, cat) { var v = (c.per_category || {})[cat]; v = v == null ? null : typeof v === "number" ? v : v[k]; return v == null || !isFinite(v) ? null : Number(v); };
    // hide question types this metric doesn't apply to (e.g. Recall@5 for out-of-scope questions): a row of dashes
    var shown = cats.filter(function (cat) { return configs.some(function (c) { return cellVal(c, cat) != null; }); });
    if (shown.length) cats = shown;
    var lowerBetter = LOWER_BETTER.test(k);
    host.innerHTML = '<div class="heat2" style="--cols:' + configs.length + '"><span></span>' +
      configs.map(function (c) { return '<span class="hh' + (c.name === "C6" ? " final" : "") + '">' + esc(c.name) + "</span>"; }).join("") +
      cats.map(function (cat, ri) {
        return '<span class="hr">' + esc(CAT_NAMES[cat] || cat.replace(/_/g, " ")) + "</span>" + configs.map(function (c, ci) {
          var v = cellVal(c, cat);
          if (v == null) return '<span class="hc na" title="Not measured">—</span>';
          var hv = Math.max(0, Math.min(1, lowerBetter ? 1 - v : v));
          return '<span class="hc' + (hv >= 0.62 ? " hi" : "") + (c.name === "C6" ? " fin" : "") + '" style="--h:' + hv.toFixed(3) + ";--d:" + (ri * 30 + ci * 15) + 'ms" title="' + esc(c.name + " · " + (CAT_NAMES[cat] || cat) + ": " + fmtShort(k, v)) + '">' + fmtShort(k, v) + "</span>";
        }).join("");
      }).join("") + "</div>";
  }

  function fullTable(configs, generated) {
    var keys = METRICS.map(function (m) { return m[0]; });
    configs.forEach(function (c) { Object.keys(c.metrics || {}).forEach(function (k) { if (k !== "n" && keys.indexOf(k) < 0 && typeof c.metrics[k] === "number") keys.push(k); }); });
    keys = keys.filter(function (k) { return ALWAYS_SHOW.indexOf(k) >= 0 || configs.some(function (c) { return c.metrics && k in c.metrics; }); });
    var best = {};
    keys.forEach(function (k) {
      var vals = configs.map(function (c) { return mval(c, k); }).filter(function (v) { return v != null; });
      if (vals.length) best[k] = LOWER_BETTER.test(k) ? Math.min.apply(null, vals) : Math.max.apply(null, vals);
    });
    return '<div class="table-scroll"><table class="exp-table"><thead><tr><th class="sticky" scope="col">Config</th>' +
      keys.map(function (k) { var m = METRICS.filter(function (x) { return x[0] === k; })[0]; return '<th class="num" scope="col" title="' + esc(m ? m[2] : k) + '">' + esc(prettyKey(k)) + "</th>"; }).join("") +
      "</tr></thead><tbody>" +
      configs.map(function (c) {
        return '<tr class="' + (c.name === "C6" ? "final" : "") + '"><th class="sticky cfg-cell" scope="row"><span class="cfg-tag' + (c.name === "C6" ? " final" : "") + '">' + esc(c.name) + '</span><span class="cfg-cap">' + esc(CAPTIONS[c.name] || c.description || "") + "</span></th>" +
          keys.map(function (k) {
            var v = mval(c, k);
            var isBest = v != null && best[k] === v;
            var naTip = v == null ? ' title="' + esc(c.name === "B0" && /recall|mrr|ndcg|period|refusal/.test(k) ? "B0 retrieves nothing, so there is nothing to score" : /key_fact|citation|faith|fallback/.test(k) && !c.generated ? "Not measured: this config was run without answer generation" : "Not applicable") + '"' : "";
            return '<td class="num' + (isBest ? " best" : "") + (v == null ? " na" : "") + '"' + naTip + ">" + fmtMetric(k, v) + "</td>";
          }).join("") + "</tr>";
      }).join("") +
      '</tbody></table></div><p class="table-foot">Hover a column name for what it measures. <b class="best-key">Teal</b> = best in column. — = not measured for that config' + (generated ? "" : " (answer-quality columns need a <code>--generate</code> run)") + ".</p>";
  }

  /* ================================================================== */
  /* HOW IT WORKS                                                        */
  /* ================================================================== */
  var NI = {
    q: '<path d="M20.5 11.5a8 8 0 0 1-11.9 7L4 19.8l1.3-4.3A8 8 0 1 1 20.5 11.5Z"/>',
    lang: '<path d="M4 5h8M8 3v2M6 5c0 4 2.5 7 6 8.5M10 5c-.5 3.5-3 6.5-6 8"/><path d="m13 21 4-9 4 9M14.5 18h5"/>',
    intent: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1" fill="currentColor"/>',
    date: '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M8 3v4M16 3v4M3.5 10h17M8 14h3"/>',
    search: '<circle cx="10.5" cy="10.5" r="6"/><path d="m15 15 5.5 5.5"/>',
    merge: '<path d="M6 4v5a6 6 0 0 0 6 6h0a6 6 0 0 0 6-6V4M12 15v5.5"/>',
    filter: '<path d="M4 5h16l-6 7.5V19l-4 1.5v-8z"/>',
    gate: '<path d="M12 3 4.5 6v5.5c0 4.5 3.2 8 7.5 9.5 4.3-1.5 7.5-5 7.5-9.5V6z"/><path d="m9 12 2 2 4-4"/>',
    write: '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
    check: '<path d="M14.5 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7.5z"/><path d="m9 14 2 2 4-4.5"/>',
  };
  // [icon, name, one line, tiny example, what the travelling question looks like after this step]
  var FLOW = [
    ["q", "Your question", "English or Hinglish, typed like you talk.", "“Naye regime mein standard deduction kitna hai?”", "Naye regime mein standard deduction kitna hai?"],
    ["lang", "Hinglish", "Hindi-English words become plain English.", "naye → new · mein → in · kitna → how much", "standard deduction in new regime, how much?"],
    ["intent", "Intent", "Is it a question, a calculation, or off-topic?", "question · 90% sure", "question"],
    ["date", "Date", "Which year's law applies? No date means today.", "Aug 2025 → before GST 2.0 · none → TY 2026-27", "Tax Year 2026-27"],
    ["search", "Search ×2", "Keyword search and meaning search, side by side.", "20 + 20 candidate passages", "40 passages"],
    ["merge", "Merge", "Passages both searches like rise to the top.", "two top-20 lists → one", "top 20"],
    ["filter", "Date filter", "Drops law that wasn't in force on that date.", "−7 passages from the old Act", "13 in force"],
    ["gate", "Safety gate", "Weak evidence or risky ask? It says “ask a CA”.", "passed: score +3.69 ≥ −5.83", "safe to answer"],
    ["write", "Calculator / Writer", "Code does the maths. The AI writes from 5 passages.", "₹75,000 from IT Act 2025 s.202", "draft answer"],
    ["check", "Fact-check", "Every sentence must cite a real passage, or it's cut.", "₹75,000 [IT-NEW-STDDED]", "✓ answer with sources"],
  ];
  var how = { loaded: false, cur: 0, timers: [], playing: false };

  function nodeIcon(k) { return '<svg viewBox="0 0 24 24" aria-hidden="true">' + NI[k] + "</svg>"; }

  function renderHow() {
    if (how.loaded) return;
    how.loaded = true;
    var html = "";
    html += '<section class="panel flow-panel">' +
      '<div class="flow-top"><div class="flow-q"><span class="flow-q-k">Sample question</span><span class="flow-q-t">' + esc(FLOW[0][4]) + '</span><span class="flow-state" id="flowQ" hidden></span></div>' +
      '<button type="button" class="btn btn-primary" id="howPlay"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4.5v15l12-7.5z"/></svg><span>Play</span></button></div>' +
      '<div class="flow" id="flow" role="list" style="--n:' + FLOW.length + '"><span class="flow-line" aria-hidden="true"><i class="flow-fill"></i></span><span class="flow-token" aria-hidden="true"></span>' +
      FLOW.map(function (f, i) {
        return '<button type="button" class="fnode" role="listitem" data-i="' + i + '" style="--i:' + i + '" aria-label="Step ' + (i + 1) + ": " + esc(f[1]) + '"><span class="fn-dot">' + nodeIcon(f[0]) + '</span><span class="fn-name">' + esc(f[1]) + '</span><span class="fn-more"><span>' + esc(f[2]) + '</span><code>' + esc(f[3]) + "</code></span></button>";
      }).join("") + "</div>" +
      '<div class="flow-card" id="flowCard" aria-live="polite"></div></section>';

    html += '<section class="how-sec"><h2 class="section-title">Why not just a chatbot?</h2><div class="why2">' +
      [["date", "Out of date", "Date filter"], ["check", "No receipts", "Every line cited"], ["write", "Guesses maths", "Exact calculator"], ["gate", "Over-confident", "Safety gate"]].map(function (w, i) {
        return '<div class="why2-card" style="--i:' + i + '"><span class="why2-ico">' + nodeIcon(w[0]) + '</span><span class="why2-bad">' + esc(w[1]) + '</span><span class="why2-arrow" aria-hidden="true">↓</span><span class="why2-fix">' + icon("check") + esc(w[2]) + "</span></div>";
      }).join("") + "</div></section>";

    html += '<section class="how-sec"><h2 class="section-title">The library, built once</h2><ol class="lib">' +
      [["check", "Official documents", "Acts, CBIC & CBDT, Budget"], ["merge", "Split into passages", "one rule each"], ["date", "Date-stamped", "valid from … to …"], ["search", "Two indexes", "keywords + meaning"]].map(function (l, i) {
        return '<li style="--i:' + i + '"><span class="lib-ico">' + nodeIcon(l[0]) + "</span><b>" + esc(l[1]) + "</b><small>" + esc(l[2]) + "</small></li>";
      }).join("") + "</ol></section>";

    html += '<section class="how-sec" id="kbCard"><h2 class="section-title">What is in the library <span class="live-tag">' + (TS.state.mock ? "recorded" : "live") + '</span></h2><div id="kbBody"><div class="kpis"><div class="skeleton kpi-sk"></div><div class="skeleton kpi-sk"></div><div class="skeleton kpi-sk"></div><div class="skeleton kpi-sk"></div></div></div></section>';
    $("#howBody").innerHTML = html;
    $("#howPlay").addEventListener("click", function () { if (how.playing) stopHow(); else playHow(); });
    $("#flow").addEventListener("click", function (e) {
      var n = e.target.closest(".fnode"); if (!n) return;
      stopHow(); setNode(+n.getAttribute("data-i"));
    });
    $("#flow").addEventListener("keydown", function (e) {
      if (["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].indexOf(e.key) < 0) return;
      e.preventDefault();
      var i = Math.max(0, Math.min(FLOW.length - 1, how.cur + (e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1)));
      stopHow(); setNode(i); var b = $('.fnode[data-i="' + i + '"]'); if (b) b.focus();
    });
    setNode(0, true);
    TS.reveal($$("#howBody > section"), { step: 80 });
    TS.api("/kb/stats", { timeout: 30000 }).then(renderKb).catch(function (e) {
      $("#kbBody").innerHTML = '<div class="notice error-card"><span class="notice-illo">' + TS.illo("offline") + '</span><div><p class="notice-title">Couldn\'t load the library stats</p><p class="notice-detail">' + esc(e.message) + "</p></div></div>";
    });
  }

  function setNode(i, quiet) {
    how.cur = i;
    var flow = $("#flow");
    flow.style.setProperty("--p", i / (FLOW.length - 1));
    $$(".fnode", flow).forEach(function (n, j) { n.classList.toggle("lit", j <= i); n.classList.toggle("now", j === i); n.setAttribute("aria-current", j === i ? "step" : "false"); });
    var f = FLOW[i];
    var card = $("#flowCard");
    card.innerHTML = '<span class="fc-ico">' + nodeIcon(f[0]) + '</span><div class="fc-main"><p class="fc-step">Step ' + (i + 1) + " of " + FLOW.length + '</p><h3>' + esc(f[1]) + "</h3><p>" + esc(f[2]) + '</p></div><code class="fc-ex">' + esc(f[3]) + "</code>";
    if (!quiet) { card.classList.remove("swap"); void card.offsetWidth; card.classList.add("swap"); }
    var q = $("#flowQ");
    q.hidden = i === 0;
    var st = "After " + f[1].toLowerCase() + ": " + f[4];
    if (i && q.textContent !== st) { q.textContent = st; q.classList.remove("swap"); void q.offsetWidth; q.classList.add("swap"); }
    q.classList.toggle("done", i === FLOW.length - 1);
  }

  function stopHow() {
    how.timers.forEach(clearTimeout); how.timers = [];
    how.playing = false;
    var b = $("#howPlay"); if (b) { b.classList.remove("on"); $("span", b).textContent = "Play"; }
    var fl = $("#flow"); if (fl) fl.classList.remove("playing");
  }
  function playHow() {
    stopHow();
    how.playing = true;
    var b = $("#howPlay"); b.classList.add("on"); $("span", b).textContent = "Stop";
    $("#flow").classList.add("playing");
    var step = TS.reducedMotion() ? 500 : 1100;
    setNode(0);
    FLOW.forEach(function (_, i) { if (i) how.timers.push(setTimeout(function () { setNode(i); }, i * step)); });
    how.timers.push(setTimeout(function () { stopHow(); TS.markLanded(); var last = $('.fnode[data-i="' + (FLOW.length - 1) + '"]'); if (last) { last.classList.remove("landed"); void last.offsetWidth; last.classList.add("landed"); } }, FLOW.length * step - step + 500));
  }

  function pickMap(d, names) {
    for (var i = 0; i < names.length; i++) {
      var v = d[names[i]];
      if (v && typeof v === "object" && !Array.isArray(v)) return v;
      if (Array.isArray(v) && v.length && typeof v[0] === "object") {
        var o = {}; v.forEach(function (x) { var k = x.name || x.law || x.topic || x.key; if (k != null) o[k] = x.count != null ? x.count : x.chunks != null ? x.chunks : x.n; }); return o;
      }
    }
    return null;
  }

  function renderKb(d) {
    d = d || {};
    var byLaw = pickMap(d, ["by_law", "per_law", "laws", "law", "chunks_per_law"]) || {};
    var byTopic = pickMap(d, ["by_topic", "per_topic", "topics", "topic", "chunks_per_topic"]) || {};
    var byType = pickMap(d, ["by_doc_type", "doc_types", "doc_type"]);
    var sources = d.sources || d.source_list || [];
    var total = d.total_chunks != null ? d.total_chunks : d.chunks != null && typeof d.chunks === "number" ? d.chunks : d.total != null ? d.total : Object.keys(byLaw).reduce(function (a, k) { return a + (Number(byLaw[k]) || 0); }, 0);
    var ver = d.verified && typeof d.verified === "object" ? d.verified : null;
    var verTot = ver ? Object.keys(ver).reduce(function (a, k) { return a + (Number(ver[k]) || 0); }, 0) : 0;
    var verPct = ver && ver.yes != null && verTot ? Math.round((ver.yes / verTot) * 100) : null;
    var partPct = ver && ver.partial != null && verTot ? Math.round((ver.partial / verTot) * 100) : 0;
    var LAW_FULL = { new_act: "Income-tax Act, 2025", old_act: "Income-tax Act, 1961", gst: "GST", mapping: "Old → new section map", general: "General guidance" };
    var LAW_COL = { gst: "#0F766E", new_act: "#14B8A6", old_act: "#94A3B8", general: "#5EEAD4", mapping: "#CBD5E1" };
    var lawKeys = Object.keys(byLaw).sort(function (a, b) { return byLaw[b] - byLaw[a]; });
    var lawSum = lawKeys.reduce(function (a, k) { return a + (Number(byLaw[k]) || 0); }, 0) || 1;

    var donut = "";
    if (verPct != null) {
      var C = 2 * Math.PI * 26;
      donut = '<svg class="donut" viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="26" class="d-bg"/>' +
        '<circle cx="32" cy="32" r="26" class="d-part" style="--len:' + ((verPct + partPct) / 100 * C).toFixed(1) + ";--c:" + C.toFixed(1) + '"/>' +
        '<circle cx="32" cy="32" r="26" class="d-yes" style="--len:' + (verPct / 100 * C).toFixed(1) + ";--c:" + C.toFixed(1) + '"/></svg>';
    }
    var tiles = [
      ['<span class="num" data-count="' + total + '" data-fmt="int">' + esc(total) + "</span>", "passages", "one rule each"],
      ['<span class="num" data-count="' + (Array.isArray(sources) ? sources.length : 0) + '" data-fmt="int">' + (Array.isArray(sources) ? sources.length : "—") + "</span>", "official sources", "PIB, CBIC, Income Tax Dept"],
      ['<span class="num" data-count="' + lawKeys.length + '" data-fmt="int">' + (lawKeys.length || "—") + "</span>", "kinds of law", "GST, both IT Acts, more"],
    ];
    var html = '<div class="kpis kb-kpis">' + tiles.map(function (t, i) { return '<div class="kpi" style="--i:' + i + '"><span class="kpi-v">' + t[0] + '</span><span class="kpi-label">' + esc(t[1]) + '</span><span class="kpi-sub">' + esc(t[2]) + "</span></div>"; }).join("") +
      (verPct != null ? '<div class="kpi kpi-donut"><div class="dn-wrap">' + donut + '<span class="dn-v num"><span data-count="' + verPct + '" data-fmt="int">' + verPct + "</span>%</span></div><span class=\"kpi-label\">checked against the source</span><span class=\"kpi-sub\">" + (partPct ? "+" + partPct + "% partly checked" : "") + "</span></div>" : "") + "</div>";
    html += '<div class="panel kb-law"><div class="panel-head"><div><h3>Passages per law</h3></div></div><div class="law-bar">' +
      lawKeys.map(function (k, i) { return '<span style="flex:' + byLaw[k] + ";background:" + (LAW_COL[k] || "#A1A1AA") + ";--i:" + i + '" title="' + esc((LAW_FULL[k] || k) + ": " + byLaw[k]) + '"></span>'; }).join("") + "</div>" +
      '<div class="law-legend">' + lawKeys.map(function (k) { return '<span><i style="background:' + (LAW_COL[k] || "#A1A1AA") + '"></i>' + esc(LAW_FULL[k] || TS.LAW_LABEL[k] || k) + ' <b class="num">' + esc(byLaw[k]) + '</b><small class="num">' + Math.round((byLaw[k] / lawSum) * 100) + "%</small></span>"; }).join("") + "</div>";
    if (byType) html += '<div class="type-row">' + Object.keys(byType).sort(function (a, b) { return byType[b] - byType[a]; }).map(function (k) { return '<span class="tag">' + esc(k) + " <b>" + esc(byType[k]) + "</b></span>"; }).join("") + "</div>";
    html += "</div>";
    if (Array.isArray(sources) && sources.length) {
      html += '<details class="panel all-numbers"><summary><span class="wk-ico" aria-hidden="true">' + icon("file") + '</span><span class="wk-t"><b>See all ' + sources.length + ' sources</b><small>' + Object.keys(byTopic).length + " topics · links to the official pages</small></span>" + icon("chevDown", "chev") + '</summary><div class="table-scroll"><table class="src-table"><thead><tr><th>Document</th><th>Publisher</th><th>Law</th><th class="num">Passages</th></tr></thead><tbody>' + sources.map(function (s) {
        if (typeof s === "string") return "<tr><td>" + esc(s) + "</td><td></td><td></td><td></td></tr>";
        var title = s.title || s.source_title || s.doc_id || "";
        var url = s.url || s.source_url;
        var law = s.law || "";
        return "<tr><td>" + (url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(title) + "</a>" : esc(title)) + '</td><td class="muted">' + esc(s.publisher || "") + '</td><td class="nowrap">' + esc(TS.LAW_LABEL[law] || law) + '</td><td class="num">' + esc(s.chunks != null ? s.chunks : s.count != null ? s.count : "") + "</td></tr>";
      }).join("") + "</tbody></table></div></details>";
    }
    $("#kbBody").innerHTML = html;
    TS.reveal($$("#kbBody .kpi, #kbBody > .panel"), { step: 60 });
    TS.animateNumbers($("#kbBody"));
  }

  /* ================================================================== */
  TS._renderExperiments = function (d) { expLoaded = true; renderExperiments(d); };

  TS.initViews = function () {
    initCompare();
    initCalc();
    TS.onView("experiments", loadExperiments);
    TS.onView("calculator", function () { TS.calcDefault(); });
    window.addEventListener("load", function () { $$(".seg").forEach(segMove); });
    TS.onView("how", renderHow);
  };
})();
