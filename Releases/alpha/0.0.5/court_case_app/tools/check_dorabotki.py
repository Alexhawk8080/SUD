# -*- coding: utf-8 -*-
"""Проверка 4 доработок через HTTP (сервер должен быть запущен)."""
import io
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import threading
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:5000"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
XLSX = os.path.join(ROOT, "2020 гр.xlsx")
XLSM = os.path.join(ROOT, "АКТ уничтожения гражданских дел 9СУ 2020.xlsm")
OUT_DIR = os.path.join(ROOT, "court_case_app", "output")


class HeartbeatThread(threading.Thread):
    """Шлёт /heartbeat каждые 3 с, чтобы watchdog не остановил сервер."""

    def __init__(self):
        super().__init__(daemon=True)
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                req("GET", BASE + "/heartbeat")
            except Exception:
                pass
            self._stop.wait(3.0)

    def stop(self):
        self._stop.set()


def req(method, url, data=None, headers=None):
    r = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def multipart(field, filepath, ctype="application/octet-stream"):
    boundary = "----checkDorabotkiBoundary123"
    with open(filepath, "rb") as f:
        content = f.read()
    body = io.BytesIO()
    body.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                "Content-Type: %s\r\n\r\n" % (boundary, field, os.path.basename(filepath), ctype)).encode("utf-8"))
    body.write(content)
    body.write(("\r\n--%s--\r\n" % boundary).encode("utf-8"))
    return body.getvalue(), {"Content-Type": "multipart/form-data; boundary=" + boundary}


results = []

hb = HeartbeatThread()
hb.start()

# --- 1. Основные страницы и heartbeat ---
for path in ("/", "/db_page", "/heartbeat"):
    code, body = req("GET", BASE + path)
    ok = code == 200
    results.append(("GET %s" % path, code, "OK" if ok else "FAIL"))
    if not ok:
        print("Тело:", body[:500])

# --- 2. Предпросмотр выбранного Excel-файла (доработка №2) ---
data, hdrs = multipart("file", XLSX,
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
code, body = req("POST", BASE + "/preview", data=data, headers=hdrs)
ok = False
try:
    j = json.loads(body.decode("utf-8"))
    ok = code == 200 and "rows" in j and "header_row" in j and "mapping" in j
    results.append(("POST /preview", code, "OK" if ok else "FAIL",
                    "header_row=%s cols=%d rows_shown=%d mapping=%s" % (
                        j.get("header_row"), len(j.get("rows", [[]])[0]) if j.get("rows") else 0,
                        len(j.get("rows", [])), sorted(j.get("mapping", {}).keys()))))
except Exception as ex:
    results.append(("POST /preview", code, "FAIL: " + str(ex)))
    print("Тело:", body[:500])

# --- 3. Импорт БД из xlsm (доработка №4, часть 1) ---
data, hdrs = multipart("file", XLSM,
                       "application/vnd.ms-excel.sheet.macroEnabled.12")
code, body = req("POST", BASE + "/api/db/import", data=data, headers=hdrs)
try:
    j = json.loads(body.decode("utf-8"))
    results.append(("POST /api/db/import", code, "OK" if code == 200 else "FAIL",
                    "added=%s total_organizations=%s" % (j.get("added"), j.get("total_organizations"))))
except Exception as ex:
    results.append(("POST /api/db/import", code, "FAIL: " + str(ex)))
    print("Тело:", body[:500])

# --- 4. Экспорт БД (доработка №4, часть 2) ---
code, body = req("GET", BASE + "/api/db/export")
out = os.path.join(OUT_DIR, "_check_db_export.xlsx")
if code == 200 and len(body) > 0:
    with open(out, "wb") as f:
        f.write(body)
    results.append(("GET /api/db/export", code, "OK", "bytes=%d saved=%s" % (len(body), out)))
else:
    results.append(("GET /api/db/export", code, "FAIL", "bytes=%d" % len(body)))

hb.stop()

# --- Вывод ---
print("=" * 70)
for r in results:
    print(" | ".join(str(x) for x in r))
print("=" * 70)
bad = [r for r in results if "FAIL" in str(r)]
print("ИТОГО: %d проверок, ошибок: %d" % (len(results), len(bad)))
sys.exit(1 if bad else 0)