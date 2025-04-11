import json
import logging
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import os

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 신문사 그룹 정의
NEWSPAPER_GROUPS = {
    '보수': {
        '조선일보': 1,
        '중앙일보': 2,
        '동아일보': 3
    },
    '진보': {
        '경향신문': 1,
        '한겨레신문': 2,
        '한국일보': 3
    },
    '경제': {
        '매일경제': 1,
        '한국경제': 2,
        '서울경제': 3,
        '아주경제': 4
    }
}

def get_newspaper_group(newspaper):
    """신문사가 속한 그룹을 반환"""
    for group_name, newspapers in NEWSPAPER_GROUPS.items():
        if newspaper in newspapers:
            return group_name
    return '기타'

def get_newspaper_priority(newspaper):
    """신문사의 우선순위를 반환"""
    for group in NEWSPAPER_GROUPS.values():
        if newspaper in group:
            return group[newspaper]
    return float('inf')

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
        logger.error(f"유사도 계산 중 오류: {e}")
        return 0.0

def find_similar_articles(group, similarity_threshold=0.7):
    """유사한 기사들을 찾아 그룹화"""
    logger.info(f"유사도 분석 시작 (임계값: {similarity_threshold})")
    logger.info(f"분석 대상 기사 수: {len(group)}")
    
    # 텍스트 전처리
    texts = group['내용'].apply(preprocess_text).tolist()
    
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
        logger.info(f"평균 유사도: {np.mean(similarities):.3f}")
        logger.info(f"최대 유사도: {np.max(similarities):.3f}")
        logger.info(f"최소 유사도: {np.min(similarities):.3f}")
        
    except Exception as e:
        logger.error(f"유사도 계산 실패: {e}")
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
            logger.info(f"유사 기사 그룹 {len(similar_groups)}: {len(similar_indices)}개 기사")
            logger.info(f"대표 기사: {group.iloc[i]['신문사']} - {group.iloc[i]['제목'][:30]}...")
            logger.info(f"유사도 범위: {np.min(similarity_matrix[i, similar_indices]):.3f} ~ {np.max(similarity_matrix[i, similar_indices]):.3f}")
    
    # 유사하지 않은 기사들도 각각 하나의 그룹으로
    remaining_indices = set(range(len(texts))) - used_indices
    if remaining_indices:
        for idx in remaining_indices:
            similar_groups.append(group.iloc[[idx]])
            logger.info(f"독립 기사 추가: {group.iloc[idx]['신문사']} - {group.iloc[idx]['제목'][:30]}...")
    
    logger.info(f"총 그룹 수: {len(similar_groups)}")
    return similar_groups

def select_articles_by_length(group_articles):
    """기사 길이와 신문사 우선순위를 고려하여 기사 선택"""
    if len(group_articles) == 0:
        return None
    
    # 기사 길이 계산
    group_articles['길이'] = group_articles['내용'].str.len()
    
    # 신문사 그룹별로 가장 긴 기사 선택
    selected_articles = []
    used_groups = set()
    
    for group_name in ['보수', '진보', '경제']:
        group_mask = group_articles['신문사'].isin(NEWSPAPER_GROUPS[group_name].keys())
        group_articles_subset = group_articles[group_mask]
        
        if len(group_articles_subset) > 0:
            # 가장 긴 기사 선택
            candidates = group_articles_subset.sort_values(['길이', '신문사'], 
                                                         key=lambda x: x.map(get_newspaper_priority) if x.name == '신문사' else x,
                                                         ascending=[False, True])
            
            # 기사 길이 차이가 20% 이상이면 길이를 우선
            if len(candidates) > 1:
                max_length = candidates.iloc[0]['길이']
                second_length = candidates.iloc[1]['길이']
                if (max_length - second_length) / max_length > 0.2:
                    selected_article = candidates.iloc[0]
                else:
                    # 길이가 비슷하면 신문사 우선순위로 선택
                    selected_article = candidates.iloc[0]
            else:
                selected_article = candidates.iloc[0]
            
            selected_articles.append(selected_article)
            used_groups.add(group_name)
            logger.info(f"{group_name}그룹에서 기사 선택: {selected_article['신문사']}")
    
    # 선택된 기사가 3개 미만이면 나머지 기사 중에서 길이가 긴 순으로 추가
    if len(selected_articles) < 3:
        remaining_articles = group_articles[~group_articles['신문사'].isin([a['신문사'] for a in selected_articles])]
        remaining_articles = remaining_articles.sort_values(['길이', '신문사'], 
                                                          key=lambda x: x.map(get_newspaper_priority) if x.name == '신문사' else x,
                                                          ascending=[False, True])
        
        for _, article in remaining_articles.iterrows():
            if len(selected_articles) >= 3:
                break
            selected_articles.append(article)
            logger.info(f"추가 선택: {article['신문사']}")
    
    return selected_articles

def deduplicate_articles(df):
    """기사 중복제거"""
    logger.info("기사 중복제거 시작...")
    
    # 키워드별로 그룹화
    grouped = df.groupby('키워드')
    deduplicated_rows = []
    
    for keyword, group in grouped:
        logger.info(f"\n키워드: {keyword}")
        logger.info(f"기사 수: {len(group)}")
        
        if len(group) < 3:
            logger.info("3개 미만이므로 모두 포함")
            deduplicated_rows.extend(group.to_dict('records'))
            continue
            
        # 유사도 기반 그룹화
        similar_groups = find_similar_articles(group)
        
        # 각 유사 그룹에서 기사 선택
        for group_idx, group_articles in enumerate(similar_groups, 1):
            logger.info(f"\n유사 그룹 {group_idx} 처리 중...")
            selected_articles = select_articles_by_length(group_articles)
            if selected_articles:
                deduplicated_rows.extend([article.to_dict() for article in selected_articles])
                logger.info(f"선택된 기사 수: {len(selected_articles)}")
    
    # DataFrame으로 변환
    deduplicated_df = pd.DataFrame(deduplicated_rows)
    logger.info(f"\n중복제거 완료. 원본: {len(df)}개, 중복제거 후: {len(deduplicated_df)}개")
    return deduplicated_df

def main():
    try:
        # JSON 파일 읽기
        input_file = 'news_data.json'
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # DataFrame으로 변환
        df = pd.DataFrame(data)
        
        # 중복제거
        deduplicated_df = deduplicate_articles(df)
        
        # 결과를 JSON 형식으로 변환
        result = deduplicated_df.to_dict('records')
        
        # JSON 파일로 저장
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"중복제거 결과를 {input_file}에 저장했습니다.")
        
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
