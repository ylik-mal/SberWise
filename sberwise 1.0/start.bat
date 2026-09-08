@echo off
title SberSplit Bot Launcher
chcp 65001 > nul
cd /d "%~dp0"

echo ===================================================
echo 🚀 СберСплит Бот — Запуск и проверка системы
echo ===================================================
echo.

:: 1. Проверка наличия Python
set "PYTHON_CMD="
where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set "PYTHON_CMD=py"
    )
)

if "%PYTHON_CMD%"=="" (
    echo ❌ [ОШИБКА] Python не найден на вашем компьютере!
    echo.
    echo 1. Скачайте Python с официального сайта:
    echo    https://www.python.org/downloads/
    echo 2. При установке ОБЯЗАТЕЛЬНО поставьте галочку:
    echo    [x] "Add python.exe to PATH"
    echo 3. После установки перезапустите этот файл start.bat.
    echo.
    pause
    exit /b 1
)

echo ✅ [OK] Найден интерпретатор: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

:: 2. Проверка файла .env
if not exist ".env" (
    if exist "env_settings.txt" (
        echo Копируем настройки из env_settings.txt в .env...
        copy env_settings.txt .env >nul
    ) else (
        echo [ВНИМАНИЕ] Создаем файл .env...
        if exist ".env.example" copy .env.example .env >nul
    )
)

:: 3. Проверка и установка библиотек
echo 📦 [1/2] Проверка необходимых библиотек...
%PYTHON_CMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo ❌ [ОШИБКА] Не удалось установить библиотеки через pip!
    echo Проверьте подключение к интернету.
    echo.
    pause
    exit /b 1
)

:: 4. Запуск бота
echo.
echo ===================================================
echo 🤖 [2/2] Запуск Telegram-бота и сервера Mini App...
echo ===================================================
echo.
%PYTHON_CMD% bot.py

echo.
echo ===================================================
echo ℹ️ Работа бота завершилась.
echo Если окно закрылось неожиданно — текст ошибки выше.
echo ===================================================
pause
