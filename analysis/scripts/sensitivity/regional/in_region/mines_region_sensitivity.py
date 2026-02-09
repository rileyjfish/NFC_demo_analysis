"""
Analyze demographic proportions near mines across different regions.
Generates figures comparing exposed populations vs. regional baseline populations and reserves.
Since mine data has no temporal component, no standard/residual split is needed.
Outputs directly to Mines/ directory.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os
import re
import xarray as xr

# Set plot style
sns.set_style('white')

# Label mapping for expanding abbreviations
LABEL_MAP = {
    '2+': '2 or More Races',
    'B': 'Black',
    'W': 'White',
    'AIAN': 'American Indian and Alaska Native',
    'AAPI': 'Asian American and Pacific Islander',
    'O': 'Other',
    'H': 'Hispanic/Latino',
    'M': 'Male',
    'F': 'Female',
    '<9': 'Less than 9th Grade',
    '<B': 'Less than Bachelor\'s Degree',
    'B+': 'Bachelor\'s Degree or Higher',
    'LF-CIV': 'Civilian Labor Force',
    'LF-CIV-EMPL': 'Employed'
}

def get_label(col):
    """Get expanded label for column name"""
    return LABEL_MAP.get(col, col)

# Get absolute paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
OUTPUT_BASE = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'regional', 'in_region', 'mines')
DEMO_BASE = os.path.join(BASE_DIR, 'outputs', 'demographics_by_county')
COMPILED_BASE = os.path.join(BASE_DIR, '../demographic_data', 'compiled')

# Create output directory
os.makedirs(OUTPUT_BASE, exist_ok=True)

# Define regions
REGION_MAP = {
    1: 'Midwest',
    2: 'Northeast',
    3: 'Southeast',
    4: 'Southwest',
    5: 'West'
}

# Define demographics and their special handling
demographics = {
    'age': {
        'file': 'age',
        'rebin': True,
        'rebin_map': {
            '<5': '<19', '5-14': '<19', '15-19': '<19',
            '20-24': '20-34', '25-34': '20-34',
            '35-44': '35-59', '45-54': '35-59', '55-59': '35-59',
            '60-64': '60+', '65-74': '60+', '75-84': '60+', '85+': '60+'
        },
        'baseline_file': os.path.join(COMPILED_BASE, 'age_combined.xlsx')
    },
    'education': {
        'file': 'education',
        'columns': ['<9', '<B', 'B+'],
        'baseline_file': os.path.join(COMPILED_BASE, 'education_compiled.xlsx')
    },
    'employment': {
        'file': 'employment',
        'special': 'unemployment',
        'columns': ['LF-CIV', 'LF-CIV-EMPL'],
        'baseline_file': os.path.join(COMPILED_BASE, 'employment_compiled.xlsx')
    },
    'poverty': {
        'file': 'poverty',
        'special': 'poverty_rate',
        'columns': ['Poverty', 'PSD'],
        'baseline_file': os.path.join(COMPILED_BASE, 'poverty_compiled.xlsx')
    },
    'race_ethnicity': {
        'file': 'race_ethnicity',
        'exclude_from_total': ['H'],
        'columns': ['W', 'B', 'AIAN', 'AAPI', 'O', '2+', 'H'],
        'baseline_file': os.path.join(COMPILED_BASE, 'race_ethnicity_compiled.xlsx')
    },
    'sex': {
        'file': 'sex',
        'columns': ['M', 'F'],
        'baseline_file': os.path.join(COMPILED_BASE, 'sex_compiled.xlsx')
    }
}

def parse_year(sheet_name):
    """Extract year from sheet name, handling ranges by taking the average"""
    match = re.search(r'(\d{4})(?:-(\d{4}))?', str(sheet_name))
    if match:
        year1 = int(match.group(1))
        year2 = match.group(2)
        if year2:
            return (year1 + int(year2)) / 2
        return float(year1)
    return None

def rebin_age_df(df, rebin_map):
    """Rebin age columns in dataframe"""
    # Get age columns (exclude FIPS, Region, Buffer_Fraction)
    age_cols = [col for col in df.columns if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
    
    if not age_cols:
        return df
    
    # Create rebinned dataframe
    rebinned_cols = {}
    for col in age_cols:
        if col in rebin_map:
            new_col = rebin_map[col]
            if new_col not in rebinned_cols:
                rebinned_cols[new_col] = df[col]
            else:
                rebinned_cols[new_col] += df[col]
        else:
            rebinned_cols[col] = df[col]
    
    # Combine with non-age columns
    result_df = df[['FIPS', 'Region']].copy()
    for col_name, col_data in rebinned_cols.items():
        result_df[col_name] = col_data
    
    return result_df

def calculate_exposed_proportions_by_region(df, demographic_config):
    """Calculate demographic proportions for exposed populations by region"""
    demo_name = demographic_config['file']
    
    # Get demographic columns (exclude FIPS, Region, Buffer_Fraction)
    demo_cols = [col for col in df.columns if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
    
    if not demo_cols:
        return {}
    
    results = {}
    
    for region_id in REGION_MAP.keys():
        region_df = df[df['Region'] == region_id]
        
        if region_df.empty:
            continue
        
        # Sum demographics across all counties in this region
        totals = region_df[demo_cols].sum()
        
        # Handle special cases
        if 'special' in demographic_config:
            if demographic_config['special'] == 'unemployment':
                if 'LF-CIV' in totals.index and 'LF-CIV-EMPL' in totals.index:
                    total_lf_civ = totals['LF-CIV']
                    total_employed = totals['LF-CIV-EMPL']
                    if total_lf_civ > 0:
                        unemployment = 1 - (total_employed / total_lf_civ)
                        results[region_id] = pd.Series({'Unemployment': unemployment})
                continue
            
            elif demographic_config['special'] == 'poverty_rate':
                if 'Poverty' in totals.index and 'PSD' in totals.index:
                    total_poverty = totals['Poverty']
                    total_psd = totals['PSD']
                    if total_psd > 0:
                        poverty_rate = total_poverty / total_psd
                        results[region_id] = pd.Series({'Poverty Rate': poverty_rate})
                continue
        
        # Calculate proportions
        if 'exclude_from_total' in demographic_config:
            # For race_ethnicity: exclude H from total, but calculate proportion for all
            total_cols = [col for col in totals.index if col not in demographic_config['exclude_from_total']]
            population_total = totals[total_cols].sum()
            if population_total > 0:
                proportions = totals / population_total
                results[region_id] = proportions
        else:
            # Standard: sum all columns for total
            population_total = totals.sum()
            if population_total > 0:
                proportions = totals / population_total
                results[region_id] = proportions
    
    return results

def calculate_baseline_and_reserves_proportions_by_region(baseline_file, demographic_config, sheet_name, expected_columns, demo_name):
    """Calculate demographic proportions for baseline and reserves populations by region
    
    Args:
        baseline_file: Path to baseline demographic file (Excel or NetCDF)
        demographic_config: Configuration for this demographic
        sheet_name: Sheet name to load (matching the mine data sheets)
        expected_columns: List of demographic columns expected (from exposed data)
        demo_name: Name of the demographic for loading reserves data
    """
    try:
        # Check if file is NetCDF or Excel
        if baseline_file.endswith('.nc'):
            # Load NetCDF file
            ds = xr.open_dataset(baseline_file)
            
            # Parse year from sheet_name
            year = parse_year(sheet_name)
            if year is None:
                return {}, None
            
            # Find the closest year in the dataset
            if 'year' in ds.dims:
                # Get the closest year
                year_idx = abs(ds['year'].values - year).argmin()
                ds = ds.isel(year=year_idx)
            
            # Convert to dataframe
            df = ds.to_dataframe().reset_index()
        else:
            # Load Excel file using the same sheet name as mine data
            df = pd.read_excel(baseline_file, sheet_name=sheet_name)
        
    except Exception as e:
        print(f"    Warning: Could not load {baseline_file} for sheet {sheet_name}: {e}")
        return {}, None
    
    if 'Region' not in df.columns:
        return {}, None
    
    # Fill missing columns with 0
    for col in expected_columns:
        if col not in df.columns:
            df[col] = 0
    
    # Only use columns that match expected demographic columns
    available_cols = [col for col in df.columns if col in expected_columns]
    
    if not available_cols:
        return {}, None
    
    demo_cols = available_cols
    
    # Handle age rebinning for baseline
    if demographic_config.get('rebin', False):
        # Create rebinned columns
        rebin_map = demographic_config['rebin_map']
        rebinned_data = {'FIPS': df['FIPS'], 'Region': df['Region']}
        
        for col in demo_cols:
            if col in rebin_map:
                new_col = rebin_map[col]
                if new_col not in rebinned_data:
                    rebinned_data[new_col] = df[col]
                else:
                    rebinned_data[new_col] += df[col]
            else:
                if col in df.columns:
                    rebinned_data[col] = df[col]
        
        df = pd.DataFrame(rebinned_data)
        demo_cols = [col for col in df.columns if col not in ['FIPS', 'Region']]
    
    results = {}
    reserves_props = {}
    
    # Load reserves data from demographics_by_county
    try:
        reserves_file = os.path.join(DEMO_BASE, demo_name, f'reserves_{demo_name}_counties.xlsx')
        df_reserves = pd.read_excel(reserves_file, sheet_name=sheet_name)
        
        # Fill missing columns with 0
        for col in expected_columns:
            if col not in df_reserves.columns:
                df_reserves[col] = 0
        
        # Get demographic columns from reserves
        reserves_demo_cols = [col for col in df_reserves.columns if col in expected_columns]
        
        # Handle age rebinning for reserves
        if demographic_config.get('rebin', False):
            rebin_map = demographic_config['rebin_map']
            rebinned_data = {'FIPS': df_reserves['FIPS'], 'Region': df_reserves['Region']}
            
            for col in reserves_demo_cols:
                if col in rebin_map:
                    new_col = rebin_map[col]
                    if new_col not in rebinned_data:
                        rebinned_data[new_col] = df_reserves[col]
                    else:
                        rebinned_data[new_col] += df_reserves[col]
                else:
                    if col in df_reserves.columns:
                        rebinned_data[col] = df_reserves[col]
            
            df_reserves = pd.DataFrame(rebinned_data)
            reserves_demo_cols = [col for col in df_reserves.columns if col not in ['FIPS', 'Region']]
        
        # Calculate reserves proportions by region
        for region_id in REGION_MAP.keys():
            region_df = df_reserves[df_reserves['Region'] == region_id]
            
            if region_df.empty:
                continue
            
            totals = region_df[reserves_demo_cols].sum()
            
            # Handle special cases
            if 'special' in demographic_config:
                if demographic_config['special'] == 'unemployment':
                    if 'LF-CIV' in totals.index and 'LF-CIV-EMPL' in totals.index:
                        total_lf_civ = totals['LF-CIV']
                        total_employed = totals['LF-CIV-EMPL']
                        if total_lf_civ > 0:
                            unemployment = 1 - (total_employed / total_lf_civ)
                            reserves_props[region_id] = pd.Series({'Unemployment': unemployment})
                    continue
                elif demographic_config['special'] == 'poverty_rate':
                    if 'Poverty' in totals.index and 'PSD' in totals.index:
                        total_poverty = totals['Poverty']
                        total_psd = totals['PSD']
                        if total_psd > 0:
                            poverty_rate = total_poverty / total_psd
                            reserves_props[region_id] = pd.Series({'Poverty Rate': poverty_rate})
                    continue
            
            # Calculate proportions
            if 'exclude_from_total' in demographic_config:
                total_cols = [col for col in totals.index if col not in demographic_config['exclude_from_total']]
                population_total = totals[total_cols].sum()
                if population_total > 0:
                    reserves_props[region_id] = totals / population_total
            else:
                population_total = totals.sum()
                if population_total > 0:
                    reserves_props[region_id] = totals / population_total
    
    except Exception as e:
        print(f"    Warning: Could not load reserves data: {e}")
    
    # Now calculate by region
    for region_id in REGION_MAP.keys():
        region_df = df[df['Region'] == region_id]
        
        if region_df.empty:
            continue
        
        # Sum demographics across all counties in this region
        totals = region_df[demo_cols].sum()
        
        # Handle special cases
        if 'special' in demographic_config:
            if demographic_config['special'] == 'unemployment':
                if 'LF-CIV' in totals.index and 'LF-CIV-EMPL' in totals.index:
                    total_lf_civ = totals['LF-CIV']
                    total_employed = totals['LF-CIV-EMPL']
                    if total_lf_civ > 0:
                        unemployment = 1 - (total_employed / total_lf_civ)
                        results[region_id] = pd.Series({'Unemployment': unemployment})
                continue
            
            elif demographic_config['special'] == 'poverty_rate':
                if 'Poverty' in totals.index and 'PSD' in totals.index:
                    total_poverty = totals['Poverty']
                    total_psd = totals['PSD']
                    if total_psd > 0:
                        poverty_rate = total_poverty / total_psd
                        results[region_id] = pd.Series({'Poverty Rate': poverty_rate})
                continue
        
        # Calculate proportions
        if 'exclude_from_total' in demographic_config:
            # For race_ethnicity: exclude H from total
            total_cols = [col for col in totals.index if col not in demographic_config['exclude_from_total']]
            population_total = totals[total_cols].sum()
            if population_total > 0:
                proportions = totals / population_total
                results[region_id] = proportions
        else:
            # Standard: sum all columns for total
            population_total = totals.sum()
            if population_total > 0:
                proportions = totals / population_total
                results[region_id] = proportions
    
    return results, reserves_props

def process_demographic(demo_name, demo_config):
    """Process one demographic across all regions
    
    Args:
        demo_name: Name of the demographic
        demo_config: Configuration dictionary for the demographic
    """
    print(f"\nProcessing {demo_name}...")
    
    results = {
        'exposed': {},  # {region_id: {column: [(year, proportion)]}}
        'baseline': {},  # {region_id: {column: [(year, proportion)]}}
        'reserves': {}  # {region_id: {column: [(year, proportion)]}}
    }
    
    # Initialize result structure
    for region_id in REGION_MAP.keys():
        results['exposed'][region_id] = {}
        results['baseline'][region_id] = {}
        results['reserves'][region_id] = {}
    
    # Load exposed data
    file_path = os.path.join(DEMO_BASE, demo_name, f'mines_{demo_name}_counties.xlsx')
    
    try:
        xls = pd.ExcelFile(file_path)
        
        # Get reference columns from the last sheet
        last_sheet = xls.sheet_names[-1]
        df_last = pd.read_excel(file_path, sheet_name=last_sheet)
        
        # Use ORIGINAL columns as reference (before rebinning) so we can fill missing in each sheet
        reference_columns = [col for col in df_last.columns 
                          if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
        
        for sheet_name in xls.sheet_names:
            year = parse_year(sheet_name)
            if year is None:
                continue
            
            # Exclude 2013 for race_ethnicity
            if demo_name == 'race_ethnicity' and year == 2013:
                continue
            
            # Read exposed data
            df_exposed = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Fill missing columns with 0 (before rebinning)
            for col in reference_columns:
                if col not in df_exposed.columns:
                    df_exposed[col] = 0
            
            # Get demographic column names from exposed data
            exposed_demo_cols = [col for col in df_exposed.columns 
                                 if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
            expected_baseline_cols = exposed_demo_cols.copy()
            
            # Handle age rebinning
            if demo_config.get('rebin', False):
                df_exposed = rebin_age_df(df_exposed, demo_config['rebin_map'])
                # Don't update expected_baseline_cols - keep original column names for baseline matching
            
            # Calculate exposed proportions by region
            exposed_props = calculate_exposed_proportions_by_region(df_exposed, demo_config)
            
            for region_id, proportions in exposed_props.items():
                for col in proportions.index:
                    if col not in results['exposed'][region_id]:
                        results['exposed'][region_id][col] = []
                    results['exposed'][region_id][col].append((year, proportions[col]))
            
            # Calculate baseline and reserves proportions by region
            baseline_props, reserves_props = calculate_baseline_and_reserves_proportions_by_region(
                demo_config['baseline_file'], demo_config, sheet_name, expected_baseline_cols, demo_name
            )
            
            for region_id, proportions in baseline_props.items():
                for col in proportions.index:
                    if col not in results['baseline'][region_id]:
                        results['baseline'][region_id][col] = []
                    results['baseline'][region_id][col].append((year, proportions[col]))
            
            # Store reserves proportions
            for region_id, proportions in reserves_props.items():
                for col in proportions.index:
                    if col not in results['reserves'][region_id]:
                        results['reserves'][region_id][col] = []
                    results['reserves'][region_id][col].append((year, proportions[col]))
        
    except FileNotFoundError:
        print(f"  Warning: File not found - {file_path}")
        return results
    except Exception as e:
        print(f"  Error processing {demo_name}: {e}")
        import traceback
        traceback.print_exc()
        return results
    
    return results

def create_figure(column_name, data, demo_name):
    """Create a figure for one demographic column comparing regions
    
    Args:
        column_name: Name of the demographic column
        data: Results dictionary with exposed, baseline, and reserves data
        demo_name: Name of the demographic
    """
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Define colors for each region
    colors = {
        1: '#1f77b4',  # Midwest - blue
        2: '#ff7f0e',  # Northeast - orange
        3: '#2ca02c',  # Southeast - green
        4: '#d62728',  # Southwest - red
        5: '#9467bd'   # West - purple
    }
    
    has_data = False
    
    # Plot exposed lines (solid)
    for region_id, region_name in REGION_MAP.items():
        if column_name in data['exposed'][region_id] and data['exposed'][region_id][column_name]:
            points = sorted(data['exposed'][region_id][column_name])
            years, values = zip(*points)
            ax.plot(years, values, marker='o', linestyle='-', linewidth=2, 
                   color=colors[region_id], label=f'{region_name} (Mines)', 
                   markersize=5, alpha=0.9)
            has_data = True
    
    # Plot baseline lines (dotted)
    for region_id, region_name in REGION_MAP.items():
        if column_name in data['baseline'][region_id] and data['baseline'][region_id][column_name]:
            points = sorted(data['baseline'][region_id][column_name])
            years, values = zip(*points)
            ax.plot(years, values, marker='s', linestyle=':', linewidth=1.5, 
                   color=colors[region_id], label=f'{region_name} (Regional)', 
                   markersize=4, alpha=0.7)
            has_data = True
    
    # Plot reserves lines (dashed)
    for region_id, region_name in REGION_MAP.items():
        if column_name in data['reserves'][region_id] and data['reserves'][region_id][column_name]:
            points = sorted(data['reserves'][region_id][column_name])
            years, values = zip(*points)
            ax.plot(years, values, marker='^', linestyle='--', linewidth=1.5, 
                   color=colors[region_id], label=f'{region_name} (Reserves)', 
                   markersize=4, alpha=0.6)
            has_data = True
    
    # Only save if there's actual data
    if not has_data:
        plt.close()
        return
    
    # Format plot
    ax.set_xlabel('Year', fontsize=12)
    
    # Set y-label based on demographic type
    if demo_name == 'employment' and column_name == 'Unemployment':
        ax.set_ylabel('Unemployment Rate', fontsize=12)
    elif demo_name == 'poverty' and column_name == 'Poverty Rate':
        ax.set_ylabel('Poverty Rate', fontsize=12)
    else:
        ax.set_ylabel('Proportion', fontsize=12)
    
    ax.legend(loc='best', fontsize=9, ncol=2)
    
    plt.tight_layout()
    
    # Save figure with new naming convention: mines_{demographic}_region
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    output_path = os.path.join(OUTPUT_BASE, f'mines_{safe_name}_region.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: mines_{safe_name}_region.png")

# Main processing loop
print("="*80)
print("Generating mines regional sensitivity figures...")
print("="*80)

for demo_name, demo_config in demographics.items():
    results = process_demographic(demo_name, demo_config)
    
    # Get columns ONLY from exposed data (not from baseline/national to avoid metadata columns)
    all_columns = set()
    for region_id in REGION_MAP.keys():
        all_columns.update(results['exposed'][region_id].keys())
    
    # Create a figure for each column
    for column in sorted(all_columns):
        create_figure(column, results, demo_name)

print("\n" + "="*80)
print("✓ All mines regional sensitivity figures generated successfully!")
print("="*80)
    



