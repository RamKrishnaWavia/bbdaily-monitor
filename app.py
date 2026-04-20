import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower", page_icon="🛡️")

# --- 2. STYLING ---
st.markdown("""
    <style>
    [data-testid="stDataFrame"] div[role="gridcell"] > div { justify-content: center !important; text-align: center !important; }
    .availability-banner {
        background-color: #e3f2fd; color: #0d47a1; padding: 15px;
        border-radius: 10px; border-left: 5px solid #1976d2;
        font-weight: bold; margin-bottom: 20px; text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower")

# --- 3. DATA ENGINE ---
uploaded_files = st.file_uploader("📂 Upload Complaint Dump", type=["xlsx", "xls", "csv"], accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
            if file.name.endswith('.csv'):
                temp_df = pd.read_csv(file, low_memory=False, encoding='ISO-8859-1')
            else:
                temp_df = pd.read_excel(file)
            
            temp_df.columns = temp_df.columns.str.strip()
            
            # Date Parsing logic for '1-4-2026'
            date_col = next((c for c in ['Date', 'Complaint Created Date & Time'] if c in temp_df.columns), None)
            if date_col:
                temp_df['Date_Parsed'] = pd.to_datetime(temp_df[date_col], dayfirst=True, errors='coerce')
                temp_df = temp_df.dropna(subset=['Date_Parsed'])
                temp_df['Date_Only'] = temp_df['Date_Parsed'].dt.date
            
            # Column Mapping
            col_map = {
                'Lob': ['Lob', 'LOB'],
                'Ticket_ID': ['Ticket ID', 'Complaint ID'],
                'L4': ['Agent Disposition Levels 4', 'Level 4'],
                'L5': ['Agent Disposition Levels 5', 'Level 5'],
                'Sub_type': ['Sub type', 'Subtype'],
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
            all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error loading {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        if 'VIP' not in df.columns: df['VIP'] = 'No'
        df['VIP'] = df['VIP'].astype(str).replace(['nan', 'None', '0.0', '0'], 'No')

        # --- 4. SIDEBAR ---
        st.sidebar.header("🎛️ Control Panel")
        
        # LOB Filter
        available_lobs = sorted(df['Lob'].dropna().unique())
        sel_lob = st.sidebar.multiselect("Select LOB", available_lobs, default=available_lobs)
        
        # Date Filter
        min_d, max_d = df['Date_Only'].min(), df['Date_Only'].max()
        start_date = st.sidebar.date_input("From Date", min_d)
        end_date = st.sidebar.date_input("To Date", max_d)
        
        # Geo Filter
        sel_cities = st.sidebar.multiselect("Select City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        hub_options = sorted(df[df['City'].isin(sel_cities)]['Hub'].unique())
        sel_hubs = st.sidebar.multiselect("Select Hub", hub_options, default=hub_options)

        # Disposition Filters
        st.sidebar.subheader("📌 Disposition Filters")
        show_l4 = st.sidebar.checkbox("Include L4 in Tables", value=True)
        sel_l4 = st.sidebar.multiselect("Filter L4", sorted(df['L4'].dropna().unique()), default=sorted(df['L4'].dropna().unique()))
        
        show_l5 = st.sidebar.checkbox("Include L5 in Tables", value=False)
        sel_l5 = st.sidebar.multiselect("Filter L5", sorted(df['L5'].dropna().unique()), default=sorted(df['L5'].dropna().unique()))

        show_st = st.sidebar.checkbox("Include Sub type in Tables", value=True)
        sel_st = st.sidebar.multiselect("Filter Sub type", sorted(df['Sub_type'].dropna().unique()), default=sorted(df['Sub_type'].dropna().unique()))

        search_query = st.sidebar.text_input("🔍 Search ID (Ticket/CEE/Member)")

        # --- 5. FILTERING LOGIC ---
        mask = (df['Lob'].isin(sel_lob)) & \
               (df['Date_Only'] >= start_date) & \
               (df['Date_Only'] <= end_date) & \
               (df['City'].isin(sel_cities)) & \
               (df['Hub'].isin(sel_hubs)) & \
               (df['L4'].isin(sel_l4)) & \
               (df['L5'].isin(sel_l5)) & \
               (df['Sub_type'].isin(sel_st))
        
        f_df = df[mask].copy()

        if search_query:
            f_df = f_df[
                f_df['Ticket_ID'].astype(str).str.contains(search_query) |
                f_df['CEE_ID'].astype(str).str.contains(search_query) |
                f_df['Member_Id'].astype(str).str.contains(search_query)
            ]

        # --- 6. REPORT ENGINES ---
        def get_aging_report(data, group_cols, e_date):
            if data.empty: return pd.DataFrame()
            res = data.groupby(group_cols).size().reset_index(name='Total_Tickets')
            buckets = [("0-5 Days", 0, 5), ("6-10 Days", 6, 10), ("11-15 Days", 11, 15)]
            for label, start, end in buckets:
                d_end = e_date - timedelta(days=start)
                d_start = e_date - timedelta(days=end)
                b_data = data[(data['Date_Only'] >= d_start) & (data['Date_Only'] <= d_end)]
                if not b_data.empty:
                    counts = b_data.groupby(group_cols).size().reset_index(name=label)
                    res = res.merge(counts, on=group_cols, how='left')
            return res.fillna(0)

        def get_l4_pivot(data, group_cols):
            if data.empty: return pd.DataFrame()
            pivot = data.groupby(group_cols + ['L4']).size().unstack(fill_value=0).reset_index()
            pivot['Grand_Total'] = pivot.iloc[:, len(group_cols):].sum(axis=1)
            return pivot

        # --- 7. TAB RENDERING ---
        t1, t2, t3, t4, t5 = st.tabs(["📊 Summary", "👤 CEE Summary", "🔍 CEE Overview", "🛒 Customer Summary", "🔎 Customer Overview"])

        # Decide extra columns for Summary Tabs
        extra = []
        if show_l4: extra.append('L4')
        if show_l5: extra.append('L5')
        if show_st: extra.append('Sub_type')

        with t1:
            st.markdown('<div class="availability-banner">Executive Analytical Summary</div>', unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Tickets", len(f_df))
            c2.metric("Unique CEEs", f_df['CEE_ID'].nunique())
            c3.metric("Unique Members", f_df['Member_Id'].nunique())
            c4.metric("Hubs", f_df['Hub'].nunique())
            st.write("### L4 Category Split")
            st.bar_chart(f_df['L4'].value_counts())

        with t2:
            st.subheader("CEE Aging Analysis")
            cee_aging = get_aging_report(f_df, ['CEE_ID', 'CEE_Name', 'Hub', 'City'] + extra, end_date)
            st.dataframe(cee_aging.sort_values('Total_Tickets', ascending=False), use_container_width=True)

        with t3:
            st.subheader("CEE Category (L4) Breakdown")
            cee_pivot = get_l4_pivot(f_df, ['CEE_ID', 'CEE_Name', 'Hub'])
            st.dataframe(cee_pivot, use_container_width=True)

        with t4:
            st.subheader("Customer Aging Analysis")
            cust_aging = get_aging_report(f_df, ['Member_Id', 'City', 'Hub', 'VIP'] + extra, end_date)
            st.dataframe(cust_aging.sort_values('Total_Tickets', ascending=False), use_container_width=True)

        with t5:
            st.subheader("Customer Category (L4) Breakdown")
            cust_pivot = get_l4_pivot(f_df, ['Member_Id', 'City', 'VIP'])
            st.dataframe(cust_pivot, use_container_width=True)

else:
    st.info("👋 Please upload the bbdaily complaint dump (CSV or Excel) to begin.")
