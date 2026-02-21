import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Control Tower")

st.title("🛡️ bbdaily Integrity Control Tower")
st.markdown("### Source: `complaints.csv` Multiple Upload")
st.info("Bypassing Drive Policy: Drag and drop all your 'complaints.csv' files here.")

# --- 2. MULTI-FILE UPLOADER ---
# This allows you to select files from different day/month folders at once.
uploaded_files = st.file_uploader(
    "Select all 'complaints.csv' files from your local folders", 
    type="csv", 
    accept_multiple_files=True
)

if uploaded_files:
    all_data = []
    
    # Process each uploaded file
    for file in uploaded_files:
        try:
            temp_df = pd.read_csv(file)
            
            # --- THUMB RULE: Segment Filter ---
            # Filtering for bbdaily-b2c immediately to save memory
            if 'Lob' in temp_df.columns:
                temp_df = temp_df[temp_df['Lob'] == 'bbdaily-b2c'].copy()
                
                # Convert Date and Time column
                date_col = 'Complaint Created Date & Time'
                if date_col in temp_df.columns:
                    temp_df['Date'] = pd.to_datetime(temp_df[date_col], errors='coerce').dt.date
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error processing {file.name}: {e}")
    
    if all_data:
        # Combine all files into one Master DataFrame
        df = pd.concat(all_data, ignore_index=True)
        
        # --- 3. SIDEBAR FILTERS ---
        st.sidebar.header("Navigation Filters")
        
        # Date Range Filter
        min_date = df['Date'].min()
        max_date = df['Date'].max()
        date_range = st.sidebar.date_input("Analysis Period", [min_date, max_date])
        
        # City & Store Filters
        all_cities = sorted(df['City'].dropna().unique())
        selected_cities = st.sidebar.multiselect("Select City", all_cities, default=all_cities)
        
        # Apply City and Date filtering
        # Check if user selected a range or single date
        start_date = date_range[0]
        end_date = date_range[1] if len(date_range) > 1 else date_range[0]
        
        filtered_df = df[
            (df['City'].isin(selected_cities)) & 
            (df['Date'] >= start_date) & 
            (df['Date'] <= end_date)
        ]
        
        all_hubs = sorted(filtered_df['Hub'].dropna().unique())
        selected_hubs = st.sidebar.multiselect("Select Store/Hub", all_hubs, default=all_hubs)
        
        final_df = filtered_df[filtered_df['Hub'].isin(selected_hubs)]

        # --- 4. THE INTEGRITY MATRIX (Time Buckets) ---
        # Today is considered the end of the selected range
        analysis_end = end_date
        intervals = {'1D': 1, '2D': 2, '3D': 3, '4D': 4, '7D': 7, '30D': 30}
        
        # Grouping by CEE and Agent Disposition Levels 4 (Category Rule)
        # We also keep VIP_Complaints separated as requested.
        cee_matrix = final_df.groupby(['CEE ID', 'CEE NAME', 'Agent Disposition Levels 4', 'Hub', 'City']).agg(
            VIP_Complaints=('Is VIP Customer', lambda x: (x == 'Yes').sum())
        ).reset_index()

        for label, days in intervals.items():
            cutoff = analysis_end - timedelta(days=days)
            window_mask = (final_df['Date'] <= analysis_end) & (final_df['Date'] > cutoff)
            counts = final_df[window_mask].groupby(['CEE ID', 'Agent Disposition Levels 4']).size().reset_index(name=label)
            cee_matrix = cee_matrix.merge(counts, on=['CEE ID', 'Agent Disposition Levels 4'], how='left').fillna(0)

        # --- 5. UI DISPLAY ---
        st.divider()
        st.subheader(f"CEE Integrity Matrix (Period: {start_date} to {end_date})")
        st.write("Tracking repeat issues by Agent Disposition Levels 4.")
        
        # Sort by 1-Day most recent complaints
        st.dataframe(cee_matrix.sort_values(by='1D', ascending=False), use_container_width=True)
        
        st.divider()
        st.subheader("👤 High-Frequency Customer Watchlist")
        cust_fraud = final_df.groupby(['Member Id', 'Is VIP Customer']).size().reset_index(name='Total_Complaints')
        st.dataframe(cust_fraud.sort_values(by='Total_Complaints', ascending=False).head(50))
        
        # Optional: Download button for the CEE report
        csv = cee_matrix.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Processed Report", data=csv, file_name="cee_integrity_report.csv", mime='text/csv')

    else:
        st.warning("No valid data found for the bbdaily-b2c segment in the uploaded files.")
else:
    st.warning("Awaiting file upload. Please drag 'complaints.csv' files here.")
