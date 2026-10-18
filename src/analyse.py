"""Zones, expansion factors, the scaling model and the counterfactual, following the anchor's equations.

    python analyse.py            GHS-POP 1990-2020 (headline)
    python analyse.py ghs2000    GHS-POP 2000-2020 (like-for-like with WorldPop)
    python analyse.py worldpop   WorldPop 2000-2020 (robustness)
    python analyse.py mx         Mexico, GHS-POP 1990-2020 (can GHS-POP see the anchor's central loss?)
    python analyse.py lga        Five LGA cities, GHS-POP 1990-2020 (the study)
    python analyse.py lga_worldpop  Five LGA cities, WorldPop 2000-2020
"""

from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
SOURCES = {
    "ghs": ("rings.csv.gz", (1990, 2000, 2010, 2020), ""),
    "ghs2000": ("rings.csv.gz", (2000, 2010, 2020), "_ghs2000"),
    "worldpop": ("rings_worldpop.csv.gz", (2000, 2010, 2020), "_worldpop"),
    "mx": ("rings_mx.csv.gz", (1990, 2000, 2010, 2020), "_mx"),
    "lga": ("rings_lga.csv.gz", (1990, 2000, 2010, 2020), "_lga"),
    "lga_ghs2000": ("rings_lga.csv.gz", (2000, 2010, 2020), "_lga_ghs2000"),
    "lga_worldpop": ("rings_lga_worldpop.csv.gz", (2000, 2010, 2020), "_lga_worldpop"),
}
CENTRES = {"mx": "centres_mx.gpkg", "lga": "centres_lga.gpkg"}
PANEL_BORN = 1990
RING = 100.0
ZONES = [("central", 0, 3), ("intermediate", 3, 5), ("distant", 5, 9.3), ("peri-urban", 9.3, np.inf)]
NAMED = {
    "ng": ("Lagos", "Kano", "Ibadan", "Port Harcourt", "Abuja"),
    "mx": ("Mexico City", "Guadalajara", "Monterrey", "Puebla"),
    "lga": ("Lagos", "Kano", "Ibadan", "Kaduna", "Onitsha"),
}
QUANTILES = np.linspace(0.01, 0.99, 99)
BOOT = 2000


def _profiles(rings_file: str, years: tuple[int, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rings = pd.read_csv(PROCESSED / rings_file)
    rings = rings[rings["year"].isin(years)].copy()
    rings["s"] = (rings["ring"] + 0.5) * RING
    totals = rings.groupby(["ID_UC_G0", "year"])["people"].sum().unstack("year")
    rings = rings.join(totals[2020].rename("P2020"), on="ID_UC_G0")
    rings["r"] = 1000 * (rings["s"] / 1000) / np.sqrt(rings["P2020"])
    return rings, totals


def _zone_table(rings: pd.DataFrame) -> pd.DataFrame:
    labels = [z[0] for z in ZONES]
    edges = [z[1] for z in ZONES] + [np.inf]
    rings = rings.assign(zone=pd.cut(rings["r"], edges, right=False, labels=labels))
    return rings.groupby(["ID_UC_G0", "zone", "year"], observed=False)["people"].sum().unstack("year")


def _quantiles(sub: pd.DataFrame) -> np.ndarray:
    sub = sub.sort_values("ring")
    upper = (sub["ring"].to_numpy() + 1) * RING
    cum = np.cumsum(sub["people"].to_numpy())
    cum = cum / cum[-1]
    return np.interp(QUANTILES, np.concatenate([[0], cum]), np.concatenate([[0], upper]))


def _phis(rings: pd.DataFrame, years: tuple[int, ...]) -> pd.DataFrame:
    q = {key: _quantiles(g) for key, g in rings.groupby(["ID_UC_G0", "year"])}
    out = []
    for uc in rings["ID_UC_G0"].unique():
        for ti, tj in combinations(years, 2):
            a, b = q.get((uc, ti)), q.get((uc, tj))
            if a is None or b is None:
                continue
            phi = float(np.dot(a, b) / np.dot(a, a))
            out.append((uc, ti, tj, phi))
    return pd.DataFrame(out, columns=["ID_UC_G0", "ti", "tj", "phi"])


def _fit(df: pd.DataFrame) -> tuple[float, float]:
    x = np.column_stack([np.log(df["growth"]), df["tj"] - df["ti"]])
    beta, alpha = np.linalg.lstsq(x, np.log(df["phi"]), rcond=None)[0]
    return float(beta), float(alpha)


def main() -> None:
    source = sys.argv[1] if len(sys.argv) > 1 else "ghs"
    rings_file, years, suffix = SOURCES[source]
    t0, t1 = years[0], years[-1]
    country = source.split("_")[0] if source.split("_")[0] in CENTRES else "ng"
    centres = gpd.read_file(PROCESSED / CENTRES.get(country, "centres.gpkg")).set_index("ID_UC_G0")
    rings, totals = _profiles(rings_file, years)
    panel = centres.index[(centres["born"] <= PANEL_BORN)].intersection(totals.index[totals[t0] > 0])

    zones = _zone_table(rings)
    zones.to_csv(PROCESSED / f"zone_people{suffix}.csv")
    zp = zones.loc[zones.index.get_level_values(0).isin(panel)].groupby(level="zone", observed=False).sum()
    zshare = zp / zp.sum()
    central = zones.xs("central", level="zone").loc[panel]
    lost = central[t1] < central[t0]

    phis = _phis(rings, years)
    phis["growth"] = [totals.at[uc, tj] / totals.at[uc, ti] for uc, ti, tj in phis[["ID_UC_G0", "ti", "tj"]].itertuples(index=False)]
    phis = phis[(phis["growth"] > 0) & np.isfinite(phis["growth"]) & (phis["phi"] > 0)]
    phis.to_csv(PROCESSED / f"expansion_factors{suffix}.csv", index=False)
    all_phis = phis
    phis = phis[phis["ID_UC_G0"].isin(panel)]
    beta, alpha = _fit(phis)
    rng = np.random.default_rng(7)
    cities = phis["ID_UC_G0"].unique()
    groups = {uc: g for uc, g in phis.groupby("ID_UC_G0")}
    boots = np.array([_fit(pd.concat([groups[c] for c in rng.choice(cities, cities.size)])) for _ in range(BOOT)])
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)

    growth = (totals.loc[panel, t1] / totals.loc[panel, t0]).mean()
    ratio = growth ** (beta - 0.5) * np.exp(alpha * (t1 - t0))

    named = []
    for name in NAMED[country]:
        hit = centres.index[centres["name"] == name]
        if hit.empty:
            continue
        uc = hit[0]
        z = zones.loc[uc]
        phi_span = all_phis.query("ID_UC_G0 == @uc and ti == @t0 and tj == @t1")["phi"]
        named.append({
            "city": name, "centre": centres.at[uc, "how"], "born": centres.at[uc, "born"],
            f"people_{t0}": round(totals.at[uc, t0]), f"people_{t1}": round(totals.at[uc, t1]),
            f"central_{t0}": round(z.at["central", t0]), f"central_{t1}": round(z.at["central", t1]),
            f"central_share_{t0}": z.at["central", t0] / z[t0].sum(),
            f"central_share_{t1}": z.at["central", t1] / z[t1].sum(),
            f"phi_{t0}_{t1}": float(phi_span.iloc[0]) if len(phi_span) else np.nan,
        })
    named = pd.DataFrame(named)
    if country == "lga":
        national = pd.read_csv(PROCESSED / f"summary{suffix.removeprefix('_lga')}.csv", index_col=0)["value"]
        nb, na = float(national["beta"]), float(national["alpha"])
        growth_c = named[f"people_{t1}"] / named[f"people_{t0}"]
        named["phi_national_fit"] = np.exp(nb * np.log(growth_c) + na * (t1 - t0))
    named.to_csv(PROCESSED / f"named_cities{suffix}.csv", index=False)

    summary = {
        "source": source,
        "panel_cities": len(panel),
        "all_cities": len(centres),
        f"people_{t0}": totals.loc[panel, t0].sum(),
        f"people_{t1}": totals.loc[panel, t1].sum(),
        **{f"{z}_change": zp.at[z, t1] - zp.at[z, t0] for z in zp.index},
        **{f"{z}_share_{t0}": zshare.at[z, t0] for z in zshare.index},
        **{f"{z}_share_{t1}": zshare.at[z, t1] for z in zshare.index},
        "cities_central_loss": int(lost.sum()),
        "beta": beta, "beta_lo": lo[0], "beta_hi": hi[0],
        "alpha": alpha, "alpha_lo": lo[1], "alpha_hi": hi[1],
        f"mean_growth_{t0}_{t1}": growth,
        "distance_ratio": ratio,
    }
    pd.Series(summary).to_csv(PROCESSED / f"summary{suffix}.csv", header=["value"])
    print(pd.Series(summary).to_string())
    print(pd.DataFrame(named).to_string())


if __name__ == "__main__":
    main()
