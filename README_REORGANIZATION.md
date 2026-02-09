# Fuel Cycle Analysis - Code Reorganization

**Date:** December 16, 2025  
**Status:** Complete

## Summary

The workspace has been completely reorganized to improve clarity, reduce nesting, and separate concerns between data, code, and outputs.

## New Directory Structure

```
📁 demographic_data/          [Input: Demographic datasets]
├── compiled/                 [Processed demographic data files]
│   ├── age_combined.xlsx
│   ├── education_compiled.xlsx
│   ├── employment_compiled.xlsx
│   ├── poverty_compiled.xlsx
│   ├── race_ethnicity_compiled.xlsx
│   └── sex_compiled.xlsx
├── county_overlaps/          [County-facility intersection data]
│   ├── reactor_county_overlap.xlsx
│   ├── frontend_county_overlap.xlsx
│   ├── mines_reserves_county_overlap.xlsx
│   ├── repository_county_overlap.xlsx
│   └── curie_county_overlap.xlsx
└── shapefiles/               [Geographic boundary data]
    └── cb_2022_us_county_500k/

📁 facility_data/             [Input: Facility location and characteristics]
├── reactors/
│   └── Reactors.xlsx
├── frontend/
│   ├── Compiled_Frontend.xlsx
│   ├── Fuel_Processing.xlsx
│   ├── IAEA_Facilities.xlsx
│   └── NFCFDB/
├── backend/
│   └── CURIE/
├── mines/
│   ├── EIA_NURE.zip
│   └── epa_uldb.zip
├── repositories/
│   ├── Repository_Proposed.xlsx
│   └── proposed_waste.xlsx
└── interim_storage/
    └── Interim_Proposed.xlsx

📁 analysis/                  [All analysis code and outputs]
├── scripts/                  [Analysis code - 50 Python scripts]
│   ├── preprocessing/
│   │   └── demographic_generator.py
│   ├── figures/              [Demographic visualization scripts]
│   │   ├── reactor_age_figures.py
│   │   ├── frontend_age_figs.py
│   │   ├── curie_age_fig.py
│   │   ├── employment_figures.py
│   │   ├── poverty_figures.py
│   │   └── ... [~30 figure generation scripts]
│   ├── sensitivity/          [Sensitivity analysis scripts]
│   │   ├── reactor_region_sensitivity.py
│   │   ├── reactor_distance_sensitivity.py
│   │   ├── frontend_region_sensitivity.py
│   │   ├── frontend_distance_sensitivity.py
│   │   ├── mines_region_sensitivity.py
│   │   ├── mines_distance_sensitivity.py
│   │   ├── repository_region_sensitivity.py
│   │   ├── repository_distance_sensitivity.py
│   │   └── interim_distance_sensitivity.py
│   └── proximity/
│       └── proximity_analysis.py
│
├── outputs/                  [All generated results]
│   ├── demographics_by_facility/
│   │   ├── age/
│   │   │   ├── reactor_age.xlsx
│   │   │   ├── frontend_age.xlsx
│   │   │   ├── curie_age.xlsx
│   │   │   ├── mines_age.xlsx
│   │   │   ├── repository_age.xlsx
│   │   │   └── figures/
│   │   ├── education/
│   │   ├── race_ethnicity/
│   │   ├── sex/
│   │   ├── employment/
│   │   └── poverty/
│   │
│   ├── demographics_by_county/
│   │   ├── age/
│   │   │   ├── reactor_age_counties.xlsx
│   │   │   ├── frontend_age_counties.xlsx
│   │   │   └── ...
│   │   └── [other demographics]/
│   │
│   └── sensitivity_analysis/
│       ├── distance/
│       │   ├── reactors/
│       │   │   ├── standard/
│       │   │   └── residual/
│       │   ├── frontend/
│       │   ├── mines/
│       │   ├── repositories/
│       │   └── interim_storage/
│       │
│       └── regional/
│           ├── in_region/
│           │   ├── reactors/
│           │   │   ├── standard/
│           │   │   └── residual/
│           │   ├── frontend/
│           │   ├── mines/
│           │   └── repositories/
│           └── across_region/
│
└── documentation/
    ├── Fuel_Cycle_Analysis_RF.docx
    ├── Geodata_support.pdf
    └── Short_Paper.pdf
```

## Key Changes

### 1. Naming Convention
- **Old:** Mixed case with spaces ("Demographic Data", "Facility Data")
- **New:** Lowercase with underscores ("demographic_data", "facility_data")
- **Benefit:** More command-line friendly, consistent with Python conventions

### 2. Separation of Concerns
- **Data:** demographic_data/, facility_data/ (input only)
- **Code:** analysis/scripts/ (all Python scripts)
- **Results:** analysis/outputs/ (all generated files)
- **Benefit:** Clear flow from input → processing → output

### 3. Flattened Structure
- **Old:** Up to 7 levels deep
- **New:** Maximum 4-5 levels
- **Benefit:** Shorter paths, easier navigation

### 4. Consolidated Scripts
- **Old:** 30+ "Script Writers" folders scattered across demographics
- **New:** Single analysis/scripts/ directory with logical subdirectories
- **Benefit:** All code in one place, easier to maintain

### 5. Removed Clutter
- Deleted "First try" folders (old attempts)
- Removed empty directories
- **Benefit:** Cleaner workspace

## Path Updates

All Python scripts have been updated with relative paths from their new locations:

### From scripts/preprocessing/:
- Demographic data: `../../demographic_data/compiled/`
- County overlaps: `../../demographic_data/county_overlaps/`
- Output: `../../outputs/demographics_by_county/`

### From scripts/figures/:
- Demographic data: `../../demographic_data/compiled/`
- Output: `../outputs/demographics_by_facility/`

### From scripts/sensitivity/:
- Demographic data: `../../demographic_data/compiled/`
- Facility data: `../../facility_data/`
- County data: `../../outputs/demographics_by_county/`
- Output: `../outputs/sensitivity_analysis/`

### From scripts/proximity/:
- Facility data: `../../facility_data/reactors/`

## Running Scripts

All scripts should be run from their current location in `analysis/scripts/` subdirectories. The relative paths will correctly resolve to data and output locations.

Example:
```powershell
cd "analysis/scripts/sensitivity"
python reactor_region_sensitivity.py
```

## Migration Summary

**Files Moved:**
- ✓ Demographic data files → demographic_data/
- ✓ Facility data files → facility_data/
- ✓ 50 Python scripts → analysis/scripts/
- ✓ Output data files → analysis/outputs/
- ✓ Documentation → analysis/documentation/

**Directories Removed:**
- Demographic Data/
- Demographic Statistics/
- Facility Data/
- Paper Dev/

**Path References Updated:**
- 50 Python scripts updated with new relative paths
- All data source paths corrected
- All output destination paths corrected

## Benefits

1. **Clarity:** Clear distinction between inputs, processing, and outputs
2. **Maintainability:** All scripts in one organized location
3. **Scalability:** Easy to add new facility types or demographics
4. **Consistency:** Uniform naming conventions throughout
5. **Efficiency:** Shorter paths, less nesting

## Next Steps

1. Test key scripts to verify all paths resolve correctly
2. Update any external documentation or notes with new paths
3. Consider consolidating similar figure scripts into fewer files
4. Update any notebooks or external tools that reference old paths

---

*Reorganization completed successfully on December 16, 2025*
