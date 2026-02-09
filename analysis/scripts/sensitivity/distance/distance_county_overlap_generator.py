"""
Generate county overlap files for different buffer distances (1, 5, 10, 25 miles).
This script applies the same frontend facility deduplication scheme used in frontend_county_overlap.py
to create consistent county overlap files across all distance sensitivities.

The deduplication scheme:
- Removes facilities with missing Start dates
- Sets missing Stop dates to 2050
- Filters out facilities with Ntl Lab data
- Deduplicates facilities within ±0.001 lat/long:
  - Keeps facility with lowest FID
  - Combines earliest Start and latest Stop dates
  - Appends "-DEDUP" to name
"""

import geopandas as gpd
import pandas as pd
import os

# Get absolute paths
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))

# Define distances to process (in miles)
distances = {
    '1mi': {'miles': 1, 'label': '1 Mile'},
    '5mi': {'miles': 5, 'label': '5 Mile'},
    '10mi': {'miles': 10, 'label': '10 Mile'},
    '25mi': {'miles': 25, 'label': '25 Mile'}
}

def load_and_deduplicate_frontend():
    """Load and deduplicate frontend facilities using the same logic as frontend_county_overlap.py"""
    facility_df = pd.read_excel(os.path.join(base_dir, 'facility_data', 'frontend', 'Compiled_Frontend.xlsx'))
    
    print(f"Initial frontend facilities: {len(facility_df)}")
    
    # Clean longitude and latitude columns
    facility_df['Long'] = facility_df['Long'].astype(str).str.replace('\u200e', '').str.strip()
    facility_df['Lat'] = facility_df['Lat'].astype(str).str.replace('\u200e', '').str.strip()
    
    # Convert to float
    facility_df['Long'] = pd.to_numeric(facility_df['Long'], errors='coerce')
    facility_df['Lat'] = pd.to_numeric(facility_df['Lat'], errors='coerce')
    
    # Drop rows with missing coordinates
    missing_coords = facility_df['Long'].isna() | facility_df['Lat'].isna()
    if missing_coords.any():
        print(f"  Excluding {missing_coords.sum()} rows with missing coordinates")
        facility_df = facility_df[~missing_coords].copy()
    
    # Drop rows with missing Start dates
    missing_start = facility_df['Start'].isna()
    if missing_start.any():
        print(f"  Excluding {missing_start.sum()} rows with missing Start dates")
        facility_df = facility_df[~missing_start].copy()
    
    # Convert Start year to date (01/01/YEAR)
    facility_df['Start'] = pd.to_datetime(facility_df['Start'].astype(int).astype(str) + '-01-01')
    
    # Convert Stop year to date, using 2050 for NaN values
    facility_df['Stop'] = facility_df['Stop'].fillna(2050)
    facility_df['Stop'] = pd.to_datetime(facility_df['Stop'].astype(int).astype(str) + '-01-01')
    
    # Filter out facilities with Ntl Lab data
    has_ntl_lab = facility_df['Ntl Lab'].notna()
    if has_ntl_lab.any():
        print(f"  Excluding {has_ntl_lab.sum()} rows with Ntl Lab data")
        facility_df = facility_df[~has_ntl_lab].copy()
    
    # Reset index before deduplication
    facility_df = facility_df.reset_index(drop=True)
    
    # Deduplicate facilities within +/- 0.001 lat/long
    print(f"  Deduplicating facilities within 0.001 degrees...")
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
    
    print(f"    Found {len(clusters)} clusters of nearby facilities")
    
    # Process each cluster: keep lowest FID with combined dates
    indices_to_drop = []
    for cluster in clusters:
        cluster_rows = facility_df.iloc[cluster]
        
        # Find position of row with lowest FID
        min_fid_pos = cluster[cluster_rows['FID'].values.argmin()]
        
        # Get earliest Start and latest Stop
        earliest_start = cluster_rows['Start'].min()
        latest_stop = cluster_rows['Stop'].max()
        
        # Update the row with lowest FID
        facility_df.at[min_fid_pos, 'Start'] = earliest_start
        facility_df.at[min_fid_pos, 'Stop'] = latest_stop
        facility_df.at[min_fid_pos, 'Name'] = facility_df.at[min_fid_pos, 'Name'] + '-DEDUP'
        
        # Mark other facilities in cluster for removal
        for pos in cluster:
            if pos != min_fid_pos:
                indices_to_drop.append(pos)
    
    # Remove duplicate facilities
    if indices_to_drop:
        facility_df = facility_df.drop(indices_to_drop).reset_index(drop=True)
        print(f"    Deduplicated: removed {len(indices_to_drop)} facilities")
    else:
        print(f"    No duplicates found")
    
    print(f"Final deduplicated frontend facilities: {len(facility_df)}")
    
    return facility_df

def generate_county_overlap_for_distance(distance_key, distance_config, frontend_df):
    """Generate county overlap file for a specific distance"""
    miles = distance_config['miles']
    label = distance_config['label']
    
    print(f"\n{'='*70}")
    print(f"Generating county overlap for {label} buffer...")
    print(f"{'='*70}")
    
    # Load county shapefile
    county_zip = os.path.join(base_dir, 'demographic_data', 'shapefiles', 'cb_2022_us_county_500k.zip')
    county_gdf = gpd.read_file(f'zip://{county_zip}')
    
    # Create GeoDataFrame for frontend facilities
    frontend_gdf = gpd.GeoDataFrame(
        frontend_df,
        geometry=gpd.points_from_xy(frontend_df['Long'], frontend_df['Lat']),
        crs="EPSG:4326"
    ).to_crs(epsg=5070)
    
    # Create buffer at specified distance
    buffer_distance = miles * 1609.344  # Convert miles to meters
    frontend_gdf['buffer'] = frontend_gdf.geometry.buffer(buffer_distance)
    
    # Project counties to same CRS
    county_gdf = county_gdf.to_crs(frontend_gdf.crs)
    
    # Prepare buffer GeoDataFrame
    buffer_gdf = gpd.GeoDataFrame(
        frontend_gdf[['Name', 'FID']],
        geometry=frontend_gdf['buffer'],
        crs=frontend_gdf.crs
    )
    
    # Spatial intersection
    print("  Computing county overlaps...")
    overlap_gdf = gpd.overlay(county_gdf, buffer_gdf, how='intersection')
    
    # Calculate overlap percentages
    overlap_gdf['county_area'] = county_gdf.set_index('GEOID').loc[overlap_gdf['GEOID'], 'geometry'].area.values
    overlap_gdf['overlap_area'] = overlap_gdf.geometry.area
    overlap_gdf['overlap_percentage'] = (overlap_gdf['overlap_area'] / overlap_gdf['county_area']) * 100
    
    # Pivot to create facility x county matrix
    pivot_df = overlap_gdf.pivot_table(
        index=['Name', 'FID'],
        columns='GEOID',
        values='overlap_percentage',
        fill_value=0
    )
    
    # Rename columns to add 'G' prefix to match expected format
    pivot_df.columns = ['G' + str(col) for col in pivot_df.columns]
    
    # Merge with full facility info to preserve all columns
    facility_info = frontend_df.set_index(['Name', 'FID'])[['Start', 'Stop', 'Capacity', 'Capacity Unit', 'Type', 'Status']]
    frontend_overlap = facility_info.join(pivot_df, how='left').fillna(0)
    
    # Reset index to make Name and FID regular columns
    frontend_overlap = frontend_overlap.reset_index()
    
    print(f"  Frontend overlap matrix: {len(frontend_overlap)} facilities x {len(pivot_df.columns)} counties")
    
    # Load other facility overlaps (we'll load from the existing 50-mile data and scale down)
    # For now, just create the frontend sheet - other facilities remain unchanged
    output_dir = os.path.join(base_dir, 'analysis', 'outputs', 'sensitivity_analysis', 'distance', label)
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, f'{distance_key}_county_overlap.xlsx')
    
    # Check if file exists to preserve other sheets
    if os.path.exists(output_file):
        print(f"  Updating existing file: {output_file}")
        # Read all existing sheets
        with pd.ExcelFile(output_file) as xls:
            existing_sheets = {sheet: pd.read_excel(xls, sheet_name=sheet) for sheet in xls.sheet_names}
        
        # Update FrontendCountyOverlap sheet
        existing_sheets['FrontendCountyOverlap'] = frontend_overlap
        
        # Write back all sheets
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            for sheet_name, df in existing_sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        print(f"  Creating new file: {output_file}")
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            frontend_overlap.to_excel(writer, sheet_name='FrontendCountyOverlap', index=False)
    
    print(f"  ✓ Saved: {output_file}")

def main():
    """Main processing function"""
    print("="*70)
    print("DISTANCE COUNTY OVERLAP GENERATOR")
    print("Applying frontend deduplication to all distance buffers")
    print("="*70)
    
    # Load and deduplicate frontend facilities once
    print("\nStep 1: Loading and deduplicating frontend facilities...")
    frontend_df = load_and_deduplicate_frontend()
    
    # Generate county overlaps for each distance
    print("\nStep 2: Generating county overlaps for each distance...")
    for distance_key, distance_config in distances.items():
        generate_county_overlap_for_distance(distance_key, distance_config, frontend_df)
    
    print("\n" + "="*70)
    print("✓ All distance county overlap files updated successfully!")
    print("="*70)
    print("\nNext steps:")
    print("  1. Run the distance sensitivity analysis scripts")

if __name__ == "__main__":
    main()
