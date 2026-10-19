import { chapters } from "./story.js";

const maplibregl = window.maplibregl;
const ASSET = "24";
const CREDIT = "© OpenStreetMap · Esri · OpenFreeMap";
const LIBERTY = "https://tiles.openfreemap.org/styles/liberty";
const GLYPHS = "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";
const FONT_REG = ["Noto Sans Regular"];
const FONT_BOLD = ["Noto Sans Bold"];
const TOUR_KEY = "wch-tour-done";

/* Bright greens + cream casing so rings stay clear on the red change layer. */
const ZONE_GREENS = {
  central: "#007a33",
  intermediate: "#1a9f4a",
  distant: "#3dba5c",
};
const RING_CASING = "#fff8e7";
const EDGE = "#3a342e";
const LGA_LINE = "#6e655c";
const STAR_YELLOW = "#ffd600";
const PLACE_INK = "#1e1a16";
const PLACE_HALO = "#fafafa";

const CHANGE_LEGEND = [
  ["#2166ac", "≤ −25"],
  ["#92c5de", "−25 to −5"],
  ["#ece8de", "−5 to 5"],
  ["#fee8c8", "5 to 25"],
  ["#fdbb84", "25 to 50"],
  ["#fc8d59", "50 to 100"],
  ["#d7301f", "100 to 200"],
  ["#7f0000", "> 200"],
];

function makeStarImageData(size = 64) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  const cx = size / 2;
  const cy = size / 2;
  const starPath = (outer, inner) => {
    ctx.beginPath();
    for (let i = 0; i < 10; i += 1) {
      const r = i % 2 === 0 ? outer : inner;
      const a = -Math.PI / 2 + (i * Math.PI) / 5;
      const x = cx + Math.cos(a) * r;
      const y = cy + Math.sin(a) * r;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
  };
  // One star only: thin dark edge then yellow body.
  starPath(size * 0.40, size * 0.16);
  ctx.fillStyle = "#111111";
  ctx.fill();
  starPath(size * 0.365, size * 0.145);
  ctx.fillStyle = STAR_YELLOW;
  ctx.fill();
  return ctx.getImageData(0, 0, size, size);
}

function ensureCentreStar() {
  if (map.hasImage("centre-star")) map.removeImage("centre-star");
  map.addImage("centre-star", makeStarImageData(96), { pixelRatio: 2 });
}

const bust = (url) => `${url}${url.includes("?") ? "&" : "?"}v=${ASSET}`;
const fmtPct = (x) => `${(100 * x).toFixed(1)}%`;
const fmtPhi = (x) => Number(x).toFixed(2);
const fmtPeople = (n) =>
  n >= 1e6 ? `${(n / 1e6).toFixed(2)} M` : n >= 1e3 ? `${(n / 1e3).toFixed(0)} k` : String(Math.round(n));

const RASTER = {
  gray: {
    tiles: [
      bust(
        "https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
      ),
    ],
    // No Esri reference labels — they duplicate our LGA names (e.g. Agege).
    maxzoom: 16,
  },
  dark: {
    tiles: [
      bust(
        "https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
      ),
    ],
    maxzoom: 16,
  },
  osm: {
    tiles: [
      "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
      "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
      "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
    ],
    maxzoom: 19,
    attribution: "© OpenStreetMap contributors",
  },
  streets: {
    tiles: [
      bust(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}"
      ),
    ],
    maxzoom: 19,
  },
  imagery: {
    tiles: [
      bust(
        "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
      ),
    ],
    labels: bust(
      "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
    ),
    maxzoom: 19,
  },
};

const TOUR_STEPS = [
  {
    title: "Results-plate stack",
    body: "People change (GHS-POP 2020−1990), zone rings, LGA lines, study outline and the yellow founding-centre star — the same symbology as the print plates.",
  },
  {
    title: "Contents and bookmarks",
    body: "Hide the panel with ☰. Bookmarks and Locate jump cities. Dark gray is the default base; Gray (plates) and OpenStreetMap are also available.",
  },
  {
    title: "Story and share",
    body: "Story mode scrolls the argument. Link copies this city and basemap. Skip the tour anytime — it will not nag.",
  },
];

const els = {
  menu: document.getElementById("menu-toggle"),
  panelClose: document.getElementById("panel-close"),
  fab: document.getElementById("layers-fab"),
  city: document.getElementById("city-select"),
  blurb: document.getElementById("city-blurb"),
  scores: document.getElementById("score-grid"),
  search: document.getElementById("place-search"),
  searchOut: document.getElementById("search-results"),
  basemap: document.getElementById("basemap-select"),
  basemapMobile: document.getElementById("basemap-select-mobile"),
  bookmarks: document.getElementById("bookmark-list"),
  lgaList: document.getElementById("lga-list"),
  legend: document.getElementById("legend"),
  caption: document.getElementById("map-caption"),
  storyBtn: document.getElementById("story-btn"),
  scrolly: document.getElementById("scrolly"),
  chapters: document.getElementById("chapters"),
  locate: document.getElementById("locate-btn"),
  share: document.getElementById("share-btn"),
  themeToggle: document.getElementById("theme-toggle"),
  tourBtn: document.getElementById("tour-btn"),
  tour: document.getElementById("tour"),
  tourTitle: document.getElementById("tour-title"),
  tourBody: document.getElementById("tour-body"),
  tourKicker: document.getElementById("tour-kicker"),
  tourNext: document.getElementById("tour-next"),
  tourSkip: document.getElementById("tour-skip"),
  tourScrim: document.getElementById("tour-scrim"),
  layers: {
    change: document.getElementById("lyr-change"),
    zones: document.getElementById("lyr-zones"),
    rings: document.getElementById("lyr-rings"),
    lgas: document.getElementById("lyr-lgas"),
    places: document.getElementById("lyr-places"),
    centres: document.getElementById("lyr-centres"),
    outline: document.getElementById("lyr-outline"),
  },
};

const params = new URLSearchParams(location.search);
let city = ["lagos", "kano", "ibadan", "kaduna", "onitsha"].includes(params.get("city"))
  ? params.get("city")
  : "lagos";
let basemap = ["gray", "osm", "dark", "streets", "color", "imagery"].includes(params.get("bm"))
  ? params.get("bm")
  : "dark";
let storyMode = params.get("story") === "1";
let meta = null;
let searchIndex = [];
let popup = null;
let activeChapter = -1;
let dataCache = null;

els.city.value = city;
els.basemap.value = basemap;
els.basemapMobile.value = basemap;
document.body.classList.add("panel-open");
if (params.get("theme") === "dark") {
  document.documentElement.classList.add("theme-dark");
  els.themeToggle.textContent = "Light";
}

function rasterStyle(key) {
  const spec = RASTER[key] || RASTER.gray;
  const sources = {
    basemap: {
      type: "raster",
      tiles: spec.tiles,
      tileSize: 256,
      maxzoom: spec.maxzoom,
      attribution: spec.attribution || CREDIT,
    },
  };
  const layers = [{ id: "basemap", type: "raster", source: "basemap" }];
  if (spec.labels) {
    sources.labels = {
      type: "raster",
      tiles: [spec.labels],
      tileSize: 256,
      maxzoom: spec.maxzoom,
      attribution: spec.attribution || CREDIT,
    };
    layers.push({ id: "basemap-labels", type: "raster", source: "labels" });
  }
  return {
    version: 8,
    sources,
    layers,
    glyphs: GLYPHS,
  };
}

const map = new maplibregl.Map({
  container: "map",
  style: basemap === "color" ? LIBERTY : rasterStyle(basemap),
  center: [3.45, 6.52],
  zoom: 9.2,
  pitch: basemap === "color" ? 45 : 0,
  bearing: 0,
  attributionControl: true,
  transformRequest: (url, resourceType) => {
    if (
      resourceType === "Tile" &&
      /arcgisonline\.com|server\.arcgisonline\.com/.test(url) &&
      !/[?&]v=/.test(url)
    ) {
      return { url: bust(url) };
    }
    return { url };
  },
});
map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-left");

function resizeMap() {
  requestAnimationFrame(() => map.resize());
}

function setPanel(open) {
  document.body.classList.toggle("panel-open", open);
  els.menu.title = open ? "Hide contents" : "Show contents";
  resizeMap();
}

els.menu.addEventListener("click", () => setPanel(!document.body.classList.contains("panel-open")));
els.panelClose.addEventListener("click", () => setPanel(false));
els.fab.addEventListener("click", () => setPanel(true));

function writeUrl() {
  const q = new URLSearchParams();
  if (city !== "lagos") q.set("city", city);
  if (basemap !== "dark") q.set("bm", basemap);
  if (storyMode) q.set("story", "1");
  if (document.documentElement.classList.contains("theme-dark")) q.set("theme", "dark");
  const qs = q.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}

function cityFilter(field = "city") {
  return ["==", ["get", field], city];
}

function applyFilters() {
  if (!map.getLayer("outline")) return;
  if (map.getLayer("lgas-line")) {
    map.setFilter("lgas-line", ["all", cityFilter(), ["==", ["get", "kind"], "shared"]]);
  }
  if (map.getLayer("lgas-hit")) map.setFilter("lgas-hit", cityFilter());
  if (map.getLayer("places")) map.setFilter("places", cityFilter());
  if (map.getLayer("zones-fill")) map.setFilter("zones-fill", cityFilter());
  if (map.getLayer("zones-line")) map.setFilter("zones-line", cityFilter());
  const ringFilters = {
    "rings-casing": ["central"],
    rings: ["central"],
    "rings-dash-casing": ["intermediate"],
    "rings-dash": ["intermediate"],
    "rings-dot-casing": ["distant"],
    "rings-dot": ["distant"],
  };
  Object.entries(ringFilters).forEach(([id, zones]) => {
    if (!map.getLayer(id)) return;
    map.setFilter(id, ["all", ["==", ["get", "slug"], city], ["==", ["get", "zone"], zones[0]]]);
  });
  if (map.getLayer("ring-labels")) map.setFilter("ring-labels", ["==", ["get", "slug"], city]);
  if (map.getLayer("centres")) map.setFilter("centres", ["==", ["get", "slug"], city]);
  if (map.getLayer("centre-label")) map.setFilter("centre-label", ["==", ["get", "slug"], city]);
  if (map.getLayer("outline")) map.setFilter("outline", ["==", ["get", "id"], city]);
  if (map.getLayer("outline-hit")) map.setFilter("outline-hit", ["==", ["get", "id"], city]);
  if (map.getLayer("city-underlay")) map.setFilter("city-underlay", ["==", ["get", "id"], city]);
}

function setChangeOverlay(slug) {
  const spec = meta.change?.[slug];
  if (!spec) return;
  if (map.getLayer("change")) map.removeLayer("change");
  if (map.getSource("change")) map.removeSource("change");
  map.addSource("change", {
    type: "image",
    url: `./data/change/${slug}.png?v=${ASSET}`,
    coordinates: spec.coordinates,
  });
  const before = map.getLayer("lgas-line")
    ? "lgas-line"
    : map.getLayer("rings")
      ? "rings"
      : map.getLayer("outline")
        ? "outline"
        : undefined;
  map.addLayer(
    {
      id: "change",
      type: "raster",
      source: "change",
      paint: { "raster-opacity": 0.92, "raster-fade-duration": 0 },
    },
    before
  );
  map.setLayoutProperty(
    "change",
    "visibility",
    els.layers.change.checked ? "visible" : "none"
  );
}

function setLayerVisibility() {
  const mapLayers = {
    change: ["change"],
    zones: ["zones-fill", "zones-line"],
    rings: [
      "rings-casing",
      "rings-dash-casing",
      "rings-dot-casing",
      "rings",
      "rings-dash",
      "rings-dot",
      "ring-labels",
    ],
    lgas: ["lgas-line", "lgas-hit"],
    places: ["places"],
    centres: ["centres", "centre-label"],
    outline: ["outline", "outline-hit", "city-underlay"],
  };
  Object.entries(mapLayers).forEach(([key, ids]) => {
    const on = els.layers[key]?.checked;
    ids.forEach((id) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    });
  });
}

function renderScores() {
  const c = meta.cities[city];
  const short = meta.centre_short?.[city] || c.centre;
  els.blurb.textContent = `${c.name} · founding centre: ${short}. People ${fmtPeople(c.people_1990)} → ${fmtPeople(c.people_2020)}.`;
  els.scores.innerHTML = `
    <div class="score-card"><span>Central share</span><strong>${fmtPct(c.central_share_1990)} → ${fmtPct(c.central_share_2020)}</strong></div>
    <div class="score-card"><span>φ (expected)</span><strong>${fmtPhi(c.phi)} (${fmtPhi(c.phi_fit)})</strong></div>
    <div class="score-card"><span>People in 1990</span><strong>${fmtPeople(c.people_1990)}</strong></div>
    <div class="score-card"><span>People in 2020</span><strong>${fmtPeople(c.people_2020)}</strong></div>
  `;
  els.caption.textContent = `${c.name} · people gained/lost per 100 m · φ ${fmtPhi(c.phi)} (fit ${fmtPhi(c.phi_fit)})`;
}

function renderBookmarks() {
  els.bookmarks.innerHTML = "";
  meta.bookmarks.forEach((b) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = b.name;
    if (b.id === city) btn.classList.add("is-active");
    btn.addEventListener("click", () => {
      if (b.id === "nigeria") {
        map.easeTo({ center: b.center, zoom: b.zoom, pitch: 0, bearing: 0, duration: 1200 });
        return;
      }
      setCity(b.id, true);
    });
    els.bookmarks.appendChild(btn);
  });
}

function renderLgaList() {
  if (!els.lgaList || !dataCache) return;
  const feats = dataCache.lgas.features
    .filter((f) => f.properties.city === city)
    .sort((a, b) => a.properties.lga_name.localeCompare(b.properties.lga_name));
  els.lgaList.innerHTML = "";
  feats.forEach((f) => {
    const p = f.properties;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "lga-item";
    btn.innerHTML = `<strong>${p.lga_name}</strong><span>${p.km2} km² · ${p.dist_km} km out</span>`;
    btn.addEventListener("click", () => {
      const g = f.geometry;
      let lon;
      let lat;
      if (g.type === "Polygon") {
        const ring = g.coordinates[0];
        lon = ring.reduce((s, c) => s + c[0], 0) / ring.length;
        lat = ring.reduce((s, c) => s + c[1], 0) / ring.length;
      } else {
        const ring = g.coordinates[0][0];
        lon = ring.reduce((s, c) => s + c[0], 0) / ring.length;
        lat = ring.reduce((s, c) => s + c[1], 0) / ring.length;
      }
      map.easeTo({ center: [lon, lat], zoom: Math.max(map.getZoom(), 11.2), duration: 900 });
      showPopup([lon, lat], lgaPopupHtml(p), map.project([lon, lat]));
    });
    els.lgaList.appendChild(btn);
  });
}

function popupShell(kicker, title, body) {
  return `<div class="pop"><p class="pop-kicker">${kicker}</p><strong>${title}</strong>${body}</div>`;
}

function densifyRingCoords(coords, targetStepDeg = 0.00035) {
  if (!Array.isArray(coords) || coords.length < 2) return coords;
  const out = [coords[0]];
  for (let i = 1; i < coords.length; i += 1) {
    const [x0, y0] = out[out.length - 1];
    const [x1, y1] = coords[i];
    const dist = Math.hypot(x1 - x0, y1 - y0);
    const steps = Math.max(1, Math.ceil(dist / targetStepDeg));
    for (let s = 1; s <= steps; s += 1) {
      const t = s / steps;
      out.push([x0 + (x1 - x0) * t, y0 + (y1 - y0) * t]);
    }
  }
  return out;
}

function densifyRings(fc) {
  return {
    type: "FeatureCollection",
    features: (fc?.features || []).map((f) => {
      if (f.geometry?.type !== "LineString") return f;
      return {
        ...f,
        geometry: {
          type: "LineString",
          coordinates: densifyRingCoords(f.geometry.coordinates),
        },
      };
    }),
  };
}

function lgaPopupHtml(p) {
  const c = meta.cities[p.city] || {};
  const cityName = c.name || p.city;
  const centre = meta.centre_short?.[p.city] || c.centre || "the founding centre";
  const dist = p.dist_km != null ? Number(p.dist_km).toFixed(1) : "—";
  const area = p.km2 != null ? Number(p.km2).toFixed(1) : "—";
  return popupShell(
    "Local government area",
    p.lga_name,
    `<p class="pop-lead"><b>${p.lga_name}</b> is an LGA inside the <b>${cityName}</b> study area — the unit this paper uses for the outline (not a ward).</p>
    <dl class="pop-dl">
      <dt>City</dt><dd>${cityName}</dd>
      <dt>LGA</dt><dd>${p.lga_name}</dd>
      <dt>Founding centre</dt><dd>${centre}</dd>
      <dt>Area</dt><dd>${area} km² of ground in this LGA inside the study outline</dd>
      <dt>Distance</dt><dd>${dist} km from ${centre} to typical ground in this LGA</dd>
    </dl>
    <p class="pop-note">The coloured squares show how many more (or fewer) people each 100 m cell held in 2020 than in 1990.</p>`
  );
}

function zonePopupHtml(p, lga) {
  const c = meta.cities[p.city] || {};
  const cityName = c.name || p.city;
  const centre = meta.centre_short?.[p.city] || c.centre || "the founding centre";
  const zone = String(p.zone || "").replace(/-/g, " ");
  const title = p.label || `${zone} zone`;
  const share = p.share_2020 != null ? fmtPct(+p.share_2020) : "—";
  const share0 = p.share_1990 != null ? fmtPct(+p.share_1990) : "—";
  const km = p.km != null ? Number(p.km).toFixed(1) : null;
  const lgaName = lga?.lga_name;
  const blurb =
    zone === "central"
      ? `Closest band to ${centre} (remoteness under 3). The solid green ring is its outer edge${km ? ` at about ${km} km` : ""}.`
      : zone === "intermediate"
        ? `Middle band (remoteness 3–5). The dashed green ring is its outer edge${km ? ` at about ${km} km` : ""}.`
        : zone === "distant"
          ? `Outer urban band (remoteness 5–9.3). The dotted green ring is its outer edge${km ? ` at about ${km} km` : ""}.`
          : `Beyond the distant ring, still inside the ${cityName} LGA outline.`;
  const here = lgaName
    ? `<p class="pop-lead">You clicked in <b>${lgaName}</b> LGA, inside this ${zone} band of <b>${cityName}</b>.</p>`
    : "";
  return popupShell(
    "Remoteness zone",
    title,
    `${here}<p class="pop-lead">${blurb}</p>
    <dl class="pop-dl">
      <dt>City</dt><dd>${cityName}</dd>
      ${lgaName ? `<dt>LGA</dt><dd>${lgaName}</dd>` : ""}
      <dt>Zone</dt><dd>${zone}</dd>
      <dt>Founding centre</dt><dd>${centre}</dd>
      <dt>People in 1990</dt><dd>${fmtPeople(+p.people_1990 || 0)}</dd>
      <dt>People in 2020</dt><dd>${fmtPeople(+p.people_2020 || 0)}</dd>
      <dt>Share of city</dt><dd>${share0} → ${share}</dd>
      <dt>Change</dt><dd>${p.change != null ? fmtPeople(+p.change) : "—"} people</dd>
    </dl>
    <p class="pop-note">Zone people counts are for the whole ${zone} band in ${cityName}, not only ${lgaName || "this LGA"}.</p>`
  );
}

function centrePopupHtml(p) {
  const c = meta.cities[p.slug] || {};
  const cityName = c.name || p.slug;
  return popupShell(
    "Founding centre",
    p.short || p.name,
    `<p class="pop-lead">Historic origin for <b>${cityName}</b>. Every ring and remoteness zone is measured from this yellow star.</p>
    <dl class="pop-dl">
      <dt>Place</dt><dd>${p.name}</dd>
      <dt>City</dt><dd>${cityName}</dd>
      <dt>Central share</dt><dd>${fmtPct(c.central_share_1990)} → ${fmtPct(c.central_share_2020)}</dd>
      <dt>φ (spread)</dt><dd>${fmtPhi(c.phi)} (national fit ${fmtPhi(c.phi_fit)})</dd>
    </dl>
    <p class="pop-note">φ &gt; 1 means the city stretched outward faster than a uniform scale-up of the 1990 map.</p>`
  );
}

function cityPopupHtml(slug, c) {
  const centre = meta.centre_short?.[slug] || c.centre;
  return popupShell(
    "Study area",
    `${c.name} outline`,
    `<p class="pop-lead">The outline is the set of LGAs that define <b>${c.name}</b> in this paper. People change, zone rings and φ are all computed inside it.</p>
    <dl class="pop-dl">
      <dt>City</dt><dd>${c.name}</dd>
      <dt>Founding centre</dt><dd>${centre}</dd>
      <dt>People in 1990</dt><dd>${fmtPeople(c.people_1990)}</dd>
      <dt>People in 2020</dt><dd>${fmtPeople(c.people_2020)}</dd>
      <dt>Central share</dt><dd>${fmtPct(c.central_share_1990)} → ${fmtPct(c.central_share_2020)}</dd>
      <dt>φ (spread)</dt><dd>${fmtPhi(c.phi)} (fit ${fmtPhi(c.phi_fit)})</dd>
    </dl>
    <p class="pop-note">Internal grey lines are LGA boundaries; green rings are remoteness edges from ${centre}.</p>`
  );
}

function ringPopupHtml(p, lga) {
  const c = meta.cities[p.slug] || {};
  const cityName = c.name || p.slug;
  const centre = meta.centre_short?.[p.slug] || c.centre || "the founding centre";
  const zone = String(p.zone || "").replace(/-/g, " ");
  const km = p.km != null ? Number(p.km).toFixed(1) : "—";
  const lgaName = lga?.lga_name;
  return popupShell(
    "Zone ring",
    p.label || `${zone} · ${km} km`,
    `<p class="pop-lead">Outer edge of the <b>${zone}</b> remoteness zone for <b>${cityName}</b>, drawn from ${centre}${lgaName ? ` — crossing <b>${lgaName}</b> LGA here` : ""}.</p>
    <dl class="pop-dl">
      <dt>City</dt><dd>${cityName}</dd>
      ${lgaName ? `<dt>LGA</dt><dd>${lgaName}</dd>` : ""}
      <dt>Zone</dt><dd>${zone}</dd>
      <dt>Radius</dt><dd>${km} km from ${centre}</dd>
      <dt>Founding centre</dt><dd>${centre}</dd>
    </dl>
    <p class="pop-note">Click the coloured ground inside the ring for people counts in that zone.</p>`
  );
}

function renderLegend() {
  const changeRows = CHANGE_LEGEND.map(
    ([c, t]) =>
      `<div class="legend-row"><span class="swatch" style="background:${c}"></span>${t}</div>`
  ).join("");
  els.legend.innerHTML = `
    <div class="legend-title">People gained per square</div>
    ${changeRows}
    <div class="legend-title">Edges</div>
    <div class="legend-row"><span class="swatch" style="background:${ZONE_GREENS.central}"></span>Central zone edge</div>
    <div class="legend-row"><span class="swatch" style="background:${ZONE_GREENS.intermediate}"></span>Intermediate zone edge</div>
    <div class="legend-row"><span class="swatch" style="background:${ZONE_GREENS.distant}"></span>Distant zone edge</div>
    <div class="legend-row"><span class="swatch" style="background:transparent;border:2px solid ${EDGE}"></span>Study area</div>
    <div class="legend-row"><span class="swatch" style="background:transparent;border:2px solid ${LGA_LINE}"></span>Local government area</div>
    <div class="legend-row"><span class="swatch star-swatch" style="background:${STAR_YELLOW}"></span>Founding centre</div>
  `;
}

function flyCity(slug, animated = true) {
  const v = meta.cities[slug].view;
  const pitch = basemap === "color" ? Math.max(v.pitch, 40) : storyMode ? v.pitch : 0;
  const opts = {
    center: v.center,
    zoom: v.zoom,
    pitch,
    bearing: basemap === "color" || storyMode ? v.bearing : 0,
    duration: animated ? 1200 : 0,
  };
  if (animated) map.easeTo(opts);
  else map.jumpTo(opts);
}

function setCity(slug, fly = true) {
  city = slug;
  els.city.value = slug;
  applyFilters();
  setChangeOverlay(slug);
  setLayerVisibility();
  renderScores();
  renderBookmarks();
  renderLgaList();
  writeUrl();
  if (fly) flyCity(slug);
}

function addThematic(data) {
  const ensure = (id, source) => {
    if (map.getSource(id)) map.getSource(id).setData(source);
    else map.addSource(id, { type: "geojson", data: source });
  };
  ensure("zones", data.zones);
  ensure("rings", data.rings);
  ensure("ring-label-pts", data.ringLabels || { type: "FeatureCollection", features: [] });
  ensure("lgas", data.lgas);
  ensure("lga-boundaries", data.lgaBoundaries || { type: "FeatureCollection", features: [] });
  ensure("lga-label-pts", data.lgaLabelPts || { type: "FeatureCollection", features: [] });
  ensure("centres", data.centres);
  ensure("cities", data.cities);

  const add = (layer) => {
    if (!map.getLayer(layer.id)) {
      map.addLayer(layer);
      return;
    }
    // Fresh paint/layout on reload so cache-bust style tweaks actually apply.
    if (layer.paint) {
      Object.entries(layer.paint).forEach(([k, v]) => {
        try {
          map.setPaintProperty(layer.id, k, v);
        } catch (_) {
          /* ignore unsupported keys on existing layer */
        }
      });
    }
    if (layer.layout) {
      Object.entries(layer.layout).forEach(([k, v]) => {
        if (k === "visibility") return;
        try {
          map.setLayoutProperty(layer.id, k, v);
        } catch (_) {
          /* ignore */
        }
      });
    }
  };

  // Drop legacy fat outline halo if an older style left it in the map.
  if (map.getLayer("outline-halo")) map.removeLayer("outline-halo");

  // Soft underlay seals edge gaps without a bold cream slab on dark basemaps.
  add({
    id: "city-underlay",
    type: "fill",
    source: "cities",
    paint: {
      "fill-color": "#ece8de",
      "fill-opacity": 0.42,
      "fill-antialias": false,
    },
  });
  add({
    id: "zones-fill",
    type: "fill",
    source: "zones",
    paint: {
      "fill-color": [
        "match",
        ["get", "zone"],
        "central",
        ZONE_GREENS.central,
        "intermediate",
        ZONE_GREENS.intermediate,
        "distant",
        ZONE_GREENS.distant,
        "#c7e9c0",
      ],
      "fill-opacity": 0.01,
    },
  });
  add({
    id: "zones-line",
    type: "line",
    source: "zones",
    paint: { "line-color": ZONE_GREENS.central, "line-width": 0, "line-opacity": 0 },
  });
  add({
    id: "lgas-hit",
    type: "fill",
    source: "lgas",
    paint: { "fill-color": "#000", "fill-opacity": 0.01 },
  });
  add({
    id: "lgas-line",
    type: "line",
    source: "lga-boundaries",
    layout: {
      "line-join": "round",
      "line-cap": "round",
    },
    paint: {
      "line-color": LGA_LINE,
      "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.35, 11, 0.55, 13, 0.7],
      "line-opacity": 0.42,
    },
  });
  // Cream casing under a thicker green core — green reads first, casing only for contrast.
  const ringLineLayout = { "line-join": "round", "line-cap": "round" };
  add({
    id: "rings-casing",
    type: "line",
    source: "rings",
    layout: ringLineLayout,
    paint: {
      "line-color": RING_CASING,
      "line-width": ["interpolate", ["linear"], ["zoom"], 8, 8, 12, 11],
      "line-opacity": 0.95,
    },
  });
  add({
    id: "rings-dash-casing",
    type: "line",
    source: "rings",
    layout: ringLineLayout,
    paint: {
      "line-color": RING_CASING,
      "line-width": ["interpolate", ["linear"], ["zoom"], 8, 7.5, 12, 10],
      "line-opacity": 0.95,
    },
  });
  add({
    id: "rings-dot-casing",
    type: "line",
    source: "rings",
    layout: ringLineLayout,
    paint: {
      "line-color": RING_CASING,
      "line-width": ["interpolate", ["linear"], ["zoom"], 8, 7, 12, 9.5],
      "line-opacity": 0.95,
    },
  });
  add({
    id: "rings",
    type: "line",
    source: "rings",
    layout: ringLineLayout,
    paint: {
      "line-color": ZONE_GREENS.central,
      "line-width": ["interpolate", ["linear"], ["zoom"], 8, 4.5, 12, 6],
      "line-opacity": 1,
    },
  });
  add({
    id: "rings-dash",
    type: "line",
    source: "rings",
    layout: ringLineLayout,
    paint: {
      "line-color": ZONE_GREENS.intermediate,
      "line-width": ["interpolate", ["linear"], ["zoom"], 8, 4, 12, 5.5],
      "line-dasharray": [2.2, 1.1],
      "line-opacity": 1,
    },
  });
  add({
    id: "rings-dot",
    type: "line",
    source: "rings",
    layout: ringLineLayout,
    paint: {
      "line-color": ZONE_GREENS.distant,
      "line-width": ["interpolate", ["linear"], ["zoom"], 8, 3.6, 12, 5],
      "line-dasharray": [1.0, 1.1],
      "line-opacity": 1,
    },
  });
  // Curved labels follow densified arcs (line placement, not flat point labels).
  add({
    id: "ring-labels",
    type: "symbol",
    source: "rings",
    layout: {
      "symbol-placement": "line",
      "symbol-spacing": 1600,
      "text-field": ["get", "label"],
      "text-size": ["interpolate", ["linear"], ["zoom"], 8, 13, 11, 15.5, 13, 17],
      "text-font": FONT_BOLD,
      "text-max-angle": 28,
      "text-padding": 2,
      "text-letter-spacing": 0.04,
      "text-keep-upright": true,
      "text-rotation-alignment": "map",
      "text-pitch-alignment": "viewport",
      "text-allow-overlap": true,
      "text-ignore-placement": true,
      "text-optional": false,
    },
    paint: {
      "text-color": [
        "match",
        ["get", "zone"],
        "central",
        ZONE_GREENS.central,
        "intermediate",
        ZONE_GREENS.intermediate,
        ZONE_GREENS.distant,
      ],
      "text-halo-color": RING_CASING,
      "text-halo-width": 3.6,
      "text-halo-blur": 0.1,
    },
    minzoom: 7,
  });
  add({
    id: "outline-hit",
    type: "fill",
    source: "cities",
    paint: { "fill-color": "#000", "fill-opacity": 0 },
  });
  // Soft study outline — no heavy black halo.
  add({
    id: "outline",
    type: "line",
    source: "cities",
    layout: { "line-join": "round", "line-cap": "round" },
    paint: {
      "line-color": EDGE,
      "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.55, 11, 0.8, 13, 1.0],
      "line-opacity": 0.32,
    },
  });
  add({
    id: "places",
    type: "symbol",
    source: "lga-label-pts",
    layout: {
      "text-field": ["get", "lga_name"],
      "text-size": ["interpolate", ["linear"], ["zoom"], 8.5, 10, 11, 12, 13, 13],
      "text-font": FONT_REG,
      "text-optional": false,
      "text-padding": 4,
      "text-max-width": 8,
      "symbol-sort-key": ["to-number", ["get", "km2"]],
      "text-allow-overlap": false,
      "text-ignore-placement": false,
    },
    paint: {
      "text-color": PLACE_INK,
      "text-halo-color": PLACE_HALO,
      "text-halo-width": 1.5,
      "text-halo-blur": 0.2,
    },
    minzoom: 8.8,
  });

  add({
    id: "centres",
    type: "symbol",
    source: "centres",
    layout: {
      "text-field": "★",
      "text-size": ["interpolate", ["linear"], ["zoom"], 8, 22, 12, 30],
      "text-font": FONT_BOLD,
      "text-allow-overlap": true,
      "text-ignore-placement": true,
      "text-anchor": "center",
      "text-optional": false,
    },
    paint: {
      "text-color": STAR_YELLOW,
      "text-halo-color": "#1a120c",
      "text-halo-width": 0.55,
      "text-halo-blur": 0,
    },
  });
  add({
    id: "centre-label",
    type: "symbol",
    source: "centres",
    layout: {
      "text-field": ["coalesce", ["get", "short"], ["get", "name"]],
      "text-size": 12,
      "text-font": FONT_BOLD,
      "text-offset": [0, 1.85],
      "text-anchor": "top",
      "text-optional": false,
      "text-allow-overlap": true,
      "text-ignore-placement": true,
    },
    paint: {
      "text-color": PLACE_INK,
      "text-halo-color": PLACE_HALO,
      "text-halo-width": 1.5,
    },
  });

  applyFilters();
  setChangeOverlay(city);
  setLayerVisibility();
}

async function loadData() {
  if (dataCache) return dataCache;
  const opts = { cache: "no-store" };
  const [zones, rings, ringLabels, lgas, lgaBoundaries, lgaLabelPts, centres, cities, m, search] =
    await Promise.all([
      fetch(`./data/zones.geojson?v=${ASSET}`, opts).then((r) => r.json()),
      fetch(`./data/zone_rings.geojson?v=${ASSET}`, opts).then((r) => r.json()),
      fetch(`./data/zone_labels.geojson?v=${ASSET}`, opts).then((r) => r.json()),
      fetch(`./data/lgas.geojson?v=${ASSET}`, opts).then((r) => r.json()),
      fetch(`./data/lga_boundaries.geojson?v=${ASSET}`, opts).then((r) => r.json()),
      fetch(`./data/lga_labels.geojson?v=${ASSET}`, opts).then((r) => r.json()),
      fetch(`./data/centres.geojson?v=${ASSET}`, opts).then((r) => r.json()),
      fetch(`./data/cities.geojson?v=${ASSET}`, opts).then((r) => r.json()),
      fetch(`./data/meta.json?v=${ASSET}`, opts).then((r) => r.json()),
      fetch(`./data/search.json?v=${ASSET}`, opts).then((r) => r.json()),
    ]);
  meta = m;
  searchIndex = search;
  dataCache = {
    zones,
    rings: densifyRings(rings),
    ringLabels,
    lgas,
    lgaBoundaries,
    lgaLabelPts,
    centres,
    cities,
  };
  return dataCache;
}

async function switchBasemap(key) {
  basemap = key;
  els.basemap.value = key;
  els.basemapMobile.value = key;
  writeUrl();
  const cam = {
    center: map.getCenter(),
    zoom: map.getZoom(),
    pitch: key === "color" ? 45 : 0,
    bearing: key === "color" ? map.getBearing() : 0,
  };
  const data = await loadData();
  await new Promise((resolve) => {
    map.once("style.load", resolve);
    map.setStyle(key === "color" ? LIBERTY : rasterStyle(key), { diff: false });
  });
  map.jumpTo(cam);
  addThematic(data);
  resizeMap();
}

els.basemap.addEventListener("change", () => switchBasemap(els.basemap.value));
els.basemapMobile.addEventListener("change", () => switchBasemap(els.basemapMobile.value));
els.city.addEventListener("change", () => setCity(els.city.value, true));
Object.values(els.layers).forEach((el) => el?.addEventListener("change", setLayerVisibility));

els.search.addEventListener("input", () => {
  const q = els.search.value.trim().toLowerCase();
  if (q.length < 2) {
    els.searchOut.hidden = true;
    els.searchOut.innerHTML = "";
    return;
  }
  const prefer = searchIndex.filter(
    (s) => s.name.toLowerCase().includes(q) && (s.city === city || s.kind === "centre")
  );
  const loose =
    prefer.length > 0
      ? prefer.slice(0, 12)
      : searchIndex.filter((s) => s.name.toLowerCase().includes(q)).slice(0, 12);
  els.searchOut.hidden = loose.length === 0;
  els.searchOut.innerHTML = loose
    .map(
      (h) =>
        `<button type="button" class="search-hit">${h.name} <span style="color:var(--muted)">· ${h.city}</span></button>`
    )
    .join("");
  [...els.searchOut.querySelectorAll(".search-hit")].forEach((btn, i) => {
    btn.addEventListener("click", () => {
      const h = loose[i];
      if (h.city && h.city !== city) setCity(h.city, false);
      map.easeTo({ center: [h.lon, h.lat], zoom: Math.max(map.getZoom(), 12), duration: 900 });
      els.searchOut.hidden = true;
    });
  });
});

els.locate.addEventListener("click", () => {
  if (!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const { longitude: lon, latitude: lat } = pos.coords;
      let best = null;
      let bestD = Infinity;
      Object.entries(meta.cities).forEach(([slug, c]) => {
        const [clon, clat] = c.view.center;
        const d = (lon - clon) ** 2 + (lat - clat) ** 2;
        if (d < bestD) {
          bestD = d;
          best = slug;
        }
      });
      if (best) setCity(best, true);
      map.easeTo({ center: [lon, lat], zoom: 11, duration: 1000 });
    },
    () => {
      els.locate.textContent = "Denied";
      setTimeout(() => (els.locate.textContent = "Locate"), 1400);
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
});

els.share.addEventListener("click", async () => {
  writeUrl();
  try {
    await navigator.clipboard.writeText(location.href);
    els.share.textContent = "Copied";
  } catch {
    els.share.textContent = "URL set";
  }
  setTimeout(() => (els.share.textContent = "Link"), 1400);
});

els.themeToggle.addEventListener("click", () => {
  const dark = document.documentElement.classList.toggle("theme-dark");
  els.themeToggle.textContent = dark ? "Light" : "Dark";
  writeUrl();
});

function popupAnchorForPoint(point) {
  const { clientWidth: w, clientHeight: h } = map.getCanvas();
  const x = point.x;
  const y = point.y;
  const left = x < w * 0.28;
  const right = x > w * 0.72;
  const top = y < h * 0.32;
  const bottom = y > h * 0.68;
  if (top && left) return "top-left";
  if (top && right) return "top-right";
  if (top) return "top";
  if (bottom && left) return "bottom-left";
  if (bottom && right) return "bottom-right";
  if (bottom) return "bottom";
  if (left) return "left";
  if (right) return "right";
  return "bottom";
}

function keepPopupInView(pop) {
  const el = pop?.getElement?.();
  if (!el) return;
  const mapEl = map.getContainer();
  const pr = el.getBoundingClientRect();
  const mr = mapEl.getBoundingClientRect();
  const pad = 14;
  const leftPad = document.body.classList.contains("panel-open") ? 8 : pad;
  let dx = 0;
  let dy = 0;
  if (pr.left < mr.left + leftPad) dx = mr.left + leftPad - pr.left;
  if (pr.right > mr.right - pad) dx = mr.right - pad - pr.right;
  if (pr.top < mr.top + pad) dy = mr.top + pad - pr.top;
  if (pr.bottom > mr.bottom - pad) dy = mr.bottom - pad - pr.bottom;
  if (dx || dy) map.panBy([dx, dy], { duration: 220 });
}

function showPopup(lngLat, html, point) {
  if (popup) popup.remove();
  const pt = point || map.project(lngLat);
  popup = new maplibregl.Popup({
    maxWidth: "340px",
    anchor: popupAnchorForPoint(pt),
    offset: 16,
    closeButton: true,
    className: "wch-pop",
  })
    .setLngLat(lngLat)
    .setHTML(html)
    .addTo(map);
  requestAnimationFrame(() => {
    requestAnimationFrame(() => keepPopupInView(popup));
  });
}

function popupFromFeature(f, lgaProps) {
  if (!f) return null;
  const id = f.layer?.id || "";
  const p = f.properties || {};
  if (id === "centres" || id === "centre-label") return centrePopupHtml(p);
  if (id.startsWith("rings") && id !== "ring-labels") return ringPopupHtml(p, lgaProps);
  if (id === "zones-fill") return zonePopupHtml(p, lgaProps);
  if (id === "lgas-hit") return lgaPopupHtml(p);
  if (id === "outline" || id === "outline-hit") {
    const c = meta.cities[p.id];
    return c ? cityPopupHtml(p.id, c) : null;
  }
  return null;
}

function bindPopup() {
  const hitLayers = [
    "centres",
    "rings-casing",
    "rings-dash-casing",
    "rings-dot-casing",
    "rings",
    "rings-dash",
    "rings-dot",
    "zones-fill",
    "lgas-hit",
    "outline",
  ];
  const priority = [
    "centres",
    "rings",
    "rings-dash",
    "rings-dot",
    "rings-casing",
    "rings-dash-casing",
    "rings-dot-casing",
    "zones-fill",
    "lgas-hit",
    "outline",
  ];

  hitLayers.forEach((id) => {
    map.on("mouseenter", id, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", id, () => (map.getCanvas().style.cursor = ""));
  });

  // One click path with priority so LGA fills do not steal zone / ring / centre popups.
  map.on("click", (e) => {
    const layers = hitLayers.filter((id) => map.getLayer(id));
    if (!layers.length) return;
    const feats = map.queryRenderedFeatures(e.point, { layers });
    if (!feats.length) return;
    const ranked = [...feats].sort((a, b) => {
      const ia = priority.indexOf(a.layer?.id);
      const ib = priority.indexOf(b.layer?.id);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });
    const lgaFeat = feats.find((f) => f.layer?.id === "lgas-hit");
    const html = popupFromFeature(ranked[0], lgaFeat?.properties);
    if (html) showPopup(e.lngLat, html, e.point);
  });
}

chapters.forEach((ch, i) => {
  const section = document.createElement("section");
  section.className = "chapter";
  section.id = ch.id;
  section.dataset.index = String(i);
  section.innerHTML = `<span class="chapter-index">${String(i + 1).padStart(2, "0")} / ${String(chapters.length).padStart(2, "0")}</span><h2>${ch.title}</h2><p>${ch.body}</p>`;
  els.chapters.appendChild(section);
});

function setStory(on) {
  storyMode = on;
  els.scrolly.hidden = !on;
  els.storyBtn.textContent = on ? "Explore" : "Story";
  if (on) setPanel(false);
  writeUrl();
  resizeMap();
}
els.storyBtn.addEventListener("click", () => setStory(!storyMode));

const chapterObserver = new IntersectionObserver(
  (entries) => {
    if (!storyMode) return;
    const visible = entries
      .filter((e) => e.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
    if (!visible.length) return;
    const idx = Number(visible[0].target.dataset.index);
    if (idx === activeChapter || Number.isNaN(idx)) return;
    activeChapter = idx;
    document.querySelectorAll(".chapter").forEach((el, i) => el.classList.toggle("is-active", i === idx));
    const ch = chapters[idx];
    els.caption.textContent = ch.caption;
    if (ch.highlight && ch.highlight !== "all" && meta.cities[ch.highlight]) setCity(ch.highlight, true);
    else if (ch.highlight === "all") {
      map.easeTo({
        center: ch.view.center,
        zoom: ch.view.zoom,
        pitch: ch.view.pitch,
        bearing: ch.view.bearing,
        duration: 1200,
      });
    }
  },
  { rootMargin: "-35% 0px -45% 0px", threshold: [0.15, 0.4, 0.7] }
);
document.querySelectorAll(".chapter").forEach((el) => chapterObserver.observe(el));

let tourStep = 0;
function closeTour(save) {
  els.tour.hidden = true;
  if (save) {
    try {
      localStorage.setItem(TOUR_KEY, "1");
    } catch {
      /* ignore */
    }
  }
}
function showTourStep() {
  const step = TOUR_STEPS[tourStep];
  els.tourKicker.textContent = `Tour ${tourStep + 1} / ${TOUR_STEPS.length}`;
  els.tourTitle.textContent = step.title;
  els.tourBody.textContent = step.body;
  els.tourNext.textContent = tourStep === TOUR_STEPS.length - 1 ? "Done" : "Next";
  els.tour.hidden = false;
}
function openTour(force = false) {
  if (!force && (params.get("tour") === "0" || localStorage.getItem(TOUR_KEY) === "1")) return;
  tourStep = 0;
  showTourStep();
}
els.tourBtn.addEventListener("click", () => openTour(true));
els.tourSkip.addEventListener("click", () => closeTour(true));
els.tourScrim.addEventListener("click", () => closeTour(true));
els.tourNext.addEventListener("click", () => {
  if (tourStep >= TOUR_STEPS.length - 1) return closeTour(true);
  tourStep += 1;
  showTourStep();
});

map.on("load", async () => {
  const data = await loadData();
  addThematic(data);
  bindPopup();
  renderScores();
  renderBookmarks();
  renderLgaList();
  renderLegend();
  flyCity(city, false);
  setStory(storyMode);
  openTour(false);
  resizeMap();
  window.__wchMap = map;
});

window.addEventListener("resize", resizeMap);
