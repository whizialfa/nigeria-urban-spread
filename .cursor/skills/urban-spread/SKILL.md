---
name: urban-spread
description: >-
  Adapts Peraza-Mues et al. (arXiv 2509.16110) on population loss at the centre
  of Mexican cities to Nigerian urban centres, 1990 to 2020. Use when working on
  remoteness zones, 100 m rings, the urban expansion factor, the beta/alpha
  scaling model, GHS-POP downloads or the Lagos/Kano/Ibadan/Port Harcourt/Abuja cases.
---

# Nigerian urban spread

An adaptation of Peraza-Mues, Resendiz, Figueroa-Soriano, Prieto-Curiel and Ponce-Lopez, *Scaling and Population Loss in Mexican Urban Centres* (arXiv 2509.16110). The trace is `notes/metric_trace.md`.

## Claim

Has the centre of Nigerian cities lost people while the edge filled, as in Mexico? Measured as people by remoteness zone (r = 1000 s / sqrt(P2020); central r < 3, intermediate 3-5, distant 5-9.3, peri-urban > 9.3), the expansion factor Phi from Q-Q slopes of radial distance, and ln Phi = beta ln(growth) + alpha dt.

## Data

- Outlines: GHSL UCDB R2024A V1.2, sub-Saharan Africa, `GHSL_UCDB_THEME_GENERAL_CHARACTERISTICS_GLOBE_R2024A`, Nigeria = 425 urban centres. Saved as `data/processed/ng_urban_centres.gpkg`. Held fixed for every year.
- People: GHS-POP R2023A 100 m via Earth Engine `JRC/GHSL/P2023A/GHS_POP`, epochs 1990, 2000, 2010, 2020. Built-up 1975 from `JRC/GHSL/P2023A/GHS_BUILT_S` for centres.
- Download with `ee.data.computePixels` as `NUMPY_NDARRAY` on the native Mollweide grid (ESRI:54009, 100 m, origin -18041000 / 9000000). GeoTIFF output fails in Mollweide; write the TIFF locally.
- Earth Engine project `cursor-511322`.

## Standing cuts

- 1990 to 2020 headline is the panel of urban centres born by 1990 (183 of 425). Younger centres are reported separately, never pooled into the loss.
- Centre: founding point for Lagos (Iga Idunganran), Kano (Gidan Rumfa), Ibadan (Mapo Hill), Port Harcourt (township waterfront). Abuja uses the Three Arms Zone and is reported as a planned exception. Others: peak of 1975 built-up, 1 km smoothing. Never the 1990 population peak (it would bias the loss).
- Ring area includes water, as in the anchor. Compare change, not level.
- Onitsha and Owerri are multi-core regions: in the totals, flagged in the text.

## Headline (decided 13 October 2026)

- Lead with the **share** of people in central zones: 39.1% in 1990 to 29.9% in 2020 (183-city panel, GHS-POP); it fell in 177 of 183 cities, median 13 points. Read it as a conservative fall.
- The **Mexico test** is why: the same pipeline on GHS-POP turns the anchor's census loss of 2.5 M into a gain of 1.91 M (central share 26.4% to 22.4%; census over 40% to 22%). `summary_mx.csv`.
- Absolute central change (+9.74 M), beta, alpha and the distance ratio are reported but never as evidence of densification.
- Distances are on the ground: azimuthal equidistant projection centred on each city. Never measure rings on the Mollweide grid (it keeps area, not distance).
- WorldPop 2000-2020 agrees on the central gain but its map barely changes shape (Phi about 1.0), so it cannot test spread.
- Scope stays Nigeria. Mexico is a test, not a second study. A global run is a later, separate repo (disk: stream per city, keep no rasters).

## Deliverables

- Academic paper + brief + metric trace + plates + charts + method flowchart.
- `qgis/urban_spread_method.py`: Processing script of the entire method (rings → zones → φ). Standing factory rule: every later paper ships its method as a QGIS script too.
- Mast link to the Mexican paper: https://arxiv.org/abs/2509.16110

## Do not

- Do not call it a replication.
- Do not call GHS-POP a census. It is modelled from built-up volume; a centre turning to shops can lose modelled residents. Say so next to every central-loss number, and check 2000-2020 against WorldPop.
- Do not commit rasters or geopackages.
