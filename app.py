import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Control Tower")

st.title("🛡️ bbdaily Integrity Control Tower")
st.markdown("### Source: `complaints.csv` (Flexible Column Mapping)")

# --- 2. MULTI-FILE UPLOADER ---
uploaded_files = st.file_uploader(
    "Select all 'complaints.csv' files", 
    type="csv", 
    accept_multiple_files=True
)

if uploaded_files:
    all_data = []
    
    for file in uploaded_files:
        try:
            # Encoding Fix (UTF-8 or ISO-8859-1 fallback)
            try:
                temp_df = pd.read_csv(file, encoding='utf-8')
            except UnicodeDecodeError:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1')
            
            # --- FLEXIBLE COLUMN MAPPING ---
            # Map columns to standard names used in the app
            col_map = {
                'Lob': ['Lob', 'LOB', 'lob'],
                'Date': ['Date', 'Complaint Created Date & Time', 'date'],
                'Category': ['Level 4', 'Agent Disposition Levels 4', 'Category', 'category'],
                'CEE_Name': ['Cee Name', 'CEE Name', 'cee_name'],
                'CEE_ID': ['CEE Number', 'CEE ID', 'CEE_ID'],
                'VIP': ['Is VIP Customer', 'VIP', 'is_vip'],
                'Hub': ['Hub', 'HUB', 'hub'],
                'City': ['City', 'CITY', 'city'],
                'Member': ['Member Id', 'Member ID', 'member_id']
            }
            
            # Apply mapping
            for standard_name, options in col_map.items():
                for option in options:
                    if option in temp_df.columns:
                        temp_df[standard_name] = temp_df[option]
                        break
            
            # --- THUMB RULE: Segment Filter ---
            if 'Lob' in temp_df.columns:
                temp_df = temp_df[temp_df['Lob'] == 'bbdaily-b2c'].copy()
                
                if 'Date' in temp_df.columns:
                    # Convert to datetime (handles different formats automatically)
                    temp_df['Date'] = pd.to_datetime(temp_df['Date'], dayfirst=True, errors='coerce').dt.date
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error processing {file.name}: {e}")
    
    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        df = df.dropna(subset=['Date']) # Remove rows where date couldn't be parsed
        
        # --- 3. SIDEBAR FILTERS ---
        st.sidebar.header("Navigation Filters")
        
        min_date = df['Date'].min()
        max_date = df['Date'].max()
        date_range = st.sidebar.date_input("Analysis Period", [min_date, max_date])
        
        # City Filter
        all_cities = sorted(df['City'].dropna().unique()) if 'City' in df.columns else []
        selected_cities = st.sidebar.multiselect("Select City", all_cities, default=all_cities)
        
        # Date Logic
        start_date = date_range[0]
        end_date = date_range[1] if len(date_range) > 1 else date_range[0]
        
        # Filter logic
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
        if 'City' in df.columns:
            mask = mask & (df['City'].isin(selected_cities))
        
        filtered_df = df[mask]
        
        # Hub Filter
        all_hubs = sorted(filtered_df['Hub'].dropna().unique()) if 'Hub' in filtered_df.columns else []
        selected_hubs = st.sidebar.multiselect("Select Store/Hub", all_hubs, default=all_hubs)
        
        final_df = filtered_df[filtered_df['Hub'].isin(selected_hubs)] if 'Hub' in filtered_df.columns else filtered_df

        # --- 4. THE INTEGRITY MATRIX (Time Buckets) ---
        if not final_df.empty:
            analysis_end = end_date
            intervals = {'1D': 1, '2D': 2, '3D': 3, '4D': 4, '7D': 7, '30D': 30}
            
            # Prepare Grouping columns
            group_cols = []
            for c in ['CEE_ID', 'CEE_Name', 'Category', 'Hub', 'City']:
                if c in final_df.columns: group_cols.append(c)
            
            # Base Matrix
            cee_matrix = final_df.groupby(group_cols).agg(
                VIP_Impact=('VIP', lambda x: (x == 'Yes').sum()) if 'VIP' in final_df.columns else ('Member', 'count')
            ).reset_index()
            
            if 'VIP' not in final_df.columns:
                cee_matrix.rename(columns={'VIP_Impact': 'Total_Complaints'}, inplace=True)

            for label, days in intervals.items():
                cutoff = analysis_end - timedelta(days=days)
                window_mask = (final_df['Date'] <= analysis_end) & (final_df['Date'] > cutoff)
                counts = final_df[window_mask].groupby(group_cols).size().reset_index(name=label)
                cee_matrix = cee_matrix.merge(counts, on=group_cols, how='left').fillna(0)

            # --- 5. UI DISPLAY ---
            st.subheader("CEE Integrity Matrix")
            st.write("Tracking frequency by Category (Level 4).")
            st.dataframe(cee_matrix.sort_values(by='1D', ascending=False), use_container_width=True)
            
            st.divider()
            st.subheader("👤 High-Frequency Customer Watchlist")
            if 'Member' in final_df.columns:
                cust_fraud = final_df.groupby(['Member']).size().reset_index(name='Complaints')
                st.dataframe(cust_fraud.sort_values(by='Complaints', ascending=False).head(50))
            
            # Download
            csv = cee_matrix.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Processed Report", data=csv, file_name="cee_report.csv", mime='text/csv')
        else:
            st.warning("No data found for the selected filters.")
    else:
        st.warning("No valid 'bbdaily-b2c' records found. Please check the 'Lob' column in your file.")
else:
    st.info("Please upload one or more 'complaints.csv' files to begin.")
