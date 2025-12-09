import json
import os
from github import Github
from github.GithubException import GithubException
import streamlit as st

class GithubDB:
    def __init__(self, token, repo_name, file_path="data.json", use_local=False):
        self.use_local = use_local
        self.file_path = file_path
        self.local_file_path = "local_data.json" if use_local else file_path
        
        if use_local:
            # 로컬 모드: 파일 시스템 사용
            st.info("🔧 로컬 개발 모드: 로컬 파일 시스템을 사용합니다.")
            return
        
        # GitHub 모드
        try:
            self.g = Github(token)
            # repo_name이 "user/repo" 형식인지 확인
            if "/" in repo_name:
                self.repo = self.g.get_repo(repo_name)
            else:
                self.repo = self.g.get_user().get_repo(repo_name)
        except GithubException as e:
            error_msg = f"GitHub 리포지토리 연결 실패: {e}"
            st.error(f"❌ {error_msg}")
            st.error(f"리포지토리 이름: {repo_name}")
            if e.status == 401:
                st.error("→ 토큰이 유효하지 않거나 만료되었습니다.")
            elif e.status == 403:
                st.error("→ 토큰에 'repo' 권한이 필요합니다.")
            elif e.status == 404:
                st.error("→ 리포지토리를 찾을 수 없습니다. 이름을 확인해주세요.")
            st.warning("💡 로컬 개발 모드를 사용하려면 secrets.toml에 USE_LOCAL = true를 추가하세요.")
            raise
        except Exception as e:
            st.error(f"❌ GitHub 초기화 오류: {e}")
            import traceback
            st.code(traceback.format_exc())
            raise

    def read_data(self, default_data=None):
        """GitHub에서 JSON 파일을 읽어옵니다. (로컬 모드면 로컬 파일 사용)"""
        # 로컬 모드
        if self.use_local:
            try:
                if os.path.exists(self.local_file_path):
                    with open(self.local_file_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                else:
                    # 파일이 없으면 기본 데이터 생성
                    if default_data:
                        self.write_data(default_data, "Initialize local data.json")
                        return default_data
                    return {}
            except Exception as e:
                st.error(f"로컬 파일 읽기 실패: {e}")
                return default_data or {}
        
        # GitHub 모드
        try:
            contents = self.repo.get_contents(self.file_path)
            return json.loads(contents.decoded_content.decode())
        except GithubException as e:
            if e.status == 404:  # 파일이 없을 때
                st.info(f"📝 data.json 파일이 없습니다. 초기 데이터를 생성합니다...")
                if default_data:
                    # 초기 데이터 생성 시도
                    if self.write_data(default_data, "Initialize data.json"):
                        st.success("✅ 초기 데이터 파일이 생성되었습니다!")
                        return default_data
                    else:
                        st.error("❌ 초기 데이터 파일 생성에 실패했습니다.")
                        return default_data or {}
                return default_data or {}
            elif e.status == 401:
                st.error(f"❌ 인증 실패: GitHub 토큰이 유효하지 않습니다.")
                st.error("토큰을 확인하고 다시 시도해주세요.")
            elif e.status == 403:
                st.error(f"❌ 권한 없음: 리포지토리에 접근할 권한이 없습니다.")
                st.error("토큰에 'repo' 권한이 있는지 확인해주세요.")
            elif e.status == 404 and "Not Found" in str(e):
                st.error(f"❌ 리포지토리를 찾을 수 없습니다: {self.repo.full_name}")
                st.error("리포지토리 이름과 토큰 권한을 확인해주세요.")
            else:
                st.error(f"❌ 데이터 로드 실패: {e}")
                st.error(f"상태 코드: {e.status}")
            return None
        except Exception as e:
            st.error(f"❌ 예상치 못한 오류: {e}")
            import traceback
            st.code(traceback.format_exc())
            return None

    def write_data(self, new_data, commit_message="Update data via Streamlit", max_retries=3):
        """JSON 데이터를 저장합니다. (로컬 모드면 로컬 파일, GitHub 모드면 커밋)"""
        # 로컬 모드
        if self.use_local:
            try:
                with open(self.local_file_path, 'w', encoding='utf-8') as f:
                    json.dump(new_data, f, indent=4, ensure_ascii=False)
                return True
            except Exception as e:
                st.error(f"로컬 파일 저장 실패: {e}")
                return False
        
        # GitHub 모드
        for attempt in range(max_retries):
            try:
                # 파일이 존재하는지 확인
                try:
                    contents = self.repo.get_contents(self.file_path)
                    # 파일이 존재하면 업데이트
                    self.repo.update_file(
                        contents.path,
                        commit_message,
                        json.dumps(new_data, indent=4, ensure_ascii=False),
                        contents.sha  # SHA를 사용한 optimistic locking
                    )
                    return True
                except GithubException as e:
                    if e.status == 404:  # 파일이 없으면 생성
                        self.repo.create_file(
                            self.file_path,
                            commit_message,
                            json.dumps(new_data, indent=4, ensure_ascii=False)
                        )
                        return True
                    else:
                        raise  # 다른 오류는 다시 발생시킴
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


