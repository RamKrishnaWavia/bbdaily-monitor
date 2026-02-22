import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io

# --- 1. PAGE CONFIGURATION & AGGRESSIVE UI STYLING ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower", page_icon="🛡️")

# Force Global Center Alignment via CSS
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    
    /* Center align data and headers for the modern Streamlit Dataframe */
    [data-testid="stDataFrame"] div[role="gridcell"] > div {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
    }
    [data-testid="stDataFrame"] th {
        text-align: center !important;
        vertical-align: middle !important;
        background-color: #f1f3f6 !important;
        font-weight: bold !important;
    }

    /* Professional Banner & Layout fixes */
    .stDataFrame { padding-right: 50px !important; border-radius: 10px; }
    
    .availability-banner {
        background-color: #e3f2fd;
        color: #0d47a1;
        padding: 18px;
        border-radius: 12px;
        border-left: 8px solid #1976d2;
        font-weight: bold;
        margin-bottom: 25px;
        text-align: center;
        font-size: 16px;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] { background-color: #f1f3f6; width: 350px !important; }
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
            # Handle encodings
            try:
                temp_df = pd.read_csv(file, encoding='utf-8', low_memory=False)
            except:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1', low_memory=False)
            
            # Cleanup headers
            temp_df.columns = temp_df.columns.str.strip()
            temp_df['Source_CSV'] = file.name
            
            # --- DATE PARSING (DD-MM-YYYY) ---
            date_priority = ['Complaint Created Date & Time', 'Created Date', 'Date', 'date']
            date_col = next((c for c in date_priority if c in temp_df.columns), None)
            
            if date_col:
                # FORCE dayfirst=True for DD-MM-YYYY format
                temp_df['Date_Parsed'] = pd.to_datetime(temp_df[date_col], dayfirst=True, errors='coerce')
                temp_df = temp_df.dropna(subset=['Date_Parsed'])
                temp_df['Date'] = temp_df['Date_Parsed'].dt.date
            
            # --- COMPREHENSIVE COLUMN MAPPING (Including your Raw Headers) ---
            col_map = {
                'Lob': ['Lob', 'LOB', 'Line of Business'],
                'Ticket_ID': ['Ticket ID', 'Complaint ID', 'Ticket Number'],
                'L4': ['Agent Disposition Levels 4', 'Level 4', 'Category'],
                'L5': ['Agent Disposition Levels 5', 'Level 5', 'Sub Category'],
                'CEE_Name': ['Cee Name', 'CEE NAME', 'Delivery Executive'],
                'CEE_ID': ['CEE Number', 'CEE ID', 'DE ID', 'cee_id'],
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
                    # Clean up ID columns
                    for col in ['CEE_Name', 'CEE_ID', 'Ticket_ID', 'Member_Id']:
                        if col in temp_df.columns:
                            temp_df[col] = temp_df[col].astype(str).replace(['nan', '0', '0.0', 'None'], 'Unknown').str.strip()
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Critical Error in File {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        
        # --- 3. SIDEBAR CONTROLS ---
        st.sidebar.header("🎛️ Control Panel")
        search_id = st.sidebar.text_input("🔍 Search (Ticket/CEE/Member)", "").strip()
        
        col_d1, col_d2 = st.sidebar.columns(2)
        with col_d1:
            start_date = st.sidebar.date_input("From Date", df['Date'].min())
        with col_d2:
            end_date = st.sidebar.date_input("To Date", df['Date'].max())
        
        st.sidebar.subheader("Grouping Options")
        g_l4 = st.sidebar.checkbox("Show Agent L4", value=True)
        g_l5 = st.sidebar.checkbox("Show Agent L5", value=False)

        # Apply Filters
        f_df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]
        if search_id:
            f_df = f_df[(f_df['Ticket_ID'].str.contains(search_id, case=False)) | 
                        (f_df['CEE_ID'].str.contains(search_id, case=False)) | 
                        (f_df['Member_Id'].str.contains(search_id, case=False))]

        # --- 4. ENGINE FUNCTIONS ---
        def generate_report(data, groups, s_date, e_date, include_daily=False):
            # Dynamic group validation to prevent KeyError
            available_groups = [g for g in groups if g in data.columns]
            
            if data.empty:
                return pd.DataFrame(columns=available_groups + ['Range_Total'])
            
            report = data.groupby(available_groups).size().reset_index(name='Range_Total')
            
            # Aging Logic
            buckets = [("0-5 Days", 0, 5), ("5-10 Days", 6, 10), ("10-15 Days", 11, 15), ("15-30 Days", 16, 30)]
            for label, s_off, e_off in buckets:
                b_end, b_start = e_date - timedelta(days=s_off), e_date - timedelta(days=e_off)
                b_data = data[(data['Date'] >= b_start) & (data['Date'] <= b_end)]
                if not b_data.empty:
                    b_counts = b_data.groupby(available_groups).size().reset_index(name=label)
                    report = report.merge(b_counts, on=available_groups, how='left').fillna(0)
                else:
                    report[label] = 0
            
            if include_daily:
                curr = s_date
                while curr <= e_date:
                    d_str = curr.strftime('%d-%b')
                    day_data = data[data['Date'] == curr]
                    if not day_data.empty:
                        d_counts = day_data.groupby(available_groups).size().reset_index(name=d_str)
                        report = report.merge(d_counts, on=available_groups, how='left').fillna(0)
                    else:
                        report[d_str] = 0
                    curr += timedelta(days=1)
            
            # Final numeric conversion
            for c in report.columns.difference(available_groups):
                report[c] = report[c].astype(int)
            return report

        def style_and_show(data, key):
            if data.empty:
                st.warning("No data found for selected criteria.")
                return
            st.dataframe(data, use_container_width=True)
            csv = data.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Download CSV", data=csv, file_name=f"{key}.csv", key=f"dl_{key}")

        # --- 5. TABS ---
        t_dash, t_cee, t_cust = st.tabs(["📊 Performance Dashboard", "👤 CEE Analysis", "🛒 Customer Analysis"])
        
        c_groups = ['CEE_ID', 'CEE_Name', 'Hub', 'City']
        if g_l4: c_groups.append('L4')
        if g_l5: c_groups.append('L5')

        with t_dash:
            if not f_df.empty:
                min_d, max_d = f_df['Date'].min().strftime('%d-%b-%Y'), f_df['Date'].max().strftime('%d-%b-%Y')
                st.markdown(f'<div class="availability-banner">📅 Data Available From {min_d} To {max_d}</div>', unsafe_allow_html=True)
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Complaints", len(f_df))
                c2.metric("Active CEEs", f_df['CEE_ID'].nunique())
                c3.metric("Impacted Customers", f_df['Member_Id'].nunique())
                
                st.markdown("---")
                st.write("**Data Source Audit Tracking**")
                style_and_show(f_df.groupby(['Source_CSV', 'Date']).size().reset_index(name='Rows').sort_values('Date'), "source_audit")

        with t_cee:
            res = generate_report(f_df, c_groups, start_date, end_date, True)
            style_and_show(res.sort_values('Range_Total', ascending=False), "cee_summary")

        with t_cust:
            m_groups = ['Member_Id', 'City', 'Hub', 'VIP']
            if g_l4: m_groups.append('L4')
            style_and_show(generate_report(f_df, m_groups, start_date, end_date), "cust_summary")

else:
    st.info("System Ready. Upload CSV files containing 'Agent Disposition Levels 4/5'.")
