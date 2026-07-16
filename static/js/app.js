// ── State ─────────────────────────────────────────────────────────────────────
const S = {
  pokemons: [],
  items:    [],
  events:   [],
  tiers:    {},
  filter:   "all",
  search:   "",
  sort:     "cp",
};

// ── Helpers ───────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ error: r.statusText }));
    throw new Error(e.error || r.statusText);
  }
  return r.json();
}

function ivClass(iv) {
  if (iv === 100) return "iv-s";
  if (iv >= 82)   return "iv-a";
  if (iv >= 60)   return "iv-n";
  return "iv-l";
}

function tierBadge(tier) {
  if (!tier) return "";
  const parts = tier.split(" ");
  const tierVal = parts[parts.length - 1] || "";
  const firstChar = tierVal.charAt(0).toUpperCase();
  const cls = { S: "badge-s", A: "badge-a", B: "badge-b", C: "badge-c", D: "badge-d" }[firstChar] || "badge";
  return `<span class="badge ${cls}">${tier}</span>`;
}

function mdToHtml(md) {
  return md
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/^#{1,3} (.+)$/gm, (_, t) => `<h2>${t.replace(/\*\*/g,"")}</h2>`)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/^[-•] (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>)+/g, m => `<ul>${m}</ul>`)
    .replace(/^(\d+\. .+)$/gm, "<li>$1</li>")
    .replace(/\n\n+/g, "</p><p>")
    .replace(/\n/g, "<br>")
    .replace(/^(.+)$/, "<p>$1</p>");
}

// ── Upload ────────────────────────────────────────────────────────────────────
function setupUpload(input) {
  input.addEventListener("change", async () => {
    if (!input.files[0]) return;
    const fd = new FormData();
    fd.append("file", input.files[0]);
    try {
      const data = await fetch("/api/upload", { method: "POST", body: fd }).then(r => r.json());
      if (data.error) throw new Error(data.error);
      onUploadSuccess(data.stats, data.player, data.pvp_stats);
    } catch (e) {
      showErr(e.message);
    }
    input.value = "";
  });
}
setupUpload($("upload-input"));
setupUpload($("upload-input-small"));

const zone = $("upload-zone");
zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("drag"); });
zone.addEventListener("dragleave", () => zone.classList.remove("drag"));
zone.addEventListener("drop", e => {
  e.preventDefault(); zone.classList.remove("drag");
  const file = e.dataTransfer.files[0];
  if (file) {
    const fd = new FormData();
    fd.append("file", file);
    fetch("/api/upload", { method: "POST", body: fd })
      .then(r => r.json())
      .then(d => d.error ? showErr(d.error) : onUploadSuccess(d.stats, d.player, d.pvp_stats))
      .catch(e => showErr(e.message));
  }
});

function showErr(msg) {
  const el = $("upload-err");
  el.textContent = "❌ " + msg;
  el.style.display = "block";
  setTimeout(() => { el.style.display = "none"; }, 5000);
}

async function onUploadSuccess(stats, player, pvp_stats) {
  $("upload-zone").style.display   = "none";
  $("upload-err").style.display    = "none";
  $("main-ui").style.display       = "block";
  $("stats-bar").style.display     = "flex";
  $("upload-small").style.display  = "block";
  $("tabs").style.display          = "flex";
  $("header-sub").textContent      = "Twoje konto Pokemon GO";
  const hint = document.querySelector(".sidebar-hint");
  if (hint) hint.style.display = "none";

  $("s-total").textContent  = stats.total;
  $("s-shiny").textContent  = stats.shinies;
  $("s-hundo").textContent  = stats.hundos;
  $("s-nando").textContent  = stats.nandos || 0;
  $("s-shadow").textContent = stats.shadows;
  $("s-lucky").textContent  = stats.luckies;
  $("tb-poke").textContent  = stats.total;
  if (stats.stardust) $("s-dust").textContent = stats.stardust.toLocaleString("pl-PL");
  updateAnalytics();

  // Handle Player Card in Sidebar
  if (player) {
    $("sidebar-player").style.display = "flex";
    $("s-player-name").textContent = player.name || "Gracz";
    $("s-player-level").textContent = `Lvl ${player.level || "?"} · ${player.kmWalked || 0} km`;
    
    const avatar = $("s-player-avatar");
    avatar.className = "";
    if (player.team === 1) {
      avatar.classList.add("team-mystic-bg");
      avatar.textContent = "❄️";
    } else if (player.team === 2) {
      avatar.classList.add("team-valor-bg");
      avatar.textContent = "🔥";
    } else if (player.team === 3) {
      avatar.classList.add("team-instinct-bg");
      avatar.textContent = "⚡";
    } else {
      avatar.textContent = "👤";
    }
  } else {
    $("sidebar-player").style.display = "none";
  }

  // Handle PvP Battle stats dashboard
  if (pvp_stats && pvp_stats.season_battles > 0) {
    $("pvp-stats-card").style.display = "block";
    $("pvp-stat-rank").textContent = pvp_stats.season_rank || "—";
    
    const winrate = pvp_stats.season_battles > 0 
      ? ((pvp_stats.season_wins / pvp_stats.season_battles) * 100).toFixed(1) + "%" 
      : "—";
    $("pvp-stat-winrate").textContent = winrate;
    $("pvp-stat-ratio").textContent = `${pvp_stats.season_wins} W / ${pvp_stats.season_battles} B`;
    $("pvp-stat-streak").textContent = pvp_stats.season_longest_streak || "—";
    $("pvp-stat-dust").textContent = pvp_stats.season_stardust ? pvp_stats.season_stardust.toLocaleString("pl-PL") : "—";
    
    const formatLeague = (wins, total) => {
      if (!total) return "—";
      const pct = ((wins / total) * 100).toFixed(0);
      return `${wins}/${total} (${pct}%)`;
    };
    $("pvp-stat-gl").textContent = formatLeague(pvp_stats.gl_wins, pvp_stats.gl_battles);
    $("pvp-stat-ul").textContent = formatLeague(pvp_stats.ul_wins, pvp_stats.ul_battles);
    $("pvp-stat-ml").textContent = formatLeague(pvp_stats.ml_wins, pvp_stats.ml_battles);
  } else {
    $("pvp-stats-card").style.display = "none";
  }

  await Promise.all([loadPokemons(), loadItems(), loadEvents(), loadTiers(), loadCacheStats(), loadConfig()]);
  loadRaid();
  loadPvP("GL");
  loadDevelop();
  updatePogoQuery();
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
$$(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    $$(".tab").forEach(b => b.classList.remove("active"));
    $$(".panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    $("panel-" + btn.dataset.tab).classList.add("active");
  });
});

// ── Pokemony ──────────────────────────────────────────────────────────────────
async function loadPokemons() {
  S.pokemons = await api("/api/pokemons");
  renderPokemons();
}

$("poke-search").addEventListener("input", e => { S.search = e.target.value.toLowerCase(); renderPokemons(); });
$("poke-filter").addEventListener("change", e => { S.filter = e.target.value; renderPokemons(); });
$("poke-sort").addEventListener("change",   e => { S.sort   = e.target.value; renderPokemons(); });

function filterPoke(p) {
  if (S.search && !p.name.toLowerCase().includes(S.search)) return false;
  switch (S.filter) {
    case "hundo":   return p.hundo;
    case "shiny":   return p.shiny;
    case "shadow":  return p.shadow;
    case "lucky":   return p.lucky;
    case "tier_s":  return p.best_tier && p.best_tier.startsWith("S");
    case "tier_a":  return p.best_tier && p.best_tier.startsWith("A");
    case "trash": {
      const cpMin = parseInt($("ropt-cp-min").value) || 1200;
      const protectHundo = $("ropt-hundo").checked;
      const protectNando = $("ropt-nando").checked;
      const protectShiny = $("ropt-shiny").checked;
      const protectShadow = $("ropt-shadow").checked;
      const protectLucky = $("ropt-lucky").checked;
      const protectFav = $("ropt-fav").checked;
      const protectMeta = $("ropt-meta").checked;
      const protectIv = $("ropt-iv").checked;
      const protectPvp = $("ropt-pvp").checked;
      const protectLvl = $("ropt-lvl").checked;

      const isProtected = (protectHundo && (p.hundo || p.iv_pct === 100))
        || (protectNando && p.iv_pct === 0)
        || (protectShiny && p.shiny)
        || (protectShadow && p.shadow)
        || (protectLucky && p.lucky)
        || (protectFav && p.fav)
        || (protectMeta && p.best_tier && (p.best_tier.startsWith("S") || p.best_tier.startsWith("A")))
        || (protectIv && p.iv_pct >= 82.2)
        || (p.cp >= cpMin)
        || (protectPvp && p.gl_rank > 0 && p.gl_rank <= 500)
        || (protectLvl && p.lvl >= 35);
        
      return !isProtected;
    }
    case "y2016":   return p.year >= 2016 && p.year <= 2018;
    case "y2022":   return p.year >= 2019 && p.year <= 2022;
    case "pvp_gem": return p.gl_rank > 0 && p.gl_rank <= 250;
    default:        return true;
  }
}

function sortPokes(arr) {
  return [...arr].sort((a, b) => {
    if (S.sort === "iv")   return b.iv_pct - a.iv_pct;
    if (S.sort === "lvl")  return b.lvl - a.lvl;
    if (S.sort === "name") return a.name.localeCompare(b.name);
    return b.cp - a.cp;
  });
}

function renderPokemons() {
  const list = sortPokes(S.pokemons.filter(filterPoke));
  $("poke-count").textContent = `${list.length} / ${S.pokemons.length}`;
  const tbody = $("poke-tbody");
  tbody.innerHTML = list.map(p => {
    const tiers = p.tiers || {};
    const tierBadges = Object.entries(tiers)
      .map(([cat, t]) => `<span class="badge badge-${t.charAt(0).toLowerCase()}" data-tooltip="${cat}">${cat.split("_").pop().toUpperCase()} ${t}</span>`)
      .join("");
    const evTags = (p.event_tags || []).slice(0, 2)
      .map(ev => `<span class="badge badge-event" data-tooltip="${ev}">📅</span>`).join("");
    const tags = [
      p.shiny  ? `<span class="badge badge-shiny" data-tooltip="Shiny">✨</span>` : "",
      p.shadow ? `<span class="badge badge-shadow" data-tooltip="Shadow (+20% ATK)">Shadow</span>` : "",
      p.hundo  ? `<span class="badge badge-hundo" data-tooltip="100% IV">💯</span>` : "",
      p.lucky  ? `<span class="badge badge-lucky" data-tooltip="Lucky (tańszy power-up)">🍀</span>` : "",
      evTags,
    ].join("");
    const yr = p.year <= 2018 ? "year-old" : p.year <= 2022 ? "year-mid" : "";
    return `<tr>
      <td class="name-cell">
        ${p.nick ? `<span data-tooltip="${p.name}">${p.nick}</span>` : p.name}
        ${p.move1_name ? `
        <div class="moves-row">
          <span class="move-tag type-${p.move1_type}" data-tooltip="Fast Move">${p.move1_name}</span>
          ${p.move2_name ? `<span class="move-tag type-${p.move2_type}" data-tooltip="Charged Move">${p.move2_name}</span>` : ''}
          ${p.move3_name ? `<span class="move-tag type-${p.move3_type}" data-tooltip="Second Charged Move">${p.move3_name}</span>` : ''}
        </div>` : ''}
      </td>
      <td class="cp-cell">${p.cp}</td>
      <td class="mono">${p.lvl}</td>
      <td class="${ivClass(p.iv_pct)}">${p.iv_pct}%</td>
      <td class="mono">${p.iv_a}/${p.iv_d}/${p.iv_s}</td>
      <td class="${yr}">${p.year || "—"}</td>
      <td>${tierBadges || '<span style="color:var(--muted);font-size:10px">—</span>'}</td>
      <td>${tags || '<span style="color:var(--muted);font-size:10px">—</span>'}</td>
      <td><button class="btn-ai" onclick="analyzeOnePokemon(${S.pokemons.indexOf(p)})">🤖 AI</button></td>
    </tr>`;
  }).join("") || `<tr><td colspan="9" style="padding:24px;text-align:center;color:var(--muted)">Brak wyników</td></tr>`;
}

function buildPogoQuery() {
  const list = sortPokes(S.pokemons.filter(filterPoke));
  if (!list.length) return null;

  const cpMin = parseInt($("ropt-cp-min").value) || 1200;
  
  const protectHundo = $("ropt-hundo").checked;
  const protectNando = $("ropt-nando").checked;
  const protectShiny = $("ropt-shiny").checked;
  const protectShadow = $("ropt-shadow").checked;
  const protectLucky = $("ropt-lucky").checked;
  const protectFav = $("ropt-fav").checked;
  const protectMeta = $("ropt-meta").checked;
  const protectIv = $("ropt-iv").checked;
  const protectPvp = $("ropt-pvp").checked;
  const protectLvl = $("ropt-lvl").checked;

  const protected_ = new Set(
    S.pokemons
      .filter(p =>
        (protectHundo && (p.hundo || p.iv_pct === 100))
        || (protectNando && p.iv_pct === 0)
        || (protectShiny && p.shiny)
        || (protectShadow && p.shadow)
        || (protectLucky && p.lucky)
        || (protectFav && p.fav)
        || (protectMeta && p.best_tier && (p.best_tier.startsWith("S") || p.best_tier.startsWith("A")))
        || (protectIv && p.iv_pct >= 82.2)
        || (p.cp >= cpMin)
        || (protectPvp && p.gl_rank > 0 && p.gl_rank <= 500)
        || (protectLvl && p.lvl >= 35)
      )
      .map(p => p.name)
  );

  const seen = new Set();
  const allPokes = list.filter(p => seen.has(p.name) ? false : (seen.add(p.name), true));
  const safePokes = allPokes.filter(p => !protected_.has(p.name));
  const skipped   = allPokes.length - safePokes.length;

  if (!safePokes.length) return { query: null, skipped, total: allPokes.length };

  let suffix = "";
  const isPl = _lang === "pl";
  
  if ($("ropt-ex-shiny").checked)     suffix += "&!shiny";
  if ($("ropt-ex-shadow").checked)    suffix += "&!shadow";
  if ($("ropt-ex-lucky").checked)     suffix += "&!lucky";
  if ($("ropt-ex-fav").checked)       suffix += isPl ? "&!ulubione" : "&!favorite";
  if ($("ropt-ex-legendary").checked) suffix += isPl ? "&!legenda" : "&!legendary";
  if ($("ropt-ex-mythical").checked)  suffix += isPl ? "&!mityczny" : "&!mythical";
  if ($("ropt-ex-ub").checked)        suffix += isPl ? "&!ultra bestia" : "&!ultrabeast";
  if ($("ropt-ex-costume").checked)   suffix += isPl ? "&!kostium" : "&!costume";
  if ($("ropt-ex-purified").checked)  suffix += isPl ? "&!oczyszczony" : "&!purified";
  if ($("ropt-ex-buddy").checked)     suffix += isPl ? "&!pomocnik" : "&!buddy";
  if ($("ropt-ex-defender").checked)  suffix += isPl ? "&!obrońca" : "&!defender";
  if ($("ropt-ex-mega").checked)      suffix += isPl ? "&!mega" : "&!mega";
  
  if ($("ropt-cp").checked) {
    const cpVal = $("ropt-cp-val").value;
    if (cpVal) suffix += `&cp-${cpVal}`;
  }

  // IDs Pokédexu zamiast nazw; sufiks JEDEN raz na końcu całej grupy
  const ids = [...new Set(safePokes.map(p => p.pid))];

  // chunking: każda paczka IDs + sufiks ≤ 300 znaków
  const LIMIT = 300;
  const chunks = [];
  let cur = [], curLen = 0;
  for (const id of ids) {
    const s = String(id);
    const add = cur.length ? s.length + 1 : s.length;   // +1 za przecinek
    if (cur.length && curLen + add + suffix.length > LIMIT) {
      chunks.push(cur.join(",") + suffix);
      cur = [s]; curLen = s.length;
    } else {
      cur.push(s); curLen += add;
    }
  }
  if (cur.length) chunks.push(cur.join(",") + suffix);

  return { chunks, skipped, total: allPokes.length };
}

// ── CSV Export ────────────────────────────────────────────────────────────────
$("btn-export-csv").addEventListener("click", () => {
  const list = sortPokes(S.pokemons);
  const headers = ["Nazwa","Pseudonim","CP","Lvl","IV%","Atk","Def","Sta","Rok",
                   "Shiny","Shadow","Lucky","Hundo","Ulubiony","Tier","Eventy"];
  const esc = v => `"${String(v ?? "").replace(/"/g,'""')}"`;
  const rows = list.map(p => [
    p.name, p.nick || "", p.cp, p.lvl, p.iv_pct,
    p.iv_a, p.iv_d, p.iv_s, p.year || "",
    p.shiny  ? "TAK" : "",
    p.shadow ? "TAK" : "",
    p.lucky  ? "TAK" : "",
    p.hundo  ? "TAK" : "",
    p.fav    ? "TAK" : "",
    p.best_tier || "",
    (p.event_tags || []).join("; "),
  ]);
  const csv = [headers, ...rows].map(r => r.map(esc).join(",")).join("\r\n");
  const blob = new Blob(["﻿" + csv], {type: "text/csv;charset=utf-8"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "pokego_box.csv"; a.click();
  URL.revokeObjectURL(url);
});

$("btn-copy-regex").addEventListener("click", () => {
  const result = buildPogoQuery();
  if (!result) return;
  const { chunks, skipped, total } = result;

  if (!chunks) {
    alert(`Wszystkie ${total} gatunków mają cenne okazy (shiny/shadow/lucky/meta) — query byłoby puste.\nSprawdź filtry.`);
    return;
  }

  // jeśli >1 paczka — pokaż dialog z wszystkimi chunkami do ręcznego kopiowania
  if (chunks.length > 1) {
    const msg = `Za dużo ID — podzielono na ${chunks.length} paczki (każda ≤300 znaków):\n\n`
      + chunks.map((c, i) => `Paczka ${i+1}:\n${c}`).join("\n\n");
    alert(msg);
    $("regex-hint").textContent = `${chunks.length} paczek · ${total - skipped} gatunków`;
    return;
  }

  const query = chunks[0];
  navigator.clipboard.writeText(query).then(() => {
    const btn  = $("btn-copy-regex");
    const prev = btn.textContent;
    btn.textContent = skipped ? `✓ Skopiowano (${total - skipped}/${total} gat.)` : `✓ ${total - skipped} gatunków`;
    btn.style.color = "var(--green)";
    btn.style.borderColor = "var(--green)";
    $("regex-hint").textContent = query.length > 60 ? query.slice(0, 57) + "…" : query;
    setTimeout(() => { btn.textContent = prev; btn.style.color = ""; btn.style.borderColor = ""; }, 3000);
  });
});

function updatePogoQuery() {
  const result = buildPogoQuery();
  const input = $("regex-query-input");
  const hint = $("regex-hint");
  if (!result || !result.chunks || result.chunks.length === 0) {
    if (input) input.value = "";
    if (hint) hint.textContent = _lang === "pl" ? "Wszystkie zachowane" : "All protected";
    return;
  }
  const { chunks, skipped, total } = result;
  if (input) {
    input.value = chunks.join(" | ");
  }
  if (hint) {
    hint.textContent = _lang === "pl"
      ? `${chunks.length} paczek · ${total - skipped} gatunków`
      : `${chunks.length} chunks · ${total - skipped} species`;
  }
}

// ── Items ─────────────────────────────────────────────────────────────────────
async function loadItems() {
  S.items = await api("/api/items");
  renderItems();
}

function renderItems() {
  $("items-grid").innerHTML = S.items.map(it =>
    `<div class="item-card">
       <span class="item-name">${it.name}</span>
       <span class="item-count">×${it.count}</span>
     </div>`
  ).join("") || `<p style="color:var(--muted);font-size:13px">Brak danych ekwipunku</p>`;
}

$("btn-analyze-items").addEventListener("click", async () => {
  const btn = $("btn-analyze-items");
  btn.disabled = true;
  btn.textContent = "⏳ Analizuję…";
  try {
    const d = await api("/api/analyze-items", { method: "POST", body: "{}" });
    $("items-ai-title").innerHTML = "Analiza ekwipunku " + (d.cached ? '<span class="badge badge-lucky">z cache</span>' : "");
    $("items-ai-body").innerHTML  = mdToHtml(d.response);
    $("items-ai-result").style.display = "block";
  } catch (e) {
    alert("Błąd AI: " + e.message);
  }
  btn.disabled = false;
  btn.textContent = "🤖 Analiza AI — co i na kogo";
});

// ── Events ────────────────────────────────────────────────────────────────────
async function loadEvents() {
  S.events = await api("/api/events");
  renderEvents();
}

$("btn-refresh-events").addEventListener("click", async () => {
  $("btn-refresh-events").textContent = "⏳";
  await api("/api/events/refresh", { method: "POST", body: "{}" });
  await loadEvents();
  $("btn-refresh-events").textContent = "🔄 Odśwież eventy";
});

$("events-filter").addEventListener("change", renderEvents);
$("events-tier-filter").addEventListener("change", renderEvents);
$("events-search").addEventListener("input", renderEvents);

function renderEvents() {
  const filt = $("events-filter").value;
  const tierFilt = $("events-tier-filter").value;
  const searchVal = $("events-search").value.toLowerCase().trim();
  
  let list = S.events;
  
  // 1. Status Filter
  if (filt !== "all") {
    list = list.filter(ev => ev.status === filt);
  }
  
  // 2. Search & Tier Filter
  list = list.filter(ev => {
    // Search match (checks title, pokemon names, and evolution names)
    const matchesSearch = !searchVal || 
      ev.name.toLowerCase().includes(searchVal) ||
      (ev.featured_pokemons && ev.featured_pokemons.some(p => 
        p.name.toLowerCase().includes(searchVal) || 
        (p.evolves_to && p.evolves_to.toLowerCase().includes(searchVal))
      ));
      
    if (!matchesSearch) return false;
    
    // Tier filter match
    if (tierFilt !== "all") {
      if (!ev.featured_pokemons || ev.featured_pokemons.length === 0) return false;
      const hasMatchingPoke = ev.featured_pokemons.some(p => {
        if (!p.tiers) return false;
        const ratings = Object.values(p.tiers);
        if (tierFilt === "s_only") {
          return ratings.some(r => r && r.toUpperCase().startsWith("S"));
        } else if (tierFilt === "meta") {
          return ratings.some(r => r && ["S", "A", "B"].some(t => r.toUpperCase().startsWith(t)));
        }
        return false;
      });
      if (!hasMatchingPoke) return false;
    }
    
    return true;
  });

  // Sort list: Active (ending soonest) -> Upcoming (starting soonest) -> Ended (recently ended first)
  list.sort((a, b) => {
    const statusOrder = { active: 1, upcoming: 2, ended: 3 };
    const orderA = statusOrder[a.status] || 99;
    const orderB = statusOrder[b.status] || 99;
    
    if (orderA !== orderB) {
      return orderA - orderB;
    }
    
    const startA = a.start ? new Date(a.start) : new Date(0);
    const startB = b.start ? new Date(b.start) : new Date(0);
    const endA = a.end ? new Date(a.end) : new Date(0);
    const endB = b.end ? new Date(b.end) : new Date(0);
    
    if (a.status === "active") {
      return endA - endB;
    } else if (a.status === "upcoming") {
      return startA - startB;
    } else {
      return endB - endA;
    }
  });

  function getEventTimeStatus(ev) {
    if (!ev.start || !ev.end) return "";
    const now = new Date();
    const start = new Date(ev.start);
    const end = new Date(ev.end);
    
    if (now < start) {
      const diff = start - now;
      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const text = days > 0 ? `${days}d ${hours}h` : `${hours}h`;
      return `<span class="event-countdown-upcoming" title="${ev.start}">⏳ Zaczyna się za: ${text}</span>`;
    } else if (now >= start && now <= end) {
      const diff = end - now;
      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const text = days > 0 ? `${days}d ${hours}h` : `${hours}h`;
      return `<span class="event-countdown-active" title="${ev.end}">⚡ Aktywne (koniec za: ${text})</span>`;
    } else {
      return `<span style="color:var(--muted); font-size:11px;">⬜ Wydarzenie zakończone</span>`;
    }
  }

  const tierClass = (r) => {
    if (!r) return "";
    const first = r.charAt(0).toUpperCase();
    return `tb-${first.toLowerCase()}`;
  };

  $("events-list").innerHTML = list.map(ev => {
    const statusCls   = { active:"status-active", upcoming:"status-upcoming", ended:"status-ended" }[ev.status] || "";
    let statusLabel = "";
    if (ev.status === "active") {
      statusLabel = "🟢 Aktywny";
    } else if (ev.status === "upcoming") {
      if (ev.days_until !== null && ev.days_until !== undefined) {
        statusLabel = ev.days_until > 0 ? `🔵 Za ${ev.days_until}d` : "🔵 Za <24h";
      } else {
        statusLabel = "🔵 Nadchodzący";
      }
    } else {
      statusLabel = "⬜ Zakończony";
    }
    const bonuses = ev.bonuses.slice(0,6).map(b => `<span style="font-size:11px">• ${typeof b === "string" ? b : JSON.stringify(b)}</span>`).join("<br>");
    
    // Render featured pokemons cards
    let pokesHtml = "";
    if (ev.featured_pokemons && ev.featured_pokemons.length > 0) {
      const sortedPokes = [...ev.featured_pokemons].sort((a, b) => {
        const weights = {
          'S+': 1, 'S': 2, 'S-': 3,
          'A+': 4, 'A': 5, 'A-': 6,
          'B+': 7, 'B': 8, 'B-': 9,
          'C+': 10, 'C': 11, 'C-': 12,
          'D+': 13, 'D': 14, 'D-': 15
        };
        const getBestWeight = (tiers) => {
          if (!tiers) return 999;
          const ratings = Object.values(tiers);
          let best = 999;
          ratings.forEach(r => {
            if (!r) return;
            const w = weights[r.toUpperCase()] || 100;
            if (w < best) best = w;
          });
          return best;
        };
        return getBestWeight(a.tiers) - getBestWeight(b.tiers);
      });
      
      const pokeCards = sortedPokes.map(p => {
        const shinyBadge = p.can_be_shiny ? `<span style="color:var(--yellow); font-size:11px;" title="Może być shiny">✨</span>` : "";
        const evoLabel = p.is_evolution && p.evolves_to ? `<div class="event-poke-evo">Ewoluuje w: <b>${p.evolves_to}</b></div>` : "";
        const sourceTag = p.source ? `<span class="event-poke-source">${p.source}</span>` : "";
        
        const tierBadges = [];
        if (p.tiers) {
          if (p.tiers.raid)       tierBadges.push(`<span class="tier-badge ${tierClass(p.tiers.raid)}">⚔️ R: ${p.tiers.raid}</span>`);
          if (p.tiers.pvp_great)  tierBadges.push(`<span class="tier-badge ${tierClass(p.tiers.pvp_great)}">🏆 GL: ${p.tiers.pvp_great}</span>`);
          if (p.tiers.pvp_ultra)  tierBadges.push(`<span class="tier-badge ${tierClass(p.tiers.pvp_ultra)}">🏆 UL: ${p.tiers.pvp_ultra}</span>`);
          if (p.tiers.pvp_master) tierBadges.push(`<span class="tier-badge ${tierClass(p.tiers.pvp_master)}">🏆 ML: ${p.tiers.pvp_master}</span>`);
        }
        
        const tiersHtml = tierBadges.length > 0 
          ? `<div class="event-poke-tiers">${tierBadges.join("")}</div>` 
          : `<div style="font-size: 10px; color: var(--muted); font-style: italic;">Brak danych meta</div>`;
          
        const isRaidBoss = p.source && p.source.toLowerCase().includes("rajd");
        const counterBtn = isRaidBoss ? `<button class="btn btn-outline btn-xs" style="margin-top:6px;width:100%;font-size:9px" onclick="showRaidCounters('${p.name.replace(/'/g, "\\'")}')">⚔️ ${_lang === "pl" ? "Kontry" : "Counters"}</button>` : "";
          
        return `<div class="event-poke-card">
          <img src="${p.image}" class="event-poke-img" onerror="this.src='https://img.pokemondb.net/sprites/sword-shield/icon/unown.png';">
          <div class="event-poke-details">
            <div class="event-poke-name-row">
              <span>${p.name}</span>
              ${shinyBadge}
            </div>
            ${evoLabel}
            ${tiersHtml}
            ${sourceTag}
            ${counterBtn}
          </div>
        </div>`;
      }).join("");
      
      pokesHtml = `
        <div class="event-pokes-title">Pokémony w wydarzeniu:</div>
        <div class="event-pokes-list">${pokeCards}</div>
      `;
    }

    const countdownHtml = getEventTimeStatus(ev);

    return `<div class="event-card ${ev.status}">
      <div class="event-header">
        <div>
          <div class="event-name">${ev.name}</div>
          <div class="event-meta">
            ${ev.start ? ev.start.replace("T", " ").substring(0, 16) : ""} → ${ev.end ? ev.end.replace("T", " ").substring(0, 16) : ""} · ${ev.type || "Wydarzenie"}
            ${countdownHtml}
          </div>
          ${ev.link ? `<a href="${ev.link}" target="_blank" style="font-size:11px">🔗 Szczegóły</a>` : ""}
        </div>
        <span class="event-status ${statusCls}">${statusLabel}</span>
      </div>
      ${bonuses ? `<div class="event-bonuses">${bonuses}</div>` : ""}
      ${pokesHtml}
      <div class="event-actions">
        <button class="btn btn-primary btn-sm" onclick="generateEventStrategy('${ev.id}')">🤖 Strategia AI</button>
        <div id="ev-loading-${ev.id}" style="display:none;align-items:center;gap:6px">
          <div class="spinner"></div><span style="font-size:11px;color:var(--muted)">Generuję…</span>
        </div>
      </div>
      <div id="ev-strategy-${ev.id}" style="display:none;margin-top:12px;padding-top:12px;border-top:1px solid var(--border)" class="ai-resp"></div>
    </div>`;
  }).join("") || `<p style="color:var(--muted);font-size:13px">Brak pasujących wydarzeń</p>`;
}

async function generateEventStrategy(evId) {
  const ev = S.events.find(e => e.id === evId);
  if (!ev) return;
  $(`ev-loading-${evId}`).style.display = "flex";
  try {
    const d = await api("/api/event-strategy", {
      method: "POST",
      body: JSON.stringify({ event: ev }),
    });
    const box = $(`ev-strategy-${evId}`);
    box.innerHTML = (d.cached ? '<span class="badge badge-lucky" style="margin-bottom:8px">z cache</span><br>' : "")
      + mdToHtml(d.response);
    box.style.display = "block";
  } catch (e) {
    alert("Błąd AI: " + e.message);
  }
  $(`ev-loading-${evId}`).style.display = "none";
}

// ── Tier list ─────────────────────────────────────────────────────────────────
async function loadTiers() {
  S.tiers = await api("/api/tier-list");
  renderTiers();
}

$("btn-refresh-tiers").addEventListener("click", async () => {
  $("btn-refresh-tiers").textContent = "⏳";
  await api("/api/tier-list/refresh", { method: "POST", body: "{}" });
  await loadTiers();
  $("btn-refresh-tiers").textContent = "🔄 Refresh teraz";
});

function renderTiers() {
  const cats = {
    raid:       "⚔️ Raidy",
    pvp_great:  "🏆 Great League",
    pvp_ultra:  "🏆 Ultra League",
    pvp_master: "🏆 Master League",
  };

  $("tier-by-cat").innerHTML = Object.entries(cats).map(([cat, label]) => {
    const byTier = {};
    Object.entries(S.tiers).forEach(([name, cats]) => {
      const t = cats[cat];
      if (t) (byTier[t] = byTier[t] || []).push(name);
    });

    const rows = ["S","A","B","C","D"].map(t => {
      const pokes = (byTier[t] || []).sort();
      if (!pokes.length) return "";
      return `<div class="tier-row">
        <div class="tier-label tier-${t.toLowerCase()}">${t}</div>
        <div class="tier-pokes">${pokes.map(n => `<span class="tier-chip">${n}</span>`).join("")}</div>
      </div>`;
    }).join("");

    return `<div class="card">
      <div class="card-title">${label}</div>
      <div class="tier-grid">${rows || '<p style="color:var(--muted);font-size:12px">Brak danych</p>'}</div>
    </div>`;
  }).join("");
}

// ── AI Modal ──────────────────────────────────────────────────────────────────
const modal    = $("ai-modal");
const aiClose  = $("ai-box-close");
const aiTitle  = $("ai-box-title");
const aiCached = $("ai-box-cached");
const aiLoading= $("ai-loading");
const aiContent= $("ai-content");

aiClose.addEventListener("click", () => modal.classList.remove("open"));
modal.addEventListener("click",   e => { if (e.target === modal) modal.classList.remove("open"); });
document.addEventListener("keydown", e => { if (e.key === "Escape") modal.classList.remove("open"); });

function openModal(title) {
  aiTitle.textContent   = title;
  aiCached.style.display= "none";
  aiContent.innerHTML   = "";
  aiLoading.style.display = "flex";
  modal.classList.add("open");
}

function setModalContent(html, cached) {
  aiLoading.style.display  = "none";
  aiContent.innerHTML      = html;
  aiCached.style.display   = cached ? "inline-block" : "none";
}

async function showRaidCounters(bossName) {
  const title = _lang === "pl" ? `Najlepsze kontry na: ${bossName}` : `Best counters for: ${bossName}`;
  openModal(title);
  try {
    const res = await fetch(`/api/raid-counters?boss=${encodeURIComponent(bossName)}`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "Błąd pobierania danych");
    }
    const data = await res.json();
    
    let html = "";
    if (data.boss_types) {
      const typesHtml = data.boss_types.map(t => `<span class="badge" style="background:var(--bg3);border:1px solid var(--border);text-transform:uppercase;font-size:10px">${t}</span>`).join(" ");
      html += `<div style="margin-bottom:15px;font-size:12px;color:var(--muted)">
        ${_lang === "pl" ? "Typy bossa:" : "Boss types:"} ${typesHtml}
      </div>`;
    }
    
    if (data.counters && data.counters.length > 0) {
      html += `<div class="tbl-wrap">
        <table style="width:100%;font-size:12px">
          <thead>
            <tr>
              <th>Pokemon</th>
              <th>CP</th>
              <th>Lvl</th>
              <th>IV</th>
              <th>${_lang === "pl" ? "Szybki atak" : "Fast Move"}</th>
              <th>${_lang === "pl" ? "Ładowany atak" : "Charged Move"}</th>
              <th style="text-align:right">${_lang === "pl" ? "Wynik" : "Score"}</th>
            </tr>
          </thead>
          <tbody>`;
          
      data.counters.forEach(c => {
        const shinyBadge = c.shiny ? `<span style="color:var(--yellow)" title="Shiny">✨</span>` : "";
        const shadowBadge = c.shadow ? `<span class="badge badge-shadow" style="font-size:8px;padding:1px 4px">Shadow</span>` : "";
        const luckyBadge = c.lucky ? `<span style="color:var(--accent)" title="Lucky">🍀</span>` : "";
        
        html += `<tr>
          <td style="font-weight:700">
            ${c.name} ${shinyBadge} ${shadowBadge} ${luckyBadge}
          </td>
          <td class="mono">${c.cp}</td>
          <td class="mono">${c.lvl}</td>
          <td class="mono" style="color:var(--accent)">${c.iv_pct}%</td>
          <td>
            <span class="move-tag type-${c.fast_move_type}" style="font-size:10px">${c.fast_move}</span>
          </td>
          <td>
            <span class="move-tag type-${c.charged_move_type}" style="font-size:10px">${c.charged_move}</span>
          </td>
          <td style="text-align:right;font-weight:800;color:var(--green)">
            ${c.counter_score}
          </td>
        </tr>`;
      });
      
      html += `</tbody></table></div>`;
    } else {
      html += `<p class="alert alert-info">${_lang === "pl" ? "Nie masz żadnych Pokémonów w plecaku, które mogłyby skontrować tego bossa." : "You do not have any Pokémon in your box to counter this boss."}</p>`;
    }
    setModalContent(html, false);
  } catch (err) {
    setModalContent(`<p class="alert alert-err">${_lang === "pl" ? "Błąd: " : "Error: "} ${err.message}</p>`, false);
  }
}

async function analyzeOnePokemon(idx) {
  const p = S.pokemons[idx];
  if (!p) return;
  openModal(`${p.name} — Analiza AI`);
  try {
    const d = await api("/api/analyze-pokemon", {
      method: "POST",
      body: JSON.stringify({ pokemon: p }),
    });
    setModalContent(mdToHtml(d.response), d.cached);
  } catch (e) {
    setModalContent(`<p class="alert alert-err">Błąd: ${e.message}</p>`, false);
  }
}

// ── Config & cache stats ──────────────────────────────────────────────────────
async function loadConfig() {
  const cfg = await api("/api/config");
  $("cfg-provider").value = cfg.provider;
}

async function loadCacheStats() {
  const s = await api("/api/cache/stats");
  $("cs-total").textContent = s.total;
  $("cs-today").textContent = s.today;
  $("cs-saved").textContent = `~${s.est_saved_usd}`;
}

// ── Raid ──────────────────────────────────────────────────────────────────────
let _raidData = [];
async function loadRaid() {
  _raidData = await api("/api/raid-candidates");
  renderRaid();
}

function renderRaid() {
  $("raid-tbody").innerHTML = _raidData.map((p, i) => {
    const tiers = p.tiers || {};
    const tb = Object.entries(tiers).map(([cat, t]) =>
      `<span class="badge badge-${t.charAt(0).toLowerCase()}">${cat.split("_").pop().toUpperCase()} ${t}</span>`).join("");
    const tags = [
      p.shiny  ? `<span class="badge badge-shiny">✨</span>` : "",
      p.shadow ? `<span class="badge badge-shadow">Shadow</span>` : "",
      p.hundo  ? `<span class="badge badge-hundo">💯</span>` : "",
      p.lucky  ? `<span class="badge badge-lucky">🍀</span>` : "",
    ].join("");
    
    let movesetHtml = '<div style="display: flex; flex-direction: column; gap: 4px; line-height: 1.2;">';
    if (p.pve_combos && p.pve_combos.length > 0) {
      p.pve_combos.forEach((combo) => {
        const fClean = combo.fast_name.replace('*', '');
        const cClean = combo.charged_name.replace('*', '');
        const isMatch = p.curr_moves && p.curr_moves.includes(fClean) && p.curr_moves.includes(cClean);
        
        const bullet = isMatch ? '<span style="color: var(--green); font-weight: bold; margin-right: 4px;">✔️</span>' : '<span style="color: #64748b; margin-right: 4px;">•</span>';
        const color = isMatch ? 'color: var(--green); font-weight: 600;' : 'color: #94a3b8; font-size: 11px;';
        
        const typeLabel = combo.fast_type === combo.charged_type ? combo.fast_type : `${combo.fast_type}/${combo.charged_type}`;
        
        movesetHtml += `
          <div style="display: flex; align-items: center; ${color}">
            ${bullet}
            <span>${combo.fast_name} + ${combo.charged_name}</span>
            <span style="font-size: 9px; color: #64748b; margin-left: 6px; font-weight: normal;">(${typeLabel})</span>
          </div>`;
      });
    } else {
      movesetHtml += '<div style="color: var(--muted);">—</div>';
    }
    movesetHtml += '</div>';

    return `<tr>
      <td style="color:var(--muted);font-weight:700;font-family:var(--fm)">${i+1}</td>
      <td class="name-cell">
        ${p.nick ? `<span data-tooltip="${p.name}">${p.nick}</span>` : p.name}
        ${p.move1_name ? `
        <div class="moves-row" style="margin-top: 3px;">
          <span class="move-tag type-${p.move1_type}" style="font-size: 9px; padding: 2px 4px;">${p.move1_name}</span>
          ${p.move2_name ? `<span class="move-tag type-${p.move2_type}" style="font-size: 9px; padding: 2px 4px;">${p.move2_name}</span>` : ''}
          ${p.move3_name ? `<span class="move-tag type-${p.move3_type}" style="font-size: 9px; padding: 2px 4px;">${p.move3_name}</span>` : ''}
        </div>` : ''}
      </td>
      <td class="cp-cell">${p.cp}</td>
      <td class="mono">${p.lvl}</td>
      <td class="${ivClass(p.iv_pct)}">${p.iv_pct}%</td>
      <td class="mono">${p.iv_a}/${p.iv_d}/${p.iv_s}</td>
      <td style="color:var(--cyan);font-weight:600;font-family:var(--fm)">${p.max_cp ? p.max_cp.toLocaleString() : "—"}</td>
      <td><div class="mono" style="text-align: left;">${movesetHtml}</div></td>
      <td>${tb || '<span style="color:var(--muted);font-size:10px">—</span>'}</td>
      <td>${tags}</td>
      <td><button class="btn-ai" onclick="analyzeOnePokemon(${S.pokemons.indexOf(S.pokemons.find(x=>x.pid===p.pid&&x.cp===p.cp))})">🤖 AI</button></td>
    </tr>`;
  }).join("") || `<tr><td colspan="11" style="padding:24px;text-align:center;color:var(--muted)">Brak danych — wgraj plik JSON</td></tr>`;
}

// ── PvP ───────────────────────────────────────────────────────────────────────
let _pvpData = {GL:[], UL:[], ML:[]};
let _pvpLocalTeams = {GL:[], UL:[], ML:[]};
let _pvpBestByRole = {GL: null, UL: null, ML: null};
let _pvpLeague = "GL";

$$(".tab-sub").forEach(btn => {
  btn.addEventListener("click", () => {
    $$(".tab-sub").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    _pvpLeague = btn.dataset.league;
    $("pvp-ai-result").style.display = "none";
    if (!_pvpData[_pvpLeague].length) {
      loadPvP(_pvpLeague);
    } else {
      renderPvP();
      renderLocalTeams(_pvpLocalTeams[_pvpLeague]);
      renderBestByRole(_pvpBestByRole[_pvpLeague]);
    }
  });
});

async function loadPvP(league) {
  const res = await api(`/api/pvp-candidates?league=${league}`);
  _pvpData[league] = res.candidates || [];
  _pvpLocalTeams[league] = res.local_teams || [];
  _pvpBestByRole[league] = res.best_by_role || { leads: [], switches: [], closers: [] };
  if (_pvpLeague === league) {
    renderPvP();
    renderLocalTeams(_pvpLocalTeams[league]);
    renderBestByRole(_pvpBestByRole[league]);
  }
}

function renderBestByRole(data) {
  const container = $("pvp-best-by-role");
  if (!container) return;
  if (!data || (!data.leads.length && !data.switches.length && !data.closers.length)) {
    container.style.display = "none";
    return;
  }
  container.style.display = "grid";
  
  const isPl = _lang === "pl";
  
  const makeList = (pokes) => {
    if (!pokes || pokes.length === 0) return `<div style="font-size:11px;color:var(--muted)">${isPl ? "Brak kandydatów" : "No candidates"}</div>`;
    return pokes.map(p => `
      <div style="display:flex; justify-content:space-between; align-items:center; background:var(--bg3); padding:6px 10px; border-radius:6px; border:1px solid var(--border2);">
        <b style="font-size:11px; color:var(--text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:110px;" title="${p.name}">${p.name}</b>
        <div style="display:flex; gap:6px; font-family:var(--fm); font-size:9px;">
          <span style="color:var(--muted);">CP ${p.cp}</span>
          <span style="color:var(--accent);">Rank #${p.pvp_rank}</span>
        </div>
      </div>
    `).join("");
  };

  container.innerHTML = `
    <!-- LEADS -->
    <div style="background:var(--bg3); padding:10px; border-radius:8px; border:1px solid var(--border2); display:flex; flex-direction:column; gap:6px;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size:10px; font-weight:700; color:var(--muted); text-transform:uppercase; display:inline-flex; align-items:center; gap:4px;">
          🚀 ${isPl ? "Liderzy (Leads)" : "Leads"}
          <span style="cursor:help; font-size:10px; color:var(--muted)" data-tooltip="${isPl ? 'Rozpoczynają walkę. Wywierają presję lub wygrywają neutralne pojedynki.' : 'Start the battle. Exert shield pressure or win neutral matchups.'}">ℹ️</span>
        </span>
      </div>
      <div style="display:flex; flex-direction:column; gap:4px;">
        ${makeList(data.leads)}
      </div>
    </div>
    
    <!-- SWITCHES -->
    <div style="background:var(--bg3); padding:10px; border-radius:8px; border:1px solid var(--border2); display:flex; flex-direction:column; gap:6px;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size:10px; font-weight:700; color:var(--muted); text-transform:uppercase; display:inline-flex; align-items:center; gap:4px;">
          🛡️ ${isPl ? "Bezpieczne zmiany" : "Safe Switches"}
          <span style="cursor:help; font-size:10px; color:var(--muted)" data-tooltip="${isPl ? 'Wprowadzane po przegranym leadzie. Mają dużą wytrzymałość (bulk) i bezpieczne pojedynki.' : 'Safe switch-in after losing lead. High bulk and safe matchups.'}">ℹ️</span>
        </span>
      </div>
      <div style="display:flex; flex-direction:column; gap:4px;">
        ${makeList(data.switches)}
      </div>
    </div>
    
    <!-- CLOSERS -->
    <div style="background:var(--bg3); padding:10px; border-radius:8px; border:1px solid var(--border2); display:flex; flex-direction:column; gap:6px;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size:10px; font-weight:700; color:var(--muted); text-transform:uppercase; display:inline-flex; align-items:center; gap:4px;">
          💣 ${isPl ? "Finiszerzy (Closers)" : "Closers"}
          <span style="cursor:help; font-size:10px; color:var(--muted)" data-tooltip="${isPl ? 'Kończą walkę. Zadają wysokie obrażenia, gdy przeciwnik nie ma już tarcz.' : 'Close the battle. Deal heavy damage when opponent has no shields left.'}">ℹ️</span>
        </span>
      </div>
      <div style="display:flex; flex-direction:column; gap:4px;">
        ${makeList(data.closers)}
      </div>
    </div>
  `;
}

function renderLocalTeams(teams) {
  const container = $("pvp-local-teams-list");
  if (!teams || teams.length === 0) {
    $("pvp-local-teams-card").style.display = "none";
    return;
  }
  
  const leagueColor = { GL: "var(--cyan)", UL: "var(--purple)", ML: "var(--yellow)" }[_pvpLeague];
  
  container.innerHTML = teams.map((team, idx) => {
    const isPl = _lang === "pl";
    const leadLbl = isPl ? "Lider (Lead)" : "Lead";
    const switchLbl = isPl ? "Bezpieczna Zmiana" : "Safe Switch";
    const closerLbl = isPl ? "Closer" : "Closer";
    const teamLbl = isPl ? `Skład #${idx + 1}` : `Team #${idx + 1}`;
    const descText = isPl 
      ? `Zbalansowany skład z liderem <b>${team.lead.name}</b>, bezpieczną zmianą <b>${team.switch.name}</b> i zamykającym <b>${team.closer.name}</b>.`
      : `Balanced team with <b>${team.lead.name}</b> as lead, <b>${team.switch.name}</b> as safe switch, and <b>${team.closer.name}</b> as closer.`;

    return `
      <div style="background: var(--bg3); padding: 12px; border-radius: 8px; border: 1px solid var(--border2); display: flex; flex-direction: column; gap: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <b style="color: var(--text); font-size: 13px;">${teamLbl}</b>
          <span style="font-size: 11px; color: ${leagueColor}; font-weight: 700; font-family: var(--fm);">${_pvpLeague}</span>
        </div>
        
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 4px;">
          <!-- LEAD -->
          <div style="display: flex; flex-direction: column; align-items: center; text-align: center; background: var(--bg2); padding: 8px; border-radius: 6px; border: 1px solid var(--border); overflow: hidden;">
            <span style="font-size: 8px; color: var(--muted); text-transform: uppercase; font-weight: 700;">${leadLbl}</span>
            <b style="font-size: 11px; color: var(--text); margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%;" title="${team.lead.name}">${team.lead.name}</b>
            <span style="font-size: 10px; color: var(--muted); margin-top: 2px; font-family: var(--fm)">CP ${team.lead.cp}</span>
            <span style="font-size: 9px; color: var(--accent); font-family: var(--fm)">Rank #${team.lead.pvp_rank}</span>
          </div>
          <!-- SWITCH -->
          <div style="display: flex; flex-direction: column; align-items: center; text-align: center; background: var(--bg2); padding: 8px; border-radius: 6px; border: 1px solid var(--border); overflow: hidden;">
            <span style="font-size: 8px; color: var(--muted); text-transform: uppercase; font-weight: 700;">${switchLbl}</span>
            <b style="font-size: 11px; color: var(--text); margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%;" title="${team.switch.name}">${team.switch.name}</b>
            <span style="font-size: 10px; color: var(--muted); margin-top: 2px; font-family: var(--fm)">CP ${team.switch.cp}</span>
            <span style="font-size: 9px; color: var(--accent); font-family: var(--fm)">Rank #${team.switch.pvp_rank}</span>
          </div>
          <!-- CLOSER -->
          <div style="display: flex; flex-direction: column; align-items: center; text-align: center; background: var(--bg2); padding: 8px; border-radius: 6px; border: 1px solid var(--border); overflow: hidden;">
            <span style="font-size: 8px; color: var(--muted); text-transform: uppercase; font-weight: 700;">${closerLbl}</span>
            <b style="font-size: 11px; color: var(--text); margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%;" title="${team.closer.name}">${team.closer.name}</b>
            <span style="font-size: 10px; color: var(--muted); margin-top: 2px; font-family: var(--fm)">CP ${team.closer.cp}</span>
            <span style="font-size: 9px; color: var(--accent); font-family: var(--fm)">Rank #${team.closer.pvp_rank}</span>
          </div>
        </div>
        
        <div style="font-size: 11px; color: var(--muted); font-style: italic; line-height: 1.4; margin-top: 2px;">
          💡 ${descText}
        </div>
      </div>
    `;
  }).join("");
  
  $("pvp-local-teams-card").style.display = "block";
}

function pvpRankBadge(rank, total, pct) {
  if (!rank || !total) return '<span style="color:var(--muted);font-size:10px">—</span>';
  const frac = rank / total;
  let cls;
  if (rank === 1)       cls = "rank-1";
  else if (frac <= .01) cls = "rank-top1";
  else if (frac <= .05) cls = "rank-top5";
  else if (frac <= .10) cls = "rank-top10";
  else                  cls = "rank-ok";
  const pctStr = pct != null ? ` ${pct}%` : "";
  return `<span class="rank-badge ${cls}" title="#${rank} z ${total}">#${rank}${pctStr}</span>`;
}

function renderPvP() {
  const data = _pvpData[_pvpLeague];
  const leagueColor = {GL:"var(--cyan)", UL:"var(--purple)", ML:"var(--yellow)"}[_pvpLeague];
  $("pvp-tbody").innerHTML = data.map((p, i) => {
    const tiers = p.tiers || {};
    let tb = "";
    const keyMap = { GL: "pvp_great", UL: "pvp_ultra", ML: "pvp_master" };
    const t = tiers[keyMap[_pvpLeague]];
    if (t) {
      tb = `<span class="badge badge-${t.charAt(0).toLowerCase()}">${_pvpLeague} ${t}</span>`;
    }
    const tags = [
      p.shiny  ? `<span class="badge badge-shiny">✨</span>` : "",
      p.shadow ? `<span class="badge badge-shadow">Shadow</span>` : "",
      p.hundo  ? `<span class="badge badge-hundo">💯</span>` : "",
      p.lucky  ? `<span class="badge badge-lucky">🍀</span>` : "",
    ].join("");
    const rankBadge = pvpRankBadge(p.pvp_rank, p.pvp_rank_total, p.pvp_rank_pct);
    return `<tr>
      <td style="color:var(--muted);font-weight:700;font-family:var(--fm)">${i+1}</td>
      <td class="name-cell">${p.name}</td>
      <td class="cp-cell">${p.cp}</td>
      <td style="font-weight:700;color:${leagueColor};font-family:var(--fm)">${p.pvp_cp || "—"}</td>
      <td class="mono">${p.pvp_lvl || p.lvl}</td>
      <td class="${ivClass(p.iv_pct)}">${p.iv_pct}%</td>
      <td class="mono">${p.iv_a}/${p.iv_d}/${p.iv_s}</td>
      <td>
        ${rankBadge}
        <div style="font-size: 9px; color: var(--muted); margin-top: 2px; font-family: var(--fm); white-space: nowrap;">Ideal: ${p.pvp_ideal || "—"}</div>
      </td>
      <td>${tb || '<span style="color:var(--muted);font-size:10px">—</span>'}</td>
      <td>${tags}</td>
      <td><button class="btn-ai" onclick="analyzeOnePokemon(${S.pokemons.indexOf(S.pokemons.find(x=>x.pid===p.pid&&x.cp===p.cp))})">🤖 AI</button></td>
    </tr>`;
  }).join("") || `<tr><td colspan="11" style="padding:24px;text-align:center;color:var(--muted)">Brak danych</td></tr>`;
}

$("btn-analyze-pvp").addEventListener("click", async () => {
  const btn = $("btn-analyze-pvp");
  btn.disabled = true;
  btn.textContent = "⏳ Analizuję składy PvP...";
  
  try {
    const d = await api("/api/analyze-pvp-teams", {
      method: "POST",
      body: JSON.stringify({ league: _pvpLeague })
    });
    
    const leagueNames = { GL: "Great League (CP ≤1500)", UL: "Ultra League (CP ≤2500)", ML: "Master League" };
    const leagueName = leagueNames[_pvpLeague] || _pvpLeague;
    $("pvp-ai-title").innerHTML = `Analiza składów PvP dla ${leagueName} ` 
      + (d.cached ? '<span class="badge badge-lucky">z cache</span>' : "");
    $("pvp-ai-body").innerHTML = mdToHtml(d.response);
    $("pvp-ai-result").style.display = "block";
  } catch (e) {
    alert("Błąd AI: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "🤖 Analiza AI — składy PvP";
  }
});

// ── Rozwój ────────────────────────────────────────────────────────────────────
let _developData = null;

async function loadDevelop() {
  _developData = await api("/api/develop-candidates");
  renderDevelop();
}

function _devPokeIdx(p) {
  return S.pokemons.indexOf(S.pokemons.find(x => x.pid === p.pid && x.cp === p.cp));
}

function renderDevelop() {
  if (!_developData) return;
  const d = _developData;

  $("dev-evolve-tbody").innerHTML = d.evolve.map(p => {
    const tags = [p.shiny ? `<span class="badge badge-shiny">✨</span>` : "",
                  p.lucky ? `<span class="badge badge-lucky">🍀</span>` : ""].join("");
    const tc = (p.final_tier && p.final_tier.startsWith("S")) ? "badge-s" : "badge-a";
    
    let limitBadge = "";
    if (p.final_cp > 2500) {
      limitBadge = ` <span class="badge badge-err" style="font-size:9px;" data-tooltip="Przekracza limit Ultra League (>2500)">>2500</span>`;
    } else if (p.final_cp > 1500) {
      limitBadge = ` <span class="badge badge-warn" style="font-size:9px;" data-tooltip="Przekracza limit Great League (>1500)">>1500</span>`;
    }

    return `<tr>
      <td class="name-cell">${p.name}</td>
      <td class="cp-cell">${p.cp}</td>
      <td class="mono">${p.lvl}</td>
      <td class="${ivClass(p.iv_pct)}">${p.iv_pct}%</td>
      <td style="color:var(--cyan);font-weight:700">→ ${p.final_name} <span style="color:var(--text);font-weight:400;font-size:11px;">(CP ${p.final_cp || '?'})</span>${limitBadge}</td>
      <td><span class="badge ${tc}">${p.final_tier}</span></td>
      <td>${tags}</td>
      <td><button class="btn-ai" onclick="analyzeOnePokemon(${_devPokeIdx(p)})">🤖 AI</button></td>
    </tr>`;
  }).join("") || `<tr><td colspan="8" style="padding:16px;text-align:center;color:var(--muted)">Brak kandydatów — potrzeba IV≥80% + meta końcowa forma</td></tr>`;

  $("dev-powerup-tbody").innerHTML = d.power_up.map(p => {
    const pIdx = _devPokeIdx(p);
    let options = '<option value="">Lvl ↓</option>';
    let minLvl = p.lvl + 0.5;
    if (minLvl <= 50) {
      for (let l = minLvl; l <= 50; l += 0.5) {
        options += `<option value="${l}">${l}</option>`;
      }
    }
    return `<tr>
      <td class="name-cell">${p.name}</td>
      <td class="cp-cell">${p.cp}</td>
      <td class="mono">${p.lvl}</td>
      <td class="${ivClass(p.iv_pct)}">${p.iv_pct}%</td>
      <td class="mono">${p.iv_a}/${p.iv_d}/${p.iv_s}</td>
      <td>
        <select onchange="recalcPowerup(this, ${pIdx})" style="width:75px; padding:2px; font-size:11px; background:var(--bg3); color:var(--text); border:1px solid var(--border); border-radius:4px;">
          ${options}
        </select>
      </td>
      <td class="calc-cell" id="pow-calc-${pIdx}" style="min-width:120px;"><span style="color:var(--muted);font-size:10px">—</span></td>
      <td><button class="btn-ai" onclick="analyzeOnePokemon(${pIdx})">🤖 AI</button></td>
    </tr>`;
  }).join("") || `<tr><td colspan="8" style="padding:16px;text-align:center;color:var(--muted)">Brak kandydatów — meta pokemony poniżej L40 z IV≥80%</td></tr>`;

  $("dev-purify-tbody").innerHTML = d.purify.map(p => {
    const pA = Math.min(15, p.iv_a+2), pD = Math.min(15, p.iv_d+2), pS = Math.min(15, p.iv_s+2);
    const tc = (p.best_tier && p.best_tier.startsWith("S")) ? "badge-s" : (p.best_tier && p.best_tier.startsWith("A")) ? "badge-a" : "";
    return `<tr>
      <td class="name-cell">${p.name}</td>
      <td class="cp-cell">${p.cp}</td>
      <td class="${ivClass(p.iv_pct)}">${p.iv_pct}%</td>
      <td class="${ivClass(p.purified_iv)}" style="font-weight:700">${p.purified_iv}%</td>
      <td class="mono">${p.iv_a}/${p.iv_d}/${p.iv_s} → <span style="color:var(--green)">${pA}/${pD}/${pS}</span></td>
      <td>${tc ? `<span class="badge ${tc}">${p.best_tier}</span>` : `<span style="color:var(--muted)">—</span>`}</td>
      <td><button class="btn-ai" onclick="analyzeOnePokemon(${_devPokeIdx(p)})">🤖 AI</button></td>
    </tr>`;
  }).join("") || `<tr><td colspan="7" style="padding:16px;text-align:center;color:var(--muted)">Brak shadow pokemonów z IV≥78 przed oczyszczeniem</td></tr>`;

  $("dev-tm-tbody").innerHTML = d.elite_tm.map(p => {
    const pidx = _devPokeIdx(p);
    const pvpOpt = p.pvp_optimal && p.pvp_optimal.length ? p.pvp_optimal.join(" + ") : "—";
    const pveOpt = p.pve_optimal && p.pve_optimal.length ? p.pve_optimal.join(" + ") : "—";
    
    let allWarnings = [...new Set((p.pvp_warnings || []).concat(p.pve_warnings || []))];
    let tmLabel = "Zgodne / OK";
    let tmStyle = "color:var(--green); font-size:10px;";
    if (allWarnings.length > 0) {
      tmLabel = allWarnings.map(w => w.split(" ").slice(2).join(" ")).join("<br>");
      tmStyle = "color:var(--yellow); font-size:10px; line-height:1.25;";
    }
    
    const currMoves = [p.move1_name, p.move2_name, p.move3_name].filter(Boolean).join(" + ");

    return `<tr>
      <td class="name-cell">${p.name}</td>
      <td class="cp-cell">${p.cp}</td>
      <td style="font-size:10px; color:var(--muted); line-height:1.25;">${currMoves}</td>
      <td style="font-size:10px; color:var(--text); line-height:1.25;">${pvpOpt}</td>
      <td style="font-size:10px; color:var(--text); line-height:1.25;">${pveOpt}</td>
      <td style="${tmStyle}">${tmLabel}</td>
    </tr>`;
  }).join("") || `<tr><td colspan="6" style="padding:16px;text-align:center;color:var(--muted)">Brak kandydatów — meta pokemony na L≥35</td></tr>`;

  const isPl = _lang === "pl";
  const populatePreview = (id, list) => {
    const el = $(id);
    if (!el) return;
    const content = $(id.replace("-preview", "-content"));
    // If the card is expanded, we do not show the preview chips
    if (content && content.style.display !== "none") {
      el.style.display = "none";
      return;
    }
    el.style.display = "flex";
    if (!list || list.length === 0) {
      el.innerHTML = `<span style="font-size:10px; color:var(--muted); font-style:italic;">${isPl ? 'Brak kandydatów' : 'No candidates'}</span>`;
      return;
    }
    el.innerHTML = list.slice(0, 3).map(p => `
      <span class="badge" style="background:var(--bg3); border:1px solid var(--border2); color:var(--text); padding: 2px 6px; border-radius: 4px; font-size:10px; font-weight:normal;">
        ${p.name} <span style="color:var(--muted); font-size:9px;">(CP ${p.cp})</span>
      </span>
    `).join(" ");
  };
  populatePreview("dev-evolve-preview", d.evolve);
  populatePreview("dev-powerup-preview", d.power_up);
  populatePreview("dev-purify-preview", d.purify);
  populatePreview("dev-tm-preview", d.elite_tm);
}

$("btn-save-cfg").addEventListener("click", async () => {
  const body = {
    provider:      $("cfg-provider").value,
    gemini_key:    $("cfg-gemini").value,
    openai_key:    $("cfg-openai").value,
    anthropic_key: $("cfg-anthropic").value,
    azure_key:     $("cfg-azure-key").value,
    azure_endpoint:$("cfg-azure-ep").value,
  };
  await api("/api/config", { method: "POST", body: JSON.stringify(body) });
  const saved = $("cfg-saved");
  saved.style.display = "inline";
  setTimeout(() => { saved.style.display = "none"; }, 2500);
});

// ── Translations ─────────────────────────────────────────────────────────────
let _lang = localStorage.getItem("pogo_lang") || "pl";

const translations = {
  pl: {
    headerSub: "Wgraj PGSStats.json żeby zacząć",
    changeFile: "↺ Zmień plik",
    totalPoke: "Pokemon",
    shinyPoke: "✨ Shiny",
    hundoPoke: "💯 Hundo",
    shadowPoke: "Shadow",
    luckyPoke: "🍀 Lucky",
    dustPoke: "⭐ Stardust",
    btnAnalyzeItems: "🤖 Analiza AI — co i na kogo",
    btnAnalyzePvp: "🤖 Analiza AI — składy PvP",
    btnSaveCfg: "Zapisz ustawienia",
    cfgSaved: "Zapisano!",
    settingsTitle: "⚙️ Ustawienia",
    settingsAiCfgTitle: "Konfiguracja AI",
    settingsProviderH3: "Provider",
    settingsApiKeysH3: "Klucze API",
    settingsCacheTitle: "📦 Cache AI (SQLite)",
    settingsCacheDesc: "Odpowiedzi AI zapisywane wg hasha statystyk — ta sama kombinacja IV/CP nie kosztuje tokenu drugi raz.",
    settingsCsTotal: "Łącznie:",
    settingsCsToday: "Dziś:",
    settingsCsSaved: "Szac. zaoszczędzone:",
    lblRegexPogo: "🔍 Regex PoGO",
    lblRoptSafe: "bez shiny/shadow/lucky",
    lblRoptIv: "bez 3★+",
    lblRoptLegendary: "bez legendary",
    lblRoptCpLbl: "max CP:",
    lblRoptCpMinLbl: "chroń CP≥",
    lblRoptPvp: "chroń PvP",
    lblRoptLvl: "chroń lvl≥35",
    btnCopyRegex: "📋 Kopiuj regex",
    lblTagsLbl: "Tagi:",
    btnExportCsv: "📥 Export CSV",
    btnRawCsv: "📦 Raw JSON→CSV",
    btnInventoryCsv: "💰 Ekwipunek CSV",
    roptCpValPlaceholder: "np. 500"
  },
  en: {
    headerSub: "Upload PGSStats.json to begin",
    changeFile: "↺ Change file",
    totalPoke: "Pokémon",
    shinyPoke: "✨ Shiny",
    hundoPoke: "💯 Hundo",
    shadowPoke: "Shadow",
    luckyPoke: "🍀 Lucky",
    dustPoke: "⭐ Stardust",
    btnAnalyzeItems: "🤖 AI Analysis — what to use on whom",
    btnAnalyzePvp: "🤖 AI Analysis — PvP Teams",
    btnSaveCfg: "Save settings",
    cfgSaved: "Saved!",
    settingsTitle: "⚙️ Settings",
    settingsAiCfgTitle: "AI Configuration",
    settingsProviderH3: "Provider",
    settingsApiKeysH3: "API Keys",
    settingsCacheTitle: "📦 AI Cache (SQLite)",
    settingsCacheDesc: "AI responses cached by stats hash — the same IV/CP combination never costs a second API call.",
    settingsCsTotal: "Total:",
    settingsCsToday: "Today:",
    settingsCsSaved: "Est. savings:",
    lblRegexPogo: "🔍 Regex PoGO",
    lblRoptSafe: "no shiny/shadow/lucky",
    lblRoptIv: "no 3★+",
    lblRoptLegendary: "no legendary",
    lblRoptCpLbl: "max CP:",
    lblRoptCpMinLbl: "protect CP≥",
    lblRoptPvp: "protect PvP",
    lblRoptLvl: "protect lvl≥35",
    btnCopyRegex: "📋 Copy regex",
    lblTagsLbl: "Tags:",
    btnExportCsv: "📥 Export CSV",
    btnRawCsv: "📦 Raw JSON→CSV",
    btnInventoryCsv: "💰 Inventory CSV",
    roptCpValPlaceholder: "e.g. 500"
  }
};

const thMap = {
  pl: {
    "Pokemon (pre-evo)": "Pokemon (pre-evo)", "→ Ewolucja": "→ Ewolucja", "Docelowy Pokemon": "Docelowy Pokemon",
    "Docelowy Tier": "Docelowy Tier", "Lvl Przed": "Lvl Przed", "Lvl Po": "Lvl Po", "Koszt": "Koszt",
    "Ruch Legacy": "Ruch Legacy", "Typ ruchu": "Typ ruchu", "Pokemon": "Pokemon", "Akt. CP": "Akt. CP",
    "CP w lidze": "CP w lidze", "Lvl": "Lvl", "IV%": "IV%", "A/D/S": "A/D/S", "Max CP": "Max CP",
    "Tiers": "Tiers", "Tagi": "Tagi", "AI": "AI", "Rank IV": "Rank IV", "Est. DPS×TDO": "Est. DPS×TDO",
    "IV teraz": "IV teraz", "IV po ocz.": "IV po ocz.", "A/D/S → po oczyszcz.": "A/D/S → po oczyszcz."
  },
  en: {
    "Pokemon (pre-evo)": "Pokémon (pre-evo)", "→ Ewolucja": "→ Evolution", "Docelowy Pokemon": "Target Pokémon",
    "Docelowy Tier": "Target Tier", "Lvl Przed": "Lvl Before", "Lvl Po": "Lvl After", "Koszt": "Cost",
    "Ruch Legacy": "Legacy Move", "Typ ruchu": "Move Type", "Pokemon": "Pokémon", "Akt. CP": "Current CP",
    "CP w lidze": "CP in League", "Lvl": "Lvl", "IV%": "IV%", "A/D/S": "A/D/S", "Max CP": "Max CP",
    "Tiers": "Tiers", "Tagi": "Tags", "AI": "AI", "Rank IV": "Rank IV", "Est. DPS×TDO": "Est. DPS×TDO",
    "IV teraz": "Current IV", "IV po ocz.": "IV after Pur.", "A/D/S → po oczyszcz.": "A/D/S → after Pur."
  }
};

const optionMap = {
  pl: {
    "Wszystkie": "Wszystkie", "✨ Shiny": "✨ Shiny", "👻 Shadow": "👻 Shadow", "🍀 Lucky": "🍀 Lucky",
    "Tier S (meta)": "Tier S (meta)", "Tier A (meta)": "Tier A (meta)", "🗑️ Kandydaci do transferu": "🗑️ Kandydaci do transferu",
    "📅 2016–2018 (lucky)": "📅 2016–2018 (lucky)", "📅 2019–2022 (lucky)": "📅 2019–2022 (lucky)",
    "🏆 PvP Gemy GL (rank ≤250)": "🏆 PvP Gemy GL (rank ≤250)", "CP ↓": "CP ↓", "IV% ↓": "IV% ↓",
    "Level ↓": "Level ↓", "Nazwa A→Z": "Nazwa A→Z", "Wszystkie Pokemony": "Wszystkie Pokemony",
    "Wartościowe (S/A/B)": "Wartościowe (S/A/B)", "🟢 Aktywne": "🟢 Aktywne", "🔵 Nadchodzące": "🔵 Nadchodzące",
    "⬜ Zakończone": "⬜ Zakończone"
  },
  en: {
    "Wszystkie": "All", "✨ Shiny": "✨ Shiny", "👻 Shadow": "👻 Shadow", "🍀 Lucky": "🍀 Lucky",
    "Tier S (meta)": "Tier S (meta)", "Tier A (meta)": "Tier A (meta)", "🗑️ Kandydaci do transferu": "🗑️ Transfer Candidates (Trash)",
    "📅 2016–2018 (lucky)": "📅 2016–2018 (lucky)", "📅 2019–2022 (lucky)": "📅 2019–2022 (lucky)",
    "🏆 PvP Gemy GL (rank ≤250)": "🏆 PvP Gems GL (rank ≤250)", "CP ↓": "CP ↓", "IV% ↓": "IV% ↓",
    "Level ↓": "Level ↓", "Nazwa A→Z": "Name A→Z", "Wszystkie Pokemony": "All Pokémon",
    "Wartościowe (S/A/B)": "Valuable (S/A/B)", "🟢 Aktywne": "🟢 Active", "🔵 Nadchodzące": "🔵 Upcoming",
    "⬜ Zakończone": "⬜ Ended"
  }
};

const chipMap = {
  pl: { "Pokemon": "Pokemon ", "Shiny": " Shiny ", "Hundo": " Hundo ", "Shadow": " Shadow ", "Lucky": " Lucky ", "Stardust": " Stardust " },
  en: { "Pokemon": "Pokémon ", "Shiny": " Shiny ", "Hundo": " Hundo ", "Shadow": " Shadow ", "Lucky": " Lucky ", "Stardust": " Stardust " }
};

const pvpLabelMap = {
  pl: {
    "Ranga Sezonu": "Ranga Sezonu", "Wskaźnik Wygranych": "Wskaźnik Wygranych",
    "Najdłuższa seria": "Najdłuższa seria", "Zarobiony Stardust": "Zarobiony Stardust"
  },
  en: {
    "Ranga Sezonu": "Season Rank", "Wskaźnik Wygranych": "Win Rate",
    "Najdłuższa seria": "Longest Streak", "Zarobiony Stardust": "Stardust Earned"
  }
};

const devCards = {
  pl: {
    evolveTitle: "🥚 Do ewoluowania",
    evolveDesc: "Pokemony z IV ≥ 80%, których końcowa forma jest meta (tier S lub A). Ewolucja nie zmienia IV — warto ewoluować zanim będziesz power-upował.",
    powerupTitle: "⚡ Do ulepszenia (Power Up)",
    powerupDesc: "Meta pokemon (tier S/A) z IV ≥ 80% poniżej poziomu 40. Inwestycja w stardust opłaca się tylko dla meta okazów.",
    purifyTitle: "✨ Do oczyszczenia (Purify Shadow)",
    purifyDesc: "Shadow pokemony, których IV po oczyszczeniu (+2 do każdego, max 15) osiągnie ≥ 80%. Shadow bonus (+20% ataku) vs. lepsze IV — zapytaj AI co bardziej się opłaca.",
    tmTitle: "⚔️ Kandydaci na Elite TM",
    tmDesc: "Meta pokemon (tier S/A) na poziomie ≥ 35 — warte sprawdzenia czy mają optymalne ataki. Elite Fast/Charged TM pozwala nauczyć legacy lub ekskluzywnych ruchów."
  },
  en: {
    evolveTitle: "🥚 To Evolve",
    evolveDesc: "Pokémon with IV ≥ 80% whose final form is meta (tier S or A). Evolution does not change IVs — it is best to evolve before powering up.",
    powerupTitle: "⚡ To Power Up",
    powerupDesc: "Meta Pokémon (tier S/A) with IV ≥ 80% below level 40. Investing in stardust is only worth it for meta specimens.",
    purifyTitle: "✨ To Purify (Shadow)",
    purifyDesc: "Shadow Pokémon whose IV after purification (+2 to each stat, max 15) will reach ≥ 80%. Shadow bonus (+20% attack) vs. better IVs — ask AI what is more worth it.",
    tmTitle: "⚔️ Elite TM Candidates",
    tmDesc: "Meta Pokémon (tier S/A) at level ≥ 35 — worth checking if they have optimal moves. Elite Fast/Charged TM allows learning legacy or exclusive moves."
  }
};

function applyLanguage() {
  const t = translations[_lang];
  if (_lang === "pl") {
    $("lang-pl").style.opacity = "1";
    $("lang-pl").style.filter = "none";
    $("lang-en").style.opacity = "0.35";
    $("lang-en").style.filter = "grayscale(90%)";
  } else {
    $("lang-pl").style.opacity = "0.35";
    $("lang-pl").style.filter = "grayscale(90%)";
    $("lang-en").style.opacity = "1";
    $("lang-en").style.filter = "none";
  }

  const ids = {
    "header-sub": t.headerSub,
    "btn-analyze-items": t.btnAnalyzeItems,
    "btn-analyze-pvp": t.btnAnalyzePvp,
    "btn-save-cfg": t.btnSaveCfg,
    "cfg-saved": t.cfgSaved,
    "settings-panel-title": t.settingsTitle,
    "settings-ai-config-title": t.settingsAiCfgTitle,
    "settings-provider-h3": t.settingsProviderH3,
    "settings-apikeys-h3": t.settingsApiKeysH3,
    "settings-cache-title": t.settingsCacheTitle,
    "settings-cache-desc": t.settingsCacheDesc,
    "lbl-regex-pogo": t.lblRegexPogo,
    "btn-copy-regex": t.btnCopyRegex,
    "lbl-tags-lbl": t.lblTagsLbl,
    "btn-raw-csv": t.btnRawCsv,
    "btn-inventory-csv": t.btnInventoryCsv
  };
  for (const [id, text] of Object.entries(ids)) {
    const el = $(id);
    if (el && text) el.textContent = text;
  }

  // Cache stats labels contain a <b> child — update only the text node, not the number
  const csTotalLbl = $("cs-total-lbl");
  if (csTotalLbl) { const b = csTotalLbl.querySelector("b"); csTotalLbl.childNodes[0].nodeValue = t.settingsCsTotal + " "; if (b) csTotalLbl.appendChild(b); }
  const csTodayLbl = $("cs-today-lbl");
  if (csTodayLbl) { const b = csTodayLbl.querySelector("b"); csTodayLbl.childNodes[0].nodeValue = t.settingsCsToday + " "; if (b) csTodayLbl.appendChild(b); }
  const csSavedLbl = $("cs-saved-lbl");
  if (csSavedLbl) { const b = csSavedLbl.querySelector("b"); csSavedLbl.childNodes[0].nodeValue = t.settingsCsSaved + " "; if (b) csSavedLbl.appendChild(b); }

  const cpVal = $("ropt-cp-val");
  if (cpVal) cpVal.placeholder = t.roptCpValPlaceholder;

  const rawCsv = $("btn-raw-csv");
  if (rawCsv) rawCsv.title = _lang === "pl"
    ? "Pełny eksport 1:1 z PGSStats.json — wszystkie 80 pól + nazwa gatunku"
    : "Full 1:1 export from PGSStats.json — all 80 fields + species name";
    
  const invCsv = $("btn-inventory-csv");
  if (invCsv) invCsv.title = _lang === "pl"
    ? "Stardust, PokéCoiny, Rare Candy + pełna lista ekwipunku"
    : "Stardust, PokéCoins, Rare Candy + complete inventory listing";
  
  const uploadSub = document.querySelector(".upload-sub");
  if (uploadSub) uploadSub.innerHTML = _lang === "pl" 
    ? "Wgraj plik <strong>PGSStats.json</strong> (PGSharp) lub eksport <strong>.csv</strong> (PokéGenie)<br>aby przeanalizować swoje konto"
    : "Upload <strong>PGSStats.json</strong> (PGSharp) or <strong>.csv</strong> export (PokéGenie)<br>to analyze your account";

  const uploadHint = $("upload-hint-text");
  if (uploadHint) uploadHint.innerHTML = _lang === "pl"
    ? `📱 <a href="https://www.pgsharp.com/" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:none">PGSharp Settings</a> &nbsp;→&nbsp; Export account data na <strong>ON</strong> (na samym dole) &nbsp;→&nbsp; wybierz folder dla pliku <strong>pgsstats.json</strong>`
    : `📱 <a href="https://www.pgsharp.com/" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:none">PGSharp Settings</a> &nbsp;→&nbsp; Export account data to <strong>ON</strong> (at the bottom) &nbsp;→&nbsp; select folder for <strong>pgsstats.json</strong>`;

  const uploadTag = document.querySelector(".upload-tag");
  if (uploadTag) uploadTag.textContent = _lang === "pl"
    ? "📌 Plik czytany lokalnie — dane nie opuszczają maszyny"
    : "📌 File processed locally — data does not leave your machine";

  const uploadSmallBtn = document.querySelector("#upload-small .btn");
  if (uploadSmallBtn) uploadSmallBtn.textContent = t.changeFile;
  
  const sidebarHint = document.querySelector(".sidebar-hint");
  if (sidebarHint) sidebarHint.textContent = _lang === "pl" ? "Wgraj plik JSON lub CSV żeby zacząć" : "Upload JSON or CSV file to begin";

  const tabNames = {
    pokemon: _lang === "pl" ? "🎮 Pokemony" : "🎮 Pokémon",
    raid: _lang === "pl" ? "⚔️ Raidy" : "⚔️ Raids",
    pvp: "🏆 PvP",
    items: _lang === "pl" ? "🎒 Ekwipunek" : "🎒 Inventory",
    events: _lang === "pl" ? "📅 Eventy" : "📅 Events",
    tiers: _lang === "pl" ? "🥇 Tier Lista" : "🥇 Tier List",
    develop: _lang === "pl" ? "🔧 Rozwój" : "🔧 Develop",
    settings: _lang === "pl" ? "⚙️ Ustawienia" : "⚙️ Settings"
  };
  $$(".tab").forEach(tab => {
    const tabKey = tab.dataset.tab;
    if (tabNames[tabKey]) {
      if (tabKey === "pokemon") {
        tab.innerHTML = `${tabNames[tabKey]} <span class="tab-badge" id="tb-poke">${S.pokemons.length || ""}</span>`;
      } else {
        tab.textContent = tabNames[tabKey];
      }
    }
  });

  const panelTitles = {
    "panel-pokemon": _lang === "pl" ? "🎮 Pokemony" : "🎮 Pokémon",
    "panel-raid": _lang === "pl" ? "⚔️ Raidy" : "⚔️ Raids",
    "panel-pvp": "🏆 PvP",
    "panel-items": _lang === "pl" ? "🎒 Ekwipunek" : "🎒 Inventory",
    "panel-events": _lang === "pl" ? "📅 Eventy" : "📅 Events",
    "panel-tiers": _lang === "pl" ? "🥇 Tier Lista" : "🥇 Tier List",
    "panel-develop": _lang === "pl" ? "🔧 Rozwój" : "🔧 Develop",
    "panel-settings": _lang === "pl" ? "⚙️ Ustawienia" : "⚙️ Settings"
  };
  for (const [id, title] of Object.entries(panelTitles)) {
    const el = $(id);
    if (el) {
      const pTitle = el.querySelector(".panel-title");
      if (pTitle) pTitle.textContent = title;
    }
  }

  $$("th").forEach(th => {
    const text = th.textContent.trim();
    const key = Object.keys(thMap.pl).find(k => thMap.pl[k] === text);
    if (key && thMap[_lang][key]) {
      th.textContent = thMap[_lang][key];
    }
  });

  $$("option").forEach(opt => {
    const text = opt.textContent.trim();
    const key = Object.keys(optionMap.pl).find(k => optionMap.pl[k] === text);
    if (key && optionMap[_lang][key]) {
      opt.textContent = optionMap[_lang][key];
    }
  });

  $$(".stat-chip").forEach(chip => {
    const textNode = Array.from(chip.childNodes).find(n => n.nodeType === Node.TEXT_NODE);
    if (textNode) {
      const text = textNode.textContent.trim();
      for (const [k, v] of Object.entries(chipMap.pl)) {
        if (text.includes(k)) {
          textNode.textContent = chipMap[_lang][k];
          break;
        }
      }
    }
  });

  $$("#pvp-stats-card div").forEach(div => {
    const text = div.textContent.trim();
    if (pvpLabelMap.pl[text]) {
      div.textContent = pvpLabelMap[_lang][text];
    }
  });
  
  const pvpLocalTitle = document.querySelector("#pvp-local-teams-card .card-title");
  if (pvpLocalTitle) pvpLocalTitle.textContent = _lang === "pl" ? "Sugerowane składy PvP (kalkulacja lokalna)" : "Suggested PvP Teams (local calculation)";

  const pvpStatsTitle = document.querySelector("#pvp-stats-card .card-title");
  if (pvpStatsTitle) pvpStatsTitle.textContent = _lang === "pl" ? "Twoje statystyki pojedynków PvP" : "Your PvP Battle Statistics";

  const pvpAlert = document.querySelector("#panel-pvp .alert-info");
  if (pvpAlert) pvpAlert.textContent = _lang === "pl" 
    ? "Ranking uwzględnia CP przy limicie ligi, bulk (def×sta), tier listę meta. Posortowane od najlepszego."
    : "Ranking takes into account CP at the league limit, bulk (def×sta), and meta tier list. Sorted from best to worst.";
    
  const raidAlert = document.querySelector("#panel-raid .alert-info");
  if (raidAlert) raidAlert.textContent = _lang === "pl"
    ? "Najlepsi atakujący do raidów PvE z Twojego plecaka (kalkulacja DPS×TDO)."
    : "Best PvE raid attackers from your box (DPS×TDO calculation).";

  // Box Analytics localized elements
  const boxAnalyticsEl = $("lbl-box-analytics");
  if (boxAnalyticsEl) boxAnalyticsEl.textContent = _lang === "pl" ? "📊 Statystyki Boxa" : "📊 Box Analytics";
  
  const ivDistEl = $("lbl-iv-dist");
  if (ivDistEl) ivDistEl.textContent = _lang === "pl" ? "Rozkład IV" : "IV Distribution";
  
  const typeDistEl = $("lbl-type-dist");
  if (typeDistEl) typeDistEl.textContent = _lang === "pl" ? "Rozkład Typów" : "Type Distribution";
  
  const nandoTrackerEl = $("lbl-nando-tracker");
  if (nandoTrackerEl) nandoTrackerEl.textContent = _lang === "pl" ? "Rzadkie okazy (0% IV - Nando):" : "Rare specimens (0% IV - Nando):";

  // Regex bar text localization
  const lblProtect = $("lbl-regex-protect");
  if (lblProtect) lblProtect.textContent = _lang === "pl" ? "Chroń:" : "Protect:";

  const lblExclude = $("lbl-regex-exclude");
  if (lblExclude) lblExclude.textContent = _lang === "pl" ? "Dodaj filtry wykluczające (&!):" : "Add negative filters (&!):";

  const copyRegexBtn = $("btn-copy-regex");
  if (copyRegexBtn) copyRegexBtn.textContent = _lang === "pl" ? "📋 Kopiuj regex" : "📋 Copy regex";

  // Develop card headings
  const devEvolveTitle = $("lbl-dev-evolve-title");
  if (devEvolveTitle) devEvolveTitle.textContent = devCards[_lang].evolveTitle;
  const devEvolveDesc = $("lbl-dev-evolve-desc");
  if (devEvolveDesc) devEvolveDesc.innerHTML = _lang === "pl"
    ? "Pokemony z IV ≥ 80%, których <strong>końcowa forma jest meta (tier S lub A)</strong>. Ewolucja nie zmienia IV — warto ewoluować zanim będziesz power-upował."
    : "Pokémon with IV ≥ 80% whose <strong>final evolution is meta (tier S or A)</strong>. Evolution does not change IVs – evolve before power-up.";

  const devPowerupTitle = $("lbl-dev-powerup-title");
  if (devPowerupTitle) devPowerupTitle.textContent = devCards[_lang].powerupTitle;
  const devPowerupDesc = $("lbl-dev-powerup-desc");
  if (devPowerupDesc) devPowerupDesc.innerHTML = _lang === "pl"
    ? "Meta pokemon (tier S/A) z IV ≥ 80% poniżej <strong>poziomu 40</strong>. Inwestycja w stardust opłaca się tylko dla meta okazów. Wybierz docelowy poziom, by sprawdzić koszt i CP."
    : "Meta Pokémon (tier S/A) with IV ≥ 80% below <strong>level 40</strong>. Investing in stardust is only worth it for meta specimens. Choose a target level to estimate cost and CP.";

  const devPurifyTitle = $("lbl-dev-purify-title");
  if (devPurifyTitle) devPurifyTitle.textContent = devCards[_lang].purifyTitle;
  const devPurifyDesc = $("lbl-dev-purify-desc");
  if (devPurifyDesc) devPurifyDesc.innerHTML = _lang === "pl"
    ? "Shadow pokemony, których IV <strong>po oczyszczeniu (+2 do każdego, max 15)</strong> osiągnie ≥ 80%. Shadow bonus (+20% ataku) vs. lepsze IV — zapytaj AI co bardziej się opłaca."
    : "Shadow Pokémon whose IV <strong>after purification (+2 to each, max 15)</strong> will reach ≥ 80%. Shadow bonus (+20% attack) vs. better IVs – ask AI what is best.";

  const devTmTitle = $("lbl-dev-tm-title");
  if (devTmTitle) devTmTitle.textContent = devCards[_lang].tmTitle;
  const devTmDesc = $("lbl-dev-tm-desc");
  if (devTmDesc) devTmDesc.innerHTML = _lang === "pl"
    ? "Meta pokemon (tier S/A) na <strong>poziomie ≥ 35</strong> — warte sprawdzenia czy mają optymalne ataki. Elite Fast/Charged TM pozwala nauczyć legacy lub ekskluzywnych ruchów."
    : "Meta Pokémon (tier S/A) at <strong>level ≥ 35</strong> – worth checking if they have optimal moves. Elite Fast/Charged TMs teach legacy or exclusive moves.";

  $("poke-search").placeholder = _lang === "pl" ? "Szukaj nazwy…" : "Search name…";
  $("events-search").placeholder = _lang === "pl" ? "Szukaj eventu lub pokemona..." : "Search event or Pokémon...";

  if (S.pokemons && S.pokemons.length > 0) {
    renderPokemons();
    renderRaid();
    renderPvP();
    renderLocalTeams(_pvpLocalTeams[_pvpLeague]);
    renderBestByRole(_pvpBestByRole[_pvpLeague]);
    renderDevelop();
    renderEvents();
    if (chartIvInstance || chartTypesInstance) {
      updateAnalytics(true);
    }
  }
}

$("lang-pl").addEventListener("click", () => {
  if (_lang !== "pl") {
    _lang = "pl";
    localStorage.setItem("pogo_lang", "pl");
    applyLanguage();
  }
});

$("lang-en").addEventListener("click", () => {
  if (_lang !== "en") {
    _lang = "en";
    localStorage.setItem("pogo_lang", "en");
    applyLanguage();
  }
});

applyLanguage();

// ── Auto-restore on page load ─────────────────────────────────────────────────
(async function checkRestoredState() {
  try {
    const status = await api("/api/status");
    if (status.loaded) {
      await onUploadSuccess(status.stats, status.player, status.pvp_stats);
    }
  } catch (_) {}
})();

// ── Custom Tooltips ───────────────────────────────────────────────────────────
(function initCustomTooltips() {
  const tooltipEl = document.createElement("div");
  tooltipEl.id = "custom-tooltip";
  tooltipEl.className = "custom-tooltip";
  document.body.appendChild(tooltipEl);

  document.addEventListener("mouseover", (e) => {
    const target = e.target.closest("[data-tooltip]");
    if (!target) return;
    
    const text = target.getAttribute("data-tooltip");
    if (!text) return;
    
    tooltipEl.innerHTML = text;
    tooltipEl.classList.add("visible");
    
    const rect = target.getBoundingClientRect();
    const tooltipRect = tooltipEl.getBoundingClientRect();
    
    // Position tooltip above the target by default, or below if not enough space
    let left = rect.left + (rect.width - tooltipRect.width) / 2;
    let top = rect.top - tooltipRect.height - 8 + window.scrollY;
    
    if (top < window.scrollY) {
      top = rect.bottom + 8 + window.scrollY;
    }
    
    if (left < 8) left = 8;
    if (left + tooltipRect.width > window.innerWidth - 8) {
      left = window.innerWidth - tooltipRect.width - 8;
    }
    
    tooltipEl.style.left = `${left}px`;
    tooltipEl.style.top = `${top}px`;
  });

  document.addEventListener("mouseout", (e) => {
    const target = e.target.closest("[data-tooltip]");
    if (target) {
      tooltipEl.classList.remove("visible");
    }
  });
})();

function makeTableSortable(table) {
  if (!table) return;
  const headers = table.querySelectorAll("thead th");
  headers.forEach((th, index) => {
    const label = th.textContent.trim();
    if (label === "AI" || label === "Tagi" || label === "Meta" || label === "Rok" || label === "#" || label === "") return;
    
    th.style.cursor = "pointer";
    th.classList.add("sortable-header");
    
    let asc = true;
    th.addEventListener("click", () => {
      const tbody = table.querySelector("tbody");
      if (!tbody) return;
      const rows = Array.from(tbody.querySelectorAll("tr"));
      if (rows.length === 0) return;
      
      headers.forEach(h => {
        if (h !== th) {
          h.classList.remove("sort-asc", "sort-desc");
        }
      });
      
      rows.sort((a, b) => {
        const cellA = a.cells[index];
        const cellB = b.cells[index];
        
        let valA = cellA ? cellA.textContent.trim() : "";
        let valB = cellB ? cellB.textContent.trim() : "";
        
        const parseValue = (val) => {
          if (val === "" || val === "—") return -Infinity;
          
          let cleaned = val.replace(/%/g, '').replace(/,/g, '').replace(/\s/g, '').trim();
          if (cleaned.includes('/')) {
            const parts = cleaned.split('/').map(Number);
            if (parts.every(x => !isNaN(x))) {
              return parts.reduce((x, y) => x + y, 0);
            }
          }
          const num = parseFloat(cleaned);
          return isNaN(num) ? val.toLowerCase() : num;
        };
        
        const pA = parseValue(valA);
        const pB = parseValue(valB);
        
        if (typeof pA === 'number' && typeof pB === 'number') {
          return asc ? pA - pB : pB - pA;
        } else {
          return asc ? String(pA).localeCompare(String(pB)) : String(pB).localeCompare(String(pA));
        }
      });
      
      if (asc) {
        th.classList.add("sort-asc");
        th.classList.remove("sort-desc");
      } else {
        th.classList.add("sort-desc");
        th.classList.remove("sort-asc");
      }
      
      asc = !asc;
      tbody.append(...rows);
    });
  });
}

(function initTableSorting() {
  makeTableSortable($("poke-table"));
  makeTableSortable($("raid-table"));
  makeTableSortable($("pvp-table"));
})();

let chartIvInstance = null;
let chartTypesInstance = null;

function toggleDevCard(contentId) {
  const content = $(contentId);
  const icon = $(contentId.replace("-content", "-toggle-icon"));
  const preview = $(contentId.replace("-content", "-preview"));
  if (content.style.display === "none") {
    content.style.display = "block";
    icon.textContent = "▲";
    if (preview) preview.style.display = "none";
  } else {
    content.style.display = "none";
    icon.textContent = "▼";
    if (preview) preview.style.display = "flex";
  }
}

function toggleAnalytics() {
  const content = $("analytics-content");
  const icon = $("analytics-toggle-icon");
  if (content.style.display === "none") {
    content.style.display = "block";
    icon.textContent = "▲";
    updateAnalytics();
  } else {
    content.style.display = "none";
    icon.textContent = "▼";
  }
}

function updateAnalytics() {
  if (!$("analytics-content") || $("analytics-content").style.display === "none") return;
  if (!S.pokemons || !S.pokemons.length) return;

  let trash = 0, good = 0, great = 0, excellent = 0, hundo = 0;
  S.pokemons.forEach(p => {
    if (p.hundo || p.iv_pct === 100) hundo++;
    else if (p.iv_pct >= 90) excellent++;
    else if (p.iv_pct >= 80) great++;
    else if (p.iv_pct >= 50) good++;
    else trash++;
  });

  const ivLabels = _lang === "pl" 
    ? ["Kosz (<50%)", "Średni (50-79%)", "Dobry (80-89%)", "Świetny (90-99%)", "Hundo (100%)"]
    : ["Trash (<50%)", "Average (50-79%)", "Good (80-89%)", "Excellent (90-99%)", "Hundo (100%)"];

  if (chartIvInstance) chartIvInstance.destroy();
  const ctxIv = $("chart-iv").getContext("2d");
  chartIvInstance = new Chart(ctxIv, {
    type: "bar",
    data: {
      labels: ivLabels,
      datasets: [{
        label: _lang === "pl" ? "Liczba" : "Count",
        data: [trash, good, great, excellent, hundo],
        backgroundColor: [
          "rgba(239, 68, 68, 0.6)",
          "rgba(249, 115, 22, 0.6)",
          "rgba(234, 179, 8, 0.6)",
          "rgba(34, 197, 94, 0.6)",
          "rgba(163, 230, 53, 0.8)"
        ],
        borderColor: [
          "#ef4444", "#f97316", "#eab308", "#22c55e", "#a3e635"
        ],
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#9ca3af", font: { size: 10 } } },
        y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#9ca3af", font: { size: 10 } } }
      }
    }
  });

  const typesMap = {};
  S.pokemons.forEach(p => {
    const pTypes = p.types || ["normal"];
    pTypes.forEach(t => {
      typesMap[t] = (typesMap[t] || 0) + 1;
    });
  });

  const sortedTypes = Object.entries(typesMap)
    .sort((a,b) => b[1] - a[1])
    .slice(0, 10);

  const typeLabels = sortedTypes.map(x => x[0].toUpperCase());
  const typeValues = sortedTypes.map(x => x[1]);

  if (chartTypesInstance) chartTypesInstance.destroy();
  const ctxTypes = $("chart-types").getContext("2d");
  chartTypesInstance = new Chart(ctxTypes, {
    type: "doughnut",
    data: {
      labels: typeLabels,
      datasets: [{
        data: typeValues,
        backgroundColor: [
          "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
          "#ec4899", "#f43f5e", "#14b8a6", "#6366f1", "#84cc16"
        ],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "right",
          labels: { color: "#d1d5db", font: { size: 9 } }
        }
      }
    }
  });

  const nandos = S.pokemons.filter(p => p.iv_a === 0 && p.iv_d === 0 && p.iv_s === 0);
  $("nando-list-label").textContent = nandos.length;
  const container = $("nando-names-container");
  container.innerHTML = nandos.map(p => 
    `<span class="badge badge-shadow" style="background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3); color:#f87171;" data-tooltip="${p.name} CP${p.cp}">Nando ${p.name} (CP ${p.cp})</span>`
  ).join("") || `<span style="color:var(--muted)">Brak okazów 0% IV</span>`;
}

async function recalcPowerup(select, idx) {
  const targetLvl = parseFloat(select.value);
  const container = $(`pow-calc-${idx}`);
  if (!targetLvl) {
    container.innerHTML = `<span style="color:var(--muted);font-size:10px">—</span>`;
    return;
  }
  
  const p = S.pokemons[idx];
  container.innerHTML = `<div style="text-align:center;"><div class="spinner" style="width:12px;height:12px;border-width:2px;display:inline-block;"></div></div>`;
  
  try {
    const res = await api("/api/powerup-calculation", {
      method: "POST",
      body: JSON.stringify({
        pid: p.pid,
        current_lvl: p.lvl,
        target_lvl: targetLvl,
        iv_a: p.iv_a,
        iv_d: p.iv_d,
        iv_s: p.iv_s,
        shadow: p.shadow,
        lucky: p.lucky,
        purified: p.purified
      })
    });
    
    let xlText = res.xl_candy > 0 ? ` · 💊${res.xl_candy}` : "";
    container.innerHTML = `
      <div style="font-size:10px; line-height:1.3; color:var(--muted);">
        <strong style="color:var(--accent);">CP ${res.target_cp}</strong><br>
        ✨${res.stardust.toLocaleString("pl-PL")} · 🍬${res.candy}${xlText}
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<span style="color:var(--red); font-size:10px;">Błąd</span>`;
  }
}

// Init event listeners for dynamic Regex PoGO and trash filtering
(function initRegexBarEvents() {
  // Bind listeners to all inputs inside regex-bar to dynamically update query and filter results if "trash" is active
  document.addEventListener("input", (e) => {
    if (e.target.closest(".regex-bar input")) {
      updatePogoQuery();
      if (S.filter === "trash") {
        renderPokemons();
      }
    }
  });
  document.addEventListener("change", (e) => {
    if (e.target.closest(".regex-bar input")) {
      updatePogoQuery();
      if (S.filter === "trash") {
        renderPokemons();
      }
    }
  });

  // Trash filter button click listener
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("#btn-filter-trash");
    if (btn) {
      $("poke-filter").value = "trash";
      S.filter = "trash";
      // Switch tab to "pokemons"
      const tabBtn = document.querySelector('.tab[data-tab="pokemons"]');
      if (tabBtn) {
        tabBtn.click();
      }
      renderPokemons();
      // Scroll to the main table toolbar so the user sees the list
      $("poke-search").scrollIntoView({ behavior: "smooth" });
    }
  });
})();
