"""Создаёт пустые шаблоны с обязательными заголовками."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import psa_common as c  # noqa: E402

FILES = {
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


def main() -> int:
    root = c.ROOT / "templates" / "project"
    for name, heads in FILES.items():
        body = "# Шаблон\n\nЗаполните разделы в копии папки. Демонстрационный кейс не перезаписывайте.\n\n"
        body += "".join(f"## {head}\n\n" for head in heads)
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    state = {
        "schema_version": 1,
        "project": "",
        "request": "",
        "current_stage": 1,
        "stages": [
            {
                "id": number,
                "status": "pending",
                "human_gate": "pending" if number in (1, 5) else "not_required",
                "completed": "",
            }
            for number in range(1, 9)
        ],
        "open_questions": [],
        "decisions": [],
        "next_actions": ["Заполнить 00-project-brief.md"],
        "waiting_for_human": "подтвердить постановку",
        "updated": "",
    }
    c.write_json(root / "state" / "project-state.json", state)
    print(f"шаблонов: {len(FILES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
