# ⚡ 빠른 시작 가이드 (웹 버전)

## 📦 3분 안에 시작하기

### Windows 사용자
```batch
1. setup.bat 더블클릭
2. run.bat 더블클릭
3. 브라우저에서 http://localhost:5000 접속
4. Slack Bot Token 입력 → 연결
5. "▶️ 모니터링 시작" 클릭 → 완료!
```

### Mac/Linux 사용자
```bash
1. chmod +x setup.sh run.sh
2. ./setup.sh
3. ./run.sh
4. 브라우저에서 http://localhost:5000 접속
5. Slack Bot Token 입력 → 연결
6. "▶️ 모니터링 시작" 클릭 → 완료!
```

---

## 🎯 주요 기능 사용법

### 1️⃣ 실시간 멘션 알림
```
1. "🔔 실시간 알림" 탭
2. "▶️ 모니터링 시작" 클릭
3. 멘션 발생 시 자동 알림 표시
4. 브라우저 알림 + 알림음 재생
```

### 2️⃣ 특정 사용자 모니터링
```
1. "👥 사용자 관리" 탭
2. 사용자 이름 입력 (예: aiden)
3. "➕ 추가" 클릭
4. 해당 사용자 멘션 시 자동 알림
```

### 3️⃣ 채널 메시지 조회
```
1. "💬 채널 메시지" 탭
2. 채널 선택
3. "📥 최근 50개" 클릭
```

---

## 🔑 Bot Token 빠른 발급

1. https://api.slack.com/apps
2. "Create New App" → "From scratch"
3. OAuth & Permissions → Bot Token Scopes:
   - `channels:read`
   - `groups:read`
   - `channels:history`
   - `groups:history`
   - `users:read`
4. "Install to Workspace"
5. Token 복사 (xoxb-...)

---

## 🌐 다른 기기에서 접속하기

### 같은 네트워크 내 접속
```
1. 서버 IP 확인: ipconfig (Windows) / ifconfig (Mac/Linux)
2. 다른 기기 브라우저에서 접속:
   http://[서버IP]:5000
   예: http://192.168.0.10:5000
```

### 모바일에서 접속
```
스마트폰 브라우저에서 동일한 주소로 접속
→ 반응형 디자인으로 모바일에 최적화됨
```

---

## 🚨 빠른 트러블슈팅

### "missing_scope" 오류
→ Slack 앱에서 "Reinstall to Workspace"

### 알림이 안 옴
→ 봇을 채널에 초대: `/invite @봇이름`

### 브라우저 알림 안 뜸
→ 브라우저 설정에서 알림 권한 허용

### 포트 5000 사용 중
→ app.py 파일에서 포트 번호 변경 (5001, 8080 등)

---

## 💡 데스크톱 vs 웹 버전

### 데스크톱 버전 (slack_notifier_complete.py)
- 개인 사용
- 윈도우 깜박임 알림
- 설치 없이 바로 실행

### 웹 버전 (이 프로젝트)
- 팀 전체 사용
- 모바일 접속 가능
- 여러 기기 동시 접속
- 서버에서 24시간 운영 가능

---

**그냥 실행하고 싶다면?**
→ `run.bat` (Windows) 또는 `./run.sh` (Mac/Linux)
→ 브라우저에서 http://localhost:5000 접속
