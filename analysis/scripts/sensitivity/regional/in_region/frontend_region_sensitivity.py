"""
Analyze demographic proportions near frontend facilities across different regions.
Generates figures comparing exposed populations vs. regional baseline populations.
Processes both standard inclusion (operating facilities) and residual inclusion (ever-operated facilities).
Outputs to respective Standard/ and Residual/ subdirectories.
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
OUTPUT_BASE = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'regional', 'in_region', 'frontend')
DEMO_BASE = os.path.join(BASE_DIR, 'outputs', 'demographics_by_county')
COMPILED_BASE = os.path.join(BASE_DIR, '../demographic_data', 'compiled')

# Create output directories
os.makedirs(os.path.join(OUTPUT_BASE, 'Standard'), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_BASE, 'Residual'), exist_ok=True)

# Define regions
REGION_MAP = {
    1: 'Midwest',
    2: 'Northeast',
    3: 'Southeast',
    4: 'Southwest',
    5: 'West'
}

# Define demographics and their special handling (matching distance sensitivity)
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

def rebin_age_columns(cols, rebin_map):
    """Create mapping from old column names to new column names"""
    col_mapping = {}
    for col in cols:
        base_col = col.replace('_S', '').replace('_R', '')
        if base_col in rebin_map:
            new_base = rebin_map[base_col]
            if col.endswith('_S'):
                col_mapping[col] = new_base + '_S'
            elif col.endswith('_R'):
                col_mapping[col] = new_base + '_R'
            else:
                col_mapping[col] = new_base
        else:
            col_mapping[col] = col
    return col_mapping

def rebin_age_df(df, rebin_map, suffix='_S'):
    """Rebin age columns in dataframe"""
    # Get columns with the specified suffix
    age_cols = [col for col in df.columns if col.endswith(suffix) and col not in ['Buffer_Fraction_S', 'Buffer_Fraction_R']]
    
    if not age_cols:
        return df
    
    # Create rebinned dataframe
    rebinned_cols = {}
    for col in age_cols:
        base_col = col.replace(suffix, '')
        if base_col in rebin_map:
            new_col = rebin_map[base_col] + suffix
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

def calculate_exposed_proportions_by_region(df, demographic_config, suffix='_S'):
    """Calculate demographic proportions for exposed populations by region"""
    demo_name = demographic_config['file']
    
    # Get demographic columns (exclude FIPS, Region, Buffer_Fraction)
    demo_cols = [col for col in df.columns 
                 if col.endswith(suffix) and col not in ['Buffer_Fraction_S', 'Buffer_Fraction_R']]
    
    if not demo_cols:
        return {}
    
    results = {}
    
    for region_id in REGION_MAP.keys():
        region_df = df[df['Region'] == region_id]
        
        if region_df.empty:
            continue
        
        # Sum demographics across all counties in this region
        totals = region_df[demo_cols].sum()
        
        # Remove suffix for processing
        totals.index = totals.index.str.replace(suffix, '')
        
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

def calculate_baseline_proportions_by_region(baseline_file, demographic_config, sheet_name, expected_columns):
    """Calculate demographic proportions for baseline population by region
    
    Args:
        baseline_file: Path to baseline demographic file (Excel or NetCDF)
        demographic_config: Configuration for this demographic
        sheet_name: Sheet name to load (matching the frontend data sheets)
        expected_columns: List of demographic columns expected (from exposed data)
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
            # Load Excel file using the same sheet name as frontend data
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
    
    # Calculate national baseline (sum across all counties, not filtering by region)
    national_totals = df[demo_cols].sum()
    
    # Handle special cases for national
    national_proportion = None
    if 'special' in demographic_config:
        if demographic_config['special'] == 'unemployment':
            if 'LF-CIV' in national_totals.index and 'LF-CIV-EMPL' in national_totals.index:
                total_lf_civ = national_totals['LF-CIV']
                total_employed = national_totals['LF-CIV-EMPL']
                if total_lf_civ > 0:
                    unemployment = 1 - (total_employed / total_lf_civ)
                    national_proportion = pd.Series({'Unemployment': unemployment})
        
        elif demographic_config['special'] == 'poverty_rate':
            if 'Poverty' in national_totals.index and 'PSD' in national_totals.index:
                total_poverty = national_totals['Poverty']
                total_psd = national_totals['PSD']
                if total_psd > 0:
                    poverty_rate = total_poverty / total_psd
                    national_proportion = pd.Series({'Poverty Rate': poverty_rate})
    
    # Calculate national proportions if not special case
    if national_proportion is None:
        if 'exclude_from_total' in demographic_config:
            # For race_ethnicity: exclude H from total
            total_cols = [col for col in national_totals.index if col not in demographic_config['exclude_from_total']]
            population_total = national_totals[total_cols].sum()
            if population_total > 0:
                national_proportion = national_totals / population_total
        else:
            # Standard: sum all columns for total
            population_total = national_totals.sum()
            if population_total > 0:
                national_proportion = national_totals / population_total
    
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
    
    return results, national_proportion

def process_demographic(demo_name, demo_config, inclusion_type='standard'):
    """Process one demographic across all regions for specified inclusion type
    
    Args:
        demo_name: Name of the demographic
        demo_config: Configuration dictionary for the demographic
        inclusion_type: Either 'standard' (_S columns) or 'residual' (_R columns)
    """
    suffix = '_S' if inclusion_type == 'standard' else '_R'
    print(f"\nProcessing {demo_name} ({inclusion_type.upper()})...")
    
    results = {
        'exposed': {},  # {region_id: {column: [(year, proportion)]}}
        'baseline': {},  # {region_id: {column: [(year, proportion)]}}
        'national': {}  # {column: [(year, proportion)]}
    }
    
    # Initialize result structure
    for region_id in REGION_MAP.keys():
        results['exposed'][region_id] = {}
        results['baseline'][region_id] = {}
    
    # Load exposed data
    file_path = os.path.join(DEMO_BASE, demo_name, f'frontend_{demo_name}_counties.xlsx')
    
    try:
        xls = pd.ExcelFile(file_path)
        
        # Get reference columns from the last sheet
        last_sheet = xls.sheet_names[-1]
        df_last = pd.read_excel(file_path, sheet_name=last_sheet)
        
        # Get valid columns with the correct suffix (exclude Buffer_Fraction)
        # Use ORIGINAL columns as reference (before rebinning) so we can fill missing in each sheet
        reference_columns = [col for col in df_last.columns 
                          if col.endswith(suffix) and col not in ['Buffer_Fraction_S', 'Buffer_Fraction_R']]
        
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
            
            # Get demographic column names from exposed data (remove suffix for baseline matching)
            exposed_demo_cols_raw = [col for col in df_exposed.columns 
                                      if col.endswith(suffix) and col not in ['Buffer_Fraction_S', 'Buffer_Fraction_R']]
            expected_baseline_cols = [col.replace(suffix, '') for col in exposed_demo_cols_raw]
            
            # Handle age rebinning
            if demo_config.get('rebin', False):
                df_exposed = rebin_age_df(df_exposed, demo_config['rebin_map'], suffix=suffix)
                # Don't update expected_baseline_cols - keep original column names for baseline matching
            
            # Calculate exposed proportions by region
            exposed_props = calculate_exposed_proportions_by_region(df_exposed, demo_config, suffix=suffix)
            
            for region_id, proportions in exposed_props.items():
                for col in proportions.index:
                    if col not in results['exposed'][region_id]:
                        results['exposed'][region_id][col] = []
                    results['exposed'][region_id][col].append((year, proportions[col]))
            
            # Calculate baseline proportions by region (only for columns present in exposed data)
            baseline_props, national_props = calculate_baseline_proportions_by_region(
                demo_config['baseline_file'], demo_config, sheet_name, expected_baseline_cols
            )
            
            for region_id, proportions in baseline_props.items():
                for col in proportions.index:
                    if col not in results['baseline'][region_id]:
                        results['baseline'][region_id][col] = []
                    results['baseline'][region_id][col].append((year, proportions[col]))
            
            # Store national proportions
            if national_props is not None:
                for col in national_props.index:
                    if col not in results['national']:
                        results['national'][col] = []
                    results['national'][col].append((year, national_props[col]))
        
    except FileNotFoundError:
        print(f"  Warning: File not found - {file_path}")
        return results
    except Exception as e:
        print(f"  Error processing {demo_name}: {e}")
        import traceback
        traceback.print_exc()
        return results
    
    return results

def create_figure(column_name, data, demo_name, inclusion_type='standard'):
    """Create a figure for one demographic column comparing regions
    
    Args:
        column_name: Name of the demographic column
        data: Results dictionary with exposed, baseline, and national data
        demo_name: Name of the demographic
        inclusion_type: Either 'standard' or 'residual'
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
                   color=colors[region_id], label=f'{region_name} (Frontend)', 
                   markersize=5, alpha=0.9)
            has_data = True
    
    # Plot baseline lines (dashed)
    for region_id, region_name in REGION_MAP.items():
        if column_name in data['baseline'][region_id] and data['baseline'][region_id][column_name]:
            points = sorted(data['baseline'][region_id][column_name])
            years, values = zip(*points)
            ax.plot(years, values, marker='s', linestyle='--', linewidth=1.5, 
                   color=colors[region_id], label=f'{region_name} (Regional)', 
                   markersize=4, alpha=0.7)
            has_data = True
    
    # Plot national average (thick black dashed line)
    if column_name in data['national'] and data['national'][column_name]:
        points = sorted(data['national'][column_name])
        years, values = zip(*points)
        ax.plot(years, values, marker='D', linestyle='--', linewidth=2.5, 
               color='black', label='National Average', 
               markersize=5, alpha=0.8)
        has_data = True
    
    # Only save if there's actual data
    if not has_data:
        plt.close()
        return
    
    # Format plot
    inclusion_label = 'standard' if inclusion_type == 'standard' else 'residual'
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
    
    # Save figure with new naming convention: frontend_{subtype}_{demographic}_region
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    output_subdir = 'Standard' if inclusion_type == 'standard' else 'Residual'
    output_path = os.path.join(OUTPUT_BASE, output_subdir, f'frontend_{inclusion_label}_{safe_name}_region.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {output_subdir}/frontend_{inclusion_label}_{safe_name}_region.png")

# Main processing loop
print("="*80)
print("Generating frontend regional sensitivity figures...")
print("="*80)

# Process each demographic with both standard and residual
for demo_name, demo_config in demographics.items():
    print(f"\n{'='*80}")
    print(f"Processing demographic: {demo_name.upper()}")
    print('='*80)
    
    for inclusion_type in ['standard', 'residual']:
        print(f"  Processing {inclusion_type} inclusion...")
        results = process_demographic(demo_name, demo_config, inclusion_type=inclusion_type)
        
        # Get columns ONLY from exposed data (not from baseline/national to avoid metadata columns)
        all_columns = set()
        for region_id in REGION_MAP.keys():
            all_columns.update(results['exposed'][region_id].keys())
        
        # Create a figure for each column
        for column in sorted(all_columns):
            create_figure(column, results, demo_name, inclusion_type=inclusion_type)

print("\n" + "="*80)
print("✓ All frontend regional sensitivity figures generated successfully!")
print("="*80)




