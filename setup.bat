@echo off
REM One-time setup for Windows. Run this by double-clicking it (or in Command Prompt).
cd /d %~dp0
echo ===== Backend setup =====
cd backend
py -3.12 -m venv venv
if errorlevel 1 (echo Python not found. Install Python 3.11+ and tick "Add Python to PATH". & pause & exit /b 1)
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (echo ERROR: pip install failed. Check your internet and try again. & pause & exit /b 1)
if not exist .env copy .env.example .env
echo ===== Training the AI model (about 1 minute) =====
python -m app.ml.train
if errorlevel 1 (echo ERROR: AI training failed. Copy the message above and send it to your helper. & pause & exit /b 1)
echo ===== Creating demo data =====
python scripts\seed.py
if errorlevel 1 (echo ERROR: demo data setup failed. & pause & exit /b 1)
cd ..\frontend
echo ===== Frontend setup =====
call npm install
if errorlevel 1 (echo npm not found. Install Node.js 18+ from nodejs.org. & pause & exit /b 1)
cd ..
echo.
echo Setup complete. Now double-click start.bat
pause
