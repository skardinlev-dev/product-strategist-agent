"""Общие функции скриптов product-strategist-agent.

Только стандартная библиотека Python 3.10+: репозиторий работает без установки пакетов.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Восемь этапов рабочего процесса: (номер, ключ, название, основной артефакт).
STAGES = [
    (1, "intake", "Постановка задачи", "00-project-brief.md"),
    (2, "research", "Исследование", "01-market-research.md"),
    (3, "evidence", "Реестр доказательств", "03-evidence-ledger.csv"),
    (4, "alternatives", "Альтернативы", "04-alternatives.md"),
    (5, "decision", "Стратегическое решение", "05-decision-record.md"),
    (6, "product_strategy", "Продуктовая стратегия", "06-product-strategy.md"),
    (7, "communication_strategy", "Коммуникационная стратегия", "07-communication-strategy.md"),
    (8, "validation", "Проверка и сопровождение", "08-experiment-plan.md"),
]
STAGE_STATUSES = {"pending", "in_progress", "draft", "awaiting_human", "done", "needs_review"}
# Этапы, которые нельзя закрыть без человека: постановка задачи и выбор варианта.
HUMAN_GATE_STAGES = {1, 5}
GATE_VALUES = {"confirmed", "assumed", "pending", "not_required"}
DECISION_STATUSES = {"proposed", "confirmed", "revised", "revoked"}

EVIDENCE_TYPES = [
    "Verified Fact",
    "Hypothesis",
    "Assumption",
    "Estimate",
    "Forecast",
    "AI Inference",
    "Unknown",
]
ORIGINS = {"public", "synthetic", "user", "model"}
CONFIDENCE = {"high", "medium", "low", "n/a"}
ENTRY_STATUSES = {"active", "superseded", "retracted"}
SOURCE_TYPES = {
    "official", "legal", "company-report", "research", "media",
    "review", "aggregator", "dataset", "interview",
}

SOURCE_COLUMNS = [
    "id", "title", "publisher", "url", "published", "accessed",
    "type", "supports", "limitations",
]
LEDGER_COLUMNS = [
    "id", "statement", "type", "origin", "source_ids", "basis", "confidence",
    "limitations", "decision_impact", "status", "updated", "note",
]
LOG_COLUMNS = [
    "timestamp", "stage", "action", "tools", "result", "artifacts",
    "human_input", "cost_note",
]

# Обязательные разделы документов: подстрока должна встретиться в строке-заголовке.
REQUIRED_SECTIONS = {
    "00-project-brief.md": [
        "Исходный запрос", "Проблема", "Заинтересованные стороны", "Целевая аудитория",
        "Желаемый результат", "Ограничения", "Известные факты", "Неизвестные",
        "Допущения", "Критерии успешного решения",
    ],
    "01-market-research.md": [
        "Исследовательские вопросы", "Рынок", "Конкуренты", "Противоречия", "Пробелы",
    ],
    "02-product-analysis.md": [
        "Продукт", "Аудитория", "Наблюдаемые преимущества и ограничения", "Данные",
    ],
    "04-alternatives.md": ["Варианты", "Сравнение", "Сценарии", "Рекомендация"],
    "05-decision-record.md": [
        "Решение", "Рассмотренные альтернативы", "Основания", "Отклонённые варианты",
        "Допущения", "Риски", "Ответственный", "Условия пересмотра",
    ],
    "06-product-strategy.md": [
        "Диагноз", "Целевая аудитория", "Задача пользователя", "Альтернативы пользователя",
        "Позиционирование", "Приоритеты", "Осознанные отказы", "Экономика",
        "Показатели", "Риски", "Последовательность",
    ],
    "07-communication-strategy.md": [
        "Аудитория и ситуации", "Барьеры", "Ключевое сообщение", "Подтверждение",
        "Каналы", "Последовательность", "Показатели", "Проверка обещаний",
    ],
    "08-experiment-plan.md": [
        "Гипотезы", "Ожидаемое изменение", "Сравнение", "Срок",
        "Нежелательные последствия", "Критерии",
    ],
}

SYNTHETIC_MARKER = "synthetic_educational"
SYNTHETIC_DISCLAIMER = (
    "Данные созданы исключительно для демонстрации возможностей Product Strategist Agent. "
    "Они не получены от МегаФона, не являются внутренней статистикой компании и не отражают "
    "фактические показатели её продуктов."
)

E_REF = re.compile(r"\bE\d{3}\b")
S_REF = re.compile(r"\bS\d{2,3}\b")
DATE_RE = re.compile(r"^\d{4}(-\d{2}){0,2}$")

# Признаки секретов: проверяются перед сборкой архива и в общей проверке.
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"),
]
SECRET_FILENAMES = {".env", "credentials.json", "id_rsa", "id_ed25519"}
SKIP_DIRS = {".git", "__pycache__", "dist", ".venv", "venv", "node_modules"}


def setup_console() -> None:
    """Делает вывод читаемым в Windows-консоли и не падает на непечатаемых символах.

    PowerShell декодирует вывод дочерних программ в кодировке консоли, а Python при
    перенаправлении вывода пишет в ANSI-кодировке. Выравниваем их.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            encoding = None
            if sys.platform == "win32" and not stream.isatty():
                import ctypes

                codepage = ctypes.windll.kernel32.GetConsoleOutputCP()
                encoding = f"cp{codepage}" if codepage else "utf-8"
            stream.reconfigure(encoding=encoding, errors="replace")
        except (AttributeError, LookupError, OSError, ValueError):
            pass


class Report:
    """Накопитель замечаний проверки."""

    def __init__(self, title: str):
        self.title = title
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def error(self, text: str) -> None:
        self.errors.append(text)

    def warn(self, text: str) -> None:
        self.warnings.append(text)

    def note(self, text: str) -> None:
        self.notes.append(text)

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        lines = [f"== {self.title} =="]
        lines += [f"ОШИБКА: {e}" for e in self.errors]
        lines += [f"ПРЕДУПРЕЖДЕНИЕ: {w}" for w in self.warnings]
        lines += [f"  {n}" for n in self.notes]
        verdict = "ПРОЙДЕНО" if self.ok else "НЕ ПРОЙДЕНО"
        lines.append(
            f"Итог: {verdict} (ошибок: {len(self.errors)}, предупреждений: {len(self.warnings)})"
        )
        return "\n".join(lines)

    def finish(self) -> int:
        print(self.render())
        return 0 if self.ok else 1


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    """Читает CSV в UTF-8 (с BOM или без). Возвращает (колонки, строки)."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = [
            {k: (v or "").strip() for k, v in row.items() if k is not None}
            for row in reader
        ]
        return list(reader.fieldnames or []), rows


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: dict) -> None:
    """Атомарная запись: сбой посреди записи не портит прежний файл."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def today() -> str:
    return dt.date.today().isoformat()


def split_ids(value: str) -> list[str]:
    return [p.strip() for p in re.split(r"[;,\s]+", value or "") if p.strip()]


def workspace_file() -> Path:
    return ROOT / "state" / "workspace.json"


def resolve_project(arg: str | None) -> Path:
    """Папка проекта: аргумент командной строки или активный проект из state/workspace.json."""
    if arg:
        path = Path(arg)
        if not path.is_absolute():
            path = ROOT / path
    else:
        ws = workspace_file()
        if not ws.exists():
            raise SystemExit(
                "Активный проект не задан. Укажите --project <папка> или создайте проект: "
                'python scripts/new_project.py --slug my-case --title "..."'
            )
        path = ROOT / read_json(ws)["active_project"]
    if not path.is_dir():
        raise SystemExit(f"Папка проекта не найдена: {path}")
    return path


def rel(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def headings(path: Path) -> list[str]:
    return [
        line.lstrip("#").strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.startswith("#")
    ]


def missing_sections(path: Path, required: list[str]) -> list[str]:
    found = " \n".join(headings(path)).lower()
    return [name for name in required if name.lower() not in found]


def project_markdown(project: Path) -> list[Path]:
    return sorted(
        p for p in project.rglob("*.md")
        if not any(part in SKIP_DIRS for part in p.parts)
    )


def load_ledger(project: Path) -> dict[str, dict]:
    path = project / "03-evidence-ledger.csv"
    if not path.exists():
        return {}
    return {row["id"]: row for row in read_csv(path)[1] if row.get("id")}


def load_sources(project: Path) -> dict[str, dict]:
    path = project / "sources.csv"
    if not path.exists():
        return {}
    return {row["id"]: row for row in read_csv(path)[1] if row.get("id")}


def scan_secrets(base: Path) -> list[str]:
    """Возвращает список находок, похожих на секреты, в текстовых файлах папки."""
    findings = []
    for path in base.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SECRET_FILENAMES:
            findings.append(f"{rel(path)}: файл с секретами не должен лежать в репозитории")
            continue
        if path.suffix.lower() in {".zip", ".png", ".jpg", ".jpeg", ".pdf", ".docx", ".xlsx"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if any(pattern.search(line) for pattern in SECRET_PATTERNS):
                findings.append(f"{rel(path)}:{number}: строка похожа на ключ или пароль")
    return findings
