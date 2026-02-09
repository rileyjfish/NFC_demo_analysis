"""
Analyze demographic proportions near proposed interim storage sites across different regions.
Three facility types with different stage structures:
- Private: Note = 0 (no stages, individual sites)
- ONWN: Note = 1, 2, 3 with cumulative stages [1,2,3], [2,3], [3]
- DOE: Note = 4, 5, 6 with cumulative stages [4,5,6], [5,6], [6]

For each facility type and stage/site, compares exposed populations against regional baseline 
populations and national average across all years.
Outputs to interim_storage/ directory with subdirectories for each facility type.
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
OUTPUT_BASE = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'regional', 'in_region', 'interim_storage')
DEMO_BASE = os.path.join(BASE_DIR, 'outputs', 'demographics_by_county')
COMPILED_BASE = os.path.join(BASE_DIR, '..', 'demographic_data', 'compiled')

# Create output directories
os.makedirs(os.path.join(OUTPUT_BASE, 'Private'), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_BASE, 'ONWN'), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_BASE, 'DOE'), exist_ok=True)

# Define regions
REGION_MAP = {
    1: 'Midwest',
    2: 'Northeast',
    3: 'Southeast',
    4: 'Southwest',
    5: 'West'
}

# Define facility type bins based on Note field (matching generator structure)
FACILITY_BINS = {
    'Private': {
        'notes': [0],
        'stages': {'Stage 0': [0]}  # Stage 0 is standalone for Private
    },
    'ONWN': {
        'notes': [1, 2, 3],
        'stages': {
            'Stage 1': [1, 2, 3],
            'Stage 2': [2, 3],
            'Stage 3': [3]
        }
    },
    'DOE': {
        'notes': [4, 5, 6],
        'stages': {
            'Stage 4': [4, 5, 6],
            'Stage 5': [5, 6],
            'Stage 6': [6]
        }
    }
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
    age_cols = [col for col in df.columns 
                if col not in ['FIPS', 'Region', 'Buffer_Fraction', 'Name', 'Note', 'Approx Year']]
    
    if not age_cols:
        return df
    
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
    
    # Preserve Buffer_Fraction and other metadata columns if they exist
    meta_cols_to_keep = ['FIPS', 'Region']
    if 'Buffer_Fraction' in df.columns:
        meta_cols_to_keep.append('Buffer_Fraction')
    
    result_df = df[meta_cols_to_keep].copy()
    for col_name, col_data in rebinned_cols.items():
        result_df[col_name] = col_data
    
    return result_df

def calculate_exposed_proportions_by_region(df, demographic_config, facility_type):
    """Calculate demographic proportions for exposed populations by region
    
    Since data is already filtered by stage in the sheet, just calculate proportions by region.
    """
    demo_cols = [col for col in df.columns 
                 if col not in ['FIPS', 'Region', 'Buffer_Fraction', 'Name', 'Note', 'Approx Year']]
    
    if not demo_cols:
        return {}
    
    results = {}
    
    # Calculate proportions for each region (data is already stage-filtered in the sheet)
    for region_id in REGION_MAP.keys():
        region_df = df[df['Region'] == region_id]
        
        if region_df.empty:
            continue
        
        # Use Buffer_Fraction > 0 to identify exposed counties
        exposed_df = region_df[region_df['Buffer_Fraction'] > 0].copy()
        
        if exposed_df.empty:
            continue
        
        # Sum demographics across all exposed counties in this region
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
            total_cols = [col for col in totals.index if col not in demographic_config['exclude_from_total']]
            population_total = totals[total_cols].sum()
            if population_total > 0:
                proportions = totals / population_total
                results[region_id] = proportions
        else:
            population_total = totals.sum()
            if population_total > 0:
                proportions = totals / population_total
                results[region_id] = proportions
    
    return results

def calculate_baseline_proportions_by_region(baseline_file, demographic_config, sheet_name, expected_columns):
    """Calculate demographic proportions for baseline population by region"""
    try:
        # Load Excel file
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
    
    if 'special' in demographic_config:
        if demographic_config['special'] == 'unemployment':
            if 'LF-CIV' in national_totals.index and 'LF-CIV-EMPL' in national_totals.index:
                total_lf_civ = national_totals['LF-CIV']
                total_employed = national_totals['LF-CIV-EMPL']
                if total_lf_civ > 0:
                    unemployment = 1 - (total_employed / total_lf_civ)
                    national_props = pd.Series({'Unemployment': unemployment})
                else:
                    national_props = None
            else:
                national_props = None
        elif demographic_config['special'] == 'poverty_rate':
            if 'Poverty' in national_totals.index and 'PSD' in national_totals.index:
                total_poverty = national_totals['Poverty']
                total_psd = national_totals['PSD']
                if total_psd > 0:
                    poverty_rate = total_poverty / total_psd
                    national_props = pd.Series({'Poverty Rate': poverty_rate})
                else:
                    national_props = None
            else:
                national_props = None
    else:
        if 'exclude_from_total' in demographic_config:
            total_cols = [col for col in national_totals.index if col not in demographic_config['exclude_from_total']]
            population_total = national_totals[total_cols].sum()
            national_props = national_totals / population_total if population_total > 0 else None
        else:
            population_total = national_totals.sum()
            national_props = national_totals / population_total if population_total > 0 else None
    
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
            total_cols = [col for col in totals.index if col not in demographic_config['exclude_from_total']]
            population_total = totals[total_cols].sum()
            if population_total > 0:
                proportions = totals / population_total
                results[region_id] = proportions
        else:
            population_total = totals.sum()
            if population_total > 0:
                proportions = totals / population_total
                results[region_id] = proportions
    
    return results, national_props

def process_demographic(demo_name, demo_config, facility_type):
    """Process one demographic for a specific facility type across all years"""
    
    results = {
        'exposed': {},  # {stage/site: {region_id: {column: [(year, proportion)]}}}
        'baseline': {},  # {region_id: {column: [(year, proportion)]}}
        'national': {}  # {column: [(year, proportion)]}
    }
    
    facility_config = FACILITY_BINS[facility_type]
    
    # Initialize result structure with stage names
    for stage_name in facility_config['stages'].keys():
        results['exposed'][stage_name] = {region_id: {} for region_id in REGION_MAP.keys()}
    
    for region_id in REGION_MAP.keys():
        results['baseline'][region_id] = {}
    
    # Load exposed data (stage-based sheets from 1990)
    file_path = os.path.join(DEMO_BASE, demo_name, f'interim_prop_{demo_name}_counties.xlsx')
    
    try:
        xls = pd.ExcelFile(file_path)
        
        # Get reference columns from the last sheet
        last_sheet = xls.sheet_names[-1]
        df_last = pd.read_excel(file_path, sheet_name=last_sheet)
        
        # Use ORIGINAL columns as reference (before rebinning)
        reference_columns = [col for col in df_last.columns 
                          if col not in ['FIPS', 'Region', 'Buffer_Fraction', 'Name', 'Note', 'Approx Year']]
        
        # Get baseline columns for matching
        expected_baseline_cols = reference_columns.copy()
        
        # Process each stage for this facility type
        for stage_name in facility_config['stages'].keys():
            # Extract stage number from stage name (e.g., "Stage 1" -> 1)
            stage_num = int(stage_name.split()[1])
            sheet_name = f"Stage {stage_num} - 1990"
            
            if sheet_name not in xls.sheet_names:
                print(f"  Warning: Sheet '{sheet_name}' not found for {facility_type}")
                continue
            
            print(f"    Processing {stage_name} from sheet: {sheet_name}")
            
            # Read exposed data
            df_exposed = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Fill missing columns with 0 (before rebinning)
            for col in reference_columns:
                if col not in df_exposed.columns:
                    df_exposed[col] = 0
            
            # Get demographic column names from exposed data
            exposed_demo_cols = [col for col in df_exposed.columns 
                                 if col not in ['FIPS', 'Region', 'Buffer_Fraction', 'Name', 'Note', 'Approx Year']]
            expected_baseline_cols = exposed_demo_cols.copy()
            
            # Handle age rebinning
            if demo_config.get('rebin', False):
                df_exposed = rebin_age_df(df_exposed, demo_config['rebin_map'])
            
            # Calculate exposed proportions by region for this stage
            exposed_props = calculate_exposed_proportions_by_region(df_exposed, demo_config, facility_type)
            
            # Store results for this stage
            for region_id, proportions in exposed_props.items():
                for col in proportions.index:
                    if col not in results['exposed'][stage_name][region_id]:
                        results['exposed'][stage_name][region_id][col] = []
                    # Single data point at 1990 for this stage
                    results['exposed'][stage_name][region_id][col].append((1990, proportions[col]))
        
        # Calculate baseline proportions by region (using 1990 data once)
        baseline_props, national_props = calculate_baseline_proportions_by_region(
            demo_config['baseline_file'], demo_config, '1990', expected_baseline_cols
        )
        
        for region_id, proportions in baseline_props.items():
            for col in proportions.index:
                if col not in results['baseline'][region_id]:
                    results['baseline'][region_id][col] = []
                results['baseline'][region_id][col].append((1990, proportions[col]))
        
        # Store national proportions
        if national_props is not None:
            for col in national_props.index:
                if col not in results['national']:
                    results['national'][col] = []
                results['national'][col].append((1990, national_props[col]))
        
    except FileNotFoundError:
        print(f"  Warning: File not found - {file_path}")
        return results
    except Exception as e:
        print(f"  Error processing {demo_name}: {e}")
        import traceback
        traceback.print_exc()
        return results
    
    return results

def create_figure(column_name, data, demo_name, facility_type, stages_list):
    """Create a bar plot for one demographic column comparing regions across stages
    
    X-axis: Development stages + Regional baseline
    Bars: Regional values grouped by stage
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
    stage_names = []
    for name in stages_list:
        if facility_type == 'Private':
            stage_names.append(name.replace('Stage 0', 'Private'))
        elif facility_type == 'DOE':
            stage_names.append(name.replace('Stage 4', 'Stage 1').replace('Stage 5', 'Stage 2').replace('Stage 6', 'Stage 3'))
        else:
            stage_names.append(name.replace('Stage 0', 'All - Unstaged'))
    stage_names.append('Regional (1990)')
    num_groups = len(stage_names)
    num_regions = len(REGION_MAP)
    bar_width = 0.15
    x = np.arange(num_groups)
    
    # Plot bars for each region (exposed values for stages + regional baseline)
    for i, (region_id, region_name) in enumerate(REGION_MAP.items()):
        all_values = []
        
        # Add exposed values for each stage (extract from [(year, value)] structure)
        for stage_name in stages_list:
            if (region_id in data['exposed'].get(stage_name, {}) and 
                column_name in data['exposed'][stage_name][region_id] and
                data['exposed'][stage_name][region_id][column_name]):
                # Get the value from (year, value) tuple
                value = data['exposed'][stage_name][region_id][column_name][0][1]
                all_values.append(value)
            else:
                all_values.append(0)
        
        # Add regional baseline value
        if (region_id in data['baseline'] and 
            column_name in data['baseline'][region_id] and
            data['baseline'][region_id][column_name]):
            # Get the value from (year, value) tuple
            value = data['baseline'][region_id][column_name][0][1]
            all_values.append(value)
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
    
    # Plot national average horizontal line (dotted)
    if column_name in data['national'] and data['national'][column_name]:
        # Get the value from (year, value) tuple
        national_value = data['national'][column_name][0][1]
        ax.axhline(y=national_value, linestyle=':', linewidth=2.5, 
                  color='black', label='National (1990)', alpha=0.8)
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
    
    # Save figure with new naming convention: interim_{subtype}_{demographic}_region
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    output_path = os.path.join(OUTPUT_BASE, facility_type, f'interim_{facility_type}_{safe_name}_region.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"    Saved: {facility_type}/interim_{facility_type}_{safe_name}_region.png")

# Main processing loop
print("="*80)
print("Generating interim storage regional sensitivity figures...")
print("="*80)

# Process each demographic with all facility types
for demo_name, demo_config in demographics.items():
    print(f"\n{'='*80}")
    print(f"Processing demographic: {demo_name.upper()}")
    print('='*80)
    
    for facility_type in FACILITY_BINS.keys():
        print(f"  Processing {facility_type}...")
        results = process_demographic(demo_name, demo_config, facility_type)
        
        # Get all stages/sites for this facility type
        stages_or_sites = list(results['exposed'].keys())
        
        if not stages_or_sites:
            print(f"    No data for {facility_type}")
            continue
        
        # Get all unique columns from exposed data
        all_columns = set()
        for stage_or_site in stages_or_sites:
            for region_id in REGION_MAP.keys():
                if region_id in results['exposed'][stage_or_site]:
                    all_columns.update(results['exposed'][stage_or_site][region_id].keys())
        
        # Create one figure per column showing all stages
        for column in sorted(all_columns):
            create_figure(column, results, demo_name, facility_type, stages_or_sites)

print("\n" + "="*80)
print("✓ All interim storage regional sensitivity figures generated successfully!")
print("="*80)
