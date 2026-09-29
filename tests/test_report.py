"""The daily report's renderer: pure in, string out.

Tested without a scan, a database or a network call, which is the point of
keeping the renderer pure. What is pinned here is the handful of decisions a
reader depends on: that an empty section explains itself, that a breached cap
is visibly marked, and that nothing in the page reaches outside it.
"""

from __future__ import annotations

from trading_report.report import Cell, Report, Section, Table, render_html


def minimal(**overrides: object) -> Report:
    base: dict[str, object] = {
        "title": "Daily trading report",
        "generated": "Generated 2026-09-21 14:00 IST",
        "verdict": "Entries BLOCKED",
        "verdict_detail": "state CAUTION",
        "verdict_blocked": True,
        "sections": [],
    }
    base.update(overrides)
    return Report(**base)  # type: ignore[arg-type]


def test_the_page_makes_no_external_requests() -> None:
    """A report is saved, mailed and opened offline. A CDN stylesheet turns
    it into a blank page on the day it matters."""
    import re

    html = render_html(minimal())

    # Anything that would fetch: a linked stylesheet or script, a url() to a
    # host, a src/href to one. The vendored Pico CSS carries inline SVG data
    # URIs whose XML namespace is spelled `http://www.w3.org/...` — a name,
    # not a request — so the test is for fetches, not for the substring.
    assert "<link" not in html
    assert "<script" not in html
    assert not re.search(r"url\(\s*[\"']?https?://", html)
    assert not re.search(r"src=[\"']https?://", html)
    # `<a href>` is navigation, not a fetch: a headline that links out loads
    # nothing into this page. The rule is about what the page *pulls in*.
    assert not re.search(r"<link[^>]*href=[\"']https?://", html)
    assert "@import" not in html


def test_an_empty_table_says_why_rather_than_rendering_nothing() -> None:
    """'no setups' and 'the scanner returned nothing' look identical as a
    blank table, and this codebase has confused them three times."""
    section = Section(
        title="TIS setups",
        tables=[
            Table(
                headers=["symbol"],
                rows=[],
                empty_note="WEEKLY produced no candidates at all.",
            )
        ],
    )

    html = render_html(minimal(sections=[section]))

    assert "WEEKLY produced no candidates at all." in html
    assert "<tbody>" not in html


def test_a_blocked_gate_is_marked_differently_from_an_open_one() -> None:
    blocked = render_html(minimal(verdict_blocked=True))
    open_gate = render_html(minimal(verdict_blocked=False, verdict="Entries permitted"))

    assert 'class="plate blocked"' in blocked
    assert 'class="plate open"' in open_gate


def test_tone_survives_into_the_markup_so_a_breach_is_visible() -> None:
    """Ninety rows are scanned by colour before they are read by arithmetic."""
    section = Section(
        title="x",
        tables=[
            Table(
                headers=["symbol", "stop%"],
                rows=[[Cell("TFCILTD", left=True), Cell("9.7%", "fail")]],
            )
        ],
    )

    html = render_html(minimal(sections=[section]))

    assert '<td class="fail">9.7%</td>' in html


def test_content_is_escaped_rather_than_interpolated() -> None:
    """Symbols and broker names come from someone else's HTML."""
    section = Section(
        title="x",
        tables=[Table(headers=["symbol"], rows=[[Cell("<script>alert(1)</script>")]])],
    )

    html = render_html(minimal(sections=[section]))

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_the_page_declares_its_scheme_and_prints() -> None:
    """Dark since 2026-09-26, light before that, declared either way.

    What matters is that the page states a scheme rather than leaving it to
    the system: an auto-switching page renders differently for the owner and
    for anyone he sends it to, and a screenshot of it settles nothing. The
    2026-09-23 complaint was an auto-dark page beside three light ones; the
    2026-09-26 instruction was to go back to dark. Both are the same
    requirement — say which.
    """
    html = render_html(minimal())

    assert "color-scheme:dark" in html
    assert "prefers-color-scheme" not in html, "the scheme is declared, never inferred"
    assert "@media print" in html


def test_the_glance_strip_is_omitted_when_there_is_nothing_to_show() -> None:
    """An empty row of boxes is worse than no row: it reads as zeroes."""
    assert '<div class="glance">' not in render_html(minimal())


def test_the_glance_strip_renders_what_the_caller_counted() -> None:
    """Counted by the caller from the rows the tables render. Recounting here
    would let the summary disagree with the table under it."""
    html = render_html(minimal(stats=[("0", "actionable"), ("1,793", "candidates")]))

    assert ">0<" in html
    assert "actionable" in html
    assert "1,793" in html


def test_sections_are_linkable_and_the_anchors_are_stable() -> None:
    """Seven sections is too many to scroll. The ids come from the titles, so
    a bookmarked link survives the numbers changing."""
    html = render_html(minimal(sections=[Section(title="Exchange filings")]))

    assert 'id="exchange-filings"' in html
    assert 'href="#exchange-filings"' not in html  # one section: no nav worth drawing


def test_a_toc_appears_once_there_are_enough_sections() -> None:
    html = render_html(minimal(sections=[Section(title=f"S{i}") for i in range(3)]))

    assert '<nav class="toc">' in html
    assert html.count('href="#s') == 3


def test_a_toned_flag_becomes_a_chip_and_a_number_does_not() -> None:
    """State is found by shape before it is found by reading. Chipping every
    figure would be noise."""
    section = Section(
        title="x",
        tables=[
            Table(
                headers=["symbol", "stop%", "blocked by"],
                rows=[
                    [
                        Cell("TFCILTD", left=True),
                        Cell("9.7%", "fail"),
                        Cell("G4", "fail", left=True),
                    ]
                ],
            )
        ],
    )

    html = render_html(minimal(sections=[section]))

    assert '<td class="fail l"><span>G4</span></td>' in html
    assert '<td class="fail">9.7%</td>' in html


def test_a_dash_is_not_chipped() -> None:
    """Absence is not a state worth a badge."""
    section = Section(
        title="x",
        tables=[Table(headers=["coverage"], rows=[[Cell("—", "warn", left=True)]])],
    )

    assert "<span>—</span>" not in render_html(minimal(sections=[section]))


# -- the shortlist as panels -------------------------------------------------


def test_a_group_of_cards_replaces_its_rows_under_the_same_caption() -> None:
    """A dozen names read better as panels than as a dozen lines of eighteen
    columns. The caption — the funnel — is the same either way, so a reader
    comparing two mornings is comparing the same sentence."""
    from trading_report.report import Card

    table = Table(
        headers=["symbol"],
        rows=[[Cell("SHOULD-NOT-RENDER")]],
        cards=[Card(title="ACUTAAS", badge="6/7 gates", badge_tone="warn")],
        caption="SWING — 855 scanned",
    )

    html = render_html(minimal(sections=[Section(title="TIS setups", tables=[table])]))

    assert '<div class="cards">' in html
    assert "ACUTAAS" in html
    assert "SHOULD-NOT-RENDER" not in html, "cards replace rows, they do not sit beside them"
    assert "SWING — 855 scanned" in html


def test_a_gate_reads_as_a_light_and_says_why_on_hover() -> None:
    """Eight verdicts are a sentence to read and a row of dots to glance at."""
    from trading_report.report import Card, Dot

    card = Card(
        title="ACUTAAS",
        dots=(
            Dot("G3", "fail", title="30-day momentum: +12% in 30d"),
            Dot("G5", "warn", title="sector rotation: LAGGING"),
            Dot("G7", "pass", title="relative strength: RS 92"),
        ),
    )

    html = render_html(minimal(sections=[Section(title="x", tables=[Table([], [], cards=[card])])]))

    assert '<span class="dot fail" title="30-day momentum: +12% in 30d">G3</span>' in html
    assert '<span class="dot warn"' in html, "a non-binding failure is not a refusal"
    assert '<span class="dot pass"' in html


def test_a_bar_places_the_figure_against_the_cap_that_judged_it() -> None:
    """3.0% and 30.0% are the same amount of ink and a very different setup."""
    from trading_report.report import Bar, Card

    card = Card(
        title="TBZ",
        bars=(Bar(label="stop width", value="30.0%", fill=100, mark=17, tone="fail"),),
    )

    html = render_html(minimal(sections=[Section(title="x", tables=[Table([], [], cards=[card])])]))

    assert 'class="fill fail" style="width:100%"' in html
    assert 'style="left:17%"' in html, "the cap marker is where the refusal happened"


def test_bar_widths_are_clamped_rather_than_trusted() -> None:
    """A width over 100% paints outside the card and under 0 disappears."""
    from trading_report.report import Bar, Card

    card = Card(title="X", bars=(Bar(label="l", value="v", fill=250, mark=-40),))

    html = render_html(minimal(sections=[Section(title="x", tables=[Table([], [], cards=[card])])]))

    assert "width:100%" in html
    assert "left:0%" in html


def test_a_cell_can_carry_a_data_bar_behind_its_figure() -> None:
    """The number stays exact; the bar gives the column a shape."""
    section = Section(
        title="x",
        tables=[Table(headers=["move"], rows=[[Cell("+9.3%", "pass", bar=62)]])],
    )

    html = render_html(minimal(sections=[section]))

    assert '<span class="cellbar" style="--w:62%">+9.3%</span>' in html


def test_the_verdict_plate_carries_the_gates_as_lights() -> None:
    """Which gate is shut should not have to be found inside a sentence."""
    from trading_report.report import Dot

    html = render_html(
        minimal(
            signals=[
                Dot("breadth OPEN", "pass", title="49.51% vs 37.56%"),
                Dot("follow-through SHUT", "fail", title="ours reads DOWNTREND"),
            ]
        )
    )

    assert '<div class="signals">' in html
    assert 'title="49.51% vs 37.56%">breadth OPEN</span>' in html
    assert '<span class="dot fail" title="ours reads DOWNTREND">follow-through SHUT</span>' in html


def test_a_table_can_carry_a_flag_above_its_caption() -> None:
    """One fact the rows cannot carry: that they are not from today. STRIKE
    and REVERSAL are not in the nightly scan, so their levels are whatever the
    last hand-run produced — correct arithmetic, older close, and identical to
    fresh rows until the page says otherwise."""
    from trading_report.report import Dot

    table = Table(
        headers=["symbol"],
        rows=[[Cell("TBZ")]],
        caption="STRIKE — 699 scanned",
        flag=Dot("STRIKE rows are 3 days old", "warn", title="last scan 2026-09-20 16:00 IST"),
    )

    html = render_html(minimal(sections=[Section(title="x", tables=[table])]))

    assert '<span class="dot warn" title="last scan 2026-09-20 16:00 IST">' in html
    assert html.index("STRIKE rows are 3 days old") < html.index("STRIKE — 699 scanned")


def test_a_flag_survives_a_table_with_no_rows() -> None:
    """A stale scanner that found nothing is the case most likely to be read
    as "nothing out there today"."""
    from trading_report.report import Dot

    table = Table(headers=["s"], rows=[], empty_note="none", flag=Dot("2 days old", "warn"))

    assert "2 days old" in render_html(minimal(sections=[Section(title="x", tables=[table])]))
