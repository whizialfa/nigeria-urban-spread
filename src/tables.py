"""Tables quoted in the paper: zone shares by year, the central share by city size, and the cities whose centre lost people."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
BANDS = [0, 1e5, 2.5e5, 1e6, 1e8]
BAND_LABELS = ["under 100,000", "100,000 to 250,000", "250,000 to 1 million", "over 1 million"]


def _panel(zone_file: str, centres_file: str) -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    zones = pd.read_csv(PROCESSED / zone_file)
    centres = gpd.read_file(PROCESSED / centres_file)
    return zones[zones["ID_UC_G0"].isin(centres.loc[centres["born"] <= 1990, "ID_UC_G0"])], centres


def main() -> None:
    zones, centres = _panel("zone_people.csv", "centres.gpkg")
    years = [c for c in zones.columns if c.isdigit()]
    totals = zones.groupby("zone")[years].sum()
    shares = (totals / totals.sum() * 100).round(1)
    shares.join((totals["2020"] - totals["1990"]).rename("change_1990_2020")).to_csv(PROCESSED / "zone_shares.csv")

    central = zones[zones["zone"] == "central"].set_index("ID_UC_G0")
    people = zones.groupby("ID_UC_G0")[years].sum()
    city = pd.DataFrame({
        "central_share_1990": central["1990"] / people["1990"] * 100,
        "central_share_2020": central["2020"] / people["2020"] * 100,
        "central_1990": central["1990"], "central_2020": central["2020"], "people_2020": people["2020"],
    }).join(centres.set_index("ID_UC_G0")["name"])
    city["share_change"] = city["central_share_2020"] - city["central_share_1990"]
    city["central_change"] = city["central_2020"] - city["central_1990"]
    city["size"] = pd.cut(city["people_2020"], BANDS, labels=BAND_LABELS)
    city.round(2).to_csv(PROCESSED / "city_central_share.csv")
    by_size = city.groupby("size", observed=True).agg(
        cities=("share_change", "size"), median_change_points=("share_change", "median"),
        fell=("share_change", lambda s: int((s < 0).sum())), lost_people=("central_change", lambda s: int((s < 0).sum())))
    by_size.round(1).to_csv(PROCESSED / "share_by_size.csv")
    city[city["central_change"] < 0].sort_values("central_change").round(0).to_csv(PROCESSED / "central_losers.csv")
    print(shares, by_size.round(1), sep="\n\n")


if __name__ == "__main__":
    main()
