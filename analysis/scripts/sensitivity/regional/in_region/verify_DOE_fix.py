"""Quick verification that DOE figures show correct regions after fix"""
import pandas as pd

file_path = r'c:\Users\rjf\Desktop\Research\Fuel Cycle Analysis\analysis\outputs\demographics_by_county\age\interim_prop_age_counties.xlsx'

stages = {
    'Stage 1': 'Stage 4 - 1990',
    'Stage 2': 'Stage 5 - 1990', 
    'Stage 3': 'Stage 6 - 1990'
}

print("DOE Facility Exposure by Region")
print("="*60)

for stage, sheet in stages.items():
    df = pd.read_excel(file_path, sheet_name=sheet)
    df_exp = df[df['Buffer_Fraction'] > 0]
    
    print(f"\n{stage} ({sheet}):")
    counts = df_exp.groupby('Region')['FIPS'].count()
    print(counts)
    
    if 4 in counts.index or 5 in counts.index:
        print("  ⚠️ WARNING: Southwest (4) or West (5) data found!")
    else:
        print("  ✓ Correct: No Southwest/West exposure")
