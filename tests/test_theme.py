"""The theme is a palette plus references, and nothing else.

A colour written into a rule below ``:root`` is invisible until the palette
changes, and then it is a white strip across a dark page. Eleven of them had
accumulated by 2026-09-26 — a hardcoded table head, the sticky nav's fade,
the pale borders on the pass/fail chips — and every one had to be found by
looking at the rendered page rather than by anything failing.

So: every colour lives in the block at the top, everything below refers to it,
and a swap is that block and nothing else.
"""

from __future__ import annotations

import re
from pathlib import Path

THEME = Path(__file__).resolve().parents[1] / "trading_report/theme.css"
COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\([^)]*\)")


def _below_root(text: str) -> str:
    """Everything after the palette block."""
    end = text.index("*{box-sizing")
    return text[end:]


def test_no_colour_literal_outside_the_palette() -> None:
    text = THEME.read_text(encoding="utf-8")
    strays = COLOUR.findall(_below_root(text))
    assert not strays, (
        "colour literals below :root — these do not follow a palette swap and "
        f"will render for the wrong theme: {sorted(set(strays))}"
    )


SET_AT_RUNTIME = {"--w"}
"""Variables the renderer sets on the element, not the stylesheet.

``--w`` is the fill width of an in-cell bar, written as ``style="--w:62%"`` by
``report.py``. It is a number per row, so it cannot live in the palette; it is
named here so the check below stays exact rather than being loosened to let it
through."""


def test_the_palette_defines_what_the_rules_reference() -> None:
    """Every ``var(--x)`` used below resolves to something declared above.

    A reference to a variable that no longer exists falls back to nothing and
    paints black on black, which is harder to spot than a wrong colour.
    """
    text = THEME.read_text(encoding="utf-8")
    declared = set(re.findall(r"(--[a-z0-9-]+)\s*:", text[: text.index("*{box-sizing")]))
    used = set(re.findall(r"var\((--[a-z0-9-]+)", _below_root(text)))
    assert used - SET_AT_RUNTIME <= declared, (
        f"undeclared variables referenced: {sorted(used - SET_AT_RUNTIME - declared)}"
    )


def test_every_runtime_variable_is_actually_used() -> None:
    """The allow-list shrinks when the stylesheet stops needing an entry."""
    used = set(re.findall(r"var\((--[a-z0-9-]+)", _below_root(THEME.read_text(encoding="utf-8"))))
    assert used >= SET_AT_RUNTIME, f"stale allowance: {sorted(SET_AT_RUNTIME - used)}"


def test_the_canvas_fade_matches_the_canvas() -> None:
    """The sticky nav fades the page out against its own background.

    It is an rgba of the canvas at alpha zero, so it is the one place a colour
    has to be repeated — and the one place a palette swap can leave a visible
    band of the previous theme.
    """
    text = THEME.read_text(encoding="utf-8")
    canvas = re.search(r"--canvas:\s*#([0-9a-fA-F]{6})", text).group(1)
    fade = re.search(r"--canvas-fade:\s*rgba\((\d+),\s*(\d+),\s*(\d+),\s*0\)", text)
    assert fade, "--canvas-fade must be an rgba(...,0)"
    expected = tuple(int(canvas[i : i + 2], 16) for i in (0, 2, 4))
    assert tuple(int(g) for g in fade.groups()) == expected, (
        f"--canvas-fade {fade.groups()} does not match --canvas #{canvas}"
    )


CHARTS = Path(__file__).resolve().parents[1] / "trading_report/charts.py"
BARE_COLOUR = re.compile(r'^\s*\w+(?::\s*Final\[str\])?\s*=\s*"(#[0-9a-fA-F]{3,8})"', re.M)


def test_chart_colours_reference_the_palette_too() -> None:
    """The same rule as the stylesheet, enforced in the other place colour is
    written down.

    An SVG is inline in the page, so ``var(--blue,#2563eb)`` resolves against
    the same palette every rule below :root uses -- and a bare literal does
    not. Three of these had leaked into the breadth chart and rendered
    Tailwind's 600-series on a dark canvas, where the theme's own note says
    the darker shades "stop reading as colour and start reading as grey". The
    fallback after the comma is the light theme's value and is what a chart
    drawn outside the report still uses.
    """
    strays = BARE_COLOUR.findall(CHARTS.read_text(encoding="utf-8"))
    assert not strays, (
        "chart colour constants without a palette reference — these ignore the "
        f"theme and render for whichever one they were written against: {sorted(set(strays))}"
    )
