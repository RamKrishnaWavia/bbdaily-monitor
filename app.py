import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import io

# --- 1. PAGE CONFIGURATION & AGGRESSIVE UI STYLING ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower", page_icon="🛡️")

# Force Center Alignment and Professional UI
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    
    /* Aggressive CSS to force center alignment in the Data Grid */
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
            
            # Date Parsing (DD-MM-YYYY)
            date_col = next((c for c in ['Complaint Created Date & Time', 'Created Date', 'Date'] if c in temp_df.columns), None)
            if date_col:
                temp_df['Date_Parsed'] = pd.to_datetime(temp_df[date_col], dayfirst=True, errors='coerce')
                temp_df = temp_df.dropna(subset=['Date_Parsed'])
                temp_df['Date'] = temp_df['Date_Parsed'].dt.date
            
            # Column Mapping
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
            
            # THUMB RULE: bbdaily-b2c Filter
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
        search_id = st.sidebar.text_input("🔍 Search (Ticket/CEE/Cust)", "").strip()
        start_date = st.sidebar.date_input("From Date", df['Date'].min())
        end_date = st.sidebar.date_input("To Date", df['Date'].max())
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("📍 Geography & Segment")
        sel_cities = st.sidebar.multiselect("Select City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        sel_hubs = st.sidebar.multiselect("Select Hub", sorted(df[df['City'].isin(sel_cities)]['Hub'].unique()), default=sorted(df[df['City'].isin(sel_cities)]['Hub'].unique()))
        sel_vip = st.sidebar.multiselect("VIP Status", sorted(df['VIP'].unique()), default=sorted(df['VIP'].unique()))
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("📌 Disposition Filters")
        show_l4 = st.sidebar.checkbox("Include L4 in Tables", value=True)
        sel_l4 = st.sidebar.multiselect("Filter L4", sorted(df['L4'].dropna().unique()), default=sorted(df['L4'].dropna().unique()))
        show_l5 = st.sidebar.checkbox("Include L5 in Tables", value=False)
        sel_l5 = st.sidebar.multiselect("Filter L5", sorted(df['L5'].dropna().unique()), default=sorted(df['L5'].dropna().unique()))

        # Filter Masking
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date) & (df['City'].isin(sel_cities)) & (df['Hub'].isin(sel_hubs)) & (df['VIP'].isin(sel_vip))
        if 'L4' in df.columns: mask &= df['L4'].isin(sel_l4)
        if 'L5' in df.columns: mask &= df['L5'].isin(sel_l5)
        f_df = df[mask]
        
        if search_id:
            f_df = f_df[(f_df['Ticket_ID'].astype(str).str.contains(search_id)) | (f_df['CEE_ID'].astype(str).str.contains(search_id)) | (f_df['Member_Id'].astype(str).str.contains(search_id))]

        # --- 4. ENGINE FUNCTIONS (FULL AGING & TREND LOGIC) ---
        def generate_report(data, groups, s_date, e_date, include_daily=False):
            available = [g for g in groups if g in data.columns]
            if data.empty: return pd.DataFrame(columns=available + ['Range_Total'])
            
            report = data.groupby(available).size().reset_index(name='Range_Total')
            
            # RESTORED AGING BUCKETS
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

        cee_cols = ['CEE_ID', 'CEE_Name', 'Hub', 'City', 'VIP']
        if show_l4: cee_cols.append('L4')
        if show_l5: cee_cols.append('L5')

        with t1:
            st.markdown(f'<div class="availability-banner">📅 Analyzing {len(f_df)} Complaints: {f_df["Date"].min()} to {f_df["Date"].max()}</div>', unsafe_allow_html=True)
            col_a, col_b = st.columns(2)
            with col_a:
                fig_l4 = px.bar(f_df['L4'].value_counts().reset_index(), x='count', y='L4', orientation='h', title="Top L4 Categories", color_discrete_sequence=['#1976d2'])
                st.plotly_chart(fig_l4, use_container_width=True)
            with col_b:
                fig_vip = px.pie(f_df, names='VIP', title="Customer Mix (VIP vs Regular)", hole=0.4)
                st.plotly_chart(fig_vip, use_container_width=True)
            
            st.write("**Daily Complaint Volume**")
            fig_trend = px.line(f_df.groupby('Date').size().reset_index(name='Tickets'), x='Date', y='Tickets', markers=True)
            st.plotly_chart(fig_trend, use_container_width=True)

        with t2:
            st.dataframe(generate_report(f_df, cee_cols, start_date, end_date), use_container_width=True)

        with t3:
            st.dataframe(generate_report(f_df, cee_cols + ['Ticket_ID', 'Date'], start_date, end_date, True), use_container_width=True)

        with t4:
            st.dataframe(generate_report(f_df, ['Member_Id', 'City', 'Hub', 'VIP'] + (['L4'] if show_l4 else []), start_date, end_date), use_container_width=True)

        with t5:
            st.dataframe(generate_report(f_df, ['Member_Id', 'Ticket_ID', 'Date', 'City', 'Hub', 'VIP'], start_date, end_date, True), use_container_width=True)

else:
    st.info("System Ready. Please upload your CSV files to activate the 250-line full logic.")
