import { chapters } from "./story.js";

const maplibregl = window.maplibregl;
const ASSET = "9";
const CREDIT = "© OpenStreetMap · Esri · OpenFreeMap";
const LIBERTY = "https://tiles.openfreemap.org/styles/liberty";
const GLYPHS = "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";
const FONT_REG = ["Noto Sans Regular"];
const FONT_BOLD = ["Noto Sans Bold"];
const TOUR_KEY = "wch-tour-done";

/* Plate symbology from qgis/build_plates.py */
const ZONE_GREENS = {
  central: "#005a32",
  intermediate: "#238b45",
  distant: "#74c476",
};
const EDGE = "#0a0a0a";
const LGA_LINE = "#1a120c";
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
  const spikes = 5;
  const outer = size * 0.42;
  const inner = size * 0.17;
  ctx.beginPath();
  for (let i = 0; i < spikes * 2; i += 1) {
    const r = i % 2 === 0 ? outer : inner;
    const a = -Math.PI / 2 + (i * Math.PI) / spikes;
    const x = cx + Math.cos(a) * r;
    const y = cy + Math.sin(a) * r;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fillStyle = STAR_YELLOW;
  ctx.fill();
  ctx.lineJoin = "round";
  ctx.strokeStyle = "#111";
  ctx.lineWidth = size * 0.045;
  ctx.stroke();
  return ctx.getImageData(0, 0, size, size);
}

function ensureCentreStar() {
  if (map.hasImage("centre-star")) map.removeImage("centre-star");
  const img = makeStarImageData(128);
  map.addImage("centre-star", img, { pixelRatio: 2 });
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
    labels: bust(
      "https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
    ),
    maxzoom: 16,
  },
  dark: {
    tiles: [
      bust(
        "https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
      ),
    ],
    labels: bust(
      "https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
    ),
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
    body: "Hide the panel with ☰. Bookmarks and Locate jump cities. Gray (plates) is the default base; OpenStreetMap is also available.",
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
  : "gray";
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
  if (basemap !== "gray") q.set("bm", basemap);
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
  if (map.getLayer("lgas-line")) map.setFilter("lgas-line", cityFilter());
  if (map.getLayer("lgas-hit")) map.setFilter("lgas-hit", cityFilter());
  if (map.getLayer("places")) map.setFilter("places", cityFilter());
  if (map.getLayer("zones-fill")) map.setFilter("zones-fill", cityFilter());
  if (map.getLayer("zones-line")) map.setFilter("zones-line", cityFilter());
  if (map.getLayer("rings")) {
    map.setFilter("rings", ["all", ["==", ["get", "slug"], city], ["==", ["get", "zone"], "central"]]);
  }
  if (map.getLayer("rings-dash")) {
    map.setFilter("rings-dash", ["all", ["==", ["get", "slug"], city], ["==", ["get", "zone"], "intermediate"]]);
  }
  if (map.getLayer("rings-dot")) {
    map.setFilter("rings-dot", ["all", ["==", ["get", "slug"], city], ["==", ["get", "zone"], "distant"]]);
  }
  if (map.getLayer("ring-labels")) map.setFilter("ring-labels", ["==", ["get", "slug"], city]);
  if (map.getLayer("centres")) map.setFilter("centres", ["==", ["get", "slug"], city]);
  if (map.getLayer("centre-label")) map.setFilter("centre-label", ["==", ["get", "slug"], city]);
  if (map.getLayer("outline")) map.setFilter("outline", ["==", ["get", "id"], city]);
  if (map.getLayer("outline-hit")) map.setFilter("outline-hit", ["==", ["get", "id"], city]);
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
    rings: ["rings", "rings-dash", "rings-dot", "ring-labels"],
    lgas: ["lgas-line", "lgas-hit"],
    places: ["places"],
    centres: ["centres", "centre-label"],
    outline: ["outline", "outline-hit"],
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
      if (popup) popup.remove();
      popup = new maplibregl.Popup({ maxWidth: "240px", anchor: "bottom", offset: 14 })
        .setLngLat([lon, lat])
        .setHTML(lgaPopupHtml(p))
        .addTo(map);
    });
    els.lgaList.appendChild(btn);
  });
}

function lgaPopupHtml(p) {
  const cityName = meta.cities[p.city]?.name || p.city;
  return `<strong>${p.lga_name}</strong><br/>Local government area in ${cityName}<br/>Area: ${p.km2} km²<br/>Distance from founding centre: ${p.dist_km} km`;
}

function zonePopupHtml(p) {
  const cityName = meta.cities[p.city]?.name || p.city;
  const share = p.share_2020 != null ? fmtPct(+p.share_2020) : "—";
  const share0 = p.share_1990 != null ? fmtPct(+p.share_1990) : "—";
  const title = p.label || `${String(p.zone).replace(/-/g, " ")} zone`;
  return `<strong>${title}</strong><br/>${cityName}<br/>People in 1990: ${fmtPeople(+p.people_1990 || 0)}<br/>People in 2020: ${fmtPeople(+p.people_2020 || 0)}<br/>Share: ${share0} → ${share}<br/>Change: ${p.change != null ? fmtPeople(+p.change) : "—"}`;
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
  ensure("centres", data.centres);
  ensure("cities", data.cities);

  const add = (layer) => {
    if (!map.getLayer(layer.id)) map.addLayer(layer);
  };

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
    source: "lgas",
    paint: {
      "line-color": LGA_LINE,
      "line-width": ["interpolate", ["linear"], ["zoom"], 8, 1.2, 11, 2.0, 13, 2.6],
      "line-opacity": 1,
    },
  });
  add({
    id: "rings",
    type: "line",
    source: "rings",
    paint: {
      "line-color": ZONE_GREENS.central,
      "line-width": 2.4,
      "line-opacity": 1,
    },
  });
  add({
    id: "rings-dash",
    type: "line",
    source: "rings",
    paint: {
      "line-color": ZONE_GREENS.intermediate,
      "line-width": 2.0,
      "line-dasharray": [2.2, 1.4],
    },
  });
  add({
    id: "rings-dot",
    type: "line",
    source: "rings",
    paint: {
      "line-color": ZONE_GREENS.distant,
      "line-width": 1.8,
      "line-dasharray": [0.9, 1.5],
    },
  });
  add({
    id: "ring-labels",
    type: "symbol",
    source: "ring-label-pts",
    layout: {
      "text-field": ["get", "label"],
      "text-size": ["interpolate", ["linear"], ["zoom"], 8, 11, 10, 12.5, 12, 14],
      "text-font": FONT_BOLD,
      "text-anchor": "left",
      "text-offset": [0.25, 0],
      "text-padding": 1,
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
      "text-halo-color": "#f7f4ee",
      "text-halo-width": 2.2,
      "text-halo-blur": 0.15,
    },
    minzoom: 7.8,
  });
  add({
    id: "outline-hit",
    type: "fill",
    source: "cities",
    paint: { "fill-color": "#000", "fill-opacity": 0 },
  });
  add({
    id: "outline",
    type: "line",
    source: "cities",
    paint: {
      "line-color": EDGE,
      "line-width": ["interpolate", ["linear"], ["zoom"], 8, 2.2, 11, 3.0, 13, 3.6],
      "line-opacity": 1,
    },
  });
  add({
    id: "places",
    type: "symbol",
    source: "lgas",
    layout: {
      "text-field": ["get", "lga_name"],
      "text-size": ["interpolate", ["linear"], ["zoom"], 8.5, 10, 11, 12, 13, 13],
      "text-font": FONT_REG,
      "text-optional": false,
      "text-padding": 2,
      "text-max-width": 8,
      "symbol-sort-key": ["to-number", ["get", "km2"]],
      "text-allow-overlap": false,
    },
    paint: {
      "text-color": PLACE_INK,
      "text-halo-color": PLACE_HALO,
      "text-halo-width": 1.5,
      "text-halo-blur": 0.2,
    },
    minzoom: 8.8,
  });

  ensureCentreStar();
  add({
    id: "centres",
    type: "symbol",
    source: "centres",
    layout: {
      "icon-image": "centre-star",
      "icon-size": 1.2,
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
      "icon-anchor": "center",
      "text-field": "★",
      "text-size": 26,
      "text-font": FONT_BOLD,
      "text-allow-overlap": true,
      "text-ignore-placement": true,
      "text-optional": true,
      "text-anchor": "center",
    },
    paint: {
      "text-color": STAR_YELLOW,
      "text-halo-color": "#111111",
      "text-halo-width": 1.4,
      "icon-opacity": 1,
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
  const [zones, rings, ringLabels, lgas, centres, cities, m, search] = await Promise.all([
    fetch(`./data/zones.geojson?v=${ASSET}`, opts).then((r) => r.json()),
    fetch(`./data/zone_rings.geojson?v=${ASSET}`, opts).then((r) => r.json()),
    fetch(`./data/zone_labels.geojson?v=${ASSET}`, opts).then((r) => r.json()),
    fetch(`./data/lgas.geojson?v=${ASSET}`, opts).then((r) => r.json()),
    fetch(`./data/centres.geojson?v=${ASSET}`, opts).then((r) => r.json()),
    fetch(`./data/cities.geojson?v=${ASSET}`, opts).then((r) => r.json()),
    fetch(`./data/meta.json?v=${ASSET}`, opts).then((r) => r.json()),
    fetch(`./data/search.json?v=${ASSET}`, opts).then((r) => r.json()),
  ]);
  meta = m;
  searchIndex = search;
  dataCache = { zones, rings, ringLabels, lgas, centres, cities };
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

function showPopup(lngLat, html) {
  if (popup) popup.remove();
  popup = new maplibregl.Popup({
    maxWidth: "260px",
    anchor: "bottom",
    offset: 14,
    closeButton: true,
  })
    .setLngLat(lngLat)
    .setHTML(html)
    .addTo(map);
}

function bindPopup() {
  const hover = (id) => {
    map.on("mouseenter", id, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", id, () => (map.getCanvas().style.cursor = ""));
  };

  map.on("click", "lgas-hit", (e) => {
    const f = e.features?.[0];
    if (!f) return;
    showPopup(e.lngLat, lgaPopupHtml(f.properties));
  });
  hover("lgas-hit");

  map.on("click", "zones-fill", (e) => {
    const f = e.features?.[0];
    if (!f) return;
    showPopup(e.lngLat, zonePopupHtml(f.properties));
  });
  hover("zones-fill");

  map.on("click", "centres", (e) => {
    const f = e.features?.[0];
    if (!f) return;
    const p = f.properties;
    const cityName = meta.cities[p.slug]?.name || p.slug;
    showPopup(
      e.lngLat,
      `<strong>${p.short || p.name}</strong><br/>Founding centre of ${cityName}<br/>${p.name}`
    );
  });
  hover("centres");

  map.on("click", "outline", (e) => {
    const f = e.features?.[0];
    if (!f) return;
    const p = f.properties;
    const c = meta.cities[p.id];
    if (!c) return;
    showPopup(
      e.lngLat,
      `<strong>${c.name} study area</strong><br/>People in 1990: ${fmtPeople(c.people_1990)}<br/>People in 2020: ${fmtPeople(c.people_2020)}<br/>Central share ${fmtPct(c.central_share_1990)} → ${fmtPct(c.central_share_2020)}<br/>φ ${fmtPhi(c.phi)} (fit ${fmtPhi(c.phi_fit)})`
    );
  });
  hover("outline");
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
