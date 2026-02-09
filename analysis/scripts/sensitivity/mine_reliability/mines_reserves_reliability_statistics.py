"""
Analyze demographic proportions near mines across different reliability levels.
Generates figures showing how demographic composition changes with mine reliability.
Reliability bins: [4,5,6], [7,8], [9,10], plus overall mines and reserves for comparison.
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

# Create output directory
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
BASE_PATH = os.path.join(BASE_DIR, 'analysis', 'outputs', 'sensitivity_analysis', 'mine_reliability')
DEMOGRAPHICS_PATH = os.path.join(BASE_PATH, 'demographics')
os.makedirs(BASE_PATH, exist_ok=True)

# Define reliability bins
reliability_bins = {
    'Low (4-6)': [4, 5, 6],
    'Medium (7-8)': [7, 8],
    'High (9-10)': [9, 10]
}

# Define demographics and their special handling
demographics = {
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
    demo_name = demographic_config['file']
    
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
        # For race_ethnicity: exclude H from total
        total_cols = [col for col in totals.index if col not in demographic_config['exclude_from_total']]
        population_total = totals[total_cols].sum()
        proportions = totals / population_total
    else:
        population_total = totals.sum()
        proportions = totals / population_total
    
    return proportions

def process_demographic(demo_name, demo_config):
    """Process one demographic across all reliability bins"""
    print(f"\nProcessing {demo_name}...")
    
    # Load pre-calculated demographic data from Demographics folder
    mines_file = f'{DEMOGRAPHICS_PATH}/mines_{demo_name}.xlsx'
    reserves_file = f'{DEMOGRAPHICS_PATH}/reserves_{demo_name}.xlsx'
    
    results = {
        'reliability_bins': {bin_name: {} for bin_name in reliability_bins.keys()},
        'overall': {},
        'reserves': {}
    }
    
    # Load mines demographic data
    print(f"  Loading mines data from {mines_file}...")
    try:
        mines_xls = pd.ExcelFile(mines_file)
        print(f"    Found {len(mines_xls.sheet_names)} year sheets for mines")
        
        for sheet_name in mines_xls.sheet_names:
            year = parse_year(sheet_name)
            if year is None:
                continue
            
            # Exclude 2013 for race_ethnicity demographic
            if demo_name == 'race_ethnicity' and year == 2013:
                continue
            
            print(f"    Processing mines year {year}...", end=' ')
            
            # Read mines data with MultiIndex (ICF_ID, RELIABILIT)
            mines_df = pd.read_excel(mines_file, sheet_name=sheet_name, index_col=[0, 1])
            
            # Filter out columns ending with _E
            valid_cols = [col for col in mines_df.columns if not str(col).endswith('_E')]
            mines_df = mines_df[valid_cols]
            
            # Handle age rebinning
            if demo_config.get('rebin', False):
                mines_df = rebin_age(mines_df, demo_config['rebin_map'])
            
            # Process each reliability bin
            for bin_name, reliability_values in reliability_bins.items():
                # Filter for this reliability bin
                reliabilit_vals = mines_df.index.get_level_values('RELIABILIT')
                mask = reliabilit_vals.isin(reliability_values)
                df_bin = mines_df[mask]
                
                if not df_bin.empty:
                    proportions = calculate_proportions(df_bin, demo_config)
                    if len(proportions) > 0:
                        for col in proportions.index:
                            if col not in results['reliability_bins'][bin_name]:
                                results['reliability_bins'][bin_name][col] = []
                            results['reliability_bins'][bin_name][col].append((year, proportions[col]))
            
            # Process overall mines (all reliability levels)
            if not mines_df.empty:
                proportions = calculate_proportions(mines_df, demo_config)
                if len(proportions) > 0:
                    for col in proportions.index:
                        if col not in results['overall']:
                            results['overall'][col] = []
                        results['overall'][col].append((year, proportions[col]))
            
            print("✓")
    
    except FileNotFoundError:
        print(f"  Warning: File not found - {mines_file}")
    except Exception as e:
        print(f"  Error processing mines for {demo_name}: {e}")
    
    # Load reserves demographic data
    print(f"  Loading reserves data from {reserves_file}...")
    try:
        reserves_xls = pd.ExcelFile(reserves_file)
        print(f"    Found {len(reserves_xls.sheet_names)} year sheets for reserves")
        
        for sheet_name in reserves_xls.sheet_names:
            year = parse_year(sheet_name)
            if year is None:
                continue
            
            # Exclude 2013 for race_ethnicity demographic
            if demo_name == 'race_ethnicity' and year == 2013:
                continue
            
            print(f"    Processing reserves year {year}...", end=' ')
            
            # Read reserves data (single row indexed as 'Reserves')
            reserves_df = pd.read_excel(reserves_file, sheet_name=sheet_name, index_col=0)
            
            # Filter out columns ending with _E
            valid_cols = [col for col in reserves_df.columns if not str(col).endswith('_E')]
            reserves_df = reserves_df[valid_cols]
            
            # Handle age rebinning
            if demo_config.get('rebin', False):
                reserves_df = rebin_age(reserves_df, demo_config['rebin_map'])
            
            if not reserves_df.empty:
                proportions = calculate_proportions(reserves_df, demo_config)
                if len(proportions) > 0:
                    for col in proportions.index:
                        if col not in results['reserves']:
                            results['reserves'][col] = []
                        results['reserves'][col].append((year, proportions[col]))
            
            print("✓")
    
    except FileNotFoundError:
        print(f"  Warning: File not found - {reserves_file}")
    except Exception as e:
        print(f"  Error processing reserves for {demo_name}: {e}")
    
    print(f"  ✓ Completed {demo_name}")
    return results

def create_figure(column_name, data, demo_name):
    """Create a figure for one demographic column"""
    print(f"    Creating figure for {column_name}...", end=' ')
    fig, ax = plt.subplots(figsize=(10, 6))
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    has_data = False
    
    # Plot reliability bins
    for i, bin_name in enumerate(reliability_bins.keys()):
        if column_name in data['reliability_bins'][bin_name]:
            points = sorted(data['reliability_bins'][bin_name][column_name])
            if points:
                years, values = zip(*points)
                ax.plot(years, values, marker='o', linestyle='-', linewidth=2, 
                       color=colors[i], label=f'Reliability {bin_name}', markersize=4)
                has_data = True
    
    # Plot overall mines
    if column_name in data['overall']:
        points = sorted(data['overall'][column_name])
        if points:
            years, values = zip(*points)
            ax.plot(years, values, marker='s', linestyle='--', linewidth=2, 
                   color=colors[3], label='Overall Mines', markersize=4)
            has_data = True
    
    # Plot reserves
    if column_name in data['reserves']:
        points = sorted(data['reserves'][column_name])
        if points:
            years, values = zip(*points)
            ax.plot(years, values, marker='^', linestyle=':', linewidth=2, 
                   color=colors[4], label='Reserves', markersize=4)
            has_data = True
    
    # Only save if there's actual data to plot
    if not has_data:
        plt.close()
        print("(no data, skipped)")
        return
    
    # Format plot
    ax.set_xlabel('Year', fontsize=12)
    
    # Set y-label based on demographic type
    if demo_name == 'employment' and column_name == 'Unemployment':
        ax.set_ylabel('Unemployment Rate', fontsize=12)
    elif demo_name == 'poverty' and column_name == 'Poverty Rate':
        ax.set_ylabel('Poverty Rate', fontsize=12)
    else:
        demo_label = get_label(column_name)
        ax.set_ylabel(f'{demo_label} Proportion', fontsize=12)
    
    ax.legend(loc='best', fontsize=9)
    
    plt.tight_layout()
    
    # Save figure with new naming convention: mines_{demographic}_reliability
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    if safe_name == 'Poverty_Rate':
        safe_name = 'Poverty'
    output_path = os.path.join(BASE_PATH, f'mines_{safe_name}_reliability.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print("✓")

# Main processing loop
print("="*70)
print("Generating mine reliability sensitivity figures...")
print("="*70)

for demo_name, demo_config in demographics.items():
    print(f"\n{'='*70}")
    print(f"Processing demographic: {demo_name.upper()}")
    print(f"{'='*70}")
    results = process_demographic(demo_name, demo_config)
    
    print(f"\n  Creating figures for {demo_name}...")
    # Get all unique columns across all bins, overall, and reserves
    all_columns = set()
    for bin_name in reliability_bins.keys():
        all_columns.update(results['reliability_bins'][bin_name].keys())
    all_columns.update(results['overall'].keys())
    all_columns.update(results['reserves'].keys())
    
    # Create a figure for each column
    print(f"  Generating {len(all_columns)} figures...")
    for column in sorted(all_columns):
        create_figure(column, results, demo_name)
    print(f"  ✓ Completed {len(all_columns)} figures for {demo_name}")

print("\n" + "="*70)
print("✓ All mine reliability sensitivity figures generated successfully!")
print("="*70)


