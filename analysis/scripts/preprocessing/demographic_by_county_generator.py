"""
Generate county-level demographic statistics for all facility types.
This script processes 6 demographics (age, education, employment, poverty, race_ethnicity, sex)
for 6 facility types (frontend, interim_prop, mines, reactor, repository, reserves).

Output structure:
- Rows: Counties (with FIPS column)
- Columns: Demographic breakdowns
- Sheets: Years
- Files: One per demographic per facility type

For each county, calculates the number of people within that county who are exposed to
facility buffer zones by multiplying county demographics by buffer zone fraction.
Uses pre-calculated buffer fractions from county overlap files.
"""

import pandas as pd
import geopandas as gpd
import os

# Get absolute paths
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
output_base = os.path.join(base_dir, 'analysis', 'outputs', 'demographics_by_county')

# Create demographic folders
demographics = ['age', 'education', 'employment', 'poverty', 'race_ethnicity', 'sex']
for demo in demographics:
    os.makedirs(os.path.join(output_base, demo), exist_ok=True)

# Define facility configurations with their county overlap files
facilities = {
    'frontend': {
        'overlap_file': os.path.join(base_dir, 'demographic_data', 'county_overlaps', 'frontend_county_overlap.xlsx'),
        'overlap_sheet': 'CountyOverlap'
    },
    'reactor': {
        'overlap_file': os.path.join(base_dir, 'demographic_data', 'county_overlaps', 'reactor_county_overlap.xlsx'),
        'overlap_sheet': 'CountyOverlap'
    },
    'mines': {
        'overlap_file': os.path.join(base_dir, 'demographic_data', 'county_overlaps', 'mines_reserves_county_overlap.xlsx'),
        'overlap_sheet': 'MinesCountyOverlap'
    },
    'reserves': {
        'overlap_file': os.path.join(base_dir, 'demographic_data', 'county_overlaps', 'mines_reserves_county_overlap.xlsx'),
        'overlap_sheet': 'ReservesCountyOverlap'
    },
    'interim_prop': {
        'overlap_file': os.path.join(base_dir, 'demographic_data', 'county_overlaps', 'prop_waste_county_overlap.xlsx'),
        'overlap_sheet': 'InterimCountyOverlap'
    },
    'repository': {
        'overlap_file': os.path.join(base_dir, 'demographic_data', 'county_overlaps', 'prop_waste_county_overlap.xlsx'),
        'overlap_sheet': 'RepositoryCountyOverlap'
    }
}

# Demographic file paths
demographic_files = {
    'age': os.path.join(base_dir, 'demographic_data', 'compiled', 'age_combined.xlsx'),
    'education': os.path.join(base_dir, 'demographic_data', 'compiled', 'education_compiled.xlsx'),
    'employment': os.path.join(base_dir, 'demographic_data', 'compiled', 'employment_compiled.xlsx'),
    'poverty': os.path.join(base_dir, 'demographic_data', 'compiled', 'poverty_compiled.xlsx'),
    'race_ethnicity': os.path.join(base_dir, 'demographic_data', 'compiled', 'race_ethnicity_compiled.xlsx'),
    'sex': os.path.join(base_dir, 'demographic_data', 'compiled', 'sex_compiled.xlsx')
}

print("="*80)
print("GENERATING COUNTY-LEVEL DEMOGRAPHICS BY FACILITY TYPE")
print("="*80)

# Load region shapefiles and create FIPS to Region mapping
print("\nLoading region data and mapping FIPS to regions...")
REGION_MAP = {
    'Midwest': 1,
    'Northeast': 2,
    'Southeast': 3,
    'Southwest': 4,
    'West': 5
}

region_gdfs = {}
region_zip = os.path.join(base_dir, 'demographic_data', 'shapefiles', 'USA_5_Regions.zip')
for region_name, region_id in REGION_MAP.items():
    gdf = gpd.read_file(f'zip://{region_zip}', layer=region_name)
    region_gdfs[region_id] = gdf.to_crs('EPSG:4326')
    print(f"  Loaded {region_name} (ID: {region_id})")

# Load county shapefile and map FIPS to regions
print("\n  Loading county shapefile...")
county_zip = os.path.join(base_dir, 'demographic_data', 'shapefiles', 'cb_2022_us_county_500k.zip')
counties = gpd.read_file(f'zip://{county_zip}')
counties = counties.to_crs('EPSG:4326')
counties['FIPS'] = 'G' + counties['GEOID']
counties['centroid'] = counties.geometry.centroid

print(f"  Mapping {len(counties)} counties to regions...")

fips_to_region = {}
for idx, county in counties.iterrows():
    fips = county['FIPS']
    centroid = county['centroid']
    
    # Default to 0 (not in any region)
    region_id = 0
    
    # Check which region contains this county's centroid
    for rid, region_gdf in region_gdfs.items():
        for geom in region_gdf.geometry:
            if geom.contains(centroid):
                region_id = rid
                break
        if region_id != 0:
            break
    
    fips_to_region[fips] = region_id

# Count counties per region
region_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
for region_id in fips_to_region.values():
    region_counts[region_id] += 1

for region_name, region_id in sorted(REGION_MAP.items(), key=lambda x: x[1]):
    print(f"    {region_name} (ID {region_id}): {region_counts[region_id]} counties")
print(f"    Not in any region (ID 0): {region_counts[0]} counties")

print("  ✓ Region mapping complete")

def parse_sheet_year(sheet_name):
    """Extract year from sheet name, handling ranges by taking midpoint"""
    import re
    if '-' in sheet_name:
        years = re.findall(r'\d{4}', sheet_name)
        if len(years) == 2:
            return (int(years[0]) + int(years[1])) / 2
    year_match = re.search(r'\d{4}', sheet_name)
    return int(year_match.group()) if year_match else None

def process_facility_demographic(facility_name, config, demographic_name, demo_file):
    """Process one demographic for one facility type"""
    print(f"\n  Processing {facility_name} - {demographic_name}...")
    
    # Check if this facility type should be split by operation status
    split_by_operation = facility_name in ['frontend', 'reactor']
    
    # Check if this facility type should use stage-based processing
    stage_based = facility_name in ['repository', 'interim_prop']
    
    # Load demographic data
    print(f"    Loading demographic data from {os.path.basename(demo_file)}...")
    xls = pd.ExcelFile(demo_file)
    
    # Load overlap data once
    print(f"    Loading overlap data...")
    overlap_df = pd.read_excel(config['overlap_file'], sheet_name=config['overlap_sheet'])
    
    # For stage-based processing, define the stage binning rules
    if stage_based:
        if facility_name == 'repository':
            # Reverse cumulative: Stage 0 = [0,1,2,3,4], Stage 1 = [1,2,3,4], etc.
            stage_bins = {
                0: [0, 1, 2, 3, 4],
                1: [1, 2, 3, 4],
                2: [2, 3, 4],
                3: [3, 4],
                4: [4]
            }
            reference_year = '1980'
        elif facility_name == 'interim_prop':
            # Stage 0 is standalone, 1-3 are cumulative, 4-6 are cumulative
            stage_bins = {
                0: [0],
                1: [1, 2, 3],
                2: [2, 3],
                3: [3],
                4: [4, 5, 6],
                5: [5, 6],
                6: [6]
            }
            reference_year = '1990'
    
    # Deduplicate reactors by base name (last 2 chars), using earliest Start and latest Stop
    if facility_name == 'reactor' and 'Name' in overlap_df.columns:
        print(f"    Deduplicating reactors by base name (last 2 chars)...")
        initial_count = len(overlap_df)
        
        if 'Start' in overlap_df.columns and 'Stop' in overlap_df.columns:
            # Parse dates first
            overlap_df['Start_dt'] = pd.to_datetime(overlap_df['Start'], errors='coerce')
            overlap_df['Stop_dt'] = pd.to_datetime(overlap_df['Stop'], errors='coerce')
            
            # Group by base name and find earliest start and latest stop
            base_name_groups = {}
            for idx, row in overlap_df.iterrows():
                base_name = row['Name'][:-2] if isinstance(row['Name'], str) and len(row['Name']) > 2 else row['Name']
                start_dt = row['Start_dt']
                stop_dt = row['Stop_dt']
                
                if pd.isnull(start_dt) or pd.isnull(stop_dt):
                    continue
                
                if base_name not in base_name_groups:
                    base_name_groups[base_name] = {
                        'idx': idx,
                        'earliest_start': start_dt,
                        'latest_stop': stop_dt
                    }
                else:
                    if start_dt < base_name_groups[base_name]['earliest_start']:
                        base_name_groups[base_name]['earliest_start'] = start_dt
                    if stop_dt > base_name_groups[base_name]['latest_stop']:
                        base_name_groups[base_name]['latest_stop'] = stop_dt
            
            # Keep only the first occurrence of each base name, but update its dates
            keep_indices = []
            for base_name, info in base_name_groups.items():
                idx = info['idx']
                keep_indices.append(idx)
                # Update the dates to the combined range
                overlap_df.at[idx, 'Start_dt'] = info['earliest_start']
                overlap_df.at[idx, 'Stop_dt'] = info['latest_stop']
                # Also update the original Start/Stop columns
                overlap_df.at[idx, 'Start'] = info['earliest_start']
                overlap_df.at[idx, 'Stop'] = info['latest_stop']
            
            overlap_df = overlap_df.loc[keep_indices].reset_index(drop=True)
            print(f"    Reactors: {initial_count} → {len(overlap_df)} (removed {initial_count - len(overlap_df)} duplicates)")
            print(f"    Date ranges updated to earliest Start and latest Stop for each site")
        else:
            # Fallback: simple deduplication by name without date correction
            overlap_df['Name_Prefix'] = overlap_df['Name'].str[:-2]
            overlap_df = overlap_df.drop_duplicates(subset='Name_Prefix', keep='first')
            overlap_df = overlap_df.drop(columns=['Name_Prefix'])
            print(f"    Reactors: {initial_count} → {len(overlap_df)} (removed {initial_count - len(overlap_df)} duplicates)")
            print(f"    ✗ Warning: Start/Stop columns not found, using simple deduplication")
    
    # Get FIPS columns
    fips_cols = [col for col in overlap_df.columns if str(col).startswith('G')]
    
    # If splitting by operation, parse Start/Stop dates once (if not already parsed)
    if split_by_operation:
        if 'Start' in overlap_df.columns and 'Stop' in overlap_df.columns:
            if 'Start_Year' not in overlap_df.columns:
                print(f"    Parsing Start/Stop dates for operation filtering...")
                if 'Start_dt' in overlap_df.columns:
                    # Already parsed as datetime
                    overlap_df['Start_Year'] = overlap_df['Start_dt'].dt.year
                    overlap_df['Stop_Year'] = overlap_df['Stop_dt'].dt.year
                else:
                    overlap_df['Start_Year'] = pd.to_datetime(overlap_df['Start'], errors='coerce').dt.year
                    overlap_df['Stop_Year'] = pd.to_datetime(overlap_df['Stop'], errors='coerce').dt.year
        else:
            print(f"    ✗ Start/Stop columns not found, cannot split by operation")
            split_by_operation = False
    
    # If not splitting by operation and not stage-based, calculate buffer fractions once
    if not split_by_operation and not stage_based:
        print(f"    Calculating buffer fractions for {len(fips_cols)} counties...")
        buffer_fractions = {fips: overlap_df[fips].sum() for fips in fips_cols}
    
    results = {}
    
    # For stage-based processing, we only process the reference year and create sheets per stage
    if stage_based:
        print(f"    Using stage-based processing with reference year: {reference_year}")
        
        # Check if Note column exists
        if 'Note' not in overlap_df.columns:
            print(f"    ✗ Note column not found in overlap data, cannot process stages")
            return
        
        # Read demographic data for reference year only
        if reference_year not in xls.sheet_names:
            print(f"    ✗ Reference year {reference_year} not found in demographic data")
            return
        
        print(f"      Loading demographic data for {reference_year}...")
        df = pd.read_excel(demo_file, sheet_name=reference_year)
        
        # Check if FIPS column exists
        if 'FIPS' not in df.columns:
            print(f"        ✗ No FIPS column, skipping")
            return
        
        # Get demographic columns
        meta_cols = ['FIPS', 'Region', 'GISJOIN']
        demo_cols = [col for col in df.columns 
                     if col not in meta_cols and not col.endswith('_E')]
        
        # Map region to each FIPS
        df['Region'] = df['FIPS'].map(fips_to_region).fillna(0).astype(int)
        
        # Process each stage
        for stage_num, included_notes in stage_bins.items():
            print(f"      Processing Stage {stage_num} (includes Note values: {included_notes})...")
            
            # Filter facilities by Note value
            stage_overlap = overlap_df[overlap_df['Note'].isin(included_notes)]
            
            if len(stage_overlap) == 0:
                print(f"        ✗ No facilities found for Stage {stage_num}")
                continue
            
            print(f"        Found {len(stage_overlap)} facilities for Stage {stage_num}")
            
            # Calculate buffer fractions for this stage
            stage_buffer_fractions = {fips: stage_overlap[fips].sum() for fips in fips_cols}
            
            # Map buffer fraction
            df['Buffer_Fraction'] = df['FIPS'].map(stage_buffer_fractions).fillna(0.0)
            
            # Create result DataFrame
            result_df = df[['FIPS', 'Region', 'Buffer_Fraction']].copy()
            
            # Multiply demographic columns by buffer fraction
            for col in demo_cols:
                result_df[col] = (df[col].fillna(0) * df['Buffer_Fraction']).round(0).astype(int)
            
            # Store with stage-based sheet name
            sheet_name = f"Stage {stage_num} - {reference_year}"
            results[sheet_name] = result_df
            print(f"        ✓ Processed {len(result_df)} counties for Stage {stage_num}")
    
    else:
        # Original year-based processing
        for sheet_name in xls.sheet_names:
            print(f"      Processing year: {sheet_name}...")
            
            # Parse sheet year for filtering facilities
            sheet_year = parse_sheet_year(sheet_name)
            
            # Calculate buffer fractions for this year if splitting by operation
            if split_by_operation and sheet_year is not None:
                # Filter facilities by operation status
                standard_mask = (overlap_df['Start_Year'] <= sheet_year) & (overlap_df['Stop_Year'] >= sheet_year)
                residual_mask = overlap_df['Start_Year'] <= sheet_year
                
                standard_df = overlap_df[standard_mask]
                residual_df = overlap_df[residual_mask]
                
                # Calculate buffer fractions
                buffer_fractions_S = {fips: standard_df[fips].sum() for fips in fips_cols}
                buffer_fractions_R = {fips: residual_df[fips].sum() for fips in fips_cols}
                
                print(f"        Standard facilities: {standard_mask.sum()}, Residual facilities: {residual_mask.sum()}")
            
            # Read demographic data
            df = pd.read_excel(demo_file, sheet_name=sheet_name)
            
            # Check if FIPS column exists
            if 'FIPS' not in df.columns:
                print(f"        ✗ No FIPS column, skipping")
                continue
            
            # Get demographic columns (exclude FIPS, Region, GISJOIN, etc.)
            meta_cols = ['FIPS', 'Region', 'GISJOIN']
            demo_cols = [col for col in df.columns 
                         if col not in meta_cols and not col.endswith('_E')]
            
            # VECTORIZED APPROACH - much faster than iterating
            
            # Map region to each FIPS (vectorized)
            df['Region'] = df['FIPS'].map(fips_to_region).fillna(0).astype(int)
            
            if split_by_operation and sheet_year is not None:
                # Map buffer fractions (vectorized)
                df['Buffer_Fraction_S'] = df['FIPS'].map(buffer_fractions_S).fillna(0.0)
                df['Buffer_Fraction_R'] = df['FIPS'].map(buffer_fractions_R).fillna(0.0)
                
                # Create result DataFrame with FIPS and Region
                result_df = df[['FIPS', 'Region', 'Buffer_Fraction_S', 'Buffer_Fraction_R']].copy()
                
                # Multiply demographic columns by buffer fractions (vectorized)
                for col in demo_cols:
                    # Standard
                    result_df[f'{col}_S'] = (df[col].fillna(0) * df['Buffer_Fraction_S']).round(0).astype(int)
                    # Residual
                    result_df[f'{col}_R'] = (df[col].fillna(0) * df['Buffer_Fraction_R']).round(0).astype(int)
            else:
                # Map buffer fraction (vectorized)
                df['Buffer_Fraction'] = df['FIPS'].map(buffer_fractions).fillna(0.0)
                
                # Create result DataFrame with FIPS and Region
                result_df = df[['FIPS', 'Region', 'Buffer_Fraction']].copy()
                
                # Multiply demographic columns by buffer fraction (vectorized)
                for col in demo_cols:
                    result_df[col] = (df[col].fillna(0) * df['Buffer_Fraction']).round(0).astype(int)
            
            results[sheet_name] = result_df
            print(f"        ✓ Processed {len(result_df)} counties")
    
    # Write to Excel
    output_file = os.path.join(output_base, demographic_name, f"{facility_name}_{demographic_name}_counties.xlsx")
    print(f"    Writing to {output_file}...")
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for sheet_name, df in results.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    print(f"    ✓ Saved {len(results)} sheets")

# Main processing loop
print("\n" + "="*80)
print("PROCESSING ALL FACILITIES AND DEMOGRAPHICS")
print("="*80)

for demographic_name in demographics:
    print(f"\n{'='*80}")
    print(f"DEMOGRAPHIC: {demographic_name.upper()}")
    print('='*80)
    
    demo_file = demographic_files[demographic_name]
    
    for facility_name, config in facilities.items():
        print(f"\nFacility: {facility_name}")
        
        # Process this facility-demographic combination
        process_facility_demographic(facility_name, config, demographic_name, demo_file)

print("\n" + "="*80)
print("✓ ALL COUNTY-LEVEL DEMOGRAPHICS GENERATED SUCCESSFULLY!")
print("="*80)
print(f"\nOutput location: {output_base}")
print(f"Demographics: {len(demographics)}")
print(f"Facility types: {len(facilities)}")
print(f"Total files: {len(demographics) * len(facilities)}")
print("="*80)
