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
    [data-testid="stDataFrame"] div[role="gridcell"] > div {
        display: flex !important; justify-content: center !important;
        align-items: center !important; text-align: center !important;
    }
    [data-testid="stDataFrame"] th {
        text-align: center !important; vertical-align: middle !important;
        background-color: #f1f3f6 !important; font-weight: bold !important;
    }
    .stDataFrame { padding-right: 50px !important; }
    .availability-banner {
        background-color: #e3f2fd; color: #0d47a1; padding: 15px;
        border-radius: 10px; border-left: 8px solid #1976d2;
        font-weight: bold; margin-bottom: 20px; text-align: center;
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
            
            # Mapping (Including Refund Logic)
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
                'VIP': ['Is VIP Customer', 'VIP Tag', 'VIP Status', 'vip'],
                'Refund_Amount': ['Refund Amount', 'Refund Value', 'Refund', 'Amount']
            }
            for standard, options in col_map.items():
                for opt in options:
                    if opt in temp_df.columns:
                        temp_df[standard] = temp_df[opt]
                        break
            
            # Data Cleanup
            if 'Refund_Amount' in temp_df.columns:
                temp_df['Refund_Amount'] = pd.to_numeric(temp_df['Refund_Amount'], errors='coerce').fillna(0)
            
            if 'Lob' in temp_df.columns:
                temp_df = temp_df[temp_df['Lob'].astype(str).str.contains('bbdaily-b2c', case=False, na=False)].copy()
                if not temp_df.empty:
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error in {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        if 'VIP' in df.columns: df['VIP'] = df['VIP'].astype(str).replace(['nan', '0', '0.0'], 'No')
        
        # --- 3. SIDEBAR ---
        st.sidebar.header("🎛️ Control Panel")
        search_id = st.sidebar.text_input("🔍 Search ID", "").strip()
        start_date = st.sidebar.date_input("From", df['Date'].min())
        end_date = st.sidebar.date_input("To", df['Date'].max())
        
        st.sidebar.subheader("📍 Geography & VIP")
        sel_cities = st.sidebar.multiselect("City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        sel_hubs = st.sidebar.multiselect("Hub", sorted(df[df['City'].isin(sel_cities)]['Hub'].unique()), default=sorted(df[df['City'].isin(sel_cities)]['Hub'].unique()))
        sel_vip = st.sidebar.multiselect("VIP Status", sorted(df['VIP'].unique()), default=sorted(df['VIP'].unique()))
        
        st.sidebar.subheader("📌 Disposition Controls")
        show_l4 = st.sidebar.checkbox("Show L4", value=True)
        sel_l4 = st.sidebar.multiselect("Filter L4", sorted(df['L4'].dropna().unique()), default=sorted(df['L4'].dropna().unique()))
        show_l5 = st.sidebar.checkbox("Show L5", value=False)
        sel_l5 = st.sidebar.multiselect("Filter L5", sorted(df['L5'].dropna().unique()), default=sorted(df['L5'].dropna().unique()))

        # Masking
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date) & (df['City'].isin(sel_cities)) & (df['Hub'].isin(sel_hubs)) & (df['VIP'].isin(sel_vip))
        if 'L4' in df.columns: mask &= df['L4'].isin(sel_l4)
        if 'L5' in df.columns: mask &= df['L5'].isin(sel_l5)
        f_df = df[mask]

        # --- 4. ENGINE FUNCTIONS ---
        def generate_report(data, groups, include_daily=False):
            available = [g for g in groups if g in data.columns]
            if data.empty: return pd.DataFrame(columns=available + ['Tickets', 'Refund_Value'])
            
            # Aggregation logic for both counts and values
            report = data.groupby(available).agg(
                Tickets=('Ticket_ID', 'count'),
                Refund_Value=('Refund_Amount', 'sum')
            ).reset_index()
            
            if include_daily:
                # Add daily counts
                curr = start_date
                while curr <= end_date:
                    d_str = curr.strftime('%d-%b')
                    day_data = data[data['Date'] == curr].groupby(available).size().reset_index(name=d_str)
                    report = report.merge(day_data, on=available, how='left').fillna(0)
                    curr += timedelta(days=1)
            return report

        def style_and_show(data, key):
            if data.empty: st.warning("No data found."); return
            st.dataframe(data, use_container_width=True)
            st.download_button("📥 Download CSV", data.to_csv(index=False), file_name=f"{key}.csv", key=f"dl_{key}")

        # --- 5. TABS ---
        t_dash, t_cee_s, t_cee_o, t_cust_s, t_cust_o = st.tabs([
            "📊 Analytical Summary", "👤 CEE Summary", "🔍 CEE Overview", "🛒 Customer Summary", "🔎 Customer Overview"
        ])

        base_groups = ['CEE_ID', 'CEE_Name', 'Hub', 'City', 'VIP']
        if show_l4: base_groups.append('L4')
        if show_l5: base_groups.append('L5')

        with t_dash:
            if not f_df.empty:
                st.markdown(f'<div class="availability-banner">📅 Data Coverage: {f_df["Date"].min()} to {f_df["Date"].max()}</div>', unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Tickets", len(f_df))
                c2.metric("Refund Value", f"₹{f_df['Refund_Amount'].sum():,.0f}")
                c3.metric("Unique CEEs", f_df['CEE_ID'].nunique())
                c4.metric("VIP Count", len(f_df[f_df['VIP'] == 'Yes']))
                style_and_show(f_df.groupby(['Source_CSV', 'Date']).size().reset_index(name='Rows'), "audit")

        with t_cee_s:
            style_and_show(generate_report(f_df, base_groups).sort_values('Tickets', ascending=False), "cee_sum")

        with t_cee_o:
            style_and_show(generate_report(f_df, base_groups + ['Ticket_ID', 'Date'], True), "cee_over")

        with t_cust_s:
            style_and_show(generate_report(f_df, ['Member_Id', 'City', 'Hub', 'VIP']).sort_values('Tickets', ascending=False), "cust_sum")

        with t_cust_o:
            # Explicitly added Refund columns for Customer Overview
            cust_groups = ['Member_Id', 'Ticket_ID', 'Date', 'City', 'Hub', 'VIP', 'L4']
            style_and_show(generate_report(f_df, cust_groups), "cust_over")

else:
    st.info("Upload CSV files. Refund values will be calculated automatically.")
