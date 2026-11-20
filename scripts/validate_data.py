"""Проверка таблицы помесячных показателей подписочного продукта.

Запуск: python scripts/validate_data.py <файл.csv> [--allow-unmarked]

Ожидаемые колонки:
month, segment, active_start, new_subscribers, churned, active_end, price_rub,
revenue_rub, partner_cost_rub, marketing_cost_rub, active_users_share, data_origin

Проверяется: состав колонок, типы и единицы, пропуски, повторы, непрерывность месяцев,
баланс базы (начало + приток − отток = конец), преемственность между месяцами,
согласованность выручки с ценой и базой, пометка происхождения данных.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import psa_common as c  # noqa: E402

COLUMNS = [
    "month", "segment", "active_start", "new_subscribers", "churned", "active_end",
    "price_rub", "revenue_rub", "partner_cost_rub", "marketing_cost_rub",
    "active_users_share", "data_origin",
]
INT_FIELDS = ["active_start", "new_subscribers", "churned", "active_end"]
MONEY_FIELDS = ["price_rub", "revenue_rub", "partner_cost_rub", "marketing_cost_rub"]
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
REVENUE_TOLERANCE = 0.01  # допустимое расхождение выручки с (средняя база × цена)


def next_month(month: str) -> str:
    year, mon = int(month[:4]), int(month[5:])
    return f"{year + (mon == 12)}-{1 if mon == 12 else mon + 1:02d}"


def parse_number(value: str) -> float | None:
    try:
        return float(value.replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def validate(path: Path, allow_unmarked: bool = False) -> c.Report:
    report = c.Report(f"Данные: {c.rel(path)}")
    if not path.exists():
        report.error("файл не найден")
        return report
    columns, rows = c.read_csv(path)
    missing = [col for col in COLUMNS if col not in columns]
    if missing:
        report.error("нет колонок: " + ", ".join(missing))
        return report
    if not rows:
        report.error("в таблице нет строк")
        return report

    parsed: dict[tuple[str, str], dict] = {}
    for number, row in enumerate(rows, 2):
        where = f"строка {number} ({row['month']}, {row['segment']})"
        empty = [col for col in COLUMNS if row[col] == ""]
        if empty:
            report.error(f"{where}: пропуски в полях {', '.join(empty)}")
            continue
        if not MONTH_RE.match(row["month"]):
            report.error(f"{where}: месяц должен быть в виде ГГГГ-ММ")
            continue
        values: dict[str, float] = {}
        bad = False
        for field in INT_FIELDS + MONEY_FIELDS + ["active_users_share"]:
            number_value = parse_number(row[field])
            if number_value is None:
                report.error(f"{where}: поле {field} не число: {row[field]!r}")
                bad = True
                continue
            if number_value < 0:
                report.error(f"{where}: поле {field} отрицательное")
                bad = True
            if field in INT_FIELDS and number_value != int(number_value):
                report.error(f"{where}: поле {field} должно быть целым числом людей")
                bad = True
            values[field] = number_value
        if bad:
            continue
        key = (row["segment"], row["month"])
        if key in parsed:
            report.error(f"{where}: повтор сочетания сегмент + месяц")
            continue
        parsed[key] = values

        if not 0 <= values["active_users_share"] <= 1:
            report.error(f"{where}: active_users_share — доля от 0 до 1, получено {row['active_users_share']}")
        expected_end = values["active_start"] + values["new_subscribers"] - values["churned"]
        if expected_end != values["active_end"]:
            report.error(
                f"{where}: баланс базы не сходится: {values['active_start']:.0f} + "
                f"{values['new_subscribers']:.0f} − {values['churned']:.0f} = {expected_end:.0f}, "
                f"а в active_end {values['active_end']:.0f}"
            )
        if values["churned"] > values["active_start"] + values["new_subscribers"]:
            report.error(f"{where}: отток больше, чем было подписчиков")
        expected_revenue = (values["active_start"] + values["active_end"]) / 2 * values["price_rub"]
        if expected_revenue == 0:
            if values["revenue_rub"] != 0:
                report.error(f"{where}: выручка при нулевой цене или базе должна быть 0")
        elif abs(values["revenue_rub"] - expected_revenue) / expected_revenue > REVENUE_TOLERANCE:
            report.error(
                f"{where}: выручка {values['revenue_rub']:.0f} ₽ не согласуется со средней базой "
                f"и ценой (ожидается около {expected_revenue:.0f} ₽)"
            )

    segments = sorted({segment for segment, _ in parsed})
    for segment in segments:
        months = sorted(month for seg, month in parsed if seg == segment)
        for previous, current in zip(months, months[1:]):
            if current != next_month(previous):
                report.error(f"сегмент {segment}: пропущены месяцы между {previous} и {current}")
                continue
            if parsed[(segment, previous)]["active_end"] != parsed[(segment, current)]["active_start"]:
                report.error(
                    f"сегмент {segment}: база на конец {previous} не равна базе на начало {current}"
                )
    month_sets = {segment: {m for s, m in parsed if s == segment} for segment in segments}
    if len({frozenset(v) for v in month_sets.values()}) > 1:
        report.warn("сегменты покрывают разные периоды: сравнение между ними ограничено")

    origins = {row["data_origin"] for row in rows}
    if origins == {c.SYNTHETIC_MARKER}:
        readme = path.parent / "README.md"
        if not readme.exists() or c.SYNTHETIC_DISCLAIMER not in " ".join(
            readme.read_text(encoding="utf-8-sig").split()
        ):
            report.error(
                "учебный набор данных: рядом нужен README.md с обязательной оговоркой о происхождении"
            )
        report.note("происхождение: учебные искусственные данные, не статистика реальной компании")
    elif c.SYNTHETIC_MARKER in origins:
        report.error("в одной таблице смешаны учебные и иные данные: разделите файлы")
    elif not allow_unmarked and (origins - {"user_provided", "public"}):
        report.error(
            "data_origin должен быть synthetic_educational, user_provided или public; "
            f"получено: {', '.join(sorted(origins))}"
        )

    all_months = sorted({month for _, month in parsed})
    if all_months:
        report.note(
            f"строк: {len(rows)}, сегментов: {len(segments)}, период: {all_months[0]} — {all_months[-1]}"
        )
        report.note("единицы: подписчики — человек; деньги — рубли за месяц; доля — от 0 до 1")
    return report


def main() -> int:
    c.setup_console()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", help="путь к таблице показателей")
    parser.add_argument(
        "--allow-unmarked", action="store_true",
        help="не требовать допустимого значения data_origin (не рекомендуется)",
    )
    args = parser.parse_args()
    path = Path(args.csv)
    if not path.is_absolute() and not path.exists():
        path = c.ROOT / path
    return validate(path, args.allow_unmarked).finish()


if __name__ == "__main__":
    raise SystemExit(main())
