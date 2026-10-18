"""Centre of each urban centre, and its people in 100 m rings around that centre.

    python radial.py            GHS-POP 1990, 2000, 2010, 2020 -> rings.csv.gz
    python radial.py worldpop   WorldPop 2000, 2010, 2020      -> rings_worldpop.csv.gz
    python radial.py mx         Mexico, GHS-POP 1990-2020      -> rings_mx.csv.gz, centres_mx.gpkg
    python radial.py lga        Five LGA cities, GHS-POP       -> rings_lga.csv.gz, centres_lga.gpkg
    python radial.py lga_worldpop  Five LGA cities, WorldPop   -> rings_lga_worldpop.csv.gz
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.features import geometry_mask
from scipy.ndimage import uniform_filter
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "ghsl"
PROCESSED = ROOT / "data" / "processed"
SOURCES = {
    "ghs": ("ng", "pop", (1990, 2000, 2010, 2020), "rings.csv.gz"),
    "worldpop": ("ng", "wp", (2000, 2010, 2020), "rings_worldpop.csv.gz"),
    "mx": ("mx", "pop", (1990, 2000, 2010, 2020), "rings_mx.csv.gz"),
    "lga": ("lga", "pop", (1990, 2000, 2010, 2020), "rings_lga.csv.gz"),
    "lga_worldpop": ("lga", "wp", (2000, 2010, 2020), "rings_lga_worldpop.csv.gz"),
}
CENTRES_OUT = {"ghs": "centres.gpkg", "mx": "centres_mx.gpkg", "lga": "centres_lga.gpkg"}
RING = 100.0
SUB = (np.arange(5) - 2) * 20.0

# Founding points (WGS84 lon, lat). Abuja's is a planned origin, not a historic core.
FOUNDING = {
    "Lagos": (3.3917, 6.4583, "Iga Idunganran, Lagos Island"),
    "Kano": (8.5197, 11.9928, "Gidan Rumfa, the Emir's palace"),
    "Ibadan": (3.9017, 7.3747, "Mapo Hill"),
    "Onitsha": (6.7982, 6.1489, "Ime-Obi Ogboza, the old palace ground of the Obi of Onitsha"),
    "Owerri": (7.0327, 5.4851, "Eke Ukwu Owerri, the ancestral market"),
    "Kaduna": (7.4363, 10.5392, "Lugard Hall, in the 1913 government district"),
    "Port Harcourt": (7.0137, 4.7676, "Port Harcourt Township waterfront"),
    "Abuja": (7.5320, 9.0650, "Three Arms Zone (planned origin)"),
    "Mexico City": (-99.1332, 19.4326, "Zocalo"),
    "Guadalajara": (-103.3468, 20.6767, "Cathedral"),
    "Monterrey": (-100.3097, 25.6667, "Macroplaza"),
    "Puebla": (-98.1983, 19.0433, "Zocalo"),
}


def _read(uc: int, name: str):
    with rasterio.open(RAW / f"{uc}_{name}.tif") as src:
        band = src.read(1).astype("float64")
        band[band < 0] = 0.0
        return band, src.transform


def _centre(uc: int, name: str, outline, inside: np.ndarray, transform) -> tuple[Point, str]:
    if name in FOUNDING:
        lon, lat, label = FOUNDING[name]
        point = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs("ESRI:54009").iloc[0]
        return point, f"founding: {label}"
    built, _ = _read(uc, "built_1975")
    smooth = uniform_filter(built, size=11, mode="constant")
    smooth[~inside] = -1
    row, col = np.unravel_index(np.argmax(smooth), smooth.shape)
    if smooth[row, col] <= 0:
        point = outline.representative_point()
        return point, "no 1975 built-up: representative point"
    x, y = transform * (col + 0.5, row + 0.5)
    return Point(x, y), "peak of 1975 built-up, 1 km smoothing"


def _ring_index(inside: np.ndarray, transform, centre: Point) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ring of every sub-point, with distance on the ground. Mollweide keeps area, not distance."""
    lon, lat = Transformer.from_crs("ESRI:54009", 4326, always_xy=True).transform(centre.x, centre.y)
    to_ground = Transformer.from_crs("ESRI:54009", f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m",
                                     always_xy=True)
    rows, cols = np.nonzero(inside)
    xs, ys = transform * (cols + 0.5, rows + 0.5)
    ks = []
    for dx in SUB:
        for dy in SUB:
            gx, gy = to_ground.transform(xs + dx, ys + dy)
            ks.append((np.hypot(gx, gy) // RING).astype(np.int32))
    return rows, cols, np.stack(ks)


def _rings(pop: np.ndarray, rows: np.ndarray, cols: np.ndarray, ks: np.ndarray) -> np.ndarray:
    weights = pop[rows, cols] / ks.shape[0]
    return np.bincount(ks.ravel(), weights=np.tile(weights, ks.shape[0]), minlength=int(ks.max()) + 1)


def main() -> None:
    source = sys.argv[1] if len(sys.argv) > 1 else "ghs"
    country, prefix, years, out_name = SOURCES[source]
    centres = gpd.read_file(PROCESSED / f"{country}_urban_centres.gpkg")
    rows_out, centre_rows = [], []
    for rec in centres.itertuples():
        uc, name, outline = int(rec.ID_UC_G0), rec.GC_UCN_MAI_2025, rec.geometry
        if not all((RAW / f"{uc}_{n}.tif").exists() for n in [f"{prefix}_{y}" for y in years] + ["built_1975"]):
            continue
        first, transform = _read(uc, f"{prefix}_{years[0]}")
        inside = geometry_mask([outline], out_shape=first.shape, transform=transform, invert=True)
        centre, how = _centre(uc, name, outline, inside, transform)
        centre_rows.append({"ID_UC_G0": uc, "name": name, "how": how, "born": int(rec.GC_UCB_YOB_2025),
                            "geometry": centre})
        rows, cols, ks = _ring_index(inside, transform, centre)
        for year in years:
            pop = first if year == years[0] else _read(uc, f"{prefix}_{year}")[0]
            counts = _rings(pop, rows, cols, ks)
            for k in np.nonzero(counts)[0]:
                rows_out.append((uc, year, int(k), float(counts[k])))
    if source in CENTRES_OUT:
        gpd.GeoDataFrame(centre_rows, crs="ESRI:54009").to_file(PROCESSED / CENTRES_OUT[source], driver="GPKG")
    rings = pd.DataFrame(rows_out, columns=["ID_UC_G0", "year", "ring", "people"])
    rings.to_csv(PROCESSED / out_name, index=False)
    print(f"{len(centre_rows)} centres, {len(rings):,} ring rows")


if __name__ == "__main__":
    main()
