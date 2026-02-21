import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower")
pd.set_option('future.no_silent_downcasting', True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.markdown("### Combined CEE & Customer Performance Dashboard")
st.info("Frozen Logic: Sidebar L4/L5 | Executive Aging Summary | bbdaily-b2c Rule")

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
            
            # --- THUMB RULE: bbdaily-b2c ONLY ---
            if 'Lob' in temp_df.columns:
                temp_df = temp_df[temp_df['Lob'].astype(str).str.contains('bbdaily-b2c', case=False, na=False)].copy()
                
                if not temp_df.empty and 'Date_Raw' in temp_df.columns:
                    temp_df['Date'] = pd.to_datetime(temp_df['Date_Raw'], errors='coerce').dt.date
                    
                    # VIP Standardization
                    if 'Is_VIP' in temp_df.columns:
                        temp_df['Is_VIP'] = temp_df['Is_VIP'].astype(str).str.lower().map({'yes': True, 'true': True, '1': True, '1.0': True}).fillna(False)
                    else:
                        temp_df['Is_VIP'] = False

                    # Clean CEE ID/Name to prevent duplicates
                    def clean_val(val):
                        v = str(val).strip()
                        return v if v not in ['', 'nan', '-', 'None', '0', '0.0'] else "Unknown"

                    temp_df['CEE_Name'] = temp_df['CEE_Name_1'].apply(clean_val).fillna(temp_df['CEE_Name_2'].apply(clean_val))
                    temp_df['CEE_ID'] = temp_df['CEE_ID_1'].apply(clean_val).fillna(temp_df['CEE_ID_2'].apply(clean_val))
                    temp_df['L4'] = temp_df['L4'].astype(str).str.strip()
                    temp_df['L5'] = temp_df['L5'].astype(str).str.strip()
                    
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True).dropna(subset=['Date'])
        refund_keywords = ['credited', 'refund', 'refunded', 'amount']
        df['Is_Refund'] = df['L4'].astype(str).str.lower().apply(lambda x: 1 if any(k in x for k in refund_keywords) else 0)

        # --- 3. SIDEBAR FILTERS ---
        st.sidebar.header("Global Filters")
        show_vip_only = st.sidebar.checkbox("⭐ Show VIP Customers Only", value=False)
        
        available_dates = sorted(df['Date'].unique())
        col_d1, col_d2 = st.sidebar.columns(2)
        with col_d1:
            start_date = st.date_input("From Date", min(available_dates))
        with col_d2:
            end_date = st.date_input("To Date", max(available_dates))
        
        all_cities = sorted(df['City'].dropna().unique())
        selected_cities = st.sidebar.multiselect("Select City", all_cities, default=all_cities)
        
        # Filter for L4/L5 Dropdowns
        pre_mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
        if show_vip_only: pre_mask = pre_mask & (df['Is_VIP'] == True)
        if 'City' in df.columns: pre_mask = pre_mask & (df['City'].isin(selected_cities))
        dropdown_df = df[pre_mask]

        selected_l4 = st.sidebar.multiselect("Level 4 Category", sorted(dropdown_df['L4'].unique()), default=sorted(dropdown_df['L4'].unique()))
        l4_filtered = dropdown_df[dropdown_df['L4'].isin(selected_l4)]
        
        selected_l5 = st.sidebar.multiselect("Level 5 Category", sorted(l4_filtered['L5'].unique()), default=sorted(l4_filtered['L5'].unique()))
        final_df = l4_filtered[l4_filtered['L5'].isin(selected_l5)]

        # --- 4. TABS ---
        t_summary, t_matrix, t_watchlist = st.tabs(["📌 Executive Summaries", "📊 30D CEE Matrix", "🕵️ Fraud Watchlist"])

        def generate_bucket_matrix(data, group_cols, e_date):
            # Sum for the specific selected range
            matrix = data.groupby(group_cols).size().reset_index(name='Range_Total')
            
            # Aging Buckets (Calculated from To Date)
            buckets = [("0-5 Days", 0, 5), ("5-10 Days", 6, 10), ("10-15 Days", 11, 15), ("15-30 Days", 16, 30)]
            for label, start_off, end_off in buckets:
                b_end = e_date - timedelta(days=start_off)
                b_start = e_date - timedelta(days=end_off)
                mask_b = (data['Date'] >= b_start) & (data['Date'] <= b_end)
                b_counts = data[mask_b].groupby(group_cols).size().reset_index(name=label)
                matrix = matrix.merge(b_counts, on=group_cols, how='left').fillna(0)
            
            for col in matrix.columns:
                if col not in group_cols: matrix[col] = matrix[col].astype(int)
            return matrix

        with t_summary:
            st.subheader("Executive Aging Summary (Aggregated by Category)")
            
            st.markdown("#### 🚛 Unique CEE Breakdown (by L4)")
            cee_exec = generate_bucket_matrix(final_df, ['CEE_ID', 'CEE_Name', 'L4'], end_date)
            st.dataframe(cee_exec.sort_values(by='Range_Total', ascending=False), width="stretch")
            
            st.divider()
            
            st.markdown("#### 👤 Customer Breakdown (by L4)")
            cust_exec = generate_bucket_matrix(final_df, ['Member', 'Is_VIP', 'L4'], end_date)
            st.dataframe(cust_exec.sort_values(by='Range_Total', ascending=False), width="stretch")

        with t_matrix:
            st.subheader("Daily CEE Matrix (Detailed)")
            current = start_date
            matrix_base = generate_bucket_matrix(final_df, ['CEE_ID', 'CEE_Name', 'L4', 'Hub'], end_date)
            while current <= end_date:
                day_counts = final_df[final_df['Date'] == current].groupby(['CEE_ID', 'CEE_Name', 'L4', 'Hub']).size().reset_index(name=str(current))
                matrix_base = matrix_base.merge(day_counts, on=['CEE_ID', 'CEE_Name', 'L4', 'Hub'], how='left').fillna(0)
                current += timedelta(days=1)
            
            # Reorder columns to show buckets first
            bucket_cols = ["0-5 Days", "5-10 Days", "10-15 Days", "15-30 Days", "Range_Total"]
            other_cols = [c for c in matrix_base.columns if c not in bucket_cols and c not in ['CEE_ID', 'CEE_Name', 'L4', 'Hub']]
            st.dataframe(matrix_base[['CEE_ID', 'CEE_Name', 'L4', 'Hub'] + bucket_cols + other_cols].sort_values(by='Range_Total', ascending=False), width="stretch")

        with t_watchlist:
            st.subheader("Fraud & Misuse Watchlist")
            watch_df = final_df.copy()
            watch_df['Days_Old'] = watch_df['Date'].apply(lambda x: (end_date - x).days if pd.notnull(x) else 0)
            
            cust_matrix = watch_df.groupby(['Member', 'Is_VIP', 'L4', 'L5', 'Hub']).agg(
                Refund_Tickets=('Is_Refund', 'sum'),
                Total_Tickets=('Member', 'count'),
                Avg_Ticket_Age=('Days_Old', 'mean')
            ).reset_index()
            
            cust_matrix['Refund_Ratio_%'] = (cust_matrix['Refund_Tickets'] / cust_matrix['Total_Tickets'] * 100).round(1)
            st.dataframe(cust_matrix.sort_values(by='Refund_Tickets', ascending=False).head(200), width="stretch")

    else:
        st.error("No valid 'bbdaily-b2c' data found.")
else:
    st.info("Awaiting file upload.")
