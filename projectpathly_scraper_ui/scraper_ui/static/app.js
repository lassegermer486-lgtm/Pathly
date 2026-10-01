/* Scraper UI — plain JavaScript, no build step.
 *
 * The page polls /api/state (light) and reloads /api/records (heavy) only when
 * the data version changes. All rendering is tolerant of unknown values and
 * unknown fields, so a newer scraper version shows up without code changes:
 * unknown codes are printed as they are, unknown fields land under
 * "Weitere Felder".
 */
(function () {
  "use strict";

  // ---------------------------------------------------------------- labels

  const TYPE = {
    university: "Universität",
    university_of_applied_sciences: "HAW",
    art_music_university: "Kunst und Musik",
    art_music: "Kunst und Musik",
    university_of_education: "Pädagogische Hochschule",
    public_administration: "Verwaltung",
    university_of_public_administration: "Verwaltung",
    dual_university: "Duale Hochschule",
    theological_university: "Theologische Hochschule",
    theological: "Theologische Hochschule",
    other: "Sonstige",
    unknown: "unbekannt",
  };
  const OWNER = {
    public: "öffentlich", private: "privat", church: "kirchlich", federal: "Bund",
    private_or_church: "privat oder kirchlich", private_or_other: "privat oder andere",
    other: "andere", unknown: "unbekannt",
  };
  const RECOG = {
    public_by_law: "staatlich", state_recognized: "staatlich anerkannt",
    other_recognized: "anderweitig anerkannt", unknown: "unbekannt",
  };
  const LOCTYPE = {
    main: "Hauptstandort", campus: "Campus", branch: "Nebenstandort",
    department: "Fachbereich", study_location: "Studienort",
  };
  const FLAG = {
    missing_official_url: "Website fehlt",
    institution_type_unknown: "Typ unbekannt",
    ownership_unresolved: "Trägerschaft offen",
    recognition_unverified: "Anerkennung offen",
    possibly_dependent_unit: "evtl. Außenstelle",
    possibly_not_a_hochschule: "evtl. keine Hochschule",
    name_without_hochschule_term: "Name ohne Hochschulbegriff",
    lifecycle_hint_in_name: "Hinweis auf Umbenennung/Schließung",
    root_domain_shared: "Domain geteilt",
    merge_institution_type_conflict: "Quellen widersprechen sich (Typ)",
    merge_ownership_conflict: "Quellen widersprechen sich (Träger)",
    merge_recognition_status_conflict: "Quellen widersprechen sich (Anerkennung)",
    website_unreachable: "Website nicht erreichbar",
    website_tls_error: "Website: Zertifikatsfehler",
    website_blocked_bot_protection: "Website blockt Abruf",
    website_redirects_to_other_domain: "Website leitet auf andere Domain",
    lifecycle_text_on_website: "Website nennt Umbenennung/Schließung",
  };
  const SIGNAL = {
    domain_exact: "gleiche Website",
    domain_root: "gleiche Hauptdomain",
    name_identical: "identischer Name",
    name_variant: "Name bis auf Ortszusatz gleich",
    address_overlap: "gleiche Adresse",
    domain_conflict: "verschiedene Websites",
  };
  const SEVERITY_RANK = { high: 0, medium: 1, low: 2 };
  const KNOWN_FIELDS = new Set([
    "name", "name_variants", "country", "institution_type", "ownership", "recognition_status",
    "official_url", "states", "listed_by", "locations", "sources", "source", "merged_from",
    "merge_flags", "validation_flags", "university_id", "lifecycle_status", "state",
    "_review_open",
  ]);

  const label = (map, v) => (v == null || v === "" ? "–" : map[v] || String(v));

  // ----------------------------------------------------------------- state

  let meta = null;        // /api/meta
  let st = null;          // /api/state
  let data = { version: -1, rows: [], review: [], dedup: null };
  let logLines = [];
  let logNext = 0;
  let activeTab = "all";
  let search = "";
  let onlyFlags = false;
  const openRows = new Set();
  let pollTimer = null;

  const $ = (id) => document.getElementById(id);

  // ------------------------------------------------------------- utilities

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
      const detail = payload && payload.detail;
      const err = new Error(typeof detail === "string" ? detail : "Anfrage fehlgeschlagen (" + res.status + ").");
      err.status = res.status;
      throw err;
    }
    return payload;
  }

  function notice(text) {
    const el = $("notice");
    el.textContent = text || "";
    el.hidden = !text;
  }

  const short = (code) => {
    const s = meta && meta.states.find((x) => x.code === code);
    return s ? s.short : (code || "?");
  };
  const stateName = (code) => {
    const s = meta && meta.states.find((x) => x.code === code);
    return s ? s.name : (code || "?");
  };

  function host(url) {
    if (!url) return "";
    try { return new URL(url).hostname.replace(/^www\./, ""); } catch (e) { return url; }
  }

  function fmtTime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleDateString("de-DE") + ", " + d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  }

  const plural = (n, one, many) => n + " " + (n === 1 ? one : many);
  const listedBy = (m) => (m.listed_by && m.listed_by.length ? m.listed_by : (m.state ? [m.state] : []));
  const sourcesOf = (m) => (m.sources && m.sources.length ? m.sources : (m.source ? [m.source] : []));

  function cities(m) {
    const set = [];
    (m.locations || []).forEach((l) => { if (l.city && !set.includes(l.city)) set.push(l.city); });
    return set;
  }

  function sortedFlags(m) {
    return (m.validation_flags || []).slice().sort(
      (a, b) => (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9));
  }

  // ---------------------------------------------------------------- header

  function renderHeader() {
    const busy = st.busy;
    const hasData = !!st.kpis;
    const open = hasData ? st.kpis.review_open : 0;

    const start = $("btn-start");
    if (st.phase === "fetching" && st.source !== "file") {
      start.textContent = "Abbrechen"; start.disabled = false; start.dataset.mode = "cancel";
    } else if (busy) {
      start.textContent = "Läuft …"; start.disabled = true; start.dataset.mode = "busy";
    } else {
      start.textContent = hasData ? "Neu abrufen" : "Abruf starten";
      start.disabled = false; start.dataset.mode = "start";
    }
    start.classList.toggle("primary", !busy && !hasData);

    const load = $("btn-load");
    load.hidden = !(meta.capabilities.last_scrape_available);
    load.disabled = busy;

    const canSave = !busy && hasData && open === 0 && !st.conflicts.length && st.phase !== "saved";
    const save = $("btn-save");
    save.disabled = !canSave;
    save.classList.toggle("primary", st.phase === "ready" && canSave);

    let hint = "";
    if (!busy && hasData) {
      if (open) hint = plural(open, "Duplikat offen", "Duplikate offen");
      else if (st.conflicts.length) hint = "Entscheidungen widersprechen sich";
    }
    $("save-hint").textContent = hint;

    const next = $("btn-next");
    next.hidden = !(st.phase === "review" && activeTab !== "review");

    $("btn-download").hidden = !(hasData && !busy && open === 0 && (st.phase === "ready" || st.phase === "saved"));

    let m = "Noch kein Abruf in dieser Sitzung";
    if (st.started_at) {
      const src = st.source === "file" ? "aus gespeichertem Abruf geladen" : "live abgerufen";
      m = st.finished_at
        ? "Letzter Abruf " + fmtTime(st.finished_at) + " · " + (st.duration != null ? String(st.duration).replace(".", ",") + " s · " : "") + src
        : "Abruf läuft seit " + fmtTime(st.started_at);
    }
    $("run-meta").textContent = m;
  }

  // ---------------------------------------------------------------- phases

  function renderPhases() {
    const k = st.kpis;
    const order = { idle: 0, fetching: 1, matching: 2, checking: 3, review: 4, ready: 5, saved: 6 };
    const pos = st.phase === "error" ? 0 : order[st.phase] || 0;
    const sel = st.selected.length;
    const finished = st.selected.filter((c) => ["ok", "error", "skipped"].includes((st.states[c] || {}).status)).length;
    const failed = st.failed_states.length;

    const steps = [];
    // 1 Abrufen
    if (st.phase === "error") steps.push(["failed", "abgebrochen"]);
    else if (pos === 0) steps.push(["pending", "noch nicht gestartet"]);
    else if (pos === 1) steps.push(["active", st.source === "file" ? "lädt Datei" : finished + " von " + sel + " Ländern"]);
    else steps.push([failed ? "failed" : "done", (k ? k.states_ok : sel - failed) + " von " + sel + " Ländern"]);
    // 2 Abgleichen
    if (pos < 2) steps.push(["pending", "–"]);
    else if (pos === 2) steps.push(["active", "läuft"]);
    else steps.push(["done", data.dedup === false ? "in dieser Version nicht verfügbar" : (k ? k.merged_away + " zusammengeführt" : "fertig")]);
    // 3 Prüfen
    if (pos < 3) steps.push(["pending", "–"]);
    else if (pos === 3) steps.push(["active", "läuft"]);
    else steps.push(["done", k ? k.with_flags + " mit Hinweisen" : "fertig"]);
    // 4 Entscheiden
    if (pos < 4) steps.push(["pending", "–"]);
    else if (k && k.review_open) steps.push(["attention", k.review_open + " offen"]);
    else steps.push(["done", k && k.review_decided ? k.review_decided + " entschieden" : "nichts offen"]);
    // 5 Speichern
    if (pos === 6) steps.push(["done", "gespeichert " + (st.saved ? fmtTime(st.saved.at).split(", ")[1] : "")]);
    else if (pos === 5 && !st.conflicts.length) steps.push(["active", "bereit"]);
    else if (pos >= 4) steps.push(["pending", "gesperrt"]);
    else steps.push(["pending", "–"]);

    const names = ["Abrufen", "Abgleichen", "Prüfen", "Entscheiden", "Speichern"];
    setHTML($("phases"), steps.map((s, i) =>
      '<div class="phase ' + s[0] + '"><div class="step">' + (i + 1) + " · " + names[i] +
      '</div><div class="val">' + esc(s[1]) + "</div></div>").join(""));
  }

  function renderStatus() {
    let text = st.message ||
      "Mit „Abruf starten“ werden die Hochschullisten der 16 Bundesländer abgerufen. Das dauert etwa eine Minute.";
    if (st.error) text += " " + st.error;
    if (st.conflicts.length) {
      text += " Widerspruch: " + st.conflicts.map((c) => c.a + " und " + c.b).join("; ") +
        " sollen getrennt bleiben, werden aber über andere Zusammenführungen vereint.";
    }
    if (st.phase === "saved" && st.saved) {
      text = "Gespeichert: " + st.saved.files.join(", ") + (st.saved.complete ? "" : " (unvollständiger Stand)");
    }
    $("status-text").textContent = text;
  }

  // ------------------------------------------------------------------ KPIs

  function renderKpis() {
    const k = st.kpis;
    const cell = (lbl, num, sub, cls) =>
      '<div class="kpi ' + (cls || "") + '"><div class="lbl">' + esc(lbl) + '</div><div class="num">' +
      esc(num) + '</div><div class="sub">' + esc(sub || " ") + "</div></div>";
    if (!k) {
      setHTML($("kpis"), ["Länder", "Landeseinträge", "Hochschulen", "Standorte", "Duplikate offen", "Ohne Website"]
        .map((l) => cell(l, "–")).join(""));
      return;
    }
    const failed = st.failed_states.length;
    setHTML($("kpis"), [
      cell("Länder", k.states_ok + "/" + k.states_total, failed ? plural(failed, "Fehler", "Fehler") : "erfolgreich", failed ? "err" : ""),
      cell("Landeseinträge", k.state_records, "aus den Landesquellen"),
      cell("Hochschulen", k.institutions, data.dedup === false ? "ohne Abgleich" : k.merged_away + " zusammengeführt"),
      cell("Standorte", k.locations, k.multi_state ? k.multi_state + " in mehreren Ländern" : ""),
      cell("Duplikate offen", k.review_open, k.auto_merge_pairs + " automatisch gelöst", k.review_open ? "warn" : ""),
      cell("Ohne Website", k.missing_url, k.with_flags + " mit Hinweisen"),
    ].join(""));
  }

  // ------------------------------------------------------------------ tabs

  function rowsFor(tab) {
    if (tab === "all") return data.rows;
    return data.rows.filter((m) => listedBy(m).includes(tab));
  }

  function renderTabs() {
    const tab = (id, text, n, cls) =>
      '<button class="tab ' + (cls || "") + '" role="tab" type="button" data-tab="' + esc(id) +
      '" aria-selected="' + (activeTab === id) + '">' + esc(text) +
      (n !== "" && n != null ? '<span class="n">' + esc(n) + "</span>" : "") + "</button>";

    const parts = [tab("all", "Gesamt", st.kpis ? st.kpis.institutions : "")];
    meta.states.forEach((s) => {
      const info = st.states[s.code];
      let n = "", cls = "";
      if (info) {
        if (info.status === "running") { n = "läuft"; cls = "running"; }
        else if (info.status === "error") { n = "Fehler"; cls = "error"; }
        else if (info.status === "ok") n = rowsFor(s.code).length || info.universities || 0;
        else if (info.status === "waiting") n = "…";
      }
      parts.push(tab(s.code, s.short, n, cls));
    });
    const open = st.kpis ? st.kpis.review_open : 0;
    parts.push(tab("review", "Duplikate", st.kpis ? open : "", "review" + (open ? " open" : "")));
    setHTML($("tabs"), parts.join(""));
  }

  // ----------------------------------------------------------------- table

  function matches(m) {
    if (onlyFlags && !(m.validation_flags && m.validation_flags.length) && !m._review_open) return false;
    if (!search) return true;
    const hay = [m.name, m.official_url, m.university_id].concat(m.name_variants || [], cities(m)).join(" ").toLowerCase();
    return hay.includes(search.toLowerCase());
  }

  function hintCell(m) {
    if (m._review_open) return '<span class="tag warn">Duplikat offen</span>';
    const flags = sortedFlags(m);
    if (!flags.length) return '<span class="tag dim">–</span>';
    const first = flags[0];
    const cls = first.severity === "high" ? "err" : first.severity === "medium" ? "warn" : "dim";
    return '<span class="tag ' + cls + '">' + esc(label(FLAG, first.code)) +
      (flags.length > 1 ? " +" + (flags.length - 1) : "") + "</span>";
  }

  function detailRow(m, cols) {
    const li = (items) => "<ul>" + items.map((x) => "<li>" + x + "</li>").join("") + "</ul>";
    const blocks = [];

    const facts = ['Kennung: <span class="mono">' + esc(m.university_id || "–") + "</span>"];
    if (m.lifecycle_status && m.lifecycle_status !== "unknown") facts.push("Status: " + esc(m.lifecycle_status));
    if (m.official_url) facts.push('Website: <a href="' + esc(m.official_url) + '" target="_blank" rel="noopener">' + esc(m.official_url) + "</a>");
    if ((m.name_variants || []).length) facts.push("Weitere Schreibweisen: " + esc(m.name_variants.join(" · ")));
    blocks.push("<div><h3>Stammdaten</h3>" + li(facts) + "</div>");

    const locs = (m.locations || []).map((l) => {
      const addr = [l.name, l.street, [l.postal_code, l.city].filter(Boolean).join(" ")].filter(Boolean).join(", ");
      return esc(addr || "ohne Adresse") + ' <span class="muted">(' + esc(short(l.state)) +
        (l.location_type ? ", " + esc(label(LOCTYPE, l.location_type)) : "") + ")</span>";
    });
    blocks.push("<div><h3>Standorte (" + locs.length + ")</h3>" + (locs.length ? li(locs) : '<span class="muted">keine</span>') + "</div>");

    const srcs = sourcesOf(m).map((s) => {
      const url = s.url || s.source_url;
      return esc(s.authority || "Quelle") +
        (url ? ' – <a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(host(url)) + "</a>" : "") +
        (s.retrieved_at ? ' <span class="muted">· abgerufen ' + esc(fmtTime(s.retrieved_at)) + "</span>" : "");
    });
    if (srcs.length) blocks.push("<div><h3>Quellen</h3>" + li(srcs) + "</div>");

    const flags = sortedFlags(m).map((f) =>
      esc(label(FLAG, f.code)) + (f.detail ? ' <span class="muted">– ' + esc(f.detail) + "</span>" : ""));
    if (flags.length) blocks.push("<div><h3>Hinweise</h3>" + li(flags) + "</div>");

    if ((m.merged_from || []).length > 1) {
      blocks.push("<div><h3>Zusammengeführt aus</h3>" +
        li(m.merged_from.map((x) => '<span class="mono">' + esc(x.source_key || x.name) + "</span>")) + "</div>");
    }

    const extra = Object.keys(m).filter((key) => !KNOWN_FIELDS.has(key));
    if (extra.length) {
      blocks.push("<div><h3>Weitere Felder</h3>" + li(extra.map((key) =>
        esc(key) + ': <span class="mono">' + esc(typeof m[key] === "object" ? JSON.stringify(m[key]) : m[key]) + "</span>")) + "</div>");
    }
    return '<tr class="detail"><td colspan="' + cols + '"><div class="dgrid">' + blocks.join("") + "</div></td></tr>";
  }

  function tableHTML(rows) {
    const widths = [27, 11, 9, 12, 12, 13, 16];
    const heads = ["Name", "Typ", "Träger", "Anerkennung", "Orte", "Website", "Hinweis"];
    let html = '<table class="list"><colgroup>' + widths.map((w) => '<col style="width:' + w + '%">').join("") +
      "</colgroup><thead><tr>" + heads.map((h) => "<th>" + h + "</th>").join("") + "</tr></thead><tbody>";
    rows.forEach((m) => {
      const id = m.university_id || m.name;
      const isOpen = openRows.has(id);
      const others = listedBy(m).filter((c) => c !== activeTab);
      const also = activeTab !== "all" && others.length ? ' <span class="tag dim">auch ' + esc(others.map(short).join(", ")) + "</span>" : "";
      const all = activeTab === "all" && listedBy(m).length ? ' <span class="tag dim">' + esc(listedBy(m).map(short).join(", ")) + "</span>" : "";
      const c = cities(m);
      html += '<tr class="row' + (isOpen ? " open" : "") + '" data-row="' + esc(id) + '" tabindex="0" aria-expanded="' + isOpen + '">' +
        '<td class="name" title="' + esc(m.name) + '">' + esc(m.name) + also + all + "</td>" +
        "<td>" + esc(label(TYPE, m.institution_type)) + "</td>" +
        "<td>" + esc(label(OWNER, m.ownership)) + "</td>" +
        "<td>" + esc(label(RECOG, m.recognition_status)) + "</td>" +
        '<td title="' + esc(c.join(", ")) + '">' + (c.length ? esc(c.join(", ")) : '<span class="tag dim">–</span>') + "</td>" +
        "<td>" + (m.official_url ? esc(host(m.official_url)) : '<span class="tag dim">–</span>') + "</td>" +
        "<td>" + hintCell(m) + "</td></tr>";
      if (isOpen) html += detailRow(m, heads.length);
    });
    return html + "</tbody></table>";
  }

  function breakdown(k) {
    const line = (title, map, labels) => "<div><b>" + title + ":</b> " +
      Object.entries(map).sort((a, b) => b[1] - a[1])
        .map(([key, n]) => esc(label(labels, key)) + " <span>" + n + "</span>").join(" · ") + "</div>";
    return '<div class="breakdown">' + line("Typ", k.by_type, TYPE) + line("Träger", k.by_ownership, OWNER) +
      line("Anerkennung", k.by_recognition, RECOG) + "</div>";
  }

  function toolbar(title, sub) {
    return '<div class="panelhead"><h2>' + esc(title) + '</h2><span class="muted grow">' + esc(sub) + "</span>" +
      '<label class="check"><input type="checkbox" id="only-flags"' + (onlyFlags ? " checked" : "") + "> nur mit Hinweisen</label>" +
      '<input type="search" id="search" placeholder="Name, Ort oder Website" value="' + esc(search) + '" aria-label="Suche"></div>';
  }

  function listPanel() {
    if (!st.kpis) {
      return '<div class="empty">Noch keine Daten. Oben rechts auf „Abruf starten“ klicken' +
        (meta.capabilities.last_scrape_available ? " oder mit „Letzten Abruf laden“ den zuletzt gespeicherten Stand öffnen." : ".") + "</div>";
    }
    const all = rowsFor(activeTab);
    const rows = all.filter(matches).sort((a, b) => String(a.name).localeCompare(String(b.name), "de"));
    let html = "";

    if (activeTab === "all") {
      html += toolbar("Alle Hochschulen", rows.length === all.length ? all.length + " Einträge" : rows.length + " von " + all.length);
      html += breakdown(st.kpis);
    } else {
      const info = st.states[activeTab] || {};
      const authority = (() => {
        for (const m of all) {
          const s = sourcesOf(m).find((x) => (x.state || activeTab) === activeTab && x.authority);
          if (s) return s.authority;
        }
        return "";
      })();
      const bits = [];
      if (info.status === "ok") bits.push(plural(all.length, "Hochschule", "Hochschulen"));
      if (info.seconds != null) bits.push(String(info.seconds).replace(".", ",") + " s");
      if (authority) bits.push("Quelle: " + authority);
      html += toolbar(stateName(activeTab), bits.join(" · "));

      if (info.status === "error") {
        html += '<div class="statebox"><span>Abruf fehlgeschlagen: ' + esc(info.error || "unbekannter Fehler") +
          '</span><button class="btn" type="button" data-retry="' + esc(activeTab) + '"' + (st.busy ? " disabled" : "") + ">Erneut abrufen</button></div>";
      } else if (info.status === "running") {
        html += '<div class="statebox info">Wird gerade abgerufen …</div>';
      } else if (info.status === "waiting") {
        html += '<div class="statebox info">Wartet auf den Abruf.</div>';
      } else if (!st.states[activeTab]) {
        html += '<div class="statebox info">Dieses Land gehört nicht zum aktuellen Lauf.</div>';
      } else if (info.status === "skipped") {
        html += '<div class="statebox info">Nicht abgerufen' + (info.detail ? " (" + esc(info.detail) + ")" : "") + ".</div>";
      } else if (info.note) {
        html += '<div class="statebox info">Hinweis: ' + esc(info.note) + ".</div>";
      }
    }

    if (rows.length) html += tableHTML(rows);
    else if (all.length) html += '<div class="empty">Kein Eintrag passt zum Filter.</div>';
    else if (activeTab === "all" || (st.states[activeTab] || {}).status === "ok") html += '<div class="empty">Keine Einträge.</div>';
    return html;
  }

  // ------------------------------------------------------------ duplicates

  function locText(side) {
    const parts = (side.locations || []).map((l) =>
      [l.name, l.street, [l.postal_code, l.city].filter(Boolean).join(" ")].filter(Boolean).join(", ")).filter(Boolean);
    return parts.length ? parts.join(" · ") : "–";
  }

  function pairHTML(p, index, total) {
    const signals = Object.keys(p.signals || {}).filter((s) => SIGNAL[s]).map((s) => SIGNAL[s]);
    const why = signals.length ? signals.join(", ") : (p.reasons || []).join("; ");
    const rows = [
      ["Name", esc(p.a.name), esc(p.b.name), p.a.name === p.b.name],
      ["Gelistet von", esc(stateName(p.a.state)), esc(stateName(p.b.state)), p.a.state === p.b.state],
      ["Typ", esc(label(TYPE, p.a.institution_type)), esc(label(TYPE, p.b.institution_type)), p.a.institution_type === p.b.institution_type],
      ["Träger", esc(label(OWNER, p.a.ownership)), esc(label(OWNER, p.b.ownership)), p.a.ownership === p.b.ownership],
      ["Anerkennung", esc(label(RECOG, p.a.recognition_status)), esc(label(RECOG, p.b.recognition_status)), p.a.recognition_status === p.b.recognition_status],
      ["Website", link(p.a.official_url), link(p.b.official_url), host(p.a.official_url) === host(p.b.official_url)],
      ["Standorte", esc(locText(p.a)), esc(locText(p.b)), locText(p.a) === locText(p.b)],
    ];
    function link(url) {
      return url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(host(url)) + "</a>" : "–";
    }
    let html = '<div class="pair' + (p.decision ? " decided" : "") + '" data-pair="' + esc(p.id) + '">' +
      '<div class="pairhead"><h3>Paar ' + index + " von " + total + '</h3><span class="why">gemeldet wegen: ' + esc(why || "Ähnlichkeit") + "</span>" +
      (p.decision ? '<span class="decision">' + (p.decision === "merge" ? "Entschieden: zusammenführen" : "Entschieden: getrennt lassen") + "</span>" : "") + "</div>" +
      '<table class="cmp"><thead><tr><th></th><th>Eintrag A</th><th>Eintrag B</th></tr></thead><tbody>' +
      rows.map((r) => '<tr class="' + (r[3] ? "same" : "diff") + '"><td class="f">' + r[0] + '</td><td class="v">' + r[1] + '</td><td class="v">' + r[2] + "</td></tr>").join("") +
      "</tbody></table>";
    if (p.decision) {
      html += '<div class="pairact"><span class="muted" style="flex:1">' + (p.note ? "Begründung: " + esc(p.note) : "ohne Begründung") +
        '</span><button class="btn" type="button" data-decide="">Zurücknehmen</button></div>';
    } else {
      html += '<div class="pairact"><input type="text" placeholder="Begründung, z. B. Beleg oder Quelle" aria-label="Begründung" maxlength="200">' +
        '<button class="btn" type="button" data-decide="keep_separate">Getrennt lassen</button>' +
        '<button class="btn" type="button" data-decide="merge">Zusammenführen</button></div>';
    }
    return html + "</div>";
  }

  function reviewPanel() {
    if (!st.kpis) return '<div class="empty">Noch keine Daten. Duplikate erscheinen nach einem Abruf.</div>';
    if (data.dedup === false) {
      return '<div class="empty">Diese Scraper-Version hat keinen Duplikat-Abgleich. Es gibt nichts zu entscheiden.</div>';
    }
    const open = data.review.filter((p) => !p.decision);
    const done = data.review.filter((p) => p.decision);
    let html = '<div class="panelhead"><h2>Mögliche Duplikate</h2><span class="muted grow">' +
      open.length + " offen · " + done.length + " in dieser Sitzung entschieden · " +
      st.kpis.auto_merge_pairs + " automatisch gelöst</span></div>";
    if (!data.review.length) {
      return html + '<div class="empty">Nichts offen. Alle erkannten Paare wurden automatisch oder durch frühere Entscheidungen gelöst.</div>';
    }
    html += '<div class="statebox info">Unterschiede sind hervorgehoben. Entscheidungen werden sofort in ' +
      esc(meta.overrides_file) + " gespeichert und gelten auch für spätere Läufe.</div>";
    const all = open.concat(done);
    all.forEach((p, i) => { html += pairHTML(p, i + 1, all.length); });
    return html;
  }

  function renderPanel() {
    setHTML($("panel"), activeTab === "review" ? reviewPanel() : listPanel());
  }

  function renderFoot() {
    const c = meta.capabilities;
    setHTML($("foot"), "Scraper: " + esc(c.scraper_dir) + " · Duplikat-Abgleich: " + (c.dedup ? "verfügbar" : "nicht verfügbar") +
      " · Entscheidungen: " + esc(meta.overrides_file) + " · Register: " + esc(meta.registry_file));
  }

  function renderLog() {
    const el = $("log");
    if (el.hidden) return;
    const atEnd = el.scrollTop + el.clientHeight >= el.scrollHeight - 8;
    el.textContent = logLines.join("\n") || "Noch keine Ausgabe.";
    if (atEnd) el.scrollTop = el.scrollHeight;
  }

  function renderAll() {
    renderHeader(); renderPhases(); renderStatus(); renderKpis(); renderTabs(); renderPanel(); renderLog();
  }

  // --------------------------------------------------------------- polling

  async function refresh() {
    let snap = await api("/api/state?log_since=" + logNext);
    if (snap.log_next < logNext || (st && snap.started_at !== st.started_at)) {
      // A new run started (possibly from another browser tab): start the log over.
      logLines = []; logNext = 0; openRows.clear();
      snap = await api("/api/state?log_since=0");
    }
    if (snap.log.length) logLines = logLines.concat(snap.log).slice(-2000);
    logNext = snap.log_next;
    st = snap;
    if (snap.version !== data.version) data = await api("/api/records");
    renderAll();
  }

  async function poll() {
    clearTimeout(pollTimer);
    try { await refresh(); }
    catch (e) { $("status-text").textContent = "Keine Verbindung zum UI-Server. Läuft er noch?"; }
    pollTimer = setTimeout(poll, st && st.busy ? 800 : 2500);
  }

  async function act(fn) {
    notice("");
    try { await fn(); } catch (e) { notice(e.message); }
    await poll();
  }

  // ---------------------------------------------------------------- events

  function selectedStates() {
    const boxes = Array.from(document.querySelectorAll("#opt-states input"));
    const checked = boxes.filter((b) => b.checked).map((b) => b.value);
    return checked.length === boxes.length ? null : checked;
  }

  function confirmDiscard() {
    if (!st.kpis || st.phase === "saved") return true;
    return window.confirm("Der aktuelle Stand ist nicht gespeichert und wird verworfen. Fortfahren?");
  }

  function startRun(source) {
    const states = selectedStates();
    if (states && !states.length) { notice("Bitte mindestens ein Bundesland auswählen."); return; }
    if (!confirmDiscard()) return;
    logLines = []; logNext = 0;
    act(() => api("/api/run", { states: states, online: $("opt-online").checked, source: source }));
  }

  $("btn-start").addEventListener("click", () => {
    if ($("btn-start").dataset.mode === "cancel") act(() => api("/api/cancel", {}));
    else startRun("live");
  });
  $("btn-load").addEventListener("click", () => startRun("file"));

  $("btn-save").addEventListener("click", () => act(async () => {
    try { await api("/api/save", { confirm_incomplete: false }); }
    catch (e) {
      if (e.status === 409 && e.message.startsWith("INCOMPLETE:")) {
        const which = e.message.slice("INCOMPLETE:".length);
        if (window.confirm("Der Stand ist unvollständig: " + which + " fehlt. Trotzdem speichern?")) {
          await api("/api/save", { confirm_incomplete: true });
        }
      } else throw e;
    }
    meta = await api("/api/meta");
  }));

  $("btn-next").addEventListener("click", () => { activeTab = "review"; renderAll(); });

  function toggle(btn, target) {
    const el = $(target);
    el.hidden = !el.hidden;
    $(btn).setAttribute("aria-expanded", String(!el.hidden));
  }
  $("btn-options").addEventListener("click", () => toggle("btn-options", "options"));
  $("btn-log").addEventListener("click", () => {
    toggle("btn-log", "log"); renderLog();
    const el = $("log"); el.scrollTop = el.scrollHeight;
  });
  $("opt-all").addEventListener("click", () => document.querySelectorAll("#opt-states input").forEach((b) => { b.checked = true; }));
  $("opt-none").addEventListener("click", () => document.querySelectorAll("#opt-states input").forEach((b) => { b.checked = false; }));

  $("tabs").addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-tab]");
    if (!btn) return;
    activeTab = btn.dataset.tab;
    renderAll();
  });

  const panel = $("panel");
  function toggleRow(tr) {
    const id = tr.dataset.row;
    if (openRows.has(id)) openRows.delete(id); else openRows.add(id);
    renderPanel();
  }
  panel.addEventListener("click", (ev) => {
    const retry = ev.target.closest("[data-retry]");
    if (retry) { act(() => api("/api/states/" + encodeURIComponent(retry.dataset.retry) + "/retry", {})); return; }

    const decide = ev.target.closest("[data-decide]");
    if (decide) {
      const box = decide.closest("[data-pair]");
      const input = box.querySelector("input[type=text]");
      act(() => api("/api/review/" + box.dataset.pair,
        { decision: decide.dataset.decide || null, note: input ? input.value : "" }));
      return;
    }
    if (ev.target.closest("a, input, label, button")) return;
    const tr = ev.target.closest("tr.row");
    if (tr) toggleRow(tr);
  });
  panel.addEventListener("keydown", (ev) => {
    if ((ev.key === "Enter" || ev.key === " ") && ev.target.matches("tr.row")) { ev.preventDefault(); toggleRow(ev.target); }
  });
  panel.addEventListener("input", (ev) => {
    if (ev.target.id !== "search") return;
    search = ev.target.value;
    const pos = ev.target.selectionStart;
    renderPanel();
    const again = $("search");
    if (again) { again.focus(); again.setSelectionRange(pos, pos); }
  });
  panel.addEventListener("change", (ev) => {
    if (ev.target.id === "only-flags") { onlyFlags = ev.target.checked; renderPanel(); }
  });

  // ------------------------------------------------------------------ init

  (async function init() {
    try {
      meta = await api("/api/meta");
    } catch (e) {
      $("status-text").textContent = "Die Oberfläche konnte nicht geladen werden: " + e.message;
      return;
    }
    $("opt-states").innerHTML = meta.states.map((s) =>
      '<label class="check"><input type="checkbox" value="' + esc(s.code) + '" checked> ' + esc(s.short) + " – " + esc(s.name) + "</label>").join("");
    $("opt-online-box").hidden = !meta.capabilities.web_check;
    renderFoot();
    poll();
  })();
})();
