import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower")
pd.set_option('future.no_silent_downcasting', True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.markdown("### 5-Tab Multi-Dimensional Analysis")
st.info("Tabs: Performance Overview | CEE Summary (Aging) | CEE Overview (Raw) | Customer Summary (Aging) | Customer Overview (Raw)")

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
                'VIP': ['Is VIP Customer', 'vip', 'VIP Tag'],
                'Status': ['STATUS', 'status', 'Ticket Status']
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
        
        # City & Store Filter
        all_cities = sorted(df['City'].dropna().unique())
        selected_cities = st.sidebar.multiselect("City Filter", all_cities, default=all_cities)
        
        hubs_in_cities = sorted(df[df['City'].isin(selected_cities)]['Hub'].dropna().unique())
        selected_hubs = st.sidebar.multiselect("Store (Hub) Filter", hubs_in_cities, default=hubs_in_cities)

        # VIP Filter
        vip_options = sorted(df['VIP'].unique())
        selected_vip = st.sidebar.multiselect("VIP Tag", vip_options, default=vip_options)
        
        # Category Filters
        l4_options = sorted(df['L4'].unique())
        selected_l4 = st.sidebar.multiselect("Level 4 Filter (Empty = Total Sum)", l4_options)
        
        l5_filtered_options = sorted(df[df['L4'].isin(selected_l4)]['L5'].unique()) if selected_l4 else sorted(df['L5'].unique())
        selected_l5 = st.sidebar.multiselect("Level 5 (Level)", l5_filtered_options)

        # FINAL FILTERING
        mask = (
            (df['Date'] >= start_date) & 
            (df['Date'] <= end_date) & 
            (df['City'].isin(selected_cities)) &
            (df['Hub'].isin(selected_hubs)) &
            (df['VIP'].isin(selected_vip))
        )
        filtered_df = df[mask]
        
        if selected_l4: filtered_df = filtered_df[filtered_df['L4'].isin(selected_l4)]
        if selected_l5: filtered_df = filtered_df[filtered_df['L5'].isin(selected_l5)]

        # --- 4. AGING LOGIC FUNCTION ---
        def generate_aging_report(data, groups, e_date):
            report = data.groupby(groups).size().reset_index(name='Range_Total')
            buckets = [("0-5 Days", 0, 5), ("5-10 Days", 6, 10), ("10-15 Days", 11, 15), ("15-30 Days", 16, 30)]
            for label, start_off, end_off in buckets:
                b_end = e_date - timedelta(days=start_off)
                b_start = e_date - timedelta(days=end_off)
                mask_b = (data['Date'] >= b_start) & (data['Date'] <= b_end)
                b_counts = data[mask_b].groupby(groups).size().reset_index(name=label)
                report = report.merge(b_counts, on=groups, how='left').fillna(0)
            numeric_cols = ["0-5 Days", "5-10 Days", "10-15 Days", "15-30 Days", "Range_Total"]
            report[numeric_cols] = report[numeric_cols].astype(int)
            return report

        # --- 5. TABS INTERFACE (5 TABS) ---
        t_perf, t_cee_sum, t_cee_over, t_cust_sum, t_cust_over = st.tabs([
            "📊 Performance Overview", 
            "👤 CEE Summary", 
            "🔍 CEE Overview", 
            "🛒 Customer Summary", 
            "🔎 Customer Overview"
        ])

        with t_perf:
            st.subheader(f"System Pulse: {start_date} to {end_date}")
            if not filtered_df.empty:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Tickets", len(filtered_df))
                m2.metric("Unique CEEs", filtered_df['CEE_ID'].nunique())
                m3.metric("Unique Customers", filtered_df['Member_Id'].nunique())
                m4.metric("Active Hubs", filtered_df['Hub'].nunique())
                
                c1, c2 = st.columns(2)
                with c1:
                    st.write("**Ticket Distribution by L4**")
                    st.bar_chart(filtered_df['L4'].value_counts().head(10))
                with c2:
                    st.write("**Top 10 Cities**")
                    st.dataframe(filtered_df['City'].value_counts().head(10), use_container_width=True)

        with t_cee_sum:
            st.subheader("CEE Aging Summary (Aggregated)")
            group_cee = ['CEE_ID', 'CEE_Name', 'Hub', 'City']
            if selected_l4: group_cee.append('L4')
            if not filtered_df.empty:
                cee_table = generate_aging_report(filtered_df, group_cee, end_date)
                st.dataframe(cee_table.sort_values(by='Range_Total', ascending=False), use_container_width=True)

        with t_cee_over:
            st.subheader("CEE Detailed Raw Data")
            view_cols = ['Date', 'CEE_ID', 'CEE_Name', 'Hub', 'Member_Id', 'L4', 'L5', 'Status']
            st.dataframe(filtered_df[view_cols].sort_values(by='Date', ascending=False), use_container_width=True)

        with t_cust_sum:
            st.subheader("Customer Aging Summary (Aggregated)")
            group_cust = ['Member_Id', 'City', 'VIP']
            if selected_l4: group_cust.append('L4')
            if not filtered_df.empty:
                cust_table = generate_aging_report(filtered_df, group_cust, end_date)
                st.dataframe(cust_table.sort_values(by='Range_Total', ascending=False), use_container_width=True)

        with t_cust_over:
            st.subheader("Customer Detailed Raw Data")
            view_cols_cust = ['Date', 'Member_Id', 'City', 'VIP', 'Hub', 'L4', 'L5', 'Status']
            st.dataframe(filtered_df[view_cols_cust].sort_values(by='Date', ascending=False), use_container_width=True)

    else:
        st.error("No valid 'bbdaily-b2c' data found for the selected filters.")
else:
    st.info("Upload CSV files to begin. System will automatically filter for 'bbdaily-b2c' records.")
