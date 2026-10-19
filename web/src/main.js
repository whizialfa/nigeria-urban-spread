import { chapters } from "./story.js";

const maplibregl = window.maplibregl;
const ASSET = "5";
const CREDIT = "Tiles © Esri · OpenStreetMap · OpenFreeMap";
const LIBERTY = "https://tiles.openfreemap.org/styles/liberty";
const TOUR_KEY = "wch-tour-done";

const ZONE_COLORS = {
  central: "#005a32",
  intermediate: "#238b45",
  distant: "#74c476",
  "peri-urban": "#c7e9c0",
};

const bust = (url) => `${url}${url.includes("?") ? "&" : "?"}v=${ASSET}`;
const fmtPct = (x) => `${(100 * x).toFixed(1)}%`;
const fmtPhi = (x) => Number(x).toFixed(2);
const fmtPeople = (n) =>
  n >= 1e6 ? `${(n / 1e6).toFixed(2)} M` : n >= 1e3 ? `${(n / 1e3).toFixed(0)} k` : String(Math.round(n));

const RASTER = {
  gray: {
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
    title: "Contents panel",
    body: "Pick a city, read the headline scores, toggle layers and colour. Hide the panel anytime with ☰ — the map resizes.",
  },
  {
    title: "Bookmarks and Locate",
    body: "Bookmarks jump to Nigeria or each city. Locate opens the nearest study city to where you are.",
  },
  {
    title: "Basemap and share",
    body: "Gray, Streets, Buildings 2.5D or Imagery — also on phones. Link copies a URL for this city, colour and basemap. Story mode scrolls the argument.",
  },
];

const els = {
  panel: document.getElementById("layers-panel"),
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
  theme: document.getElementById("theme-select"),
  bookmarks: document.getElementById("bookmark-list"),
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
let basemap = ["gray", "streets", "color", "imagery"].includes(params.get("bm"))
  ? params.get("bm")
  : "gray";
let colour = ["zones", "share", "change"].includes(params.get("colour"))
  ? params.get("colour")
  : "zones";
let storyMode = params.get("story") === "1";
let meta = null;
let searchIndex = [];
let popup = null;
let activeChapter = -1;

els.city.value = city;
els.basemap.value = basemap;
els.basemapMobile.value = basemap;
els.theme.value = colour;
document.body.classList.add("panel-open");
if (params.get("theme") === "light") {
  document.documentElement.classList.remove("theme-dark");
  document.documentElement.classList.add("theme-light");
  els.themeToggle.textContent = "Dark";
}

function rasterStyle(key) {
  const spec = RASTER[key] || RASTER.gray;
  const sources = {
    basemap: {
      type: "raster",
      tiles: spec.tiles,
      tileSize: 256,
      maxzoom: spec.maxzoom,
      attribution: CREDIT,
    },
  };
  const layers = [{ id: "basemap", type: "raster", source: "basemap" }];
  if (spec.labels) {
    sources.labels = {
      type: "raster",
      tiles: [spec.labels],
      tileSize: 256,
      maxzoom: spec.maxzoom,
      attribution: CREDIT,
    };
    layers.push({ id: "basemap-labels", type: "raster", source: "labels" });
  }
  return { version: 8, sources, layers, glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf" };
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
  if (colour !== "zones") q.set("colour", colour);
  if (storyMode) q.set("story", "1");
  if (document.documentElement.classList.contains("theme-light")) q.set("theme", "light");
  const qs = q.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}

function cityFilter(field = "city") {
  return ["==", ["get", field], city];
}

function applyFilters() {
  if (!map.getLayer("zones-fill")) return;
  map.setFilter("zones-fill", cityFilter());
  map.setFilter("zones-outline", cityFilter());
  map.setFilter("rings", ["all", ["==", ["get", "slug"], city], ["==", ["get", "zone"], "central"]]);
  if (map.getLayer("rings-dash")) {
    map.setFilter("rings-dash", ["all", ["==", ["get", "slug"], city], ["==", ["get", "zone"], "intermediate"]]);
  }
  if (map.getLayer("rings-dot")) {
    map.setFilter("rings-dot", ["all", ["==", ["get", "slug"], city], ["==", ["get", "zone"], "distant"]]);
  }
  map.setFilter("lgas-line", cityFilter());
  map.setFilter("lgas-fill", cityFilter());
  map.setFilter("places", cityFilter());
  map.setFilter("centres", ["==", ["get", "slug"], city]);
  map.setFilter("outline", ["==", ["get", "id"], city]);
}

function zoneColorExpr() {
  if (colour === "zones") {
    return [
      "match",
      ["get", "zone"],
      "central",
      ZONE_COLORS.central,
      "intermediate",
      ZONE_COLORS.intermediate,
      "distant",
      ZONE_COLORS.distant,
      "peri-urban",
      ZONE_COLORS["peri-urban"],
      "#888",
    ];
  }
  if (colour === "share") {
    return [
      "interpolate",
      ["linear"],
      ["coalesce", ["get", "share_2020"], 0],
      0.15,
      "#edf8fb",
      0.25,
      "#b2e2e2",
      0.35,
      "#66c2a4",
      0.45,
      "#2ca25f",
      0.55,
      "#006d2c",
    ];
  }
  return [
    "interpolate",
    ["linear"],
    ["coalesce", ["get", "change"], 0],
    0,
    "#f7fcf5",
    200000,
    "#c7e9c0",
    500000,
    "#74c476",
    1000000,
    "#238b45",
    1500000,
    "#005a32",
  ];
}

function paintZones() {
  if (!map.getLayer("zones-fill")) return;
  map.setPaintProperty("zones-fill", "fill-color", zoneColorExpr());
  map.setPaintProperty("zones-fill", "fill-opacity", 0.72);
  renderLegend();
}

function setLayerVisibility() {
  const mapLayers = {
    zones: ["zones-fill", "zones-outline"],
    rings: ["rings", "rings-dash", "rings-dot"],
    lgas: ["lgas-line", "lgas-fill"],
    places: ["places"],
    centres: ["centres"],
    outline: ["outline"],
  };
  Object.entries(mapLayers).forEach(([key, ids]) => {
    const on = els.layers[key].checked;
    ids.forEach((id) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    });
  });
}

function renderScores() {
  const c = meta.cities[city];
  els.blurb.textContent = `${c.name} · founding centre: ${c.centre}. People ${fmtPeople(c.people_1990)} → ${fmtPeople(c.people_2020)}.`;
  els.scores.innerHTML = `
    <div class="score-card"><span>Central share</span><strong>${fmtPct(c.central_share_1990)} → ${fmtPct(c.central_share_2020)}</strong></div>
    <div class="score-card"><span>φ (expected)</span><strong>${fmtPhi(c.phi)} (${fmtPhi(c.phi_fit)})</strong></div>
    <div class="score-card"><span>People 1990</span><strong>${fmtPeople(c.people_1990)}</strong></div>
    <div class="score-card"><span>People 2020</span><strong>${fmtPeople(c.people_2020)}</strong></div>
  `;
  els.caption.textContent = `${c.name} · φ ${fmtPhi(c.phi)} (fit ${fmtPhi(c.phi_fit)}) · central ${fmtPct(c.central_share_2020)}`;
}

function renderBookmarks() {
  els.bookmarks.innerHTML = "";
  meta.bookmarks.forEach((b) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = b.name;
    btn.dataset.id = b.id;
    if (b.id === city) btn.classList.add("is-active");
    btn.addEventListener("click", () => {
      if (b.id === "nigeria") {
        map.easeTo({ center: b.center, zoom: b.zoom, pitch: b.pitch || 0, bearing: b.bearing || 0, duration: 1200 });
        return;
      }
      setCity(b.id, true);
    });
    els.bookmarks.appendChild(btn);
  });
}

function renderLegend() {
  if (colour === "zones") {
    els.legend.innerHTML = ["central", "intermediate", "distant", "peri-urban"]
      .map(
        (z) =>
          `<div class="legend-row"><span class="swatch" style="background:${ZONE_COLORS[z]}"></span>${z}</div>`
      )
      .join("");
    return;
  }
  if (colour === "share") {
    els.legend.innerHTML = [
      ["#edf8fb", "15%"],
      ["#b2e2e2", "25%"],
      ["#66c2a4", "35%"],
      ["#2ca25f", "45%"],
      ["#006d2c", "55%+"],
    ]
      .map(
        ([c, t]) =>
          `<div class="legend-row"><span class="swatch" style="background:${c}"></span>Central share ${t}</div>`
      )
      .join("");
    return;
  }
  els.legend.innerHTML = [
    ["#f7fcf5", "+0"],
    ["#c7e9c0", "+0.2 M"],
    ["#74c476", "+0.5 M"],
    ["#238b45", "+1.0 M"],
    ["#005a32", "+1.5 M"],
  ]
    .map(
      ([c, t]) =>
        `<div class="legend-row"><span class="swatch" style="background:${c}"></span>People change ${t}</div>`
    )
    .join("");
}

function flyCity(slug, animated = true) {
  const v = meta.cities[slug].view;
  const pitch = basemap === "color" ? Math.max(v.pitch, 40) : storyMode ? v.pitch : Math.min(v.pitch, 20);
  const opts = { center: v.center, zoom: v.zoom, pitch, bearing: v.bearing, duration: animated ? 1200 : 0 };
  if (animated) map.easeTo(opts);
  else map.jumpTo(opts);
}

function setCity(slug, fly = true) {
  city = slug;
  els.city.value = slug;
  applyFilters();
  renderScores();
  renderBookmarks();
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
  ensure("lgas", data.lgas);
  ensure("places", data.places);
  ensure("centres", data.centres);
  ensure("cities", data.cities);

  const add = (layer) => {
    if (!map.getLayer(layer.id)) map.addLayer(layer);
  };

  add({
    id: "zones-fill",
    type: "fill",
    source: "zones",
    paint: { "fill-color": ZONE_COLORS.central, "fill-opacity": 0.72 },
  });
  add({
    id: "zones-outline",
    type: "line",
    source: "zones",
    paint: { "line-color": "#d7e4ea", "line-width": 0.6, "line-opacity": 0.55 },
  });
  add({
    id: "lgas-fill",
    type: "fill",
    source: "lgas",
    paint: { "fill-color": "#000", "fill-opacity": 0.01 },
  });
  add({
    id: "lgas-line",
    type: "line",
    source: "lgas",
    paint: { "line-color": "#9aa7a3", "line-width": 0.7, "line-opacity": 0.75 },
  });
  add({
    id: "rings",
    type: "line",
    source: "rings",
    paint: {
      "line-color": [
        "match",
        ["get", "zone"],
        "central",
        ZONE_COLORS.central,
        "intermediate",
        ZONE_COLORS.intermediate,
        "distant",
        ZONE_COLORS.distant,
        "#888",
      ],
      "line-width": ["match", ["get", "zone"], "central", 2.4, "intermediate", 1.6, 1.3],
      "line-opacity": 0.95,
    },
  });
  // Dashed intermediate / dotted distant via separate filter layers
  add({
    id: "rings-dash",
    type: "line",
    source: "rings",
    filter: ["==", ["get", "zone"], "intermediate"],
    paint: {
      "line-color": ZONE_COLORS.intermediate,
      "line-width": 1.6,
      "line-dasharray": [2, 1.2],
    },
  });
  add({
    id: "rings-dot",
    type: "line",
    source: "rings",
    filter: ["==", ["get", "zone"], "distant"],
    paint: {
      "line-color": ZONE_COLORS.distant,
      "line-width": 1.3,
      "line-dasharray": [0.8, 1.4],
    },
  });
  add({
    id: "outline",
    type: "line",
    source: "cities",
    paint: { "line-color": "#e8f4f2", "line-width": 1.8, "line-opacity": 0.95 },
  });
  add({
    id: "places",
    type: "symbol",
    source: "places",
    layout: {
      "text-field": ["get", "name"],
      "text-size": 11,
      "text-font": ["Open Sans Regular", "Arial Unicode MS Regular"],
      "text-optional": true,
      "symbol-sort-key": ["length", ["get", "name"]],
    },
    paint: {
      "text-color": "#e8f4f2",
      "text-halo-color": "#071018",
      "text-halo-width": 1.4,
    },
    minzoom: 9.5,
  });
  add({
    id: "centres",
    type: "circle",
    source: "centres",
    paint: {
      "circle-radius": 6,
      "circle-color": "#5ec4ba",
      "circle-stroke-width": 2,
      "circle-stroke-color": "#071018",
    },
  });

  applyFilters();
  paintZones();
  setLayerVisibility();
}

async function loadData() {
  const opts = { cache: "no-store" };
  const [zones, rings, lgas, places, centres, cities, m, search] = await Promise.all([
    fetch(`./data/zones.geojson?v=${ASSET}`, opts).then((r) => r.json()),
    fetch(`./data/zone_rings.geojson?v=${ASSET}`, opts).then((r) => r.json()),
    fetch(`./data/lgas.geojson?v=${ASSET}`, opts).then((r) => r.json()),
    fetch(`./data/places.geojson?v=${ASSET}`, opts).then((r) => r.json()),
    fetch(`./data/centres.geojson?v=${ASSET}`, opts).then((r) => r.json()),
    fetch(`./data/cities.geojson?v=${ASSET}`, opts).then((r) => r.json()),
    fetch(`./data/meta.json?v=${ASSET}`, opts).then((r) => r.json()),
    fetch(`./data/search.json?v=${ASSET}`, opts).then((r) => r.json()),
  ]);
  meta = m;
  searchIndex = search;
  return { zones, rings, lgas, places, centres, cities };
}

async function switchBasemap(key) {
  basemap = key;
  els.basemap.value = key;
  els.basemapMobile.value = key;
  const cam = {
    center: map.getCenter(),
    zoom: map.getZoom(),
    pitch: key === "color" ? 45 : map.getPitch(),
    bearing: map.getBearing(),
  };
  const data = await loadData();
  map.setStyle(key === "color" ? LIBERTY : rasterStyle(key));
  map.once("style.load", () => {
    map.jumpTo(cam);
    addThematic(data);
    writeUrl();
  });
}

els.basemap.addEventListener("change", () => switchBasemap(els.basemap.value));
els.basemapMobile.addEventListener("change", () => switchBasemap(els.basemapMobile.value));
els.city.addEventListener("change", () => setCity(els.city.value, true));
els.theme.addEventListener("change", () => {
  colour = els.theme.value;
  paintZones();
  writeUrl();
});
Object.values(els.layers).forEach((el) => el.addEventListener("change", setLayerVisibility));

els.search.addEventListener("input", () => {
  const q = els.search.value.trim().toLowerCase();
  if (q.length < 2) {
    els.searchOut.hidden = true;
    els.searchOut.innerHTML = "";
    return;
  }
  const hits = searchIndex
    .filter((s) => s.name.toLowerCase().includes(q) && (!city || s.city === city || s.kind === "centre"))
    .slice(0, 12);
  const loose =
    hits.length > 0
      ? hits
      : searchIndex.filter((s) => s.name.toLowerCase().includes(q)).slice(0, 12);
  els.searchOut.hidden = loose.length === 0;
  els.searchOut.innerHTML = loose
    .map(
      (h, i) =>
        `<button type="button" class="search-hit" data-i="${i}" role="option">${h.name} <span style="color:var(--muted)">· ${h.city}</span></button>`
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
  if (!navigator.geolocation) {
    els.locate.textContent = "No GPS";
    setTimeout(() => (els.locate.textContent = "Locate"), 1200);
    return;
  }
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
  const light = document.documentElement.classList.toggle("theme-light");
  document.documentElement.classList.toggle("theme-dark", !light);
  els.themeToggle.textContent = light ? "Dark" : "Light";
  writeUrl();
});

function bindPopup() {
  map.on("click", "zones-fill", (e) => {
    const f = e.features?.[0];
    if (!f) return;
    const p = f.properties;
    const html = `<strong>${p.zone}</strong><br/>People 1990: ${fmtPeople(+p.people_1990 || 0)}<br/>People 2020: ${fmtPeople(+p.people_2020 || 0)}<br/>Share 2020: ${p.share_2020 != null ? fmtPct(+p.share_2020) : "—"}<br/>Change: ${p.change != null ? fmtPeople(+p.change) : "—"}`;
    if (popup) popup.remove();
    popup = new maplibregl.Popup({ maxWidth: "240px", anchor: "bottom", offset: 12 })
      .setLngLat(e.lngLat)
      .setHTML(html)
      .addTo(map);
  });
  map.on("click", "lgas-fill", (e) => {
    const f = e.features?.[0];
    if (!f) return;
    const p = f.properties;
    if (popup) popup.remove();
    popup = new maplibregl.Popup({ maxWidth: "220px", anchor: "bottom", offset: 10 })
      .setLngLat(e.lngLat)
      .setHTML(`<strong>${p.lga_name}</strong><br/>${meta.cities[p.city]?.name || p.city}`)
      .addTo(map);
  });
  map.on("mouseenter", "zones-fill", () => (map.getCanvas().style.cursor = "pointer"));
  map.on("mouseleave", "zones-fill", () => (map.getCanvas().style.cursor = ""));
}

/* Story mode */
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
  document.body.classList.toggle("story-on", on);
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
    if (ch.highlight && ch.highlight !== "all" && meta.cities[ch.highlight]) {
      setCity(ch.highlight, true);
    } else if (ch.highlight === "all") {
      map.easeTo({ center: ch.view.center, zoom: ch.view.zoom, pitch: ch.view.pitch, bearing: ch.view.bearing, duration: 1200 });
    }
  },
  { rootMargin: "-35% 0px -45% 0px", threshold: [0.15, 0.4, 0.7] }
);
document.querySelectorAll(".chapter").forEach((el) => chapterObserver.observe(el));

/* Tour */
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
  renderLegend();
  flyCity(city, false);
  setStory(storyMode);
  openTour(false);
  resizeMap();
  window.__wchMap = map;
});

window.addEventListener("resize", resizeMap);
