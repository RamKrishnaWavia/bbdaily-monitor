import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="bbdaily Integrity Control Tower")

st.title("🛡️ bbdaily Integrity & Refund Misuse Tower")
st.markdown("### Focus: Customer-wise Complaints & Potential Refund Misuse")

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
            
            # Column Mapping
            col_map = {
                'Lob': ['Lob', 'LOB'],
                'Date_Raw': ['Date', 'Complaint Created Date & Time'],
                'Category': ['Level 4', 'Agent Disposition Levels 4', 'Category'],
                'Member': ['Member Id', 'Member ID'],
                'Hub': ['Hub', 'HUB'],
                'City': ['City', 'CITY'],
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
        
        # --- 3. REFUND IDENTIFICATION LOGIC ---
        # We flag rows as 'Refund' if Category mentions Credited or Refunded
        refund_keywords = ['credited', 'refund', 'refunded', 'amount']
        df['Is_Refund_Incident'] = df['Category'].astype(str).str.lower().apply(
            lambda x: 1 if any(k in x for k in refund_keywords) else 0
        )

        # --- 4. SIDEBAR ---
        available_dates = sorted(df['Date'].unique())
        st.sidebar.header("Filters")
        date_range = st.sidebar.date_input("Analysis Window", [min(available_dates), max(available_dates)])
        start_date, end_date = date_range[0], (date_range[1] if len(date_range)>1 else date_range[0])
        
        mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
        final_df = df[mask]

        # --- 5. CUSTOMER WATCHLIST (Misuse Detection) ---
        st.subheader("🕵️ Customer-wise Complaint & Refund Summary")
        st.write("Targeting users with high repeat 'Amount Credited' incidents.")

        # Grouping for Misuse Analysis
        cust_cols = ['Member', 'Hub', 'City']
        if 'Is_VIP' in final_df.columns: cust_cols.insert(1, 'Is_VIP')
        
        cust_matrix = final_df.groupby(cust_cols).agg(
            Total_Complaints=('Member', 'count'),
            Refund_Incidents=('Is_Refund_Incident', 'sum'),
            Unique_Categories=('Category', 'nunique')
        ).reset_index()

        # Calculate Refund Percentage (High % indicates potential misuse)
        cust_matrix['Refund_Ratio %'] = (cust_matrix['Refund_Incidents'] / cust_matrix['Total_Complaints'] * 100).round(1)

        # Time Buckets for Refund Incidents (To see if they are doing it daily)
        analysis_anchor = end_date
        intervals = {'Refund_1D': 1, 'Refund_7D': 7, 'Refund_30D': 30}
        for label, days in intervals.items():
            cutoff = analysis_anchor - timedelta(days=days)
            win_mask = (final_df['Date'] <= analysis_anchor) & (final_df['Date'] > cutoff) & (final_df['Is_Refund_Incident'] == 1)
            counts = final_df[win_mask].groupby(cust_cols).size().reset_index(name=label)
            cust_matrix = cust_matrix.merge(counts, on=cust_cols, how='left').fillna(0)

        # Sort by high refund incidents
        st.dataframe(cust_matrix.sort_values(by=['Refund_Incidents', 'Total_Complaints'], ascending=False), use_container_width=True)

        # --- 6. DRILL DOWN: View Specific Categories for Top Misusers ---
        st.divider()
        st.subheader("📋 Drill-down: What are these customers claiming?")
        top_member = st.selectbox("Select Member ID to investigate", cust_matrix.sort_values(by='Refund_Incidents', ascending=False)['Member'].head(20))
        
        if top_member:
            member_details = final_df[final_df['Member'] == top_member][['Date', 'Category', 'Hub', 'Is_Refund_Incident']]
            st.table(member_details)

        # Download
        st.download_button("📥 Export Fraud Watchlist", cust_matrix.to_csv(index=False), "refund_misuse_report.csv")
    else:
        st.error("No valid data found.")
else:
    st.info("Upload 'complaints.csv' to detect refund misuse.")
