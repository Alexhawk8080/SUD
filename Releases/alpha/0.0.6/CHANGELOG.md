# История изменений

## 0.0.6-alpha — 2026-09-27

- База дел: иерархия «судебный участок → год → файл → дела → результат»
- Схема БД v2: court_areas, court_years, source_files, cases
- Миграция v1 → v2 (migrate_db_v2.py)
- Модули БД: cases.py, results.py, inventories.py, category_snapshots.py
- core/db_pipeline.py: save_year_source_from_xlsx, process_year,
  export_year_result_to_file
- API: /api/db_tree, /api/source_files/*, /api/court_years/<id>/*,
  /api/results/*
- UI: постоянный сайдбар с деревом, страница года с 5 табами
- fix_21: heartbeat timeout 20 → 120 с
- fix_22: year_page.js перезаписан цельным файлом
- Тесты: 49 модулей, все OK
