import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static
import pyarrow.parquet as pq
import tempfile
import os

st.set_page_config(page_title="Geometry Viewer", layout="wide")

st.title("Geometry Viewer from Parquet Data")
st.write("Upload a parquet file containing geometry data to visualize on a map.")

# File uploader
uploaded_file = st.file_uploader("Choose a parquet file", type=["parquet"])

if uploaded_file is not None:
    # Save the uploaded file to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.parquet') as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name
    
    try:
        # Read the parquet file
        parquet_table = pq.read_table(tmp_path)
        df = parquet_table.to_pandas()
        
        # Check if the file contains geometry data
        geometry_cols = [col for col in df.columns if 'geom' in col.lower() or 'geometry' in col.lower()]
        
        if not geometry_cols:
            st.error("No geometry column found in the uploaded file. Please make sure your file contains a column with geometry data.")
        else:
            # Allow user to select which geometry column to use
            if len(geometry_cols) > 1:
                geometry_col = st.selectbox("Select geometry column", geometry_cols)
            else:
                geometry_col = geometry_cols[0]
            
            try:
                # Try to convert to GeoDataFrame
                gdf = gpd.GeoDataFrame(df, geometry=geometry_col)
                
                # If geometry is in WKB or WKT format, convert it
                if not isinstance(gdf.geometry.iloc[0], gpd.geoseries.GeoSeries):
                    try:
                        # Try to convert from WKT or WKB
                        gdf = gpd.GeoDataFrame(df, geometry=gpd.GeoSeries.from_wkt(df[geometry_col]))
                    except:
                        try:
                            gdf = gpd.GeoDataFrame(df, geometry=gpd.GeoSeries.from_wkb(df[geometry_col]))
                        except:
                            st.error("Could not convert the geometry column to a valid geometry. Please check your data.")
                
                # Get info about the data
                st.subheader("Data Information")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"Total rows: {len(gdf)}")
                    st.write(f"CRS: {gdf.crs}")
                with col2:
                    geometry_types = gdf.geometry.type.unique()
                    st.write(f"Geometry types: {', '.join(geometry_types)}")
                
                # Display a sample of the data
                st.subheader("Data Sample")
                st.dataframe(df.head())
                
                # Filter by geometry type
                st.subheader("Filter by Geometry Type")
                selected_types = st.multiselect("Select geometry types to display", 
                                                options=list(geometry_types),
                                                default=list(geometry_types))
                
                if selected_types:
                    filtered_gdf = gdf[gdf.geometry.type.isin(selected_types)]
                    
                    # Create a map centered on the mean of the data
                    try:
                        # Convert to EPSG:4326 if needed
                        if gdf.crs and gdf.crs != "EPSG:4326":
                            filtered_gdf = filtered_gdf.to_crs("EPSG:4326")
                        
                        # Calculate center of the data
                        bounds = filtered_gdf.total_bounds
                        center_lat = (bounds[1] + bounds[3]) / 2
                        center_lon = (bounds[0] + bounds[2]) / 2
                        
                        # Create map
                        m = folium.Map(location=[center_lat, center_lon], zoom_start=10)
                        
                        # Add different styles for different geometry types
                        for geom_type in selected_types:
                            type_gdf = filtered_gdf[filtered_gdf.geometry.type == geom_type]
                            
                            if len(type_gdf) > 0:
                                if geom_type == 'Point':
                                    # Use marker cluster for points to improve performance
                                    marker_cluster = MarkerCluster().add_to(m)
                                    for idx, row in type_gdf.iterrows():
                                        folium.Marker(
                                            location=[row.geometry.y, row.geometry.x],
                                            popup=f"ID: {idx}"
                                        ).add_to(marker_cluster)
                                
                                elif geom_type in ['LineString', 'MultiLineString']:
                                    # Add lines
                                    folium.GeoJson(
                                        type_gdf,
                                        name=geom_type,
                                        style_function=lambda x: {
                                            'color': 'blue',
                                            'weight': 3,
                                            'opacity': 0.7
                                        }
                                    ).add_to(m)
                                
                                elif geom_type in ['Polygon', 'MultiPolygon']:
                                    # Add polygons
                                    folium.GeoJson(
                                        type_gdf,
                                        name=geom_type,
                                        style_function=lambda x: {
                                            'fillColor': 'green',
                                            'color': 'black',
                                            'weight': 1,
                                            'fillOpacity': 0.5
                                        }
                                    ).add_to(m)
                        
                        # Add layer control
                        folium.LayerControl().add_to(m)
                        
                        # Display the map
                        st.subheader("Map Visualization")
                        folium_static(m)
                        
                    except Exception as e:
                        st.error(f"Error creating map: {e}")
                else:
                    st.warning("Please select at least one geometry type to display")
                
            except Exception as e:
                st.error(f"Error processing the data: {e}")
    
    except Exception as e:
        st.error(f"Error reading the parquet file: {e}")
    
    finally:
        # Clean up the temporary file
        os.unlink(tmp_path)
else:
    st.info("Please upload a parquet file containing geometry data.")

# Add some information about supported formats
st.markdown("""
### Supported formats
- The app expects geometry data in a common format (WKT, WKB, or GeoSeries)
- Supported geometry types: Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon
- The parquet file should contain at least one column with geometry data
- For best results, use data with EPSG:4326 (WGS84) coordinate reference system
""")

# Add requirements info
st.sidebar.title("Requirements")
st.sidebar.markdown("""
To run this app, you need the following Python packages:
```
streamlit
pandas
geopandas
folium
streamlit-folium
pyarrow
shapely
```

Install them with:
```
pip install streamlit pandas geopandas folium streamlit-folium pyarrow shapely
```
""")
