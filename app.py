import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower")

st.title("🛡️ bbdaily Integrity & Fraud Master Tower")
st.markdown("### Combined: CEE Performance & Customer Refund Misuse")

# --- 2. MULTI-FILE UPLOADER ---
uploaded_files = st.file_uploader("Upload 'complaints.csv' files", type="csv", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
            try:
                temp_df = pd.read_csv(file, encoding='utf-8')
            except UnicodeDecodeError:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1')
            
            # Flexible Column Mapping
            col_map = {
                'Lob': ['Lob', 'LOB'],
                'Date_Raw': ['Date', 'Complaint Created Date & Time'],
                'Category': ['Level 4', 'Agent Disposition Levels 4', 'Category'],
                'CEE_Name': ['Cee Name', 'CEE NAME'],
                'CEE_ID': ['CEE Number', 'CEE ID'],
                'Hub': ['Hub', 'HUB'],
                'City': ['City', 'CITY'],
                'Member': ['Member Id', 'Member ID'],
                'Is_VIP': ['Is VIP Customer', 'VIP']
            }
            for standard, options in col_map.items():
                for opt in options:
                    if opt in temp_df.columns:
                        temp_df[standard] = temp_df[opt]
                        break
            
            # Thumb Rule: bbdaily-b2c
            if 'Lob' in temp_df.columns:
                temp_df = temp_df[temp_df['Lob'] == 'bbdaily-b2c'].copy()
                if 'Date_Raw' in temp_df.columns:
                    temp_df['Date'] = pd.to_datetime(temp_df['Date_Raw'], dayfirst=True, errors='coerce').dt.date
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True).dropna(subset=['Date'])
        
        # --- 3. LOGIC TAGGING ---
        refund_keywords = ['credited', 'refund', 'refunded', 'amount']
        df['Is_Refund'] = df['Category'].astype(str).str.lower().apply(lambda x: 1 if any(k in x for k in refund_keywords) else 0)

        # --- 4. SIDEBAR FILTERS (City & Store) ---
        st.sidebar.header("Global Filters")
        available_dates = sorted(df['Date'].unique())
        date_range = st.sidebar.date_input("Analysis Window", [min(available_dates), max(available_dates)])
        start_date, end_date = date_range[0], (date_range[1] if len(date_range)>1 else date_range[0])
        
        # City Filter
        all_cities = sorted(df['City'].dropna().unique()) if 'City' in df.columns else []
        selected_cities = st.sidebar.multiselect("Select City", all_cities, default=all_cities)
        
        # Apply City and Date Filter
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
        if 'City' in df.columns: mask = mask & (df['City'].isin(selected_cities))
        filtered_df = df[mask]
        
        # Store/Hub Filter
        all_hubs = sorted(filtered_df['Hub'].dropna().unique()) if 'Hub' in filtered_df.columns else []
        selected_hubs = st.sidebar.multiselect("Select Store/Hub", all_hubs, default=all_hubs)
        final_df = filtered_df[filtered_df['Hub'].isin(selected_hubs)] if 'Hub' in filtered_df.columns else filtered_df

        # --- 5. TABS FOR DASHBOARDS ---
        tab1, tab2 = st.tabs(["📊 CEE Complaints Dashboard", "🕵️ Customer Refund Misuse"])

        with tab1:
            st.subheader("CEE Integrity Matrix (Level 4)")
            cee_cols = ['CEE_ID', 'CEE_Name', 'Category', 'Hub', 'City']
            cee_matrix = final_df.groupby(cee_cols).size().reset_index(name='Total')
            
            intervals = {'1D': 1, '2D': 2, '3D': 3, '4D': 4, '30D': 30}
            for label, days in intervals.items():
                cutoff = end_date - timedelta(days=days)
                win_mask = (final_df['Date'] <= end_date) & (final_df['Date'] > cutoff)
                counts = final_df[win_mask].groupby(cee_cols).size().reset_index(name=label)
                cee_matrix = cee_matrix.merge(counts, on=cee_cols, how='left').fillna(0)
            
            st.dataframe(cee_matrix.sort_values(by='1D', ascending=False), use_container_width=True)
            st.download_button("📥 Download CEE Report", cee_matrix.to_csv(index=False), "cee_report.csv")

        with tab2:
            st.subheader("Customer Watchlist (Refund Tracking)")
            cust_cols = ['Member', 'Hub', 'City']
            if 'Is_VIP' in final_df.columns: cust_cols.insert(1, 'Is_VIP')
            
            cust_matrix = final_df.groupby(cust_cols).agg(
                Total_Complaints=('Member', 'count'),
                Refund_Incidents=('Is_Refund', 'sum'),
            ).reset_index()
            cust_matrix['Refund_Ratio_%'] = (cust_matrix['Refund_Incidents'] / cust_matrix['Total_Complaints'] * 100).round(1)
            
            st.dataframe(cust_matrix.sort_values(by='Refund_Incidents', ascending=False).head(50), use_container_width=True)
            st.download_button("📥 Download Fraud Report", cust_matrix.to_csv(index=False), "refund_misuse.csv")

    else:
        st.error("No valid 'bbdaily-b2c' data found.")
else:
    st.info("Upload 'complaints.csv' files to see the dashboards.")
