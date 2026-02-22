import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io

# --- 1. PAGE CONFIGURATION & AGGRESSIVE UI STYLING ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower", page_icon="🛡️")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    
    /* Aggressive Center Alignment for Data and Headers */
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
    }

    .stDataFrame { padding-right: 50px !important; }
    
    .availability-banner {
        background-color: #e3f2fd;
        color: #0d47a1;
        padding: 15px;
        border-radius: 10px;
        border-left: 8px solid #1976d2;
        font-weight: bold;
        margin-bottom: 20px;
        text-align: center;
    }
    
    section[data-testid="stSidebar"] { width: 400px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.markdown("---")

# --- 2. MULTI-FILE UPLOADER ---
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
            
            temp_df.columns = temp_df.columns.str.strip()
            temp_df['Source_CSV'] = file.name
            
            # Date Parsing
            date_col = next((c for c in ['Complaint Created Date & Time', 'Created Date', 'Date'] if c in temp_df.columns), None)
            if date_col:
                temp_df['Date_Parsed'] = pd.to_datetime(temp_df[date_col], dayfirst=True, errors='coerce')
                temp_df = temp_df.dropna(subset=['Date_Parsed'])
                temp_df['Date'] = temp_df['Date_Parsed'].dt.date
            
            # Mapping
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
                'VIP': ['Is VIP Customer', 'VIP Tag', 'VIP Status', 'vip']
            }
            for standard, options in col_map.items():
                for opt in options:
                    if opt in temp_df.columns:
                        temp_df[standard] = temp_df[opt]
                        break
            
            # Filter bbdaily-b2c (The Thumb Rule)
            if 'Lob' in temp_df.columns:
                temp_df = temp_df[temp_df['Lob'].astype(str).str.contains('bbdaily-b2c', case=False, na=False)].copy()
                if not temp_df.empty:
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error in {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        # Ensure VIP is treated as string for consistent filtering
        if 'VIP' in df.columns:
            df['VIP'] = df['VIP'].astype(str).str.strip().replace(['nan', 'None', '0', '0.0'], 'No')
        
        # --- 3. SIDEBAR CONTROLS ---
        st.sidebar.header("🎛️ Master Control Panel")
        
        # Search & Dates
        search_id = st.sidebar.text_input("🔍 Search ID (Ticket/CEE/Cust)", "").strip()
        start_date = st.sidebar.date_input("From Date", df['Date'].min())
        end_date = st.sidebar.date_input("To Date", df['Date'].max())
        
        st.sidebar.markdown("---")
        
        # Location & VIP Filters
        st.sidebar.subheader("📍 Geography & Segment")
        unique_cities = sorted(df['City'].unique()) if 'City' in df.columns else []
        sel_cities = st.sidebar.multiselect("Select City", unique_cities, default=unique_cities)
        
        unique_hubs = sorted(df[df['City'].isin(sel_cities)]['Hub'].unique()) if 'Hub' in df.columns else []
        sel_hubs = st.sidebar.multiselect("Select Hub", unique_hubs, default=unique_hubs)
        
        # RESTORED VIP FILTER
        unique_vip = sorted(df['VIP'].unique()) if 'VIP' in df.columns else []
        sel_vip = st.sidebar.multiselect("VIP Status Filter", unique_vip, default=unique_vip)
        
        st.sidebar.markdown("---")
        
        # Disposition Controls (L4/L5)
        st.sidebar.subheader("📌 Disposition Controls")
        show_l4 = st.sidebar.checkbox("Show L4 in Tables", value=True)
        unique_l4 = sorted(df['L4'].dropna().unique()) if 'L4' in df.columns else []
        sel_l4 = st.sidebar.multiselect("Filter L4 Categories", unique_l4, default=unique_l4)
        
        show_l5 = st.sidebar.checkbox("Show L5 in Tables", value=False)
        unique_l5 = sorted(df['L5'].dropna().unique()) if 'L5' in df.columns else []
        sel_l5 = st.sidebar.multiselect("Filter L5 Categories", unique_l5, default=unique_l5)

        # Apply Global Mask
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
        if 'City' in df.columns: mask &= df['City'].isin(sel_cities)
        if 'Hub' in df.columns: mask &= df['Hub'].isin(sel_hubs)
        if 'VIP' in df.columns: mask &= df['VIP'].isin(sel_vip)
        if 'L4' in df.columns: mask &= df['L4'].isin(sel_l4)
        if 'L5' in df.columns: mask &= df['L5'].isin(sel_l5)
        
        f_df = df[mask]
        if search_id:
            f_df = f_df[(f_df['Ticket_ID'].astype(str).str.contains(search_id)) | 
                        (f_df['CEE_ID'].astype(str).str.contains(search_id)) | 
                        (f_df['Member_Id'].astype(str).str.contains(search_id))]

        # --- 4. ENGINE FUNCTIONS ---
        def generate_report(data, groups, s_date, e_date, include_daily=False):
            available_groups = [g for g in groups if g in data.columns]
            if data.empty: return pd.DataFrame(columns=available_groups + ['Range_Total'])
            
            report = data.groupby(available_groups).size().reset_index(name='Range_Total')
            buckets = [("0-5 Days", 0, 5), ("5-10 Days", 6, 10), ("10-15 Days", 11, 15), ("15-30 Days", 16, 30)]
            for label, s_off, e_off in buckets:
                b_end, b_start = e_date - timedelta(days=s_off), e_date - timedelta(days=e_off)
                b_mask = (data['Date'] >= b_start) & (data['Date'] <= b_end)
                b_counts = data[b_mask].groupby(available_groups).size().reset_index(name=label)
                report = report.merge(b_counts, on=available_groups, how='left').fillna(0)
            
            if include_daily:
                curr = s_date
                while curr <= e_date:
                    d_str = curr.strftime('%d-%b')
                    day_data = data[data['Date'] == curr].groupby(available_groups).size().reset_index(name=d_str)
                    report = report.merge(day_data, on=available_groups, how='left').fillna(0)
                    curr += timedelta(days=1)
            
            for c in report.columns.difference(available_groups): report[c] = report[c].astype(int)
            return report

        def style_and_show(data, key):
            if data.empty:
                st.warning("No data found.")
                return
            st.dataframe(data, use_container_width=True)
            st.download_button("📥 Download CSV", data.to_csv(index=False), file_name=f"{key}.csv", key=f"dl_{key}")

        # --- 5. TABS ---
        t_dash, t_cee, t_cust = st.tabs(["📊 Performance Dashboard", "👤 CEE Analysis", "🛒 Customer Analysis"])
        
        base_groups = ['CEE_ID', 'CEE_Name', 'Hub', 'City', 'VIP']
        if show_l4: base_groups.append('L4')
        if show_l5: base_groups.append('L5')

        with t_dash:
            if not f_df.empty:
                st.markdown(f'<div class="availability-banner">📅 Active Data Range: {f_df["Date"].min()} to {f_df["Date"].max()}</div>', unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Tickets", len(f_df))
                c2.metric("CEEs", f_df['CEE_ID'].nunique())
                c3.metric("Cities", f_df['City'].nunique())
                c4.metric("VIP Tickets", len(f_df[f_df['VIP'] == 'Yes']) if 'VIP' in f_df.columns else 0)
                
                st.markdown("---")
                st.write("**Integrity Audit: Source Files**")
                style_and_show(f_df.groupby(['Source_CSV', 'Date']).size().reset_index(name='Rows').sort_values('Date'), "audit")

        with t_cee:
            style_and_show(generate_report(f_df, base_groups, start_date, end_date, True).sort_values('Range_Total', ascending=False), "cee_report")

        with t_cust:
            m_groups = ['Member_Id', 'City', 'Hub', 'VIP']
            if show_l4: m_groups.append('L4')
            if show_l5: m_groups.append('L5')
            style_and_show(generate_report(f_df, m_groups, start_date, end_date), "cust_report")

else:
    st.info("Upload CSV files. VIP, L4, and L5 filters will appear in the sidebar automatically.")
