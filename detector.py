import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from statsmodels.tsa.seasonal import STL
from sklearn.cluster import DBSCAN
from math import radians
import urllib.parse
import os
from dotenv import load_dotenv

load_dotenv()

class EarthquakeAnomalyDetector:
    def __init__(self, db_connection_string):
        """Initialize the engine with your PostGIS database connection."""
        self.engine = create_engine(db_connection_string)

    def _fetch_data(self, start_date, end_date):
        """Extract spatial and temporal data from PostGIS."""
        # Adjust table name and columns based on your PostGIS schema
        query = f"""
            SELECT event_time, latitude, longitude, magnitude, region_id
            FROM earthquakes
            WHERE event_time >= '{start_date}' AND event_time <= '{end_date}'
        """
        df = pd.read_sql(query, self.engine)
        df['event_time'] = pd.to_datetime(df['event_time'])
        return df

    def establish_temporal_baseline(self, df):
        """Aggregate and run STL decomposition to get residuals."""
        print("Calculating temporal baselines and residuals...")
        
        # Aggregate by region and week (using earthquake count as our metric)
        agg_df = df.groupby(['region_id', pd.Grouper(key='event_time', freq='W')]).size().reset_index(name='quake_count')
        
        results = []
        for region, group in agg_df.groupby('region_id'):
            group = group[['event_time', 'quake_count']].set_index('event_time').sort_index()
            # Forward fill to ensure a continuous time series index
            group = group.asfreq('W', fill_value=0)
            
            # STL needs at least two full seasonal cycles. We assume a 52-week cycle.
            if len(group) < 104:
                continue 
                
            # Run STL Decomposition
            stl = STL(group['quake_count'], seasonal=53, robust=True)
            res = stl.fit()
            
            group['predicted'] = res.trend + res.seasonal
            group['residual'] = res.resid
            
            # Define an anomaly as a residual > 2 standard deviations from the mean
            threshold = group['residual'].mean() + (2 * group['residual'].std())
            group['is_temporal_anomaly'] = group['residual'] > threshold
            
            group['region_id'] = region
            results.append(group.reset_index())
            
        return pd.concat(results, ignore_index=True)

    def detect_spatial_hotspots(self, df_original, df_temporal):
        """DBSCAN clustering on high-deviation residuals."""
        print("Running spatial clustering on temporal anomalies...")
        
        # 1. Isolate the regions and weeks where the temporal model flagged an anomaly
        anomalies = df_temporal[df_temporal['is_temporal_anomaly']]
        
        if anomalies.empty:
            return pd.DataFrame() # No anomalies found
            
        # 2. Map anomalies back to their precise coordinates
        # We merge back to original data to get the exact lat/lons of events that occurred during that anomalous week
        hotspot_data = []
        for _, row in anomalies.iterrows():
            week_start = row['event_time']
            week_end = week_start + pd.Timedelta(days=7)
            
            events = df_original[
                (df_original['region_id'] == row['region_id']) & 
                (df_original['event_time'] >= week_start) & 
                (df_original['event_time'] < week_end)
            ]
            hotspot_data.append(events)
            
        if not hotspot_data:
             return pd.DataFrame()
             
        spatial_df = pd.concat(hotspot_data)
        
        # 3. Spatial Clustering using DBSCAN and Haversine distance
        # Convert lat/lon to radians for the haversine metric
        coords = np.radians(spatial_df[['latitude', 'longitude']].values)
        
        # eps is the max distance between two samples for them to be considered as in the same neighborhood.
        # Earth radius is approx 6371 km. Let's use a 50km radius: 50 / 6371
        kms_per_radian = 6371.0088
        epsilon = 50 / kms_per_radian
        
        db = DBSCAN(eps=epsilon, min_samples=3, algorithm='ball_tree', metric='haversine')
        spatial_df['cluster_id'] = db.fit_predict(coords)
        
        # Filter out noise (DBSCAN assigns -1 to outliers)
        true_hotspots = spatial_df[spatial_df['cluster_id'] != -1].copy()
        return true_hotspots

    def run_pipeline(self, start_date, end_date):
        """Day 14: Orchestrate the engine and return the final report."""
        print(f"--- Starting Pipeline for {start_date} to {end_date} ---")
        
        df_raw = self._fetch_data(start_date, end_date)
        if df_raw.empty:
            return "No data found for this date range."
            
        df_temporal = self.establish_temporal_baseline(df_raw)
        df_hotspots = self.detect_spatial_hotspots(df_raw, df_temporal)
        
        if df_hotspots.empty:
            return "Pipeline Complete: No significant spatio-temporal hotspots detected."
            
        # Compile final anomaly report
        report = df_hotspots.groupby(['cluster_id']).agg(
            centroid_lat=('latitude', 'mean'),
            centroid_lon=('longitude', 'mean'),
            event_count=('magnitude', 'count'),
            max_magnitude=('magnitude', 'max'),
            affected_regions=('region_id', lambda x: ', '.join(set(x))),
            time_window_start=('event_time', 'min'),
            time_window_end=('event_time', 'max')
        ).reset_index()
        
        return report

# --- Execution Example ---
#my_password = os.getenv('POSTGRES_PASSWORD')
#encoded_password = urllib.parse.quote_plus(my_password)
#CONN_STR = f'postgresql://postgres:{encoded_password}@localhost:5432/staddb'

#detector = EarthquakeAnomalyDetector(CONN_STR)
#anomaly_report = detector.run_pipeline('2022-06-20', '2026-06-19')
#print(anomaly_report)
