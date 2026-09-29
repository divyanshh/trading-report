"""The setup chart, as SVG the report can carry.

Shared by `equity-service` and `crypto-service`. It reached them from
``stocks_signals/zerodha/services/chart_service.py``, which drew a dark
matplotlib candlestick and sent the PNG to Telegram on every entry. The
picture is the same picture — candles, the moving averages the setup is built
around, entry and stop drawn where the order would sit. Three things changed:

**SVG rather than a PNG.** The report has never loaded anything from outside
itself, and a chart that arrives as a URL breaks that the first time the host
is unreachable — which for an archived page is eventually always. Inlining a
PNG instead costs about 80 KB a name against 3 KB of SVG, and 17 setups of it
would be most of the page. Vector also stays sharp on the phone the report is
read on, and takes the page's own colours rather than carrying a second theme
inside an image.

**No matplotlib.** Drawing this needs line segments and rectangles, and
carrying numpy, pandas and a plotting library in the slug to get them is a
dependency that has to be maintained, audited and built on every deploy. The
arithmetic here is a linear scale and a moving average.

**The page's colours, not its own.** The original was dark because Telegram
is. Every colour here is a `var(--...)` into the report's theme, so a chart
follows a theme swap instead of having to be found and re-coloured after one.
The literal fallbacks are the old light values, for a chart rendered outside a
report.

**A "session" is one bar of whatever resolution the caller folded to.** Equity
counts trading sessions because the instrument has them; a perpetual has a
daily candle by convention and never closes. The axis says nothing about the
gap between bars, so drawing an intraday series here is the caller's
judgement, not this module's.

Adapters live with the thing they adapt: `base_of` needs equity's own
contraction rule and stays there, `from_candles` needs crypto's `Candle` and
stays there. This module knows only :class:`Bar`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

WIDTH: Final[int] = 720
HEIGHT: Final[int] = 260
PAD_LEFT: Final[int] = 8
PAD_RIGHT: Final[int] = 64
"""Room on the right for the price labels, which sit outside the plot."""
PAD_TOP: Final[int] = 10
PAD_BOTTOM: Final[int] = 22

SESSIONS: Final[int] = 65
"""Sessions drawn. Three months, the window the predecessor used."""

MA_PERIODS: Final[tuple[int, ...]] = (10, 20, 50)
"""The averages the setups are built around. A chart that trails a line the
entry never considered is a different chart from the one the rule reads."""

# Every colour here is a reference into the page's theme, not a literal.
# The chart is inline SVG inside the report, so `var(--x)` in a fill or stroke
# resolves against `theme.css` exactly as it would in a stylesheet — which
# means the chart follows a theme swap instead of having to be found and
# re-coloured after one. It was eight literals until 2026-09-26, and on the
# first dark build they were a green candle and a grey grid drawn for a white
# page. The fallbacks are the light theme's values, so a chart rendered
# outside the report still draws.
UP: Final[str] = "var(--green,#15803d)"
DOWN: Final[str] = "var(--red,#b91c1c)"
MA_COLOURS: Final[dict[int, str]] = {
    10: "var(--blue,#2563eb)",
    20: "var(--amber,#b45309)",
    50: "var(--faint,#94a3b8)",
}
ENTRY_COLOUR: Final[str] = "var(--green,#15803d)"
STOP_COLOUR: Final[str] = "var(--red,#b91c1c)"
INIT_STOP_COLOUR: Final[str] = "var(--faint,#94a3b8)"
"""Where the stop started. Grey rather than a second red: the current stop is
the line that matters and two reds make the reader work out which."""
TARGET_COLOUR: Final[str] = "var(--blue,#2563eb)"
BAND: Final[str] = "var(--amber-100,#fef3c7)"
GRID: Final[str] = "var(--line,#e5e9f0)"
INK: Final[str] = "var(--muted,#64748b)"


@dataclass(frozen=True, slots=True)
class Bar:
    """One session. Every field required: a chart is exactly the place where a
    missing low gets quietly replaced by a close."""

    day: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


@dataclass(frozen=True, slots=True)
class Marks:
    """What the order would look like on the picture.

    All optional, because a chart of a name with no derivable stop is still
    worth looking at — it just cannot be drawn with a stop on it.
    """

    entry: Decimal | None = None
    stop: Decimal | None = None
    """Where the stop is **now**. On a position that has trailed this is not
    where the risk was taken — see :attr:`initial_stop`."""

    initial_stop: Decimal | None = None
    """Where the stop started, when that is somewhere else.

    Drawn faint and labelled ``init``, and it is the whole picture on a trade
    that has been running: the gap between this line and :attr:`stop` is the
    move the trail has locked in, and a chart showing only the current stop
    says a position is risking 2% when it opened risking 11% and is now
    protecting a gain. Left ``None`` when it equals the current stop, so a
    position that has never trailed does not carry two lines on top of each
    other."""

    target: Decimal | None = None
    """The take-profit, when there is one.

    **Clamped to the top of the plot rather than scaled into.** An 8.5R target
    sits two or three times the price above the candles, and including it in
    the y-range compresses forty bars into a band at the bottom — the picture
    stops showing what the price is doing, which is the only reason it is
    there. Off-scale it is drawn at the edge with an arrow in the label, which
    says "further than this" without lying about where."""

    band_low: Decimal | None = None
    band_high: Decimal | None = None
    """The contraction, shaded. ``None`` when there is no base — which the
    report says in words too, and the chart should not imply one by drawing a
    band around whatever the last few sessions happened to do."""

    band_from: int | None = None
    """Index of the first session in the band, counted in the drawn window."""


def fold(bars: Sequence[Bar], days_per_bar: int) -> list[Bar]:
    """Daily bars folded into a coarser timeframe, oldest first.

    **Chunked from the right**, matching ``strategies.base.Timeframe.bars``: the
    newest bar always ends on the latest session, because a chart drawn for
    tonight's decision must not leave the last complete bar days old. The
    oldest bar may be short, and nothing reads the oldest bar.

    The high is the block's highest high and the low its lowest low — the
    aggregation the gates could not do, because ``Timeframe`` folds *closes*
    and weekly extremes were unavailable to it. A chart needs them: a weekly
    candle built from daily closes is a body with no wicks, which is a
    different and more confident-looking picture than the real one.

    **Why this exists.** Until 2026-09-26 the report drew every candidate on
    daily bars regardless of the strategy that found it, so a WEEKLY setup got
    daily candles with weekly-derived entry and stop lines painted across them.
    GRWRHITECH on the 25th showed an entry of 7,477.50 — its weekly base high —
    over daily bars that had not traded above 6,770 in eight sessions, and the
    picture invited exactly the conclusion the owner drew: that the entry was
    wrong. The entry was right for the timeframe; the chart was the wrong one.
    """
    if days_per_bar <= 1 or not bars:
        return list(bars)
    blocks = [bars[max(end - days_per_bar, 0) : end] for end in range(len(bars), 0, -days_per_bar)][
        ::-1
    ]
    return [
        Bar(
            day=block[-1].day,
            open=block[0].open,
            high=max(b.high for b in block),
            low=min(b.low for b in block),
            close=block[-1].close,
        )
        for block in blocks
        if block
    ]


def _sma(values: Sequence[Decimal], period: int) -> list[float | None]:
    out: list[float | None] = []
    running = 0.0
    window: list[float] = []
    for value in values:
        window.append(float(value))
        running += window[-1]
        if len(window) > period:
            running -= window.pop(0)
        out.append(running / period if len(window) == period else None)
    return out


def _fmt(value: float) -> str:
    """Two decimals is the tick; the labels are read, not dealt on."""
    return f"{value:,.0f}" if abs(value) >= 1000 else f"{value:,.1f}"


def render(bars: Sequence[Bar], marks: Marks | None = None, *, sessions: int = SESSIONS) -> str:
    """One setup as an ``<svg>`` element, or ``""`` when there is nothing to draw.

    Returns a string rather than writing a file: it is embedded in the page,
    and a chart on disk is a chart that can go missing from an archive.
    """
    if not bars:
        return ""
    marks = marks or Marks()
    window = list(bars[-sessions:])
    n = len(window)

    closes_all = [bar.close for bar in bars]
    averages = {period: _sma(closes_all, period)[-n:] for period in MA_PERIODS}

    lows = [float(bar.low) for bar in window]
    highs = [float(bar.high) for bar in window]
    floor, roof = min(lows), max(highs)
    for level in (marks.entry, marks.stop):
        if level is not None:
            floor, roof = min(floor, float(level)), max(roof, float(level))
    if roof <= floor:
        roof = floor + 1
    margin = (roof - floor) * 0.06
    floor, roof = floor - margin, roof + margin

    plot_w = WIDTH - PAD_LEFT - PAD_RIGHT
    plot_h = HEIGHT - PAD_TOP - PAD_BOTTOM
    step = plot_w / max(n, 1)
    body = max(1.6, step * 0.62)

    def x(i: float) -> float:
        return PAD_LEFT + step * (i + 0.5)

    def y(price: float) -> float:
        return PAD_TOP + plot_h * (roof - price) / (roof - floor)

    parts: list[str] = [
        f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" class="chart" preserveAspectRatio="none" role="img">'
    ]

    # the contraction, behind everything
    if marks.band_low is not None and marks.band_high is not None:
        start = marks.band_from if marks.band_from is not None else max(0, n - 5)
        x0 = x(start) - body / 2
        top, bottom = y(float(marks.band_high)), y(float(marks.band_low))
        parts.append(
            f'<rect x="{x0:.1f}" y="{top:.1f}" width="{WIDTH - PAD_RIGHT - x0:.1f}" '
            f'height="{max(bottom - top, 1):.1f}" fill="{BAND}"/>'
        )

    # four gridlines, labelled on the right
    for k in range(5):
        price = floor + (roof - floor) * k / 4
        gy = y(price)
        parts.append(
            f'<line x1="{PAD_LEFT}" y1="{gy:.1f}" x2="{WIDTH - PAD_RIGHT}" y2="{gy:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
            f'<text x="{WIDTH - PAD_RIGHT + 6}" y="{gy + 3:.1f}" font-size="9" '
            f'fill="{INK}">{_fmt(price)}</text>'
        )

    # candles: one path per direction, so a 65-bar chart is four elements
    for colour, rising in ((UP, True), (DOWN, False)):
        wicks: list[str] = []
        bodies: list[str] = []
        for i, bar in enumerate(window):
            if (bar.close >= bar.open) != rising:
                continue
            cx = x(i)
            wicks.append(f"M{cx:.1f} {y(float(bar.high)):.1f}V{y(float(bar.low)):.1f}")
            top = y(float(max(bar.open, bar.close)))
            bottom = y(float(min(bar.open, bar.close)))
            bodies.append(
                f"M{cx - body / 2:.1f} {top:.1f}h{body:.1f}v{max(bottom - top, 1):.1f}h{-body:.1f}Z"
            )
        if wicks:
            parts.append(
                f'<path d="{"".join(wicks)}" stroke="{colour}" stroke-width="1" fill="none"/>'
            )
        if bodies:
            parts.append(f'<path d="{"".join(bodies)}" fill="{colour}"/>')

    # the averages
    for period in MA_PERIODS:
        points = [
            f"{x(i):.1f},{y(value):.1f}"
            for i, value in enumerate(averages[period])
            if value is not None
        ]
        if len(points) > 1:
            parts.append(
                f'<polyline points="{" ".join(points)}" fill="none" '
                f'stroke="{MA_COLOURS[period]}" stroke-width="1.4" opacity="0.9"/>'
            )

    # entry and stop, labelled where the order would rest
    for level, colour, label in (
        (marks.entry, ENTRY_COLOUR, "entry"),
        (marks.stop, STOP_COLOUR, "stop"),
    ):
        if level is None:
            continue
        ly = y(float(level))
        parts.append(
            f'<line x1="{PAD_LEFT}" y1="{ly:.1f}" x2="{WIDTH - PAD_RIGHT}" y2="{ly:.1f}" '
            f'stroke="{colour}" stroke-width="1.2" stroke-dasharray="5 4"/>'
            f'<text x="{WIDTH - PAD_RIGHT + 6}" y="{ly + 3:.1f}" font-size="9" '
            f'font-weight="700" fill="{colour}">{label}</text>'
        )

    # dates, every eighth session
    stride = max(n // 7, 1)
    for i in range(0, n, stride):
        parts.append(
            f'<text x="{x(i):.1f}" y="{HEIGHT - 6}" font-size="9" fill="{INK}" '
            f'text-anchor="middle">{window[i].day.strftime("%d %b")}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


MINI_WIDTH: Final[int] = 340
MINI_HEIGHT: Final[int] = 124
MINI_SESSIONS: Final[int] = 40
"""Two months beside the numbers. It was 210x54 for one afternoon and could
not be read: at five pixels a candle the wicks are a smudge and there is no
room to say which line is the stop. At 340x124 a candle is eight pixels, the
three levels carry their own labels, and the row is still a row."""

LABEL: Final[int] = 8
"""Type size for the labels inside the plot. Small, because the row prints
every one of these numbers in full a few columns to the right — the label says
*which line is which*, not what it is worth."""


# The band this module draws is supplied, never derived. Finding a base is a
# strategy's judgement and the two services disagree about it: equity shades
# the contraction it entered on, by a wick rule that lives in its own
# `indicators`; no crypto strategy enters on a base at all — `leader_pullback`
# explicitly refuses tight coils, "a coin with a 15% daily range does not coil
# to 10%, its pullback *is* the base". A shared `base_of` would have to pick
# one of those and would then draw, for the other, a shape none of its rules
# reads. So the caller passes `Marks.band_low`/`band_high` or passes nothing.


def _band_start(window: Sequence[Bar], low: Decimal, high: Decimal) -> int:
    """First session of the run that stays inside the contraction.

    Walked back from the newest bar rather than passed in, because
    ``contraction_bounds`` answers with a price range and not with the bars it
    came from. An earlier bar that also sits inside the range is included, and
    that is the honest answer: it is inside the range.
    """
    start = len(window)
    for i in range(len(window) - 1, -1, -1):
        if window[i].low < low or window[i].high > high:
            break
        start = i
    return min(start, len(window) - 1)


def render_mini(
    bars: Sequence[Bar], marks: Marks | None = None, *, sessions: int = MINI_SESSIONS
) -> str:
    """The row's chart: candles, the 20-day average, and the three levels named.

    A full chart is 7 KB and half a screen; a hundred of them is a page nobody
    scrolls. This is the version that belongs beside the numbers it describes
    — no axis and no dates, because the row carries the prices and the
    sessions, but the entry, the stop and the contraction are *labelled*: an
    unlabelled dashed line is a line the reader has to guess at, and the two
    guesses are a buy and a loss.
    """
    if not bars:
        return ""
    marks = marks or Marks()
    window = list(bars[-sessions:])
    n = len(window)

    averages = _sma([bar.close for bar in bars], 20)[-n:]

    floor = min(float(bar.low) for bar in window)
    roof = max(float(bar.high) for bar in window)
    # The target is deliberately absent from this loop: see `Marks.target`.
    for level in (
        marks.entry,
        marks.stop,
        marks.initial_stop,
        marks.band_low,
        marks.band_high,
    ):
        if level is not None:
            floor, roof = min(floor, float(level)), max(roof, float(level))
    if roof <= floor:
        roof = floor + 1
    pad = (roof - floor) * 0.05
    floor, roof = floor - pad, roof + pad

    right = 52  # room for the labels, outside the candles
    plot_w = MINI_WIDTH - right
    step = plot_w / max(n, 1)
    body = max(2.0, step * 0.62)

    def x(i: float) -> float:
        return step * (i + 0.5)

    def y(price: float) -> float:
        return 3 + (MINI_HEIGHT - 6) * (roof - price) / (roof - floor)

    parts = [f'<svg viewBox="0 0 {MINI_WIDTH} {MINI_HEIGHT}" class="spark" role="img">']

    if marks.band_low is not None and marks.band_high is not None:
        x0 = x(_band_start(window, marks.band_low, marks.band_high)) - body
        top, bottom = y(float(marks.band_high)), y(float(marks.band_low))
        parts.append(
            f'<rect x="{max(x0, 0):.1f}" y="{top:.1f}" width="{plot_w - max(x0, 0):.1f}" '
            f'height="{max(bottom - top, 1):.1f}" fill="{BAND}"/>'
            f'<text x="{plot_w + 3}" y="{(top + bottom) / 2 + 3:.1f}" font-size="{LABEL}" '
            f'fill="{INK}">base</text>'
        )

    for colour, rising in ((UP, True), (DOWN, False)):
        strokes: list[str] = []
        for i, bar in enumerate(window):
            if (bar.close >= bar.open) != rising:
                continue
            cx = x(i)
            strokes.append(f"M{cx:.1f} {y(float(bar.high)):.1f}V{y(float(bar.low)):.1f}")
            top = y(float(max(bar.open, bar.close)))
            bottom = y(float(min(bar.open, bar.close)))
            strokes.append(
                f"M{cx - body / 2:.1f} {top:.1f}h{body:.1f}v{max(bottom - top, 1.0):.1f}"
                f"h{-body:.1f}Z"
            )
        if strokes:
            parts.append(
                f'<path d="{"".join(strokes)}" fill="{colour}" stroke="{colour}" '
                f'stroke-width="0.9"/>'
            )

    points = [f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(averages) if v is not None]
    if len(points) > 1:
        parts.append(
            f'<polyline points="{" ".join(points)}" fill="none" '
            f'stroke="{MA_COLOURS[20]}" stroke-width="1.1" opacity="0.85"/>'
        )

    # Faintest first, so a trailed stop sitting near its origin draws over it.
    levels = [
        (marks.initial_stop, INIT_STOP_COLOUR, "init", 0.65, "2 3"),
        (marks.entry, ENTRY_COLOUR, "entry", 1.0, "4 3"),
        (marks.stop, STOP_COLOUR, "stop", 1.0, "4 3"),
    ]
    present = [(y(float(v)), c, t, o, d) for v, c, t, o, d in levels if v is not None]
    # Two labels at the same height overprint into something unreadable, so a
    # height carries one caption — the **last** level at it, which by the order
    # above is the strongest line and the one worth naming. Deciding this
    # first-come instead gave the row to `init` and left the live stop
    # unlabelled, which is exactly backwards.
    captioned = {round(ly, 1): i for i, (ly, *_rest) in enumerate(present)}
    for i, (ly, colour, label, opacity, dashes) in enumerate(present):
        caption = label if captioned[round(ly, 1)] == i else ""
        parts.append(
            f'<line x1="0" y1="{ly:.1f}" x2="{plot_w:.1f}" y2="{ly:.1f}" stroke="{colour}" '
            f'stroke-width="1" stroke-dasharray="{dashes}" opacity="{opacity}"/>'
            + (
                f'<text x="{plot_w + 3}" y="{ly + 3:.1f}" font-size="{LABEL}" '
                f'font-weight="700" fill="{colour}">{caption}</text>'
                if caption
                else ""
            )
        )

    if marks.target is not None:
        value = float(marks.target)
        above = value > roof
        below = value < floor
        ly = 4.0 if above else (MINI_HEIGHT - 4.0 if below else y(value))
        label = "target" + (" ^" if above else " v" if below else "")
        parts.append(
            f'<line x1="0" y1="{ly:.1f}" x2="{plot_w:.1f}" y2="{ly:.1f}" '
            f'stroke="{TARGET_COLOUR}" stroke-width="1" stroke-dasharray="6 2" '
            f'opacity="{0.55 if (above or below) else 1.0}"/>'
            f'<text x="{plot_w + 3}" y="{ly + 3:.1f}" font-size="{LABEL}" font-weight="700" '
            f'fill="{TARGET_COLOUR}">{label}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)
