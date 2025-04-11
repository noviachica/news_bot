import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import os
import json
import requests
from bs4 import BeautifulSoup
import base64
from datetime import datetime
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
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]
        credentials = ServiceAccountCredentials.from_json_keyfile_name('google_credentials.json', scope)
        client = gspread.authorize(credentials)
        
        # 스프레드시트 열기
        spreadsheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1HLTb59lcJQIZmaPMrJ0--hEsheyERIkCg5aBxSEFDtc/edit#gid=0')
        worksheet = spreadsheet.worksheet("Result")
        
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
        if 'naver.com' in url:
            # 네이버 뉴스 URL에서 신문사 코드 추출
            code = url.split('/article/')[1].split('/')[0]
            return NEWSPAPER_CODES.get(code, '기타')
        return '기타'
    except:
        return '기타'

def crawl_article(url):
    """기사 URL에서 내용을 크롤링합니다."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
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
                
                logger.info(f"성공적으로 본문을 찾았습니다. 선택자: {selector}")
                return text
        
        logger.warning(f"본문을 찾을 수 없습니다: {url}")
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
        
        # 파일 존재 여부와 내용 확인
        if os.path.exists(output_file):
            logger.info(f"{output_file} 파일이 성공적으로 생성되었습니다.")
            file_size = os.path.getsize(output_file)
            logger.info(f"파일 크기: {file_size} bytes")
            
            # 파일 내용 일부 확인
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read(500)  # 처음 500자만 읽기
                logger.info(f"파일 내용 시작 부분:\n{content}")
        else:
            logger.error(f"{output_file} 파일이 생성되지 않았습니다.")
            raise FileNotFoundError(f"{output_file} 파일이 생성되지 않았습니다.")
        
        # shorten.py 실행
        logger.info("중복 제거를 시작합니다...")
        try:
            logger.info("shorten.py 실행 시도...")
            result = subprocess.run(['python', 'shorten.py'], check=True, capture_output=True, text=True)
            logger.info(f"shorten.py 실행 결과: {result.stdout}")
            if result.stderr:
                logger.error(f"shorten.py 실행 중 오류: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logger.error(f"shorten.py 실행 실패: {str(e)}")
            logger.error(f"오류 출력: {e.stderr}")
            raise
        
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
