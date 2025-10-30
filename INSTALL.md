# 📥 Slack 알림 모니터링 웹 버전 - 상세 설치 가이드

## 목차

1. [시스템 요구사항](#시스템-요구사항)
2. [Python 설치](#python-설치)
3. [프로젝트 설치](#프로젝트-설치)
4. [Slack 설정](#slack-설정)
5. [실행 및 테스트](#실행-및-테스트)
6. [문제 해결](#문제-해결)

---

## 시스템 요구사항

### 서버 (최소)
- CPU: 1 Core
- RAM: 512MB
- 디스크: 100MB
- Python 3.8 이상
- 네트워크 연결

### 서버 (권장)
- CPU: 2 Cores
- RAM: 1GB
- 디스크: 1GB
- Python 3.11 이상
- 고정 IP 또는 DDNS

### 클라이언트
- 모던 웹 브라우저
  - Chrome 90+
  - Firefox 88+
  - Safari 14+
  - Edge 90+
- JavaScript 활성화
- 네트워크 연결

---

## Python 설치

### Windows

#### 방법 1: Python.org에서 다운로드

1. https://www.python.org/downloads/ 접속
2. "Download Python 3.11.x" 클릭
3. 설치 프로그램 실행
4. **중요**: "Add Python to PATH" 체크박스 선택
5. "Install Now" 클릭

#### 방법 2: Microsoft Store

1. Microsoft Store 열기
2. "Python 3.11" 검색
3. 설치

#### 확인

```batch
python --version
# Python 3.11.x 출력되면 성공
```

### macOS

#### 방법 1: Homebrew (권장)

```bash
# Homebrew 설치 (없는 경우)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python 설치
brew install python3

# 확인
python3 --version
```

#### 방법 2: Python.org

1. https://www.python.org/downloads/macos/
2. macOS 인스톨러 다운로드
3. .pkg 파일 실행
4. 설치 진행

### Linux (Ubuntu/Debian)

```bash
# 시스템 업데이트
sudo apt update

# Python 3 설치
sudo apt install python3 python3-pip -y

# 확인
python3 --version
```

### Linux (CentOS/RHEL)

```bash
# Python 3 설치
sudo yum install python3 python3-pip -y

# 확인
python3 --version
```

---

## 프로젝트 설치

### 1단계: 압축 해제

#### Windows

```batch
# 7-Zip, WinRAR 또는 Windows 내장 기능 사용
tar -xzf slack-notifier-web-v1.0.tar.gz

# 또는 파일 탐색기에서
# 파일 우클릭 → "압축 풀기"
```

#### Mac/Linux

```bash
tar -xzf slack-notifier-web-v1.0.tar.gz
```

### 2단계: 폴더로 이동

```bash
cd slack-notifier-web
```

### 3단계: 실행 권한 부여 (Mac/Linux만)

```bash
chmod +x setup.sh run.sh
```

### 4단계: 의존성 설치

#### Windows

```batch
setup.bat
```

#### Mac/Linux

```bash
./setup.sh
```

#### 수동 설치 (문제 발생 시)

```bash
# Python 가상환경 생성 (선택사항)
python3 -m venv venv

# 가상환경 활성화
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

---

## Slack 설정

### 1단계: Slack 앱 생성

1. https://api.slack.com/apps 접속
2. Slack 워크스페이스 로그인
3. **"Create New App"** 클릭
4. **"From scratch"** 선택
5. 앱 이름 입력 (예: "알림 모니터")
6. 워크스페이스 선택
7. **"Create App"** 클릭

### 2단계: Bot Token Scopes 추가

1. 왼쪽 메뉴에서 **"OAuth & Permissions"** 클릭
2. **"Scopes"** 섹션으로 스크롤
3. **"Bot Token Scopes"** 에서 다음 권한 추가:

```
channels:read        - 공개 채널 정보 읽기
groups:read          - 비공개 채널 정보 읽기
channels:history     - 공개 채널 메시지 읽기
groups:history       - 비공개 채널 메시지 읽기
users:read           - 사용자 정보 읽기
```

**각 권한을 하나씩 "Add an OAuth Scope" 버튼으로 추가**

### 3단계: 워크스페이스에 설치

1. 페이지 상단으로 스크롤
2. **"Install to Workspace"** 클릭
3. 권한 확인 페이지에서 **"허용"** 클릭

### 4단계: Bot Token 복사

1. **"OAuth & Permissions"** 페이지로 돌아감
2. **"Bot User OAuth Token"** 복사
   - `xoxb-`로 시작하는 긴 문자열
   - 예: `xoxb-YOUR-BOT-TOKEN-HERE`

### 5단계: 봇을 채널에 초대

1. Slack에서 모니터링할 채널로 이동
2. 채널에서 다음 명령어 입력:
```
/invite @[봇이름]
```
3. 봇이 채널에 추가됨

---

## 실행 및 테스트

### 1단계: 서버 실행

#### Windows

```batch
run.bat
```

#### Mac/Linux

```bash
./run.sh
```

#### 수동 실행

```bash
python app.py
# 또는
python3 app.py
```

### 2단계: 서버 확인

콘솔에 다음과 같은 메시지가 표시되어야 합니다:

```
============================================================
🌐 Slack 알림 모니터링 웹 서버 시작
============================================================
📍 URL: http://localhost:5000
🔄 브라우저에서 위 주소로 접속하세요
============================================================
 * Running on http://0.0.0.0:5000
```

### 3단계: 브라우저 접속

1. 웹 브라우저 열기
2. 주소창에 입력:
```
http://localhost:5000
```

### 4단계: Slack 연결

1. 페이지 상단의 "Slack Bot Token" 입력란에 토큰 붙여넣기
2. **"연결"** 버튼 클릭
3. "연결됨" 상태 확인

### 5단계: 모니터링 시작

1. **"🔔 실시간 알림"** 탭 선택
2. **"▶️ 모니터링 시작"** 클릭
3. "실시간 모니터링 중..." 메시지 확인

### 6단계: 테스트

1. Slack에서 봇이 있는 채널로 이동
2. 봇 멘션 메시지 작성:
```
@[봇이름] 테스트
```
3. 웹 페이지에 알림이 표시되는지 확인
4. 브라우저 알림 권한 허용 (팝업 발생 시)

---

## 네트워크 설정

### 로컬 접속 (기본)

```
http://localhost:5000
```

### 같은 네트워크 내 접속

#### 서버 IP 확인

**Windows:**
```batch
ipconfig
# "IPv4 주소" 확인 (예: 192.168.0.10)
```

**Mac/Linux:**
```bash
ifconfig
# 또는
ip addr
# inet 주소 확인 (예: 192.168.0.10)
```

#### 클라이언트 접속

```
http://[서버IP]:5000
예: http://192.168.0.10:5000
```

### 외부 네트워크 접속 (선택)

#### 포트포워딩 설정

1. 라우터 관리 페이지 접속
2. 포트포워딩 설정:
   - 외부 포트: 5000
   - 내부 IP: [서버IP]
   - 내부 포트: 5000
   - 프로토콜: TCP

#### 공인 IP 확인

https://www.whatismyip.com/

#### 접속

```
http://[공인IP]:5000
```

⚠️ **보안 주의**: 외부 접속 시 반드시 인증 시스템 추가 권장

---

## 문제 해결

### Python 설치 관련

#### "python: command not found"

**해결:**
```bash
# Windows: PATH 환경변수 확인
# Mac/Linux: python3 사용
python3 --version
```

#### "pip: command not found"

**해결:**
```bash
# Mac/Linux
sudo apt install python3-pip

# Windows: Python 재설치 (Add to PATH 체크)
```

### 설치 관련

#### "ModuleNotFoundError: No module named 'flask'"

**해결:**
```bash
pip install Flask requests
# 또는
pip3 install Flask requests
```

#### "Permission denied: './setup.sh'"

**해결:**
```bash
chmod +x setup.sh run.sh
```

### 서버 실행 관련

#### "Address already in use"

**원인:** 포트 5000이 이미 사용 중

**해결:**
```python
# app.py 파일 마지막 줄 수정
app.run(debug=True, host='0.0.0.0', port=5001, threaded=True)
```

#### "ModuleNotFoundError: No module named 'werkzeug'"

**해결:**
```bash
pip install werkzeug
```

### 연결 관련

#### "missing_scope" 오류

**해결:**
1. Slack 앱 설정에서 Bot Token Scopes 확인
2. 모든 권한 추가되었는지 확인
3. **"Reinstall to Workspace"** 클릭

#### "not_in_channel" 오류

**해결:**
```
/invite @[봇이름]
```

#### "invalid_auth" 오류

**해결:**
- Token이 올바른지 확인
- `xoxb-`로 시작하는지 확인
- Token 재발급

### 브라우저 관련

#### 브라우저 알림이 안 뜸

**해결:**
1. 브라우저 설정 → 알림 권한 확인
2. HTTPS가 아닌 경우 일부 브라우저에서 제한
3. 팝업 차단 해제

#### "Server-Sent Events 연결 오류"

**해결:**
1. 브라우저 캐시 삭제
2. 시크릿 모드에서 테스트
3. 다른 브라우저로 시도

### 네트워크 관련

#### 다른 기기에서 접속 안됨

**해결:**
1. 방화벽 확인:
```bash
# Windows: Windows Defender 방화벽
# Mac: 시스템 환경설정 → 보안 및 개인 정보 보호 → 방화벽
# Linux: ufw 또는 iptables
```

2. 서버가 `0.0.0.0`으로 실행 중인지 확인
3. 네트워크 연결 확인

---

## 고급 설정

### 가상환경 사용 (권장)

```bash
# 가상환경 생성
python3 -m venv venv

# 활성화
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 설치
pip install -r requirements.txt

# 실행
python app.py

# 비활성화
deactivate
```

### 프로덕션 배포 (Gunicorn)

```bash
# Gunicorn 설치
pip install gunicorn

# 실행
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# 백그라운드 실행
nohup gunicorn -w 4 -b 0.0.0.0:5000 app:app &
```

### systemd 서비스 (Linux)

```bash
# /etc/systemd/system/slack-notifier.service 생성
sudo nano /etc/systemd/system/slack-notifier.service
```

```ini
[Unit]
Description=Slack Notifier Web Service
After=network.target

[Service]
User=your-username
WorkingDirectory=/path/to/slack-notifier-web
ExecStart=/usr/bin/python3 /path/to/slack-notifier-web/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 활성화
sudo systemctl enable slack-notifier
sudo systemctl start slack-notifier

# 상태 확인
sudo systemctl status slack-notifier
```

---

## 보안 설정

### HTTPS 설정 (Nginx)

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 방화벽 설정

**Linux (ufw):**
```bash
sudo ufw allow 5000/tcp
sudo ufw enable
```

**CentOS (firewalld):**
```bash
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```

---

## 검증 체크리스트

설치가 완료되면 다음을 확인하세요:

- [ ] Python 3.8 이상 설치됨
- [ ] Flask 및 requests 설치됨
- [ ] 서버가 정상 실행됨
- [ ] 브라우저에서 접속됨
- [ ] Slack 연결 성공
- [ ] 채널 목록 조회됨
- [ ] 메시지 조회 가능
- [ ] 실시간 모니터링 동작
- [ ] 브라우저 알림 허용됨
- [ ] 알림음 재생됨

---

## 추가 리소스

- [README.md](README.md) - 전체 사용 설명서
- [QUICK_START.md](QUICK_START.md) - 빠른 시작 가이드
- [Slack API 문서](https://api.slack.com/)
- [Flask 문서](https://flask.palletsprojects.com/)

---

**설치 완료! 즐거운 Slack 모니터링 되세요! 🎉**
