import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_config(layout="wide", page_title="bbdaily Integrity Master Tower")

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.markdown("### Combined: CEE Performance & Customer Refund Misuse")
st.info("Frozen Logic: Full 30-Day Matrix | Sidebar L4/L5 Filters | Clean CEE Mapping")

# --- 2. MULTI-FILE UPLOADER ---
uploaded_files = st.file_uploader("Upload 'complaints.csv' or 'CmsTicketDetailReport.csv' files", type="csv", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
            try:
                temp_df = pd.read_csv(file, encoding='utf-8')
            except:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1')
            
            # Flexible Column Mapping for CEE and Categories
            col_map = {
                'Lob': ['Lob', 'LOB', 'lob'],
                'Date_Raw': ['Date', 'Complaint Created Date & Time', 'date'],
                'L4': ['Level 4', 'Agent Disposition Levels 4', 'Category'],
                'L5': ['Level 5', 'Agent Disposition Levels 5'],
                'CEE_Name_1': ['Cee Name', 'Cee name'],
                'CEE_Name_2': ['CEE NAME', 'cee_name'],
                'CEE_ID_1': ['CEE Number', 'cee_number'],
                'CEE_ID_2': ['CEE ID', 'cee_id'],
                'Hub': ['Hub', 'HUB', 'hub'],
                'City': ['City', 'CITY', 'city'],
                'Member': ['Member Id', 'Member ID', 'member_id'],
                'Is_VIP': ['Is VIP Customer', 'VIP', 'is_vip']
            }
            
            for standard, options in col_map.items():
                for opt in options:
                    if opt in temp_df.columns:
                        temp_df[standard] = temp_df[opt]
                        break
            
            # --- THUMB RULE: bbdaily-b2c ONLY ---
            if 'Lob' in temp_df.columns:
                temp_df = temp_df[temp_df['Lob'] == 'bbdaily-b2c'].copy()
                
                if not temp_df.empty and 'Date_Raw' in temp_df.columns:
                    temp_df['Date'] = pd.to_datetime(temp_df['Date_Raw'], dayfirst=True, errors='coerce').dt.date
                    
                    # --- CLEANING CEE NAME & ID (Handling '-' and Blanks) ---
                    def clean_val(val):
                        v = str(val).strip()
                        return v if v not in ['', 'nan', '-', 'None', '0', '0.0'] else None

                    temp_df['CEE_Name'] = temp_df['CEE_Name_1'].apply(clean_val).fillna(temp_df['CEE_Name_2'].apply(clean_val)).fillna("Unknown_CEE")
                    temp_df['CEE_ID'] = temp_df['CEE_ID_1'].apply(clean_val).fillna(temp_df['CEE_ID_2'].apply(clean_val)).fillna("Unknown_ID")
                    
                    # Fill other blanks
                    temp_df['L4'] = temp_df['L4'].fillna("Not Categorized")
                    temp_df['L5'] = temp_df['L5'].fillna("Not Categorized")
                    
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True).dropna(subset=['Date'])
        
        # Refund Logic
        refund_keywords = ['credited', 'refund', 'refunded', 'amount']
        df['Is_Refund'] = df['L4'].astype(str).str.lower().apply(lambda x: 1 if any(k in x for k in refund_keywords) else 0)

        # --- 3. SIDEBAR FILTERS ---
        st.sidebar.header("Global Filters")
        
        # Date Filter
        available_dates = sorted(df['Date'].unique())
        date_range = st.sidebar.date_input("Analysis Window", [min(available_dates), max(available_dates)])
        start_date = date_range[0]
        end_date = date_range[1] if len(date_range) > 1 else date_range[0]
        
        # City & Store Filters
        all_cities = sorted(df['City'].dropna().unique())
        selected_cities = st.sidebar.multiselect("Select City", all_cities, default=all_cities)
        
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
        if 'City' in df.columns: mask = mask & (df['City'].isin(selected_cities))
        city_filtered = df[mask]
        
        # Level 4 & Level 5 Sidebar Filters
        all_l4 = sorted(city_filtered['L4'].unique())
        selected_l4 = st.sidebar.multiselect("Filter by Level 4", all_l4, default=all_l4)
        l4_filtered = city_filtered[city_filtered['L4'].isin(selected_l4)]
        
        all_l5 = sorted(l4_filtered['L5'].unique())
        selected_l5 = st.sidebar.multiselect("Filter by Level 5", all_l5, default=all_l5)
        l5_filtered = l4_filtered[l4_filtered['L5'].isin(selected_l5)]
        
        all_hubs = sorted(l5_filtered['Hub'].dropna().unique())
        selected_hubs = st.sidebar.multiselect("Select Store/Hub", all_hubs, default=all_hubs)
        
        final_df = l5_filtered[l5_filtered['Hub'].isin(selected_hubs)]

        # --- 4. TABS ---
        tab1, tab2, tab3 = st.tabs(["📊 CEE 30-Day Matrix (L4)", "🔍 CEE 30-Day Matrix (L5)", "🕵️ Customer Misuse"])

        def generate_full_30d_matrix(data, group_cols, anchor_date):
            # Base group
            matrix = data.groupby(group_cols).size().reset_index(name='Total_Period')
            # Generate 1D to 30D columns
            for d in range(1, 31):
                label = f"{d}D"
                cutoff = anchor_date - timedelta(days=d-1)
                win_mask = (data['Date'] <= anchor_date) & (data['Date'] >= cutoff)
                counts = data[win_mask].groupby(group_cols).size().reset_index(name=label)
                matrix = matrix.merge(counts, on=group_cols, how='left').fillna(0)
            return matrix

        with tab1:
            st.subheader("CEE Level 4: Rolling 30-Day Analysis")
            res_l4 = generate_full_30d_matrix(final_df, ['CEE_ID', 'CEE_Name', 'L4', 'Hub', 'City'], end_date)
            st.dataframe(res_l4.sort_values(by='1D', ascending=False), use_container_width=True)

        with tab2:
            st.subheader("CEE Level 5: Rolling 30-Day Analysis")
            res_l5 = generate_full_30d_matrix(final_df, ['CEE_ID', 'CEE_Name', 'L4', 'L5', 'Hub', 'City'], end_date)
            st.dataframe(res_l5.sort_values(by='1D', ascending=False), use_container_width=True)

        with tab3:
            st.subheader("Customer Watchlist (Refund & Misuse)")
            cust_cols = ['Member', 'Hub', 'City']
            if 'Is_VIP' in final_df.columns: cust_cols.insert(1, 'Is_VIP')
            cust_matrix = final_df.groupby(cust_cols).agg(
                Total_Complaints=('Member', 'count'),
                Refund_Incidents=('Is_Refund', 'sum'),
            ).reset_index()
            cust_matrix['Refund_Ratio_%'] = (cust_matrix['Refund_Incidents'] / cust_matrix['Total_Complaints'] * 100).round(1)
            st.dataframe(cust_matrix.sort_values(by='Refund_Incidents', ascending=False).head(50), use_container_width=True)

    else:
        st.error("No 'bbdaily-b2c' data found. Please check your LOB column.")
else:
    st.info("Upload your raw complaint files to begin.")
