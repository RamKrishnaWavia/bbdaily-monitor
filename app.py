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
        background-color: #f3e5f5; color: #4a148c; padding: 15px;
        border-radius: 10px; border-left: 5px solid #9c27b0;
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
            
            # Date Parsing
            date_col = next((c for c in ['Date', 'Complaint Created Date & Time'] if c in temp_df.columns), None)
            if date_col:
                temp_df['Date_Parsed'] = pd.to_datetime(temp_df[date_col], dayfirst=True, errors='coerce')
                temp_df = temp_df.dropna(subset=['Date_Parsed'])
                temp_df['Date_Only'] = temp_df['Date_Parsed'].dt.date
            
            # Column Mapping (Added SKU mapping)
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
                'VIP': ['Is VIP Customer', 'VIP Tag'],
                'SKU_Name': ['SKU Name', 'Product Name'],
                'SKU_Cat': ['SKU Category', 'Category']
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

        st.sidebar.subheader("📌 Disposition Filters")
        sel_l4 = st.sidebar.multiselect("Filter L4", sorted(df['L4'].dropna().unique()), default=sorted(df['L4'].dropna().unique()))
        sel_st = st.sidebar.multiselect("Filter Sub type", sorted(df['Sub_type'].dropna().unique()), default=sorted(df['Sub_type'].dropna().unique()))

        # --- 5. FILTERING ---
        mask = (df['Lob'].isin(sel_lob)) & \
               (df['Date_Only'] >= start_date) & \
               (df['Date_Only'] <= end_date) & \
               (df['City'].isin(sel_cities)) & \
               (df['L4'].isin(sel_l4)) & \
               (df['Sub_type'].isin(sel_st))
        
        f_df = df[mask].copy()

        # --- 6. TABS ---
        tabs = st.tabs([
            "📊 Summary", "👤 CEE Summary", "🔍 CEE Overview", 
            "🛒 Customer Summary", "🔎 Customer Overview", 
            "🏪 Store Summary", "📦 SKU Analysis"
        ])

        # TAB 1: SUMMARY
        with tabs[0]:
            st.markdown('<div class="availability-banner">Executive Analytical Summary</div>', unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Tickets", len(f_df))
            m2.metric("Unique CEEs", f_df['CEE_ID'].nunique())
            m3.metric("Unique SKUs", f_df['SKU_Name'].nunique())
            m4.metric("Active Hubs", f_df['Hub'].nunique())
            
            c1, c2 = st.columns(2)
            with c1:
                st.write("**L4 Distribution**")
                st.bar_chart(f_df['L4'].value_counts())
            with c2:
                st.write("**Sub type Distribution**")
                st.bar_chart(f_df['Sub_type'].value_counts())

        # TAB 6: STORE SUMMARY
        with tabs[5]:
            st.subheader("Hub & CEE Deep Dive")
            store_pivot = f_df.groupby(['Hub', 'CEE_Name', 'Sub_type']).size().unstack(fill_value=0).reset_index()
            st.dataframe(store_pivot, use_container_width=True, hide_index=True)

        # TAB 7: SKU WISE CONTRIBUTION
        with tabs[6]:
            st.markdown('<div class="availability-banner">📦 SKU Wise Complaint Contribution</div>', unsafe_allow_html=True)
            
            # SKU Contribution calculation
            sku_contrib = f_df.groupby(['SKU_Name', 'SKU_Cat']).agg(
                Total_Complaints=('Ticket_ID', 'count'),
                Unique_Customers=('Member_Id', 'nunique'),
                Unique_CEEs=('CEE_ID', 'nunique')
            ).reset_index()
            
            # Sort by highest complaints
            sku_contrib = sku_contrib.sort_values('Total_Complaints', ascending=False)
            
            # Percentage contribution
            total_tickets = len(f_df)
            sku_contrib['Contribution_%'] = ((sku_contrib['Total_Complaints'] / total_tickets) * 100).round(2)

            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.write("### Top Contributing SKUs")
                st.dataframe(sku_contrib, use_container_width=True, hide_index=True)
            
            with col_b:
                st.write("### SKU Category Split")
                cat_split = f_df['SKU_Cat'].value_counts()
                st.table(cat_split)

            st.markdown("---")
            st.write("### SKU Wise Disposition Breakdown")
            sku_l4_pivot = f_df.groupby(['SKU_Name', 'L4']).size().unstack(fill_value=0)
            st.dataframe(sku_l4_pivot, use_container_width=True)

        # (Other tabs t1, t2, t3, t4 logic remains consistent)

else:
    st.info("👋 Please upload the bbdaily complaint dump to begin.")
