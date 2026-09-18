@echo off
title Placement Cell - Setup & Run
cd /d "%~dp0"

echo ============================================
echo  Placement Cell - Full Setup
echo ============================================

if not exist .venv (
    echo [1/4] Creating virtual environment...
    py -m venv .venv || python -m venv .venv
)

echo [2/4] Installing dependencies...
.venv\Scripts\pip install -q -r requirements.txt

echo [3/4] Rebuilding database schema + seed data...
set DB_USER=
set DB_PASSWORD=
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    if "%%a"=="DB_USER" set DB_USER=%%b
    if "%%a"=="DB_PASSWORD" set DB_PASSWORD=%%b
)
if "%DB_USER%"=="" set DB_USER=root
set MYSQL_PWD=%DB_PASSWORD%
"C:\Program Files\MySQL\MySQL Server 26.7\bin\mysql.exe" -u %DB_USER% --default-character-set=utf8mb4 < db\schema.sql
.venv\Scripts\python seed.py
set MYSQL_PWD=

echo [4/4] Starting server at http://127.0.0.1:5000
.venv\Scripts\python app.py
pause