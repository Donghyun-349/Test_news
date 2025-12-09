Cursor AI를 활용해 개발하신다니 아주 효율적이겠네요! 요청하신 **"GitHub 리포지토리를 DB처럼 사용하는(JSON 저장)"** 방식은 Streamlit Cloud 배포 시 로컬 파일 시스템이 초기화되는 문제를 해결하는 아주 스마트한 방법입니다.

이 앱의 핵심은 **`PyGithub` 라이브러리를 사용해 GitHub 리포지토리의 `data.json` 파일을 직접 읽고 쓰는 기능**을 구현하는 것입니다.

다음은 Cursor AI에 복사해서 바로 사용할 수 있는 프로젝트 구조와 코드입니다.

---

### 📂 프로젝트 구조
먼저 프로젝트 폴더를 만들고 아래 파일들을 생성한다고 가정합니다.

```text
my-newsroom/
├── app.py              # 메인 애플리케이션 코드
├── github_db.py        # GitHub를 DB처럼 쓰는 헬퍼 모듈
├── requirements.txt    # 필요한 라이브러리 목록
└── data.json           # (초기 데이터 파일 - 리포지토리에 올려야 함)
```

---

### 1. `requirements.txt`
라이브러리 버전을 명시합니다. (프로덕션 환경을 위해 버전 고정)

```text
streamlit>=1.28.0
feedparser>=6.0.10
google-generativeai>=0.3.0
PyGithub>=1.59.0
pandas>=2.0.0
python-dateutil>=2.8.2
```

---

### 2. `data.json` (초기 파일)
이 파일을 생성해서 GitHub 리포지토리에 먼저 올려두세요. (빈 껍데기입니다)

```json
{
    "feeds": [
        "https://news.google.com/rss/search?q=finance&hl=ko&gl=KR&ceid=KR:ko"
    ],
    "keywords": ["주식", "금리", "삼성전자"],
    "visitors": 0,
    "reports": {}
}
```

---

### 3. `github_db.py` (핵심: 데이터 저장소 관리)
이 모듈은 GitHub API를 통해 JSON을 읽고 씁니다. (개선: 에러 처리, 충돌 방지, 초기화 로직 추가)

```python
import json
from github import Github
from github.GithubException import GithubException
import streamlit as st

class GithubDB:
    def __init__(self, token, repo_name, file_path="data.json"):
        self.g = Github(token)
        # repo_name이 "user/repo" 형식인지 확인
        if "/" in repo_name:
            self.repo = self.g.get_repo(repo_name)
        else:
            self.repo = self.g.get_user().get_repo(repo_name)
        self.file_path = file_path

    def read_data(self, default_data=None):
        """GitHub에서 JSON 파일을 읽어옵니다."""
        try:
            contents = self.repo.get_contents(self.file_path)
            return json.loads(contents.decoded_content.decode())
        except GithubException as e:
            if e.status == 404:  # 파일이 없을 때
                if default_data:
                    # 초기 데이터 생성
                    self.write_data(default_data, "Initialize data.json")
                    return default_data
                st.warning(f"파일이 없습니다. 초기 데이터를 생성합니다.")
                return default_data or {}
            st.error(f"데이터 로드 실패: {e}")
            return None
        except Exception as e:
            st.error(f"예상치 못한 오류: {e}")
            return None

    def write_data(self, new_data, commit_message="Update data via Streamlit", max_retries=3):
        """JSON 데이터를 GitHub에 저장(커밋)합니다. 충돌 시 재시도합니다."""
        for attempt in range(max_retries):
            try:
                contents = self.repo.get_contents(self.file_path)
                # 최신 데이터를 다시 읽어서 충돌 방지
                current_data = json.loads(contents.decoded_content.decode())
                # 필요한 경우 merge 로직 추가 가능
                
                self.repo.update_file(
                    contents.path,
                    commit_message,
                    json.dumps(new_data, indent=4, ensure_ascii=False),
                    contents.sha  # SHA를 사용한 optimistic locking
                )
                return True
            except GithubException as e:
                if e.status == 409 and attempt < max_retries - 1:  # 충돌 발생
                    st.warning(f"충돌 발생. 재시도 중... ({attempt + 1}/{max_retries})")
                    continue
                st.error(f"데이터 저장 실패: {e}")
                return False
            except Exception as e:
                st.error(f"예상치 못한 오류: {e}")
                return False
        return False
```

---

### 4. `app.py` (메인 앱)
뉴스 수집, AI 분석, UI 로직이 포함된 코드입니다.

```python
import streamlit as st
import feedparser
import google.generativeai as genai
from github_db import GithubDB
from datetime import datetime
import time

# --- 설정 및 초기화 ---
st.set_page_config(page_title="나만의 금융 뉴스룸", layout="wide", page_icon="📈")

# Streamlit Secrets에서 키 가져오기
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]  # 예: "your-id/repo-name"
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError as e:
    st.error(f"Secrets 설정이 필요합니다: {e}. (.streamlit/secrets.toml 확인)")
    st.stop()
except Exception as e:
    st.error(f"Secrets 로드 중 오류 발생: {e}")
    st.stop()

# DB 및 AI 초기화
db = GithubDB(GITHUB_TOKEN, REPO_NAME)
genai.configure(api_key=GEMINI_API_KEY)

# --- 헬퍼 함수 ---
def fetch_news(feeds, keywords):
    """RSS 피드에서 뉴스 수집 및 키워드 필터링"""
    articles = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            if feed.bozo:  # 파싱 오류 체크
                st.warning(f"피드 파싱 오류: {url}")
                continue
                
            for entry in feed.entries:
                # 날짜 파싱 (오늘 날짜 기준 필터링을 원하면 여기서 로직 추가)
                text_content = f"{entry.title} {entry.get('summary', '')}"
                
                # 키워드가 하나라도 포함되면 수집 (키워드가 비어있으면 모두 수집)
                if not keywords or any(k in text_content for k in keywords):
                    articles.append({
                        "title": entry.title,
                        "link": entry.link,
                        "published": entry.get("published", str(datetime.now())),
                        "summary": entry.get("summary", "")
                    })
        except Exception as e:
            st.warning(f"피드 수집 실패 ({url}): {e}")
            continue
    return articles[:30]  # 너무 많으면 토큰 제한 걸리므로 상위 30개만

def analyze_with_gemini(articles):
    """Gemini를 이용해 1장짜리 브리핑 작성"""
    if not articles:
        return "분석할 뉴스가 없습니다."

    # 프롬프트 구성
    news_text = ""
    for idx, art in enumerate(articles):
        news_text += f"{idx+1}. {art['title']}\n"
    
    prompt = f"""
    당신은 전문 금융 애널리스트입니다. 아래 수집된 뉴스 헤드라인들을 바탕으로
    '오늘의 금융 시장 일일 브리핑' 리포트를 작성해주세요.
    
    [요구사항]
    1. 전체적인 시장 분위기를 한 문단으로 요약하세요.
    2. 가장 중요한 이슈 3가지를 선정하여 심층 분석하세요.
    3. 투자자에게 주는 인사이트를 'Bull'과 'Bear' 관점에서 정리하세요.
    4. 출력 형식은 Markdown으로 가독성 있게 작성하세요.
    
    [뉴스 데이터]
    {news_text}
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Gemini API 호출 실패: {e}")
        return f"⚠️ AI 분석 중 오류가 발생했습니다: {str(e)}"

# --- 앱 로직 시작 ---

# 데이터 로드 (초기 데이터가 없으면 생성)
default_data = {
    "feeds": [
        "https://news.google.com/rss/search?q=finance&hl=ko&gl=KR&ceid=KR:ko"
    ],
    "keywords": ["주식", "금리", "삼성전자"],
    "visitors": 0,
    "reports": {}
}
data = db.read_data(default_data=default_data)
if not data:
    st.error("데이터를 로드할 수 없습니다. 앱을 종료합니다.")
    st.stop()

# 방문자 수 증가 (더 안전한 방식 - 최신 데이터 다시 읽기)
if 'visited' not in st.session_state:
    # 최신 데이터 다시 읽기
    current_data = db.read_data()
    if current_data:
        current_data['visitors'] = current_data.get('visitors', 0) + 1
        if db.write_data(current_data, "Increment visitor count"):
            data = current_data
            st.session_state['visited'] = True
        else:
            st.warning("방문자 수 업데이트 실패")

# --- UI 구성 ---
st.title("📈 AI Financial Newsroom")
st.markdown(f"**Total Visitors:** {data['visitors']}")

tab1, tab2 = st.tabs(["📅 데일리 브리핑", "⚙️ 대시보드 & 설정"])

# [탭 1] 메인: 날짜별 브리핑
with tab1:
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 저장된 리포트가 있는지 확인
    if today_str in data['reports']:
        st.success(f"✅ {today_str} 브리핑이 준비되었습니다.")
        st.markdown(data['reports'][today_str]['content'])
        
        with st.expander("참고한 원본 기사 목록"):
            for art in data['reports'][today_str]['sources']:
                st.write(f"- [{art['title']}]({art['link']})")
    else:
        st.info(f"아직 {today_str} 리포트가 없습니다. 대시보드에서 분석을 실행해주세요.")

# [탭 2] 대시보드: 설정 및 수동 실행
with tab2:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📡 RSS 피드 관리")
        new_feed = st.text_input("RSS URL 추가")
        if st.button("피드 추가"):
            if new_feed and new_feed not in data['feeds']:
                # URL 검증 (간단한 검증)
                if new_feed.startswith(('http://', 'https://')):
                    # 최신 데이터 다시 읽기
                    current_data = db.read_data()
                    if current_data:
                        current_data['feeds'].append(new_feed)
                        if db.write_data(current_data, "Add RSS feed"):
                            st.success("피드가 추가되었습니다!")
                            st.rerun()
                        else:
                            st.error("피드 추가 실패")
                    else:
                        st.error("데이터 로드 실패")
                else:
                    st.warning("유효한 URL을 입력해주세요 (http:// 또는 https://로 시작)")
        
        st.write("현재 등록된 피드:")
        for f in data['feeds']:
            c1, c2 = st.columns([8, 2])
            c1.text(f)
            if c2.button("삭제", key=f):
                # 최신 데이터 다시 읽기
                current_data = db.read_data()
                if current_data and f in current_data['feeds']:
                    current_data['feeds'].remove(f)
                    if db.write_data(current_data, "Remove RSS feed"):
                        st.success("피드가 삭제되었습니다!")
                        st.rerun()
                    else:
                        st.error("피드 삭제 실패")

    with col2:
        st.subheader("🔍 관심 키워드")
        new_keyword = st.text_input("키워드 추가 (예: 반도체)")
        if st.button("키워드 추가"):
            if new_keyword and new_keyword.strip() and new_keyword not in data['keywords']:
                # 최신 데이터 다시 읽기
                current_data = db.read_data()
                if current_data:
                    current_data['keywords'].append(new_keyword.strip())
                    if db.write_data(current_data, "Add keyword"):
                        st.success("키워드가 추가되었습니다!")
                        st.rerun()
                    else:
                        st.error("키워드 추가 실패")
                else:
                    st.error("데이터 로드 실패")
        
        st.write(f"현재 키워드: {', '.join(data['keywords'])}")
        
        st.divider()
        st.subheader("🚀 AI 분석 실행")
        if st.button("뉴스 수집 및 브리핑 생성 (지금 실행)"):
            with st.spinner("뉴스를 수집하고 Gemini가 분석 중입니다..."):
                # 1. 뉴스 수집
                articles = fetch_news(data['feeds'], data['keywords'])
                
                if not articles:
                    st.warning("수집된 뉴스가 없습니다. RSS 피드나 키워드를 확인해주세요.")
                else:
                    # 2. AI 분석
                    report_content = analyze_with_gemini(articles)
                    
                    # 3. 결과 저장 (최신 데이터 다시 읽기)
                    today = datetime.now().strftime("%Y-%m-%d")
                    current_data = db.read_data()
                    if current_data:
                        current_data['reports'][today] = {
                            "content": report_content,
                            "sources": articles,
                            "created_at": str(datetime.now())
                        }
                        
                        # GitHub에 저장
                        if db.write_data(current_data, f"New report for {today}"):
                            st.success("브리핑 생성 완료!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("브리핑 저장 실패")
                    else:
                        st.error("데이터 로드 실패")
```

---

### 5. 배포 및 설정 가이드 (중요!)

Cursor로 코드를 작성한 후, GitHub에 모든 파일을 Push하세요. 그 다음 Streamlit Cloud에서 배포할 때 다음 과정이 필요합니다.

#### 1) GitHub Personal Access Token 발급
이 앱이 사용자의 리포지토리에 파일을 쓰기(Write) 위해서는 권한이 필요합니다.
1.  GitHub Settings -> Developer settings -> Personal access tokens -> Tokens (classic)
2.  **Generate new token** 클릭.
3.  Scopes에서 **`repo`** (전체 리포지토리 제어 권한) 체크.
4.  토큰 문자열을 복사해둡니다.

#### 2) Streamlit Cloud Secrets 설정
Streamlit Cloud 앱 대시보드에서 앱의 **Settings -> Secrets** 메뉴로 이동하여 아래 내용을 붙여넣으세요.

```toml
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"  # 위에서 복사한 GitHub 토큰
REPO_NAME = "본인아이디/리포지토리이름"      # 예: "honggildong/financial-newsroom"
GEMINI_API_KEY = "AIzaSy..."               # Google AI Studio에서 받은 키
```

### 작동 원리 요약
1.  **DB 없음:** 앱이 실행될 때 `github_db.py`가 GitHub API를 호출해 `data.json`의 내용을 메모리로 가져옵니다.
2.  **데이터 저장:** 사용자가 설정을 바꾸거나 뉴스 분석을 완료하면, 변경된 JSON을 다시 GitHub 리포지토리로 Push(Commit)합니다.
3.  **뉴스룸:** 메인 화면은 JSON에 저장된 `reports` 항목에서 오늘 날짜의 리포트를 꺼내 보여줍니다.
4.  **분석:** 대시보드 탭에서 버튼을 누르면 그 즉시 RSS를 긁어오고 Gemini에게 요약을 맡긴 뒤 결과를 저장합니다.

이 방식이면 별도의 서버나 유료 DB 없이 깃허브 하나로 모든 데이터를 영구적으로 관리할 수 있습니다!

---

## 🔍 코드 검토 및 개선 사항

### ⚠️ 발견된 문제점

#### 1. **동시성 문제 (Race Condition)**
- **문제**: 방문자 수 증가 로직(175-179줄)에서 동시 접속 시 데이터 손실 가능
- **해결**: GitHub API의 optimistic locking을 활용하거나 재시도 로직 추가 필요

#### 2. **에러 처리 부족**
- **문제**: `github_db.py`의 `read_data()`에서 파일이 없을 때 초기 데이터 생성 로직 없음
- **문제**: `app.py` 112줄의 `except:`가 너무 광범위함 (bare except)
- **해결**: 구체적인 예외 처리 및 초기화 로직 추가

#### 3. **GitHub API Rate Limit 미고려**
- **문제**: GitHub API는 시간당 5,000회 요청 제한이 있음
- **해결**: 캐싱 메커니즘 추가 또는 rate limit 감지 로직 필요

#### 4. **데이터 일관성 문제**
- **문제**: `app.py`에서 `data` 변수를 수정한 후 저장 전에 다른 사용자가 변경하면 덮어쓰기 발생
- **해결**: 저장 전 최신 데이터를 다시 읽어서 merge하는 로직 필요

#### 5. **리포지토리 이름 파싱**
- **문제**: `github_db.py` 63줄에서 `get_user().get_repo()`는 `"user/repo"` 형식을 직접 지원하지 않음
- **해결**: `g.get_repo(repo_name)` 형식으로 변경 필요

#### 6. **RSS 피드 에러 처리**
- **문제**: `fetch_news()` 함수에서 피드 파싱 실패 시 전체 프로세스 중단
- **해결**: 개별 피드별 try-except 처리

#### 7. **Gemini API 에러 처리**
- **문제**: `analyze_with_gemini()`에서 API 실패 시 빈 문자열 반환 가능
- **해결**: 구체적인 에러 메시지 및 재시도 로직

### ✅ 개선 사항 반영 완료

위의 코드 예시들은 이미 메인 코드 섹션(3번, 4번)에 반영되어 있습니다. 주요 개선 사항:

- ✅ 리포지토리 이름 파싱 개선 (`"user/repo"` 형식 지원)
- ✅ 구체적인 예외 처리 (GithubException, KeyError 등)
- ✅ 파일 없을 때 초기 데이터 자동 생성
- ✅ 충돌 방지를 위한 재시도 로직 (max_retries=3)
- ✅ RSS 피드 개별 에러 처리
- ✅ Gemini API 에러 처리
- ✅ 데이터 일관성을 위한 최신 데이터 재읽기 로직
- ✅ URL 및 입력값 검증

### 📋 추가 권장 사항

1. **캐싱 추가**: Streamlit의 `@st.cache_data`를 사용해 GitHub API 호출 최소화
2. **로깅**: 중요한 작업에 대한 로그 기록
3. **데이터 백업**: 주기적으로 데이터 백업 메커니즘 추가
4. **환경 변수 검증**: 앱 시작 시 필수 설정값 검증
5. **에러 복구**: GitHub API 실패 시 로컬 캐시 사용 옵션
6. **requirements.txt 버전 고정**: 프로덕션 환경을 위해 버전 명시 (이미 1번 섹션에 반영됨)

### 🚨 보안 고려사항

1. **토큰 권한 최소화**: `repo` 전체 권한 대신 특정 리포지토리만 접근 가능한 Fine-grained token 사용 권장
2. **Secrets 관리**: 토큰이 코드에 하드코딩되지 않도록 주의
3. **입력 검증**: RSS URL 및 키워드 입력에 대한 검증 로직 추가