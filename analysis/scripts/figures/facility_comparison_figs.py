"""
Create comparison plots for unemployment and poverty rates across facility types.
Compares reactors (standard, residual), frontend (standard, residual), and national averages.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Set plotting style
sns.set_style("white")
plt.rcParams['figure.figsize'] = (14, 8)

# Define base paths
BASE_PATH = r"c:\Users\rjf\Desktop\Research\Fuel Cycle Analysis\analysis\outputs\demographics_by_facility"
EMPLOYMENT_PATH = os.path.join(BASE_PATH, "employment", "figures", "figure_data")
POVERTY_PATH = os.path.join(BASE_PATH, "poverty", "figures", "figure_data")
OUTPUT_PATH = r"c:\Users\rjf\Desktop\Research\Fuel Cycle Analysis\analysis\outputs\demographics_by_facility"

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_PATH, exist_ok=True)


def load_csv_data(filepath):
    """Load CSV data with year as index."""
    df = pd.read_csv(filepath, index_col=0)
    return df


def create_unemployment_plot():
    """Create unemployment comparison plot."""
    # Load data
    reactor_standard = load_csv_data(os.path.join(EMPLOYMENT_PATH, "reactor_employment_standard_proportions.csv"))
    reactor_residual = load_csv_data(os.path.join(EMPLOYMENT_PATH, "reactor_employment_residual_proportions.csv"))
    frontend_standard = load_csv_data(os.path.join(EMPLOYMENT_PATH, "frontend_employment_standard_proportions.csv"))
    frontend_residual = load_csv_data(os.path.join(EMPLOYMENT_PATH, "frontend_employment_residual_proportions.csv"))
    national = load_csv_data(os.path.join(EMPLOYMENT_PATH, "reactor_employment_national_proportions.csv"))
    
    # Create figure
    fig, ax = plt.subplots(figsize=(16, 8))
    
    # Define colors for each facility type
    reactor_color = '#1f77b4'
    frontend_color = '#ff7f0e'
    national_color = "#000000"
    
    # Plot lines - same color per facility type, different styles for standard/residual
    ax.plot(reactor_standard.index, reactor_standard['Unemployment'], 
            marker='o', label='Reactors (Standard)', linewidth=2, markersize=6,
            color=reactor_color, linestyle='-')
    ax.plot(reactor_residual.index, reactor_residual['Unemployment'], 
            marker='^', label='Reactors (Residual)', linewidth=2, markersize=6,
            color=reactor_color, linestyle=':', alpha=0.85)
    ax.plot(frontend_standard.index, frontend_standard['Unemployment'], 
            marker='o', label='Frontend (Standard)', linewidth=2, markersize=6,
            color=frontend_color, linestyle='-')
    ax.plot(frontend_residual.index, frontend_residual['Unemployment'], 
            marker='^', label='Frontend (Residual)', linewidth=2, markersize=6,
            color=frontend_color, linestyle=':', alpha=0.85)
    ax.plot(national.index, national['Unemployment'], 
            marker='s', label='National', linewidth=2, markersize=6,
            color=national_color, linestyle='--', alpha=0.7)
    
    # Customize plot
    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel('Unemployment Rate', fontsize=12)
    ax.legend(loc='best', fontsize=10)
    
    # Save figure
    output_file = os.path.join(BASE_PATH, "employment", "figures", "unemployment_facility_comparison.png")
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Saved unemployment comparison plot to: {output_file}")
    plt.close()


def create_poverty_plot():
    """Create poverty comparison plot."""
    # Load data
    reactor_standard = load_csv_data(os.path.join(POVERTY_PATH, "reactor_poverty_standard_proportions.csv"))
    reactor_residual = load_csv_data(os.path.join(POVERTY_PATH, "reactor_poverty_residual_proportions.csv"))
    frontend_standard = load_csv_data(os.path.join(POVERTY_PATH, "frontend_poverty_standard_proportions.csv"))
    frontend_residual = load_csv_data(os.path.join(POVERTY_PATH, "frontend_poverty_residual_proportions.csv"))
    national = load_csv_data(os.path.join(POVERTY_PATH, "reactor_poverty_national_proportions.csv"))
    
    # Create figure
    fig, ax = plt.subplots(figsize=(16, 8))
    
    # Define colors for each facility type
    reactor_color = '#1f77b4'
    frontend_color = '#ff7f0e'
    national_color = '#2ca02c'
    
    # Plot lines - same color per facility type, different styles for standard/residual
    ax.plot(reactor_standard.index, reactor_standard['Poverty Rate'], 
            marker='o', label='Reactors (Standard)', linewidth=2, markersize=6,
            color=reactor_color, linestyle='-')
    ax.plot(reactor_residual.index, reactor_residual['Poverty Rate'], 
            marker='^', label='Reactors (Residual)', linewidth=2, markersize=6,
            color=reactor_color, linestyle=':', alpha=0.85)
    ax.plot(frontend_standard.index, frontend_standard['Poverty Rate'], 
            marker='o', label='Frontend (Standard)', linewidth=2, markersize=6,
            color=frontend_color, linestyle='-')
    ax.plot(frontend_residual.index, frontend_residual['Poverty Rate'], 
            marker='^', label='Frontend (Residual)', linewidth=2, markersize=6,
            color=frontend_color, linestyle=':', alpha=0.85)
    ax.plot(national.index, national['Poverty Rate'], 
            marker='s', label='National', linewidth=2, markersize=6,
            color=national_color, linestyle='--', alpha=0.7)
    
    # Customize plot
    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel('Poverty Rate', fontsize=12)
    ax.legend(loc='best', fontsize=10)
    
    # Format y-axis as percentage
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: '{:.1%}'.format(y)))
    
    # Save figure
    output_file = os.path.join(BASE_PATH, "poverty", "figures", "poverty_facility_comparison.png")
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Saved poverty comparison plot to: {output_file}")
    plt.close()


def main():
    """Main function to generate both plots."""
    print("Creating facility comparison plots...")
    print("-" * 50)
    
    create_unemployment_plot()
    create_poverty_plot()
    
    print("-" * 50)
    print("All plots created successfully!")


if __name__ == "__main__":
    main()
