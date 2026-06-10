# Temporal Overlap Calculator - QGIS Plugin

## Overview

This QGIS plugin calculates the percentage overlap between a static input layer and temporal overlay layers. The plugin measures **how much the input layer is covered by overlay features over time**, accounting for:

- **Temporal ranges**: Each overlay feature has a begin and end date/time
- **Year-by-year analysis**: If a feature exists at any point in a year, it's counted for the entire year
- **Deduplication**: Overlapping overlay features are unioned, so their overlap portion is counted only once
- **Accurate area measurement**: Uses QGIS's `QgsDistanceArea` for ellipsoidal/projected areas

## Installation

1. Copy the `Overlap` folder to your QGIS plugins directory:
   - **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

2. Restart QGIS or reload plugins via **Plugins > Manage and Install Plugins**

3. Enable the plugin: In **Plugins > Manage and Install Plugins**, search for "Temporal Overlap" and enable it

## Usage

### Basic Workflow

1. **Prepare your data**:
   - **Input layer**: Static polygon layer (e.g., water bodies, regions)
   - **Overlay layer(s)**: Temporal polygon/point layers with date/time fields
   - All layers must be in the **same CRS**

2. **Open the plugin**: Go to **Plugins > Temporal Overlap > Temporal Overlap Calculator**

3. **Configure settings**:
   - **Input layer**: Select your static layer
   - **Overlay layers**: Select one or more temporal layers (use Ctrl+Click for multiple)
   - **Begin time field**: Field name with start dates (e.g., `date_in`, `start_time`)
   - **End time field**: Field name with end dates (e.g., `date_out`, `end_time`)
   - **Output area units**: Choose desired unit (m², km², nm², etc.)

4. **Calculate**: Click **Calculate Overlap**

5. **Review and export**: 
   - View results in the table (Year, areas, percentage)
   - Click **Save Results to CSV** to export

## Supported Date/Time Formats

The plugin automatically parses various date formats:

- `MM/DD/YYYY`, `MM/DD/YY`, `MM-DD-YYYY`
- `DD/MM/YYYY`, `DD-MM-YYYY`
- `YYYY-MM-DD`, `YYYY/MM/DD`
- `YYYY-MM-DD HH:MM:SS`, `YYYY-MM-DD HH:MM`
- `M/D/YYYY HH:MM:SS`, `M/D/YYYY HH:MM`
- `Mon DD YYYY`, `Month DD YYYY`, `DD Mon YYYY`, `DD Month YYYY`
- Excel serial dates (e.g., `45000`)
- ISO 8601 with timezone

## Calculation Logic

### Key Features

1. **Input Layer Union**: All input features are unioned into a single geometry
2. **Overlay by Year**: For each year, all overlay features active that year are collected
3. **Overlay Union**: Overlay geometries per year are unioned (deduplicating overlaps)
4. **Intersection**: The intersection of input union and overlay union is calculated
5. **Area Measurement**: Uses `QgsDistanceArea` for accurate ellipsoidal/projected areas
6. **Percentage**: `(overlap_area / input_area) * 100`

### Example

Given:
- Input layer: 100 nm² total
- Year 2020, Overlay features A and B:
  - Feature A: 10 nm²
  - Feature B: 10 nm², overlapping Feature A by 5 nm²
  - Both fully cover input layer

Calculation:
1. Union of A and B = 10 + 10 - 5 = 15 nm²
2. Intersection with input = 15 nm²
3. Percentage = (15 / 100) × 100 = 15%

## Output CSV

The CSV file contains columns:
- **Year**: Year of the analysis
- **Input Area (unit)**: Total area of input layer (in selected units)
- **Overlap Area (unit)**: Area of input covered by overlays (in selected units)
- **Overlap Area (nm²)**: Same as above, always in nautical miles²
- **Overlap %**: Percentage of input covered

## Troubleshooting

### No results returned
- Verify all layers have the same CRS
- Check that time fields exist and are correctly named
- Ensure overlay features have valid geometries (use **Vector > Check Geometry Validity**)
- Confirm at least one feature's date range falls within a calendar year

### Unexpected overlap percentages
- Check for invalid/corrupt geometries in source layers
- Verify time field values are being correctly parsed
- Use a consistent CRS across all operations (avoid on-the-fly reprojections)
- For geographic layers (EPSG:4326), ensure you've selected an appropriate output unit (e.g., nm² or m²)

### Performance issues with large datasets
- Simplify geometries if possible (reduce vertices)
- Work with a subset of years if processing is slow
- Consider pre-filtering overlay layers by date range

## Technical Details

### Area Measurement
- Uses `QgsDistanceArea` with project ellipsoid and transform context
- For geographic CRS (degrees), areas are measured in square meters
- Conversion factors provided for m², km², ha, ft², mi², nm², etc.

### Supported CRS
- Any QGIS-supported CRS (geographic, projected, local)
- All layers must share the same CRS

## Plugin Files

- `Overlap.py`: Main plugin class
- `Overlap_dialog.py`: Dialog UI and calculation logic
- `__init__.py`: Package initialization
- `metadata.txt`: Plugin metadata for QGIS

## Limitations

- All layers must have the same CRS (no automatic reprojection)
- Time fields must exist in overlay layers
- Input layer is assumed static (no temporal component)
- Large datasets (millions of features) may be slow

## Future Enhancements

- Support for raster input/overlay layers
- Interactive date range filtering
- Automated CRS alignment
- Performance optimization for large datasets
- Web interface export

## License

See repository for license details.

## Support

For issues or feature requests, contact the development team or open an issue in the repository.
