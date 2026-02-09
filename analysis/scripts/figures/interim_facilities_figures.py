"""
Generate demographic figures for Interim Storage (Proposed) facilities.
Includes overall, private (Note=0), ONWN stages (Note=1,2,3), and DOE stages (Note=4,5,6) with cumulative binning.
ONWN Stages: 1 (includes 1,2,3), 2 (includes 2,3), 3 (only 3)
DOE Stages: 1 (includes 4,5,6), 2 (includes 5,6), 3 (only 6)

Outputs to: analysis/outputs/demographics_by_facility/{demographic}/figures/
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import numpy as np
import re

# Get absolute paths
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
input_base = os.path.join(base_dir, 'analysis', 'outputs', 'demographics_by_facility')
compiled_base = os.path.join(base_dir, 'demographic_data', 'compiled')

# Set plotting style
sns.set_style("white")
plt.rcParams['figure.figsize'] = (12, 8)

# Label mapping for expanded demographic names
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
    'LF-CIV-EMPL': 'Employed',
    'Poverty': 'In Poverty',
    'Unemployment': 'Unemployment Rate'
}

def get_label(col):
    """Get expanded label for column name"""
    return LABEL_MAP.get(col, col)

FACILITY = 'interim_prop'

# Define demographics and their special handling
DEMOGRAPHIC_CONFIG = {
    'age': {
        'rebin': True,
        'rebin_map': {
            '<19': ['<5', '5-14', '15-19'],
            '20-34': ['20-24', '25-34'],
            '35-59': ['35-44', '45-54', '55-59'],
            '60+': ['60-64', '65-74', '75-84', '85+']
        },
        'baseline_file': 'age_combined.xlsx',
        'baseline_year': 1990
    },
    'education': {
        'columns': ['<9', '<B', 'B+'],
        'baseline_file': 'education_compiled.xlsx',
        'baseline_year': 1990
    },
    'employment': {
        'special': 'unemployment',
        'columns': ['LF-CIV', 'LF-CIV-EMPL'],
        'baseline_file': 'employment_compiled.xlsx',
        'baseline_year': 1990
    },
    'poverty': {
        'special': 'poverty_rate',
        'columns': ['Poverty', 'PSD'],
        'baseline_file': 'poverty_compiled.xlsx',
        'baseline_year': 1990
    },
    'race_ethnicity': {
        'exclude_from_total': ['H'],
        'columns': ['W', 'B', 'AIAN', 'AAPI', 'O', '2+', 'H'],
        'baseline_file': 'race_ethnicity_compiled.xlsx',
        'baseline_year': 1990
    },
    'sex': {
        'columns': ['M', 'F'],
        'baseline_file': 'sex_compiled.xlsx',
        'baseline_year': 1990
    }
}

# Define ONWN stage bins with cumulative inclusion
ONWN_STAGE_BINS = {
    '1': [1, 2, 3],
    '2': [2, 3],
    '3': [3]
}

# Define DOE stage bins with cumulative inclusion
DOE_STAGE_BINS = {
    '1': [4, 5, 6],
    '2': [5, 6],
    '3': [6]
}

DEMOGRAPHICS = list(DEMOGRAPHIC_CONFIG.keys())

print("="*80)
print("GENERATING INTERIM STORAGE DEMOGRAPHIC FIGURES")
print("="*80)

def parse_sheet_year(sheet_name):
    """Parse year from sheet name, handling ranges by taking the mean."""
    sheet_str = str(sheet_name)
    
    # Handle range format like "2006-2010"
    if '-' in sheet_str:
        years = re.findall(r'\d{4}', sheet_str)
        if len(years) == 2:
            return (int(years[0]) + int(years[1])) / 2
    
    # Handle single year
    year_match = re.search(r'\d{4}', sheet_str)
    if year_match:
        return int(year_match.group())
    
    return None

def load_facility_data_all_years(demographic_name):
    """Load demographic data for all years"""
    file_path = os.path.join(input_base, demographic_name, f"{FACILITY}_{demographic_name}_facilities.xlsx")
    
    if not os.path.exists(file_path):
        print(f"  ✗ File not found: {file_path}")
        return None
    
    xls = pd.ExcelFile(file_path)
    data_by_year = {}
    
    for sheet_name in xls.sheet_names:
        year = parse_sheet_year(sheet_name)
        if year is not None:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            data_by_year[sheet_name] = {'year': year, 'df': df}
    
    return data_by_year

def load_national_data(demographic_name, year):
    """Load national demographic data for specific year"""
    config = DEMOGRAPHIC_CONFIG.get(demographic_name, {})
    file_name = config.get('baseline_file', f"{demographic_name}_compiled.xlsx")
    file_path = os.path.join(compiled_base, file_name)
    
    if not os.path.exists(file_path):
        print(f"  ✗ National data not found: {file_path}")
        return None
    
    try:
        df = pd.read_excel(file_path, sheet_name=str(year))
        return df
    except Exception as e:
        print(f"  ✗ Could not load year {year}: {e}")
        return None

def rebin_age_columns(data, rebin_map):
    """Rebin age columns according to mapping"""
    rebinned_data = {}
    
    for new_bin, orig_bins in rebin_map.items():
        total = 0
        for orig_bin in orig_bins:
            if orig_bin in data:
                total += data[orig_bin]
        rebinned_data[new_bin] = total
    
    return pd.Series(rebinned_data)

def calculate_cumulative_demographics(data_by_year, demographic_name, note_filter=None):
    """Calculate demographics for facilities based on Approx Year and optional Note filter"""
    config = DEMOGRAPHIC_CONFIG.get(demographic_name, {})
    
    # Build a mapping from sheet name to parsed year
    sheet_years = {sheet: info['year'] for sheet, info in data_by_year.items()}
    
    # Identify demographic columns from first sheet
    first_sheet = list(data_by_year.keys())[0]
    first_df = data_by_year[first_sheet]['df']
    meta_cols = ['Name', 'FID', 'Type', 'Capacity', 'Note', 'Start', 'Stop', 'Approx Year']
    demo_cols = [col for col in first_df.columns if col not in meta_cols and not col.endswith('_E')]
    
    # Accumulate demographics
    sums = {col: 0 for col in demo_cols}
    
    # Process each facility
    for sheet_name, data in data_by_year.items():
        df = data['df']
        if 'Approx Year' not in df.columns:
            continue
        
        for idx, row in df.iterrows():
            approx_year = row.get('Approx Year')
            note = row.get('Note')
            
            if pd.isna(approx_year):
                continue
            
            # Apply note filter if provided
            if note_filter is not None:
                if callable(note_filter):
                    if not note_filter(note):
                        continue
                elif note not in note_filter:
                    continue
            
            # Handle Timestamp by extracting the year
            if isinstance(approx_year, pd.Timestamp):
                approx_year = approx_year.year
            else:
                approx_year = float(approx_year)
            
            # Find the closest sheet year
            closest_sheet = min(sheet_years.keys(), key=lambda s: abs(sheet_years[s] - approx_year))
            closest_df = data_by_year[closest_sheet]['df']
            
            # Get demographics from closest year sheet
            if idx < len(closest_df):
                closest_row = closest_df.iloc[idx]
                
                # Add to sums
                for col in demo_cols:
                    val = closest_row.get(col, 0)
                    if pd.notna(val):
                        sums[col] += val
    
    return sums, demo_cols

def plot_demographic_comparison(demographic_name):
    """Create bar charts comparing interim storage demographics to national baseline"""
    print(f"\n  Processing {FACILITY} - {demographic_name}...")
    
    config = DEMOGRAPHIC_CONFIG.get(demographic_name, {})
    
    # Load facility data
    facility_data = load_facility_data_all_years(demographic_name)
    if facility_data is None:
        return
    
    # Load national data for baseline year
    baseline_year = config.get('baseline_year', 1990)
    national_data = load_national_data(demographic_name, baseline_year)
    if national_data is None:
        return
    
    # Filter facility data to only include sheets >= baseline_year
    filtered_facility_data = {
        sheet: data for sheet, data in facility_data.items() 
        if data['year'] >= baseline_year
    }
    
    print(f"    Loaded {len(facility_data)} year sheets for facilities (using {len(filtered_facility_data)} >= {baseline_year})")
    print(f"    Loaded national data for {baseline_year}")
    
    # Calculate cumulative demographics for overall
    overall_sums, demo_cols = calculate_cumulative_demographics(filtered_facility_data, demographic_name)
    
    # Calculate for private (Note = 0)
    private_sums, _ = calculate_cumulative_demographics(filtered_facility_data, demographic_name, 
                                                        note_filter=lambda n: n == 0 if pd.notna(n) else False)
    
    # Calculate for ONWN stages
    onwn_stage_sums = {}
    for stage, included_notes in ONWN_STAGE_BINS.items():
        stage_sums, _ = calculate_cumulative_demographics(filtered_facility_data, demographic_name,
                                                          note_filter=included_notes)
        onwn_stage_sums[stage] = stage_sums
    
    # Calculate for DOE stages
    doe_stage_sums = {}
    for stage, included_notes in DOE_STAGE_BINS.items():
        stage_sums, _ = calculate_cumulative_demographics(filtered_facility_data, demographic_name,
                                                          note_filter=included_notes)
        doe_stage_sums[stage] = stage_sums
    
    # Apply age rebinning if needed
    if config.get('rebin', False):
        rebin_map = config['rebin_map']
        overall_sums = rebin_age_columns(pd.Series(overall_sums), rebin_map)
        private_sums = rebin_age_columns(pd.Series(private_sums), rebin_map)
        for stage in onwn_stage_sums.keys():
            onwn_stage_sums[stage] = rebin_age_columns(pd.Series(onwn_stage_sums[stage]), rebin_map)
        for stage in doe_stage_sums.keys():
            doe_stage_sums[stage] = rebin_age_columns(pd.Series(doe_stage_sums[stage]), rebin_map)
        demo_cols = list(rebin_map.keys())
        
        # Rebin national data
        natl_sums = {}
        for new_bin, orig_bins in rebin_map.items():
            total = 0
            for orig_bin in orig_bins:
                if orig_bin in national_data.columns:
                    total += national_data[orig_bin].sum()
            natl_sums[new_bin] = total
    else:
        # Calculate national sums
        natl_sums = {}
        for col in demo_cols:
            if col in national_data.columns:
                natl_sums[col] = national_data[col].sum()
    
    # Handle special cases for proportions
    if 'special' in config:
        if config['special'] == 'unemployment':
            if 'LF-CIV' in overall_sums and 'LF-CIV-EMPL' in overall_sums and overall_sums['LF-CIV'] > 0:
                overall_props = {'Unemployment': 1 - (overall_sums['LF-CIV-EMPL'] / overall_sums['LF-CIV'])}
                private_props = {'Unemployment': 1 - (private_sums['LF-CIV-EMPL'] / private_sums['LF-CIV'])} if private_sums.get('LF-CIV', 0) > 0 else {'Unemployment': 0}
                private_total = private_sums.get('LF-CIV', 0)  # Track if there's private data
                onwn_stage_props = {}
                for stage, sums in onwn_stage_sums.items():
                    onwn_stage_props[stage] = {'Unemployment': 1 - (sums['LF-CIV-EMPL'] / sums['LF-CIV'])} if sums.get('LF-CIV', 0) > 0 else {'Unemployment': 0}
                doe_stage_props = {}
                for stage, sums in doe_stage_sums.items():
                    doe_stage_props[stage] = {'Unemployment': 1 - (sums['LF-CIV-EMPL'] / sums['LF-CIV'])} if sums.get('LF-CIV', 0) > 0 else {'Unemployment': 0}
                natl_props = {'Unemployment': 1 - (natl_sums['LF-CIV-EMPL'] / natl_sums['LF-CIV'])} if natl_sums.get('LF-CIV', 0) > 0 else {'Unemployment': 0}
                demo_cols = ['Unemployment']
            else:
                print(f"    ✗ Missing employment data, skipping {demographic_name}")
                return
        elif config['special'] == 'poverty_rate':
            if 'Poverty' in overall_sums and 'PSD' in overall_sums and overall_sums['PSD'] > 0:
                overall_props = {'Poverty Rate': overall_sums['Poverty'] / overall_sums['PSD']}
                private_props = {'Poverty Rate': private_sums['Poverty'] / private_sums['PSD']} if private_sums.get('PSD', 0) > 0 else {'Poverty Rate': 0}
                private_total = private_sums.get('PSD', 0)  # Track if there's private data
                onwn_stage_props = {}
                for stage, sums in onwn_stage_sums.items():
                    onwn_stage_props[stage] = {'Poverty Rate': sums['Poverty'] / sums['PSD']} if sums.get('PSD', 0) > 0 else {'Poverty Rate': 0}
                doe_stage_props = {}
                for stage, sums in doe_stage_sums.items():
                    doe_stage_props[stage] = {'Poverty Rate': sums['Poverty'] / sums['PSD']} if sums.get('PSD', 0) > 0 else {'Poverty Rate': 0}
                natl_props = {'Poverty Rate': natl_sums['Poverty'] / natl_sums['PSD']} if natl_sums.get('PSD', 0) > 0 else {'Poverty Rate': 0}
                demo_cols = ['Poverty Rate']
            else:
                print(f"    ✗ Missing poverty data, skipping {demographic_name}")
                return
    else:
        # Calculate proportions
        if 'exclude_from_total' in config:
            # For race_ethnicity: exclude H from total
            total_cols = [col for col in demo_cols if col not in config['exclude_from_total']]
            
            overall_total = sum(overall_sums[col] for col in total_cols)
            overall_props = {col: overall_sums[col] / overall_total if overall_total > 0 else 0 for col in demo_cols}
            
            private_total = sum(private_sums[col] for col in total_cols)
            private_props = {col: private_sums[col] / private_total if private_total > 0 else 0 for col in demo_cols}
            
            onwn_stage_props = {}
            for stage, sums in onwn_stage_sums.items():
                stage_total = sum(sums[col] for col in total_cols)
                onwn_stage_props[stage] = {col: sums[col] / stage_total if stage_total > 0 else 0 for col in demo_cols}
            
            doe_stage_props = {}
            for stage, sums in doe_stage_sums.items():
                stage_total = sum(sums[col] for col in total_cols)
                doe_stage_props[stage] = {col: sums[col] / stage_total if stage_total > 0 else 0 for col in demo_cols}
            
            natl_total = sum(natl_sums[col] for col in total_cols)
            natl_props = {col: natl_sums[col] / natl_total if natl_total > 0 else 0 for col in demo_cols}
        else:
            # Standard: sum all columns for total
            overall_total = sum(overall_sums[col] for col in demo_cols)
            overall_props = {col: overall_sums[col] / overall_total if overall_total > 0 else 0 for col in demo_cols}
            
            private_total = sum(private_sums[col] for col in demo_cols)
            private_props = {col: private_sums[col] / private_total if private_total > 0 else 0 for col in demo_cols}
            
            onwn_stage_props = {}
            for stage, sums in onwn_stage_sums.items():
                stage_total = sum(sums[col] for col in demo_cols)
                onwn_stage_props[stage] = {col: sums[col] / stage_total if stage_total > 0 else 0 for col in demo_cols}
            
            doe_stage_props = {}
            for stage, sums in doe_stage_sums.items():
                stage_total = sum(sums[col] for col in demo_cols)
                doe_stage_props[stage] = {col: sums[col] / stage_total if stage_total > 0 else 0 for col in demo_cols}
            
            natl_total = sum(natl_sums.values())
            natl_props = {col: natl_sums[col] / natl_total if natl_total > 0 else 0 for col in demo_cols}
    
    # Create output directory
    output_dir = os.path.join(input_base, demographic_name, 'figures')
    os.makedirs(output_dir, exist_ok=True)
    
    bar_width = 0.35
    x = list(range(len(demo_cols)))
    
    # Plot 1: Overall vs National
    fig, ax = plt.subplots(figsize=(10, 7))
    bars1 = ax.bar([i - bar_width/2 for i in x], [overall_props[col] for col in demo_cols],
                    width=bar_width, label='Near interim storage at time of proposal', color='tab:blue')
    bars2 = ax.bar([i + bar_width/2 for i in x], [natl_props[col] for col in demo_cols],
                    width=bar_width, label=f'National ({baseline_year})', color='tab:orange')
    
    # Add data labels
    for bar in bars1:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.3f}', ha='center', va='bottom', fontsize=9)
    for bar in bars2:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.3f}', ha='center', va='bottom', fontsize=9)
    
    ax.set_xticks(x)
    ax.set_xticklabels([get_label(col) for col in demo_cols])
    # Determine y-label based on demographic type
    if demographic_name == 'poverty':
        ylabel = 'Poverty Rate'
    elif demographic_name == 'employment':
        ylabel = 'Unemployment Rate'
    else:
        ylabel = 'Proportion Relative to Total Population'
    ax.set_ylabel(ylabel)
    ax.legend(loc='best')
    plt.tight_layout()
    
    output_file = os.path.join(output_dir, f'{FACILITY}_{demographic_name}_overall.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"    ✓ Saved: {output_file}")
    
    # Plot 2: Private vs National
    if private_total > 0:
        fig, ax = plt.subplots(figsize=(10, 7))
        bars1 = ax.bar([i - bar_width/2 for i in x], [private_props[col] for col in demo_cols],
                        width=bar_width, label='Near Private interim storage at time of proposal', color='tab:blue')
        bars2 = ax.bar([i + bar_width/2 for i in x], [natl_props[col] for col in demo_cols],
                        width=bar_width, label=f'National ({baseline_year})', color='tab:orange')
        
        # Add data labels
        for bar in bars1:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.3f}', ha='center', va='bottom', fontsize=9)
        for bar in bars2:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.3f}', ha='center', va='bottom', fontsize=9)
        
        ax.set_xticks(x)
        ax.set_xticklabels([get_label(col) for col in demo_cols])
        # Determine y-label based on demographic type
        if demographic_name == 'poverty':
            ylabel = 'Poverty Rate'
        elif demographic_name == 'employment':
            ylabel = 'Unemployment Rate'
        else:
            ylabel = 'Proportion Relative to Total Population'
        ax.set_ylabel(ylabel)
        ax.legend(loc='best')
        plt.tight_layout()
        
        output_file_private = os.path.join(output_dir, f'{FACILITY}_{demographic_name}_private.png')
        plt.savefig(output_file_private, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"    ✓ Saved (private): {output_file_private}")
    
    # Plot 3: ONWN stages vs National
    fig, ax = plt.subplots(figsize=(12, 8))
    bar_width_stage = 0.2
    x_stage = list(range(len(demo_cols)))
    colors_stage = ['tab:blue', 'tab:cyan', 'tab:green', 'tab:orange']
    
    # Plot bars for each ONWN stage
    for i, stage in enumerate(['1', '2', '3']):
        offset = (i - 1.5) * bar_width_stage
        if stage in onwn_stage_props:
            stage_vals = [onwn_stage_props[stage][col] for col in demo_cols]
            bars = ax.bar([j + offset for j in x_stage], stage_vals, width=bar_width_stage,
                           label=f'ONWN Stage {stage}', color=colors_stage[i])
            
            # Add data labels
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.3f}', ha='center', va='bottom', fontsize=7)
    
    # Plot national bars
    offset = 1.5 * bar_width_stage
    natl_vals = [natl_props[col] for col in demo_cols]
    bars_natl = ax.bar([j + offset for j in x_stage], natl_vals, width=bar_width_stage,
                        label=f'National ({baseline_year})', color=colors_stage[3])
    
    # Add data labels
    for bar in bars_natl:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.3f}', ha='center', va='bottom', fontsize=7)
    
    ax.set_xticks(x_stage)
    ax.set_xticklabels([get_label(col) for col in demo_cols], fontsize=10)
    # Determine y-label based on demographic type
    if demographic_name == 'poverty':
        ylabel = 'Poverty Rate'
    elif demographic_name == 'employment':
        ylabel = 'Unemployment Rate'
    else:
        ylabel = 'Proportion Relative to Total Population'
    ax.set_ylabel(ylabel, fontsize=11)
    ax.legend(loc='best', fontsize=9)
    plt.tight_layout()
    
    output_file_onwn = os.path.join(output_dir, f'{FACILITY}_{demographic_name}_onwn_staged.png')
    plt.savefig(output_file_onwn, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"    ✓ Saved (ONWN staged): {output_file_onwn}")
    
    # Plot 4: DOE stages vs National
    fig, ax = plt.subplots(figsize=(12, 8))
    bar_width_stage = 0.2
    x_stage = list(range(len(demo_cols)))
    colors_stage = ['tab:blue', 'tab:cyan', 'tab:green', 'tab:orange']
    
    # Plot bars for each DOE stage
    for i, stage in enumerate(['1', '2', '3']):
        offset = (i - 1.5) * bar_width_stage
        if stage in doe_stage_props:
            stage_vals = [doe_stage_props[stage][col] for col in demo_cols]
            bars = ax.bar([j + offset for j in x_stage], stage_vals, width=bar_width_stage,
                           label=f'DOE Stage {stage}', color=colors_stage[i])
            
            # Add data labels
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.3f}', ha='center', va='bottom', fontsize=7)
    
    # Plot national bars
    offset = 1.5 * bar_width_stage
    natl_vals = [natl_props[col] for col in demo_cols]
    bars_natl = ax.bar([j + offset for j in x_stage], natl_vals, width=bar_width_stage,
                        label=f'National ({baseline_year})', color=colors_stage[3])
    
    # Add data labels
    for bar in bars_natl:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.3f}', ha='center', va='bottom', fontsize=7)
    
    ax.set_xticks(x_stage)
    ax.set_xticklabels([get_label(col) for col in demo_cols], fontsize=10)
    # Determine y-label based on demographic type
    if demographic_name == 'poverty':
        ylabel = 'Poverty Rate'
    elif demographic_name == 'employment':
        ylabel = 'Unemployment Rate'
    else:
        ylabel = 'Proportion Relative to Total Population'
    ax.set_ylabel(ylabel, fontsize=11)
    ax.legend(loc='best', fontsize=9)
    plt.tight_layout()
    
    output_file_doe = os.path.join(output_dir, f'{FACILITY}_{demographic_name}_doe_staged.png')
    plt.savefig(output_file_doe, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"    ✓ Saved (DOE staged): {output_file_doe}")
    
    # Save data to CSV
    csv_dir = os.path.join(output_dir, 'figure_data')
    os.makedirs(csv_dir, exist_ok=True)
    
    # Overall data
    overall_df = pd.DataFrame({
        'category': demo_cols,
        'interim': [overall_props[col] for col in demo_cols],
        f'national_{baseline_year}': [natl_props[col] for col in demo_cols]
    })
    overall_df.to_csv(os.path.join(csv_dir, f'{FACILITY}_{demographic_name}_overall.csv'), index=False)
    
    # Private data
    if private_total > 0:
        private_df = pd.DataFrame({
            'category': demo_cols,
            'private': [private_props[col] for col in demo_cols],
            f'national_{baseline_year}': [natl_props[col] for col in demo_cols]
        })
        private_df.to_csv(os.path.join(csv_dir, f'{FACILITY}_{demographic_name}_private.csv'), index=False)
    
    # ONWN staged data
    onwn_df = pd.DataFrame({
        'category': demo_cols,
        **{f'onwn_stage_{stage}': [onwn_stage_props[stage][col] for col in demo_cols] for stage in ['1', '2', '3'] if stage in onwn_stage_props},
        f'national_{baseline_year}': [natl_props[col] for col in demo_cols]
    })
    onwn_df.to_csv(os.path.join(csv_dir, f'{FACILITY}_{demographic_name}_onwn_staged.csv'), index=False)
    
    print(f"    ✓ Saved proportion data")

# Process all demographics
for demographic in DEMOGRAPHICS:
    plot_demographic_comparison(demographic)

print("\n" + "="*80)
print("✓ ALL INTERIM STORAGE FIGURES GENERATED!")
print("="*80)
