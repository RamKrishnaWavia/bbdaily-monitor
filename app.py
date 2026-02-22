import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Master Tower")
pd.set_option('future.no_silent_downcasting', True)

st.title("🛡️ BBD 2.0 Integrity & Fraud Master Tower - RK")
st.markdown("---")

# --- 2. MULTI-FILE UPLOADER ---
uploaded_files = st.file_uploader("📂 Upload Complaint Dump (CSV)", type="csv", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    
    for file in uploaded_files:
        try:
            # Handle encodings
            try:
                temp_df = pd.read_csv(file, encoding='utf-8', low_memory=False)
            except:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1', low_memory=False)
            
            # --- DATA PRE-CLEANING ---
            temp_df['Source_CSV'] = file.name
            temp_df.columns = temp_df.columns.str.strip()
            
            # --- STRICT DD-MM-YYYY DATE PARSING ---
            # Prioritizing your specific column name
            date_priority = ['Complaint Created Date & Time', 'Created Date', 'Date', 'date']
            date_col = None
            
            for candidate in date_priority:
                if candidate in temp_df.columns:
                    date_col = candidate
                    break
            
            if date_col:
                # FORCE DD-MM-YYYY Logic
                # dayfirst=True ensures 01-02 is Feb 1st, not Jan 2nd
                temp_df['Date_Parsed'] = pd.to_datetime(
                    temp_df[date_col], 
                    dayfirst=True, 
                    errors='coerce'
                )
                
                # Filter out rows where date parsing failed
                temp_df = temp_df.dropna(subset=['Date_Parsed'])
                temp_df['Date'] = temp_df['Date_Parsed'].dt.date
            
            # --- COLUMN MAPPING TOOLKIT (Comprehensive) ---
            col_map = {
                'Lob': ['Lob', 'LOB', 'lob', 'Line of Business'],
                'Ticket_ID': ['Ticket ID', 'Complaint ID', 'Complaint Number', 'Ticket Number', 'id'],
                'L4': ['Level 4', 'Agent Disposition Levels 4', 'Category', 'L4 Category'],
                'L5': ['Level 5', 'Agent Disposition Levels 5', 'Sub Category', 'L5 Category'],
                'CEE_Name_1': ['Cee Name', 'Cee name', 'CEE NAME', 'Delivery Executive'],
                'CEE_ID_1': ['CEE Number', 'cee_number', 'CEE ID', 'cee_id', 'DE ID'],
                'Member_Id': ['Member Id', 'member_id', 'Member ID', 'Customer ID'],
                'Hub': ['Hub', 'HUB', 'hub', 'FC NAME', 'Hub Name', 'Store'],
                'City': ['City', 'CITY', 'city'],
                'VIP': ['Is VIP Customer', 'vip', 'VIP Tag', 'VIP Status']
            }
            
            for standard, options in col_map.items():
                for opt in options:
                    if opt in temp_df.columns:
                        temp_df[standard] = temp_df[opt]
                        break
            
            # --- THUMB RULE: bbdaily-b2c ONLY ---
            if 'Lob' in temp_df.columns:
                temp_df = temp_df[temp_df['Lob'].astype(str).str.contains('bbdaily-b2c', case=False, na=False)].copy()
                
                if not temp_df.empty and 'Date' in temp_df.columns:
                    # Final value cleaning
                    def clean_val(val):
                        v = str(val).strip()
                        return v if v not in ['', 'nan', '-', 'None', '0', '0.0'] else "Unknown"

                    temp_df['CEE_Name'] = temp_df['CEE_Name_1'].apply(clean_val)
                    temp_df['CEE_ID'] = temp_df['CEE_ID_1'].apply(clean_val)
                    temp_df['Ticket_ID'] = temp_df['Ticket_ID'].apply(clean_val)
                    temp_df['Member_Id'] = temp_df['Member_Id'].apply(clean_val)
                    temp_df['L4'] = temp_df['L4'].astype(str).str.strip()
                    temp_df['L5'] = temp_df['L5'].astype(str).str.strip()
                    temp_df['VIP'] = temp_df['VIP'].astype(str).str.strip()
                    
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error processing {file.name}: {e}")

    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        
        # --- 3. SIDEBAR CONTROLS ---
        st.sidebar.header("🎛️ Control Panel")
        
        # Date Status Diagnostic
        st.sidebar.info(f"📅 Format: DD-MM-YYYY (Forced)")
        
        # Integrated Multi-ID Search
        st.sidebar.subheader("🔍 Integrated Search")
        search_id = st.sidebar.text_input("Enter Ticket / CEE / Member ID", "").strip()
        
        # Date Range Selection
        col_d1, col_d2 = st.sidebar.columns(2)
        with col_d1:
            start_date = st.sidebar.date_input("Date From", df['Date'].min())
        with col_d2:
            end_date = st.sidebar.date_input("Date To", df['Date'].max())
        
        # Geographic Filters
        selected_cities = st.sidebar.multiselect("City", sorted(df['City'].unique()), default=sorted(df['City'].unique()))
        selected_hubs = st.sidebar.multiselect("Store (Hub)", sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()), default=sorted(df[df['City'].isin(selected_cities)]['Hub'].unique()))
        
        # Grouping Toggles
        st.sidebar.subheader("Grouping Selection")
        group_by_l4 = st.sidebar.checkbox("Group by Level 4", value=True)
        group_by_l5 = st.sidebar.checkbox("Group by Level 5", value=False)

        # APPLY FILTERS
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date) & (df['City'].isin(selected_cities)) & (df['Hub'].isin(selected_hubs))
        filtered_df = df[mask]
        
        if search_id:
            filtered_df = filtered_df[
                (filtered_df['Ticket_ID'].astype(str).str.contains(search_id, case=False)) |
                (filtered_df['CEE_ID'].astype(str).str.contains(search_id, case=False)) |
                (filtered_df['Member_Id'].astype(str).str.contains(search_id, case=False))
            ]

        # --- 4. AGGREGATION ENGINE ---
        def generate_report(data, groups, s_date, e_date, include_daily=False):
            report = data.groupby(groups).size().reset_index(name='Range_Total')
            buckets = [("0-5 Days", 0, 5), ("5-10 Days", 6, 10), ("10-15 Days", 11, 15), ("15-30 Days", 16, 30)]
            for label, s_off, e_off in buckets:
                b_end, b_start = e_date - timedelta(days=s_off), e_date - timedelta(days=e_off)
                b_counts = data[(data['Date'] >= b_start) & (data['Date'] <= b_end)].groupby(groups).size().reset_index(name=label)
                report = report.merge(b_counts, on=groups, how='left').fillna(0)
            
            if include_daily:
                curr = s_date
                while curr <= e_date:
                    d_str = curr.strftime('%d-%b')
                    day_data = data[data['Date'] == curr].groupby(groups).size().reset_index(name=d_str)
                    report = report.merge(day_data, on=groups, how='left').fillna(0)
                    curr += timedelta(days=1)
            
            numeric_cols = report.columns.difference(groups)
            report[numeric_cols] = report[numeric_cols].astype(int)
            return report

        # --- 5. TABS ---
        tabs = st.tabs(["📊 Performance", "👤 CEE Summary", "🔍 CEE Overview", "🛒 Cust Summary", "🔎 Cust Overview"])
        
        cee_groups = ['CEE_ID', 'CEE_Name', 'Hub', 'City']
        if group_by_l4: cee_groups.append('L4')
        if group_by_l5: cee_groups.append('L5')
        
        cust_groups = ['Member_Id', 'City', 'Hub', 'VIP']
        if group_by_l4: cust_groups.append('L4')
        if group_by_l5: cust_groups.append('L5')

        with tabs[0]:
            st.subheader("Data & File Audit")
            if not filtered_df.empty:
                st.write("**File Source Verification (Confirm Jan Rows Here)**")
                file_chk = filtered_df.groupby(['Source_CSV', 'Date']).size().reset_index(name='Rows')
                st.dataframe(file_chk.sort_values('Date'), use_container_width=True)
                st.line_chart(filtered_df.groupby('Date').size())

        with tabs[1]:
            st.dataframe(generate_report(filtered_df, cee_groups, start_date, end_date, False).sort_values('Range_Total', ascending=False), use_container_width=True)

        with tabs[2]:
            st.dataframe(generate_report(filtered_df, cee_groups + ['Ticket_ID', 'Date', 'Source_CSV'], start_date, end_date, True).sort_values('Date', ascending=False), use_container_width=True)

        with tabs[3]:
            st.dataframe(generate_report(filtered_df, cust_groups, start_date, end_date, False).sort_values('Range_Total', ascending=False), use_container_width=True)

        with tabs[4]:
            st.dataframe(generate_report(filtered_df, cust_groups + ['Ticket_ID', 'Date', 'Source_CSV'], start_date, end_date, True).sort_values('Date', ascending=False), use_container_width=True)
            
    else:
        st.warning("No data found. Ensure your dates in CSV are DD-MM-YYYY format.")
else:
    st.info("Upload CSV. Forced format: DD-MM-YYYY.")
