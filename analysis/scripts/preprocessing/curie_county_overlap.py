import geopandas as gpd
import pandas as pd
import os

# Get absolute paths
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))

# Load data
county_zip = os.path.join(base_dir, 'demographic_data', 'shapefiles', 'cb_2022_us_county_500k.zip')
county_gdf = gpd.read_file(f'zip://{county_zip}')
facility_df = pd.read_excel(os.path.join(base_dir, 'facility_data', 'backend', 'CURIE', 'ReactorInfo.xlsx'))

# Create GeoDataFrame for facilities and project to meters
facility_gdf = gpd.GeoDataFrame(
    facility_df,
    geometry=gpd.points_from_xy(facility_df['longitude'], facility_df['latitude']),
    crs="EPSG:4326"
).to_crs(epsg=5070)

# Create 50 mile buffer around each facility
buffer_distance = 50 * 1609.344
facility_gdf['buffer'] = facility_gdf.geometry.buffer(buffer_distance)

# Project counties to same CRS
county_gdf = county_gdf.to_crs(facility_gdf.crs)

# Prepare buffer GeoDataFrame
buffer_gdf = gpd.GeoDataFrame(
    facility_gdf[['FID', 'facility_name']],
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
result_df = overlap_gdf[['facility_name', 'GEOID', 'percent_overlap']].rename(columns={'GEOID': 'CountyFIPS'})
buffer_result_df = overlap_gdf[['facility_name', 'GEOID', 'percent_buffer_overlap']].rename(columns={'GEOID': 'CountyFIPS'})

# Prepare combined results DataFrame with both metrics
combined_df = overlap_gdf[['facility_name', 'FID', 'GEOID', 'percent_overlap', 'percent_buffer_overlap']].rename(
    columns={'GEOID': 'CountyFIPS'}
)

# Merge facility attributes into combined_df
facility_attrs = facility_df[['FID', 'facility_name', 'operating_date', 'license_expiration_date']]
combined_df = combined_df.merge(
    facility_attrs,
    on=['FID', 'facility_name'],
    how='left'
)

# Pivot each metric to 2D tables for Excel output, including FID in the index
pivot_county = combined_df.pivot_table(
    index=['facility_name', 'FID', 'operating_date', 'license_expiration_date'],
    columns='CountyFIPS',
    values='percent_overlap',
    fill_value=0
)
pivot_buffer = combined_df.pivot_table(
    index=['facility_name', 'FID', 'operating_date', 'license_expiration_date'],
    columns='CountyFIPS',
    values='percent_buffer_overlap',
    fill_value=0
)

# Remove rows that are completely identical across all FIPS columns
pivot_county = pivot_county.loc[~pivot_county.duplicated(subset=pivot_county.columns, keep='first')]
pivot_buffer = pivot_buffer.loc[~pivot_buffer.duplicated(subset=pivot_buffer.columns, keep='first')]

# Add 'G' prefix to column names to ensure GEOID values are treated as strings in Excel
pivot_county.columns = ['G' + str(col) for col in pivot_county.columns]
pivot_buffer.columns = ['G' + str(col) for col in pivot_buffer.columns]

# Export to Excel
output_path = os.path.join(base_dir, 'demographic_data', 'county_overlaps', 'curie_county_overlap.xlsx')
with pd.ExcelWriter(output_path) as writer:
    pivot_county.to_excel(writer, sheet_name='CountyOverlap')
    pivot_buffer.to_excel(writer, sheet_name='BufferOverlap')

print("✓ Created curie_county_overlap.xlsx")




