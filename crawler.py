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
import logging
import subprocess

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("1. 시작...")

# 신문사 코드 매핑
NEWSPAPER_CODES = {
    '001': '한국경제',
    '002': '매일경제',
    '003': '서울경제',
    '004': '아주경제',
    '005': '조선일보',
    '006': '중앙일보',
    '007': '동아일보',
    '008': '경향신문',
    '009': '한겨레신문',
    '010': '한국일보'
}

# ✅ STEP 1: Google Sheets에서 데이터 불러오기
def get_google_sheets_data():
    """구글 스프레드시트에서 데이터를 가져옵니다."""
    try:
        # 환경 변수에서 인증 정보 가져오기
        credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
        if not credentials_json:
            raise ValueError("GOOGLE_CREDENTIALS 환경 변수가 설정되지 않았습니다.")
        
        # 인증 정보를 임시 파일로 저장
        with open('google_credentials.json', 'w') as f:
            f.write(credentials_json)
        
        # 구글 API 인증
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_name('google_credentials.json', scope)
        client = gspread.authorize(credentials)
        
        # 스프레드시트 열기
        spreadsheet = client.open('news_bot')
        worksheet = spreadsheet.get_worksheet(0)  # 첫 번째 워크시트 선택
        
        # 모든 데이터 가져오기
        data = worksheet.get_all_values()
        
        # 헤더와 데이터 분리
        headers = data[0]
        rows = data[1:]
        
        # 데이터프레임 생성
        df = pd.DataFrame(rows, columns=headers)
        
        # 신문사 정보 추가
        df['신문사'] = df['링크'].apply(extract_newspaper_from_url)
        
        logger.info(f"스프레드시트에서 {len(df)}개의 행을 가져왔습니다.")
        logger.info(f"헤더: {headers}")
        
        return df
    
    except Exception as e:
        logger.error(f"구글 스프레드시트 데이터 가져오기 중 오류 발생: {str(e)}")
        raise

def extract_newspaper_from_url(url):
    """URL에서 신문사 코드를 추출합니다."""
    try:
        # URL에서 신문사 코드 추출 (예: https://n.news.naver.com/mnews/article/001/0012345678)
        code = url.split('/')[-2]
        return NEWSPAPER_CODES.get(code, '알 수 없음')
    except:
        return '알 수 없음'

def crawl_article(url):
    """기사 URL에서 내용을 크롤링합니다."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        article = soup.select_one('article')
        
        if article:
            return article.get_text(strip=True)
        else:
            logger.warning(f"기사 내용을 찾을 수 없습니다: {url}")
            return ""
    except Exception as e:
        logger.error(f"기사 크롤링 중 오류 발생: {str(e)}")
        return ""

def main():
    try:
        # 구글 스프레드시트에서 데이터 가져오기
        df = get_google_sheets_data()
        
        # 기사 내용 크롤링
        df['내용'] = df['링크'].apply(crawl_article)
        
        # 결과를 JSON 형식으로 변환
        result = []
        for _, row in df.iterrows():
            article = {
                '키워드': row['키워드'],
                '발행일': row['발행일'],
                '제목': row['제목'],
                '링크': row['링크'],
                '내용': row['내용'],
                '신문사': row['신문사']
            }
            result.append(article)
        
        # JSON 파일로 저장
        output_file = 'news_data.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"크롤링 결과를 {output_file}에 저장했습니다.")
        
        # shorten.py 실행
        logger.info("중복 제거를 시작합니다...")
        subprocess.run(['python', 'shorten.py'], check=True)
        
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
