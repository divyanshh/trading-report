# trading-report

The daily report renderer shared by
[`equity-service`](https://github.com/divyanshh/equity-service) and
`crypto-service`, and the stylesheet the
[trading-book](https://divyanshh.github.io/trading-book/) archive re-skins
itself from.

**Pure by contract.** Finished rows in, one self-contained HTML page out.
Nothing here reads a database, a venue or the clock, and that is the test for
whether something belongs in this package rather than in the service calling
it. Models, strategies, brokers and limits stay in their services: equity has
tenants, trading sessions and rupees; crypto has leverage, liquidation prices
and contract multipliers spanning six orders of magnitude. A shared `Trade`
would be a lie that costs money. A shared stylesheet, at worst, looks slightly
off.

## Why it exists

Both services rendered the same page from their own copy of these three files.
On 2026-09-29 one change — drawing a position's initial stop, current stop and
target — was made twice by hand, and the second copy got it wrong: the mini
chart's coordinates were pasted over the full-size `render`. Nothing failed.
mypy passed. Three thousand tests passed. It surfaced only because a test
written against the *other* copy noticed a missing label.

## Install

```
pip install "trading-report @ git+https://github.com/divyanshh/trading-report@v1.0.0"
```

Pin both services to the same tag and bump them together. Skew here means the
archive carries two themes at once, which is the problem this package was made
to remove.

## Use

```python
from trading_report import Cell, Report, Section, Table, charts, render_html

page = render_html(
    Report(
        title="Morning Book",
        generated="Built 2026-09-29 14:28 IST",
        verdict="Entries PERMITTED",
        verdict_detail="Book and venue agree and the regime is bull.",
        verdict_blocked=False,
        sections=[Section(title="Positions", tables=[Table(headers=[...], rows=[...])])],
    )
)
```

Charts are drawn from `charts.Bar` rows and marked with `charts.Marks`:

```python
charts.render_mini(
    bars,
    charts.Marks(entry=entry, stop=stop_now, initial_stop=stop_at_entry, target=target),
)
```

Adapters live with the thing they adapt — equity's `base_of` needs its own
contraction rule, crypto's `from_candles` needs its own `Candle` — so each
service keeps its own and passes `Bar` rows in.
