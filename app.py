import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower")

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.markdown("### Combined: CEE Performance & Customer Refund Misuse")
st.info("Frozen Logic: Dynamic Date Columns | Range Total | 5-Day Aging Buckets")

# --- 2. MULTI-FILE UPLOADER ---
uploaded_files = st.file_uploader("Upload 'complaints.csv' or 'CmsTicketDetailReport.csv' files", type="csv", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
            try:
                temp_df = pd.read_csv(file, encoding='utf-8', low_memory=False)
            except:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1', low_memory=False)
            
            col_map = {
                'Lob': ['Lob', 'LOB', 'lob'],
                'Date_Raw': ['Date', 'Complaint Created Date & Time', 'date'],
                'L4': ['Level 4', 'Agent Disposition Levels 4', 'Category'],
                'L5': ['Level 5', 'Agent Disposition Levels 5'],
                'CEE_Name_1': ['Cee Name', 'Cee name'],
                'CEE_Name_2': ['CEE NAME', 'cee_name'],
                'CEE_ID_1': ['CEE Number', 'cee_number'],
                'CEE_ID_2': ['CEE ID', 'cee_id'],
                'Hub': ['Hub', 'HUB', 'hub'],
                'City': ['City', 'CITY', 'city'],
                'Member': ['Member Id', 'Member ID', 'member_id'],
                'Is_VIP': ['Is VIP Customer', 'VIP', 'is_vip']
            }
            
            for standard, options in col_map.items():
                for opt in options:
                    if opt in temp_df.columns:
                        temp_df[standard] = temp_df[opt]
                        break
            
            if 'Lob' in temp_df.columns:
                temp_df = temp_df[temp_df['Lob'].astype(str).str.contains('bbdaily-b2c', case=False, na=False)].copy()
                
                if not temp_df.empty and 'Date_Raw' in temp_df.columns:
                    temp_df['Date'] = pd.to_datetime(temp_df['Date_Raw'], errors='coerce').dt.date
                    
                    def clean_val(val):
                        v = str(val).strip()
                        return v if v not in ['', 'nan', '-', 'None', '0', '0.0'] else None

                    temp_df['CEE_Name'] = temp_df['CEE_Name_1'].apply(clean_val).fillna(temp_df['CEE_Name_2'].apply(clean_val)).fillna("Unknown_CEE")
                    temp_df['CEE_ID'] = temp_df['CEE_ID_1'].apply(clean_val).fillna(temp_df['CEE_ID_2'].apply(clean_val)).fillna("Unknown_ID")
                    
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True).dropna(subset=['Date'])
        refund_keywords = ['credited', 'refund', 'refunded', 'amount']
        df['Is_Refund'] = df['L4'].astype(str).str.lower().apply(lambda x: 1 if any(k in x for k in refund_keywords) else 0)

        # --- 3. SIDEBAR FILTERS ---
        st.sidebar.header("Global Filters")
        available_dates = sorted(df['Date'].unique())
        col_d1, col_d2 = st.sidebar.columns(2)
        with col_d1:
            start_date = st.date_input("From Date", min(available_dates))
        with col_d2:
            end_date = st.date_input("To Date", max(available_dates))
        
        all_cities = sorted(df['City'].dropna().unique())
        selected_cities = st.sidebar.multiselect("Select City", all_cities, default=all_cities)
        
        city_mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
        if 'City' in df.columns: city_mask = city_mask & (df['City'].isin(selected_cities))
        city_filtered = df[city_mask]
        
        selected_l4 = st.sidebar.multiselect("Level 4", sorted(city_filtered['L4'].unique()), default=sorted(city_filtered['L4'].unique()))
        l4_filtered = city_filtered[city_filtered['L4'].isin(selected_l4)]
        
        selected_l5 = st.sidebar.multiselect("Level 5", sorted(l4_filtered['L5'].unique()), default=sorted(l4_filtered['L5'].unique()))
        l5_filtered = l4_filtered[l4_filtered['L5'].isin(selected_l5)]
        
        final_df = l5_filtered

        # --- 4. TABS ---
        tab1, tab2 = st.tabs(["📊 CEE Performance Matrix", "🕵️ Customer Refund Watchlist"])

        def generate_dynamic_matrix(data, group_cols, s_date, e_date):
            # 1. Base Data Grouping
            matrix = data.groupby(group_cols).size().reset_index(name='Range_Total')
            
            # 2. Add Individual Date Columns
            current = s_date
            while current <= e_date:
                day_counts = data[data['Date'] == current].groupby(group_cols).size().reset_index(name=str(current))
                matrix = matrix.merge(day_counts, on=group_cols, how='left').fillna(0)
                current += timedelta(days=1)
            
            # 3. Add Aging Buckets (Cumulative from To Date)
            buckets = [
                ("0-5 Days", 0, 5),
                ("5-10 Days", 6, 10),
                ("10-15 Days", 11, 15),
                ("15-30 Days", 16, 30)
            ]
            for label, start, end in buckets:
                b_end = e_date - timedelta(days=start)
                b_start = e_date - timedelta(days=end)
                mask = (data['Date'] >= b_start) & (data['Date'] <= b_end)
                b_counts = data[mask].groupby(group_cols).size().reset_index(name=label)
                matrix = matrix.merge(b_counts, on=group_cols, how='left').fillna(0)
            
            return matrix

        with tab1:
            st.subheader("Dynamic CEE Matrix (Daily Breakout + Buckets)")
            res = generate_dynamic_matrix(final_df, ['CEE_ID', 'CEE_Name', 'L4', 'L5', 'Hub', 'City'], start_date, end_date)
            # Make aging buckets visible at the start by reordering columns
            cols = list(res.columns)
            bucket_cols = ["0-5 Days", "5-10 Days", "10-15 Days", "15-30 Days", "Range_Total"]
            other_cols = [c for c in cols if c not in bucket_cols and c not in ['CEE_ID', 'CEE_Name', 'L4', 'L5', 'Hub', 'City']]
            final_cols = ['CEE_ID', 'CEE_Name', 'L4', 'L5', 'Hub', 'City'] + bucket_cols + other_cols
            
            st.dataframe(res[final_cols].sort_values(by='Range_Total', ascending=False), width="stretch")

        with tab2:
            st.subheader("Customer Watchlist")
            cust = final_df.groupby(['Member', 'Hub', 'City']).agg(
                Total_Complaints=('Member', 'count'),
                Refund_Incidents=('Is_Refund', 'sum'),
            ).reset_index()
            cust['Refund_Ratio_%'] = (cust['Refund_Incidents'] / cust['Total_Complaints'] * 100).round(1)
            st.dataframe(cust.sort_values(by='Refund_Incidents', ascending=False).head(100), width="stretch")

    else:
        st.error("No 'bbdaily-b2c' data found.")
else:
    st.info("Upload files to see the dynamic matrix.")
