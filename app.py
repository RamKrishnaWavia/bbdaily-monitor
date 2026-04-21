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
        # Fill missing grouping values
        fill_cols = ['L4', 'L5', 'Complaints_Category', 'Hub', 'City', 'CEE_Name', 'SKU_Name', 'SKU_Cat', 'VIP', 'Lob']
        for col in fill_cols:
            if col in df.columns: df[col] = df[col].fillna("Unknown")
            else: df[col] = "Unknown"
        
        df['VIP'] = df['VIP'].astype(str).replace(['nan', 'None', '0.0', '0'], 'No')
        df['City_Store'] = df['City'] + " - " + df['Hub']

        # --- 5. SIDEBAR CONTROL PANEL ---
        st.sidebar.header("🎛️ Control Panel")
        
        # Core Filters
        sel_lob = st.sidebar.multiselect("Select LOB", sorted(df['Lob'].unique()), default=sorted(df['Lob'].unique()))
        start_date = st.sidebar.date_input("From Date", df['Date_Only'].min())
        end_date = st.sidebar.date_input("To Date", df['Date_Only'].max())
        sel_cities = st.sidebar.multiselect("Select City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        
        # Hub Filter (Filtered by City)
        hub_list = sorted(df[df['City'].isin(sel_cities)]['Hub'].unique())
        sel_hubs = st.sidebar.multiselect("Select Hub/Store", hub_list, default=hub_list)

        st.sidebar.subheader("📌 Performance Filters")
        # CEE Filter
        cee_list = sorted(df[df['Hub'].isin(sel_hubs)]['CEE_Name'].unique())
        sel_cee = st.sidebar.multiselect("Filter by CEE Name", cee_list, default=cee_list)
        
        # Category & L4 Filters
        sel_cat = st.sidebar.multiselect("Filter Complaints Category", sorted(df['Complaints_Category'].unique()), default=sorted(df['Complaints_Category'].unique()))
        sel_l4 = st.sidebar.multiselect("Filter L4 Categories", sorted(df['L4'].unique()), default=sorted(df['L4'].unique()))
        sel_vip = st.sidebar.multiselect("Filter VIP Status", sorted(df['VIP'].unique()), default=sorted(df['VIP'].unique()))

        # --- 6. MASTER FILTERING ---
        mask = (df['Lob'].isin(sel_lob)) & \
               (df['Date_Only'] >= start_date) & \
               (df['Date_Only'] <= end_date) & \
               (df['City'].isin(sel_cities)) & \
               (df['Hub'].isin(sel_hubs)) & \
               (df['CEE_Name'].isin(sel_cee)) & \
               (df['Complaints_Category'].isin(sel_cat)) & \
               (df['L4'].isin(sel_l4)) & \
               (df['VIP'].isin(sel_vip))
        
        f_df = df[mask].copy()

        # --- 7. TABS ---
        t = st.tabs(["📊 Summary", "👤 CEE Summary", "🔍 CEE Overview", "🛒 Customer Summary", "🔎 Customer Overview", "🏪 Store Summary", "📦 SKU Analysis", "📂 Category Analysis"])

        # TAB 1: EXECUTIVE SUMMARY
        with t[0]:
            st.markdown('<div class="availability-banner">Executive Analytical Dashboard</div>', unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Tickets", len(f_df))
            c2.metric("Unique CEEs", f_df['CEE_ID'].nunique())
            c3.metric("Unique Members", f_df['Member_Id'].nunique())
            c4.metric("Active Hubs", f_df['Hub'].nunique())
            
            cola, colb = st.columns(2)
            cola.write("### Category Distribution")
            cola.bar_chart(f_df['Complaints_Category'].value_counts())
            colb.write("### Top Hubs by Volume")
            colb.bar_chart(f_df['Hub'].value_counts().head(10))

        # TAB 2: CEE SUMMARY
        with t[1]:
            st.subheader("CEE Performance Summary")
            cee_sum = f_df.groupby(['Hub', 'CEE_ID', 'CEE_Name']).size().reset_index(name='Tickets')
            st.dataframe(cee_sum.sort_values('Tickets', ascending=False), use_container_width=True, hide_index=True)

        # TAB 3: CEE OVERVIEW (PIVOT)
        with t[2]:
            st.subheader("CEE Category-wise (L4) Breakdown")
            if not f_df.empty:
                pivot = f_df.groupby(['Hub', 'CEE_ID', 'CEE_Name', 'L4'], dropna=False).size().unstack(fill_value=0).reset_index()
                num_cols = pivot.select_dtypes(include=[np.number]).columns
                pivot['Grand Total'] = pivot[num_cols].sum(axis=1)
                st.dataframe(pivot.sort_values('Grand Total', ascending=False), use_container_width=True, hide_index=True)

        # TAB 4: CUSTOMER SUMMARY (City - Store combined)
        with t[3]:
            st.subheader("Customer Volume (City - Hub)")
            cust_sum = f_df.groupby(['Member_Id', 'City_Store', 'VIP']).size().reset_index(name='Total_Tickets')
            st.dataframe(cust_sum.sort_values('Total_Tickets', ascending=False), use_container_width=True, hide_index=True)

        # TAB 5: CUSTOMER OVERVIEW (City - Store combined)
        with t[4]:
            st.subheader("Customer L4 Breakdown")
            if not f_df.empty:
                pivot_c = f_df.groupby(['Member_Id', 'City_Store', 'VIP', 'L4'], dropna=False).size().unstack(fill_value=0).reset_index()
                num_cols_c = pivot_c.select_dtypes(include=[np.number]).columns
                pivot_c['Grand Total'] = pivot_c[num_cols_c].sum(axis=1)
                st.dataframe(pivot_c.sort_values('Grand Total', ascending=False), use_container_width=True, hide_index=True)

        # TAB 6: STORE SUMMARY (Grand Total row included)
        with t[5]:
            st.subheader("Hub & Category Matrix")
            store_p = f_df.groupby(['Hub', 'Complaints_Category']).size().unstack(fill_value=0).reset_index()
            num_cols_s = store_p.select_dtypes(include=[np.number]).columns
            store_p['Grand Total'] = store_p[num_cols_s].sum(axis=1)
            
            # Total row
            hub_totals = store_p[num_cols_s].sum().to_frame().T
            hub_totals['Hub'] = 'GRAND TOTAL'
            hub_totals['Grand Total'] = hub_totals[num_cols_s].sum(axis=1)
            
            store_display = pd.concat([store_p.sort_values('Grand Total', ascending=False), hub_totals], ignore_index=True)
            st.dataframe(store_display, use_container_width=True, hide_index=True)

        # TAB 7: SKU ANALYSIS (Cleaned)
        with t[6]:
            st.subheader("SKU Contribution (Excluding Blanks)")
            sku_f = f_df[(f_df['SKU_Name'].notna()) & (f_df['SKU_Name'] != "Unknown") & (f_df['SKU_Name'].astype(str).str.lower() != "nan")].copy()
            if not sku_f.empty:
                sku_d = sku_f.groupby(['SKU_Cat', 'SKU_Name']).size().reset_index(name='Count')
                sku_d['% Contribution'] = ((sku_d['Count'] / len(f_df)) * 100).round(2)
                st.dataframe(sku_d.sort_values('Count', ascending=False), use_container_width=True, hide_index=True)
            else:
                st.warning("No valid SKU data available.")

        # TAB 8: CATEGORY ANALYSIS (Denominator = Unique Customers)
        with t[7]:
            st.markdown('<div class="availability-banner">📂 Category Rate & % Contribution</div>', unsafe_allow_html=True)
            
            total_unique_cust = f_df['Member_Id'].nunique()
            total_tickets = len(f_df)
            
            cat_final = f_df.groupby('Complaints_Category').agg(
                Total_Complaints=('Ticket_ID', 'count'),
                Unique_Customers=('Member_Id', 'nunique')
            ).reset_index()
            
            cat_final['Category_Rate'] = (cat_final['Total_Complaints'] / total_unique_cust if total_unique_cust > 0 else 0).round(4)
            cat_final['%_Contribution'] = ((cat_final['Total_Complaints'] / total_tickets) * 100).round(2)
            
            # Grand Total row
            total_row = pd.DataFrame({
                'Complaints_Category': ['GRAND TOTAL'],
                'Total_Complaints': [total_tickets],
                'Unique_Customers': [total_unique_cust],
                'Category_Rate': [(total_tickets / total_unique_cust if total_unique_cust > 0 else 0)],
                '%_Contribution': [100.00]
            })
            
            cat_display = pd.concat([cat_final.sort_values('Total_Complaints', ascending=False), total_row], ignore_index=True)
            st.write(f"**Overall Unique Customers in this Filter:** `{total_unique_cust}`")
            st.dataframe(cat_display, use_container_width=True, hide_index=True)

else:
    st.info("👋 System Ready. Please upload the complaint dump files.")
