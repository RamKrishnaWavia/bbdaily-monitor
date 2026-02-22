import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io

# --- 1. PAGE CONFIGURATION & AGGRESSIVE UI STYLING ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower", page_icon="🛡️")

# Aggressive CSS Injection for Alignment and UI Layout
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    
    /* Force center alignment for every cell in the dataframe */
    [data-testid="stDataFrame"] div[role="gridcell"] > div {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
    }
    
    /* Force center alignment for headers */
    [data-testid="stDataFrame"] th {
        text-align: center !important;
        vertical-align: middle !important;
        background-color: #f1f3f6 !important;
    }

    /* Fix the scroll and last column visibility */
    .stDataFrame {
        padding-right: 50px !important;
        border: 1px solid #e6e9ef;
        border-radius: 10px;
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

    /* Availability Banner */
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
            try:
                temp_df = pd.read_csv(file, encoding='utf-8', low_memory=False)
            except:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1', low_memory=False)
            
            temp_df['Source_CSV'] = file.name
            temp_df.columns = temp_df.columns.str.strip()
            
            # --- DATE LOCK (DD-MM-YYYY) ---
            date_priority = ['Complaint Created Date & Time', 'Created Date', 'Date', 'date']
            date_col = next((c for c in date_priority if c in temp_df.columns), None)
            
            if date_col:
                # dayfirst=True ensures correct parsing of 01-02-2026 as Feb 1st
                temp_df['Date_Parsed'] = pd.to_datetime(temp_df[date_col], dayfirst=True, errors='coerce')
                temp_df = temp_df.dropna(subset=['Date_Parsed'])
                temp_df['Date'] = temp_df['Date_Parsed'].dt.date
            
            # --- COLUMN MAPPING ---
            col_map = {
                'Lob': ['Lob', 'LOB', 'lob', 'Line of Business'],
                'Ticket_ID': ['Ticket ID', 'Complaint ID', 'Ticket Number', 'id'],
                'L4': ['Level 4', 'Category', 'L4 Category'],
                'L5': ['Level 5', 'Sub Category', 'L5 Category'],
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
            st.error(f"Processing error in {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        
        # --- 3. SIDEBAR CONTROLS ---
        st.sidebar.header("🎛️ Control Panel")
        search_id = st.sidebar.text_input("🔍 Search ID (Ticket/CEE/Member)", "").strip()
        
        col_d1, col_d2 = st.sidebar.columns(2)
        start_date = col_d1.date_input("From", df['Date'].min())
        end_date = col_d2.date_input("To", df['Date'].max())
        
        selected_cities = st.sidebar.multiselect("City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        selected_hubs = st.sidebar.multiselect("Hub", sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()), default=sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()))
        
        st.sidebar.subheader("Grouping")
        g_l4 = st.sidebar.checkbox("Show L4 Category", value=True)
        g_l5 = st.sidebar.checkbox("Show L5 Category", value=False)

        # Apply Filtering
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date) & (df['City'].isin(selected_cities)) & (df['Hub'].isin(selected_hubs))
        f_df = df[mask]
        
        if search_id:
            f_df = f_df[(f_df['Ticket_ID'].str.contains(search_id, case=False)) | 
                        (f_df['CEE_ID'].str.contains(search_id, case=False)) | 
                        (f_df['Member_Id'].str.contains(search_id, case=False))]

        # --- 4. ENGINE FUNCTIONS ---
        # Fixed the Duplicate ID error by passing a unique 'id_key'
        def style_and_show(data, id_key):
            if data.empty:
                st.warning("No records found for the chosen filters.")
                return
            
            # CSS centering applied automatically via header style injection
            st.dataframe(data, use_container_width=True)
            
            csv = data.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download This Table (CSV)", 
                data=csv, 
                file_name=f"BBD_Report_{id_key}_{datetime.now().strftime('%Y%m%d')}.csv", 
                mime='text/csv',
                key=f"btn_{id_key}" # THIS FIXES THE DUPLICATE ELEMENT ERROR
            )

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
        if g_l4: c_groups.append('L4')
        if g_l5: c_groups.append('L5')
        
        m_groups = ['Member_Id', 'City', 'Hub', 'VIP']
        if g_l4: m_groups.append('L4')
        if g_l5: m_groups.append('L5')

        with t_dash:
            if not f_df.empty:
                min_d, max_d = f_df['Date'].min().strftime('%d-%b-%Y'), f_df['Date'].max().strftime('%d-%b-%Y')
                st.markdown(f'<div class="availability-banner">📅 Data Coverage: {min_d} to {max_d}</div>', unsafe_allow_html=True)
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Tickets", len(f_df))
                c2.metric("Active CEEs", f_df['CEE_ID'].nunique())
                c3.metric("Impacted Customers", f_df['Member_Id'].nunique())
                
                st.markdown("---")
                st.write("**File Source Verification Audit**")
                style_and_show(f_df.groupby(['Source_CSV', 'Date']).size().reset_index(name='Rows').sort_values('Date'), "source_audit")

        with t_cee_s:
            res = generate_report(f_df, c_groups, start_date, end_date)
            style_and_show(res.sort_values('Range_Total', ascending=False) if not res.empty else res, "cee_summary")
            
        with t_cee_d:
            res = generate_report(f_df, c_groups + ['Ticket_ID', 'Date', 'Source_CSV'], start_date, end_date, True)
            style_and_show(res.sort_values('Date', ascending=False) if not res.empty else res, "cee_detailed")

        with t_cust_s:
            res = generate_report(f_df, m_groups, start_date, end_date)
            style_and_show(res.sort_values('Range_Total', ascending=False) if not res.empty else res, "cust_summary")

        with t_cust_d:
            res = generate_report(f_df, m_groups + ['Ticket_ID', 'Date', 'Source_CSV'], start_date, end_date, True)
            style_and_show(res.sort_values('Date', ascending=False) if not res.empty else res, "cust_detailed")

else:
    st.info("System Ready. Upload CSV files. Date format DD-MM-YYYY is strictly enforced.")
