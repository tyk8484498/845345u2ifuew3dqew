@echo off
:: Устанавливаем кодировку UTF-8 для корректного отображения кириллицы
chcp 65001 >nul

:: Проверка: если main.py уже запущен в WSL, пропускаем запуск
wsl pgrep -f "venv/bin/python3 main.py" >nul
if %errorlevel% equ 0 (
    echo [ИНФО] Скрипт main.py уже запущен.
) else (
    echo [СТАРТ] Запуск main.py в WSL...
    :: Запуск в фоне, переход в папку и выполнение через бинарник venv
    start /b wsl bash -c "cd /mnt/c/z && ./venv/bin/python3 main.py > log.txt 2>&1"
    
    echo [ПАУЗА] Ожидание 40 секунд для инициализации сервера...
    timeout /t 40 /nobreak >nul
)

echo [БРАУЗЕР] Запуск Edge в режиме киоска...
start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --edge-kiosk-type=fullscreen --disable-pinch --disable-features=msEdgePreload --no-first-run --kiosk http://localhost:8000

echo [ГОТОВО] Все процессы инициированы.