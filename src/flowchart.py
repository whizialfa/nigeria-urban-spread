"""Methodology flowchart, drawn as a plate in the same family as the walking paper's pipeline."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch, Rectangle

CHARTS = Path(__file__).resolve().parents[1] / "charts"
ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
ARIAL_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
for _path in (ARIAL, ARIAL_BOLD):
    font_manager.fontManager.addfont(_path)
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

PAGE = "#ffffff"
LAND = "#f4f1ea"
INK = "#000000"
MUTED = "#3d3d3d"
CREDIT = "©Wisdom Akpabio"
STROKE = 1.15

TITLE = "FROM GRID TO RINGS"
SUBTITLE = "Five cities, one founding centre each, and what is reported"
FOOTNOTE = (
    "Left: the sources. Middle: 100 m rings around each founding centre.\n"
    "Right: where each strand is reported in the results.\n"
    "The same steps run on 183 Nigerian cities and on Mexico, where a census says what happened."
)
NOTE = "Every outline is a fixed group of local government areas, the same from 1990 to 2020."
COLUMNS = [
    ("Data", "#2e4057", [
        ("Five cities", "Lagos 20 LGAs, Kano 16, Ibadan 11,\nKaduna 4, Onitsha 5 (geoBoundaries)"),
        ("People", "GHS-POP 100 m, 1990 to 2020.\nWorldPop 2000 to 2020 as a check"),
        ("Centres", "A founding place for each city,\nfrom Iga Idunganran to Lugard Hall"),
        ("Yardsticks", "183 GHSL cities urban by 1990;\nMexico's 92, against its census"),
    ]),
    ("Rings", "#2166ac", [
        ("100 m rings", "Each pixel split into 25 points,\npeople counted by distance"),
        ("Remoteness", "r = 1000 x km / sqrt(people 2020).\nCentral r < 3, peri-urban r > 9.3"),
        ("Spread factor", "Q-Q slope of distance quantiles,\n1% to 99%, 1990 against 2020"),
        ("Expected spread", "ln Phi = beta ln growth + alpha dt,\nfitted on 183 cities, applied to five"),
    ]),
    ("Results", "#238b45", [
        ("Where people live", "Zone shares, 1990 to 2020.\nSection 6.1, Tables 1-2, Figure 3a"),
        ("City by city", "Change plates and density profiles.\nSection 6.2, Figures 4-5"),
        ("Spread against expected", "Observed Phi against the national fit.\nSection 6.3, Figure 3b"),
        ("Three checks", "Nigeria's 183 cities, Mexico, WorldPop.\nSections 6.4-6.6, Figures 3c, 6"),
    ]),
]


def _fp(bold: bool, size: float) -> FontProperties:
    return FontProperties(fname=ARIAL_BOLD if bold else ARIAL, size=size)


def _text_frac(text: str, size: float, *, fig_w: float = 15.0, pad_in: float = 0.50) -> float:
    return (pad_in + len(text) * size / 72.0 * 0.56) / fig_w


def _frame(fig, x, y, w, h) -> None:
    fig.patches.append(Rectangle((x, y), w, h, transform=fig.transFigure, facecolor=PAGE, edgecolor=INK,
                                 linewidth=STROKE, zorder=31, clip_on=False))


def _open_plate():
    fig = plt.figure(figsize=(15.0, 9.2), facecolor=PAGE, dpi=200)
    mx, my = 0.022, 0.036
    fig.patches.append(Rectangle((mx, my), 1 - 2 * mx, 1 - 2 * my, transform=fig.transFigure, facecolor="none",
                                 edgecolor=INK, linewidth=STROKE, zorder=30, clip_on=False))

    title_w = min(max(_text_frac(TITLE, 15), _text_frac(SUBTITLE, 13), 0.26), 0.46)
    title_h = 0.100
    title_x, title_y = mx, 1 - my - title_h
    _frame(fig, title_x, title_y, title_w, title_h)
    fig.text(title_x + title_w / 2, title_y + 0.64 * title_h, TITLE, ha="center", va="center",
             fontproperties=_fp(True, 15), color=INK, zorder=32)
    fig.text(title_x + title_w / 2, title_y + 0.28 * title_h, SUBTITLE, ha="center", va="center",
             fontproperties=_fp(True, 13), color=INK, zorder=32)

    lines = [ln for ln in FOOTNOTE.split("\n") if ln.strip()]
    note_w = min(max(max(_text_frac(ln, 12, pad_in=0.55) for ln in lines), 0.40), 0.62)
    note_h = 0.100
    note_x = 0.5 - note_w / 2
    _frame(fig, note_x, my, note_w, note_h)
    fig.text(0.5, my + note_h / 2, FOOTNOTE, ha="center", va="center", fontproperties=_fp(True, 12),
             color=INK, zorder=32, linespacing=1.35)
    fig.text(1 - mx - 0.012, my + 0.012, CREDIT, ha="right", va="bottom", fontproperties=_fp(False, 8),
             color=INK, zorder=32)

    ax = fig.add_axes([0.048, 0.198, 0.904, 0.618])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


def _header(ax, x, y, w, h, text, fc) -> None:
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, edgecolor=fc, linewidth=0, zorder=3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontproperties=_fp(True, 12),
            color=PAGE, zorder=4)


def _box(ax, x, y, w, h, title, body, ec) -> None:
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.006,rounding_size=0.012", facecolor=LAND,
                                edgecolor=ec, linewidth=1.15, zorder=3, mutation_aspect=0.45))
    ax.text(x + w / 2, y + h - 0.032, title, ha="center", va="top", fontproperties=_fp(True, 11),
            color=ec, zorder=4)
    ax.text(x + w / 2, y + 0.048, body, ha="center", va="center", fontproperties=_fp(False, 10),
            color=INK, zorder=4, linespacing=1.28)


def _arrow(ax, x0, x1, y) -> None:
    ax.annotate("", xy=(x1, y), xytext=(x0, y), zorder=2,
                arrowprops={"arrowstyle": "-|>", "color": INK, "lw": 1.4, "mutation_scale": 11,
                            "shrinkA": 0, "shrinkB": 0})


def main() -> None:
    fig, ax = _open_plate()
    xs, col_w = (0.000, 0.350, 0.700), 0.268
    header_h, box_h, gap, header_y = 0.078, 0.168, 0.022, 0.910
    ys = [header_y - 0.024 - box_h - i * (box_h + gap) for i in range(4)]
    for x, (name, colour, boxes) in zip(xs, COLUMNS):
        _header(ax, x, header_y, col_w, header_h, name, colour)
        for y, (title, body) in zip(ys, boxes):
            _box(ax, x, y, col_w, box_h, title, body, colour)
    mid = 0.5 * (ys[0] + box_h + ys[-1])
    _arrow(ax, xs[0] + col_w + 0.010, xs[1] - 0.010, mid)
    _arrow(ax, xs[1] + col_w + 0.010, xs[2] - 0.010, mid)
    ax.text(0.5, 0.012, NOTE, ha="center", va="bottom", fontproperties=_fp(False, 9), color=MUTED, zorder=4)

    CHARTS.mkdir(exist_ok=True)
    out = CHARTS / "method_flowchart.png"
    fig.savefig(out, dpi=200, facecolor=PAGE, edgecolor="none")
    fig.savefig(out.with_suffix(".pdf"), facecolor=PAGE, edgecolor="none")
    plt.close(fig)
    print(out)


if __name__ == "__main__":
    main()
