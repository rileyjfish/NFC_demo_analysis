import geopandas as gpd
import pandas as pd

# --- Load tract boundaries ---
tract_gdf = gpd.read_file('Demographic Data\cb_2023_us_tract_500k\cb_2023_us_tract_500k.shp')
tract_gdf = tract_gdf.to_crs(epsg=5070)  # Albers Equal Area

# --- Load mine facilities (EPA ULDB) ---
mines_gdf = gpd.read_file('Facility Data/epa_uldb.zip')
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

# --- Spatial intersection: tract & mine buffer ---
mines_overlap_gdf = gpd.overlay(tract_gdf, mines_buffer_gdf, how='intersection')
mines_overlap_gdf['overlap_area'] = mines_overlap_gdf.geometry.area
mines_overlap_gdf['tract_area'] = tract_gdf.set_index('GEOID').loc[mines_overlap_gdf['GEOID'], 'geometry'].area.values
mines_overlap_gdf['percent_overlap'] = mines_overlap_gdf['overlap_area'] / mines_overlap_gdf['tract_area']

# --- Prepare results for mines ---
mines_result_df = mines_overlap_gdf[['ICF_ID', 'GEOID', 'percent_overlap']].rename(columns={'GEOID': 'TractFIPS'})
mines_result_df = mines_result_df.merge(mines_gdf[['ICF_ID', 'RELIABILIT']], on='ICF_ID', how='left')

# --- Pivot to 2D table for Excel ---
mines_pivot = mines_result_df.pivot_table(
    index=['ICF_ID', 'RELIABILIT'],
    columns='TractFIPS',
    values='percent_overlap',
    fill_value=0
)
mines_pivot.columns = ['G' + str(col) for col in mines_pivot.columns]

# --- Load uranium reserves (EIA NURE) ---

# Load and clean uranium reserves (EIA NURE)
reserves_gdf = gpd.read_file('Facility Data/EIA_NURE.zip')
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
if not isinstance(tract_gdf, gpd.GeoDataFrame):
    tract_gdf = gpd.GeoDataFrame(tract_gdf)
if not isinstance(reserves_gdf, gpd.GeoDataFrame):
    reserves_gdf = gpd.GeoDataFrame(reserves_gdf)
if 'geometry' not in tract_gdf.columns:
    print('tract_gdf missing geometry column!')
if 'geometry' not in reserves_gdf.columns:
    print('reserves_gdf missing geometry column!')
print('tract_gdf type:', type(tract_gdf))
print('reserves_gdf type:', type(reserves_gdf))
print('tract_gdf geometry type:', tract_gdf.geometry.iloc[0].geom_type)

# --- Spatial intersection: tract & reserves ---
reserves_overlap_gdf = gpd.overlay(tract_gdf, reserves_gdf, how='intersection')
reserves_overlap_gdf['overlap_area'] = reserves_overlap_gdf.geometry.area
reserves_overlap_gdf['tract_area'] = tract_gdf.set_index('GEOID').loc[reserves_overlap_gdf['GEOID'], 'geometry'].area.values
reserves_overlap_gdf['percent_overlap'] = reserves_overlap_gdf['overlap_area'] / reserves_overlap_gdf['tract_area']

# --- Prepare results for reserves ---
reserves_result_df = reserves_overlap_gdf[['GEOID', 'percent_overlap']].rename(columns={'GEOID': 'TractFIPS'})
if 'NAME' in reserves_gdf.columns:
    reserves_result_df = reserves_result_df.merge(reserves_gdf[['NAME']], left_on='TractFIPS', right_index=True, how='left')

# --- Pivot to 2D table for Excel ---
reserves_pivot = reserves_result_df.pivot_table(
    index=['NAME'] if 'NAME' in reserves_result_df.columns else None,
    columns='TractFIPS',
    values='percent_overlap',
    fill_value=0
)
reserves_pivot.columns = ['G' + str(col) for col in reserves_pivot.columns]

# --- Export to Excel ---
with pd.ExcelWriter('Demographic Data/mines_reserves_tract_overlap.xlsx') as writer:
    mines_pivot.to_excel(writer, sheet_name='MinesTractOverlap')
    reserves_pivot.to_excel(writer, sheet_name='ReservesTractOverlap')
