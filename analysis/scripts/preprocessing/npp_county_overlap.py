import geopandas as gpd
import pandas as pd
import os

# Get absolute paths
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))

# Load data
county_zip = os.path.join(base_dir, 'demographic_data', 'shapefiles', 'cb_2022_us_county_500k.zip')
county_gdf = gpd.read_file(f'zip://{county_zip}')
facility_df = pd.read_excel(os.path.join(base_dir, 'facility_data', 'reactors', 'Reactors.xlsx'))

# Rename columns for consistency
facility_df = facility_df.rename(columns={
    'Critical': 'Start',
    'Shutdown': 'Stop',
    'RUP (MWe)': 'Capacity (MWe)'
})

# Create GeoDataFrame for facilities and project to meters
facility_gdf = gpd.GeoDataFrame(
    facility_df,
    geometry=gpd.points_from_xy(facility_df['Long'], facility_df['Lat']),
    crs="EPSG:4326"
).to_crs(epsg=5070)

# Create 50 mile buffer around each facility
buffer_distance = 50 * 1609.344
facility_gdf['buffer'] = facility_gdf.geometry.buffer(buffer_distance)

# Project counties to same CRS
county_gdf = county_gdf.to_crs(facility_gdf.crs)

# Prepare buffer GeoDataFrame
buffer_gdf = gpd.GeoDataFrame(
    facility_gdf[['Name', 'FID']],
    geometry=facility_gdf['buffer'],
    crs=facility_gdf.crs
)

# Spatial intersection
overlap_gdf = gpd.overlay(county_gdf, buffer_gdf, how='intersection')

# Calculate overlap metrics
overlap_gdf['overlap_area'] = overlap_gdf.geometry.area
overlap_gdf['county_area'] = county_gdf.set_index('GEOID').loc[overlap_gdf['GEOID'], 'geometry'].area.values
overlap_gdf['buffer_area'] = buffer_gdf.set_index('FID').loc[overlap_gdf['FID'], 'geometry'].area.values
overlap_gdf['percent_overlap'] = overlap_gdf['overlap_area'] / overlap_gdf['county_area']
overlap_gdf['percent_buffer_overlap'] = overlap_gdf['overlap_area'] / overlap_gdf['buffer_area']

# Prepare results
result_df = overlap_gdf[['Name', 'FID', 'GEOID', 'percent_overlap']].rename(columns={'GEOID': 'CountyFIPS'})
buffer_result_df = overlap_gdf[['Name', 'FID', 'GEOID', 'percent_buffer_overlap']].rename(columns={'GEOID': 'CountyFIPS'})

# Prepare combined results DataFrame with both metrics
combined_df = overlap_gdf[['Name', 'FID', 'GEOID', 'percent_overlap', 'percent_buffer_overlap']].rename(
    columns={'GEOID': 'CountyFIPS'}
)

# Merge facility attributes into combined_df
facility_attrs = facility_df[['FID', 'Name', 'Start', 'Stop', 'Capacity (MWe)']]
combined_df = combined_df.merge(facility_attrs, on=['FID', 'Name'], how='left')

# Pivot each metric to 2D tables for Excel output, including extra attributes in the index
pivot_county = combined_df.pivot_table(
    index=['Name', 'FID', 'Start', 'Stop', 'Capacity (MWe)'],
    columns='CountyFIPS',
    values='percent_overlap',
    fill_value=0
)
pivot_buffer = combined_df.pivot_table(
    index=['Name', 'FID', 'Start', 'Stop', 'Capacity (MWe)'],
    columns='CountyFIPS',
    values='percent_buffer_overlap',
    fill_value=0
)

# Add 'G' prefix to column names to ensure GEOID values are treated as strings in Excel
pivot_county.columns = ['G' + str(col) for col in pivot_county.columns]
pivot_buffer.columns = ['G' + str(col) for col in pivot_buffer.columns]
# Add Region row to both tables
for col in pivot_county.columns:
    if col in fips_to_region_id:
        pivot_county.loc['Region', col] = fips_to_region_id[col]
        pivot_buffer.loc['Region', col] = fips_to_region_id[col]


# Export to Excel
output_path = os.path.join(base_dir, 'demographic_data', 'county_overlaps', 'reactor_county_overlap.xlsx')
with pd.ExcelWriter(output_path) as writer:
    pivot_county.to_excel(writer, sheet_name='CountyOverlap')
    pivot_buffer.to_excel(writer, sheet_name='BufferOverlap')

print("\u2713 Created reactor_county_overlap.xlsx with regional indices")

# --- Diagnostic code for Boulder County and Fort St Vrain ---
# Find Boulder County row in county_gdf
boulder_county = county_gdf[county_gdf['GEOID'] == '08013']
# Find Fort St Vrain buffer row in buffer_gdf
fort_st_vrain = buffer_gdf[buffer_gdf['Name'].str.contains('FORT ST. VRAIN', case=False)]

print('CRS:', county_gdf.crs)
print('Boulder County geometry type:', boulder_county.geometry.iloc[0].geom_type)
print('Fort St Vrain buffer geometry type:', fort_st_vrain.geometry.iloc[0].geom_type)

# Calculate areas
boulder_area = boulder_county.geometry.area.iloc[0]
buffer_area = fort_st_vrain.geometry.area.iloc[0]
intersection = boulder_county.geometry.iloc[0].intersection(fort_st_vrain.geometry.iloc[0])
overlap_area = intersection.area

print(f"Boulder County Area: {boulder_area:,.2f}")
print(f"Buffer Area: {buffer_area:,.2f}")
print(f"Intersection Area: {overlap_area:,.2f}")
print(f"Percent overlap (intersection/county): {overlap_area/boulder_area:.4f}")
print(f"Percent buffer overlap (intersection/buffer): {overlap_area/buffer_area:.4f}")

# Check if buffer fully contains county
contains = fort_st_vrain.geometry.iloc[0].contains(boulder_county.geometry.iloc[0])
within = boulder_county.geometry.iloc[0].within(fort_st_vrain.geometry.iloc[0])
print(f"Buffer contains county? {contains}")
print(f"County within buffer? {within}")

# Optional: plot for visual check
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(8,8))
boulder_county.boundary.plot(ax=ax, color='blue', linewidth=2, label='Boulder County')
fort_st_vrain.boundary.plot(ax=ax, color='purple', linewidth=2, label='Buffer')
gpd.GeoSeries(intersection.boundary).plot(ax=ax, color='red', linewidth=2, label='Intersection')
plt.legend()
plt.title('Boulder County, Buffer, and Intersection')
plt.show()
# --- End diagnostics ---


