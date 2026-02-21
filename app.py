import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower")

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.markdown("### Combined: CEE Performance & Customer Refund Misuse")
st.info("Frozen Logic: VIP Filter | Dynamic Date Columns | Refund Aging | Disposition Levels")

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
                    
                    # VIP Logic
                    if 'Is_VIP' in temp_df.columns:
                        temp_df['Is_VIP'] = temp_df['Is_VIP'].astype(str).str.lower().map({'yes': True, 'true': True, '1': True, '1.0': True}).fillna(False)
                    else:
                        temp_df['Is_VIP'] = False

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
        show_vip_only = st.sidebar.checkbox("⭐ Show VIP Customers Only", value=False)
        
        available_dates = sorted(df['Date'].unique())
        col_d1, col_d2 = st.sidebar.columns(2)
        with col_d1:
            start_date = st.date_input("From Date", min(available_dates))
        with col_d2:
            end_date = st.date_input("To Date", max(available_dates))
        
        all_cities = sorted(df['City'].dropna().unique())
        selected_cities = st.sidebar.multiselect("Select City", all_cities, default=all_cities)
        
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
        if show_vip_only: mask = mask & (df['Is_VIP'] == True)
        if 'City' in df.columns: mask = mask & (df['City'].isin(selected_cities))
        
        sidebar_filtered_df = df[mask]
        
        selected_l4 = st.sidebar.multiselect("Level 4", sorted(sidebar_filtered_df['L4'].unique()), default=sorted(sidebar_filtered_df['L4'].unique()))
        l4_filtered = sidebar_filtered_df[sidebar_filtered_df['L4'].isin(selected_l4)]
        
        selected_l5 = st.sidebar.multiselect("Level 5", sorted(l4_filtered['L5'].unique()), default=sorted(l4_filtered['L5'].unique()))
        final_df = l4_filtered[l4_filtered['L5'].isin(selected_l5)]

        # --- 4. TABS ---
        tab1, tab2 = st.tabs(["📊 CEE Performance Matrix", "🕵️ Customer Refund Watchlist"])

        def generate_dynamic_matrix(data, group_cols, s_date, e_date):
            matrix = data.groupby(group_cols).size().reset_index(name='Range_Total')
            current = s_date
            while current <= e_date:
                day_counts = data[data['Date'] == current].groupby(group_cols).size().reset_index(name=str(current))
                matrix = matrix.merge(day_counts, on=group_cols, how='left').fillna(0)
                current += timedelta(days=1)
            buckets = [("0-5 Days", 0, 5), ("5-10 Days", 6, 10), ("10-15 Days", 11, 15), ("15-30 Days", 16, 30)]
            for label, start_off, end_off in buckets:
                b_end = e_date - timedelta(days=start_off)
                b_start = e_date - timedelta(days=end_off)
                mask_b = (data['Date'] >= b_start) & (data['Date'] <= b_end)
                b_counts = data[mask_b].groupby(group_cols).size().reset_index(name=label)
                matrix = matrix.merge(b_counts, on=group_cols, how='left').fillna(0)
            return matrix

        with tab1:
            st.subheader("Dynamic CEE Matrix")
            res = generate_dynamic_matrix(final_df, ['CEE_ID', 'CEE_Name', 'L4', 'L5', 'Hub', 'City'], start_date, end_date)
            bucket_cols = ["0-5 Days", "5-10 Days", "10-15 Days", "15-30 Days", "Range_Total"]
            other_cols = [c for c in res.columns if c not in bucket_cols and c not in ['CEE_ID', 'CEE_Name', 'L4', 'L5', 'Hub', 'City']]
            final_cols = ['CEE_ID', 'CEE_Name', 'L4', 'L5', 'Hub', 'City'] + bucket_cols + other_cols
            st.dataframe(res[final_cols].sort_values(by='Range_Total', ascending=False), width="stretch")

        with tab2:
            st.subheader("Customer Watchlist (Detailed Dispositions & Refund Aging)")
            
            # Filter for tickets where a refund was involved to calculate aging accurately
            refund_df = final_df.copy()
            refund_df['Days_Since_Refund'] = refund_df['Date'].apply(lambda x: (end_date - x).days if pd.notnull(x) else 0)
            
            cust = refund_df.groupby(['Member', 'Is_VIP', 'Hub', 'City', 'L4', 'L5']).agg(
                Refund_Tickets=('Is_Refund', 'sum'),
                Total_Complaints=('Member', 'count'),
                Avg_Refund_Age_Days=('Days_Since_Refund', 'mean')
            ).reset_index()
            
            cust['Refund_Ratio_%'] = (cust['Refund_Tickets'] / cust['Total_Complaints'] * 100).round(1)
            cust['Avg_Refund_Age_Days'] = cust['Avg_Refund_Age_Days'].round(1)
            
            # Sort by highest refund tickets
            st.dataframe(cust.sort_values(by='Refund_Tickets', ascending=False).head(200), width="stretch")

    else:
        st.error("No valid 'bbdaily-b2c' data found.")
else:
    st.info("Awaiting file upload.")
