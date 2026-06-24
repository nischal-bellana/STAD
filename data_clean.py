import json
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

def run_earthquake_etl(csv_path, geojson_path, output_csv_path=None):
    print("--- Step 1: Loading Data ---")
    # Load raw USGS earthquake data
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} raw earthquake records.")
    
    # Load India States GeoJSON
    india_gdf = gpd.read_file(geojson_path)
    # Ensure you know the exact column name for state names/IDs in your GeoJSON
    # Common names: 'ST_NM', 'state_name', 'NAME_1'. Adjust 'state_name' below if needed.
    state_column_name = 'nam' 
    if state_column_name not in india_gdf.columns:
        raise KeyError(f"Column '{state_column_name}' not found in GeoJSON. Available columns: {list(india_gdf.columns)}")

    print("--- Step 2: Cleaning & Parsing Data ---")
    # Drop rows missing crucial spatial/metric values
    df = df.dropna(subset=['latitude', 'longitude', 'mag', 'time', 'id'])
    
    # Convert timestamps to ISO-8601 strings / Datetime objects
    df['time'] = pd.to_datetime(df['time'])
    df['updated'] = pd.to_datetime(df['updated'])
    
    print("--- Step 3: Converting to GeoDataFrame ---")
    # Create spatial geometry points (assuming USGS standard WGS84 EPSG:4326)
    geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
    eq_gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

    print("--- Step 4: Spatial Join for region_id ---")
    # Ensure both datasets share the exact same Coordinate Reference System (CRS)
    if eq_gdf.crs != india_gdf.crs:
        india_gdf = india_gdf.to_crs(eq_gdf.crs)
        
    # Spatial Join: Find which state polygon contains each earthquake point
    # 'how="left"' ensures we keep earthquakes that occurred offshore/outside state borders
    joined_gdf = gpd.sjoin(eq_gdf, india_gdf[[state_column_name, 'geometry']], how='left', predicate='within')
    
    # Rename the matched spatial column to your standardized 'region_id'
    joined_gdf = joined_gdf.rename(columns={state_column_name: 'region_id'})
    
    # Gracefully handle earthquakes that happened in marine regions outside state lines
    joined_gdf['region_id'] = joined_gdf['region_id'].fillna('Outside Border')

    print("--- Step 5: Structuring into Standardized Schema ---")
    # Define columns to isolate into the JSONB metadata field
    metadata_cols = [
        'magType', 'nst', 'gap', 'dmin', 'rms', 'net', 
        'horizontalError', 'depthError', 'magError', 'magNst', 
        'status', 'locationSource', 'magSource'
    ]
    
    # Convert those columns to a single JSON string column per row
    def row_to_json(row):
        # Extract metadata attributes, safely converting NaN values to None for clean JSON output
        meta_dict = {col: (None if pd.isna(row[col]) else row[col]) for col in metadata_cols if col in row}
        return json.dumps(meta_dict)

    joined_gdf['metadata'] = joined_gdf.apply(row_to_json, axis=1)

    # Rename and select only the columns matching your database schema
    final_df = pd.DataFrame({
        'event_id': joined_gdf['id'],
        'event_time': joined_gdf['time'].dt.strftime('%Y-%m-%d %H:%M:%S%z'),
        'latitude': joined_gdf['latitude'],
        'longitude': joined_gdf['longitude'],
        'geom': joined_gdf['geometry'].apply(lambda x: x.wkt), # Export as Well-Known Text (WKT) for SQL consumption
        'magnitude': joined_gdf['mag'],
        'depth_km': joined_gdf['depth'],
        'region_id': joined_gdf['region_id'],
        'place_description': joined_gdf['place'],
        'event_type': joined_gdf['type'],
        'updated_time': joined_gdf['updated'].dt.strftime('%Y-%m-%d %H:%M:%S%z'),
        'metadata': joined_gdf['metadata']
    })

    print(f"--- Processing Complete. Processed {len(final_df)} rows. ---")
    
    if output_csv_path:
        final_df.to_csv(output_csv_path, index=False)
        print(f"Saved cleaned data to {output_csv_path}")
        
    return final_df

# Example Usage:
#df_cleaned = run_earthquake_etl('query.csv', 'japan_prefectures.geojson', 'Outputs/cleaned_earthquakes.csv')
