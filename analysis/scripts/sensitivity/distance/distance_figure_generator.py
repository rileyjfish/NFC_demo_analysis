"""
Consolidated distance sensitivity figure generator.
Generates all distance sensitivity figures for:
- Frontend facilities (standard & residual inclusion)
- Reactors (standard & residual inclusion)
- Mines (no temporal filtering)
- Interim storage (by facility type and stage)
- Repositories (by development stage)
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os
import re

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
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
PROXIMITY_BASE = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis')

# Define demographics and their special handling
DEMOGRAPHICS = {
    'age': {
        'file': 'age',
        'rebin': True,
        'rebin_map': {
            '<5': '<19', '5-9': '<19', '10-14': '<19', '15-19': '<19',
            '20-24': '20-34', '25-34': '20-34',
            '35-44': '35-59', '45-59': '35-59',
            '60-64': '60+', '65-74': '60+', '75-84': '60+', '85+': '60+'
        }
    },
    'education': {
        'file': 'education',
        'columns': ['<9', '<B', 'B+']
    },
    'employment': {
        'file': 'employment',
        'special': 'unemployment',
        'columns': ['LF-CIV', 'LF-CIV-EMPL']
    },
    'poverty': {
        'file': 'poverty',
        'special': 'poverty_rate',
        'columns': ['Poverty', 'PSD']
    },
    'race_ethnicity': {
        'file': 'race_ethnicity',
        'exclude_from_total': ['H'],
        'columns': ['W', 'B', 'AIAN', 'AAPI', 'O', '2+', 'H']
    },
    'sex': {
        'file': 'sex',
        'columns': ['M', 'F']
    }
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

def rebin_age(df, rebin_map):
    """Rebin age columns according to mapping"""
    rebinned = {}
    for old_col, new_col in rebin_map.items():
        if old_col in df.columns:
            if new_col not in rebinned:
                rebinned[new_col] = df[old_col]
            else:
                rebinned[new_col] += df[old_col]
    return pd.DataFrame(rebinned, index=df.index)

def calculate_proportions(df, demographic_config):
    """Calculate demographic proportions based on configuration"""
    # Handle special cases
    if 'special' in demographic_config:
        if demographic_config['special'] == 'unemployment':
            if 'LF-CIV' in df.columns and 'LF-CIV-EMPL' in df.columns:
                total_lf_civ = df['LF-CIV'].sum()
                total_employed = df['LF-CIV-EMPL'].sum()
                unemployment = 1 - (total_employed / total_lf_civ)
                return pd.Series({'Unemployment': unemployment})
            return pd.Series()
        
        elif demographic_config['special'] == 'poverty_rate':
            if 'Poverty' in df.columns and 'PSD' in df.columns:
                total_poverty = df['Poverty'].sum()
                total_psd = df['PSD'].sum()
                poverty_rate = total_poverty / total_psd
                return pd.Series({'Poverty Rate': poverty_rate})
            return pd.Series()
    
    # Calculate total population and proportions
    totals = df.sum(axis=0)
    
    if 'exclude_from_total' in demographic_config:
        # For race_ethnicity: exclude H from total, but calculate proportion for all including H
        total_cols = [col for col in totals.index if col not in demographic_config['exclude_from_total']]
        population_total = totals[total_cols].sum()
        proportions = totals / population_total
    else:
        # Standard: sum all columns for total
        population_total = totals.sum()
        proportions = totals / population_total
    
    return proportions

# =============================================================================
# FRONTEND FACILITIES
# =============================================================================

def filter_facilities_standard(df, year):
    """Standard inclusion: facilities operating during the year"""
    start_vals = df.index.get_level_values('Start')
    stop_vals = df.index.get_level_values('Stop')
    
    # Convert to numeric years if they're datetime
    if pd.api.types.is_datetime64_any_dtype(start_vals):
        start_vals = pd.to_datetime(start_vals).year
    else:
        start_vals = pd.to_numeric(start_vals, errors='coerce')
    
    if pd.api.types.is_datetime64_any_dtype(stop_vals):
        stop_vals = pd.to_datetime(stop_vals).year
    else:
        stop_vals = pd.to_numeric(stop_vals, errors='coerce')
    
    mask = (start_vals <= year) & (stop_vals >= year)
    return df[mask]

def filter_facilities_residual(df, year):
    """Residual inclusion: facilities that have ever operated by this year"""
    start_vals = df.index.get_level_values('Start')
    
    # Convert to numeric years if they're datetime
    if pd.api.types.is_datetime64_any_dtype(start_vals):
        start_vals = pd.to_datetime(start_vals).year
    else:
        start_vals = pd.to_numeric(start_vals, errors='coerce')
    
    mask = start_vals <= year
    return df[mask]

def process_frontend_demographic(demo_name, demo_config):
    """Process one demographic across all distances for frontend facilities"""
    distances = ['1mi', '5mi', '10mi', '25mi', '50mi']
    print(f"\nProcessing frontend: {demo_name}...")
    
    results = {
        'standard': {dist: {} for dist in distances},
        'residual': {dist: {} for dist in distances}
    }
    
    for dist in distances:
        if dist == '50mi':
            file_path = os.path.join(BASE_DIR, 'outputs', 'demographics_by_facility', demo_name, f'frontend_{demo_name}_facilities.xlsx')
        else:
            dist_folder = dist.replace('mi', ' Mile')
            file_path = os.path.join(PROXIMITY_BASE, 'distance', dist_folder, demo_name, f'{dist}_frontend_{demo_name}.xlsx')
        
        try:
            xls = pd.ExcelFile(file_path)
            last_sheet = xls.sheet_names[-1]
            df_last = pd.read_excel(file_path, sheet_name=last_sheet, header=0, index_col=[0, 1, 2, 3, 4, 5, 6, 7])
            valid_cols_last = [col for col in df_last.columns if not str(col).endswith('_E')]
            
            if demo_config.get('rebin', False):
                df_last_subset = df_last[valid_cols_last]
                df_last_rebinned = rebin_age(df_last_subset, demo_config['rebin_map'])
                reference_columns = df_last_rebinned.columns.tolist()
            else:
                reference_columns = valid_cols_last
            
            for sheet_name in xls.sheet_names:
                year = parse_year(sheet_name)
                if year is None:
                    continue
                
                if demo_name == 'race_ethnicity' and year == 2013:
                    continue
                
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=0, index_col=[0, 1, 2, 3, 4, 5, 6, 7])
                valid_cols = [col for col in df.columns if not str(col).endswith('_E')]
                df = df[valid_cols]
                
                if demo_config.get('rebin', False):
                    df = rebin_age(df, demo_config['rebin_map'])
                
                for col in reference_columns:
                    if col not in df.columns:
                        df[col] = 0
                
                # Filter for standard inclusion
                df_standard = filter_facilities_standard(df, year)
                if not df_standard.empty:
                    proportions = calculate_proportions(df_standard, demo_config)
                    if len(proportions) > 0:
                        for col in proportions.index:
                            if col not in results['standard'][dist]:
                                results['standard'][dist][col] = []
                            results['standard'][dist][col].append((year, proportions[col]))
                
                # Filter for residual inclusion
                df_residual = filter_facilities_residual(df, year)
                if not df_residual.empty:
                    proportions = calculate_proportions(df_residual, demo_config)
                    if len(proportions) > 0:
                        for col in proportions.index:
                            if col not in results['residual'][dist]:
                                results['residual'][dist][col] = []
                            results['residual'][dist][col].append((year, proportions[col]))
        
        except FileNotFoundError:
            print(f"  Warning: File not found - {file_path}")
            continue
        except Exception as e:
            print(f"  Error processing {dist} for {demo_name}: {e}")
            continue
    
    return results

def create_frontend_figure(column_name, data, demo_name, inclusion_type):
    """Create a figure for one demographic column and inclusion type"""
    distances = ['1mi', '5mi', '10mi', '25mi', '50mi']
    distance_labels = ['1 Mile', '5 Mile', '10 Mile', '25 Mile', '50 Mile']
    output_base = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'distance', 'frontend')
    
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    has_data = False
    
    for i, (dist, label) in enumerate(zip(distances, distance_labels)):
        if column_name in data[inclusion_type][dist]:
            points = sorted(data[inclusion_type][dist][column_name])
            if points:
                years, values = zip(*points)
                ax.plot(years, values, marker='o', linestyle='-', linewidth=2, 
                       color=colors[i], label=label, markersize=4)
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
        ax.set_ylabel('Proportion', fontsize=12)
    
    ax.legend(loc='best', fontsize=9)
    plt.tight_layout()
    
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    subdir_label = 'Standard' if inclusion_type == 'standard' else 'Residual'
    output_path = os.path.join(output_base, subdir_label, f'frontend_{inclusion_label}_{safe_name}_distance.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {subdir_label}/frontend_{inclusion_label}_{safe_name}_distance.png")

def generate_frontend_figures():
    """Generate all frontend distance sensitivity figures"""
    print("="*70)
    print("Generating frontend distance sensitivity figures...")
    print("="*70)
    
    output_base = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'distance', 'frontend')
    os.makedirs(os.path.join(output_base, 'Standard'), exist_ok=True)
    os.makedirs(os.path.join(output_base, 'Residual'), exist_ok=True)
    
    for demo_name, demo_config in DEMOGRAPHICS.items():
        results = process_frontend_demographic(demo_name, demo_config)
        
        for inclusion_type in ['standard', 'residual']:
            all_columns = set()
            for dist in ['1mi', '5mi', '10mi', '25mi', '50mi']:
                all_columns.update(results[inclusion_type][dist].keys())
            
            for column in sorted(all_columns):
                create_frontend_figure(column, results, demo_name, inclusion_type)
    
    print("✓ Frontend figures complete\n")

# =============================================================================
# REACTORS
# =============================================================================

def filter_reactors_standard(df, year):
    """Standard inclusion: reactors operating during the year"""
    name_vals = df.index.get_level_values('Name')
    start_vals = df.index.get_level_values('Start')
    stop_vals = df.index.get_level_values('Stop')
    
    if pd.api.types.is_datetime64_any_dtype(start_vals):
        start_years = pd.to_datetime(start_vals).year
    else:
        start_years = pd.to_numeric(start_vals, errors='coerce')
    
    if pd.api.types.is_datetime64_any_dtype(stop_vals):
        stop_years = pd.to_datetime(stop_vals).year
    else:
        stop_years = pd.to_numeric(stop_vals, errors='coerce')
    
    # Find earliest start and latest stop for each base name
    base_name_groups = {}
    for i in range(len(df)):
        name = name_vals[i]
        base_name = name[:-2] if isinstance(name, str) and len(name) > 2 else name
        start_year = start_years.iloc[i] if hasattr(start_years, 'iloc') else start_years[i]
        stop_year = stop_years.iloc[i] if hasattr(stop_years, 'iloc') else stop_years[i]
        
        if pd.isnull(start_year) or pd.isnull(stop_year):
            continue
        
        if base_name not in base_name_groups:
            base_name_groups[base_name] = {'indices': [i], 'earliest_start': start_year, 'latest_stop': stop_year}
        else:
            base_name_groups[base_name]['indices'].append(i)
            if start_year < base_name_groups[base_name]['earliest_start']:
                base_name_groups[base_name]['earliest_start'] = start_year
            if stop_year > base_name_groups[base_name]['latest_stop']:
                base_name_groups[base_name]['latest_stop'] = stop_year
    
    keep_indices = []
    for base_name, info in base_name_groups.items():
        if info['earliest_start'] <= year <= info['latest_stop']:
            keep_indices.append(info['indices'][0])
    
    return df.iloc[keep_indices]

def filter_reactors_residual(df, year):
    """Residual inclusion: reactors that have ever operated by this year"""
    name_vals = df.index.get_level_values('Name')
    start_vals = df.index.get_level_values('Start')
    
    if pd.api.types.is_datetime64_any_dtype(start_vals):
        start_years = pd.to_datetime(start_vals).year
    else:
        start_years = pd.to_numeric(start_vals, errors='coerce')
    
    base_name_groups = {}
    for i in range(len(df)):
        name = name_vals[i]
        base_name = name[:-2] if isinstance(name, str) and len(name) > 2 else name
        start_year = start_years.iloc[i] if hasattr(start_years, 'iloc') else start_years[i]
        
        if pd.isnull(start_year):
            continue
        
        if base_name not in base_name_groups:
            base_name_groups[base_name] = {'indices': [i], 'earliest_start': start_year}
        else:
            base_name_groups[base_name]['indices'].append(i)
            if start_year < base_name_groups[base_name]['earliest_start']:
                base_name_groups[base_name]['earliest_start'] = start_year
    
    keep_indices = []
    for base_name, info in base_name_groups.items():
        if info['earliest_start'] <= year:
            keep_indices.append(info['indices'][0])
    
    return df.iloc[keep_indices]

def process_reactor_demographic(demo_name, demo_config):
    """Process one demographic across all distances for reactors"""
    distances = ['1mi', '5mi', '10mi', '25mi', '50mi']
    print(f"\nProcessing reactors: {demo_name}...")
    
    results = {
        'standard': {dist: {} for dist in distances},
        'residual': {dist: {} for dist in distances}
    }
    
    for dist in distances:
        if dist == '50mi':
            file_path = os.path.join(BASE_DIR, 'outputs', 'demographics_by_facility', demo_name, f'reactor_{demo_name}_facilities.xlsx')
        else:
            dist_folder = dist.replace('mi', ' Mile')
            file_path = os.path.join(PROXIMITY_BASE, 'distance', dist_folder, demo_name, f'{dist}_reactor_{demo_name}.xlsx')
        
        try:
            xls = pd.ExcelFile(file_path)
            last_sheet = xls.sheet_names[-1]
            df_last = pd.read_excel(file_path, sheet_name=last_sheet, header=0, index_col=[0, 1, 2, 3, 4])
            valid_cols_last = [col for col in df_last.columns if not str(col).endswith('_E')]
            
            if demo_config.get('rebin', False):
                df_last_subset = df_last[valid_cols_last]
                df_last_rebinned = rebin_age(df_last_subset, demo_config['rebin_map'])
                reference_columns = df_last_rebinned.columns.tolist()
            else:
                reference_columns = valid_cols_last
            
            for sheet_name in xls.sheet_names:
                year = parse_year(sheet_name)
                if year is None:
                    continue
                
                if demo_name == 'race_ethnicity' and year == 2013:
                    continue
                
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=0, index_col=[0, 1, 2, 3, 4])
                valid_cols = [col for col in df.columns if not str(col).endswith('_E')]
                df = df[valid_cols]
                
                if demo_config.get('rebin', False):
                    df = rebin_age(df, demo_config['rebin_map'])
                
                for col in reference_columns:
                    if col not in df.columns:
                        df[col] = 0
                
                # Filter for standard inclusion
                df_standard = filter_reactors_standard(df, year)
                if not df_standard.empty:
                    proportions = calculate_proportions(df_standard, demo_config)
                    if len(proportions) > 0:
                        for col in proportions.index:
                            if col not in results['standard'][dist]:
                                results['standard'][dist][col] = []
                            results['standard'][dist][col].append((year, proportions[col]))
                
                # Filter for residual inclusion
                df_residual = filter_reactors_residual(df, year)
                if not df_residual.empty:
                    proportions = calculate_proportions(df_residual, demo_config)
                    if len(proportions) > 0:
                        for col in proportions.index:
                            if col not in results['residual'][dist]:
                                results['residual'][dist][col] = []
                            results['residual'][dist][col].append((year, proportions[col]))
        
        except FileNotFoundError:
            print(f"  Warning: File not found - {file_path}")
            continue
        except Exception as e:
            print(f"  Error processing {dist} for {demo_name}: {e}")
            continue
    
    return results

def create_reactor_figure(column_name, data, demo_name, inclusion_type):
    """Create a figure for one demographic column and inclusion type"""
    distances = ['1mi', '5mi', '10mi', '25mi', '50mi']
    distance_labels = ['1 Mile', '5 Mile', '10 Mile', '25 Mile', '50 Mile']
    output_base = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'distance', 'reactors')
    
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    has_data = False
    
    for i, (dist, label) in enumerate(zip(distances, distance_labels)):
        if column_name in data[inclusion_type][dist]:
            points = sorted(data[inclusion_type][dist][column_name])
            if points:
                years, values = zip(*points)
                ax.plot(years, values, marker='o', linestyle='-', linewidth=2, 
                       color=colors[i], label=label, markersize=4)
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
        ax.set_ylabel('Proportion', fontsize=12)
    
    ax.legend(loc='best', fontsize=9)
    plt.tight_layout()
    
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    if safe_name == 'Poverty_Rate':
        safe_name = 'Poverty'
    subdir_label = 'Standard' if inclusion_type == 'standard' else 'Residual'
    output_path = os.path.join(output_base, subdir_label, f'reactors_{inclusion_label}_{safe_name}_distance.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {subdir_label}/reactors_{inclusion_label}_{safe_name}_distance.png")

def generate_reactor_figures():
    """Generate all reactor distance sensitivity figures"""
    print("="*70)
    print("Generating reactor distance sensitivity figures...")
    print("="*70)
    
    output_base = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'distance', 'reactors')
    os.makedirs(os.path.join(output_base, 'Standard'), exist_ok=True)
    os.makedirs(os.path.join(output_base, 'Residual'), exist_ok=True)
    
    for demo_name, demo_config in DEMOGRAPHICS.items():
        results = process_reactor_demographic(demo_name, demo_config)
        
        for inclusion_type in ['standard', 'residual']:
            all_columns = set()
            for dist in ['1mi', '5mi', '10mi', '25mi', '50mi']:
                all_columns.update(results[inclusion_type][dist].keys())
            
            for column in sorted(all_columns):
                create_reactor_figure(column, results, demo_name, inclusion_type)
    
    print("✓ Reactor figures complete\n")

# =============================================================================
# MINES
# =============================================================================

def process_mines_demographic(demo_name, demo_config):
    """Process one demographic across all distances for mines"""
    distances = ['1mi', '5mi', '10mi', '25mi']
    print(f"\nProcessing mines: {demo_name}...")
    
    results = {dist: {} for dist in distances}
    
    for dist in distances:
        dist_folder = dist.replace('mi', ' Mile')
        file_path = os.path.join(PROXIMITY_BASE, 'distance', dist_folder, demo_name, f'{dist}_mines_{demo_name}.xlsx')
        
        try:
            xls = pd.ExcelFile(file_path)
            last_sheet = xls.sheet_names[-1]
            df_last = pd.read_excel(file_path, sheet_name=last_sheet, header=0, index_col=[0, 1])
            valid_cols_last = [col for col in df_last.columns if not str(col).endswith('_E')]
            
            if demo_config.get('rebin', False):
                df_last_subset = df_last[valid_cols_last]
                df_last_rebinned = rebin_age(df_last_subset, demo_config['rebin_map'])
                reference_columns = df_last_rebinned.columns.tolist()
            else:
                reference_columns = valid_cols_last
            
            for sheet_name in xls.sheet_names:
                year = parse_year(sheet_name)
                if year is None:
                    continue
                
                if demo_name == 'race_ethnicity' and year == 2013:
                    continue
                
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=0, index_col=[0, 1])
                valid_cols = [col for col in df.columns if not str(col).endswith('_E')]
                df = df[valid_cols]
                
                if demo_config.get('rebin', False):
                    df = rebin_age(df, demo_config['rebin_map'])
                
                for col in reference_columns:
                    if col not in df.columns:
                        df[col] = 0
                
                proportions = calculate_proportions(df, demo_config)
                if len(proportions) > 0:
                    for col in proportions.index:
                        if col not in results[dist]:
                            results[dist][col] = []
                        results[dist][col].append((year, proportions[col]))
        
        except FileNotFoundError:
            print(f"  Warning: File not found - {file_path}")
            continue
        except Exception as e:
            print(f"  Error processing {dist} for {demo_name}: {e}")
            continue
    
    return results

def create_mines_figure(column_name, data, demo_name):
    """Create a figure for one demographic column"""
    distances = ['1mi', '5mi', '10mi', '25mi']
    distance_labels = ['1 Mile', '5 Mile', '10 Mile', '25 Mile']
    output_base = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'distance', 'mines')
    
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
    has_data = False
    
    for i, (dist, label) in enumerate(zip(distances, distance_labels)):
        if column_name in data[dist]:
            points = sorted(data[dist][column_name])
            if points:
                years, values = zip(*points)
                ax.plot(years, values, marker='o', linestyle='-', linewidth=2, 
                       color=colors[i], label=label, markersize=4)
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
        ax.set_ylabel('Proportion', fontsize=12)
    
    ax.legend(loc='best', fontsize=9)
    plt.tight_layout()
    
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    if safe_name == 'Poverty_Rate':
        safe_name = 'Poverty'
    output_path = os.path.join(output_base, f'mines_{safe_name}_distance.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: mines_{safe_name}_distance.png")

def generate_mines_figures():
    """Generate all mines distance sensitivity figures"""
    print("="*70)
    print("Generating mines distance sensitivity figures...")
    print("="*70)
    
    output_base = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'distance', 'mines')
    os.makedirs(output_base, exist_ok=True)
    
    for demo_name, demo_config in DEMOGRAPHICS.items():
        results = process_mines_demographic(demo_name, demo_config)
        
        all_columns = set()
        for dist in ['1mi', '5mi', '10mi', '25mi']:
            all_columns.update(results[dist].keys())
        
        for column in sorted(all_columns):
            create_mines_figure(column, results, demo_name)
    
    print("✓ Mines figures complete\n")

# =============================================================================
# INTERIM STORAGE
# =============================================================================

INTERIM_FACILITY_BINS = {
    'Private': {
        'notes': [0],
        'stages': None
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

def calculate_interim_facility_proportions(site_ds, demo_config, distance, facility_type):
    """Calculate proportions for each facility type (Private, ONWN, DOE)"""
    demo_name = demo_config['file']
    demo_cols = demo_config.get('columns', [])
    
    site_sheet_years = {sheet: parse_year(sheet) for sheet in site_ds.keys()}
    site_sheet_years = {k: v for k, v in site_sheet_years.items() if v is not None}
    
    facility_config = INTERIM_FACILITY_BINS[facility_type]
    
    # For Private (no stages), accumulate by individual site
    if facility_config['stages'] is None:
        site_sums = {}
        site_names = {}
        
        for sheet_name, df in site_ds.items():
            if 'Approx Year' not in df.columns or 'Note' not in df.columns:
                continue
            
            for idx, row in df.iterrows():
                approx_year = row['Approx Year']
                note = row['Note']
                if pd.isna(approx_year) or pd.isna(note):
                    continue
                
                if note not in facility_config['notes']:
                    continue
                
                site_name = row.get('Name', f'Site {idx}')
                if pd.isna(site_name):
                    site_name = f'Site {idx}'
                site_names[idx] = site_name
                
                if isinstance(approx_year, pd.Timestamp):
                    approx_year = approx_year.year
                else:
                    approx_year = float(approx_year)
                
                if not site_sheet_years:
                    continue
                closest_sheet = min(site_sheet_years.keys(), key=lambda s: abs(site_sheet_years[s] - approx_year))
                
                closest_df = site_ds[closest_sheet]
                
                if demo_config.get('rebin', False):
                    closest_df = rebin_age(closest_df, demo_config['rebin_map'])
                    current_demo_cols = list(closest_df.columns)
                else:
                    current_demo_cols = demo_cols
                
                if idx < len(closest_df):
                    closest_row = closest_df.iloc[idx]
                    if site_name not in site_sums:
                        site_sums[site_name] = {col: 0 for col in current_demo_cols}
                    
                    for col in current_demo_cols:
                        if col in closest_row:
                            site_sums[site_name][col] = closest_row.get(col, 0)
        
        # Calculate proportions for each site
        site_props = {}
        for site_name, sums in site_sums.items():
            site_props[site_name] = {}
            
            if 'special' in demo_config:
                if demo_config['special'] == 'unemployment':
                    if 'LF-CIV' in sums and 'LF-CIV-EMPL' in sums:
                        lf_civ = sums['LF-CIV']
                        employed = sums['LF-CIV-EMPL']
                        unemployment = 1 - (employed / lf_civ) if lf_civ > 0 else 0
                        site_props[site_name]['Unemployment'] = unemployment
                elif demo_config['special'] == 'poverty_rate':
                    if 'Poverty' in sums and 'PSD' in sums:
                        poverty = sums['Poverty']
                        psd = sums['PSD']
                        poverty_rate = poverty / psd if psd > 0 else 0
                        site_props[site_name]['Poverty Rate'] = poverty_rate
            else:
                if 'exclude_from_total' in demo_config:
                    total = sum(sums[col] for col in sums.keys() if col not in demo_config['exclude_from_total'])
                else:
                    total = sum(sums.values())
                
                for col in sums.keys():
                    site_props[site_name][col] = sums[col] / total if total > 0 else 0
        
        return site_props
    
    # For ONWN/DOE (with stages), accumulate by stage
    else:
        if demo_config.get('rebin', False):
            first_sheet = list(site_ds.keys())[0]
            temp_df = site_ds[first_sheet]
            temp_rebinned = rebin_age(temp_df, demo_config['rebin_map'])
            init_demo_cols = list(temp_rebinned.columns)
        else:
            init_demo_cols = demo_cols
        
        stage_sums = {stage: {col: 0 for col in init_demo_cols} for stage in facility_config['stages'].keys()}
        
        for sheet_name, df in site_ds.items():
            if 'Approx Year' not in df.columns or 'Note' not in df.columns:
                continue
            
            for idx, row in df.iterrows():
                approx_year = row['Approx Year']
                note = row['Note']
                if pd.isna(approx_year) or pd.isna(note):
                    continue
                
                if isinstance(approx_year, pd.Timestamp):
                    approx_year = approx_year.year
                else:
                    approx_year = float(approx_year)
                
                if not site_sheet_years:
                    continue
                closest_sheet = min(site_sheet_years.keys(), key=lambda s: abs(site_sheet_years[s] - approx_year))
                
                closest_df = site_ds[closest_sheet]
                
                if demo_config.get('rebin', False):
                    closest_df = rebin_age(closest_df, demo_config['rebin_map'])
                    current_demo_cols = list(closest_df.columns)
                else:
                    current_demo_cols = demo_cols
                
                if idx < len(closest_df):
                    closest_row = closest_df.iloc[idx]
                    for stage, included_notes in facility_config['stages'].items():
                        if note in included_notes:
                            for col in current_demo_cols:
                                if col in closest_row:
                                    stage_sums[stage][col] += closest_row.get(col, 0)
        
        # Calculate proportions for each stage
        stage_props = {}
        for stage in facility_config['stages'].keys():
            stage_props[stage] = {}
            
            if 'special' in demo_config:
                if demo_config['special'] == 'unemployment':
                    if 'LF-CIV' in stage_sums[stage] and 'LF-CIV-EMPL' in stage_sums[stage]:
                        lf_civ = stage_sums[stage]['LF-CIV']
                        employed = stage_sums[stage]['LF-CIV-EMPL']
                        unemployment = 1 - (employed / lf_civ) if lf_civ > 0 else 0
                        stage_props[stage]['Unemployment'] = unemployment
                elif demo_config['special'] == 'poverty_rate':
                    if 'Poverty' in stage_sums[stage] and 'PSD' in stage_sums[stage]:
                        poverty = stage_sums[stage]['Poverty']
                        psd = stage_sums[stage]['PSD']
                        poverty_rate = poverty / psd if psd > 0 else 0
                        stage_props[stage]['Poverty Rate'] = poverty_rate
            else:
                if 'exclude_from_total' in demo_config:
                    total = sum(stage_sums[stage][col] for col in stage_sums[stage].keys() if col not in demo_config['exclude_from_total'])
                else:
                    total = sum(stage_sums[stage].values())
                
                for col in stage_sums[stage].keys():
                    stage_props[stage][col] = stage_sums[stage][col] / total if total > 0 else 0
        
        return stage_props

def process_interim_demographic(demo_name, demo_config):
    """Process one demographic across all distances and facility types"""
    distances = ['5mi', '10mi', '25mi', '50mi']
    print(f"\nProcessing interim: {demo_name}...")
    
    results = {facility: {dist: {} for dist in distances} for facility in INTERIM_FACILITY_BINS.keys()}
    
    for dist in distances:
        if dist == '50mi':
            file_path = os.path.join(BASE_DIR, 'outputs', 'demographics_by_facility', demo_name, f'interim_prop_{demo_name}_facilities.xlsx')
        else:
            dist_folder = dist.replace('mi', ' Mile')
            file_path = os.path.join(PROXIMITY_BASE, 'distance', dist_folder, demo_name, f'{dist}_interim_prop_{demo_name}.xlsx')
        
        try:
            site_ds = pd.ExcelFile(file_path)
            last_sheet = site_ds.sheet_names[-1]
            df_last = pd.read_excel(file_path, sheet_name=last_sheet)
            
            valid_cols_last = [col for col in df_last.columns if not str(col).endswith('_E') and col not in ['Approx Year', 'Note', 'Name']]
            
            if demo_config.get('rebin', False):
                df_last_rebinned = rebin_age(df_last[valid_cols_last], demo_config['rebin_map'])
                reference_columns = df_last_rebinned.columns.tolist()
            else:
                reference_columns = valid_cols_last
            
            sheet_dict = {}
            for sheet in site_ds.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet)
                for col in reference_columns:
                    if col not in df.columns:
                        df[col] = 0
                sheet_dict[sheet] = df
            
            for facility_type in INTERIM_FACILITY_BINS.keys():
                facility_props = calculate_interim_facility_proportions(sheet_dict, demo_config, dist, facility_type)
                results[facility_type][dist] = facility_props
            
        except FileNotFoundError:
            print(f"  Warning: File not found - {file_path}")
            for facility_type in INTERIM_FACILITY_BINS.keys():
                results[facility_type][dist] = {}
        except Exception as e:
            print(f"  Error processing {dist}: {e}")
            for facility_type in INTERIM_FACILITY_BINS.keys():
                results[facility_type][dist] = {}
    
    return results

def create_interim_figure(column_name, data, demo_name, facility_type):
    """Create a bar plot for one demographic column and facility type"""
    distances = ['5mi', '10mi', '25mi', '50mi']
    distance_labels = ['5 Miles', '10 Miles', '25 Miles', '50 Miles']
    output_base = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'distance', 'interim_storage')
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    all_groups = set()
    for dist in distances:
        all_groups.update(data[facility_type][dist].keys())
    
    if not all_groups:
        plt.close()
        return
    
    groups = sorted(all_groups)
    
    has_data = False
    for dist in distances:
        for group in groups:
            if column_name in data[facility_type][dist].get(group, {}):
                has_data = True
                break
        if has_data:
            break
    
    if not has_data:
        plt.close()
        return
    
    num_groups = len(groups)
    num_distances = len(distances)
    bar_width = 0.15
    x = np.arange(num_groups)
    
    colors = ['#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    for i, (dist, label) in enumerate(zip(distances, distance_labels)):
        values = []
        for group in groups:
            val = data[facility_type][dist].get(group, {}).get(column_name, 0)
            values.append(val)
        
        offset = (i - num_distances/2 + 0.5) * bar_width
        bars = ax.bar(x + offset, values, width=bar_width, label=label, color=colors[i])
        
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.3f}', ha='center', va='bottom', fontsize=7)
    
    ax.set_xticks(x)
    ax.set_xticklabels(groups, fontsize=10)
    ax.set_xlabel('Stage' if facility_type != 'Private' else 'Site', fontsize=12)
    
    if demo_name == 'employment' and column_name == 'Unemployment':
        ax.set_ylabel('Unemployment Rate (at Time of Siting)', fontsize=12)
    elif demo_name == 'poverty' and column_name == 'Poverty Rate':
        ax.set_ylabel('Poverty Rate (at Time of Siting)', fontsize=12)
    else:
        demo_label = get_label(column_name)
        ax.set_ylabel(f'{demo_label} Proportion (at Time of Siting)', fontsize=12)
    
    ax.legend(loc='best', fontsize=9)
    plt.tight_layout()
    
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    if safe_name == 'Poverty_Rate':
        safe_name = 'Poverty'
    output_path = os.path.join(output_base, facility_type, f'interim_{facility_type}_{safe_name}_distance.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {facility_type}/interim_{facility_type}_{safe_name}_distance.png")

def generate_interim_figures():
    """Generate all interim storage distance sensitivity figures"""
    print("="*70)
    print("Generating interim storage distance sensitivity figures...")
    print("="*70)
    
    output_base = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'distance', 'interim_storage')
    os.makedirs(os.path.join(output_base, 'Private'), exist_ok=True)
    os.makedirs(os.path.join(output_base, 'ONWN'), exist_ok=True)
    os.makedirs(os.path.join(output_base, 'DOE'), exist_ok=True)
    
    for demo_name, demo_config in DEMOGRAPHICS.items():
        results = process_interim_demographic(demo_name, demo_config)
        
        for facility_type in INTERIM_FACILITY_BINS.keys():
            all_columns = set()
            for dist in ['5mi', '10mi', '25mi', '50mi']:
                for group_data in results[facility_type][dist].values():
                    all_columns.update(group_data.keys())
            
            for column in sorted(all_columns):
                create_interim_figure(column, results, demo_name, facility_type)
    
    print("✓ Interim storage figures complete\n")

# =============================================================================
# REPOSITORIES
# =============================================================================

REPO_STAGE_BINS = {
    'Stage 1': [1, 2, 3, 4],
    'Stage 2': [2, 3, 4],
    'Stage 3': [3, 4],
    'Stage 4': [4]
}

def calculate_repo_stage_proportions(site_ds, demo_config, distance):
    """Calculate proportions for each stage bin using cumulative Note values"""
    demo_name = demo_config['file']
    race_bins = demo_config.get('columns', [])
    
    site_sheet_years = {sheet: parse_year(sheet) for sheet in site_ds.keys()}
    site_sheet_years = {k: v for k, v in site_sheet_years.items() if v is not None}
    
    stage_sums = {stage: {col: 0 for col in race_bins} for stage in REPO_STAGE_BINS.keys()}
    
    for sheet_name, df in site_ds.items():
        if 'Approx Year' not in df.columns or 'Note' not in df.columns:
            continue
        
        if demo_config.get('rebin', False):
            df = rebin_age(df, demo_config['rebin_map'])
            race_bins = list(df.columns)
            race_bins = [col for col in race_bins if col not in ['Approx Year', 'Note'] and not str(col).endswith('_E')]
        
        for idx, row in df.iterrows():
            approx_year = row['Approx Year']
            note = row['Note']
            if pd.isna(approx_year) or pd.isna(note):
                continue
            
            if isinstance(approx_year, pd.Timestamp):
                approx_year = approx_year.year
            else:
                approx_year = float(approx_year)
            
            if not site_sheet_years:
                continue
            closest_sheet = min(site_sheet_years.keys(), key=lambda s: abs(site_sheet_years[s] - approx_year))
            
            closest_df = site_ds[closest_sheet]
            
            if demo_config.get('rebin', False):
                closest_df = rebin_age(closest_df, demo_config['rebin_map'])
            
            if idx < len(closest_df):
                closest_row = closest_df.iloc[idx]
                for stage, included_notes in REPO_STAGE_BINS.items():
                    if note in included_notes:
                        for col in race_bins:
                            if col in closest_row:
                                stage_sums[stage][col] += closest_row.get(col, 0)
    
    # Calculate proportions for each stage
    stage_props = {}
    for stage in REPO_STAGE_BINS.keys():
        if 'special' in demo_config:
            if demo_config['special'] == 'unemployment':
                if 'LF-CIV' in stage_sums[stage] and 'LF-CIV-EMPL' in stage_sums[stage]:
                    lf_civ = stage_sums[stage]['LF-CIV']
                    employed = stage_sums[stage]['LF-CIV-EMPL']
                    unemployment = 1 - (employed / lf_civ) if lf_civ > 0 else 0
                    stage_props[stage] = {'Unemployment': unemployment}
                else:
                    stage_props[stage] = {}
            elif demo_config['special'] == 'poverty_rate':
                if 'Poverty' in stage_sums[stage] and 'PSD' in stage_sums[stage]:
                    poverty = stage_sums[stage]['Poverty']
                    psd = stage_sums[stage]['PSD']
                    poverty_rate = poverty / psd if psd > 0 else 0
                    stage_props[stage] = {'Poverty Rate': poverty_rate}
                else:
                    stage_props[stage] = {}
        else:
            if 'exclude_from_total' in demo_config:
                total_stage = sum(stage_sums[stage][col] for col in race_bins if col not in demo_config['exclude_from_total'])
            else:
                total_stage = sum(stage_sums[stage][col] for col in race_bins)
            
            stage_props[stage] = {}
            for col in race_bins:
                stage_props[stage][col] = stage_sums[stage][col] / total_stage if total_stage > 0 else 0
    
    return stage_props

def process_repo_demographic(demo_name, demo_config):
    """Process one demographic across all distances"""
    distances = ['5mi', '10mi', '25mi', '50mi']
    print(f"\nProcessing repositories: {demo_name}...")
    
    results = {dist: {} for dist in distances}
    
    for dist in distances:
        if dist == '50mi':
            file_path = os.path.join(BASE_DIR, 'outputs', 'demographics_by_facility', demo_name, f'repository_{demo_name}_facilities.xlsx')
        else:
            dist_folder = dist.replace('mi', ' Mile')
            file_path = os.path.join(PROXIMITY_BASE, 'distance', dist_folder, demo_name, f'{dist}_repo_prop_{demo_name}.xlsx')
        
        try:
            site_ds = pd.ExcelFile(file_path)
            last_sheet = site_ds.sheet_names[-1]
            df_last = pd.read_excel(file_path, sheet_name=last_sheet)
            
            valid_cols_last = [col for col in df_last.columns if not str(col).endswith('_E') and col not in ['Approx Year', 'Note']]
            
            if demo_config.get('rebin', False):
                df_last_rebinned = rebin_age(df_last[valid_cols_last], demo_config['rebin_map'])
                reference_columns = df_last_rebinned.columns.tolist()
            else:
                reference_columns = valid_cols_last
            
            sheet_dict = {}
            for sheet in site_ds.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet)
                for col in reference_columns:
                    if col not in df.columns:
                        df[col] = 0
                sheet_dict[sheet] = df
            
            stage_props = calculate_repo_stage_proportions(sheet_dict, demo_config, dist)
            results[dist] = stage_props
            
        except FileNotFoundError:
            print(f"  Warning: File not found - {file_path}")
            results[dist] = {stage: {} for stage in REPO_STAGE_BINS.keys()}
        except Exception as e:
            print(f"  Error processing {dist}: {e}")
            results[dist] = {stage: {} for stage in REPO_STAGE_BINS.keys()}
    
    return results

def create_repo_figure(column_name, data, demo_name):
    """Create a bar plot for one demographic column showing stages and distances"""
    distances = ['5mi', '10mi', '25mi', '50mi']
    distance_labels = ['5 Miles', '10 Miles', '25 Miles', '50 Miles']
    output_base = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'distance', 'repositories')
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    has_data = False
    for dist in distances:
        for stage in REPO_STAGE_BINS.keys():
            if column_name in data[dist].get(stage, {}):
                has_data = True
                break
        if has_data:
            break
    
    if not has_data:
        plt.close()
        return
    
    num_stages = len(REPO_STAGE_BINS)
    num_distances = len(distances)
    bar_width = 0.15
    x = np.arange(num_stages)
    
    colors = ['#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    for i, (dist, label) in enumerate(zip(distances, distance_labels)):
        values = []
        for stage in REPO_STAGE_BINS.keys():
            val = data[dist].get(stage, {}).get(column_name, 0)
            values.append(val)
        
        offset = (i - num_distances/2 + 0.5) * bar_width
        bars = ax.bar(x + offset, values, width=bar_width, label=label, color=colors[i])
        
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.3f}', ha='center', va='bottom', fontsize=7)
    
    ax.set_xticks(x)
    ax.set_xticklabels(REPO_STAGE_BINS.keys(), fontsize=10)
    ax.set_xlabel('Development Stage', fontsize=12)
    
    if demo_name == 'employment' and column_name == 'Unemployment':
        ax.set_ylabel('Unemployment Rate (at Time of Siting)', fontsize=12)
    elif demo_name == 'poverty' and column_name == 'Poverty Rate':
        ax.set_ylabel('Poverty Rate (at Time of Siting)', fontsize=12)
    else:
        demo_label = get_label(column_name)
        ax.set_ylabel(f'{demo_label} Proportion (at Time of Siting)', fontsize=12)
    
    ax.legend(loc='best', fontsize=9)
    plt.tight_layout()
    
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    if safe_name == 'Poverty_Rate':
        safe_name = 'Poverty'
    output_path = os.path.join(output_base, f'repository_{safe_name}_distance.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: repositories_{safe_name}_distance.png")

def generate_repo_figures():
    """Generate all repository distance sensitivity figures"""
    print("="*70)
    print("Generating repository distance sensitivity figures...")
    print("="*70)
    
    output_base = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'distance', 'repositories')
    os.makedirs(output_base, exist_ok=True)
    
    for demo_name, demo_config in DEMOGRAPHICS.items():
        results = process_repo_demographic(demo_name, demo_config)
        
        all_columns = set()
        for dist in ['5mi', '10mi', '25mi', '50mi']:
            for stage in REPO_STAGE_BINS.keys():
                all_columns.update(results[dist].get(stage, {}).keys())
        
        for column in sorted(all_columns):
            create_repo_figure(column, results, demo_name)
    
    print("✓ Repository figures complete\n")

# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("DISTANCE SENSITIVITY FIGURE GENERATOR")
    print("Generating all distance sensitivity figures for all facility types")
    print("="*70 + "\n")
    
    # Generate figures for each facility type
    generate_frontend_figures()
    generate_reactor_figures()
    generate_mines_figures()
    generate_interim_figures()
    generate_repo_figures()
    
    print("="*70)
    print("✓ ALL DISTANCE SENSITIVITY FIGURES GENERATED SUCCESSFULLY!")
    print("="*70)
