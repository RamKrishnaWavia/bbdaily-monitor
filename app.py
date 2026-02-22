import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower")
pd.set_option('future.no_silent_downcasting', True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.info("Logic: Ticket-Level Verification in Overviews | Aging Summaries | bbdaily-b2c")

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
                'Ticket_ID': ['Ticket ID', 'Complaint ID', 'Complaint Number', 'Ticket Number', 'id'],
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
        
        # --- 3. SIDEBAR ---
        st.sidebar.header("🎛️ Control Panel")
        start_date = st.sidebar.date_input("Date From", df['Date'].min())
        end_date = st.sidebar.date_input("Date To", df['Date'].max())
        
        selected_cities = st.sidebar.multiselect("City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        selected_hubs = st.sidebar.multiselect("Store (Hub)", sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()), default=sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()))
        
        st.sidebar.subheader("Grouping Toggle")
        group_by_l4 = st.sidebar.checkbox("Group by Level 4", value=True)
        group_by_l5 = st.sidebar.checkbox("Group by Level 5", value=False)

        selected_l4 = st.sidebar.multiselect("L4 Filter", sorted(df['L4'].unique()))
        selected_l5 = st.sidebar.multiselect("L5 Filter", sorted(df['L5'].unique()))

        # Filter Logic
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date) & (df['City'].isin(selected_cities)) & (df['Hub'].isin(selected_hubs))
        f_df = df[mask]
        if selected_l4: f_df = f_df[f_df['L4'].isin(selected_l4)]
        if selected_l5: f_df = f_df[f_df['L5'].isin(selected_l5)]

        # --- 4. AGGREGATION ENGINE ---
        def generate_report(data, groups, e_date, include_daily=False):
            report = data.groupby(groups).size().reset_index(name='Range_Total')
            buckets = [("0-5 Days", 0, 5), ("5-10 Days", 6, 10), ("10-15 Days", 11, 15), ("15-30 Days", 16, 30)]
            for label, s_off, e_off in buckets:
                b_end, b_start = e_date - timedelta(days=s_off), e_date - timedelta(days=e_off)
                b_counts = data[(data['Date'] >= b_start) & (data['Date'] <= b_end)].groupby(groups).size().reset_index(name=label)
                report = report.merge(b_counts, on=groups, how='left').fillna(0)
            
            if include_daily:
                curr = start_date
                while curr <= end_date:
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
            st.subheader("High-Level Statistics")
            c1, c2, c3 = st.columns(3)
            c1.metric("Tickets", len(f_df))
            c2.metric("CEEs", f_df['CEE_ID'].nunique())
            c3.metric("Customers", f_df['Member_Id'].nunique())
            st.bar_chart(f_df['L4'].value_counts().head(10))

        with t_cee_sum:
            st.subheader("CEE Aging Summary")
            st.dataframe(generate_report(f_df, cee_groups, end_date, False).sort_values('Range_Total', ascending=False), use_container_width=True)

        with t_cee_over:
            st.subheader("CEE Detailed - Ticket IDs Included")
            # We add Ticket_ID to the grouping ONLY for this view for verification
            cee_groups_over = cee_groups + ['Ticket_ID', 'Date']
            st.dataframe(generate_report(f_df, cee_groups_over, end_date, True).sort_values('Date', ascending=False), use_container_width=True)

        with t_cust_sum:
            st.subheader("Customer Aging Summary")
            st.dataframe(generate_report(f_df, cust_groups, end_date, False).sort_values('Range_Total', ascending=False), use_container_width=True)

        with t_cust_over:
            st.subheader("Customer Detailed - Ticket IDs Included")
            cust_groups_over = cust_groups + ['Ticket_ID', 'Date']
            st.dataframe(generate_report(f_df, cust_groups_over, end_date, True).sort_values('Date', ascending=False), use_container_width=True)

    else:
        st.error("No valid 'bbdaily-b2c' data found.")
else:
    st.info("Upload CSV files to begin. Verification columns are active in Overview tabs.")
