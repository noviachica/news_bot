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
        print(f"✅ Gist 업데이트 성공!\n🌐 Raw 파일 주소: {raw_url}")
        return raw_url
    else:
        print(f"❌ 업데이트 실패: {response.status_code}\n{response.text}")
        return None


# ✅ STEP 4: 실제 실행
GITHUB_TOKEN = os.environ['GIST_TOKEN']
GIST_ID = "97a5c5e30792c31542cb0845a8af6b9f"  # <- 네가 복사한 Gist ID 넣기
update_gist(json_content, GITHUB_TOKEN, GIST_ID)

