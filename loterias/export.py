"""Exporta o mesmo objeto apresentado na tela, inclusive o Mês da Sorte."""

import io
import json
from dataclasses import asdict, is_dataclass
from decimal import Decimal

import pandas as pd

from .config import MONTHS
from .generation import Ticket
from .probability import ticket_price


def tickets_table(tickets: list[Ticket], lottery, base_price: Decimal) -> pd.DataFrame:
    rows = []
    for i, ticket in enumerate(tickets, 1):
        row = {
            "Jogo": i,
            **{f"N{j:02d}": n for j, n in enumerate(ticket.numbers, 1)},
            "Soma": sum(ticket.numbers),
            "Custo (R$)": float(ticket_price(lottery, len(ticket.numbers), base_price)),
        }
        if ticket.month is not None:
            row["Mês da Sorte"] = MONTHS[ticket.month - 1]
        rows.append(row)
    return pd.DataFrame(rows)


def csv_bytes(table: pd.DataFrame) -> bytes:
    return table.to_csv(index=False).encode("utf-8-sig")


def excel_bytes(table: pd.DataFrame, metadata: dict) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        table.to_excel(writer, sheet_name="Jogos", index=False)
        pd.DataFrame(
            [{"Campo": key, "Valor": str(value)} for key, value in metadata.items()]
        ).to_excel(writer, sheet_name="Informações", index=False)
    return buffer.getvalue()


def metadata_bytes(metadata: dict) -> bytes:
    def encode(value):
        return asdict(value) if is_dataclass(value) else str(value)

    return json.dumps(metadata, ensure_ascii=False, indent=2, default=encode).encode("utf-8")
