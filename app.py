"""
Slack 알림 모니터링 웹 애플리케이션
실시간 멘션 알림, 채널 메시지 조회, 사용자 관리 기능 제공
"""

import sys
import io

# Windows 인코딩 문제 해결
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from flask import Flask, render_template, request, jsonify, Response, session
import requests
import json
import time
from datetime import datetime
import threading
import os
import anthropic
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import re

app = Flask(__name__)
app.secret_key = os.urandom(24)  # 세션 암호화 키

# 전역 변수
monitoring_active = {}  # 사용자별 모니터링 상태
last_check_times = {}  # 사용자별 마지막 체크 시간
notification_queues = {}  # 사용자별 알림 큐

# 사용자 데이터 디렉토리
USER_DATA_DIR = 'user_data'

# 전역 캐시 (메모리 기반, TTL 포함)
_global_user_cache = {}  # {user_id: {"data": user_info, "timestamp": time}}
_global_bot_cache = {}   # {bot_id: {"data": bot_info, "timestamp": time}}
_global_channel_cache = {}  # {token: {"data": channels, "timestamp": time}}
_global_users_list_cache = {}  # {token: {"data": members, "timestamp": time}}
CACHE_TTL = 300  # 5분 TTL
USERS_LIST_CACHE_TTL = 600  # 10분 TTL (users.list는 덜 자주 변경됨)

# 스레드 풀 (병렬 처리용)
executor = ThreadPoolExecutor(max_workers=10)

# Claude API 설정 (환경 변수에서 읽기, 없으면 None)
CLAUDE_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
CLAUDE_ENABLED = CLAUDE_API_KEY is not None

# 우선순위 키워드 정의
PRIORITY_KEYWORDS = {
    'critical': ['버그', '에러', 'error', '장애', '다운', 'down', '긴급', 'urgent', 'ASAP', '급해', '지금', '당장', '안됨', '안돼', '작동안함'],
    'high': [
        # 기존 확인/리뷰 관련
        '확인', '체크', '리뷰', 'review', '승인', 'approve', '피드백', 'feedback', '?', '질문', '어떻게', '왜', '언제',
        # 시간/기한 관련 키워드
        '오늘', '내일', '이번주', '금주', '다음주', '이번달', '마감', 'deadline', '기한', 'due',
        '~까지', '까지', 'by', 'until', 'before',
        '시까지', '시간', 'time', '분까지', '일까지',
        '오전', '오후', 'AM', 'PM', 'am', 'pm',
        '주말', '평일', '월요일', '화요일', '수요일', '목요일', '금요일',
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
        'EOD', 'eod', 'COB', 'cob',  # End of Day, Close of Business
    ],
    'normal': ['공유', '참고', 'FYI', '알려', '업데이트', 'update', '공지'],
}

# 캐시 정리 함수
def cleanup_expired_caches():
    """만료된 캐시 항목 정리"""
    current_time = time.time()

    # User 캐시 정리
    expired_users = [uid for uid, cached in _global_user_cache.items()
                     if current_time - cached["timestamp"] > CACHE_TTL]
    for uid in expired_users:
        del _global_user_cache[uid]

    # Bot 캐시 정리
    expired_bots = [bid for bid, cached in _global_bot_cache.items()
                    if current_time - cached["timestamp"] > CACHE_TTL]
    for bid in expired_bots:
        del _global_bot_cache[bid]

    # Channel 캐시 정리
    expired_channels = [token for token, cached in _global_channel_cache.items()
                        if current_time - cached["timestamp"] > CACHE_TTL]
    for token in expired_channels:
        del _global_channel_cache[token]

    # Users list 캐시 정리
    expired_users_list = [token for token, cached in _global_users_list_cache.items()
                          if current_time - cached["timestamp"] > USERS_LIST_CACHE_TTL]
    for token in expired_users_list:
        del _global_users_list_cache[token]

# 캐시 정리를 주기적으로 실행
def cache_cleanup_thread():
    """백그라운드에서 주기적으로 캐시 정리"""
    while True:
        time.sleep(600)  # 10분마다
        cleanup_expired_caches()

# 캐시 정리 스레드 시작
cleanup_thread = threading.Thread(target=cache_cleanup_thread, daemon=True)
cleanup_thread.start()


# ============================================================
# 사용자별 데이터 관리 헬퍼 함수
# ============================================================

def get_user_data_dir(bot_id):
    """사용자별 데이터 디렉토리 경로 반환"""
    user_dir = os.path.join(USER_DATA_DIR, bot_id)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir, exist_ok=True)
    return user_dir

def get_user_file_path(bot_id, filename):
    """사용자별 파일 경로 반환"""
    return os.path.join(get_user_data_dir(bot_id), filename)

def load_user_watched_users(bot_id):
    """사용자별 watched_users 로드"""
    filepath = get_user_file_path(bot_id, 'watched_users.json')
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ watched_users 로드 실패 ({bot_id}): {e}")
            return []
    return []

def save_user_watched_users(bot_id, users):
    """사용자별 watched_users 저장"""
    filepath = get_user_file_path(bot_id, 'watched_users.json')
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ watched_users 저장 실패 ({bot_id}): {e}")
        return False

def load_user_priority_keywords(bot_id):
    """사용자별 우선순위 키워드 로드"""
    filepath = get_user_file_path(bot_id, 'priority_keywords.json')
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ priority_keywords 로드 실패 ({bot_id}): {e}")
            return None
    return None

def save_user_priority_keywords(bot_id, keywords):
    """사용자별 우선순위 키워드 저장"""
    filepath = get_user_file_path(bot_id, 'priority_keywords.json')
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(keywords, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ priority_keywords 저장 실패 ({bot_id}): {e}")
        return False

def load_user_settings(bot_id):
    """사용자별 설정 로드"""
    filepath = get_user_file_path(bot_id, 'settings.json')
    default_settings = {
        'notification_sound': True,
        'claude_enabled': CLAUDE_ENABLED
    }
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # 기본 설정과 병합
                default_settings.update(loaded)
                return default_settings
        except Exception as e:
            print(f"⚠️ settings 로드 실패 ({bot_id}): {e}")
            return default_settings
    return default_settings

def save_user_settings(bot_id, settings):
    """사용자별 설정 저장"""
    filepath = get_user_file_path(bot_id, 'settings.json')
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ settings 저장 실패 ({bot_id}): {e}")
        return False

def get_user_priority_keywords(bot_id):
    """사용자별 우선순위 키워드 가져오기 (기본값 포함)"""
    user_keywords = load_user_priority_keywords(bot_id)
    if user_keywords:
        return user_keywords
    # 기본 키워드 반환
    return PRIORITY_KEYWORDS.copy()

def load_user_starred_messages(bot_id):
    """사용자별 별표 메시지 로드"""
    filepath = get_user_file_path(bot_id, 'starred_messages.json')
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ starred_messages 로드 실패 ({bot_id}): {e}", flush=True)
            return []
    return []

def save_user_starred_messages(bot_id, starred_messages):
    """사용자별 별표 메시지 저장"""
    filepath = get_user_file_path(bot_id, 'starred_messages.json')
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(starred_messages, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ starred_messages 저장 실패 ({bot_id}): {e}", flush=True)
        return False

# 우선순위 분류 함수
def classify_message_by_keywords(text, keywords=None):
    """키워드 기반 빠른 우선순위 분류"""
    if keywords is None:
        keywords = PRIORITY_KEYWORDS

    text_lower = text.lower()

    # Critical 키워드 확인
    for keyword in keywords.get('critical', []):
        if keyword.lower() in text_lower:
            return 'critical', f'키워드 매칭: {keyword}'

    # High 키워드 확인
    for keyword in keywords.get('high', []):
        if keyword in text_lower:
            return 'high', f'키워드 매칭: {keyword}'

    # Normal 키워드 확인
    for keyword in keywords.get('normal', []):
        if keyword in text_lower:
            return 'normal', f'키워드 매칭: {keyword}'

    # 기본값
    return 'normal', '기본 분류'

def classify_message_with_claude(text, sender, channel):
    """Claude API를 사용한 정확한 우선순위 분류 (키워드 매칭 실패 시에만 사용)"""
    if not CLAUDE_ENABLED:
        return None, 'Claude API 비활성화'

    try:
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

        prompt = f"""다음 Slack 메시지의 우선순위를 분류해주세요.

메시지: "{text}"
발신자: {sender}
채널: {channel}

분류 기준:
- critical: 즉시 대응 필요 (버그, 장애, 고객 불만, 긴급 요청)
- high: 빠른 답변 필요 (피드백 요청, 승인 요청, 중요 질문)
- normal: 일반 메시지 (정보 공유, 업데이트)
- low: 낮은 우선순위 (잡담, 단순 정보)

다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{"priority": "critical|high|normal|low", "reason": "분류 이유 (한 줄)"}}"""

        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )

        # JSON 파싱
        response_text = message.content[0].text.strip()
        result = json.loads(response_text)
        return result['priority'], result['reason']

    except Exception as e:
        print(f"⚠️ Claude API 오류: {e}")
        return None, f'API 오류: {str(e)}'

def classify_message_priority(text, sender='', channel='', keywords=None):
    """하이브리드 우선순위 분류 (키워드 + Claude API)"""
    # 1단계: 빠른 키워드 필터링
    priority, reason = classify_message_by_keywords(text, keywords)

    # Critical 또는 High가 아니면 Claude API로 재검증 (선택적)
    if CLAUDE_ENABLED and priority == 'normal' and len(text) > 20:
        # 일부 메시지만 Claude로 검증 (비용 절감)
        claude_priority, claude_reason = classify_message_with_claude(text, sender, channel)
        if claude_priority:
            return claude_priority, f'Claude: {claude_reason}'

    return priority, reason


class SlackNotifier:
    def __init__(self, token, bot_id=None):
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}"}
        self.bot_user_id = bot_id
        self.watched_users = []
        self.watched_user_ids = []  # username을 user_id로 변환한 캐시
        self.team_url = None  # 워크스페이스 URL
        # 우선순위 키워드 (사용자별)
        self.priority_keywords = None
        # 정규표현식 컴파일 (성능 향상)
        self.mention_pattern = re.compile(r'<@([A-Z0-9]+)>')
        # HTTP 세션 재사용 (연결 풀링으로 성능 향상)
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        # 타임아웃 설정 (connect timeout: 5초, read timeout: 10초)
        self.timeout = (5, 10)
        # User Group 캐시 (ID -> handle 매핑)
        self._usergroups_cache = {}  # {subteam_id: handle}
        self._usergroups_cache_time = 0  # 캐시 생성 시간
        self._usergroups_cache_ttl = 600  # 10분 TTL
        # User Group 멤버 캐시 (ID -> members 매핑)
        self._usergroup_members_cache = {}  # {subteam_id: [user_ids]}
        self._usergroup_members_cache_time = {}  # {subteam_id: timestamp}
        self._usergroup_members_cache_ttl = 300  # 5분 TTL

    def test_connection(self):
        """Slack 연결 테스트 및 봇 정보 가져오기"""
        try:
            response = self.session.get("https://slack.com/api/auth.test", timeout=self.timeout)
            data = response.json()

            print(f"\n=== auth.test 응답 ===")
            print(f"Response: {data}")
            print(f"=" * 50)

            if data.get("ok"):
                self.bot_user_id = data.get("user_id")
                # 워크스페이스 URL 저장 (https://[team].slack.com)
                self.team_url = data.get("url", "")
                print(f"✅ 연결 성공! user_id={self.bot_user_id}, user={data.get('user')}, team_url={self.team_url}")
                return {
                    "success": True,
                    "bot_id": self.bot_user_id,
                    "user": data.get("user"),
                    "team": data.get("team"),
                    "team_url": self.team_url
                }
            else:
                return {
                    "success": False,
                    "error": data.get("error", "Unknown error")
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_message_link(self, channel_id, timestamp):
        """Slack 메시지 링크 생성"""
        if not self.team_url or not channel_id or not timestamp:
            return None

        # timestamp를 Slack 링크 형식으로 변환 (점을 제거하고 p 추가)
        # 예: 1234567890.123456 -> p1234567890123456
        ts_for_link = "p" + timestamp.replace(".", "")

        # team_url이 https://team.slack.com 형식
        return f"{self.team_url}archives/{channel_id}/{ts_for_link}"

    def get_channels_with_bot(self):
        """봇이 참여한 채널 목록 가져오기 (전역 캐시 + TTL)"""
        global _global_channel_cache

        # 전역 캐시 확인
        cache_key = self.token[:20]  # 토큰 일부를 키로 사용
        if cache_key in _global_channel_cache:
            cached = _global_channel_cache[cache_key]
            # TTL 확인
            if time.time() - cached["timestamp"] < CACHE_TTL:
                return cached["data"]

        try:
            response = self.session.get(
                "https://slack.com/api/users.conversations",
                params={"types": "public_channel,private_channel"},
                timeout=self.timeout
            )
            data = response.json()

            if data.get("ok"):
                channels = data.get("channels", [])
                # 전역 캐시 저장
                _global_channel_cache[cache_key] = {
                    "data": channels,
                    "timestamp": time.time()
                }
                return channels
            else:
                return []
        except Exception as e:
            print(f"채널 조회 오류: {e}")
            return []

    def get_channel_messages(self, channel_id, limit=50):
        """특정 채널의 메시지 조회 (병렬 처리로 최적화)"""
        try:
            response = self.session.get(
                "https://slack.com/api/conversations.history",
                params={"channel": channel_id, "limit": limit},
                timeout=self.timeout
            )
            data = response.json()

            if data.get("ok"):
                messages = data.get("messages", [])

                if not messages:
                    return []

                # 사용자 정보 캐시
                user_cache = {}
                bot_cache = {}

                # 필요한 모든 사용자 ID와 봇 ID 수집
                user_ids = set()
                bot_ids = set()
                mention_user_ids = set()

                for msg in messages:
                    # 메시지 작성자
                    if "user" in msg:
                        user_ids.add(msg["user"])
                    elif "bot_id" in msg:
                        bot_ids.add(msg["bot_id"])

                    # 멘션된 사용자
                    if "text" in msg:
                        mentions = self.mention_pattern.findall(msg["text"])
                        mention_user_ids.update(mentions)

                # 모든 사용자를 병렬로 조회
                all_user_ids = user_ids | mention_user_ids
                if all_user_ids:
                    user_cache = self.get_user_info_batch(list(all_user_ids))

                # 봇 정보 조회 (병렬)
                if bot_ids:
                    def fetch_bot(bid):
                        return bid, self.get_bot_info(bid)

                    futures = [executor.submit(fetch_bot, bid) for bid in bot_ids]
                    for future in as_completed(futures):
                        bid, info = future.result()
                        bot_cache[bid] = info

                # 메시지에 정보 추가
                for msg in messages:
                    # 메시지 텍스트에서 사용자 멘션 변환
                    if "text" in msg:
                        msg["text"] = self.replace_user_mentions(msg["text"], user_cache)

                    if "user" in msg:
                        user_id = msg["user"]
                        user_info = user_cache.get(user_id, {})
                        msg["user_name"] = self.get_display_name(user_info)
                        msg["is_bot"] = user_info.get("is_bot", False)
                    elif "bot_id" in msg:
                        bot_id = msg["bot_id"]
                        bot_info = bot_cache.get(bot_id, {})
                        msg["user_name"] = bot_info.get("name", msg.get("username", "Bot"))
                        msg["is_bot"] = True
                    elif "username" in msg:
                        msg["user_name"] = msg["username"]
                        msg["is_bot"] = True
                    else:
                        msg["user_name"] = "Unknown"
                        msg["is_bot"] = False

                    # 스레드 정보 추가
                    if msg.get("thread_ts"):
                        msg["has_thread"] = True
                        msg["reply_count"] = msg.get("reply_count", 0)
                        msg["reply_users_count"] = msg.get("reply_users_count", 0)
                    else:
                        msg["has_thread"] = False

                return messages
            else:
                return []
        except Exception as e:
            print(f"메시지 조회 오류: {e}")
            return []

    def get_user_info(self, user_id):
        """사용자 정보 조회 (전역 캐시 + TTL)"""
        global _global_user_cache

        # 전역 캐시 확인
        if user_id in _global_user_cache:
            cached = _global_user_cache[user_id]
            # TTL 확인
            if time.time() - cached["timestamp"] < CACHE_TTL:
                return cached["data"]

        try:
            response = self.session.get(
                "https://slack.com/api/users.info",
                params={"user": user_id},
                timeout=self.timeout
            )
            data = response.json()

            if data.get("ok"):
                user_info = data.get("user", {})
                # 전역 캐시 저장
                _global_user_cache[user_id] = {
                    "data": user_info,
                    "timestamp": time.time()
                }
                return user_info
            return {}
        except Exception as e:
            print(f"사용자 정보 조회 오류: {e}")
            return {}

    def get_user_id_by_username(self, username):
        """username으로 user_id 조회 (캐싱 최적화)"""
        global _global_users_list_cache

        try:
            # 전역 캐시 확인
            cache_key = self.token[:20]
            members = None

            if cache_key in _global_users_list_cache:
                cached = _global_users_list_cache[cache_key]
                # TTL 확인
                if time.time() - cached["timestamp"] < USERS_LIST_CACHE_TTL:
                    members = cached["data"]

            # 캐시 미스 시 API 호출
            if members is None:
                response = self.session.get("https://slack.com/api/users.list", timeout=self.timeout)
                data = response.json()

                if data.get("ok"):
                    members = data.get("members", [])
                    # 전역 캐시 저장
                    _global_users_list_cache[cache_key] = {
                        "data": members,
                        "timestamp": time.time()
                    }
                else:
                    return None

            # username 매칭
            for member in members:
                if (member.get("name") == username or
                    member.get("real_name") == username or
                    member.get("profile", {}).get("display_name") == username):
                    return member.get("id")

            return None
        except Exception as e:
            print(f"username 조회 오류: {e}")
            return None

    def refresh_watched_user_ids(self):
        """watched_users를 user_id로 변환하여 캐시"""
        self.watched_user_ids = []
        for username in self.watched_users:
            user_id = self.get_user_id_by_username(username)
            if user_id:
                self.watched_user_ids.append(user_id)
                print(f"✅ 감시 사용자 변환: {username} -> {user_id}")
            else:
                print(f"⚠️ 사용자 '{username}' 찾을 수 없음")

    def get_bot_info(self, bot_id):
        """봇 정보 조회 (전역 캐시 + TTL)"""
        global _global_bot_cache

        # 전역 캐시 확인
        if bot_id in _global_bot_cache:
            cached = _global_bot_cache[bot_id]
            # TTL 확인
            if time.time() - cached["timestamp"] < CACHE_TTL:
                return cached["data"]

        try:
            response = self.session.get(
                "https://slack.com/api/bots.info",
                params={"bot": bot_id}
            , timeout=self.timeout)
            data = response.json()

            if data.get("ok"):
                bot_info = data.get("bot", {})
                # 전역 캐시 저장
                _global_bot_cache[bot_id] = {
                    "data": bot_info,
                    "timestamp": time.time()
                }
                return bot_info
            return {}
        except Exception as e:
            print(f"봇 정보 조회 오류: {e}")
            return {}

    def get_display_name(self, user_info):
        """사용자 정보에서 표시할 이름 추출 (닉네임 우선)"""
        if not user_info:
            return "Unknown"

        # 1순위: profile.display_name (닉네임)
        profile = user_info.get("profile", {})
        display_name = profile.get("display_name", "").strip()
        if display_name:
            return display_name

        # 2순위: real_name (실명)
        real_name = user_info.get("real_name", "").strip()
        if real_name:
            return real_name

        # 3순위: name (사용자 ID)
        return user_info.get("name", "Unknown")

    def replace_user_mentions(self, text, user_cache):
        """메시지 텍스트에서 <@USER_ID> 형식을 실제 사용자 이름으로 변환 (최적화)"""
        # 컴파일된 정규표현식 사용
        mentions = self.mention_pattern.findall(text)

        if not mentions:
            return text

        # 각 멘션을 실제 이름으로 변환
        for user_id in mentions:
            if user_id not in user_cache:
                user_cache[user_id] = self.get_user_info(user_id)

            user_info = user_cache[user_id]
            user_name = self.get_display_name(user_info)

            # <@USER_ID>를 @사용자이름으로 변환
            text = text.replace(f'<@{user_id}>', f'@{user_name}')

        return text

    def get_user_info_batch(self, user_ids):
        """여러 사용자 정보를 병렬로 조회"""
        global _global_user_cache

        results = {}
        to_fetch = []

        # 캐시에서 먼저 확인
        for user_id in user_ids:
            if user_id in _global_user_cache:
                cached = _global_user_cache[user_id]
                if time.time() - cached["timestamp"] < CACHE_TTL:
                    results[user_id] = cached["data"]
                    continue
            to_fetch.append(user_id)

        # 병렬로 나머지 조회
        if to_fetch:
            def fetch_user(uid):
                return uid, self.get_user_info(uid)

            futures = [executor.submit(fetch_user, uid) for uid in to_fetch]
            for future in as_completed(futures):
                uid, info = future.result()
                results[uid] = info

        return results

    def get_thread_replies(self, channel_id, thread_ts):
        """스레드 답글 조회"""
        try:
            response = self.session.get(
                "https://slack.com/api/conversations.replies",
                params={
                    "channel": channel_id,
                    "ts": thread_ts
                }
            , timeout=self.timeout)
            data = response.json()

            if data.get("ok"):
                messages = data.get("messages", [])

                if not messages:
                    return []

                # 첫 번째 메시지는 원본 메시지이므로 제외
                thread_replies = messages[1:] if len(messages) > 1 else []

                # 사용자 정보 캐시
                user_cache = {}
                bot_cache = {}

                # 필요한 모든 사용자 ID와 봇 ID 수집
                user_ids = set()
                bot_ids = set()
                mention_user_ids = set()

                for msg in thread_replies:
                    # 메시지 작성자
                    if "user" in msg:
                        user_ids.add(msg["user"])
                    elif "bot_id" in msg:
                        bot_ids.add(msg["bot_id"])

                    # 멘션된 사용자
                    if "text" in msg:
                        mentions = self.mention_pattern.findall(msg["text"])
                        mention_user_ids.update(mentions)

                # 모든 사용자를 병렬로 조회
                all_user_ids = user_ids | mention_user_ids
                if all_user_ids:
                    user_cache = self.get_user_info_batch(list(all_user_ids))

                # 봇 정보 조회 (병렬)
                if bot_ids:
                    def fetch_bot(bid):
                        return bid, self.get_bot_info(bid)

                    futures = [executor.submit(fetch_bot, bid) for bid in bot_ids]
                    for future in as_completed(futures):
                        bid, info = future.result()
                        bot_cache[bid] = info

                # 메시지에 정보 추가
                for msg in thread_replies:
                    # 메시지 텍스트에서 사용자 멘션 변환
                    if "text" in msg:
                        msg["text"] = self.replace_user_mentions(msg["text"], user_cache)

                    if "user" in msg:
                        user_id = msg["user"]
                        user_info = user_cache.get(user_id, {})
                        msg["user_name"] = self.get_display_name(user_info)
                        msg["is_bot"] = user_info.get("is_bot", False)
                    elif "bot_id" in msg:
                        bot_id = msg["bot_id"]
                        bot_info = bot_cache.get(bot_id, {})
                        msg["user_name"] = bot_info.get("name", msg.get("username", "Bot"))
                        msg["is_bot"] = True
                    elif "username" in msg:
                        msg["user_name"] = msg["username"]
                        msg["is_bot"] = True
                    else:
                        msg["user_name"] = "Unknown"
                        msg["is_bot"] = False

                return thread_replies
            else:
                return []
        except Exception as e:
            print(f"스레드 답글 조회 오류: {e}")
            return []

    def get_my_activity(self, limit=50):
        """내 활동 메시지 조회 (멘션, 반응, 스레드, DM 등 모든 활동)"""
        try:
            all_activities = []
            channels = self.get_channels_with_bot()

            print(f"=== 내 활동 조회 시작: 총 {len(channels)}개 채널 검색 ===")

            # 1. 각 채널에서 나와 관련된 활동 찾기
            for channel in channels:
                channel_id = channel["id"]
                channel_name = channel["name"]
                channel_type = "channel"

                try:
                    response = self.session.get(
                        "https://slack.com/api/conversations.history",
                        params={
                            "channel": channel_id,
                            "limit": 100  # 각 채널에서 최근 100개 확인
                        }
                    , timeout=self.timeout)
                    data = response.json()

                    if data.get("ok"):
                        messages = data.get("messages", [])

                        for msg in messages:
                            text = msg.get("text", "")
                            activity_type = None
                            msg_user = msg.get("user")

                            # 1) 나에 대한 직접 멘션
                            if f'<@{self.bot_user_id}>' in text:
                                activity_type = "mention"
                                msg["activity_type"] = "멘션"
                                msg["activity_icon"] = "💬"

                            # 2) 내가 보낸 메시지에 대한 스레드 답글
                            elif msg.get("thread_ts") and msg.get("thread_ts") != msg.get("ts"):
                                # 스레드의 원본 메시지가 내가 작성한 것인지 확인
                                thread_parent_ts = msg.get("thread_ts")
                                # 원본 메시지 찾기
                                parent_msg = next((m for m in messages if m.get("ts") == thread_parent_ts), None)
                                # 원본 메시지가 내가 작성한 것이고, 답글은 다른 사람이 작성한 경우만 포함
                                if parent_msg and parent_msg.get("user") == self.bot_user_id and msg_user != self.bot_user_id:
                                    activity_type = "thread"
                                    msg["activity_type"] = "스레드 답글"
                                    msg["activity_icon"] = "💭"

                            # 3) 내 메시지에 대한 반응 (내가 작성한 메시지만)
                            elif msg.get("reactions") and msg_user == self.bot_user_id:
                                activity_type = "reaction"
                                reactions_text = ", ".join([f":{r['name']}:" for r in msg.get("reactions", [])])
                                msg["activity_type"] = f"반응: {reactions_text}"
                                msg["activity_icon"] = "❤️"

                            # 4) @channel, @here 전체 멘션 (내가 보낸 것이 아닌 경우만)
                            elif ("@channel" in text or "@here" in text) and msg_user != self.bot_user_id:
                                activity_type = "broadcast"
                                msg["activity_type"] = "전체 멘션"
                                msg["activity_icon"] = "📢"

                            if activity_type:
                                msg["channel_id"] = channel_id
                                msg["channel_name"] = channel_name
                                msg["channel_type"] = channel_type
                                all_activities.append(msg)

                except Exception as e:
                    print(f"채널 {channel_name} 조회 오류: {e}")
                    continue

            # 2. DM (Direct Message) 조회
            try:
                dm_response = self.session.get(
                    "https://slack.com/api/conversations.list",
                    params={
                        "types": "im",  # Direct Message
                        "limit": 100
                    }
                , timeout=self.timeout)
                dm_data = dm_response.json()

                if dm_data.get("ok"):
                    dm_channels = dm_data.get("channels", [])
                    print(f"=== {len(dm_channels)}개 DM 채널 검색 ===")

                    for dm_channel in dm_channels[:10]:  # 최근 10개 DM만 확인
                        dm_id = dm_channel["id"]

                        try:
                            dm_history = self.session.get(
                                "https://slack.com/api/conversations.history",
                                params={
                                    "channel": dm_id,
                                    "limit": 20
                                }
                            , timeout=self.timeout)
                            dm_history_data = dm_history.json()

                            if dm_history_data.get("ok"):
                                dm_messages = dm_history_data.get("messages", [])

                                for msg in dm_messages:
                                    # 내가 받은 DM (상대방이 보낸 메시지)
                                    if msg.get("user") != self.bot_user_id:
                                        msg["channel_id"] = dm_id
                                        msg["channel_name"] = "DM"
                                        msg["channel_type"] = "dm"
                                        msg["activity_type"] = "DM"
                                        msg["activity_icon"] = "✉️"
                                        all_activities.append(msg)
                        except Exception as e:
                            print(f"DM 조회 오류: {e}")
                            continue

            except Exception as e:
                print(f"DM 목록 조회 오류: {e}")

            print(f"=== 총 {len(all_activities)}개 활동 발견 ===")

            # 타임스탬프로 정렬 (최신순)
            all_activities.sort(key=lambda x: float(x.get('ts', 0)), reverse=True)

            # limit 적용
            messages = all_activities[:limit]

            if not messages:
                print("=== 멘션 메시지 없음 ===")
                return []

            # 사용자 정보 캐싱
            user_cache = {}
            bot_cache = {}

            # 필요한 모든 사용자 ID와 봇 ID 수집
            user_ids = set()
            bot_ids = set()
            mention_user_ids = set()

            for msg in messages:
                # 메시지 작성자
                if "user" in msg:
                    user_ids.add(msg["user"])
                elif "bot_id" in msg:
                    bot_ids.add(msg["bot_id"])

                # 멘션된 사용자
                if "text" in msg:
                    mentions = self.mention_pattern.findall(msg["text"])
                    mention_user_ids.update(mentions)

            # 모든 사용자를 병렬로 조회
            all_user_ids = user_ids | mention_user_ids
            if all_user_ids:
                user_cache = self.get_user_info_batch(list(all_user_ids))

            # 봇 정보 조회 (병렬)
            if bot_ids:
                def fetch_bot(bid):
                    return bid, self.get_bot_info(bid)

                futures = [executor.submit(fetch_bot, bid) for bid in bot_ids]
                for future in as_completed(futures):
                    bid, info = future.result()
                    bot_cache[bid] = info

            # 메시지에 정보 추가
            for msg in messages:
                # 메시지 텍스트에서 사용자 멘션 변환
                if "text" in msg:
                    msg["text"] = self.replace_user_mentions(msg["text"], user_cache)

                if "user" in msg:
                    user_id = msg["user"]
                    user_info = user_cache.get(user_id, {})
                    msg["user_name"] = self.get_display_name(user_info)
                    msg["is_bot"] = user_info.get("is_bot", False)
                elif "bot_id" in msg:
                    bot_id = msg["bot_id"]
                    bot_info = bot_cache.get(bot_id, {})
                    msg["user_name"] = bot_info.get("name", msg.get("username", "Bot"))
                    msg["is_bot"] = True
                elif "username" in msg:
                    msg["user_name"] = msg["username"]
                    msg["is_bot"] = True
                else:
                    msg["user_name"] = "Unknown"
                    msg["is_bot"] = False

            print(f"=== {len(messages)}개 메시지 반환 ===")
            return messages
        except Exception as e:
            print(f"내 활동 조회 오류: {e}")
            return []

    def get_usergroup_handle(self, subteam_id):
        """User Group ID로 handle 조회 (캐싱 적용)"""
        current_time = time.time()

        # 캐시가 유효하고 해당 ID가 캐시에 있으면 반환
        if (current_time - self._usergroups_cache_time < self._usergroups_cache_ttl and
            subteam_id in self._usergroups_cache):
            return self._usergroups_cache[subteam_id]

        # 캐시가 만료되었거나 없으면 전체 목록 새로 조회
        if current_time - self._usergroups_cache_time >= self._usergroups_cache_ttl:
            try:
                list_response = self.session.get(
                    "https://slack.com/api/usergroups.list",
                    params={"include_users": False}
                , timeout=self.timeout)
                list_data = list_response.json()
                if list_data.get("ok"):
                    # 전체 캐시 갱신
                    self._usergroups_cache = {
                        ug.get("id"): ug.get("handle", "그룹")
                        for ug in list_data.get("usergroups", [])
                    }
                    self._usergroups_cache_time = current_time
            except Exception as e:
                print(f"❌ User Group 목록 조회 실패: {e}")

        # 캐시에서 반환 (없으면 기본값)
        return self._usergroups_cache.get(subteam_id, "그룹")

    def get_usergroup_members(self, subteam_id):
        """User Group ID로 멤버 리스트 조회 (캐싱 적용)"""
        current_time = time.time()

        # 캐시가 유효하고 해당 ID가 캐시에 있으면 반환
        if (subteam_id in self._usergroup_members_cache_time and
            current_time - self._usergroup_members_cache_time[subteam_id] < self._usergroup_members_cache_ttl):
            return self._usergroup_members_cache.get(subteam_id, [])

        # 캐시가 없거나 만료되면 API 호출
        try:
            response = self.session.get(
                "https://slack.com/api/usergroups.users.list",
                params={"usergroup": subteam_id}
            , timeout=self.timeout)
            data = response.json()
            if data.get("ok"):
                members = data.get("users", [])
                # 캐시 저장
                self._usergroup_members_cache[subteam_id] = members
                self._usergroup_members_cache_time[subteam_id] = current_time
                return members
        except Exception as e:
            print(f"❌ 그룹 멤버 조회 실패: {e}")

        # 실패 시 빈 리스트 반환
        return []

    def check_new_mentions(self, since_timestamp):
        """새로운 멘션 확인 (병렬 처리 최적화)"""
        notifications = []
        channels = self.get_channels_with_bot()
        max_timestamp = since_timestamp  # 처리한 메시지 중 가장 최신 timestamp 추적

        # 채널 병렬 처리 함수
        def check_channel(channel):
            channel_notifications = []
            local_max_ts = since_timestamp
            channel_id = channel["id"]
            channel_name = channel["name"]

            try:
                response = self.session.get(
                    "https://slack.com/api/conversations.history",
                    params={
                        "channel": channel_id,
                        "oldest": str(since_timestamp),
                        "limit": 100
                    },
                    timeout=self.timeout
                )
                data = response.json()

                if data.get("ok"):
                    messages = data.get("messages", [])

                    for msg in messages:
                        text = msg.get("text", "")
                        user_id = msg.get("user", "")
                        bot_id = msg.get("bot_id", "")
                        ts = float(msg.get("ts", 0))

                        # 자신의 메시지는 제외
                        if user_id == self.bot_user_id:
                            continue

                        is_notification = False
                        notification_reason = ""

                        # 1. 봇 멘션 확인
                        if f'<@{self.bot_user_id}>' in text:
                            is_notification = True
                            notification_reason = "봇 멘션"

                        # 2. @channel, @here 확인
                        elif '@here' in text or '@channel' in text or '<!channel' in text or '<!here' in text:
                            is_notification = True
                            notification_reason = "@here/@channel"

                        # 3. User Group 멘션 확인 (<!subteam^ID> 또는 <!subteam^ID|@groupname> 형식)
                        elif '<!subteam^' in text:
                            # 두 가지 패턴 모두 지원: <!subteam^ID> 또는 <!subteam^ID|@groupname>
                            subteam_pattern = re.compile(r'<!subteam\^([A-Z0-9]+)(?:\|@([^>]+))?>')
                            matches = subteam_pattern.findall(text)
                            for match in matches:
                                subteam_id = match[0]
                                # 메시지에 포함된 이름이 있으면 사용, 없으면 캐시에서 조회
                                group_name = match[1] if match[1] else self.get_usergroup_handle(subteam_id)

                                # User Group 멤버 확인 (캐싱 사용)
                                members = self.get_usergroup_members(subteam_id)

                                # 1) 감시 중인 사용자가 그룹에 속해있는지 확인
                                for watched_user_id in self.watched_user_ids:
                                    if watched_user_id in members:
                                        is_notification = True
                                        notification_reason = f"그룹 멘션 (@{group_name})"
                                        break

                                # 2) watched_users가 비어있거나, 봇 자신이 그룹 멤버인 경우
                                if not is_notification:
                                    if not self.watched_user_ids or self.bot_user_id in members:
                                        is_notification = True
                                        notification_reason = f"그룹 멘션 (@{group_name})"

                                if is_notification:
                                    break

                        # 4. 등록된 사용자 멘션 확인
                        if not is_notification:
                            for watched_user_id in self.watched_user_ids:
                                if f'<@{watched_user_id}>' in text:
                                    is_notification = True
                                    notification_reason = f"사용자 멘션"
                                    break

                        if is_notification:
                            # 사용자 또는 봇 정보 가져오기
                            if user_id:
                                user_info = self.get_user_info(user_id)
                                display_name = self.get_display_name(user_info)
                            elif bot_id:
                                bot_info = self.get_bot_info(bot_id)
                                display_name = bot_info.get("name", msg.get("username", "Bot"))
                            else:
                                display_name = msg.get("username", "Unknown")

                            # 텍스트에서 사용자 멘션을 실제 이름으로 변환
                            user_cache = {}
                            display_text = self.replace_user_mentions(text, user_cache)

                            # 메시지 링크 생성
                            message_link = self.get_message_link(channel_id, str(ts))

                            # 우선순위 분류 (사용자별 키워드 사용)
                            priority, priority_reason = classify_message_priority(
                                text, display_name, channel_name,
                                keywords=self.priority_keywords
                            )

                            channel_notifications.append({
                                "channel": channel_name,
                                "channel_id": channel_id,
                                "user": display_name,
                                "text": display_text,
                                "timestamp": ts,
                                "reason": notification_reason,
                                "time": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
                                "message_link": message_link,
                                "priority": priority,
                                "priority_reason": priority_reason
                            })

                        # 메시지 timestamp 추적
                        if ts > local_max_ts:
                            local_max_ts = ts

            except Exception as e:
                pass  # 에러는 무시 (로그 감소)

            return channel_notifications, local_max_ts

        # 채널들을 병렬로 처리
        futures = [executor.submit(check_channel, ch) for ch in channels]
        for future in as_completed(futures):
            channel_notifs, local_max = future.result()
            notifications.extend(channel_notifs)
            if local_max > max_timestamp:
                max_timestamp = local_max

        # 4. DM (Direct Message) 확인
        try:
            dm_response = self.session.get(
                "https://slack.com/api/conversations.list",
                params={
                    "types": "im",  # Direct Message
                    "limit": 100
                }
            , timeout=self.timeout)
            dm_data = dm_response.json()

            if dm_data.get("ok"):
                dm_channels = dm_data.get("channels", [])

                for dm_channel in dm_channels:
                    dm_id = dm_channel["id"]

                    try:
                        dm_history = self.session.get(
                            "https://slack.com/api/conversations.history",
                            params={
                                "channel": dm_id,
                                "oldest": str(since_timestamp),
                                "limit": 50
                            },
                            timeout=self.timeout
                        )
                        dm_history_data = dm_history.json()

                        if dm_history_data.get("ok"):
                            dm_messages = dm_history_data.get("messages", [])

                            for msg in dm_messages:
                                # 내가 받은 DM (상대방이 보낸 메시지)
                                if msg.get("user") != self.bot_user_id:
                                    user_id = msg.get("user", "")
                                    text = msg.get("text", "")
                                    ts = float(msg.get("ts", 0))

                                    user_info = self.get_user_info(user_id)
                                    display_name = self.get_display_name(user_info)

                                    # 텍스트에서 사용자 멘션을 실제 이름으로 변환
                                    user_cache = {}
                                    display_text = self.replace_user_mentions(text, user_cache)

                                    # 메시지 링크 생성
                                    message_link = self.get_message_link(dm_id, str(ts))

                                    notifications.append({
                                        "channel": f"DM from {display_name}",
                                        "channel_id": dm_id,
                                        "user": display_name,
                                        "text": display_text,
                                        "timestamp": ts,
                                        "reason": "DM",
                                        "time": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
                                        "message_link": message_link
                                    })

                                    # 메시지 timestamp 추적
                                    if ts > max_timestamp:
                                        max_timestamp = ts
                    except Exception as e:
                        print(f"DM 확인 오류: {e}")
                        continue

        except Exception as e:
            print(f"DM 목록 조회 오류: {e}")

        return notifications, max_timestamp


# Flask 라우트
@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')


@app.route('/api/connect', methods=['POST'])
def connect():
    """Slack 연결"""
    data = request.json
    token = data.get('token', '')

    if not token:
        return jsonify({"success": False, "error": "토큰이 필요합니다"})

    notifier = SlackNotifier(token)
    result = notifier.test_connection()

    if result["success"]:
        # 세션에 토큰과 notifier 정보 저장
        session['token'] = token
        session['bot_id'] = result['bot_id']
        session['team_url'] = result.get('team_url', '')
        session_id = session.sid if hasattr(session, 'sid') else str(time.time())

        # 사용자별 초기화
        if session_id not in monitoring_active:
            monitoring_active[session_id] = False
            last_check_times[session_id] = time.time()
            notification_queues[session_id] = []

    return jsonify(result)


@app.route('/api/channels', methods=['GET'])
def get_channels():
    """채널 목록 조회"""
    token = session.get('token')
    if not token:
        return jsonify({"success": False, "error": "연결되지 않음"})

    notifier = SlackNotifier(token)
    notifier.bot_user_id = session.get('bot_id')
    channels = notifier.get_channels_with_bot()

    # 디버그 로그
    print(f"=== 채널 목록 조회 ===")
    print(f"총 {len(channels)}개 채널 발견:")
    for ch in channels:
        print(f"  - {ch['name']} (ID: {ch['id']})")
    print("=" * 50)

    return jsonify({
        "success": True,
        "channels": [{"id": ch["id"], "name": ch["name"]} for ch in channels]
    })


@app.route('/api/debug/channels', methods=['GET'])
def debug_channels():
    """모든 채널 조회 (디버그용)"""
    token = session.get('token')
    if not token:
        return jsonify({"success": False, "error": "연결되지 않음"})

    try:
        # 모든 public 채널 조회
        response = requests.get(
            "https://slack.com/api/conversations.list",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "types": "public_channel,private_channel",
                "exclude_archived": True,
                "limit": 200
            }
        )
        data = response.json()

        if data.get("ok"):
            all_channels = data.get("channels", [])
            bot_id = session.get('bot_id')

            result = {
                "success": True,
                "total_channels": len(all_channels),
                "bot_id": bot_id,
                "channels": []
            }

            for ch in all_channels:
                channel_info = {
                    "id": ch["id"],
                    "name": ch["name"],
                    "is_member": ch.get("is_member", False),
                    "is_private": ch.get("is_private", False),
                    "num_members": ch.get("num_members", 0)
                }
                result["channels"].append(channel_info)

            return jsonify(result)
        else:
            return jsonify({"success": False, "error": data.get("error", "Unknown")})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/messages/<channel_id>', methods=['GET'])
def get_messages(channel_id):
    """채널 메시지 조회"""
    token = session.get('token')
    limit = request.args.get('limit', 50, type=int)

    if not token:
        return jsonify({"success": False, "error": "연결되지 않음"})

    notifier = SlackNotifier(token)
    messages = notifier.get_channel_messages(channel_id, limit)

    return jsonify({
        "success": True,
        "messages": messages
    })


@app.route('/api/my-activity', methods=['GET'])
def get_my_activity():
    """내 활동 메시지 조회 (나에게 온 멘션 등)"""
    token = session.get('token')
    bot_id = session.get('bot_id')
    limit = request.args.get('limit', 50, type=int)

    if not token:
        return jsonify({"success": False, "error": "연결되지 않음"})

    notifier = SlackNotifier(token)
    notifier.bot_user_id = bot_id
    messages = notifier.get_my_activity(limit)

    return jsonify({
        "success": True,
        "messages": messages
    })


@app.route('/api/monitoring/start', methods=['POST'])
def start_monitoring():
    """실시간 모니터링 시작"""
    session_id = request.json.get('session_id', str(time.time()))

    if session_id not in monitoring_active:
        monitoring_active[session_id] = False
        # 10초 전부터 감지하도록 설정
        last_check_times[session_id] = time.time() - 10
        notification_queues[session_id] = []

    monitoring_active[session_id] = True
    # 모니터링 시작 시점도 10초 전으로 설정
    last_check_times[session_id] = time.time() - 10

    return jsonify({"success": True, "message": "모니터링 시작됨"})


@app.route('/api/monitoring/stop', methods=['POST'])
def stop_monitoring():
    """실시간 모니터링 중지"""
    session_id = request.json.get('session_id', str(time.time()))

    if session_id in monitoring_active:
        monitoring_active[session_id] = False

    return jsonify({"success": True, "message": "모니터링 중지됨"})


@app.route('/api/monitoring/test', methods=['POST'])
def test_notification():
    """테스트 알림 생성"""
    session_id = request.json.get('session_id', str(time.time()))

    # 더미 알림 데이터 생성
    test_notifications = [
        {
            "channel": "테스트-채널",
            "channel_id": "C123456",
            "user": "테스트사용자",
            "text": "@당신 테스트 멘션입니다! 실시간 알림이 잘 작동하는지 확인하는 메시지입니다.",
            "timestamp": time.time(),
            "reason": "봇 멘션",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "channel": "일반-채널",
            "channel_id": "C789012",
            "user": "김철수",
            "text": "@channel 전체 공지사항입니다.",
            "timestamp": time.time(),
            "reason": "@here/@channel",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "channel": "DM from 이영희",
            "channel_id": "D345678",
            "user": "이영희",
            "text": "안녕하세요! DM 테스트 메시지입니다.",
            "timestamp": time.time(),
            "reason": "DM",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    ]

    # 세션의 알림 큐에 추가
    if session_id not in notification_queues:
        notification_queues[session_id] = []

    notification_queues[session_id].extend(test_notifications)

    return jsonify({"success": True, "message": f"{len(test_notifications)}개의 테스트 알림 생성됨"})


@app.route('/api/monitoring/events')
def monitoring_events():
    """Server-Sent Events를 통한 실시간 알림"""
    # request 컨텍스트에서 미리 값을 추출
    session_id = request.args.get('session_id', str(time.time()))
    token = session.get('token')
    bot_id = session.get('bot_id')
    team_url = session.get('team_url', '')

    print(f"🔥 SSE 연결 요청 (session_id={session_id}, bot_id={bot_id})", flush=True)

    def generate():
        # 클로저로 session_id, token, bot_id, team_url 사용
        if not token:
            print(f"❌ 토큰 없음 (session_id={session_id})", flush=True)
            yield f"data: {json.dumps({'error': '연결되지 않음'})}\n\n"
            return

        try:
            notifier = SlackNotifier(token, bot_id)
            notifier.team_url = team_url

            # watched_users 로드 (사용자별)
            notifier.watched_users = load_user_watched_users(bot_id)

            # 우선순위 키워드 로드 (사용자별)
            notifier.priority_keywords = get_user_priority_keywords(bot_id)

            # watched_users를 user_id로 변환 (초기화 시 한 번만)
            notifier.refresh_watched_user_ids()

            # 적응형 폴링 설정
            polling_fast = 0.2      # 빠른 모드: 알림 있을 때
            polling_normal = 0.5    # 일반 모드: 활동 중
            polling_slow = 0.8      # 느린 모드: 알림 없을 때
            current_polling = polling_normal

            # 폴링 속도 조정을 위한 변수
            consecutive_empty_checks = 0  # 연속 빈 체크 횟수
            last_notification_time = time.time()

            # 감시 사용자 목록 리로드 타이머
            last_reload_time = time.time()
            reload_interval = 5  # 5초마다 watched_users 다시 읽기

            # 연결 성공 heartbeat 전송
            yield f": heartbeat\n\n"

            print(f"✅ SSE 연결 성공 (session_id={session_id}, watched_users={notifier.watched_users}, adaptive_polling=ON)", flush=True)
        except Exception as e:
            print(f"❌ SSE 초기화 오류: {e}", flush=True)
            yield f"data: {json.dumps({'error': f'초기화 실패: {str(e)}'})}\n\n"
            return

        while True:
            try:
                if session_id in monitoring_active and monitoring_active[session_id]:
                    # 0. 주기적으로 watched_users 리로드 (사용자별)
                    current_time = time.time()
                    if current_time - last_reload_time >= reload_interval:
                        try:
                            new_watched_users = load_user_watched_users(bot_id)
                            # 변경 사항이 있으면 리로드
                            if new_watched_users != notifier.watched_users:
                                notifier.watched_users = new_watched_users
                                notifier.refresh_watched_user_ids()
                                print(f"🔄 감시 사용자 목록 리로드됨 ({bot_id}): {notifier.watched_users}")
                            last_reload_time = current_time
                        except Exception as e:
                            print(f"⚠️ watched_users 리로드 실패: {e}")

                    # 1. 큐에 있는 테스트 알림 먼저 전송
                    if session_id in notification_queues and notification_queues[session_id]:
                        queued_notifications = notification_queues[session_id][:]
                        notification_queues[session_id] = []
                        for notif in queued_notifications:
                            yield f"data: {json.dumps(notif)}\n\n"

                    # 2. 실제 Slack 알림 확인
                    since = last_check_times.get(session_id, time.time())
                    notifications, max_timestamp = notifier.check_new_mentions(since)

                    if notifications:
                        # 알림이 있으면 빠른 모드로 전환
                        consecutive_empty_checks = 0
                        current_polling = polling_fast
                        last_notification_time = time.time()

                        print(f"🔔 {len(notifications)}개 알림 전송 (session_id={session_id}, polling={current_polling}s)", flush=True)
                        for i, notif in enumerate(notifications):
                            print(f"  [{i+1}] {notif.get('reason')}: {notif.get('channel')} - {notif.get('text')[:50]}", flush=True)
                            yield f"data: {json.dumps(notif)}\n\n"
                    else:
                        # 알림이 없으면 점점 느리게
                        consecutive_empty_checks += 1

                        if consecutive_empty_checks >= 6:
                            # 6회 이상 빈 체크: 느린 모드 (1.5초)
                            current_polling = polling_slow
                        elif consecutive_empty_checks >= 3:
                            # 3-5회 빈 체크: 일반 모드 (0.5초)
                            current_polling = polling_normal
                        # else: 1-2회는 빠른 모드 유지 (0.2초)

                    # 가장 최신 메시지 timestamp로 업데이트 (time.time() 대신)
                    last_check_times[session_id] = max_timestamp

                time.sleep(current_polling)

            except GeneratorExit:
                # 클라이언트 연결 종료
                print(f"🔌 SSE 연결 종료됨 (session_id={session_id})", flush=True)
                break
            except Exception as e:
                print(f"⚠️ 모니터링 루프 오류: {e}", flush=True)
                import traceback
                traceback.print_exc()
                # 에러가 나도 계속 진행
                time.sleep(1)

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/channel/stream/<channel_id>')
def channel_stream(channel_id):
    """채널 메시지 실시간 스트리밍"""
    token = session.get('token')
    bot_id = session.get('bot_id')

    print(f"=== 채널 스트리밍 요청: {channel_id} ===")

    def generate():
        if not token:
            print("토큰 없음!")
            yield f"data: {json.dumps({'error': '연결되지 않음'})}\n\n"
            return

        notifier = SlackNotifier(token)
        notifier.bot_user_id = bot_id

        # 초기 타임스탬프 설정 (10초 전부터 감지하도록)
        last_ts = time.time() - 10

        print(f"채널 스트리밍 루프 시작: {channel_id}, last_ts={last_ts}")

        while True:
            try:
                # 최신 메시지 조회 (limit 5로 줄여서 API 응답속도 향상)
                messages = notifier.get_channel_messages(channel_id, limit=5)

                if messages:
                    # 새로운 메시지만 전송
                    new_messages = [msg for msg in messages if float(msg.get('ts', 0)) > last_ts]

                    if new_messages:
                        print(f">>> 새 메시지 {len(new_messages)}개 발견!")
                        # 타임스탬프 업데이트
                        last_ts = max(float(msg.get('ts', 0)) for msg in messages)

                        # 새 메시지 전송 (최신순)
                        for msg in new_messages:
                            print(f"메시지 전송: {msg.get('text', '')[:30]}...")
                            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"

                time.sleep(1.5)  # 1.5초마다 체크 (응답속도 최적화)

            except Exception as e:
                print(f"!!! 채널 스트림 오류: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive'
    })


@app.route('/api/users/watched', methods=['GET'])
def get_watched_users():
    """모니터링 사용자 목록 조회 (사용자별)"""
    bot_id = session.get('bot_id')
    if not bot_id:
        return jsonify({"success": False, "error": "연결되지 않음"})

    users = load_user_watched_users(bot_id)
    return jsonify({"success": True, "users": users})


@app.route('/api/users/watched', methods=['POST'])
def add_watched_user():
    """모니터링 사용자 추가 (사용자별)"""
    bot_id = session.get('bot_id')
    if not bot_id:
        return jsonify({"success": False, "error": "연결되지 않음"})

    data = request.json
    user = data.get('user', '').strip()

    if not user:
        return jsonify({"success": False, "error": "사용자 이름이 필요합니다"})

    users = load_user_watched_users(bot_id)

    if user not in users:
        users.append(user)
        if save_user_watched_users(bot_id, users):
            return jsonify({"success": True, "users": users})
        else:
            return jsonify({"success": False, "error": "저장 실패"})

    return jsonify({"success": False, "error": "이미 추가된 사용자입니다"})


@app.route('/api/users/watched/<user>', methods=['DELETE'])
def remove_watched_user(user):
    """모니터링 사용자 제거 (사용자별)"""
    bot_id = session.get('bot_id')
    if not bot_id:
        return jsonify({"success": False, "error": "연결되지 않음"})

    users = load_user_watched_users(bot_id)

    if user in users:
        users.remove(user)
        if save_user_watched_users(bot_id, users):
            return jsonify({"success": True, "users": users})
        else:
            return jsonify({"success": False, "error": "저장 실패"})

    return jsonify({"success": False, "error": "사용자를 찾을 수 없습니다"})


@app.route('/api/thread/<channel_id>/<thread_ts>', methods=['GET'])
def get_thread(channel_id, thread_ts):
    """스레드 답글 조회"""
    token = session.get('token')

    if not token:
        return jsonify({"success": False, "error": "연결되지 않음"})

    notifier = SlackNotifier(token)
    notifier.bot_user_id = session.get('bot_id')
    replies = notifier.get_thread_replies(channel_id, thread_ts)

    return jsonify({
        "success": True,
        "replies": replies
    })


# ============================================================
# 우선순위 키워드 관리 API
# ============================================================

@app.route('/api/priority/keywords', methods=['GET'])
def get_priority_keywords():
    """우선순위 키워드 목록 조회 (사용자별)"""
    bot_id = session.get('bot_id')
    if not bot_id:
        return jsonify({"success": False, "error": "연결되지 않음"})

    keywords = get_user_priority_keywords(bot_id)
    return jsonify({
        'success': True,
        'keywords': keywords
    })

@app.route('/api/priority/keywords/<priority>', methods=['POST'])
def add_priority_keyword(priority):
    """우선순위 키워드 추가 (사용자별)"""
    bot_id = session.get('bot_id')
    if not bot_id:
        return jsonify({"success": False, "error": "연결되지 않음"})

    try:
        keywords = get_user_priority_keywords(bot_id)

        if priority not in keywords:
            return jsonify({'success': False, 'error': '잘못된 우선순위입니다'})

        data = request.json
        keyword = data.get('keyword', '').strip()

        if not keyword:
            return jsonify({'success': False, 'error': '키워드를 입력하세요'})

        if keyword in keywords[priority]:
            return jsonify({'success': False, 'error': '이미 존재하는 키워드입니다'})

        keywords[priority].append(keyword)

        # 사용자별 키워드 저장
        if save_user_priority_keywords(bot_id, keywords):
            return jsonify({
                'success': True,
                'keywords': keywords
            })
        else:
            return jsonify({'success': False, 'error': '저장 실패'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/priority/keywords/<priority>/<keyword>', methods=['DELETE'])
def delete_priority_keyword(priority, keyword):
    """우선순위 키워드 삭제 (사용자별)"""
    bot_id = session.get('bot_id')
    if not bot_id:
        return jsonify({"success": False, "error": "연결되지 않음"})

    try:
        keywords = get_user_priority_keywords(bot_id)

        if priority not in keywords:
            return jsonify({'success': False, 'error': '잘못된 우선순위입니다'})

        if keyword not in keywords[priority]:
            return jsonify({'success': False, 'error': '키워드를 찾을 수 없습니다'})

        keywords[priority].remove(keyword)

        # 사용자별 키워드 저장
        if save_user_priority_keywords(bot_id, keywords):
            return jsonify({
                'success': True,
                'keywords': keywords
            })
        else:
            return jsonify({'success': False, 'error': '저장 실패'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============================================================
# 사용자별 설정 관리 API
# ============================================================

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """사용자별 설정 조회"""
    bot_id = session.get('bot_id')
    if not bot_id:
        return jsonify({"success": False, "error": "연결되지 않음"})

    settings = load_user_settings(bot_id)
    return jsonify({"success": True, "settings": settings})

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """사용자별 설정 업데이트"""
    bot_id = session.get('bot_id')
    if not bot_id:
        return jsonify({"success": False, "error": "연결되지 않음"})

    data = request.json
    settings = data.get('settings', {})

    if save_user_settings(bot_id, settings):
        return jsonify({"success": True, "settings": settings})
    else:
        return jsonify({"success": False, "error": "저장 실패"})

# ===== 별표 메시지 API =====
@app.route('/api/starred', methods=['GET'])
def get_starred_messages():
    """사용자별 별표 메시지 조회"""
    bot_id = session.get('bot_id')
    if not bot_id:
        return jsonify({"success": False, "error": "연결되지 않음"})

    starred_messages = load_user_starred_messages(bot_id)
    return jsonify({"success": True, "messages": starred_messages})

@app.route('/api/starred', methods=['POST'])
def add_starred_message():
    """별표 메시지 추가"""
    bot_id = session.get('bot_id')
    if not bot_id:
        return jsonify({"success": False, "error": "연결되지 않음"})

    data = request.json
    message = data.get('message')

    if not message:
        return jsonify({"success": False, "error": "메시지 데이터 없음"})

    # 기존 별표 메시지 로드
    starred_messages = load_user_starred_messages(bot_id)

    # 메시지 ID 생성 (channel_id + ts)
    message_id = f"{message.get('channel_id', '')}_{message.get('ts', '')}"
    message['message_id'] = message_id
    message['starred_at'] = time.time()

    # 중복 체크 (이미 별표한 메시지인지)
    if not any(msg.get('message_id') == message_id for msg in starred_messages):
        starred_messages.append(message)

        if save_user_starred_messages(bot_id, starred_messages):
            return jsonify({"success": True, "message": "별표 추가됨"})
        else:
            return jsonify({"success": False, "error": "저장 실패"})
    else:
        return jsonify({"success": True, "message": "이미 별표된 메시지"})

@app.route('/api/starred/<message_id>', methods=['DELETE'])
def remove_starred_message(message_id):
    """별표 메시지 제거"""
    bot_id = session.get('bot_id')
    if not bot_id:
        return jsonify({"success": False, "error": "연결되지 않음"})

    # 기존 별표 메시지 로드
    starred_messages = load_user_starred_messages(bot_id)

    # 메시지 제거
    starred_messages = [msg for msg in starred_messages if msg.get('message_id') != message_id]

    if save_user_starred_messages(bot_id, starred_messages):
        return jsonify({"success": True, "message": "별표 제거됨"})
    else:
        return jsonify({"success": False, "error": "저장 실패"})


if __name__ == '__main__':
    # user_data 디렉토리 생성
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR, exist_ok=True)

    print("=" * 60)
    print("🌐 Slack 알림 모니터링 웹 서버 시작")
    print("=" * 60)
    print("📍 URL: http://localhost:5001")
    print("🔄 브라우저에서 위 주소로 접속하세요")
    print("=" * 60)

    app.run(debug=True, host='0.0.0.0', port=5001, threaded=True, use_reloader=False)
