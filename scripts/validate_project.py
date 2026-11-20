"""Проверка структуры проекта и файла состояния.

Запуск:
  python scripts/validate_project.py                 # активный проект
  python scripts/validate_project.py --project demo/megafon-plus
  python scripts/validate_project.py --repo          # структура самого репозитория агента

Проверяется: схема state/project-state.json, согласованность статусов этапов,
наличие артефактов и обязательных разделов, участие человека в ключевых этапах,
ссылки решений на реестр доказательств.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import psa_common as c  # noqa: E402

REPO_REQUIRED = [
    "README.md", "AGENTS.md", ".gitignore",
    ".cursor/rules/00-core.mdc",
    "methodology/workflow.md", "methodology/evidence-standard.md",
    "methodology/decision-framework.md", "methodology/limitations.md",
    "knowledge/glossary.md",
    "prompts/resume.md",
    "templates/project/state/project-state.json",
    "scripts/psa_common.py", "state/current-task.md",
]
SKILLS = [
    "product-intake", "evidence-research", "strategic-alternatives", "product-strategy",
    "communication-strategy", "experiment-design", "decision-review",
]
PROJECT_REQUIRED = ["00-project-brief.md", "sources.csv", "03-evidence-ledger.csv",
                    "state/project-state.json", "state/decision-log.md", "state/activity-log.csv"]


def validate_repo(report: c.Report) -> None:
    for item in REPO_REQUIRED:
        if not (c.ROOT / item).exists():
            report.error(f"нет обязательного файла {item}")
    for skill in SKILLS:
        path = c.ROOT / ".cursor" / "skills" / skill / "SKILL.md"
        if not path.exists():
            report.error(f"нет навыка {skill}")
            continue
        text = path.read_text(encoding="utf-8-sig")
        if not text.startswith("---") or f"name: {skill}" not in text or "description:" not in text:
            report.error(f"навык {skill}: нет заголовка с name и description")
    for rule in sorted((c.ROOT / ".cursor" / "rules").glob("*.mdc")):
        text = rule.read_text(encoding="utf-8-sig")
        if not text.startswith("---") or "description:" not in text:
            report.error(f"правило {rule.name}: нет заголовка с description")
    template = c.ROOT / "templates" / "project"
    for name, sections in c.REQUIRED_SECTIONS.items():
        path = template / name
        if not path.exists():
            report.error(f"нет шаблона {name}")
        elif c.missing_sections(path, sections):
            report.error(
                f"шаблон {name}: нет разделов " + ", ".join(c.missing_sections(path, sections))
            )
    for path in c.ROOT.rglob("*"):
        if path.is_file() and path.stat().st_size == 0 and not any(
            part in c.SKIP_DIRS for part in path.parts
        ):
            report.warn(f"пустой файл: {c.rel(path)}")
    for finding in c.scan_secrets(c.ROOT):
        report.error(finding)
    report.note(f"навыков: {len(SKILLS)}, проверено шаблонов: {len(c.REQUIRED_SECTIONS)}")


def validate_state(project: Path, report: c.Report) -> dict | None:
    path = project / "state" / "project-state.json"
    try:
        state = c.read_json(path)
    except FileNotFoundError:
        report.error("нет state/project-state.json")
        return None
    except json.JSONDecodeError as exc:
        report.error(f"state/project-state.json повреждён: {exc}")
        return None

    for key in ("schema_version", "project", "request", "current_stage", "stages",
                "open_questions", "decisions", "next_actions", "waiting_for_human", "updated"):
        if key not in state:
            report.error(f"в состоянии нет поля {key}")
    if report.errors:
        return state
    if not str(state["request"]).strip():
        report.error("исходный запрос (request) пуст")

    stages = {s.get("id"): s for s in state["stages"]}
    if sorted(stages) != [n for n, *_ in c.STAGES]:
        report.error("в состоянии должны быть этапы с id от 1 до 8")
        return state
    if state["current_stage"] not in stages:
        report.error("current_stage должен быть числом от 1 до 8")

    for number, key, title, artifact in c.STAGES:
        stage = stages[number]
        status = stage.get("status")
        gate = stage.get("human_gate", "not_required")
        if status not in c.STAGE_STATUSES:
            report.error(f"этап {number}: неизвестный статус {status!r}")
            continue
        if gate not in c.GATE_VALUES:
            report.error(f"этап {number}: неизвестное значение human_gate {gate!r}")
        if number in c.HUMAN_GATE_STAGES and status == "done" and gate not in {"confirmed", "assumed"}:
            report.error(f"этап {number} «{title}» закрыт без участия человека (human_gate={gate})")
        if number == 5 and status == "done" and gate != "confirmed":
            report.error("выбор варианта может быть закрыт только подтверждением человека")
        if number == 1 and gate == "assumed":
            report.warn("постановка задачи не подтверждена человеком: работа идёт на допущениях")
        if status in {"done", "draft", "awaiting_human", "needs_review"}:
            artifact_path = project / artifact
            if not artifact_path.exists():
                report.error(f"этап {number} отмечен как {status}, но нет файла {artifact}")
            elif artifact in c.REQUIRED_SECTIONS:
                missing = c.missing_sections(artifact_path, c.REQUIRED_SECTIONS[artifact])
                if missing:
                    report.error(f"{artifact}: нет разделов " + ", ".join(missing))
        if status == "done" and not stage.get("completed"):
            report.warn(f"этап {number}: не указана дата завершения")

    statuses = [stages[n]["status"] for n, *_ in c.STAGES]
    for index, status in enumerate(statuses):
        if status in {"done", "draft"} and "pending" in statuses[:index]:
            report.warn(f"этап {index + 1} выполнен раньше, чем предыдущие этапы")
            break
    if any(s == "awaiting_human" for s in statuses) and not state["waiting_for_human"]:
        report.error("есть этап в ожидании человека, но поле waiting_for_human пусто")

    ledger = c.load_ledger(project)
    for decision in state["decisions"]:
        did = decision.get("id", "?")
        if decision.get("status") not in c.DECISION_STATUSES:
            report.error(f"решение {did}: неизвестный статус {decision.get('status')!r}")
        for field in ("date", "summary", "by", "review_trigger"):
            if not decision.get(field):
                report.error(f"решение {did}: пустое поле {field}")
        if decision.get("status") == "confirmed" and not decision.get("confirmed_by"):
            report.error(f"решение {did}: подтверждённое решение должно называть подтвердившего человека")
        evidence = decision.get("evidence", [])
        if not evidence:
            report.error(f"решение {did}: не указаны доказательства")
        for eid in evidence:
            if eid not in ledger:
                report.error(f"решение {did}: доказательство {eid} не найдено в реестре")
            elif ledger[eid]["status"] != "active" and decision.get("status") in {"proposed", "confirmed"}:
                report.error(
                    f"решение {did} опирается на отозванную запись {eid}: требуется пересмотр"
                )
        record = decision.get("record")
        if record and not (project / record).exists():
            report.error(f"решение {did}: нет файла {record}")
    for question in state["open_questions"]:
        if not question.get("id") or not question.get("text"):
            report.error("открытый вопрос без id или текста")
    if not state["next_actions"]:
        report.warn("не указаны следующие действия: продолжить после перерыва будет труднее")
    return state


def validate_project(project: Path) -> c.Report:
    report = c.Report(f"Проект: {c.rel(project)}")
    for item in PROJECT_REQUIRED:
        if not (project / item).exists():
            report.error(f"нет обязательного файла {item}")
    state = validate_state(project, report)
    if state:
        done = sum(1 for s in state["stages"] if s.get("status") == "done")
        report.note(f"текущий этап: {state.get('current_stage')}, закрыто этапов: {done} из 8")
        if state.get("waiting_for_human"):
            report.note(f"ожидается решение человека: {state['waiting_for_human']}")
    return report


def main() -> int:
    c.setup_console()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", help="папка проекта; по умолчанию активный проект")
    parser.add_argument("--repo", action="store_true", help="проверить структуру репозитория агента")
    args = parser.parse_args()
    if args.repo:
        report = c.Report("Репозиторий агента")
        validate_repo(report)
        return report.finish()
    return validate_project(c.resolve_project(args.project)).finish()


if __name__ == "__main__":
    raise SystemExit(main())
