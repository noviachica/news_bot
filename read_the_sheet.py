import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import os
import json
import requests
from bs4 import BeautifulSoup

# ✅ STEP 1: Google Sheets에서 데이터 불러오기
creds_json = json.loads(os.environ['GOOGLE_CREDENTIALS'])

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)

sheet_url = 'https://docs.google.com/spreadsheets/d/1HLTb59lcJQIZmaPMrJ0--hEsheyERIkCg5aBxSEFDtc/edit#gid=0'
sheet = client.open_by_url(sheet_url).worksheet("Result")
data = sheet.get_all_records()
df = pd.DataFrame(data)

print("✅ 구글 시트 불러오기 완료")

# ✅ STEP 2: 기사 본문 크롤러 정의
def extract_article_text(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')

        # 💡 Naver 뉴스 기준 (뉴스 사이트에 따라 여기 수정해야 함)
        article = soup.select_one('div#dic_area')  # Naver 뉴스 본문 영역
        return article.get_text(strip=True) if article else "본문 없음"

    except Exception as e:
        return f"[크롤링 에러] {e}"

# ✅ STEP 3: 기사 본문 열 추가
df['본문'] = df['링크'].apply(extract_article_text)
print("✅ 기사 본문 크롤링 완료")

# ✅ STEP 4: JSON 변환
json_content = df.to_json(orient='records', force_ascii=False, indent=2)

# ✅ STEP 5: Gist 덮어쓰기 함수
def update_gist(json_data, github_token, gist_id, filename='news_batch.json'):
    url = f"https://api.github.com/gists/{gist_id}"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "files": {
            filename: {
                "content": json_data
            }
        }
    }

    response = requests.patch(url, headers=headers, data=json.dumps(payload))

    if response.status_code == 200:
        raw_url = response.json()['files'][filename]['raw_url']
        print(f"✅ Gist 업데이트 성공!\n🌐 Raw URL: {raw_url}")
        return raw_url
    else:
        print(f"❌ Gist 업데이트 실패: {response.status_code}\n{response.text}")
        return None

# ✅ STEP 6: Gist에 덮어쓰기 업로드
GIST_ID = "4b8649fdd09ca3c07aeb9922add0b838"  # 예: "abc1234567890def"
GITHUB_TOKEN = os.environ['GIST_TOKEN']  # GitHub Secrets 또는 .env 에서 불러오기

update_gist(json_content, GITHUB_TOKEN, GIST_ID)
