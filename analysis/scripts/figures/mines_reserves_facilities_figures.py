"""
Generate demographic proportion figures for Mines & Reserves facilities over time.
Creates time series visualizations comparing facility demographics to national proportions.

Outputs to: analysis/outputs/demographics_by_facility/{demographic}/figures/
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import numpy as np

# Get absolute paths
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
input_base = os.path.join(base_dir, 'analysis', 'outputs', 'demographics_by_facility')
compiled_base = os.path.join(base_dir, 'demographic_data', 'compiled')

# Set plotting style
sns.set_style("white")
plt.rcParams['figure.figsize'] = (14, 8)

# Facility types to process
FACILITIES = ['mines', 'reserves']

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

# Define demographics and their special handling
DEMOGRAPHIC_CONFIG = {
    'age': {
        'rebin': True,
        'rebin_map': {
            '<5': '<19', '5-14': '<19', '15-19': '<19',
            '20-24': '20-34', '25-34': '20-34',
            '35-44': '35-59', '45-54': '35-59', '55-59': '35-59',
            '60-64': '60+', '65-74': '60+', '75-84': '60+', '85+': '60+'
        },
        'baseline_file': 'age_combined.xlsx'
    },
    'education': {
        'columns': ['<9', '<B', 'B+']
    },
    'employment': {
        'special': 'unemployment',
        'columns': ['LF-CIV', 'LF-CIV-EMPL']
    },
    'poverty': {
        'special': 'poverty_rate',
        'columns': ['Poverty', 'PSD']
    },
    'race_ethnicity': {
        'exclude_from_total': ['H'],
        'columns': ['W', 'B', 'AIAN', 'AAPI', 'O', '2+', 'H']
    },
    'sex': {
        'columns': ['M', 'F']
    }
}

# Demographics to process
DEMOGRAPHICS = list(DEMOGRAPHIC_CONFIG.keys())

print("="*80)
print("GENERATING MINES & RESERVES DEMOGRAPHIC FIGURES (TIME SERIES)")
print("="*80)

def parse_year(sheet_name):
    """Parse year from sheet name, handling XXXX-XXXX format. Returns None if not parseable."""
    try:
        if '-' in sheet_name:
            years = sheet_name.split('-')
            return (int(years[0]) + int(years[1])) / 2
        return int(sheet_name)
    except (ValueError, IndexError):
        return None

def load_facility_data_all_years(facility_name, demographic_name):
    """Load demographic data for all years"""
    file_path = os.path.join(input_base, demographic_name, f"{facility_name}_{demographic_name}_facilities.xlsx")
    
    if not os.path.exists(file_path):
        print(f"  ✗ File not found: {file_path}")
        return None
    
    xls = pd.ExcelFile(file_path)
    data_by_year = {}
    
    for sheet_name in xls.sheet_names:
        year = parse_year(sheet_name)
        if year is not None:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            data_by_year[year] = df
    
    return data_by_year

def load_national_data(demographic_name):
    """Load national demographic data from compiled files"""
    config = DEMOGRAPHIC_CONFIG.get(demographic_name, {})
    file_name = config.get('baseline_file', f"{demographic_name}_compiled.xlsx")
    file_path = os.path.join(compiled_base, file_name)
    
    if not os.path.exists(file_path):
        print(f"  ✗ National data not found: {file_path}")
        return None
    
    xls = pd.ExcelFile(file_path)
    data_by_year = {}
    
    for sheet_name in xls.sheet_names:
        year = parse_year(sheet_name)
        if year is not None:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            data_by_year[year] = df
    
    return data_by_year

def rebin_age_columns(df, rebin_map):
    """Rebin age columns according to mapping"""
    rebinned_data = {}
    meta_cols = ['Name', 'FID', 'Type', 'Capacity', 'Note', 'Start', 'Stop', 
                 'Approx Year', 'ICF_ID', 'DOCS']
    
    # First, preserve meta columns
    for col in meta_cols:
        if col in df.columns:
            rebinned_data[col] = df[col]
    
    # Then rebin demographic columns
    for col in df.columns:
        if col in meta_cols:
            continue
        if col in rebin_map:
            new_col = rebin_map[col]
            if new_col not in rebinned_data:
                rebinned_data[new_col] = df[col]
            else:
                rebinned_data[new_col] += df[col]
        else:
            rebinned_data[col] = df[col]
    
    return pd.DataFrame(rebinned_data)

def calculate_facility_proportions(data_by_year, demographic_name):
    """Calculate aggregate proportions across all facilities for each year"""
    config = DEMOGRAPHIC_CONFIG.get(demographic_name, {})
    proportions_by_year = {}
    
    for year, df in data_by_year.items():
        # Apply age rebinning if needed
        if config.get('rebin', False):
            df = rebin_age_columns(df, config['rebin_map'])
        
        # Identify demographic columns
        meta_cols = ['Name', 'FID', 'Type', 'Capacity', 'Note', 'Start', 'Stop', 
                     'Approx Year', 'ICF_ID', 'DOCS']
        demo_cols = [col for col in df.columns if col not in meta_cols]
        
        # Sum across all facilities (only numeric columns, exclude _E error margins)
        numeric_df = df[demo_cols].select_dtypes(include=[np.number])
        # Exclude _E columns before summing
        numeric_df = numeric_df[[col for col in numeric_df.columns if not col.endswith('_E')]]
        totals = numeric_df.sum()
        
        # Handle special cases
        if 'special' in config:
            if config['special'] == 'unemployment':
                if 'LF-CIV' in totals.index and 'LF-CIV-EMPL' in totals.index:
                    total_lf_civ = totals['LF-CIV']
                    total_employed = totals['LF-CIV-EMPL']
                    if total_lf_civ > 0:
                        unemployment = 1 - (total_employed / total_lf_civ)
                        proportions_by_year[year] = pd.Series({'Unemployment': unemployment})
                continue
            elif config['special'] == 'poverty_rate':
                if 'Poverty' in totals.index and 'PSD' in totals.index:
                    total_poverty = totals['Poverty']
                    total_psd = totals['PSD']
                    if total_psd > 0:
                        poverty_rate = total_poverty / total_psd
                        proportions_by_year[year] = pd.Series({'Poverty Rate': poverty_rate})
                continue
        
        # Calculate proportions
        if 'exclude_from_total' in config:
            # For race_ethnicity: exclude H from total
            total_cols = [col for col in totals.index if col not in config['exclude_from_total']]
            population_total = totals[total_cols].sum()
            if population_total > 0:
                proportions = totals / population_total
                proportions_by_year[year] = proportions
        else:
            # Standard: sum all columns for total
            population_total = totals.sum()
            if population_total > 0:
                proportions = totals / totals.sum()
                proportions_by_year[year] = proportions
    
    return pd.DataFrame(proportions_by_year).T

def calculate_national_proportions(data_by_year, demographic_name):
    """Calculate national proportions for each year"""
    config = DEMOGRAPHIC_CONFIG.get(demographic_name, {})
    proportions_by_year = {}
    
    for year, df in data_by_year.items():
        # Apply age rebinning if needed
        if config.get('rebin', False):
            # Rebin national data
            rebinned_data = {'FIPS': df['FIPS']}
            if 'Region' in df.columns:
                rebinned_data['Region'] = df['Region']
            if 'GISJOIN' in df.columns:
                rebinned_data['GISJOIN'] = df['GISJOIN']
            
            rebin_map = config['rebin_map']
            for col in df.columns:
                if col in ['FIPS', 'GISJOIN', 'Region']:
                    continue
                if col in rebin_map:
                    new_col = rebin_map[col]
                    if new_col not in rebinned_data:
                        rebinned_data[new_col] = df[col]
                    else:
                        rebinned_data[new_col] += df[col]
                else:
                    rebinned_data[col] = df[col]
            df = pd.DataFrame(rebinned_data)
        
        # Identify demographic columns (exclude FIPS, GISJOIN, Region)
        meta_cols = ['FIPS', 'GISJOIN', 'Region']
        demo_cols = [col for col in df.columns if col not in meta_cols]
        
        # Sum across all counties (exclude _E error margins)
        demo_cols = [col for col in demo_cols if not col.endswith('_E')]
        totals = df[demo_cols].sum()
        
        # Handle special cases
        if 'special' in config:
            if config['special'] == 'unemployment':
                if 'LF-CIV' in totals.index and 'LF-CIV-EMPL' in totals.index:
                    total_lf_civ = totals['LF-CIV']
                    total_employed = totals['LF-CIV-EMPL']
                    if total_lf_civ > 0:
                        unemployment = 1 - (total_employed / total_lf_civ)
                        proportions_by_year[year] = pd.Series({'Unemployment': unemployment})
                continue
            elif config['special'] == 'poverty_rate':
                if 'Poverty' in totals.index and 'PSD' in totals.index:
                    total_poverty = totals['Poverty']
                    total_psd = totals['PSD']
                    if total_psd > 0:
                        poverty_rate = total_poverty / total_psd
                        proportions_by_year[year] = pd.Series({'Poverty Rate': poverty_rate})
                continue
        
        # Calculate proportions
        if 'exclude_from_total' in config:
            # For race_ethnicity: exclude H from total
            total_cols = [col for col in totals.index if col not in config['exclude_from_total']]
            population_total = totals[total_cols].sum()
            if population_total > 0:
                proportions = totals / population_total
                proportions_by_year[year] = proportions
        else:
            # Standard: sum all columns for total
            population_total = totals.sum()
            if population_total > 0:
                proportions = totals / totals.sum()
                proportions_by_year[year] = proportions
    
    return pd.DataFrame(proportions_by_year).T

def plot_demographic_comparison(facility_name, demographic_name):
    """Create time series comparison of mines vs reserves proportions"""
    print(f"\n  Processing {facility_name} - {demographic_name}...")
    
    # Load data for mines and reserves
    mines_data = load_facility_data_all_years('mines', demographic_name)
    reserves_data = load_facility_data_all_years('reserves', demographic_name)
    
    if mines_data is None or reserves_data is None:
        return
    
    print(f"    Loaded {len(mines_data)} years for mines")
    print(f"    Loaded {len(reserves_data)} years for reserves")
    
    # Calculate proportions
    mines_props = calculate_facility_proportions(mines_data, demographic_name)
    reserves_props = calculate_facility_proportions(reserves_data, demographic_name)
    
    # Create output directory
    output_dir = os.path.join(input_base, demographic_name, 'figures')
    os.makedirs(output_dir, exist_ok=True)
    
    # Plot each demographic category over time
    # Only use columns that exist in both mines and reserves data
    # Exclude _E (error margin) columns
    demo_cols = [col for col in mines_props.columns 
                 if col in reserves_props.columns and not col.endswith('_E')]
    
    if len(demo_cols) == 0:
        print(f"    ✗ No matching demographic columns between mines and reserves data")
        return
    
    # Special handling for race_ethnicity: exclude 2013 data
    if demographic_name == 'race_ethnicity':
        mines_props = mines_props[mines_props.index != 2013]
        reserves_props = reserves_props[reserves_props.index != 2013]
    
    # Create single plot with all categories
    fig, ax = plt.subplots(figsize=(14, 8))
    
    mines_years = sorted(mines_props.index)
    reserves_years = [y for y in mines_years if y in reserves_props.index]
    
    # Use different colors for each demographic category (discrete high-contrast colors)
    color_list = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                  '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    colors = [color_list[i % len(color_list)] for i in range(len(demo_cols))]
    
    for i, col in enumerate(demo_cols):
        # Plot mines proportions
        ax.plot(mines_years, mines_props.loc[mines_years, col], 
                marker='o', label=f'{get_label(col)} (Mines)', linewidth=2, markersize=6,
                color=colors[i], linestyle='-')
        
        # Plot reserves proportions (only for overlapping years)
        if reserves_years:
            ax.plot(reserves_years, reserves_props.loc[reserves_years, col],
                   marker='s', label=f'{get_label(col)} (Reserves)', linewidth=2, markersize=6,
                   color=colors[i], linestyle='--', alpha=0.7)
    
    # Determine y-label based on demographic type
    if demographic_name == 'poverty':
        ylabel = 'Poverty Rate'
    elif demographic_name == 'employment':
        ylabel = 'Unemployment Rate'
    else:
        ylabel = 'Proportion Relative to Total Population'
    
    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.legend(loc='best', fontsize=9)
    
    output_file = os.path.join(output_dir, f'mines_reserves_{demographic_name}_timeseries.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"    ✓ Saved: {output_file}")
    
    # Special handling for race_ethnicity: create additional plot without W
    if demographic_name == 'race_ethnicity' and 'W' in demo_cols:
        fig, ax = plt.subplots(figsize=(14, 8))
        demo_cols_no_w = [col for col in demo_cols if col != 'W']
        colors_no_w = [color_list[i % len(color_list)] for i in range(len(demo_cols_no_w))]
        
        for i, col in enumerate(demo_cols_no_w):
            ax.plot(mines_years, mines_props.loc[mines_years, col], \
                    marker='o', label=f'{get_label(col)} (Mines)', linewidth=2, markersize=6,
                    color=colors_no_w[i], linestyle='-')
            
            if reserves_years:
                ax.plot(reserves_years, reserves_props.loc[reserves_years, col],
                       marker='s', label=f'{get_label(col)} (Reserves)', linewidth=2, markersize=6,
                       color=colors_no_w[i], linestyle='--', alpha=0.7)
        
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Proportion Relative to Total Population', fontsize=12)
        ax.legend(loc='best', fontsize=9)
        
        output_file_no_w = os.path.join(output_dir, f'mines_reserves_{demographic_name}_timeseries_no_w.png')
        plt.savefig(output_file_no_w, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"    ✓ Saved (no W): {output_file_no_w}")
    
    # Save proportions to CSV in figure_data subdirectory
    csv_dir = os.path.join(output_dir, 'figure_data')
    os.makedirs(csv_dir, exist_ok=True)
    mines_props.to_csv(os.path.join(csv_dir, f'mines_{demographic_name}_proportions.csv'))
    reserves_props.to_csv(os.path.join(csv_dir, f'reserves_{demographic_name}_proportions.csv'))
    print(f"    ✓ Saved proportion data")

# Main processing loop
for demographic in DEMOGRAPHICS:
    plot_demographic_comparison('mines_reserves', demographic)

def plot_total_population():
    """Plot total population (M + F) over time for mines and reserves"""
    print(f"\n  Processing total population...")
    
    # Load sex data for mines and reserves
    mines_sex_data = load_facility_data_all_years('mines', 'sex')
    reserves_sex_data = load_facility_data_all_years('reserves', 'sex')
    
    if mines_sex_data is None or reserves_sex_data is None:
        return
    
    print(f"    Loaded {len(mines_sex_data)} years for mines sex data")
    print(f"    Loaded {len(reserves_sex_data)} years for reserves sex data")
    
    # Calculate total population for mines
    mines_totals = {}
    for year, df in mines_sex_data.items():
        if 'M' in df.columns and 'F' in df.columns:
            total = df['M'].sum() + df['F'].sum()
            mines_totals[year] = total
    
    # Calculate total population for reserves
    reserves_totals = {}
    for year, df in reserves_sex_data.items():
        if 'M' in df.columns and 'F' in df.columns:
            total = df['M'].sum() + df['F'].sum()
            reserves_totals[year] = total
    
    # Convert to Series for plotting
    mines_series = pd.Series(mines_totals).sort_index()
    reserves_series = pd.Series(reserves_totals).sort_index()
    
    # Create plot
    fig, ax = plt.subplots(figsize=(14, 8))
    
    mines_years = sorted(mines_series.index)
    reserves_years = sorted(reserves_series.index)
    
    ax.plot(mines_years, mines_series.loc[mines_years],
           marker='o', label='Mines', linewidth=2, markersize=6,
           color='#1f77b4', linestyle='-')
    
    ax.plot(reserves_years, reserves_series.loc[reserves_years],
           marker='s', label='Reserves', linewidth=2, markersize=6,
           color='#ff7f0e', linestyle='--', alpha=0.7)
    
    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel('Person*Exposure', fontsize=12)
    ax.legend(loc='best', fontsize=10)
    
    # Save plot
    output_dir = os.path.join(input_base, 'total', 'figures')
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'mines_reserves_total_population.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"    ✓ Saved: {output_file}")
    
    # Save data to CSV
    csv_dir = os.path.join(output_dir, 'figure_data')
    os.makedirs(csv_dir, exist_ok=True)
    
    pop_df = pd.DataFrame({
        'mines': mines_series,
        'reserves': reserves_series
    })
    pop_df.to_csv(os.path.join(csv_dir, 'mines_reserves_total_population.csv'))
    print(f"    ✓ Saved population data")

# Plot total population
plot_total_population()

print("\n" + "="*80)
print("✓ ALL MINES & RESERVES FIGURES GENERATED!")
print("="*80)
