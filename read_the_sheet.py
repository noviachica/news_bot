import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import os
import json

# GitHub Secret에서 JSON 키를 불러오는 방식으로 변경
creds_json = json.loads(os.environ['GOOGLE_CREDENTIALS'])

# Google Sheets API 인증 범위 설정
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

# 인증 및 시트 접근 준비 (키파일 대신 dict 사용)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)

# 접근할 구글 시트 URL 입력
sheet_url = 'https://docs.google.com/spreadsheets/d/1HLTb59lcJQIZmaPMrJ0--hEsheyERIkCg5aBxSEFDtc/edit#gid=0'

# 시트 열기 (첫 번째 시트, 다른 시트 이름도 가능)
sheet = client.open_by_url(sheet_url).sheet1

# 데이터 전체 가져오기 (리스트 형태)
data = sheet.get_all_records()

# pandas DataFrame으로 변환해서 편리하게 보기
df = pd.DataFrame(data)

print(df.head())
