"""Rendering a daily trading report as one self-contained HTML page.

Shared by `equity-service` and `crypto-service`, which publish the same page
for two very different books. It lives outside both because on 2026-09-29 the
same change was made twice by hand and got it wrong once — the mini chart's
coordinates were pasted over the full-size `render`, and nothing failed: mypy
passed and three thousand tests passed. It surfaced only because a test
written against the *other* copy noticed a missing label.

**Pure, and that is the whole boundary.** Nothing here touches a database, a
network or the clock: it takes finished rows and returns a string. That is
what let the equity renderer become the crypto one in an afternoon with
nothing to strip out, and it is the test for whether something belongs in this
package at all. Models, strategies, brokers and limits stay in their own
services — equity has tenants, sessions and rupees, crypto has leverage,
liquidation and contract multipliers spanning six orders of magnitude, and a
shared `Trade` would be a lie that costs money rather than a stylesheet that
looks slightly off.

Every number arrives already formatted, because a renderer that computes is a
second place for the arithmetic to disagree with the first.

**Self-contained by necessity.** One file with inlined CSS and no external
requests, because the page has to survive being saved, mailed, or opened on a
phone with no network. No JavaScript: a report that needs to execute to be
read cannot be printed reliably. The stylesheet is the page's own — see
:data:`CSS`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Final

CSS: Final[str] = (Path(__file__).parent / "theme.css").read_text(encoding="utf-8")
"""The Morning Book's stylesheet, inlined into every page.

A light fintech-dashboard theme — white cards on a pale canvas, blue accents,
green/red/amber semantics, dense tabular-numeric tables — the register the
owner reads beside Trendlyne, Screener and Kite. Light only, on purpose: an
auto-dark page beside three light ones was the complaint. The palette is
Tailwind CSS's colour scales (MIT); the type is Inter where installed.

Every rule targets a class the renderer emits, so an older stored page
re-skins by swapping its ``<style>`` block — which the trading-book mirror
does to keep the archive consistent. Pico CSS was the base for one release
(v151) and is gone: a classless framework's element styles fought the tables.
"""


@dataclass(frozen=True, slots=True)
class Cell:
    """One value, plus how it should read.

    ``tone`` is the whole reason this is not a bare string: a stop that
    breaches the cap and a stop that clears it are different facts, and a
    reader scanning ninety rows finds the difference by colour long before
    they find it by arithmetic.
    """

    text: str
    tone: str = ""
    left: bool = False

    href: str = ""
    """Makes the cell a link. Navigation, not a fetch: the page still loads
    nothing from outside itself, which is what ``no external requests`` has
    always meant here."""

    svg: str = ""
    """Markup shown instead of the text, for a chart in a row.

    Inserted verbatim, so whatever builds it owns the escaping —
    :mod:`trade_service.scanning.charts` emits numbers it computed, never a
    value off the wire. ``text`` stays as the cell's meaning for anything that
    reads the table as data.
    """

    bar: int | None = None
    """Percent of the column's width to tint behind the figure, 0-100.

    A data bar, in the spreadsheet sense: the number stays exact and readable
    and the bar behind it gives the column a shape the eye reads before the
    arithmetic. Set on the one or two columns per table where magnitude is the
    point — a stop width against its cap, a sector's mean move — and left
    ``None`` everywhere else, because a table where every cell is a bar is a
    chart nobody can read."""


@dataclass(frozen=True, slots=True)
class Table:
    headers: list[str]
    rows: list[list[Cell]]
    cards: list[Card] = field(default_factory=list)
    """Shown instead of the rows when present, under the same caption.

    A group of a dozen names reads better as panels than as a dozen lines of
    eighteen columns; the same group at several hundred (``--include-blocked``)
    reads better as the table. The caller decides which, and the caption — the
    funnel — is the same either way."""

    caption: str = ""
    flag: Dot | None = None
    """A chip above the caption, for something true of the whole table.

    It exists for one fact the rows cannot carry: that they are not from
    today. STRIKE and REVERSAL are not in the nightly scan, so their rows are
    whatever the last manual run produced — correct numbers, wrong session,
    and indistinguishable from fresh ones until the page says so."""

    empty_note: str = "Nothing here."
    """Shown instead of an empty table. A table with no rows and no
    explanation reads as a broken report; every section says why it is
    empty, because 'no setups' and 'the source did not answer' look
    identical otherwise."""


@dataclass(frozen=True, slots=True)
class Dot:
    """One gate, as an indicator light.

    Eight gate verdicts are a sentence to read and a row of dots to glance at.
    The ``title`` is the whole reason a fail is not just red: hovering says
    *why* — "8.4% below entry, over the 5.0% cap" — without the row having to
    carry a sentence."""

    label: str
    tone: str = ""
    """``pass`` / ``fail`` / ``warn`` / empty for a gate that does not count."""
    title: str = ""


@dataclass(frozen=True, slots=True)
class Bar:
    """A figure against the limit it is judged by.

    "3.0%" and "30.0%" are the same amount of ink and a very different setup.
    ``fill`` is how much of the track the value takes; ``mark`` is where the
    cap sits on it, so a bar that stops short of the mark passed and one that
    runs past it did not."""

    label: str
    value: str
    fill: int
    """0-100. The caller scales; the renderer does no arithmetic."""
    mark: int | None = None
    tone: str = ""
    caption: str = ""


@dataclass(frozen=True, slots=True)
class Stat:
    """One labelled figure inside a card."""

    label: str
    value: str
    tone: str = ""


@dataclass(frozen=True, slots=True)
class Link:
    """A headline, or anything else worth clicking out to.

    ``meta`` is the attribution — publisher and age — kept beside the text
    rather than inside it, because a reader decides whether to open a story on
    who wrote it and when at least as often as on what it says.
    """

    text: str
    href: str = ""
    tone: str = ""
    meta: str = ""


@dataclass(frozen=True, slots=True)
class Card:
    """One name, presented as a panel rather than a row.

    A table is right for forty rows and wrong for twelve: at twelve the
    question stops being "which line do I want" and becomes "what is the case
    for this name", and the answer is a headline, the gate lights, the stop
    against its cap, and the sizing — which is a card. The morning shortlist
    is a card grid; ``--include-blocked``'s several hundred rows stay a table.
    """

    title: str
    subtitle: str = ""
    badge: str = ""
    badge_tone: str = ""
    dots: tuple[Dot, ...] = ()
    bars: tuple[Bar, ...] = ()
    stats: tuple[Stat, ...] = ()
    links: tuple[Link, ...] = ()
    note: str = ""
    note_tone: str = ""
    href: str = ""


@dataclass(frozen=True, slots=True)
class Figure:
    """One chart, with the name and the line of fact that belong beside it.

    ``svg`` is markup, not a URL and not a data URI: the page has never loaded
    anything from outside itself, and a chart that arrives over the network is
    a chart that is missing the first time the archive is read somewhere the
    host is not reachable.

    It is inserted verbatim, so whatever builds it owns the escaping —
    :mod:`trade_service.scanning.charts` emits numbers it computed and text it
    formatted, never a value off the wire.
    """

    title: str
    svg: str
    caption: str = ""
    tone: str = ""


@dataclass(frozen=True, slots=True)
class Section:
    title: str
    tables: list[Table] = field(default_factory=list)
    lead: str = ""
    notes: list[str] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    """Full-size charts under the tables.

    Unused by the daily report since 2026-09-25: a grid of half-screen charts
    is a page nobody scrolls, and the picture belongs beside the numbers it
    describes. The row carries a :attr:`Cell.svg` chart instead. Kept because
    a one-name page — an IPO note, a post-mortem — is exactly where a full
    chart earns its space."""


@dataclass(frozen=True, slots=True)
class Report:
    title: str
    generated: str
    verdict: str
    verdict_detail: str
    verdict_blocked: bool
    sections: list[Section] = field(default_factory=list)
    stats: list[tuple[str, str]] = field(default_factory=list)
    """Headline numbers, as (value, label).

    Seven sections and a thousand rows need somewhere the eye lands first.
    Computed by the caller from the same rows the tables render, never
    recounted here — a summary that disagrees with the table below it is
    worse than no summary."""

    signals: list[Dot] = field(default_factory=list)
    """The gates, as lights on the verdict plate. Two on this page — breadth
    and follow-through — and a reader should not have to find them inside a
    sentence to learn which one is shut."""

    eyebrow: str = ""

    footer: str = (
        "Generated by `daily_report`. Every number here is a record of a job "
        "that ran, not a recomputation at render time. Sections that are empty "
        "say why."
    )
    """The line under the page. A parameter rather than a constant because the
    two services that share this renderer are not the same service, and a
    crypto page claiming to come from equity-service is the kind of small lie
    that costs somebody ten minutes a year from now."""


def _cell(cell: Cell) -> str:
    """One cell. A toned, left-aligned cell becomes a chip.

    Verdicts and flags read as state rather than prose, and a reader scanning
    ninety rows finds state by shape long before they find it by reading. The
    numeric columns stay plain — a chip around every figure would be noise.
    """
    classes = " ".join(part for part in (cell.tone, "l" if cell.left else "") if part)
    attribute = f' class="{classes}"' if classes else ""
    if cell.svg:
        return f"<td{attribute}>{cell.svg}</td>"
    body = escape(cell.text)
    if cell.href:
        body = f'<a href="{escape(cell.href)}" target="_blank" rel="noopener">{body}</a>'
    if cell.tone and cell.left and cell.text not in {"", "—"}:
        body = f"<span>{body}</span>"
    elif cell.bar is not None:
        # Clamped here rather than trusted: a width over 100% paints outside
        # the cell and under 0 disappears, and neither is a thing the caller
        # meant to say.
        width = max(0, min(100, cell.bar))
        body = f'<span class="cellbar" style="--w:{width}%">{body}</span>'
    return f"<td{attribute}>{body}</td>"


def _dot(dot: Dot) -> str:
    title = f' title="{escape(dot.title)}"' if dot.title else ""
    tone = f" {dot.tone}" if dot.tone else ""
    return f'<span class="dot{tone}"{title}>{escape(dot.label)}</span>'


def _bar(bar: Bar) -> str:
    fill = max(0, min(100, bar.fill))
    mark = f'<i style="left:{max(0, min(100, bar.mark))}%"></i>' if bar.mark is not None else ""
    tone = f" {bar.tone}" if bar.tone else ""
    caption = f"<span>{escape(bar.caption)}</span>" if bar.caption else "<span></span>"
    return (
        f'<div class="bar"><div class="barhead"><span>{escape(bar.label)}</span>'
        f'<b class="{bar.tone}">{escape(bar.value)}</b></div>'
        f'<div class="track"><div class="fill{tone}" style="width:{fill}%"></div>{mark}</div>'
        f'<div class="barfoot">{caption}</div></div>'
    )


def _links(links: tuple[Link, ...]) -> str:
    rows = "".join(
        f'<li class="{link.tone}">'
        + (
            f'<a href="{escape(link.href)}" target="_blank" rel="noopener">{escape(link.text)}</a>'
            if link.href
            else escape(link.text)
        )
        + (f"<span>{escape(link.meta)}</span>" if link.meta else "")
        + "</li>"
        for link in links
    )
    return f'<ul class="links">{rows}</ul>'


def _card(card: Card) -> str:
    title = escape(card.title)
    if card.href:
        title = f'<a href="{escape(card.href)}">{title}</a>'
    badge = (
        f'<span class="badge {card.badge_tone}">{escape(card.badge)}</span>' if card.badge else ""
    )
    parts = [f"<header><h3>{title}</h3>{badge}</header>"]
    if card.subtitle:
        parts.append(f'<p class="meta">{escape(card.subtitle)}</p>')
    if card.dots:
        parts.append('<div class="dots">' + "".join(_dot(d) for d in card.dots) + "</div>")
    parts.extend(_bar(bar) for bar in card.bars)
    if card.stats:
        parts.append(
            '<dl class="stats">'
            + "".join(
                f"<div><dt>{escape(stat.label)}</dt>"
                f'<dd class="{stat.tone}">{escape(stat.value)}</dd></div>'
                for stat in card.stats
            )
            + "</dl>"
        )
    if card.links:
        parts.append(_links(card.links))
    if card.note:
        parts.append(f'<p class="cardnote {card.note_tone}">{escape(card.note)}</p>')
    return '<article class="card">' + "".join(parts) + "</article>"


def _table(table: Table) -> str:
    caption = f'<p class="sub">{escape(table.caption)}</p>' if table.caption else ""
    if table.flag is not None:
        caption = f'<div class="dots">{_dot(table.flag)}</div>' + caption
    if table.cards:
        return f'{caption}<div class="cards">' + "".join(_card(c) for c in table.cards) + "</div>"
    if not table.rows:
        # The caption stays: on a page that lists only actionable setups, the
        # ordinary morning is every table empty, and the caption is where the
        # funnel (scanned, stop derived, near-passes) is stated.
        return f'{caption}<p class="empty">{escape(table.empty_note)}</p>'
    head = "".join(
        f'<th class="l">{escape(h)}</th>' if i < 2 else f"<th>{escape(h)}</th>"
        for i, h in enumerate(table.headers)
    )
    body = "".join("<tr>" + "".join(_cell(c) for c in row) + "</tr>" for row in table.rows)
    return (
        f'{caption}<div class="scroll"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def _slug(title: str) -> str:
    """An anchor id from a section title. Stable across runs, so a bookmarked
    link keeps working when the numbers change."""
    return "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")


def _section(section: Section) -> str:
    parts = [f'<h2 id="{_slug(section.title)}">{escape(section.title)}</h2>']
    if section.lead:
        parts.append(f'<p class="lead">{escape(section.lead)}</p>')
    parts.extend(_table(table) for table in section.tables)
    if section.figures:
        parts.append(
            '<div class="figures">'
            + "".join(_figure(figure) for figure in section.figures)
            + "</div>"
        )
    parts.extend(f'<p class="note">{escape(note)}</p>' for note in section.notes)
    return "".join(parts)


def _figure(figure: Figure) -> str:
    tone = f" {figure.tone}" if figure.tone else ""
    caption = f"<figcaption>{escape(figure.caption)}</figcaption>" if figure.caption else ""
    return (
        f'<figure class="fig{tone}"><h3>{escape(figure.title)}</h3>{figure.svg}{caption}</figure>'
    )


def render_html(report: Report) -> str:
    """The whole report as one string. No I/O, no clock, no network."""
    state = "blocked" if report.verdict_blocked else "open"
    body = "".join(_section(section) for section in report.sections)
    glance = (
        '<div class="glance">'
        + "".join(
            f'<div><div class="n">{escape(value)}</div><div class="k">{escape(label)}</div></div>'
            for value, label in report.stats
        )
        + "</div>"
        if report.stats
        else ""
    )
    toc = (
        '<nav class="toc">'
        + "".join(
            f'<a href="#{_slug(section.title)}">{escape(section.title)}</a>'
            for section in report.sections
        )
        + "</nav>"
        if len(report.sections) > 2
        else ""
    )
    signals = (
        '<div class="signals">' + "".join(_dot(d) for d in report.signals) + "</div>"
        if report.signals
        else ""
    )
    eyebrow = f'<p class="eyebrow">{escape(report.eyebrow)}</p>' if report.eyebrow else ""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(report.title)}</title><style>{CSS}</style></head><body>"
        f'<div class="wrap">{eyebrow}<h1>{escape(report.title)}</h1>'
        f'<p class="stamp">{escape(report.generated)}</p>'
        f'<div class="plate {state}"><div class="state">{escape(report.verdict)}</div>'
        f"{signals}<p>{escape(report.verdict_detail)}</p></div>"
        f"{glance}{toc}{body}"
        f"<footer>{escape(report.footer)}</footer>"
        "</div></body></html>"
    )
