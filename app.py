import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from google.oauth2 import service_account
from datetime import datetime, timedelta
import io

# --- 1. CONFIGURATION ---
FOLDER_NAME = "CEE Performance and CX Monitoring"
SERVICE_ACCOUNT_FILE = 'credentials.json' 
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

st.set_page_config(layout="wide", page_title="bbdaily Integrity Control Tower")

# --- 2. GOOGLE DRIVE API CONNECTION ---
@st.cache_resource
def get_drive_service():
    # Authenticates using the credentials.json file you upload to GitHub
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def fetch_latest_file_from_drive():
    service = get_drive_service()
    
    # Locate the folder ID
    folder_query = f"name = '{FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder'"
    folder_results = service.files().list(q=folder_query).execute().get('files', [])
    
    if not folder_results:
        st.error(f"Folder '{FOLDER_NAME}' not found in Drive. Ensure it is shared with the Service Account email.")
        return None, None
    
    folder_id = folder_results[0]['id']
    
    # List the most recent CSV file in that folder
    file_results = service.files().list(
        q=f"'{folder_id}' in parents and mimeType = 'text/csv'",
        orderBy="modifiedTime desc", 
        pageSize=1
    ).execute().get('files', [])
    
    if not file_results:
        return None, None
    
    file_id = file_results[0]['id']
    file_name = file_results[0]['name']
    
    # Download the file content into memory
    request = service.files().get_media(fileId=file_id)
    return io.BytesIO(request.execute()), file_name

# --- 3. DATA PROCESSING & DASHBOARD ---
data_stream, file_name = fetch_latest_file_from_drive()

if data_stream:
    # Load 1 Lakh Rows
    df = pd.read_csv(data_stream)
    
    # MANDATORY THUMB RULE FILTERS
    df = df[df['Lob'] == 'bbdaily-b2c'].copy()
    df['Date'] = pd.to_datetime(df['Complaint Created Date & Time'], errors='coerce').dt.date
    
    st.sidebar.info(f"📁 Processing File: {file_name}")

    # --- DYNAMIC FILTERS ---
    st.sidebar.header("Navigation Filters")
    
    # Date Selection
    available_dates = sorted(df['Date'].dropna().unique(), reverse=True)
    if available_dates:
        selected_date = st.sidebar.selectbox("Select Analysis Date", available_dates)
    
    # City & Store Filters
    all_cities = sorted(df['City'].dropna().unique())
    selected_cities = st.sidebar.multiselect("City Filter", all_cities, default=all_cities)
    
    city_filtered_df = df[df['City'].isin(selected_cities)]
    all_hubs = sorted(city_filtered_df['Hub'].dropna().unique())
    selected_hubs = st.sidebar.multiselect("Store/Hub Filter", all_hubs, default=all_hubs)

    # Apply Final Filter
    final_df = city_filtered_df[city_filtered_df['Hub'].isin(selected_hubs)]

    # --- METRICS OVERVIEW ---
    st.title("🛡️ bbdaily Integrity Control Tower")
    st.markdown(f"**Reporting Period:** {selected_date} | **Segment:** bbdaily-b2c")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Complaints", len(final_df))
    m2.metric("VIP Complaints", len(final_df[final_df['Is VIP Customer'] == 'Yes']))
    m3.metric("Unique CEEs Active", final_df['CEE ID'].nunique())

    # --- TIME-SERIES BUCKET LOGIC (The Core Tracker) ---
    intervals = {'1D': 1, '2D': 2, '3D': 3, '4D': 4, '7D': 7, '30D': 30}
    
    # Group by CEE and Level 4 Category
    cee_matrix = final_df.groupby(['CEE ID', 'CEE NAME', 'Agent Disposition Levels 4', 'Hub', 'City']).agg(
        VIP_Impact=('Is VIP Customer', lambda x: (x == 'Yes').sum())
    ).reset_index()

    for label, days in intervals.items():
        cutoff = selected_date - timedelta(days=days)
        # Filter for the specific time window
        window_mask = (final_df['Date'] <= selected_date) & (final_df['Date'] > cutoff)
        counts = final_df[window_mask].groupby(['CEE ID', 'Agent Disposition Levels 4']).size().reset_index(name=label)
        cee_matrix = cee_matrix.merge(counts, on=['CEE ID', 'Agent Disposition Levels 4'], how='left').fillna(0)

    # --- VISUALIZATION ---
    st.divider()
    st.subheader("📍 CEE Complaint Frequency by Level 4 Category")
    st.write("Tracking repeat issues across 1, 2, 3, 4, 7, and 30 day windows.")
    st.dataframe(cee_matrix.sort_values(by='1D', ascending=False), use_container_width=True)

    st.divider()
    st.subheader("👤 Customer Fraud Watchlist (Member ID)")
    # Identify customers with high refund/complaint frequency
    fraud_df = final_df.groupby(['Member Id', 'Is VIP Customer']).agg(
        Total_Complaints=('Ticket ID', 'count'),
        Refund_Count=('Agent Disposition Levels 5', lambda x: (x == 'Refunded').sum())
    ).reset_index()
    
    st.dataframe(fraud_df.sort_values(by='Total_Complaints', ascending=False), use_container_width=True)

else:
    st.warning("Awaiting CSV file in the 'CEE Performance and CX Monitoring' folder...")
