"""A header is aligned like the column it names.

The rule was "the first two headers are left, the rest right", which held only
because the tables written first put their text columns first. A table with a
left-aligned cell further along — the regime table's "ours" and "attempt", or
"sector" in the setups table — got a right-aligned header floating a column-width
away from its own values.
"""

from __future__ import annotations

import re

from trading_report.report import Cell, Report, Section, Table, render_html


def page(rows: list[list[Cell]], headers: list[str]) -> str:
    report = Report(
        title="t",
        generated="g",
        verdict="v",
        verdict_detail="d",
        verdict_blocked=True,
        sections=[Section(title="s", tables=[Table(headers=headers, rows=rows)])],
    )
    return render_html(report)


def header_is_left(html: str) -> list[bool]:
    head = re.search(r"<thead><tr>(.*?)</tr></thead>", html, re.S)
    assert head, "no header row rendered"
    return ['class="l"' in th for th in re.findall(r"<th[^>]*>.*?</th>", head.group(1), re.S)]


class TestTheHeaderFollowsItsColumn:
    def test_a_left_cell_beyond_the_second_column_gets_a_left_header(self) -> None:
        """The bug. Column 3 is left-aligned and its header was not."""
        rows = [[Cell("a", left=True), Cell("b", left=True), Cell("1"), Cell("c", left=True)]]

        assert header_is_left(page(rows, ["i", "p", "n", "attempt"])) == [
            True,
            True,
            False,
            True,
        ]

    def test_a_right_cell_in_the_first_two_columns_gets_a_right_header(self) -> None:
        """The inverse, which the old rule also got wrong: it left-aligned the
        first two headers whatever their cells did."""
        rows = [[Cell("1"), Cell("2"), Cell("c", left=True)]]

        assert header_is_left(page(rows, ["n", "n", "name"])) == [False, False, True]

    def test_an_all_numeric_table_has_no_left_headers(self) -> None:
        rows = [[Cell("1"), Cell("2"), Cell("3")]]

        assert header_is_left(page(rows, ["a", "b", "c"])) == [False, False, False]

    def test_a_header_with_no_cell_under_it_falls_back(self) -> None:
        """More headers than cells is a caller bug, but it must not raise."""
        rows = [[Cell("a", left=True)]]

        assert header_is_left(page(rows, ["one", "two", "three"])) == [True, True, False]


class TestWhenThereAreNoRows:
    def test_an_empty_table_renders_its_note_not_a_header_row(self) -> None:
        """Nothing to align to, and nothing to misalign."""
        html = page([], ["a", "b", "c"])

        assert "<thead>" not in html
