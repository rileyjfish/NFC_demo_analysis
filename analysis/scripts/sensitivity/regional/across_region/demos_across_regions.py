"""
Analyze demographic distributions across regions for different facility types.
Creates horizontal stacked bar charts showing regional distribution (normalized to 1.0) 
for each demographic category across different facility types.

Facility types included:
- Reactors/Standard (latest year, rad_type='S')
- Reactors/Residual (latest year, rad_type='R')
- Frontend/Standard (latest year, rad_type='S')
- Frontend/Residual (latest year, rad_type='R')
- Mines (latest year, all facilities)
- Repositories (Stage 0 - 1980, all facilities)
- Interim Storage (sum of Stage 0, Stage 1, Stage 4 from 1990)

Each figure shows one demographic category with 7 horizontal stacked bars.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# Get absolute paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
OUTPUT_BASE = os.path.join(BASE_DIR, 'outputs', 'sensitivity_analysis', 'regional', 'across_region')
DEMO_BASE = os.path.join(BASE_DIR, 'outputs', 'demographics_by_county')

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

# Define region colors
REGION_COLORS = {
    1: '#1f77b4',  # Midwest - blue
    2: '#ff7f0e',  # Northeast - orange
    3: '#2ca02c',  # Southeast - green
    4: '#d62728',  # Southwest - red
    5: '#9467bd'   # West - purple
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

def rebin_age_df(df, rebin_map):
    """Rebin age columns in dataframe"""
    age_cols = [col for col in df.columns 
                if col not in ['FIPS', 'Region', 'Buffer_Fraction', 'Name', 'Note', 'Approx Year', 'rad_type']]
    
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
    
    # Preserve metadata columns
    meta_cols_to_keep = ['FIPS', 'Region', 'Buffer_Fraction']
    if 'rad_type' in df.columns:
        meta_cols_to_keep.append('rad_type')
    
    result_df = df[[col for col in meta_cols_to_keep if col in df.columns]].copy()
    for col_name, col_data in rebinned_cols.items():
        result_df[col_name] = col_data
    
    return result_df

def load_facility_data(demo_name, demo_config, facility_type):
    """Load demographic data for a specific facility type
    
    Returns:
        Tuple of (DataFrame with regional sums, year string) or (None, None) if no data
    """
    file_path = os.path.join(DEMO_BASE, demo_name, f'{facility_type}_{demo_name}_counties.xlsx')
    
    if not os.path.exists(file_path):
        print(f"  Warning: File not found - {file_path}")
        return None, None
    
    try:
        xls = pd.ExcelFile(file_path)
        
        # Determine which sheet(s) to load based on facility type
        year_str = None
        if facility_type == 'repository':
            sheet_name = 'Stage 0 - 1980'
            year_str = '1980'
            if sheet_name not in xls.sheet_names:
                print(f"  Warning: Sheet '{sheet_name}' not found in {facility_type}")
                return None, None
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            dfs_to_process = [df]
            
        elif facility_type == 'interim_prop':
            # Sum Stage 0, Stage 1, and Stage 4 from 1990
            year_str = '1990'
            stage_sheets = ['Stage 0 - 1990', 'Stage 1 - 1990', 'Stage 4 - 1990']
            dfs_to_process = []
            for sheet_name in stage_sheets:
                if sheet_name in xls.sheet_names:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    dfs_to_process.append(df)
                else:
                    print(f"  Warning: Sheet '{sheet_name}' not found in {facility_type}")
            
            if not dfs_to_process:
                return None, None
                
        else:
            # For reactors, frontend, mines - use last sheet
            last_sheet = xls.sheet_names[-1]
            df = pd.read_excel(file_path, sheet_name=last_sheet)
            dfs_to_process = [df]
        
        # Process each dataframe
        combined_regional_sums = {}
        
        for df in dfs_to_process:
            # Filter for exposed counties only
            df_exposed = df[df['Buffer_Fraction'] > 0].copy()
            
            if df_exposed.empty:
                continue
            
            # Handle age rebinning if needed
            if demo_config.get('rebin', False):
                df_exposed = rebin_age_df(df_exposed, demo_config['rebin_map'])
            
            # Get demographic columns
            demo_cols = [col for col in df_exposed.columns 
                        if col not in ['FIPS', 'Region', 'Buffer_Fraction', 'Name', 'Note', 'Approx Year', 'rad_type']]
            
            if not demo_cols:
                continue
            
            # Sum by region
            regional_sums = df_exposed.groupby('Region')[demo_cols].sum()
            
            # Add to combined sums
            for region_id in regional_sums.index:
                if region_id not in combined_regional_sums:
                    combined_regional_sums[region_id] = regional_sums.loc[region_id]
                else:
                    combined_regional_sums[region_id] += regional_sums.loc[region_id]
        
        if not combined_regional_sums:
            return None, None
        
        # Convert to DataFrame
        result_df = pd.DataFrame(combined_regional_sums).T
        return result_df, year_str
        
    except Exception as e:
        print(f"  Error loading {facility_type}: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def load_facility_data_with_filter(demo_name, demo_config, facility_type, rad_type_filter=None):
    """Load demographic data for a specific facility type with optional rad_type filter
    
    Args:
        demo_name: Name of demographic
        demo_config: Configuration for demographic
        facility_type: Type of facility (e.g., 'reactor', 'frontend')
        rad_type_filter: Filter for rad_type field ('S' for Standard, 'R' for Residual, None for all)
    
    Returns:
        Tuple of (DataFrame with regional sums, year string) or (None, None) if no data
    """
    file_path = os.path.join(DEMO_BASE, demo_name, f'{facility_type}_{demo_name}_counties.xlsx')
    
    if not os.path.exists(file_path):
        print(f"  Warning: File not found - {file_path}")
        return None, None
    
    try:
        xls = pd.ExcelFile(file_path)
        
        # Use last sheet for reactors/frontend/mines
        last_sheet = xls.sheet_names[-1]
        year_str = last_sheet  # Store the sheet name as year string
        df = pd.read_excel(file_path, sheet_name=last_sheet)
        
        # For reactors/frontend, columns are split by rad_type (_S and _R suffixes)
        # We need to filter and reshape the data
        if rad_type_filter is not None:
            # Check if this file has split columns (Buffer_Fraction_S, Buffer_Fraction_R)
            buffer_col = f'Buffer_Fraction_{rad_type_filter}'
            
            if buffer_col in df.columns:
                # Filter for exposed counties using the appropriate buffer column
                df_exposed = df[df[buffer_col] > 0].copy()
                
                if df_exposed.empty:
                    return None, None
                
                # Get demographic columns with this rad_type suffix
                suffix = f'_{rad_type_filter}'
                demo_cols_with_suffix = [col for col in df_exposed.columns if col.endswith(suffix)]
                
                # Create new dataframe with renamed columns (remove suffix)
                df_result = df_exposed[['FIPS', 'Region']].copy()
                for col in demo_cols_with_suffix:
                    new_col_name = col[:-len(suffix)]  # Remove suffix
                    df_result[new_col_name] = df_exposed[col]
                
                df_exposed = df_result
            else:
                # Fallback: single Buffer_Fraction column
                if 'Buffer_Fraction' in df.columns:
                    df_exposed = df[df['Buffer_Fraction'] > 0].copy()
                else:
                    df_exposed = df.copy()
        else:
            # No rad_type filter - use Buffer_Fraction if exists
            if 'Buffer_Fraction' in df.columns:
                df_exposed = df[df['Buffer_Fraction'] > 0].copy()
            else:
                df_exposed = df.copy()
        
        if df_exposed.empty:
            return None, None
        
        # Handle age rebinning if needed
        if demo_config.get('rebin', False):
            df_exposed = rebin_age_df(df_exposed, demo_config['rebin_map'])
        
        # Get demographic columns (exclude metadata)
        demo_cols = [col for col in df_exposed.columns 
                    if col not in ['FIPS', 'Region', 'Buffer_Fraction', 'Buffer_Fraction_S', 'Buffer_Fraction_R', 
                                   'Name', 'Note', 'Approx Year', 'rad_type']]
        
        if not demo_cols:
            return None, None
        
        # Sum by region
        regional_sums = df_exposed.groupby('Region')[demo_cols].sum()
        
        return regional_sums, year_str
        
    except Exception as e:
        print(f"  Error loading {facility_type} with filter {rad_type_filter}: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def calculate_regional_distribution(regional_sums, column_name, demo_config):
    """Calculate normalized regional distribution for a demographic column
    
    Args:
        regional_sums: DataFrame with regional sums (index=region_id, columns=demo categories)
        column_name: Name of demographic column to analyze
        demo_config: Configuration for this demographic
    
    Returns:
        Dictionary mapping region_id to proportion (normalized to sum to 1.0), or None if no data
    """
    if regional_sums is None or regional_sums.empty:
        return None
    
    if column_name not in regional_sums.columns:
        return None
    
    # Handle special cases
    if 'special' in demo_config:
        if demo_config['special'] == 'unemployment':
            if 'LF-CIV' in regional_sums.columns and 'LF-CIV-EMPL' in regional_sums.columns:
                # Calculate unemployment rate per region
                unemployment_by_region = {}
                for region_id in regional_sums.index:
                    lf_civ = regional_sums.loc[region_id, 'LF-CIV']
                    employed = regional_sums.loc[region_id, 'LF-CIV-EMPL']
                    if lf_civ > 0:
                        # Weight by labor force size for regional distribution
                        unemployment_by_region[region_id] = lf_civ
                    
                # Normalize to sum to 1.0
                total = sum(unemployment_by_region.values())
                if total > 0:
                    return {k: v/total for k, v in unemployment_by_region.items()}
            return None
        
        elif demo_config['special'] == 'poverty_rate':
            if 'PSD' in regional_sums.columns:
                # Weight by PSD (poverty status determined) population
                psd_by_region = {}
                for region_id in regional_sums.index:
                    psd = regional_sums.loc[region_id, 'PSD']
                    if psd > 0:
                        psd_by_region[region_id] = psd
                
                # Normalize to sum to 1.0
                total = sum(psd_by_region.values())
                if total > 0:
                    return {k: v/total for k, v in psd_by_region.items()}
            return None
    
    # Standard case: sum column across regions and normalize
    column_sums = {}
    for region_id in regional_sums.index:
        value = regional_sums.loc[region_id, column_name]
        if value > 0:
            column_sums[region_id] = value
    
    if not column_sums:
        return None
    
    # Normalize to sum to 1.0
    total = sum(column_sums.values())
    if total > 0:
        return {k: v/total for k, v in column_sums.items()}
    
    return None

def create_figure(demo_name, demo_config, column_name):
    """Create horizontal stacked bar chart showing regional distribution across facility types
    
    Args:
        demo_name: Name of demographic
        demo_config: Configuration for demographic
        column_name: Name of demographic column to visualize
    """
    print(f"  Creating figure for {column_name}...")
    
    # Define facility types and their base labels (in desired order)
    facility_specs = [
        ('mines', None, 'Mines'),
        ('frontend', 'S', 'Frontend/Standard'),
        ('frontend', 'R', 'Frontend/Residual'),
        ('reactor', 'S', 'Reactor/Standard'),
        ('reactor', 'R', 'Reactor/Residual'),
        ('interim_prop', None, 'Interim'),
        ('repository', None, 'Repositories')
    ]
    
    # Collect data for each facility type
    all_data = []
    facility_labels = []
    
    for facility_type, rad_filter, base_label in facility_specs:
        if facility_type in ['repository', 'interim_prop']:
            regional_sums, year_str = load_facility_data(demo_name, demo_config, facility_type)
        else:
            regional_sums, year_str = load_facility_data_with_filter(demo_name, demo_config, facility_type, rad_filter)
        
        regional_dist = calculate_regional_distribution(regional_sums, column_name, demo_config)
        
        if regional_dist:
            all_data.append(regional_dist)
            # Add year to label
            if year_str:
                label = f"{base_label} ({year_str})"
            else:
                label = base_label
            facility_labels.append(label)
    
    if not all_data:
        print(f"    No data available for {column_name}")
        return
    
    # Create horizontal stacked bar chart
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Prepare data for stacking
    num_facilities = len(all_data)
    y_pos = np.arange(num_facilities)
    
    # Plot stacked bars for each region
    left_positions = np.zeros(num_facilities)
    
    for region_id in sorted(REGION_MAP.keys()):
        region_name = REGION_MAP[region_id]
        region_color = REGION_COLORS[region_id]
        
        # Get values for this region across all facility types
        values = []
        for dist_dict in all_data:
            values.append(dist_dict.get(region_id, 0))
        
        # Plot horizontal bars
        bars = ax.barh(y_pos, values, left=left_positions, 
                      color=region_color, label=region_name, alpha=0.9)
        
        # Add percentage labels on segments (only if segment is large enough)
        for i, (bar, value) in enumerate(zip(bars, values)):
            if value > 0.05:  # Only label if > 5%
                x_pos = left_positions[i] + value / 2
                ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
                       f'{value:.1%}', ha='center', va='center',
                       fontsize=9, fontweight='bold', color='white')
        
        # Update left positions for next region
        left_positions += values
    
    # Format plot
    ax.set_yticks(y_pos)
    ax.set_yticklabels(facility_labels, fontsize=11)
    ax.set_xlabel('Regional Distribution (Proportion)', fontsize=12)
    ax.set_title(f'Regional Distribution Across Facility Types: {demo_name.replace("_", " ").title()}, {column_name}',
                fontsize=14, fontweight='bold')
    ax.legend(title='Region', loc='center left', bbox_to_anchor=(1, 0.5), fontsize=10)
    ax.set_xlim(0, 1)
    ax.grid(axis='x', alpha=0.3)
    
    # Add 100% reference line
    ax.axvline(x=1.0, color='black', linestyle='--', linewidth=1, alpha=0.5)
    
    plt.tight_layout()
    
    # Save figure
    safe_name = str(column_name).replace('/', '_').replace('<', 'lt').replace('+', 'plus').replace(' ', '_')
    output_path = os.path.join(OUTPUT_BASE, f'{demo_name}_{safe_name}_regional_distribution.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"    Saved: {demo_name}_{safe_name}_regional_distribution.png")

# Main processing loop
print("="*80)
print("Generating regional distribution figures across facility types...")
print("="*80)

for demo_name, demo_config in demographics.items():
    print(f"\n{'='*80}")
    print(f"Processing demographic: {demo_name.upper()}")
    print('='*80)
    
    # Get all possible columns for this demographic
    # Load one facility type with rad_type filter to get properly processed column names
    test_data, _ = load_facility_data_with_filter(demo_name, demo_config, 'reactor', 'S')
    
    if test_data is None or test_data.empty:
        # Try repository as fallback
        test_data, _ = load_facility_data(demo_name, demo_config, 'repository')
    
    if test_data is None or test_data.empty:
        print(f"  No data found for {demo_name}")
        continue
    
    # Get all demographic columns (these are now base names without _S/_R suffixes)
    all_columns = test_data.columns.tolist()
    
    # Handle special cases
    if 'special' in demo_config:
        if demo_config['special'] == 'unemployment':
            all_columns = ['Unemployment']
        elif demo_config['special'] == 'poverty_rate':
            all_columns = ['Poverty Rate']
    
    # Create figure for each column
    for column in sorted(all_columns):
        create_figure(demo_name, demo_config, column)

print("\n" + "="*80)
print("✓ All regional distribution figures generated successfully!")
print("="*80)
