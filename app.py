import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower")
pd.set_option('future.no_silent_downcasting', True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.markdown("### Consolidated CEE Performance Dashboard")
st.info("Frozen Logic: Total Roll-up on Deselect | Sidebar Filtering | bbdaily-b2c Rule")

# --- 2. MULTI-FILE UPLOADER ---
uploaded_files = st.file_uploader("Upload CSV files", type="csv", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
            try:
                temp_df = pd.read_csv(file, encoding='utf-8', low_memory=False)
            except:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1', low_memory=False)
            
            col_map = {
                'Lob': ['Lob', 'LOB', 'lob'],
                'Date_Raw': ['Date', 'Complaint Created Date & Time', 'date'],
                'L4': ['Level 4', 'Agent Disposition Levels 4', 'Category'],
                'L5': ['Level 5', 'Agent Disposition Levels 5'],
                'CEE_Name_1': ['Cee Name', 'Cee name', 'CEE NAME'],
                'CEE_ID_1': ['CEE Number', 'cee_number', 'CEE ID', 'cee_id'],
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
                    
                    def clean_val(val):
                        v = str(val).strip()
                        return v if v not in ['', 'nan', '-', 'None', '0', '0.0'] else "Unknown"

                    temp_df['CEE_Name'] = temp_df['CEE_Name_1'].apply(clean_val)
                    temp_df['CEE_ID'] = temp_df['CEE_ID_1'].apply(clean_val)
                    temp_df['L4'] = temp_df['L4'].astype(str).str.strip()
                    temp_df['L5'] = temp_df['L5'].astype(str).str.strip()
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True).dropna(subset=['Date'])
        
        # --- 3. SIDEBAR FILTERS ---
        st.sidebar.header("Global Filters")
        
        # City & Date
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

        # --- DYNAMIC GROUPING LOGIC ---
        # 1. Get unique values for filters
        l4_options = sorted(filtered_df['L4'].unique())
        selected_l4 = st.sidebar.multiselect("Level 4 Filter", l4_options) # Default Empty
        
        l5_options = sorted(filtered_df[filtered_df['L4'].isin(selected_l4)]['L5'].unique()) if selected_l4 else sorted(filtered_df['L5'].unique())
        selected_l5 = st.sidebar.multiselect("Level 5 Filter", l5_options) # Default Empty

        # 2. Determine Grouping Columns
        # If user selected items, group by them. If empty, roll up to CEE level.
        group_cols = ['CEE_ID', 'CEE_Name', 'Hub', 'City']
        
        final_display_df = filtered_df.copy()
        
        if selected_l4:
            group_cols.append('L4')
            final_display_df = final_display_df[final_display_df['L4'].isin(selected_l4)]
        
        if selected_l5:
            group_cols.append('L5')
            final_display_df = final_display_df[final_display_df['L5'].isin(selected_l5)]

        # --- 4. DATA AGGREGATION ---
        def generate_report(data, groups, s_date, e_date):
            # Total Column
            report = data.groupby(groups).size().reset_index(name='Range_Total')
            
            # Aging Buckets
            buckets = [("0-5 Days", 0, 5), ("5-10 Days", 6, 10), ("10-15 Days", 11, 15), ("15-30 Days", 16, 30)]
            for label, start_off, end_off in buckets:
                b_end = e_date - timedelta(days=start_off)
                b_start = e_date - timedelta(days=end_off)
                mask_b = (data['Date'] >= b_start) & (data['Date'] <= b_end)
                b_counts = data[mask_b].groupby(groups).size().reset_index(name=label)
                report = report.merge(b_counts, on=groups, how='left').fillna(0)
            
            # Daily Columns
            curr = s_date
            while curr <= e_date:
                d_str = curr.strftime('%d-%m-%Y')
                day_data = data[data['Date'] == curr].groupby(groups).size().reset_index(name=d_str)
                report = report.merge(day_data, on=groups, how='left').fillna(0)
                curr += timedelta(days=1)

            # Format as integers
            numeric_cols = report.columns.difference(groups)
            report[numeric_cols] = report[numeric_cols].astype(int)
            return report

        # --- 5. DISPLAY ---
        st.subheader("CEE Complaint Summary")
        if not final_display_df.empty:
            result_table = generate_report(final_display_df, group_cols, start_date, end_date)
            st.dataframe(result_table.sort_values(by='Range_Total', ascending=False), use_container_width=True)
            
            csv = result_table.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Report", csv, "cee_report.csv", "text/csv")
        else:
            st.warning("No data found for the current selection.")

    else:
        st.error("No valid 'bbdaily-b2c' data found.")
else:
    st.info("Please upload files to begin.")
