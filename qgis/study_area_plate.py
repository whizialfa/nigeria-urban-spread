"""Study area plate for any place on Earth, in Wisdom's house style. A QGIS Processing script.

Install: Processing Toolbox > Python icon > Add Script to Toolbox... > pick this file.
Run:     Processing Toolbox > Wisdom maps > Study area plate.

Three inputs make the plate; everything else is optional.
  * Area of interest: a polygon layer. One feature is the outline; several (districts, wards, LGAs, catchments)
    are drawn and labelled inside the outline their union makes
  * Raster(s) of interest: any number. Each is cut to the area, put on a metre grid in the local UTM zone and
    classed by natural breaks, one plate per raster. Tick 'bivariate' to show the first two on one 3 x 3 plate.
    Tick 'counts' for rasters of people (or anything counted) per cell, so they read per hectare
  * Country of interest: picked from QGIS's built-in world map for the locator, or found from the area

The A3 landscape layout (title, north arrow, scale, legends, footnote, credit, locator, zoomed inset) is added to
the project and opened in the layout designer for adjusting or printing. PNG and PDF are written if an output
folder is set. The optional base is Esri's light-grey canvas, which needs an internet connection; switch it off
to work offline or on a plain white page.
"""

from __future__ import annotations

import datetime
import json
import math
import os
import shutil
import tempfile
import time
import zipfile
from urllib.parse import quote

import numpy as np
from osgeo import gdal, ogr, osr
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsBlockingNetworkRequest,
    QgsCallout,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFillSymbol,
    QgsGeometry,
    QgsLabelingEngineSettings,
    QgsLabelObstacleSettings,
    QgsLayoutExporter,
    QgsLayoutItem,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemMapOverview,
    QgsLayoutItemPicture,
    QgsLayoutItemScaleBar,
    QgsLayoutItemShape,
    QgsLayoutMeasurement,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsLegendRenderer,
    QgsLegendStyle,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsNetworkAccessManager,
    QgsPalettedRasterRenderer,
    QgsPalLayerSettings,
    QgsPointXY,
    QgsPrintLayout,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterField,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingParameterPoint,
    QgsProcessingParameterString,
    QgsProcessingParameterVectorLayer,
    QgsProject,
    QgsProperty,
    QgsRasterLayer,
    QgsRectangle,
    QgsScaleBarSettings,
    QgsSimpleLineCallout,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsUnitTypes,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtCore import QUrl, QVariant, Qt
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtNetwork import QNetworkRequest, QSslConfiguration

MM = QgsUnitTypes.LayoutMillimeters
PAGE_W, PAGE_H = 420.0, 297.0
FRAME_X, FRAME_Y, FRAME_W, FRAME_H = 8.0, 8.0, 404.0, 281.0
TITLE_W, TITLE_H = 128.0, 32.0
NOTE_W, NOTE_H, NOTE_BOTTOM = 214.0, 40.0, 8.0
LEGEND_W = 74.0
KEY_H = 66.0
KEY_CELL = 9.0
FURNITURE_GAP = 3.0
BOTTOM_CLEAR = 6.0
INSET_W = 96.0
INSET_GAIN = 2.0
EMPTY_PER_HA = 1.0

EDGE = "28,25,22,255"
UNIT_EDGE = "70,52,40,235"
STAR_YELLOW = "255,214,0,255"
LOCATOR_RED = "200,30,30,255"
GREY_BASE = ("type=xyz&url=https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/"
             "MapServer/tile/%7Bz%7D/%7By%7D/%7Bx%7D&zmax=16&zmin=0&crs=EPSG3857")

# Stevens green/blue. Rows: first grid low to high. Columns: second grid low to high.
BIVARIATE = (
    ("232,232,232", "181,192,218", "108,131,181"),
    ("184,214,190", "144,178,179", "86,121,148"),
    ("115,174,128", "90,145,120", "42,90,91"),
)
# ColorBrewer YlOrRd by number of classes.
SEQUENTIAL = {
    3: ("255,237,160", "254,178,76", "240,59,32"),
    4: ("255,255,178", "254,204,92", "253,141,60", "227,26,28"),
    5: ("255,255,178", "254,204,92", "253,141,60", "240,59,32", "189,0,38"),
    6: ("255,255,178", "254,217,118", "254,178,76", "253,141,60", "240,59,32", "189,0,38"),
    7: ("255,255,178", "254,217,118", "254,178,76", "253,141,60", "252,78,42", "227,26,28", "177,0,38"),
}

NORTH_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 108">
  <g fill="none" stroke="#1a1a1a" stroke-width="4.2" stroke-linejoin="round" stroke-linecap="round">
    <circle cx="40" cy="58" r="26"/>
    <polygon points="40,8 47.5,58 40,51 32.5,58"/>
    <polygon points="40,96 43.6,58 40,63 36.4,58"/>
    <circle cx="40" cy="58" r="3.1"/>
  </g>
  <path d="M32.4,22.2 V8.4 h2.35 L45.4,19.1 V8.4 H47.7 V22.2 H45.35 L34.75,11.5 V22.2 Z" fill="#1a1a1a"/>
  <circle cx="40" cy="58" r="26" fill="none" stroke="#ffffff" stroke-width="2.3"/>
  <polygon points="40,8 47.5,58 40,51" fill="#ededed" stroke="#ffffff" stroke-width="0.6" stroke-linejoin="round"/>
  <polygon points="40,8 32.5,58 40,51" fill="#ffffff" stroke="#ffffff" stroke-width="0.6" stroke-linejoin="round"/>
  <polygon points="40,96 43.6,58 40,63 36.4,58" fill="#ffffff" stroke="#ffffff" stroke-width="0.5"/>
  <circle cx="40" cy="58" r="3.1" fill="#ffffff"/>
  <path d="M32.4,22.2 V8.4 h2.35 L45.4,19.1 V8.4 H47.7 V22.2 H45.35 L34.75,11.5 V22.2 Z" fill="#ffffff"/>
</svg>
"""


# ---------------------------------------------------------------- symbols and text

def _fill(color, outline="0,0,0,0", width="0"):
    return QgsFillSymbol.createSimple({"color": color, "outline_color": outline, "outline_width": width,
                                       "outline_width_unit": "MM", "outline_style": "solid" if width != "0" else "no"})


def _line(color, width):
    return QgsLineSymbol.createSimple({"line_color": color, "line_width": width, "line_width_unit": "MM",
                                       "capstyle": "round"})


def _text(size, bold=True, halo=1.5):
    fmt = QgsTextFormat()
    fmt.setFont(QFont("Helvetica", int(size), QFont.Bold if bold else QFont.Normal))
    fmt.setSize(size)
    fmt.setSizeUnit(QgsUnitTypes.RenderPoints)
    fmt.setColor(QColor(0, 0, 0))
    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSize(halo)
    buf.setSizeUnit(QgsUnitTypes.RenderMillimeters)
    buf.setColor(QColor(255, 255, 255))
    fmt.setBuffer(buf)
    return fmt


def _rgb(text):
    return QColor(*map(int, text.split(",")[:3]))


# ---------------------------------------------------------------- layout geometry

def _place(layout, item, x, y, w=None, h=None):
    layout.addLayoutItem(item)
    item.attemptMove(QgsLayoutPoint(x, y, MM))
    if w is not None and h is not None:
        item.attemptResize(QgsLayoutSize(w, h, MM))


def _white_box(layout, x, y, w, h):
    box = QgsLayoutItemShape(layout)
    box.setShapeType(QgsLayoutItemShape.Rectangle)
    box.setSymbol(QgsFillSymbol.createSimple({"color": "255,255,255,255", "outline_color": "0,0,0,255",
                                              "outline_width": "0.45", "outline_width_unit": "MM"}))
    box.setFrameEnabled(False)
    box.setZValue(20)
    _place(layout, box, x, y, w, h)
    return box


def _label(layout, text, x, y, w, h, size=9.5, bold=False, align=Qt.AlignHCenter, z=23):
    item = QgsLayoutItemLabel(layout)
    item.setText(text)
    item.setFont(QFont("Arial", int(size), QFont.Bold if bold else QFont.Normal))
    item.setHAlign(align)
    item.setVAlign(Qt.AlignVCenter)
    item.setMargin(0)
    item.setZValue(z)
    _place(layout, item, x, y, w, h)
    return item


def _item_box(item):
    tl = item.positionAtReferencePoint(QgsLayoutItem.UpperLeft)
    size = item.sizeWithUnits()
    return float(tl.x()) - FRAME_X, float(tl.y()) - FRAME_Y, float(size.width()), float(size.height())


def _grow(box, pad):
    return box[0] - pad, box[1] - pad, box[2] + 2 * pad, box[3] + 2 * pad


def _overlap(a, b):
    return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + b[3] and a[1] + a[3] > b[1]


def _framed_extent(city: QgsRectangle, boxes, shape: QgsGeometry) -> QgsRectangle:
    """Largest view of the outline that clears every piece of furniture, kept as central as it allows."""
    cw, ch = max(city.width(), 1.0), max(city.height(), 1.0)
    padded = [_grow(b, FURNITURE_GAP) for b in boxes]
    shape = shape.simplify(max(cw, ch) / 400.0) or shape

    def to_ground(cx, cy, w_mm, h_mm, bx, by, bw, bh):
        x0 = city.xMinimum() + (bx - cx) / w_mm * cw
        x1 = city.xMinimum() + (bx + bw - cx) / w_mm * cw
        y1 = city.yMaximum() - (by - cy) / h_mm * ch
        y0 = city.yMaximum() - (by + bh - cy) / h_mm * ch
        return QgsGeometry.fromRect(QgsRectangle(x0, y0, x1, y1))

    def fits(cx, cy, w_mm, h_mm):
        inner = to_ground(cx, cy, w_mm, h_mm, 3.0, 3.0, FRAME_W - 6.0, FRAME_H - 6.0)
        if not inner.contains(shape):
            return False
        return not any(_overlap((cx, cy, w_mm, h_mm), b) and shape.intersects(to_ground(cx, cy, w_mm, h_mm, *b))
                       for b in padded)

    def place(w_mm, nx=13, ny=11):
        h_mm = w_mm * ch / cw
        if w_mm > 1.4 * FRAME_W or h_mm > 1.4 * FRAME_H:
            return None
        x0, x1 = sorted((3.0, FRAME_W - 3.0 - w_mm))
        y0, y1 = sorted((3.0, FRAME_H - 3.0 - h_mm))
        tx, ty = 0.5 * (FRAME_W - w_mm), 0.5 * (FRAME_H - h_mm)
        best, best_d = None, 1e18
        for i in range(nx):
            cx = x0 + (x1 - x0) * i / (nx - 1)
            for j in range(ny):
                cy = y0 + (y1 - y0) * j / (ny - 1)
                if fits(cx, cy, w_mm, h_mm):
                    d = (cx - tx) ** 2 + (cy - ty) ** 2
                    if d < best_d:
                        best, best_d = (cx, cy, w_mm, h_mm), d
        return best

    lo, hi = 40.0, 1.4 * min(FRAME_W, FRAME_H * cw / ch)
    best = place(lo) or (0.5 * (FRAME_W - lo), 0.5 * (FRAME_H - lo * ch / cw), lo, lo * ch / cw)
    for _ in range(24):
        mid = 0.5 * (lo + hi)
        placed = place(mid)
        if placed is None:
            hi = mid
        else:
            best, lo = placed, mid
    best = place(best[2], 24, 18) or best
    x, y, w_mm, h_mm = best
    view_w, view_h = FRAME_W * cw / w_mm, FRAME_H * ch / h_mm
    xmin = city.xMinimum() - x / FRAME_W * view_w
    ymax = city.yMaximum() + y / FRAME_H * view_h
    return QgsRectangle(xmin, ymax - view_h, xmin + view_w, ymax)


def _nice_scale(scale, map_item, target_mm=26.0):
    raw = target_mm * map_item.scale() / 1e6
    steps = (0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10, 20, 25, 50, 100, 150, 200, 250, 500)
    scale.setSegmentSizeMode(QgsScaleBarSettings.SegmentSizeFixed)
    scale.setUnitsPerSegment(min(steps, key=lambda v: abs(v - raw)))
    scale.update()


# ---------------------------------------------------------------- numbers

def _round_break(value):
    if value < 10:
        return float(max(1, round(value)))
    step = 10 ** (len(str(int(value))) - 1) / 2
    return float(round(value / step) * step)


def _jenks(values, k, sample=1200):
    """Fisher-Jenks natural breaks on a sample; returns the k - 1 inner cuts."""
    x = np.sort(np.random.default_rng(0).choice(values, size=min(len(values), sample), replace=False))
    n = len(x)
    cs, cs2 = np.concatenate([[0], np.cumsum(x)]), np.concatenate([[0], np.cumsum(x * x)])
    cost = np.full((k + 1, n + 1), np.inf)
    back = np.zeros((k + 1, n + 1), dtype=int)
    cost[0, 0] = 0.0
    for c in range(1, k + 1):
        for j in range(c, n + 1):
            i = np.arange(c - 1, j)
            s = cs[j] - cs[i]
            v = cost[c - 1, i] + (cs2[j] - cs2[i]) - s * s / (j - i)
            m = int(np.argmin(v))
            cost[c, j], back[c, j] = v[m], i[m]
    starts, j = [], n
    for c in range(k, 1, -1):
        j = back[c, j]
        starts.append(j)
    return [float(x[s - 1]) for s in sorted(starts)]


def _nice(value):
    if value == 0:
        return 0.0
    digits = 1 - int(math.floor(math.log10(abs(value))))
    return float(round(value, digits))


def _cuts(values, k, counts):
    values = values[np.isfinite(values)]
    raw = _jenks(values, k)
    cuts = sorted({(_round_break if counts else _nice)(c) for c in raw})
    return cuts if len(cuts) == k - 1 else sorted(set(raw))


def _fmt(value):
    if abs(value) >= 100:
        return f"{value:,.0f}"
    return f"{value:g}"


def _native_metres(path):
    ds = gdal.Open(path)
    gt = ds.GetGeoTransform()
    srs = osr.SpatialReference(wkt=ds.GetProjection())
    if srs.IsGeographic():
        lat = gt[3] + gt[5] * ds.RasterYSize / 2
        return abs(gt[1]) * 111_320.0 * math.cos(math.radians(lat))
    return abs(gt[1])


def _grid(path, outline_utm: QgsGeometry, utm_wkt, pixel, folder, tag, counts):
    """The raster on a `pixel`-metre UTM grid over the outline (NaN where it has no data). Counts per cell
    become densities before the warp, then people (or whatever is counted) per hectare."""
    src = gdal.Open(path)
    if src is None:
        raise QgsProcessingException(f"cannot open raster {path}")
    src_srs = osr.SpatialReference(wkt=src.GetProjection())
    src_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    dst_srs = osr.SpatialReference(wkt=utm_wkt)
    dst_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    box = outline_utm.boundingBox()
    box.grow(max(pixel, _native_metres(path)) * 20)
    to_src = osr.CoordinateTransformation(dst_srs, src_srs)
    corners = [to_src.TransformPoint(x, y)[:2] for x in (box.xMinimum(), box.xMaximum())
               for y in (box.yMinimum(), box.yMaximum())]
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    clip = os.path.join(folder, f"{tag}_clip.tif")
    gdal.Translate(clip, src, projWin=[min(xs), max(ys), max(xs), min(ys)])
    ds = gdal.Open(clip)
    gt = ds.GetGeoTransform()
    band = ds.GetRasterBand(1)
    arr = band.ReadAsArray().astype("float64")
    nodata = band.GetNoDataValue()
    bad = ~np.isfinite(arr) | ((arr == nodata) if nodata is not None else False)
    if counts:
        arr[bad | (arr < 0)] = 0.0
        if src_srs.IsGeographic():
            lat = gt[3] + gt[5] * np.arange(ds.RasterYSize + 1)
            area = 6371007.2 ** 2 * math.radians(abs(gt[1])) * np.abs(np.diff(np.sin(np.radians(lat))))[:, None]
        else:
            area = abs(gt[1] * gt[5])
        arr = arr / area
    else:
        arr[bad] = np.nan
    prep = os.path.join(folder, f"{tag}_prep.tif")
    out = gdal.GetDriverByName("GTiff").Create(prep, ds.RasterXSize, ds.RasterYSize, 1, gdal.GDT_Float32)
    out.SetGeoTransform(gt)
    out.SetProjection(ds.GetProjection())
    out.GetRasterBand(1).SetNoDataValue(float("nan"))
    out.GetRasterBand(1).WriteArray(arr.astype("float32"))
    out = None
    ds = None
    bb = outline_utm.boundingBox()
    x0, y0 = math.floor(bb.xMinimum() / pixel) * pixel, math.floor(bb.yMinimum() / pixel) * pixel
    x1, y1 = math.ceil(bb.xMaximum() / pixel) * pixel, math.ceil(bb.yMaximum() / pixel) * pixel
    warped = gdal.Warp(os.path.join(folder, f"{tag}_utm.tif"), prep, dstSRS=utm_wkt, xRes=pixel, yRes=pixel,
                       outputBounds=(x0, y0, x1, y1), resampleAlg="average", srcNodata=float("nan"),
                       dstNodata=float("nan"))
    grid = warped.ReadAsArray().astype("float64")
    if counts:
        grid = np.nan_to_num(grid, nan=0.0) * 10_000.0
    return grid, (x0, pixel, 0.0, y1, 0.0, -pixel)


def _inside_mask(outline_utm: QgsGeometry, shape, gt, utm_wkt, folder):
    path = os.path.join(folder, "outline_mask.tif")
    mem = gdal.GetDriverByName("GTiff").Create(path, shape[1], shape[0], 1, gdal.GDT_Byte)
    mem.SetGeoTransform(gt)
    mem.SetProjection(utm_wkt)
    srs = osr.SpatialReference(wkt=utm_wkt)
    vec = ogr.GetDriverByName("Memory").CreateDataSource("outline")
    layer = vec.CreateLayer("outline", srs, ogr.wkbMultiPolygon)
    feat = ogr.Feature(layer.GetLayerDefn())
    feat.SetGeometry(ogr.CreateGeometryFromWkb(bytes(outline_utm.asWkb())))
    layer.CreateFeature(feat)
    gdal.RasterizeLayer(mem, [1], layer, burn_values=[1])
    mask = mem.GetRasterBand(1).ReadAsArray().astype(bool)
    mem = None
    return mask


def _write_codes(code, gt, utm_wkt, path):
    out = gdal.GetDriverByName("GTiff").Create(path, code.shape[1], code.shape[0], 1, gdal.GDT_Byte,
                                               options=["COMPRESS=DEFLATE"])
    out.SetGeoTransform(gt)
    out.SetProjection(utm_wkt)
    band = out.GetRasterBand(1)
    band.SetNoDataValue(255)
    band.WriteArray(code)
    out = None


def _core_box(code, gt, centre) -> QgsRectangle:
    """Box around the largest cluster above the lowest class (and the centre), for the inset."""
    settled = (code != 255) & (code != 0)
    if not settled.any():
        settled = code != 255
    try:
        from scipy import ndimage
        clusters, _ = ndimage.label(ndimage.binary_dilation(settled, iterations=3))
        sizes = np.bincount(clusters[settled])
        sizes[0] = 0
        settled = settled & (clusters == sizes.argmax())
    except ImportError:
        pass
    rows, cols = np.nonzero(settled)
    r0, r1 = np.percentile(rows, [5, 95])
    c0, c1 = np.percentile(cols, [5, 95])
    pad = 0.08 * max(r1 - r0, c1 - c0, 10)
    if centre is not None:
        cc, cr = (centre.x() - gt[0]) / gt[1], (centre.y() - gt[3]) / gt[5]
        r0, r1, c0, c1 = min(r0, cr), max(r1, cr), min(c0, cc), max(c1, cc)
    r0, r1, c0, c1 = r0 - pad, r1 + pad, c0 - pad, c1 + pad
    return QgsRectangle(gt[0] + c0 * gt[1], gt[3] + (r1 + 1) * gt[5], gt[0] + (c1 + 1) * gt[1], gt[3] + r0 * gt[5])


def _plural(word):
    if word.endswith("y") and not word.endswith(("ay", "ey", "oy")):
        return word[:-1] + "ies"
    return word if word.endswith("s") else word + "s"


def _count_text(n):
    return f"{n / 1e6:.1f} million" if n >= 1e6 else f"{n:,.0f}"


# ---------------------------------------------------------------- the plate

def build_plate(aoi: QgsVectorLayer, title: str, *, rasters=(), country: str = "", name_field: str = "",
                unit_name: str = "", centre=None, centre_crs=None, centre_label: str = "", centre_desc: str = "",
                counts: bool = False, legend_title: str = "", classes: int = 5, bivariate: bool = False,
                inset: bool = True, callouts=(), credit: str = "", out_dir: str = "", pixel: float = 0.0,
                basemap: bool = True, project: QgsProject = None, feedback=None) -> dict:
    """One plate. `rasters` is a list of (path, name): none draws boundaries only, one a natural-breaks map,
    two with `bivariate` a 3 x 3 comparison. `country` is an ISO3 code for the locator ("" finds it)."""
    project = project or QgsProject.instance()
    say = feedback.pushInfo if feedback is not None else print
    ctx = project.transformContext()
    wgs = QgsCoordinateReferenceSystem("EPSG:4326")
    work = tempfile.mkdtemp(prefix="study_plate_")
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    rasters = list(rasters)[:2] if bivariate else list(rasters)[:1]
    bivariate = bivariate and len(rasters) == 2
    names = [n for _, n in rasters]

    # Area of interest and its units in the local UTM zone.
    centroid = QgsGeometry.unaryUnion([f.geometry() for f in aoi.getFeatures()]).centroid()
    centroid.transform(QgsCoordinateTransform(aoi.crs(), wgs, ctx))
    mid = centroid.asPoint()
    zone = int((mid.x() + 180) // 6) + 1
    utm = QgsCoordinateReferenceSystem(f"EPSG:{(32600 if mid.y() >= 0 else 32700) + zone}")
    to_utm = QgsCoordinateTransform(aoi.crs(), utm, ctx)
    unit_layer = QgsVectorLayer(f"MultiPolygon?crs={utm.authid()}", f"{title} units", "memory")
    unit_layer.dataProvider().addAttributes([QgsField("name", QVariant.String), QgsField("km2", QVariant.Double)])
    unit_layer.updateFields()
    outline = None
    feats = []
    for f in aoi.getFeatures():
        g = QgsGeometry(f.geometry())
        if g.isEmpty():
            continue
        g.transform(to_utm)
        g = g.makeValid()
        g.convertToMultiType()
        outline = g if outline is None else outline.combine(g)
        nf = QgsFeature(unit_layer.fields())
        nf.setGeometry(g)
        nf.setAttributes([str(f[name_field]) if name_field else "", g.area() / 1e6])
        feats.append(nf)
    if outline is None:
        raise QgsProcessingException("the area of interest has no polygons")
    unit_layer.dataProvider().addFeatures(feats)
    outline = outline.makeValid()
    outline.convertToMultiType()
    km2 = outline.area() / 1e6
    outline_layer = QgsVectorLayer(f"MultiPolygon?crs={utm.authid()}", f"{title} outline", "memory")
    nf = QgsFeature()
    nf.setGeometry(outline)
    outline_layer.dataProvider().addFeatures([nf])
    centre_utm = None
    centre_layer = QgsVectorLayer(f"Point?crs={utm.authid()}", f"{title} centre", "memory")
    if centre is not None:
        centre_utm = QgsCoordinateTransform(centre_crs or aoi.crs(), utm, ctx).transform(centre)
        nf = QgsFeature()
        nf.setGeometry(QgsGeometry.fromPointXY(centre_utm))
        centre_layer.dataProvider().addFeatures([nf])
    say(f"{title}: {len(feats)} unit(s), {km2:,.0f} km2, UTM zone {zone}")

    # Rasters.
    data_layer, cuts, total, core, grid_m = None, [], None, None, 0.0
    if rasters:
        grid_m = pixel or round(min(_native_metres(p) for p, _ in rasters))
        grids = []
        for i, (path, _) in enumerate(rasters):
            grid, gt = _grid(path, outline, utm.toWkt(), grid_m, work, f"r{i}", counts)
            grids.append(grid)
        shape = min(g.shape[0] for g in grids), min(g.shape[1] for g in grids)
        grids = [g[:shape[0], :shape[1]] for g in grids]
        inside = _inside_mask(outline, shape, gt, utm.toWkt(), work)
        if counts:
            total = float((grids[0][inside] * grid_m * grid_m / 10_000.0).sum())
        if bivariate:
            cuts = _cuts(np.concatenate([g[inside] for g in grids]), 3, counts)
            code = (3 * np.digitize(grids[0], cuts) + np.digitize(grids[1], cuts)).astype("uint8")
            empty = np.isnan(grids[0]) | np.isnan(grids[1])
            if counts:
                empty |= (grids[0] < EMPTY_PER_HA) & (grids[1] < EMPTY_PER_HA)
            colours = [(3 * g + w, BIVARIATE[g][w]) for g in range(3) for w in range(3)]
            agree = (np.digitize(grids[0], cuts) == np.digitize(grids[1], cuts))[inside & ~empty].mean()
            say(f"shared cuts {cuts}; the two rasters agree on {agree:.0%} of cells")
        else:
            k = int(min(max(classes, 3), 7))
            cuts = _cuts(grids[0][inside], k, counts)
            code = np.digitize(grids[0], cuts).astype("uint8")
            empty = np.isnan(grids[0])
            if counts:
                empty |= grids[0] < EMPTY_PER_HA
            colours = list(enumerate(SEQUENTIAL[len(cuts) + 1]))
            say(f"natural-break cuts {cuts}")
        code[empty | ~inside] = 255
        code_path = os.path.join(out_dir or work, f"{_slug(title)}_classes.tif")
        _write_codes(code, gt, utm.toWkt(), code_path)
        data_layer = QgsRasterLayer(code_path, f"{title}: {' and '.join(n for _, n in rasters)}")
        classes_r = [QgsPalettedRasterRenderer.Class(v, _rgb(c), "") for v, c in colours]
        data_layer.setRenderer(QgsPalettedRasterRenderer(data_layer.dataProvider(), 1, classes_r))
        data_layer.setOpacity(0.9)
        if inset and (code != 255).any():
            core = _core_box(code, gt, centre_utm)

    # Map layers, saved to a GeoPackage so the project keeps them.
    store = os.path.join(out_dir or work, f"{_slug(title)}_study_area.gpkg")
    if os.path.exists(store):
        os.remove(store)
    unit_layer = _save(unit_layer, store, "units", ctx)
    outline_layer = _save(outline_layer, store, "outline", ctx)
    centre_layer = _save(centre_layer, store, "centre", ctx) if centre_utm is not None else None
    engine = project.labelingEngineSettings()
    engine.setFlag(QgsLabelingEngineSettings.UsePartialCandidates, False)
    project.setLabelingEngineSettings(engine)
    base = [QgsRasterLayer(GREY_BASE, "Esri light grey", "wms")] if basemap else []
    unit_layer.renderer().setSymbol(_fill("0,0,0,0", UNIT_EDGE, "0.35"))
    small_km2 = max(5.0, km2 / 400.0)
    crowded = f"\"km2\" < {small_km2}"
    if callouts:
        crowded += " OR \"name\" IN (" + ", ".join("'" + c.replace("'", "''") + "'" for c in callouts) + ")"
    labelled = []
    if name_field and len(feats) > 1:
        big = QgsVectorLayer(f"{store}|layername=units", f"{title} unit names", "ogr")
        big.setSubsetString(f"NOT ({crowded})")
        big.renderer().setSymbol(_fill("0,0,0,0"))
        ln = QgsPalLayerSettings()
        ln.fieldName = "replace(replace(\"name\", '/', '/' || char(8203)), ' ', char(160))"
        ln.isExpression = True
        ln.placement = Qgis.LabelPlacement.AroundPoint
        ln.dist = 0.5
        ln.centroidInside = True
        ln.priority = 5
        ln.setUnplacedVisibility(Qgis.UnplacedLabelVisibility.NeverShow)
        ln.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.PreventOverlap)
        fmt = _text(11, bold=False, halo=0.9)
        fmt.setColor(QColor(30, 26, 22))
        ln.setFormat(fmt)
        ln.dataDefinedProperties().setProperty(QgsPalLayerSettings.Size, QgsProperty.fromExpression(
            "CASE WHEN \"km2\" < 50 THEN 9.5 ELSE 11 END"))
        big.setLabeling(QgsVectorLayerSimpleLabeling(ln))
        big.setLabelsEnabled(True)
        small = QgsVectorLayer(f"{store}|layername=units", f"{title} small unit names", "ogr")
        small.setSubsetString(crowded)
        small.renderer().setSymbol(_fill("0,0,0,0"))
        sl = QgsPalLayerSettings(ln)
        sl.placement = Qgis.LabelPlacement.OutsidePolygons
        sl.dist = 4.0
        sl.priority = 9
        leader = QgsSimpleLineCallout()
        leader.setEnabled(True)
        leader.setLineSymbol(_line("30,26,22,255", "0.3"))
        leader.setAnchorPoint(QgsCallout.PointOnSurface)
        sl.setCallout(leader)
        small.setLabeling(QgsVectorLayerSimpleLabeling(sl))
        small.setLabelsEnabled(True)
        labelled = [small, big]

    outline_layer.renderer().setSymbol(_fill("0,0,0,0", EDGE, "0.9"))
    block = QgsPalLayerSettings()
    block.drawLabels = False
    block.obstacle = True
    block.obstacleSettings().setType(QgsLabelObstacleSettings.PolygonBoundary)
    block.fieldName = "''"
    block.isExpression = True
    outline_layer.setLabeling(QgsVectorLayerSimpleLabeling(block))
    outline_layer.setLabelsEnabled(True)

    star = QgsMarkerSymbol.createSimple({"name": "star", "color": STAR_YELLOW, "outline_color": "0,0,0,255",
                                         "outline_width": "0.5", "size": "7.5"})
    labelled_centre = []
    if centre_layer is not None:
        centre_layer.renderer().setSymbol(star)
        labelled_centre = [centre_layer]
    cl = QgsPalLayerSettings()
    cl.fieldName = "'" + (centre_label or "").replace("'", "''") + "'"
    cl.isExpression = True
    cl.placement = Qgis.LabelPlacement.OrderedPositionsAroundPoint
    cl.predefinedPositionOrder = [QgsPalLayerSettings.TopRight, QgsPalLayerSettings.TopLeft,
                                  QgsPalLayerSettings.MiddleRight, QgsPalLayerSettings.BottomRight,
                                  QgsPalLayerSettings.MiddleLeft, QgsPalLayerSettings.BottomLeft]
    cl.offsetType = Qgis.LabelOffsetType.FromSymbolBounds
    cl.dist = 1.0
    cl.priority = 10
    cl.obstacle = True
    cl.setFormat(_text(12, halo=1.0))
    if centre_layer is not None and centre_label:
        centre_layer.setLabeling(QgsVectorLayerSimpleLabeling(cl))
        centre_layer.setLabelsEnabled(True)

    stack = (labelled_centre + labelled + [outline_layer] + ([unit_layer] if len(feats) > 1 else [])
             + ([data_layer] if data_layer else []) + base)
    group = project.layerTreeRoot().insertGroup(0, f"Study area plate: {title}")
    for layer in reversed(stack):
        project.addMapLayer(layer, False)
        group.insertLayer(0, layer)
    group.setItemVisibilityChecked(False)

    # Layout.
    name = f"Study area: {title}" + (f" ({' vs '.join(names)})" if bivariate else
                                      f" ({names[0]})" if rasters else "")
    manager = project.layoutManager()
    old = manager.layoutByName(name)
    if old is not None:
        manager.removeLayout(old)
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(name)
    layout.pageCollection().page(0).setPageSize(QgsLayoutSize(PAGE_W, PAGE_H, MM))
    manager.addLayout(layout)

    map_item = _map(layout, utm, stack)
    ext = outline.boundingBox()
    map_item.setExtent(ext)
    locator, locator_ok = _locator(layout, project, outline, utm, title, mid, group, country)

    unit_word = unit_name or "unit"
    parts = f"{len(feats)} {_plural(unit_word)}, " if len(feats) > 1 else ""
    lead = f"The black outline is the study area, {title}: {parts}{km2:,.0f} square kilometres"
    lead += f", with {_count_text(total)} counted by {rasters[0][1]}." if total else "."
    names = [n for _, n in rasters]
    if bivariate:
        middle = (f" Each {grid_m:g}-metre square is coloured by {names[0]} (green) and {names[1]} (blue); dark teal "
                  f"is where both are high.")
    elif rasters:
        middle = (f" Each {grid_m:g}-metre square is coloured by {names[0]} in {len(cuts) + 1} natural-break "
                  f"classes.")
    else:
        middle = ""
    star_note = f" The yellow star marks {centre_desc or centre_label or 'the centre'}." if centre_utm else ""
    caption = lead + middle + star_note
    entries = [("Polygon", "Study area", _fill("0,0,0,0", EDGE, "0.9"))]
    if len(feats) > 1:
        entries.append(("Polygon", unit_word[:1].upper() + unit_word[1:], _fill("0,0,0,0", UNIT_EDGE, "0.4")))
    if centre_utm is not None:
        entries.append(("Point", centre_label or "Centre", star.clone()))
    boxes, scale, legend = _furniture(layout, map_item, project, group, title=f"STUDY AREA\n{title}",
                                      caption=caption, entries=entries,
                                      credit="\n".join(t for t in (credit, "Base map © Esri" if basemap else "") if t),
                                      locator=locator if locator_ok else None)

    legend_top = _item_box(legend)[1]
    heading = legend_title or (names[0] if len(names) == 1 else "Values")
    if bivariate:
        key = _bivariate_key(layout, cuts, names[0], names[1], heading, FRAME_X + 6.0,
                             FRAME_Y + legend_top - KEY_H - 3.0)
    elif rasters:
        key = _sequence_key(layout, cuts, names[0], heading, FRAME_X + 6.0, FRAME_Y + legend_top)
    else:
        key = None
    if key is not None:
        map_item.addLabelBlockingItem(key)
        boxes.append(_grow(_item_box(key), BOTTOM_CLEAR))

    framed = _framed_extent(ext, boxes, outline)
    if core is not None and locator_ok:
        inset = _core_inset(layout, locator, core, stack, utm)
        framed = _framed_extent(ext, boxes + [_grow(_item_box(inset), FURNITURE_GAP)], outline)
        widest = inset.rect().width() * framed.width() / (INSET_GAIN * map_item.rect().width())
        if core.width() > widest:
            core.scale(widest / core.width())
            mx, my = 0.25 * core.width(), 0.25 * core.height()
            sx, sy = (centre_utm.x(), centre_utm.y()) if centre_utm is not None else (core.center().x(),
                                                                                      core.center().y())
            dx = min(0.0, sx - (core.xMinimum() + mx)) + max(0.0, sx - (core.xMaximum() - mx))
            dy = min(0.0, sy - (core.yMinimum() + my)) + max(0.0, sy - (core.yMaximum() - my))
            core = QgsRectangle(core.xMinimum() + dx, core.yMinimum() + dy, core.xMaximum() + dx,
                                core.yMaximum() + dy)
            inset.setExtent(core)
            _inset_title(inset.title_label, core)
        map_item.addLabelBlockingItem(inset)
        overview = QgsLayoutItemMapOverview("Core", map_item)
        overview.setLinkedMap(inset)
        overview.setFrameSymbol(_fill("0,0,0,0", LOCATOR_RED, "0.6"))
        map_item.overviews().addOverview(overview)
    map_item.setExtent(framed)
    map_item.refresh()
    _nice_scale(scale, map_item)
    scale.refresh()

    result = {"layout": name, "total": total, "km2": km2, "cuts": cuts}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        stem = os.path.join(out_dir, f"{_slug(title)}_study_area" + (f"_{_slug(names[0])}" if names and not
                                                                                       bivariate else ""))
        exporter = QgsLayoutExporter(layout)
        img = QgsLayoutExporter.ImageExportSettings()
        img.dpi = 200
        exporter.exportToImage(stem + ".png", img)
        exporter.exportToPdf(stem + ".pdf", QgsLayoutExporter.PdfExportSettings())
        result.update(png=stem + ".png", pdf=stem + ".pdf")
        say(f"wrote {stem}.png and .pdf")
        # Without out_dir the project's layers still read from work.
        shutil.rmtree(work, ignore_errors=True)
    return result


def _save(layer, path, name, ctx):
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = name
    if os.path.exists(path):
        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    err = QgsVectorFileWriter.writeAsVectorFormatV3(layer, path, ctx, opts)
    if err[0] != QgsVectorFileWriter.NoError:
        raise QgsProcessingException(f"could not write {name}: {err[1]}")
    saved = QgsVectorLayer(f"{path}|layername={name}", layer.name(), "ogr")
    if not saved.isValid():
        raise QgsProcessingException(f"could not read back {name}")
    return saved


def _slug(text):
    return "".join(c.lower() if c.isalnum() else "_" for c in text).strip("_")


def _map(layout, crs, layers):
    item = QgsLayoutItemMap(layout)
    item.setFrameEnabled(True)
    item.setFrameStrokeColor(QColor(0, 0, 0))
    item.setFrameStrokeWidth(QgsLayoutMeasurement(0.55, MM))
    item.setBackgroundColor(QColor("#eceae4"))
    item.setCrs(crs)
    item.setKeepLayerSet(True)
    item.setKeepLayerStyles(True)
    item.setLayers(layers)
    item.setLabelMargin(QgsLayoutMeasurement(3.0, MM))
    item.setMapFlags(QgsLayoutItemMap.MapItemFlags())
    item.setZValue(0)
    _place(layout, item, FRAME_X, FRAME_Y, FRAME_W, FRAME_H)
    return item


def _locator(layout, project, outline: QgsGeometry, utm, title, centre_ll: QgsPointXY, group, iso3=""):
    """Country with its provinces from QGIS's own world map, the city outline in red, and the city's name."""
    world = os.path.join(QgsApplication.pkgDataPath(), "resources", "data", "world_map.gpkg")
    countries = QgsVectorLayer(f"{world}|layername=countries", "Locator countries", "ogr")
    if not countries.isValid():
        return None, False
    here = QgsGeometry.fromPointXY(centre_ll)
    hit = next((f for f in countries.getFeatures() if iso3 and f["ISO_A3"] == iso3), None)
    if hit is None:
        hit = next((f for f in countries.getFeatures() if f.geometry().intersects(here)), None)
    if hit is None:
        hit = min(countries.getFeatures(), key=lambda f: f.geometry().distance(here))
    iso = hit["ISO_A3"]
    country = QgsVectorLayer(f"{world}|layername=countries", "Locator country", "ogr")
    country.setSubsetString(f"\"fid\" = {hit.id()}")
    country.renderer().setSymbol(_fill("0,0,0,0", EDGE, "0.4"))
    provinces = QgsVectorLayer(f"{world}|layername=states_provinces", "Locator provinces", "ogr")
    provinces.setSubsetString(f"\"adm0_a3\" = '{iso}'")
    provinces.renderer().setSymbol(_fill("236,234,228,255", "150,146,140,255", "0.12"))
    if provinces.featureCount() == 0:
        provinces = QgsVectorLayer(f"{world}|layername=countries", "Locator provinces", "ogr")
        provinces.setSubsetString(f"\"fid\" = {hit.id()}")
        provinces.renderer().setSymbol(_fill("236,234,228,255"))
    city = QgsVectorLayer(f"Polygon?crs={utm.authid()}", "Locator city", "memory")
    f = QgsFeature()
    f.setGeometry(outline)
    city.dataProvider().addFeatures([f])
    city.renderer().setSymbol(_fill(LOCATOR_RED, "120,0,0,255", "0.5"))
    pin = QgsVectorLayer(f"Point?crs={utm.authid()}", "Locator name", "memory")
    f = QgsFeature()
    f.setGeometry(outline.pointOnSurface())
    pin.dataProvider().addFeatures([f])
    pin.renderer().setSymbol(QgsMarkerSymbol.createSimple({"name": "circle", "color": "0,0,0,0",
                                                           "outline_style": "no", "size": "3.0"}))
    tag = QgsPalLayerSettings()
    tag.fieldName = "'" + title.replace("'", "''") + "'"
    tag.isExpression = True
    tag.placement = Qgis.LabelPlacement.OrderedPositionsAroundPoint
    tag.predefinedPositionOrder = [QgsPalLayerSettings.MiddleRight, QgsPalLayerSettings.TopRight,
                                   QgsPalLayerSettings.MiddleLeft, QgsPalLayerSettings.BottomRight]
    tag.offsetType = Qgis.LabelOffsetType.FromSymbolBounds
    tag.dist = 0.6
    tag.setFormat(_text(9, halo=0.8))
    pin.setLabeling(QgsVectorLayerSimpleLabeling(tag))
    pin.setLabelsEnabled(True)
    for layer in (provinces, country, city, pin):
        project.addMapLayer(layer, False)
        group.addLayer(layer)

    ctx = project.transformContext()
    lon = hit.geometry().centroid().asPoint().x()
    lat = hit.geometry().centroid().asPoint().y()
    crs = QgsCoordinateReferenceSystem()
    crs.createFromProj(f"+proj=laea +lat_0={lat:.3f} +lon_0={lon:.3f} +datum=WGS84 +units=m +no_defs")
    shape = QgsGeometry(hit.geometry())
    shape.transform(QgsCoordinateTransform(countries.crs(), crs, ctx))
    ext = shape.boundingBox()
    ext.grow(0.04 * max(ext.width(), ext.height()))
    w = 52.0
    h = max(min(w * ext.height() / ext.width(), 60.0), 26.0)
    w = min(h * ext.width() / ext.height(), 70.0)
    loc = QgsLayoutItemMap(layout)
    loc.setFrameEnabled(True)
    loc.setFrameStrokeColor(QColor(0, 0, 0))
    loc.setFrameStrokeWidth(QgsLayoutMeasurement(0.35, MM))
    loc.setBackgroundColor(QColor("#ffffff"))
    loc.setCrs(crs)
    loc.setKeepLayerSet(True)
    loc.setKeepLayerStyles(True)
    loc.setLayers([pin, city, country, provinces])
    loc.setZValue(22)
    _place(layout, loc, PAGE_W - 14.0 - w, 46.0, w, h)
    loc.setExtent(ext)
    return loc, True


def _furniture(layout, map_item, project, group, *, title, caption, entries, credit, locator):
    title_panel = _white_box(layout, FRAME_X, FRAME_Y, TITLE_W, TITLE_H)
    head = _label(layout, title, FRAME_X, FRAME_Y, TITLE_W, TITLE_H, size=15, bold=True, z=21)
    head.setMargin(2.0)

    svg_path = os.path.join(tempfile.gettempdir(), "wisdom_north_arrow.svg")
    with open(svg_path, "w") as fh:
        fh.write(NORTH_SVG)
    north = QgsLayoutItemPicture(layout)
    north.setMode(QgsLayoutItemPicture.FormatSVG)
    north.setPicturePath(svg_path)
    north.setLinkedMap(map_item)
    north.setNorthMode(QgsLayoutItemPicture.GridNorth)
    north.setFrameEnabled(False)
    north.setBackgroundEnabled(False)
    north.setZValue(24)
    _place(layout, north, PAGE_W - 40.0, 10.0, 26.0, 32.0)

    legend = QgsLayoutItemLegend(layout)
    legend.setLinkedMap(map_item)
    legend.setTitle("Boundaries")
    legend.setTitleAlignment(Qt.AlignLeft)
    legend.setStyleFont(QgsLegendStyle.Title, QFont("Arial", 13, QFont.Bold))
    legend.setStyleFont(QgsLegendStyle.SymbolLabel, QFont("Arial", 12))
    legend.setSymbolWidth(7.0)
    legend.setSymbolHeight(5.0)
    legend.setBoxSpace(2.5)
    legend.setLineSpacing(1.6)
    legend.setStyleMargin(QgsLegendStyle.Title, QgsLegendStyle.Bottom, 2.0)
    legend.setStyleMargin(QgsLegendStyle.Symbol, QgsLegendStyle.Top, 0.8)
    legend.setStyleMargin(QgsLegendStyle.Symbol, QgsLegendStyle.Bottom, 0.8)
    legend.setFrameEnabled(True)
    legend.setFrameStrokeColor(QColor(0, 0, 0))
    legend.setFrameStrokeWidth(QgsLayoutMeasurement(0.45, MM))
    legend.setBackgroundColor(QColor(255, 255, 255))
    legend.setBackgroundEnabled(True)
    legend.setAutoUpdateModel(False)
    legend.setColumnCount(1)
    root = legend.model().rootGroup()
    for child in list(root.children()):
        root.removeChildNode(child)
    for kind, text, symbol in entries:
        lyr = QgsVectorLayer(f"{kind}?crs=EPSG:4326", text, "memory")
        lyr.renderer().setSymbol(symbol)
        project.addMapLayer(lyr, False)
        group.addLayer(lyr)
        node = root.addLayer(lyr)
        QgsLegendRenderer.setNodeLegendStyle(node, QgsLegendStyle.Hidden)
    legend.setZValue(20)
    layout.addLayoutItem(legend)
    pad = float(legend.boxSpace())
    row = float(legend.symbolHeight()) + 1.05
    target_h = 2.0 * pad + 6.4 + len(entries) * row
    legend.setResizeToContents(True)
    legend.setReferencePoint(QgsLayoutItem.UpperLeft)
    legend.attemptMove(QgsLayoutPoint(FRAME_X + 6.0, FRAME_Y + 120.0, MM))
    legend.attemptResize(QgsLayoutSize(LEGEND_W, target_h, MM))
    legend.refresh()
    try:
        legend.adjustBoxSize()
    except Exception:
        pass
    measured = legend.sizeWithUnits()
    mw, mh = float(measured.width()), float(measured.height())
    w = mw if 36.0 <= mw <= LEGEND_W + 8.0 else LEGEND_W
    h = min(mh, target_h) if mh >= 16.0 else target_h
    h = min(h, target_h)
    legend.setResizeToContents(False)
    legend.setReferencePoint(QgsLayoutItem.LowerLeft)
    legend.attemptResize(QgsLayoutSize(w, h, MM))
    legend.attemptMove(QgsLayoutPoint(FRAME_X + 6.0, FRAME_Y + FRAME_H - 6.0, MM))

    scale = QgsLayoutItemScaleBar(layout)
    scale.setLinkedMap(map_item)
    scale.setStyle("Line Ticks Up")
    scale.setUnits(QgsUnitTypes.DistanceKilometers)
    scale.setNumberOfSegments(2)
    scale.setNumberOfSegmentsLeft(0)
    scale.setUnitLabel("km")
    scale.setFont(QFont("Arial", 11))
    scale.setHeight(2.4)
    scale.setLineWidth(0.5)
    scale.setFrameEnabled(False)
    scale.setBackgroundEnabled(False)
    scale.setZValue(20)
    scale.setSegmentSizeMode(QgsScaleBarSettings.SegmentSizeFitWidth)
    scale.setMinimumBarWidth(40)
    scale.setMaximumBarWidth(60)
    layout.addLayoutItem(scale)
    scale.setReferencePoint(QgsLayoutItem.LowerRight)
    scale.attemptMove(QgsLayoutPoint(PAGE_W - 20.0, FRAME_Y + FRAME_H - 2.0, MM))
    scale.refresh()

    scale_w = max(scale.sizeWithUnits().width(), 78.0)
    left = 6.0 + LEGEND_W + FURNITURE_GAP
    right = FRAME_W - 6.0 - scale_w - FURNITURE_GAP
    avail = max(right - left, 80.0)
    note_w = min(NOTE_W, avail)
    note_x = FRAME_X + left + 0.5 * (avail - note_w)
    note_y = FRAME_Y + FRAME_H - NOTE_BOTTOM - NOTE_H
    note_panel = _white_box(layout, note_x, note_y, note_w, NOTE_H)
    note = _label(layout, caption, note_x, note_y, note_w, NOTE_H, size=12, bold=True, z=21)
    note.setMargin(2.4)

    items = [title_panel, north, legend, scale, note_panel]
    boxes = [_grow(_item_box(title_panel), 2.0), _item_box(north), _grow(_item_box(legend), BOTTOM_CLEAR),
             _grow(_item_box(note_panel), BOTTOM_CLEAR)]
    sx, sy, sw, sh = _item_box(scale)
    boxes.append((sx - 3.0, sy - 12.0, sw + 6.0, sh + 14.0))
    if credit:
        cr = QgsLayoutItemLabel(layout)
        cr.setText(credit)
        fmt = _text(7, bold=False, halo=0.6)
        fmt.setFont(QFont("Arial", 7))
        cr.setTextFormat(fmt)
        cr.setHAlign(Qt.AlignRight)
        cr.setVAlign(Qt.AlignBottom)
        cr.setZValue(22)
        top = FRAME_Y + FRAME_H - 6.0 - max(scale.sizeWithUnits().height(), 14.0)
        _place(layout, cr, PAGE_W - 14.0 - scale_w - 30.0, top - 10.5, scale_w + 30.0, 9.0)
        items.append(cr)
        boxes.append(_grow(_item_box(cr), 2.0))
    if locator is not None:
        items.append(locator)
        boxes.append(_item_box(locator))
    for item in items:
        map_item.addLabelBlockingItem(item)
    return boxes, scale, legend


def _swatch(layout, x, y, w, h, colour):
    cell = QgsLayoutItemShape(layout)
    cell.setShapeType(QgsLayoutItemShape.Rectangle)
    cell.setSymbol(QgsFillSymbol.createSimple({"color": f"{colour},255", "outline_color": "255,255,255,255",
                                               "outline_width": "0.3"}))
    cell.setZValue(22)
    _place(layout, cell, x, y, w, h)


def _bivariate_key(layout, cuts, label_a, label_b, heading, x, y):
    low, high = (_fmt(c) for c in cuts)
    ticks = (f"under {low}", f"{low}\u2013{high}", f"over {high}")
    w, h = LEGEND_W, KEY_H
    box = _white_box(layout, x, y, w, h)
    _label(layout, heading, x + 2.5, y + 2.5, w - 5, 6, size=11, bold=True, align=Qt.AlignLeft)
    gx, gy = x + 25.0, y + 11.5
    for g in range(3):
        for c in range(3):
            _swatch(layout, gx + c * KEY_CELL, gy + (2 - g) * KEY_CELL, KEY_CELL, KEY_CELL, BIVARIATE[g][c])
    for i, tick in enumerate(ticks):
        _label(layout, tick, gx - 21.0, gy + (2 - i) * KEY_CELL, 20.0, KEY_CELL, size=8, align=Qt.AlignRight)
        _label(layout, tick.replace(" ", "\n", 1) if i != 1 else tick, gx + i * KEY_CELL - 1.5,
               gy + 3 * KEY_CELL + 0.8, KEY_CELL + 3.0, 7.0, size=7.5)
    _label(layout, f"{label_b} \u2192", gx, gy + 3 * KEY_CELL + 8.5, 3 * KEY_CELL, 5, size=10, bold=True)
    _label(layout, f"{label_a} \u2191", gx + 3 * KEY_CELL + 1.5, gy + 1.5 * KEY_CELL - 2.5, 22, 5, size=9,
           bold=True, align=Qt.AlignLeft)
    _label(layout, f"Green: only {label_a} is high. Blue: only {label_b}.\nDark teal: both high.",
           x + 2.5, y + h - 11.5, w - 5, 10, size=8, align=Qt.AlignLeft)
    return box


def _sequence_key(layout, cuts, label_a, heading, x, legend_top):
    fmt = _fmt
    names = [f"under {fmt(cuts[0])}"] + [f"{fmt(a)}\u2013{fmt(b)}" for a, b in zip(cuts, cuts[1:])]
    names.append(f"over {fmt(cuts[-1])}")
    h = 14.0 + 6.0 * len(names) + 6.0
    y = legend_top - h - 3.0
    box = _white_box(layout, x, y, LEGEND_W, h)
    _label(layout, heading, x + 2.5, y + 2.5, LEGEND_W - 5, 6, size=11, bold=True, align=Qt.AlignLeft)
    for i, text in enumerate(names):
        _swatch(layout, x + 3.0, y + 11.0 + 6.0 * i, 7.0, 4.5, SEQUENTIAL[len(names)][i])
        _label(layout, text, x + 12.0, y + 10.5 + 6.0 * i, LEGEND_W - 15.0, 5.5, size=10, align=Qt.AlignLeft)
    _label(layout, f"Source: {label_a}", x + 2.5, y + h - 7.0, LEGEND_W - 5, 5, size=8, align=Qt.AlignLeft)
    return box


def _core_inset(layout, locator, core: QgsRectangle, layers, crs):
    lx, ly, lw, lh = _item_box(locator)
    top = FRAME_Y + ly + lh + 5.0
    max_h = 250.0 - top
    w = INSET_W
    h = w * core.height() / core.width()
    if h > max_h:
        h, w = max_h, max_h * core.width() / core.height()
    inset = _map(layout, crs, layers)
    inset.setFrameStrokeColor(_rgb(LOCATOR_RED))
    inset.setLabelMargin(QgsLayoutMeasurement(1.5, MM))
    inset.setZValue(22)
    inset.attemptMove(QgsLayoutPoint(PAGE_W - 14.0 - w, top, MM))
    inset.attemptResize(QgsLayoutSize(w, h, MM))
    inset.setExtent(core)
    label = QgsLayoutItemLabel(layout)
    label.setFont(QFont("Arial", 10, QFont.Bold))
    label.setBackgroundEnabled(True)
    label.setBackgroundColor(QColor(255, 255, 255))
    label.setMargin(1.2)
    label.setZValue(23)
    _place(layout, label, PAGE_W - 14.0 - w + 1.5, top + 1.5)
    _inset_title(label, core)
    inset.addLabelBlockingItem(label)
    inset.title_label = label
    return inset


def _inset_title(label, core: QgsRectangle):
    km = core.width() / 1000
    label.setText(f"Zoomed area, {km:.0f} km across" if km >= 2 else f"Zoomed area, {core.width():.0f} m across")
    label.adjustSizeToText()
    size = label.sizeWithUnits()
    label.attemptResize(QgsLayoutSize(size.width() + 4.0, size.height(), MM))


# ---------------------------------------------------------------- Processing wrapper

def _countries():
    world = os.path.join(QgsApplication.pkgDataPath(), "resources", "data", "world_map.gpkg")
    layer = QgsVectorLayer(f"{world}|layername=countries", "countries", "ogr")
    if not layer.isValid():
        return []
    return sorted({(f["NAME"], f["ISO_A3"]) for f in layer.getFeatures() if f["NAME"]})


# ---------------------------------------------------------------- fetching a place from its name

USER_AGENT = b"WisdomStudyAreaPlate/1.0 (QGIS Processing script)"
NOMINATIM = ("https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&polygon_geojson=1"
             "&polygon_threshold=0.0005&limit=10&q=")
GEOBOUNDARIES = "https://www.geoboundaries.org/api/current/{release}/{iso3}/ADM{level}/"
GHSL_ROOT = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL"
GHSL_X0, GHSL_Y0, GHSL_TILE = -18041000.0, 9000000.0, 1_000_000.0
GHSL_YEARS = tuple(range(1975, 2031, 5))
MOLLWEIDE = "ESRI:54009"
# key, GHSL product, cell metres, version, name on the plate, counts per cell, legend title
DOWNLOADS = (
    ("pop", "GHS_POP", "100", "V1-0", "GHS-POP", True, "People per hectare, {year}"),
    ("built", "GHS_BUILT_S", "100", "V1-0", "GHS-BUILT-S", False, "Built-up share of the land, {year} (%)"),
)
CITYISH = {"city", "town", "municipality", "village", "city_district", "borough", "suburb", "county",
           "state_district", "district", "hamlet"}
AREA_MODES = ("Units that make up the built-up city (automatic)", "The built-up city outline (GHSL urban centre)",
              "The official boundary from OpenStreetMap")
UNIT_SHARE = 0.5
MAX_UNITS = 80
MAX_LEVEL_UNITS = 25_000
ISO2_FIX = {"FR": "FRA", "NO": "NOR", "XK": "XKX"}
POP_MIRROR = ("https://data.source.coop/nlebovits/ghsl/pop-{year}/pop-{year}-R{row}_C{col}/"
              "GHS_POP_E{year}_GLOBE_R2023A_54009_100_V1_0_R{row}_C{col}.tif")
POP_MIRROR_NOTE = ("the Cloud Optimized GeoTIFF mirror of the JRC tiles on Source Cooperative "
                   "(https://source.coop/nlebovits/ghsl), reading only the cells needed")
DETAILS = ("100 m (best)", "1 km (for regions and countries; built-up land downloads much less)")
CHUNK_MIN, CHUNK_MAX = 256 * 1024, 32 * 1024 * 1024
DOWNLOAD_TIMEOUT_MS = 300_000


def _cache_dir():
    path = os.path.join(QgsApplication.qgisSettingsDirPath(), "study_area_plate_cache")
    os.makedirs(path, exist_ok=True)
    return path


def _request(url, feedback=None, start=None, size=0, tries=5):
    """(HTTP status, body, Content-Range) of a GET through QGIS's own network settings, retried on failure.
    With `start`, asks for `size` bytes from that offset."""
    error = ""
    for attempt in range(tries):
        if feedback is not None and feedback.isCanceled():
            break
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", USER_AGENT)
        if start is not None:
            request.setRawHeader(b"Range", f"bytes={start}-{start + size - 1}".encode())
        blocking = QgsBlockingNetworkRequest()
        code = blocking.get(request, True, feedback)
        reply = blocking.reply()
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        body = bytes(reply.content())
        if status in (404, 416) or (code == QgsBlockingNetworkRequest.NoError and status in (200, 206) and
                                    (body or start is None)):
            return status, body, bytes(reply.rawHeader(b"Content-Range")).decode()
        error = blocking.errorMessage() or f"HTTP {status}, {len(body)} bytes"
        time.sleep(3 * (attempt + 1))
    if feedback is not None and feedback.isCanceled():
        raise QgsProcessingException("cancelled; run again and the download carries on where it stopped")
    raise QgsProcessingException(f"could not download {url}: {error}")


def _get(url, feedback=None):
    """Body of a small GET, or None when the server has no such file."""
    status, body, _ = _request(url, feedback)
    return None if status == 404 else body


def _usable(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    return zipfile.is_zipfile(path) if path.endswith(".zip") else True


def _cached(url, name, feedback=None):
    """Local copy of `url` in the cache folder, downloaded the first time only, in chunks that resume after a
    cancelled or broken run. None if the server has no such file."""
    path = os.path.join(_cache_dir(), name)
    if _usable(path):
        return path
    if os.path.exists(path):
        os.remove(path)
    part = path + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    total, told, chunk = None, -1, CHUNK_MIN
    if feedback is not None:
        feedback.pushInfo(f"downloading {url}" + (f" (resuming at {have / 1e6:.1f} MB)" if have else ""))
    timeout = QgsNetworkAccessManager.timeout()
    QgsNetworkAccessManager.setTimeout(max(timeout, DOWNLOAD_TIMEOUT_MS))
    try:
        while total is None or have < total:
            began = time.time()
            status, body, span = _request(url, feedback, start=have, size=chunk)
            if status == 404:
                return None
            if status == 416:
                break
            if status != 206:
                with open(part, "wb") as fh:
                    fh.write(body)
                break
            total = int(span.rsplit("/", 1)[-1]) if "/" in span and not span.endswith("*") else have + len(body)
            with open(part, "ab") as fh:
                fh.write(body)
            have += len(body)
            # Size the next piece to about a minute at the speed the server is giving now.
            rate = len(body) / max(time.time() - began, 0.1)
            chunk = int(min(CHUNK_MAX, max(CHUNK_MIN, rate * 60)))
            step = int(10 * have / total) if total else 10
            if feedback is not None and total > CHUNK_MIN and step != told:
                told = step
                left = (total - have) / max(rate, 1.0) / 60
                feedback.pushInfo(f"  {have / 1e6:.1f} of {total / 1e6:.1f} MB at {rate / 1e3:,.0f} KB/s"
                                  + (f", about {left:,.0f} min to go" if have < total else ""))
    finally:
        QgsNetworkAccessManager.setTimeout(timeout)
    os.replace(part, path)
    if not _usable(path):
        os.remove(path)
        raise QgsProcessingException(f"the download of {url} came back broken; run again to retry")
    return path


def _search(query, feedback=None, extra=""):
    time.sleep(1.0)
    body = _get(NOMINATIM + quote(query) + extra, feedback)
    return json.loads(body or b"[]")


def _pick_place(results):
    """Prefer a city, town or district over a state of the same name, then OpenStreetMap's importance."""
    return max(results, key=lambda r: (r.get("addresstype") in CITYISH and r.get("category") in ("place", "boundary"),
                                       r.get("importance") or 0.0))


def _iso3(iso2):
    iso2 = (iso2 or "").upper()
    world = os.path.join(QgsApplication.pkgDataPath(), "resources", "data", "world_map.gpkg")
    layer = QgsVectorLayer(f"{world}|layername=countries", "countries", "ogr")
    for f in layer.getFeatures():
        if iso2 in (f["iso_a2"], f["WB_A2"]) and f["ISO_A3"] and f["ISO_A3"] != "-99":
            return f["ISO_A3"]
    return ISO2_FIX.get(iso2, "")


def _snap(box, cell):
    x0, y0, x1, y1 = box
    return (math.floor(x0 / cell) * cell, math.floor(y0 / cell) * cell,
            math.ceil(x1 / cell) * cell, math.ceil(y1 / cell) * cell)


def _ca_bundle():
    """QGIS's trusted certificates as a PEM file, for GDAL's own web reads (QGIS's GDAL has none on macOS)."""
    path = os.path.join(_cache_dir(), "ca_bundle.pem")
    if not os.path.exists(path):
        pems = [bytes(c.toPem()) for c in QSslConfiguration.defaultConfiguration().caCertificates()]
        if not pems:
            return ""
        with open(path, "wb") as fh:
            fh.write(b"".join(pems))
    return path


def _mirror_clip(year, box, dest, cell, feedback=None):
    """GHS-POP cut to `box` by reading only the needed window of the Cloud Optimized GeoTIFF mirror, summed to
    1 km when `cell` is 1000. False if the mirror cannot be read, so the caller falls back to the JRC zips."""
    x0, y0, x1, y1 = _snap(box, float(cell))
    sources = []
    for row in range(int((GHSL_Y0 - y1) // GHSL_TILE) + 1, int((GHSL_Y0 - y0) // GHSL_TILE) + 2):
        for col in range(int((x0 - GHSL_X0) // GHSL_TILE) + 1, int((x1 - GHSL_X0) // GHSL_TILE) + 2):
            sources.append("/vsicurl/" + POP_MIRROR.format(year=year, row=row, col=col))
    options = {"CURL_CA_BUNDLE": _ca_bundle(), "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
               "GDAL_HTTP_MAX_RETRY": "4", "GDAL_HTTP_RETRY_DELAY": "3", "GDAL_HTTP_TIMEOUT": "120",
               "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif"}
    before = {k: gdal.GetConfigOption(k) for k in options}
    for k, v in options.items():
        gdal.SetConfigOption(k, v or None)
    tmp = dest + ".100m.tif"
    try:
        if feedback is not None:
            feedback.pushInfo(f"reading GHS-POP {year} from the cloud mirror ({len(sources)} tile(s))")
        readable = [s for s in sources if gdal.Open(s) is not None]
        if not readable:
            return False
        vrt = gdal.BuildVRT(dest + ".vrt", readable)
        done = gdal.Translate(tmp, vrt, projWin=[x0, y1, x1, y0], creationOptions=["COMPRESS=DEFLATE"])
        vrt = None
        if done is None:
            return False
        done = None
    finally:
        for k, v in before.items():
            gdal.SetConfigOption(k, v)
        if os.path.exists(dest + ".vrt"):
            os.remove(dest + ".vrt")
    if cell == "100":
        os.replace(tmp, dest)
        return True
    ds = gdal.Open(tmp)
    arr = ds.ReadAsArray().astype("float64")
    gt, wkt = ds.GetGeoTransform(), ds.GetProjection()
    ds = None
    os.remove(tmp)
    valid = arr >= 0
    arr[~valid] = 0.0
    k = int(cell) // 100
    h, w = arr.shape[0] // k, arr.shape[1] // k
    total = arr[:h * k, :w * k].reshape(h, k, w, k).sum(axis=(1, 3))
    seen = valid[:h * k, :w * k].reshape(h, k, w, k).any(axis=(1, 3))
    total[~seen] = -200.0
    out = gdal.GetDriverByName("GTiff").Create(dest, w, h, 1, gdal.GDT_Float32, options=["COMPRESS=DEFLATE"])
    out.SetGeoTransform((gt[0], gt[1] * k, 0.0, gt[3], 0.0, gt[5] * k))
    out.SetProjection(wkt)
    out.GetRasterBand(1).SetNoDataValue(-200.0)
    out.GetRasterBand(1).WriteArray(total.astype("float32"))
    out = None
    return True


def _ghsl_clip(product, cell, version, year, box, dest, feedback=None):
    """Cut a GHSL R2023A layer to `box` (Mollweide metres). Population comes from the cloud mirror when it
    answers; otherwise the 1,000 km JRC tiles are downloaded once into the cache. Returns (path, source)."""
    if product == "GHS_POP" and _mirror_clip(year, box, dest, cell, feedback):
        return dest, POP_MIRROR_NOTE
    if product == "GHS_POP" and feedback is not None:
        feedback.pushInfo("the cloud mirror did not answer; downloading the JRC tiles instead")
    stem = f"{product}_E{year}_GLOBE_R2023A_54009_{cell}"
    folder = f"{GHSL_ROOT}/{product}_GLOBE_R2023A/{stem}/{version}/tiles"
    x0, y0, x1, y1 = _snap(box, float(cell))
    sources = []
    for row in range(int((GHSL_Y0 - y1) // GHSL_TILE) + 1, int((GHSL_Y0 - y0) // GHSL_TILE) + 2):
        for col in range(int((x0 - GHSL_X0) // GHSL_TILE) + 1, int((x1 - GHSL_X0) // GHSL_TILE) + 2):
            name = f"{stem}_{version.replace('-', '_')}_R{row}_C{col}"
            path = _cached(f"{folder}/{name}.zip", f"{name}.zip", feedback)
            if path:
                sources.append(f"/vsizip/{path}/{name}.tif")
    if not sources:
        raise QgsProcessingException(f"GHSL has no {product} tiles here")
    vrt = gdal.BuildVRT(dest + ".vrt", sources)
    gdal.Translate(dest, vrt, projWin=[x0, y1, x1, y0], creationOptions=["COMPRESS=DEFLATE"])
    vrt = None
    os.remove(dest + ".vrt")
    return dest, f"{folder}/ (JRC download server)"


def _component(mask, seed, eight):
    """Cells of `mask` joined to `seed`, by 4 or 8 neighbours."""
    out = np.zeros_like(mask)
    steps = [(-1, 0), (1, 0), (0, -1), (0, 1)] + ([(-1, -1), (-1, 1), (1, -1), (1, 1)] if eight else [])
    stack = [seed]
    out[seed] = True
    while stack:
        r, c = stack.pop()
        for dr, dc in steps:
            rr, cc = r + dr, c + dc
            if 0 <= rr < mask.shape[0] and 0 <= cc < mask.shape[1] and mask[rr, cc] and not out[rr, cc]:
                out[rr, cc] = True
                stack.append((rr, cc))
    return out


def _cells_to_geometry(cells, gt, wkt) -> QgsGeometry:
    drv = gdal.GetDriverByName("MEM")
    ras = drv.Create("", cells.shape[1], cells.shape[0], 1, gdal.GDT_Byte)
    ras.SetGeoTransform(gt)
    ras.SetProjection(wkt)
    ras.GetRasterBand(1).WriteArray(cells.astype("uint8"))
    vec = ogr.GetDriverByName("Memory").CreateDataSource("cells")
    layer = vec.CreateLayer("cells", osr.SpatialReference(wkt=wkt), ogr.wkbPolygon)
    layer.CreateField(ogr.FieldDefn("v", ogr.OFTInteger))
    band = ras.GetRasterBand(1)
    gdal.Polygonize(band, band, layer, 0)
    parts = [QgsGeometry.fromWkt(f.GetGeometryRef().ExportToWkt()) for f in layer]
    return QgsGeometry.unaryUnion(parts).removeInteriorRings()


def _urban_centre(point_m: QgsPointXY, year, work, feedback=None):
    """The GHSL urban centre (dense 1 km cells, joined by edges) at or next to the point, else the wider urban
    cluster, as a Mollweide polygon. None for a place GHSL counts as rural."""
    reach = 80_000.0
    box = (point_m.x() - reach, point_m.y() - reach, point_m.x() + reach, point_m.y() + reach)
    pop_path = os.path.join(work, "pop_1km.tif")
    if _mirror_clip(year, box, pop_path, "1000", feedback):
        # GHSL's own degree-of-urbanisation rule on 1 km population, so the slow JRC server is not needed.
        ds = gdal.Open(pop_path)
        gt, wkt = ds.GetGeoTransform(), ds.GetProjection()
        pop = np.maximum(ds.ReadAsArray().astype("float64"), 0.0)
        ds = None
        row, col = int((point_m.y() - gt[3]) / gt[5]), int((point_m.x() - gt[0]) / gt[1])
        for density, eight, least, kind in ((1500, False, 50_000, "urban centre"), (300, True, 5_000, "urban cluster")):
            mask = pop >= density
            near = [(abs(r) + abs(c), row + r, col + c) for r in range(-3, 4) for c in range(-3, 4)
                    if 0 <= row + r < mask.shape[0] and 0 <= col + c < mask.shape[1] and mask[row + r, col + c]]
            if near:
                _, r, c = min(near)
                cells = _component(mask, (r, c), eight)
                if pop[cells].sum() >= least:
                    return _cells_to_geometry(cells, gt, wkt), kind
        return None, ""
    path, _ = _ghsl_clip("GHS_SMOD", "1000", "V2-0", year, box, os.path.join(work, "smod.tif"), feedback)
    ds = gdal.Open(path)
    gt, wkt = ds.GetGeoTransform(), ds.GetProjection()
    smod = ds.ReadAsArray()
    row, col = int((point_m.y() - gt[3]) / gt[5]), int((point_m.x() - gt[0]) / gt[1])
    for classes, eight, kind in (((30,), False, "urban centre"), ((21, 22, 23, 30), True, "urban cluster")):
        mask = np.isin(smod, classes)
        near = [(abs(r) + abs(c), row + r, col + c) for r in range(-3, 4) for c in range(-3, 4)
                if 0 <= row + r < mask.shape[0] and 0 <= col + c < mask.shape[1] and mask[row + r, col + c]]
        if near:
            _, r, c = min(near)
            return _cells_to_geometry(_component(mask, (r, c), eight), gt, wkt), kind
    return None, ""


def _boundary_meta(iso3, level, feedback=None):
    for release in ("gbOpen", "gbHumanitarian", "gbAuthoritative"):
        path = _cached(GEOBOUNDARIES.format(release=release, iso3=iso3, level=level),
                       f"geoBoundaries-{release}-{iso3}-ADM{level}.json", feedback)
        if not path:
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                meta = json.load(fh)
        except ValueError:
            os.remove(path)
            continue
        if isinstance(meta, dict) and meta.get("simplifiedGeometryGeoJSON"):
            meta["release"] = release
            return meta
        os.remove(path)
    return None


def _singular(word):
    word = (word or "unit").strip().lower()
    if word.endswith("ies"):
        return word[:-3] + "y"
    return word[:-1] if word.endswith("s") and not word.endswith("ss") else word


def _units_for(iso3, city_m: QgsGeometry, level, ctx, feedback=None):
    """geoBoundaries units with at least half their area inside the built-up city. With `level` 0, the finest
    level that splits the city into 2 to MAX_UNITS units."""
    wgs, moll = QgsCoordinateReferenceSystem("EPSG:4326"), QgsCoordinateReferenceSystem(MOLLWEIDE)
    to_m = QgsCoordinateTransform(wgs, moll, ctx)
    rect = QgsCoordinateTransform(moll, wgs, ctx).transformBoundingBox(city_m.boundingBox())
    best, tried = None, []
    for lvl in ([level] if level else range(1, 6)):
        meta = _boundary_meta(iso3, lvl, feedback)
        if meta is None:
            break
        if not level and int(meta.get("admUnitCount") or 0) > MAX_LEVEL_UNITS:
            break
        path = _cached(meta["simplifiedGeometryGeoJSON"], f"geoBoundaries-{meta['release']}-{iso3}-ADM{lvl}.geojson",
                       feedback)
        layer = QgsVectorLayer(path, f"ADM{lvl}", "ogr")
        kept = []
        for f in layer.getFeatures(QgsFeatureRequest().setFilterRect(rect)):
            g = QgsGeometry(f.geometry())
            g.transform(to_m)
            g = g.makeValid()
            if g.area() > 0 and g.intersection(city_m).area() / g.area() >= UNIT_SHARE:
                kept.append((str(f["shapeName"]), g))
        tried.append(f"ADM{lvl}: {len(kept)}")
        if (2 <= len(kept) <= MAX_UNITS and (best is None or len(kept) > len(best[1]))) or (level and kept):
            best = (lvl, kept, meta)
        if len(kept) > MAX_UNITS:
            break
    return best, tried


def fetch_study_data(place, out_root, *, year=2020, layers=("pop",), detail="100", area_mode=0, level=0,
                     centre_search="", project=None, feedback=None) -> dict:
    """Search a place by name and gather what a study-area plate needs, in out_root/<place>/:
    data/<place>_boundaries.gpkg (units, outline, city centre), data/<place>_<raster>_<year>.tif cut to the area,
    and sources.txt saying where each piece came from. Downloads are cached, so a second run is quick."""
    project = project or QgsProject.instance()
    ctx = project.transformContext()
    say = feedback.pushInfo if feedback is not None else print
    wgs, moll = QgsCoordinateReferenceSystem("EPSG:4326"), QgsCoordinateReferenceSystem(MOLLWEIDE)
    to_m, to_ll = QgsCoordinateTransform(wgs, moll, ctx), QgsCoordinateTransform(moll, wgs, ctx)

    results = _search(place, feedback)
    if not results:
        raise QgsProcessingException(f"OpenStreetMap found nothing called '{place}'")
    hit = _pick_place(results)
    name = hit.get("name") or place.split(",")[0].strip()
    country_code = (hit.get("address") or {}).get("country_code", "")
    iso3 = _iso3(country_code)
    point_ll = QgsPointXY(float(hit["lon"]), float(hit["lat"]))
    point_m = to_m.transform(point_ll)
    say(f"found {hit.get('display_name')} ({hit.get('addresstype')}, {iso3 or country_code})")

    folder = os.path.join(out_root, _slug(name))
    data_dir, maps_dir = os.path.join(folder, "data"), os.path.join(folder, "maps")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(maps_dir, exist_ok=True)
    work = tempfile.mkdtemp(prefix="study_fetch_")
    notes = []

    city_m, kind = _urban_centre(point_m, min(GHSL_YEARS, key=lambda y: abs(y - year)), work, feedback)
    shutil.rmtree(work, ignore_errors=True)
    osm = None
    if hit.get("geojson", {}).get("type") in ("Polygon", "MultiPolygon"):
        osm = QgsGeometry.fromWkt(ogr.CreateGeometryFromJson(json.dumps(hit["geojson"])).ExportToWkt())
        osm.transform(to_m)
        osm = osm.makeValid()
    if city_m is None:
        city_m = osm if osm is not None else QgsGeometry.fromPointXY(point_m).buffer(5000.0, 32)
        kind = "OpenStreetMap boundary" if osm is not None else "5 km circle"
    say(f"built-up city: GHSL {kind}, {city_m.area() / 1e6:,.0f} km2")

    units, unit_word, level_used = [], "", None
    if area_mode == 1:
        units = [(name, city_m)]
        notes.append(f"Study area: the GHSL {kind} around {name} in {year}, traced from GHS-SMOD 1 km cells.")
    elif area_mode == 2 and osm is not None:
        units = [(name, osm)]
        notes.append(f"Study area: the OpenStreetMap boundary of {name} (osm {hit.get('osm_type')} "
                     f"{hit.get('osm_id')}).")
    else:
        best, tried = _units_for(iso3, city_m, level, ctx, feedback) if iso3 else (None, [])
        if best is not None:
            level_used, units, meta = best
            unit_word = _singular(meta.get("boundaryCanonical") or meta.get("boundaryType"))
            notes.append(f"Study area: the {len(units)} geoBoundaries ADM{level_used} units "
                         f"({meta.get('boundaryCanonical') or 'units'}) with at least half their area inside the "
                         f"GHSL {kind} around {name}. Levels tried: {', '.join(tried)}. Release {meta['release']}, "
                         f"{meta.get('boundaryYearRepresented', '')}, source {meta.get('boundarySource', '')}, "
                         f"licence {meta.get('boundaryLicense', '')}.")
        else:
            units = [(name, city_m)]
            notes.append(f"Study area: no administrative level split {name} cleanly (levels tried: "
                         f"{', '.join(tried) or 'none'}), so the GHSL {kind} outline is used.")
    say(f"study area: {len(units)} unit(s)" + (f" at ADM{level_used}" if level_used else ""))

    store = os.path.join(data_dir, f"{_slug(name)}_boundaries.gpkg")
    if os.path.exists(store):
        os.remove(store)
    unit_layer = QgsVectorLayer("MultiPolygon?crs=EPSG:4326", f"{name} units", "memory")
    unit_layer.dataProvider().addAttributes([QgsField("name", QVariant.String)])
    unit_layer.updateFields()
    feats = []
    for unit_name, g in units:
        g = QgsGeometry(g)
        g.transform(to_ll)
        g.convertToMultiType()
        f = QgsFeature(unit_layer.fields())
        f.setGeometry(g)
        f.setAttributes([unit_name])
        feats.append(f)
    unit_layer.dataProvider().addFeatures(feats)
    unit_layer = _save(unit_layer, store, "units", ctx)
    city_layer = QgsVectorLayer("MultiPolygon?crs=EPSG:4326", f"{name} built-up city", "memory")
    g = QgsGeometry(city_m)
    g.transform(to_ll)
    f = QgsFeature()
    f.setGeometry(g)
    city_layer.dataProvider().addFeatures([f])
    _save(city_layer, store, "built_up_city", ctx)

    centre_ll, centre_label, centre_desc = point_ll, "City centre", f"where OpenStreetMap places the centre of {name}"
    if centre_search:
        box = to_ll.transformBoundingBox(QgsGeometry.unaryUnion([g for _, g in units]).boundingBox())
        extra = (f"&countrycodes={country_code}&bounded=1&viewbox={box.xMinimum()},{box.yMaximum()},"
                 f"{box.xMaximum()},{box.yMinimum()}")
        found = _search(centre_search, feedback, extra) or _search(f"{centre_search}, {name}", feedback)
        if found:
            pick = found[0]
            centre_ll = QgsPointXY(float(pick["lon"]), float(pick["lat"]))
            centre_label = centre_search.split(",")[0].strip()
            centre_desc = ", ".join(pick.get("display_name", centre_label).split(", ")[:2])
            say(f"centre: {pick.get('display_name')}")
        else:
            say(f"OpenStreetMap found no '{centre_search}' inside {name}; the star stays on the city centre")
    centre_layer = QgsVectorLayer("Point?crs=EPSG:4326", f"{name} centre", "memory")
    centre_layer.dataProvider().addAttributes([QgsField("name", QVariant.String)])
    centre_layer.updateFields()
    f = QgsFeature(centre_layer.fields())
    f.setGeometry(QgsGeometry.fromPointXY(centre_ll))
    f.setAttributes([centre_label])
    centre_layer.dataProvider().addFeatures([f])
    _save(centre_layer, store, "centre", ctx)
    notes.append(f"Centre: {centre_desc} ({centre_ll.y():.5f}, {centre_ll.x():.5f}), from OpenStreetMap "
                 f"Nominatim.")

    area_m = QgsGeometry.unaryUnion([g for _, g in units]).boundingBox()
    area_m.grow(3000.0 if detail == "100" else 5000.0)
    rasters = []
    for key, product, cell, version, label, counts, legend in DOWNLOADS:
        if key not in layers:
            continue
        cell = detail or cell
        say(f"cutting {label} {year} to the area")
        dest = os.path.join(data_dir, f"{_slug(name)}_{_slug(label)}_{year}" + ("_1km" if cell == "1000" else "")
                            + ".tif")
        _, source = _ghsl_clip(product, cell, version, year, (area_m.xMinimum(), area_m.yMinimum(),
                                                              area_m.xMaximum(), area_m.yMaximum()), dest, feedback)
        if not counts:
            ds = gdal.Open(dest)
            band = ds.GetRasterBand(1)
            arr = band.ReadAsArray().astype("float32")
            nodata = band.GetNoDataValue()
            if nodata is not None:
                arr[arr == nodata] = np.nan
            arr /= float(cell) * float(cell) / 100.0
            gt, wkt = ds.GetGeoTransform(), ds.GetProjection()
            ds = None
            out = gdal.GetDriverByName("GTiff").Create(dest, arr.shape[1], arr.shape[0], 1, gdal.GDT_Float32,
                                                       options=["COMPRESS=DEFLATE"])
            out.SetGeoTransform(gt)
            out.SetProjection(wkt)
            out.GetRasterBand(1).SetNoDataValue(float("nan"))
            out.GetRasterBand(1).WriteArray(arr)
            out = None
        rasters.append({"path": dest, "name": f"{label} {year}", "counts": counts,
                        "legend": legend.format(year=year)})
        notes.append(f"{label} {year}: European Commission JRC, GHSL R2023A, {cell} m World Mollweide grid "
                     f"(CC BY 4.0), read from {source}"
                     + ("" if counts else "; built-up square metres turned into a percentage of each cell")
                     + ("; 100 m cells summed to 1 km" if counts and cell == "1000" else "") + ".")

    with open(os.path.join(folder, "sources.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"Study area data for {name}\n")
        fh.write(f"Search: '{place}' -> {hit.get('display_name')}\n")
        fh.write(f"Gathered {datetime.date.today().isoformat()} by study_area_plate.py\n\n")
        fh.write("\n\n".join(notes))
        fh.write("\n\nPlace search and centre: OpenStreetMap contributors via Nominatim (ODbL).\n"
                 "Built-up city: the GHSL degree-of-urbanisation rule (1 km cells of at least 1,500 people per "
                 "km2, joined by edges, 50,000 people or more) applied to GHS-POP; GHS-SMOD R2023A only when the "
                 "population mirror cannot be reached (CC BY 4.0).\n"
                 "Boundaries: geoBoundaries, Runfola et al. 2020, PLoS ONE 15(4): e0231866.\n"
                 "Base map: Esri World Light Gray Canvas.\n")
    say(f"data and sources in {folder}")
    return {"name": name, "iso3": iso3, "units": unit_layer, "unit_name": unit_word, "centre": centre_ll,
            "centre_label": centre_label, "centre_desc": centre_desc, "rasters": rasters, "folder": folder,
            "maps": maps_dir}


class StudyAreaPlate(QgsProcessingAlgorithm):
    PLACE, DOWNLOAD, YEAR, AREA_FROM, UNIT_LEVEL, CENTRE_SEARCH = (
        "PLACE", "DOWNLOAD", "YEAR", "AREA_FROM", "UNIT_LEVEL", "CENTRE_SEARCH")
    DETAIL = "DETAIL"
    AOI, NAME_FIELD, UNIT_NAME, TITLE = "AOI", "NAME_FIELD", "UNIT_NAME", "TITLE"
    RASTERS, RASTER_NAMES, COUNTS, LEGEND_TITLE, CLASSES, BIVARIATE = (
        "RASTERS", "RASTER_NAMES", "COUNTS", "LEGEND_TITLE", "CLASSES", "BIVARIATE")
    COUNTRY, CENTRE, CENTRE_LABEL, CENTRE_DESC = "COUNTRY", "CENTRE", "CENTRE_LABEL", "CENTRE_DESC"
    INSET, CALLOUTS, CREDIT, PIXEL, OUT_DIR = "INSET", "CALLOUTS", "CREDIT", "PIXEL", "OUT_DIR"
    BASEMAP = "BASEMAP"

    def __init__(self):
        super().__init__()
        self._country_list = []

    def name(self):
        return "study_area_plate"

    def displayName(self):
        return "Study area plate"

    def group(self):
        return "Wisdom maps"

    def groupId(self):
        return "wisdom_maps"

    def shortHelpString(self):
        return ("A3 landscape study-area plate for any place on Earth.\n\n"
                "The quick way: type a place (e.g. 'Mumbai' or 'Kano, Nigeria'). The script finds it on "
                "OpenStreetMap, traces the built-up city from GHSL, picks the districts that make it up from "
                "geoBoundaries, downloads GHSL population (and built-up land if asked) for the chosen year, and "
                "files everything in <output folder>/<place>/ with a sources.txt. Optionally name a landmark for "
                "the centre star (e.g. 'Chhatrapati Shivaji Terminus').\n\n"
                "Or bring your own: an area-of-interest layer, any rasters and a country. Each raster gets its own "
                "plate in natural-break classes; tick 'bivariate' to compare two on one plate.\n\n"
                "Every plate has a title, north arrow, scale, legends, a footnote, a country locator and a zoomed "
                "inset, on Esri's light-grey base unless that is switched off. The layout opens in the designer, "
                "and PNG and PDF are written to the output folder.")

    def flags(self):
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading

    def createInstance(self):
        return StudyAreaPlate()

    def initAlgorithm(self, config=None):
        self._country_list = _countries()
        self.addParameter(QgsProcessingParameterString(
            self.PLACE, "Place to search for (fetches everything; leave empty to use your own layers)",
            optional=True))
        self.addParameter(QgsProcessingParameterEnum(
            self.DOWNLOAD, "Rasters to download for the place",
            options=["Population (GHS-POP)", "Built-up share of the land (GHS-BUILT-S)"], allowMultiple=True,
            defaultValue=[0], optional=True))
        self.addParameter(QgsProcessingParameterEnum(
            self.YEAR, "Year", options=[str(y) for y in GHSL_YEARS], defaultValue=GHSL_YEARS.index(2020)))
        self.addParameter(QgsProcessingParameterEnum(
            self.DETAIL, "Raster detail", options=list(DETAILS), defaultValue=0))
        self.addParameter(QgsProcessingParameterEnum(
            self.AREA_FROM, "Study area for the place", options=list(AREA_MODES), defaultValue=0))
        self.addParameter(QgsProcessingParameterEnum(
            self.UNIT_LEVEL, "Administrative level of the units",
            options=["Automatic"] + [f"ADM{n}" for n in range(1, 6)], defaultValue=0))
        self.addParameter(QgsProcessingParameterString(
            self.CENTRE_SEARCH, "Landmark for the centre star (searched inside the place; optional)", optional=True))
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.AOI, "Or your own area of interest (polygons)", [QgsProcessing.TypeVectorPolygon], optional=True))
        self.addParameter(QgsProcessingParameterString(
            self.TITLE, "Plate title (default: the place name)", optional=True))
        self.addParameter(QgsProcessingParameterMultipleLayers(
            self.RASTERS, "Your own raster(s) of interest", QgsProcessing.TypeRaster, optional=True))
        self.addParameter(QgsProcessingParameterEnum(
            self.COUNTRY, "Country of interest (locator)",
            options=["Detect from the area of interest"] + [n for n, _ in self._country_list], defaultValue=0))
        self.addParameter(QgsProcessingParameterField(
            self.NAME_FIELD, "Field naming the units inside your area (optional)",
            parentLayerParameterName=self.AOI, optional=True))
        self.addParameter(QgsProcessingParameterString(
            self.UNIT_NAME, "What one unit is called (district, ward, LGA...)", optional=True))
        self.addParameter(QgsProcessingParameterString(
            self.RASTER_NAMES, "Names for your rasters, comma separated (default: layer names)", optional=True))
        self.addParameter(QgsProcessingParameterString(
            self.LEGEND_TITLE, "Legend title for your rasters (e.g. 'People per hectare, 2020')", optional=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.COUNTS, "Your rasters hold counts per cell (population etc.): show per hectare",
            defaultValue=False))
        self.addParameter(QgsProcessingParameterNumber(
            self.CLASSES, "Number of classes (3 to 7)", QgsProcessingParameterNumber.Integer, defaultValue=5,
            minValue=3, maxValue=7))
        self.addParameter(QgsProcessingParameterBoolean(
            self.BIVARIATE, "Compare your first two rasters on one bivariate plate", defaultValue=False))
        self.addParameter(QgsProcessingParameterPoint(self.CENTRE, "Centre point (optional)", optional=True))
        self.addParameter(QgsProcessingParameterString(self.CENTRE_LABEL, "Centre name on the map", optional=True))
        self.addParameter(QgsProcessingParameterString(
            self.CENTRE_DESC, "Centre in the footnote (e.g. 'Mapo Hill, the old council hall')", optional=True))
        self.addParameter(QgsProcessingParameterBoolean(self.INSET, "Add a zoomed inset", defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.BASEMAP, "Esri light-grey basemap (needs internet)", defaultValue=True))
        self.addParameter(QgsProcessingParameterString(
            self.CALLOUTS, "Units to label with a leader line, comma separated", optional=True))
        self.addParameter(QgsProcessingParameterString(self.CREDIT, "Credit", defaultValue="©Wisdom Akpabio"))
        self.addParameter(QgsProcessingParameterNumber(
            self.PIXEL, "Grid cell size in metres (0 = the raster's own)", QgsProcessingParameterNumber.Double,
            defaultValue=0.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterFolderDestination(
            self.OUT_DIR, "Output folder (default for a searched place: Documents/Study area plates)",
            optional=True))

    def processAlgorithm(self, parameters, context, feedback):
        project = context.project() or QgsProject.instance()
        place = self.parameterAsString(parameters, self.PLACE, context).strip()
        aoi = self.parameterAsVectorLayer(parameters, self.AOI, context)
        if not place and aoi is None:
            raise QgsProcessingException("type a place to search for, or give an area-of-interest layer")
        out_dir = self.parameterAsString(parameters, self.OUT_DIR, context)
        if out_dir in ("TEMPORARY_OUTPUT",):
            out_dir = ""

        layers = self.parameterAsLayerList(parameters, self.RASTERS, context) or []
        given = [n.strip() for n in self.parameterAsString(parameters, self.RASTER_NAMES, context).split(",")]
        own = [(lyr.source(), given[i] if i < len(given) and given[i] else lyr.name()) for i, lyr in enumerate(layers)]
        own_counts = self.parameterAsBool(parameters, self.COUNTS, context)
        own_legend = self.parameterAsString(parameters, self.LEGEND_TITLE, context)
        bivariate = self.parameterAsBool(parameters, self.BIVARIATE, context) and len(own) >= 2
        runs = ([(own[:2], own_counts, own_legend, True)] if bivariate
                else [([r], own_counts, own_legend, False) for r in own])

        pick = self.parameterAsEnum(parameters, self.COUNTRY, context)
        if not self._country_list:
            self._country_list = _countries()
        iso3 = self._country_list[pick - 1][1] if pick > 0 and pick - 1 < len(self._country_list) else ""
        centre, centre_crs = None, None
        if parameters.get(self.CENTRE):
            centre = self.parameterAsPoint(parameters, self.CENTRE, context)
            centre_crs = self.parameterAsPointCrs(parameters, self.CENTRE, context)
        title = self.parameterAsString(parameters, self.TITLE, context).strip()
        name_field = self.parameterAsString(parameters, self.NAME_FIELD, context)
        unit_name = self.parameterAsString(parameters, self.UNIT_NAME, context)
        centre_label = self.parameterAsString(parameters, self.CENTRE_LABEL, context)
        centre_desc = self.parameterAsString(parameters, self.CENTRE_DESC, context)
        credit = self.parameterAsString(parameters, self.CREDIT, context)

        if place:
            root = out_dir or os.path.join(os.path.expanduser("~"), "Documents", "Study area plates")
            picked = self.parameterAsEnums(parameters, self.DOWNLOAD, context)
            fetched = fetch_study_data(
                place, root, year=GHSL_YEARS[self.parameterAsEnum(parameters, self.YEAR, context)],
                layers=[("pop", "built")[i] for i in picked],
                detail=("100", "1000")[self.parameterAsEnum(parameters, self.DETAIL, context)],
                area_mode=self.parameterAsEnum(parameters, self.AREA_FROM, context),
                level=self.parameterAsEnum(parameters, self.UNIT_LEVEL, context),
                centre_search=self.parameterAsString(parameters, self.CENTRE_SEARCH, context).strip(),
                project=project, feedback=feedback)
            aoi, name_field = fetched["units"], "name"
            title = title or fetched["name"]
            iso3 = iso3 or fetched["iso3"]
            unit_name = unit_name or fetched["unit_name"]
            out_dir = fetched["maps"]
            if centre is None:
                centre, centre_crs = fetched["centre"], QgsCoordinateReferenceSystem("EPSG:4326")
                centre_label = centre_label or fetched["centre_label"]
                centre_desc = centre_desc or fetched["centre_desc"]
            runs = [([(r["path"], r["name"])], r["counts"], r["legend"], False) for r in fetched["rasters"]] + runs
            credit = "\n".join(t for t in (credit, "Data: OpenStreetMap, geoBoundaries, GHSL") if t)
        title = title or (aoi.name() if aoi is not None else "Study area")
        runs = runs or [([], False, "", False)]

        common = dict(
            country=iso3, name_field=name_field, unit_name=unit_name, centre=centre, centre_crs=centre_crs,
            centre_label=centre_label, centre_desc=centre_desc,
            classes=self.parameterAsInt(parameters, self.CLASSES, context),
            inset=self.parameterAsBool(parameters, self.INSET, context),
            callouts=[c.strip() for c in self.parameterAsString(parameters, self.CALLOUTS, context).split(",")
                      if c.strip()],
            credit=credit, out_dir=out_dir, pixel=self.parameterAsDouble(parameters, self.PIXEL, context),
            basemap=self.parameterAsBool(parameters, self.BASEMAP, context), project=project, feedback=feedback)
        made = []
        for i, (rasters, counts, legend, two) in enumerate(runs):
            if feedback.isCanceled():
                break
            feedback.setProgress(100 * i / len(runs))
            made.append(build_plate(aoi, title, rasters=rasters, counts=counts, legend_title=legend, bivariate=two,
                                    **common))
        try:
            from qgis.utils import iface
            if iface is not None and made:
                iface.openLayoutDesigner(project.layoutManager().layoutByName(made[0]["layout"]))
        except Exception:
            pass
        return {self.OUT_DIR: out_dir, "LAYOUTS": [m["layout"] for m in made]}


