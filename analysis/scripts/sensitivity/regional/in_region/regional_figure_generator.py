"""
Consolidated regional sensitivity figure generator.
Generates all regional sensitivity figures for:
- Frontend facilities (standard & residual inclusion)
- Reactors (standard & residual inclusion)
- Mines (no temporal filtering)
- Interim storage (by facility type and stage)
- Repositories (by development stage)

Compares exposed populations against regional baseline populations and national averages.
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
    'O': 'Other Race',
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
DEMO_BASE = os.path.join(BASE_DIR, 'outputs', 'demographics_by_county')
COMPILED_BASE = os.path.join(BASE_DIR, '..', 'demographic_data', 'compiled')
REGIONAL_BASE = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'regional', 'in_region')

# Define regions
REGION_MAP = {
    1: 'Midwest',
    2: 'Northeast',
    3: 'Southeast',
    4: 'Southwest',
    5: 'West'
}

# Define demographics and their special handling
DEMOGRAPHICS = {
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

# Interim facility bins (matching distance generator)
INTERIM_FACILITY_BINS = {
    'Private': {
        'notes': [0],
        'stages': {'Stage 0': [0]}
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
            'Stage 1': [4, 5, 6],
            'Stage 2': [5, 6],
            'Stage 3': [6]
        }
    }
}

# Repository stage bins
REPO_STAGE_BINS = {
    'Stage 0': [0],  # Non-cumulative: all candidate sites, labeled as 'Unstaged'
    'Stage 1': [1, 2, 3, 4],
    'Stage 2': [2, 3, 4],
    'Stage 3': [3, 4],
    'Stage 4': [4]
}

# =============================================================================
# COMMON UTILITY FUNCTIONS
# =============================================================================

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

def rebin_age_df(df, rebin_map, suffix='_S'):
    """Rebin age columns in dataframe"""
    age_cols = [col for col in df.columns if col.endswith(suffix) and col not in ['Buffer_Fraction_S', 'Buffer_Fraction_R']]
    
    if not age_cols:
        return df
    
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
    
    result_df = df[['FIPS', 'Region']].copy()
    for col_name, col_data in rebinned_cols.items():
        result_df[col_name] = col_data
    
    return result_df

def rebin_age_baseline(df, rebin_map):
    """Rebin age columns in baseline NetCDF data"""
    rebinned = {}
    for old_col, new_col in rebin_map.items():
        if old_col in df.columns:
            if new_col not in rebinned:
                rebinned[new_col] = df[old_col]
            else:
                rebinned[new_col] += df[old_col]
    return pd.DataFrame(rebinned, index=df.index)

def calculate_exposed_proportions_by_region(df, demographic_config, suffix='_S'):
    """Calculate demographic proportions for exposed populations by region"""
    demo_cols = [col for col in df.columns 
                 if col.endswith(suffix) and col not in ['Buffer_Fraction_S', 'Buffer_Fraction_R']]
    
    if not demo_cols:
        return {}
    
    results = {}
    
    for region_id in REGION_MAP.keys():
        region_df = df[df['Region'] == region_id]
        
        if region_df.empty:
            continue
        
        totals = region_df[demo_cols].sum()
        totals.index = totals.index.str.replace(suffix, '')
        
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
        
        if 'exclude_from_total' in demographic_config:
            total_cols = [col for col in totals.index if col not in demographic_config['exclude_from_total']]
            population_total = totals[total_cols].sum()
        else:
            population_total = totals.sum()
        
        if population_total > 0:
            proportions = totals / population_total
            results[region_id] = proportions
    
    return results

def calculate_baseline_proportions_by_region(baseline_file, demographic_config, sheet_name, expected_columns):
    """Calculate baseline demographic proportions by region and nationally
    
    Matches interim_region_sensitivity.py and repository_region_sensitivity.py approach:
    1. Load baseline file (Excel for all demographics)
    2. Rebin if needed (age)
    3. Calculate proportions by region and nationally
    """
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
    
    return results, national_props

# =============================================================================
# FRONTEND FACILITIES
# =============================================================================

def process_frontend_demographic(demo_name, demo_config, inclusion_type='standard'):
    """Process one demographic for frontend facilities"""
    print(f"\n  Processing frontend {inclusion_type}: {demo_name}...")
    
    suffix = '_S' if inclusion_type == 'standard' else '_R'
    
    results = {
        'exposed': {region_id: {} for region_id in REGION_MAP.keys()},
        'baseline': {region_id: {} for region_id in REGION_MAP.keys()},
        'national': {}
    }
    
    file_path = os.path.join(DEMO_BASE, demo_name, f'frontend_{demo_name}_counties.xlsx')
    
    try:
        xls = pd.ExcelFile(file_path)
        last_sheet = xls.sheet_names[-1]
        df_last = pd.read_excel(file_path, sheet_name=last_sheet)
        
        reference_columns = [col for col in df_last.columns 
                          if col.endswith(suffix) and col not in ['Buffer_Fraction_S', 'Buffer_Fraction_R']]
        
        for sheet_name in xls.sheet_names:
            year = parse_year(sheet_name)
            if year is None:
                continue
            
            if demo_name == 'race_ethnicity' and year == 2013:
                continue
            
            df_exposed = pd.read_excel(file_path, sheet_name=sheet_name)
            
            for col in reference_columns:
                if col not in df_exposed.columns:
                    df_exposed[col] = 0
            
            exposed_demo_cols_raw = [col for col in df_exposed.columns 
                                      if col.endswith(suffix) and col not in ['Buffer_Fraction_S', 'Buffer_Fraction_R']]
            expected_baseline_cols = [col.replace(suffix, '') for col in exposed_demo_cols_raw]
            
            if demo_config.get('rebin', False):
                df_exposed = rebin_age_df(df_exposed, demo_config['rebin_map'], suffix=suffix)
            
            exposed_props = calculate_exposed_proportions_by_region(df_exposed, demo_config, suffix=suffix)
            
            for region_id, proportions in exposed_props.items():
                for col in proportions.index:
                    if col not in results['exposed'][region_id]:
                        results['exposed'][region_id][col] = []
                    results['exposed'][region_id][col].append((year, proportions[col]))
            
            baseline_props, national_props = calculate_baseline_proportions_by_region(
                demo_config['baseline_file'], demo_config, sheet_name, expected_baseline_cols
            )
            
            for region_id, proportions in baseline_props.items():
                for col in proportions.index:
                    if col not in results['baseline'][region_id]:
                        results['baseline'][region_id][col] = []
                    results['baseline'][region_id][col].append((year, proportions[col]))
            
            if national_props is not None:
                for col in national_props.index:
                    if col not in results['national']:
                        results['national'][col] = []
                    results['national'][col].append((year, national_props[col]))
        
    except FileNotFoundError:
        print(f"    Warning: File not found - {file_path}")
        return results
    except Exception as e:
        print(f"    Error processing {demo_name}: {e}")
        return results
    
    return results

def create_frontend_figure(column_name, data, demo_name, inclusion_type):
    """Create a figure for one demographic column and inclusion type"""
    output_base = os.path.join(REGIONAL_BASE, 'frontend')
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    colors = {
        1: '#1f77b4', 2: '#ff7f0e', 3: '#2ca02c',
        4: '#d62728', 5: '#9467bd'
    }
    
    has_data = False
    
    for region_id, region_name in REGION_MAP.items():
        if column_name in data['exposed'][region_id] and data['exposed'][region_id][column_name]:
            points = sorted(data['exposed'][region_id][column_name])
            years, values = zip(*points)
            ax.plot(years, values, marker='o', linestyle='-', linewidth=2, 
                   color=colors[region_id], label=f'{region_name} (Frontend)', 
                   markersize=5, alpha=0.9)
            has_data = True
    
    for region_id, region_name in REGION_MAP.items():
        if column_name in data['baseline'][region_id] and data['baseline'][region_id][column_name]:
            points = sorted(data['baseline'][region_id][column_name])
            years, values = zip(*points)
            ax.plot(years, values, marker='s', linestyle='--', linewidth=1.5, 
                   color=colors[region_id], label=f'{region_name} (Regional)', 
                   markersize=4, alpha=0.7)
            has_data = True
    
    if column_name in data['national'] and data['national'][column_name]:
        points = sorted(data['national'][column_name])
        years, values = zip(*points)
        ax.plot(years, values, marker='D', linestyle='--', linewidth=2.5, 
               color='black', label='National Average', 
               markersize=5, alpha=0.8)
        has_data = True
    
    if not has_data:
        plt.close()
        return
    
    inclusion_label = 'standard' if inclusion_type == 'standard' else 'residual'
    ax.set_xlabel('Year', fontsize=12)
    
    if demo_name == 'employment' and column_name == 'Unemployment':
        ax.set_ylabel('Unemployment Rate', fontsize=12)
    elif demo_name == 'poverty' and column_name == 'Poverty Rate':
        ax.set_ylabel('Poverty Rate', fontsize=12)
    else:
        demo_label = get_label(column_name)
        ax.set_ylabel(f'{demo_label} Proportion', fontsize=12)
    
    ax.legend(loc='best', fontsize=9, ncol=2)
    plt.tight_layout()
    
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    if safe_name == 'Poverty_Rate':
        safe_name = 'Poverty'
    output_subdir = 'Standard' if inclusion_type == 'standard' else 'Residual'
    output_path = os.path.join(output_base, output_subdir, f'frontend_{inclusion_label}_{safe_name}_region.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"    Saved: {output_subdir}/frontend_{inclusion_label}_{safe_name}_region.png")

def generate_frontend_figures():
    """Generate all frontend regional sensitivity figures"""
    print("="*70)
    print("Generating frontend regional sensitivity figures...")
    print("="*70)
    
    output_base = os.path.join(REGIONAL_BASE, 'frontend')
    os.makedirs(os.path.join(output_base, 'Standard'), exist_ok=True)
    os.makedirs(os.path.join(output_base, 'Residual'), exist_ok=True)
    
    for demo_name, demo_config in DEMOGRAPHICS.items():
        for inclusion_type in ['standard', 'residual']:
            results = process_frontend_demographic(demo_name, demo_config, inclusion_type=inclusion_type)
            
            all_columns = set()
            for region_id in REGION_MAP.keys():
                all_columns.update(results['exposed'][region_id].keys())
            
            for column in sorted(all_columns):
                create_frontend_figure(column, results, demo_name, inclusion_type)
    
    print("✓ Frontend figures complete\n")

# =============================================================================
# REACTORS
# =============================================================================

def process_reactor_demographic(demo_name, demo_config, inclusion_type='standard'):
    """Process one demographic for reactors"""
    print(f"\n  Processing reactors {inclusion_type}: {demo_name}...")
    
    suffix = '_S' if inclusion_type == 'standard' else '_R'
    
    results = {
        'exposed': {region_id: {} for region_id in REGION_MAP.keys()},
        'baseline': {region_id: {} for region_id in REGION_MAP.keys()},
        'national': {}
    }
    
    file_path = os.path.join(DEMO_BASE, demo_name, f'reactor_{demo_name}_counties.xlsx')
    
    try:
        xls = pd.ExcelFile(file_path)
        last_sheet = xls.sheet_names[-1]
        df_last = pd.read_excel(file_path, sheet_name=last_sheet)
        
        reference_columns = [col for col in df_last.columns 
                          if col.endswith(suffix) and col not in ['Buffer_Fraction_S', 'Buffer_Fraction_R']]
        
        for sheet_name in xls.sheet_names:
            year = parse_year(sheet_name)
            if year is None:
                continue
            
            if demo_name == 'race_ethnicity' and year == 2013:
                continue
            
            df_exposed = pd.read_excel(file_path, sheet_name=sheet_name)
            
            for col in reference_columns:
                if col not in df_exposed.columns:
                    df_exposed[col] = 0
            
            exposed_demo_cols_raw = [col for col in df_exposed.columns 
                                      if col.endswith(suffix) and col not in ['Buffer_Fraction_S', 'Buffer_Fraction_R']]
            expected_baseline_cols = [col.replace(suffix, '') for col in exposed_demo_cols_raw]
            
            if demo_config.get('rebin', False):
                df_exposed = rebin_age_df(df_exposed, demo_config['rebin_map'], suffix=suffix)
            
            exposed_props = calculate_exposed_proportions_by_region(df_exposed, demo_config, suffix=suffix)
            
            for region_id, proportions in exposed_props.items():
                for col in proportions.index:
                    if col not in results['exposed'][region_id]:
                        results['exposed'][region_id][col] = []
                    results['exposed'][region_id][col].append((year, proportions[col]))
            
            baseline_props, national_props = calculate_baseline_proportions_by_region(
                demo_config['baseline_file'], demo_config, sheet_name, expected_baseline_cols
            )
            
            for region_id, proportions in baseline_props.items():
                for col in proportions.index:
                    if col not in results['baseline'][region_id]:
                        results['baseline'][region_id][col] = []
                    results['baseline'][region_id][col].append((year, proportions[col]))
            
            if national_props is not None:
                for col in national_props.index:
                    if col not in results['national']:
                        results['national'][col] = []
                    results['national'][col].append((year, national_props[col]))
        
    except FileNotFoundError:
        print(f"    Warning: File not found - {file_path}")
        return results
    except Exception as e:
        print(f"    Error processing {demo_name}: {e}")
        return results
    
    return results

def create_reactor_figure(column_name, data, demo_name, inclusion_type):
    """Create a figure for one demographic column and inclusion type"""
    output_base = os.path.join(REGIONAL_BASE, 'reactors')
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    colors = {
        1: '#1f77b4', 2: '#ff7f0e', 3: '#2ca02c',
        4: '#d62728', 5: '#9467bd'
    }
    
    has_data = False
    
    for region_id, region_name in REGION_MAP.items():
        if column_name in data['exposed'][region_id] and data['exposed'][region_id][column_name]:
            points = sorted(data['exposed'][region_id][column_name])
            years, values = zip(*points)
            ax.plot(years, values, marker='o', linestyle='-', linewidth=2, 
                   color=colors[region_id], label=f'{region_name} (Reactor)', 
                   markersize=5, alpha=0.9)
            has_data = True
    
    for region_id, region_name in REGION_MAP.items():
        if column_name in data['baseline'][region_id] and data['baseline'][region_id][column_name]:
            points = sorted(data['baseline'][region_id][column_name])
            years, values = zip(*points)
            ax.plot(years, values, marker='s', linestyle='--', linewidth=1.5, 
                   color=colors[region_id], label=f'{region_name} (Regional)', 
                   markersize=4, alpha=0.7)
            has_data = True
    
    if column_name in data['national'] and data['national'][column_name]:
        points = sorted(data['national'][column_name])
        years, values = zip(*points)
        ax.plot(years, values, marker='D', linestyle='--', linewidth=2.5, 
               color='black', label='National Average', 
               markersize=5, alpha=0.8)
        has_data = True
    
    if not has_data:
        plt.close()
        return
    
    inclusion_label = 'standard' if inclusion_type == 'standard' else 'residual'
    ax.set_xlabel('Year', fontsize=12)
    
    if demo_name == 'employment' and column_name == 'Unemployment':
        ax.set_ylabel('Unemployment Rate', fontsize=12)
    elif demo_name == 'poverty' and column_name == 'Poverty Rate':
        ax.set_ylabel('Poverty Rate', fontsize=12)
    else:
        demo_label = get_label(column_name)
        ax.set_ylabel(f'{demo_label} Proportion', fontsize=12)
    
    ax.legend(loc='best', fontsize=9, ncol=2)
    plt.tight_layout()
    
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    if safe_name == 'Poverty_Rate':
        safe_name = 'Poverty'
    output_subdir = 'Standard' if inclusion_type == 'standard' else 'Residual'
    output_path = os.path.join(output_base, output_subdir, f'reactors_{inclusion_label}_{safe_name}_region.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"    Saved: {output_subdir}/reactors_{inclusion_label}_{safe_name}_region.png")

def generate_reactor_figures():
    """Generate all reactor regional sensitivity figures"""
    print("="*70)
    print("Generating reactor regional sensitivity figures...")
    print("="*70)
    
    output_base = os.path.join(REGIONAL_BASE, 'reactors')
    os.makedirs(os.path.join(output_base, 'Standard'), exist_ok=True)
    os.makedirs(os.path.join(output_base, 'Residual'), exist_ok=True)
    
    for demo_name, demo_config in DEMOGRAPHICS.items():
        for inclusion_type in ['standard', 'residual']:
            results = process_reactor_demographic(demo_name, demo_config, inclusion_type=inclusion_type)
            
            all_columns = set()
            for region_id in REGION_MAP.keys():
                all_columns.update(results['exposed'][region_id].keys())
            
            for column in sorted(all_columns):
                create_reactor_figure(column, results, demo_name, inclusion_type)
    
    print("✓ Reactor figures complete\n")

# =============================================================================
# MINES
# =============================================================================

def process_mines_demographic(demo_name, demo_config):
    """Process one demographic for mines (no temporal filtering)"""
    print(f"\n  Processing mines: {demo_name}...")
    
    results = {
        'exposed': {region_id: {} for region_id in REGION_MAP.keys()},
        'baseline': {region_id: {} for region_id in REGION_MAP.keys()},
        'national': {},
        'reserves': {region_id: {} for region_id in REGION_MAP.keys()}
    }
    
    # Process mines
    file_path = os.path.join(DEMO_BASE, demo_name, f'mines_{demo_name}_counties.xlsx')
    
    try:
        xls = pd.ExcelFile(file_path)
        
        for sheet_name in xls.sheet_names:
            year = parse_year(sheet_name)
            if year is None:
                continue
            
            if demo_name == 'race_ethnicity' and year == 2013:
                continue
            
            df_exposed = pd.read_excel(file_path, sheet_name=sheet_name)
            
            expected_baseline_cols = [col for col in df_exposed.columns 
                                    if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
            
            if demo_config.get('rebin', False):
                age_cols = [col for col in expected_baseline_cols if col in demo_config['rebin_map'] or col in demo_config['rebin_map'].values()]
                if age_cols:
                    df_age = df_exposed[age_cols + ['FIPS', 'Region']]
                    df_rebinned = rebin_age_baseline(df_age.set_index(['FIPS', 'Region']), demo_config['rebin_map']).reset_index()
                    df_exposed = df_exposed[['FIPS', 'Region']].merge(df_rebinned, on=['FIPS', 'Region'])
            
            # Create a pseudo-suffix version for compatibility with exposed calculation function
            df_temp = df_exposed.copy()
            for col in [c for c in df_temp.columns if c not in ['FIPS', 'Region']]:
                df_temp.rename(columns={col: col + '_S'}, inplace=True)
            
            exposed_props = calculate_exposed_proportions_by_region(df_temp, demo_config, suffix='_S')
            
            for region_id, proportions in exposed_props.items():
                for col in proportions.index:
                    if col not in results['exposed'][region_id]:
                        results['exposed'][region_id][col] = []
                    results['exposed'][region_id][col].append((year, proportions[col]))
            
            baseline_props, national_props = calculate_baseline_proportions_by_region(
                demo_config['baseline_file'], demo_config, sheet_name, expected_baseline_cols
            )
            
            for region_id, proportions in baseline_props.items():
                for col in proportions.index:
                    if col not in results['baseline'][region_id]:
                        results['baseline'][region_id][col] = []
                    results['baseline'][region_id][col].append((year, proportions[col]))
            
            if national_props is not None:
                for col in national_props.index:
                    if col not in results['national']:
                        results['national'][col] = []
                    results['national'][col].append((year, national_props[col]))
        
    except FileNotFoundError:
        print(f"    Warning: File not found - {file_path}")
    except Exception as e:
        print(f"    Error processing mines {demo_name}: {e}")
    
    # Process reserves
    reserves_file = os.path.join(DEMO_BASE, demo_name, f'reserves_{demo_name}_counties.xlsx')
    
    try:
        xls = pd.ExcelFile(reserves_file)
        
        for sheet_name in xls.sheet_names:
            year = parse_year(sheet_name)
            if year is None:
                continue
            
            if demo_name == 'race_ethnicity' and year == 2013:
                continue
            
            df_reserves = pd.read_excel(reserves_file, sheet_name=sheet_name)
            
            if demo_config.get('rebin', False):
                expected_cols = [col for col in df_reserves.columns if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
                age_cols = [col for col in expected_cols if col in demo_config['rebin_map'] or col in demo_config['rebin_map'].values()]
                if age_cols:
                    df_age = df_reserves[age_cols + ['FIPS', 'Region']]
                    df_rebinned = rebin_age_baseline(df_age.set_index(['FIPS', 'Region']), demo_config['rebin_map']).reset_index()
                    df_reserves = df_reserves[['FIPS', 'Region']].merge(df_rebinned, on=['FIPS', 'Region'])
            
            df_temp = df_reserves.copy()
            for col in [c for c in df_temp.columns if c not in ['FIPS', 'Region']]:
                df_temp.rename(columns={col: col + '_S'}, inplace=True)
            
            reserves_props = calculate_exposed_proportions_by_region(df_temp, demo_config, suffix='_S')
            
            for region_id, proportions in reserves_props.items():
                for col in proportions.index:
                    if col not in results['reserves'][region_id]:
                        results['reserves'][region_id][col] = []
                    results['reserves'][region_id][col].append((year, proportions[col]))
        
    except FileNotFoundError:
        print(f"    Warning: Reserves file not found - {reserves_file}")
    except Exception as e:
        print(f"    Error processing reserves {demo_name}: {e}")
    
    return results

def create_mines_figure(column_name, data, demo_name):
    """Create a figure for one demographic column for mines"""
    output_base = os.path.join(REGIONAL_BASE, 'mines')
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    colors = {
        1: '#1f77b4', 2: '#ff7f0e', 3: '#2ca02c',
        4: '#d62728', 5: '#9467bd'
    }
    
    has_data = False
    
    for region_id, region_name in REGION_MAP.items():
        if column_name in data['exposed'][region_id] and data['exposed'][region_id][column_name]:
            points = sorted(data['exposed'][region_id][column_name])
            years, values = zip(*points)
            ax.plot(years, values, marker='o', linestyle='-', linewidth=2, 
                   color=colors[region_id], label=f'{region_name} (Mines)', 
                   markersize=5, alpha=0.9)
            has_data = True
    
    for region_id, region_name in REGION_MAP.items():
        if column_name in data['reserves'][region_id] and data['reserves'][region_id][column_name]:
            points = sorted(data['reserves'][region_id][column_name])
            years, values = zip(*points)
            ax.plot(years, values, marker='^', linestyle=':', linewidth=1.5, 
                   color=colors[region_id], label=f'{region_name} (Reserves)', 
                   markersize=4, alpha=0.7)
            has_data = True
    
    for region_id, region_name in REGION_MAP.items():
        if column_name in data['baseline'][region_id] and data['baseline'][region_id][column_name]:
            points = sorted(data['baseline'][region_id][column_name])
            years, values = zip(*points)
            ax.plot(years, values, marker='s', linestyle='--', linewidth=1.5, 
                   color=colors[region_id], label=f'{region_name} (Regional)', 
                   markersize=4, alpha=0.5)
    
    if column_name in data['national'] and data['national'][column_name]:
        points = sorted(data['national'][column_name])
        years, values = zip(*points)
        ax.plot(years, values, marker='D', linestyle='--', linewidth=2.5, 
               color='black', label='National Average', 
               markersize=5, alpha=0.8)
        has_data = True
    
    if not has_data:
        plt.close()
        return
    
    ax.set_xlabel('Year', fontsize=12)
    
    if demo_name == 'employment' and column_name == 'Unemployment':
        ax.set_ylabel('Unemployment Rate', fontsize=12)
    elif demo_name == 'poverty' and column_name == 'Poverty Rate':
        ax.set_ylabel('Poverty Rate', fontsize=12)
    else:
        demo_label = get_label(column_name)
        ax.set_ylabel(f'{demo_label} Proportion', fontsize=12)
    
    ax.legend(loc='best', fontsize=8, ncol=2)
    plt.tight_layout()
    
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    if safe_name == 'Poverty_Rate':
        safe_name = 'Poverty'
    output_path = os.path.join(output_base, f'mines_{safe_name}_region.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"    Saved: mines_{safe_name}_region.png")

def generate_mines_figures():
    """Generate all mines regional sensitivity figures"""
    print("="*70)
    print("Generating mines regional sensitivity figures...")
    print("="*70)
    
    output_base = os.path.join(REGIONAL_BASE, 'mines')
    os.makedirs(output_base, exist_ok=True)
    
    for demo_name, demo_config in DEMOGRAPHICS.items():
        results = process_mines_demographic(demo_name, demo_config)
        
        all_columns = set()
        for region_id in REGION_MAP.keys():
            all_columns.update(results['exposed'][region_id].keys())
        
        for column in sorted(all_columns):
            create_mines_figure(column, results, demo_name)
    
    print("✓ Mines figures complete\n")

# =============================================================================
# INTERIM STORAGE
# =============================================================================

def calculate_exposed_proportions_by_stage_interim(df, demographic_config):
    """Calculate demographic proportions for exposed populations by region from stage-specific data"""
    demo_cols = [col for col in df.columns 
                 if col not in ['FIPS', 'Region', 'Buffer_Fraction', 'Name', 'Note', 'Approx Year']]
    
    if not demo_cols:
        return {}
    
    results = {}
    
    for region_id in REGION_MAP.keys():
        region_df = df[df['Region'] == region_id].copy()
        
        if region_df.empty:
            continue
        
        exposed_df = region_df[region_df['Buffer_Fraction'] > 0].copy()
        
        if exposed_df.empty:
            continue
        
        totals = exposed_df[demo_cols].sum()
        
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

def process_interim_demographic(demo_name, demo_config, facility_type):
    """Process one demographic for a specific facility type across all years"""
    print(f"\n  Processing interim {facility_type}: {demo_name}...")
    
    results = {
        'exposed': {},
        'baseline': {},
        'national': {}
    }
    
    facility_config = INTERIM_FACILITY_BINS[facility_type]
    
    for stage_name in facility_config['stages'].keys():
        results['exposed'][stage_name] = {region_id: {} for region_id in REGION_MAP.keys()}
    
    for region_id in REGION_MAP.keys():
        results['baseline'][region_id] = {}
    
    file_path = os.path.join(DEMO_BASE, demo_name, f'interim_prop_{demo_name}_counties.xlsx')
    
    try:
        xls = pd.ExcelFile(file_path)
        last_sheet = xls.sheet_names[-1]
        df_last = pd.read_excel(file_path, sheet_name=last_sheet)
        
        reference_columns = [col for col in df_last.columns 
                          if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
        
        expected_baseline_cols = reference_columns.copy()
        
        # Process each stage for this facility type
        for stage_name, note_list in facility_config['stages'].items():
            # Read all sheets for the notes in this stage (e.g., DOE Stage 1 reads notes [4,5,6])
            # which corresponds to sheets "Stage 4 - 1990", "Stage 5 - 1990", "Stage 6 - 1990"
            all_dfs = []
            for note in note_list:
                sheet_name = f"Stage {note} - 1990"
                
                if sheet_name not in xls.sheet_names:
                    print(f"    Warning: Sheet '{sheet_name}' not found for {facility_type} {stage_name}")
                    continue
                
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                
                # Fill missing columns with 0
                for col in reference_columns:
                    if col not in df.columns:
                        df[col] = 0
                
                all_dfs.append(df)
            
            if not all_dfs:
                continue
            
            # Concatenate all dataframes for this stage
            df_all = pd.concat(all_dfs, ignore_index=True)
            
            if demo_config.get('rebin', False):
                # Use the rebinning approach from interim_region_sensitivity.py
                age_cols = [col for col in df_all.columns 
                           if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
                rebinned_cols = {}
                for col in age_cols:
                    if col in demo_config['rebin_map']:
                        new_col = demo_config['rebin_map'][col]
                        if new_col not in rebinned_cols:
                            rebinned_cols[new_col] = df_all[col]
                        else:
                            rebinned_cols[new_col] += df_all[col]
                    else:
                        rebinned_cols[col] = df_all[col]
                
                # Preserve metadata columns
                result_df = df_all[['FIPS', 'Region', 'Buffer_Fraction']].copy()
                for col_name, col_data in rebinned_cols.items():
                    result_df[col_name] = col_data
                df_all = result_df
            
            # Process the entire dataframe for this stage
            stage_props = calculate_exposed_proportions_by_stage_interim(df_all, demo_config)
            
            for region_id, proportions in stage_props.items():
                for col in proportions.index:
                    if col not in results['exposed'][stage_name][region_id]:
                        results['exposed'][stage_name][region_id][col] = []
                    # Store as (year, value) tuple - single data point at 1990 for this stage
                    results['exposed'][stage_name][region_id][col].append((1990, proportions[col]))
        
        # Calculate baseline using constant year 1990 from baseline demographic files
        baseline_props, national_props = calculate_baseline_proportions_by_region(
            demo_config['baseline_file'], demo_config, '1990', expected_baseline_cols
        )
        
        for region_id, proportions in baseline_props.items():
            for col in proportions.index:
                if col not in results['baseline'][region_id]:
                    results['baseline'][region_id][col] = []
                # Store as (year, value) tuple for baseline (1990)
                results['baseline'][region_id][col].append((1990, proportions[col]))
        
        if national_props is not None:
            for col in national_props.index:
                if col not in results['national']:
                    results['national'][col] = []
                # Store as (year, value) tuple for national (1990)
                results['national'][col].append((1990, national_props[col]))
        
    except FileNotFoundError:
        print(f"    Warning: File not found - {file_path}")
        return results
    except Exception as e:
        print(f"    Error processing {demo_name}: {e}")
        return results
    
    return results

def create_interim_figure(column_name, data, demo_name, facility_type, stages_list):
    """Create a bar plot for one demographic column comparing regions across stages"""
    output_base = os.path.join(REGIONAL_BASE, 'interim_storage')
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    colors = {
        1: '#1f77b4', 2: '#ff7f0e', 3: '#2ca02c',
        4: '#d62728', 5: '#9467bd'
    }
    
    has_data = False
    
    # Create stage names for x-axis, relabeling DOE stages and Private
    stage_names = []
    for stage in stages_list:
        if facility_type == 'Private':
            # Relabel Private Stage 0 to "Private"
            stage_names.append(stage.replace('Stage 0', 'Private'))
        elif facility_type == 'DOE':
            # Relabel DOE stages from 4,5,6 to 1,2,3
            stage_names.append(stage.replace('Stage 4', 'Stage 1').replace('Stage 5', 'Stage 2').replace('Stage 6', 'Stage 3'))
        else:
            # For ONWN, replace Stage 0 with All - Unstaged
            stage_names.append(stage.replace('Stage 0', 'All - Unstaged'))
    stage_names.append('Regional (1990)')
    
    num_groups = len(stage_names)
    num_regions = len(REGION_MAP)
    bar_width = 0.15
    x = np.arange(num_groups)
    
    for i, (region_id, region_name) in enumerate(REGION_MAP.items()):
        all_values = []
        
        for stage_name in stages_list:
            if (region_id in data['exposed'].get(stage_name, {}) and 
                column_name in data['exposed'][stage_name][region_id] and
                data['exposed'][stage_name][region_id][column_name]):
                value = data['exposed'][stage_name][region_id][column_name][0][1]
                all_values.append(value)
            else:
                all_values.append(0)
        
        if (region_id in data['baseline'] and 
            column_name in data['baseline'][region_id] and
            data['baseline'][region_id][column_name]):
            value = data['baseline'][region_id][column_name][0][1]
            all_values.append(value)
        else:
            all_values.append(0)
        
        if any(v > 0 for v in all_values):
            offset = (i - num_regions/2 + 0.5) * bar_width
            bars = ax.bar(x + offset, all_values, width=bar_width, label=f'{region_name}', 
                         color=colors[region_id], alpha=0.9)
            
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:.3f}', ha='center', va='bottom', fontsize=7)
            has_data = True
    
    if column_name in data['national'] and data['national'][column_name]:
        national_value = data['national'][column_name][0][1]
        ax.axhline(y=national_value, linestyle=':', linewidth=2.5, 
                  color='black', label='National (1990)', alpha=0.8)
        has_data = True
    
    if not has_data:
        plt.close()
        return
    
    ax.set_xticks(x)
    ax.set_xticklabels(stage_names, fontsize=10)
    ax.set_xlabel('Development Stage / Regional Baseline', fontsize=12)
    
    if demo_name == 'employment' and column_name == 'Unemployment':
        ax.set_ylabel('Unemployment Rate', fontsize=12)
    elif demo_name == 'poverty' and column_name == 'Poverty Rate':
        ax.set_ylabel('Poverty Rate', fontsize=12)
    else:
        demo_label = get_label(column_name)
        ax.set_ylabel(f'{demo_label} Proportion', fontsize=12)
    
    ax.legend(loc='best', fontsize=8, ncol=1)
    plt.tight_layout()
    
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    if safe_name == 'Poverty_Rate':
        safe_name = 'Poverty'
    output_path = os.path.join(output_base, facility_type, f'interim_{facility_type}_{safe_name}_region.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"    Saved: {facility_type}/interim_{facility_type}_{safe_name}_region.png")

def generate_interim_figures():
    """Generate all interim storage regional sensitivity figures"""
    print("="*70)
    print("Generating interim storage regional sensitivity figures...")
    print("="*70)
    
    output_base = os.path.join(REGIONAL_BASE, 'interim_storage')
    os.makedirs(os.path.join(output_base, 'Private'), exist_ok=True)
    os.makedirs(os.path.join(output_base, 'ONWN'), exist_ok=True)
    os.makedirs(os.path.join(output_base, 'DOE'), exist_ok=True)
    
    for demo_name, demo_config in DEMOGRAPHICS.items():
        for facility_type in INTERIM_FACILITY_BINS.keys():
            results = process_interim_demographic(demo_name, demo_config, facility_type)
            
            stages_or_sites = list(results['exposed'].keys())
            
            if not stages_or_sites:
                continue
            
            all_columns = set()
            for stage_or_site in stages_or_sites:
                for region_id in REGION_MAP.keys():
                    if region_id in results['exposed'][stage_or_site]:
                        all_columns.update(results['exposed'][stage_or_site][region_id].keys())
            
            for column in sorted(all_columns):
                create_interim_figure(column, results, demo_name, facility_type, stages_or_sites)
    
    print("✓ Interim storage figures complete\n")

# =============================================================================
# REPOSITORIES
# =============================================================================

def process_repo_demographic(demo_name, demo_config):
    """Process one demographic for repositories (using 1980 data)"""
    print(f"\n  Processing repositories: {demo_name}...")
    
    results = {
        'exposed': {},
        'baseline': {},
        'national': {}
    }
    
    for stage_name in REPO_STAGE_BINS.keys():
        results['exposed'][stage_name] = {region_id: {} for region_id in REGION_MAP.keys()}
    
    for region_id in REGION_MAP.keys():
        results['baseline'][region_id] = {}
    
    file_path = os.path.join(DEMO_BASE, demo_name, f'repository_{demo_name}_counties.xlsx')
    
    try:
        xls = pd.ExcelFile(file_path)
        last_sheet = xls.sheet_names[-1]
        df_last = pd.read_excel(file_path, sheet_name=last_sheet)
        
        reference_columns = [col for col in df_last.columns 
                          if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
        
        expected_baseline_cols = reference_columns.copy()
        
        # Process each stage for repositories
        for stage_name in REPO_STAGE_BINS.keys():
            sheet_name = f"{stage_name} - 1980"
            
            if sheet_name not in xls.sheet_names:
                print(f"    Warning: Sheet '{sheet_name}' not found")
                continue
            
            df_all = pd.read_excel(file_path, sheet_name=sheet_name)
            
            for col in reference_columns:
                if col not in df_all.columns:
                    df_all[col] = 0
            
            if demo_config.get('rebin', False):
                # Use the rebinning approach from repository_region_sensitivity.py
                age_cols = [col for col in df_all.columns 
                           if col not in ['FIPS', 'Region', 'Buffer_Fraction']]
                rebinned_cols = {}
                for col in age_cols:
                    if col in demo_config['rebin_map']:
                        new_col = demo_config['rebin_map'][col]
                        if new_col not in rebinned_cols:
                            rebinned_cols[new_col] = df_all[col]
                        else:
                            rebinned_cols[new_col] += df_all[col]
                    else:
                        rebinned_cols[col] = df_all[col]
                
                # Preserve metadata columns
                result_df = df_all[['FIPS', 'Region', 'Buffer_Fraction']].copy()
                for col_name, col_data in rebinned_cols.items():
                    result_df[col_name] = col_data
                df_all = result_df
            
            # Process the entire dataframe for this stage
            stage_props = calculate_exposed_proportions_by_stage_interim(df_all, demo_config)
            # Store direct values (not tuples) for each stage
            results['exposed'][stage_name] = stage_props
        
        # Calculate baseline using constant year 1980 from baseline demographic files
        baseline_props, national_props = calculate_baseline_proportions_by_region(
            demo_config['baseline_file'], demo_config, '1980', expected_baseline_cols
        )
        
        results['baseline'] = baseline_props
        results['national'] = national_props if national_props is not None else {}
        
    except FileNotFoundError:
        print(f"    Warning: File not found - {file_path}")
        return results
    except Exception as e:
        print(f"    Error processing {demo_name}: {e}")
        return results
    
    return results

def create_repo_figure(column_name, data, demo_name):
    """Create a bar plot for one demographic column comparing regions across stages"""
    output_base = os.path.join(REGIONAL_BASE, 'repositories')
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    colors = {
        1: '#1f77b4', 2: '#ff7f0e', 3: '#2ca02c',
        4: '#d62728', 5: '#9467bd'
    }
    
    has_data = False
    
    stage_names = [name.replace('Stage 0', 'Unstaged') for name in REPO_STAGE_BINS.keys()] + ['Regional (1980)']
    num_groups = len(stage_names)
    num_regions = len(REGION_MAP)
    bar_width = 0.15
    x = np.arange(num_groups)
    
    for i, (region_id, region_name) in enumerate(REGION_MAP.items()):
        all_values = []
        
        for stage_name in REPO_STAGE_BINS.keys():
            if region_id in data['exposed'].get(stage_name, {}) and column_name in data['exposed'][stage_name][region_id]:
                all_values.append(data['exposed'][stage_name][region_id][column_name])
            else:
                all_values.append(0)
        
        if region_id in data['baseline'] and column_name in data['baseline'][region_id]:
            all_values.append(data['baseline'][region_id][column_name])
        else:
            all_values.append(0)
        
        if any(v > 0 for v in all_values):
            offset = (i - num_regions/2 + 0.5) * bar_width
            bars = ax.bar(x + offset, all_values, width=bar_width, label=f'{region_name}', 
                         color=colors[region_id], alpha=0.9)
            
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:.3f}', ha='center', va='bottom', fontsize=7)
            has_data = True
    
    if column_name in data['national']:
        national_value = data['national'][column_name]
        ax.axhline(y=national_value, linestyle='--', linewidth=2.5, 
                  color='black', label='National (1980)', alpha=0.8)
        has_data = True
    
    if not has_data:
        plt.close()
        return
    
    ax.set_xticks(x)
    ax.set_xticklabels(stage_names, fontsize=10)
    ax.set_xlabel('Development Stage / Regional Baseline', fontsize=12)
    
    if demo_name == 'employment' and column_name == 'Unemployment':
        ax.set_ylabel('Unemployment Rate', fontsize=12)
    elif demo_name == 'poverty' and column_name == 'Poverty Rate':
        ax.set_ylabel('Poverty Rate', fontsize=12)
    else:
        demo_label = get_label(column_name)
        ax.set_ylabel(f'{demo_label} Proportion', fontsize=12)
    
    ax.legend(loc='best', fontsize=8, ncol=1)
    plt.tight_layout()
    
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    if safe_name == 'Poverty_Rate':
        safe_name = 'Poverty'
    output_path = os.path.join(output_base, f'repository_{safe_name}_region.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"    Saved: repository_{safe_name}_region.png")

def generate_repo_figures():
    """Generate all repository regional sensitivity figures"""
    print("="*70)
    print("Generating repository regional sensitivity figures...")
    print("="*70)
    
    output_base = os.path.join(REGIONAL_BASE, 'repositories')
    os.makedirs(output_base, exist_ok=True)
    
    for demo_name, demo_config in DEMOGRAPHICS.items():
        results = process_repo_demographic(demo_name, demo_config)
        
        all_columns = set()
        for stage_name in REPO_STAGE_BINS.keys():
            for region_id in REGION_MAP.keys():
                if region_id in results['exposed'].get(stage_name, {}):
                    all_columns.update(results['exposed'][stage_name][region_id].keys())
        
        for column in sorted(all_columns):
            create_repo_figure(column, results, demo_name)
    
    print("✓ Repository figures complete\n")

# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("REGIONAL SENSITIVITY FIGURE GENERATOR")
    print("Generating all regional sensitivity figures for all facility types")
    print("="*70 + "\n")
    
    # Generate figures for each facility type
    #generate_frontend_figures()
    #generate_reactor_figures()
    #generate_mines_figures()
    generate_interim_figures()
    generate_repo_figures()
    
    print("="*70)
    print("✓ ALL REGIONAL SENSITIVITY FIGURES GENERATED SUCCESSFULLY!")
    print("="*70)
