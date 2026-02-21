import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Control Tower")

st.title("🛡️ bbdaily Integrity Control Tower")
st.markdown("### Logic: bbdaily-b2c | Level 4 Category | Multi-Day Tracking")

# --- 2. MULTI-FILE UPLOADER ---
uploaded_files = st.file_uploader(
    "Upload your 'complaints.csv' files (Select multiple to see 1D/2D/3D differences)", 
    type="csv", 
    accept_multiple_files=True
)

if uploaded_files:
    all_data = []
    
    for file in uploaded_files:
        try:
            # Handle Encoding (ISO-8859-1 handles special symbols in Excel CSVs)
            try:
                temp_df = pd.read_csv(file, encoding='utf-8')
            except UnicodeDecodeError:
                file.seek(0)
                temp_df = pd.read_csv(file, encoding='ISO-8859-1')
            
            # --- FLEXIBLE COLUMN MAPPING (Based on your shared file) ---
            col_map = {
                'Lob': ['Lob', 'LOB', 'lob'],
                'Date_Raw': ['Date', 'Complaint Created Date & Time', 'date'],
                'Category': ['Level 4', 'Agent Disposition Levels 4', 'Category'],
                'CEE_Name': ['Cee Name', 'Cee name', 'CEE NAME'],
                'CEE_ID': ['CEE Number', 'CEE ID', 'CEE_ID'],
                'Hub': ['Hub', 'HUB', 'hub'],
                'City': ['City', 'CITY', 'city'],
                'Member': ['Member Id', 'Member ID', 'member_id'],
                'Is_VIP': ['Is VIP Customer', 'VIP', 'vip_flag']
            }
            
            # Map columns to standard internal names
            for standard, options in col_map.items():
                for opt in options:
                    if opt in temp_df.columns:
                        temp_df[standard] = temp_df[opt]
                        break
            
            # --- THUMB RULE: bbdaily-b2c ---
            if 'Lob' in temp_df.columns:
                temp_df = temp_df[temp_df['Lob'] == 'bbdaily-b2c'].copy()
                
                if 'Date_Raw' in temp_df.columns:
                    # Parse dates
                    temp_df['Date'] = pd.to_datetime(temp_df['Date_Raw'], dayfirst=True, errors='coerce').dt.date
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")
    
    if all_data:
        df = pd.concat(all_data, ignore_index=True).dropna(subset=['Date'])
        
        # --- DATA SUMMARY (To explain why buckets might be the same) ---
        available_dates = sorted(df['Date'].unique())
        st.sidebar.success(f"Loaded {len(available_dates)} unique dates.")
        if len(available_dates) == 1:
            st.sidebar.warning("Note: Only 1 day of data detected. 1D to 30D buckets will be identical.")

        # --- 3. SIDEBAR FILTERS ---
        st.sidebar.header("Navigation Filters")
        date_range = st.sidebar.date_input("Analysis Window", [min(available_dates), max(available_dates)])
        
        # City Filter
        all_cities = sorted(df['City'].dropna().unique()) if 'City' in df.columns else []
        selected_cities = st.sidebar.multiselect("Select City", all_cities, default=all_cities)
        
        # Start/End logic
        start_date = date_range[0]
        end_date = date_range[1] if len(date_range) > 1 else date_range[0]
        
        # Apply Filters
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
        if 'City' in df.columns:
            mask = mask & (df['City'].isin(selected_cities))
        
        filtered_df = df[mask]
        
        # Hub Filter
        all_hubs = sorted(filtered_df['Hub'].dropna().unique()) if 'Hub' in filtered_df.columns else []
        selected_hubs = st.sidebar.multiselect("Select Store/Hub", all_hubs, default=all_hubs)
        final_df = filtered_df[filtered_df['Hub'].isin(selected_hubs)] if 'Hub' in filtered_df.columns else filtered_df

        # --- 4. INTEGRITY MATRIX LOGIC ---
        if not final_df.empty:
            # The 'Today' for our logic is the end of the user's selected range
            analysis_anchor = end_date
            intervals = {'1D': 1, '2D': 2, '3D': 3, '4D': 4, '7D': 7, '30D': 30}
            
            # Columns to group by
            group_cols = []
            for c in ['CEE_ID', 'CEE_Name', 'Category', 'Hub', 'City']:
                if c in final_df.columns: group_cols.append(c)
            
            # Base data
            cee_matrix = final_df.groupby(group_cols).size().reset_index(name='Total_Period_Complaints')

            # Calculate individual buckets relative to analysis_anchor
            for label, days in intervals.items():
                cutoff = analysis_anchor - timedelta(days=days)
                # Bucket logic: (Date <= Current Selection) AND (Date > Selection - X Days)
                window_mask = (final_df['Date'] <= analysis_anchor) & (final_df['Date'] > cutoff)
                counts = final_df[window_mask].groupby(group_cols).size().reset_index(name=label)
                cee_matrix = cee_matrix.merge(counts, on=group_cols, how='left').fillna(0)

            # --- 5. UI DISPLAY ---
            st.subheader(f"CEE Integrity Matrix (Reference Date: {analysis_anchor})")
            st.info("Note: Buckets are relative to the end date of your filter.")
            
            # Sort by 1-Day (Current day issues)
            st.dataframe(cee_matrix.sort_values(by='1D', ascending=False), use_container_width=True)
            
            # Customer Watchlist
            st.divider()
            st.subheader("👤 Top Complainants (Member IDs)")
            if 'Member' in final_df.columns:
                cust_data = final_df.groupby(['Member']).size().reset_index(name='Complaints')
                st.dataframe(cust_data.sort_values(by='Complaints', ascending=False).head(20))

            # Download
            csv = cee_matrix.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export Matrix to CSV", data=csv, file_name=f"CEE_Report_{analysis_anchor}.csv")
        else:
            st.warning("No data found for the selected City/Store/Date range.")
    else:
        st.error("No valid 'bbdaily-b2c' data found in your files.")
else:
    st.info("Please upload one or more 'complaints.csv' files to generate the dashboard.")
