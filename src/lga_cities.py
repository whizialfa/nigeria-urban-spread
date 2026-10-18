"""The five largest Nigerian cities by people in 2020, each drawn as the local government areas that make it up.

Lagos is all twenty LGAs of Lagos State, so Ikorodu and the Lekki corridor are inside. Kano is the eight
metropolitan LGAs plus the eight that border them, because the metropolitan ones stop 17 km from the palace,
short of the outer zones. Ibadan is all eleven metropolitan LGAs, not
the core five, because the city grew into the outer six. Kaduna is its four metropolitan LGAs; Chikun and Igabi
hold Narayi, Sabon Tasha and Rigasa. Onitsha is the five LGAs of the built-up Greater Onitsha in UN-Habitat's
structure plan. `rank` writes every centre GHSL put over a million people, so the five can be checked."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "boundaries"
OUT = ROOT / "data" / "processed" / "lga_urban_centres.gpkg"

CITIES = {
    "lagos": (9001, "Lagos", "Lagos", (
        "Agege", "Ajeromi/Ifelodun", "Alimosho", "Amuwo Odofin", "Apapa", "Badagry", "Epe", "Eti Osa", "Ibeju Lekki",
        "Ifako/Ijaye", "Ikeja", "Ikorodu", "Kosofe", "Lagos Island", "Lagos Mainland", "Mushin", "Ojo", "Oshodi/Isolo",
        "Shomolu", "Surulere")),
    "onitsha": (9002, "Onitsha", "Anambra", (
        "Onitsha North", "Onitsha South", "Idemili North", "Ogbaru", "Oyi")),
    "kano": (9003, "Kano", "Kano", (
        "Dala", "Fagge", "Gwale", "Kano Municipal", "Kumbotso", "Nassarawa", "Tarauni", "Ungogo",
        "Dawakin Kudu", "Dawakin Tofa", "Gezawa", "Madobi", "Minjibir", "Rimin Gado", "Tofa", "Warawa")),
    "ibadan": (9004, "Ibadan", "Oyo", (
        "Ibadan North", "Ibadan North East", "Ibadan North West", "Ibadan South East", "Ibadan South West",
        "Akinyele", "Egbeda", "Ido", "Lagelu", "Oluyole", "Ona Ara")),
    "kaduna": (9009, "Kaduna", "Kaduna", ("Kaduna North", "Kaduna South", "Chikun", "Igabi")),
}

# Every other centre GHSL put over a million people in 2020, by its usual metropolitan LGAs.
CANDIDATES = {
    **CITIES,
    "owerri": (9005, "Owerri", "Imo", ("Owerri Municipal", "Owerri North", "Owerri West")),
    "port_harcourt": (9006, "Port Harcourt", "Rivers", ("Port-Harcourt", "Obio/Akpor")),
    "abuja": (9007, "Abuja", "Abuja Federal Capital Territory", ("Municipal Area Council",)),
    "benin_city": (9008, "Benin City", "Edo", ("Oredo", "Egor", "Ikpoba-Okha")),
    "aba": (9010, "Aba", "Abia", ("Aba North", "Aba South")),
    "warri": (9011, "Warri", "Delta", ("Warri South", "Uvwie", "Udu")),
    "uyo": (9012, "Uyo", "Akwa Ibom", ("Uyo",)),
    "ilorin": (9013, "Ilorin", "Kwara", ("Ilorin West", "Ilorin East", "Ilorin South")),
    "maiduguri": (9014, "Maiduguri", "Borno", ("Maiduguri", "Jere")),
    "enugu": (9015, "Enugu", "Enugu", ("Enugu North", "Enugu South", "Enugu East")),
    "jos": (9016, "Jos", "Plateau", ("Jos North", "Jos South")),
}


def lgas() -> gpd.GeoDataFrame:
    """Every LGA with its state, so homonyms (Nassarawa, Ifelodun) resolve by state."""
    lga = gpd.read_file(RAW / "geoBoundaries-NGA-ADM2.geojson").to_crs(4326)
    states = gpd.read_file(RAW / "geoBoundaries-NGA-ADM1.geojson").to_crs(4326)
    joined = gpd.sjoin(lga.set_geometry(lga.representative_point()),
                       states[["shapeName", "geometry"]].rename(columns={"shapeName": "state"}), predicate="within")
    lga["state"] = joined["state"]
    return lga


def main() -> None:
    import sys

    ranking = sys.argv[1:] == ["rank"]
    lga = lgas()
    rows = []
    for slug, (uc, name, state, members) in (CANDIDATES if ranking else CITIES).items():
        pick = lga[(lga["state"] == state) & lga["shapeName"].isin(members)]
        missing = set(members) - set(pick["shapeName"])
        if missing:
            raise SystemExit(f"{name}: no LGA named {sorted(missing)}")
        geom = pick.union_all()
        km2 = gpd.GeoSeries([geom], crs=4326).to_crs("ESRI:54009").area.iloc[0] / 1e6
        rows.append({"ID_UC_G0": uc, "slug": slug, "GC_UCN_MAI_2025": name, "state": state,
                     "lgas": "; ".join(sorted(members)), "n_lgas": len(members), "km2": round(km2, 1),
                     "GC_UCB_YOB_2025": 1975, "geometry": geom})
        print(f"{name}: {len(members)} LGAs, {km2:,.0f} km2")
    out = OUT.with_name("lga_candidates_urban_centres.gpkg") if ranking else OUT
    gpd.GeoDataFrame(rows, crs=4326).to_crs("ESRI:54009").to_file(out, driver="GPKG")


if __name__ == "__main__":
    main()
