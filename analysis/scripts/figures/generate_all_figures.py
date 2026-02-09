"""
Master script to generate all demographic figures.
Runs all figure generation scripts in the analysis/scripts/figures directory.
"""

import os
import sys
import subprocess
import time

# Get the directory containing this script
script_dir = os.path.dirname(os.path.abspath(__file__))

# List of figure scripts to run (in order)
FIGURE_SCRIPTS = [
    'curie_facilities_figures.py',
    'reactors_facilities_figures.py',
    'frontend_facilities_figures.py',
    'mines_reserves_facilities_figures.py',
    'repositories_facilities_figures.py',
    'interim_facilities_figures.py',
    'facility_comparison_figs.py'
]

def run_script(script_name):
    """Run a single figure generation script."""
    script_path = os.path.join(script_dir, script_name)
    
    if not os.path.exists(script_path):
        print(f"  ✗ Script not found: {script_name}")
        return False
    
    print(f"\nRunning {script_name}...")
    print("=" * 80)
    
    try:
        # Run the script as a subprocess
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=script_dir,
            capture_output=False,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✓ {script_name} completed successfully")
            return True
        else:
            print(f"✗ {script_name} failed with exit code {result.returncode}")
            return False
            
    except Exception as e:
        print(f"✗ Error running {script_name}: {e}")
        return False

def main():
    """Main function to run all figure generation scripts."""
    print("=" * 80)
    print("GENERATING ALL DEMOGRAPHIC FIGURES")
    print("=" * 80)
    print(f"Total scripts to run: {len(FIGURE_SCRIPTS)}")
    
    start_time = time.time()
    results = {}
    
    for script in FIGURE_SCRIPTS:
        success = run_script(script)
        results[script] = success
    
    # Summary
    end_time = time.time()
    elapsed = end_time - start_time
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    successful = sum(1 for v in results.values() if v)
    failed = len(results) - successful
    
    for script, success in results.items():
        status = "✓" if success else "✗"
        print(f"  {status} {script}")
    
    print(f"\nTotal: {successful}/{len(results)} successful, {failed} failed")
    print(f"Time elapsed: {elapsed:.1f} seconds")
    print("=" * 80)
    
    if failed > 0:
        sys.exit(1)
    else:
        print("\n✓ All figures generated successfully!")

if __name__ == "__main__":
    main()
