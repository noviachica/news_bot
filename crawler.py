import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import os
import json
import requests
from bs4 import BeautifulSoup
import base64
from datetime import datetime

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

# 신문사 그룹 및 우선순위 정의
NEWSPAPER_GROUPS = {
    'group1': {
        'newspapers': ['조선일보', '중앙일보', '동아일보'],
        'priority': {'조선일보': 1, '중앙일보': 2, '동아일보': 3}
    },
    'group2': {
        'newspapers': ['경향신문', '한겨레신문', '한국일보'],
        'priority': {'경향신문': 1, '한겨레신문': 2, '한국일보': 3}
    },
    'group3': {
        'newspapers': ['매일경제', '한국경제', '서울경제', '아주경제'],
        'priority': {'매일경제': 1, '한국경제': 2, '서울경제': 3, '아주경제': 4}
    }
}

def get_newspaper_group(newspaper):
    """신문사가 속한 그룹을 반환"""
    for group_name, group_info in NEWSPAPER_GROUPS.items():
        if newspaper in group_info['newspapers']:
            return group_name
    return None

def get_newspaper_priority(newspaper):
    """신문사의 우선순위를 반환"""
    for group_info in NEWSPAPER_GROUPS.values():
        if newspaper in group_info['priority']:
            return group_info['priority'][newspaper]
    return float('inf')  # 우선순위가 없는 경우 가장 낮은 우선순위

def select_articles_by_length(group, threshold=0.2):
    """기사 길이와 신문사 우선순위를 고려하여 기사 선택"""
    # 기사 길이 계산 (본문의 길이)
    group['length'] = group['본문'].str.len()
    max_length = group['length'].max()
    
    # 길이 기준 필터링 (최대 길이의 80% 이상인 기사들)
    length_threshold = max_length * (1 - threshold)
    candidates = group[group['length'] >= length_threshold].copy()
    
    if len(candidates) == 0:
        candidates = group.copy()
    
    # 신문사 우선순위 추가
    candidates['priority'] = candidates['신문사'].apply(get_newspaper_priority)
    
    # 우선순위 기준으로 정렬
    candidates = candidates.sort_values(['priority'])
    
    return candidates.iloc[0] if len(candidates) > 0 else None

def deduplicate_articles(df):
    """기사 중복제거"""
    print("12. 기사 중복제거 시작...")
    
    # 키워드별로 그룹화
    grouped = df.groupby('키워드')
    deduplicated_rows = []
    
    for keyword, group in grouped:
        if len(group) < 3:
            # 3개 미만이면 모두 포함
            deduplicated_rows.extend(group.to_dict('records'))
            continue
            
        # 신문사 그룹별로 기사 선택
        selected_articles = []
        used_groups = set()
        
        # 발행일 기준으로 정렬 (최신순)
        group = group.sort_values('발행일', ascending=False)
        
        # 각 그룹별로 기사 선택
        for group_name, group_info in NEWSPAPER_GROUPS.items():
            if group_name in used_groups:
                continue
                
            # 해당 그룹의 기사들만 필터링
            group_articles = group[group['신문사'].isin(group_info['newspapers'])]
            
            if len(group_articles) > 0:
                # 기사 길이와 우선순위를 고려하여 선택
                selected_article = select_articles_by_length(group_articles)
                if selected_article is not None:
                    selected_articles.append(selected_article)
                    used_groups.add(group_name)
            
            if len(selected_articles) >= 3:
                break
        
        deduplicated_rows.extend(selected_articles)
    
    # DataFrame으로 변환
    deduplicated_df = pd.DataFrame(deduplicated_rows)
    print(f"13. 중복제거 완료. 원본: {len(df)}개, 중복제거 후: {len(deduplicated_df)}개")
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
        # GitHub API 엔드포인트
        url = f"https://api.github.com/repos/{repo_name}/contents/{file_path}"
        print(f"API URL: {url}")
        
        # 기존 파일 정보 가져오기
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        print("헤더 설정 완료")
        
        # 기존 파일의 SHA 가져오기
        print("기존 파일 정보 요청 중...")
        response = requests.get(url, headers=headers)
        print(f"기존 파일 응답 상태: {response.status_code}")
        sha = None
        if response.status_code == 200:
            sha = response.json()['sha']
            print("기존 파일 SHA 획득")
        else:
            print("새 파일 생성")
        
        # 파일 업데이트
        payload = {
            "message": f"Update news data {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": base64.b64encode(json_data.encode()).decode(),
            "sha": sha
        }
        print("업데이트 요청 전송 중...")
        
        response = requests.put(url, headers=headers, data=json.dumps(payload))
        print(f"업데이트 응답 상태: {response.status_code}")
        print(f"응답 내용: {response.text}")
        
        if response.status_code in [200, 201]:
            raw_url = response.json()['content']['download_url']
            print(f"✅ GitHub Repository 업데이트 성공!\n🌐 Raw URL: {raw_url}")
            return raw_url
        else:
            print(f"❌ GitHub Repository 업데이트 실패: {response.status_code}\n{response.text}")
            return None
    except Exception as e:
        print(f"❌ GitHub Repository 업데이트 중 오류 발생: {e}")
        return None

# ✅ STEP 6: GitHub Repository에 업로드
GITHUB_REPO = "noviachica/news_bot"  # GitHub 저장소 이름
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # GitHub Actions에서 제공하는 토큰 사용

if GITHUB_TOKEN:
    update_github_repo(json_content, GITHUB_TOKEN, GITHUB_REPO)
else:
    print("⚠️ GITHUB_TOKEN이 설정되지 않았습니다. GitHub 업데이트를 건너뜁니다.") 
