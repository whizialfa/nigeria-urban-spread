"""Review sheets: each chosen centre on a street basemap, with the central-zone circle and the 1975 built-up peak."""

from __future__ import annotations

from pathlib import Path

import contextily as cx
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from scipy.ndimage import uniform_filter
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "ghsl"
PROCESSED = ROOT / "data" / "processed"
MAPS = ROOT / "maps"
FOUNDING = ("Lagos", "Kano", "Ibadan", "Port Harcourt", "Abuja")
LOSERS = 8


def _peak(uc: int, outline) -> Point:
    with rasterio.open(RAW / f"{uc}_built_1975.tif") as src:
        built, transform = src.read(1).astype("float64"), src.transform
    built[built < 0] = 0
    inside = geometry_mask([outline], out_shape=built.shape, transform=transform, invert=True)
    smooth = uniform_filter(built, size=11, mode="constant")
    smooth[~inside] = -1
    row, col = np.unravel_index(np.argmax(smooth), smooth.shape)
    return Point(*(transform * (col + 0.5, row + 0.5)))


def _sheet(ids: list[int], title: str, out: Path) -> None:
    centres = gpd.read_file(PROCESSED / "centres.gpkg").set_index("ID_UC_G0")
    outlines = gpd.read_file(PROCESSED / "ng_urban_centres.gpkg").set_index("ID_UC_G0")
    zones = pd.read_csv(PROCESSED / "zone_people.csv").query("zone == 'central'").set_index("ID_UC_G0")
    totals = pd.read_csv(PROCESSED / "rings.csv.gz").query("year == 2020").groupby("ID_UC_G0")["people"].sum()
    cols = 4
    rows = -(-len(ids) // cols)
    fig, axes = plt.subplots(rows, cols, figsize=(4.6 * cols, 4.8 * rows))
    for ax in axes.flat[len(ids):]:
        ax.remove()
    for ax, uc in zip(axes.flat, ids):
        c = centres.loc[uc].geometry
        radius = 3 * np.sqrt(totals[uc])
        view = max(radius * 1.8, 3000)
        gpd.GeoSeries([outlines.loc[uc].geometry], crs="ESRI:54009").boundary.plot(ax=ax, color="#555", lw=0.8)
        gpd.GeoSeries([c.buffer(radius)], crs="ESRI:54009").boundary.plot(ax=ax, color="#d7301f", lw=1.4)
        peak = _peak(uc, outlines.loc[uc].geometry)
        ax.plot(peak.x, peak.y, "o", ms=9, mfc="none", mec="#2166ac", mew=2)
        ax.plot(c.x, c.y, "*", ms=14, color="#d7301f", mec="white")
        ax.set_xlim(c.x - view, c.x + view)
        ax.set_ylim(c.y - view, c.y + view)
        cx.add_basemap(ax, crs="ESRI:54009", source=cx.providers.Esri.WorldStreetMap, attribution=False)
        z = zones.loc[uc]
        ax.set_title(f"{centres.at[uc, 'name']}  (central {z['1990'] / 1e3:,.0f}k \u2192 {z['2020'] / 1e3:,.0f}k)",
                     fontsize=10)
        ax.set_axis_off()
    fig.suptitle(f"{title}\nred star: centre used; red circle: central zone (r < 3); blue ring: peak of 1975 built-up",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(out)


def main() -> None:
    centres = gpd.read_file(PROCESSED / "centres.gpkg").set_index("ID_UC_G0")
    zones = pd.read_csv(PROCESSED / "zone_people.csv").query("zone == 'central'").set_index("ID_UC_G0")
    founding = [centres.index[centres["name"] == n][0] for n in FOUNDING]
    panel = centres.index[centres["born"] <= 1990]
    change = (zones["2020"] - zones["1990"]).loc[panel].sort_values()
    MAPS.mkdir(exist_ok=True)
    _sheet(founding, "Founding points", MAPS / "centre_check_founding.png")
    _sheet(list(change.index[:LOSERS]), "Largest central losses, 1990 to 2020", MAPS / "centre_check_losers.png")


if __name__ == "__main__":
    main()
