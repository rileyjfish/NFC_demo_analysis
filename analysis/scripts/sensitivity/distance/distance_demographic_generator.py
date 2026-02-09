"""
Generate demographic Excel files for all facilities at different buffer distances (1, 5, 10, 25 miles).
This script processes all 6 demographics (age, education, employment, poverty, race_ethnicity, sex)
for all facility types (curie, reactor, frontend, mines, interim_prop, repo_prop) at each distance.

The 50-mile buffer data is handled separately as the baseline and is not regenerated here.
"""

import xarray as xr
import pandas as pd
import os

# Get absolute paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))

# Define distances to process
DISTANCES = {
    '1mi': '1 Mile',
    '5mi': '5 Mile',
    '10mi': '10 Mile',
    '25mi': '25 Mile'
}

# Define demographics
DEMOGRAPHICS = ['age', 'education', 'employment', 'poverty', 'race_ethnicity', 'sex']

# Define facility configurations
FACILITY_CONFIGS = {
    'curie': {
        'overlap_sheet': 'CURIECountyOverlap',
        'id_cols': ['facility_name', 'FID', 'operating_date', 'license_expiration_date']
    },
    'reactor': {
        'overlap_sheet': 'NPPCountyOverlap',
        'id_cols': ['Name', 'FID', 'Start', 'Stop', 'Capacity (MWe)']
    },
    'frontend': {
        'overlap_sheet': 'FrontendCountyOverlap',
        'id_cols': ['Name', 'FID', 'Start', 'Stop', 'Capacity', 'Capacity Unit', 'Type', 'Status']
    },
    'mines': {
        'overlap_sheet': 'MinesCountyOverlap',
        'id_cols': ['ICF_ID', 'DOCS'],
        'use_excel': True
    },
    'interim_prop': {
        'overlap_sheet': 'InterimCountyOverlap',
        'id_cols': ['Name', 'FID', 'Type', 'Capacity', 'Approx Year', 'Note']
    },
    'repo_prop': {
        'overlap_sheet': 'RepositoryCountyOverlap',
        'id_cols': ['Name', 'FID', 'Type', 'Capacity', 'Approx Year', 'Note']
    }
}

def process_facility_with_nc(distance_key, distance_label, facility_name, config, demographic, demo_ds, overlap_sheets):
    """Process facilities that use NetCDF demographic data files"""
    print(f"    {facility_name}_{demographic}...", end='')
    
    # Get county overlap from pre-loaded sheets
    county_overlap = overlap_sheets[config['overlap_sheet']]
    
    # Get FIPS columns and extract overlap matrix
    fips_cols = [col for col in county_overlap.columns if str(col).startswith('G')]
    overlap_matrix = county_overlap[fips_cols].values  # Shape: (n_facilities, n_counties)
    
    # Extract ID columns for MultiIndex
    id_df = county_overlap[config['id_cols']]
    
    results = {}
    
    for sheet in demo_ds.sheet.values:
        demo = demo_ds['data'].sel(sheet=sheet)
        demo_fips = demo_ds['FIPS'].sel(sheet=sheet).values
        demo_df = pd.DataFrame(demo.values, columns=demo.col.values)
        demo_df['FIPS'] = demo_fips
        demo_df = demo_df.set_index('FIPS')
        
        # Handle duplicate FIPS
        if demo_df.index.duplicated().any():
            demo_df = demo_df[~demo_df.index.duplicated(keep='first')]
        
        # Get demographic columns (exclude _E margin columns)
        demo_cols = [col for col in demo_df.columns if not str(col).endswith('_E')]
        
        # Reindex to match overlap matrix column order
        demo_df_aligned = demo_df.reindex(fips_cols, fill_value=0)
        
        # Extract demographic values as matrix (counties × demographics)
        demo_matrix = demo_df_aligned[demo_cols].fillna(0).values  # Shape: (n_counties, n_demographics)
        
        # VECTORIZED MATRIX MULTIPLICATION
        # overlap_matrix @ demo_matrix = (n_facilities, n_counties) @ (n_counties, n_demographics)
        # Result: (n_facilities, n_demographics)
        facility_demo_matrix = overlap_matrix @ demo_matrix
        
        # Create DataFrame with MultiIndex
        result_df = pd.DataFrame(
            facility_demo_matrix,
            columns=demo_cols
        ).round(0).astype(int)
        result_df.index = pd.MultiIndex.from_frame(id_df)
        results[sheet] = result_df
    
    # Export to Excel
    output_dir = os.path.join(BASE_DIR, 'analysis', 'outputs', 'sensitivity_analysis', 'distance', distance_label, demographic)
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'{distance_key}_{facility_name}_{demographic}.xlsx')
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for sheet, df in results.items():
            df.to_excel(writer, sheet_name=str(sheet))
    
    print(f" ✓")

def process_mines_with_excel(distance_key, distance_label, demographic, demo_ds, overlap_sheets):
    """Process mines facilities that use Excel demographic data files"""
    print(f"    mines_{demographic}...", end='')
    
    # Get county overlap from pre-loaded sheets
    mines_overlap = overlap_sheets['MinesCountyOverlap']
    
    # Get FIPS columns and extract overlap matrix
    fips_cols = [col for col in mines_overlap.columns if str(col).startswith('G')]
    overlap_matrix = mines_overlap[fips_cols].values  # Shape: (n_facilities, n_counties)
    
    # Extract ID columns
    mines_id_df = mines_overlap[FACILITY_CONFIGS['mines']['id_cols']]
    
    mines_results = {}
    
    for sheet_name, demo_df in demo_ds.items():
        # Skip sheets before 1970 for education/employment
        if demographic in ['education', 'employment']:
            if '1950' in sheet_name or '1960' in sheet_name:
                continue
        
        # Set FIPS as index if it's a column
        if 'FIPS' in demo_df.columns:
            demo_df = demo_df.set_index('FIPS')
        
        # Select only numeric columns
        demo_df = demo_df.select_dtypes(include=['number'])
        
        # Handle duplicate columns
        if demo_df.columns.duplicated().any():
            demo_df = demo_df.groupby(demo_df.columns, axis=1).sum()
        
        # Handle duplicate FIPS
        if demo_df.index.duplicated().any():
            demo_df = demo_df.groupby(demo_df.index).sum()
        
        # Store column names
        demo_cols = demo_df.columns.tolist()
        
        # Reindex to match overlap matrix column order
        demo_df_aligned = demo_df.reindex(fips_cols, fill_value=0)
        
        # Extract demographic values as matrix (counties × demographics)
        demo_matrix = demo_df_aligned.fillna(0).values  # Shape: (n_counties, n_demographics)
        
        # VECTORIZED MATRIX MULTIPLICATION
        # overlap_matrix @ demo_matrix = (n_facilities, n_counties) @ (n_counties, n_demographics)
        # Result: (n_facilities, n_demographics)
        facility_demo_matrix = overlap_matrix @ demo_matrix
        
        # Create DataFrame with MultiIndex
        result_df = pd.DataFrame(
            facility_demo_matrix,
            columns=demo_cols
        ).round(0).astype(int)
        result_df.index = pd.MultiIndex.from_frame(mines_id_df)
        mines_results[sheet_name] = result_df
    
    # Export to Excel
    output_dir = os.path.join(BASE_DIR, 'analysis', 'outputs', 'sensitivity_analysis', 'distance', distance_label, demographic)
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'{distance_key}_mines_{demographic}.xlsx')
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for sheet, df in mines_results.items():
            df.to_excel(writer, sheet_name=str(sheet))
    
    print(f" ✓")

def process_distance(distance_key, distance_label):
    """Process all demographics and facilities for one distance"""
    print(f"\n{'='*70}")
    print(f"Processing {distance_label} ({distance_key})")
    print(f"{'='*70}")
    
    # Load all county overlap sheets once for this distance
    overlap_file = os.path.join(BASE_DIR, 'analysis', 'outputs', 'sensitivity_analysis', 'distance', distance_label, f'{distance_key}_county_overlap.xlsx')
    print(f"  Loading county overlap file...")
    with pd.ExcelFile(overlap_file) as xls:
        overlap_sheets = {sheet: pd.read_excel(xls, sheet_name=sheet) for sheet in xls.sheet_names}
    print(f"  ✓ Loaded {len(overlap_sheets)} overlap sheets")
    
    for demographic in DEMOGRAPHICS:
        print(f"  {demographic}:")
        
        # Load demographic data once for this demographic
        if demographic in ['age', 'education', 'employment']:
            # Excel-based demographics (for mines)
            if demographic == 'age':
                demo_path = os.path.join(BASE_DIR, 'demographic_data', 'compiled', 'age_combined.xlsx')
            else:
                demo_path = os.path.join(BASE_DIR, 'demographic_data', 'compiled', f'{demographic}_compiled.xlsx')
            demo_excel = pd.read_excel(demo_path, sheet_name=None)
        else:
            demo_excel = None
        
        # NetCDF-based demographics (for all facilities)
        demo_path = os.path.join(BASE_DIR, 'demographic_data', 'compiled', f'{demographic}_combined.nc')
        demo_ds = xr.open_dataset(demo_path)
        
        # Process each facility type
        for facility_name, config in FACILITY_CONFIGS.items():
            if facility_name == 'mines' and demo_excel is not None:
                process_mines_with_excel(distance_key, distance_label, demographic, demo_excel, overlap_sheets)
            else:
                process_facility_with_nc(distance_key, distance_label, facility_name, config, demographic, demo_ds, overlap_sheets)
        
        # Close the NetCDF file to free memory
        demo_ds.close()

def main():
    """Main processing function"""
    print("="*70)
    print("DISTANCE DEMOGRAPHIC GENERATOR")
    print("Generating demographic Excel files for all facilities at all distances")
    print("="*70)
    
    for distance_key, distance_label in DISTANCES.items():
        process_distance(distance_key, distance_label)
    
    print("\n" + "="*70)
    print("✓ All distance demographic files generated successfully!")
    print("="*70)

if __name__ == "__main__":
    main()
