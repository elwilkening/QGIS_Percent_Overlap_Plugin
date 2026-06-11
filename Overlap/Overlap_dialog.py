"""
Dialog and calculation logic for temporal overlay calculator.
"""

import datetime
import re
import math
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QLabel,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
)
from qgis.core import (
    QgsGeometry,
    QgsProject,
    QgsVectorLayer,
    QgsDistanceArea,
    QgsUnitTypes,
)


class OverlapDialog(QDialog):
    """Main dialog for temporal overlay calculation."""

    def __init__(self, iface):
        """Initialize the dialog.
        
        Args:
            iface: QGIS interface instance
        """
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.results = []
        self.setWindowTitle("Temporal Overlap Calculator")
        self.resize(900, 600)
        self.setupUi()
        self.refreshLayerList()

    def setupUi(self):
        """Set up the user interface."""
        mainLayout = QVBoxLayout(self)

        # Input layer selection
        row = QHBoxLayout()
        row.addWidget(QLabel("Input layer (static):"), 0)
        self.inputLayerCombo = QComboBox()
        self.inputLayerCombo.currentIndexChanged.connect(self.updateFieldLists)
        row.addWidget(self.inputLayerCombo, 1)
        mainLayout.addLayout(row)

        # Overlay layer selection
        row = QHBoxLayout()
        row.addWidget(QLabel("Overlay layers (temporal):"), 0)
        self.overlayLayerList = QListWidget()
        self.overlayLayerList.setSelectionMode(QListWidget.MultiSelection)
        self.overlayLayerList.itemSelectionChanged.connect(self.updateFieldLists)
        row.addWidget(self.overlayLayerList, 1)
        mainLayout.addLayout(row)

        # Time field selection
        row = QHBoxLayout()
        row.addWidget(QLabel("Begin time field (overlay layers):"), 0)
        self.beginTimeField = QComboBox()
        self.beginTimeField.setEditable(True)
        self.beginTimeField.setToolTip("Field name containing feature start date/time")
        row.addWidget(self.beginTimeField, 1)
        mainLayout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("End time field (overlay layers):"), 0)
        self.endTimeField = QComboBox()
        self.endTimeField.setEditable(True)
        self.endTimeField.setToolTip("Field name containing feature end date/time")
        row.addWidget(self.endTimeField, 1)
        mainLayout.addLayout(row)

        # Output unit selection
        row = QHBoxLayout()
        row.addWidget(QLabel("Output area units:"), 0)
        self.outputUnitCombo = QComboBox()
        self.outputUnitCombo.currentIndexChanged.connect(self.onOutputUnitChanged)
        row.addWidget(self.outputUnitCombo, 1)
        mainLayout.addLayout(row)

        # Buttons
        row = QHBoxLayout()
        self.refreshButton = QPushButton("Refresh Layers")
        self.refreshButton.clicked.connect(self.refreshLayerList)
        row.addWidget(self.refreshButton)

        self.calculateButton = QPushButton("Calculate Overlap")
        self.calculateButton.clicked.connect(self.onCalculate)
        row.addWidget(self.calculateButton)

        row.addStretch()

        self.saveCsvButton = QPushButton("Save Results to CSV")
        self.saveCsvButton.clicked.connect(self.onSaveCsv)
        self.saveCsvButton.setEnabled(False)
        row.addWidget(self.saveCsvButton)
        mainLayout.addLayout(row)

        # Results table
        self.resultsTable = QTableWidget(0, 5)
        self.resultsTable.setHorizontalHeaderLabels([
            "Year",
            "Input Area (map units²)",
            "Overlap Area (map units²)",
            "Overlap Area (nm²)",
            "Overlap %"
        ])
        self.resultsTable.horizontalHeader().setStretchLastSection(True)
        mainLayout.addWidget(self.resultsTable)

        self.areaUnitLabel = "map units²"
        self.updateAreaHeaders(None)

    def refreshLayerList(self):
        """Refresh the layer lists from the project."""
        self.inputLayerCombo.clear()
        self.overlayLayerList.clear()
        self.beginTimeField.clear()
        self.endTimeField.clear()

        layers = [
            layer for layer in QgsProject.instance().mapLayers().values()
            if isinstance(layer, QgsVectorLayer)
        ]
        for layer in layers:
            self.inputLayerCombo.addItem(layer.name(), layer.id())
            item = QListWidgetItem(layer.name())
            item.setData(Qt.UserRole, layer.id())
            self.overlayLayerList.addItem(item)

        self.updateFieldLists()

    def updateFieldLists(self):
        """Update available fields based on selected layers."""
        self.beginTimeField.clear()
        self.endTimeField.clear()

        selected_overlays = self.getSelectedOverlayLayers()
        if selected_overlays:
            common_fields = self.getCommonFieldNames(selected_overlays)
            self.beginTimeField.addItems([""] + common_fields)
            self.endTimeField.addItems([""] + common_fields)

        input_layer = self.getCurrentInputLayer()
        self.updateOutputUnits(input_layer)
        self.updateCalculateButtonState()

    def getCurrentInputLayer(self):
        """Get the currently selected input layer."""
        idx = self.inputLayerCombo.currentIndex()
        if idx < 0:
            return None
        layer_id = self.inputLayerCombo.itemData(idx)
        return QgsProject.instance().mapLayer(layer_id)

    def getSelectedOverlayLayers(self):
        """Get all selected overlay layers."""
        selected_items = self.overlayLayerList.selectedItems()
        layers = []
        for item in selected_items:
            layer_id = item.data(Qt.UserRole)
            layer = QgsProject.instance().mapLayer(layer_id)
            if isinstance(layer, QgsVectorLayer):
                layers.append(layer)
        return layers

    def getCommonFieldNames(self, layers):
        """Get field names common to all layers."""
        if not layers:
            return []
        all_names = [set(layer.fields().names()) for layer in layers]
        common = set.intersection(*all_names)
        return sorted(common)

    def updateCalculateButtonState(self):
        """Enable/disable calculate button based on selections."""
        input_layer = self.getCurrentInputLayer()
        overlay_layers = self.getSelectedOverlayLayers()

        if input_layer is None or not overlay_layers:
            self.calculateButton.setEnabled(False)
            self.calculateButton.setToolTip("Select both input and overlay layers.")
            return

        # Check CRS match
        for overlay_layer in overlay_layers:
            if input_layer.crs().authid() != overlay_layer.crs().authid():
                self.calculateButton.setEnabled(False)
                self.calculateButton.setToolTip("All layers must have the same CRS.")
                return

        self.calculateButton.setEnabled(True)
        self.calculateButton.setToolTip("Calculate overlap by year")

    def updateOutputUnits(self, layer):
        """Update available output unit choices."""
        previous_unit = self.outputUnitCombo.currentText()
        self.outputUnitCombo.clear()
        choices = self.getAreaUnitChoices(layer)
        self.outputUnitCombo.addItems(choices)
        if previous_unit and previous_unit in choices:
            self.outputUnitCombo.setCurrentText(previous_unit)
        elif choices:
            self.outputUnitCombo.setCurrentIndex(0)

    def getAreaUnitChoices(self, layer):
        """Get available area unit choices for a layer."""
        if layer is None:
            return ["map units²"]
        try:
            map_unit = layer.crs().mapUnits()
        except Exception:
            return ["map units²"]

        if map_unit == QgsUnitTypes.DistanceMeters:
            return ["m²", "km²", "ha", "ft²", "mi²", "nm²", "map units²"]
        if map_unit == QgsUnitTypes.DistanceKilometers:
            return ["km²", "m²", "ha", "ft²", "mi²", "nm²", "map units²"]
        if map_unit in (QgsUnitTypes.DistanceFeet, QgsUnitTypes.DistanceYards,
                        QgsUnitTypes.DistanceMiles, QgsUnitTypes.DistanceNauticalMiles):
            return ["ft²", "yd²", "mi²", "nm²", "m²", "km²", "ha", "map units²"]
        if map_unit == QgsUnitTypes.DistanceDegrees:
            # Geographic CRS: areas measured in m² by QgsDistanceArea
            return ["m²", "km²", "ha", "ft²", "mi²", "nm²", "deg²", "map units²"]
        return ["map units²"]

    def getAreaConversionFactor(self, layer, output_unit):
        """Get conversion factor from map units² to output units²."""
        if layer is None or not output_unit:
            return 1.0

        try:
            map_unit = layer.crs().mapUnits()
        except Exception:
            return 1.0

        # Normalize degree CRS to meters for conversion (areas measured in m²)
        if map_unit == QgsUnitTypes.DistanceDegrees:
            map_unit = QgsUnitTypes.DistanceMeters

        # Conversion factors
        if map_unit == QgsUnitTypes.DistanceMeters:
            conversions = {
                "m²": 1.0,
                "km²": 1e-6,
                "ha": 1e-4,
                "ft²": 10.76391,
                "yd²": 1.1960,
                "mi²": 3.861e-7,
                "nm²": 2.590e-7,
            }
            return conversions.get(output_unit, 1.0)
        elif map_unit == QgsUnitTypes.DistanceKilometers:
            conversions = {
                "km²": 1.0,
                "m²": 1e6,
                "ha": 100.0,
                "ft²": 1.0764e7,
                "yd²": 1.196e6,
                "mi²": 0.3861,
                "nm²": 0.2590,
            }
            return conversions.get(output_unit, 1.0)
        elif map_unit == QgsUnitTypes.DistanceFeet:
            conversions = {
                "ft²": 1.0,
                "yd²": 1.0 / 9.0,
                "mi²": 1.0 / (5280.0 * 5280.0),
                "nm²": 1.0 / (6076.12 * 6076.12),
                "m²": 0.09290304,
                "km²": 9.290e-8,
            }
            return conversions.get(output_unit, 1.0)
        elif map_unit == QgsUnitTypes.DistanceMiles:
            conversions = {
                "mi²": 1.0,
                "ft²": 5280.0 * 5280.0,
                "yd²": 1760.0 * 1760.0,
                "nm²": (1.0 / 1.1508) ** 2,
                "m²": 2589988.11,
                "km²": 2.589988,
            }
            return conversions.get(output_unit, 1.0)
        elif map_unit == QgsUnitTypes.DistanceNauticalMiles:
            conversions = {
                "nm²": 1.0,
                "mi²": 1.324,
                "ft²": 6076.12 * 6076.12,
                "yd²": (6076.12 / 3.0) * (6076.12 / 3.0),
                "m²": 3429904.0,
                "km²": 3.429904,
            }
            return conversions.get(output_unit, 1.0)

        return 1.0

    def onOutputUnitChanged(self):
        """Handle output unit selection change."""
        if self.results:
            self.populateResultsTable()

    def updateAreaHeaders(self, layer):
        """Update table headers with current unit label."""
        if self.outputUnitCombo.currentText():
            self.areaUnitLabel = self.outputUnitCombo.currentText()
        else:
            self.areaUnitLabel = "map units²"

    def onCalculate(self):
        """Calculate overlap when button is clicked."""
        input_layer = self.getCurrentInputLayer()
        overlay_layers = self.getSelectedOverlayLayers()
        begin_field = self.beginTimeField.currentText().strip()
        end_field = self.endTimeField.currentText().strip()

        if input_layer is None:
            QMessageBox.warning(self, "Error", "Please select an input layer.")
            return
        if not overlay_layers:
            QMessageBox.warning(self, "Error", "Please select overlay layers.")
            return

        try:
            self.results = self.calculateOverlap(
                input_layer, overlay_layers, begin_field, end_field
            )
        except Exception as exc:
            QMessageBox.warning(
                self, "Calculation Failed",
                f"An error occurred during calculation:\n{str(exc)}"
            )
            return

        if not self.results:
            QMessageBox.information(
                self, "No Results",
                "Calculation completed but produced no results. Check that:\n"
                "- Overlay layers have valid geometries\n"
                "- Time fields are correctly specified\n"
                "- Features have overlapping geometries"
            )
            return

        self.populateResultsTable()
        self.saveCsvButton.setEnabled(True)

    def calculateOverlap(self, input_layer, overlay_layers, begin_field, end_field):
        """
        Calculate overlap between input and overlay layers by year.
        
        Args:
            input_layer: Static input layer
            overlay_layers: List of temporal overlay layers
            begin_field: Field name for feature begin time
            end_field: Field name for feature end time
            
        Returns:
            List of dicts with year and overlap statistics
        """
        results = []

        # Build input layer geometry union
        input_geoms = []
        for feat in input_layer.getFeatures():
            geom = feat.geometry()
            valid_geom = self.normalizeGeometry(geom)
            if valid_geom is not None and not valid_geom.isEmpty():
                input_geoms.append(valid_geom)

        if not input_geoms:
            return results

        input_union = self.safeUnion(input_geoms)
        if input_union is None or input_union.isEmpty():
            return results
        # Debug: report input union bbox
        try:
            bbox = input_union.boundingBox()
            print(f"[Overlap] Input union bbox: {bbox.xMinimum()}, {bbox.yMinimum()} -> {bbox.xMaximum()}, {bbox.yMaximum()}")
        except Exception:
            pass

        input_area = self.getGeometryArea(input_union, input_layer)
        if input_area <= 0:
            return results

        # Helper to parse dates
        def parse_date(val):
            if val is None:
                return None
            try:
                # Handle Qt date objects
                if hasattr(val, 'toPyDate'):
                    return int(val.toPyDate().year)
                if hasattr(val, 'toPython'):
                    py = val.toPython()
                    if isinstance(py, datetime.date):
                        return int(py.year)
            except Exception:
                pass

            if isinstance(val, (datetime.datetime, datetime.date)):
                return int(val.year)

            # Excel serial date
            if isinstance(val, (int, float)):
                if 10000 <= val <= 60000:
                    try:
                        base_date = datetime.date(1899, 12, 30)
                        target = base_date + datetime.timedelta(days=int(val))
                        return int(target.year)
                    except Exception:
                        pass
                if 1000 <= int(val) <= datetime.datetime.now().year + 10:
                    return int(val)

            # String parsing
            s = str(val).strip() if val else ""
            if not s:
                return None

            # Try various date formats
            formats = [
                "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y",
                "%d/%m/%Y", "%d-%m-%Y",
                "%Y-%m-%d", "%Y/%m/%d",
                "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                "%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y",
            ]
            for fmt in formats:
                try:
                    dt = datetime.datetime.strptime(s, fmt)
                    return int(dt.year)
                except ValueError:
                    pass

            # Look for 4-digit year
            match = re.search(r"(19|20)\d{2}", s)
            if match:
                return int(match.group(0))

            return None

        # Collect geometries by year
        year_geoms = {}

        if begin_field and end_field:
            # Temporal mode: group by year
            for overlay in overlay_layers:
                for feat in overlay.getFeatures():
                    geom = self.normalizeGeometry(feat.geometry())
                    if geom is None or geom.isEmpty():
                        continue

                    begin_year = parse_date(feat[begin_field])
                    end_year = parse_date(feat[end_field])

                    if begin_year is None or end_year is None:
                        continue

                    if begin_year > end_year:
                        begin_year, end_year = end_year, begin_year

                    # Add geometry for each year in range
                    for year in range(begin_year, end_year + 1):
                        if year not in year_geoms:
                            year_geoms[year] = []
                        # Skip geometries with non-finite coordinates, try to repair once
                        if not self.geometryIsFinite(geom):
                            try:
                                repaired = geom.makeValid() or geom
                                if repaired is not None and not repaired.isEmpty():
                                    repaired = repaired.buffer(0, 5)
                                if repaired is not None and not repaired.isEmpty() and self.geometryIsFinite(repaired):
                                    year_geoms[year].append(repaired)
                                    continue
                            except Exception:
                                pass
                            print(f"[Overlap] Year {year}: skipping feature with invalid coordinates")
                            continue
                        year_geoms[year].append(geom)
        else:
            # Non-temporal mode: combine all
            all_geoms = []
            for overlay in overlay_layers:
                for feat in overlay.getFeatures():
                    geom = feat.geometry()
                    if geom and not geom.isEmpty():
                        all_geoms.append(geom)
            if all_geoms:
                year_geoms["all"] = all_geoms

        # Calculate overlap for each year
        for year in sorted(year_geoms.keys()):
            overlay_geoms = year_geoms[year]
            if not overlay_geoms:
                continue

            # Union overlays (so overlapping features count only once)
            overlay_union = self.safeUnion(overlay_geoms)
            if overlay_union is None or overlay_union.isEmpty():
                print(f"[Overlap] Year {year}: overlay_union is empty or None (count={len(overlay_geoms)})")
                continue

            # Debug: report overlay union bbox
            try:
                ob = overlay_union.boundingBox()
                print(f"[Overlap] Year {year}: overlay union bbox: {ob.xMinimum()}, {ob.yMinimum()} -> {ob.xMaximum()}, {ob.yMaximum()}")
            except Exception:
                pass

            # Intersection: how much of input is covered by overlay
            intersection = input_union.intersection(overlay_union)
            overlap_area = 0.0
            if intersection is None:
                print(f"[Overlap] Year {year}: intersection returned None")
            else:
                print(f"[Overlap] Year {year}: intersection isEmpty={intersection.isEmpty()}")

            if intersection and not intersection.isEmpty():
                overlap_area = self.getGeometryArea(intersection, input_layer)
            else:
                # Fallback: try reprojecting to a projected CRS and intersect there
                try:
                    src_crs = input_layer.crs()
                    proj_epsg = 3857
                    in_proj = self.reprojectGeometry(input_union, src_crs, proj_epsg)
                    ov_proj = self.reprojectGeometry(overlay_union, src_crs, proj_epsg)
                    if in_proj is not None and ov_proj is not None:
                        inter2 = in_proj.intersection(ov_proj)
                        if inter2 is not None and not inter2.isEmpty():
                            dest_crs = __import__('qgis').core.QgsCoordinateReferenceSystem(f"EPSG:{proj_epsg}")
                            overlap_area = self.measureAreaWithCrs(inter2, dest_crs)
                            print(f"[Overlap] Year {year}: fallback projected intersection area={overlap_area}")
                        else:
                            print(f"[Overlap] Year {year}: fallback projected intersection empty")
                    else:
                        print(f"[Overlap] Year {year}: could not reproject geometries for fallback")
                except Exception as e:
                    print(f"[Overlap] Year {year}: fallback projection/intersection failed: {e}")

                # Additional per-feature diagnostics when union intersection fails
                try:
                    per_feature_inters = []
                    for idx, feat_geom in enumerate(overlay_geoms):
                        try:
                            if feat_geom is None or feat_geom.isEmpty():
                                continue
                            intersects = input_union.intersects(feat_geom)
                            if intersects:
                                inter_f = input_union.intersection(feat_geom)
                                if inter_f is not None and not inter_f.isEmpty():
                                    per_feature_inters.append(inter_f)
                                    area_f = self.getGeometryArea(inter_f, input_layer)
                                else:
                                    area_f = 0.0
                                print(f"[Overlap] Year {year}: feature {idx} intersects true, area={area_f}")
                                # continue scanning to accumulate intersections
                            else:
                                if idx < 5:
                                    bbox_f = None
                                    try:
                                        b = feat_geom.boundingBox()
                                        bbox_f = (b.xMinimum(), b.yMinimum(), b.xMaximum(), b.yMaximum())
                                    except Exception:
                                        pass
                                    print(f"[Overlap] Year {year}: feature {idx} intersects false, bbox={bbox_f}")
                        except Exception as e:
                            print(f"[Overlap] Year {year}: feature {idx} test failed: {e}")
                    # If we collected per-feature intersections, union them and measure
                    if per_feature_inters:
                        try:
                            inter_union = self.safeUnion(per_feature_inters)
                            if inter_union is not None and not inter_union.isEmpty():
                                overlap_area = self.getGeometryArea(inter_union, input_layer)
                                print(f"[Overlap] Year {year}: per-feature intersection union area={overlap_area}")
                            else:
                                print(f"[Overlap] Year {year}: per-feature intersection union empty")
                        except Exception as e:
                            print(f"[Overlap] Year {year}: per-feature union failed: {e}")
                except Exception:
                    pass

            percent = (overlap_area / input_area * 100.0) if input_area > 0 else 0.0

            results.append({
                "year": year,
                "input_area": input_area,
                "overlap_area": overlap_area,
                "percent": percent,
            })

        return results

    def getGeometryArea(self, geom, layer):
        """
        Get area of geometry using QgsDistanceArea for accuracy.
        
        Args:
            geom: QgsGeometry object
            layer: Layer to get CRS from
            
        Returns:
            Area in map units²
        """
        if geom is None or geom.isEmpty():
            return 0.0

        try:
            dah = QgsDistanceArea()
            dah.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
            try:
                ell = QgsProject.instance().ellipsoid()
                if not ell:
                    ell = 'WGS84'
                dah.setEllipsoid(ell)
                if hasattr(dah, 'setEllipsoidalMode'):
                    dah.setEllipsoidalMode(True)
            except Exception:
                pass
            return abs(dah.measureArea(geom))
        except Exception:
            try:
                valid = self.normalizeGeometry(geom)
                if valid is not None and not valid.isEmpty():
                    return abs(dah.measureArea(valid))
            except Exception:
                pass
            # Fallback to planar area
            return abs(geom.area())

    def normalizeGeometry(self, geom):
        """Return a valid geometry if possible."""
        if geom is None or geom.isEmpty():
            return None
        try:
            valid = geom
            if hasattr(geom, 'isGeosValid') and not geom.isGeosValid():
                valid = geom.makeValid() or geom
            if valid is None or valid.isEmpty():
                valid = geom.buffer(0, 5)
            if valid is not None and not valid.isEmpty():
                return valid
        except Exception:
            pass
        return geom

    def geometryIsFinite(self, geom):
        """Return True if geometry's bounding box coordinates are finite numbers."""
        if geom is None or geom.isEmpty():
            return False
        try:
            bbox = geom.boundingBox()
            vals = [bbox.xMinimum(), bbox.yMinimum(), bbox.xMaximum(), bbox.yMaximum()]
            for v in vals:
                if not isinstance(v, (int, float)) or not math.isfinite(v):
                    return False
            return True
        except Exception:
            return False
    def reprojectGeometry(self, geom, source_crs, dest_epsg):
        """Return a copy of geom reprojected to dest_epsg, or None on failure."""
        try:
            from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform

            dest = QgsCoordinateReferenceSystem(f"EPSG:{dest_epsg}")
            xform = QgsCoordinateTransform(source_crs, dest, QgsProject.instance().transformContext())
            g = QgsGeometry(geom)
            g.transform(xform)
            return g
        except Exception:
            return None

    def measureAreaWithCrs(self, geom, crs):
        """Measure area of geom assuming coordinates are in the provided CRS."""
        try:
            dah = QgsDistanceArea()
            dah.setSourceCrs(crs, QgsProject.instance().transformContext())
            try:
                ell = QgsProject.instance().ellipsoid()
                if not ell:
                    ell = 'WGS84'
                dah.setEllipsoid(ell)
                if hasattr(dah, 'setEllipsoidalMode'):
                    dah.setEllipsoidalMode(True)
            except Exception:
                pass
            return abs(dah.measureArea(geom))
        except Exception:
            try:
                return abs(geom.area())
            except Exception:
                return 0.0

    def safeUnion(self, geoms):
        """Union geometries safely, filtering invalid geometry first."""
        valid_geoms = []
        for geom in geoms:
            geom = self.normalizeGeometry(geom)
            if geom is None or geom.isEmpty():
                continue

            # Ensure geometry has finite coordinates; try to repair once if not.
            if not self.geometryIsFinite(geom):
                try:
                    repaired = geom.makeValid() or geom
                    if repaired is not None and not repaired.isEmpty():
                        repaired = repaired.buffer(0, 5)
                    if repaired is not None and not repaired.isEmpty() and self.geometryIsFinite(repaired):
                        valid_geoms.append(repaired)
                        continue
                except Exception:
                    pass

                print("[Overlap] Skipping geometry with non-finite coordinates")
                continue

            valid_geoms.append(geom)

        if not valid_geoms:
            return None
        if len(valid_geoms) == 1:
            return valid_geoms[0]

        # First collect geometries into a single geometry, then attempt unaryUnion.
        try:
            collected = QgsGeometry.collectGeometry(valid_geoms)
            if collected is not None and not collected.isEmpty():
                try:
                    union = QgsGeometry.unaryUnion(collected)
                    if union is not None and not union.isEmpty():
                        return union
                except Exception:
                    # If unaryUnion on the collected geometry fails, return the collected geometry
                    return collected
        except Exception:
            pass

        return None

    def populateResultsTable(self):
        """Populate results table with calculated data."""
        self.resultsTable.clearContents()
        self.resultsTable.setRowCount(len(self.results))

        input_layer = self.getCurrentInputLayer()
        factor = self.getAreaConversionFactor(input_layer, self.outputUnitCombo.currentText())
        nm_factor = self.getAreaConversionFactor(input_layer, "nm²")

        for row, result in enumerate(self.results):
            year_str = str(result["year"])
            input_area_converted = result["input_area"] * factor
            overlap_area_converted = result["overlap_area"] * factor
            overlap_nm2 = result["overlap_area"] * nm_factor

            self.resultsTable.setItem(row, 0, QTableWidgetItem(year_str))
            self.resultsTable.setItem(row, 1, QTableWidgetItem(f"{input_area_converted:.4f}"))
            self.resultsTable.setItem(row, 2, QTableWidgetItem(f"{overlap_area_converted:.4f}"))
            self.resultsTable.setItem(row, 3, QTableWidgetItem(f"{overlap_nm2:.4f}"))
            self.resultsTable.setItem(row, 4, QTableWidgetItem(f"{result['percent']:.2f}%"))

        self.resultsTable.resizeColumnsToContents()

    def onSaveCsv(self):
        """Save results to CSV file."""
        if not self.results:
            QMessageBox.information(self, "No Results", "No results to save.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Results", "overlap_results.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f"Year,Input Area ({self.areaUnitLabel}),"
                        f"Overlap Area ({self.areaUnitLabel}),"
                        f"Overlap Area (nm²),Overlap %\n")

                input_layer = self.getCurrentInputLayer()
                factor = self.getAreaConversionFactor(input_layer, self.outputUnitCombo.currentText())
                nm_factor = self.getAreaConversionFactor(input_layer, "nm²")

                for result in self.results:
                    year = result["year"]
                    input_area = result["input_area"] * factor
                    overlap_area = result["overlap_area"] * factor
                    overlap_nm2 = result["overlap_area"] * nm_factor
                    percent = result["percent"]
                    f.write(f"{year},{input_area:.4f},{overlap_area:.4f},"
                            f"{overlap_nm2:.4f},{percent:.2f}\n")

            QMessageBox.information(self, "Success", f"Results saved to {path}")
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", f"Could not save file:\n{str(exc)}")
