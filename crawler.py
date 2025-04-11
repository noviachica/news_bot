name: News Crawler

on:
  schedule:
    - cron: '30 23 * * *'  # UTC 23:30 (한국 시간 08:30)
  workflow_dispatch:  # 수동 실행 가능

jobs:
  crawl:
    runs-on: ubuntu-latest
    
    # GitHub 토큰 권한 설정
    permissions:
      contents: write  # 저장소 내용 수정 권한
      pull-requests: write  # PR 생성 권한
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install numpy==1.24.3
        pip install scipy==1.10.1
        pip install scikit-learn==1.3.0
        pip install gspread oauth2client pandas requests beautifulsoup4
        pip install konlpy
        pip install JPype1  # konlpy 의존성
    
    - name: Run crawler
      env:
        GOOGLE_CREDENTIALS: ${{ secrets.GOOGLE_CREDENTIAL }}
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      run: |
        echo "환경 변수 확인:"
        echo "GOOGLE_CREDENTIALS 길이: ${#GOOGLE_CREDENTIALS}"
        echo "GOOGLE_CREDENTIALS 시작 부분: ${GOOGLE_CREDENTIALS:0:100}"
        echo "GITHUB_TOKEN 길이: ${#GITHUB_TOKEN}"
        echo "GITHUB_TOKEN 시작 부분: ${GITHUB_TOKEN:0:10}..."
        python crawler.py 
