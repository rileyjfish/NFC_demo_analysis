import pandas as pd
import numpy as np
import re

# Load cleaned map data
df = pd.read_excel('Facility Data/CURIE/MapData - Cleaned.xlsx')

# Create a site_name by removing trailing numeric unit identifiers (e.g., 'Braidwood 1' -> 'Braidwood')
def site_from_reactor(name):
    if pd.isna(name):
        return name
    s = str(name).strip()
    # remove trailing unit numbers or parentheses like ' Unit 1' or ' 1' or '#1'
    s = re.sub(r"\s*(unit|reactor|nr|no)?\s*\#?\(?\d+\)?$", "", s, flags=re.IGNORECASE).strip()
    return s

df['site_name'] = df['reactor_name'].apply(site_from_reactor)

# Years range
start_year = int(df['Discharge_Year'].min())
yr = np.arange(start_year, 2026, 1)

# Cumulative MTHM by reactor_name x year (preserve original behavior)
rx_units = df['reactor_name'].unique()
cum_MTHM_by_reactor = pd.DataFrame(index=rx_units, columns=yr, dtype=float)
for rx in rx_units:
    for y in yr:
        cum_MTHM_by_reactor.loc[rx, y] = df[(df['reactor_name'] == rx) & (df['Discharge_Year'] <= y)]['Metric Tons of Heavy Metal (MTHM)'].sum()

# Cumulative MTHM by site_name x year (sum reactors at same site)
site_names = df['site_name'].unique()
cum_MTHM_by_site = pd.DataFrame(index=site_names, columns=yr, dtype=float)
for site in site_names:
    for y in yr:
        cum_MTHM_by_site.loc[site, y] = df[(df['site_name'] == site) & (df['Discharge_Year'] <= y)]['Metric Tons of Heavy Metal (MTHM)'].sum()


# Set index labels for clarity
cum_MTHM_by_reactor.index.name = 'reactor'
cum_MTHM_by_site.index.name = 'site'

# Save outputs to an Excel workbook with two sheets
with pd.ExcelWriter('Facility Data\\CURIE\\Cumulative Interim Storage.xlsx') as writer:
    cum_MTHM_by_reactor.to_excel(writer, sheet_name='by_reactor')
    cum_MTHM_by_site.to_excel(writer, sheet_name='by_site')

print("Total interim waste in 2025 (by reactor):", cum_MTHM_by_reactor[2025].sum().round(1), "MTHM")
print("Total interim waste in 2025 (by site):", cum_MTHM_by_site[2025].sum().round(1), "MTHM")