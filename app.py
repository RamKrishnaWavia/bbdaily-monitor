import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io

# --- 1. PAGE CONFIGURATION & AGGRESSIVE UI STYLING ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower", page_icon="🛡️")

# Force Global Alignment via Aggressive CSS Injection
st.markdown("""
    <style>
    /* Main Background */
    .main { background-color: #f8f9fa; }
    
    /* Aggressive Center Alignment for all DataFrames */
    div[data-testid="stDataFrame"] div[role="gridcell"] > div {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
    }
    
    /* Center align headers */
    [data-testid="stDataFrame"] th {
        text-align: center !important;
        vertical-align: middle !important;
        background-color: #f1f3f6 !important;
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

    /* Fix for last column visibility and horizontal padding */
    .stDataFrame {
        padding-right: 40px !important;
    }

    /* Availability Banner Styling */
    .availability-banner {
        background-color: #e1f5fe;
        color: #01579b;
        padding: 18px;
        border-radius: 12px;
        border-left: 6px solid #0288d1;
        font-weight: bold;
        margin-bottom: 25px;
        text-align: center;
        font-size: 18px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
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

# --- 2. MULTI-FILE UPLOADER & ROBUST PROCESSING ---
uploaded_files = st.file_uploader("📂 Upload Complaint Dump (CSV Files)", type="csv", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    
    for file in uploaded_files:
        try:
            # Handle encodings - UTF-8 or ISO-8859-1
            try:
                temp_df = pd.read_csv(file, encoding='utf-8', low_memory=False)
            except:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1', low_memory=False)
            
            # Record source file and clean column whitespace
            temp_df['Source_CSV'] = file.name
            temp_df.columns = temp_df.columns.str.strip()
            
            # --- ROBUST DATE PARSING (FORCED DD-MM-YYYY) ---
            date_priority = ['Complaint Created Date & Time', 'Created Date', 'Date', 'date', 'Complaint Date']
            date_col = next((c for c in date_priority if c in temp_df.columns), None)
            
            if date_col:
                # FORCE dayfirst=True to ensure 01-02 is Feb 1st
                temp_df['Date_Parsed'] = pd.to_datetime(temp_df[date_col], dayfirst=True, errors='coerce')
                temp_df = temp_df.dropna(subset=['Date_Parsed'])
                temp_df['Date'] = temp_df['Date_Parsed'].dt.date
            
            # --- COMPREHENSIVE COLUMN MAPPING ---
            col_map = {
                'Lob': ['Lob', 'LOB', 'lob', 'Line of Business'],
                'Ticket_ID': ['Ticket ID', 'Complaint ID', 'Ticket Number', 'id'],
                'L4': ['Level 4', 'Agent Disposition Levels 4', 'Category'],
                'L5': ['Level 5', 'Agent Disposition Levels 5', 'Sub Category'],
                'CEE_Name_1': ['Cee Name', 'CEE NAME', 'Delivery Executive'],
                'CEE_ID_1': ['CEE Number', 'CEE ID', 'DE ID'],
                'Member_Id': ['Member Id', 'Member ID', 'Customer ID'],
                'Hub': ['Hub', 'HUB', 'FC NAME', 'Hub Name', 'Store'],
                'City': ['City', 'CITY'],
                'VIP': ['Is VIP Customer', 'VIP Tag', 'VIP Status']
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
                    for col in ['CEE_Name', 'CEE_ID', 'Ticket_ID', 'Member_Id']:
                        orig_col = col + '_1' if col + '_1' in temp_df.columns else col
                        temp_df[col] = temp_df[orig_col].astype(str).replace(['nan', '0', '0.0', 'None'], 'Unknown').str.strip()
                    
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Critical Error in File {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        
        # --- 3. SIDEBAR CONTROLS ---
        st.sidebar.header("🎛️ Control Panel")
        st.sidebar.markdown("---")
        
        search_id = st.sidebar.text_input("🔍 Integrated Search (Ticket/CEE/Member)", "").strip()
        
        col_d1, col_d2 = st.sidebar.columns(2)
        with col_d1:
            start_date = st.sidebar.date_input("From Date", df['Date'].min())
        with col_d2:
            end_date = st.sidebar.date_input("To Date", df['Date'].max())
        
        selected_cities = st.sidebar.multiselect("Select City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        selected_hubs = st.sidebar.multiselect("Select Hub", sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()), default=sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()))
        
        st.sidebar.subheader("Grouping Control")
        group_by_l4 = st.sidebar.checkbox("Show L4 Category", value=True)
        group_by_l5 = st.sidebar.checkbox("Show L5 Category", value=False)

        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date) & (df['City'].isin(selected_cities)) & (df['Hub'].isin(selected_hubs))
        f_df = df[mask]
        
        if search_id:
            f_df = f_df[(f_df['Ticket_ID'].str.contains(search_id, case=False)) | 
                        (f_df['CEE_ID'].str.contains(search_id, case=False)) | 
                        (f_df['Member_Id'].str.contains(search_id, case=False))]

        # --- 4. ENGINE FUNCTIONS ---
        def style_and_show(data):
            if data.empty:
                st.warning("No data found for the selected range.")
                return
            
            # Using simple dataframe first to ensure no module errors
            # We apply the centering via the CSS injected in Step 1
            st.dataframe(data, use_container_width=True)
            
            # CSV Download as fallback to prevent xlsxwriter errors
            csv = data.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Download This Table (CSV)", data=csv, file_name=f"report_{datetime.now().strftime('%Y%m%d')}.csv", mime='text/csv')

        def generate_report(data, groups, s_date, e_date, include_daily=False):
            if data.empty: 
                return pd.DataFrame(columns=groups + ['Range_Total'])
            
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
            
            for c in report.columns.difference(groups): 
                report[c] = report[c].astype(int)
            return report

        # --- 5. TABS ---
        t_dash, t_cee_s, t_cee_d, t_cust_s, t_cust_d = st.tabs([
            "📊 Dashboard", "👤 CEE Summary", "🔍 CEE Detailed", "🛒 Customer Summary", "🔎 Customer Detailed"
        ])

        c_groups = ['CEE_ID', 'CEE_Name', 'Hub', 'City']
        if group_by_l4: c_groups.append('L4')
        if group_by_l5: c_groups.append('L5')
        
        m_groups = ['Member_Id', 'City', 'Hub', 'VIP']
        if group_by_l4: m_groups.append('L4')
        if group_by_l5: m_groups.append('L5')

        with t_dash:
            if not f_df.empty:
                min_d, max_d = f_df['Date'].min().strftime('%d-%b-%Y'), f_df['Date'].max().strftime('%d-%b-%Y')
                st.markdown(f'<div class="availability-banner">📅 Data Range Detected: {min_d} to {max_d}</div>', unsafe_allow_html=True)
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Tickets", len(f_df))
                c2.metric("Unique CEEs", f_df['CEE_ID'].nunique())
                c3.metric("Unique Customers", f_df['Member_Id'].nunique())
                
                st.markdown("---")
                st.write("**File Source Verification Table**")
                style_and_show(f_df.groupby(['Source_CSV', 'Date']).size().reset_index(name='Rows').sort_values('Date'))

        with t_cee_s:
            res = generate_report(f_df, c_groups, start_date, end_date)
            style_and_show(res.sort_values('Range_Total', ascending=False) if not res.empty else res)
            
        with t_cee_d:
            res = generate_report(f_df, c_groups + ['Ticket_ID', 'Date', 'Source_CSV'], start_date, end_date, True)
            style_and_show(res.sort_values('Date', ascending=False) if not res.empty else res)

        with t_cust_s:
            res = generate_report(f_df, m_groups, start_date, end_date)
            style_and_show(res.sort_values('Range_Total', ascending=False) if not res.empty else res)

        with t_cust_d:
            res = generate_report(f_df, m_groups + ['Ticket_ID', 'Date', 'Source_CSV'], start_date, end_date, True)
            style_and_show(res.sort_values('Date', ascending=False) if not res.empty else res)

else:
    st.info("System Ready. Upload CSV files. Date format DD-MM-YYYY is strictly enforced.")
