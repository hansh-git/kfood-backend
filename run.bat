@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
if not exist .venv (
  echo [1/3] 가상환경 생성 중...
  %PY% -m venv .venv || (echo Python 3.10 이상이 필요합니다. python.org에서 설치 후 "Add to PATH" 체크 & pause & exit /b 1)
)
call .venv\Scripts\activate.bat
echo [2/3] 패키지 설치 중...
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements-dev.txt || (pause & exit /b 1)
if not exist .env (
  copy .env.example .env >nul
  echo .env 파일을 만들었습니다. 메모장으로 열어 키 3개를 입력한 뒤 다시 실행하세요.
  notepad .env
)
echo [3/3] 서버 실행: http://localhost:8000/docs
python -m uvicorn app.main:app --reload
pause
