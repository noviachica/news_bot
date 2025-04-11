import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import os
import json
import requests
from bs4 import BeautifulSoup
import base64
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re
from konlpy.tag import Okt  # 한국어 텍스트 처리용

print("1. 시작...")

# ✅ STEP 1: Google Sheets에서 데이터 불러오기
def get_google_sheets_data():
    print("2. Google 서비스 계정 키 파일 읽기 시도...")
    
    try:
        # 환경 변수에서 JSON 문자열을 읽어서 파싱
        credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
        if not credentials_json:
            print("환경 변수 내용:")
            print(os.environ)
            raise ValueError("GOOGLE_CREDENTIALS 환경 변수가 설정되지 않았습니다.")
            
        print("3. JSON 데이터 길이:", len(credentials_json))
        print("4. JSON 데이터 시작 부분:", credentials_json[:100])  # 처음 100자만 출력
        
        # JSON 문자열을 파일로 저장하여 디버깅
        with open('temp_credentials.json', 'w') as f:
            f.write(credentials_json)
        print("5. 임시 credentials 파일 저장 완료")
        
        credentials_dict = json.loads(credentials_json)
        
        # 스코프 설정
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]
        
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        gc = gspread.authorize(credentials)
        print("6. Google Sheets 인증 성공")
        
        # 스프레드시트 열기
        spreadsheet = gc.open_by_url('https://docs.google.com/spreadsheets/d/1HLTb59lcJQIZmaPMrJ0--hEsheyERIkCg5aBxSEFDtc/edit#gid=0')
        
        # Result 워크시트 선택
        worksheet = spreadsheet.worksheet("Result")
        print(f"7. 선택된 워크시트: {worksheet.title}")
        
        # 전체 데이터 가져오기
        all_values = worksheet.get_all_values()
        print(f"8. 전체 데이터 행 수: {len(all_values)}")
        
        # 헤더 확인
        headers = all_values[0]
        print("9. 헤더:", headers)
        
        # 데이터프레임 생성
        df = pd.DataFrame(all_values[1:], columns=headers)
        print(f"10. DataFrame 생성 완료. 행 수: {len(df)}")
        
        # 신문사 정보 추출 (URL에서)
        def extract_newspaper(url):
            if 'naver.com' in url:
                # 네이버 뉴스 URL에서 신문사 코드 추출
                newspaper_codes = {
                    '023': '조선일보',
                    '025': '중앙일보',
                    '020': '동아일보',
                    '032': '경향신문',
                    '028': '한겨레신문',
                    '469': '한국일보',
                    '009': '매일경제',
                    '015': '한국경제',
                    '011': '서울경제',
                    '277': '아주경제'
                }
                try:
                    code = url.split('/article/')[1].split('/')[0]
                    return newspaper_codes.get(code, '기타')
                except:
                    return '기타'
            return '기타'
        
        # 신문사 열 추가
        df['신문사'] = df['링크'].apply(extract_newspaper)
        print("11. 신문사 정보 추출 완료")
        
        return df
        
    except Exception as e:
        print(f"❌ Google Sheets 접근 중 오류 발생: {str(e)}")
        print(f"오류 유형: {type(e).__name__}")
        raise

# ✅ STEP 2: 기사 본문 크롤러 정의
def extract_article_text(url):
    try:
        print(f"\n크롤링 시도: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()  # HTTP 에러 체크
        print(f"HTTP 상태 코드: {res.status_code}")
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 다양한 뉴스 사이트에 대한 선택자
        selectors = [
            'div#dic_area',  # Naver 뉴스
            'div.article-body',  # 일반적인 뉴스 사이트
            'article',  # 일반적인 뉴스 사이트
            'div.article-content',  # 일반적인 뉴스 사이트
            'div.article-text',  # 일반적인 뉴스 사이트
            'div#articleBody',  # 비즈니스포스트
            'div#news_body_area',  # 비바100
            'div#article-view-content-div',  # 뉴스프라임
            'div.article_body',  # 딜사이트
            'div#articeBody',  # 네이버 엔터테인먼트
            'div.end_body',  # 네이버 엔터테인먼트 모바일
            'div#newsEndContents',  # 네이버 스포츠
            'div.article_txt',  # 추가 일반
            'div#articleContent',  # 추가 일반
            'div#newsContent',  # 추가 일반
            'div.news_body',  # 추가 일반
            'div#newsViewArea',  # 추가 일반
            'div#content',  # 추가 일반
            'div.article',  # 네이버 엔터테인먼트 추가
            'div.article-content',  # 네이버 엔터테인먼트 추가
            'div.article-body',  # 네이버 엔터테인먼트 추가
        ]
        
        for selector in selectors:
            article = soup.select_one(selector)
            if article:
                # 불필요한 요소 제거
                for tag in article.select('script, style, iframe, .reporter_area, .copyright, .promotion'):
                    tag.decompose()
                
                # 텍스트 정제
                text = article.get_text(strip=True)
                text = ' '.join(text.split())  # 연속된 공백 제거
                
                print(f"성공적으로 본문을 찾았습니다. 선택자: {selector}")
                return text
        
        print("본문을 찾을 수 없습니다. 사용 가능한 선택자:")
        for selector in selectors:
            elements = soup.select(selector)
            print(f"{selector}: {len(elements)}개 발견")
            
        # 마지막 시도: 본문으로 추정되는 가장 긴 텍스트 블록 찾기
        paragraphs = soup.find_all(['p', 'div'])
        if paragraphs:
            longest_text = max(paragraphs, key=lambda p: len(p.get_text(strip=True)))
            text = longest_text.get_text(strip=True)
            if len(text) > 100:  # 최소 100자 이상인 경우만 본문으로 간주
                print("본문으로 추정되는 텍스트를 찾았습니다.")
                return text
            
        return "본문 없음"

    except requests.exceptions.RequestException as e:
        print(f"요청 에러: {e}")
        return f"[크롤링 에러] 요청 실패: {e}"
    except Exception as e:
        print(f"예상치 못한 에러: {e}")
        return f"[크롤링 에러] {e}"

# 신문사 그룹 정의
NEWSPAPER_GROUPS = {
    '보수': ['조선일보', '중앙일보', '동아일보'],
    '진보': ['경향신문', '한겨레신문', '한국일보'],
    '경제': ['매일경제', '한국경제', '서울경제', '아주경제']
}

def get_newspaper_group(newspaper):
    """신문사가 속한 그룹을 반환"""
    for group_name, newspapers in NEWSPAPER_GROUPS.items():
        if newspaper in newspapers:
            return group_name
    return '기타'

def preprocess_text(text):
    """텍스트 전처리"""
    if not isinstance(text, str):
        return ""
        
    # 한글, 숫자, 공백만 남기기
    text = re.sub(r'[^가-힣0-9\s]', ' ', text)
    # 연속된 공백 제거
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def calculate_similarity(text1, text2):
    """두 텍스트 간의 코사인 유사도 계산"""
    if not text1 or not text2:
        return 0.0
        
    # 텍스트 전처리
    text1 = preprocess_text(text1)
    text2 = preprocess_text(text2)
    
    vectorizer = TfidfVectorizer(
        max_features=10000,  # 최대 특성 수 제한
        min_df=2,  # 최소 문서 빈도
        max_df=0.95  # 최대 문서 빈도
    )
    
    try:
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return similarity
    except Exception as e:
        print(f"유사도 계산 중 오류: {e}")
        return 0.0

def find_similar_articles(group, similarity_threshold=0.7):
    """유사한 기사들을 찾아 그룹화"""
    print(f"  - 유사도 분석 시작 (임계값: {similarity_threshold})")
    print(f"  - 분석 대상 기사 수: {len(group)}")
    
    # 텍스트 전처리
    texts = group['본문'].apply(preprocess_text).tolist()
    
    # 유사도 행렬 계산
    vectorizer = TfidfVectorizer(
        max_features=10000,
        min_df=2,
        max_df=0.95
    )
    
    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
        similarity_matrix = cosine_similarity(tfidf_matrix)
        
        # 유사도 분포 분석
        similarities = similarity_matrix[np.triu_indices_from(similarity_matrix, k=1)]
        print(f"  - 평균 유사도: {np.mean(similarities):.3f}")
        print(f"  - 최대 유사도: {np.max(similarities):.3f}")
        print(f"  - 최소 유사도: {np.min(similarities):.3f}")
        
    except Exception as e:
        print(f"  - 유사도 계산 실패: {e}")
        return group
    
    # 유사한 기사 그룹화
    similar_groups = []
    used_indices = set()
    
    for i in range(len(texts)):
        if i in used_indices:
            continue
            
        # 현재 기사와 유사한 기사 찾기
        similar_indices = np.where(similarity_matrix[i] > similarity_threshold)[0]
        similar_indices = [idx for idx in similar_indices if idx not in used_indices]
        
        if similar_indices:
            # 유사한 기사들을 하나의 그룹으로
            group_articles = group.iloc[similar_indices]
            similar_groups.append(group_articles)
            
            # 사용된 인덱스 표시
            used_indices.update(similar_indices)
            print(f"  - 유사 기사 그룹 {len(similar_groups)}: {len(similar_indices)}개 기사")
            print(f"    - 대표 기사: {group.iloc[i]['신문사']} - {group.iloc[i]['제목'][:30]}...")
            print(f"    - 유사도 범위: {np.min(similarity_matrix[i, similar_indices]):.3f} ~ {np.max(similarity_matrix[i, similar_indices]):.3f}")
    
    # 유사하지 않은 기사들도 각각 하나의 그룹으로
    remaining_indices = set(range(len(texts))) - used_indices
    if remaining_indices:
        for idx in remaining_indices:
            similar_groups.append(group.iloc[[idx]])
            print(f"  - 독립 기사 추가: {group.iloc[idx]['신문사']} - {group.iloc[idx]['제목'][:30]}...")
    
    print(f"  - 총 그룹 수: {len(similar_groups)}")
    return similar_groups

def select_articles_from_group(group_articles):
    """그룹에서 기사 선택"""
    selected_articles = []
    used_groups = set()
    
    # 각 신문사 그룹별로 가장 긴 기사 선택
    for group_name in ['보수', '진보', '경제']:
        group_mask = group_articles['신문사'].isin(NEWSPAPER_GROUPS[group_name])
        group_articles_subset = group_articles[group_mask]
        
        if len(group_articles_subset) > 0:
            # 가장 긴 기사 선택
            longest_article = group_articles_subset.loc[group_articles_subset['본문'].str.len().idxmax()]
            selected_articles.append(longest_article)
            used_groups.add(group_name)
            print(f"  - {group_name}그룹에서 기사 선택: {longest_article['신문사']}")
    
    # 선택된 기사가 3개 미만이면 나머지 기사 중에서 길이가 긴 순으로 추가
    if len(selected_articles) < 3:
        remaining_articles = group_articles[~group_articles['신문사'].isin([a['신문사'] for a in selected_articles])]
        remaining_articles = remaining_articles.sort_values('본문', key=lambda x: x.str.len(), ascending=False)
        
        for _, article in remaining_articles.iterrows():
            if len(selected_articles) >= 3:
                break
            selected_articles.append(article)
            print(f"  - 추가 선택: {article['신문사']}")
    
    return selected_articles

def deduplicate_articles(df):
    """기사 중복제거"""
    print("12. 기사 중복제거 시작...")
    
    # 키워드별로 그룹화
    grouped = df.groupby('키워드')
    deduplicated_rows = []
    
    for keyword, group in grouped:
        print(f"\n키워드: {keyword}")
        print(f"  - 기사 수: {len(group)}")
        
        if len(group) < 3:
            print("  - 3개 미만이므로 모두 포함")
            deduplicated_rows.extend(group.to_dict('records'))
            continue
            
        # 유사도 기반 그룹화
        similar_groups = find_similar_articles(group)
        
        # 각 유사 그룹에서 기사 선택
        for group_idx, group_articles in enumerate(similar_groups, 1):
            print(f"\n  유사 그룹 {group_idx} 처리 중...")
            selected_articles = select_articles_from_group(group_articles)
            deduplicated_rows.extend([article.to_dict() for article in selected_articles])
            print(f"  - 선택된 기사 수: {len(selected_articles)}")
    
    # DataFrame으로 변환
    deduplicated_df = pd.DataFrame(deduplicated_rows)
    print(f"\n13. 중복제거 완료. 원본: {len(df)}개, 중복제거 후: {len(deduplicated_df)}개")
    return deduplicated_df

# ✅ STEP 3: 기사 본문 열 추가
print("\n10. 기사 본문 크롤링 시작...")
try:
    df = get_google_sheets_data()  # DataFrame 가져오기
    df['본문'] = df['링크'].apply(extract_article_text)
    print("11. 기사 본문 크롤링 완료")
    
    # 중복제거
    df = deduplicate_articles(df)
    
except Exception as e:
    print(f"❌ 크롤링 중 오류 발생: {e}")
    exit(1)

# ✅ STEP 4: JSON 변환
print("14. JSON 변환 시작...")
try:
    json_content = df.to_json(orient='records', force_ascii=False, indent=2)
    print("15. JSON 변환 완료")
except Exception as e:
    print(f"❌ JSON 변환 중 오류 발생: {e}")
    exit(1)

# ✅ STEP 5: GitHub Repository 업데이트 함수
def update_github_repo(json_data, github_token, repo_name, file_path='news_batch.json'):
    try:
        print("16. GitHub Repository 업데이트 시도...")
        print(f"  - 저장소: {repo_name}")
        print(f"  - 파일 경로: {file_path}")
        print(f"  - JSON 데이터 크기: {len(json_data)} bytes")
        
        # GitHub API 엔드포인트
        url = f"https://api.github.com/repos/{repo_name}/contents/{file_path}"
        print(f"  - API URL: {url}")
        
        # 기존 파일 정보 가져오기
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # 기존 파일의 SHA 가져오기
        print("  - 기존 파일 정보 요청 중...")
        response = requests.get(url, headers=headers)
        print(f"  - 기존 파일 응답 상태: {response.status_code}")
        
        sha = None
        if response.status_code == 200:
            sha = response.json()['sha']
            print("  - 기존 파일 SHA 획득")
        else:
            print("  - 새 파일 생성")
        
        # 파일 업데이트
        payload = {
            "message": f"Update news data {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": base64.b64encode(json_data.encode()).decode(),
            "sha": sha
        }
        print("  - 업데이트 요청 전송 중...")
        
        response = requests.put(url, headers=headers, data=json.dumps(payload))
        print(f"  - 업데이트 응답 상태: {response.status_code}")
        print(f"  - 응답 내용: {response.text}")
        
        if response.status_code in [200, 201]:
            raw_url = response.json()['content']['download_url']
            print(f"✅ GitHub Repository 업데이트 성공!")
            print(f"🌐 Raw URL: {raw_url}")
            return raw_url
        else:
            print(f"❌ GitHub Repository 업데이트 실패: {response.status_code}")
            print(f"  - 에러 메시지: {response.text}")
            return None
    except Exception as e:
        print(f"❌ GitHub Repository 업데이트 중 오류 발생: {e}")
        return None

# ✅ STEP 6: GitHub Repository에 업로드
GITHUB_REPO = "noviachica/news_bot"  # GitHub 저장소 이름
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # GitHub Actions에서 제공하는 토큰 사용

# 환경 변수 확인
print("\n환경 변수 확인:")
print(f"  - GITHUB_TOKEN 존재 여부: {'있음' if GITHUB_TOKEN else '없음'}")
if GITHUB_TOKEN:
    print(f"  - GITHUB_TOKEN 길이: {len(GITHUB_TOKEN)}")
    print(f"  - GITHUB_TOKEN 시작 부분: {GITHUB_TOKEN[:10]}...")
else:
    print("  - GITHUB_TOKEN이 설정되지 않았습니다.")
    print("  - GitHub Actions의 secrets에 GITHUB_TOKEN이 설정되어 있는지 확인해주세요.")
    print("  - secrets 설정 방법: https://docs.github.com/en/actions/security-guides/encrypted-secrets")

if GITHUB_TOKEN:
    print("\nGitHub 업데이트 시작...")
    print(f"  - JSON 데이터 크기: {len(json_content)}")
    raw_url = update_github_repo(json_content, GITHUB_TOKEN, GITHUB_REPO)
    if raw_url:
        print(f"✅ GitHub 업데이트 완료: {raw_url}")
    else:
        print("❌ GitHub 업데이트 실패")
else:
    print("⚠️ GITHUB_TOKEN이 설정되지 않았습니다. GitHub 업데이트를 건너뜁니다.") 
