import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from utils import (
    to_krw_from_thousand, 
    format_kor_money_from_thousand, 
    extract_data_from_markdown, 
    parse_html_details
)
import os
import traceback

# 페이지 설정
st.set_page_config(page_title="상가/점포 매물 대시보드", layout="wide", page_icon="🏢")

# Custom CSS
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .card { background-color: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 20px; border-left: 5px solid #007bff; }
    .price-text { color: #d9534f; font-weight: bold; font-size: 1.1em; }
    .info-label { color: #6c757d; font-size: 0.9em; }
    .debug-box { background-color: #fef2f2; border: 1px solid #f87171; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 0.8em; }
</style>
""", unsafe_allow_html=True)

def load_and_preprocess_data(file_content):
    try:
        json_data, html_content = extract_data_from_markdown(file_content)
        
        if json_data is None:
            st.error("❌ JSON 데이터를 파싱하지 못했습니다. (데이터 구조 불일치 또는 괄호 누락)")
            with st.expander("디버깅 정보: 추출된 텍스트 확인"):
                st.text(file_content[:1000] + "...")
            return None, html_content
            
        if "items" not in json_data:
            st.error("❌ JSON 내 'items' 키를 찾을 수 없습니다.")
            st.json(json_data)
            return None, html_content
        
        df = pd.DataFrame(json_data["items"])
        
        if df.empty:
            st.warning("⚠️ 'items' 리스트가 비어 있습니다.")
            return df, html_content

        # 기본 전처리: 날짜 변환
        if 'createdDateUtc' in df.columns:
            df['createdDateUtc'] = pd.to_datetime(df['createdDateUtc'])
        
        # 금액 변환
        amount_cols = ['deposit', 'monthlyRent', 'premium', 'maintenanceFee']
        for col in amount_cols:
            if col in df.columns:
                df[f'{col}_man'] = df[col] / 10
                df[f'{col}_fmt'] = df[col].apply(format_kor_money_from_thousand)
            else:
                df[f'{col}_man'] = 0.0
                df[f'{col}_fmt'] = "0"

        return df, html_content
    except Exception as e:
        st.error(f"❌ 데이터 전처리 중 오류 발생: {e}")
        st.code(traceback.format_exc())
        return None, ""

def main():
    st.title("🏢 상가/점포 매물 인사이트 대시보드")
    
    # 데이터 소스 선택 (배포 환경 호환을 위한 상대 경로 설정)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, "data", "nemo_stores.db")
    sample_md_path = os.path.join(current_dir, "data_json_html.md")
    
    df = None
    raw_html = ""

    with st.sidebar:
        st.header("📂 데이터 관리")
        data_source = st.radio("데이터 소스 선택", ["SQLite 데이터베이스", "Markdown 파일 업로드", "샘플 Markdown"])
        
        if data_source == "SQLite 데이터베이스":
            if os.path.exists(db_path):
                from utils import load_data_from_db
                df_db = load_data_from_db(db_path)
                if not df_db.empty:
                    df = df_db.copy()
                    st.success(f"✅ DB 로드 완료 ({len(df)}건)")
                else:
                    st.error("DB가 비어있거나 로드에 실패했습니다.")
            else:
                st.error(f"DB 파일을 찾을 수 없습니다: {db_path}")
                
        elif data_source == "Markdown 파일 업로드":
            uploaded_file = st.file_uploader("Markdown 파일 업로드", type=["md", "txt", "json"])
            if uploaded_file:
                file_content = uploaded_file.getvalue().decode("utf-8")
                df, raw_html = load_and_preprocess_data(file_content)
                
        elif data_source == "샘플 Markdown":
            if os.path.exists(sample_md_path):
                with open(sample_md_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                df, raw_html = load_and_preprocess_data(file_content)
                st.success("✅ 샘플 로드 완료")

    if df is None:
        st.info("왼쪽 사이드바에서 데이터 소스를 선택해 주세요.")
        return

    # DB 전용 전처리 (Markdown 로더에서는 이미 수행됨)
    if data_source == "SQLite 데이터베이스" and not df.empty:
        # DB에서 불러온 직후 필요한 전처리 수행
        if 'createdDateUtc' in df.columns:
            df['createdDateUtc'] = pd.to_datetime(df['createdDateUtc'])
        
        # 금액 변환
        amount_cols = ['deposit', 'monthlyRent', 'premium', 'maintenanceFee']
        for col in amount_cols:
            if col in df.columns:
                df[f'{col}_man'] = df[col] / 10
                df[f'{col}_fmt'] = df[col].apply(format_kor_money_from_thousand)
            else:
                df[f'{col}_man'] = 0.0
                df[f'{col}_fmt'] = "0"

    # 2. 필터 섹션 (사이드바)
    st.sidebar.header("🔍 필터 옵션")
    
    search_query = st.sidebar.text_input("매물 제목 검색", "")
    
    # 안전하게 옵션 추출
    business_options = sorted(df['businessMiddleCodeName'].unique().tolist()) if 'businessMiddleCodeName' in df.columns else []
    selected_business = st.sidebar.multiselect("업종(중분류)", options=business_options, default=business_options)
    
    price_types = df['priceTypeName'].unique().tolist() if 'priceTypeName' in df.columns else []
    selected_price_type = st.sidebar.multiselect("가격 유형", options=price_types, default=price_types)
    
    # 금액 필터
    st.sidebar.subheader("💰 금액 범위 (만원)")
    
    # 보증금 필터
    dep_min = float(df['deposit_man'].min()) if 'deposit_man' in df.columns else 0.0
    dep_max = float(df['deposit_man'].max()) if 'deposit_man' in df.columns else 10000.0
    
    if dep_min == dep_max:
        st.sidebar.info(f"보증금: {format_kor_money_from_thousand(df['deposit'].iloc[0])} (단일값)")
        dep_range = (dep_min, dep_max)
    else:
        dep_range = st.sidebar.slider("보증금(만원)", dep_min, dep_max, (dep_min, dep_max))
    
    # 월세 필터
    rent_min = float(df['monthlyRent_man'].min()) if 'monthlyRent_man' in df.columns else 0.0
    rent_max = float(df['monthlyRent_man'].max()) if 'monthlyRent_man' in df.columns else 1000.0
    
    if rent_min == rent_max:
        st.sidebar.info(f"월세: {format_kor_money_from_thousand(df['monthlyRent'].iloc[0])} (단일값)")
        rent_range = (rent_min, rent_max)
    else:
        rent_range = st.sidebar.slider("월세(만원)", rent_min, rent_max, (rent_min, rent_max))

    # 데이터 필터링 적용
    mask = (
        (df['businessMiddleCodeName'].isin(selected_business)) &
        (df['priceTypeName'].isin(selected_price_type)) &
        (df['deposit_man'].between(dep_range[0], dep_range[1])) &
        (df['monthlyRent_man'].between(rent_range[0], rent_range[1]))
    )
    filtered_df = df[mask]
    
    if search_query:
        filtered_df = filtered_df[filtered_df['title'].str.contains(search_query, case=False)]

    # 3. 메인 대시보드 표시
    kpi_cols = st.columns(5)
    kpi_cols[0].metric("매물 수", f"{len(filtered_df)}건")
    if not filtered_df.empty:
        kpi_cols[1].metric("평균 월세", format_kor_money_from_thousand(filtered_df['monthlyRent'].mean()))
        kpi_cols[2].metric("평균 보증금", format_kor_money_from_thousand(filtered_df['deposit'].mean()))
        kpi_cols[3].metric("평균 권리금", format_kor_money_from_thousand(filtered_df['premium'].mean()))
        kpi_cols[4].metric("평균 면적", f"{filtered_df['size'].mean():.1f}㎡")

    # 차트
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        fig1 = px.scatter(filtered_df, x="size", y="monthlyRent_man", color="businessMiddleCodeName", 
                         title="면적별 월세 분포", template="plotly_white")
        st.plotly_chart(fig1, use_container_width=True)
    with c2:
        fig2 = px.histogram(filtered_df, x="monthlyRent_man", title="월세 가격대 분포", template="plotly_white")
        st.plotly_chart(fig2, use_container_width=True)

    # 매물 카드 리스트
    st.divider()
    html_details = parse_html_details(raw_html)
    
    for _, row in filtered_df.iterrows():
        with st.container():
            st.markdown(f"""
            <div class="card">
                <div style="display: flex; gap: 20px;">
                    <img src="{row['previewPhotoUrl']}" style="width: 150px; height: 110px; border-radius: 8px; object-fit: cover;">
                    <div style="flex: 1;">
                        <h4 style="margin:0;">{row['title']}</h4>
                        <p style="margin:5px 0;"><small>{row['businessMiddleCodeName']} | {row['floor']}층 | {row['size']}㎡</small></p>
                        <p><span class="price-text">보증금 {row['deposit_fmt']} / 월세 {row['monthlyRent_fmt']}</span></p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("상세 보기"):
                st.write(f"**📍 위치:** {row['nearSubwayStation']}")
                st.write("**📄 설명:**")
                st.info(html_details.get('comment', '설명이 없습니다.'))
                if 'originPhotoUrls' in row and row['originPhotoUrls']:
                    st.image(row['originPhotoUrls'][:3], width=200)

if __name__ == "__main__":
    main()
