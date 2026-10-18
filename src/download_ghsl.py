"""GHS-POP (1990, 2000, 2010, 2020), GHS-BUILT-S (1975) and WorldPop (2000, 2010, 2020) for every Nigerian
urban centre, on the native GHSL 100 m Mollweide grid."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import ee
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import Affine

ROOT = Path(__file__).resolve().parents[1]
CENTRES = ROOT / "data" / "processed" / "ng_urban_centres.gpkg"
OUT = ROOT / "data" / "raw" / "ghsl"
PROJECT = "cursor-511322"
MARGIN = 2000
LAYERS = {
    **{f"pop_{y}": ("JRC/GHSL/P2023A/GHS_POP", str(y), "population_count") for y in (1990, 2000, 2010, 2020)},
    "built_1975": ("JRC/GHSL/P2023A/GHS_BUILT_S", "1975", "built_surface"),
    **{f"wp_{y}": ("WorldPop/GP/100m/pop", y, "population") for y in (2000, 2010, 2020)},
}


def _image(collection: str, index, band: str) -> ee.Image:
    if collection.startswith("WorldPop"):
        # WorldPop counts sit on a 3 arc-second grid: resample as density so a 100 m cell gets its share.
        img = (ee.ImageCollection(collection).filter(ee.Filter.eq("country", "NGA"))
               .filter(ee.Filter.eq("year", index)).first().select(band))
        area = ee.Image.pixelArea().reproject(img.projection())
        return img.divide(area).resample("bilinear").multiply(10_000)
    return ee.ImageCollection(collection).filter(ee.Filter.eq("system:index", index)).first().select(band)


def _fetch(uc_id: int, bounds, name: str, crs_wkt: str) -> str:
    dest = OUT / f"{uc_id}_{name}.tif"
    if dest.exists():
        return "skip"
    x0, y0, x1, y1 = bounds
    x0, y0 = (x0 - MARGIN) // 100 * 100, (y0 - MARGIN) // 100 * 100
    x1, y1 = -(-(x1 + MARGIN) // 100) * 100, -(-(y1 + MARGIN) // 100) * 100
    request = {
        "expression": _image(*LAYERS[name]).toFloat(),
        "fileFormat": "NUMPY_NDARRAY",
        "grid": {
            "dimensions": {"width": int((x1 - x0) / 100), "height": int((y1 - y0) / 100)},
            "affineTransform": {"scaleX": 100, "shearX": 0, "translateX": x0,
                                "shearY": 0, "scaleY": -100, "translateY": y1},
            "crsWkt": crs_wkt,
        },
    }
    error = ""
    for attempt in range(4):
        try:
            arr = ee.data.computePixels(request)
            band = np.asarray(arr[arr.dtype.names[0]], dtype="float32")
            profile = {"driver": "GTiff", "width": band.shape[1], "height": band.shape[0], "count": 1,
                       "dtype": "float32", "crs": "ESRI:54009", "transform": Affine(100, 0, x0, 0, -100, y1),
                       "compress": "deflate", "nodata": -200}
            with rasterio.open(dest, "w", **profile) as out:
                out.write(band, 1)
            return "ok"
        except Exception as exc:
            error = str(exc)
            time.sleep(5 * (attempt + 1))
    return f"fail {error[:200]}"


def main() -> None:
    ee.Initialize(project=PROJECT)
    OUT.mkdir(parents=True, exist_ok=True)
    crs_wkt = _image(*LAYERS["pop_1990"]).projection().wkt().getInfo()
    args = sys.argv[1:]
    country = args.pop(0) if args and not args[0].isdigit() else "ng"
    centres = gpd.read_file(CENTRES if country == "ng" else CENTRES.with_name(f"{country}_urban_centres.gpkg"))
    layers = [n for n in LAYERS if country == "ng" or country.startswith("lga") or not n.startswith("wp_")]
    only = {int(a) for a in args}
    if only:
        centres = centres[centres.ID_UC_G0.isin(only)]
    jobs = [(int(r.ID_UC_G0), r.geometry.bounds, name) for r in centres.itertuples() for name in layers]
    t0 = time.time()
    counts = {"ok": 0, "skip": 0, "fail": 0}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch, uc, b, name, crs_wkt): (uc, name) for uc, b, name in jobs}
        for i, fut in enumerate(as_completed(futures), 1):
            status = fut.result()
            counts[status.split()[0]] += 1
            if status.startswith("fail"):
                print("FAIL", *futures[fut], status, flush=True)
            if i % 100 == 0 or i == len(jobs):
                print(f"{i}/{len(jobs)} {counts} {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
