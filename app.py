import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower")
pd.set_option('future.no_silent_downcasting', True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.markdown("### Multi-View Performance Dashboard")
st.info("Frozen Logic: Dual View (CEE/Customer) | Dynamic Roll-up | bbdaily-b2c Rule")

# --- 2. MULTI-FILE UPLOADER ---
uploaded_files = st.file_uploader("Upload CSV files", type="csv", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
            # Handle encoding issues
            try:
                temp_df = pd.read_csv(file, encoding='utf-8', low_memory=False)
            except:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1', low_memory=False)
            
            # Column Mapping
            col_map = {
                'Lob': ['Lob', 'LOB', 'lob'],
                'Date_Raw': ['Date', 'Complaint Created Date & Time', 'date'],
                'L4': ['Level 4', 'Agent Disposition Levels 4', 'Category'],
                'L5': ['Level 5', 'Agent Disposition Levels 5'],
                'CEE_Name_1': ['Cee Name', 'Cee name', 'CEE NAME'],
                'CEE_ID_1': ['CEE Number', 'cee_number', 'CEE ID', 'cee_id'],
                'Member_Id': ['Member Id', 'member_id', 'Member ID'],
                'Hub': ['Hub', 'HUB', 'hub'],
                'City': ['City', 'CITY', 'city']
            }
            
            for standard, options in col_map.items():
                for opt in options:
                    if opt in temp_df.columns:
                        temp_df[standard] = temp_df[opt]
                        break
            
            # --- THUMB RULE: bbdaily-b2c ONLY ---
            if 'Lob' in temp_df.columns:
                temp_df = temp_df[temp_df['Lob'].astype(str).str.contains('bbdaily-b2c', case=False, na=False)].copy()
                
                if not temp_df.empty and 'Date_Raw' in temp_df.columns:
                    temp_df['Date'] = pd.to_datetime(temp_df['Date_Raw'], errors='coerce').dt.date
                    
                    # Clean Values
                    def clean_val(val):
                        v = str(val).strip()
                        return v if v not in ['', 'nan', '-', 'None', '0', '0.0'] else "Unknown"

                    temp_df['CEE_Name'] = temp_df['CEE_Name_1'].apply(clean_val)
                    temp_df['CEE_ID'] = temp_df['CEE_ID_1'].apply(clean_val)
                    temp_df['Member_Id'] = temp_df['Member_Id'].apply(clean_val)
                    temp_df['L4'] = temp_df['L4'].astype(str).str.strip()
                    temp_df['L5'] = temp_df['L5'].astype(str).str.strip()
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True).dropna(subset=['Date'])
        
        # --- 3. SIDEBAR FILTERS ---
        st.sidebar.header("Global Filters")
        
        all_cities = sorted(df['City'].dropna().unique())
        selected_cities = st.sidebar.multiselect("Select City", all_cities, default=all_cities)
        
        available_dates = sorted(df['Date'].unique())
        col_d1, col_d2 = st.sidebar.columns(2)
        with col_d1:
            start_date = st.date_input("From Date", min(available_dates))
        with col_d2:
            end_date = st.date_input("To Date", max(available_dates))
        
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date) & (df['City'].isin(selected_cities))
        filtered_df = df[mask]

        # Category Filters
        l4_options = sorted(filtered_df['L4'].unique())
        selected_l4 = st.sidebar.multiselect("Level 4 Filter (Leave empty for total sum)", l4_options)
        
        l5_options = sorted(filtered_df[filtered_df['L4'].isin(selected_l4)]['L5'].unique()) if selected_l4 else sorted(filtered_df['L5'].unique())
        selected_l5 = st.sidebar.multiselect("Level 5 Filter", l5_options)

        # Filtering logic for the display data
        final_display_df = filtered_df.copy()
        if selected_l4: final_display_df = final_display_df[final_display_df['L4'].isin(selected_l4)]
        if selected_l5: final_display_df = final_display_df[final_display_df['L5'].isin(selected_l5)]

        # Aggregation Logic
        def generate_report(data, groups, s_date, e_date):
            report = data.groupby(groups).size().reset_index(name='Range_Total')
            buckets = [("0-5 Days", 0, 5), ("5-10 Days", 6, 10), ("10-15 Days", 11, 15), ("15-30 Days", 16, 30)]
            for label, start_off, end_off in buckets:
                b_end = e_date - timedelta(days=start_off)
                b_start = e_date - timedelta(days=end_off)
                mask_b = (data['Date'] >= b_start) & (data['Date'] <= b_end)
                b_counts = data[mask_b].groupby(groups).size().reset_index(name=label)
                report = report.merge(b_counts, on=groups, how='left').fillna(0)
            
            curr = s_date
            while curr <= e_date:
                d_str = curr.strftime('%d-%b') # Shorter date format for columns
                day_data = data[data['Date'] == curr].groupby(groups).size().reset_index(name=d_str)
                report = report.merge(day_data, on=groups, how='left').fillna(0)
                curr += timedelta(days=1)

            numeric_cols = report.columns.difference(groups)
            report[numeric_cols] = report[numeric_cols].astype(int)
            return report

        # --- 4. TABS INTERFACE ---
        tab1, tab2 = st.tabs(["👤 CEE Summary", "🛒 Customer Summary"])

        with tab1:
            group_cee = ['CEE_ID', 'CEE_Name', 'Hub', 'City']
            if selected_l4: group_cee.append('L4')
            if selected_l5: group_cee.append('L5')
            
            st.subheader("CEE Complaint Performance")
            if not final_display_df.empty:
                cee_table = generate_report(final_display_df, group_cee, start_date, end_date)
                st.dataframe(cee_table.sort_values(by='Range_Total', ascending=False), use_container_width=True)
            else:
                st.warning("No data for CEE view.")

        with tab2:
            group_cust = ['Member_Id', 'City']
            if selected_l4: group_cust.append('L4')
            if selected_l5: group_cust.append('L5')
            
            st.subheader("High Complaint Customers")
            if not final_display_df.empty:
                cust_table = generate_report(final_display_df, group_cust, start_date, end_date)
                st.dataframe(cust_table.sort_values(by='Range_Total', ascending=False), use_container_width=True)
            else:
                st.warning("No data for Customer view.")

    else:
        st.error("No valid 'bbdaily-b2c' data found.")
else:
    st.info("Please upload your CMS Ticket reports.")
