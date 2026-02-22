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
    
    /* Global Center Alignment for modern Dataframes */
    [data-testid="stDataFrame"] div[role="gridcell"] > div {
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
        font-weight: bold !important;
    }

    /* Padding for last column and scroll fixes */
    .stDataFrame { padding-right: 50px !important; border-radius: 10px; }
    
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
            
            # Date Parsing (DD-MM-YYYY)
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
                'CEE_ID': ['CEE Number', 'CEE ID', 'DE ID'],
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
            
            # Filter bbdaily-b2c ONLY
            if 'Lob' in temp_df.columns:
                temp_df = temp_df[temp_df['Lob'].astype(str).str.contains('bbdaily-b2c', case=False, na=False)].copy()
                if not temp_df.empty:
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error in {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        if 'VIP' in df.columns: 
            df['VIP'] = df['VIP'].astype(str).str.strip().replace(['nan', '0', '0.0', 'None'], 'No')
        
        # --- 3. SIDEBAR CONTROLS ---
        st.sidebar.header("🎛️ Control Panel")
        search_id = st.sidebar.text_input("🔍 Search ID", "").strip()
        start_date = st.sidebar.date_input("From", df['Date'].min())
        end_date = st.sidebar.date_input("To", df['Date'].max())
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("📍 Geography & VIP")
        sel_cities = st.sidebar.multiselect("Select City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        sel_hubs = st.sidebar.multiselect("Select Hub", sorted(df[df['City'].isin(sel_cities)]['Hub'].unique()), default=sorted(df[df['City'].isin(sel_cities)]['Hub'].unique()))
        sel_vip = st.sidebar.multiselect("VIP Status", sorted(df['VIP'].unique()), default=sorted(df['VIP'].unique()))
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("📌 Disposition Filters")
        show_l4 = st.sidebar.checkbox("Include L4 in Tables", value=True)
        sel_l4 = st.sidebar.multiselect("Filter L4 Categories", sorted(df['L4'].dropna().unique()), default=sorted(df['L4'].dropna().unique()))
        
        show_l5 = st.sidebar.checkbox("Include L5 in Tables", value=False)
        sel_l5 = st.sidebar.multiselect("Filter L5 Categories", sorted(df['L5'].dropna().unique()), default=sorted(df['L5'].dropna().unique()))

        # Masking
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date) & (df['City'].isin(sel_cities)) & (df['Hub'].isin(sel_hubs)) & (df['VIP'].isin(sel_vip))
        if 'L4' in df.columns: mask &= df['L4'].isin(sel_l4)
        if 'L5' in df.columns: mask &= df['L5'].isin(sel_l5)
        f_df = df[mask]
        
        if search_id:
            f_df = f_df[(f_df['Ticket_ID'].astype(str).str.contains(search_id)) | 
                        (f_df['CEE_ID'].astype(str).str.contains(search_id)) | 
                        (f_df['Member_Id'].astype(str).str.contains(search_id))]

        # --- 4. ENGINE FUNCTIONS ---
        def generate_report(data, groups, include_daily=False):
            available = [g for g in groups if g in data.columns]
            if data.empty: return pd.DataFrame(columns=available + ['Total_Tickets'])
            
            report = data.groupby(available).size().reset_index(name='Total_Tickets')
            
            if include_daily:
                curr = start_date
                while curr <= end_date:
                    d_str = curr.strftime('%d-%b')
                    day_data = data[data['Date'] == curr].groupby(available).size().reset_index(name=d_str)
                    report = report.merge(day_data, on=available, how='left').fillna(0)
                    curr += timedelta(days=1)
                for c in report.columns.difference(available):
                    report[c] = report[c].astype(int)
            return report

        def style_and_show(data, key):
            if data.empty: st.warning("No data found."); return
            st.dataframe(data, use_container_width=True)
            st.download_button("📥 Download CSV", data.to_csv(index=False), file_name=f"{key}.csv", key=f"dl_{key}")

        # --- 5. TABS ---
        t_dash, t_cee_s, t_cee_o, t_cust_s, t_cust_o = st.tabs([
            "📊 Analytical Summary", "👤 CEE Summary", "🔍 CEE Overview", "🛒 Customer Summary", "🔎 Customer Overview"
        ])

        # Define columns for summary
        base_cols = ['CEE_ID', 'CEE_Name', 'Hub', 'City', 'VIP']
        if show_l4: base_cols.append('L4')
        if show_l5: base_cols.append('L5')

        with t_dash:
            if not f_df.empty:
                st.markdown(f'<div class="availability-banner">📅 Active Range: {f_df["Date"].min()} to {f_df["Date"].max()}</div>', unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Tickets", len(f_df))
                c2.metric("Active CEEs", f_df['CEE_ID'].nunique())
                c3.metric("Impacted Customers", f_df['Member_Id'].nunique())
                c4.metric("VIP Tickets", len(f_df[f_df['VIP'].str.contains('Yes', case=False, na=False)]))
                
                st.markdown("---")
                st.write("**Source Audit: Tickets per File**")
                style_and_show(f_df.groupby(['Source_CSV', 'Date']).size().reset_index(name='Count'), "audit")

        with t_cee_s:
            style_and_show(generate_report(f_df, base_cols).sort_values('Total_Tickets', ascending=False), "cee_summary")

        with t_cee_o:
            style_and_show(generate_report(f_df, base_cols + ['Ticket_ID', 'Date'], True), "cee_overview")

        with t_cust_s:
            cust_cols = ['Member_Id', 'City', 'Hub', 'VIP']
            if show_l4: cust_cols.append('L4')
            style_and_show(generate_report(f_df, cust_cols).sort_values('Total_Tickets', ascending=False), "cust_summary")

        with t_cust_o:
            cust_over_cols = ['Member_Id', 'Ticket_ID', 'Date', 'City', 'Hub', 'VIP']
            if show_l4: cust_over_cols.append('L4')
            if show_l5: cust_over_cols.append('L5')
            style_and_show(generate_report(f_df, cust_over_cols, True), "cust_overview")

else:
    st.info("System Ready. Upload CSV files to activate 5-tab analysis.")
