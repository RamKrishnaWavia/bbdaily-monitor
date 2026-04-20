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
        background-color: #fff3cd; color: #856404; padding: 15px;
        border-radius: 10px; border-left: 5px solid #ffeeba;
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
            
            # Date Parsing logic
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
                'Hub': ['Hub', 'HUB', 'Store'],
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
        
        available_lobs = sorted(df['Lob'].dropna().unique())
        sel_lob = st.sidebar.multiselect("Select LOB", available_lobs, default=available_lobs)
        
        start_date = st.sidebar.date_input("From Date", df['Date_Only'].min())
        end_date = st.sidebar.date_input("To Date", df['Date_Only'].max())
        
        sel_cities = st.sidebar.multiselect("Select City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        
        # Disposition Filters
        st.sidebar.subheader("📌 Disposition Filters")
        sel_l4 = st.sidebar.multiselect("Filter L4", sorted(df['L4'].dropna().unique()), default=sorted(df['L4'].dropna().unique()))
        sel_st = st.sidebar.multiselect("Filter Sub type", sorted(df['Sub_type'].dropna().unique()), default=sorted(df['Sub_type'].dropna().unique()))

        # --- 5. FILTERING LOGIC ---
        mask = (df['Lob'].isin(sel_lob)) & \
               (df['Date_Only'] >= start_date) & \
               (df['Date_Only'] <= end_date) & \
               (df['City'].isin(sel_cities)) & \
               (df['L4'].isin(sel_l4)) & \
               (df['Sub_type'].isin(sel_st))
        
        f_df = df[mask].copy()

        # --- 6. TABS ---
        t1, t2, t3, t4, t5, t6 = st.tabs([
            "📊 Summary", "👤 CEE Summary", "🔍 CEE Overview", 
            "🛒 Customer Summary", "🔎 Customer Overview", "🏪 Store (IBND) Summary"
        ])

        with t1:
            st.markdown('<div class="availability-banner">Executive Analytical Summary</div>', unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Tickets", len(f_df))
            c2.metric("Unique CEEs", f_df['CEE_ID'].nunique())
            c3.metric("Unique Members", f_df['Member_Id'].nunique())
            c4.metric("Active Hubs", f_df['Hub'].nunique())
            st.write("### Top 10 Hubs by Complaint Volume")
            st.bar_chart(f_df['Hub'].value_counts().head(10))

        with t2:
            st.subheader("CEE Wise Performance")
            cee_sum = f_df.groupby(['Hub', 'CEE_ID', 'CEE_Name']).size().reset_index(name='Total_Complaints')
            st.dataframe(cee_sum.sort_values('Total_Complaints', ascending=False), use_container_width=True)

        with t3:
            st.subheader("CEE Category Split")
            cee_pivot = f_df.groupby(['CEE_Name', 'L4']).size().unstack(fill_value=0)
            st.dataframe(cee_pivot, use_container_width=True)

        with t4:
            st.subheader("Customer Wise Summary")
            cust_sum = f_df.groupby(['Member_Id', 'City', 'VIP']).size().reset_index(name='Total_Complaints')
            st.dataframe(cust_sum.sort_values('Total_Complaints', ascending=False), use_container_width=True)

        with t5:
            st.subheader("Customer Category Split")
            cust_pivot = f_df.groupby(['Member_Id', 'L4']).size().unstack(fill_value=0)
            st.dataframe(cust_pivot, use_container_width=True)

        with t6:
            st.markdown('<div class="availability-banner">🏪 Store & CEE IBND Deep Dive</div>', unsafe_allow_html=True)
            
            # Logic: Filter for IBND specifically if possible, or show overall distribution
            st.write("### Store-wise Contribution")
            # Group by Hub and CEE to show the hierarchy
            store_cee_sum = f_df.groupby(['Hub', 'CEE_ID', 'CEE_Name', 'Sub_type']).size().reset_index(name='Ticket_Count')
            
            # Pivot table for better readability
            store_pivot = store_cee_sum.pivot_table(
                index=['Hub', 'CEE_ID', 'CEE_Name'], 
                columns='Sub_type', 
                values='Ticket_Count', 
                aggfunc='sum', 
                fill_value=0
            ).reset_index()
            
            # Add a Total Column
            numeric_cols = store_pivot.select_dtypes(include=[np.number]).columns
            store_pivot['Grand Total'] = store_pivot[numeric_cols].sum(axis=1)
            
            st.dataframe(store_pivot.sort_values(['Hub', 'Grand Total'], ascending=[True, False]), use_container_width=True)
            
            # Store Summary Metric
            st.write("### Hub Distribution")
            hub_dist = f_df.groupby('Hub').size().reset_index(name='Total')
            st.bar_chart(hub_dist.set_index('Hub'))

else:
    st.info("👋 Please upload the bbdaily complaint dump to begin.")
