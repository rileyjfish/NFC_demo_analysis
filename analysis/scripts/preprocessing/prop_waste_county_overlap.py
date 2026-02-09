import geopandas as gpd
import pandas as pd
import os

# Get absolute paths
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))

# Load county shapefile
county_zip = os.path.join(base_dir, 'demographic_data', 'shapefiles', 'cb_2022_us_county_500k.zip')
county_gdf = gpd.read_file(f'zip://{county_zip}')

# Read both sheets from the new Excel file
facility_xls = pd.ExcelFile(os.path.join(base_dir, 'facility_data', 'repositories', 'Repository_Proposed.xlsx'))
sheet_map = {
    'Interim': ('InterimCountyOverlap', 'InterimBufferOverlap'),
    'Repositories': ('RepositoryCountyOverlap', 'RepositoryBufferOverlap')
}

output_path = os.path.join(base_dir, 'demographic_data', 'county_overlaps', 'prop_waste_county_overlap.xlsx')
excel_writer = pd.ExcelWriter(output_path, engine='xlsxwriter')

for sheet, (county_label, buffer_label) in sheet_map.items():
    facility_df = facility_xls.parse(sheet)
    # Ensure correct column types
    facility_df['Lat'] = pd.to_numeric(facility_df['Lat'], errors='coerce')
    facility_df['Long'] = pd.to_numeric(facility_df['Long'], errors='coerce')

    # Create GeoDataFrame for facilities and project to meters
    facility_gdf = gpd.GeoDataFrame(
        facility_df,
        geometry=gpd.points_from_xy(facility_df['Long'], facility_df['Lat']),
        crs="EPSG:4326"
    ).to_crs(epsg=5070)

    # Create 50 mile buffer around each facility
    buffer_distance = 50 * 1609.344
    facility_gdf['buffer'] = facility_gdf.geometry.buffer(buffer_distance)

    # Project counties to same CRS
    county_gdf_proj = county_gdf.to_crs(facility_gdf.crs)

    # Prepare buffer GeoDataFrame
    buffer_gdf = gpd.GeoDataFrame(
        facility_gdf[['FID', 'Type', 'Name', 'Capacity', 'Approx Year', 'Note']],
        geometry=facility_gdf['buffer'],
        crs=facility_gdf.crs
    )

    # Spatial intersection
    overlap_gdf = gpd.overlay(county_gdf_proj, buffer_gdf, how='intersection')

    # Calculate overlap metrics
    overlap_gdf['overlap_area'] = overlap_gdf.geometry.area
    overlap_gdf['county_area'] = county_gdf_proj.set_index('GEOID').loc[overlap_gdf['GEOID'], 'geometry'].area.values
    overlap_gdf['buffer_area'] = buffer_gdf.set_index('FID').loc[overlap_gdf['FID'], 'geometry'].area.values
    overlap_gdf['percent_overlap'] = overlap_gdf['overlap_area'] / overlap_gdf['county_area']
    overlap_gdf['percent_buffer_overlap'] = overlap_gdf['overlap_area'] / overlap_gdf['buffer_area']

    # Prepare combined results DataFrame with both metrics
    combined_df = overlap_gdf[['Name', 'FID', 'Type', 'Capacity', 'Approx Year', 'Note', 'GEOID', 'percent_overlap', 'percent_buffer_overlap']].rename(
        columns={'GEOID': 'CountyFIPS'}
    )

    # Pivot each metric to 2D tables for Excel output, including extra attributes in the index
    pivot_county = combined_df.pivot_table(
        index=['Name', 'FID', 'Type', 'Capacity', 'Approx Year', 'Note'],
        columns='CountyFIPS',
        values='percent_overlap',
        fill_value=0
    )
    pivot_buffer = combined_df.pivot_table(
        index=['Name', 'FID', 'Type', 'Capacity', 'Approx Year', 'Note'],
        columns='CountyFIPS',
        values='percent_buffer_overlap',
        fill_value=0
    )

    # Add 'G' prefix to column names to ensure GEOID values are treated as strings in Excel
    pivot_county.columns = ['G' + str(col) for col in pivot_county.columns]
    pivot_buffer.columns = ['G' + str(col) for col in pivot_buffer.columns]

    # Write to Excel file with 4 sheets
    pivot_county.to_excel(excel_writer, sheet_name=county_label)
    pivot_buffer.to_excel(excel_writer, sheet_name=buffer_label)

excel_writer.close()

print("✓ Created prop_waste_county_overlap.xlsx")


