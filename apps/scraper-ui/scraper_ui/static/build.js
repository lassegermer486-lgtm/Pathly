/* Registry-Build view — plain JavaScript, no build step.
 *
 * Shows the scraper's own pipeline (python -m registry.pipeline). Every
 * number comes from /api/build/state, which reads the pipeline's report
 * files; the page only arranges them. The live feed is the pipeline output,
 * sorted into step > source/institution > result.
 */
(function () {
  "use strict";

  const CLI_STEPS = [
    ["discovery", "1 · Deutsche Discovery"],
    ["international", "2 · Internationale Discovery"],
    ["websites", "3 · Website-Prüfung (deutsch)"],
    ["websites_intl", "3 · Website-Prüfung (international)"],
    ["agent", "4 · Agent (deutsch)"],
    ["agent_intl", "4 · Agent (international)"],
    ["dedup", "5 · Deduplizierung"],
    ["master", "6–8 · Master, Präsenz, Online-DE"],
    ["supabase", "9 · Supabase-Export"],
  ];
  const BUILD_STATUS = {
    complete: "COMPLETE", review: "REVIEW", degraded: "DEGRADED", failed: "FAILED", unknown: "–",
  };
  const COUNT_STATUS = {
    normal: "normal", suspicious: "Drift", no_baseline: "neu", source_failed: "–", not_run: "–",
  };

  let view = "pipeline";
  let since = 0;
  let rawSince = 0;
  let events = [];
  let raw = [];
  let last = null;
  let timer = null;
  const openGroups = new Set();

  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function setHTML(el, html) {
    if (el.__html !== html) { el.innerHTML = html; el.__html = html; }
  }

  async function api(path, body) {
    const opts = body === undefined ? {} : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    };
    const res = await fetch(path, opts);
    let payload = null;
    try { payload = await res.json(); } catch (e) { /* no body */ }
    if (!res.ok) {
      const d = payload && payload.detail;
      throw new Error(typeof d === "string" ? d : "Anfrage fehlgeschlagen (" + res.status + ").");
    }
    return payload;
  }

  function notice(text) { $("notice").textContent = text || ""; $("notice").hidden = !text; }

  function clock(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }
  function when(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleDateString("de-DE") + " " + d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  }
  const host = (url) => { try { return new URL(url).hostname.replace(/^www\./, ""); } catch (e) { return url; } };

  // ------------------------------------------------------------ status bar

  function renderStatus(o, p) {
    const h = o.header;
    const cell = (lbl, num, sub, cls) => '<div class="bs ' + (cls || "") + '"><div class="lbl">' + esc(lbl) +
      '</div><div class="num">' + esc(num) + '</div><div class="sub">' + esc(sub || " ") + "</div></div>";
    const statusCls = { complete: "ok", review: "warn", degraded: "err", failed: "err" }[h.build_status] || "";
    const safe = h.production_safe === true ? "JA" : h.production_safe === false ? "NEIN" : "–";
    const ids = h.stable_ids;
    setHTML($("build-status"), [
      p.running ? cell("Build", "LÄUFT", (stepLabel(p.step) || "startet …"), "run")
        : cell("Build-Status", BUILD_STATUS[h.build_status] || h.build_status, "laut build_status.json", statusCls),
      cell("Production safe", safe, ids ? ids.kept + "/" + ids.existing + " IDs erhalten" : "", h.production_safe ? "ok" : (h.production_safe === false ? "err" : "")),
      cell("Quellen", h.sources_ok + " / " + h.sources_total, h.errors ? h.errors + " fehlgeschlagen" : "16 Länder + international", h.errors ? "err" : (h.sources_total ? "ok" : "")),
      cell("Hochschulen", h.institutions == null ? "–" : h.institutions, "im Master-Register"),
      cell("Review", h.review, "+ " + h.online_de_candidates + " Online-DE-Kandidaten", h.review ? "warn" : ""),
      cell("Drift", h.drift, h.drift ? "nicht bestätigt" : "keine", h.drift ? "warn" : ""),
      cell("Fehler", h.errors + (p.exit_code && p.exit_code !== 0 ? 1 : 0),
        p.exit_code && p.exit_code !== 0 ? "letzter Build: Exit " + p.exit_code : "", (h.errors || (p.exit_code && p.exit_code !== 0)) ? "err" : ""),
    ].join(""));
  }

  function stepLabel(cli) {
    const s = CLI_STEPS.find((x) => x[0] === cli);
    return s ? s[1] : cli;
  }

  // -------------------------------------------------------------- pipeline

  function renderSteps(o, p, live) {
    const lastLive = {};
    events.forEach((e) => { if (e.step && e.level !== "step") lastLive[e.step] = e.text; });
    const cliFor = { german_discovery: ["discovery"], international_discovery: ["international"],
      websites: ["websites", "websites_intl"], agent: ["agent", "agent_intl"], dedup: ["dedup"],
      presence: ["master"], online_de: ["master"], master: ["master"], supabase: ["supabase"] };

    setHTML($("steps"), o.steps.map((s) => {
      let status = s.status;
      const l = live[s.id];
      const older = p.started_at && s.generated_at && s.generated_at < p.started_at;
      if (l === "running") status = "running";
      else if (l === "waiting") status = "waiting";
      let whenTxt = s.generated_at ? when(s.generated_at) : "noch nicht gelaufen";
      if (older && l) whenTxt = "aus vorherigem Lauf · " + whenTxt;
      if (s.stale) whenTxt = "älter als der vorherige Schritt · " + whenTxt;
      const liveLine = status === "running"
        ? (cliFor[s.id] || []).map((c) => lastLive[c]).filter(Boolean).pop() : null;
      return '<li class="stepc ' + esc(status) + '"><div class="h"><span class="t">' + s.number + ". " + esc(s.title) +
        '</span><span class="when' + (s.stale ? " stale" : "") + '">' + esc(whenTxt) + "</span></div>" +
        (liveLine ? '<div class="live">' + esc(liveLine) + "</div>" : "") +
        (s.lines.length ? "<dl>" + s.lines.map((ln) => "<dt>" + esc(ln[0]) + "</dt><dd>" + esc(ln[1]) + "</dd>").join("") + "</dl>" : "") +
        "</li>";
    }).join(""));
  }

  function renderFeed(p) {
    const el = $("feed");
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    const shown = events.slice(-600);
    setHTML(el, shown.length ? shown.map((e) =>
      '<li class="' + esc(e.level) + '"><span class="tm">' + esc(clock(e.time)) + '</span><span class="tx">' +
      esc(e.text) + "</span></li>").join("")
      : '<li><span class="empty">Noch kein Build in dieser Sitzung. Die Kacheln links zeigen den Stand der letzten Reports.</span></li>');
    if (atBottom || p.running) el.scrollTop = el.scrollHeight;
    $("feed-state").textContent = p.running ? "· läuft seit " + clock(p.started_at)
      : p.finished_at ? "· beendet " + clock(p.finished_at) + (p.exit_code === 0 ? "" : " (Exit " + p.exit_code + ")") : "";
  }

  // --------------------------------------------------------------- sources

  function renderSources(o) {
    const rows = o.sources;
    $("n-sources").textContent = rows.length ? " " + rows.filter((r) => r.source_status === "success").length + "/" + rows.length : "";
    if (!rows.length) { setHTML($("view-sources"), '<p class="empty">Noch keine Quellen-Reports.</p>'); return; }
    const pct = (v) => (v == null ? "" : (v * 100).toFixed(1).replace(".", ",") + " %");
    const status = (r) => {
      if (r.source_status === "success") return '<span class="st-ok">erfolgreich</span>';
      if (r.source_status === "failed") return '<span class="st-err">fehlgeschlagen</span>' + (r.failure_reason ? '<div class="rs">' + esc(r.failure_reason) + "</div>" : "");
      return esc(r.source_status || r.status || "–");
    };
    const drift = (r) => {
      const t = COUNT_STATUS[r.count_status] || r.count_status || "–";
      if (r.count_status === "suspicious") return '<span class="st-warn">' + esc(t) + (r.drift_accepted ? " (bestätigt)" : "") + "</span>";
      return esc(t);
    };
    setHTML($("view-sources"),
      '<table class="list"><thead><tr><th style="width:110px">Quelle</th><th>Name</th><th style="width:150px">Status</th>' +
      '<th class="num" style="width:80px">vorher</th><th class="num" style="width:80px">jetzt</th><th class="num" style="width:90px">Δ</th>' +
      '<th style="width:90px">Drift</th><th class="num" style="width:110px">Requests</th></tr></thead><tbody>' +
      rows.map((r) => "<tr><td>" + esc(r.state) + "</td><td>" + esc(r.name || "") + "</td><td>" + status(r) +
        '</td><td class="num">' + esc(r.previous_count == null ? "–" : r.previous_count) +
        '</td><td class="num">' + esc(r.current_count == null ? "–" : r.current_count) +
        '</td><td class="num">' + (r.absolute_delta == null ? "–" : esc((r.absolute_delta > 0 ? "+" : "") + r.absolute_delta) + '<div class="rs">' + pct(r.relative_delta) + "</div>") +
        "</td><td>" + drift(r) + '</td><td class="num">' +
        esc(r.request_attempts == null ? "–" : r.request_attempts + (r.request_retries ? " (" + r.request_retries + " Retries)" : "")) +
        "</td></tr>").join("") + "</tbody></table>");
  }

  // --------------------------------------------------------------- reviews

  function renderReviews(o) {
    const groups = o.reviews;
    $("n-reviews").textContent = " " + o.header.review;
    setHTML($("view-reviews"), groups.map((g) => {
      const n = g.items.length;
      const items = n ? '<ul class="ritems">' + g.items.slice(0, 300).map((it) =>
        '<li><div class="rn">' + esc(it.title) + "</div>" +
        (it.subtitle || it.url ? '<div class="rs">' + esc(it.subtitle || "") +
          (it.url ? (it.subtitle ? " · " : "") + '<a href="' + esc(it.url) + '" target="_blank" rel="noopener">' + esc(host(it.url)) + "</a>" : "") + "</div>" : "") +
        '<div class="chips">' + (it.reasons || []).filter(Boolean).map((r) => '<span class="chip">' + esc(r) + "</span>").join("") + "</div></li>").join("") +
        (n > 300 ? '<li class="rs">… und ' + (n - 300) + " weitere</li>" : "") + "</ul>" : "";
      return '<details class="rgroup" data-group="' + esc(g.id) + '"' + (openGroups.has(g.id) ? " open" : "") + ">" +
        '<summary><span class="rt">' + esc(g.title) + '</span><span class="rc ' + (n ? "some" : "zero") + '">' + n + "</span></summary>" +
        '<p class="why">' + esc(g.explanation) + "</p>" + items + "</details>";
    }).join(""));
  }

  // ------------------------------------------------------------------- log

  function renderLog() {
    const el = $("rawlog");
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    el.textContent = raw.length ? raw.join("\n") : "Noch keine Ausgabe in dieser Sitzung.";
    if (atBottom) el.scrollTop = el.scrollHeight;
  }

  function renderFoot(o) {
    const known = Object.entries(o.reports).filter((e) => e[1]);
    $("reports-foot").textContent = known.length
      ? "Quelle der Angaben: " + known.length + " Report-Dateien in data/reports (Stand je Schritt in den Kacheln)."
      : "Noch keine Reports vorhanden.";
  }

  // -------------------------------------------------------------- controls

  function renderControls(p) {
    const btn = $("btn-build");
    btn.textContent = p.running ? "Abbrechen" : "Build starten";
    btn.classList.toggle("primary", !p.running);
    $("btn-build-options").disabled = p.running;
    const from = $("opt-from").value, to = $("opt-to").value;
    $("opt-command").textContent = "python -m registry.pipeline --from " + from + " --to " + to +
      ($("opt-agent-api").checked ? "" : " --agent-cache-only");
    $("build-meta").textContent = p.running
      ? "Build läuft seit " + clock(p.started_at) + " · " + (stepLabel(p.step) || "")
      : (p.finished_at ? "Letzter Build in dieser Sitzung: " + when(p.finished_at) + (p.exit_code === 0 ? " · erfolgreich" : " · Exit " + p.exit_code) + ". "
        : "") + "Alle Angaben stammen aus den Reports der Pipeline (data/reports).";
  }

  // -------------------------------------------------------------- polling

  async function poll() {
    try {
      const s = await api("/api/build/state?since=" + since + "&raw_since=" + rawSince);
      const p = s.process;
      if (p.started_at && last && last.process.started_at !== p.started_at) { events = []; raw = []; }
      events = events.concat(p.events).slice(-5000);
      raw = raw.concat(p.raw).slice(-20000);
      since = p.events_next; rawSince = p.raw_next;
      last = s;
      renderStatus(s.overview, p);
      renderSteps(s.overview, p, s.live || {});
      renderFeed(p);
      renderSources(s.overview);
      renderReviews(s.overview);
      if (view === "log") renderLog();
      renderFoot(s.overview);
      renderControls(p);
    } catch (e) {
      notice("Verbindung zur UI unterbrochen: " + e.message);
    }
    clearTimeout(timer);
    timer = setTimeout(poll, last && last.process.running ? 1000 : 4000);
  }

  // --------------------------------------------------------------- events

  function init() {
    CLI_STEPS.forEach((s, i) => {
      $("opt-from").insertAdjacentHTML("beforeend", '<option value="' + s[0] + '">' + esc(s[1]) + "</option>");
      $("opt-to").insertAdjacentHTML("beforeend", '<option value="' + s[0] + '"' + (i === CLI_STEPS.length - 1 ? " selected" : "") + ">" + esc(s[1]) + "</option>");
    });
    ["opt-from", "opt-to", "opt-agent-api"].forEach((id) => $(id).addEventListener("change", () => last && renderControls(last.process)));

    $("btn-build-options").addEventListener("click", () => {
      const el = $("build-options");
      el.hidden = !el.hidden;
      $("btn-build-options").setAttribute("aria-expanded", String(!el.hidden));
    });

    $("btn-build").addEventListener("click", async () => {
      notice("");
      try {
        if (last && last.process.running) {
          if (!confirm("Laufenden Build abbrechen? Bereits geschriebene Dateien bleiben, wie sie sind.")) return;
          await api("/api/build/cancel", {});
        } else {
          const agentApi = $("opt-agent-api").checked;
          if (agentApi && !confirm("Der Agent fragt dann für offene Fälle die API (OpenRouter) an. Das kostet Guthaben. Fortfahren?")) return;
          await api("/api/build/start", { start: $("opt-from").value, stop: $("opt-to").value, agent_api: agentApi });
          events = []; raw = [];
        }
        poll();
      } catch (e) { notice(e.message); }
    });

    document.querySelectorAll(".tab[data-view]").forEach((t) => t.addEventListener("click", () => {
      view = t.dataset.view;
      document.querySelectorAll(".tab[data-view]").forEach((x) => x.setAttribute("aria-selected", String(x === t)));
      ["pipeline", "sources", "reviews", "log"].forEach((v) => { $("view-" + v).hidden = v !== view; });
      if (view === "log") renderLog();
    }));

    $("view-reviews").addEventListener("toggle", (e) => {
      const g = e.target.dataset && e.target.dataset.group;
      if (!g) return;
      if (e.target.open) openGroups.add(g); else openGroups.delete(g);
    }, true);

    poll();
  }

  init();
})();
