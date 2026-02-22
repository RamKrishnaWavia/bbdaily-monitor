import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io

# --- 1. PAGE CONFIGURATION & AGGRESSIVE ALIGNMENT CSS ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower", page_icon="🛡️")

# Force Center Alignment across all Data Grid elements
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    
    [data-testid="stDataFrame"] div[role="gridcell"] > div,
    [data-testid="stDataFrame"] div[role="columnheader"] > div,
    [data-testid="stDataFrame"] .st-emotion-cache-1wivap2,
    [data-testid="stDataFrame"] .data-grid-container {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        width: 100% !important;
    }

    [data-testid="stDataFrame"] th {
        text-align: center !important;
        vertical-align: middle !important;
        background-color: #f1f3f6 !important;
        font-weight: bold !important;
    }

    .stDataFrame {
        padding-right: 50px !important;
        border-radius: 10px;
    }
    
    .availability-banner {
        background-color: #e3f2fd;
        color: #0d47a1;
        padding: 20px;
        border-radius: 12px;
        border-left: 8px solid #1976d2;
        font-weight: bold;
        margin-bottom: 25px;
        text-align: center;
        font-size: 18px;
    }
    
    section[data-testid="stSidebar"] { width: 400px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.markdown("---")

# --- 2. MULTI-FILE UPLOADER ---
uploaded_files = st.file_uploader("📂 Upload Complaint Dump (CSV Files)", type="csv", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
            try:
                temp_df = pd.read_csv(file, encoding='utf-8', low_memory=False)
            except:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1', low_memory=False)
            
            temp_df.columns = temp_df.columns.str.strip()
            temp_df['Source_CSV'] = file.name
            
            # Date Parsing logic
            date_col = next((c for c in ['Complaint Created Date & Time', 'Created Date', 'Date'] if c in temp_df.columns), None)
            if date_col:
                temp_df['Date_Parsed'] = pd.to_datetime(temp_df[date_col], dayfirst=True, errors='coerce')
                temp_df = temp_df.dropna(subset=['Date_Parsed'])
                temp_df['Date'] = temp_df['Date_Parsed'].dt.date
            
            # Column Mapping (Strict Integrity)
            col_map = {
                'Lob': ['Lob', 'LOB', 'Line of Business'],
                'Ticket_ID': ['Ticket ID', 'Complaint ID', 'Ticket Number'],
                'L4': ['Agent Disposition Levels 4', 'Level 4', 'Category'],
                'L5': ['Agent Disposition Levels 5', 'Level 5', 'Sub Category'],
                'CEE_Name': ['Cee Name', 'CEE NAME', 'Delivery Executive'],
                'CEE_ID': ['CEE Number', 'CEE ID', 'DE ID'],
                'Member_Id': ['Member Id', 'Member ID', 'Customer ID'],
                'Hub': ['Hub', 'HUB', 'FC NAME', 'Store'],
                'City': ['City', 'CITY'],
                'VIP': ['Is VIP Customer', 'VIP Tag', 'VIP Status', 'vip']
            }
            for standard, options in col_map.items():
                for opt in options:
                    if opt in temp_df.columns:
                        temp_df[standard] = temp_df[opt]
                        break
            
            # Thumb Rule: bbdaily-b2c filter
            if 'Lob' in temp_df.columns:
                temp_df = temp_df[temp_df['Lob'].astype(str).str.contains('bbdaily-b2c', case=False, na=False)].copy()
                if not temp_df.empty:
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error in {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        if 'VIP' in df.columns:
            df['VIP'] = df['VIP'].astype(str).str.strip().replace(['nan', '0', '0.0', 'None'], 'No')
        
        # --- 3. SIDEBAR CONTROLS ---
        st.sidebar.header("🎛️ Control Panel")
        search_id = st.sidebar.text_input("🔍 Search ID", "").strip()
        start_date = st.sidebar.date_input("From Date", df['Date'].min())
        end_date = st.sidebar.date_input("To Date", df['Date'].max())
        
        st.sidebar.subheader("📍 Geography & VIP")
        sel_cities = st.sidebar.multiselect("Select City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        sel_hubs = st.sidebar.multiselect("Select Hub", sorted(df[df['City'].isin(sel_cities)]['Hub'].unique()), default=sorted(df[df['City'].isin(sel_cities)]['Hub'].unique()))
        sel_vip = st.sidebar.multiselect("VIP Status", sorted(df['VIP'].unique()), default=sorted(df['VIP'].unique()))
        
        st.sidebar.subheader("📌 Disposition Filters")
        show_l4 = st.sidebar.checkbox("Include L4 in Tables", value=True)
        sel_l4 = st.sidebar.multiselect("Filter L4", sorted(df['L4'].dropna().unique()), default=sorted(df['L4'].dropna().unique()))
        show_l5 = st.sidebar.checkbox("Include L5 in Tables", value=False)
        sel_l5 = st.sidebar.multiselect("Filter L5", sorted(df['L5'].dropna().unique()), default=sorted(df['L5'].dropna().unique()))

        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date) & (df['City'].isin(sel_cities)) & (df['Hub'].isin(sel_hubs)) & (df['VIP'].isin(sel_vip))
        if 'L4' in df.columns: mask &= df['L4'].isin(sel_l4)
        if 'L5' in df.columns: mask &= df['L5'].isin(sel_l5)
        f_df = df[mask]
        
        if search_id:
            f_df = f_df[(f_df['Ticket_ID'].astype(str).str.contains(search_id)) | (f_df['CEE_ID'].astype(str).str.contains(search_id)) | (f_df['Member_Id'].astype(str).str.contains(search_id))]

        # --- 4. ENGINE FUNCTIONS ---
        def generate_report(data, groups, s_date, e_date, include_daily=False):
            available = [g for g in groups if g in data.columns]
            if data.empty: return pd.DataFrame(columns=available + ['Range_Total'])
            report = data.groupby(available).size().reset_index(name='Range_Total')
            
            buckets = [("0-5 Days", 0, 5), ("5-10 Days", 6, 10), ("10-15 Days", 11, 15), ("15-30 Days", 16, 30)]
            for label, s_off, e_off in buckets:
                b_end, b_start = e_date - timedelta(days=s_off), e_date - timedelta(days=e_off)
                b_mask = (data['Date'] >= b_start) & (data['Date'] <= b_end)
                b_counts = data[b_mask].groupby(available).size().reset_index(name=label)
                report = report.merge(b_counts, on=available, how='left').fillna(0)
            
            if include_daily:
                curr = s_date
                while curr <= e_date:
                    d_str = curr.strftime('%d-%b')
                    day_data = data[data['Date'] == curr].groupby(available).size().reset_index(name=d_str)
                    report = report.merge(day_data, on=available, how='left').fillna(0)
                    curr += timedelta(days=1)
            
            for c in report.columns.difference(available): report[c] = report[c].astype(int)
            return report

        # --- 5. TABS ---
        t1, t2, t3, t4, t5 = st.tabs(["📊 Analytical Summary", "👤 CEE Summary", "🔍 CEE Overview", "🛒 Customer Summary", "🔎 Customer Overview"])

        extra_cols = []
        if show_l4: extra_cols.append('L4')
        if show_l5: extra_cols.append('L5')

        with t1:
            st.markdown(f'<div class="availability-banner">📊 Analytical Summary Dashboard</div>', unsafe_allow_html=True)
            
            # Overall Metrics
            m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
            m_col1.metric("Total Tickets", len(f_df))
            m_col2.metric("Total CEEs", f_df['CEE_ID'].nunique() if 'CEE_ID' in f_df.columns else 0)
            m_col3.metric("Total Customers", f_df['Member_Id'].nunique() if 'Member_Id' in f_df.columns else 0)
            m_col4.metric("L4 Cat Count", f_df['L4'].nunique() if 'L4' in f_df.columns else 0)
            m_col5.metric("L5 Cat Count", f_df['L5'].nunique() if 'L5' in f_df.columns else 0)
            st.markdown("---")

            # Graphs Row 1
            gl1, gl2 = st.columns(2)
            with gl1:
                st.write("**Ticket Distribution (L4)**")
                st.bar_chart(f_df['L4'].value_counts())
            with gl2:
                st.write("**City-wise Volume**")
                st.bar_chart(f_df['City'].value_counts())
            
            # Graphs Row 2
            gl3, gl4 = st.columns(2)
            with gl3:
                st.write("**VIP Mix**")
                st.bar_chart(f_df['VIP'].value_counts())
            with gl4:
                st.write("**Daily Ticket Trend**")
                st.line_chart(f_df.groupby('Date').size())

            st.markdown("---")
            st.subheader("📝 Remark & Category Count Details")
            
            # --- NEW: DETAILED COUNT BREAKDOWNS ---
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                st.write("**L4 Category Breakdown**")
                l4_counts = f_df['L4'].value_counts().reset_index()
                l4_counts.columns = ['L4 Category', 'Total Count']
                st.dataframe(l4_counts, hide_index=True, use_container_width=True)
            
            with d_col2:
                st.write("**L5 Remark Breakdown**")
                l5_counts = f_df['L5'].value_counts().reset_index()
                l5_counts.columns = ['L5 Remark / Sub-Category', 'Total Count']
                st.dataframe(l5_counts, hide_index=True, use_container_width=True)

        with t2:
            cee_sum_cols = ['CEE_ID', 'CEE_Name', 'Hub', 'City', 'VIP'] + extra_cols
            st.dataframe(generate_report(f_df, cee_sum_cols, start_date, end_date).sort_values('Range_Total', ascending=False), use_container_width=True)

        with t3:
            cee_over_cols = ['CEE_ID', 'CEE_Name', 'Ticket_ID', 'Date', 'Hub', 'City', 'VIP'] + extra_cols
            st.dataframe(generate_report(f_df, cee_over_cols, start_date, end_date, True), use_container_width=True)

        with t4:
            cust_sum_cols = ['Member_Id', 'City', 'Hub', 'VIP'] + extra_cols
            st.dataframe(generate_report(f_df, cust_sum_cols, start_date, end_date).sort_values('Range_Total', ascending=False), use_container_width=True)

        with t5:
            cust_over_cols = ['Member_Id', 'Ticket_ID', 'Date', 'Hub', 'City', 'VIP'] + extra_cols
            st.dataframe(generate_report(f_df, cust_over_cols, start_date, end_date, True), use_container_width=True)
else:
    st.info("System Ready. Please upload CSV files to generate full analytics.")
