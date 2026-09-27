# -*- coding: utf-8 -*-
"""Проверка стабильности heartbeat: сервер должен жить при регулярном heartbeat
и умереть после пропажи (watchdog, таймаут 20 с)."""
import json
import os
import sys
import threading
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:5000"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=10) as r:
            return r.status
    except Exception:
        return None


results = []

# 1. Статические файлы нового heartbeat
for p in ("/static/js/heartbeat_worker.js", "/static/js/main.js", "/db_page", "/"):
    code = get(p)
    results.append(("GET %s" % p, code, "OK" if code == 200 else "FAIL"))

# 2. Проверка содержимого main.js: sendBeacon('/shutdown') не должен вызываться
try:
    with open(os.path.join(ROOT, "court_case_app", "static", "js", "main.js"),
              encoding="utf-8") as f:
        mjs = f.read()
    results.append(("main.js: Worker используется",
                    "new Worker" in mjs and "sendBeacon(\"/shutdown\")" not in mjs,
                    "OK" if "new Worker" in mjs and "sendBeacon(\"/shutdown\")" not in mjs else "FAIL"))
except OSError as ex:
    results.append(("main.js чтение", str(ex), "FAIL"))

# 3. Сервер жив 35 с при регулярном heartbeat (эмуляция Worker'а)
stop = threading.Event()

def beat_loop():
    while not stop.is_set():
        get("/heartbeat")
        stop.wait(4.0)

t = threading.Thread(target=beat_loop, daemon=True)
t.start()
time.sleep(35)
stop.set()

alive = get("/heartbeat")
results.append(("Сервер жив через 35 с heartbeat-эмуляции", alive,
                "OK (жив)" if alive == 200 else "FAIL (умер)"))

# 4. Watchdog: после остановки heartbeat сервер должен умереть сам (20 с таймаут)
time.sleep(26)
dead = get("/heartbeat") is None
results.append(("Сервер остановился сам через 20 с без heartbeat", dead,
                "OK (остановился)" if dead else "FAIL (ещё жив)"))

print("=" * 70)
for r in results:
    print(" | ".join(str(x) for x in r))
print("=" * 70)
bad = [r for r in results if "FAIL" in str(r)]
print("ИТОГО: %d проверок, ошибок: %d" % (len(results), len(bad)))
sys.exit(1 if bad else 0)