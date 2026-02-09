"""
Generate facility-level demographic statistics directly from compiled demographic data.
This script uses county overlap files to weight demographic data and aggregate to facilities.

Process:
1. Load overlap file (facilities as rows, FIPS codes as columns with overlap weights)
2. Load compiled demographic data (FIPS codes as rows, demographic categories as columns, years as sheets)
3. For each facility, multiply county demographics by overlap weights and sum

Output structure:
- Rows: Facilities (with all metadata from overlap files)
- Columns: Demographic totals
- Sheets: Years
- Files: One per demographic per facility type
"""

import pandas as pd
import numpy as np
import os

# Get absolute paths
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
output_base = os.path.join(base_dir, 'analysis', 'outputs', 'demographics_by_facility')

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
    'curie': {
        'overlap_file': os.path.join(base_dir, 'demographic_data', 'county_overlaps', 'curie_county_overlap.xlsx'),
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

# Demographic file paths - use compiled files directly
demographic_files = {
    'age': os.path.join(base_dir, 'demographic_data', 'compiled', 'age_combined.xlsx'),
    'education': os.path.join(base_dir, 'demographic_data', 'compiled', 'education_compiled.xlsx'),
    'employment': os.path.join(base_dir, 'demographic_data', 'compiled', 'employment_compiled.xlsx'),
    'poverty': os.path.join(base_dir, 'demographic_data', 'compiled', 'poverty_compiled.xlsx'),
    'race_ethnicity': os.path.join(base_dir, 'demographic_data', 'compiled', 'race_ethnicity_compiled.xlsx'),
    'sex': os.path.join(base_dir, 'demographic_data', 'compiled', 'sex_compiled.xlsx')
}

print("="*80)
print("GENERATING FACILITY-LEVEL DEMOGRAPHICS")
print("="*80)

def process_facility_demographic(facility_name, config, demographic_name, demo_file):
    """Calculate facility-level demographics using overlap weights"""
    print(f"\n  Processing {facility_name} - {demographic_name}...")
    
    # Load overlap data
    print(f"    Loading overlap data from {config['overlap_sheet']}...")
    overlap_df = pd.read_excel(config['overlap_file'], sheet_name=config['overlap_sheet'])
    
    # Identify FIPS columns (counties) and metadata columns
    fips_cols = [col for col in overlap_df.columns if str(col).startswith('G')]
    meta_cols = [col for col in overlap_df.columns if col not in fips_cols]
    
    print(f"    Found {len(overlap_df)} facilities, {len(fips_cols)} counties with overlap")
    
    # Extract facility metadata
    facility_meta = overlap_df[meta_cols].copy()
    
    # Extract overlap weights matrix (facilities × counties)
    overlap_matrix = overlap_df[fips_cols].values  # Shape: (n_facilities, n_counties)
    
    # Load demographic data
    print(f"    Loading demographic data from {os.path.basename(demo_file)}...")
    demo_xls = pd.ExcelFile(demo_file)
    
    results = {}
    
    for sheet_name in demo_xls.sheet_names:
        print(f"      Processing year: {sheet_name}...")
        
        # Load demographic data for this year
        demo_df = pd.read_excel(demo_file, sheet_name=sheet_name)
        
        # Check for FIPS column
        if 'FIPS' not in demo_df.columns:
            print(f"        ✗ No FIPS column found, skipping")
            continue
        
        # Get demographic columns (exclude metadata columns)
        meta_demo_cols = ['FIPS', 'GISJOIN', 'Region']
        demo_cols = [col for col in demo_df.columns 
                     if col not in meta_demo_cols]
        
        print(f"        Found {len(demo_cols)} demographic columns")
        
        # Remove rows with duplicate or missing FIPS
        demo_df = demo_df.drop_duplicates(subset='FIPS', keep='first')
        demo_df = demo_df.dropna(subset=['FIPS'])
        
        # Set FIPS as index and reindex to match overlap matrix column order
        demo_df = demo_df.set_index('FIPS')
        demo_df_aligned = demo_df.reindex(fips_cols, fill_value=0)
        
        # Extract demographic values as matrix (counties × demographics)
        demo_matrix = demo_df_aligned[demo_cols].fillna(0).values  # Shape: (n_counties, n_demographics)
        
        # VECTORIZED MATRIX MULTIPLICATION
        # overlap_matrix @ demo_matrix = (n_facilities, n_counties) @ (n_counties, n_demographics)
        # Result: (n_facilities, n_demographics)
        facility_demo_matrix = overlap_matrix @ demo_matrix
        
        # Convert to DataFrame
        facility_demo_df = pd.DataFrame(
            facility_demo_matrix,
            columns=demo_cols
        ).round(0).astype(int)
        
        # Combine with facility metadata
        result_df = pd.concat([facility_meta.reset_index(drop=True), facility_demo_df], axis=1)
        
        results[sheet_name] = result_df
        
        print(f"        ✓ Calculated demographics for {len(result_df)} facilities")
    
    # Write to Excel
    output_file = os.path.join(output_base, demographic_name, f"{facility_name}_{demographic_name}_facilities.xlsx")
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
print("✓ ALL FACILITY-LEVEL DEMOGRAPHICS GENERATED SUCCESSFULLY!")
print("="*80)
print(f"\nOutput location: {output_base}")
print(f"Demographics: {len(demographics)}")
print(f"Facility types: {len(facilities)}")
print(f"Total files: {len(demographics) * len(facilities)}")
print("="*80)
