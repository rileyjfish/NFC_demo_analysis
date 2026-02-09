import geopandas as gpd
import pandas as pd
import os

# Get absolute paths
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))

# Load data
county_zip = os.path.join(base_dir, 'demographic_data', 'shapefiles', 'cb_2022_us_county_500k.zip')
county_gdf = gpd.read_file(f'zip://{county_zip}')
facility_df = pd.read_excel(os.path.join(base_dir, 'facility_data', 'frontend', 'Compiled_Frontend.xlsx'))

print(f"Total rows loaded: {len(facility_df)}")

# Clean longitude and latitude columns (remove invisible Unicode characters and convert to float)
facility_df['Long'] = facility_df['Long'].astype(str).str.replace('\u200e', '').str.strip()
facility_df['Lat'] = facility_df['Lat'].astype(str).str.replace('\u200e', '').str.strip()

# Check for missing or invalid coordinates
print(f"Rows with 'nan' or empty Long: {facility_df['Long'].isin(['nan', '', 'None']).sum()}")
print(f"Rows with 'nan' or empty Lat: {facility_df['Lat'].isin(['nan', '', 'None']).sum()}")

# Convert to float, which will set invalid values to NaN
facility_df['Long'] = pd.to_numeric(facility_df['Long'], errors='coerce')
facility_df['Lat'] = pd.to_numeric(facility_df['Lat'], errors='coerce')

# Report and drop rows with missing coordinates
missing_coords = facility_df['Long'].isna() | facility_df['Lat'].isna()
if missing_coords.any():
    print(f"\nWARNING: {missing_coords.sum()} rows have missing coordinates and will be excluded:")
    print(facility_df[missing_coords][['Name', 'FID', 'Long', 'Lat']])
    facility_df = facility_df[~missing_coords].copy()

# Convert Start and Stop from year integers to dates
# Drop rows with missing Start dates
missing_start = facility_df['Start'].isna()
if missing_start.any():
    print(f"\nWARNING: {missing_start.sum()} rows have missing Start dates and will be excluded:")
    print(facility_df[missing_start][['Name', 'FID', 'Start', 'Stop']])
    facility_df = facility_df[~missing_start].copy()

# Convert Start year to date (01/01/YEAR)
facility_df['Start'] = pd.to_datetime(facility_df['Start'].astype(int).astype(str) + '-01-01')

# Convert Stop year to date, using 2050 for NaN values
facility_df['Stop'] = facility_df['Stop'].fillna(2050)
facility_df['Stop'] = pd.to_datetime(facility_df['Stop'].astype(int).astype(str) + '-01-01')

# Filter out facilities that have data in Ntl Lab column
has_ntl_lab = facility_df['Ntl Lab'].notna()
if has_ntl_lab.any():
    print(f"WARNING: {has_ntl_lab.sum()} rows have Ntl Lab data and will be excluded:")
    print(facility_df[has_ntl_lab][['Name', 'FID', 'Ntl Lab']])
    facility_df = facility_df[~has_ntl_lab].copy()

# Reset index before deduplication to ensure clean integer positions
facility_df = facility_df.reset_index(drop=True)

# Deduplicate facilities within +/- 0.001 lat/long of each other
print(f"\nDeduplicating facilities within 0.001 degrees...")
initial_count = len(facility_df)
threshold = 0.001
clusters = []
processed = set()

# Find clusters of nearby facilities
for i in range(len(facility_df)):
    if i in processed:
        continue
    
    cluster = [i]
    processed.add(i)
    
    for j in range(i+1, len(facility_df)):
        if j in processed:
            continue
        
        lat_diff = abs(facility_df.iloc[i]['Lat'] - facility_df.iloc[j]['Lat'])
        long_diff = abs(facility_df.iloc[i]['Long'] - facility_df.iloc[j]['Long'])
        
        if lat_diff <= threshold and long_diff <= threshold:
            cluster.append(j)
            processed.add(j)
    
    if len(cluster) > 1:
        clusters.append(cluster)

print(f"  Found {len(clusters)} clusters of nearby facilities")

# Process each cluster: keep lowest FID with combined dates
indices_to_drop = []
for cluster in clusters:
    cluster_rows = facility_df.iloc[cluster]
    
    # Find position of row with lowest FID within cluster
    min_fid_pos = cluster[cluster_rows['FID'].values.argmin()]
    min_fid = facility_df.iloc[min_fid_pos]['FID']
    
    # Get earliest Start and latest Stop
    earliest_start = cluster_rows['Start'].min()
    latest_stop = cluster_rows['Stop'].max()
    
    # Update the row with lowest FID
    facility_df.at[min_fid_pos, 'Start'] = earliest_start
    facility_df.at[min_fid_pos, 'Stop'] = latest_stop
    facility_df.at[min_fid_pos, 'Name'] = facility_df.at[min_fid_pos, 'Name'] + '-DEDUP'
    
    # Mark other facilities in cluster for removal (keep only the one with lowest FID)
    for pos in cluster:
        if pos != min_fid_pos:
            indices_to_drop.append(pos)
    
    print(f"  Cluster with FID {min_fid}: Combined {len(cluster)} facilities")
    print(f"    Start: {earliest_start.date()}, Stop: {latest_stop.date()}")

# Remove duplicate facilities
if indices_to_drop:
    facility_df = facility_df.drop(indices_to_drop).reset_index(drop=True)
    print(f"  ✓ Deduplicated: {initial_count} → {len(facility_df)} facilities (removed {len(indices_to_drop)})")
else:
    print(f"  ✓ No duplicates found")

print(f"\nRows after cleaning: {len(facility_df)}\n")

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

# Check which facilities have no overlap with any counties
facilities_with_overlap = overlap_gdf['FID'].unique()
facilities_without_overlap = facility_gdf[~facility_gdf['FID'].isin(facilities_with_overlap)]
if len(facilities_without_overlap) > 0:
    print(f"WARNING: {len(facilities_without_overlap)} facilities have no county overlap (likely in territories or outside US):")
    print(facilities_without_overlap[['Name', 'FID', 'Long', 'Lat']])
    print()

print(f"Facilities with county overlap: {len(facilities_with_overlap)}")
print(f"Total facility-county pairs: {len(overlap_gdf)}\n")

# Check for duplicate FIDs in the original data
print(f"Unique FIDs in facility_df: {facility_df['FID'].nunique()}")
print(f"Total rows in facility_df: {len(facility_df)}")
if facility_df['FID'].nunique() < len(facility_df):
    print(f"WARNING: {len(facility_df) - facility_df['FID'].nunique()} duplicate FIDs found")
    duplicates = facility_df[facility_df.duplicated(subset=['FID'], keep=False)].sort_values('FID')
    print(f"Duplicate FIDs:\n{duplicates[['Name', 'FID', 'Start', 'Stop', 'Type', 'Status']]}\n")

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
facility_attrs = facility_df[['FID', 'Name', 'Start', 'Stop', 'Capacity', 'Capacity Unit', 'Type', 'Status']]
combined_df = combined_df.merge(facility_attrs, on=['FID', 'Name'], how='left')

# Check for NaN values in index columns
print("NaN values in index columns:")
for col in ['Name', 'FID', 'Start', 'Stop', 'Capacity', 'Capacity Unit', 'Type', 'Status']:
    nan_count = combined_df[col].isna().sum()
    if nan_count > 0:
        print(f"  {col}: {nan_count} NaN values")
print()

# Fill NaN values to prevent aggregation in pivot table
# Start and Stop are now datetime objects and should not have NaN values after cleaning
# Using empty string for text fields
combined_df['Capacity'] = combined_df['Capacity'].fillna('')
combined_df['Capacity Unit'] = combined_df['Capacity Unit'].fillna('')
combined_df['Type'] = combined_df['Type'].fillna('')
combined_df['Status'] = combined_df['Status'].fillna('')

# Check for duplicate attribute combinations
print(f"Unique facilities (by FID): {combined_df['FID'].nunique()}")
attr_combos = combined_df[['Name', 'FID', 'Start', 'Stop', 'Capacity', 'Capacity Unit', 'Type', 'Status']].drop_duplicates()
print(f"Unique attribute combinations: {len(attr_combos)}")
if len(attr_combos) < combined_df['FID'].nunique():
    print(f"WARNING: Multiple FIDs share the same attributes - they will be aggregated in pivot table")
    # Find which attributes are duplicated
    dup_attrs = attr_combos.drop(columns='FID').duplicated(keep=False)
    if dup_attrs.any():
        print(f"Facilities with duplicate attributes:\n{attr_combos[dup_attrs].sort_values('Name')}\n")

# Pivot each metric to 2D tables for Excel output, including extra attributes in the index
pivot_county = combined_df.pivot_table(
    index=['Name', 'FID', 'Start', 'Stop', 'Capacity', 'Capacity Unit', 'Type', 'Status'],
    columns='CountyFIPS',
    values='percent_overlap',
    fill_value=0
)
pivot_buffer = combined_df.pivot_table(
    index=['Name', 'FID', 'Start', 'Stop', 'Capacity', 'Capacity Unit', 'Type', 'Status'],
    columns='CountyFIPS',
    values='percent_buffer_overlap',
    fill_value=0
)

print(f"Rows in pivot table: {len(pivot_county)}")
print(f"This should match unique FIDs: {combined_df['FID'].nunique()}\n")

# Add 'G' prefix to column names to ensure GEOID values are treated as strings in Excel
pivot_county.columns = ['G' + str(col) for col in pivot_county.columns]
pivot_buffer.columns = ['G' + str(col) for col in pivot_buffer.columns]

# Export to Excel
output_path = os.path.join(base_dir, 'demographic_data', 'county_overlaps', 'frontend_county_overlap.xlsx')
with pd.ExcelWriter(output_path) as writer:
    pivot_county.to_excel(writer, sheet_name='CountyOverlap')
    pivot_buffer.to_excel(writer, sheet_name='BufferOverlap')

print("✓ Created frontend_county_overlap.xlsx")

