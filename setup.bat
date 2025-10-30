@echo off
echo ==========================================
echo Slack 알림 모니터링 웹 설치 (Windows)
echo ==========================================
echo.

REM Python 버전 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되지 않았습니다.
    echo Python 3.8 이상을 설치하세요: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Python 확인 완료
python --version

echo.
echo [2/3] 필요한 라이브러리 설치 중...
pip install -r requirements.txt

if errorlevel 1 (
    echo [오류] 라이브러리 설치 실패
    pause
    exit /b 1
)

echo.
echo [3/3] 설정 파일 생성 중...
if not exist watched_users.json (
    echo [] > watched_users.json
)

echo.
echo ==========================================
echo ✅ 설치 완료!
echo ==========================================
echo.
echo 다음 단계:
echo 1. run.bat 실행
echo 2. 브라우저에서 http://localhost:5000 접속
echo 3. Slack Bot Token 입력
echo.
pause
