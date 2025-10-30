#!/bin/bash

echo "=========================================="
echo "Slack 알림 모니터링 웹 설치 (Mac/Linux)"
echo "=========================================="
echo ""

# Python 버전 확인
if ! command -v python3 &> /dev/null; then
    echo "[오류] Python3이 설치되지 않았습니다."
    echo "Python 3.8 이상을 설치하세요: https://www.python.org/downloads/"
    exit 1
fi

echo "[1/3] Python 확인 완료"
python3 --version

echo ""
echo "[2/3] 필요한 라이브러리 설치 중..."
pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "[오류] 라이브러리 설치 실패"
    exit 1
fi

echo ""
echo "[3/3] 설정 파일 생성 중..."
if [ ! -f watched_users.json ]; then
    echo "[]" > watched_users.json
fi

echo ""
echo "=========================================="
echo "✅ 설치 완료!"
echo "=========================================="
echo ""
echo "다음 단계:"
echo "1. ./run.sh 실행"
echo "2. 브라우저에서 http://localhost:5000 접속"
echo "3. Slack Bot Token 입력"
echo ""
