import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io

# --- 1. PAGE CONFIGURATION & DEEP UI STYLING ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower", page_icon="🛡️")

# Injected CSS for center alignment, table visibility, and professional metrics
st.markdown("""
    <style>
    /* Main Background and Font */
    .main { background-color: #f8f9fa; }
    
    /* Center Align all Table Cells and Headers */
    [data-testid="stTable"] td, [data-testid="stTable"] th {
        text-align: center !important;
    }
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th {
        text-align: center !important;
        vertical-align: middle !important;
    }
    
    /* Metric Card Styling */
    [data-testid="stMetricValue"] {
        font-size: 32px;
        font-weight: bold;
        text-align: center;
        color: #1f77b4;
    }
    [data-testid="stMetricLabel"] {
        text-align: center;
        font-size: 16px;
    }

    /* Fix for last column visibility and horizontal scroll */
    .stDataFrame div[data-testid="stHorizontalBlock"] {
        padding-right: 30px;
    }
    
    /* Styling the sidebar */
    section[data-testid="stSidebar"] {
        background-color: #f1f3f6;
        width: 350px !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.markdown("---")

# --- 2. MULTI-FILE UPLOADER & PROCESSING ---
uploaded_files = st.file_uploader("📂 Upload Complaint Dump (CSV Files)", type="csv", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    
    for file in uploaded_files:
        try:
            # Handle encodings - UTF-8 or Excel-Specific ISO
            try:
                temp_df = pd.read_csv(file, encoding='utf-8', low_memory=False)
            except:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1', low_memory=False)
            
            # Record source file and clean column whitespace
            temp_df['Source_CSV'] = file.name
            temp_df.columns = temp_df.columns.str.strip()
            
            # --- ROBUST DATE PARSING (FORCED DD-MM-YYYY) ---
            # Prioritizing your specific column: "Complaint Created Date & Time"
            date_priority = ['Complaint Created Date & Time', 'Created Date', 'Date', 'date', 'Complaint Date']
            date_col = None
            for candidate in date_priority:
                if candidate in temp_df.columns:
                    date_col = candidate
                    break
            
            if date_col:
                # FORCE dayfirst=True to stop 01-02 being Jan 2nd (Fixed the Jan data mystery)
                temp_df['Date_Parsed'] = pd.to_datetime(temp_df[date_col], dayfirst=True, errors='coerce')
                # Remove unparseable dates to maintain integrity
                temp_df = temp_df.dropna(subset=['Date_Parsed'])
                temp_df['Date'] = temp_df['Date_Parsed'].dt.date
            
            # --- COMPREHENSIVE COLUMN MAPPING ---
            col_map = {
                'Lob': ['Lob', 'LOB', 'lob', 'Line of Business'],
                'Ticket_ID': ['Ticket ID', 'Complaint ID', 'Complaint Number', 'Ticket Number', 'id'],
                'L4': ['Level 4', 'Agent Disposition Levels 4', 'Category', 'L4 Category'],
                'L5': ['Level 5', 'Agent Disposition Levels 5', 'Sub Category'],
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
                    # Final string cleanup for IDs
                    def clean_val(val):
                        v = str(val).strip()
                        return v if v not in ['', 'nan', '-', 'None', '0', '0.0'] else "Unknown"

                    temp_df['CEE_Name'] = temp_df['CEE_Name_1'].apply(clean_val)
                    temp_df['CEE_ID'] = temp_df['CEE_ID_1'].apply(clean_val)
                    temp_df['Ticket_ID'] = temp_df['Ticket_ID'].apply(clean_val)
                    temp_df['Member_Id'] = temp_df['Member_Id'].apply(clean_val)
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Critical Error in File {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        
        # --- 3. SIDEBAR CONTROLS ---
        st.sidebar.header("🎛️ Dashboard Control Panel")
        st.sidebar.markdown("---")
        
        # Integrated Search Logic (Ticket/CEE/Member)
        st.sidebar.subheader("🔍 Integrated Search")
        search_id = st.sidebar.text_input("Enter ID (Ticket/CEE/Member)", "").strip()
        
        # Global Date Range
        col_d1, col_d2 = st.sidebar.columns(2)
        with col_d1:
            start_date = st.sidebar.date_input("From", df['Date'].min())
        with col_d2:
            end_date = st.sidebar.date_input("To", df['Date'].max())
        
        # Geographic Filters
        selected_cities = st.sidebar.multiselect("Select City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        selected_hubs = st.sidebar.multiselect("Select Store (Hub)", sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()), default=sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()))
        
        # Dynamic Grouping Control
        st.sidebar.subheader("Table Grouping Options")
        group_by_l4 = st.sidebar.checkbox("Show L4 Category", value=True)
        group_by_l5 = st.sidebar.checkbox("Show L5 Category", value=False)

        # Apply Master Mask
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date) & (df['City'].isin(selected_cities)) & (df['Hub'].isin(selected_hubs))
        f_df = df[mask]
        
        # Search Filter (Cross-column)
        if search_id:
            f_df = f_df[
                (f_df['Ticket_ID'].astype(str).str.contains(search_id, case=False)) |
                (f_df['CEE_ID'].astype(str).str.contains(search_id, case=False)) |
                (f_df['Member_Id'].astype(str).str.contains(search_id, case=False))
            ]

        # --- 4. AGGREGATION ENGINE (AGING & MATRIX) ---
        def generate_report(data, groups, s_date, e_date, include_daily=False):
            # Safety Guard: If no data, return template with correct columns to prevent Sort Errors
            if data.empty:
                return pd.DataFrame(columns=groups + ['Range_Total'])
            
            report = data.groupby(groups).size().reset_index(name='Range_Total')
            
            # Rolling Aging Buckets
            buckets = [("0-5 Days", 0, 5), ("5-10 Days", 6, 10), ("10-15 Days", 11, 15), ("15-30 Days", 16, 30)]
            for label, s_off, e_off in buckets:
                b_end, b_start = e_date - timedelta(days=s_off), e_date - timedelta(days=e_off)
                b_counts = data[(data['Date'] >= b_start) & (data['Date'] <= b_end)].groupby(groups).size().reset_index(name=label)
                report = report.merge(b_counts, on=groups, how='left').fillna(0)
            
            # Daily Frequency Matrix
            if include_daily:
                curr = s_date
                while curr <= e_date:
                    d_str = curr.strftime('%d-%b')
                    day_data = data[data['Date'] == curr].groupby(groups).size().reset_index(name=d_str)
                    report = report.merge(day_data, on=groups, how='left').fillna(0)
                    curr += timedelta(days=1)
            
            # Ensure all numerical columns are Integers
            numeric_cols = report.columns.difference(groups)
            report[numeric_cols] = report[numeric_cols].astype(int)
            return report

        # --- 5. TABBED INTERFACE ---
        t_dash, t_cee_sum, t_cee_det, t_cust_sum, t_cust_det = st.tabs([
            "📊 Dashboard", "👤 CEE Summary", "🔍 CEE Detailed", "🛒 Customer Summary", "🔎 Customer Detailed"
        ])

        # Define Dynamic Headers
        base_groups = ['CEE_ID', 'CEE_Name', 'Hub', 'City']
        if group_by_l4: base_groups.append('L4')
        if group_by_l5: base_groups.append('L5')
        
        cust_groups = ['Member_Id', 'City', 'Hub', 'VIP']
        if group_by_l4: cust_groups.append('L4')
        if group_by_l5: cust_groups.append('L5')

        with t_dash:
            st.subheader("Executive Stats & File Integrity Audit")
            if not f_df.empty:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Complaints", len(f_df))
                m2.metric("Active CEEs", f_df['CEE_ID'].nunique())
                m3.metric("Impacted Customers", f_df['Member_Id'].nunique())
                m4.metric("Average/Day", round(len(f_df)/max((end_date-start_date).days, 1), 1))
                
                st.markdown("---")
                st.write("**File Source Verification (Identify January Row Sources)**")
                source_check = f_df.groupby(['Source_CSV', 'Date']).size().reset_index(name='Rows')
                st.dataframe(source_check.sort_values(['Date', 'Source_CSV']), use_container_width=True)
            else:
                st.warning("No data found for the selected range. Check 'Lob' or Date format.")

        with t_cee_sum:
            res_cee = generate_report(f_df, base_groups, start_date, end_date, False)
            if not res_cee.empty:
                st.dataframe(res_cee.sort_values('Range_Total', ascending=False), use_container_width=True)

        with t_cee_det:
            res_cee_d = generate_report(f_df, base_groups + ['Ticket_ID', 'Date', 'Source_CSV'], start_date, end_date, True)
            if not res_cee_d.empty:
                st.dataframe(res_cee_d.sort_values('Date', ascending=False), use_container_width=True)

        with t_cust_sum:
            res_cust = generate_report(f_df, cust_groups, start_date, end_date, False)
            if not res_cust.empty:
                st.dataframe(res_cust.sort_values('Range_Total', ascending=False), use_container_width=True)

        with t_cust_det:
            res_cust_d = generate_report(f_df, cust_groups + ['Ticket_ID', 'Date', 'Source_CSV'], start_date, end_date, True)
            if not res_cust_d.empty:
                st.dataframe(res_cust_d.sort_values('Date', ascending=False), use_container_width=True)
            
    else:
        st.error("No valid bbdaily-b2c data found in the uploaded files.")
else:
    st.info("System Ready. Please upload one or more CSV files to start the integrity analysis.")
