"""Debug script to trace exactly what the plotting function sees for DOE age 20-34"""
import pandas as pd
import sys
import os

# Add the script directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configuration
REGION_MAP = {1: 'Midwest', 2: 'Northeast', 3: 'Southeast', 4: 'Southwest', 5: 'West'}
file_path = r'c:\Users\rjf\Desktop\Research\Fuel Cycle Analysis\analysis\outputs\demographics_by_county\age\interim_prop_age_counties.xlsx'

INTERIM_FACILITY_BINS = {
    'DOE': {
        'Stage 1': [4],
        'Stage 2': [5],
        'Stage 3': [6]
    }
}

AGE_CONFIG = {
    'baseline_file': r'c:\Users\rjf\Desktop\Research\Fuel Cycle Analysis\demographic_data\compiled\age_combined.xlsx',
    'rebin': True,
    'rebin_map': {
        '0-4': '<19', '5-9': '<19', '10-14': '<19', '15-19': '<19',
        '20-24': '20-34', '25-29': '20-34', '30-34': '20-34',
        '35-39': '35-59', '40-44': '35-59', '45-49': '35-59',
        '50-54': '35-59', '55-59': '35-59',
        '60-64': '60+', '65-69': '60+', '70-74': '60+', '75+': '60+'
    },
    'exclude_from_total': []
}

def calculate_exposed_proportions_by_stage(df, demo_cols):
    """Calculate demographic proportions for exposed populations by region"""
    results = {}
    
    for region_id in REGION_MAP.keys():
        region_df = df[df['Region'] == region_id].copy()
        
        if region_df.empty:
            print(f"  Region {region_id} ({REGION_MAP[region_id]}): No data at all")
            continue
        
        exposed_df = region_df[region_df['Buffer_Fraction'] > 0].copy()
        
        if exposed_df.empty:
            print(f"  Region {region_id} ({REGION_MAP[region_id]}): Has data but no exposure (Buffer_Fraction > 0)")
            continue
        
        totals = exposed_df[demo_cols].sum()
        population_total = totals.sum()
        
        if population_total > 0:
            proportions = totals / population_total
            results[region_id] = proportions
            print(f"  Region {region_id} ({REGION_MAP[region_id]}): {len(exposed_df)} exposed counties, 20-34 proportion = {proportions['20-34']:.6f}")
        else:
            print(f"  Region {region_id} ({REGION_MAP[region_id]}): Has exposed counties but population total = 0")
    
    return results

print("="*80)
print("DEBUGGING DOE PLOTTING FOR AGE 20-34")
print("="*80)

# Process each DOE stage
for stage_name, note_list in INTERIM_FACILITY_BINS['DOE'].items():
    print(f"\n{stage_name} (Notes {note_list}):")
    print("-" * 80)
    
    # Read all sheets for this stage's notes
    all_dfs = []
    for note in note_list:
        sheet_name = f"Stage {note} - 1990"
        print(f"  Reading sheet: {sheet_name}")
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        all_dfs.append(df)
    
    # Combine all dataframes
    df_all = pd.concat(all_dfs, ignore_index=True)
    
    # Apply rebinning
    print("\n  Rebinning age groups...")
    age_cols = [col for col in df_all.columns if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
    rebinned_cols = {}
    for col in age_cols:
        if col in AGE_CONFIG['rebin_map']:
            new_col = AGE_CONFIG['rebin_map'][col]
            if new_col not in rebinned_cols:
                rebinned_cols[new_col] = df_all[col]
            else:
                rebinned_cols[new_col] += df_all[col]
        else:
            rebinned_cols[col] = df_all[col]
    
    result_df = df_all[['FIPS', 'Region', 'Buffer_Fraction']].copy()
    for col_name, col_data in rebinned_cols.items():
        result_df[col_name] = col_data
    df_all = result_df
    
    # Get rebinned demo columns
    demo_cols = [col for col in df_all.columns if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
    
    print(f"\n  Calculating proportions by region:")
    stage_props = calculate_exposed_proportions_by_stage(df_all, demo_cols)
    
    print(f"\n  SUMMARY - Regions with 20-34 data:")
    for region_id, proportions in stage_props.items():
        print(f"    Region {region_id} ({REGION_MAP[region_id]}): 20-34 = {proportions['20-34']:.6f}")

print("\n" + "="*80)
print("PLOTTING SIMULATION")
print("="*80)

# Simulate what the plotting function would see
stages_list = ['Stage 1', 'Stage 2', 'Stage 3']
data = {'exposed': {'Stage 1': {}, 'Stage 2': {}, 'Stage 3': {}}}

# Simulate populating data structure as done in process_interim_demographic
for stage_name, note_list in INTERIM_FACILITY_BINS['DOE'].items():
    all_dfs = []
    for note in note_list:
        sheet_name = f"Stage {note} - 1990"
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        all_dfs.append(df)
    
    df_all = pd.concat(all_dfs, ignore_index=True)
    
    # Apply rebinning
    age_cols = [col for col in df_all.columns if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
    rebinned_cols = {}
    for col in age_cols:
        if col in AGE_CONFIG['rebin_map']:
            new_col = AGE_CONFIG['rebin_map'][col]
            if new_col not in rebinned_cols:
                rebinned_cols[new_col] = df_all[col]
            else:
                rebinned_cols[new_col] += df_all[col]
        else:
            rebinned_cols[col] = df_all[col]
    
    result_df = df_all[['FIPS', 'Region', 'Buffer_Fraction']].copy()
    for col_name, col_data in rebinned_cols.items():
        result_df[col_name] = col_data
    df_all = result_df
    
    # Calculate proportions
    demo_cols = [col for col in df_all.columns if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
    stage_props = calculate_exposed_proportions_by_stage(df_all, demo_cols)
    
    # Store in data structure
    data['exposed'][stage_name] = {}
    for region_id, proportions in stage_props.items():
        data['exposed'][stage_name][region_id] = {}
        for col in proportions.index:
            data['exposed'][stage_name][region_id][col] = [(1990, proportions[col])]

print("\nWhat the plotting function sees for each region and stage:")
column_name = '20-34'
for stage_name in stages_list:
    print(f"\n{stage_name}:")
    for region_id, region_name in REGION_MAP.items():
        if (region_id in data['exposed'].get(stage_name, {}) and 
            column_name in data['exposed'][stage_name][region_id] and
            data['exposed'][stage_name][region_id][column_name]):
            value = data['exposed'][stage_name][region_id][column_name][0][1]
            print(f"  Region {region_id} ({region_name}): {value:.6f}")
        else:
            print(f"  Region {region_id} ({region_name}): 0 (no data)")
