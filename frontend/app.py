import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import os

# --- Configuration ---
st.set_page_config(page_title="Earthquake Anomaly Detector", layout="wide")
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1/anomalies")

# --- UI Header ---
st.title("🌍 Spatial-Temporal Earthquake Anomalies")
st.markdown("Detecting statistically significant seismic deviations over time and space.")

# --- Sidebar Controls ---
st.sidebar.header("Filter Parameters")
start_date = st.sidebar.date_input("Start Date", pd.to_datetime("2023-01-01"))
end_date = st.sidebar.date_input("End Date", pd.to_datetime("today"))

if st.sidebar.button("Detect Anomalies"):
    with st.spinner("Querying API and running clustering algorithms..."):
        
        # --- Fetch Data ---
        try:
            params = {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            }
            response = requests.get(API_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("data"):
                st.warning("No anomalies detected in this time range.")
            else:
                # --- Process Data ---
                df = pd.DataFrame(data["data"])
                
                st.success(f"Detected {len(df)} anomaly clusters.")
                
                # --- Map Visualization ---
                # Size of bubble = event_count, Color = max_magnitude
                fig = px.scatter_mapbox(
                    df, 
                    lat="centroid_lat", 
                    lon="centroid_lon", 
                    size="event_count",
                    color="max_magnitude",
                    color_continuous_scale=px.colors.sequential.YlOrRd,
                    hover_name="affected_regions",
                    hover_data=["max_magnitude", "event_count", "time_window_start"],
                    zoom=3, 
                    title="Anomaly Hotspots (Japan & Surrounding Regions)"
                )
                
                # Use a dark map style (CartoDB dark matter) so the bright heat colors pop
                fig.update_layout(mapbox_style="carto-darkmatter")
                fig.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
                
                st.plotly_chart(fig, use_container_width=True)
                
                # --- Raw Data Table ---
                st.subheader("Cluster Details")
                st.dataframe(
                    df[["cluster_id", "affected_regions", "max_magnitude", "event_count"]], 
                    use_container_width=True
                )
                
        except Exception as e:
            st.error(f"Failed to connect to API: {e}")
