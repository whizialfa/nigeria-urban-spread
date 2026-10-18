"""Study-area plate and five city plates. Run with QGIS Python: env -u PYTHONPATH python3.9 build_plates.py [slug ...]"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLATES = ROOT / "data" / "processed" / "plates"
MAPS = ROOT / "maps"
STYLES = ROOT / "qgis" / "styles"
NORTH_SVG = STYLES / "north_arrow_white.svg"

os.environ.setdefault("QGIS_PREFIX_PATH", "/Applications/QGIS.app/Contents/MacOS")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (  # noqa: E402
    Qgis,
    QgsApplication,
    QgsCallout,
    QgsCategorizedSymbolRenderer,
    QgsColorRampShader,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeatureRequest,
    QgsFillSymbol,
    QgsGeometry,
    QgsLabelLineSettings,
    QgsLabelObstacleSettings,
    QgsLayoutExporter,
    QgsLayoutItem,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLabelingEngineSettings,
    QgsLayoutItemMap,
    QgsLayoutItemMapOverview,
    QgsLayoutItemPicture,
    QgsLayoutItemPolyline,
    QgsLayoutItemScaleBar,
    QgsLayoutItemShape,
    QgsLayoutMeasurement,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsLegendRenderer,
    QgsLegendStyle,
    QgsLineSymbol,
    QgsMapBoxGlStyleConverter,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsPalettedRasterRenderer,
    QgsPointXY,
    QgsPrintLayout,
    QgsProperty,
    QgsProject,
    QgsRasterLayer,
    QgsRasterShader,
    QgsRectangle,
    QgsRendererCategory,
    QgsScaleBarSettings,
    QgsSimpleLineCallout,
    QgsSingleBandPseudoColorRenderer,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
    QgsVectorTileLayer,
)
from qgis.PyQt.QtCore import QPointF, Qt  # noqa: E402
from qgis.PyQt.QtGui import QColor, QFont, QPolygonF  # noqa: E402

MM = QgsUnitTypes.LayoutMillimeters
FRAME_W, FRAME_H = 404.0, 281.0
TITLE_H = 32.0
NOTE_H = 40.0
NOTE_W = 214.0
NOTE_BOTTOM = 8.0
FURNITURE_GAP = 3.0
BOTTOM_CLEAR = 6.0
EDGE = "28,25,22,255"
SLATE = "46,64,87"
SAND = "201,166,107"
FILL_ALPHA = 204
STATE_LINE = "88,84,78,230"
LGA_LINE = "150,146,140,150"
LGA_EDGE = "120,84,60,235"
# Under this size (or named in CALLOUT_LGAS) the name sits outside with a leader, so metro cores stay readable.
SMALL_LGA_KM2 = 40

CHANGE_CLASSES = (
    (-25, "33,102,172", "\u2264 \u221225"),
    (-5, "146,197,222", "\u221225 to \u22125"),
    (5, "236,232,222", "\u22125 to 5"),
    (25, "254,232,200", "5 to 25"),
    (50, "253,187,132", "25 to 50"),
    (100, "252,141,89", "50 to 100"),
    (200, "215,48,31", "100 to 200"),
    (1e9, "127,0,0", "> 200"),
)

CITIES = {
    "lagos": {"name": "Lagos", "utm": "EPSG:32631", "centre": "Iga Idunganran on Lagos Island"},
    "kano": {"name": "Kano", "utm": "EPSG:32632", "centre": "Gidan Rumfa, the Emir's palace"},
    "ibadan": {"name": "Ibadan", "utm": "EPSG:32631", "centre": "Mapo Hill"},
    "port_harcourt": {"name": "Port Harcourt", "utm": "EPSG:32632", "centre": "the old Township waterfront"},
    "abuja": {"name": "Abuja", "utm": "EPSG:32632", "centre": "the Three Arms Zone, the city's planned origin"},
}

_KEEP = []


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


def _vector(name: str, title: str) -> QgsVectorLayer:
    lyr = QgsVectorLayer(f"{(PLATES / f'{name}.gpkg').as_posix()}|layername={name}", title, "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"could not read {name}")
    return lyr


def _fill(color: str, outline: str = "0,0,0,0", width: str = "0") -> QgsFillSymbol:
    return QgsFillSymbol.createSimple({"color": color, "outline_color": outline, "outline_width": width,
                                       "outline_width_unit": "MM", "outline_style": "solid" if width != "0" else "no"})


def _line(color: str, width: str, style: str = "solid") -> QgsLineSymbol:
    return QgsLineSymbol.createSimple({"line_color": color, "line_width": width, "line_width_unit": "MM",
                                       "line_style": style, "capstyle": "round"})


def _text(size: float, bold: bool = True, halo: float = 1.5) -> QgsTextFormat:
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


def _labels(layer: QgsVectorLayer, field: str, size: float, priority: int = 5, *, polygon: bool = False) -> None:
    s = QgsPalLayerSettings()
    s.fieldName = f"replace(\"{field}\", ' ', char(160))"
    s.isExpression = True
    s.placement = Qgis.LabelPlacement.Horizontal if polygon else Qgis.LabelPlacement.OverPoint
    s.centroidInside = True
    s.priority = priority
    s.obstacle = True
    s.setUnplacedVisibility(Qgis.UnplacedLabelVisibility.NeverShow)
    s.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.PreventOverlap)
    s.setFormat(_text(size))
    layer.setLabeling(QgsVectorLayerSimpleLabeling(s))
    layer.setLabelsEnabled(True)


def _invisible_points(layer: QgsVectorLayer) -> None:
    layer.renderer().setSymbol(QgsMarkerSymbol.createSimple({"name": "circle", "color": "0,0,0,0",
                                                             "outline_color": "0,0,0,0", "size": "0.1"}))


def _grey_base() -> QgsRasterLayer:
    return QgsRasterLayer("type=xyz&url=https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/"
                          "World_Light_Gray_Base/MapServer/tile/%7Bz%7D/%7By%7D/%7Bx%7D&zmax=16&zmin=0&crs=EPSG3857",
                          "Grey base", "wms")


def _positron() -> QgsVectorTileLayer:
    converter = QgsMapBoxGlStyleConverter()
    converter.convert((STYLES / "positron.json").read_text())
    layer = QgsVectorTileLayer("type=xyz&url=https://tiles-a.basemaps.cartocdn.com/vectortiles/carto.streets/v1/"
                               "{z}/{x}/{y}.mvt&zmin=0&zmax=14", "Positron")
    if not layer.isValid() or converter.renderer() is None:
        raise RuntimeError("Positron failed")
    layer.setRenderer(converter.renderer())
    layer.setLabelsEnabled(False)
    _KEEP.append(converter)
    return layer


def _union(layer: QgsVectorLayer) -> QgsGeometry:
    merged = None
    for feat in layer.getFeatures():
        g = QgsGeometry(feat.geometry())
        merged = g if merged is None else merged.combine(g)
    return merged.makeValid()


def _rects_overlap(a, b):
    return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + b[3] and a[1] + a[3] > b[1]


def _item_box(item, origin=8.0):
    tl = item.positionAtReferencePoint(QgsLayoutItem.UpperLeft)
    size = item.sizeWithUnits()
    return float(tl.x()) - origin, float(tl.y()) - origin, float(size.width()), float(size.height())


def _grow(box, pad):
    return box[0] - pad, box[1] - pad, box[2] + 2 * pad, box[3] + 2 * pad


def _inside_frame(cx, cy, w_mm, h_mm, city: QgsRectangle, shape: QgsGeometry) -> bool:
    cw, ch = max(city.width(), 1.0), max(city.height(), 1.0)
    x0 = city.xMinimum() + (3.0 - cx) / w_mm * cw
    x1 = city.xMinimum() + (FRAME_W - 3.0 - cx) / w_mm * cw
    y1 = city.yMaximum() - (3.0 - cy) / h_mm * ch
    y0 = city.yMaximum() - (FRAME_H - 3.0 - cy) / h_mm * ch
    return QgsGeometry.fromRect(QgsRectangle(x0, y0, x1, y1)).contains(shape)


def _framed_extent(city: QgsRectangle, boxes, shape: QgsGeometry) -> QgsRectangle:
    """Largest city footprint whose outline clears the furniture, kept as close to the middle as it allows."""
    cw, ch = max(city.width(), 1.0), max(city.height(), 1.0)
    padded = [_grow(b, FURNITURE_GAP) for b in boxes]
    shape = shape.simplify(max(cw, ch) / 400.0) or shape

    def hits(cx, cy, w_mm, h_mm, box):
        if not _rects_overlap((cx, cy, w_mm, h_mm), box):
            return False
        bx, by, bw, bh = box
        x0 = city.xMinimum() + (bx - cx) / w_mm * cw
        x1 = city.xMinimum() + (bx + bw - cx) / w_mm * cw
        y1 = city.yMaximum() - (by - cy) / h_mm * ch
        y0 = city.yMaximum() - (by + bh - cy) / h_mm * ch
        return shape.intersects(QgsGeometry.fromRect(QgsRectangle(x0, y0, x1, y1)))

    def place(w_mm, nx=13, ny=11):
        h_mm = w_mm * ch / cw
        x0, x1 = min(3.0, FRAME_W - 3.0 - w_mm), max(3.0, FRAME_W - 3.0 - w_mm)
        y0, y1 = min(3.0, FRAME_H - 3.0 - h_mm), max(3.0, FRAME_H - 3.0 - h_mm)
        if w_mm > 1.4 * FRAME_W or h_mm > 1.4 * FRAME_H:
            return None
        tx = 0.5 * (FRAME_W - w_mm)
        ty = 0.5 * (FRAME_H - h_mm)
        best, best_d = None, 1e18
        for i in range(nx):
            cx = x0 + (x1 - x0) * i / (nx - 1)
            for j in range(ny):
                cy = y0 + (y1 - y0) * j / (ny - 1)
                if any(hits(cx, cy, w_mm, h_mm, b) for b in padded) or not _inside_frame(cx, cy, w_mm, h_mm, city, shape):
                    continue
                d = (cx - tx) ** 2 + (cy - ty) ** 2
                if d < best_d:
                    best, best_d = (cx, cy, w_mm, h_mm), d
        return best

    lo, hi = 40.0, 1.4 * min(FRAME_W, FRAME_H * cw / ch)
    best = place(lo)
    for _ in range(28):
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


def _legend(layout, map_item, project, title, entries, width, height=None):
    """Snug legend: even bar spacing, box sized to painted content — no empty pad inside the frame."""
    legend = QgsLayoutItemLegend(layout)
    legend.setLinkedMap(map_item)
    legend.setTitle(title)
    legend.setTitleAlignment(Qt.AlignLeft)
    legend.setStyleFont(QgsLegendStyle.Title, QFont("Arial", 13, QFont.Bold))
    legend.setStyleFont(QgsLegendStyle.SymbolLabel, QFont("Arial", 12))
    legend.setFontColor(QColor(0, 0, 0))
    legend.setSymbolWidth(7.0)
    legend.setSymbolHeight(4.2)
    legend.setBoxSpace(2.2)
    legend.setColumnSpace(2.5)
    legend.setLineSpacing(0.7)
    legend.setStyleMargin(QgsLegendStyle.Title, QgsLegendStyle.Bottom, 1.4)
    legend.setStyleMargin(QgsLegendStyle.Symbol, QgsLegendStyle.Top, 0.25)
    legend.setStyleMargin(QgsLegendStyle.Symbol, QgsLegendStyle.Bottom, 0.25)
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
    for kind, label, symbol in entries:
        lyr = QgsVectorLayer(f"{kind}?crs=EPSG:4326", label, "memory")
        lyr.renderer().setSymbol(symbol)
        project.addMapLayer(lyr, False)
        node = root.addLayer(lyr)
        QgsLegendRenderer.setNodeLegendStyle(node, QgsLegendStyle.Hidden)
    legend.setZValue(20)
    layout.addLayoutItem(legend)
    # QGIS adjustBoxSize will not shrink a tall box and will not grow a short one reliably.
    # Size from the class stack only: title block + one row per entry + equal insets.
    # Calibrated against painted plates so the last entry sits on the bottom inset, not in air.
    pad = float(legend.boxSpace())
    sym = float(legend.symbolHeight())
    title_block = 4.8
    # Tight row; box ends at last entry + boxSpace only (no air under the star).
    row = sym + 0.40
    stack_h = 2.0 * pad + title_block + len(entries) * row
    h = height if height is not None else stack_h
    # Longest labels are ~"Intermediate zone edge" / "Local government area"; 62 mm is snug.
    w = min(width, 62.0)
    legend.setResizeToContents(False)
    legend.setReferencePoint(QgsLayoutItem.LowerLeft)
    legend.attemptResize(QgsLayoutSize(w, h, MM))
    legend.attemptMove(QgsLayoutPoint(14.0, 283.0, MM))
    print(f"    legend {w:.1f}×{h:.1f} mm ({len(entries)} entries, row {row:.2f})", flush=True)
    return legend


def _zone_curve_labels(layer: QgsVectorLayer) -> None:
    """Distance labels curved along each zone ring, e.g. '7.5 km'."""
    s = QgsPalLayerSettings()
    # Longer text so the bend around the ring is visible (a short "7.5 km" looks flat on a large radius).
    s.fieldName = (
        "CASE WHEN \"zone\" = 'central' THEN format('Central zone · %1 km', round(\"km\", 1)) "
        "WHEN \"zone\" = 'intermediate' THEN format('Intermediate · %1 km', round(\"km\", 1)) "
        "ELSE format('Distant · %1 km', round(\"km\", 1)) END")
    s.isExpression = True
    s.placement = Qgis.LabelPlacement.Curved
    s.maxCurvedCharAngleIn = 35
    s.maxCurvedCharAngleOut = -35
    line = QgsLabelLineSettings()
    # Above the ring so the dashed line does not cut through the letters.
    line.setPlacementFlags(Qgis.LabelLinePlacementFlag.AboveLine)
    line.setOverrunDistance(6.0)
    line.setOverrunDistanceUnit(QgsUnitTypes.RenderMillimeters)
    line.setLineAnchorPercent(0.18)
    s.setLineSettings(line)
    s.dist = 1.8
    s.distUnits = QgsUnitTypes.RenderMillimeters
    s.priority = 6
    s.obstacle = True
    s.obstacleSettings().setFactor(1.2)
    s.setUnplacedVisibility(Qgis.UnplacedLabelVisibility.NeverShow)
    s.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.PreventOverlap)
    fmt = _text(9.5, bold=True, halo=1.8)
    fmt.setFont(QFont("Helvetica", 9, QFont.Bold))
    s.setFormat(fmt)
    s.dataDefinedProperties().setProperty(
        QgsPalLayerSettings.Color,
        QgsProperty.fromExpression(
            "CASE WHEN \"zone\" = 'central' THEN color_rgb(0,90,50) "
            "WHEN \"zone\" = 'intermediate' THEN color_rgb(35,139,69) "
            "ELSE color_rgb(116,196,118) END"))
    s.dataDefinedProperties().setProperty(
        QgsPalLayerSettings.FontLetterSpacing,
        QgsProperty.fromValue(1.2))
    layer.setLabeling(QgsVectorLayerSimpleLabeling(s))
    layer.setLabelsEnabled(True)


def _zones_for_plate(slug: str):
    """City zone rings as a densified memory layer so distance labels can curve."""
    src = _vector("zone_circles_lga", "Zones")
    src.setSubsetString(f"\"slug\" = '{slug}'")
    mem = QgsVectorLayer(f"LineString?crs={src.crs().authid()}", "Zones", "memory")
    dp = mem.dataProvider()
    dp.addAttributes(src.fields())
    mem.updateFields()
    feats = []
    for feat in src.getFeatures():
        f = feat
        geom = feat.geometry()
        if geom and not geom.isEmpty():
            # About one vertex every 80 m so curved labels can bend.
            f.setGeometry(geom.densifyByDistance(0.0007))
        feats.append(f)
    dp.addFeatures(feats)
    mem.updateExtents()
    return mem


def _furniture(layout, map_item, project, *, title, caption, legend_title, entries, legend_w, credit_text,
               locator=None, legend_h=None):
    title_w = 128.0
    title_panel = _white_box(layout, 8, 8, title_w, TITLE_H)
    label = QgsLayoutItemLabel(layout)
    label.setText(title)
    label.setFont(QFont("Arial", 15, QFont.Bold))
    label.setHAlign(Qt.AlignHCenter)
    label.setVAlign(Qt.AlignVCenter)
    label.setMargin(2.0)
    label.setZValue(21)
    _place(layout, label, 8, 8, title_w, TITLE_H)

    north = QgsLayoutItemPicture(layout)
    north.setMode(QgsLayoutItemPicture.FormatSVG)
    north.setPicturePath(str(NORTH_SVG))
    north.setLinkedMap(map_item)
    north.setNorthMode(QgsLayoutItemPicture.GridNorth)
    north.setFrameEnabled(False)
    north.setBackgroundEnabled(False)
    north.setZValue(24)
    _place(layout, north, 380, 10, 26, 32)

    legend = _legend(layout, map_item, project, legend_title, entries, legend_w, legend_h)

    scale = QgsLayoutItemScaleBar(layout)
    scale.setLinkedMap(map_item)
    scale.setStyle("Line Ticks Up")
    scale.setUnits(QgsUnitTypes.DistanceKilometers)
    scale.setSegmentSizeMode(QgsScaleBarSettings.SegmentSizeFitWidth)
    scale.setMinimumBarWidth(40)
    scale.setMaximumBarWidth(60)
    scale.setNumberOfSegments(2)
    scale.setNumberOfSegmentsLeft(0)
    scale.setUnitLabel("km")
    scale.setFont(QFont("Arial", 11))
    scale.setHeight(2.4)
    scale.setLineWidth(0.5)
    scale.setFrameEnabled(False)
    scale.setBackgroundEnabled(False)
    scale.setZValue(20)
    layout.addLayoutItem(scale)
    scale.setReferencePoint(QgsLayoutItem.LowerRight)
    scale.attemptMove(QgsLayoutPoint(400, 287, MM))
    scale.refresh()

    scale_w = max(scale.sizeWithUnits().width(), 78.0)
    gap_left = 14.0 + legend_w + FURNITURE_GAP
    gap_right = 400.0 - scale_w - FURNITURE_GAP
    avail = max(gap_right - gap_left, 80.0)
    note_w = min(NOTE_W, avail)
    note_x = gap_left + 0.5 * (avail - note_w)
    note_y = 8 + FRAME_H - NOTE_BOTTOM - NOTE_H
    note_panel = _white_box(layout, note_x, note_y, note_w, NOTE_H)
    note = QgsLayoutItemLabel(layout)
    note.setText(caption)
    note.setFont(QFont("Arial", 12, QFont.Bold))
    note.setHAlign(Qt.AlignHCenter)
    note.setVAlign(Qt.AlignVCenter)
    note.setMargin(2.4)
    note.setZValue(21)
    _place(layout, note, note_x, note_y, note_w, NOTE_H)

    credit = QgsLayoutItemLabel(layout)
    credit.setText(credit_text)
    fmt = _text(7, bold=False, halo=0.6)
    fmt.setFont(QFont("Arial", 7))
    credit.setTextFormat(fmt)
    credit.setHAlign(Qt.AlignRight)
    credit.setVAlign(Qt.AlignBottom)
    credit.setZValue(22)
    scale_top = 283.0 - max(scale.sizeWithUnits().height(), 14.0)
    _place(layout, credit, 400.0 - scale_w - 30, scale_top - 10.5, scale_w + 30, 9.0)

    sx, sy, sw, sh = _item_box(scale)
    tx, ty, tw, th = _item_box(title_panel)
    boxes = [
        (tx, ty, tw, th + 4.0),
        _item_box(north),
        _grow(_item_box(legend), BOTTOM_CLEAR),
        _grow(_item_box(note_panel), BOTTOM_CLEAR),
        (sx - 3.0, sy - 12.0, sw + 6.0, sh + 14.0),
        _grow(_item_box(credit), 2.0),
    ]
    if locator is not None:
        boxes.append(_item_box(locator))
    for item in (title_panel, north, legend, scale, note_panel, credit, locator):
        if item is not None:
            map_item.addLabelBlockingItem(item)
    return boxes, scale


def _nice_scale(scale, map_item, target_mm: float = 26.0) -> None:
    km_per_mm = map_item.scale() / 1e6
    raw = target_mm * km_per_mm
    step = min((1, 2, 2.5, 5, 10, 20, 25, 50, 100, 150, 200, 250), key=lambda v: abs(v - raw))
    scale.setSegmentSizeMode(QgsScaleBarSettings.SegmentSizeFixed)
    scale.setUnitsPerSegment(step)
    scale.update()


def _nice_scale(scale, map_item, target_mm: float = 26.0) -> None:
    km_per_mm = map_item.scale() / 1e6
    raw = target_mm * km_per_mm
    step = min((1, 2, 2.5, 5, 10, 20, 25, 50, 100, 150, 200, 250), key=lambda v: abs(v - raw))
    scale.setSegmentSizeMode(QgsScaleBarSettings.SegmentSizeFixed)
    scale.setUnitsPerSegment(step)
    scale.update()


def _export(layout, slug: str) -> Path:
    MAPS.mkdir(parents=True, exist_ok=True)
    png = MAPS / f"{slug}.png"
    tmp = png.with_name(f"{png.stem}_tmp.png")
    for path in (png, png.with_suffix(".pdf"), tmp):
        if path.exists():
            path.unlink()
    exporter = QgsLayoutExporter(layout)
    img = QgsLayoutExporter.ImageExportSettings()
    img.dpi = 160
    img.cropToContents = False
    if exporter.exportToImage(str(tmp), img) != QgsLayoutExporter.Success:
        raise RuntimeError(f"export failed: {slug}")
    tmp.replace(png)
    exporter.exportToPdf(str(png.with_suffix(".pdf")), QgsLayoutExporter.PdfExportSettings())
    print(png)
    return png


def _new_layout(project, name):
    for old in list(project.layoutManager().layouts()):
        project.layoutManager().removeLayout(old)
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(name)
    layout.pageCollection().page(0).setPageSize(QgsLayoutSize(420, 297, MM))
    return layout


def _map_item(layout, crs, layers, background="#eceae4"):
    item = QgsLayoutItemMap(layout)
    item.setFrameEnabled(True)
    item.setFrameStrokeColor(QColor(0, 0, 0))
    item.setFrameStrokeWidth(QgsLayoutMeasurement(0.55, MM))
    item.setBackgroundColor(QColor(background))
    item.setCrs(crs)
    item.setKeepLayerSet(True)
    item.setKeepLayerStyles(True)
    item.setLayers(layers)
    item.setLabelMargin(QgsLayoutMeasurement(3.0, MM))
    item.setMapFlags(QgsLayoutItemMap.MapItemFlags())
    item.setZValue(0)
    _place(layout, item, 8, 8, FRAME_W, FRAME_H)
    return item


SIZE_CLASSES = (
    (5_000_000, 8.0, "Over 5 million"),
    (1_000_000, 5.4, "1 to 5 million"),
    (250_000, 3.6, "250,000 to 1 million"),
    (100_000, 2.5, "100,000 to 250,000"),
    (0, 1.8, "Under 100,000"),
)


def _size_expression() -> str:
    cases = " ".join(f'WHEN "people" >= {floor} THEN {size}' for floor, size, _ in SIZE_CLASSES)
    return f"CASE {cases} END"


def _dot(color: str, size: float = 3.0) -> QgsMarkerSymbol:
    return QgsMarkerSymbol.createSimple({"name": "circle", "color": color, "outline_color": "255,255,255,255",
                                         "outline_width": "0.25", "outline_width_unit": "MM", "size": str(size)})


def _sized_dot(color: str) -> QgsMarkerSymbol:
    sym = _dot(color)
    sym.setDataDefinedSize(QgsProperty.fromExpression(_size_expression()))
    return sym


def study_area() -> Path:
    project = QgsProject.instance()
    project.clear()
    project.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
    grey = _grey_base()
    africa = _vector("africa", "Africa")
    africa.renderer().setSymbol(_fill("236,234,228,255", "120,120,120,255", "0.15"))
    pin = _vector("nigeria", "Nigeria pin")
    pin.renderer().setSymbol(_fill("40,40,40,255", "40,40,40,255", "0.15"))

    outside = _vector("outside", "Outside")
    outside.renderer().setSymbol(_fill("255,255,255,150"))
    lgas = _vector("lgas", "LGAs")
    lgas.renderer().setSymbol(_fill("0,0,0,0", LGA_LINE, "0.1"))
    states = _vector("states", "States")
    states.renderer().setSymbol(_fill("0,0,0,0", STATE_LINE, "0.35"))
    state_names = _vector("states", "State names")
    state_names.renderer().setSymbol(_fill("0,0,0,0"))
    sn = QgsPalLayerSettings()
    sn.fieldName = "label"
    sn.placement = Qgis.LabelPlacement.Horizontal
    sn.centroidInside = True
    sn.priority = 1
    sn.obstacle = False
    sn.setUnplacedVisibility(Qgis.UnplacedLabelVisibility.NeverShow)
    sn.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.PreventOverlap)
    fmt = _text(7.5, bold=False, halo=0.7)
    font = QFont("Helvetica", 8)
    font.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
    fmt.setFont(font)
    fmt.setColor(QColor(118, 112, 104))
    sn.setFormat(fmt)
    state_names.setLabeling(QgsVectorLayerSimpleLabeling(sn))
    state_names.setLabelsEnabled(True)
    nigeria = _vector("nigeria", "Nigeria")
    nigeria.renderer().setSymbol(_fill("0,0,0,0", EDGE, "0.9"))

    dots = _vector("city_points", "Urban centres")
    dots.setRenderer(QgsCategorizedSymbolRenderer("group", [
        QgsRendererCategory("panel", _sized_dot(f"{SLATE},235"), "Urban by 1990"),
        QgsRendererCategory("younger", _sized_dot(f"{SAND},235"), "Urban after 1990"),
    ]))
    dots.renderer().setOrderBy(QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause("people", False)]))
    dots.renderer().setOrderByEnabled(True)
    block = QgsPalLayerSettings()
    block.drawLabels = False
    block.obstacle = True
    block.fieldName = "name"
    dots.setLabeling(QgsVectorLayerSimpleLabeling(block))
    dots.setLabelsEnabled(True)

    names = _vector("city_points", "City names")
    names.setSubsetString("\"tier\" <> 'none'")
    _invisible_points(names)
    cn = QgsPalLayerSettings()
    cn.fieldName = "replace(\"name\", ' ', char(160))"
    cn.isExpression = True
    cn.placement = Qgis.LabelPlacement.AroundPoint
    cn.offsetType = Qgis.LabelOffsetType.FromSymbolBounds
    cn.dist = 0.8
    cn.obstacle = True
    cn.setUnplacedVisibility(Qgis.UnplacedLabelVisibility.NeverShow)
    cn.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.PreventOverlap)
    cn.setFormat(_text(10.5, halo=0.9))
    props = cn.dataDefinedProperties()
    props.setProperty(QgsPalLayerSettings.Size, QgsProperty.fromExpression("IF(\"tier\" = 'plate', 13.5, 10)"))
    props.setProperty(QgsPalLayerSettings.Priority, QgsProperty.fromExpression("IF(\"tier\" = 'plate', 10, 7)"))
    props.setProperty(QgsPalLayerSettings.LabelDistance,
                      QgsProperty.fromExpression(f"2.2 + 0.5 * ({_size_expression()})"))
    cn.setDataDefinedProperties(props)
    leader = QgsSimpleLineCallout()
    leader.setEnabled(True)
    leader.setLineSymbol(_line("28,25,22,255", "0.3"))
    leader.setMinimumLength(0.5)
    leader.dataDefinedProperties().setProperty(QgsCallout.OffsetFromAnchor,
                                               QgsProperty.fromExpression(f"0.5 * ({_size_expression()})"))
    cn.setCallout(leader)
    names.setLabeling(QgsVectorLayerSimpleLabeling(cn))
    names.setLabelsEnabled(True)

    for layer in (grey, africa, pin, outside, lgas, states, state_names, nigeria, dots, names):
        project.addMapLayer(layer, False)

    layout = _new_layout(project, "Study area")
    utm = QgsCoordinateReferenceSystem("EPSG:32632")
    map_item = _map_item(layout, utm, [names, dots, nigeria, state_names, states, lgas, outside, grey])
    poly = _union(nigeria)
    poly.transform(QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"), utm, project.transformContext()))
    ext = poly.boundingBox()
    map_item.setExtent(ext)

    web = QgsCoordinateReferenceSystem("EPSG:3857")
    to_web = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"), web, project.transformContext())
    loc_ext = to_web.transformBoundingBox(QgsRectangle(-18.5, -35.5, 52.5, 38.0))
    loc_w = 44.0
    loc_h = loc_w * loc_ext.height() / loc_ext.width()
    loc = QgsLayoutItemMap(layout)
    loc.setFrameEnabled(True)
    loc.setFrameStrokeColor(QColor(0, 0, 0))
    loc.setFrameStrokeWidth(QgsLayoutMeasurement(0.35, MM))
    loc.setBackgroundColor(QColor("#ffffff"))
    loc.setCrs(web)
    loc.setKeepLayerSet(True)
    loc.setKeepLayerStyles(True)
    loc.setLayers([pin, africa])
    loc.setZValue(22)
    _place(layout, loc, 406.0 - loc_w, 46.0, loc_w, loc_h)
    loc.setExtent(loc_ext)

    caption = ("Each circle is one of Nigeria's 425 GHSL urban centres, drawn at its centre and sized by its "
               "people in 2020 from GHS-POP. The 183 dark circles were already urban by 1990 and are the cities "
               "compared from 1990 to 2020; the light circles became urban later. "
               "Grey lines are the 36 states, the FCT and the 774 local government areas.")
    entries = [
        ("Point", "Urban by 1990 (183)", _dot(f"{SLATE},235", 3.6)),
        ("Point", "Urban after 1990 (242)", _dot(f"{SAND},235", 3.6)),
    ]
    entries += [("Point", label, _dot("150,150,150,235", size)) for _f, size, label in SIZE_CLASSES]
    entries += [
        ("LineString", "Nigeria", _line(EDGE, "0.9")),
        ("LineString", "State", _line(STATE_LINE, "0.35")),
        ("LineString", "Local government area", _line("135,130,124,220", "0.2")),
    ]
    boxes, scale = _furniture(layout, map_item, project, title="STUDY AREA\nNigeria's 425 urban centres",
                              caption=caption, legend_title="Urban centres, people in 2020", entries=entries,
                              legend_w=74.0, credit_text="©Wisdom Akpabio\nBase map © Esri", locator=loc,
                              legend_h=None)
    map_item.setExtent(_framed_extent(ext, boxes, poly))
    map_item.refresh()
    _nice_scale(scale, map_item)
    scale.refresh()
    return _export(layout, "nigeria_study_area")


TOP5 = {
    "lagos": ("Lagos", "EPSG:32631", "Iga Idunganran", "Iga Idunganran, the Oba's palace on Lagos Island"),
    "kano": ("Kano", "EPSG:32632", "Gidan Rumfa", "Gidan Rumfa, the Emir's palace"),
    "ibadan": ("Ibadan", "EPSG:32631", "Mapo Hill", "Mapo Hill"),
    "kaduna": ("Kaduna", "EPSG:32632", "Lugard Hall", "Lugard Hall, in the 1913 government district"),
    "onitsha": ("Onitsha", "EPSG:32632", "Ime-Obi Ogboza", "Ime-Obi Ogboza, the old palace ground of the Obi of Onitsha"),
}


def _locator(layout, project, slug: str, x: float = None, y: float = 46.0, w: float = 52.0):
    states = _vector("states", "Locator states")
    states.renderer().setSymbol(_fill("236,234,228,255", "150,146,140,255", "0.12"))
    country = _vector("nigeria", "Locator Nigeria")
    country.renderer().setSymbol(_fill("0,0,0,0", EDGE, "0.4"))
    here = _vector("study_centres", "Locator city")
    here.setSubsetString(f"\"slug\" = '{slug}'")
    here.renderer().setSymbol(QgsMarkerSymbol.createSimple({"name": "square", "color": "200,30,30,255",
                                                            "outline_color": "255,255,255,255",
                                                            "outline_width": "0.3", "size": "3.0"}))
    shape = None
    if (PLATES / f"{slug}_outline.gpkg").exists():
        shape = _vector(f"{slug}_outline", "Locator outline")
        shape.renderer().setSymbol(_fill("200,30,30,255", "120,0,0,255", "0.5"))
        here.renderer().setSymbol(QgsMarkerSymbol.createSimple({"name": "circle", "color": "0,0,0,0",
                                                                "outline_style": "no", "size": "3.0"}))
    tag = QgsPalLayerSettings()
    tag.fieldName = f"'{TOP5[slug][0]}'" if slug in TOP5 else "\"name\""
    tag.isExpression = True
    tag.placement = Qgis.LabelPlacement.OrderedPositionsAroundPoint
    tag.predefinedPositionOrder = [QgsPalLayerSettings.MiddleRight, QgsPalLayerSettings.TopRight,
                                   QgsPalLayerSettings.MiddleLeft, QgsPalLayerSettings.BottomRight]
    tag.offsetType = Qgis.LabelOffsetType.FromSymbolBounds
    tag.dist = 0.6
    tag.setFormat(_text(9, halo=0.8))
    here.setLabeling(QgsVectorLayerSimpleLabeling(tag))
    here.setLabelsEnabled(True)
    for layer in (states, country, here, shape):
        if layer is not None:
            project.addMapLayer(layer, False)
    crs = QgsCoordinateReferenceSystem("EPSG:32632")
    ext = _union(country)
    ext.transform(QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"), crs, project.transformContext()))
    ext = ext.boundingBox()
    ext.grow(25_000)
    h = w * ext.height() / ext.width()
    x = 406.0 - w if x is None else x
    loc = QgsLayoutItemMap(layout)
    loc.setFrameEnabled(True)
    loc.setFrameStrokeColor(QColor(0, 0, 0))
    loc.setFrameStrokeWidth(QgsLayoutMeasurement(0.35, MM))
    loc.setBackgroundColor(QColor("#ffffff"))
    loc.setCrs(crs)
    loc.setKeepLayerSet(True)
    loc.setKeepLayerStyles(True)
    loc.setLayers([layer for layer in (here, shape, country, states) if layer is not None])
    loc.setZValue(22)
    _place(layout, loc, x, y, w, h)
    loc.setExtent(ext)
    return loc


# Rows: GHS-POP low to high. Columns: WorldPop low to high. Green is GHS-POP, blue is WorldPop.
BIVARIATE = (
    ("232,232,232", "181,192,218", "108,131,181"),
    ("184,214,190", "144,178,179", "86,121,148"),
    ("115,174,128", "90,145,120", "42,90,91"),
)
STAR_YELLOW = "255,214,0,255"
CALLOUT_LGAS = (
    "Surulere", "Lagos Island", "Lagos Mainland", "Shomolu", "Mushin", "Agege", "Ajeromi/Ifelodun",
    "Kano Municipal", "Dala", "Fagge", "Gwale", "Tarauni", "Nassarawa",
    "Ibadan South East", "Ibadan North East", "Ibadan South West", "Ibadan North West", "Ibadan North",
    "Kaduna North", "Kaduna South", "Onitsha South", "Onitsha North",
)
KEY_CELL = 9.0


def _bivariate_layer(slug: str) -> QgsRasterLayer:
    layer = QgsRasterLayer(str(PLATES / f"{slug}_bivariate_2020.tif"), "People, two grids")
    classes = [QgsPalettedRasterRenderer.Class(3 * g + w, QColor(*map(int, BIVARIATE[g][w].split(","))), "")
               for g in range(3) for w in range(3)]
    layer.setRenderer(QgsPalettedRasterRenderer(layer.dataProvider(), 1, classes))
    layer.dataProvider().setNoDataValue(1, 255)
    layer.setOpacity(0.9)
    return layer


def _key_text(layout, text, x, y, w, h, size=9.5, bold=False, align=Qt.AlignHCenter, rotate=0.0):
    item = QgsLayoutItemLabel(layout)
    item.setText(text)
    item.setFont(QFont("Arial", int(size), QFont.Bold if bold else QFont.Normal))
    item.setHAlign(align)
    item.setVAlign(Qt.AlignVCenter)
    item.setMargin(0)
    item.setZValue(23)
    _place(layout, item, x, y, w, h)
    if rotate:
        item.setItemRotation(rotate)
    return item


def _bivariate_key(layout, cuts, x, y):
    """A 3 x 3 colour key in a white box; returns the box."""
    low, high = (f"{c:,.0f}" for c in cuts)
    ticks = (f"under {low}", f"{low}\u2013{high}", f"over {high}")
    w, h = 74.0, 66.0
    box = _white_box(layout, x, y, w, h)
    _key_text(layout, "People per hectare, 2020", x + 2.5, y + 2.5, w - 5, 6, size=11, bold=True, align=Qt.AlignLeft)
    gx, gy = x + 25.0, y + 11.5
    for g in range(3):
        for wcol in range(3):
            cell = QgsLayoutItemShape(layout)
            cell.setShapeType(QgsLayoutItemShape.Rectangle)
            cell.setSymbol(QgsFillSymbol.createSimple({"color": f"{BIVARIATE[g][wcol]},255",
                                                       "outline_color": "255,255,255,255", "outline_width": "0.3"}))
            cell.setZValue(22)
            _place(layout, cell, gx + wcol * KEY_CELL, gy + (2 - g) * KEY_CELL, KEY_CELL, KEY_CELL)
    for i, tick in enumerate(ticks):
        _key_text(layout, tick, gx - 21.0, gy + (2 - i) * KEY_CELL, 20.0, KEY_CELL, size=8, align=Qt.AlignRight)
        _key_text(layout, tick.replace(" ", "\n", 1) if i != 1 else tick, gx + i * KEY_CELL - 1.5,
                  gy + 3 * KEY_CELL + 0.8, KEY_CELL + 3.0, 7.0, size=7.5)
    _key_text(layout, "WorldPop \u2192", gx, gy + 3 * KEY_CELL + 8.5, 3 * KEY_CELL, 5, size=10, bold=True)
    _key_text(layout, "GHS-POP \u2191", gx + 3 * KEY_CELL + 1.5, gy + 1.5 * KEY_CELL - 2.5, 24, 5, size=10,
              bold=True, align=Qt.AlignLeft)
    _key_text(layout, "Green: only GHS-POP is dense. Blue: only WorldPop.\nDark teal: both agree.",
              x + 2.5, y + h - 11.5, w - 5, 10, size=8, align=Qt.AlignLeft)
    return box


def _fresh_project() -> QgsProject:
    project = QgsProject.instance()
    project.clear()
    project.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
    engine = project.labelingEngineSettings()
    engine.setFlag(QgsLabelingEngineSettings.UsePartialCandidates, False)
    project.setLabelingEngineSettings(engine)
    return project


def _city_layers(slug: str) -> dict:
    """In-city LGA lines and names, the study outline and the starred centre, shared by the study and results
    plates for one of the five cities."""
    short = TOP5[slug][2]
    lgas = _vector(f"{slug}_lgas", "LGAs")
    lgas.setSubsetString("\"in_city\" = 1")
    lgas.renderer().setSymbol(_fill("0,0,0,0", "70,52,40,235", "0.35"))
    named = ", ".join(f"'{n}'" for n in CALLOUT_LGAS)
    crowded = f"\"km2\" < {SMALL_LGA_KM2} OR \"shapeName\" IN ({named})"
    lga_names = _vector(f"{slug}_lgas", "LGA names")
    lga_names.setSubsetString(f"\"in_city\" = 1 AND NOT ({crowded})")
    lga_names.renderer().setSymbol(_fill("0,0,0,0"))
    ln = QgsPalLayerSettings()
    ln.fieldName = "replace(replace(\"shapeName\", '/', '/' || char(8203)), ' ', char(160))"
    ln.isExpression = True
    ln.placement = Qgis.LabelPlacement.AroundPoint
    ln.dist = 0.5
    ln.centroidInside = True
    ln.fitInPolygonOnly = False
    ln.priority = 5
    ln.setUnplacedVisibility(Qgis.UnplacedLabelVisibility.NeverShow)
    ln.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.PreventOverlap)
    fmt = _text(11, bold=False, halo=0.9)
    fmt.setColor(QColor(30, 26, 22))
    ln.setFormat(fmt)
    ln.dataDefinedProperties().setProperty(QgsPalLayerSettings.Size, QgsProperty.fromExpression(
        "CASE WHEN \"km2\" < 50 THEN 9.5 ELSE 11 END"))
    lga_names.setLabeling(QgsVectorLayerSimpleLabeling(ln))
    lga_names.setLabelsEnabled(True)
    small_names = _vector(f"{slug}_lgas", "Small LGA names")
    small_names.setSubsetString(f"\"in_city\" = 1 AND ({crowded})")
    small_names.renderer().setSymbol(_fill("0,0,0,0"))
    sl = QgsPalLayerSettings(ln)
    sl.placement = Qgis.LabelPlacement.OutsidePolygons
    sl.dist = 7.5
    sl.priority = 8
    sl.setUnplacedVisibility(Qgis.UnplacedLabelVisibility.NeverShow)
    sl.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.PreventOverlap)
    leader = QgsSimpleLineCallout()
    leader.setEnabled(True)
    leader.setLineSymbol(_line("30,26,22,255", "0.3"))
    leader.setAnchorPoint(QgsCallout.PointOnSurface)
    leader.setMinimumLength(2.5)
    sl.setCallout(leader)
    small_names.setLabeling(QgsVectorLayerSimpleLabeling(sl))
    small_names.setLabelsEnabled(True)

    outline = _vector(f"{slug}_outline", "Study area")
    outline.renderer().setSymbol(_fill("0,0,0,0", EDGE, "0.9"))
    edge_block = QgsPalLayerSettings()
    edge_block.drawLabels = False
    edge_block.obstacle = True
    edge_block.obstacleSettings().setType(QgsLabelObstacleSettings.PolygonBoundary)
    edge_block.fieldName = "name"
    outline.setLabeling(QgsVectorLayerSimpleLabeling(edge_block))
    outline.setLabelsEnabled(True)
    feat = next(outline.getFeatures())
    km2, n_lga, people_n = int(round(feat["km2"])), int(feat["n_lgas"]), float(feat["people"])

    centre = _vector("study_centres", "Centre")
    centre.setSubsetString(f"\"slug\" = '{slug}'")
    star = QgsMarkerSymbol.createSimple({"name": "star", "color": STAR_YELLOW, "outline_color": "0,0,0,255",
                                         "outline_width": "0.5", "size": "7.5"})
    centre.renderer().setSymbol(star)
    cl = QgsPalLayerSettings()
    cl.fieldName = f"'{short}'"
    cl.isExpression = True
    cl.placement = Qgis.LabelPlacement.OrderedPositionsAroundPoint
    cl.predefinedPositionOrder = [QgsPalLayerSettings.TopRight, QgsPalLayerSettings.TopLeft,
                                  QgsPalLayerSettings.MiddleRight, QgsPalLayerSettings.BottomRight,
                                  QgsPalLayerSettings.MiddleLeft, QgsPalLayerSettings.BottomLeft]
    cl.offsetType = Qgis.LabelOffsetType.FromSymbolBounds
    cl.dist = 3.5
    cl.priority = 10
    cl.obstacle = True
    cl.obstacleSettings().setFactor(3.0)
    cl.setUnplacedVisibility(Qgis.UnplacedLabelVisibility.NeverShow)
    cl.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.PreventOverlap)
    cl.setFormat(_text(12, halo=1.2))
    centre.setLabeling(QgsVectorLayerSimpleLabeling(cl))
    centre.setLabelsEnabled(True)
    return {"lgas": lgas, "lga_names": lga_names, "small_names": small_names, "outline": outline,
            "centre": centre, "star": star, "km2": km2, "n_lga": n_lga, "people": people_n}


def _fit_with_inset(layout, map_item, project, slug, loc, layers, utm, ext, boxes, poly, centre,
                    inset_w: float = 96.0) -> None:
    """Zoomed core inset under the locator, then the main map framed around every piece of furniture."""
    core = _union(_vector(f"{slug}_core", "Core"))
    core.transform(QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"), utm, project.transformContext()))
    core = core.boundingBox()
    inset = _core_inset(layout, loc, core, layers, utm, inset_w)
    framed = _framed_extent(ext, boxes + [_grow(_item_box(inset), FURNITURE_GAP)], poly)
    widest = inset.rect().width() * framed.width() / (INSET_GAIN * map_item.rect().width())
    if core.width() > widest:
        core.scale(widest / core.width())
        star_at = next(centre.getFeatures()).geometry()
        star_at.transform(QgsCoordinateTransform(centre.crs(), utm, project.transformContext()))
        sx, sy = star_at.asPoint().x(), star_at.asPoint().y()
        mx, my = 0.25 * core.width(), 0.25 * core.height()
        dx = min(0.0, sx - (core.xMinimum() + mx)) + max(0.0, sx - (core.xMaximum() - mx))
        dy = min(0.0, sy - (core.yMinimum() + my)) + max(0.0, sy - (core.yMaximum() - my))
        core = QgsRectangle(core.xMinimum() + dx, core.yMinimum() + dy, core.xMaximum() + dx, core.yMaximum() + dy)
        inset.setExtent(core)
        _inset_title(inset.title_label, core)
    map_item.addLabelBlockingItem(inset)
    overview = QgsLayoutItemMapOverview("Core", map_item)
    overview.setLinkedMap(inset)
    overview.setFrameSymbol(_fill("0,0,0,0", "200,30,30,255", "0.6"))
    map_item.overviews().addOverview(overview)
    map_item.setExtent(framed)
    map_item.refresh()
    _inset_arrow(layout, map_item, inset)


def _inset_arrow(layout, map_item, inset) -> None:
    """Red arrow from the small box on the main map to the zoomed frame it stands for."""
    box = inset.extent()
    mx, my = map_item.positionWithUnits().x(), map_item.positionWithUnits().y()
    a = map_item.mapToItemCoords(QPointF(box.xMaximum(), box.center().y()))
    start = QPointF(mx + a.x() + 1.0, my + a.y())
    ix, iy = inset.positionWithUnits().x(), inset.positionWithUnits().y()
    ih = inset.sizeWithUnits().height()
    end = QPointF(ix - 1.5, min(max(start.y(), iy + 8.0), iy + ih - 8.0))
    if end.x() - start.x() < 6.0:
        return
    arrow = QgsLayoutItemPolyline(QPolygonF([start, end]), layout)
    arrow.setSymbol(_line("200,30,30,255", "0.6"))
    arrow.setEndMarker(QgsLayoutItemPolyline.ArrowHead)
    arrow.setArrowHeadWidth(3.2)
    arrow.setArrowHeadFillColor(QColor(200, 30, 30))
    arrow.setArrowHeadStrokeColor(QColor(200, 30, 30))
    arrow.setZValue(21)
    layout.addLayoutItem(arrow)
    map_item.addLabelBlockingItem(arrow)


def city_study(slug: str) -> Path:
    name, utm_code, short, long = TOP5[slug]
    project = _fresh_project()
    grey = _grey_base()
    cuts = [float(v) for v in (PLATES / f"{slug}_people_breaks.txt").read_text().split(",")]
    people = _bivariate_layer(slug)
    c = _city_layers(slug)
    lgas, lga_names, small_names, outline, centre, star = (c["lgas"], c["lga_names"], c["small_names"],
                                                           c["outline"], c["centre"], c["star"])
    km2, n_lga, people_n = c["km2"], c["n_lga"], c["people"]

    for layer in (grey, people, lgas, lga_names, small_names, outline, centre):
        project.addMapLayer(layer, False)

    layout = _new_layout(project, f"Study area {name}")
    utm = QgsCoordinateReferenceSystem(utm_code)
    map_item = _map_item(layout, utm, [centre, small_names, lga_names, outline, lgas, people, grey])
    poly = _union(outline)
    poly.transform(QgsCoordinateTransform(outline.crs(), utm, project.transformContext()))
    ext = poly.boundingBox()
    map_item.setExtent(ext)
    loc = _locator(layout, project, slug)

    caption = (f"The black outline is {name}: the {n_lga} local government areas that make up the city, "
               f"{km2:,} square kilometres and {people_n / 1e6:.1f} million people in 2020. "
               f"Each 100-metre square is coloured by how many people GHS-POP and WorldPop each put in it. "
               f"The yellow star is {long}, from which every distance is measured.")
    entries = [
        ("Polygon", "Study area", _fill("0,0,0,0", EDGE, "0.9")),
        ("Polygon", "Local government area", _fill("0,0,0,0", "70,52,40,235", "0.4")),
        ("Point", "Centre", star.clone()),
    ]
    boxes, scale = _furniture(layout, map_item, project, title=f"STUDY AREA\n{name}", caption=caption,
                              legend_title="Boundaries", entries=entries, legend_w=74.0,
                              credit_text="©Wisdom Akpabio\nBase map © Esri", locator=loc)
    legend_box = boxes[2]
    key_y = 8.0 + legend_box[1] + BOTTOM_CLEAR - 66.0 - 3.0
    key = _bivariate_key(layout, cuts, 14.0, key_y)
    map_item.addLabelBlockingItem(key)
    boxes.append(_grow(_item_box(key), BOTTOM_CLEAR))
    _fit_with_inset(layout, map_item, project, slug, loc,
                    [centre, small_names, lga_names, outline, lgas, people, grey], utm, ext, boxes, poly, centre)
    _nice_scale(scale, map_item)
    scale.refresh()
    return _export(layout, f"{slug}_study_area")


INSET_GAIN = 2.0


def _core_inset(layout, loc, core: QgsRectangle, layers, crs, width: float = 96.0):
    """Zoomed frame on the built-up core, in the right-hand column under the locator, or under the north arrow
    when the plate has no locator."""
    if loc is not None:
        lx, ly, lw, lh = _item_box(loc)
        top = 8.0 + ly + lh + 5.0
    else:
        top = 48.0
    max_h = 250.0 - top
    w = width
    h = w * core.height() / core.width()
    if h > max_h:
        h, w = max_h, max_h * core.width() / core.height()
    inset = _map_item(layout, crs, layers)
    inset.setFrameStrokeColor(QColor(200, 30, 30))
    inset.setLabelMargin(QgsLayoutMeasurement(1.5, MM))
    inset.setZValue(22)
    inset.attemptMove(QgsLayoutPoint(406.0 - w, top, MM))
    inset.attemptResize(QgsLayoutSize(w, h, MM))
    inset.setExtent(core)
    label = QgsLayoutItemLabel(layout)
    label.setFont(QFont("Arial", 10, QFont.Bold))
    label.setBackgroundEnabled(True)
    label.setBackgroundColor(QColor(255, 255, 255))
    label.setMargin(1.2)
    label.setZValue(23)
    _place(layout, label, 406.0 - w + 1.5, top + 1.5)
    _inset_title(label, core)
    inset.addLabelBlockingItem(label)
    inset.title_label = label
    return inset


def _inset_title(label, core: QgsRectangle) -> None:
    label.setText(f"City core, {core.width() / 1000:.0f} km across")
    label.adjustSizeToText()
    size = label.sizeWithUnits()
    label.attemptResize(QgsLayoutSize(size.width() + 4.0, size.height(), MM))


ZONE_GREENS = {"central": "0,90,50", "intermediate": "35,139,69", "distant": "116,196,118"}


def _change_layer(path: Path) -> QgsRasterLayer:
    """People gained or lost per 100 m square; squares within five people of no change stay see-through."""
    change = QgsRasterLayer(str(path), "Change")
    ramp = QgsColorRampShader()
    ramp.setColorRampType(QgsColorRampShader.Discrete)
    ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(
        v, QColor(0, 0, 0, 0) if v == 5 else QColor(*map(int, c.split(","))), lab) for v, c, lab in CHANGE_CLASSES])
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(ramp)
    change.setRenderer(QgsSingleBandPseudoColorRenderer(change.dataProvider(), 1, shader))
    change.setOpacity(0.92)
    change.dataProvider().setNoDataValue(1, -9999)
    return change


def _city_result_numbers(name: str) -> dict:
    import csv

    with open(ROOT / "data" / "processed" / "named_cities_lga.csv", newline="") as fh:
        return next(r for r in csv.DictReader(fh) if r["city"] == name)


def city_result(slug: str) -> Path:
    """Results plate for one of the five cities: where people were added and lost between 1990 and 2020, with the
    zone edges around the founding centre and the city's headline numbers in the footnote."""
    name, utm_code, short, long = TOP5[slug]
    project = _fresh_project()
    grey = _grey_base()
    change = _change_layer(PLATES / f"{slug}_change_lga.tif")
    c = _city_layers(slug)
    lgas, lga_names, small_names, outline, centre, star = (c["lgas"], c["lga_names"], c["small_names"],
                                                           c["outline"], c["centre"], c["star"])
    zones = _zones_for_plate(slug)
    zone_lines = {z: _line(f"{ZONE_GREENS[z]},255", w, style) for z, w, style in
                  (("central", "1.1", "solid"), ("intermediate", "1.0", "dash"), ("distant", "1.0", "dot"))}
    zones.setRenderer(QgsCategorizedSymbolRenderer("zone", [
        QgsRendererCategory(z, s.clone(), z.capitalize()) for z, s in zone_lines.items()]))
    _zone_curve_labels(zones)
    edges = {f["zone"]: f["km"] for f in zones.getFeatures()}

    stack = [centre, small_names, lga_names, outline, zones, lgas, change, grey]
    for layer in reversed(stack):
        project.addMapLayer(layer, False)
    layout = _new_layout(project, f"Results {name}")
    utm = QgsCoordinateReferenceSystem(utm_code)
    map_item = _map_item(layout, utm, stack)
    poly = _union(outline)
    poly.transform(QgsCoordinateTransform(outline.crs(), utm, project.transformContext()))
    ext = poly.boundingBox()
    map_item.setExtent(ext)

    n = _city_result_numbers(name)
    s90, s20 = float(n["central_share_1990"]), float(n["central_share_2020"])
    phi, expect = float(n["phi_1990_2020"]), float(n["phi_national_fit"])
    gained = (float(n["people_2020"]) - float(n["people_1990"])) / 1e6
    move = (f"{(phi - 1) * 100:.0f}% farther from" if phi >= 1.005 else
            f"{(1 - phi) * 100:.0f}% closer to" if phi <= 0.995 else "as far from")
    caption = (f"Each 100-metre square shows people in 2020 minus people in 1990 (GHS-POP) across the "
               f"{c['n_lga']} local government areas of {name}, which gained {gained:.1f} million people. "
               f"The circles are the central, intermediate and distant zone edges around {short}, at "
               f"{edges['central']:.1f}, {edges['intermediate']:.1f} and {edges['distant']:.1f} km. "
               f"The central zone held {s90:.0%} of the city's people in 1990 and {s20:.0%} in 2020, and the typical "
               f"resident lived {move} the centre (expected from all Nigerian cities: {(expect - 1) * 100:.0f}% "
               f"farther).")
    entries = [("Polygon", lab, _fill(f"{col},235") if v != 5 else _fill("0,0,0,0", "150,146,140,255", "0.2"))
               for v, col, lab in CHANGE_CLASSES]
    # Legend-only symbols: same look, sized to the 5 mm row so a 7.5 mm map star cannot blow the box.
    legend_star = QgsMarkerSymbol.createSimple({
        "name": "star", "color": STAR_YELLOW, "outline_color": "0,0,0,255",
        "outline_width": "0.4", "size": "4.2", "size_unit": "MM"})
    entries += [
        ("LineString", "Central zone edge", zone_lines["central"].clone()),
        ("LineString", "Intermediate zone edge", zone_lines["intermediate"].clone()),
        ("LineString", "Distant zone edge", zone_lines["distant"].clone()),
        ("Polygon", "Study area", _fill("0,0,0,0", EDGE, "0.9")),
        ("Polygon", "Local government area", _fill("0,0,0,0", "70,52,40,235", "0.4")),
        ("Point", short, legend_star),
    ]
    boxes, scale = _furniture(layout, map_item, project, title=f"{name.upper()}, 1990 TO 2020\n"
                              "Where people were added and lost", caption=caption,
                              legend_title="People gained per square", entries=entries, legend_w=74.0,
                              credit_text="©Wisdom Akpabio\nBase map © Esri", legend_h=None)
    _fit_with_inset(layout, map_item, project, slug, None, stack, utm, ext, boxes, poly, centre, inset_w=132.0)
    _nice_scale(scale, map_item)
    scale.refresh()
    return _export(layout, f"{slug}_results")


def city(slug: str) -> Path:
    spec = CITIES[slug]
    project = QgsProject.instance()
    project.clear()
    project.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
    base = _positron()

    change = QgsRasterLayer(str(PLATES / f"{slug}_change.tif"), "Change")
    ramp = QgsColorRampShader()
    ramp.setColorRampType(QgsColorRampShader.Discrete)
    ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v, QColor(*map(int, c.split(","))), lab)
                               for v, c, lab in CHANGE_CLASSES])
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(ramp)
    renderer = QgsSingleBandPseudoColorRenderer(change.dataProvider(), 1, shader)
    change.setRenderer(renderer)
    change.setOpacity(FILL_ALPHA / 255)
    change.dataProvider().setNoDataValue(1, -9999)

    outline = _vector(f"{slug}_outline", "Urban centre")
    outline.renderer().setSymbol(_fill("0,0,0,0", EDGE, "0.9"))
    zones = _vector("zone_circles", "Zones")
    zones.setSubsetString(f"\"slug\" = '{slug}'")
    zones.setRenderer(QgsCategorizedSymbolRenderer("zone", [
        QgsRendererCategory("central", _line(f"{SLATE},255", "0.9"), "Central"),
        QgsRendererCategory("intermediate", _line(f"{SLATE},255", "0.6", "dash"), "Intermediate"),
        QgsRendererCategory("distant", _line(f"{SLATE},255", "0.5", "dot"), "Distant"),
    ]))
    centre = _vector("city_centres", "Centre")
    centre.setSubsetString(f"\"slug\" = '{slug}'")
    star = QgsMarkerSymbol.createSimple({"name": "star", "color": "255,255,255,255", "outline_color": "0,0,0,255",
                                         "outline_width": "0.45", "size": "5.5"})
    centre.renderer().setSymbol(star)
    keep_clear = QgsPalLayerSettings()
    keep_clear.drawLabels = False
    keep_clear.obstacle = True
    keep_clear.obstacleSettings().setFactor(2.0)
    keep_clear.fieldName = "slug"
    centre.setLabeling(QgsVectorLayerSimpleLabeling(keep_clear))
    centre.setLabelsEnabled(True)
    places = _vector(f"{slug}_places", "Places")
    _invisible_points(places)
    _labels(places, "name", 10, 5)
    for layer in (base, change, outline, zones, centre, places):
        project.addMapLayer(layer, False)

    layout = _new_layout(project, spec["name"])
    utm = QgsCoordinateReferenceSystem(spec["utm"])
    map_item = _map_item(layout, utm, [places, centre, zones, outline, change, base], background="#f3f1ed")
    poly = _union(outline)
    poly.transform(QgsCoordinateTransform(outline.crs(), utm, project.transformContext()))
    ext = poly.boundingBox()
    map_item.setExtent(ext)

    caption = (f"Each square is 100 metres across and shows people in 2020 minus people in 1990, from GHS-POP, "
               f"a modelled population grid, inside the 2025 GHSL outline of {spec['name']}. "
               f"Red squares gained people and blue squares lost them. "
               f"The circles mark the edges of the central, intermediate and distant zones around {spec['centre']}.")
    entries = [("Polygon", lab, _fill(f"{c},{FILL_ALPHA}")) for _v, c, lab in CHANGE_CLASSES]
    entries += [
        ("LineString", "Central zone edge", _line(f"{SLATE},255", "0.9")),
        ("LineString", "Intermediate edge", _line(f"{SLATE},255", "0.6", "dash")),
        ("LineString", "Distant edge", _line(f"{SLATE},255", "0.5", "dot")),
        ("LineString", "Urban centre", _line(EDGE, "0.9")),
        ("Point", "Centre", star.clone()),
    ]
    boxes, scale = _furniture(layout, map_item, project, title=f"{spec['name'].upper()}, 1990 TO 2020\n"
                              "Where people were added and lost", caption=caption,
                              legend_title="People gained per square", entries=entries, legend_w=66.0,
                              credit_text="©Wisdom Akpabio\n© OpenStreetMap contributors © CARTO")
    map_item.setExtent(_framed_extent(ext, boxes, poly))
    map_item.refresh()
    _nice_scale(scale, map_item)
    scale.refresh()
    return _export(layout, f"{slug}_change")


if __name__ == "__main__":
    QgsApplication.setPrefixPath(os.environ["QGIS_PREFIX_PATH"], True)
    app = QgsApplication([], False)
    app.initQgis()
    try:
        for target in sys.argv[1:] or ["study", *CITIES]:
            if target == "study":
                study_area()
            elif target.startswith("study_"):
                city_study(target.removeprefix("study_"))
            elif target.startswith("results_"):
                city_result(target.removeprefix("results_"))
            else:
                city(target)
    except Exception:
        import traceback

        traceback.print_exc()
        os._exit(1)
    os._exit(0)
