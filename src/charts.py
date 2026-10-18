"""The argument in three charts: the share at the centre, five density profiles, and the two tests."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
CHARTS = ROOT / "charts"
for _path in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
    font_manager.fontManager.addfont(_path)
plt.rcParams.update({"font.family": "Arial", "font.size": 10, "pdf.fonttype": 42, "axes.spines.top": False,
                     "axes.spines.right": False})

SLATE, CLAY, SAGE, SAND, INK = "#2e4057", "#8c5e3c", "#5d7f63", "#c9a66b", "#222222"
ZONE_COLOURS = {"central": SLATE, "intermediate": "#7d8fa8", "distant": SAND, "peri-urban": "#e6dcc6"}
ZONES = list(ZONE_COLOURS)
NAMED = ("Lagos", "Kano", "Ibadan", "Port Harcourt", "Abuja")
RING = 100.0
ANCHOR_CENTRAL_CHANGE = -2.5e6
ANCHOR_SHARE = (40.0, 22.0)


def _panel_zones(zone_file: str, centres_file: str) -> pd.DataFrame:
    zones = pd.read_csv(PROCESSED / zone_file)
    centres = gpd.read_file(PROCESSED / centres_file)
    return zones[zones["ID_UC_G0"].isin(centres.loc[centres["born"] <= 1990, "ID_UC_G0"])]


def _shares(zones: pd.DataFrame) -> pd.DataFrame:
    s = zones.drop(columns="ID_UC_G0").groupby("zone").sum()
    return (s / s.sum()).loc[ZONES]


def _save(fig, name: str) -> None:
    CHARTS.mkdir(exist_ok=True)
    fig.savefig(CHARTS / f"{name}.png", dpi=200, bbox_inches="tight")
    fig.savefig(CHARTS / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    print(CHARTS / f"{name}.png")


def zone_shares() -> None:
    zones = _panel_zones("zone_people.csv", "centres.gpkg")
    shares = _shares(zones) * 100
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={"width_ratios": [1, 1.2]})
    bottom = np.zeros(shares.shape[1])
    years = [str(c) for c in shares.columns]
    for zone in ZONES:
        vals = shares.loc[zone].to_numpy()
        a.bar(years, vals, bottom=bottom, color=ZONE_COLOURS[zone], width=0.62, label=zone.capitalize())
        for x, v, b0 in zip(years, vals, bottom):
            a.text(x, b0 + v / 2, f"{v:.0f}%", ha="center", va="center", fontsize=9,
                   color="white" if zone in ("central", "intermediate") else INK)
        bottom += vals
    a.set_ylim(0, 100)
    a.set_ylabel("Share of people in the 183 cities (%)")
    a.set_title("a. Where the people of the 183 cities live", loc="left", fontweight="bold")
    a.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.08), fontsize=9)

    central = zones[zones["zone"] == "central"].set_index("ID_UC_G0")
    totals = zones.groupby("ID_UC_G0")[["1990", "2020"]].sum()
    change = (central["2020"] / totals["2020"] - central["1990"] / totals["1990"]) * 100
    b.hist(change, bins=np.arange(-45, 11, 2.5), color=SLATE, edgecolor="white")
    b.axvline(0, color=INK, lw=0.8)
    b.axvline(change.median(), color=CLAY, lw=1.6, ls="--")
    b.text(change.median() - 1, b.get_ylim()[1] * 0.92, f"median {change.median():.0f} points", ha="right",
           color=CLAY, fontsize=9)
    b.set_xlabel("Change in the central share, 1990 to 2020 (percentage points)")
    b.set_ylabel("Cities")
    b.set_title(f"b. The share fell in {int((change < 0).sum())} of {len(change)} cities", loc="left",
                fontweight="bold")
    fig.tight_layout()
    _save(fig, "zone_shares")


def density_profiles() -> None:
    rings = pd.read_csv(PROCESSED / "rings.csv.gz")
    centres = gpd.read_file(PROCESSED / "centres.gpkg").set_index("name")
    fig, axes = plt.subplots(1, 5, figsize=(15, 3.6), sharey=False)
    for ax, name in zip(axes, NAMED):
        uc = centres.at[name, "ID_UC_G0"]
        sub = rings[rings["ID_UC_G0"] == uc]
        p2020 = sub.loc[sub["year"] == 2020, "people"].sum()
        edge = 3 * np.sqrt(p2020) / 1000
        reach = 9.3 * np.sqrt(p2020) / 1000
        for year, colour in ((1990, SAND), (2020, SLATE)):
            g = sub[sub["year"] == year].set_index("ring")["people"]
            g = g.reindex(np.arange(g.index.max() + 1), fill_value=0)
            area_ha = np.pi * ((g.index + 1) ** 2 - g.index**2) * RING**2 / 1e4
            dens = (g / area_ha).rolling(5, center=True, min_periods=1).mean()
            km = (g.index + 0.5) * RING / 1000
            ax.plot(km, dens, color=colour, lw=1.6, label=str(year))
        ax.axvspan(0, edge, color=SLATE, alpha=0.07)
        ax.axvline(edge, color=SLATE, lw=0.8, ls=":")
        ax.set_xlim(0, min(reach, 30))
        ax.set_title(name, loc="left", fontweight="bold")
        ax.set_xlabel("Distance from the centre (km)")
    axes[0].set_ylabel("People per hectare")
    axes[0].legend(frameon=False)
    axes[0].text(0.03, 0.96, "shaded: central zone", transform=axes[0].transAxes, va="top", fontsize=8,
                 color=SLATE)
    fig.tight_layout()
    _save(fig, "density_profiles")


def tests() -> None:
    summ = {k: pd.read_csv(PROCESSED / f"summary{k}.csv", index_col=0)["value"] for k in ("", "_mx", "_worldpop")}
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.2, 4.8), constrained_layout=True)
    bars = [
        ("Mexico\ncensus (truth)", ANCHOR_CENTRAL_CHANGE, CLAY),
        ("Mexico\nGHS-POP (grid)", float(summ["_mx"]["central_change"]), CLAY),
        ("Nigeria\nGHS-POP", float(summ[""]["central_change"]), SLATE),
        ("Nigeria\nWorldPop 2000-20", float(summ["_worldpop"]["central_change"]), SLATE),
    ]
    for i, (label, value, colour) in enumerate(bars):
        a.bar(i, value / 1e6, color=colour, alpha=1 if i != 0 else 0.55, hatch="//" if i == 0 else None,
              edgecolor="white", width=0.62)
        a.text(i, value / 1e6 + (0.35 if value > 0 else -0.35), f"{value / 1e6:+.1f} M", ha="center",
               va="bottom" if value > 0 else "top", fontsize=9)
    a.axhline(0, color=INK, lw=0.8)
    a.set_xticks(range(len(bars)), [b_[0] for b_ in bars], fontsize=9)
    a.set_ylabel("Change in central-zone population (millions)")
    a.set_ylim(-4.2, 12.0)
    a.set_title("a. Can the grid see a known loss?", loc="left", fontweight="bold", pad=10)

    lines = [
        ("Nigeria, GHS-POP", _shares(_panel_zones("zone_people.csv", "centres.gpkg")), SLATE, "-"),
        ("Nigeria, WorldPop", _shares(_panel_zones("zone_people_worldpop.csv", "centres.gpkg")), SLATE, ":"),
        ("Mexico, GHS-POP", _shares(_panel_zones("zone_people_mx.csv", "centres_mx.gpkg")), CLAY, "-"),
    ]
    for label, shares, colour, ls in lines:
        years = shares.columns.astype(int)
        b.plot(years, shares.loc["central"] * 100, color=colour, ls=ls, lw=2, marker="o", ms=4, label=label)
    b.plot([1990, 2020], ANCHOR_SHARE, color=CLAY, ls="--", lw=1.4, marker="s", ms=5, mfc="white",
           label="Mexico, census (truth)")
    b.text(1991.0, ANCHOR_SHARE[0] + 1.2, "census start", color=CLAY, fontsize=9)
    b.set_xticks([1990, 2000, 2010, 2020])
    b.set_ylim(15, 46)
    b.set_ylabel("Share of people in central zones (%)")
    b.set_title("b. Does the share at least fall the right way?", loc="left", fontweight="bold", pad=10)
    b.legend(frameon=False, fontsize=8.5, loc="upper right", borderaxespad=0.4, labelspacing=0.45,
             handlelength=2.2, handletextpad=0.5)
    _save(fig, "tests")

CITY_IDS = {"Lagos": 9001, "Kano": 9003, "Ibadan": 9004, "Kaduna": 9009, "Onitsha": 9002}
ZONE_EDGES = (("central", 3.0, "-"), ("intermediate", 5.0, "--"), ("distant", 9.3, ":"))


# Green edges match the results plates: dark = nearest, light = farthest.
ZONE_EDGE_COLOURS = {"central": "#005a32", "intermediate": "#238b45", "distant": "#74c476"}


def city_profiles() -> None:
    """People per hectare by distance from the founding centre, 1990 and 2020, inside each city's LGAs."""
    rings = pd.read_csv(PROCESSED / "rings_lga.csv.gz")
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 7.6), constrained_layout=True)
    panels = list(axes.flat)
    for ax, (name, uc) in zip(panels, CITY_IDS.items()):
        sub = rings[rings["ID_UC_G0"] == uc]
        p2020 = sub.loc[sub["year"] == 2020, "people"].sum()
        for year, colour in ((1990, SAND), (2020, SLATE)):
            g = sub[sub["year"] == year].set_index("ring")["people"]
            g = g.reindex(np.arange(g.index.max() + 1), fill_value=0)
            area_ha = np.pi * ((g.index + 1) ** 2 - g.index**2) * RING**2 / 1e4
            dens = (g / area_ha).rolling(5, center=True, min_periods=1).mean()
            ax.plot((g.index + 0.5) * RING / 1000, dens, color=colour, lw=2.0, label=str(year))
        for zone, r, ls in ZONE_EDGES:
            ax.axvline(r * np.sqrt(p2020) / 1000, color=ZONE_EDGE_COLOURS[zone], lw=1.0, ls=ls)
        ax.axvspan(0, 3 * np.sqrt(p2020) / 1000, color=ZONE_EDGE_COLOURS["central"], alpha=0.08)
        ax.set_xlim(0, 1.08 * 9.3 * np.sqrt(p2020) / 1000)
        ax.set_ylim(bottom=0)
        ax.set_title(name, loc="left", fontweight="bold", fontsize=12, pad=8)
        ax.set_xlabel("Distance from the centre (km)")
        ax.set_ylabel("People per hectare")
        ax.tick_params(labelsize=9)
        ax.grid(axis="y", color="#e6e2da", lw=0.6)
    note = panels[5]
    note.axis("off")
    note.plot([], [], color=SAND, lw=2.0, label="1990 density")
    note.plot([], [], color=SLATE, lw=2.0, label="2020 density")
    for zone, _, ls in ZONE_EDGES:
        note.plot([], [], color=ZONE_EDGE_COLOURS[zone], lw=1.2, ls=ls, label=f"{zone.capitalize()} zone edge")
    note.legend(frameon=False, loc="center", fontsize=11, labelspacing=1.1, handlelength=2.6)
    note.text(
        0.5, 0.22,
        "Read left to right: denser near the centre,\n"
        "thinner farther out. If the slate line sits\n"
        "above the sand line near 0 km, the core filled.\n"
        "The green band is that city's central zone.\n"
        "Each panel has its own distance scale.",
        transform=note.transAxes, ha="center", va="top", fontsize=9.5, color=INK, linespacing=1.45)
    _save(fig, "city_profiles")

def city_results() -> None:
    """Zone shares in 1990 and 2020, the spread factor against the national expectation, and the WorldPop check."""
    zones = pd.read_csv(PROCESSED / "zone_people_lga.csv")
    named = pd.read_csv(PROCESSED / "named_cities_lga.csv").set_index("city")
    ghs00 = pd.read_csv(PROCESSED / "named_cities_lga_ghs2000.csv").set_index("city")
    wp00 = pd.read_csv(PROCESSED / "named_cities_lga_worldpop.csv").set_index("city")
    cities = list(CITY_IDS)
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(15.2, 5.0), gridspec_kw={"width_ratios": [1.35, 1, 1]},
                                 constrained_layout=True)

    y = np.arange(len(cities)) * 2.6
    for k, year in enumerate(("1990", "2020")):
        left = np.zeros(len(cities))
        for zone in ZONES:
            vals = []
            for name in cities:
                z = zones[zones["ID_UC_G0"] == CITY_IDS[name]].set_index("zone")[year]
                vals.append(100 * z[zone] / z.sum())
            vals = np.array(vals)
            a.barh(y + k * 1.05, vals, left=left, height=0.95, color=ZONE_COLOURS[zone],
                   label=zone.capitalize() if k == 0 else None)
            if zone == "central":
                for yy, v in zip(y + k * 1.05, vals):
                    a.text(v / 2, yy, f"{v:.0f}%", ha="center", va="center", color="white", fontsize=8.5)
            left += vals
    a.set_yticks(np.concatenate([y, y + 1.05]), [f"{n}  1990" for n in cities] + ["2020" for _ in cities],
                 fontsize=9)
    a.invert_yaxis()
    a.set_xlim(0, 100)
    a.set_xlabel("Share of the city's people (%)")
    a.set_title("a. Who lives near the centre?", loc="left", fontweight="bold", pad=10)
    a.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.45, -0.14), fontsize=9,
             columnspacing=1.0, handletextpad=0.4)

    yy = np.arange(len(cities))
    phi = named.loc[cities, "phi_1990_2020"].to_numpy()
    expect = named.loc[cities, "phi_national_fit"].to_numpy()
    for i in yy:
        b.plot([phi[i], expect[i]], [i, i], color="#b9b2a6", lw=1.2, zorder=1)
    b.scatter(expect, yy, s=60, facecolor="white", edgecolor=CLAY, lw=1.6, zorder=2,
              label="Expected (national fit)")
    b.scatter(phi, yy, s=60, color=SLATE, zorder=3, label="Observed")
    b.axvline(1, color=INK, lw=0.8)
    b.set_yticks(yy, cities)
    b.set_ylim(len(cities) - 0.4, -0.9)
    b.text(1.01, -0.55, "1.0 = no outward shift", fontsize=8, color=INK, va="center")
    b.set_xlim(0.9, 1.25)
    b.set_xlabel("Spread factor \u03c6, 1990 to 2020")
    b.set_title("b. Did people move outward?", loc="left", fontweight="bold", pad=10)
    b.legend(frameon=False, fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2,
             columnspacing=1.2, handletextpad=0.4)

    pts = [("GHS-POP", ghs00, SLATE, "o"), ("WorldPop", wp00, CLAY, "s")]
    for j, (label, df, colour, marker) in enumerate(pts):
        change = (100 * (df.loc[cities, "central_share_2020"] - df.loc[cities, "central_share_2000"])).reindex(cities)
        c.scatter(change.to_numpy(), yy + (j - 0.5) * 0.28, s=50, color=colour, marker=marker, label=label,
                  zorder=3)
        for i, name in enumerate(cities):
            v = float(change.loc[name])
            # Keep value labels off the markers and off each other (GHS above / WorldPop below).
            dy = 0.14 if j == 0 else -0.14
            c.text(v, i + (j - 0.5) * 0.28 + dy, f"{v:+.1f}", ha="center", va="bottom" if j == 0 else "top",
                   fontsize=7.5, color=colour)
    c.axvline(0, color=INK, lw=0.8)
    c.set_yticks(yy, cities)
    c.invert_yaxis()
    c.set_xlabel("Change in the central share, 2000 to 2020 (points)")
    c.set_title("c. Do two grids agree?", loc="left", fontweight="bold", pad=10)
    c.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2,
             columnspacing=1.2, handletextpad=0.4)
    _save(fig, "city_results")

if __name__ == "__main__":
    import sys

    jobs = {"zone_shares": zone_shares, "density_profiles": density_profiles, "tests": tests,
            "city_profiles": city_profiles, "city_results": city_results}
    for job in sys.argv[1:] or jobs:
        jobs[job]()
