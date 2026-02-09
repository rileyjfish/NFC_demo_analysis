"""
Analyze demographic proportions near proposed repositories across different regions and development stages.
Uses cumulative stage binning where Stage 1 = [1,2,3,4], Stage 2 = [2,3,4], Stage 3 = [3,4], Stage 4 = [4].
For each stage, compares exposed populations (within 50 miles of repositories at that stage or later)
against regional baseline populations and national average.
Uses only 1980 data for all comparisons.
Outputs directly to Repositories/ directory.
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
OUTPUT_BASE = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'regional', 'in_region', 'repositories')
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

# Define cumulative stage bins based on Note field
STAGE_BINS = {
    'Stage 0': [0, 1, 2, 3, 4],
    'Stage 1': [1, 2, 3, 4],
    'Stage 2': [2, 3, 4],
    'Stage 3': [3, 4],
    'Stage 4': [4]
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

def rebin_age_df(df, rebin_map):
    """Rebin age columns in dataframe"""
    # Get age columns (exclude FIPS, Region, Buffer_Fraction, Note, Approx Year)
    age_cols = [col for col in df.columns if col not in ['FIPS', 'Region', 'Buffer_Fraction', 'Note', 'Approx Year']]
    
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



def calculate_exposed_proportions_by_stage(df, demographic_config):
    """Calculate demographic proportions for exposed populations by region from stage-specific data
    
    The input df already contains only the counties/demographics for this specific stage.
    """
    demo_cols = [col for col in df.columns 
                 if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
    
    if not demo_cols:
        return {}
    
    results = {}
    
    for region_id in REGION_MAP.keys():
        region_df = df[df['Region'] == region_id].copy()
        
        if region_df.empty:
            continue
        
        # Use Buffer_Fraction > 0 to identify exposed counties
        exposed_df = region_df[region_df['Buffer_Fraction'] > 0].copy()
        
        if exposed_df.empty:
            continue
        
        # Sum demographics across exposed counties
        totals = exposed_df[demo_cols].sum()
        
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
    
    return results

def calculate_baseline_proportions_by_region(baseline_file, demographic_config, expected_columns):
    """Calculate demographic proportions for baseline population by region using 1980 data
    
    Args:
        baseline_file: Path to baseline demographic file (Excel)
        demographic_config: Configuration for this demographic
        expected_columns: List of demographic columns expected (from exposed data)
    """
    try:
        # Load Excel file using 1980 sheet
        df = pd.read_excel(baseline_file, sheet_name='1980')
        
    except Exception as e:
        print(f"    Warning: Could not load {baseline_file} for 1980: {e}")
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
    
    # Calculate national baseline (sum across all counties)
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

def process_demographic(demo_name, demo_config):
    """Process one demographic across all regions and stages
    
    Args:
        demo_name: Name of the demographic
        demo_config: Configuration dictionary for the demographic
    """
    print(f"\nProcessing {demo_name}...")
    
    results = {
        'exposed': {},  # {stage: {region_id: {column: proportion}}}
        'baseline': {},  # {region_id: {column: proportion}}
        'national': {}  # {column: proportion}
    }
    
    # Initialize exposed result structure for each stage
    for stage_name in STAGE_BINS.keys():
        results['exposed'][stage_name] = {}
    
    # Load exposed data (stage-based sheets)
    file_path = os.path.join(DEMO_BASE, demo_name, f'repository_{demo_name}_counties.xlsx')
    
    try:
        # Get reference columns from the last sheet (for column harmonization)
        xls = pd.ExcelFile(file_path)
        last_sheet = xls.sheet_names[-1]
        df_last = pd.read_excel(file_path, sheet_name=last_sheet)
        
        # Use ORIGINAL columns as reference (before rebinning) so we can fill missing in each sheet
        reference_columns = [col for col in df_last.columns 
                           if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
        
        # Get demographic column names for baseline matching
        expected_baseline_cols = reference_columns.copy()
        
        # Process each stage sheet
        for stage_name in STAGE_BINS.keys():
            sheet_name = f"{stage_name} - 1980"
            
            if sheet_name not in xls.sheet_names:
                print(f"  Warning: Sheet '{sheet_name}' not found")
                continue
            
            # Read stage sheet
            df_stage = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Fill missing columns with 0
            for col in reference_columns:
                if col not in df_stage.columns:
                    df_stage[col] = 0
            
            # Handle age rebinning
            if demo_config.get('rebin', False):
                df_stage = rebin_age_df(df_stage, demo_config['rebin_map'])
            
            # Calculate exposed proportions for this stage by region
            stage_props = calculate_exposed_proportions_by_stage(df_stage, demo_config)
            results['exposed'][stage_name] = stage_props
        
        # Calculate baseline proportions by region (using 1980 data)
        baseline_props, national_props = calculate_baseline_proportions_by_region(
            demo_config['baseline_file'], demo_config, expected_baseline_cols
        )
        
        results['baseline'] = baseline_props
        results['national'] = national_props if national_props is not None else {}
        
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
    """Create a bar plot for one demographic column comparing regions across stages
    
    X-axis: Development stages (Stage 1 through Stage 4)
    Bars: Regional exposed populations grouped by stage
    Horizontal lines: Regional baseline and national average
    
    Args:
        column_name: Name of the demographic column
        data: Results dictionary with exposed, baseline, and national data
        demo_name: Name of the demographic
    """
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Define colors for each region
    colors = {
        1: '#1f77b4',  # Midwest - blue
        2: '#ff7f0e',  # Northeast - orange
        3: '#2ca02c',  # Southeast - green
        4: '#d62728',  # Southwest - red
        5: '#9467bd'   # West - purple
    }
    
    has_data = False
    
    # Prepare stage labels and regional baseline for x-axis
    stage_names = [name.replace('Stage 0', 'All - Unstaged') for name in STAGE_BINS.keys()] + ['Regional (1980)']
    num_groups = len(stage_names)
    num_regions = len(REGION_MAP)
    bar_width = 0.15
    x = np.arange(num_groups)
    
    # Plot bars for each region (exposed values for stages + regional baseline)
    for i, (region_id, region_name) in enumerate(REGION_MAP.items()):
        all_values = []
        
        # Add exposed values for each stage
        for stage_name in STAGE_BINS.keys():
            if region_id in data['exposed'].get(stage_name, {}) and column_name in data['exposed'][stage_name][region_id]:
                all_values.append(data['exposed'][stage_name][region_id][column_name])
            else:
                all_values.append(0)
        
        # Add regional baseline value
        if region_id in data['baseline'] and column_name in data['baseline'][region_id]:
            all_values.append(data['baseline'][region_id][column_name])
        else:
            all_values.append(0)
        
        # Only plot if there's at least some data
        if any(v > 0 for v in all_values):
            offset = (i - num_regions/2 + 0.5) * bar_width
            bars = ax.bar(x + offset, all_values, width=bar_width, label=f'{region_name}', 
                         color=colors[region_id], alpha=0.9)
            
            # Add data labels on top of bars
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:.3f}', ha='center', va='bottom', fontsize=7)
            has_data = True
    
    # Plot national average horizontal line
    if column_name in data['national']:
        national_value = data['national'][column_name]
        ax.axhline(y=national_value, linestyle='--', linewidth=2.5, 
                  color='black', label='National (1980)', alpha=0.8)
        has_data = True
    
    # Only save if there's actual data
    if not has_data:
        plt.close()
        return
    
    # Format plot
    ax.set_xticks(x)
    ax.set_xticklabels(stage_names, fontsize=10)
    ax.set_xlabel('Development Stage / Regional Baseline', fontsize=12)
    
    # Set y-label based on demographic type
    if demo_name == 'employment' and column_name == 'Unemployment':
        ax.set_ylabel('Unemployment Rate', fontsize=12)
    elif demo_name == 'poverty' and column_name == 'Poverty Rate':
        ax.set_ylabel('Poverty Rate', fontsize=12)
    else:
        ax.set_ylabel('Proportion', fontsize=12)
    
    ax.legend(loc='best', fontsize=8, ncol=1)
    
    plt.tight_layout()
    
    # Save figure with new naming convention: repositories_{demographic}_region
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    output_path = os.path.join(OUTPUT_BASE, f'repositories_{safe_name}_region.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: repositories_{safe_name}_region.png")

# Main processing loop
print("="*80)
print("Generating repository regional sensitivity figures by development stage...")
print("Using 1980 demographic data for all comparisons")
print("="*80)

for demo_name, demo_config in demographics.items():
    results = process_demographic(demo_name, demo_config)
    
    # Get columns from exposed data (first stage that has data)
    all_columns = set()
    for stage_name in STAGE_BINS.keys():
        for region_id in REGION_MAP.keys():
            if region_id in results['exposed'].get(stage_name, {}):
                all_columns.update(results['exposed'][stage_name][region_id].keys())
    
    # Create a figure for each column
    for column in sorted(all_columns):
        create_figure(column, results, demo_name)

print("\n" + "="*80)
print("✓ All repository regional sensitivity figures generated successfully!")
print("="*80)




