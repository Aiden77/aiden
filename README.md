# 🌐 Slack 알림 모니터링 웹 애플리케이션

데스크톱 버전과 동일한 기능을 웹 브라우저에서 사용할 수 있는 Slack 알림 모니터링 시스템입니다.

## ✨ 주요 기능

### 🔔 실시간 알림 모니터링
- 봇 멘션 자동 감지 (@봇이름)
- @channel/@here 전체 알림 감지
- 특정 사용자 멘션 모니터링
- 5초 간격 자동 체크
- 브라우저 알림 (Notification API)
- 알림음 재생
- 실시간 업데이트 (Server-Sent Events)

### 💬 채널 메시지 뷰어
- 봇 참여 채널 자동 조회
- 최근 메시지 조회 (50/100/200개)
- 사용자/봇 구분 표시
- 타임스탬프 표시

### 👥 사용자 관리
- 모니터링 사용자 추가/제거
- 설정 자동 저장/로드
- JSON 기반 설정 관리

## 🖥️ 지원 플랫폼

- ✅ Windows (10/11)
- ✅ macOS (10.15+)
- ✅ Linux (Ubuntu 20.04+)

## 📋 시스템 요구사항

- Python 3.8 이상
- Flask 3.0.0
- requests 2.31.0
- 모던 웹 브라우저 (Chrome, Firefox, Safari, Edge)

## 📥 설치 방법

### Windows

```batch
# 1. 압축 해제 후 폴더로 이동
cd slack-notifier-web

# 2. 설치
setup.bat

# 3. 실행
run.bat

# 4. 브라우저에서 접속
# http://localhost:5000
```

### Mac/Linux

```bash
# 1. 압축 해제 후 폴더로 이동
cd slack-notifier-web

# 2. 실행 권한 부여
chmod +x setup.sh run.sh

# 3. 설치
./setup.sh

# 4. 실행
./run.sh

# 5. 브라우저에서 접속
# http://localhost:5000
```

## 🔑 Slack Bot Token 발급

1. https://api.slack.com/apps 접속
2. "Create New App" → "From scratch"
3. OAuth & Permissions → Bot Token Scopes 추가:
   - `channels:read`
   - `groups:read`
   - `channels:history`
   - `groups:history`
   - `users:read`
4. "Install to Workspace"
5. Bot User OAuth Token 복사 (xoxb-로 시작)

## 📖 사용 방법

### 1단계: Slack 연결

1. 브라우저에서 `http://localhost:5000` 접속
2. Slack Bot Token 입력란에 토큰 붙여넣기
3. "연결" 버튼 클릭
4. "연결됨" 상태 확인

### 2단계: 실시간 알림 모니터링

1. "🔔 실시간 알림" 탭 선택
2. "▶️ 모니터링 시작" 버튼 클릭
3. 새로운 멘션이 오면 자동으로 알림 표시
4. 브라우저 알림 권한 허용 (선택사항)

### 3단계: 채널 메시지 조회

1. "💬 채널 메시지" 탭 선택
2. 드롭다운에서 채널 선택
3. "📥 최근 50개" 버튼 클릭하여 메시지 조회

### 4단계: 모니터링 사용자 추가

1. "👥 사용자 관리" 탭 선택
2. 사용자 이름 또는 ID 입력 (예: aiden, U07R293JDV4)
3. "➕ 추가" 버튼 클릭
4. 해당 사용자가 멘션되면 자동 알림

## 🎨 주요 특징

### 데스크톱 버전과의 차이점

| 기능 | 데스크톱 (tkinter) | 웹 버전 (Flask) |
|------|-------------------|-----------------|
| 실시간 알림 | ✅ 윈도우 깜박임 | ✅ 브라우저 알림 |
| 알림음 | ✅ 시스템 벨 | ✅ Web Audio API |
| 접근성 | 로컬 실행 | 네트워크로 접근 가능 |
| 멀티 세션 | 단일 인스턴스 | 다중 사용자 지원 |
| 플랫폼 | OS 의존 | 브라우저만 필요 |

### 웹 버전만의 장점

- 🌍 **어디서나 접근**: 같은 네트워크 내 다른 기기에서 접속 가능
- 📱 **모바일 지원**: 스마트폰/태블릿 브라우저에서도 사용 가능
- 🔄 **자동 업데이트**: 새로고침 없이 실시간 업데이트
- 🎨 **반응형 디자인**: 다양한 화면 크기 지원
- 🔔 **브라우저 알림**: OS 네이티브 알림 시스템 활용

## 🔧 고급 설정

### 다른 포트 사용

`app.py` 파일 마지막 줄 수정:

```python
app.run(debug=True, host='0.0.0.0', port=8080, threaded=True)
```

### 외부 접속 허용

기본적으로 `0.0.0.0`으로 설정되어 있어 같은 네트워크 내 다른 기기에서 접속 가능합니다.

```
http://[서버IP]:5000
```

### HTTPS 사용 (프로덕션 환경)

프로덕션 환경에서는 Gunicorn + Nginx 조합 사용 권장:

```bash
# Gunicorn 설치
pip install gunicorn

# 실행
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 📁 파일 구조

```
slack-notifier-web/
├── app.py                    # Flask 웹 서버
├── templates/
│   └── index.html           # 프론트엔드 UI
├── requirements.txt          # Python 의존성
├── watched_users.json        # 모니터링 사용자 목록 (자동 생성)
├── README.md                # 이 파일
├── setup.bat                # Windows 설치 스크립트
├── setup.sh                 # Mac/Linux 설치 스크립트
├── run.bat                  # Windows 실행 스크립트
└── run.sh                   # Mac/Linux 실행 스크립트
```

## 🐛 문제 해결

### "연결 실패: missing_scope" 오류

Slack 앱 설정에서 Bot Token Scopes를 다시 확인하고 "Reinstall to Workspace" 클릭

### 알림이 오지 않음

1. 봇을 채널에 초대: `/invite @봇이름`
2. 모니터링이 시작된 후의 메시지만 감지됩니다
3. 브라우저 알림 권한 허용 여부 확인

### 브라우저 알림이 안 뜸

1. 브라우저 설정에서 알림 권한 확인
2. HTTPS가 아닌 경우 일부 브라우저에서 제한될 수 있음

### 포트 5000이 이미 사용 중

`app.py`에서 포트 번호 변경 (예: 5001, 8080 등)

### Python 모듈 import 오류

```bash
pip install -r requirements.txt --upgrade
```

## 🔐 보안 주의사항

1. **Token 관리**: Slack Bot Token은 절대 공개하지 마세요
2. **방화벽**: 외부 접속이 필요없다면 localhost만 허용
3. **HTTPS**: 프로덕션 환경에서는 반드시 HTTPS 사용
4. **세션 관리**: `app.secret_key`를 환경변수로 관리 권장

## 🆚 데스크톱 vs 웹 버전 선택 가이드

### 데스크톱 버전 추천

- 개인 사용
- 로컬 환경에서만 사용
- 설치 없이 바로 실행하고 싶을 때

### 웹 버전 추천

- 팀 전체가 사용
- 모바일에서도 접속하고 싶을 때
- 서버에서 24시간 운영하고 싶을 때
- 여러 기기에서 동시 접속이 필요할 때

## 🔄 업데이트 내역

### v1.0 (2025-10-25) - Initial Release

- ✅ Flask 기반 웹 서버
- ✅ Server-Sent Events 실시간 알림
- ✅ 반응형 웹 UI
- ✅ 브라우저 알림 지원
- ✅ Web Audio API 알림음
- ✅ 사용자 관리 기능
- ✅ 채널 메시지 뷰어
- ✅ 크로스 플랫폼 지원

## 📚 관련 문서

- [Slack API 문서](https://api.slack.com/)
- [Flask 문서](https://flask.palletsprojects.com/)
- [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)

## 📄 라이선스

MIT License - 자유롭게 사용 가능

## 🤝 기여

버그 리포트나 기능 제안은 이슈로 등록해주세요.

---

**Made with ❤️ for Slack Users**
