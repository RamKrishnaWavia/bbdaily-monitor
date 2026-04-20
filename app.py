import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    layout="wide", 
    page_title="bbdaily Integrity Master Tower", 
    page_icon="🛡️"
)

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

# --- 3. COMPREHENSIVE MAPPING DICTIONARY ---
SUBTYPE_MAP = {
    'D_R_Fruits & Vegetables': 'Others', 'Damaged Product': 'Others',
    'Delay Delivery': 'Delay Delivery', 'EXPIRED': 'Near to Expiry',
    'False Commitment': 'Others', 'False Commitment ': 'Others',
    'FILLRATE': 'Others', 'Free Product Not Delivered ': 'Others',
    'GRAMMAGE': 'Others', 'IBND': 'IBND',
    'Incorrect action in the admin/Kapture': 'Others',
    'Incorrect Marking by CEE': 'Others',
    'Incorrect order acknowledgement': 'IOA', 'MRP': 'Others',
    'Near to Expiry': 'Near to Expiry', 'OOS': 'Others',
    'Others': 'Others', 'Partial Product': 'Partial Product',
    'Payment Related': 'Others', 'Rude Behaviour': 'Others',
    'Rude on Call': 'Others', 'Token Issue': 'Others',
    'Transaction': 'Others', 'Unable to login': 'Others',
    'Unable to place order': 'Others', 'Voucher': 'Others',
    'Website / App is slow': 'Others', 'Wrong / Incomplete Info': 'Others',
    'Wrong credit /debit raised': 'Others', 'Wrong Product': 'Others',
    'Wrong Product (Organic)': 'Others'
}

# --- 4. DATA ENGINE ---
uploaded_files = st.file_uploader("📂 Upload Complaint Dump", type=["csv", "xlsx", "xls"], accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
            if file.name.endswith('.csv'):
                temp_df = pd.read_csv(file, encoding='ISO-8859-1', low_memory=False)
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
                'Lob': ['Lob', 'LOB'], 'Ticket_ID': ['Ticket ID', 'Complaint ID'],
                'L4': ['Agent Disposition Levels 4', 'Level 4'], 'L5': ['Agent Disposition Levels 5', 'Level 5'],
                'Sub_type': ['Sub type', 'Subtype'], 'CEE_Name': ['Cee Name', 'CEE NAME'],
                'CEE_ID': ['CEE Number', 'CEE ID'], 'Member_Id': ['Member Id', 'Member ID'],
                'Hub': ['Hub', 'HUB', 'Store'], 'City': ['City', 'CITY'],
                'VIP': ['Is VIP Customer', 'VIP Tag', 'VIP Status', 'vip'],
                'SKU_Name': ['SKU Name', 'Product Name'], 'SKU_Cat': ['SKU Category']
            }
            for standard, options in col_map.items():
                for opt in options:
                    if opt in temp_df.columns:
                        temp_df[standard] = temp_df[opt]
                        break

            if 'VIP' not in temp_df.columns: temp_df['VIP'] = 'No'

            # Clean IDs
            for c in ['CEE_ID', 'Member_Id', 'Ticket_ID']:
                if c in temp_df.columns:
                    temp_df[c] = temp_df[c].astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', 'Unknown')

            # Category Mapping
            if 'Sub_type' in temp_df.columns:
                def map_category(val):
                    val_s = str(val).strip()
                    if val_s.upper().startswith('Q_I_'): return 'Quality Issues'
                    return SUBTYPE_MAP.get(val_s, 'Others')
                temp_df['Complaints_Category'] = temp_df['Sub_type'].apply(map_category)
            else:
                temp_df['Complaints_Category'] = 'Others'
            
            all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error loading file: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        for col in ['L4', 'L5', 'Complaints_Category', 'Hub', 'City', 'CEE_Name', 'SKU_Name', 'SKU_Cat', 'VIP']:
            df[col] = df[col].fillna("Unknown") if col in df.columns else "Unknown"
        
        df['VIP'] = df['VIP'].astype(str).replace(['nan', 'None', '0.0', '0'], 'No')

        # --- 5. SIDEBAR ---
        st.sidebar.header("🎛️ Control Panel")
        sel_lob = st.sidebar.multiselect("Select LOB", sorted(df['Lob'].unique()), default=sorted(df['Lob'].unique()))
        start_date = st.sidebar.date_input("From Date", df['Date_Only'].min())
        end_date = st.sidebar.date_input("To Date", df['Date_Only'].max())
        sel_cities = st.sidebar.multiselect("Select City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))

        st.sidebar.subheader("📌 Filters")
        sel_l4 = st.sidebar.multiselect("Filter L4", sorted(df['L4'].unique()), default=sorted(df['L4'].unique()))
        sel_cat = st.sidebar.multiselect("Filter Complaints Category", sorted(df['Complaints_Category'].unique()), default=sorted(df['Complaints_Category'].unique()))
        sel_vip = st.sidebar.multiselect("Filter VIP", sorted(df['VIP'].unique()), default=sorted(df['VIP'].unique()))

        # --- 6. FILTERING ---
        mask = (df['Lob'].isin(sel_lob)) & (df['Date_Only'] >= start_date) & (df['Date_Only'] <= end_date) & \
               (df['City'].isin(sel_cities)) & (df['L4'].isin(sel_l4)) & \
               (df['Complaints_Category'].isin(sel_cat)) & (df['VIP'].isin(sel_vip))
        f_df = df[mask].copy()

        # --- 7. TABS ---
        t = st.tabs(["📊 Summary", "👤 CEE Summary", "🔍 CEE Overview", "🛒 Customer Summary", "🔎 Customer Overview", "🏪 Store Summary", "📦 SKU Analysis", "📂 Category Analysis"])

        with t[0]: # SUMMARY
            st.markdown('<div class="availability-banner">Executive Dashboard</div>', unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Tickets", len(f_df))
            c2.metric("Unique CEEs", f_df['CEE_ID'].nunique())
            c3.metric("Unique Members", f_df['Member_Id'].nunique())
            c4.metric("Hubs", f_df['Hub'].nunique())
            cola, colb = st.columns(2)
            cola.write("### Complaints Category Distribution")
            cola.bar_chart(f_df['Complaints_Category'].value_counts())
            colb.write("### L4 Distribution")
            colb.bar_chart(f_df['L4'].value_counts())

        with t[2]: # CEE OVERVIEW
            if not f_df.empty:
                pivot = f_df.groupby(['Hub', 'CEE_ID', 'CEE_Name', 'L4'], dropna=False).size().unstack(fill_value=0).reset_index()
                pivot['Grand Total'] = pivot.select_dtypes(include=[np.number]).sum(axis=1)
                st.dataframe(pivot.sort_values('Grand Total', ascending=False), use_container_width=True, hide_index=True)

        with t[5]: # STORE SUMMARY
            st.subheader("Hub & Category Deep Dive")
            store_p = f_df.groupby(['Hub', 'Complaints_Category']).size().unstack(fill_value=0).reset_index()
            store_p['Grand Total'] = store_p.select_dtypes(include=[np.number]).sum(axis=1)
            st.dataframe(store_p.sort_values('Grand Total', ascending=False), use_container_width=True, hide_index=True)

        with t[6]: # SKU ANALYSIS (Filtered)
            sku_f = f_df[(f_df['SKU_Name'].notna()) & (f_df['SKU_Name'] != "Unknown") & (f_df['SKU_Name'].astype(str).str.lower() != "nan")].copy()
            if not sku_f.empty:
                sku_d = sku_f.groupby(['SKU_Cat', 'SKU_Name']).size().reset_index(name='Count')
                sku_d['% Contribution'] = ((sku_d['Count'] / len(f_df)) * 100).round(2)
                st.dataframe(sku_d.sort_values('Count', ascending=False), use_container_width=True, hide_index=True)
            else:
                st.warning("No SKU data.")

        with t[7]: # CATEGORY ANALYSIS (PER DATE CALCULATION)
            st.markdown('<div class="availability-banner">📂 Category Contribution divided by Daily Unique Customers</div>', unsafe_allow_html=True)
            
            # 1. Total unique customers per date
            daily_unique_cust = f_df.groupby('Date_Only')['Member_Id'].nunique().reset_index(name='Daily_Total_Cust')
            
            # 2. Count of complaints per category per date
            cat_daily = f_df.groupby(['Date_Only', 'Complaints_Category']).size().reset_index(name='Cat_Count')
            
            # 3. Merge and calculate the rate
            cat_merged = pd.merge(cat_daily, daily_unique_cust, on='Date_Only')
            cat_merged['Rate_per_Daily_Cust'] = (cat_merged['Cat_Count'] / cat_merged['Daily_Total_Cust']).round(4)
            
            # 4. Aggregate for the final table view
            final_cat_a = cat_merged.groupby('Complaints_Category').agg({
                'Cat_Count': 'sum',
                'Rate_per_Daily_Cust': 'mean' # Averaged across the selected date range
            }).reset_index().rename(columns={'Cat_Count': 'Total_Tickets', 'Rate_per_Daily_Cust': 'Avg_Daily_Rate'})
            
            # 5. Add Total Contribution %
            final_cat_a['%_Contribution'] = ((final_cat_a['Total_Tickets'] / len(f_df)) * 100).round(2)
            
            st.dataframe(final_cat_a.sort_values('Total_Tickets', ascending=False), use_container_width=True, hide_index=True)
            st.info("💡 'Avg_Daily_Rate' = Sum of (Daily Category Count / Daily Unique Customers) divided by Number of Days.")

        # Customer Summary Logic
        with t[3]:
            st.dataframe(f_df.groupby(['Member_Id', 'City', 'VIP']).size().reset_index(name='Tickets').sort_values('Tickets', ascending=False), use_container_width=True, hide_index=True)

else:
    st.info("👋 System Ready. Please upload data.")
