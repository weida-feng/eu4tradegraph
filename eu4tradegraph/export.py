"""Tabular exports preserve canonical IDs and numeric save fields."""

import csv
from io import StringIO

from .parser import TradeSnapshot


def node_rows(snapshot: TradeSnapshot) -> list[dict]:
    return [{"node_id": node.name, "label_zh": node.label, "inland": node.inland,
             "current": node.current, "local_value": node.local_value,
             "outgoing": node.outgoing} for node in snapshot.nodes]


def route_rows(snapshot: TradeSnapshot) -> list[dict]:
    return [{"source": snapshot.nodes[route.source].name,
             "target": snapshot.nodes[route.target].name, "value": route.value}
            for route in snapshot.routes]


def to_csv(rows: list[dict], columns: tuple[str, ...]) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")
