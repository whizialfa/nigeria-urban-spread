"""Urban-spread method: rings, remoteness zones and the spread factor, as a QGIS Processing script.

Install: Processing Toolbox > Python icon > Add Script to Toolbox... > pick this file.
Run:     Processing Toolbox > Where the centre holds > Urban spread method.

What it does (the whole paper method on one city at a time):
  1. Takes an outline (one polygon or several that union to the city), a centre point, and one
     population raster per year (GHS-POP or WorldPop at 100 m).
  2. Counts people in 100 metre rings around the centre. Distance is measured on the ground in an
     azimuthal equidistant projection centred on that city, not on the raster's flat grid.
  3. Scales distance by the square root of the city's final-year population (remoteness r). Cuts
     the city into central (r < 3), intermediate (3 to 5), distant (5 to 9.3) and peri-urban.
  4. Writes a ring table, a zone summary, the spread factor φ between the first and last year, and
     zone-edge circles as a vector layer. Loads the circles and a short summary layer into the project.

Zone edges in kilometres are r_cut × √(people in the last year) / 1000. A bigger city gets wider
circles; that is intentional. The cut-offs and the φ arithmetic follow Peraza-Mues et al.
(arXiv:2509.16110). This script is the method in one place; the plate scripts only draw.
"""

from __future__ import annotations

import csv
import math
import os
from collections import defaultdict

import numpy as np
from osgeo import gdal, osr
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsFillSymbol,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterPoint,
    QgsProcessingParameterString,
    QgsProcessingParameterVectorLayer,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant

RING_M = 100.0
ZONE_CUTS = (
    ("central", 0.0, 3.0),
    ("intermediate", 3.0, 5.0),
    ("distant", 5.0, 9.3),
    ("peri-urban", 9.3, float("inf")),
)
ZONE_EDGE_R = (3.0, 5.0, 9.3)
ZONE_EDGE_COLOURS = ("#005a32", "#238b45", "#74c476")
QUANTILES = np.linspace(0.01, 0.99, 99)


def _year_from_name(name: str, fallback: int) -> int:
    digits = "".join(ch if ch.isdigit() else " " for ch in name)
    parts = [p for p in digits.split() if len(p) == 4]
    for p in parts:
        y = int(p)
        if 1970 <= y <= 2100:
            return y
    return fallback


def _aeqd_wkt(lon: float, lat: float) -> str:
    return (
        f'PROJCS["Azimuthal_Equidistant",'
        f'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
        f'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
        f'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
        f'PROJECTION["Azimuthal_Equidistant"],'
        f'PARAMETER["False_Easting",0.0],PARAMETER["False_Northing",0.0],'
        f'PARAMETER["Central_Meridian",{lon}],PARAMETER["Latitude_Of_Origin",{lat}],'
        f'UNIT["Meter",1.0]]'
    )


def _zone_of(r: float) -> str:
    for name, lo, hi in ZONE_CUTS:
        if lo <= r < hi:
            return name
    return "peri-urban"


def _quantiles_from_rings(people_by_ring: dict[int, float]) -> np.ndarray:
    if not people_by_ring:
        return np.full(QUANTILES.shape, np.nan)
    rings = sorted(people_by_ring)
    counts = np.array([people_by_ring[k] for k in rings], dtype=float)
    total = counts.sum()
    if total <= 0:
        return np.full(QUANTILES.shape, np.nan)
    upper = (np.array(rings, dtype=float) + 1.0) * RING_M
    cum = np.cumsum(counts) / total
    return np.interp(QUANTILES, np.concatenate([[0.0], cum]), np.concatenate([[0.0], upper]))


def _phi(q0: np.ndarray, q1: np.ndarray) -> float:
    if not np.isfinite(q0).all() or not np.isfinite(q1).all():
        return float("nan")
    denom = float(np.dot(q0, q0))
    if denom <= 0:
        return float("nan")
    return float(np.dot(q0, q1) / denom)


def _union_geom(layer) -> QgsGeometry:
    geoms = []
    for feat in layer.getFeatures():
        g = feat.geometry()
        if g and not g.isEmpty():
            geoms.append(QgsGeometry(g))
    if not geoms:
        raise QgsProcessingException("the outline layer has no geometries")
    out = geoms[0]
    for g in geoms[1:]:
        out = out.combine(g)
    if out is None or out.isEmpty():
        raise QgsProcessingException("could not union the outline")
    return out


def _read_masked(path: str, outline_wgs: QgsGeometry, feedback):
    """Return people array (nodata=0), origin x/y, dx, dy, width, height, src_wkt."""
    ds = gdal.Open(path)
    if ds is None:
        raise QgsProcessingException(f"could not open raster: {path}")
    band = ds.GetRasterBand(1)
    gt = ds.GetGeoTransform()
    src_wkt = ds.GetProjection() or "EPSG:4326"
    nodata = band.GetNoDataValue()

    src = osr.SpatialReference()
    src.ImportFromWkt(src_wkt)
    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    wgs = osr.SpatialReference()
    wgs.ImportFromEPSG(4326)
    wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    to_src = osr.CoordinateTransformation(wgs, src)

    bbox = outline_wgs.boundingBox()
    corners = [
        (bbox.xMinimum(), bbox.yMinimum()),
        (bbox.xMinimum(), bbox.yMaximum()),
        (bbox.xMaximum(), bbox.yMinimum()),
        (bbox.xMaximum(), bbox.yMaximum()),
    ]
    xs, ys = [], []
    for lon, lat in corners:
        x, y, _ = to_src.TransformPoint(lon, lat)
        xs.append(x)
        ys.append(y)
    # pad one cell
    px, py = abs(gt[1]), abs(gt[5])
    xmin, xmax = min(xs) - px, max(xs) + px
    ymin, ymax = min(ys) - py, max(ys) + py

    # pixel window
    col0 = int(math.floor((xmin - gt[0]) / gt[1]))
    col1 = int(math.ceil((xmax - gt[0]) / gt[1]))
    row0 = int(math.floor((ymax - gt[3]) / gt[5]))  # gt[5] negative
    row1 = int(math.ceil((ymin - gt[3]) / gt[5]))
    col0 = max(0, col0)
    row0 = max(0, row0)
    col1 = min(ds.RasterXSize, col1)
    row1 = min(ds.RasterYSize, row1)
    if col1 <= col0 or row1 <= row0:
        raise QgsProcessingException(f"outline does not overlap raster: {path}")

    width, height = col1 - col0, row1 - row0
    data = band.ReadAsArray(col0, row0, width, height).astype(np.float64)
    if nodata is not None:
        data[data == nodata] = 0.0
    data[data < 0] = 0.0

    origin_x = gt[0] + col0 * gt[1]
    origin_y = gt[3] + row0 * gt[5]
    feedback.pushInfo(f"  {os.path.basename(path)}: {width}×{height} cells, {data.sum():,.0f} people in window")
    return data, origin_x, origin_y, gt[1], gt[5], width, height, src_wkt


def _mask_inside(origin_x, origin_y, dx, dy, width, height, src_wkt, outline_wgs) -> np.ndarray:
    """Boolean mask of cells whose centres fall inside the outline (GDAL burn)."""
    from osgeo import ogr

    src = osr.SpatialReference()
    src.ImportFromWkt(src_wkt)
    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    wgs = osr.SpatialReference()
    wgs.ImportFromEPSG(4326)
    wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    to_src = osr.CoordinateTransformation(wgs, src)

    outline_src = QgsGeometry(outline_wgs)
    outline_src.transform(QgsCoordinateTransform(
        QgsCoordinateReferenceSystem("EPSG:4326"),
        QgsCoordinateReferenceSystem(src_wkt),
        QgsProject.instance()))

    drv = gdal.GetDriverByName("MEM")
    mask_ds = drv.Create("", width, height, 1, gdal.GDT_Byte)
    mask_ds.SetGeoTransform((origin_x, dx, 0.0, origin_y, 0.0, dy))
    mask_ds.SetProjection(src_wkt)

    mem = ogr.GetDriverByName("Memory").CreateDataSource("mem")
    layer = mem.CreateLayer("aoi", srs=src, geom_type=ogr.wkbMultiPolygon)
    feat = ogr.Feature(layer.GetLayerDefn())
    feat.SetGeometry(ogr.CreateGeometryFromWkt(outline_src.asWkt()))
    layer.CreateFeature(feat)
    gdal.RasterizeLayer(mask_ds, [1], layer, burn_values=[1])
    inside = mask_ds.GetRasterBand(1).ReadAsArray().astype(bool)
    mem = None
    mask_ds = None
    _ = to_src  # kept for CRS side-effects on some GDAL builds
    return inside


def _ring_people(data, inside, origin_x, origin_y, dx, dy, width, height, src_wkt,
                 centre_lon: float, centre_lat: float, feedback) -> dict[int, float]:
    """Sum people into 100 m rings using ground distance from the centre."""
    src = osr.SpatialReference()
    src.ImportFromWkt(src_wkt)
    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    aeqd = osr.SpatialReference()
    aeqd.ImportFromWkt(_aeqd_wkt(centre_lon, centre_lat))
    aeqd.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    to_aeqd = osr.CoordinateTransformation(src, aeqd)

    rows, cols = np.nonzero(inside)
    if rows.size == 0:
        raise QgsProcessingException("no raster cells fall inside the outline")
    xs = origin_x + (cols + 0.5) * dx
    ys = origin_y + (rows + 0.5) * dy
    # transform in batches
    gx = np.empty(rows.size, dtype=float)
    gy = np.empty(rows.size, dtype=float)
    step = 100000
    for i in range(0, rows.size, step):
        j = min(i + step, rows.size)
        pts = np.column_stack([xs[i:j], ys[i:j], np.zeros(j - i)])
        out = np.array(to_aeqd.TransformPoints(pts.tolist()))
        gx[i:j] = out[:, 0]
        gy[i:j] = out[:, 1]
    dist = np.hypot(gx, gy)
    ring = (dist // RING_M).astype(np.int32)
    weights = data[rows, cols]
    people = defaultdict(float)
    for k, w in zip(ring.tolist(), weights.tolist()):
        if w > 0:
            people[int(k)] += float(w)
    feedback.pushInfo(f"  {len(people)} rings with people; farthest {max(people) * RING_M / 1000:.1f} km")
    return dict(people)


class UrbanSpreadMethod(QgsProcessingAlgorithm):
    AOI = "AOI"
    CENTRE = "CENTRE"
    RASTERS = "RASTERS"
    CITY_NAME = "CITY_NAME"
    OUT_DIR = "OUT_DIR"
    ZONES_OUT = "ZONES_OUT"

    def name(self):
        return "urban_spread_method"

    def displayName(self):
        return "Urban spread method"

    def group(self):
        return "Where the centre holds"

    def groupId(self):
        return "centre_holds"

    def shortHelpString(self):
        return (
            "Runs the urban-spread method on one city: 100 m rings around a centre, remoteness "
            "zones scaled to city size, zone shares, and the spread factor φ.\n\n"
            "Inputs: outline polygons, a centre point, and one population raster per year "
            "(name them with the year, e.g. ghs_pop_1990). Output folder gets rings.csv, "
            "zone_people.csv, summary.txt and zone_edges.gpkg. Zone-edge circles are also "
            "written to the feature sink and loaded in the project.\n\n"
            "Distance is on the ground (azimuthal equidistant). Zone cuts follow "
            "Peraza-Mues et al., arXiv:2509.16110: central r&lt;3, intermediate 3–5, "
            "distant 5–9.3, peri-urban beyond. φ is the Q–Q slope of distance percentiles "
            "between the first and last year."
        )

    def flags(self):
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading

    def createInstance(self):
        return UrbanSpreadMethod()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.AOI, "City outline (polygons; several are unioned)",
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterPoint(
            self.CENTRE, "Centre point (founding place)"))
        self.addParameter(QgsProcessingParameterMultipleLayers(
            self.RASTERS, "Population rasters, one per year (year in the layer name)",
            QgsProcessing.TypeRaster))
        self.addParameter(QgsProcessingParameterString(
            self.CITY_NAME, "City name", defaultValue="City"))
        self.addParameter(QgsProcessingParameterFolderDestination(
            self.OUT_DIR, "Output folder"))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.ZONES_OUT, "Zone-edge circles",
            type=QgsProcessing.TypeVectorPolygon, optional=True))

    def processAlgorithm(self, parameters, context, feedback):
        aoi = self.parameterAsVectorLayer(parameters, self.AOI, context)
        if aoi is None:
            raise QgsProcessingException("give a city outline")
        centre = self.parameterAsPoint(parameters, self.CENTRE, context, aoi.crs())
        rasters = self.parameterAsLayerList(parameters, self.RASTERS, context) or []
        if len(rasters) < 2:
            raise QgsProcessingException("give at least two population rasters (two years)")
        city = self.parameterAsString(parameters, self.CITY_NAME, context).strip() or "City"
        out_dir = self.parameterAsString(parameters, self.OUT_DIR, context)
        if not out_dir or out_dir == "TEMPORARY_OUTPUT":
            raise QgsProcessingException("set an output folder")
        os.makedirs(out_dir, exist_ok=True)

        # Centre to WGS84 lon/lat
        wgs = QgsCoordinateReferenceSystem("EPSG:4326")
        to_wgs = QgsCoordinateTransform(aoi.crs(), wgs, context.transformContext())
        centre_wgs = to_wgs.transform(centre)
        lon, lat = centre_wgs.x(), centre_wgs.y()
        feedback.pushInfo(f"{city}: centre at {lon:.5f}, {lat:.5f}")

        outline = _union_geom(aoi)
        if aoi.crs() != wgs:
            outline.transform(to_wgs)

        # Pair rasters with years
        pairs = []
        for i, layer in enumerate(rasters):
            path = layer.source().split("|")[0]
            year = _year_from_name(layer.name(), 1990 + 10 * i)
            pairs.append((year, path, layer.name()))
        pairs.sort(key=lambda t: t[0])
        years = [y for y, _, _ in pairs]
        feedback.pushInfo(f"years: {', '.join(str(y) for y in years)}")

        # Rings for each year (mask from first raster)
        y0, path0, _ = pairs[0]
        feedback.pushInfo(f"reading {y0}")
        data0, ox, oy, dx, dy, width, height, src_wkt = _read_masked(path0, outline, feedback)
        feedback.setProgress(10)
        feedback.pushInfo("masking cells inside the outline")
        inside = _mask_inside(ox, oy, dx, dy, width, height, src_wkt, outline)
        feedback.pushInfo(f"  {int(inside.sum()):,} cells inside")
        feedback.setProgress(30)

        rings_by_year: dict[int, dict[int, float]] = {}
        rings_by_year[y0] = _ring_people(
            data0, inside, ox, oy, dx, dy, width, height, src_wkt, lon, lat, feedback)
        feedback.setProgress(40)

        for i, (year, path, _) in enumerate(pairs[1:], start=1):
            if feedback.isCanceled():
                break
            feedback.pushInfo(f"reading {year}")
            data, ox2, oy2, dx2, dy2, w2, h2, wkt2 = _read_masked(path, outline, feedback)
            if (w2, h2) != (width, height) or abs(ox2 - ox) > abs(dx) or abs(oy2 - oy) > abs(dy):
                feedback.pushInfo("  grid differs from first year; remasking")
                inside_y = _mask_inside(ox2, oy2, dx2, dy2, w2, h2, wkt2, outline)
                rings_by_year[year] = _ring_people(
                    data, inside_y, ox2, oy2, dx2, dy2, w2, h2, wkt2, lon, lat, feedback)
            else:
                rings_by_year[year] = _ring_people(
                    data, inside, ox, oy, dx, dy, width, height, src_wkt, lon, lat, feedback)
            feedback.setProgress(40 + int(40 * i / max(1, len(pairs) - 1)))

        t0, t1 = years[0], years[-1]
        p_last = sum(rings_by_year[t1].values())
        if p_last <= 0:
            raise QgsProcessingException(f"no people in {t1}")
        scale = math.sqrt(p_last)  # people; r = 1000 * s_km / sqrt(P)
        edge_km = {name: r_cut * scale / 1000.0 for name, r_cut in zip(
            ("central", "intermediate", "distant"), ZONE_EDGE_R)}

        # Zone people
        zone_people = {z[0]: {y: 0.0 for y in years} for z in ZONE_CUTS}
        for year, people in rings_by_year.items():
            for k, n in people.items():
                s_km = (k + 0.5) * RING_M / 1000.0
                r = 1000.0 * s_km / scale
                zone_people[_zone_of(r)][year] += n

        # φ
        q0 = _quantiles_from_rings(rings_by_year[t0])
        q1 = _quantiles_from_rings(rings_by_year[t1])
        phi = _phi(q0, q1)

        # Write rings.csv
        ring_path = os.path.join(out_dir, "rings.csv")
        with open(ring_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["city", "year", "ring", "people", "distance_km", "remoteness_r", "zone"])
            for year in years:
                for k in sorted(rings_by_year[year]):
                    n = rings_by_year[year][k]
                    s_km = (k + 0.5) * RING_M / 1000.0
                    r = 1000.0 * s_km / scale
                    w.writerow([city, year, k, f"{n:.6f}", f"{s_km:.4f}", f"{r:.4f}", _zone_of(r)])

        # Write zone_people.csv
        zone_path = os.path.join(out_dir, "zone_people.csv")
        with open(zone_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["city", "zone"] + [str(y) for y in years] + ["share_first", "share_last"])
            totals = {y: sum(zone_people[z][y] for z in zone_people) for y in years}
            for zname, _, _ in ZONE_CUTS:
                row = [city, zname] + [f"{zone_people[zname][y]:.3f}" for y in years]
                s0 = zone_people[zname][t0] / totals[t0] if totals[t0] else 0.0
                s1 = zone_people[zname][t1] / totals[t1] if totals[t1] else 0.0
                row += [f"{100 * s0:.2f}", f"{100 * s1:.2f}"]
                w.writerow(row)

        # Summary
        central0 = zone_people["central"][t0]
        central1 = zone_people["central"][t1]
        share0 = 100 * central0 / totals[t0] if totals[t0] else 0.0
        share1 = 100 * central1 / totals[t1] if totals[t1] else 0.0
        growth = totals[t1] / totals[t0] if totals[t0] else float("nan")
        summary_lines = [
            f"City: {city}",
            f"Centre (WGS84): {lon:.6f}, {lat:.6f}",
            f"Years: {t0} to {t1}",
            f"People: {totals[t0]:,.0f} ({t0}) → {totals[t1]:,.0f} ({t1}); growth ×{growth:.3f}",
            f"Central zone reaches: {edge_km['central']:.1f} km",
            f"Intermediate edge: {edge_km['intermediate']:.1f} km",
            f"Distant edge: {edge_km['distant']:.1f} km",
            f"Central share: {share0:.1f}% ({t0}) → {share1:.1f}% ({t1})",
            f"Central change in people: {central1 - central0:+,.0f}",
            f"Spread factor φ ({t0}→{t1}): {phi:.4f}",
            f"  φ > 1: typical resident farther from the centre",
            f"  φ < 1: typical resident closer in",
            f"Method: 100 m rings; remoteness r = 1000 × s_km / √P{t1};",
            f"  zones central<3, intermediate 3–5, distant 5–9.3, peri-urban>9.3",
            f"  after Peraza-Mues et al. arXiv:2509.16110",
            f"Outputs: rings.csv, zone_people.csv, zone_edges.gpkg",
        ]
        summary_path = os.path.join(out_dir, "summary.txt")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write("\n".join(summary_lines) + "\n")
        for line in summary_lines:
            feedback.pushInfo(line)

        # Zone-edge circles (WGS84)
        fields = QgsFields()
        fields.append(QgsField("city", QVariant.String))
        fields.append(QgsField("zone_edge", QVariant.String))
        fields.append(QgsField("r_cut", QVariant.Double))
        fields.append(QgsField("radius_km", QVariant.Double))
        fields.append(QgsField("people_last", QVariant.Double))
        fields.append(QgsField("phi", QVariant.Double))
        fields.append(QgsField("central_share_0", QVariant.Double))
        fields.append(QgsField("central_share_1", QVariant.Double))

        sink_id = None
        sink = None
        if self.ZONES_OUT in parameters and parameters[self.ZONES_OUT] is not None:
            sink, sink_id = self.parameterAsSink(
                parameters, self.ZONES_OUT, context, fields, QgsWkbTypes.Polygon, wgs)

        edges_path = os.path.join(out_dir, "zone_edges.gpkg")
        if os.path.exists(edges_path):
            try:
                os.remove(edges_path)
            except OSError:
                pass
        edges = QgsVectorLayer("Polygon?crs=EPSG:4326", "zone_edges", "memory")
        edges_data = edges.dataProvider()
        edges_data.addAttributes(fields.toList())
        edges.updateFields()

        # Build circles in aeqd then transform to WGS84
        aeqd_crs = QgsCoordinateReferenceSystem()
        aeqd_crs.createFromWkt(_aeqd_wkt(lon, lat))
        to_wgs_aeqd = QgsCoordinateTransform(aeqd_crs, wgs, context.transformContext())
        centre_aeqd = QgsPointXY(0.0, 0.0)

        for (zname, r_cut), colour in zip(
                (("central", 3.0), ("intermediate", 5.0), ("distant", 9.3)), ZONE_EDGE_COLOURS):
            radius_m = r_cut * scale
            circ = QgsGeometry.fromPointXY(centre_aeqd).buffer(radius_m, 72)
            circ.transform(to_wgs_aeqd)
            feat = QgsFeature(fields)
            feat.setGeometry(circ)
            feat.setAttributes([
                city, zname, float(r_cut), float(radius_m / 1000.0), float(p_last),
                float(phi) if math.isfinite(phi) else None,
                float(share0), float(share1),
            ])
            edges_data.addFeature(feat)
            if sink is not None:
                sink.addFeature(feat, QgsFeature.SetActive)
            _ = colour  # colours applied when styling below

        # Save gpkg via processing-less copy: write as GeoJSON then... use QgsVectorFileWriter
        from qgis.core import QgsVectorFileWriter
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.fileEncoding = "UTF-8"
        err = QgsVectorFileWriter.writeAsVectorFormatV3(
            edges, edges_path, context.transformContext(), opts)
        if err[0] != QgsVectorFileWriter.NoError:
            feedback.pushWarning(f"could not write {edges_path}: {err}")

        # Load into project with simple styling
        project = context.project() or QgsProject.instance()
        loaded = QgsVectorLayer(edges_path, f"{city} zone edges", "ogr")
        if loaded.isValid():
            # rule-free: categorize by zone_edge
            from qgis.core import QgsCategorizedSymbolRenderer, QgsRendererCategory
            cats = []
            for zname, colour in zip(("central", "intermediate", "distant"), ZONE_EDGE_COLOURS):
                sym = QgsFillSymbol.createSimple({
                    "color": "0,0,0,0",
                    "outline_color": colour,
                    "outline_width": "0.55",
                    "outline_width_unit": "MM",
                })
                cats.append(QgsRendererCategory(zname, sym, zname.capitalize()))
            loaded.setRenderer(QgsCategorizedSymbolRenderer("zone_edge", cats))
            project.addMapLayer(loaded)

        # Centre marker
        centre_layer = QgsVectorLayer("Point?crs=EPSG:4326", f"{city} centre", "memory")
        cprov = centre_layer.dataProvider()
        cprov.addAttributes([QgsField("name", QVariant.String), QgsField("role", QVariant.String)])
        centre_layer.updateFields()
        cf = QgsFeature(centre_layer.fields())
        cf.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
        cf.setAttributes([city, "founding centre"])
        cprov.addFeature(cf)
        from qgis.core import QgsMarkerSymbol
        centre_layer.renderer().setSymbol(QgsMarkerSymbol.createSimple({
            "name": "star", "color": "#c9a66b", "size": "4", "outline_color": "#222222",
        }))
        project.addMapLayer(centre_layer)

        feedback.setProgress(100)
        results = {"OUTPUT_FOLDER": out_dir, "RINGS": ring_path, "ZONES": zone_path,
                   "SUMMARY": summary_path, "EDGES": edges_path, "PHI": phi}
        if sink_id:
            results[self.ZONES_OUT] = sink_id
        return results

