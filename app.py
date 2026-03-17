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

# --- 2. AGGRESSIVE UI & CENTER ALIGNMENT STYLING (FROZEN) ---
st.markdown("""
    <style>
    .main { 
        background-color: #f8f9fa; 
    }
    
    /* Force Center Alignment for Data Grids */
    [data-testid="stDataFrame"] div[role="gridcell"] > div,
    [data-testid="stDataFrame"] div[role="columnheader"] > div,
    [data-testid="stDataFrame"] .st-emotion-cache-1wivap2,
    [data-testid="stDataFrame"] .data-grid-container {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        width: 100% !important;
    }

    [data-testid="stDataFrame"] th {
        text-align: center !important;
        vertical-align: middle !important;
        background-color: #f1f3f6 !important;
        font-weight: bold !important;
        border: 1px solid #dee2e6 !important;
    }

    .stDataFrame {
        padding-right: 50px !important;
        border-radius: 10px;
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
    
    section[data-testid="stSidebar"] { 
        width: 400px !important; 
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.markdown("---")

# --- 3. MULTI-FILE UPLOADER & DATA ENGINE ---
uploaded_files = st.file_uploader("📂 Upload Complaint Dump (CSV Files)", type="csv", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    
    for file in uploaded_files:
        try:
            # Multi-encoding support for stability
            try:
                temp_df = pd.read_csv(file, encoding='utf-8', low_memory=False)
            except:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1', low_memory=False)
            
            temp_df.columns = temp_df.columns.str.strip()
            
            # Date Parsing Logic (DD-MM-YYYY)
            date_col = next((c for c in ['Complaint Created Date & Time', 'Created Date', 'Date'] if c in temp_df.columns), None)
            if date_col:
                temp_df['Date_Parsed'] = pd.to_datetime(temp_df[date_col], dayfirst=True, errors='coerce')
                temp_df = temp_df.dropna(subset=['Date_Parsed'])
                temp_df['Date'] = temp_df['Date_Parsed'].dt.date
            
            # Core Column Mapping
            col_map = {
                'Lob': ['Lob', 'LOB', 'Line of Business', 'lob'],
                'Ticket_ID': ['Ticket ID', 'Complaint ID', 'Ticket Number', 'ticket_id'],
                'L4': ['Agent Disposition Levels 4', 'Level 4', 'Category', 'l4'],
                'L5': ['Agent Disposition Levels 5', 'Level 5', 'Sub Category', 'l5'],
                'CEE_Name': ['Cee Name', 'CEE NAME', 'Delivery Executive', 'cee_name'],
                'CEE_ID': ['CEE Number', 'CEE ID', 'DE ID', 'cee_id'],
                'Member_Id': ['Member Id', 'Member ID', 'Customer ID', 'member_id'],
                'Hub': ['Hub', 'HUB', 'FC NAME', 'Store', 'hub'],
                'City': ['City', 'CITY', 'city'],
                'VIP': ['Is VIP Customer', 'VIP Tag', 'VIP Status', 'vip']
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
        
        # Clean VIP data
        if 'VIP' in df.columns:
            df['VIP'] = df['VIP'].astype(str).str.strip().replace(['nan', '0', '0.0', 'None'], 'No')
        
        # --- 4. SIDEBAR CONTROL PANEL ---
        st.sidebar.header("🎛️ Control Panel")
        
        # LOB Filter
        available_lobs = sorted(df['Lob'].astype(str).unique())
        default_lob = [l for l in available_lobs if 'bbdaily-b2c' in l.lower()]
        sel_lob = st.sidebar.multiselect("Select LOB", available_lobs, default=default_lob)
        
        search_id = st.sidebar.text_input("🔍 Search ID", "").strip()
        start_date = st.sidebar.date_input("From Date", df['Date'].min())
        end_date = st.sidebar.date_input("To Date", df['Date'].max())
        
        st.sidebar.subheader("📍 Geography & VIP")
        sel_cities = st.sidebar.multiselect("Select City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        hub_list = sorted(df[df['City'].isin(sel_cities)]['Hub'].unique())
        sel_hubs = st.sidebar.multiselect("Select Hub", hub_list, default=hub_list)
        sel_vip = st.sidebar.multiselect("VIP Status", sorted(df['VIP'].unique()), default=sorted(df['VIP'].unique()))
        
        st.sidebar.subheader("📌 Disposition Filters")
        show_l4 = st.sidebar.checkbox("Include L4", value=True)
        sel_l4 = st.sidebar.multiselect("Filter L4", sorted(df['L4'].dropna().unique()), default=sorted(df['L4'].dropna().unique()))
        show_l5 = st.sidebar.checkbox("Include L5", value=True)
        sel_l5 = st.sidebar.multiselect("Filter L5", sorted(df['L5'].dropna().unique()), default=sorted(df['L5'].dropna().unique()))

        # --- 5. FILTERING MASK ---
        mask = (df['Lob'].astype(str).isin(sel_lob)) & \
               (df['Date'] >= start_date) & \
               (df['Date'] <= end_date) & \
               (df['City'].isin(sel_cities)) & \
               (df['Hub'].isin(sel_hubs)) & \
               (df['VIP'].isin(sel_vip))
        
        if 'L4' in df.columns: mask &= df['L4'].isin(sel_l4)
        if 'L5' in df.columns: mask &= df['L5'].isin(sel_l5)
        f_df = df[mask]
        
        if search_id:
            f_df = f_df[(f_df['Ticket_ID'].astype(str).str.contains(search_id)) | 
                        (f_df['CEE_ID'].astype(str).str.contains(search_id)) | 
                        (f_df['Member_Id'].astype(str).str.contains(search_id))]

        # --- 6. REPORT ENGINES ---
        # Summary Engine (Aging Buckets)
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
            for c in report.columns.difference(avail): report[c] = report[c].astype(int)
            return report

        # Overview Engine (L4 Pivot) - NEW REQUIREMENT
        def generate_l4_pivot(data, index_cols):
            avail_idx = [c for c in index_cols if c in data.columns]
            if data.empty: return pd.DataFrame(columns=avail_idx)
            # Group by index + L4 and pivot
            pivot = data.groupby(avail_idx + ['L4']).size().unstack(fill_value=0).reset_index()
            # Add Total column
            pivot['Total_Tickets'] = pivot.iloc[:, len(avail_idx):].sum(axis=1)
            return pivot

        # --- 7. TABS ---
        t1, t2, t3, t4, t5 = st.tabs(["📊 Analytical Summary", "👤 CEE Summary", "🔍 CEE Overview", "🛒 Customer Summary", "🔎 Customer Overview"])

        extra_cols = []
        if show_l4: extra_cols.append('L4')
        if show_l5: extra_cols.append('L5')

        with t1:
            st.markdown(f'<div class="availability-banner">📊 Analytical Summary Dashboard</div>', unsafe_allow_html=True)
            m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
            m_col1.metric("Total Tickets", len(f_df))
            m_col2.metric("Unique CEEs", f_df['CEE_ID'].nunique() if 'CEE_ID' in f_df.columns else 0)
            m_col3.metric("Unique Customers", f_df['Member_Id'].nunique() if 'Member_Id' in f_df.columns else 0)
            m_col4.metric("L4 Categories", f_df['L4'].nunique() if 'L4' in f_df.columns else 0)
            m_col5.metric("L5 Remarks", f_df['L5'].nunique() if 'L5' in f_df.columns else 0)
            st.markdown("---")
            c1, c2 = st.columns(2)
            with c1: st.write("**L4 Distribution**"); st.bar_chart(f_df['L4'].value_counts())
            with c2: st.write("**City Distribution**"); st.bar_chart(f_df['City'].value_counts())
            c3, c4 = st.columns(2)
            with c3: st.write("**VIP Mix**"); st.bar_chart(f_df['VIP'].value_counts())
            with c4: st.write("**Daily Trend**"); st.line_chart(f_df.groupby('Date').size())
            st.markdown("---")
            b1, b2 = st.columns(2)
            with b1: st.dataframe(f_df['L4'].value_counts().reset_index().rename(columns={'count':'Total'}), hide_index=True, use_container_width=True)
            with b2: st.dataframe(f_df['L5'].value_counts().reset_index().rename(columns={'count':'Total'}), hide_index=True, use_container_width=True)

        with t2:
            st.dataframe(generate_report(f_df, ['CEE_ID', 'CEE_Name', 'Hub', 'City', 'VIP'] + extra_cols, start_date, end_date).sort_values('Range_Total', ascending=False), use_container_width=True)

        with t3:
            # CEE Overview with L4 Columns instead of Ranges
            cee_ov_idx = ['CEE_ID', 'CEE_Name', 'Hub', 'City', 'VIP']
            st.dataframe(generate_l4_pivot(f_df, cee_ov_idx), use_container_width=True)

        with t4:
            st.dataframe(generate_report(f_df, ['Member_Id', 'City', 'Hub', 'VIP'] + extra_cols, start_date, end_date).sort_values('Range_Total', ascending=False), use_container_width=True)

        with t5:
            # Customer Overview with L4 Columns instead of Ranges
            cust_ov_idx = ['Member_Id', 'City', 'Hub', 'VIP']
            st.dataframe(generate_l4_pivot(f_df, cust_ov_idx), use_container_width=True)
else:
    st.info("System Ready. Please upload CSV files.")
