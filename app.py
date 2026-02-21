import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Control Tower")

st.title("🛡️ bbdaily Integrity Control Tower")
st.markdown("### Source: `complaints.csv` (Fix for Encoding Error)")

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
            # FIX: Try different encodings to stop the 'utf-8' decode error
            try:
                temp_df = pd.read_csv(file, encoding='utf-8')
            except UnicodeDecodeError:
                # If UTF-8 fails, try ISO-8859-1 (common for Excel CSVs)
                file.seek(0) # Reset file pointer
                temp_df = pd.read_csv(file, encoding='ISO-8859-1')
            
            # --- THUMB RULE: Segment Filter ---
            if 'Lob' in temp_df.columns:
                temp_df = temp_df[temp_df['Lob'] == 'bbdaily-b2c'].copy()
                
                date_col = 'Complaint Created Date & Time'
                if date_col in temp_df.columns:
                    temp_df['Date'] = pd.to_datetime(temp_df[date_col], errors='coerce').dt.date
                    all_data.append(temp_df)
        except Exception as e:
            st.error(f"Error processing {file.name}: {e}")
    
    if all_data:
        df = pd.concat(all_data, ignore_index=True)
        
        # --- 3. SIDEBAR FILTERS ---
        st.sidebar.header("Navigation Filters")
        
        min_date = df['Date'].min()
        max_date = df['Date'].max()
        # Default to showing the last date if data exists
        date_range = st.sidebar.date_input("Analysis Period", [min_date, max_date])
        
        all_cities = sorted(df['City'].dropna().unique())
        selected_cities = st.sidebar.multiselect("Select City", all_cities, default=all_cities)
        
        # Date Logic handling
        start_date = date_range[0]
        end_date = date_range[1] if len(date_range) > 1 else date_range[0]
        
        mask = (df['City'].isin(selected_cities)) & (df['Date'] >= start_date) & (df['Date'] <= end_date)
        filtered_df = df[mask]
        
        all_hubs = sorted(filtered_df['Hub'].dropna().unique())
        selected_hubs = st.sidebar.multiselect("Select Store/Hub", all_hubs, default=all_hubs)
        
        final_df = filtered_df[filtered_df['Hub'].isin(selected_hubs)]

        # --- 4. THE INTEGRITY MATRIX (Time Buckets) ---
        analysis_end = end_date
        intervals = {'1D': 1, '2D': 2, '3D': 3, '4D': 4, '7D': 7, '30D': 30}
        
        cee_matrix = final_df.groupby(['CEE ID', 'CEE NAME', 'Agent Disposition Levels 4', 'Hub', 'City']).agg(
            VIP_Complaints=('Is VIP Customer', lambda x: (x == 'Yes').sum())
        ).reset_index()

        for label, days in intervals.items():
            cutoff = analysis_end - timedelta(days=days)
            window_mask = (final_df['Date'] <= analysis_end) & (final_df['Date'] > cutoff)
            counts = final_df[window_mask].groupby(['CEE ID', 'Agent Disposition Levels 4']).size().reset_index(name=label)
            cee_matrix = cee_matrix.merge(counts, on=['CEE ID', 'Agent Disposition Levels 4'], how='left').fillna(0)

        # --- 5. UI DISPLAY ---
        st.subheader("CEE Integrity Matrix")
        st.dataframe(cee_matrix.sort_values(by='1D', ascending=False), use_container_width=True)
        
        st.subheader("High-Frequency Customer Watchlist")
        cust_fraud = final_df.groupby(['Member Id', 'Is VIP Customer']).size().reset_index(name='Total_Complaints')
        st.dataframe(cust_fraud.sort_values(by='Total_Complaints', ascending=False).head(50))
        
        # Download button
        csv = cee_matrix.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Result", data=csv, file_name="cee_report.csv", mime='text/csv')

    else:
        st.warning("No valid data found for bbdaily-b2c.")
else:
    st.warning("Please upload 'complaints.csv' files.")
