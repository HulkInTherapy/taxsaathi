/* TaxSaathi demo UI: core, API layer, header, router, Ask view, drawer and pipeline trace.
 * Plain ES2017, no framework, no build step. views.js adds the other tabs.
 */
(function () {
  "use strict";

  var TS = (window.TS = window.TS || {});

  /* ================================================================== */
  /* Utilities                                                           */
  /* ================================================================== */
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  function esc(v) {
    return String(v == null ? "" : v)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  // Indian digit grouping: 1200000 -> 12,00,000
  function inr(n, opts) {
    opts = opts || {};
    if (n == null || n === "" || !isFinite(Number(n))) return "—";
    var v = Math.round(Number(n));
    var neg = v < 0; v = Math.abs(v);
    var s = String(v);
    if (s.length > 3) {
      var last3 = s.slice(-3), rest = s.slice(0, -3);
      s = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + last3;
    }
    return (neg ? "−" : "") + (opts.noSymbol ? "" : "₹") + s;
  }
  function lakhWords(n) {
    n = Number(n) || 0;
    if (n >= 1e7) return trimNum(n / 1e7) + " crore";
    if (n >= 1e5) return trimNum(n / 1e5) + " lakh";
    if (n >= 1e3) return trimNum(n / 1e3) + " thousand";
    return String(Math.round(n));
  }
  function trimNum(x) { return (Math.round(x * 100) / 100).toString(); }

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  function fmtDate(iso) {
    if (!iso) return "";
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso));
    if (!m) return String(iso);
    return Number(m[3]) + " " + MONTHS[Number(m[2]) - 1] + " " + m[1];
  }
  function fmtMs(ms) {
    if (ms == null || !isFinite(ms)) return "";
    ms = Number(ms);
    if (ms < 1000) return Math.round(ms) + " ms";
    return (ms / 1000).toFixed(ms < 10000 ? 1 : 0) + " s";
  }
  function pct(x, digits) {
    if (x == null || !isFinite(x)) return "—";
    return (Number(x) * 100).toFixed(digits == null ? 0 : digits) + "%";
  }
  function debounce(fn, ms) {
    var t; return function () { var a = arguments, s = this; clearTimeout(t); t = setTimeout(function () { fn.apply(s, a); }, ms); };
  }

  // Tax year (Apr–Mar) that contains an ISO date: "2026-10-29" -> "Tax Year 2026-27"
  function yearOf(iso) {
    var m = /^(\d{4})-(\d{2})/.exec(String(iso || ""));
    if (!m) return "";
    var y = +m[2] >= 4 ? +m[1] : +m[1] - 1;
    return (y >= 2026 ? "Tax Year " : "FY ") + y + "-" + String(y + 1).slice(-2);
  }
  function periodLabel(d, asYear) {
    if (!d || !d.start) return "current law";
    var s = String(d.start), e = String(d.end || d.start);
    var sm = /^(\d{4})-(\d{2})-(\d{2})/.exec(s), em = /^(\d{4})-(\d{2})-(\d{2})/.exec(e);
    if (!sm || !em) return s + (e && e !== s ? " → " + e : "");
    // "today" (assumed current law) reads better as the tax year it falls in
    if (asYear && s === e) return yearOf(s) + ", as of " + fmtDate(s);
    var sy = +sm[1], ey = +em[1];
    if (sm[2] === "04" && sm[3] === "01" && em[2] === "03" && em[3] === "31" && ey === sy + 1) {
      var yy = String(ey).slice(-2);
      return (sy >= 2026 ? "Tax Year " : "FY ") + sy + "-" + yy;
    }
    if (s === e) return fmtDate(s);
    if (sm[1] === em[1] && sm[2] === em[2] && sm[3] === "01") return MONTHS_LONG[+sm[2] - 1] + " " + sm[1];
    return fmtDate(s) + " – " + fmtDate(e);
  }

  var LAW_LABEL = { new_act: "IT Act 2025", old_act: "IT Act 1961", gst: "GST", mapping: "Section map", general: "General" };
  function inferLaw(c) {
    if (c.law && LAW_LABEL[c.law]) return c.law;
    var id = String(c.id || "").toUpperCase(), st = String(c.source_title || "");
    if (/^GST/.test(id) || /GST|CGST|IGST/i.test(st)) return "gst";
    if (/^MAP/.test(id) || /mapping/i.test(st)) return "mapping";
    if (/^IT61|^IT-1961|1961/.test(id) || /1961/.test(st)) return "old_act";
    if (/^IT25|^IT-|2025/.test(id) || /2025/.test(st)) return "new_act";
    return "general";
  }

  function toast(msg, kind) {
    var t = $("#toast");
    if (!t) return;
    t.innerHTML = icon(kind === "warn" ? "info" : "check") + "<span>" + esc(msg) + "</span>";
    t.className = "toast" + (kind ? " toast-" + kind : "");
    t.hidden = false;
    requestAnimationFrame(function () { t.classList.add("show"); });
    clearTimeout(toast._t);
    toast._t = setTimeout(function () {
      t.classList.remove("show");
      setTimeout(function () { t.hidden = true; }, 250);
    }, 2600);
  }


  /* ================================================================== */
  /* Icons: one small Lucide-style line set (24px grid, 1.5px stroke)    */
  /* ================================================================== */
  var ICONS = {
    arrowUp: '<path d="M12 19V5M5.5 11.5 12 5l6.5 6.5"/>',
    arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    arrowUpRight: '<path d="M7 17 17 7M8 7h9v9"/>',
    copy: '<rect x="9" y="9" width="12" height="12" rx="2.5"/><path d="M5 15H4.5A1.5 1.5 0 0 1 3 13.5v-9A1.5 1.5 0 0 1 4.5 3h9A1.5 1.5 0 0 1 15 4.5V5"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    thumbUp: '<path d="M7 10v11"/><path d="M15 5.9 14 10h5.8a2 2 0 0 1 1.9 2.6l-2.3 8a2 2 0 0 1-1.9 1.4H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.8a2 2 0 0 0 1.8-1.1L12 2a3.1 3.1 0 0 1 3 3.9Z"/>',
    thumbDown: '<path d="M17 14V3"/><path d="M9 18.1 10 14H4.2a2 2 0 0 1-1.9-2.6l2.3-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.8a2 2 0 0 0-1.8 1.1L12 22a3.1 3.1 0 0 1-3-3.9Z"/>',
    route: '<circle cx="6" cy="19" r="2.5"/><path d="M8.5 19H17a3.5 3.5 0 0 0 0-7H7a3.5 3.5 0 0 1 0-7h8.5"/><circle cx="18" cy="5" r="2.5"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    external: '<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    calc: '<rect x="4" y="2" width="16" height="20" rx="2.5"/><path d="M8 6.5h8M8 11h.01M12 11h.01M16 11h.01M8 14.5h.01M12 14.5h.01M16 14.5h.01M8 18h.01M12 18h.01M16 18h.01"/>',
    briefcase: '<rect x="2.5" y="7" width="19" height="13.5" rx="2.5"/><path d="M16 20.5V5.5A2 2 0 0 0 14 3.5h-4a2 2 0 0 0-2 2v15"/>',
    calendar: '<rect x="3" y="4.5" width="18" height="17" rx="2.5"/><path d="M16 2.5v4M8 2.5v4M3 10h18"/>',
    clock: '<circle cx="12" cy="12" r="9.5"/><path d="M12 7v5l3 2"/>',
    corner: '<path d="M15 10l5 5-5 5"/><path d="M4 4v7a4 4 0 0 0 4 4h12"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    refresh: '<path d="M3 12a9 9 0 0 1 15.4-6.4L21 8M21 3v5h-5M21 12a9 9 0 0 1-15.4 6.4L3 16M8 16H3v5"/>',
    chevDown: '<path d="m6 9 6 6 6-6"/>',
    chevRight: '<path d="m9 6 6 6-6 6"/>',
    info: '<circle cx="12" cy="12" r="9.5"/><path d="M12 16v-4.5M12 8h.01"/>',
    alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>',
    file: '<path d="M14.5 2.5H6.5a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-12z"/><path d="M14 2.5v5h5.5M9 13h6M9 17h6"/>',
    expand: '<path d="m7 15 5 5 5-5M7 9l5-5 5 5"/>',
    collapse: '<path d="m7 20 5-5 5 5M7 4l5 5 5-5"/>',
    play: '<path d="M7 4.5v15l12-7.5z"/>',
  };
  function icon(name, cls) {
    return '<svg class="ico' + (cls ? " " + cls : "") + '" viewBox="0 0 24 24" aria-hidden="true">' + (ICONS[name] || "") + "</svg>";
  }
  TS.icon = icon;

  /* ================================================================== */
  /* Motion helpers: count-up, staggered reveal, brand-mark states       */
  /* ================================================================== */
  function reducedMotion() { return !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches); }
  TS.reducedMotion = reducedMotion;
  var FMT = {
    inr: function (v) { return inr(v); },
    int: function (v) { return String(Math.round(v)); },
    pct: function (v) { return String(Math.round(v)); },
    dec2: function (v) { return v.toFixed(2); },
    grp: function (v) { return inr(v, { noSymbol: true }); },
  };
  // Count a number up from its previous value (or 0). el: data-count="1234" data-fmt="inr"
  function countUp(el, to, fmt, ms) {
    var f = FMT[fmt || el.getAttribute("data-fmt") || "int"] || FMT.int;
    to = Number(to); if (!isFinite(to)) return;
    var from = el._cv != null ? el._cv : 0;
    el._cv = to;
    if (reducedMotion() || from === to) { el.textContent = f(to); return; }
    var t0 = performance.now(), dur = ms || 700;
    cancelAnimationFrame(el._raf);
    var step = function (now) {
      var k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      el.textContent = f(from + (to - from) * e);
      if (k < 1) el._raf = requestAnimationFrame(step);
    };
    el._raf = requestAnimationFrame(step);
  }
  function animateNumbers(root) {
    $$("[data-count]", root).forEach(function (el, i) {
      var to = Number(el.getAttribute("data-count"));
      if (!el._cv && !reducedMotion()) el.textContent = (FMT[el.getAttribute("data-fmt") || "int"] || FMT.int)(0);
      setTimeout(function () { countUp(el, to); }, i * 60);
    });
  }
  TS.countUp = countUp; TS.animateNumbers = animateNumbers;

  // Stagger children in, quickly (whole sequence stays under ~600 ms)
  function reveal(units, opts) {
    opts = opts || {};
    var step = opts.step || 35, cap = opts.cap || 300;
    units.forEach(function (el, i) {
      el.style.setProperty("--d", Math.min(cap, (opts.delay || 0) + i * step) + "ms");
      el.classList.remove("rv"); void el.offsetWidth; el.classList.add("rv");
    });
  }
  TS.reveal = reveal;

  function markLanded() {
    $$(".nav .mark").forEach(function (m) { m.classList.remove("landed"); void m.getBoundingClientRect(); m.classList.add("landed"); setTimeout(function () { m.classList.remove("landed"); }, 700); });
  }
  TS.markLanded = markLanded;
  var MARK_SVG = '<svg class="mark" viewBox="0 0 32 32" aria-hidden="true"><rect class="mark-tile" width="32" height="32" rx="9"/><path class="mark-body" d="M10.5 7H19l5 5v8.5a2.5 2.5 0 0 1-2.5 2.5H14l-4 3.4V23a2.5 2.5 0 0 1-2-2.45V9.5A2.5 2.5 0 0 1 10.5 7Z"/><path class="mark-fold" d="M19 7v3.6a1.4 1.4 0 0 0 1.4 1.4H24Z"/><path class="mark-check" pathLength="1" d="m11.9 15.5 2.8 2.8 5-5.3"/></svg>';
  TS.markSvg = function (cls) { return MARK_SVG.replace('class="mark"', 'class="mark' + (cls ? " " + cls : "") + '"'); };

  /* Tiny spot illustrations, same line language as the mark */
  var ILLOS = {
    ca: '<svg class="illo" viewBox="0 0 96 80" aria-hidden="true"><rect x="18" y="30" width="60" height="40" rx="9" class="il-fill-amber"/><path d="M38 30v-6a5 5 0 0 1 5-5h10a5 5 0 0 1 5 5v6" class="il-line"/><rect x="18" y="30" width="60" height="40" rx="9" class="il-line"/><path d="M18 46h60" class="il-line"/><rect x="43" y="41" width="10" height="10" rx="3" class="il-solid-amber"/><circle cx="76" cy="18" r="11" class="il-bubble"/><path d="m71.5 18 3 3 6-6.5" class="il-tick"/></svg>',
    offline: '<svg class="illo" viewBox="0 0 96 80" aria-hidden="true"><path d="M30 58h38a14 14 0 0 0 1-28 20 20 0 0 0-38-3A15.5 15.5 0 0 0 30 58Z" class="il-fill"/><path d="M30 58h38a14 14 0 0 0 1-28 20 20 0 0 0-38-3A15.5 15.5 0 0 0 30 58Z" class="il-line"/><path d="M22 66 74 18" class="il-line il-strong"/></svg>',
    compare: '<svg class="illo" viewBox="0 0 120 80" aria-hidden="true"><rect x="8" y="14" width="46" height="34" rx="10" class="il-fill"/><rect x="8" y="14" width="46" height="34" rx="10" class="il-line"/><path d="M18 48l-4 10 12-10" class="il-line"/><text x="31" y="37" text-anchor="middle" class="il-q">?</text><rect x="66" y="26" width="46" height="34" rx="10" class="il-bubble"/><path d="M102 60l4 10-12-10" class="il-bubble"/><path d="m80 43 5 5 10-11" class="il-tick"/></svg>',
    empty: '<svg class="illo" viewBox="0 0 96 80" aria-hidden="true"><rect x="22" y="12" width="44" height="56" rx="8" class="il-fill"/><rect x="22" y="12" width="44" height="56" rx="8" class="il-line"/><path d="M32 28h24M32 38h24M32 48h14" class="il-line"/><circle cx="66" cy="56" r="12" class="il-bubble"/><path d="m61 56 3.5 3.5 6.5-7" class="il-tick"/></svg>',
  };
  TS.illo = function (k) { return ILLOS[k] || ""; };
  /* ================================================================== */
  /* API layer with mock fallback                                         */
  /* ================================================================== */
  var params = new URLSearchParams(location.search);
  var state = {
    mock: params.get("mock") === "1" || location.protocol === "file:",
    mockReason: params.get("mock") === "1" ? "param" : location.protocol === "file:" ? "file" : null,
    health: null,
    partial: {},
  };
  TS.state = state;

  function setMock(reason) {
    if (!window.TaxMock) return;
    var was = state.mock;
    state.mock = true;
    state.mockReason = state.mockReason || reason;
    renderBanner();
    if (!was) { refreshHealth(); toast("Server not reachable, so switched to demo mode", "warn"); }
  }

  function api(path, opts) {
    opts = opts || {};
    var method = opts.method || (opts.body ? "POST" : "GET");
    var timeout = opts.timeout || 120000;
    // Wait for the first /health probe so we know whether to use mock mode
    if (path !== "/health" && state.probe && !opts._afterProbe) {
      var o2 = Object.assign({}, opts, { _afterProbe: true });
      return state.probe.then(function () { return api(path, o2); });
    }
    if (state.mock) {
      if (!window.TaxMock) return Promise.reject(new Error("Mock data (mock.js) failed to load."));
      return window.TaxMock.handle(path, opts.body);
    }
    var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, timeout) : null;
    return fetch(path, {
      method: method,
      headers: opts.body ? { "Content-Type": "application/json", Accept: "application/json" } : { Accept: "application/json" },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      signal: ctrl ? ctrl.signal : undefined,
    }).then(
      function (res) {
        clearTimeout(timer);
        if (res.status === 404 && path === "/health" && window.TaxMock && !opts.noMockFallback) {
          // Something is serving the files, but it is not the TaxSaathi API
          setMock("noapi");
          return window.TaxMock.handle(path, opts.body);
        }
        if (res.status === 404 && window.TaxMock && !opts.noMockFallback) {
          state.partial[path] = true;
          renderBanner();
          return window.TaxMock.handle(path, opts.body).then(function (d) { if (d && typeof d === "object") d.__sample = true; return d; });
        }
        return res.text().then(function (text) {
          var data;
          try { data = text ? JSON.parse(text) : {}; } catch (e) { data = { detail: text.slice(0, 300) }; }
          if (!res.ok) {
            var d = data && data.detail;
            var msg = typeof d === "string" ? d : d ? JSON.stringify(d) : (data && data.error) || "HTTP " + res.status;
            var err = new Error(msg); err.status = res.status; err.data = data; throw err;
          }
          return data;
        });
      },
      function (err) {
        clearTimeout(timer);
        if (err && err.name === "AbortError") {
          // A slow answer is not a dead backend: never silently swap in sample data on a timeout.
          var te = new Error("The server took longer than " + Math.round(timeout / 1000) + " s to respond. It may be busy; please try again.");
          te.timeout = true; throw te;
        }
        // Only the first /health probe may switch the whole UI to mock mode. Once we know the live
        // backend is there, a failed request is shown as an error instead of fake data.
        if (path === "/health" && !state.live && window.TaxMock && !opts.noMockFallback) { setMock("unreachable"); return window.TaxMock.handle(path, opts.body); }
        throw new Error("Couldn't reach the TaxSaathi server (" + ((err && err.message) || "network error") + ").");
      }
    );
  }
  TS.api = api;


  /* ================================================================== */
  /* Header: health + mode banner                                          */
  /* ================================================================== */
  function refreshHealth() {
    var h = $("#health");
    if (!h) return Promise.resolve();
    return api("/health", { timeout: 20000 })
      .then(function (d) {
        state.health = d;
        if (!state.mock) state.live = true;
        var ok = d && (d.status === "ok" || d.status === "healthy");
        h.className = "health " + (state.mock ? "is-mock" : ok ? "is-ok" : "is-warn");
        $(".health-text", h).textContent = state.mock ? "Demo" : ok ? "Live" : "Warming up";
        h.title = state.mock ? "Offline demo mode: answers come from saved samples" : "Live server · " + (d.llm || "LLM") + (d.chunks != null ? " · " + d.chunks + " passages" : "");
      })
      .catch(function (e) {
        // e.g. /health timed out because the server is busy: stay in live mode, just say so
        h.className = "health " + (e && e.timeout ? "is-warn" : "is-down");
        $(".health-text", h).textContent = e && e.timeout ? "Busy" : "Offline";
        h.title = String(e && e.message);
      });
  }

  function renderBanner() {
    var b = $("#modeBanner");
    if (!b) return;
    var partial = Object.keys(state.partial);
    if (!state.mock && !partial.length) { b.hidden = true; document.body.classList.remove("has-banner"); return; }
    var msg;
    if (state.mock) {
      msg =
        state.mockReason === "param" || state.mockReason === "file"
          ? "<strong>Demo mode</strong><span class=\"mb-long\"> · answers come from saved samples, so this works without internet.</span>"
          : "<strong>Demo mode</strong><span class=\"mb-long\"> · the live server isn't reachable, so saved sample answers are shown.</span>";
    } else {
      msg = "<strong>Partly sample data</strong> · the server has no " + partial.map(function (p) { return "<code>" + esc(p) + "</code>"; }).join(", ") + " endpoint yet, so sample data is shown there.";
    }
    var retry = state.mock && state.mockReason !== "file" ? (state.mockReason === "param" ? '<a class="text-btn" href="' + esc(location.pathname) + '">Use live server</a>' : '<button type="button" class="text-btn" id="retryLive">Try live server again</button>') : "";
    b.innerHTML = '<div class="mode-inner"><span class="mode-dot" aria-hidden="true"></span><span class="mode-msg">' + msg + "</span>" + retry + '<button type="button" class="icon-btn xs mode-close" aria-label="Dismiss">' + icon("x") + "</button></div>";
    b.hidden = false;
    document.body.classList.add("has-banner");
    $(".mode-close", b).onclick = function () { b.hidden = true; document.body.classList.remove("has-banner"); };
    var r = $("#retryLive", b);
    if (r) r.onclick = function () {
      state.mock = false; state.mockReason = null;
      api("/health", { timeout: 20000, noMockFallback: true })
        .then(function () { state.live = true; renderBanner(); refreshHealth(); toast("Connected to the live server", "ok"); })
        .catch(function () { state.mock = true; state.mockReason = "unreachable"; renderBanner(); toast("Still unreachable, so staying in demo mode", "warn"); });
    };
  }

  /* ================================================================== */
  /* Router                                                              */
  /* ================================================================== */
  var VIEWS = ["ask", "compare", "calculator", "experiments", "how"];
  var viewHooks = {};
  TS.onView = function (name, fn) { viewHooks[name] = fn; };
  function showView(name) {
    if (VIEWS.indexOf(name) < 0) name = "ask";
    VIEWS.forEach(function (v) {
      var sec = $("#view-" + v), tab = $("#tab-" + v);
      var on = v === name;
      if (sec) sec.hidden = !on;
      if (tab) { tab.setAttribute("aria-selected", on ? "true" : "false"); tab.tabIndex = on ? 0 : -1; }
    });
    var prev = document.body.getAttribute("data-view");
    document.body.setAttribute("data-view", name);
    moveIndicator();
    setTimeout(moveIndicator, 340); // after mid-width labels finish expanding
    if (prev && prev !== name) window.scrollTo({ top: 0 });
    if (name !== "ask" && TS.closeDrawer) TS.closeDrawer(true);
    if (viewHooks[name]) { try { viewHooks[name](); } catch (e) { console.error(e); } }
  }
  TS.go = function (name) {
    if (location.hash !== "#" + name) location.hash = name; else showView(name);
  };
  // The white "glass bead" that glides to the active tab
  function moveIndicator() {
    var ind = $(".tab-ind"), t = $('.tab[aria-selected="true"]');
    if (!ind || !t || !t.offsetWidth) return;
    ind.style.setProperty("--x", t.offsetLeft + "px");
    ind.style.setProperty("--w", t.offsetWidth + "px");
    if (!ind.classList.contains("ready")) requestAnimationFrame(function () { ind.classList.add("ready"); });
  }
  TS.moveIndicator = moveIndicator;

  function initRouter() {
    $$(".tab").forEach(function (t) {
      t.addEventListener("click", function () { TS.go(t.getAttribute("data-view")); });
      t.addEventListener("keydown", function (e) {
        var i = VIEWS.indexOf(t.getAttribute("data-view")), n = null;
        if (e.key === "ArrowRight" || e.key === "ArrowDown") n = VIEWS[(i + 1) % VIEWS.length];
        else if (e.key === "ArrowLeft" || e.key === "ArrowUp") n = VIEWS[(i + VIEWS.length - 1) % VIEWS.length];
        else if (e.key === "Home") n = VIEWS[0];
        else if (e.key === "End") n = VIEWS[VIEWS.length - 1];
        if (!n) return;
        e.preventDefault();
        TS.go(n); var nt = $("#tab-" + n); if (nt) nt.focus();
      });
    });
    window.addEventListener("hashchange", function () { showView(location.hash.slice(1)); });
    showView(location.hash.slice(1) || "ask");
    window.addEventListener("resize", debounce(moveIndicator, 80));
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(moveIndicator);
    // Compact header once the page scrolls
    var nav = $("#nav"), ticking = false;
    window.addEventListener("scroll", function () {
      if (ticking) return; ticking = true;
      requestAnimationFrame(function () {
        ticking = false;
        var c = window.scrollY > 24;
        if (c !== nav.classList.contains("compact")) { nav.classList.toggle("compact", c); setTimeout(moveIndicator, 280); }
      });
    }, { passive: true });
    // "/" or Cmd/Ctrl+K: jump to the question box
    document.addEventListener("keydown", function (e) {
      var tag = (e.target && e.target.tagName) || "";
      var typing = /INPUT|TEXTAREA|SELECT/.test(tag) || (e.target && e.target.isContentEditable);
      if ((e.key === "/" && !typing && !e.metaKey && !e.ctrlKey) || ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K"))) {
        e.preventDefault();
        if (document.body.getAttribute("data-view") !== "ask") TS.go("ask");
        setTimeout(function () { var i = $("#askInput"); if (i) i.focus(); }, 30);
      }
    });
    var hm = $(".hero-mark .mark");
    if (hm && !reducedMotion()) hm.classList.add("intro");
  }

  /* ================================================================== */
  /* Pipeline knowledge (plain-English)                                  */
  /* ================================================================== */
  var CONFIGS = [
    { name: "B0", short: "LLM only", desc: "Plain LLM, no retrieval. It answers from memory." },
    { name: "B1", short: "BM25", desc: "Keyword search (BM25) top-5 → LLM" },
    { name: "C1", short: "Embeddings", desc: "Meaning search (embeddings) top-5 → LLM" },
    { name: "C2", short: "Hybrid", desc: "Keyword + meaning search, merged with RRF" },
    { name: "C3", short: "+ Rerank", desc: "Hybrid top-20 → reranker re-reads → top-5, plus safety gate" },
    { name: "C4", short: "+ Dates", desc: "C3 + date filter: only law in force for your period" },
    { name: "C5", short: "+ Hinglish", desc: "C4 + Hinglish normalisation (reranker decides the order)" },
    { name: "C6", short: "Final", desc: "Final system: C5, but keep the hybrid order; the reranker is only the safety check" },
  ];
  TS.CONFIGS = CONFIGS;
  var CONFIG_STEPS = {
    B0: ["pii", "generate"],
    B1: ["pii", "intent", "period", "entities", "bm25", "generate", "citation_check"],
    C1: ["pii", "intent", "period", "entities", "dense", "generate", "citation_check"],
    C2: ["pii", "intent", "period", "entities", "bm25", "dense", "fusion", "generate", "citation_check"],
    C3: ["pii", "intent", "period", "entities", "bm25", "dense", "fusion", "rerank", "gate", "generate", "citation_check"],
    C4: ["pii", "intent", "period", "entities", "bm25", "dense", "fusion", "date_filter", "rerank", "gate", "generate", "citation_check"],
    C5: ["pii", "hinglish", "intent", "period", "entities", "bm25", "dense", "fusion", "date_filter", "rerank", "gate", "generate", "citation_check"],
    C6: ["pii", "hinglish", "intent", "period", "entities", "bm25", "dense", "fusion", "date_filter", "rerank", "gate", "generate", "citation_check"],
  };
  TS.CONFIG_STEPS = CONFIG_STEPS;

  var STEP = {
    pii: { g: "understand", name: "Privacy scrub", why: "Masks PAN, Aadhaar and phone numbers before anything is logged.", wait: "Masking personal details…" },
    hinglish: { g: "understand", name: "Hinglish fix", why: "Rewrites Hindi-English mix into English so it matches the official documents.", wait: "Translating Hinglish words…" },
    intent: { g: "understand", name: "Intent", why: "A small classifier (TF-IDF + logistic regression) decides: question, calculation or out of scope.", wait: "Working out what you want…" },
    period: { g: "understand", name: "Time period", why: "Tax law changes every Budget, so we find which year's rules apply.", wait: "Looking for dates and tax years…" },
    entities: { g: "understand", name: "Sections & amounts", why: "Spots section numbers (like 80C) and ₹ amounts, and maps old sections to the new Act.", wait: "Spotting sections and amounts…" },
    bm25: { g: "retrieve", name: "Keyword search", why: "BM25: like Ctrl+F, but it knows which words are rare and important.", wait: "Keyword search (BM25)…" },
    dense: { g: "retrieve", name: "Meaning search", why: "Embeddings find 'pay less tax' even when the document says 'deduction'.", wait: "Meaning search (embeddings)…" },
    fusion: { g: "retrieve", name: "Merge rankings", why: "RRF combines the two top lists, like merging two judges' rankings.", wait: "Merging both rankings (RRF)…" },
    date_filter: { g: "retrieve", name: "Date filter", why: "Removes passages from laws that weren't in force for your period.", wait: "Removing out-of-date law…" },
    rerank: { g: "retrieve", name: "Reranker", why: "A careful second reader (cross-encoder) reads each passage with the question.", wait: "Reranker re-reading the top 20…" },
    gate: { g: "guard", name: "Safety gate", why: "The bouncer: if it's out of scope or evidence is weak, we send you to a CA.", wait: "Safety gate check…" },
    calculator: { g: "generate", name: "Tax calculator", why: "Exact arithmetic in code. The LLM never does the maths.", wait: "Running the tax calculator…" },
    generate: { g: "generate", name: "Write answer", why: "The LLM explains using only the retrieved passages and tags each claim with [ID].", wait: "LLM writing a grounded answer…" },
    citation_check: { g: "guard", name: "Citation check", why: "Deletes any sentence whose citation is missing or made up.", wait: "Checking every citation…" },
  };
  TS.STEP = STEP;

  function stepData(trace, name) {
    for (var i = 0; i < (trace || []).length; i++) if (trace[i].step === name) return trace[i].data || {};
    return null;
  }

  function topId(d) { var r = (d.results || [])[0]; return r ? r.id : null; }
  function piiFound(d) {
    // backend: found = {"PAN": 1, "phone": 2}; older mocks used a list of {type, value}
    var f = d.found || d.entities;
    if (Array.isArray(f)) return f.map(function (x) { return { type: x.type || String(x), n: 1, value: x.value }; });
    if (f && typeof f === "object") return Object.keys(f).filter(function (k) { return f[k]; }).map(function (k) { return { type: k, n: Number(f[k]) || 1 }; });
    return [];
  }
  function amountValue(a) { return a != null && typeof a === "object" ? a.value : a; }
  function logit(v) { var n = Number(v); return (n > 0 ? "+" : "") + n.toFixed(2); }

  function friendlyLabel(s, result) {
    var d = s.data || {};
    var meta = STEP[s.step];
    try {
      switch (s.step) {
        case "pii": {
          var f = piiFound(d), n = f.reduce(function (a, x) { return a + x.n; }, 0);
          if (n) return "Masked " + n + " personal detail" + (n > 1 ? "s" : "") + " (" + f.map(function (x) { return x.type; }).join(", ") + ")";
          if (typeof d.found === "number" && d.found) return "Masked " + d.found + " personal detail(s)";
          return "No personal details found";
        }
        case "hinglish": {
          var rep = d.replaced || [], isHi = (d.language || "").toLowerCase().indexOf("hi") === 0;
          if (isHi && d.applied === false) return "Hinglish detected, but this config doesn't translate it";
          if (isHi || rep.length)
            return "Translated Hinglish → English (" + rep.length + " word" + (rep.length === 1 ? "" : "s") + ")";
          return "Language: English, no changes needed";
        }
        case "intent": {
          var lab = d.label || d.intent || "", p = d.probs && d.probs[lab];
          if (!lab) return s.summary || s.label || "Intent classified";
          return "Detected intent: " + lab.replace(/_/g, " ") + (p != null ? " (" + Math.round(p * 100) + "%)" : "") + (d.rule ? " · rule applied" : "");
        }
        case "period":
          if (d.assumed_current) return "No date mentioned, so using current law (" + periodLabel(d, true) + ")";
          return "Found period: " + periodLabel(d);
        case "entities": {
          var parts = [];
          (d.sections || []).forEach(function (x) { parts.push("section " + x); });
          (d.amounts || []).slice(0, 3).forEach(function (a) { parts.push(inr(amountValue(a)) + (a && a.per_month ? "/month" : "")); });
          (d.hsn || []).forEach(function (h) { parts.push("HSN " + h); });
          if (d.mapping) Object.keys(d.mapping).forEach(function (k) { parts.push(k + " → s." + d.mapping[k]); });
          if (d.age_category) parts.push("age " + String(d.age_category).replace(/to/, "–").replace(/below/, "below "));
          return parts.length ? "Spotted " + parts.join(" · ") : "No section numbers or amounts";
        }
        case "bm25": case "dense": {
          var nm = s.step === "bm25" ? "Keyword search (BM25)" : "Meaning search (embeddings)";
          var t = topId(d);
          return t ? nm + ": best match " + t : nm + ": no matches";
        }
        case "fusion": {
          var tf = topId(d);
          return "Merged both rankings (RRF" + (d.k ? ", k=" + d.k : "") + ")" + (tf ? ": " + tf + " on top" : "");
        }
        case "date_filter": {
          var rem = d.removed ? d.removed.length : d.before != null && d.after != null ? d.before - d.after : 0;
          return rem ? "Removed " + rem + " of the top " + (d.before || 20) + " passages: not in force for this period" : "All top passages are in force for this period";
        }
        case "rerank": {
          var c = d.pool || d.candidates || d.before || 20, top = (d.results || [])[0];
          var reorders = !(result && result.config === "C6");
          return (reorders ? "Reranker re-read the top " + c + " and re-ordered them" : "Reranker scored the top " + c + " (confidence only, order kept)") +
            (top ? ": best " + logit(top.score) : "");
        }
        case "gate": {
          var sc = d.top_score, th = d.threshold;
          if (d.passed) return "Safety gate: passed" + (sc != null && th != null ? " (best score " + logit(sc) + " ≥ threshold " + logit(th) + ")" : "");
          var r = String(d.reason || "");
          return "Safety gate: blocked" + (/intent|scope/i.test(r) ? " (out of scope)" : /inject/i.test(r) ? " (prompt injection)" : sc != null && th != null ? " (best score " + logit(sc) + " < threshold " + logit(th) + ")" : r ? " (" + r + ")" : "");
        }
        case "calculator": {
          var res = d.result || d;
          if (d.status === "missing_inputs" || (d.missing && d.missing.length) || (!d.result && /follow|missing/i.test(s.summary || ""))) return "Calculator needs your salary, so asked a follow-up";
          if (res.better) {
            var sav = d.saving != null ? d.saving : res.old_total != null && res.new_total != null ? Math.abs(res.old_total - res.new_total) : null;
            return res.better === "same" ? "Calculator: both regimes cost the same" : "Calculator: " + res.better.toUpperCase() + " regime is cheaper" + (sav ? " by " + inr(sav) : "");
          }
          return s.label || "Ran tax calculator";
        }
        case "generate":
          if (d.error) return "LLM error, so no answer was written";
          if (result && result.config === "B0") return "LLM answered from memory (no sources)";
          if (d.fallback) return "LLM answer unusable, so quoted the best passage instead";
          var np = Array.isArray(d.passages) ? d.passages.length : d.passages;
          return "LLM wrote the answer" + (d.model ? " with " + d.model : "") + (np ? " from " + np + " passage" + (np > 1 ? "s" : "") : "");
        case "citation_check":
          return "Checked citations: " + (d.kept != null ? d.kept : "?") + " sentence" + (d.kept === 1 ? "" : "s") + " kept, " + (d.dropped != null ? d.dropped : 0) + " dropped";
      }
    } catch (e) { /* fall through */ }
    return s.label || (meta ? meta.name : s.step);
  }
  TS.friendlyLabel = friendlyLabel;
  TS.periodLabel = periodLabel;

  /* ---------------- trace detail renderers ---------------- */
  function resultsList(results, opts) {
    opts = opts || {};
    results = (results || []).slice(0, opts.limit || 8);
    if (!results.length) return '<p class="muted small">No results.</p>';
    var scores = results.map(function (r) { return Number(r.score) || 0; });
    var max = Math.max.apply(null, scores), min = Math.min.apply(null, scores);
    var span = max - min || 1;
    var cited = opts.cited || {}, removed = opts.removed || {};
    return (
      '<ol class="rlist">' +
      results.map(function (r, i) {
        var w = opts.logit ? ((Math.max(-10, Math.min(10, r.score)) + 10) / 20) * 100 : min >= 0 && max > 0 ? (r.score / max) * 100 : ((r.score - min) / span) * 85 + 15;
        w = Math.max(4, Math.min(100, w));
        var cls = removed[r.id] ? " removed" : cited[r.id] ? " cited" : "";
        var digits = Math.abs(max) < 1 ? 3 : Math.abs(max) < 10 ? 2 : 1;
        if (opts.rrf) digits = 4;
        return (
          '<li class="ritem' + cls + (r.score < 0 ? " neg" : "") + '">' +
          '<span class="rrank">' + (i + 1) + "</span>" +
          '<span class="rmain"><code class="rid">' + esc(r.id) + "</code>" +
          (r.title ? '<span class="rtitle">' + esc(r.title) + "</span>" : "") +
          (removed[r.id] ? '<span class="rtag tag-bad">wrong period</span>' : cited[r.id] ? '<span class="rtag tag-good">cited</span>' : "") +
          "</span>" +
          '<span class="rbar"><span style="width:' + w.toFixed(1) + '%"></span></span>' +
          '<span class="rscore">' + (r.score != null ? Number(r.score).toFixed(digits) : "") + "</span>" +
          "</li>"
        );
      }).join("") +
      "</ol>"
    );
  }

  function probBars(probs, winner) {
    var keys = Object.keys(probs || {}).sort(function (a, b) { return probs[b] - probs[a]; });
    return (
      '<div class="pbars">' +
      keys.map(function (k) {
        var v = Number(probs[k]) || 0;
        return '<div class="pbar' + (k === winner ? " win" : "") + '"><span class="plabel">' + esc(k.replace(/_/g, " ")) + '</span><span class="ptrack"><span style="width:' + (v * 100).toFixed(1) + '%"></span></span><span class="pval">' + Math.round(v * 100) + "%</span></div>";
      }).join("") +
      "</div>"
    );
  }

  function kv(rows) {
    return '<dl class="kv">' + rows.filter(function (r) { return r[1] != null && r[1] !== ""; }).map(function (r) { return "<dt>" + esc(r[0]) + "</dt><dd>" + r[1] + "</dd>"; }).join("") + "</dl>";
  }

  function stepDetail(s, result) {
    var d = s.data || {};
    var cited = {};
    (result.citations || []).forEach(function (c) { cited[c.id] = 1; });
    var df = stepData(result.trace, "date_filter");
    var removed = {};
    if (df && df.removed) df.removed.forEach(function (id) { removed[id] = 1; });
    var html = "";
    switch (s.step) {
      case "pii": {
        var pf = piiFound(d);
        html = (pf.length
          ? '<div class="chips-inline">' + pf.map(function (f) { return '<span class="chip-sm chip-warn">' + esc(f.type || "PII") + (f.n > 1 ? " ×" + f.n : "") + (f.value ? " · " + esc(f.value) : "") + "</span>"; }).join("") + "</div>"
          : "") + ((d.masked || d.redacted) ? kv([[pf.length ? "Logged as" : "Question (as logged)", '<span class="mono">' + esc(d.masked || d.redacted) + "</span>"]]) : "");
        break;
      }
      case "hinglish":
        html = kv([["Original", "“" + esc(d.original) + "”"], ["Normalised", d.normalised && d.normalised !== d.original ? "“" + esc(d.normalised) + "”" : null], ["Language", esc(d.language === "en" ? "English" : d.language === "hinglish" ? "Hinglish" : d.language)], ["Applied", d.applied === false && d.language === "hinglish" ? "No, Hinglish normalisation is switched off in this config" : null]]);
        if (d.replaced && d.replaced.length)
          html += '<div class="wchips">' + d.replaced.map(function (p) {
            var a = Array.isArray(p) ? p[0] : p.from, b = Array.isArray(p) ? p[1] : p.to;
            return '<span class="wchip"><span class="w-from">' + esc(a) + '</span><span class="w-arrow">→</span><span class="w-to">' + esc(b) + "</span></span>";
          }).join("") + "</div>";
        break;
      case "intent":
        html = (d.probs ? probBars(d.probs, d.label) : kv([["Label", esc(d.label)]])) + (d.rule ? '<p class="muted small">A keyword rule adjusted the classifier: <span class="mono">' + esc(d.rule) + "</span></p>" : "");
        break;
      case "period":
        html = kv([["From", esc(fmtDate(d.start))], ["To", esc(fmtDate(d.end))], ["Why", esc(d.reason)], ["Assumed current law", d.assumed_current ? "Yes, no date in the question" : "No, taken from the question"]]);
        html += periodTimeline(d);
        break;
      case "entities":
        html = kv([
          ["Sections", (d.sections || []).map(function (x) { return '<span class="chip-sm">' + esc(x) + "</span>"; }).join(" ") || "—"],
          ["Amounts", (d.amounts || []).map(function (x) { return '<span class="chip-sm"' + (x && x.text ? ' title="from “' + esc(x.text) + '”"' : "") + ">" + esc(inr(amountValue(x))) + (x && x.per_month ? "/month" : "") + "</span>"; }).join(" ") || "—"],
          ["Age group", d.age_category ? esc(d.age_category) + (d.age ? " (age " + esc(d.age) + ")" : "") : null],
          ["Old → new Act", d.mapping ? Object.keys(d.mapping).map(function (k) { return '<span class="chip-sm chip-good">' + esc(k) + " → s." + esc(d.mapping[k]) + "</span>"; }).join(" ") : null],
          ["Other", d.hsn ? "HSN " + esc(d.hsn.join(", ")) : null],
        ]);
        break;
      case "bm25":
      case "dense":
      case "fusion":
        html = resultsList(d.results, { cited: cited, removed: removed, rrf: s.step === "fusion", limit: s.step === "fusion" ? 10 : 8 });
        if (s.step === "fusion") html += '<p class="muted small">RRF score = Σ 1 / (60 + rank) across both lists. A passage ranked well by both searches rises to the top.</p>';
        break;
      case "date_filter":
        var pd = stepData(result.trace, "period") || {};
        html = '<div class="df-head"><span class="df-num">' + esc(d.before) + '</span><span class="df-arrow">→</span><span class="df-num good">' + esc(d.after) + '</span><span class="muted small">of the top ' + esc(d.before) + " passages are in force for " + esc(periodLabel(pd, pd.assumed_current)) + "</span></div>";
        if (d.removed && d.removed.length)
          html += '<div class="chips-inline">' + d.removed.map(function (id) { return '<span class="chip-sm chip-strike" title="Not in force for this period">' + esc(id) + "</span>"; }).join("") + "</div>";
        if (d.removed_total != null && d.removed && d.removed_total > d.removed.length)
          html += '<p class="muted small">' + esc(d.removed_total) + " out-of-period passages were dropped from the whole candidate list; the chips show the ones that were in the top " + esc(d.before) + ".</p>";
        break;
      case "rerank":
        var gd = stepData(result.trace, "gate") || {};
        html = resultsList(d.results, { cited: cited, limit: 6, logit: true }) +
          '<p class="muted small">Scores are cross-encoder logits: above 0 means probably relevant, below 0 probably not' + (gd.threshold != null ? "; the safety gate needs the best one to reach " + logit(gd.threshold) : "") + "." +
          (result.config === "C6" ? " In the final config (C6) these scores only feed the safety gate; the answer keeps the hybrid order, which ranked better in experiments." : "") + "</p>" +
          (d.boosted && d.boosted.length ? kv([["Added for old sections", d.boosted.map(function (id) { return '<span class="chip-sm chip-good">' + esc(id) + "</span>"; }).join(" ")]]) : "");
        break;
      case "gate":
        html = gateGauge(d);
        break;
      case "calculator":
        if (!d.result && !d.missing && d.inputs && !d.inputs.gross_salary) d = Object.assign({ missing: ["gross_salary"] }, d);
        if (d.result) d = Object.assign({}, d, d.result, { saving: d.result.old_total != null && d.result.new_total != null ? Math.abs(d.result.old_total - d.result.new_total) : null });
        if (d.missing) html = kv([["Missing", (d.missing || []).map(function (m) { return '<span class="chip-sm chip-warn">' + esc(m.replace(/_/g, " ")) + "</span>"; }).join(" ")]]);
        else {
          var inp = d.inputs || {};
          html = kv([
            ["Gross salary", esc(inr(inp.gross_salary))],
            ["80C", inp.deductions_80c ? esc(inr(inp.deductions_80c)) : null],
            ["80D", inp.deductions_80d ? esc(inr(inp.deductions_80d)) : null],
            ["80D (parents)", inp.deductions_80d_parents ? esc(inr(inp.deductions_80d_parents)) : null],
            ["HRA exemption", inp.hra_exemption ? esc(inr(inp.hra_exemption)) : null],
            ["Age group", inp.age && inp.age !== "below60" ? esc(inp.age) : null],
            ["Tax year", inp.tax_year ? esc(inp.tax_year) : null],
            ["Home-loan interest", inp.home_loan_interest ? esc(inr(inp.home_loan_interest)) : null],
            ["NPS 80CCD(1B)", inp.nps_80ccd1b ? esc(inr(inp.nps_80ccd1b)) : null],
            ["Old regime tax", d.old_total != null ? esc(inr(d.old_total)) : null],
            ["New regime tax", d.new_total != null ? esc(inr(d.new_total)) : null],
            ["Better", d.better ? "<strong>" + esc(d.better.toUpperCase()) + "</strong>" + (d.saving ? ", saves " + esc(inr(d.saving)) : "") : null],
          ]);
          if (d.assigned && d.assigned.length)
            html += '<p class="muted small">Read from your question: ' + d.assigned.map(function (a) { return '<span class="chip-sm">“' + esc(a[1]) + "” → " + esc(String(a[0]).replace(/_/g, " ")) + "</span>"; }).join(" ") + "</p>";
        }
        break;
      case "generate":
        html = kv([["Model", d.model ? '<span class="mono">' + esc(d.model) + "</span>" : null],
          ["Passages given", Array.isArray(d.passages) ? d.passages.map(function (id) { return '<span class="chip-sm' + (cited[id] ? " chip-good" : "") + '">' + esc(id) + "</span>"; }).join(" ") : d.passages != null ? esc(d.passages) : null],
          ["Fallback", d.fallback ? '<span class="chip-sm chip-warn">extractive answer</span> ' + esc(String(d.fallback_reason || "").replace(/_/g, " ")) : null],
          ["Error", d.error ? esc(d.error) : null], ["Prompt tokens", d.prompt_tokens != null ? esc(inr(d.prompt_tokens, { noSymbol: true })) : null], ["Output tokens", d.output_tokens != null ? esc(d.output_tokens) : null], ["Temperature", d.temperature != null ? esc(d.temperature) : null]]);
        if (result.config === "B0") html += '<p class="callout callout-warn small">No retrieval: the model answers from what it memorised during training, which may be out of date.</p>';
        else if (d.raw) html += '<details class="raw-out"><summary>Raw LLM output (before the citation check)</summary><p class="mono small">' + esc(d.raw) + "</p></details>";
        break;
      case "citation_check":
        html = '<div class="cc-stats"><span class="cc-stat good"><b>' + esc(d.kept != null ? d.kept : "–") + '</b> sentences kept</span><span class="cc-stat bad"><b>' + esc(d.dropped != null ? d.dropped : 0) + "</b> dropped</span>" +
          (d.n_tags != null ? '<span class="cc-stat"><b>' + esc(d.n_valid_tags != null ? d.n_valid_tags : "?") + "/" + esc(d.n_tags) + "</b> citation tags valid</span>" : "") + "</div>";
        if (d.invalid_ids && d.invalid_ids.length)
          html += '<p class="small muted">Invalid IDs removed (the LLM made these up or cited a passage it wasn\'t given):</p><div class="chips-inline">' + d.invalid_ids.map(function (id) { return '<span class="chip-sm chip-strike">' + esc(id) + "</span>"; }).join("") + "</div>";
        break;
    }
    if (!html) {
      var keys = Object.keys(d);
      html = keys.length ? '<pre class="json">' + esc(JSON.stringify(d, null, 2)) + "</pre>" : '<p class="muted small">No extra data for this step.</p>';
    }
    if (s.summary && s.summary !== friendlyLabel(s, result)) html = '<p class="step-summary">' + esc(s.summary) + "</p>" + html;
    return html;
  }

  function periodTimeline(d) {
    if (!d.start) return "";
    // A tiny timeline from FY 2023-24 to Tax Year 2026-27 with the asked window highlighted
    var t0 = Date.parse("2023-04-01"), t1 = Date.parse("2027-03-31");
    var s = Date.parse(d.start), e = Date.parse(d.end || d.start) + 864e5;
    if (!isFinite(s) || !isFinite(e)) return "";
    var L = Math.max(0, Math.min(100, ((s - t0) / (t1 - t0)) * 100));
    var R = Math.max(0, Math.min(100, ((e - t0) / (t1 - t0)) * 100));
    var marks = [["2023-04-01", "FY23-24"], ["2024-04-01", "FY24-25"], ["2025-04-01", "FY25-26"], ["2026-04-01", "TY26-27"]];
    var gst = ((Date.parse("2025-09-22") - t0) / (t1 - t0)) * 100;
    var act = ((Date.parse("2026-04-01") - t0) / (t1 - t0)) * 100;
    return (
      '<div class="ptl" aria-hidden="true"><div class="ptl-track">' +
      marks.map(function (m) { var x = ((Date.parse(m[0]) - t0) / (t1 - t0)) * 100; return '<span class="ptl-tick" style="left:' + x + '%"><i>' + m[1] + "</i></span>"; }).join("") +
      '<span class="ptl-event" style="left:' + gst + '%" title="GST 2.0 from 22 Sep 2025"><i>GST 2.0</i></span>' +
      '<span class="ptl-event act" style="left:' + act + '%" title="Income-tax Act, 2025 in force"><i>New Act</i></span>' +
      '<span class="ptl-win" style="left:' + L + "%;width:" + Math.max(1.2, R - L) + '%"></span>' +
      "</div></div>"
    );
  }

  var REASONS = {
    out_of_scope: "The intent classifier marked this as outside individual income tax and GST, so TaxSaathi won't answer it, whatever the search found.",
    prompt_injection: "The question looked like an attempt to change TaxSaathi's instructions.",
    low_retrieval_score: "Even the best passage in the knowledge base wasn't a confident match (reranker score below the threshold), so TaxSaathi would rather not guess.",
  };
  function reasonText(r) { return r ? REASONS[r] || String(r).replace(/_/g, " ") : ""; }
  TS.reasonText = reasonText;

  function gateGauge(d) {
    var hasScore = d.top_score != null && d.threshold != null;
    var sc = Number(d.top_score), th = Number(d.threshold);
    var lo = Math.min(-8, sc - 1, th - 2), hi = Math.max(10, sc + 1);
    var pos = function (v) { return ((v - lo) / (hi - lo)) * 100; };
    var html = "";
    if (hasScore && isFinite(sc) && isFinite(th))
      html +=
        '<div class="gauge ' + (sc >= th ? "pass" : "fail") + '"><div class="g-track"><span class="g-fail" style="width:' + pos(th) + '%"></span>' +
        '<span class="g-th" style="left:' + pos(th) + '%"><i>threshold ' + th.toFixed(1) + "</i></span>" +
        '<span class="g-pt" style="left:' + pos(sc) + '%"><i>' + sc.toFixed(2) + "</i></span></div></div>";
    if (hasScore && !d.passed && /scope|inject/.test(String(d.reason)) && sc >= th) html += '<p class="muted small">The score was high enough, but the intent classifier had already blocked the question.</p>';
    if (d.threshold == null) html += '<p class="muted small">This config has no reranker, so the gate only checks the intent (no score threshold).</p>';
    html += kv([["Decision", d.passed ? '<span class="chip-sm chip-good">Passed: answer allowed</span>' : '<span class="chip-sm chip-warn">Blocked: escalate to a CA</span>'], ["Reason", esc(reasonText(d.reason))],
      ["Rule", d.threshold != null ? "Refuse if the question is out of scope, or if the best reranker score is below " + esc(Number(d.threshold).toFixed(2)) + " (tuned on the dev set). Calculations skip the score check." : null]]);
    return html;
  }


  /* ---------------- trace renderer (vertical timeline) ---------------- */
  var traceTimers = [];
  function clearTraceTimers() { traceTimers.forEach(clearTimeout); traceTimers = []; }

  var GROUP_NAME = { understand: "Understand", retrieve: "Search", guard: "Check", generate: "Answer" };

  function stepHtml(s, i, result) {
    var meta = STEP[s.step] || { g: "generate", name: s.step, why: "" };
    return (
      '<li class="step g-' + meta.g + '" data-i="' + i + '">' +
      '<button type="button" class="step-head" aria-expanded="false">' +
      '<span class="step-dot" aria-hidden="true"></span>' +
      '<span class="step-text"><span class="step-name">' + esc(meta.name) + '<span class="step-group">' + esc(GROUP_NAME[meta.g] || "") + "</span></span>" +
      '<span class="step-label">' + esc(friendlyLabel(s, result)) + "</span></span>" +
      '<span class="step-ms">' + esc(fmtMs(s.ms)) + "</span>" +
      icon("chevDown", "step-chev") +
      "</button>" +
      '<div class="step-detail" hidden></div>' +
      "</li>"
    );
  }

  function renderTrace(container, result, opts) {
    opts = opts || {};
    clearTraceTimers();
    var trace = result.trace || [];
    if (!trace.length) {
      container.innerHTML = '<p class="placeholder">The server returned no trace for this answer.</p>';
      return;
    }
    var total = trace.reduce(function (a, s) { return a + (Number(s.ms) || 0); }, 0);
    var html = timeBar(trace, total) + '<ol class="steps' + (opts.animate ? " animating" : " done") + '" style="--draw:' + (trace.length * 140) + 'ms">' + trace.map(function (s, i) { return stepHtml(s, i, result); }).join("") + "</ol>";
    container.innerHTML = html;
    var items = $$(".step", container);
    items.forEach(function (li) {
      var i = +li.getAttribute("data-i");
      var head = $(".step-head", li), det = $(".step-detail", li);
      head.addEventListener("click", function () {
        var open = head.getAttribute("aria-expanded") === "true";
        if (!open && !det.innerHTML) {
          var meta = STEP[trace[i].step];
          det.innerHTML = (meta && meta.why ? '<p class="step-why">' + esc(meta.why) + "</p>" : "") + stepDetail(trace[i], result);
        }
        head.setAttribute("aria-expanded", open ? "false" : "true");
        det.hidden = open;
        li.classList.toggle("open", !open);
      });
    });
    var stepsEl = $(".steps", container);
    if (opts.animate && !reducedMotion()) {
      items.forEach(function (li, i) {
        traceTimers.push(setTimeout(function () { li.classList.add("on"); }, 80 + i * 140));
      });
      traceTimers.push(setTimeout(function () {
        stepsEl.classList.remove("animating"); stepsEl.classList.add("done");
        autoOpenKey(trace, items, result, opts);
      }, 120 + items.length * 140));
    } else {
      items.forEach(function (li) { li.classList.add("on"); });
      stepsEl.classList.remove("animating"); stepsEl.classList.add("done");
      autoOpenKey(trace, items, result, opts);
    }
  }
  TS.renderTrace = renderTrace;

  // Open the most telling step: the gate when refused, the date filter when it removed something
  function autoOpenKey(trace, items, result, opts) {
    if (opts.autoOpen === false) return;
    var df = stepData(trace, "date_filter");
    var key = result.refused ? "gate" : df && (df.removed || []).length ? "date_filter" : null;
    if (!key) return;
    var idx = trace.map(function (s) { return s.step; }).indexOf(key);
    if (idx < 0) return;
    var h = $(".step-head", items[idx]);
    if (h && h.getAttribute("aria-expanded") !== "true") h.click();
  }

  function timeBar(trace, total) {
    if (!total) return "";
    var segs = trace.filter(function (s) { return s.ms > 0; }).map(function (s) {
      var meta = STEP[s.step] || { g: "generate", name: s.step };
      var w = (s.ms / total) * 100;
      return '<span class="tb-seg tb-' + esc(s.step) + '" style="width:' + Math.max(0.8, w).toFixed(2) + '%" title="' + esc(meta.name + ": " + fmtMs(s.ms)) + '"></span>';
    }).join("");
    var gen = trace.filter(function (s) { return s.step === "generate"; })[0];
    var rr = trace.filter(function (s) { return s.step === "rerank"; })[0];
    var legend = '<span class="tb-key"><i class="k-gen"></i>Writing (LLM)' + (gen && gen.ms ? " " + esc(fmtMs(gen.ms)) : "") + "</span>" +
      (rr && rr.ms ? '<span class="tb-key"><i class="k-rr"></i>Reranker ' + esc(fmtMs(rr.ms)) + "</span>" : "") +
      '<span class="tb-key"><i class="k-other"></i>Everything else</span>';
    return '<div class="timebar"><div class="tb-head"><span>Where the time went</span><span class="num">' + esc(fmtMs(total)) + '</span></div><div class="tb-track">' + segs + '</div><div class="tb-legend">' + legend + "</div></div>";
  }

  // Kept for compatibility: a static list of the steps a config will run
  function renderThinking(container, config) {
    clearTraceTimers();
    var steps = CONFIG_STEPS[config] || CONFIG_STEPS.C6;
    container.innerHTML = '<ol class="steps done">' + steps.map(function (k) {
      var m = STEP[k];
      return '<li class="step on"><div class="step-head static"><span class="step-dot" aria-hidden="true"></span><span class="step-text"><span class="step-name">' + esc(m.name) + '</span><span class="step-label">' + esc(m.wait) + "</span></span></div></li>";
    }).join("") + "</ol>";
  }
  TS.renderThinking = renderThinking;

  /* ================================================================== */
  /* Drawer (side sheet) for sources and the pipeline trace              */
  /* ================================================================== */
  var drawer = { open: false, key: null, trigger: null, onClose: null };
  function openDrawer(o) {
    var d = $("#drawer");
    $("#drawerKicker").textContent = o.kicker || "";
    $("#drawerTitle").textContent = o.title || "";
    var body = $("#drawerBody");
    body.innerHTML = o.html || "";
    body.scrollTop = 0;
    d.classList.toggle("wide", !!o.wide);
    if (drawer.onClose && drawer.key !== o.key) { try { drawer.onClose(); } catch (e) { /* ignore */ } }
    drawer.key = o.key || null;
    drawer.onClose = o.onClose || null;
    if (o.trigger) drawer.trigger = o.trigger;
    var wasOpen = drawer.open;
    drawer.open = true;
    d.hidden = false;
    $("#scrim").hidden = false;
    document.body.classList.add("drawer-open");
    document.body.classList.toggle("drawer-wide", !!o.wide);
    if (!wasOpen) {
      requestAnimationFrame(function () { d.classList.add("in"); $("#scrim").classList.add("in"); });
      setTimeout(function () { try { $("#drawerClose").focus({ preventScroll: true }); } catch (e) { /* ignore */ } }, 30);
    }
    if (o.after) o.after(body);
  }
  function closeDrawer(silent) {
    if (!drawer.open) return;
    var d = $("#drawer");
    drawer.open = false;
    d.classList.remove("in"); $("#scrim").classList.remove("in");
    document.body.classList.remove("drawer-open", "drawer-wide");
    clearTraceTimers();
    if (drawer.onClose) { try { drawer.onClose(); } catch (e) { /* ignore */ } }
    drawer.onClose = null; drawer.key = null;
    setTimeout(function () { if (!drawer.open) { d.hidden = true; $("#scrim").hidden = true; } }, reducedMotion() ? 0 : 220);
    var t = drawer.trigger; drawer.trigger = null;
    if (!silent && t && document.contains(t)) { try { t.focus({ preventScroll: true }); } catch (e) { /* ignore */ } }
  }
  TS.openDrawer = openDrawer; TS.closeDrawer = closeDrawer;
  TS.drawerKey = function () { return drawer.open ? drawer.key : null; };

  /* ---------------- citations ---------------- */
  var TODAY = "2026-10-29";
  function citePeriod(c) {
    var from = c.effective_from ? fmtDate(c.effective_from) : "";
    var to = c.effective_to ? fmtDate(c.effective_to) : "";
    var current = !c.effective_to || Date.parse(c.effective_to) >= Date.parse(TODAY);
    if (!from && !to) return { text: "", current: true };
    if (current) return { text: from ? "In force from " + from : "In force", current: true };
    return { text: (from || "…") + " – " + to, current: false };
  }
  function citeLawLine(c) {
    var law = inferLaw(c);
    return LAW_LABEL[law] + (c.section ? " · s. " + c.section : "");
  }
  TS.citePeriod = citePeriod; TS.citeLawLine = citeLawLine;

  // Full passage card (drawer, compare view, "sources in full")
  function citeCardHtml(c, i, scope) {
    var p = citePeriod(c);
    return (
      '<article class="cite-card" tabindex="-1" data-cite="' + esc(c.id) + '" data-scope="' + esc(scope) + '">' +
      '<header class="cite-top"><span class="cite-n">' + (i + 1) + '</span><span class="cite-law">' + esc(citeLawLine(c)) + "</span>" +
      (p.text ? '<span class="cite-period' + (p.current ? "" : " old") + '">' + esc(p.text) + "</span>" : "") + "</header>" +
      '<h3 class="cite-title">' + esc(c.title || c.id) + "</h3>" +
      (c.text ? '<p class="cite-text">' + esc(c.text) + '</p><button type="button" class="text-btn cite-more">Show full passage</button>' : "") +
      '<footer class="cite-foot"><code class="cite-id">' + esc(c.id) + "</code>" +
      (c.source_url ? '<a class="cite-src" href="' + esc(c.source_url) + '" target="_blank" rel="noopener noreferrer">Official source' + icon("arrowUpRight") + "</a>" : "") +
      "</footer></article>"
    );
  }
  TS.citeCardHtml = citeCardHtml;

  // The drawer view of one source: everything, no clamping
  function sourceSheetHtml(c, i) {
    var p = citePeriod(c);
    var law = inferLaw(c);
    return (
      '<div class="sheet-source">' +
      '<div class="ss-meta"><span class="ss-n">' + (i + 1) + "</span>" + esc(LAW_NAMES_FULL[law] || LAW_LABEL[law]) + (c.section ? " · Section " + esc(c.section) : "") + "</div>" +
      '<h3 class="ss-title">' + esc(c.title || c.id) + "</h3>" +
      (p.text ? '<p class="ss-period' + (p.current ? "" : " old") + '">' + icon("calendar") + esc(p.text) + (p.current ? "" : " · historical") + "</p>" : "") +
      (c.text ? '<blockquote class="ss-text">' + esc(c.text) + "</blockquote>" : "") +
      '<dl class="kv ss-kv">' +
      (c.source_title ? "<dt>Document</dt><dd>" + esc(c.source_title) + "</dd>" : "") +
      (c.publisher ? "<dt>Publisher</dt><dd>" + esc(c.publisher) + "</dd>" : "") +
      "<dt>Passage ID</dt><dd><code>" + esc(c.id) + "</code></dd>" +
      "</dl>" +
      (c.source_url ? '<a class="btn btn-secondary btn-sm ss-link" href="' + esc(c.source_url) + '" target="_blank" rel="noopener noreferrer">Open the official source' + icon("arrowUpRight") + "</a>" : "") +
      "</div>"
    );
  }
  var LAW_NAMES_FULL = { new_act: "Income-tax Act, 2025", old_act: "Income-tax Act, 1961", gst: "GST law", mapping: "Section map (1961 → 2025)", general: "General guidance" };

  function wireCiteCards(root) {
    $$(".cite-card", root).forEach(function (card) {
      var more = $(".cite-more", card), txt = $(".cite-text", card);
      if (more && txt) {
        if (txt.textContent.length < 240) more.remove();
        else more.onclick = function () { var o = card.classList.toggle("expanded"); more.textContent = o ? "Show less" : "Show full passage"; };
      }
    });
  }
  TS.wireCiteCards = wireCiteCards;

  var CALC_ICON = icon("calc");
  var CITE_RE = /\[([A-Za-z0-9][A-Za-z0-9._:\-]{2,}(?:\s*[,;]\s*[A-Za-z0-9][A-Za-z0-9._:\-]{2,})*)\]/g;
  // Lightweight markdown: **bold**, paragraphs, "- " bullets, [CHUNK-ID] / [A, B] citation markers and [CALC] markers
  function richText(text, citations, scope) {
    var idx = {};
    (citations || []).forEach(function (c, i) { idx[c.id] = { n: i + 1, c: c }; idx[String(c.id).toUpperCase()] = idx[c.id]; });
    var src = String(text || "");
    // Calculator answers come as "line. [CALC] line. [CALC] explanation": give each calculator line its own row
    if (/\[CALC\]/.test(src)) src = src.replace(/\s*\[CALC\]\s*/g, " [CALC]\n").replace(/\n+$/, "").replace(/\[CALC\]\n(?![\s\S]*\[CALC\])/, "[CALC]\n\n");
    var html = esc(src);
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    var one = function (id) {
      if (id.toUpperCase() === "CALC")
        return '<button type="button" class="cite cite-calc" data-calcpill="1" title="From the exact tax calculator, not the AI" aria-label="Calculated by the tax calculator">' + CALC_ICON + "</button>";
      var hit = idx[id] || idx[id.toUpperCase()];
      if (!hit) return '<span class="cite cite-bad" title="' + esc(id) + ' is not among the returned sources">?</span>';
      return '<button type="button" class="cite" data-cite="' + esc(hit.c.id) + '" data-scope="' + esc(scope) + '" title="' + esc(hit.c.title || hit.c.id) + '" aria-label="Source ' + hit.n + '">' + hit.n + "</button>";
    };
    html = html.replace(CITE_RE, function (m, ids) {
      return '<span class="cites">' + ids.split(/\s*[,;]\s*/).map(one).join("") + "</span>";
    });
    html = html.replace(/\s+<span class="cites">/g, '<span class="cites">');
    var blocks = html.split(/\n{2,}/);
    return blocks.map(function (b) {
      var lines = b.split("\n");
      if (lines.every(function (l) { return /^\s*[-•*]\s+/.test(l) || !l.trim(); }) || (lines.length > 1 && lines.slice(1).every(function (l) { return /^\s*[-•*]\s+/.test(l); }))) {
        var head = /^\s*[-•*]\s+/.test(lines[0]) ? "" : "<p>" + lines.shift() + "</p>";
        return head + "<ul>" + lines.filter(function (l) { return l.trim(); }).map(function (l) { return "<li>" + l.replace(/^\s*[-•*]\s+/, "") + "</li>"; }).join("") + "</ul>";
      }
      return "<p>" + lines.join("<br>") + "</p>";
    }).join("");
  }
  TS.richText = richText;

  function flashEl(el) {
    el.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "nearest" });
    el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash");
  }
  TS.flashEl = flashEl;

  function focusCite(root, id) {
    var card = $('.cite-card[data-cite="' + (window.CSS && CSS.escape ? CSS.escape(id) : id) + '"]', root);
    if (!card) return;
    $$(".cite-card.flash", root).forEach(function (c) { c.classList.remove("flash"); });
    card.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "nearest" });
    void card.offsetWidth;
    card.classList.add("flash");
    try { card.focus({ preventScroll: true }); } catch (e) { /* old browsers */ }
  }
  TS.focusCite = focusCite;

  function latencyBadge(ms) {
    if (ms == null) return "";
    return '<span class="lat" title="End-to-end time">' + icon("clock") + esc(fmtMs(ms)) + "</span>";
  }
  TS.latencyBadge = latencyBadge;

  function normalize(r) {
    r = r || {};
    r.citations = Array.isArray(r.citations) ? r.citations : [];
    r.trace = Array.isArray(r.trace) ? r.trace : [];
    r.answer = r.answer || "";
    return r;
  }
  TS.normalize = normalize;

  /* ---------------- calculator verdict block (used in answers + compare) ---------------- */
  function calcVerdict(c) {
    if (c.headline) return String(c.headline);
    var o = Number(c.old && c.old.total) || 0, n = Number(c["new"] && c["new"].total) || 0;
    if (o === 0 && n === 0) return "No tax in either regime";
    var better = c.better || (o < n ? "old" : n < o ? "new" : "same");
    if (better === "same") return "Both regimes cost the same";
    var saving = c.saving != null ? c.saving : Math.abs(o - n);
    return (better === "new" ? "New" : "Old") + " regime saves " + inr(saving);
  }
  TS.calcVerdict = calcVerdict;

  function calcBlock(c, opts) {
    if (!c || !c.old || !c["new"]) return "";
    opts = opts || {};
    var o = Number(c.old.total) || 0, n = Number(c["new"].total) || 0;
    var better = c.better || (o < n ? "old" : n < o ? "new" : "same");
    var bothZero = o === 0 && n === 0;
    var col = function (key, label, v) {
      var win = better === key && !bothZero;
      return '<div class="cb-col' + (win ? " win" : "") + '"><span class="cb-k">' + label + (win ? '<span class="cb-tag">Lower</span>' : "") + '</span><span class="cb-v num" data-count="' + v + '" data-fmt="inr">' + inr(v) + '</span><span class="cb-s">' + (c[key].taxable != null ? "on taxable " + inr(c[key].taxable) : "") + "</span></div>";
    };
    var ty = c.tax_year ? ((+String(c.tax_year).slice(0, 4) >= 2026 ? "Tax Year " : "FY ") + c.tax_year) : "";
    return (
      '<div class="calc-block">' +
      '<div class="cb-head"><p class="cb-verdict">' + esc(calcVerdict(c)) + "</p>" +
      (ty || c.law ? '<p class="cb-law">' + esc([ty, c.law].filter(Boolean).join(" · ")) + "</p>" : "") + "</div>" +
      '<div class="cb-cols">' + col("old", "Old regime", o) + col("new", "New regime", n) + "</div>" +
      (c.notes && c.notes.length ? '<ul class="cb-notes">' + c.notes.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ul>" : "") +
      '<div class="cb-foot"><span>' + CALC_ICON + "Calculated by exact code, not the AI</span>" + (opts.noLink ? "" : '<button type="button" class="text-btn open-calc">Full breakdown' + icon("arrowRight") + "</button>") + "</div>" +
      "</div>"
    );
  }
  TS.calcBlock = calcBlock;
  TS.miniCalc = function (c) { return calcBlock(c); };

  /* ================================================================== */
  /* ASK view                                                            */
  /* ================================================================== */

  /* ------------------------------------------------------------------
   * EXAMPLES: the tappable example questions on the home screen.
   * Edit / replace this ONE array to change them. (icon and tag are kept for
   * compatibility; the current design shows only the question text.)
   * ------------------------------------------------------------------ */
  var EXAMPLES = [
    { icon: "💼", tag: "Salary", q: "Which tax regime is better for my ₹12 lakh salary?" },
    { icon: "🛒", tag: "Shopping", q: "What is the GST on an AC right now?" },
    { icon: "🗣️", tag: "Hinglish", q: "Naye regime mein standard deduction kitna hai?" },
    { icon: "📅", tag: "Old dates", q: "What was GST on AC in August 2025?" },
    { icon: "📜", tag: "New law", q: "Is 80C still available in the new Income-tax Act?" },
    { icon: "🤔", tag: "Tricky", q: "How do I avoid tax on foreign crypto income?" },
  ];
  TS.EXAMPLES = EXAMPLES;

  // Real questions people actually asked online (data/eval/real_questions.jsonl), shortened.
  var REAL_EXAMPLES = [
    { src: "r/IndiaTax", url: "https://www.reddit.com/r/IndiaTax/", q: "It says no tax until 12L and also says 5% tax for 4-8L. I am confused. What does it mean?" },
    { src: "r/IndiaTax", url: "https://www.reddit.com/r/IndiaTax/", q: "I just started freelancing as a software consultant. My turnover is below ₹20L. Is GST registration mandatory?" },
    { src: "CAclubindia", url: "https://www.caclubindia.com/forum/", q: "What is the standard deduction for old regime and new regime for FY 2024-25 (salaries)?" },
  ];

  // "Related" suggestions shown under an answer, picked by topic.
  var RELATED = {
    calc: ["What if my salary is ₹18 lakh?", "Which deductions are allowed in the new regime?", "What is the 87A rebate limit now?"],
    gst: ["What is the GST on a TV right now?", "What was GST on AC in August 2025?", "What is the GST on medicines?"],
    tax: ["Which tax regime is better for my ₹12 lakh salary?", "What is the 87A rebate limit now?", "Is 80C still available in the new Income-tax Act?"],
    refused: ["What is the standard deduction in the new regime?", "What is the GST on an AC right now?"],
  };

  // Status lines shown while the pipeline runs: [time in ms, text]. The backend does not stream,
  // so these follow the typical timing of the real steps (see the trace).
  var NARRATIVE = [
    [0, "Understanding your question"],
    [1500, "Finding the right law"],
    [4000, "Checking which dates apply"],
    [7500, "Reading the best passages"],
    [15000, "Writing the answer"],
  ];
  var HINGLISH_RE = /\b(naye|naya|nayi|mein|kitna|kitni|hai|kya|kaise|tha|mera|meri|mujhe|kaunsa|konsa|accha|behtar|purane|lagega|batao|milta|chahiye|kab|kitne|wala|wali)\b/i;

  var SIMPLE_REASONS = {
    out_of_scope: "This goes beyond the general income-tax and GST rules TaxSaathi covers, or it asks how to get around the law.",
    prompt_injection: "The question looked like it was trying to change TaxSaathi's rules.",
    low_retrieval_score: "TaxSaathi couldn't find an official passage that clearly answers this, and it would rather not guess.",
  };

  var ask = { config: "C6", messages: [], pending: false, seq: 0, followUpBase: null, autoTrace: false };
  TS.ask = ask;

  function initAsk() {
    var seg = $("#configSeg");
    seg.innerHTML = CONFIGS.map(function (c) {
      return '<button type="button" role="radio" data-value="' + c.name + '" aria-checked="' + (c.name === ask.config) + '" title="' + esc(c.desc) + '"><b>' + c.name + "</b><small>" + esc(c.short) + "</small></button>";
    }).join("");
    var setCfg = function (v, quiet) {
      ask.config = v;
      $$("button", seg).forEach(function (b) { b.setAttribute("aria-checked", b.getAttribute("data-value") === v ? "true" : "false"); });
      var c = CONFIGS.filter(function (x) { return x.name === v; })[0];
      $("#configDesc").innerHTML = c ? "<b>" + esc(c.name) + "</b> · " + esc(c.desc) : "";
      document.body.classList.toggle("cfg-nondefault", v !== "C6");
      var ac = $("#advCfg"); if (ac) { ac.textContent = v; ac.hidden = v === "C6"; }
      if (!quiet) toast(v === "C6" ? "Back to the final system (C6)" : "Now answering with " + v + ": " + (c ? c.short : ""), "ok");
    };
    seg.addEventListener("click", function (e) { var b = e.target.closest("button[data-value]"); if (b) setCfg(b.getAttribute("data-value")); });
    seg.addEventListener("keydown", function (e) {
      if (["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].indexOf(e.key) < 0) return;
      e.preventDefault();
      var i = CONFIGS.map(function (c) { return c.name; }).indexOf(ask.config);
      var n = CONFIGS[(i + (e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : CONFIGS.length - 1)) % CONFIGS.length].name;
      setCfg(n); var b = $('button[data-value="' + n + '"]', seg); if (b) b.focus();
    });
    setCfg(params.get("config") && CONFIG_STEPS[params.get("config").toUpperCase()] ? params.get("config").toUpperCase() : "C6", true);

    // Advanced popover
    var adv = $("#advPanel"), advBtn = $("#advBtn");
    var openAdv = function (on) {
      if (on) {
        var r = advBtn.getBoundingClientRect();
        adv.style.setProperty("--pop-top", Math.round(r.bottom + 10) + "px");
        adv.style.setProperty("--pop-right", Math.max(12, Math.round(window.innerWidth - r.right - 6)) + "px");
        adv.hidden = false; requestAnimationFrame(function () { adv.classList.add("in"); });
      }
      else { adv.classList.remove("in"); adv.hidden = true; }
      advBtn.setAttribute("aria-expanded", on ? "true" : "false");
      if (on) { renderAdvServer(); var f = $("button[aria-checked='true']", seg); if (f) f.focus(); }
    };
    advBtn.addEventListener("click", function () { openAdv(adv.hidden); });
    $("#advClose").addEventListener("click", function () { openAdv(false); advBtn.focus(); });
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      if (!adv.hidden) { openAdv(false); advBtn.focus(); return; }
      if (drawer.open) closeDrawer();
    });
    document.addEventListener("click", function (e) { if (!adv.hidden && !adv.contains(e.target) && !advBtn.contains(e.target)) openAdv(false); });
    $("#drawerClose").addEventListener("click", function () { closeDrawer(); });
    $("#scrim").addEventListener("click", function () { closeDrawer(); });
    var at = $("#autoTrace");
    try { ask.autoTrace = localStorage.getItem("ts.autoTrace") === "1"; } catch (e) { /* private mode */ }
    at.checked = ask.autoTrace;
    at.addEventListener("change", function () { ask.autoTrace = at.checked; try { localStorage.setItem("ts.autoTrace", at.checked ? "1" : "0"); } catch (e) { /* ignore */ } });
    var dl = $("#demoLink");
    if (state.mock && state.mockReason === "param") { dl.textContent = "Switch to the live server"; dl.href = location.pathname; }

    $("#exampleGrid").innerHTML = EXAMPLES.map(function (e, i) {
      return '<button type="button" class="example" style="--i:' + i + '" data-q="' + esc(e.q) + '">' + esc(e.q) + "</button>";
    }).join("");
    var rg = $("#realGrid");
    if (rg) rg.innerHTML = REAL_EXAMPLES.map(function (e, i) {
      return '<button type="button" class="real-q" style="--i:' + i + '" data-q="' + esc(e.q) + '"><span class="real-text">' + esc(e.q) + '</span><span class="real-src">' + esc(e.src) + "</span></button>";
    }).join("");
    $("#view-ask").addEventListener("click", function (e) {
      var b = e.target.closest("[data-q]");
      if (b && !ask.pending) { ask.followUpBase = null; sendAsk(b.getAttribute("data-q")); }
    });

    var input = $("#askInput");
    if (window.matchMedia) {
      var mq = matchMedia("(max-width: 640px)");
      var setPh = function () { input.placeholder = mq.matches ? "Ask a tax question" : "Ask a tax question in English or Hinglish"; };
      setPh(); if (mq.addEventListener) mq.addEventListener("change", setPh);
    }
    var grow = function () { input.style.height = "auto"; input.style.height = Math.min(180, input.scrollHeight) + "px"; $("#askForm").classList.toggle("has-text", !!input.value.trim()); };
    input.addEventListener("input", grow);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); submitMain(); }
    });
    var submitMain = function () {
      var v = input.value.trim();
      if (!v) { input.focus(); var cb = $(".composer-box"); cb.classList.remove("nudge"); void cb.offsetWidth; cb.classList.add("nudge"); return; }
      if (ask.pending) { toast("Still working on your last question", "warn"); return; }
      input.value = ""; grow();
      sendAsk(v);
    };
    $("#askForm").addEventListener("submit", function (e) { e.preventDefault(); submitMain(); });
    $("#clearChat").addEventListener("click", function () {
      if (ask.pending) return;
      ask.messages = []; ask.followUpBase = null;
      $("#messages").innerHTML = "";
      document.body.classList.remove("has-chat");
      closeDrawer(true);
      window.scrollTo({ top: 0 });
      input.focus();
    });

    // Delegated clicks inside answers
    $("#messages").addEventListener("click", function (e) {
      var msgEl = e.target.closest(".turn");
      if (!msgEl) return;
      var id = +msgEl.getAttribute("data-id");
      var m = findMsg(id);
      var src = e.target.closest("[data-cite]");
      if (src) { showSource(msgEl, m, src.getAttribute("data-cite"), src); return; }
      var cp = e.target.closest(".cite-calc");
      if (cp) { var cb = $(".calc-block", msgEl); if (cb) flashEl(cb); return; }
      var fb = e.target.closest("[data-vote]");
      if (fb) { sendFeedback(id, fb.getAttribute("data-vote"), msgEl); return; }
      if (e.target.closest(".copy-btn")) { copyAnswer(m, e.target.closest(".copy-btn")); return; }
      if (e.target.closest(".how-toggle")) { toggleHow(msgEl, m, false, e.target.closest(".how-toggle")); return; }
      if (e.target.closest(".open-calc")) { if (m && m.result && m.result.calculation && TS.showCalc) TS.showCalc(m.result.calculation); return; }
      if (e.target.closest(".retry")) {
        if (m) { msgEl.remove(); ask.messages = ask.messages.filter(function (x) { return x.id !== id; }); sendAsk(m.display, m.q); }
        return;
      }
    });
    // Inline reply box for "one more detail needed"
    $("#messages").addEventListener("submit", function (e) {
      var f = e.target.closest(".fu-form");
      if (!f) return;
      e.preventDefault();
      var inp = $("input", f), v = inp.value.trim();
      if (!v) { inp.focus(); return; }
      if (ask.pending) return;
      sendAsk(v);
    });

    // Trace drawer tools (delegated, the drawer body is re-rendered)
    $("#drawerBody").addEventListener("click", function (e) {
      var k = drawer.key || "";
      if (!/^trace:/.test(k)) return;
      var m = findMsg(+k.slice(6));
      if (e.target.closest(".how-replay")) { if (m && m.result) renderTrace($(".how-trace", $("#drawerBody")), m.result, { animate: true }); return; }
      var ex = e.target.closest(".how-expand");
      if (ex) {
        var heads = $$(".how-trace .step-head[aria-expanded]", $("#drawerBody"));
        var anyClosed = heads.some(function (h) { return h.getAttribute("aria-expanded") !== "true"; });
        heads.forEach(function (h) { if ((h.getAttribute("aria-expanded") === "true") !== anyClosed) h.click(); });
        ex.innerHTML = icon(anyClosed ? "collapse" : "expand") + (anyClosed ? "Collapse all" : "Expand all");
      }
    });

    var q = params.get("q");
    if (q) setTimeout(function () { sendAsk(q); }, 300);
  }

  function renderAdvServer() {
    var el = $("#advServer"), h = state.health || {};
    if (!el) return;
    el.innerHTML = '<div class="pop-label"><span>Server</span></div>' + kv([
      ["Mode", state.mock ? "Offline demo (saved samples)" : state.live ? "Live" : "Connecting…"],
      ["Language model", h.llm ? '<span class="mono">' + esc(h.llm) + "</span> on CPU" : null],
      ["Passages", h.chunks != null ? esc(inr(h.chunks, { noSymbol: true })) : null],
      ["Server date", h.today ? esc(fmtDate(h.today)) : null],
      ["Gate threshold", h.rerank_threshold != null ? '<span class="num">' + esc(Number(h.rerank_threshold).toFixed(2)) + "</span>" : null],
    ]);
  }

  function findMsg(id) { return ask.messages.filter(function (m) { return m.id === id; })[0]; }

  function scrollToEl(el) {
    if (!el) return;
    requestAnimationFrame(function () { el.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" }); });
  }

  function sendAsk(display, sendText) {
    if (ask.pending) return;
    display = String(display || "").trim();
    if (!display) return;
    var q = sendText || display;
    var combined = false;
    if (!sendText && ask.followUpBase) { q = ask.followUpBase + " " + display; combined = true; }
    ask.followUpBase = null;
    document.body.classList.add("has-chat");
    var msg = { id: ++ask.seq, q: q, display: display, config: ask.config, status: "pending", started: performance.now() };
    ask.messages.push(msg);
    var list = $("#messages");
    list.insertAdjacentHTML("beforeend",
      '<article class="turn pending" data-id="' + msg.id + '">' +
      '<h2 class="turn-q">' + esc(display) + "</h2>" +
      (combined ? '<p class="turn-combined">' + icon("corner") + "Added to your earlier question</p>" : "") +
      '<div class="turn-body">' + progressHtml(msg) + "</div></article>");
    // remove any open follow-up reply boxes: they have been answered
    $$(".fu-form", list).forEach(function (f) { f.remove(); });
    var el = $('.turn[data-id="' + msg.id + '"]');
    scrollToEl(el);
    setPending(true);
    var stopProgress = runProgress(el, msg);

    api("/ask", { body: { question: q, config: msg.config }, timeout: 180000 })
      .then(function (r) { msg.result = normalize(r); msg.status = "done"; })
      .catch(function (e) { msg.status = "error"; msg.error = (e && e.message) || "Request failed"; msg.timeout = !!(e && e.timeout); })
      .then(function () { return stopProgress(msg.status === "done"); })
      .then(function () {
        setPending(false);
        if (!el) return;
        el.classList.remove("pending");
        var body = $(".turn-body", el);
        try { body.innerHTML = answerHtml(msg); }
        catch (err) { console.error(err); msg.status = "error"; msg.error = "Couldn't display this answer (" + err.message + ")"; body.innerHTML = answerHtml(msg); }
        el.classList.add("arrive");
        revealAnswer(body);
        if (msg.status === "done") markLanded();
        if (msg.result && msg.result.follow_up) { ask.followUpBase = msg.q; var fi = $(".fu-form input", el); if (fi) setTimeout(function () { fi.focus({ preventScroll: true }); }, 50); }
        if (msg.status === "done" && ask.autoTrace) toggleHow(el, msg, true);
      });
  }

  // Answer lands: blocks, paragraphs and cards fade up in quick succession (< 600 ms total)
  function revealAnswer(body) {
    var units = [];
    Array.prototype.forEach.call(body.children, function (c) {
      if (c.classList.contains("prose")) {
        $$(":scope > p, :scope > ul > li", c).forEach(function (x) { units.push(x); });
      } else if (c.classList.contains("sources")) {
        units.push($(".eyebrow", c)); $$(".src-card", c).forEach(function (x) { units.push(x); });
      } else units.push(c);
    });
    reveal(units.filter(Boolean));
    animateNumbers(body);
  }
  TS.revealAnswer = revealAnswer;

  function setPending(on) {
    ask.pending = on;
    document.body.classList.toggle("thinking", on);
    $("#askSend").disabled = on;
    $("#view-ask").classList.toggle("is-pending", on);
    $$("#view-ask [data-q]").forEach(function (b) { b.disabled = on; });
  }

  function narrativeFor(msg) {
    if (msg.config === "B0") return [[0, "Asking the plain model, with no documents"], [6000, "Writing the answer"]];
    var n = NARRATIVE.slice();
    if (HINGLISH_RE.test(msg.q) && (msg.config === "C5" || msg.config === "C6")) n.splice(1, 0, [700, "Translating Hinglish to English"]);
    return n;
  }

  function progressHtml(msg) {
    var steps = narrativeFor(msg);
    return (
      '<div class="progress" role="status" aria-live="polite">' +
      '<div class="pg-line"><span class="pg-mark" aria-hidden="true">' + TS.markSvg("thinking") + '</span><span class="pg-text">' + esc(steps[0][1]) + '…</span><span class="pg-time num" aria-label="Seconds elapsed">0s</span></div>' +
      '<div class="pg-track" aria-hidden="true">' + steps.map(function () { return "<i></i>"; }).join("") + "<i></i></div>" +
      '<div class="sk-lines" aria-hidden="true"><span class="skeleton"></span><span class="skeleton"></span><span class="skeleton"></span><span class="skeleton short"></span></div>' +
      '<p class="pg-note">' + (msg.config === "B0" ? "This config skips the documents, so there will be no sources." : "Careful answers take 20–60 seconds. A small AI model runs on an ordinary CPU server.") + "</p>" +
      "</div>"
    );
  }

  // Drives the status line; returns stop(ok) -> Promise that resolves after the final tick
  function runProgress(el, msg) {
    var steps = narrativeFor(msg);
    var textEl = $(".pg-text", el), timeEl = $(".pg-time", el), dots = $$(".pg-track i", el);
    var cur = -1, t0 = msg.started, done = false, timer = null;
    var setText = function (txt) {
      textEl.classList.remove("swap"); void textEl.offsetWidth;
      textEl.textContent = txt; textEl.classList.add("swap");
    };
    var setCur = function (i) {
      if (i === cur) return;
      cur = i;
      setText(steps[i][1] + "…");
      dots.forEach(function (d, j) { d.classList.toggle("on", j <= i); });
    };
    var tick = function () {
      if (done) return;
      var t = performance.now() - t0, i = 0;
      steps.forEach(function (s, j) { if (t >= s[0]) i = j; });
      setCur(i);
      if (timeEl) timeEl.textContent = Math.floor(t / 1000) + "s";
      var note = $(".pg-note", el);
      if (t > 45000 && note && !note.classList.contains("slow")) { note.classList.add("slow"); note.textContent = "Still working. The server is busy right now; thanks for waiting."; }
      timer = setTimeout(tick, 250);
    };
    tick();
    return function (ok) {
      done = true; clearTimeout(timer);
      if (!ok) return Promise.resolve();
      setText("Verifying sources…");
      dots.forEach(function (d) { d.classList.add("on"); });
      return new Promise(function (r) { setTimeout(r, reducedMotion() ? 0 : 450); });
    };
  }

  /* ---------------- answer ---------------- */
  var LAW_NAMES = { new_act: "Income-tax Act, 2025", old_act: "Income-tax Act, 1961", gst: "GST law" };
  function periodOf(r) { return r.period || stepData(r.trace, "period"); }
  function lawApplied(r) {
    var per = periodOf(r);
    if (!per || !per.start) return null;
    var laws = [];
    (r.citations || []).forEach(function (c) { var l = inferLaw(c); if (LAW_NAMES[l] && laws.indexOf(l) < 0) laws.push(l); });
    if (r.calculation && r.calculation.law) {
      var cl = /1961/.test(r.calculation.law) ? "old_act" : /2025/.test(r.calculation.law) ? "new_act" : null;
      if (cl && laws.indexOf(cl) < 0) laws.push(cl);
    }
    var gstOnly = laws.length === 1 && laws[0] === "gst";
    var when;
    if (r.calculation && r.calculation.tax_year) {
      var ty = String(r.calculation.tax_year); var y = +ty.slice(0, 4);
      when = (y >= 2026 ? "Tax Year " : "FY ") + ty;
    } else if (per.assumed_current) when = gstOnly ? "Today, " + fmtDate(per.start) : yearOf(per.start);
    else when = periodLabel(per);
    var note = "";
    if (laws.indexOf("gst") >= 0) {
      var e = Date.parse(per.end || per.start), s = Date.parse(per.start), g2 = Date.parse("2025-09-22");
      if (e < g2) note = "before GST 2.0"; else if (s >= g2) note = "after GST 2.0";
    }
    if (!note && per.assumed_current) note = "current law";
    return { when: when, laws: laws.map(function (l) { return LAW_NAMES[l]; }), note: note, assumed: !!per.assumed_current };
  }
  TS.lawApplied = lawApplied;

  function metaRowHtml(r) {
    var la = lawApplied(r);
    var bits = [];
    if (la) {
      bits.push('<span class="meta-k">Law applied</span><span class="meta-strong">' + esc(la.when) + "</span>");
      if (la.laws.length) bits.push("<span>" + esc(la.laws.join(" + ")) + "</span>");
      if (la.note) bits.push("<span>" + esc(la.note) + "</span>");
    }
    if (!bits.length) return "";
    return '<div class="turn-meta" title="' + esc(la && la.assumed ? "No date in the question, so TaxSaathi used the law in force today." : "TaxSaathi found this date in your question and only used law in force then.") + '">' + icon("calendar") + bits.join('<span class="dot" aria-hidden="true"></span>') + "</div>";
  }

  function relatedFor(msg) {
    var r = msg.result || {}, q = msg.q || "";
    var key = r.refused ? "refused" : r.calculation ? "calc" : /\bgst\b/i.test(q + " " + (r.answer || "")) || (r.citations || []).some(function (c) { return inferLaw(c) === "gst"; }) ? "gst" : "tax";
    var asked = ask.messages.map(function (m) { return m.q.toLowerCase(); });
    return RELATED[key].filter(function (x) { return asked.indexOf(x.toLowerCase()) < 0; }).slice(0, 3);
  }

  function sourcesRow(r) {
    if (!r.citations.length) return "";
    return '<section class="sources" aria-label="Sources"><p class="eyebrow">Sources</p><div class="src-row">' + r.citations.map(function (c, i) {
      var p = citePeriod(c);
      return '<button type="button" class="src-card" data-cite="' + esc(c.id) + '" aria-label="Source ' + (i + 1) + ": " + esc(c.title || c.id) + '">' +
        '<span class="src-top"><span class="src-n">' + (i + 1) + '</span><span class="src-law">' + esc(citeLawLine(c)) + "</span></span>" +
        '<span class="src-title">' + esc(c.title || c.id) + "</span>" +
        (p.text ? '<span class="src-period' + (p.current ? "" : " old") + '">' + esc(p.text) + "</span>" : "") +
        "</button>";
    }).join("") + "</div></section>";
  }

  function answerHtml(msg) {
    if (msg.status === "error") {
      return '<div class="notice error-card">' + '<span class="notice-illo">' + TS.illo("offline") + "</span>" + '<div><p class="notice-title">' + (msg.timeout ? "That took too long" : "We couldn't get an answer") + "</p><p>" +
        esc(msg.timeout ? "The server is very busy right now. Please try again in a moment." : "The TaxSaathi server didn't respond properly. Please try again.") +
        '</p><p class="notice-detail">' + esc(msg.error) + '</p><div class="notice-actions"><button type="button" class="btn btn-primary btn-sm retry">' + icon("refresh") + "Try again</button>" +
        (state.mock ? "" : '<a class="btn btn-secondary btn-sm" href="?mock=1">Use offline demo</a>') + "</div></div></div>";
    }
    var r = msg.result;
    var html = "";
    if (r.refused) {
      html +=
        '<div class="ca-card">' + '<span class="ca-illo">' + TS.illo("ca") + "</span><div class=\"ca-main\">" +
        '<h3 class="ca-title">This needs a Chartered Accountant</h3>' +
        '<p class="ca-why">' + esc(r.refusal_reason ? SIMPLE_REASONS[r.refusal_reason] || reasonText(r.refusal_reason) : "TaxSaathi chose not to guess on this one.") + "</p>" +
        (r.answer ? '<div class="ca-answer prose">' + richText(r.answer, r.citations, "ask") + "</div>" : "") +
        '<div class="ca-next"><a class="btn btn-amber btn-sm" href="https://www.icai.org/" target="_blank" rel="noopener noreferrer">Find a CA on the ICAI website' + icon("arrowUpRight") + '</a><span>A CA can look at your full situation and documents.</span></div>' +
        "</div></div>";
    } else if (r.follow_up) {
      if (r.answer) html += '<div class="prose answer">' + richText(r.answer, r.citations, "ask") + "</div>";
      html +=
        '<div class="followup"><p class="fu-label">One more detail</p>' +
        '<div class="fu-q">' + richText(r.follow_up, [], "ask") + "</div>" +
        '<form class="fu-form" autocomplete="off"><input class="input" type="text" placeholder="e.g. 12 lakh" aria-label="Your reply" /><button type="submit" class="send-btn sm" aria-label="Send reply">' + icon("arrowUp") + "</button></form></div>";
    } else {
      html += metaRowHtml(r);
      var hasCalc = r.calculation && r.calculation.old && r.calculation["new"];
      var lastCalc = String(r.answer).lastIndexOf("[CALC]");
      if (hasCalc && lastCalc >= 0) {
        // Verdict first, then the explanation, with the exact calculator lines one tap away
        var working = String(r.answer).slice(0, lastCalc + 6), rest = String(r.answer).slice(lastCalc + 6).trim();
        html += calcBlock(r.calculation);
        if (rest) html += '<div class="prose answer">' + richText(rest, r.citations, "ask") + "</div>";
        html += '<details class="disclosure working"><summary><span>Show the working</span>' + icon("chevDown", "chev") + '</summary><div class="prose answer small">' + richText(working, r.citations, "ask") + "</div></details>";
      } else {
        html += '<div class="prose answer">' + richText(r.answer, r.citations, "ask") + "</div>";
        if (hasCalc) html += calcBlock(r.calculation);
      }
      if (r.config === "B0" || (!r.citations.length && !(r.calculation && /\[CALC\]/.test(r.answer))))
        html += '<p class="note warn">' + icon("info") + "No official source for this answer, so it can't be checked.</p>";
      html += sourcesRow(r);
    }

    var related = relatedFor(msg);
    var total = r.latency_ms;
    html +=
      '<div class="actions">' +
      '<button type="button" class="icon-btn copy-btn" aria-label="Copy answer" title="Copy answer">' + icon("copy") + "</button>" +
      '<button type="button" class="icon-btn fb-btn" data-vote="up" aria-label="Helpful" aria-pressed="false" title="Helpful">' + icon("thumbUp") + "</button>" +
      '<button type="button" class="icon-btn fb-btn" data-vote="down" aria-label="Not helpful" aria-pressed="false" title="Not helpful">' + icon("thumbDown") + "</button>" +
      '<span class="act-sep" aria-hidden="true"></span>' +
      '<button type="button" class="text-btn how-toggle" aria-expanded="false">' + icon("route") + "How this was found</button>" +
      '<span class="spacer"></span>' +
      '<span class="act-meta">' + (r.config && r.config !== "C6" ? '<span class="cfg-tag" title="Answered with pipeline config ' + esc(r.config) + '">' + esc(r.config) + "</span>" : "") + (total != null ? '<span class="num">' + esc(fmtMs(total)) + "</span>" : "") + "</span>" +
      "</div>" +
      (related.length ? '<section class="related" aria-label="Related questions"><p class="eyebrow">Related</p>' + related.map(function (x) { return '<button type="button" class="related-q" data-q="' + esc(x) + '"><span>' + esc(x) + "</span>" + icon("plus") + "</button>"; }).join("") + "</section>" : "") +
      (r.disclaimer ? '<p class="disclaimer">' + esc(r.disclaimer) + "</p>" : "");
    return html;
  }

  function setActiveCite(msgEl, id) {
    $$(".turn .cite.active, .turn .src-card.on", document).forEach(function (x) { x.classList.remove("active"); x.classList.remove("on"); });
    if (!msgEl || !id) return;
    $$("[data-cite]", msgEl).forEach(function (x) { if (x.getAttribute("data-cite") === id) x.classList.add(x.classList.contains("src-card") ? "on" : "active"); });
  }

  function showSource(msgEl, m, id, trigger) {
    if (!m || !m.result) return;
    var c = null, n = 0;
    m.result.citations.forEach(function (x, i) { if (x.id === id) { c = x; n = i; } });
    if (!c) return;
    var key = "src:" + m.id + ":" + id;
    if (drawer.open && drawer.key === key) { closeDrawer(); return; }
    var total = m.result.citations.length;
    openDrawer({
      key: key, trigger: trigger, kicker: "Source " + (n + 1) + " of " + total, title: "Official passage",
      html: sourceSheetHtml(c, n) + (total > 1 ? '<nav class="ss-nav" aria-label="Other sources">' + m.result.citations.map(function (x, i) {
        return '<button type="button" class="ss-nav-btn' + (i === n ? " on" : "") + '" data-goto="' + esc(x.id) + '" aria-label="Source ' + (i + 1) + '">' + (i + 1) + "</button>";
      }).join("") + "</nav>" : ""),
      onClose: function () { setActiveCite(null); },
      after: function (body) {
        setActiveCite(msgEl, id);
        $$("[data-goto]", body).forEach(function (b) { b.onclick = function () { showSource(msgEl, m, b.getAttribute("data-goto"), trigger); }; });
      },
    });
  }

  function toggleHow(msgEl, m, forceOpen, trigger) {
    if (!m || !m.result) return;
    var key = "trace:" + m.id;
    if (drawer.open && drawer.key === key && !forceOpen) { closeDrawer(); return; }
    var r = m.result;
    var total = r.latency_ms != null ? r.latency_ms : r.trace.reduce(function (a, s) { return a + (s.ms || 0); }, 0);
    var html =
      '<p class="trace-q">“' + esc(m.display) + "”</p>" +
      '<div class="trace-meta"><span class="cfg-tag' + ((r.config || m.config) === "C6" ? " final" : "") + '">' + esc(r.config || m.config) + "</span>" +
      "<span>" + esc((CONFIGS.filter(function (c) { return c.name === (r.config || m.config); })[0] || {}).short || "") + "</span>" +
      '<span class="dot" aria-hidden="true"></span><span>' + r.trace.length + " steps</span>" +
      '<span class="dot" aria-hidden="true"></span><span class="num">' + esc(fmtMs(total)) + "</span></div>" +
      '<div class="how-trace"></div>' +
      '<div class="how-tools"><button type="button" class="text-btn how-expand">' + icon("expand") + 'Expand all</button><button type="button" class="text-btn how-replay">' + icon("refresh") + "Replay</button></div>" +
      (r.citations.length ? '<section class="how-sources"><p class="eyebrow">Sources in full · ' + r.citations.length + "</p>" + r.citations.map(function (c, i) { return citeCardHtml(c, i, "ask"); }).join("") + "</section>" : "") +
      (r.retrieved && r.retrieved.length ? '<p class="how-retrieved"><span class="eyebrow">Top passages found</span>' + r.retrieved.slice(0, 6).map(function (x) { return "<code>" + esc(x) + "</code>"; }).join(" ") + "</p>" : "");
    var btn = $(".how-toggle", msgEl);
    openDrawer({
      key: key, wide: true, trigger: trigger || btn, kicker: "Pipeline trace", title: "How TaxSaathi found this", html: html,
      onClose: function () { if (btn) btn.setAttribute("aria-expanded", "false"); },
      after: function (body) {
        if (btn) btn.setAttribute("aria-expanded", "true");
        renderTrace($(".how-trace", body), r, { animate: true });
        wireCiteCards(body);
      },
    });
  }

  function plainAnswer(m) {
    var r = m.result || {};
    var txt = String(r.refused ? "This needs a Chartered Accountant. " + (r.answer || "") : r.follow_up ? r.follow_up : r.answer || "");
    var idx = {};
    (r.citations || []).forEach(function (c, i) { idx[c.id] = i + 1; });
    txt = txt.replace(/\s*\[CALC\]/g, "").replace(CITE_RE, function (mm, ids) {
      return ids.split(/\s*[,;]\s*/).map(function (id) { return idx[id] ? "[" + idx[id] + "]" : ""; }).join("");
    }).replace(/\*\*/g, "");
    var la = lawApplied(r);
    var out = "Q: " + m.display + "\n\n";
    if (r.calculation && r.calculation.old && r.calculation["new"]) out += calcVerdict(r.calculation) + "\n\n";
    out += txt.trim();
    if (la && !r.refused) out += "\n\nLaw applied: " + la.when + (la.laws.length ? " (" + la.laws.join(" + ") + ")" : "");
    if (r.citations && r.citations.length) out += "\n\nSources:\n" + r.citations.map(function (c, i) { return "[" + (i + 1) + "] " + (c.title || c.id) + (c.source_url ? " — " + c.source_url : ""); }).join("\n");
    return out + "\n\n(TaxSaathi)";
  }
  function copyAnswer(m, btn) {
    if (!m || !m.result) return;
    var text = plainAnswer(m);
    var ok = function () { btn.classList.add("done"); btn.innerHTML = icon("check"); toast("Answer copied", "ok"); setTimeout(function () { btn.classList.remove("done"); btn.innerHTML = icon("copy"); }, 1600); };
    var fallback = function () {
      var ta = document.createElement("textarea");
      ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      var done = false; try { done = document.execCommand("copy"); } catch (e) { done = false; }
      document.body.removeChild(ta);
      if (done) ok(); else toast("Couldn't copy. Please select the text instead.", "warn");
    };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(ok, fallback);
    else fallback();
  }

  // Used by the Compare view: show an existing result in the Ask view with its full trace
  TS.injectAsk = function (q, result) {
    TS.go("ask");
    if (ask.pending || !result) return;
    document.body.classList.add("has-chat");
    var msg = { id: ++ask.seq, q: q, display: q, config: result.config || "C6", status: "done", result: normalize(result), started: performance.now() };
    ask.messages.push(msg);
    $("#messages").insertAdjacentHTML("beforeend",
      '<article class="turn arrive" data-id="' + msg.id + '"><h2 class="turn-q">' + esc(q) + '</h2><div class="turn-body">' + answerHtml(msg) + "</div></article>");
    var el = $('.turn[data-id="' + msg.id + '"]');
    revealAnswer($(".turn-body", el));
    scrollToEl(el);
    setTimeout(function () { toggleHow(el, msg, true); }, 60);
  };

  function sendFeedback(id, vote, msgEl) {
    var m = findMsg(id);
    if (!m || !m.result) return;
    $$(".fb-btn", msgEl).forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-vote") === vote); b.setAttribute("aria-pressed", b.getAttribute("data-vote") === vote ? "true" : "false"); });
    api("/feedback", { body: { question: m.q, answer: m.result.answer || m.result.follow_up || "", vote: vote, config: m.result.config || m.config }, timeout: 20000 })
      .then(function () { toast(vote === "up" ? "Thanks for the feedback" : "Thanks. We'll use this to improve.", "ok"); })
      .catch(function () { toast("Couldn't save feedback", "warn"); });
  }

  /* ================================================================== */
  /* Boot                                                                */
  /* ================================================================== */
  TS.$ = $; TS.$$ = $$; TS.esc = esc; TS.inr = inr; TS.lakhWords = lakhWords; TS.fmtDate = fmtDate; TS.fmtMs = fmtMs; TS.pct = pct;
  TS.toast = toast; TS.debounce = debounce; TS.inferLaw = inferLaw; TS.LAW_LABEL = LAW_LABEL; TS.stepData = stepData; TS.kv = kv;

  document.addEventListener("DOMContentLoaded", function () {
    renderBanner();
    state.probe = refreshHealth();
    initAsk();
    if (TS.initViews) { try { TS.initViews(); } catch (e) { console.error(e); } }
    initRouter();
  });
})();
