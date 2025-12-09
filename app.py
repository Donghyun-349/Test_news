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
    USE_LOCAL = st.secrets.get("USE_LOCAL", False)  # 로컬 개발 모드 (기본값: False)
    GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
    REPO_NAME = st.secrets.get("REPO_NAME", "")
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError as e:
    st.error(f"Secrets 설정이 필요합니다: {e}. (.streamlit/secrets.toml 확인)")
    st.stop()
except Exception as e:
    st.error(f"Secrets 로드 중 오류 발생: {e}")
    st.stop()

# 로컬 모드 체크
if USE_LOCAL:
    st.warning("⚠️ 로컬 개발 모드: GitHub 연결 없이 로컬 파일을 사용합니다.")
    db = GithubDB("", "", use_local=True)
else:
    if not GITHUB_TOKEN or not REPO_NAME:
        st.error("GitHub 토큰과 리포지토리 이름이 필요합니다.")
        st.info("💡 로컬 개발 모드를 사용하려면 secrets.toml에 USE_LOCAL = true를 추가하세요.")
        st.stop()
    
    # DB 및 AI 초기화
    try:
        db = GithubDB(GITHUB_TOKEN, REPO_NAME)
    except Exception as e:
        st.error(f"GitHub 연결 실패: {e}")
        st.info("💡 로컬 개발 모드를 사용하려면 secrets.toml에 USE_LOCAL = true를 추가하세요.")
        st.stop()

# AI 초기화
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error(f"Gemini API 초기화 실패: {e}")
    st.stop()

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
        model = genai.GenerativeModel('gemini-2.5-flash')
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
    "reports": {},
    "collected_news": {}  # 날짜별로 수집된 뉴스 저장
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

tab1, tab2, tab3 = st.tabs(["📅 데일리 브리핑", "📰 수집된 뉴스", "⚙️ 대시보드 & 설정"])

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

# [탭 2] 수집된 뉴스 보기 (간단한 목록)
with tab2:
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 오늘 날짜의 수집된 뉴스 표시
    collected_news = data.get('collected_news', {})
    date_keys = [k for k in collected_news.keys() if not k.endswith('_collected_at')]
    
    if today_str in date_keys:
        articles = collected_news[today_str]
        st.success(f"✅ 오늘 수집된 뉴스 {len(articles)}개")
        
        # 제목과 링크만 간단하게 표시
        for idx, art in enumerate(articles, 1):
            st.write(f"{idx}. [{art['title']}]({art['link']})")
    else:
        st.info("오늘 수집된 뉴스가 없습니다. 대시보드에서 뉴스를 수집해주세요.")

# [탭 3] 대시보드: 설정 및 수동 실행
with tab3:
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
        
        st.write("현재 등록된 키워드:")
        for kw in data['keywords']:
            k1, k2 = st.columns([8, 2])
            k1.write(f"• {kw}")
            if k2.button("삭제", key=f"del_kw_{kw}"):
                # 최신 데이터 다시 읽기
                current_data = db.read_data()
                if current_data and kw in current_data['keywords']:
                    current_data['keywords'].remove(kw)
                    if db.write_data(current_data, "Remove keyword"):
                        st.success("키워드가 삭제되었습니다!")
                        st.rerun()
                    else:
                        st.error("키워드 삭제 실패")
        
        st.divider()
        st.subheader("📥 뉴스 수집")
        if st.button("뉴스 수집 (지금 실행)", type="primary"):
            with st.spinner("RSS 피드에서 뉴스를 수집 중입니다..."):
                # 뉴스 수집
                articles = fetch_news(data['feeds'], data['keywords'])
                
                if not articles:
                    st.warning("수집된 뉴스가 없습니다. RSS 피드나 키워드를 확인해주세요.")
                else:
                    # 수집된 뉴스 저장
                    today = datetime.now().strftime("%Y-%m-%d")
                    current_data = db.read_data()
                    if current_data:
                        if 'collected_news' not in current_data:
                            current_data['collected_news'] = {}
                        current_data['collected_news'][today] = articles
                        current_data['collected_news'][f"{today}_collected_at"] = str(datetime.now())
                        
                        # GitHub에 저장
                        if db.write_data(current_data, f"Collect news for {today}"):
                            st.success(f"✅ {len(articles)}개의 뉴스가 수집되었습니다!")
                            st.info("'수집된 뉴스' 탭에서 확인할 수 있습니다.")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("뉴스 저장 실패")
                    else:
                        st.error("데이터 로드 실패")
        
        st.divider()
        st.subheader("🤖 브리핑 생성")
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 오늘 수집된 뉴스가 있는지 확인
        collected_news = data.get('collected_news', {})
        date_keys = [k for k in collected_news.keys() if not k.endswith('_collected_at')]
        
        if today in date_keys:
            articles = collected_news[today]
            st.info(f"📰 오늘 수집된 뉴스: {len(articles)}개")
            
            if st.button("브리핑 생성 (지금 실행)", type="primary"):
                with st.spinner("Gemini AI가 브리핑을 생성 중입니다..."):
                    # AI 분석
                    report_content = analyze_with_gemini(articles)
                    
                    # 결과 저장 (최신 데이터 다시 읽기)
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
                            st.info("'데일리 브리핑' 탭에서 확인할 수 있습니다.")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("브리핑 저장 실패")
                    else:
                        st.error("데이터 로드 실패")
        else:
            st.warning("⚠️ 먼저 뉴스를 수집해주세요.")
            st.info("위의 '뉴스 수집' 버튼을 먼저 실행하세요.")
        
        st.divider()
        st.subheader("📰 수집된 뉴스 관리")
        
        # 날짜 선택
        collected_news = data.get('collected_news', {})
        date_keys = [k for k in collected_news.keys() if not k.endswith('_collected_at')]
        date_keys = sorted(date_keys, reverse=True)
        
        if date_keys:
            selected_date = st.selectbox("날짜 선택", date_keys, index=0)
            
            if selected_date in collected_news:
                articles = collected_news[selected_date]
                collected_at = collected_news.get(f"{selected_date}_collected_at", "알 수 없음")
                st.info(f"📰 {selected_date}에 수집된 뉴스 {len(articles)}개")
                st.caption(f"수집 시간: {collected_at}")
                
                # 검색 기능
                search_term = st.text_input("🔍 뉴스 검색", key="news_search")
                
                # 필터링된 뉴스
                filtered_articles = articles
                if search_term:
                    filtered_articles = [
                        art for art in articles 
                        if search_term.lower() in art['title'].lower() or 
                           search_term.lower() in art.get('summary', '').lower()
                    ]
                    st.info(f"검색 결과: {len(filtered_articles)}개")
                
                # 상세 정보 표시
                for idx, art in enumerate(filtered_articles, 1):
                    with st.expander(f"{idx}. {art['title']}", expanded=False):
                        st.write(f"**링크:** [{art['link']}]({art['link']})")
                        st.write(f"**발행일:** {art['published']}")
                        if art.get('summary'):
                            st.write(f"**요약:** {art['summary']}")
        else:
            st.info("아직 수집된 뉴스가 없습니다. 위의 '뉴스 수집' 버튼을 실행해주세요.")


