import { chapters } from "./story.js";

const maplibregl = window.maplibregl;
const ASSET = "2";
const FILL = "#5ec4ba";
const FILL_DIM = "#3a5560";
const OUTLINE = "#d7e4ea";
const CREDIT = "Tiles © Esri · OpenStreetMap";
const TOUR_KEY = "wch-tour-done";

const bust = (url) => `${url}${url.includes("?") ? "&" : "?"}v=${ASSET}`;

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
    attribution: CREDIT,
  },
  streets: {
    tiles: [
      bust(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}"
      ),
    ],
    maxzoom: 19,
    attribution: CREDIT,
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
    attribution: CREDIT,
  },
};

const TOUR_STEPS = [
  {
    title: "Scroll the story",
    body: "Each card flies the map to a city. The numbers are the paper headline: central share and the spread factor φ.",
  },
  {
    title: "Basemap is in the header",
    body: "Gray, Streets or Imagery — also on phones. No API key. Tiles are pulled fresh, not from a stale cache.",
  },
  {
    title: "Share a chapter",
    body: "Tap Link to copy a URL that opens on that beat. Skip this tour anytime; it will not nag on reload.",
  },
];

const chaptersEl = document.getElementById("chapters");
const captionEl = document.getElementById("map-caption");
const basemapSelect = document.getElementById("basemap-select");
const shareBtn = document.getElementById("share-btn");
const tourBtn = document.getElementById("tour-btn");
const tourEl = document.getElementById("tour");
const tourTitle = document.getElementById("tour-title");
const tourBody = document.getElementById("tour-body");
const tourKicker = document.getElementById("tour-kicker");
const tourNext = document.getElementById("tour-next");
const tourSkip = document.getElementById("tour-skip");
const tourScrim = document.getElementById("tour-scrim");

chapters.forEach((ch, i) => {
  const section = document.createElement("section");
  section.className = "chapter";
  section.id = ch.id;
  section.dataset.index = String(i);
  section.innerHTML = `
    <span class="chapter-index">${String(i + 1).padStart(2, "0")} / ${String(chapters.length).padStart(2, "0")}</span>
    <h2>${ch.title}</h2>
    <p>${ch.body}</p>
  `;
  chaptersEl.appendChild(section);
});

const params = new URLSearchParams(location.search);
let basemap = ["gray", "streets", "imagery"].includes(params.get("bm"))
  ? params.get("bm")
  : "gray";
basemapSelect.value = basemap;

const startId = params.get("chapter") || params.get("c");
const startIndex = Math.max(
  0,
  chapters.findIndex((c) => c.id === startId)
);

function rasterStyle(key) {
  const spec = RASTER[key] || RASTER.gray;
  const sources = {
    basemap: {
      type: "raster",
      tiles: spec.tiles,
      tileSize: 256,
      maxzoom: spec.maxzoom,
      attribution: spec.attribution,
    },
  };
  const layers = [{ id: "basemap", type: "raster", source: "basemap" }];
  if (spec.labels) {
    sources.labels = {
      type: "raster",
      tiles: [spec.labels],
      tileSize: 256,
      maxzoom: spec.maxzoom,
      attribution: spec.attribution,
    };
    layers.push({ id: "basemap-labels", type: "raster", source: "labels" });
  }
  return { version: 8, sources, layers };
}

const map = new maplibregl.Map({
  container: "map",
  style: rasterStyle(basemap),
  center: chapters[startIndex === -1 ? 0 : startIndex].view.center,
  zoom: chapters[startIndex === -1 ? 0 : startIndex].view.zoom,
  pitch: chapters[startIndex === -1 ? 0 : startIndex].view.pitch,
  bearing: chapters[startIndex === -1 ? 0 : startIndex].view.bearing,
  interactive: true,
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

let activeIndex = -1;
let citiesData = null;
let centresData = null;

function setHighlight(key) {
  if (!map.getLayer("cities-fill")) return;
  if (!key) {
    map.setPaintProperty("cities-fill", "fill-opacity", 0.15);
    map.setPaintProperty("cities-fill", "fill-color", FILL_DIM);
    map.setPaintProperty("cities-line", "line-opacity", 0.35);
    return;
  }
  if (key === "all") {
    map.setPaintProperty("cities-fill", "fill-color", FILL);
    map.setPaintProperty("cities-fill", "fill-opacity", 0.45);
    map.setPaintProperty("cities-line", "line-opacity", 0.95);
    return;
  }
  map.setPaintProperty("cities-fill", "fill-color", [
    "case",
    ["==", ["get", "id"], key],
    FILL,
    FILL_DIM,
  ]);
  map.setPaintProperty("cities-fill", "fill-opacity", [
    "case",
    ["==", ["get", "id"], key],
    0.55,
    0.12,
  ]);
  map.setPaintProperty("cities-line", "line-opacity", [
    "case",
    ["==", ["get", "id"], key],
    1,
    0.2,
  ]);
}

function writeUrl(index) {
  const ch = chapters[index];
  const q = new URLSearchParams();
  if (ch.id !== "open") q.set("chapter", ch.id);
  if (basemap !== "gray") q.set("bm", basemap);
  const qs = q.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}

function activate(index, { scroll = false, write = true } = {}) {
  if (index === activeIndex || index < 0 || index >= chapters.length) return;
  activeIndex = index;
  const ch = chapters[index];

  document.querySelectorAll(".chapter").forEach((el, i) => {
    el.classList.toggle("is-active", i === index);
  });

  captionEl.textContent = ch.caption;
  setHighlight(ch.highlight);

  map.easeTo({
    ...ch.view,
    duration: 1200,
    essential: true,
  });

  if (write) writeUrl(index);
  if (scroll) {
    document.getElementById(ch.id)?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }
}

function addThematic() {
  if (!citiesData || !centresData) return;
  if (map.getSource("cities")) {
    map.getSource("cities").setData(citiesData);
    map.getSource("centres").setData(centresData);
    setHighlight(chapters[Math.max(0, activeIndex)].highlight);
    return;
  }

  map.addSource("cities", { type: "geojson", data: citiesData });
  map.addSource("centres", { type: "geojson", data: centresData });

  map.addLayer({
    id: "cities-fill",
    type: "fill",
    source: "cities",
    paint: { "fill-color": FILL_DIM, "fill-opacity": 0.15 },
  });
  map.addLayer({
    id: "cities-line",
    type: "line",
    source: "cities",
    paint: { "line-color": OUTLINE, "line-width": 1.6, "line-opacity": 0.35 },
  });
  map.addLayer({
    id: "centres",
    type: "circle",
    source: "centres",
    paint: {
      "circle-radius": 5,
      "circle-color": FILL,
      "circle-stroke-width": 2,
      "circle-stroke-color": "#071018",
    },
  });

  if (activeIndex >= 0) setHighlight(chapters[activeIndex].highlight);
}

async function switchBasemap(key) {
  basemap = key;
  const center = map.getCenter();
  const zoom = map.getZoom();
  const pitch = map.getPitch();
  const bearing = map.getBearing();
  map.setStyle(rasterStyle(key));
  map.once("style.load", () => {
    map.jumpTo({ center, zoom, pitch, bearing });
    addThematic();
    if (activeIndex >= 0) writeUrl(activeIndex);
  });
}

basemapSelect.addEventListener("change", () => switchBasemap(basemapSelect.value));

shareBtn.addEventListener("click", async () => {
  writeUrl(Math.max(0, activeIndex));
  try {
    await navigator.clipboard.writeText(location.href);
    shareBtn.textContent = "Copied";
    setTimeout(() => {
      shareBtn.textContent = "Link";
    }, 1400);
  } catch {
    shareBtn.textContent = "URL set";
    setTimeout(() => {
      shareBtn.textContent = "Link";
    }, 1400);
  }
});

let tourStep = 0;
function closeTour(save) {
  tourEl.hidden = true;
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
  tourKicker.textContent = `Tour ${tourStep + 1} / ${TOUR_STEPS.length}`;
  tourTitle.textContent = step.title;
  tourBody.textContent = step.body;
  tourNext.textContent = tourStep === TOUR_STEPS.length - 1 ? "Done" : "Next";
  tourEl.hidden = false;
}
function openTour(force = false) {
  const suppressed = params.get("tour") === "0";
  let done = false;
  try {
    done = localStorage.getItem(TOUR_KEY) === "1";
  } catch {
    done = false;
  }
  if (!force && (suppressed || done)) return;
  tourStep = 0;
  showTourStep();
}

tourBtn.addEventListener("click", () => openTour(true));
tourSkip.addEventListener("click", () => closeTour(true));
tourScrim.addEventListener("click", () => closeTour(true));
tourNext.addEventListener("click", () => {
  if (tourStep >= TOUR_STEPS.length - 1) {
    closeTour(true);
    return;
  }
  tourStep += 1;
  showTourStep();
});

map.on("load", async () => {
  const opts = { cache: "no-store" };
  const [cities, centres] = await Promise.all([
    fetch(`./data/cities.geojson?v=${ASSET}`, opts).then((r) => r.json()),
    fetch(`./data/centres.geojson?v=${ASSET}`, opts).then((r) => r.json()),
  ]);
  citiesData = cities;
  centresData = centres;
  addThematic();

  const idx = startIndex === -1 ? 0 : startIndex;
  activate(idx, { scroll: startIndex > 0, write: true });

  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((e) => e.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
      if (!visible.length) return;
      const i = Number(visible[0].target.dataset.index);
      if (!Number.isNaN(i)) activate(i);
    },
    {
      root: null,
      rootMargin: "-35% 0px -45% 0px",
      threshold: [0.15, 0.4, 0.7],
    }
  );
  document.querySelectorAll(".chapter").forEach((el) => observer.observe(el));
  openTour(false);
});
