import folium
import pandas as pd

# Load your cleaned data
df = pd.read_csv('Outputs/cleaned_earthquakes.csv')

# Create a base map centered roughly over India
india_map = folium.Map(location=[35.6528, 139.8395], zoom_start=5, tiles='CartoDB positron')

# Plot the top 500 largest earthquakes to keep the browser fast
top_quakes = df

for idx, row in top_quakes.iterrows():
    folium.CircleMarker(
        location=[row['latitude'], row['longitude']],
        radius=row['magnitude'] * 1.5, # Scale size by magnitude
        popup=f"Mag: {row['magnitude']} <br> Place: {row['place_description']}",
        color='crimson',
        fill=True,
        fill_color='crimson'
    ).add_to(india_map)

# Save to an interactive HTML file
india_map.save('earthquake_map.html')
print("Map saved to earthquake_map.html. Open it in your browser!")
