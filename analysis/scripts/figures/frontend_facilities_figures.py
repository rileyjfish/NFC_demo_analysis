"""
Generate demographic proportion figures for Frontend facilities over time.
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

FACILITY = 'frontend'

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

DEMOGRAPHICS = list(DEMOGRAPHIC_CONFIG.keys())

print("="*80)
print("GENERATING FRONTEND DEMOGRAPHIC FIGURES (TIME SERIES)")
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

def load_facility_data_all_years(demographic_name):
    """Load demographic data for all years"""
    file_path = os.path.join(input_base, demographic_name, f"{FACILITY}_{demographic_name}_facilities.xlsx")
    
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
    meta_cols = ['Name', 'FID', 'Type', 'Capacity', 'Start', 'Stop']
    
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

def extract_year_from_date(date_str):
    """Extract year from date string in format XX-XX-XXXX"""
    if pd.isna(date_str):
        return None
    try:
        if isinstance(date_str, str):
            return int(date_str.split('-')[-1])
        elif hasattr(date_str, 'year'):
            return date_str.year
        else:
            return None
    except (ValueError, IndexError, AttributeError):
        return None

def calculate_facility_proportions_standard(data_by_year, demographic_name):
    """Calculate aggregate proportions for facilities operating during each year (Standard).
    Includes facility if year is BETWEEN Start and Stop dates."""
    config = DEMOGRAPHIC_CONFIG.get(demographic_name, {})
    proportions_by_year = {}
    
    for year, df in data_by_year.items():
        # Filter facilities: include if year is between Start and Stop
        df['_start_year'] = df['Start'].apply(extract_year_from_date)
        df['_stop_year'] = df['Stop'].apply(extract_year_from_date)
        df_filtered = df[
            (df['_start_year'].notna()) & 
            (df['_stop_year'].notna()) &
            (df['_start_year'] <= year) & 
            (year <= df['_stop_year'])
        ].copy()
        df_filtered = df_filtered.drop(columns=['_start_year', '_stop_year'])
        
        if len(df_filtered) == 0:
            continue
        
        # Apply age rebinning if needed
        if config.get('rebin', False):
            df_filtered = rebin_age_columns(df_filtered, config['rebin_map'])
        
        # Identify demographic columns
        meta_cols = ['Name', 'FID', 'Type', 'Capacity', 'Start', 'Stop']
        demo_cols = [col for col in df_filtered.columns if col not in meta_cols]
        
        # Sum across all facilities (only numeric columns, exclude _E error margins)
        numeric_df = df_filtered[demo_cols].select_dtypes(include=[np.number])
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
            total_cols = [col for col in totals.index if col not in config['exclude_from_total']]
            population_total = totals[total_cols].sum()
            if population_total > 0:
                proportions = totals / population_total
                proportions_by_year[year] = proportions
        else:
            population_total = totals.sum()
            if population_total > 0:
                proportions = totals / totals.sum()
                proportions_by_year[year] = proportions
    
    return pd.DataFrame(proportions_by_year).T

def calculate_facility_proportions_residual(data_by_year, demographic_name):
    """Calculate aggregate proportions for facilities after start date (Residual).
    Includes facility if year is AFTER Start date (Stop date irrelevant)."""
    config = DEMOGRAPHIC_CONFIG.get(demographic_name, {})
    proportions_by_year = {}
    
    for year, df in data_by_year.items():
        # Filter facilities: include if year is after Start
        df['_start_year'] = df['Start'].apply(extract_year_from_date)
        df_filtered = df[
            (df['_start_year'].notna()) & 
            (df['_start_year'] <= year)
        ].copy()
        df_filtered = df_filtered.drop(columns=['_start_year'])
        
        if len(df_filtered) == 0:
            continue
        
        # Apply age rebinning if needed
        if config.get('rebin', False):
            df_filtered = rebin_age_columns(df_filtered, config['rebin_map'])
        
        # Identify demographic columns
        meta_cols = ['Name', 'FID', 'Type', 'Capacity', 'Start', 'Stop']
        demo_cols = [col for col in df_filtered.columns if col not in meta_cols]
        
        # Sum across all facilities (only numeric columns, exclude _E error margins)
        numeric_df = df_filtered[demo_cols].select_dtypes(include=[np.number])
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
            total_cols = [col for col in totals.index if col not in config['exclude_from_total']]
            population_total = totals[total_cols].sum()
            if population_total > 0:
                proportions = totals / population_total
                proportions_by_year[year] = proportions
        else:
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

def plot_demographic_comparison(demographic_name):
    """Create time series comparison of facility vs national proportions"""
    print(f"\n  Processing {FACILITY} - {demographic_name}...")
    
    # Load data
    facility_data = load_facility_data_all_years(demographic_name)
    national_data = load_national_data(demographic_name)
    
    if facility_data is None or national_data is None:
        return
    
    print(f"    Loaded {len(facility_data)} years for facilities")
    print(f"    Loaded {len(national_data)} years for national data")
    
    # Calculate proportions: Standard, Residual, and National
    standard_props = calculate_facility_proportions_standard(facility_data, demographic_name)
    residual_props = calculate_facility_proportions_residual(facility_data, demographic_name)
    national_props = calculate_national_proportions(national_data, demographic_name)
    
    # Create output directory
    output_dir = os.path.join(input_base, demographic_name, 'figures')
    os.makedirs(output_dir, exist_ok=True)
    
    # Plot each demographic category over time
    # Find common columns across all three datasets
    demo_cols = [col for col in standard_props.columns 
                 if col in national_props.columns and col in residual_props.columns 
                 and not col.endswith('_E')]
    
    if len(demo_cols) == 0:
        print(f"    ✗ No matching demographic columns between datasets")
        return
    
    # Special handling for race_ethnicity: exclude 2013 data
    if demographic_name == 'race_ethnicity':
        standard_props = standard_props[standard_props.index != 2013]
        residual_props = residual_props[residual_props.index != 2013]
        national_props = national_props[national_props.index != 2013]
    
    # Create single plot with all categories
    fig, ax = plt.subplots(figsize=(16, 8))
    
    all_years = sorted(set(list(standard_props.index) + list(residual_props.index)))
    national_years = [y for y in all_years if y in national_props.index]
    
    # Use different colors for each demographic category (discrete high-contrast colors)
    color_list = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                  '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    colors = [color_list[i % len(color_list)] for i in range(len(demo_cols))]
    
    for i, col in enumerate(demo_cols):
        # Plot Standard proportions
        standard_years = [y for y in all_years if y in standard_props.index]
        if standard_years:
            ax.plot(standard_years, standard_props.loc[standard_years, col], 
                    marker='o', label=f'{get_label(col)} (Standard)', linewidth=2, markersize=6,
                    color=colors[i], linestyle='-')
        
        # Plot Residual proportions
        residual_years = [y for y in all_years if y in residual_props.index]
        if residual_years:
            ax.plot(residual_years, residual_props.loc[residual_years, col],
                   marker='^', label=f'{get_label(col)} (Residual)', linewidth=2, markersize=6,
                   color=colors[i], linestyle=':', alpha=0.85)
        
        # Plot national proportions (only for overlapping years)
        if national_years:
            ax.plot(national_years, national_props.loc[national_years, col],
                   marker='s', label=f'{get_label(col)} (National)', linewidth=2, markersize=6,
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
    ax.legend(loc='best', fontsize=8)
    
    output_file = os.path.join(output_dir, f'{FACILITY}_{demographic_name}_timeseries.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"    ✓ Saved: {output_file}")
    
    # Special handling for race_ethnicity: create additional plot without W
    if demographic_name == 'race_ethnicity' and 'W' in demo_cols:
        fig, ax = plt.subplots(figsize=(16, 8))
        demo_cols_no_w = [col for col in demo_cols if col != 'W']
        colors_no_w = [color_list[i % len(color_list)] for i in range(len(demo_cols_no_w))]
        
        for i, col in enumerate(demo_cols_no_w):
            standard_years = [y for y in all_years if y in standard_props.index]
            if standard_years:
                ax.plot(standard_years, standard_props.loc[standard_years, col], 
                        marker='o', label=f'{get_label(col)} (Standard)', linewidth=2, markersize=6,
                        color=colors_no_w[i], linestyle='-')
            
            residual_years = [y for y in all_years if y in residual_props.index]
            if residual_years:
                ax.plot(residual_years, residual_props.loc[residual_years, col],
                       marker='^', label=f'{get_label(col)} (Residual)', linewidth=2, markersize=6,
                       color=colors_no_w[i], linestyle=':', alpha=0.85)
            
            if national_years:
                ax.plot(national_years, national_props.loc[national_years, col],
                       marker='s', label=f'{get_label(col)} (National)', linewidth=2, markersize=6,
                       color=colors_no_w[i], linestyle='--', alpha=0.7)
        
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Proportion Relative to Total Population', fontsize=12)
        ax.legend(loc='best', fontsize=8)
        
        output_file_no_w = os.path.join(output_dir, f'{FACILITY}_{demographic_name}_timeseries_no_w.png')
        plt.savefig(output_file_no_w, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"    ✓ Saved (no W): {output_file_no_w}")
    
    # Save proportions to CSV in figure_data subdirectory
    csv_dir = os.path.join(output_dir, 'figure_data')
    os.makedirs(csv_dir, exist_ok=True)
    standard_props.to_csv(os.path.join(csv_dir, f'{FACILITY}_{demographic_name}_standard_proportions.csv'))
    residual_props.to_csv(os.path.join(csv_dir, f'{FACILITY}_{demographic_name}_residual_proportions.csv'))
    national_props.to_csv(os.path.join(csv_dir, f'{FACILITY}_{demographic_name}_national_proportions.csv'))
    print(f"    ✓ Saved proportion data")

# Process all demographics
for demographic in DEMOGRAPHICS:
    plot_demographic_comparison(demographic)

def plot_total_population():
    """Plot total population (M + F) over time for standard and residual"""
    print(f"\n  Processing total population...")
    
    # Load sex data
    sex_data = load_facility_data_all_years('sex')
    if sex_data is None:
        return
    
    print(f"    Loaded {len(sex_data)} years for sex data")
    
    # Calculate standard total population (between Start and Stop)
    standard_totals = {}
    for year, df in sex_data.items():
        # Extract years from Start and Stop dates
        df['_start_year'] = df['Start'].apply(extract_year_from_date)
        df['_stop_year'] = df['Stop'].apply(extract_year_from_date)
        
        # Filter by Start <= year <= Stop
        df_filtered = df[
            (df['_start_year'].notna()) & 
            (df['_stop_year'].notna()) &
            (df['_start_year'] <= year) & 
            (year <= df['_stop_year'])
        ].copy()
        
        if len(df_filtered) == 0:
            continue
        
        # Sum M and F across all facilities
        if 'M' in df_filtered.columns and 'F' in df_filtered.columns:
            total = df_filtered['M'].sum() + df_filtered['F'].sum()
            standard_totals[year] = total
    
    # Calculate residual total population (after Start)
    residual_totals = {}
    for year, df in sex_data.items():
        # Extract years from Start date
        df['_start_year'] = df['Start'].apply(extract_year_from_date)
        
        # Filter by Start <= year
        df_filtered = df[
            (df['_start_year'].notna()) &
            (df['_start_year'] <= year)
        ].copy()
        
        if len(df_filtered) == 0:
            continue
        
        # Sum M and F across all facilities
        if 'M' in df_filtered.columns and 'F' in df_filtered.columns:
            total = df_filtered['M'].sum() + df_filtered['F'].sum()
            residual_totals[year] = total
    
    # Convert to Series for plotting
    standard_series = pd.Series(standard_totals).sort_index()
    residual_series = pd.Series(residual_totals).sort_index()
    
    # Create plot
    fig, ax = plt.subplots(figsize=(14, 8))
    
    years_standard = sorted(standard_series.index)
    years_residual = sorted(residual_series.index)
    
    ax.plot(years_standard, standard_series.loc[years_standard],
           marker='o', label='Standard', linewidth=2, markersize=6,
           color='#1f77b4', linestyle='-')
    
    ax.plot(years_residual, residual_series.loc[years_residual],
           marker='^', label='Residual', linewidth=2, markersize=6,
           color='#ff7f0e', linestyle=':')
    
    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel('Person*Exposure', fontsize=12)
    ax.legend(loc='best', fontsize=10)
    
    # Save plot
    output_dir = os.path.join(input_base, 'total', 'figures')
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'{FACILITY}_total_population.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"    ✓ Saved: {output_file}")
    
    # Save data to CSV
    csv_dir = os.path.join(output_dir, 'figure_data')
    os.makedirs(csv_dir, exist_ok=True)
    
    pop_df = pd.DataFrame({
        'standard': standard_series,
        'residual': residual_series
    })
    pop_df.to_csv(os.path.join(csv_dir, f'{FACILITY}_total_population.csv'))
    print(f"    ✓ Saved population data")

# Plot total population
plot_total_population()

print("\n" + "="*80)
print("✓ ALL FRONTEND FIGURES GENERATED!")
print("="*80)
