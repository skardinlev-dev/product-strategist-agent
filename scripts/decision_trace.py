"""Трассировка решений: какие выводы на чём основаны и что затронет изменение.

Запуск:
  python scripts/decision_trace.py                      # карта «документ → доказательства»
  python scripts/decision_trace.py --impact E012 E015   # что пересмотреть, если записи изменились
  python scripts/decision_trace.py --write              # сохранить карту в state/decision-trace.md

Режим --impact отвечает на вопрос «какие выводы затронуты новыми сведениями»: находит
записи реестра, выведенные из указанных, документы и строки, где они использованы,
и решения, которые на них опираются.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import psa_common as c  # noqa: E402


def dependents(ledger: dict[str, dict], roots: set[str]) -> set[str]:
    """Записи, чьё основание (basis) прямо или через цепочку ссылается на исходные."""
    affected = set(roots)
    changed = True
    while changed:
        changed = False
        for eid, row in ledger.items():
            if eid not in affected and affected & set(c.E_REF.findall(row["basis"])):
                affected.add(eid)
                changed = True
    return affected - roots


def usages(project: Path, ids: set[str]) -> dict[str, list[tuple[int, str, list[str]]]]:
    found: dict[str, list[tuple[int, str, list[str]]]] = {}
    for path in c.project_markdown(project):
        if path.name == "decision-trace.md":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            hit = sorted(ids & set(c.E_REF.findall(line)))
            if hit:
                found.setdefault(c.rel(path), []).append((number, line.strip()[:160], hit))
    return found


def render_map(project: Path, ledger: dict[str, dict], state: dict) -> str:
    lines = [f"# Трассировка решений: {c.rel(project)}", "",
             f"Сформировано скриптом scripts/decision_trace.py {c.now_iso()}. Не редактируйте вручную.", ""]
    lines += ["## Решения", ""]
    if not state.get("decisions"):
        lines.append("Решений пока нет.")
    for decision in state.get("decisions", []):
        lines.append(f"### {decision['id']}: {decision['summary']}")
        lines.append(f"- Статус: {decision['status']}; дата: {decision['date']}; кем: {decision['by']}")
        lines.append(f"- Условие пересмотра: {decision['review_trigger']}")
        lines.append("- Основания:")
        for eid in decision.get("evidence", []):
            row = ledger.get(eid)
            if row:
                lines.append(
                    f"  - {eid} [{row['type']}, {row['origin']}, уверенность {row['confidence']}, "
                    f"{row['status']}]: {row['statement']}"
                )
            else:
                lines.append(f"  - {eid}: НЕ НАЙДЕНО В РЕЕСТРЕ")
        lines.append("")
    lines += ["## Документы и их основания", "",
              "| Документ | Факты | Гипотезы и допущения | Оценки и прогнозы | Выводы модели | Неизвестное |",
              "| --- | --- | --- | --- | --- | --- |"]
    groups = [
        {"Verified Fact"}, {"Hypothesis", "Assumption"}, {"Estimate", "Forecast"},
        {"AI Inference"}, {"Unknown"},
    ]
    for path in c.project_markdown(project):
        if path.name == "decision-trace.md":
            continue
        refs = sorted(set(c.E_REF.findall(path.read_text(encoding="utf-8-sig"))) & ledger.keys())
        if not refs:
            continue
        cells = [", ".join(r for r in refs if ledger[r]["type"] in group) or "—" for group in groups]
        lines.append(f"| {c.rel(path)} | " + " | ".join(cells) + " |")
    synthetic = sorted(eid for eid, row in ledger.items() if row["origin"] == "synthetic")
    if synthetic:
        lines += ["", "Записи на учебных данных (не являются сведениями о реальной компании): "
                  + ", ".join(synthetic)]
    return "\n".join(lines) + "\n"


def render_impact(project: Path, ledger: dict[str, dict], state: dict, roots: set[str]) -> str:
    unknown = sorted(roots - ledger.keys())
    if unknown:
        raise SystemExit("В реестре нет записей: " + ", ".join(unknown))
    derived = dependents(ledger, roots)
    affected = roots | derived
    lines = ["== Что затронуто изменением записей " + ", ".join(sorted(roots)) + " ==", ""]
    for eid in sorted(roots):
        row = ledger[eid]
        lines.append(f"{eid} [{row['type']}, {row['status']}]: {row['statement']}")
    lines += ["", "Записи реестра, выведенные из изменённых:"]
    lines += [f"  {eid} [{ledger[eid]['type']}]: {ledger[eid]['statement']}" for eid in sorted(derived)] or ["  нет"]
    lines += ["", "Решения, которые нужно пересмотреть:"]
    hit_decisions = [d for d in state.get("decisions", []) if affected & set(d.get("evidence", []))]
    lines += [
        f"  {d['id']} ({d['status']}): {d['summary']} — затронуты "
        + ", ".join(sorted(affected & set(d['evidence'])))
        for d in hit_decisions
    ] or ["  нет"]
    lines += ["", "Места в документах:"]
    found = usages(project, affected)
    if not found:
        lines.append("  нет")
    for doc, hits in found.items():
        lines.append(f"  {doc}")
        lines += [f"    строка {number} [{', '.join(ids)}]: {text}" for number, text, ids in hits]
    lines += ["", f"Итого: записей затронуто {len(affected)}, документов {len(found)}, "
              f"решений {len(hit_decisions)}."]
    return "\n".join(lines)


def main() -> int:
    c.setup_console()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", help="папка проекта; по умолчанию активный проект")
    parser.add_argument("--impact", nargs="+", metavar="E###", help="id изменившихся записей реестра")
    parser.add_argument("--write", action="store_true", help="сохранить карту в state/decision-trace.md")
    args = parser.parse_args()
    project = c.resolve_project(args.project)
    ledger = c.load_ledger(project)
    state = c.read_json(project / "state" / "project-state.json")
    if args.impact:
        print(render_impact(project, ledger, state, set(args.impact)))
        return 0
    text = render_map(project, ledger, state)
    if args.write:
        target = project / "state" / "decision-trace.md"
        target.write_text(text, encoding="utf-8")
        print(f"Сохранено: {c.rel(target)}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
