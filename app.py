import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io

# --- 1. PAGE CONFIGURATION & LAYOUT ---
st.set_page_config(
    layout="wide", 
    page_title="bbdaily Integrity Master Tower", 
    page_icon="🛡️"
)

# --- 2. UI STYLING ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    [data-testid="stDataFrame"] div[role="gridcell"] > div,
    [data-testid="stDataFrame"] div[role="columnheader"] > div {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
    }
    .availability-banner {
        background-color: #e3f2fd; 
        color: #0d47a1; 
        padding: 20px;
        border-radius: 12px; 
        border-left: 8px solid #1976d2;
        font-weight: bold; 
        margin-bottom: 25px; 
        text-align: center; 
        font-size: 18px;
    }
    section[data-testid="stSidebar"] { width: 400px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower")
st.markdown("---")

# --- 3. EXCEL DATA ENGINE ---
uploaded_files = st.file_uploader("📂 Upload Complaint Dump (Excel Files)", type=["xlsx", "xls", "csv"], accept_multiple_files=True)

if uploaded_files:
    all_data = []
    
    for file in uploaded_files:
        try:
            # Handle both CSV and Excel for flexibility
            if file.name.endswith('.csv'):
                temp_df = pd.read_csv(file, low_memory=False, encoding='ISO-8859-1')
            else:
                engine = 'openpyxl' if file.name.endswith('xlsx') else None
                temp_df = pd.read_excel(file, engine=engine)
            
            temp_df.columns = temp_df.columns.str.strip()
            
            # Date Parsing
            date_col = next((c for c in ['Date', 'Complaint Created Date & Time'] if c in temp_df.columns), None)
            if date_col:
                temp_df['Date_Parsed'] = pd.to_datetime(temp_df[date_col], dayfirst=True, errors='coerce')
                temp_df = temp_df.dropna(subset=['Date_Parsed'])
                temp_df['Date'] = temp_df['Date_Parsed'].dt.date
            
            # Core Column Mapping (Updated with Sub type)
            col_map = {
                'Lob': ['Lob', 'LOB', 'Line of Business'],
                'Ticket_ID': ['Ticket ID', 'Complaint ID'],
                'L4': ['Agent Disposition Levels 4', 'Level 4'],
                'L5': ['Agent Disposition Levels 5', 'Level 5'],
                'Sub_type': ['Sub type', 'Subtype', 'sub_type'], # Added Sub type mapping
                'CEE_Name': ['Cee Name', 'Delivery Executive'],
                'CEE_ID': ['CEE Number', 'CEE ID'],
                'Member_Id': ['Member Id', 'Member ID'],
                'Hub': ['Hub', 'HUB'],
                'City': ['City', 'CITY'],
                'VIP': ['Is VIP Customer', 'VIP Tag']
            }
            
            for standard, options in col_map.items():
                for opt in options:
                    if opt in temp_df.columns:
                        temp_df[standard] = temp_df[opt]
                        break
            
            if 'Lob' in temp_df.columns:
                all_data.append(temp_df)
                
        except Exception as e:
            st.error(f"Error processing {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        if 'VIP' not in df.columns: df['VIP'] = 'No'
        df['VIP'] = df['VIP'].astype(str).str.strip().replace(['nan', '0', '0.0', 'None'], 'No')
        
        # --- 4. SIDEBAR CONTROL PANEL ---
        st.sidebar.header("🎛️ Control Panel")
        
        available_lobs = sorted(df['Lob'].astype(str).unique())
        sel_lob = st.sidebar.multiselect("Select LOB", available_lobs, default=[l for l in available_lobs if 'bbdaily' in l.lower()])
        
        start_date = st.sidebar.date_input("From Date", df['Date'].min())
        end_date = st.sidebar.date_input("To Date", df['Date'].max())
        
        st.sidebar.subheader("📍 Geography & VIP")
        sel_cities = st.sidebar.multiselect("Select City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        sel_hubs = st.sidebar.multiselect("Select Hub", sorted(df[df['City'].isin(sel_cities)]['Hub'].unique()), default=sorted(df[df['City'].isin(sel_cities)]['Hub'].unique()))
        sel_vip = st.sidebar.multiselect("VIP Status", sorted(df['VIP'].unique()), default=sorted(df['VIP'].unique()))
        
        st.sidebar.subheader("📌 Disposition Filters")
        # Existing Filters
        show_l4 = st.sidebar.checkbox("Include L4", value=True)
        sel_l4 = st.sidebar.multiselect("Filter L4", sorted(df['L4'].dropna().unique()), default=sorted(df['L4'].dropna().unique()))
        
        show_l5 = st.sidebar.checkbox("Include L5", value=True)
        sel_l5 = st.sidebar.multiselect("Filter L5", sorted(df['L5'].dropna().unique()), default=sorted(df['L5'].dropna().unique()))

        # NEW: Sub type Filter
        show_subtype = st.sidebar.checkbox("Include Sub type", value=False)
        sel_subtype = st.sidebar.multiselect("Filter Sub type", sorted(df['Sub_type'].dropna().unique()), default=sorted(df['Sub_type'].dropna().unique()))

        # --- 5. FILTERING MASK ---
        mask = (df['Lob'].astype(str).isin(sel_lob)) & \
               (df['Date'] >= start_date) & \
               (df['Date'] <= end_date) & \
               (df['City'].isin(sel_cities)) & \
               (df['Hub'].isin(sel_hubs)) & \
               (df['VIP'].isin(sel_vip))
        
        if 'L4' in df.columns: mask &= df['L4'].isin(sel_l4)
        if 'L5' in df.columns: mask &= df['L5'].isin(sel_l5)
        if 'Sub_type' in df.columns: mask &= df['Sub_type'].isin(sel_subtype)
        
        f_df = df[mask]

        # --- 6. REPORT ENGINE ---
        def generate_report(data, groups, s_date, e_date):
            avail = [g for g in groups if g in data.columns]
            if data.empty: return pd.DataFrame(columns=avail + ['Range_Total'])
            report = data.groupby(avail).size().reset_index(name='Range_Total')
            buckets = [("0-5 Days", 0, 5), ("5-10 Days", 6, 10), ("10-15 Days", 11, 15), ("15-30 Days", 16, 30)]
            for label, s_off, e_off in buckets:
                b_end, b_start = e_date - timedelta(days=s_off), e_date - timedelta(days=e_off)
                b_mask = (data['Date'] >= b_start) & (data['Date'] <= b_end)
                b_counts = data[b_mask].groupby(avail).size().reset_index(name=label)
                report = report.merge(b_counts, on=avail, how='left').fillna(0)
            return report

        # --- 7. TABS ---
        t1, t2, t3, t4, t5 = st.tabs(["📊 Summary", "👤 CEE Summary", "🔍 CEE Overview", "🛒 Customer Summary", "🔎 Customer Overview"])

        # Determine extra columns based on checkboxes
        extra_cols = []
        if show_l4: extra_cols.append('L4')
        if show_l5: extra_cols.append('L5')
        if show_subtype: extra_cols.append('Sub_type')

        with t2:
            cee_rep = generate_report(f_df, ['CEE_ID', 'CEE_Name', 'Hub', 'City', 'VIP'] + extra_cols, start_date, end_date)
            st.dataframe(cee_rep.sort_values('Range_Total', ascending=False), use_container_width=True)

        with t4:
            cust_rep = generate_report(f_df, ['Member_Id', 'City', 'Hub', 'VIP'] + extra_cols, start_date, end_date)
            st.dataframe(cust_rep.sort_values('Range_Total', ascending=False), use_container_width=True)

        # (Other tabs t1, t3, t5 remain same as previous logic)
else:
    st.info("System Ready. Please upload files.")
