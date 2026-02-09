"""
Debug script to trace through DOE processing step-by-step
Compare what regional_figure_generator.py does vs what should happen
"""

import pandas as pd
import os

# Get absolute paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
DEMO_BASE = os.path.join(BASE_DIR, 'outputs', 'demographics_by_county')

REGION_MAP = {
    1: 'Midwest',
    2: 'Northeast',
    3: 'Southeast',
    4: 'Southwest',
    5: 'West'
}

# Age rebinning map
REBIN_MAP = {
    '<5': '<19', '5-14': '<19', '15-19': '<19',
    '20-24': '20-34', '25-34': '20-34',
    '35-44': '35-59', '45-54': '35-59', '55-59': '35-59',
    '60-64': '60+', '65-74': '60+', '75-84': '60+', '85+': '60+'
}

DOE_STAGES = {
    'Stage 1': 4,
    'Stage 2': 5,
    'Stage 3': 6
}

print("="*70)
print("Debugging DOE Age Processing for 20-34 Age Group")
print("="*70)

file_path = os.path.join(DEMO_BASE, 'age', 'interim_prop_age_counties.xlsx')
xls = pd.ExcelFile(file_path)

for stage_name, stage_num in DOE_STAGES.items():
    print(f"\n{'='*70}")
    print(f"{stage_name} (Note {stage_num})")
    print('='*70)
    
    sheet_name = f"Stage {stage_num} - 1990"
    print(f"\nReading sheet: {sheet_name}")
    
    df_raw = pd.read_excel(file_path, sheet_name=sheet_name)
    
    print(f"\nRaw data shape: {df_raw.shape}")
    print(f"Columns: {df_raw.columns.tolist()}")
    
    # Check exposed counties by region BEFORE rebinning
    print("\n--- BEFORE REBINNING ---")
    for region_id, region_name in REGION_MAP.items():
        region_df = df_raw[df_raw['Region'] == region_id]
        exposed = region_df[region_df['Buffer_Fraction'] > 0]
        print(f"{region_name} (Region {region_id}): {len(exposed)} exposed counties")
        if len(exposed) > 0:
            print(f"  FIPS codes: {exposed['FIPS'].tolist()[:5]}...")  # Show first 5
    
    # Apply rebinning like the fixed code does
    print("\n--- APPLYING REBINNING ---")
    age_cols = [col for col in df_raw.columns 
               if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
    print(f"Age columns found: {age_cols}")
    
    rebinned_cols = {}
    for col in age_cols:
        if col in REBIN_MAP:
            new_col = REBIN_MAP[col]
            if new_col not in rebinned_cols:
                rebinned_cols[new_col] = df_raw[col]
            else:
                rebinned_cols[new_col] += df_raw[col]
        else:
            rebinned_cols[col] = df_raw[col]
    
    # Preserve metadata columns
    result_df = df_raw[['FIPS', 'Region', 'Buffer_Fraction']].copy()
    for col_name, col_data in rebinned_cols.items():
        result_df[col_name] = col_data
    
    print(f"After rebinning columns: {result_df.columns.tolist()}")
    
    # Check exposed counties by region AFTER rebinning
    print("\n--- AFTER REBINNING ---")
    for region_id, region_name in REGION_MAP.items():
        region_df = result_df[result_df['Region'] == region_id]
        exposed = region_df[region_df['Buffer_Fraction'] > 0]
        print(f"{region_name} (Region {region_id}): {len(exposed)} exposed counties")
    
    # Calculate proportions for 20-34 age group
    print("\n--- CALCULATING PROPORTIONS FOR 20-34 ---")
    demo_cols = [col for col in result_df.columns 
                 if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
    
    for region_id, region_name in REGION_MAP.items():
        region_df = result_df[result_df['Region'] == region_id].copy()
        exposed_df = region_df[region_df['Buffer_Fraction'] > 0].copy()
        
        if exposed_df.empty:
            print(f"{region_name}: No exposed counties")
            continue
        
        totals = exposed_df[demo_cols].sum()
        population_total = totals.sum()
        
        if population_total > 0:
            proportions = totals / population_total
            if '20-34' in proportions.index:
                print(f"{region_name}: 20-34 proportion = {proportions['20-34']:.6f}")
                print(f"  Total exposed pop: {population_total:.0f}")
                print(f"  20-34 pop: {totals['20-34']:.0f}")
        else:
            print(f"{region_name}: Population total is 0")

print("\n" + "="*70)
print("ANALYSIS COMPLETE")
print("="*70)
