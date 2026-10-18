# Metric trace

Anchor: Peraza-Mues, Resendiz, Figueroa-Soriano, Prieto-Curiel and Ponce-Lopez, *Scaling and Population Loss in Mexican Urban Centres*, arXiv:2509.16110 (v3, May 2026). An adaptation, not a clone.

## The anchor's numbers, from raw input to reported value

| Step | Anchor (Mexico) | Here (Nigeria) |
|---|---|---|
| People | INEGI census, AGEB blocks 1990, 2000, 2010, 2020, aligned and spread onto a ~470 m grid | GHS-POP R2023A, 100 m, epochs 1990, 2000, 2010, 2020 (modelled, not a census) |
| City extent | 2020 central urban cluster of each metropolitan area, held fixed for all years | Union of the city's LGAs (geoBoundaries ADM2), held fixed (`src/lga_cities.py`). Yardstick: GHSL Urban Centre Database R2024A V1.2, 2025 outline |
| Cities | 69 (47 metro areas + 22 metro municipalities) | The five largest by people in 2020 inside their own LGAs: Lagos (20 LGAs), Kano (16), Ibadan (11), Kaduna (4), Onitsha (5). Yardstick panel: GHSL urban centres born by 1990 (183 of 425) |
| Centre | Historic founding point | Founding point for each of the five: Iga Idunganran, Gidan Rumfa, Mapo Hill, Lugard Hall, Ime-Obi Ogboza. Yardstick panel: the peak of 1975 built-up surface, smoothed at 1 km, where no founding point is known |
| Rings | 100 m rings, cell population split by area share | 100 m rings; each 100 m pixel split into 5 x 5 sub-points |
| Density | sigma(s) = ring population / ring area | Same |
| Remoteness | r = 1000 s / sqrt(P_2020) | Same, P = population inside the fixed outline in 2020 |
| Zones | central r < 3, intermediate 3-5, distant 5-9.3, peri-urban > 9.3 | Same |
| Headline 1 | Central zones lost 2.5 M people 1990-2020; outer zones gained | Change in central-zone population, summed and city by city |
| Headline 2 | Share of urban population in central zones fell from > 40% to 22% | Same share |
| Expansion factor | Phi_ij = slope of the Q-Q fit of radial distance quantiles, t_i to t_j | Same, quantiles 1% to 99%, fit through the origin |
| Model | ln Phi = beta ln(P_j/P_i) + alpha (t_j - t_i); beta 0.60, alpha 0.0057 | Same OLS, all six year pairs, 95% bootstrap by city |
| Headline 3 | Distances 28% longer than a density-preserving counterfactual: (growth)^(beta - 0.5) e^(alpha dt) with growth 2.16 | Five cities are too few to fit. Each city's Phi 1990-2020 is set against growth^beta e^(30 alpha) from the 183-city panel fit (beta -0.027, alpha 0.0065), about 1.19 |


## The five cities (`named_cities_lga.csv`, `zone_people_lga.csv`, `summary_lga.csv`)

| City | People 1990 to 2020 | Central zone reaches | Central share | Phi observed | Phi expected |
|---|---|---|---|---|---|
| Lagos | 5.82 M to 11.31 M | 10.1 km | 25.8% to 25.6% | 1.010 | 1.195 |
| Kano | 2.88 M to 6.22 M | 7.5 km | 55.3% to 49.6% | 1.046 | 1.192 |
| Ibadan | 1.68 M to 3.69 M | 5.8 km | 49.5% to 45.0% | 1.081 | 1.191 |
| Kaduna | 1.08 M to 2.09 M | 4.3 km | 27.6% to 22.4% | 1.019 | 1.195 |
| Onitsha | 0.89 M to 2.05 M | 4.3 km | 21.4% to 23.9% | 0.954 | 1.190 |
| All five | 12.34 M to 25.36 M | | 35.8% to 33.9% | | |

Central zones gained 4.18 M (32% of growth); no central zone lost people. WorldPop 2000 to 2020 (`named_cities_lga_worldpop.csv`) agrees with GHS-POP on the sign of the change in central share in Lagos, Kano and Ibadan, and disagrees in Kaduna (GHS-POP -5.7 points, WorldPop +1.1) and Onitsha (+2.5, -0.8). The comparison that survives the Mexican test is observed against expected Phi, because both sit on GHS-POP.

## What breaks here

1. **The population is modelled.** GHS-POP places people by built-up volume. A centre whose buildings turn to shops and offices loses modelled people whether or not residents left. The anchor rejected GHS-POP for Mexico for this reason. Here it is the only consistent 1990-2020 grid; Nigeria's censuses are 1991 and 2006. Check: repeat the 2000-2020 result on WorldPop and report both.
2. **One point does not fit every city.** Onitsha (5.8 M) and Owerri (3.6 M) are continuous settled regions with many cores. They stay in the totals and are flagged; the named cases are single-centred.
3. **Young cities.** 242 of 425 urban centres did not exist as urban centres in 1990. They cannot lose a centre they did not have. The 1990-2020 headline is the 183-city panel.
4. **Abuja has no founding point.** It was laid out from 1976. Its origin is a planning decision, and it is reported as the exception, not pooled with the historic cores.
5. **Coasts and lagoons.** Ring area includes water, as in the anchor. Lagos's central density is low because the ring is half lagoon, not because the island is empty. Change in density, not level, is the comparison.

## Checks run

**A second population model (WorldPop, 2000 to 2020).** Same 183 cities, centres, rings and zones (`summary_ghs2000.csv` vs `summary_worldpop.csv`).

| 2000 to 2020, panel of 183 | GHS-POP | WorldPop |
|---|---|---|
| Central-zone change | +6.22 M | +6.52 M |
| Central share | 37.0% to 29.9% | 24.9% to 24.7% |
| Cities where the central share fell | 178 | 59 |
| Cities losing central people | 28 | 0 |
| beta (95% CI) | 0.004 (-0.07 to 0.08) | -0.05 (-0.08 to -0.03) |
| alpha | 0.0064 | 0.0018 |
| Distance ratio vs density-preserving | 0.89 | 0.70 |

Both say the centres gained people. Neither shows Mexico's loss. But WorldPop cannot test change in shape: its map barely moves between years (Phi 1.00 to 1.04 for the named cities, central share flat), as if a near-fixed pattern were rescaled to each year's total. So the check rules out "GHS-POP alone invents the central gain", and it does not confirm GHS-POP's spreading of the share outward. That outward shift rests on GHS-POP's built-up change, which is real satellite evidence of building, not of residents.

**Mexico through the same pipeline (GHS-POP, 1990 to 2020).** 182 GHSL urban centres, 92 existing by 1990; founding points for Mexico City (Zocalo), Guadalajara (Cathedral), Monterrey (Macroplaza) and Puebla (Zocalo), the 1975 built-up peak elsewhere (`summary_mx.csv`).

| 1990 to 2020 | Anchor (census) | GHS-POP, same method |
|---|---|---|
| Central-zone change | -2.5 M | +1.91 M |
| Central share | over 40% to 22% | 26.4% to 22.4% |
| Cities losing central people | most large metros | 2 of 92 (Mexico City -230k, Guadalajara -76k) |
| beta | 0.60 | -0.003 (-0.03 to 0.03) |

GHS-POP gets the 2020 share right and the direction of the share right, but it turns a census loss of 2.5 M into a gain of 1.9 M, and its 1990 map is already too spread out. It cannot be trusted to show a centre emptying. For Nigeria this means: the fall in the central share (39.1% to 29.9%) is a defensible, probably conservative reading; the central gain of 9.7 M people, and beta and the distance ratio built on it, are not evidence of densification.

**Distance on the ground.** Rings were first measured on the Mollweide grid, which keeps area but not distance: near Nigeria it squeezes east-west and stretches north-south by about a tenth, and in Mexico it also shears. Every distance is now measured in an azimuthal equidistant projection centred on each city. The headline moved by less than a point (central share 38.6% to 29.4% before, 39.1% to 29.9% after).

**Centre points** (`maps/centre_check_founding.png`, `maps/centre_check_losers.png`). Lagos, Kano and Ibadan sit on their old cores, close to the 1975 built-up peak. Port Harcourt's Township point lies about 2 km south of the 1975 peak, on the waterfront, so its central circle is part creek. Abuja's Three Arms Zone sits at the sparse eastern end of the city by Aso Rock; its central zone holds 37k people, which is a fact about the plan, not an error. The largest losers (Akure, Ikorodu, Katsina Ala, Yenagoa, Ado, Wukari, Dutse, Sagamu, Benin City) all have their centre on the old town, so their losses are not a misplaced point. Ado is the Karu-side settlement next to Abuja, not Ado-Ekiti.

## Boundary and vintage in one sentence

Five Nigerian cities drawn as fixed unions of geoBoundaries LGAs, with GHS-POP R2023A population for 1990, 2000, 2010 and 2020 inside them, read against 183 GHSL urban centres outlined in 2025.
