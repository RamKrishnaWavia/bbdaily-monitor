import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io

# --- 1. PAGE CONFIGURATION & STYLING ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower", page_icon="🛡️")

# Custom CSS to improve UI professional look and table readability
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 10px; }
    .css-10trblm { color: #FF4B4B; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.info("System Status: Strict DD-MM-YYYY Date Parsing | Multi-ID Search | File Source Auditing")

# --- 2. MULTI-FILE UPLOADER ---
uploaded_files = st.file_uploader("📂 Upload Complaint Dump (CSV Files)", type="csv", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    
    for file in uploaded_files:
        try:
            # Handle encodings (UTF-8 or ISO-8859-1)
            try:
                temp_df = pd.read_csv(file, encoding='utf-8', low_memory=False)
            except:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1', low_memory=False)
            
            # Record source file for verification
            temp_df['Source_CSV'] = file.name
            temp_df.columns = temp_df.columns.str.strip()
            
            # --- STRICT DATE LOCK LOGIC (DD-MM-YYYY) ---
            # Prioritize 'Complaint Created Date & Time'
            date_priority = ['Complaint Created Date & Time', 'Created Date', 'Date', 'date']
            date_col = None
            for candidate in date_priority:
                if candidate in temp_df.columns:
                    date_col = candidate
                    break
            
            if date_col:
                # Force dayfirst=True to ensure 01-02 is Feb 1st, NOT Jan 2nd
                temp_df['Date_Parsed'] = pd.to_datetime(
                    temp_df[date_col], 
                    dayfirst=True, 
                    errors='coerce'
                )
                
                # Cleanup rows with unparseable dates
                temp_df = temp_df.dropna(subset=['Date_Parsed'])
                temp_df['Date'] = temp_df['Date_Parsed'].dt.date
            
            # --- COMPREHENSIVE COLUMN MAPPING ---
            col_map = {
                'Lob': ['Lob', 'LOB', 'lob', 'Line of Business'],
                'Ticket_ID': ['Ticket ID', 'Complaint ID', 'Complaint Number', 'Ticket Number', 'id'],
                'L4': ['Level 4', 'Agent Disposition Levels 4', 'Category', 'L4 Category'],
                'L5': ['Level 5', 'Agent Disposition Levels 5', 'Sub Category', 'L5 Category'],
                'CEE_Name_1': ['Cee Name', 'Cee name', 'CEE NAME', 'Delivery Executive'],
                'CEE_ID_1': ['CEE Number', 'cee_number', 'CEE ID', 'cee_id', 'DE ID'],
                'Member_Id': ['Member Id', 'member_id', 'Member ID', 'Customer ID'],
                'Hub': ['Hub', 'HUB', 'hub', 'FC NAME', 'Hub Name', 'Store'],
                'City': ['City', 'CITY', 'city'],
                'VIP': ['Is VIP Customer', 'vip', 'VIP Tag', 'VIP Status']
            }
            
            for standard, options in col_map.items():
                for opt in options:
                    if opt in temp_df.columns:
                        temp_df[standard] = temp_df[opt]
                        break
            
            # --- THUMB RULE: bbdaily-b2c ONLY ---
            if 'Lob' in temp_df.columns:
                temp_df = temp_df[temp_df['Lob'].astype(str).str.contains('bbdaily-b2c', case=False, na=False)].copy()
                
                if not temp_df.empty and 'Date' in temp_df.columns:
                    # Utility function for cleaning data noise
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
            else:
                st.warning(f"File {file.name} ignored: 'Lob' column missing.")
        except Exception as e:
            st.error(f"Critical Error processing {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        
        # --- 3. SIDEBAR CONTROLS ---
        st.sidebar.header("🎛️ Control Panel")
        st.sidebar.markdown("---")
        
        # Integrated Search Feature
        st.sidebar.subheader("🔍 Multi-ID Search")
        search_id = st.sidebar.text_input("Enter Ticket, CEE, or Member ID", "").strip()
        
        # Date Logic
        col_d1, col_d2 = st.sidebar.columns(2)
        with col_d1:
            start_date = st.sidebar.date_input("Date From", df['Date'].min())
        with col_d2:
            end_date = st.sidebar.date_input("Date To", df['Date'].max())
        
        # Geographic Filters
        selected_cities = st.sidebar.multiselect("City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        selected_hubs = st.sidebar.multiselect("Store (Hub)", sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()), default=sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()))
        
        # Grouping Control
        st.sidebar.subheader("Detailed Grouping")
        group_by_l4 = st.sidebar.checkbox("Show Level 4 Category", value=True)
        group_by_l5 = st.sidebar.checkbox("Show Level 5 Category", value=False)

        # APPLY GLOBAL FILTERS
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date) & (df['City'].isin(selected_cities)) & (df['Hub'].isin(selected_hubs))
        filtered_df = df[mask]
        
        if search_id:
            filtered_df = filtered_df[
                (filtered_df['Ticket_ID'].astype(str).str.contains(search_id, case=False)) |
                (filtered_df['CEE_ID'].astype(str).str.contains(search_id, case=False)) |
                (filtered_df['Member_Id'].astype(str).str.contains(search_id, case=False))
            ]

        # --- 4. ANALYTICS ENGINE ---
        def generate_report(data, groups, s_date, e_date, include_daily=False):
            if data.empty: return pd.DataFrame()
            report = data.groupby(groups).size().reset_index(name='Range_Total')
            
            # Aging Buckets (Reference point is End Date)
            buckets = [("0-5 Days", 0, 5), ("5-10 Days", 6, 10), ("10-15 Days", 11, 15), ("15-30 Days", 16, 30)]
            for label, s_off, e_off in buckets:
                b_end, b_start = e_date - timedelta(days=s_off), e_date - timedelta(days=e_off)
                b_counts = data[(data['Date'] >= b_start) & (data['Date'] <= b_end)].groupby(groups).size().reset_index(name=label)
                report = report.merge(b_counts, on=groups, how='left').fillna(0)
            
            # Daily Matrix Generation
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

        # --- 5. TABS & VISUALIZATION ---
        t_perf, t_cee_sum, t_cee_over, t_cust_sum, t_cust_over = st.tabs([
            "📊 Executive Dashboard", "👤 CEE Summary", "🔍 CEE Detailed", "🛒 Customer Summary", "🔎 Customer Detailed"
        ])

        # Define Dynamic Grouping Fields
        cee_groups = ['CEE_ID', 'CEE_Name', 'Hub', 'City']
        if group_by_l4: cee_groups.append('L4')
        if group_by_l5: cee_groups.append('L5')
        
        cust_groups = ['Member_Id', 'City', 'Hub', 'VIP']
        if group_by_l4: cust_groups.append('L4')
        if group_by_l5: cust_groups.append('L5')

        with t_perf:
            st.subheader("Complaint Trends & Source Integrity")
            if not filtered_df.empty:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Tickets", f"{len(filtered_df):,}")
                col2.metric("Active CEEs", filtered_df['CEE_ID'].nunique())
                col3.metric("Impacted Customers", filtered_df['Member_Id'].nunique())
                col4.metric("Avg Daily Volume", round(len(filtered_df)/max((end_date-start_date).days, 1), 1))
                
                st.markdown("---")
                st.write("**File Upload Audit (Verify Date Ranges by File Name)**")
                file_summary = filtered_df.groupby(['Source_CSV', 'Date']).size().reset_index(name='Rows')
                st.dataframe(file_summary.sort_values(['Date', 'Source_CSV']), use_container_width=True)
                st.line_chart(filtered_df.groupby('Date').size())

        with t_cee_sum:
            st.subheader("CEE Aging Performance")
            res_cee = generate_report(filtered_df, cee_groups, start_date, end_date, False)
            st.dataframe(res_cee.sort_values('Range_Total', ascending=False), use_container_width=True)

        with t_cee_over:
            st.subheader("CEE Audit (Includes Ticket IDs)")
            res_cee_over = generate_report(filtered_df, cee_groups + ['Ticket_ID', 'Date', 'Source_CSV'], start_date, end_date, True)
            st.dataframe(res_cee_over.sort_values('Date', ascending=False), use_container_width=True)

        with t_cust_sum:
            st.subheader("Customer Frequent Complaint Summary")
            res_cust = generate_report(filtered_df, cust_groups, start_date, end_date, False)
            st.dataframe(res_cust.sort_values('Range_Total', ascending=False), use_container_width=True)

        with t_cust_over:
            st.subheader("Customer Fraud Audit (Full History)")
            res_cust_over = generate_report(filtered_df, cust_groups + ['Ticket_ID', 'Date', 'Source_CSV'], start_date, end_date, True)
            st.dataframe(res_cust_over.sort_values('Date', ascending=False), use_container_width=True)
            
    else:
        st.error("No valid bbdaily-b2c records found. Please check date format (DD-MM-YYYY) and filters.")
else:
    st.info("System Ready. Please upload CSV files to begin analytics.")
