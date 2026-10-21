# Вспомогательные проверки

- `check_army_readiness.py` — остаток места 350/352, отбраковка неполной/пустой
  армии и отсутствие повторной тренировки; работает без эмулятора.

- `check_combat_controls.py` — регрессии HP, таймеров героев, остатков войск
  и мониторинга после ускорения. Не подключается к эмулятору.
  Запуск из корня: `py -3.13 -X utf8 scripts/check_combat_controls.py`.
- `mbr_detect_eval.py` — оценка распознавания для MBR.
- `check_account_navigation.py` — маршрут до списка ID и остановка при ошибке
  перехода; запуск из корня через `py -3.13 -X utf8 scripts/check_account_navigation.py`.
- `git-hooks/pre-commit` — проверка секретов перед коммитом.
