@echo off
rem Запуск окна-пульта без консоли.
rem Двойной клик по этому файлу.

setlocal
cd /d "%~dp0"

set "PYW=.venv\Scripts\pythonw.exe"
set "PY=.venv\Scripts\python.exe"

if exist "%PYW%" (
    start "" "%PYW%" "launcher.py"
) else if exist "%PY%" (
    start "" "%PY%" "launcher.py"
) else (
    echo Не найдено виртуальное окружение .venv.
    echo Сначала запустите: python setup_env.py
    pause
    exit /b 1
)

endlocal
