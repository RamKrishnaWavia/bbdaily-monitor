import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower")
pd.set_option('future.no_silent_downcasting', True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.info("Logic: Multi-ID Search | Priority Date Mapping | bbdaily-b2c Rule")

# --- 2. MULTI-FILE UPLOADER ---
uploaded_files = st.file_uploader("Upload CSV files", type="csv", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    detected_date_col = "None"
    
    for file in uploaded_files:
        try:
            try:
                temp_df = pd.read_csv(file, encoding='utf-8', low_memory=False)
            except:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1', low_memory=False)
            
            # --- CLEANING HEADERS & DATE LOCK ---
            temp_df.columns = temp_df.columns.str.strip()
            
            # Strict priority for Complaint timestamps
            date_priority = ['Complaint Created Date & Time', 'Created Date', 'Date', 'date']
            date_col = None
            for candidate in date_priority:
                if candidate in temp_df.columns:
                    date_col = candidate
                    detected_date_col = candidate
                    break
            
            if date_col:
                temp_df['Date_Raw'] = temp_df[date_col]
            
            # --- COLUMN MAPPING ---
            col_map = {
                'Lob': ['Lob', 'LOB', 'lob'],
                'Ticket_ID': ['Ticket ID', 'Complaint ID', 'Complaint Number', 'Ticket Number', 'id'],
                'L4': ['Level 4', 'Agent Disposition Levels 4', 'Category'],
                'L5': ['Level 5', 'Agent Disposition Levels 5'],
                'CEE_Name_1': ['Cee Name', 'Cee name', 'CEE NAME'],
                'CEE_ID_1': ['CEE Number', 'cee_number', 'CEE ID', 'cee_id'],
                'Member_Id': ['Member Id', 'member_id', 'Member ID'],
                'Hub': ['Hub', 'HUB', 'hub', 'FC NAME', 'Hub Name'],
                'City': ['City', 'CITY', 'city'],
                'VIP': ['Is VIP Customer', 'vip', 'VIP Tag']
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
                    
                    def clean_val(val):
                        v = str(val).strip()
                        return v if v not in ['', 'nan', '-', 'None', '0', '0.0'] else "Unknown"

                    temp_df['CEE_Name'] = temp_df['CEE_Name_1'].apply(clean_val)
                    temp_df['CEE_ID'] = temp_df['CEE_ID_1'].apply(clean_val)
                    temp_df['Ticket_ID'] = temp_df['Ticket_ID'].apply(clean_val)
                    temp_df['Member_Id'] = temp_df['Member_Id'].apply(clean_val)
                    temp_df['L4'] = temp_df['L4'].astype(str).str.strip()
                    temp_df['L5'] = temp_df['L5'].astype(str).str.strip()
                    temp_df['VIP'] = temp_df['VIP'].astype(str).str.strip()
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True).dropna(subset=['Date'])
        
        # --- 3. SIDEBAR FILTERS ---
        st.sidebar.header("🎛️ Control Panel")
        
        # Diagnostic Info (Verify correct date column is picked)
        st.sidebar.success(f"📅 Active Date: **{detected_date_col}**")
        
        # SEARCH SECTION
        st.sidebar.subheader("🔍 Integrated Search")
        search_id = st.sidebar.text_input("Enter Ticket / CEE / Member ID", "").strip()
        
        col_d1, col_d2 = st.sidebar.columns(2)
        with col_d1:
            start_date = st.sidebar.date_input("Date From", df['Date'].min())
        with col_d2:
            end_date = st.sidebar.date_input("Date To", df['Date'].max())
        
        selected_cities = st.sidebar.multiselect("City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        selected_hubs = st.sidebar.multiselect("Store (Hub)", sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()), default=sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()))
        
        st.sidebar.subheader("Grouping Selection")
        group_by_l4 = st.sidebar.checkbox("Group by Level 4", value=True)
        group_by_l5 = st.sidebar.checkbox("Group by Level 5", value=False)

        # APPLY FILTERS
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date) & (df['City'].isin(selected_cities)) & (df['Hub'].isin(selected_hubs))
        filtered_df = df[mask]
        
        # Logic for integrated search across 3 IDs
        if search_id:
            filtered_df = filtered_df[
                (filtered_df['Ticket_ID'].astype(str).str.contains(search_id, case=False)) |
                (filtered_df['CEE_ID'].astype(str).str.contains(search_id, case=False)) |
                (filtered_df['Member_Id'].astype(str).str.contains(search_id, case=False))
            ]

        # --- 4. AGGREGATION ENGINE ---
        def generate_report(data, groups, s_date, e_date, include_daily=False):
            report = data.groupby(groups).size().reset_index(name='Range_Total')
            buckets = [("0-5 Days", 0, 5), ("5-10 Days", 6, 10), ("10-15 Days", 11, 15), ("15-30 Days", 16, 30)]
            for label, s_off, e_off in buckets:
                b_end, b_start = e_date - timedelta(days=s_off), e_date - timedelta(days=e_off)
                b_counts = data[(data['Date'] >= b_start) & (data['Date'] <= b_end)].groupby(groups).size().reset_index(name=label)
                report = report.merge(b_counts, on=groups, how='left').fillna(0)
            if include_daily:
                curr = s_date
                while curr <= e_date:
                    d_str = curr.strftime('%d-%b')
                    day_data = data[data['Date'] == curr].groupby(groups).size().reset_index(name=d_str)
                    report = report.merge(day_data, on=groups, how='left').fillna(0)
                    curr += timedelta(days=1)
            numeric_cols = report.columns.difference(groups)
            report[numeric_cols] = report[numeric_cols].astype(int)
            return report

        # --- 5. TABS ---
        t_perf, t_cee_sum, t_cee_over, t_cust_sum, t_cust_over = st.tabs([
            "📊 Performance Overview", "👤 CEE Summary", "🔍 CEE Detailed Overview", "🛒 Customer Summary", "🔎 Customer Overview"
        ])

        cee_groups = ['CEE_ID', 'CEE_Name', 'Hub', 'City']
        if group_by_l4: cee_groups.append('L4')
        if group_by_l5: cee_groups.append('L5')
        cust_groups = ['Member_Id', 'City', 'Hub', 'VIP']
        if group_by_l4: cust_groups.append('L4')
        if group_by_l5: cust_groups.append('L5')

        with t_perf:
            st.subheader("Executive Complaint Analytics")
            if not filtered_df.empty:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Complaints", f"{len(filtered_df):,}")
                m2.metric("Unique CEEs", filtered_df['CEE_ID'].nunique())
                m3.metric("Unique Customers", filtered_df['Member_Id'].nunique())
                m4.metric("Avg Tickets/Day", round(len(filtered_df)/max((end_date-start_date).days, 1), 1))
                st.bar_chart(filtered_df['L4'].value_counts().head(10))

        with t_cee_sum:
            st.subheader("CEE Complaints Summary")
            st.dataframe(generate_report(filtered_df, cee_groups, start_date, end_date, False).sort_values('Range_Total', ascending=False), use_container_width=True)

        with t_cee_over:
            st.subheader("CEE Detailed (Verification Mode)")
            st.dataframe(generate_report(filtered_df, cee_groups + ['Ticket_ID', 'Date'], start_date, end_date, True).sort_values('Date', ascending=False), use_container_width=True)

        with t_cust_sum:
            st.subheader("Customer Refund Summary")
            st.dataframe(generate_report(filtered_df, cust_groups, start_date, end_date, False).sort_values('Range_Total', ascending=False), use_container_width=True)

        with t_cust_over:
            st.subheader("Customer Detailed (Verification Mode)")
            st.dataframe(generate_report(filtered_df, cust_groups + ['Ticket_ID', 'Date'], start_date, end_date, True).sort_values('Date', ascending=False), use_container_width=True)
    else:
        st.error("No records match the selected IDs, Filters, or Date Range.")
else:
    st.info("Upload CSV files. Use the sidebar Integrated Search for Ticket ID, CEE ID, or Member ID.")
