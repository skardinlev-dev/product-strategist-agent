"""Сценарный расчёт по учебной таблице подписки.

Запуск:
  python scripts/scenario.py --project demo/megafon-plus
  python scripts/scenario.py --project demo/megafon-plus --write

Считает вклад как выручка минус партнёрские и маркетинговые затраты.
Чувствительность меняет долю партнёров и июньский отток. Это не прогноз
реальной выручки МегаФона: источник чисел — учебный CSV.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import psa_common as c  # noqa: E402


def load(project: Path) -> list[dict]:
    path = project / "data" / "synthetic_metrics.csv"
    columns, rows = c.read_csv(path)
    missing = [name for name in (
        "month", "segment", "active_end", "churned", "price_rub", "revenue_rub",
        "partner_cost_rub", "marketing_cost_rub", "data_origin",
    ) if name not in columns]
    if missing:
        raise SystemExit("В таблице нет колонок: " + ", ".join(missing))
    parsed = []
    for row in rows:
        item = dict(row)
        for key in (
            "active_start", "new_subscribers", "active_end", "churned", "price_rub",
            "revenue_rub", "partner_cost_rub", "marketing_cost_rub",
        ):
            item[key] = int(float(row[key]))
        item["active_users_share"] = float(row["active_users_share"])
        parsed.append(item)
    origins = {row["data_origin"] for row in parsed}
    if origins != {c.SYNTHETIC_MARKER}:
        raise SystemExit("scenario.py считает только учебный набор с пометкой synthetic_educational")
    return parsed


def contribution(rows: list[dict], partner_of_revenue: float | None = None) -> int:
    total = 0
    for row in rows:
        partner = row["partner_cost_rub"]
        if partner_of_revenue is not None and row["price_rub"] > 0:
            partner = int(row["revenue_rub"] * partner_of_revenue)
        total += row["revenue_rub"] - partner - row["marketing_cost_rub"]
    return total


def june_with_churn(rows: list[dict], multiplier: float) -> dict:
    """Пересчитывает только июнь: отток платящих умножается, цена и приток те же."""
    revenue = partner = marketing = 0
    payers_end = 0
    for row in rows:
        if row["month"] != "2026-06":
            continue
        marketing += row["marketing_cost_rub"]
        if row["price_rub"] == 0:
            partner += row["partner_cost_rub"]
            continue
        churned = round(row["churned"] * multiplier)
        end = max(row["active_start"] + row["new_subscribers"] - churned, 0)
        month_revenue = round((row["active_start"] + end) / 2 * row["price_rub"])
        revenue += month_revenue
        partner += month_revenue * 3 // 4
        payers_end += end
    return {
        "revenue_rub": revenue,
        "partner_cost_rub": partner,
        "marketing_cost_rub": marketing,
        "contribution_rub": revenue - partner - marketing,
        "paying_end": payers_end,
    }


def report(rows: list[dict]) -> str:
    lines = [
        "# Учебный сценарный расчёт",
        "",
        "Цифры ниже получены скриптом scripts/scenario.py из data/synthetic_metrics.csv.",
        "Это не прогноз и не отчётность МегаФона. Доля партнёров 3/4 выручки — допущение генератора таблицы.",
        "",
        "## Вклад за январь–июнь 2026, учебные рубли",
        "",
        "| Сегмент | Выручка | Партнёры | Маркетинг | Вклад |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    segments = []
    for row in rows:
        if row["segment"] not in segments:
            segments.append(row["segment"])
    grand = [0, 0, 0]
    for segment in segments:
        part = [row for row in rows if row["segment"] == segment]
        revenue = sum(row["revenue_rub"] for row in part)
        partner = sum(row["partner_cost_rub"] for row in part)
        marketing = sum(row["marketing_cost_rub"] for row in part)
        lines.append(f"| {segment} | {revenue} | {partner} | {marketing} | {revenue - partner - marketing} |")
        grand[0] += revenue
        grand[1] += partner
        grand[2] += marketing
    lines.append(f"| итого | {grand[0]} | {grand[1]} | {grand[2]} | {grand[0] - grand[1] - grand[2]} |")
    lines += ["", "## Чувствительность вклада за полгода к доле партнёров", "",
              "Платные сегменты пересчитаны как доля выручки. Включённые в тариф не меняются.", ""]
    base = contribution(rows)
    for ratio, title in ((0.60, "оптимистичный"), (0.75, "базовый"), (0.85, "пессимистичный")):
        value = contribution(rows, ratio)
        lines.append(f"- {title}, доля {ratio:.0%}: вклад {value} ₽ (сдвиг к базовой таблице {value - base:+} ₽)")
    lines += ["", "## Июнь при другом оттоке платящих", "",
              "Приток и цена июня те же. Это сценарий на учебных данных, не прогноз.", ""]
    for multiplier, title in ((0.7, "оптимистичный"), (1.0, "базовый"), (1.4, "пессимистичный")):
        case = june_with_churn(rows, multiplier)
        lines.append(
            f"- {title}, отток ×{multiplier}: платящих на конец июня {case['paying_end']}, "
            f"вклад июня {case['contribution_rub']} ₽"
        )
    lines += ["", "Сильнее всего вклад двигает доля партнёров, а не разовый скачок оттока:",
              "сдвиг доли с 75% до 85% меняет полугодовой вклад на миллионы учебных рублей,",
              "а умножение июньского оттока на 1,4 меняет только один месяц.", ""]
    return "\n".join(lines)


def main() -> int:
    c.setup_console()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", help="папка проекта; по умолчанию активный проект")
    parser.add_argument("--write", action="store_true", help="записать data/scenario.md")
    args = parser.parse_args()
    project = c.resolve_project(args.project)
    text = report(load(project))
    if args.write:
        path = project / "data" / "scenario.md"
        path.write_text(text, encoding="utf-8")
        print(f"Сохранено: {c.rel(path)}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
