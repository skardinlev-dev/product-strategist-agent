"""Собирает учебный помесячный CSV демонстрационного кейса.

Запуск из корня репозитория:
  python scripts/build_synthetic_demo.py

Файл перезаписывается детерминированно. Это не статистика МегаФона.
Формулы зафиксированы здесь, а не в таблице вручную:
- active_end = active_start + new_subscribers - churned
- revenue_rub = round((active_start + active_end) / 2 * price_rub)
- у платных сегментов partner_cost_rub = revenue_rub * 3 // 4
- у включённых в тариф partner_cost_rub = active_end * 40
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import psa_common as c  # noqa: E402

OUT = c.ROOT / "demo" / "megafon-plus" / "data" / "synthetic_metrics.csv"

# new, churned, price_rub, active_users_share, marketing_cost_rub
PAID = {
    "megafon_balance": [
        (1500, 1100, 399, 0.46, 500_000),
        (1400, 1200, 399, 0.45, 500_000),
        (1300, 1250, 399, 0.44, 500_000),
        (1100, 1300, 399, 0.43, 500_000),
        (900, 1400, 399, 0.41, 500_000),
        (400, 1800, 460, 0.37, 500_000),
    ],
    "card_other_operator": [
        (800, 700, 399, 0.58, 300_000),
        (700, 750, 399, 0.57, 300_000),
        (650, 800, 399, 0.55, 300_000),
        (500, 850, 399, 0.52, 300_000),
        (400, 900, 399, 0.49, 300_000),
        (150, 1200, 460, 0.44, 300_000),
    ],
}
INCLUDED = {
    "tariff_included": [
        (500, 400, 0.19),
        (450, 420, 0.19),
        (400, 430, 0.18),
        (380, 450, 0.18),
        (350, 480, 0.17),
        (300, 500, 0.16),
    ]
}
STARTS = {"megafon_balance": 12_000, "card_other_operator": 6_000, "tariff_included": 20_000}
MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]


def rows() -> list[dict]:
    table = []
    for segment, series in PAID.items():
        active = STARTS[segment]
        for month, (new, churned, price, share, marketing) in zip(MONTHS, series):
            end = active + new - churned
            revenue = round((active + end) / 2 * price)
            table.append({
                "month": month, "segment": segment, "active_start": active,
                "new_subscribers": new, "churned": churned, "active_end": end,
                "price_rub": price, "revenue_rub": revenue,
                "partner_cost_rub": revenue * 3 // 4, "marketing_cost_rub": marketing,
                "active_users_share": share, "data_origin": c.SYNTHETIC_MARKER,
            })
            active = end
    for segment, series in INCLUDED.items():
        active = STARTS[segment]
        for month, (new, churned, share) in zip(MONTHS, series):
            end = active + new - churned
            table.append({
                "month": month, "segment": segment, "active_start": active,
                "new_subscribers": new, "churned": churned, "active_end": end,
                "price_rub": 0, "revenue_rub": 0, "partner_cost_rub": end * 40,
                "marketing_cost_rub": 0, "active_users_share": share,
                "data_origin": c.SYNTHETIC_MARKER,
            })
            active = end
    return table


def main() -> int:
    c.setup_console()
    data = rows()
    c.write_csv(OUT, [
        "month", "segment", "active_start", "new_subscribers", "churned", "active_end",
        "price_rub", "revenue_rub", "partner_cost_rub", "marketing_cost_rub",
        "active_users_share", "data_origin",
    ], data)
    print(f"Записано строк: {len(data)} → {c.rel(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
