"""
Generate demographic statistics for mines and reserves at 10-mile buffer zone.
This script processes all 6 demographics (age, education, employment, poverty, race_ethnicity, sex)
for mines (indexed by ICF_ID, RELIABILIT) and reserves (aggregated across all reserve counties).
"""

import xarray as xr
import pandas as pd
import os

# Define paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
BASE_PATH = os.path.join(BASE_DIR, 'analysis', 'outputs', 'sensitivity_analysis', 'mine_reliability')
OVERLAP_FILE = os.path.join(BASE_PATH, 'mines_reserves_reliability_overlap.xlsx')

# Define demographics
demographics = ['age', 'education', 'employment', 'poverty', 'race_ethnicity', 'sex']

# Load overlap data once (reused for all demographics)
print("Loading overlap data...")
MINES_OVERLAP = pd.read_excel(OVERLAP_FILE, sheet_name='MinesCountyOverlap', index_col=[0, 1])
RESERVES_OVERLAP = pd.read_excel(OVERLAP_FILE, sheet_name='ReservesCountyOverlap', index_col=0)
FIPS_COLS = [col for col in MINES_OVERLAP.columns if str(col).startswith('G')]
print(f"✓ Loaded overlap data: {len(MINES_OVERLAP)} mines, {len([c for c in RESERVES_OVERLAP.columns if str(c).startswith('G')])} reserve counties\n")

def process_mines_with_nc(demographic):
    """Process mines facilities that use NetCDF demographic data files"""
    print(f"  Processing mines_{demographic}...")
    
    # Load demographic dataset
    demo_ds = xr.open_dataset(os.path.join(BASE_DIR, 'demographic_data', 'compiled', f'{demographic}_combined.nc'))
    
    results = {}
    
    for sheet in demo_ds.sheet.values:
        print(f"    Processing year: {sheet}")
        demo = demo_ds['data'].sel(sheet=sheet)
        demo_fips = demo_ds['FIPS'].sel(sheet=sheet).values
        demo_df = pd.DataFrame(demo.values, columns=demo.col.values)
        demo_df['FIPS'] = demo_fips
        demo_df = demo_df.set_index('FIPS')
        
        # Handle duplicate FIPS by keeping only the first occurrence
        if demo_df.index.duplicated().any():
            demo_df = demo_df[~demo_df.index.duplicated(keep='first')]
        
        mine_results = []
        mine_count = 0
        for idx in range(len(MINES_OVERLAP)):
            mine_count += 1
            if mine_count % 100 == 0:
                icf_id = MINES_OVERLAP.iloc[idx].name[0]  # Get ICF_ID from MultiIndex
                print(f"      Processed {mine_count} mines (current: ICF_ID={icf_id})")
            overlap = MINES_OVERLAP.iloc[idx][FIPS_COLS]
            overlap.name = None  # Remove name to avoid alignment issues
            overlap = overlap[overlap > 0]
            joined = demo_df.loc[demo_df.index.intersection(overlap.index)]
            weighted = joined.mul(overlap, axis=0)
            buffer_sum = weighted.sum(axis=0)
            mine_results.append(buffer_sum)
        
        # Create DataFrame with MultiIndex
        result_df = pd.DataFrame(mine_results, columns=demo.col.values)
        result_df = result_df.round(0).astype(int)
        result_df.index = MINES_OVERLAP.index
        results[sheet] = result_df
    
    # Export to Excel
    output_file = os.path.join(BASE_PATH, 'demographics', f'mines_{demographic}.xlsx')
    with pd.ExcelWriter(output_file) as writer:
        for sheet, df in results.items():
            df.to_excel(writer, sheet_name=str(sheet))
    
    print(f"    Saved {output_file}")

def process_mines_with_excel(demographic):
    """Process mines facilities that use Excel demographic data files"""
    print(f"  Processing mines_{demographic}...")
    
    # Determine data source
    if demographic == 'age':
        demo_ds = pd.read_excel('Demographic Data/Demographic Data Compilation/age_combined.xlsx', sheet_name=None)
    elif demographic in ['education', 'employment']:
        demo_ds = pd.read_excel(f'Demographic Data/Demographic Data Compilation/Compiled sheets/{demographic}_compiled.xlsx', sheet_name=None)
    else:
        # For poverty, race_ethnicity, sex - use nc files
        process_mines_with_nc(demographic)
        return
    
    mines_results = {}
    
    for sheet_name, demo_df in demo_ds.items():
        # Skip sheets before 1970 for education/employment
        if demographic in ['education', 'employment']:
            if '1950' in sheet_name or '1960' in sheet_name:
                continue
        
        print(f"    Processing year: {sheet_name}")
        
        # Set FIPS as index if it's a column
        if 'FIPS' in demo_df.columns:
            demo_df = demo_df.set_index('FIPS')
        
        # Select only numeric columns
        demo_df = demo_df.select_dtypes(include=['number'])
        
        # Store column names before processing
        column_names = demo_df.columns.tolist()
        
        # Handle duplicate columns by grouping and summing
        if demo_df.columns.duplicated().any():
            demo_df = demo_df.groupby(demo_df.columns, axis=1).sum()
            column_names = demo_df.columns.tolist()
        
        # Handle duplicate FIPS in index by grouping and summing
        if demo_df.index.duplicated().any():
            demo_df = demo_df.groupby(demo_df.index).sum()
        
        mine_results = []
        mine_count = 0
        for idx in range(len(MINES_OVERLAP)):
            mine_count += 1
            if mine_count % 100 == 0:
                icf_id = MINES_OVERLAP.iloc[idx].name[0]  # Get ICF_ID from MultiIndex
                print(f"      Processed {mine_count} mines (current: ICF_ID={icf_id})")
            overlap = MINES_OVERLAP.iloc[idx][FIPS_COLS]
            overlap.name = None  # Remove name to avoid alignment issues
            overlap = overlap[overlap > 0]
            joined = demo_df.loc[demo_df.index.intersection(overlap.index)]
            weighted = joined.mul(overlap, axis=0)
            buffer_sum = weighted.sum(axis=0)
            mine_results.append(buffer_sum)
        
        # Create DataFrame with MultiIndex
        result_df = pd.DataFrame(mine_results, columns=column_names)
        result_df = result_df.round(0).astype(int)
        result_df.index = MINES_OVERLAP.index
        mines_results[sheet_name] = result_df
    
    # Export to Excel
    output_file = os.path.join(BASE_PATH, 'demographics', f'mines_{demographic}.xlsx')
    with pd.ExcelWriter(output_file) as writer:
        for sheet, df in mines_results.items():
            df.to_excel(writer, sheet_name=str(sheet))
    
    print(f"    Saved {output_file}")

def process_reserves_with_nc(demographic):
    """Process reserves that use NetCDF demographic data files"""
    print(f"  Processing reserves_{demographic}...")
    
    # Load demographic dataset
    demo_ds = xr.open_dataset(os.path.join(BASE_DIR, 'demographic_data', 'compiled', f'{demographic}_combined.nc'))
    
    results = {}
    
    for sheet in demo_ds.sheet.values:
        print(f"    Processing year: {sheet}")
        demo = demo_ds['data'].sel(sheet=sheet)
        demo_fips = demo_ds['FIPS'].sel(sheet=sheet).values
        demo_df = pd.DataFrame(demo.values, columns=demo.col.values)
        demo_df['FIPS'] = demo_fips
        demo_df = demo_df.set_index('FIPS')
        
        # Handle duplicate FIPS by keeping only the first occurrence
        if demo_df.index.duplicated().any():
            demo_df = demo_df[~demo_df.index.duplicated(keep='first')]
        
        # Calculate weighted demographics across all reserve counties
        reserve_results = []
        for fips_code in RESERVES_OVERLAP.columns:
            if not str(fips_code).startswith('G'):
                continue
            overlap_pct = RESERVES_OVERLAP.loc['percent_overlap', fips_code]
            if overlap_pct > 0 and fips_code in demo_df.index:
                weighted = demo_df.loc[fips_code] * overlap_pct
                reserve_results.append(weighted)
        
        # Sum all weighted counties for reserves
        if reserve_results:
            result_df = pd.DataFrame(reserve_results).sum(axis=0).to_frame().T
            result_df.columns = demo.col.values
            result_df = result_df.round(0).astype(int)
            result_df.index = ['Reserves']
        else:
            result_df = pd.DataFrame(columns=demo.col.values)
        
        results[sheet] = result_df
    
    # Export to Excel
    output_file = f"{BASE_PATH}/../../outputs/sensitivity_analysis/mine_reliability/demographics/reserves_{demographic}.xlsx"
    with pd.ExcelWriter(output_file) as writer:
        for sheet, df in results.items():
            df.to_excel(writer, sheet_name=str(sheet))
    
    print(f"    Saved {output_file}")

def process_reserves_with_excel(demographic):
    """Process reserves that use Excel demographic data files"""
    print(f"  Processing reserves_{demographic}...")
    
    # Determine data source
    if demographic == 'age':
        demo_ds = pd.read_excel('Demographic Data/Demographic Data Compilation/age_combined.xlsx', sheet_name=None)
    elif demographic in ['education', 'employment']:
        demo_ds = pd.read_excel(f'Demographic Data/Demographic Data Compilation/Compiled sheets/{demographic}_compiled.xlsx', sheet_name=None)
    else:
        # For poverty, race_ethnicity, sex - use nc files
        process_reserves_with_nc(demographic)
        return
    
    reserves_results = {}
    
    for sheet_name, demo_df in demo_ds.items():
        # Skip sheets before 1970 for education/employment
        if demographic in ['education', 'employment']:
            if '1950' in sheet_name or '1960' in sheet_name:
                continue
        
        print(f"    Processing year: {sheet_name}")
        
        # Set FIPS as index if it's a column
        if 'FIPS' in demo_df.columns:
            demo_df = demo_df.set_index('FIPS')
        
        # Select only numeric columns
        demo_df = demo_df.select_dtypes(include=['number'])
        
        # Store column names before processing
        column_names = demo_df.columns.tolist()
        
        # Handle duplicate columns by grouping and summing
        if demo_df.columns.duplicated().any():
            demo_df = demo_df.groupby(demo_df.columns, axis=1).sum()
            column_names = demo_df.columns.tolist()
        
        # Handle duplicate FIPS in index by grouping and summing
        if demo_df.index.duplicated().any():
            demo_df = demo_df.groupby(demo_df.index).sum()
        
        # Calculate weighted demographics across all reserve counties
        reserve_results = []
        for fips_code in RESERVES_OVERLAP.columns:
            if not str(fips_code).startswith('G'):
                continue
            overlap_pct = RESERVES_OVERLAP.loc['percent_overlap', fips_code]
            if overlap_pct > 0 and fips_code in demo_df.index:
                weighted = demo_df.loc[fips_code] * overlap_pct
                reserve_results.append(weighted)
        
        # Sum all weighted counties for reserves
        if reserve_results:
            result_df = pd.DataFrame(reserve_results).sum(axis=0).to_frame().T
            result_df.columns = column_names
            result_df = result_df.round(0).astype(int)
            result_df.index = ['Reserves']
        else:
            result_df = pd.DataFrame(columns=column_names)
        
        reserves_results[sheet_name] = result_df
    
    # Export to Excel
    output_file = os.path.join(BASE_PATH, 'demographics', f'reserves_{demographic}.xlsx')
    with pd.ExcelWriter(output_file) as writer:
        for sheet, df in reserves_results.items():
            df.to_excel(writer, sheet_name=str(sheet))
    
    print(f"    Saved {output_file}")

# Main processing loop
print(f"Generating demographic statistics for mines and reserves...")
print("=" * 70)

# Create output directory
os.makedirs(os.path.join(BASE_PATH, 'demographics'), exist_ok=True)

for demographic in demographics:
    print(f"\nProcessing {demographic} demographic:")
    
    # Process mines
    if demographic in ['age', 'education', 'employment']:
        process_mines_with_excel(demographic)
    else:
        process_mines_with_nc(demographic)
    
    # Process reserves
    if demographic in ['age', 'education', 'employment']:
        process_reserves_with_excel(demographic)
    else:
        process_reserves_with_nc(demographic)

print("\n" + "=" * 70)
print(f"✓ All demographic statistics for mines and reserves generated successfully!")
print(f"✓ Output files saved to: {os.path.join(BASE_PATH, 'demographics')}")
print("=" * 70)


