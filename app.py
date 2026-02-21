import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower")
pd.set_option('future.no_silent_downcasting', True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.info("Logic: Summary (Aging Only) | Overview (Aging + Daily) | Checkbox Grouping | bbdaily-b2c")

# --- 2. MULTI-FILE UPLOADER ---
uploaded_files = st.file_uploader("Upload CSV files", type="csv", accept_multiple_files=True)

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
                'Date_Raw': ['Date', 'Complaint Created Date & Time', 'date', 'Created Date'],
                'L4': ['Level 4', 'Agent Disposition Levels 4', 'Category'],
                'L5': ['Level 5', 'Agent Disposition Levels 5'],
                'CEE_Name_1': ['Cee Name', 'Cee name', 'CEE NAME'],
                'CEE_ID_1': ['CEE Number', 'cee_number', 'CEE ID', 'cee_id'],
                'Member_Id': ['Member Id', 'member_id', 'Member ID'],
                'Hub': ['Hub', 'HUB', 'hub', 'FC NAME'],
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
        
        # Date Filter
        available_dates = sorted(df['Date'].unique())
        col_d1, col_d2 = st.sidebar.columns(2)
        with col_d1:
            start_date = st.date_input("Date From", min(available_dates))
        with col_d2:
            end_date = st.date_input("Date To", max(available_dates))
        
        # Global Filters
        selected_cities = st.sidebar.multiselect("City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        selected_hubs = st.sidebar.multiselect("Store (Hub)", sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()), default=sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()))
        selected_vip = st.sidebar.multiselect("VIP Tag", sorted(df['VIP'].unique()), default=sorted(df['VIP'].unique()))

        # Category Grouping Toggles (Checkboxes)
        st.sidebar.markdown("---")
        st.sidebar.subheader("Grouping & Category Filters")
        group_by_l4 = st.sidebar.checkbox("Group by Level 4", value=True)
        group_by_l5 = st.sidebar.checkbox("Group by Level 5", value=False)

        # Category Filters (Multi-select)
        l4_list = sorted(df['L4'].unique())
        selected_l4 = st.sidebar.multiselect("L4 Filter (Filter specific items)", l4_list)
        
        l5_list = sorted(df[df['L4'].isin(selected_l4)]['L5'].unique()) if selected_l4 else sorted(df['L5'].unique())
        selected_l5 = st.sidebar.multiselect("L5 Filter (Filter specific items)", l5_list)

        # APPLY FILTERS
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date) & (df['City'].isin(selected_cities)) & (df['Hub'].isin(selected_hubs)) & (df['VIP'].isin(selected_vip))
        filtered_df = df[mask]
        if selected_l4: filtered_df = filtered_df[filtered_df['L4'].isin(selected_l4)]
        if selected_l5: filtered_df = filtered_df[filtered_df['L5'].isin(selected_l5)]

        # --- 4. DATA AGGREGATION ENGINE ---
        def generate_master_report(data, groups, s_date, e_date, include_daily=False):
            # 1. Base Range Total
            report = data.groupby(groups).size().reset_index(name='Range_Total')
            
            # 2. Aging Buckets
            buckets = [("0-5 Days", 0, 5), ("5-10 Days", 6, 10), ("10-15 Days", 11, 15), ("15-30 Days", 16, 30)]
            for label, start_off, end_off in buckets:
                b_end = e_date - timedelta(days=start_off)
                b_start = e_date - timedelta(days=end_off)
                mask_b = (data['Date'] >= b_start) & (data['Date'] <= b_end)
                b_counts = data[mask_b].groupby(groups).size().reset_index(name=label)
                report = report.merge(b_counts, on=groups, how='left').fillna(0)
            
            # 3. Dynamic Daily Columns
            if include_daily:
                curr = s_date
                while curr <= e_date:
                    d_str = curr.strftime('%d-%b')
                    day_data = data[data['Date'] == curr].groupby(groups).size().reset_index(name=d_str)
                    report = report.merge(day_data, on=groups, how='left').fillna(0)
                    curr += timedelta(days=1)

            # Convert to integers
            numeric_cols = report.columns.difference(groups)
            report[numeric_cols] = report[numeric_cols].astype(int)
            return report

        # --- 5. TABS INTERFACE ---
        t_perf, t_cee_sum, t_cee_over, t_cust_sum, t_cust_over = st.tabs([
            "📊 Performance Overview", "👤 CEE Summary", "🔍 CEE Detailed Overview", "🛒 Customer Summary", "🔎 Customer Overview"
        ])

        # Define Groupings based on Checkboxes
        cee_groups = ['CEE_ID', 'CEE_Name', 'Hub', 'City']
        if group_by_l4: cee_groups.append('L4')
        if group_by_l5: cee_groups.append('L5')

        cust_groups = ['Member_Id', 'City', 'VIP']
        if group_by_l4: cust_groups.append('L4')
        if group_by_l5: cust_groups.append('L5')

        with t_perf:
            st.subheader("Global Metrics")
            if not filtered_df.empty:
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Complaints", len(filtered_df))
                m2.metric("Unique CEEs", filtered_df['CEE_ID'].nunique())
                m3.metric("Unique Customers", filtered_df['Member_Id'].nunique())
                st.line_chart(filtered_df.groupby('Date').size())

        with t_cee_sum:
            st.subheader("CEE Aging Summary (No Daily)")
            if not filtered_df.empty:
                summary_table = generate_master_report(filtered_df, cee_groups, start_date, end_date, include_daily=False)
                st.dataframe(summary_table.sort_values('Range_Total', ascending=False), use_container_width=True)

        with t_cee_over:
            st.subheader("CEE Detailed Overview (Aging + Daily Matrix)")
            if not filtered_df.empty:
                detailed_table = generate_master_report(filtered_df, cee_groups, start_date, end_date, include_daily=True)
                # Reorder to match user request: ID, Name, L4, L5, Hub, City, Buckets, Total, Daily...
                st.dataframe(detailed_table.sort_values('Range_Total', ascending=False), use_container_width=True)
                st.download_button("📥 Download CEE Detailed CSV", detailed_table.to_csv(index=False), "cee_detailed.csv")

        with t_cust_sum:
            st.subheader("Customer Aging Summary")
            if not filtered_df.empty:
                cust_sum = generate_master_report(filtered_df, cust_groups, start_date, end_date, include_daily=False)
                st.dataframe(cust_sum.sort_values('Range_Total', ascending=False), use_container_width=True)

        with t_cust_over:
            st.subheader("Customer Detailed Overview (Aging + Daily Matrix)")
            if not filtered_df.empty:
                cust_over = generate_master_report(filtered_df, cust_groups, start_date, end_date, include_daily=True)
                st.dataframe(cust_over.sort_values('Range_Total', ascending=False), use_container_width=True)

    else:
        st.error("No valid 'bbdaily-b2c' data found.")
else:
    st.info("Please upload CSV files. Use the sidebar to toggle Grouping by L4/L5.")
