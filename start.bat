@echo off
REM Starts the backend (port 8000) and frontend (port 5173) and opens the website.
cd /d %~dp0
start "Backend API" cmd /k "cd backend && call venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"
start "Frontend" cmd /k "cd frontend && npm run dev"
timeout /t 8 >nul
start http://127.0.0.1:5173
