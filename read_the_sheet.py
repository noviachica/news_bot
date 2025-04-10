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
try:
    print("2. Google 서비스 계정 키 파일 읽기 시도...")
    with open('google_credentials.json', 'r') as f:
        creds_json = json.load(f)
    print("3. Google 서비스 계정 키 파일 읽기 성공")

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]

    print("4. Google Sheets 인증 시도...")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    print("5. Google Sheets 인증 성공")

    print("6. 스프레드시트 접근 시도...")
    sheet_url = 'https://docs.google.com/spreadsheets/d/1HLTb59lcJQIZmaPMrJ0--hEsheyERIkCg5aBxSEFDtc/edit#gid=0'
    sheet = client.open_by_url(sheet_url).worksheet("Result")
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    print("7. 스프레드시트 데이터 로드 성공")
    print(f"8. 총 {len(df)}개의 기사가 있습니다.")

except Exception as e:
    print(f"❌ Google Sheets 접근 중 오류 발생: {e}")
    exit(1)

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

# ✅ STEP 3: 기사 본문 열 추가
print("\n9. 기사 본문 크롤링 시작...")
try:
    df['본문'] = df['링크'].apply(extract_article_text)
    print("10. 기사 본문 크롤링 완료")
except Exception as e:
    print(f"❌ 크롤링 중 오류 발생: {e}")
    exit(1)

# ✅ STEP 4: JSON 변환
print("11. JSON 변환 시작...")
try:
    json_content = df.to_json(orient='records', force_ascii=False, indent=2)
    print("12. JSON 변환 완료")
except Exception as e:
    print(f"❌ JSON 변환 중 오류 발생: {e}")
    exit(1)

# ✅ STEP 5: GitHub Repository 업데이트 함수
def update_github_repo(json_data, github_token, repo_name, file_path='news_batch.json'):
    try:
        print("13. GitHub Repository 업데이트 시도...")
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
