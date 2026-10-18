---
name: publication-maps
description: >-
  Wisdom's publication cartography for print map plates: A3 furniture (title,
  legend, footnote, north, scale, credit), no overlap, furniture-aware zoom,
  snug legends with even insets, plain-language titles. Use when building QGIS
  print layouts, choropleth hex maps, map plates, legends, north arrows, scale
  bars, or exporting PNG/PDF maps.
---

# Publication maps (Wisdom)

How Wisdom makes print plates. Apply in every project that exports choropleth maps, QGIS layouts, or PNG/PDF map figures. Iterate by looking at the plate, not by arguing from layout coordinates.

## What you show him

A map he is asked to look at is a landscape A3 plate. A QGIS canvas dump, a matplotlib figure, or a legend painted onto a screenshot is not a map in this workshop. The Los Angeles and Lagos "so far" images failed this test: grey or bare canvas, no title box, no north arrow, no scale, no three-sentence footnote, no `©Wisdom Akpabio`, and a legend that did not sit in the furniture.

Thematic plates sit on the published Carto Positron style. Do not paint a substitute palette, and do not use OpenStreetMap or Liberty for these plates. Place names from that style are drawn above the choropleth in Helvetica, because the style's own font is not on this machine and names under the cells cannot be read. Esri light grey is only for study-area figures. A small `© OpenStreetMap contributors © CARTO` sits with the Wisdom credit, not in its own box.

When he corrects a plate, write the correction into this skill before the next city. Then copy this file into that project's `.cursor/skills/publication-maps/SKILL.md`. Read the project copy before drawing.

## Page

Landscape A3. Thin black neatline. White paper. Published Carto Positron under the choropleth, with its place names drawn above the colours.

Furniture lives **inside** the neatline, never overlapping each other or the drawn city:

| Item | Place | Treatment |
|---|---|---|
| Title | top-left white box | Two short lines, non-technical, Arial 15 Bold, centered in the box |
| North | top-right | White compass SVG, grid north, no letter N |
| Legend | bottom-left | Snug to content; even inset; intuitive header; range-only classes |
| Footnote | bottom-center | Three sentences, 12 pt Bold, what the map shows |
| Scale | bottom-right | Line Ticks Up, kilometres, long enough to read |
| Credit | above the scale | `©Wisdom Akpabio`, small, white-buffered, no box |

White boxes: fill 255, thin black stroke (~0.45 mm). Match the title box — that is the visual family.

## Overlap is a defect

No furniture on the city. No ward label under the title. No coast eating the legend. No scale sitting on hexes.

Zoom **in** as far as the furniture allows, then center: take the city up, down, left, or right. Zooming out “to be safe” is the usual failure. Round cities on landscape A3 will show the base map left and right. That is the page, not a reason to shrink the city.

Collision must use the **real** item box, not a reserved empty slot. A 90 mm legend frame with 40 mm of content will hold the whole city off the south coast.

For a wide coastal city, a shorter legend is what lets the shoreline drop. Grow the title’s collision box if northern labels sit above the hexes (Lagos: Alagbado / Alakuko).

## Title and footnote

Title names the phenomenon, not the field:

- `POPULATION IN LAGOS` / `People in each neighbourhood`
- `WALKING ACCESS IN LAGOS` / `To clinics and schools`

Not `PT_k`, `pop`, `n=5`, or a file name.

Footnote: three sentences a non-specialist can read. What the map shows, the cell size, how to read the colour. 12 pt Bold — smaller is illegible in print.

## Legend

Keep the font size; change the box.

- Header in plain language: `People per hexagon`, `Minutes on foot`
- Class labels are the range only (`≤ 5 min`, `5–400`), not `Very close (≤ 5 min)`
- Title ~13 pt Bold, classes ~12 pt, Arial
- Inset ~2.5 mm between type and frame — not glued to the stroke, not a padded void
- Row spacing stays tight. Empty white **inside** the box is the defect, not a short box
- Size from content. If the layout engine reports ~0 mm, give the item a real rect first; do **not** floor height to 90 mm of air

## Geography on the plate

- Study boundary: bold black, the strongest line
- Internal units (wards): visible, thinner and greyer than the study edge (~0.22 mm). Hyphenated names stay on **one** line (non-breaking hyphen)
- Choropleth fill ~80% opacity (alpha 204) so the base map reads through. 70% washes sequential greens into each other
- No extra admin layer the reader does not need
- No hatch or veil that recodes the ramp. Completeness belongs in a table or a separate mask figure, not as a tint on the access map

## Colour

- **Minute metrics:** one shared nominal ladder across every city in the panel. 15 must be an edge (so the first classes sum to F15). Keep a 60 edge — otherwise everything above 30 min is one class
- **Counts / density:** Jenks **per city**, then round the cuts, on a sequential ramp (ColorBrewer YlOrRd). Pretty breaks on the value range flatten a skewed city. A shared ladder empties classes in compact cities

## Study-area figures (in the paper)

Same family as the A3 plates. QGIS, Esri light-grey base, furniture inside the neatline. Not a matplotlib blob on cream.

- Title `STUDY AREA` / city name, Nigeria locator, scale, grid-north compass SVG, snug legend, three-sentence footnote, `©Wisdom Akpabio`
- Study outline is the strongest line. Wards thinner and greyer. Place labels Helvetica, no overlap
- If the analysis splits the city (old city / fringe, rural ring), those fills sit on the grey base at ~80% or less so streets still read
- Caption says what the outline is, why, and the people / area count
- Same city, same outline: reuse the plate Wisdom already signed off (Kano heat copies `15-min-cities-nigeria/maps/kano_study_area.png`). A later analytical cut (old city / fringe / ring) lives in the prose, not a second study-area style
- Rebuild with QGIS's `python3.9` and `env -u PYTHONPATH`
- **Nigerian city outlines are LGAs** (geoBoundaries ADM2, joined to ADM1 for duplicate names), not GHSL urban-centre blobs. GHSL merges neighbouring towns (Onitsha with Nnewi, Owerri with Orlu)
- **Only in-study boundaries.** Draw and label the LGAs inside the outline. No neighbouring LGAs, no state lines, no outside fill. The locator carries the national context
- Every in-study LGA gets a label. LGAs too small or crowded take an outside label with a thin leader line
- **Centre is a yellow star** (`255,214,0`, black edge, ~7.5 mm) with its place name in bold, so it is found at a glance
- **Population inside the outline, one panel.** Clip the rasters to the outline. When two grids are compared (GHS-POP and WorldPop), use a single **bivariate 3 × 3** map (Stevens green/blue: green = only GHS-POP dense, blue = only WorldPop, dark teal = both), with shared rounded Jenks cuts and a square key with arrows on both axes. Not twin panels, not two grids stacked with transparency
- Leave near-empty hectares (under ~1 person per ha in both grids) transparent so the base map shows; do not paint the whole outline grey
- **Every city plate gets a core inset** (red frame, matching red box on the main map, title "City core, N km across"), at least 2× the main map's zoom, star kept inside. Partial labels off; the inset title blocks labels
- **Nigeria locator shows the study outline** filled red with a bold dark-red edge, and names the city. Not a generic square
- **A red arrow joins the small red box to the inset frame**, so the eye goes straight from one to the other
- **Results plates drop the country locator** (the study plate already placed the city). The inset takes the freed column: starts under the north arrow and grows wider (~130 mm)
- **Distance rings and buffer lines are coloured by distance**: one sequential hue, dark for the nearest edge and light for the farthest, in a hue the data palette does not use (greens beside a red/blue change map). Keep solid, dashed and dotted as a second cue
- **Buffer labels are curved on the rings**: each zone edge carries its distance (and a short zone name), curved AlongLine / OnLine so the bend is readable. Short "7.5 km" alone looks flat on a large radius; use `Central zone · 7.5 km` (and the same pattern for intermediate and distant). Colour the label with its ring
- **Legend bar spacing is even**: symbol height about 5 mm, line spacing about 1.6 mm, equal top and bottom symbol margins, box inset 2.5 mm. Size the legend height from the row count (`row ≈ symbolHeight + 1.4`), then clip any bloated QGIS measure with `min(measured, target)`. Never floor height upward. Empty white inside the box is the defect; crush is also a defect
- **Chart titles and guide lines must not share the same y**: put how-to-read text in the paper prose or figcaption, not as `ax.text` on top of `set_title`
- **Metro LGA names that crowd the centre** take outside callouts with leaders; the centre star label keeps clearance (`dist` ≥ 3 mm) and PreventOverlap
- **Document theme follows the map palette**: paper CSS uses the plate colours (slate `#2e4057`, loss blue `#2166ac`, gain red `#b30000`, zone green `#238b45`, near-zero cream `#ece8de`), not a separate clay/cream scheme

- **Any place, on the fly:** `study_area_plate.py` (next to this skill) is a QGIS Processing script that builds this plate from three inputs: area of interest, raster(s) of interest, country of interest. Add it via Processing Toolbox > Add Script to Toolbox; it opens the layout for printing and writes PNG and PDF

## Rebuild and look

After any furniture or style change, rebuild the plate and inspect it. Stale maps are silent.

QGIS print layouts: run **QGIS’s** Python, with `env -u PYTHONPATH`, so a project venv (numpy built for a newer CPython) cannot load.

Export PNG (~200 dpi) and PDF. Do not commit rasters or plates unless asked.

## Do not

- Show a progress map that is not a plate
- Paint a legend onto a rendered image instead of laying it out
- Tiny footnotes
- Technical legend titles
- Overlap “just this corner”
- Zoom out to keep furniture happy
- Stretch a legend to a fixed slot
- Metro / LGA fills on top of a hex choropleth
- Drop no-data cells to make the map prettier
- A second colour language that copies the previous project's ramp. Built-up on the heat plates is a dull red because he asked for that, and it must not be the walking-access red
