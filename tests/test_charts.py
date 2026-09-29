"""The setup chart, ported from the Telegram chart service.

The predecessor drew a dark matplotlib candlestick and sent the PNG. This
draws the same picture as SVG the report carries inline, and these tests are
about the two things a chart can silently get wrong: drawing a bar the market
did not trade, and drawing a scale that makes the wrong thing look true.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal

import pytest

from trading_report import charts


def series(closes: list[str], *, spread: str = "2") -> list[charts.Bar]:
    """Bars around each close, with a real high and low."""
    out = []
    day = date(2026, 7, 1)
    edge = Decimal(spread)
    for i, close in enumerate(closes):
        price = Decimal(close)
        out.append(
            charts.Bar(
                day=day + timedelta(days=i),
                open=price - edge / 2,
                high=price + edge,
                low=price - edge,
                close=price,
            )
        )
    return out


class TestItDrawsTheBarsItWasGiven:
    def test_an_empty_series_draws_nothing_rather_than_an_empty_frame(self) -> None:
        """An axis with no candles reads as "this name did not trade"."""
        assert charts.render([]) == ""

    def test_every_session_in_the_window_gets_a_candle(self) -> None:
        svg = charts.render(series(["100", "101", "99", "102"]))

        bodies = re.findall(r'<path d="([^"]*)" fill="', svg)
        drawn = sum(body.count("M") for body in bodies)
        assert drawn == 4

    def test_a_rising_and_a_falling_session_are_different_colours(self) -> None:
        """``series`` builds every bar closing above its open, so the falling
        one is written out: the colour is decided by open against close, not
        by this close against the last."""
        rising, falling = series(["100", "120"])
        falling = charts.Bar(
            day=falling.day,
            open=Decimal("125"),
            high=Decimal("126"),
            low=Decimal("118"),
            close=Decimal("119"),
        )

        svg = charts.render([rising, falling])

        assert charts.UP in svg
        assert charts.DOWN in svg

    def test_only_the_last_sessions_are_drawn(self) -> None:
        """Three months, like the original. The earlier bars still feed the
        averages — a 50MA that starts a third of the way across the picture is
        the one thing a reader would take as a signal."""
        svg = charts.render(series([str(100 + i) for i in range(120)]), sessions=65)

        # Matched on the attribute, not on a colour: the fills became
        # `var(--green,...)` on 2026-09-26 so the chart follows the page's
        # theme, and a test anchored to `fill="#` silently found nothing and
        # asserted 0 == 65.
        bodies = re.findall(r'<path d="([^"]*)" fill="', svg)
        assert sum(body.count("M") for body in bodies) == 65
        assert f'stroke="{charts.MA_COLOURS[50]}"' in svg, (
            "the 50MA is drawn from the first visible bar"
        )


class TestTheScaleIncludesWhatIsMarked:
    def test_a_stop_below_every_low_is_still_on_the_chart(self) -> None:
        """A stop drawn off the bottom edge is a stop that looks safe."""
        bars = series(["100"] * 30)
        svg = charts.render(bars, charts.Marks(stop=Decimal("60")))

        ys = [float(m) for m in re.findall(r'<line x1="8" y1="([\d.]+)"', svg)]
        assert ys, "the stop line is drawn"
        assert max(ys) <= charts.HEIGHT, "and inside the frame"

    def test_the_entry_and_stop_are_labelled(self) -> None:
        svg = charts.render(
            series(["100"] * 30), charts.Marks(entry=Decimal("102"), stop=Decimal("96"))
        )

        assert ">entry<" in svg
        assert ">stop<" in svg

    def test_no_marks_means_no_lines(self) -> None:
        svg = charts.render(series(["100"] * 30))

        assert ">entry<" not in svg
        assert ">stop<" not in svg


class TestTheContractionIsOnlyShadedWhenThereIsOne:
    def test_a_band_is_drawn_when_bounds_are_given(self) -> None:
        svg = charts.render(
            series(["100"] * 30),
            charts.Marks(band_low=Decimal("98"), band_high=Decimal("103"), band_from=25),
        )

        assert charts.BAND in svg

    def test_no_bounds_shades_nothing(self) -> None:
        """SHILPAMED on 25 September had no base by the wick rule and the page
        said so in words. A band drawn round the last few sessions anyway
        would have contradicted it in the picture."""
        svg = charts.render(series(["100"] * 30))

        assert charts.BAND not in svg


class TestItIsSafeToInlineInThePage:
    def test_the_markup_is_a_single_svg_element(self) -> None:
        svg = charts.render(series(["100"] * 10))

        assert svg.startswith("<svg viewBox=")
        assert svg.endswith("</svg>")
        assert svg.count("<svg") == 1

    def test_nothing_is_fetched_from_outside_the_page(self) -> None:
        """The report has never loaded anything external and the chart must
        not be the first thing that does."""
        svg = charts.render(series(["100"] * 30), charts.Marks(entry=Decimal("101")))

        for forbidden in ("http://", "https://", "<image", "xlink:href", "url("):
            assert forbidden not in svg

    def test_it_stays_small_enough_to_ship_a_dozen(self) -> None:
        """Twelve of these ride in a page that is about 115 KB without them."""
        svg = charts.render(series([str(100 + i % 7) for i in range(65)]))

        assert len(svg) < 8_000, f"{len(svg):,} bytes a chart is too much for twelve"


class TestTheAverageIsTheOneTheSetupUses:
    @pytest.mark.parametrize("period", [10, 20, 50])
    def test_each_average_has_its_own_colour(self, period: int) -> None:
        svg = charts.render(series([str(100 + i) for i in range(80)]))

        assert charts.MA_COLOURS[period] in svg

    def test_an_average_with_too_few_bars_is_not_drawn(self) -> None:
        """Not drawn short, and not drawn from a shorter window wearing the
        same label."""
        svg = charts.render(series(["100"] * 12))

        assert charts.MA_COLOURS[10] in svg
        assert charts.MA_COLOURS[50] not in svg


class TestTheRowSizedChart:
    """What actually ships in the table. The full-size version was the first
    attempt and filled half a screen a name."""

    def test_it_fits_in_a_cell(self) -> None:
        svg = charts.render_mini(series([str(100 + i % 9) for i in range(40)]))

        assert f'viewBox="0 0 {charts.MINI_WIDTH} {charts.MINI_HEIGHT}"' in svg
        assert len(svg) < 4_000, "a hundred of these ride in one page"

    def test_it_carries_no_axis_and_no_dates(self) -> None:
        """The row prints every price and the section says the dates. What the
        chart does carry is the *name* of each line — see the class below."""
        svg = charts.render_mini(
            series(["100"] * 40), charts.Marks(entry=Decimal("104"), stop=Decimal("97"))
        )

        assert "Jul" not in svg and "Sep" not in svg, "no dates"
        labels = set(re.findall(r">([a-z]+)</text>", svg))
        assert labels <= {"entry", "stop", "base"}, f"nothing else is labelled: {labels}"

    def test_the_two_levels_are_drawn(self) -> None:
        svg = charts.render_mini(
            series(["100"] * 40), charts.Marks(entry=Decimal("104"), stop=Decimal("97"))
        )

        assert svg.count("stroke-dasharray") == 2

    def test_a_stop_under_every_low_still_fits_the_frame(self) -> None:
        svg = charts.render_mini(series(["100"] * 40), charts.Marks(stop=Decimal("70")))

        ys = [float(m) for m in re.findall(r'y1="([\d.]+)"', svg)]
        assert ys and max(ys) <= charts.MINI_HEIGHT

    def test_an_empty_series_draws_nothing(self) -> None:
        assert charts.render_mini([]) == ""


class TestTheRowChartNamesItsLevels:
    """It was 210x54 for one afternoon and could not be read. An unlabelled
    dashed line is a line the reader has to guess at, and the two guesses are
    a buy and a loss."""

    def test_the_entry_and_stop_carry_their_names(self) -> None:
        svg = charts.render_mini(
            series(["100"] * 40), charts.Marks(entry=Decimal("104"), stop=Decimal("97"))
        )

        assert ">entry<" in svg
        assert ">stop<" in svg

    def test_the_base_is_shaded_and_named(self) -> None:
        svg = charts.render_mini(
            series(["100"] * 40),
            charts.Marks(band_low=Decimal("98"), band_high=Decimal("103")),
        )

        assert charts.BAND in svg
        assert ">base<" in svg

    def test_it_is_big_enough_to_read(self) -> None:
        assert charts.MINI_WIDTH >= 320
        assert charts.MINI_HEIGHT >= 110

    def test_the_band_starts_where_price_leaves_it(self) -> None:
        """Walked back from the newest bar: ``base_bounds`` answers with a
        price range, not with the bars it came from."""
        bars = series(["100"] * 20) + series(["140"] * 5)

        start = charts._band_start(bars, Decimal("138"), Decimal("142"))

        assert start == 20, "only the five that sit inside the range"


# `base_of` and the tests for it stayed in equity-service: finding a base is
# that book's own contraction rule, and this module only draws the band it is
# handed. See the note beside `_band_start`.


class TestItFoldsToTheTimeframeItWasAskedFor:
    """The chart must be drawn on the bars the candidate was found on.

    Until 2026-09-26 the report drew every candidate on daily bars whatever
    strategy produced it, so a WEEKLY setup got daily candles with
    weekly-derived entry and stop lines across them. GRWRHITECH on the 25th
    showed an entry of 7,477.50 — its weekly base high — over daily bars that
    had not traded above 6,770 in eight sessions. The entry was right for its
    timeframe; the picture was the wrong timeframe.
    """

    def test_one_day_per_bar_is_the_identity(self) -> None:
        bars = series([str(100 + i) for i in range(10)])
        assert charts.fold(bars, 1) == list(bars)

    def test_five_daily_bars_become_one_weekly_bar(self) -> None:
        folded = charts.fold(series([str(100 + i) for i in range(20)]), 5)
        assert len(folded) == 4

    def test_the_weekly_bar_spans_its_week(self) -> None:
        """Open from the first session, close from the last, and the extremes
        from the whole block — not from the closes, which would draw a body
        with no wicks and look like a calmer week than it was."""
        daily = series(["100", "110", "90", "105", "102"])
        week = charts.fold(daily, 5)[0]

        assert week.open == daily[0].open
        assert week.close == daily[-1].close
        assert week.high == max(b.high for b in daily)
        assert week.low == min(b.low for b in daily)
        assert week.day == daily[-1].day, "the bar is dated by the session it ends on"

    def test_the_newest_bar_ends_on_the_latest_session(self) -> None:
        """Chunked from the right, like `Timeframe.bars`. Chunking from the
        left would leave the last complete bar days old on a chart drawn for
        tonight's decision."""
        daily = series([str(100 + i) for i in range(22)])
        folded = charts.fold(daily, 5)

        assert folded[-1].day == daily[-1].day
        assert folded[-1].close == daily[-1].close

    def test_a_short_oldest_block_is_kept_not_dropped(self) -> None:
        """22 sessions is four weeks and two days. The stub is the oldest bar,
        which nothing measures against, and dropping it would silently shorten
        the window a reader thinks they are looking at."""
        folded = charts.fold(series([str(100 + i) for i in range(22)]), 5)
        assert len(folded) == 5

    def test_folding_nothing_gives_nothing(self) -> None:
        assert charts.fold([], 5) == []


class TestTheLevelsOnAnOpenTrade:
    """Four lines, and the one that matters most is the pair.

    A chart carrying only the current stop says a position is risking 2% when
    it opened risking 8% and is now protecting a gain. The gap between where
    the stop started and where it is now *is* what the trail has done.
    """

    def test_all_four_levels_are_drawn_and_labelled(self) -> None:
        svg = charts.render_mini(
            series([str(100 + i) for i in range(60)]),
            charts.Marks(
                entry=Decimal("140"),
                stop=Decimal("145"),
                initial_stop=Decimal("130"),
                target=Decimal("155"),
            ),
        )
        for label in (">entry<", ">stop<", ">init<", ">target<"):
            assert label in svg, label

    def test_a_target_out_of_reach_is_clamped_rather_than_scaled_into(self) -> None:
        """A 10R target sits multiples of the price above the candles.
        Including it in the y-range compresses forty sessions into a strip and
        the picture stops showing what the price is doing."""
        bars = series([str(100 + i) for i in range(60)])
        near = charts.render_mini(bars, charts.Marks(entry=Decimal(140), target=Decimal(155)))
        far = charts.render_mini(bars, charts.Marks(entry=Decimal(140), target=Decimal(9000)))

        assert ">target<" in near
        assert ">target ^<" in far, "off-scale says 'further than this', not a wrong level"
        assert near.count("<path") == far.count("<path"), "the candles keep their geometry"

    def test_two_levels_at_one_height_do_not_overprint_their_labels(self) -> None:
        """The stronger line takes the row; the fainter keeps its line without
        a caption. Two labels at the same y are unreadable."""
        svg = charts.render_mini(
            series([str(100 + i) for i in range(60)]),
            charts.Marks(entry=Decimal("140"), stop=Decimal("130"), initial_stop=Decimal("130")),
        )
        assert svg.count(">stop<") == 1
        assert ">init<" not in svg

    def test_the_levels_name_no_colour_of_their_own(self) -> None:
        """Every colour is a reference into the page's theme, so a chart
        follows a theme swap instead of having to be found and re-coloured."""
        svg = charts.render_mini(
            series([str(100 + i) for i in range(60)]),
            charts.Marks(
                entry=Decimal("140"),
                stop=Decimal("145"),
                initial_stop=Decimal("130"),
                target=Decimal("155"),
            ),
        )
        assert re.search(r"#[0-9a-f]{6}(?![^\"]*var\()", svg) is None or "var(--" in svg
        for token in ("var(--green", "var(--red", "var(--faint", "var(--blue"):
            assert token in svg, token
