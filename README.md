# Percentage Overlap QGIS Plugin

This plugin calculates the overlap between a static input layer and one or more overlay layers over time.

## Features

- Calculate percentage overlap and absolute overlap area.
- Output values in the selected area unit plus nautical miles squared (`nm²`).
- Handle overlay features with a begin/end date range and count them for the entire active year.
- Honor an optional per-year attribute on the base input layer.
- Support combined results, per-overlay-layer results, or both.

## Installation

1. Copy the `percentage_overlap` folder into your QGIS plugin directory, or add it to your Python path.
2. Restart QGIS.
3. Enable the plugin from the Plugin Manager if necessary.

## Usage

1. Select the base input layer.
2. (Optional) Select the base input layer's per-year attribute in the "Base year field on input layer" dropdown.
   - Leave blank to treat the input layer as static over time.
3. Select one or more overlay layers.
4. Choose the overlay begin/end fields.
   - Leave both blank to compare full layers without temporal matching.
5. Choose the output area unit.
6. Select the output mode:
   - `Combined`: combined result across all overlay layers.
   - `Per overlay layer`: separate result rows for each overlay layer.
   - `Both`: combined and per-layer results.
7. Click `Calculate overlap`.
8. Click `Save results to CSV` to export the table.

## Notes

- If the overlay date fields are provided, features are assumed to exist for the entire calendar year in which they are present.
- If the base year field is provided, the plugin matches overlap by year using the base layer's year values.
- Overlap among multiple overlay features is deduplicated by taking a geometric union before intersection.

## Example

- Base layer has a `year` field representing annual geometry.
- Overlay layer has `date in` and `date out` fields.
- The plugin calculates the area of overlap for each year where both base and overlay geometries exist.

## Sample test case

Use a base layer with fields like:

- `id`
- `year`
- geometry

And an overlay layer with fields like:

- `id`
- `date_in`
- `date_out`
- geometry

Example values for a simple test:

Base layer row:

- `id`: 1
- `year`: 2024

Overlay layer rows:

- `id`: 1, `date_in`: 2024-01-10, `date_out`: 2024-12-31
- `id`: 2, `date_in`: 2024-02-25, `date_out`: 2024-05-15

Workflow:

1. Load both layers in QGIS.
2. Set the base layer as the input layer.
3. Set `Base year field on input layer` to `year`.
4. Add the overlay layer in the overlay layers selection.
5. Set `Overlay begin field` to `date_in` and `Overlay end field` to `date_out`.
6. Choose output mode `Both` to see combined and per-layer overlap rows.
7. Click `Calculate overlap`.
8. Export the table to CSV using `Save results to CSV`.

This test verifies the plugin can parse common date formats, match by base year, and generate per-year overlap output.
