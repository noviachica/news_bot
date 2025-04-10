import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import os
import json
import requests

# ✅ STEP 1: Google Sheets에서 데이터 읽기
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

print("✅ Google Sheets에서 데이터 읽기 완료!")
print(df.head())

# ✅ STEP 2: JSON 변환
json_content = df.to_json(orient='records', force_ascii=False, indent=2)

# ✅ STEP 3: Gist에 업로드
def upload_to_gist(json_data, github_token, filename='news_batch.json', description='뉴스 JSON 자동 업로드'):
    url = "https://api.github.com/gists"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "description": description,
        "public": True,
        "files": {
            filename: {
                "content": json_data
            }
        }
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))

    if response.status_code == 201:
        gist_url = response.json()['html_url']
        raw_url = response.json()['files'][filename]['raw_url']
        print(f"✅ Gist 업로드 성공!\n📄 Gist 주소: {gist_url}\n🌐 Raw 파일 주소: {raw_url}")
        return raw_url
    else:
        print(f"❌ 업로드 실패: {response.status_code}\n{response.text}")
        return None

# ✅ STEP 4: 실제 실행
GITHUB_TOKEN = os.environ['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']  # GitHub Personal Access Token은 GitHub Secrets에 저장 필요
upload_to_gist(json_content, GITHUB_TOKEN)
