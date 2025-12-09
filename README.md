# 📈 AI Financial Newsroom

GitHub 리포지토리를 DB처럼 사용하여 데이터를 영구 저장하는 Streamlit 기반 금융 뉴스룸 애플리케이션입니다.

## ✨ 주요 기능

- 📰 RSS 피드에서 금융 뉴스 자동 수집
- 🤖 Google Gemini AI를 활용한 일일 브리핑 자동 생성
- 💾 GitHub 리포지토리를 데이터베이스로 활용 (Streamlit Cloud 배포 시 로컬 파일 시스템 문제 해결)
- 📊 방문자 수 추적
- ⚙️ RSS 피드 및 키워드 관리

## 🚀 시작하기

### 1. 필수 요구사항

- Python 3.8 이상
- GitHub Personal Access Token (repo 권한)
- Google Gemini API Key
- GitHub 리포지토리

### 2. 설치

```bash
# 리포지토리 클론
git clone <your-repo-url>
cd my-newsroom

# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 3. 설정

#### 로컬 개발 환경

`.streamlit/secrets.toml` 파일을 생성하고 다음 내용을 추가하세요:

```toml
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"
REPO_NAME = "your-username/your-repo-name"
GEMINI_API_KEY = "AIzaSy..."
```

#### Streamlit Cloud 배포

1. GitHub에 리포지토리 Push
2. Streamlit Cloud에서 앱 연결
3. Settings -> Secrets에 위의 TOML 내용 추가

### 4. 실행

```bash
streamlit run app.py
```

## 📁 프로젝트 구조

```
my-newsroom/
├── app.py              # 메인 애플리케이션
├── github_db.py        # GitHub API를 통한 데이터 관리
├── requirements.txt    # Python 패키지 의존성
├── data.json           # 초기 데이터 파일 (GitHub에 업로드 필요)
└── README.md           # 프로젝트 문서
```

## 🔑 API 키 발급 방법

### GitHub Personal Access Token

1. GitHub Settings -> Developer settings -> Personal access tokens -> Tokens (classic)
2. "Generate new token" 클릭
3. Scopes에서 `repo` 권한 체크
4. 토큰 복사 및 안전하게 보관

### Google Gemini API Key

1. [Google AI Studio](https://makersuite.google.com/app/apikey) 접속
2. "Create API Key" 클릭
3. API 키 복사 및 안전하게 보관

## 📝 사용 방법

1. **데일리 브리핑 탭**: 오늘 날짜의 AI 생성 브리핑 확인
2. **대시보드 탭**: 
   - RSS 피드 추가/삭제
   - 관심 키워드 관리
   - 뉴스 수집 및 브리핑 생성 실행

## ⚠️ 주의사항

- GitHub API는 시간당 5,000회 요청 제한이 있습니다
- `data.json` 파일은 GitHub 리포지토리에 먼저 업로드되어 있어야 합니다
- Secrets는 절대 코드에 하드코딩하지 마세요

## 🛠️ 기술 스택

- **Streamlit**: 웹 애플리케이션 프레임워크
- **PyGithub**: GitHub API 클라이언트
- **feedparser**: RSS 피드 파싱
- **Google Generative AI**: AI 브리핑 생성
- **pandas**: 데이터 처리

## 📄 라이선스

이 프로젝트는 자유롭게 사용 가능합니다.




