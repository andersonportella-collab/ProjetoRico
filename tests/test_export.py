import io
import json

import pandas as pd

from loterias.config import LOTTERIES, MONTHS
from loterias.export import csv_bytes, excel_bytes, metadata_bytes, tickets_table
from loterias.generation import generate_uniform


def test_months_costs_and_numbers_survive_both_exports():
    cfg = LOTTERIES["diadesorte"]
    tickets = generate_uniform(cfg, 8, 10, 42)
    table = tickets_table(tickets, cfg, cfg.base_price)
    csv = pd.read_csv(io.BytesIO(csv_bytes(table)))
    xlsx = pd.read_excel(io.BytesIO(excel_bytes(table, {"semente": 42})))
    for exported in (csv, xlsx):
        assert list(exported["Mês da Sorte"]) == [MONTHS[t.month - 1] for t in tickets]
        assert list(exported["Custo (R$)"]) == [20] * 10
        for i, ticket in enumerate(tickets):
            assert tuple(exported.loc[i, [f"N{j:02d}" for j in range(1, 9)]]) == ticket.numbers
    metadata = pd.read_excel(
        io.BytesIO(excel_bytes(table, {"semente": 42})), sheet_name="Informações"
    )
    assert str(metadata.loc[0, "Valor"]) == "42"
    assert json.loads(metadata_bytes({"semente": 42}))["semente"] == 42
