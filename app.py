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
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower")

# --- 3. MAPPING DICTIONARY ---
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
                'VIP': ['Is VIP Customer', 'VIP Tag'],
                'SKU_Name': ['SKU Name', 'Product Name'],
                'SKU_Cat': ['SKU Category']
            }
            for standard, options in col_map.items():
                for opt in options:
                    if opt in temp_df.columns:
                        temp_df[standard] = temp_df[opt]
                        break
            
            # Apply New Category Mapping
            if 'Sub_type' in temp_df.columns:
                def map_category(val):
                    val = str(val).strip()
                    if val.startswith('Q_I_'): return 'Qulaity Issues'
                    return SUBTYPE_MAP.get(val, 'Others')
                
                temp_df['Complaints_Category'] = temp_df['Sub_type'].apply(map_category)
            
            # Clean IDs
            for c in ['CEE_ID', 'Member_Id', 'Ticket_ID']:
                if c in temp_df.columns:
                    temp_df[c] = temp_df[c].astype(str).str.replace(r'\.0$', '', regex=True)
            
            all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error loading {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        # Fill Unknowns
        for col in ['L4', 'L5', 'Complaints_Category', 'Hub', 'City', 'CEE_Name', 'SKU_Name']:
            if col in df.columns: df[col] = df[col].fillna("Unknown")
            else: df[col] = "Unknown"

        # --- 5. SIDEBAR CONTROL PANEL ---
        st.sidebar.header("🎛️ Control Panel")
        
        sel_lob = st.sidebar.multiselect("Select LOB", sorted(df['Lob'].unique()), default=sorted(df['Lob'].unique()))
        start_date = st.sidebar.date_input("From Date", df['Date_Only'].min())
        end_date = st.sidebar.date_input("To Date", df['Date_Only'].max())
        sel_cities = st.sidebar.multiselect("Select City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))

        st.sidebar.subheader("📌 Disposition Filters")
        sel_l4 = st.sidebar.multiselect("Filter L4", sorted(df['L4'].unique()), default=sorted(df['L4'].unique()))
        
        # NEW SIDEBAR FILTER: Complaints Category Mapping
        sel_cat = st.sidebar.multiselect("Filter Complaints Category", sorted(df['Complaints_Category'].unique()), default=sorted(df['Complaints_Category'].unique()))

        search_id = st.sidebar.text_input("🔍 Quick Search (Ticket/CEE/Member ID)")

        # --- 6. FILTERING ---
        mask = (df['Lob'].isin(sel_lob)) & \
               (df['Date_Only'] >= start_date) & \
               (df['Date_Only'] <= end_date) & \
               (df['City'].isin(sel_cities)) & \
               (df['L4'].isin(sel_l4)) & \
               (df['Complaints_Category'].isin(sel_cat))
        
        f_df = df[mask].copy()

        if search_id:
            f_df = f_df[f_df['Ticket_ID'].str.contains(search_id) | 
                        f_df['CEE_ID'].str.contains(search_id) | 
                        f_df['Member_Id'].str.contains(search_id)]

        # --- 7. TABS ---
        t = st.tabs([
            "📊 Summary", "👤 CEE Summary", "🔍 CEE Overview", 
            "🛒 Customer Summary", "🔎 Customer Overview", 
            "🏪 Store Summary", "📦 SKU Analysis"
        ])

        # Helper for pivots to avoid blank data
        def get_pivot(data, group_cols):
            if data.empty: return pd.DataFrame()
            pivot = data.groupby(group_cols + ['L4'], dropna=False).size().unstack(fill_value=0).reset_index()
            num_cols = pivot.select_dtypes(include=[np.number]).columns
            pivot['Grand_Total'] = pivot[num_cols].sum(axis=1)
            return pivot.sort_values('Grand_Total', ascending=False)

        with t[0]: # SUMMARY
            st.markdown('<div class="availability-banner">Executive Dashboard - New Mapped Categories</div>', unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Tickets", len(f_df))
            m2.metric("Unique CEEs", f_df['CEE_ID'].nunique())
            m3.metric("Unique Members", f_df['Member_Id'].nunique())
            m4.metric("Active Hubs", f_df['Hub'].nunique())
            
            c1, c2 = st.columns(2)
            with c1:
                st.write("### Complaints Category Distribution")
                st.bar_chart(f_df['Complaints_Category'].value_counts())
            with c2:
                st.write("### Category Table")
                st.dataframe(f_df['Complaints_Category'].value_counts().reset_index(name='Count'), use_container_width=True, hide_index=True)

        with t[2]: # CEE OVERVIEW
            st.subheader("CEE Wise L4 Breakdown")
            res = get_pivot(f_df, ['Hub', 'CEE_ID', 'CEE_Name'])
            st.dataframe(res, use_container_width=True, hide_index=True)

        with t[4]: # CUSTOMER OVERVIEW
            st.subheader("Customer Wise L4 Breakdown")
            res = get_pivot(f_df, ['Member_Id', 'City'])
            st.dataframe(res, use_container_width=True, hide_index=True)

        with t[5]: # STORE SUMMARY
            st.subheader("Store & Category Breakdown")
            store_p = f_df.groupby(['Hub', 'Complaints_Category']).size().unstack(fill_value=0).reset_index()
            st.dataframe(store_p, use_container_width=True, hide_index=True)

        with t[6]: # SKU ANALYSIS
            st.subheader("SKU Wise Contribution")
            sku_d = f_df.groupby(['SKU_Name']).size().reset_index(name='Count')
            sku_d['% Contribution'] = ((sku_d['Count'] / len(f_df)) * 100).round(2)
            st.dataframe(sku_d.sort_values('Count', ascending=False), use_container_width=True, hide_index=True)

else:
    st.info("👋 Please upload your data file to begin.")
