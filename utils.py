import pandas as pd
import numpy as np
import re
import json
import os
from bs4 import BeautifulSoup

def to_krw_from_thousand(v):
    """
    천원 단위 값을 원화로 변환
    """
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return 0
    try:
        return int(v) * 1000
    except (ValueError, TypeError):
        return 0

def format_kor_money_from_thousand(v):
    """
    천원 단위 값을 한국식 단위(억/만)로 포맷팅
    """
    if v is None or (isinstance(v, float) and np.isnan(v)) or v == 0:
        return "0"
    
    # 만원 단위로 먼저 환산 (json_value / 10)
    try:
        val_man = int(v) / 10
    except (ValueError, TypeError):
        return "0"

    if val_man >= 10000:
        uk = int(val_man // 10000)
        man = int(val_man % 10000)
        if man > 0:
            return f"{uk}억 {man:,}만"
        else:
            return f"{uk}억"
    else:
        return f"{int(val_man):,}만"

def extract_data_from_markdown(content):
    """
    마크다운 파일에서 JSON과 HTML 섹션을 추출
    """
    json_data = None
    
    # JSON 부분과 HTML 부분 분리 시도
    # 보통 HTML은 <div 로 시작함
    json_part = content
    html_part = ""
    
    if "<div" in content:
        parts = content.split("<div", 1)
        json_part = parts[0].strip()
        html_part = "<div" + parts[1]
    
    # JSON 파트 정제하기
    try:
        # 첫 번째 { 찾기
        start_idx = json_part.find('{')
        if start_idx != -1:
            json_str = json_part[start_idx:].strip()
            
            # 마지막 } 또는 ] 또는 , 이후의 비-JSON 텍스트 제거
            last_valid_char_idx = -1
            for char in ['}', ']', ',']:
                idx = json_str.rfind(char)
                if idx > last_valid_char_idx:
                    last_valid_char_idx = idx
            
            if last_valid_char_idx != -1:
                json_str = json_str[:last_valid_char_idx + 1].strip()
            
            if json_str.endswith(','):
                json_str = json_str[:-1].strip()
            
            # 먼저 정상 파싱 시도
            try:
                json_data = json.loads(json_str)
            except Exception:
                # 파싱 실패 시, 불완전한 JSON 보정 시도 (괄호 추가)
                for suffix in [']}', '}', ']}', ' ] }']:
                    try:
                        json_data = json.loads(json_str + suffix)
                        break
                    except:
                        continue
    except Exception as e:
        print(f"Extraction Error: {e}")

    return json_data, html_part

def parse_html_details(html_content):
    """
    HTML에서 가격표 및 상세 정보 파싱
    """
    if not html_content:
        return {}
    
    soup = BeautifulSoup(html_content, 'html.parser')
    details = {}

    # 가격표 파싱 (price-container)
    price_container = soup.find('div', class_='price-container')
    if price_container:
        rows = price_container.find_all('tr')
        for row in rows:
            th = row.find('th')
            td = row.find('td')
            if th and td:
                key = th.get_text(strip=True)
                val = td.get_text(strip=True)
                details[key] = val

    # 중개사 코멘트
    comment = soup.find('div', class_='comment')
    if comment:
        p_tag = comment.find('p')
        if p_tag:
            details['comment'] = p_tag.get_text(separator="\n", strip=True)

    # 유사매물 파싱
    similar_items = []
    similar_section = soup.find('div', class_='similar')
    if similar_section:
        items = similar_section.find_all('li', class_='article-list-item')
        for item in items:
            price_tag = item.find('div', class_='price1')
            if price_tag:
                similar_items.append({
                    'price': price_tag.get_text(strip=True)
                })
    details['similar_items'] = similar_items

    return details

def load_data_from_db(db_path):
    """
    SQLite DB에서 매물 데이터를 로드하고 전처리
    """
    import sqlite3
    import json
    
    if not os.path.exists(db_path):
        return pd.DataFrame()
        
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query("SELECT * FROM items", conn)
        conn.close()
        
        # JSON 문자열 필드를 리스트/딕셔너리로 복원
        json_fields = ['originPhotoUrls', 'subPhotoUrls', 'businessMiddleCodeName'] # 필요 시 추가
        for field in json_fields:
            if field in df.columns:
                def safe_json_loads(val):
                    if not val or not isinstance(val, str):
                        return val
                    try:
                        return json.loads(val)
                    except:
                        return val
                df[field] = df[field].apply(safe_json_loads)
                
        return df
    except Exception as e:
        print(f"DB Load Error: {e}")
        return pd.DataFrame()

# 테스트용 코드
if __name__ == "__main__":
    test_values = [45000, 1700, 19000, 90, 135000]
    print("--- Currency Formatting Test ---")
    for v in test_values:
        print(f"Input: {v} -> Output: {format_kor_money_from_thousand(v)}")
    
    # DB 테스트 (필요시 주석 해제)
    # db_test_path = r"c:\Users\Sunny Kang\Desktop\fcicb7\nemostore\data\nemo_stores.db"
    # if os.path.exists(db_test_path):
    #     df_db = load_data_from_db(db_test_path)
    #     print(f"Loaded {len(df_db)} items from DB")
