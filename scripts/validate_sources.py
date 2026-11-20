"""Проверка реестра источников, реестра доказательств и ссылок на них в документах.

Запуск: python scripts/validate_sources.py [--project <папка проекта>]

Что проверяется:
- sources.csv: обязательные поля, уникальность, формат URL и дат, допустимый тип;
- 03-evidence-ledger.csv: тип утверждения, происхождение, уверенность, статус,
  существование источников, правила для подтверждённых фактов и учебных данных;
- документы проекта: каждый упомянутый E### и S## существует; стратегические документы
  ссылаются на доказательства; ссылки на отозванные записи помечаются.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import psa_common as c  # noqa: E402

# Документы, в которых ссылка на отозванную запись допустима: они описывают сам пересмотр.
REVIEW_DOCS = {"09-decision-review.md", "decision-log.md", "decision-trace.md"}
# Документы, выводы которых обязаны опираться на реестр.
MUST_CITE = [
    "04-alternatives.md", "05-decision-record.md", "06-product-strategy.md",
    "07-communication-strategy.md", "08-experiment-plan.md",
]


def check_sources(columns: list[str], rows: list[dict], report: c.Report) -> dict[str, dict]:
    missing = [col for col in c.SOURCE_COLUMNS if col not in columns]
    if missing:
        report.error(f"sources.csv: нет колонок {', '.join(missing)}")
        return {}
    sources: dict[str, dict] = {}
    for number, row in enumerate(rows, 2):
        sid = row["id"]
        where = f"sources.csv, строка {number} ({sid or 'без id'})"
        if not c.S_REF.fullmatch(sid):
            report.error(f"{where}: id должен иметь вид S01")
            continue
        if sid in sources:
            report.error(f"{where}: повтор id")
        sources[sid] = row
        for field in ("title", "publisher", "url", "accessed", "type", "supports"):
            if not row[field]:
                report.error(f"{where}: пустое поле {field}")
        url = row["url"]
        if url and not url.startswith(("http://", "https://", "local:")):
            report.error(f"{where}: url должен начинаться с http(s):// или local:")
        if row["type"] and row["type"] not in c.SOURCE_TYPES:
            report.error(f"{where}: неизвестный тип источника {row['type']!r}")
        if row["type"] == "dataset" and url and not url.startswith("local:"):
            report.warn(f"{where}: набор данных обычно указывается как local:путь")
        if url.startswith("local:") and row["type"] not in {"dataset", "interview"}:
            report.error(f"{where}: локальный материал должен иметь тип dataset или interview")
        for field in ("published", "accessed"):
            if row[field] and not c.DATE_RE.match(row[field]):
                report.error(f"{where}: {field} должен быть в виде ГГГГ, ГГГГ-ММ или ГГГГ-ММ-ДД")
        if not row["published"]:
            report.warn(f"{where}: дата публикации не указана")
        if not row["limitations"]:
            report.warn(f"{where}: не описаны ограничения достоверности")
    return sources


def check_ledger(
    columns: list[str], rows: list[dict], sources: dict[str, dict], report: c.Report
) -> dict[str, dict]:
    missing = [col for col in c.LEDGER_COLUMNS if col not in columns]
    if missing:
        report.error(f"03-evidence-ledger.csv: нет колонок {', '.join(missing)}")
        return {}
    ledger: dict[str, dict] = {}
    for number, row in enumerate(rows, 2):
        eid = row["id"]
        where = f"реестр доказательств, строка {number} ({eid or 'без id'})"
        if not c.E_REF.fullmatch(eid):
            report.error(f"{where}: id должен иметь вид E001")
            continue
        if eid in ledger:
            report.error(f"{where}: повтор id")
        ledger[eid] = row
        for field in ("statement", "type", "origin", "confidence", "decision_impact", "status", "updated"):
            if not row[field]:
                report.error(f"{where}: пустое поле {field}")
        etype, origin = row["type"], row["origin"]
        if etype and etype not in c.EVIDENCE_TYPES:
            report.error(f"{where}: неизвестный тип {etype!r}")
        if origin and origin not in c.ORIGINS:
            report.error(f"{where}: неизвестное происхождение {origin!r}")
        if row["confidence"] and row["confidence"] not in c.CONFIDENCE:
            report.error(f"{where}: уверенность должна быть high, medium, low или n/a")
        if row["status"] and row["status"] not in c.ENTRY_STATUSES:
            report.error(f"{where}: статус должен быть active, superseded или retracted")
        if row["updated"] and not c.DATE_RE.match(row["updated"]):
            report.error(f"{where}: updated должен быть датой ГГГГ-ММ-ДД")
        ids = c.split_ids(row["source_ids"])
        unknown = [sid for sid in ids if sid not in sources]
        if unknown:
            report.error(f"{where}: источники не найдены в sources.csv: {', '.join(unknown)}")
        source_types = {sources[sid]["type"] for sid in ids if sid in sources}

        if etype == "Verified Fact":
            if not ids:
                report.error(f"{where}: подтверждённый факт без источника")
            if origin not in {"public", "user"}:
                report.error(f"{where}: подтверждённый факт не может иметь происхождение {origin!r}")
            if row["confidence"] == "n/a":
                report.error(f"{where}: у подтверждённого факта должна быть оценка уверенности")
            if source_types and source_types <= {"review", "aggregator"}:
                report.warn(f"{where}: факт опирается только на отзывы или агрегаторы")
        if origin == "synthetic":
            if "dataset" not in source_types:
                report.error(f"{where}: учебные данные должны ссылаться на источник типа dataset")
            if "учебн" not in (row["statement"] + row["limitations"]).lower():
                report.error(f"{where}: в формулировке или ограничениях нужна пометка «учебные данные»")
        if origin == "model" and etype not in {"AI Inference", "Hypothesis", "Assumption", "Estimate", "Forecast", "Unknown"}:
            report.error(f"{where}: вывод модели не может быть типом {etype!r}")
        if etype in {"AI Inference", "Unknown", "Assumption"} and not row["basis"]:
            report.error(f"{where}: для типа {etype} поле basis обязательно (на чём основано или как выяснить)")
        if etype in {"Hypothesis", "Estimate", "Forecast"} and not (row["basis"] or ids):
            report.error(f"{where}: нужен источник или основание")
        if row["status"] == "superseded" and not c.E_REF.search(row["note"]):
            report.error(f"{where}: у заменённой записи в note нужен id новой записи")
        if row["status"] != "active" and not row["note"]:
            report.error(f"{where}: у неактивной записи в note нужна причина")

    for eid, row in ledger.items():
        for ref in c.E_REF.findall(row["basis"] + " " + row["note"]):
            if ref not in ledger:
                report.error(f"реестр доказательств, {eid}: ссылка на несуществующую запись {ref}")
    return ledger


def check_references(
    project: Path, ledger: dict[str, dict], sources: dict[str, dict], report: c.Report
) -> None:
    cited: set[str] = set()
    for path in c.project_markdown(project):
        text = path.read_text(encoding="utf-8-sig")
        e_refs = set(c.E_REF.findall(text))
        s_refs = set(c.S_REF.findall(text))
        cited |= e_refs
        name = path.name
        for ref in sorted(e_refs - ledger.keys()):
            report.error(f"{c.rel(path)}: ссылка на несуществующее доказательство {ref}")
        for ref in sorted(s_refs - sources.keys()):
            report.error(f"{c.rel(path)}: ссылка на несуществующий источник {ref}")
        if name not in REVIEW_DOCS:
            stale = sorted(r for r in e_refs & ledger.keys() if ledger[r]["status"] != "active")
            if stale:
                report.error(
                    f"{c.rel(path)}: вывод опирается на отозванные или заменённые записи: "
                    + ", ".join(stale)
                )
        if name in MUST_CITE and path.parent == project and not e_refs:
            report.error(f"{c.rel(path)}: нет ни одной ссылки на реестр доказательств")
    unused = sorted(
        eid for eid, row in ledger.items() if row["status"] == "active" and eid not in cited
    )
    if unused:
        report.warn("записи реестра не использованы ни в одном документе: " + ", ".join(unused))


def validate(project: Path) -> c.Report:
    report = c.Report(f"Источники и доказательства: {c.rel(project)}")
    sources_path = project / "sources.csv"
    ledger_path = project / "03-evidence-ledger.csv"
    sources: dict[str, dict] = {}
    ledger: dict[str, dict] = {}
    if sources_path.exists():
        sources = check_sources(*c.read_csv(sources_path), report)
    else:
        report.error("нет файла sources.csv")
    if ledger_path.exists():
        ledger = check_ledger(*c.read_csv(ledger_path), sources, report)
    else:
        report.error("нет файла 03-evidence-ledger.csv")
    check_references(project, ledger, sources, report)
    by_type: dict[str, int] = {}
    for row in ledger.values():
        if row["status"] == "active":
            by_type[row["type"]] = by_type.get(row["type"], 0) + 1
    report.note(f"источников: {len(sources)}, записей реестра: {len(ledger)}")
    if by_type:
        report.note("действующие записи по типам: " + ", ".join(f"{k} — {v}" for k, v in sorted(by_type.items())))
    return report


def main() -> int:
    c.setup_console()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", help="папка проекта; по умолчанию активный проект")
    args = parser.parse_args()
    return validate(c.resolve_project(args.project)).finish()


if __name__ == "__main__":
    raise SystemExit(main())
