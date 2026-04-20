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
        background-color: #f0f4f8; color: #1a365d; padding: 15px;
        border-radius: 10px; border-left: 5px solid #2b6cb0;
        font-weight: bold; margin-bottom: 20px; text-align: center;
    }
    .stMetric { background-color: #ffffff; padding: 10px; border-radius: 5px; border: 1px solid #e2e8f0; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower")

# --- 3. COMPREHENSIVE MAPPING DICTIONARY ---
SUBTYPE_MAP = {
    'D_R_Fruits & Vegetables': 'Others',
    'Damaged Product': 'Others',
    'Delay Delivery': 'Delay Delivery',
    'EXPIRED': 'Near to Expiry',
    'False Commitment': 'Others',
    'False Commitment ': 'Others',
    'FILLRATE': 'Others',
    'Free Product Not Delivered ': 'Others',
    'GRAMMAGE': 'Others',
    'IBND': 'IBND',
    'Incorrect action in the admin/Kapture': 'Others',
    'Incorrect Marking by CEE': 'Others',
    'Incorrect order acknowledgement': 'IOA',
    'MRP': 'Others',
    'Near to Expiry': 'Near to Expiry',
    'OOS': 'Others',
    'Others': 'Others',
    'Partial Product': 'Partial Product',
    'Payment Related': 'Others',
    'Rude Behaviour': 'Others',
    'Rude on Call': 'Others',
    'Token Issue': 'Others',
    'Transaction': 'Others',
    'Unable to login': 'Others',
    'Unable to place order': 'Others',
    'Voucher': 'Others',
    'Website / App is slow': 'Others',
    'Wrong / Incomplete Info': 'Others',
    'Wrong credit /debit raised': 'Others',
    'Wrong Product': 'Others',
    'Wrong Product (Organic)': 'Others'
}

# --- 4. DATA ENGINE ---
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
            
            # Detailed Column Mapping
            col_map = {
                'Lob': ['Lob', 'LOB', 'Line of Business'],
                'Ticket_ID': ['Ticket ID', 'Complaint ID', 'Ticket Number'],
                'L4': ['Agent Disposition Levels 4', 'Level 4', 'Category'],
                'L5': ['Agent Disposition Levels 5', 'Level 5', 'Sub Category'],
                'Sub_type': ['Sub type', 'Subtype', 'sub_type'],
                'CEE_Name': ['Cee Name', 'CEE NAME', 'Delivery Executive'],
                'CEE_ID': ['CEE Number', 'CEE ID', 'DE ID'],
                'Member_Id': ['Member Id', 'Member ID', 'Customer ID'],
                'Hub': ['Hub', 'HUB', 'Store', 'FC NAME'],
                'City': ['City', 'CITY'],
                'VIP': ['Is VIP Customer', 'VIP Tag', 'VIP Status'],
                'SKU_Name': ['SKU Name', 'Product Name', 'Item Name'],
                'SKU_Cat': ['SKU Category', 'Item Category', 'Category']
            }
            
            for standard, options in col_map.items():
                for opt in options:
                    if opt in temp_df.columns:
                        temp_df[standard] = temp_df[opt]
                        break
            
            # Clean IDs before grouping
            for c in ['CEE_ID', 'Member_Id', 'Ticket_ID']:
                if c in temp_df.columns:
                    temp_df[c] = temp_df[c].astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', 'Unknown')

            # Apply New Category Mapping
            if 'Sub_type' in temp_df.columns:
                def map_category(val):
                    val = str(val).strip()
                    if val.upper().startswith('Q_I_'): return 'Quality Issues'
                    return SUBTYPE_MAP.get(val, 'Others')
                temp_df['Complaints_Category'] = temp_df['Sub_type'].apply(map_category)
            else:
                temp_df['Complaints_Category'] = 'Others'
            
            all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error loading {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        
        # Critical: Fill missing values with "Unknown" so they don't disappear from filters
        fill_cols = ['L4', 'L5', 'Complaints_Category', 'Hub', 'City', 'CEE_Name', 'SKU_Name', 'SKU_Cat', 'Lob']
        for col in fill_cols:
            if col in df.columns: df[col] = df[col].fillna("Unknown")
            else: df[col] = "Unknown"
        
        if 'VIP' not in df.columns: df['VIP'] = 'No'
        df['VIP'] = df['VIP'].astype(str).replace(['nan', 'None', '0.0', '0'], 'No')

        # --- 5. SIDEBAR ---
        st.sidebar.header("🎛️ Control Panel")
        sel_lob = st.sidebar.multiselect("Select LOB", sorted(df['Lob'].unique()), default=sorted(df['Lob'].unique()))
        start_date = st.sidebar.date_input("From Date", df['Date_Only'].min())
        end_date = st.sidebar.date_input("To Date", df['Date_Only'].max())
        sel_cities = st.sidebar.multiselect("Select City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))

        st.sidebar.subheader("📌 Disposition Filters")
        sel_l4 = st.sidebar.multiselect("Filter L4", sorted(df['L4'].unique()), default=sorted(df['L4'].unique()))
        sel_cat = st.sidebar.multiselect("Filter Complaints Category", sorted(df['Complaints_Category'].unique()), default=sorted(df['Complaints_Category'].unique()))

        # --- 6. FILTERING ---
        mask = (df['Lob'].isin(sel_lob)) & \
               (df['Date_Only'] >= start_date) & \
               (df['Date_Only'] <= end_date) & \
               (df['City'].isin(sel_cities)) & \
               (df['L4'].isin(sel_l4)) & \
               (df['Complaints_Category'].isin(sel_cat))
        
        f_df = df[mask].copy()

        # --- 7. TABS ---
        t = st.tabs([
            "📊 Summary", "👤 CEE Summary", "🔍 CEE Overview", 
            "🛒 Customer Summary", "🔎 Customer Overview", 
            "🏪 Store Summary", "📦 SKU Analysis"
        ])

        # Unified Pivot Function to prevent blank results
        def get_safe_pivot(data, group_cols):
            if data.empty: return pd.DataFrame(columns=group_cols + ['Grand_Total'])
            pivot = data.groupby(group_cols + ['L4'], dropna=False).size().unstack(fill_value=0).reset_index()
            num_cols = pivot.select_dtypes(include=[np.number]).columns
            pivot['Grand_Total'] = pivot[num_cols].sum(axis=1)
            return pivot.sort_values('Grand_Total', ascending=False)

        with t[0]: # SUMMARY
            st.markdown('<div class="availability-banner">Executive Dashboard - Integrity Master Tower</div>', unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Tickets", len(f_df))
            c2.metric("Unique CEEs", f_df['CEE_ID'].nunique())
            c3.metric("Unique Members", f_df['Member_Id'].nunique())
            c4.metric("Active Hubs", f_df['Hub'].nunique())
            
            cola, colb = st.columns(2)
            with cola:
                st.write("### Complaints Category Split")
                st.bar_chart(f_df['Complaints_Category'].value_counts())
            with colb:
                st.write("### L4 Category Distribution")
                st.bar_chart(f_df['L4'].value_counts())

        with t[1]: # CEE SUMMARY
            st.subheader("CEE Wise Contribution")
            cee_sum = f_df.groupby(['Hub', 'CEE_ID', 'CEE_Name']).size().reset_index(name='Total_Tickets')
            st.dataframe(cee_sum.sort_values('Total_Tickets', ascending=False), use_container_width=True, hide_index=True)

        with t[2]: # CEE OVERVIEW
            st.subheader("CEE Wise L4 Breakdown")
            st.dataframe(get_safe_pivot(f_df, ['Hub', 'CEE_ID', 'CEE_Name']), use_container_width=True, hide_index=True)

        with t[3]: # CUSTOMER SUMMARY
            st.subheader("Customer Wise Contribution")
            cust_sum = f_df.groupby(['Member_Id', 'City', 'VIP']).size().reset_index(name='Total_Tickets')
            st.dataframe(cust_sum.sort_values('Total_Tickets', ascending=False), use_container_width=True, hide_index=True)

        with t[4]: # CUSTOMER OVERVIEW
            st.subheader("Customer Wise L4 Breakdown")
            st.dataframe(get_safe_pivot(f_df, ['Member_Id', 'City', 'VIP']), use_container_width=True, hide_index=True)

        with t[5]: # STORE SUMMARY
            st.subheader("Hub & Category Deep Dive")
            store_p = f_df.groupby(['Hub', 'Complaints_Category']).size().unstack(fill_value=0).reset_index()
            st.dataframe(store_p, use_container_width=True, hide_index=True)

        with t[6]: # SKU ANALYSIS
            st.subheader("SKU Wise Contribution")
            # We filter out "Unknown" from display here if you prefer, but it's better to see it for data quality
            sku_d = f_df.groupby(['SKU_Cat', 'SKU_Name']).size().reset_index(name='Count')
            sku_d['% Contribution'] = ((sku_d['Count'] / len(f_df)) * 100).round(2)
            st.dataframe(sku_d.sort_values('Count', ascending=False), use_container_width=True, hide_index=True)

else:
    st.info("👋 System Ready. Please upload your complaint dump (Excel or CSV).")
