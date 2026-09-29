"""Rendering for the daily trading reports, shared by the two book services.

Pure: finished rows in, a self-contained HTML page out. Nothing here reads a
database, a venue or the clock — that is the test for whether code belongs in
this package rather than in the service that calls it.
"""

from trading_report import charts, report
from trading_report.report import (
    Bar,
    Card,
    Cell,
    Dot,
    Figure,
    Link,
    Report,
    Section,
    Stat,
    Table,
    render_html,
)

__all__ = [
    "Bar",
    "Card",
    "Cell",
    "Dot",
    "Figure",
    "Link",
    "Report",
    "Section",
    "Stat",
    "Table",
    "charts",
    "render_html",
    "report",
]
