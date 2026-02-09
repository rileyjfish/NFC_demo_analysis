import geopandas as gpd
import pandas as pd
import os

# Define BASE_DIR
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))

# --- Load county boundaries ---
county_gdf = gpd.read_file(os.path.join(BASE_DIR, 'demographic_data', 'shapefiles', 'cb_2022_us_county_500k', 'cb_2022_us_county_500k.shp'))
county_gdf = county_gdf.to_crs(epsg=5070)  # Albers Equal Area

# --- Load mine facilities (EPA ULDB) ---
mines_gdf = gpd.read_file(os.path.join(BASE_DIR, 'facility_data', 'mines', 'epa_uldb.zip'))
# Use all mines, no filtering by DOCS
mines_gdf = mines_gdf.to_crs(epsg=5070)

# --- Create 10 mile buffer around each mine facility ---
buffer_distance = 10 * 1609.344  # meters
mines_gdf['buffer'] = mines_gdf.geometry.buffer(buffer_distance)

# --- Prepare buffer GeoDataFrame ---
mines_buffer_gdf = gpd.GeoDataFrame(
    mines_gdf,
    geometry=mines_gdf['buffer'],
    crs=mines_gdf.crs
)

# --- Spatial intersection: county & mine buffer ---
mines_overlap_gdf = gpd.overlay(county_gdf, mines_buffer_gdf, how='intersection')
mines_overlap_gdf['overlap_area'] = mines_overlap_gdf.geometry.area
mines_overlap_gdf['county_area'] = county_gdf.set_index('GEOID').loc[mines_overlap_gdf['GEOID'], 'geometry'].area.values
mines_overlap_gdf['percent_overlap'] = mines_overlap_gdf['overlap_area'] / mines_overlap_gdf['county_area']

# --- Prepare results for mines ---
mines_result_df = mines_overlap_gdf[['ICF_ID', 'GEOID', 'percent_overlap']].rename(columns={'GEOID': 'CountyFIPS'})
# Include Reliability instead of DOCS
mines_result_df = mines_result_df.merge(mines_gdf[['ICF_ID', 'RELIABILIT']], on='ICF_ID', how='left')

# --- Pivot to 2D table for Excel ---
mines_pivot = mines_result_df.pivot_table(
    index=['ICF_ID', 'RELIABILIT'],
    columns='CountyFIPS',
    values='percent_overlap',
    fill_value=0
)
mines_pivot.columns = ['G' + str(col) for col in mines_pivot.columns]

# --- Load uranium reserves (EIA NURE) ---

# Load and clean uranium reserves (EIA NURE)
reserves_gdf = gpd.read_file(os.path.join(BASE_DIR, 'facility_data', 'mines', 'EIA_NURE.zip'))
if not isinstance(reserves_gdf, gpd.GeoDataFrame):
    reserves_gdf = gpd.GeoDataFrame(reserves_gdf)
reserves_gdf = reserves_gdf.to_crs(epsg=5070)
print('Reserves columns:', reserves_gdf.columns)
print('Reserves geometry type:', reserves_gdf.geometry.iloc[0].geom_type)
# Clean invalid geometries
reserves_gdf = reserves_gdf[reserves_gdf.is_valid]
reserves_gdf['geometry'] = reserves_gdf.buffer(0)
reserves_gdf = reserves_gdf[reserves_gdf.is_valid]

# Ensure both are GeoDataFrames and have geometry
if not isinstance(county_gdf, gpd.GeoDataFrame):
    county_gdf = gpd.GeoDataFrame(county_gdf)
if not isinstance(reserves_gdf, gpd.GeoDataFrame):
    reserves_gdf = gpd.GeoDataFrame(reserves_gdf)
if 'geometry' not in county_gdf.columns:
    print('county_gdf missing geometry column!')
if 'geometry' not in reserves_gdf.columns:
    print('reserves_gdf missing geometry column!')
print('county_gdf type:', type(county_gdf))
print('reserves_gdf type:', type(reserves_gdf))
print('county_gdf geometry type:', county_gdf.geometry.iloc[0].geom_type)

# --- Spatial intersection: county & reserves ---
reserves_overlap_gdf = gpd.overlay(county_gdf, reserves_gdf, how='intersection')
reserves_overlap_gdf['overlap_area'] = reserves_overlap_gdf.geometry.area
reserves_overlap_gdf['county_area'] = county_gdf.set_index('GEOID').loc[reserves_overlap_gdf['GEOID'], 'geometry'].area.values
reserves_overlap_gdf['percent_overlap'] = reserves_overlap_gdf['overlap_area'] / reserves_overlap_gdf['county_area']

# --- Prepare results for reserves ---
reserves_result_df = reserves_overlap_gdf[['GEOID', 'percent_overlap']].rename(columns={'GEOID': 'CountyFIPS'})
if 'NAME' in reserves_gdf.columns:
    reserves_result_df = reserves_result_df.merge(reserves_gdf[['NAME']], left_on='CountyFIPS', right_index=True, how='left')

# --- Pivot to 2D table for Excel ---
reserves_pivot = reserves_result_df.pivot_table(
    index=['NAME'] if 'NAME' in reserves_result_df.columns else None,
    columns='CountyFIPS',
    values='percent_overlap',
    fill_value=0
)
reserves_pivot.columns = ['G' + str(col) for col in reserves_pivot.columns]

# --- Export to Excel ---
output_path = os.path.join(BASE_DIR, 'analysis', 'outputs', 'sensitivity_analysis', 'mine_reliability', 'mines_reserves_reliability_overlap.xlsx')
with pd.ExcelWriter(output_path) as writer:
    mines_pivot.to_excel(writer, sheet_name='MinesCountyOverlap')
    reserves_pivot.to_excel(writer, sheet_name='ReservesCountyOverlap')


