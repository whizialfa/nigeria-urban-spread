"""Layers for the QGIS plates: change rasters, zone circles, outlines, place names and the locator."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from scipy import ndimage
from shapely.geometry import Point, box

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUT = PROCESSED / "plates"
PLACES = ROOT.parent / "15-min-cities-nigeria" / "data" / "raw"
CITIES = {"lagos": "Lagos", "kano": "Kano", "ibadan": "Ibadan", "port_harcourt": "Port Harcourt", "abuja": "Abuja"}
ZONE_EDGES = (("central", 3.0), ("intermediate", 5.0), ("distant", 9.3))
LABEL_NAMES = {"Aboh": "Aboh Mbaise"}


def _change(uc: int, outline, slug: str, name: str = "") -> None:
    with rasterio.open(RAW / "ghsl" / f"{uc}_pop_1990.tif") as a, rasterio.open(RAW / "ghsl" / f"{uc}_pop_2020.tif") as b:
        p90, p20, profile = a.read(1), b.read(1), a.profile
    p90[p90 < 0] = 0
    p20[p20 < 0] = 0
    change = (p20 - p90).astype("float32")
    inside = geometry_mask([outline], out_shape=change.shape, transform=profile["transform"], invert=True)
    change[~inside] = -9999
    profile.update(nodata=-9999, dtype="float32", compress="deflate")
    with rasterio.open(OUT / f"{name or slug + '_change'}.tif", "w", **profile) as dst:
        dst.write(change, 1)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    outlines = gpd.read_file(PROCESSED / "ng_urban_centres.gpkg")
    centres = gpd.read_file(PROCESSED / "centres.gpkg").set_index("name")
    rings = pd.read_csv(PROCESSED / "rings.csv.gz").query("year == 2020")
    p2020 = rings.groupby("ID_UC_G0")["people"].sum()

    zone_rows, centre_rows = [], []
    for slug, name in CITIES.items():
        uc = int(centres.at[name, "ID_UC_G0"])
        outline = outlines.loc[outlines["ID_UC_G0"] == uc].geometry.iloc[0]
        gpd.GeoDataFrame({"name": [name]}, geometry=[outline], crs=outlines.crs).to_file(
            OUT / f"{slug}_outline.gpkg", layer=f"{slug}_outline", driver="GPKG")
        _change(uc, outline, slug)
        point = centres.at[name, "geometry"]
        label = centres.at[name, "how"].split(": ", 1)[-1].replace(" (planned origin)", "")
        centre_rows.append({"slug": slug, "name": label, "geometry": point})
        lonlat = gpd.GeoSeries([point], crs=outlines.crs).to_crs(4326).iloc[0]
        ground = f"+proj=aeqd +lat_0={lonlat.y} +lon_0={lonlat.x} +datum=WGS84 +units=m"
        for zone, r in ZONE_EDGES:
            radius = r * np.sqrt(p2020[uc])
            circle = gpd.GeoSeries([Point(0, 0).buffer(radius, 256).boundary], crs=ground).to_crs(outlines.crs)
            zone_rows.append({"slug": slug, "zone": zone, "km": radius / 1000, "geometry": circle.iloc[0]})
        places = gpd.read_file(PLACES / f"{slug}_osm_places.geojson").to_crs(outlines.crs)
        places = places[places.within(outline.buffer(2000)) & places["name"].notna()]
        main = places[places["place"].isin(["suburb", "town", "city", "quarter"])]
        places = main if len(main) >= 25 else places[places["place"] != "village"]
        places[["name", "place", "geometry"]].to_file(OUT / f"{slug}_places.gpkg", layer=f"{slug}_places",
                                                      driver="GPKG")
        print(slug, uc, f"{p2020[uc]:,.0f} people 2020, central radius {3 * np.sqrt(p2020[uc]) / 1000:.1f} km,",
              len(places), "places")
    gpd.GeoDataFrame(zone_rows, crs=outlines.crs).to_file(OUT / "zone_circles.gpkg", layer="zone_circles",
                                                         driver="GPKG")
    gpd.GeoDataFrame(centre_rows, crs=outlines.crs).to_file(OUT / "city_centres.gpkg", layer="city_centres",
                                                           driver="GPKG")

    named = centres.loc[list(CITIES.values())].reset_index()[["name", "geometry"]]
    gpd.GeoDataFrame(named, crs=outlines.crs).to_crs(4326).to_file(OUT / "named_cities.gpkg",
                                                                   layer="named_cities", driver="GPKG")


TOP5 = {"lagos": "Lagos", "kano": "Kano", "ibadan": "Ibadan", "kaduna": "Kaduna", "onitsha": "Onitsha"}


def _round_break(value: float) -> float:
    if value < 10:
        return float(max(1, round(value)))
    step = 10 ** (len(str(int(value))) - 1) / 2
    return float(round(value / step) * step)


EMPTY_PER_HA = 1.0


def _write_core(slug: str, code: np.ndarray, profile: dict, lonlat: tuple[float, float]) -> None:
    """Box around the main built-up cluster and the centre, for the plate's core inset."""
    dense = (code != 255) & (code != 0)
    clusters, _ = ndimage.label(ndimage.binary_dilation(dense, iterations=3))
    sizes = np.bincount(clusters[dense])
    sizes[0] = 0
    rows, cols = np.nonzero(dense & (clusters == sizes.argmax()))
    r0, r1 = np.percentile(rows, [5, 95])
    c0, c1 = np.percentile(cols, [5, 95])
    pad = 0.08 * max(r1 - r0, c1 - c0)
    t = profile["transform"]
    lon, lat = lonlat
    cx, cy = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(profile["crs"]).iloc[0].coords[0]
    cc, cr = ~t * (cx, cy)
    r0, r1, c0, c1 = min(r0, cr - pad), max(r1, cr + pad), min(c0, cc - pad), max(c1, cc + pad)
    xs = [t.c + t.a * c for c in (c0 - pad, c1 + 1 + pad)]
    ys = [t.f + t.e * r for r in (r0 - pad, r1 + 1 + pad)]
    core = box(min(xs), min(ys), max(xs), max(ys))
    gpd.GeoDataFrame({"slug": [slug]}, geometry=[core], crs=profile["crs"]).to_crs(4326).to_file(
        OUT / f"{slug}_core.gpkg", driver="GPKG")


def _people_grids(rec, slug: str, lonlat: tuple[float, float]) -> list[float]:
    """GHS-POP and WorldPop 2020 cut to the study outline, and one set of Jenks cuts fitted to both."""
    import mapclassify

    values = []
    for source, layer in (("ghspop", "pop_2020"), ("worldpop", "wp_2020")):
        with rasterio.open(RAW / "ghsl" / f"{rec['ID_UC_G0']}_{layer}.tif") as src:
            band, profile = src.read(1), src.profile
            inside = geometry_mask([rec.geometry], out_shape=band.shape, transform=src.transform, invert=True)
        band = np.where(band < 0, 0, band).astype("float32")
        band[~inside] = -9999
        values.append(band[inside])
        profile.update(nodata=-9999, dtype="float32", compress="deflate")
        with rasterio.open(OUT / f"{slug}_{source}_2020.tif", "w", **profile) as dst:
            dst.write(band, 1)
    pooled = np.concatenate(values)
    sample = np.random.default_rng(0).choice(pooled, size=min(len(pooled), 40_000), replace=False)
    cuts = sorted({_round_break(b) for b in mapclassify.NaturalBreaks(sample, k=3).bins[:-1]})
    (OUT / f"{slug}_people_breaks.txt").write_text(",".join(f"{c:g}" for c in cuts))

    grids = []
    for source in ("ghspop", "worldpop"):
        with rasterio.open(OUT / f"{slug}_{source}_2020.tif") as src:
            grids.append(src.read(1))
            profile = src.profile
    ghs, wp = grids
    code = (3 * np.digitize(ghs, cuts) + np.digitize(wp, cuts)).astype("uint8")
    code[ghs == -9999] = 255
    code[(ghs < EMPTY_PER_HA) & (wp < EMPTY_PER_HA)] = 255
    profile.update(dtype="uint8", nodata=255)
    _write_core(slug, code, profile, lonlat)
    with rasterio.open(OUT / f"{slug}_bivariate_2020.tif", "w", **profile) as dst:
        dst.write(code, 1)
    inside = code != 255
    agree = (np.digitize(ghs, cuts) == np.digitize(wp, cuts))[inside].mean()
    print(f"  {slug}: the two grids put a hectare in the same class {agree:.0%} of the time")
    return cuts


def study_city(slug: str, rec, members, lga: gpd.GeoDataFrame, lonlat: tuple[float, float], label: str) -> dict:
    """Outline, in-city LGAs, clipped grids, core box and centre for one study-area plate.

    `rec` needs ID_UC_G0, GC_UCN_MAI_2025, state, n_lgas, km2 and a Mollweide geometry."""
    OUT.mkdir(parents=True, exist_ok=True)
    with rasterio.open(RAW / "ghsl" / f"{rec['ID_UC_G0']}_pop_2020.tif") as src:
        pop = src.read(1)
        inside = geometry_mask([rec.geometry], out_shape=pop.shape, transform=src.transform, invert=True)
    people = float(pop[inside & (pop > 0)].sum())
    geom = gpd.GeoSeries([rec.geometry], crs="ESRI:54009").to_crs(4326).iloc[0]
    gpd.GeoDataFrame({"name": [rec["GC_UCN_MAI_2025"]], "km2": [rec["km2"]], "people": [round(people)],
                      "n_lgas": [rec["n_lgas"]]}, geometry=[geom], crs=4326).to_file(
        OUT / f"{slug}_outline.gpkg", layer=f"{slug}_outline", driver="GPKG")
    near = lga[lga.intersects(geom.buffer(0.15))].copy()
    near["in_city"] = (near["shapeName"].isin(set(members)) & (near["state"] == rec["state"])).astype(int)
    near["km2"] = near.to_crs("ESRI:54009").area / 1e6
    near[["shapeName", "state", "in_city", "km2", "geometry"]].to_file(OUT / f"{slug}_lgas.gpkg",
                                                                       layer=f"{slug}_lgas", driver="GPKG")
    breaks = _people_grids(rec, slug, lonlat)
    print(f"  {slug} classes per hectare: {', '.join(f'{b:g}' for b in breaks)}")
    print(f"{slug}: {rec['n_lgas']} LGAs, {rec['km2']:,} km2, {people:,.0f} people in 2020")

    centres_file = OUT / "study_centres.gpkg"
    row = gpd.GeoDataFrame([{"slug": slug, "name": label, "geometry": Point(*lonlat)}], crs=4326)
    if centres_file.exists():
        row = pd.concat([gpd.read_file(centres_file).query("slug != @slug"), row], ignore_index=True)
    gpd.GeoDataFrame(row, crs=4326).to_file(centres_file, layer="study_centres", driver="GPKG")
    return {"people": people, "breaks": breaks}


def city_study_layers() -> None:
    """Study-area layers for each of the five largest urban centres."""
    from lga_cities import CITIES as LGA_CITIES, lgas as all_lgas
    from radial import FOUNDING

    cities = gpd.read_file(PROCESSED / "lga_urban_centres.gpkg").set_index("slug")
    lga = all_lgas()
    for slug in TOP5:
        rec = cities.loc[slug]
        lon, lat, label = FOUNDING[rec["GC_UCN_MAI_2025"]]
        study_city(slug, rec, LGA_CITIES[slug][3], lga, (lon, lat), label)


def city_result_layers() -> None:
    """For each of the five cities: people gained or lost per hectare, 1990 to 2020, inside the LGA outline, and
    the central, intermediate and distant zone edges (r = 3, 5, 9.3 times the square root of 2020 people)."""
    cities = gpd.read_file(PROCESSED / "lga_urban_centres.gpkg").set_index("slug")
    named = pd.read_csv(PROCESSED / "named_cities_lga.csv").set_index("city")
    centres = gpd.read_file(OUT / "study_centres.gpkg").set_index("slug")
    rows = []
    for slug in TOP5:
        rec = cities.loc[slug]
        _change(int(rec["ID_UC_G0"]), rec.geometry, slug, f"{slug}_change_lga")
        people = float(named.at[rec["GC_UCN_MAI_2025"], "people_2020"])
        point = centres.at[slug, "geometry"]
        ground = f"+proj=aeqd +lat_0={point.y} +lon_0={point.x} +datum=WGS84 +units=m"
        for zone, r in ZONE_EDGES:
            radius = r * np.sqrt(people)
            circle = gpd.GeoSeries([Point(0, 0).buffer(radius, 256).boundary], crs=ground).to_crs(4326)
            rows.append({"slug": slug, "zone": zone, "km": radius / 1000, "geometry": circle.iloc[0]})
        print(f"{slug}: zone edges " + ", ".join(f"{r * np.sqrt(people) / 1000:.1f}" for _, r in ZONE_EDGES) + " km")
    gpd.GeoDataFrame(rows, crs=4326).to_file(OUT / "zone_circles_lga.gpkg", layer="zone_circles_lga",
                                             driver="GPKG")


def study_layers() -> None:
    """Boundaries, the outside mask and one sized point per urban centre for the study-area plate."""
    OUT.mkdir(parents=True, exist_ok=True)
    outlines = gpd.read_file(PROCESSED / "ng_urban_centres.gpkg").set_index("ID_UC_G0")
    centres = gpd.read_file(PROCESSED / "centres.gpkg").set_index("ID_UC_G0")
    rings = pd.read_csv(PROCESSED / "rings.csv.gz").query("year == 2020")
    p2020 = rings.groupby("ID_UC_G0")["people"].sum()

    points = centres[["geometry"]].copy()
    points["name"] = [LABEL_NAMES.get(n, n) for n in outlines.loc[points.index, "GC_UCN_MAI_2025"]]
    points["people"] = p2020.reindex(points.index).round()
    points["group"] = np.where(outlines.loc[points.index, "GC_UCB_YOB_2025"] <= 1990, "panel", "younger")
    points["tier"] = np.where(points["name"].isin(CITIES.values()), "plate",
                              np.where(points["people"] >= 1_000_000, "big", "none"))
    points = points.sort_values("people", ascending=False).reset_index()
    points.to_crs(4326).to_file(OUT / "city_points.gpkg", layer="city_points", driver="GPKG")
    print(points.groupby(["group", "tier"]).size().to_string())

    states = gpd.read_file(RAW / "boundaries" / "geoBoundaries-NGA-ADM1.geojson").to_crs(4326)
    states["label"] = states["shapeName"].replace({"Abuja Federal Capital Territory": "FCT"}).str.upper()
    states[["shapeName", "label", "geometry"]].to_file(OUT / "states.gpkg", layer="states", driver="GPKG")
    nigeria = states.dissolve()[["geometry"]]
    nigeria.to_file(OUT / "nigeria.gpkg", layer="nigeria", driver="GPKG")
    lgas = gpd.read_file(RAW / "boundaries" / "geoBoundaries-NGA-ADM2.geojson").to_crs(4326)
    lgas[["shapeName", "geometry"]].to_file(OUT / "lgas.gpkg", layer="lgas", driver="GPKG")
    outside = box(-30, -40, 60, 45).difference(nigeria.geometry.iloc[0])
    gpd.GeoDataFrame(geometry=[outside], crs=4326).to_file(OUT / "outside.gpkg", layer="outside", driver="GPKG")
    world = gpd.read_file(f"zip://{RAW / 'boundaries' / 'ne_50m_admin_0_countries.zip'}")
    world[world["CONTINENT"] == "Africa"][["NAME", "geometry"]].to_file(OUT / "africa.gpkg", layer="africa",
                                                                       driver="GPKG")


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "cities"
    {"study": study_layers, "top5": city_study_layers, "results": city_result_layers}.get(mode, main)()
