"""Хук начала сессии: напоминает, какой проект продолжать.

Печатает JSON в stdout и дописывает logs/session.log. Ошибка записи не должна
ломать чат: при сбое печатается пустой объект и код выхода 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    sys.stdin.read()
    message = (
        "Продолжай активный проект из state/workspace.json и state/current-task.md. "
        "Не начинай исследование заново. Прежний вывод агента не считай фактом, "
        "если в реестре нет активной записи с источником."
    )
    try:
        log = ROOT / "logs" / "session.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write("sessionStart\n")
    except OSError:
        pass
    print(json.dumps({"additional_context": message}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
