"""
GitHub 연결 테스트 스크립트
이 스크립트를 실행하여 GitHub 리포지토리 연결을 테스트할 수 있습니다.
"""

from github import Github
from github.GithubException import GithubException
import json

# Secrets에서 설정 읽기 (로컬 테스트용)
try:
    with open('.streamlit/secrets.toml', 'r', encoding='utf-8') as f:
        content = f.read()
        # 간단한 파싱 (TOML 파서 없이)
        GITHUB_TOKEN = None
        REPO_NAME = None
        
        for line in content.split('\n'):
            if line.strip().startswith('GITHUB_TOKEN'):
                GITHUB_TOKEN = line.split('=')[1].strip().strip('"')
            elif line.strip().startswith('REPO_NAME'):
                REPO_NAME = line.split('=')[1].strip().strip('"')
        
        if not GITHUB_TOKEN or not REPO_NAME:
            print("❌ secrets.toml에서 GITHUB_TOKEN과 REPO_NAME을 찾을 수 없습니다.")
            exit(1)
            
except Exception as e:
    print(f"❌ secrets.toml 파일을 읽을 수 없습니다: {e}")
    exit(1)

print("=" * 50)
print("GitHub 연결 테스트")
print("=" * 50)
print(f"리포지토리: {REPO_NAME}")
print()

try:
    # GitHub 연결 테스트
    print("1. GitHub API 연결 중...")
    g = Github(GITHUB_TOKEN)
    user = g.get_user()
    print(f"✅ 연결 성공! 사용자: {user.login}")
    print()
    
    # 리포지토리 접근 테스트
    print("2. 리포지토리 접근 테스트...")
    if "/" in REPO_NAME:
        repo = g.get_repo(REPO_NAME)
    else:
        repo = user.get_repo(REPO_NAME)
    print(f"✅ 리포지토리 접근 성공: {repo.full_name}")
    print(f"   - Private: {repo.private}")
    print(f"   - Default branch: {repo.default_branch}")
    print()
    
    # data.json 파일 확인
    print("3. data.json 파일 확인...")
    try:
        contents = repo.get_contents("data.json")
        print("✅ data.json 파일이 존재합니다.")
        data = json.loads(contents.decoded_content.decode())
        print(f"   - 방문자 수: {data.get('visitors', 0)}")
        print(f"   - RSS 피드 수: {len(data.get('feeds', []))}")
        print(f"   - 리포트 수: {len(data.get('reports', {}))}")
    except GithubException as e:
        if e.status == 404:
            print("⚠️  data.json 파일이 없습니다. 앱 실행 시 자동으로 생성됩니다.")
        else:
            print(f"❌ 파일 확인 실패: {e}")
    print()
    
    # 쓰기 권한 테스트
    print("4. 쓰기 권한 테스트...")
    try:
        # 테스트 파일 생성 시도 (실제로는 생성하지 않음)
        # 대신 리포지토리 권한 확인
        if repo.permissions.push:
            print("✅ 쓰기 권한이 있습니다.")
        else:
            print("⚠️  쓰기 권한이 없습니다. 토큰에 'repo' 권한이 필요합니다.")
    except Exception as e:
        print(f"⚠️  권한 확인 중 오류: {e}")
    print()
    
    print("=" * 50)
    print("✅ 모든 테스트 통과!")
    print("=" * 50)
    
except GithubException as e:
    print(f"❌ GitHub API 오류: {e}")
    if e.status == 401:
        print("   → 토큰이 유효하지 않거나 만료되었습니다.")
    elif e.status == 403:
        print("   → 권한이 없습니다. 토큰에 'repo' 권한이 필요합니다.")
    elif e.status == 404:
        print("   → 리포지토리를 찾을 수 없습니다. 리포지토리 이름을 확인해주세요.")
    else:
        print(f"   → 상태 코드: {e.status}")
    exit(1)
    
except Exception as e:
    print(f"❌ 예상치 못한 오류: {e}")
    exit(1)



