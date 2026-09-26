# История изменений

## 0.0.3-alpha — 2026-09-21

- Этап A: справочник судебных участков (`court_areas`) + миграция
  из `settings` + CRUD + API + UI
- Этап B: Excel -> Word (метки, пакет `core/converter/`, роуты, UI)
- Этап C: Word -> Excel (парсер акта, роут, UI)
- Этап 14: модуль «Внутренняя опись» (Word -> лист «Таблица»):
  `core/inventory/` (docx_reader, normalizer, case_number, flow,
  sheets_io, writer, api), страница «Внутренняя опись», фикстуры,
  регрессия
- fix_10_v2: `_x000D_` -> `\n` на всех границах
- Тесты: 31 модуль, все OK
