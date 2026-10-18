---
name: house-docs
description: >-
  Wisdom's academic paper and brief: professor skeleton, catchy title plus
  precise subtitle, human voice, study-area plate on a landscape page, a
  methodology flowchart in every paper, data availability as a labeled list. Use when writing notes/results.md, the brief,
  or the PDF. Copy this file into every new project.
---

# House documents (Wisdom)

Write like `15-min-cities-nigeria/notes/results.md`. Named places and numbers in the claim. Mixed sentence length. A little blunt. No em dashes in body copy.

Do not sound generated: no "the remainder of this paper is structured as follows", no "it is important to note", no stacked Furthermore / Moreover / Additionally, no "robust framework", "shed light", or "delve".

## Mast

Catchy title, precise subtitle. `The city as shade` / *Surface heat in metropolitan Kano, 2015 to 2026*. A little philosophical is fine. A two-word stub is not. A sentence on the mast is not. The same mast is on the brief, the paper, the README, and the map.

## Skeleton

Professor comments of 20 September 2026. Do not ship a short question / method / results note and call it the paper.

1. Glossary
2. Introduction
3. Statement of the problem, its own section
4. Justification, its own section: why this study, why these places, why this design, and what it is entitled to claim
5. Study area, with a study-area plate on its own landscape page
6. Data and methods, opening with a methodology flowchart (see below)
7. Results, with the important figures in bold
8. Discussion
9. Limitations specific to the place
10. Policy that names places and says what to do
11. Conclusions with enough flesh to answer the question the paper asked. Do not restate the abstract in one paragraph
12. Data availability
13. References

## Methodology flowchart

Every paper has one. No exceptions, even when the method feels simple. It is Figure 2, introduced in the first paragraph of Data and methods, and later figures are numbered after it.

The model is `15-min-cities-nigeria/charts/pipeline.png` (`pipeline_flowchart` in `src/proximity/charts.py`). Copy that plate, not a box-and-arrow diagram:

- A landscape plate, 15 by 9.2 inches: neatline, snug title box top left (capitals title, plain subtitle), footnote box bottom centre, credit bottom right, one muted note line above the footnote.
- Three columns with coloured header bars, for example Data, the working unit (Walks, Squares, Surfaces), and what is reported (Scores, Shares, Results). Four boxes per column, one arrow between columns.
- Each box: a bold coloured title and two short lines of body text at 10 pt. Real numbers where they define the method: thresholds, scene counts, accuracy, distances. The last column names the table, figure, plate or section each strand feeds.
- The paper's own palette for the three header bars. Not the 15-min teal and red on a paper with its own colours.
- Drawn in code to `charts/method_flowchart.png` and `.pdf`.

It goes on its own landscape page, like a plate, at full page width. A portrait diagram squeezed into the text column is too small to read; Wisdom rejected one. Place the landscape page where it does not strand a short paragraph above a blank: next to another landscape page, or at the end of a subsection, and keep figure numbers in reading order.

When a method changes, redraw the flowchart before rebuilding the PDF.

## Anchor link on the mast

Every paper and brief mast carries a one-line adaptation credit with a live link to the source paper (DOI or arXiv), in the `.adapt` line under the byline. The README opens with the same link. Do not leave the source only in References.

## Method as a QGIS script

Every paper ships a QGIS Processing script under `qgis/` that runs the **analysis method** end to end (not only the study-area plate). Install with Add Script to Toolbox; group `Wisdom maps`. The script takes the paper's inputs (outline, centre, rasters or layers) and writes the same rings, zones, scores or tables the `src/` pipeline quotes. Name it for the method (`urban_spread_method.py`, `proximity_method.py`, …). List it under Code in Data availability. Standing rule also lives in `paper-replica-factory`.

## Data availability

A short note, then a labeled list: Write-up, Tables, Maps, Charts, Code. The label column is narrow. Paths sit next to the label. Not one packed paragraph. Code includes both `src/` and the QGIS method script.

## Pages

Tight. Unnecessary space is a defect, and it is fixed before the page is shown. A heading and one sentence must not sit alone above a blank page. A figure stays with the paragraph that introduces it. A forced page break that leaves the previous page half empty is a gap, not a layout. A figure that jumps forward and leaves a white band under a short paragraph is the same defect.

Study-area plates and result plates each take their own landscape page. The page holds the map and its caption. The write-up stays in the running text, and the write-ups of several cities share a page when one city would otherwise sit alone above a blank. Do not put the words beside the map, and do not put them on the map's landscape page. Size the map so it fills that landscape page. Do not stack blank lines, padded section gaps, or a caption floating away from its figure.

When he corrects a page, update this skill before the next paper, and copy it into that project's `.cursor/skills/house-docs/SKILL.md`.
