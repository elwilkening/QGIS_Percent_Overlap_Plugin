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
    QgsFeatureRequest,
    QgsUnitTypes,
)
import datetime
import re


class PercentageOverlapDialog(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setWindowTitle("Percentage Overlap by Year")
        self.resize(820, 520)
        self.setupUi()
        self.refreshLayerList()

    def setupUi(self):
        mainLayout = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel("Input layer:"), 0)
        self.inputLayerCombo = QComboBox()
        self.inputLayerCombo.currentIndexChanged.connect(self.updateFieldLists)
        row.addWidget(self.inputLayerCombo, 1)
        mainLayout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Overlay layers:"), 0)
        self.overlayLayerList = QListWidget()
        self.overlayLayerList.setSelectionMode(QListWidget.MultiSelection)
        self.overlayLayerList.itemSelectionChanged.connect(self.updateFieldLists)
        row.addWidget(self.overlayLayerList, 1)
        overlayFieldsLayout = QVBoxLayout()
        overlayFieldsLayout.addWidget(QLabel("Begin year field on overlay layers:"))
        self.overlayBeginYearField = QComboBox()
        self.overlayBeginYearField.setEditable(True)
        self.overlayBeginYearField.setToolTip("If overlay layers use the same begin year field name, select or enter it here.")
        overlayFieldsLayout.addWidget(self.overlayBeginYearField)

        overlayFieldsLayout.addWidget(QLabel("End year field on overlay layers:"))
        self.overlayEndYearField = QComboBox()
        self.overlayEndYearField.setEditable(True)
        self.overlayEndYearField.setToolTip("If overlay layers use the same end year field name, select or enter it here.")
        overlayFieldsLayout.addWidget(self.overlayEndYearField)

        overlayFieldsLayout.addWidget(QLabel("Leave both blank to skip per-year matching and compare full layers."))
        row.addLayout(overlayFieldsLayout)
        mainLayout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Output area units:"), 0)
        self.outputUnitCombo = QComboBox()
        self.outputUnitCombo.currentIndexChanged.connect(self.onOutputUnitChanged)
        row.addWidget(self.outputUnitCombo, 1)
        # Output mode: Combined, Per overlay, or Both
        row.addWidget(QLabel("Output mode:"), 0)
        self.outputModeCombo = QComboBox()
        self.outputModeCombo.addItems(["Combined", "Per overlay layer", "Both"])
        row.addWidget(self.outputModeCombo, 1)
        mainLayout.addLayout(row)

        row = QHBoxLayout()
        self.refreshButton = QPushButton("Refresh layers")
        self.refreshButton.clicked.connect(self.refreshLayerList)
        row.addWidget(self.refreshButton)
        self.calculateButton = QPushButton("Calculate overlap")
        self.calculateButton.clicked.connect(self.onCalculate)
        row.addWidget(self.calculateButton)
        row.addStretch()
        self.saveCsvButton = QPushButton("Save results to CSV")
        self.saveCsvButton.clicked.connect(self.onSaveCsv)
        self.saveCsvButton.setEnabled(False)
        row.addWidget(self.saveCsvButton)
        mainLayout.addLayout(row)

        self.areaUnitLabel = "map units²"
        # Add an extra column for nautical miles² (nm²) for CSV and display
        self.resultsTable = QTableWidget(0, 7)
        self.resultsTable.horizontalHeader().setStretchLastSection(True)
        mainLayout.addWidget(self.resultsTable)

        self.results = []
        self.updateAreaHeaders(None)

    def refreshLayerList(self):
        self.inputLayerCombo.clear()
        self.overlayLayerList.clear()
        self.overlayBeginYearField.clear()
        self.overlayEndYearField.clear()

        layers = [layer for layer in QgsProject.instance().mapLayers().values() if isinstance(layer, QgsVectorLayer)]
        for layer in layers:
            self.inputLayerCombo.addItem(layer.name(), layer.id())
            item = QListWidgetItem(layer.name())
            item.setData(Qt.UserRole, layer.id())
            self.overlayLayerList.addItem(item)

        self.updateFieldLists()

    def updateFieldLists(self):
        self.overlayBeginYearField.clear()
        self.overlayEndYearField.clear()

        input_layer = self.getCurrentInputLayer()
        selected_overlays = self.getSelectedOverlayLayers()
        if selected_overlays:
            common_fields = self.getCommonFieldNames(selected_overlays)
            self.overlayBeginYearField.addItems([""] + common_fields)
            self.overlayEndYearField.addItems([""] + common_fields)
        self.updateOutputUnits(input_layer)
        self.updateAreaHeaders(input_layer)
        self.updateCalculateButtonState()

    def getCurrentInputLayer(self):
        idx = self.inputLayerCombo.currentIndex()
        if idx < 0:
            return None
        layer_id = self.inputLayerCombo.itemData(idx)
        return QgsProject.instance().mapLayer(layer_id)

    def getSelectedOverlayLayers(self):
        selected_items = self.overlayLayerList.selectedItems()
        layers = []
        for item in selected_items:
            layer_id = item.data(Qt.UserRole)
            layer = QgsProject.instance().mapLayer(layer_id)
            if isinstance(layer, QgsVectorLayer):
                layers.append(layer)
        return layers

    def getCommonFieldNames(self, layers):
        if not layers:
            return []
        all_names = [set(layer.fields().names()) for layer in layers]
        common = set.intersection(*all_names)
        return sorted(common)

    def updateCalculateButtonState(self):
        input_layer = self.getCurrentInputLayer()
        overlay_layers = self.getSelectedOverlayLayers()
        if input_layer is None or not overlay_layers:
            self.calculateButton.setEnabled(False)
            self.calculateButton.setToolTip("Select both input and overlay layers to calculate overlap.")
            return

        for overlay_layer in overlay_layers:
            if input_layer.crs().authid() != overlay_layer.crs().authid():
                self.calculateButton.setEnabled(False)
                self.calculateButton.setToolTip("Both the input and overlay layers need to be in the same projection.")
                return

        self.calculateButton.setEnabled(True)
        self.calculateButton.setToolTip("Calculate overlap")

    def onOutputUnitChanged(self):
        input_layer = self.getCurrentInputLayer()
        if input_layer is not None:
            self.updateAreaHeaders(input_layer)
        if self.results:
            self.populateResultsTable()

    def updateOutputUnits(self, layer):
        previous_unit = self.outputUnitCombo.currentText()
        self.outputUnitCombo.clear()
        choices = self.getAreaUnitChoices(layer)
        self.outputUnitCombo.addItems(choices)
        if previous_unit and previous_unit in choices:
            self.outputUnitCombo.setCurrentText(previous_unit)
        elif choices:
            self.outputUnitCombo.setCurrentIndex(0)

    def getAreaUnitChoices(self, layer):
        if layer is None:
            return ["map units²"]
        try:
            map_unit = layer.crs().mapUnits()
        except Exception:
            return ["map units²"]

        if map_unit == QgsUnitTypes.DistanceMeters:
            return ["m²", "km²", "cm²", "mm²", "ha", "ft²", "yd²", "mi²", "nm²", "in²", "map units²"]
        if map_unit == QgsUnitTypes.DistanceKilometers:
            return ["km²", "m²", "cm²", "mm²", "ha", "ft²", "yd²", "mi²", "nm²", "in²", "map units²"]
        if map_unit in (QgsUnitTypes.DistanceFeet, QgsUnitTypes.DistanceYards, QgsUnitTypes.DistanceMiles, QgsUnitTypes.DistanceNauticalMiles):
            return ["ft²", "yd²", "mi²", "nm²", "m²", "km²", "cm²", "mm²", "in²", "map units²"]
        if map_unit == QgsUnitTypes.DistanceDegrees:
            return ["deg²", "map units²"]
        return ["map units²"]

    def getAreaConversionFactor(self, layer, output_unit):
        if layer is None or not output_unit:
            return 1.0
        try:
            map_unit = layer.crs().mapUnits()
        except Exception:
            return 1.0

        if map_unit == QgsUnitTypes.DistanceMeters:
            if output_unit == "m²":
                return 1.0
            if output_unit == "km²":
                return 1e-6
            if output_unit == "cm²":
                return 1e4
            if output_unit == "mm²":
                return 1e6
            if output_unit == "ha":
                return 1e-4
            if output_unit == "ft²":
                return 10.76391041671
            if output_unit == "yd²":
                return 1.1959900463
            if output_unit == "mi²":
                return 3.861021585424458e-7
            if output_unit == "nm²":
                return 2.590206837e-7
            if output_unit == "in²":
                return 1550.0031000062
            return 1.0
        if map_unit == QgsUnitTypes.DistanceKilometers:
            if output_unit == "km²":
                return 1.0
            if output_unit == "m²":
                return 1e6
            if output_unit == "cm²":
                return 1e10
            if output_unit == "mm²":
                return 1e12
            if output_unit == "ha":
                return 100.0
            if output_unit == "ft²":
                return 1.076391041671e7
            if output_unit == "yd²":
                return 1.1959900463e6
            if output_unit == "mi²":
                return 0.3861021585
            if output_unit == "nm²":
                return 0.2590206837
            if output_unit == "in²":
                return 1.5500031000062e9
            return 1.0
        if map_unit == QgsUnitTypes.DistanceFeet:
            if output_unit == "ft²":
                return 1.0
            if output_unit == "yd²":
                return 1.0 / 9.0
            if output_unit == "mi²":
                return 1.0 / (5280.0 * 5280.0)
            if output_unit == "nm²":
                return 1.0 / (6076.11549 * 6076.11549)
            if output_unit == "m²":
                return 0.09290304
            if output_unit == "km²":
                return 9.290304e-8
            if output_unit == "cm²":
                return 929.0304
            if output_unit == "mm²":
                return 92903.04
            if output_unit == "in²":
                return 144.0
            return 1.0
        if map_unit == QgsUnitTypes.DistanceYards:
            if output_unit == "yd²":
                return 1.0
            if output_unit == "ft²":
                return 9.0
            if output_unit == "mi²":
                return 1.0 / (1760.0 * 1760.0)
            if output_unit == "nm²":
                return 1.0 / ((6076.11549 / 3.0) * (6076.11549 / 3.0))
            if output_unit == "m²":
                return 0.83612736
            if output_unit == "km²":
                return 8.3612736e-7
            if output_unit == "cm²":
                return 8361.2736
            if output_unit == "mm²":
                return 836127.36
            if output_unit == "in²":
                return 1296.0
            return 1.0
        if map_unit == QgsUnitTypes.DistanceMiles:
            if output_unit == "mi²":
                return 1.0
            if output_unit == "ft²":
                return 5280.0 * 5280.0
            if output_unit == "yd²":
                return 1760.0 * 1760.0
            if output_unit == "nm²":
                return (1.0 / 1.15077945) ** 2
            if output_unit == "m²":
                return 2589988.110336
            if output_unit == "km²":
                return 2.589988110336
            if output_unit == "cm²":
                return 2.589988110336e10
            if output_unit == "mm²":
                return 2.589988110336e12
            if output_unit == "in²":
                return 4014489600.0
            return 1.0
        if map_unit == QgsUnitTypes.DistanceNauticalMiles:
            if output_unit == "nm²":
                return 1.0
            if output_unit == "mi²":
                return 1.324
            if output_unit == "ft²":
                return 6076.11549 * 6076.11549
            if output_unit == "yd²":
                return (6076.11549 / 3.0) * (6076.11549 / 3.0)
            if output_unit == "m²":
                return 3429904.0
            if output_unit == "km²":
                return 3.429904
            if output_unit == "cm²":
                return 3.429904e10
            if output_unit == "mm²":
                return 3.429904e12
            if output_unit == "in²":
                return 5.311e9
            return 1.0
        return 1.0

    def onCalculate(self):
        input_layer = self.getCurrentInputLayer()
        overlay_layers = self.getSelectedOverlayLayers()
        begin_year_field = self.overlayBeginYearField.currentText().strip()
        end_year_field = self.overlayEndYearField.currentText().strip()

        if input_layer is None:
            QMessageBox.warning(self, "Input layer required", "Please select an input layer.")
            return
        if not overlay_layers:
            QMessageBox.warning(self, "Overlay layers required", "Please select one or more overlay layers.")
            return
        if (bool(begin_year_field) != bool(end_year_field)):
            QMessageBox.warning(
                self,
                "Begin and end year fields required",
                "Please provide both a begin year field and an end year field, or leave both blank to compare full layers."
            )
            return

        self.updateAreaHeaders(input_layer)
        mode = self.outputModeCombo.currentText()
        self.results = self.calculateOverlap(input_layer, overlay_layers, begin_year_field, end_year_field, mode)
        self.populateResultsTable()
        self.saveCsvButton.setEnabled(bool(self.results))

    def calculateOverlap(self, input_layer, overlay_layers, begin_year_field, end_year_field, mode="Combined"):
        # Aggregate overlap per-calendar-year across all selected overlay layers.
        results = []

        # Build base (input) union geometry and compute total base area (unique)
        base_geoms = []
        for feat in input_layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            base_geoms.append(geom)
        if not base_geoms:
            return results
        base_union = QgsGeometry.unaryUnion(base_geoms)
        if base_union is None or base_union.isEmpty():
            return results
        base_area = base_union.area()

        # Helper: parse many date input types into a year (int) or None
        def to_year(val):
            if val is None:
                return None
            # QDate/QDateTime from PyQt expose toPyDate/toPython in some versions
            try:
                if hasattr(val, 'toPyDate'):
                    return int(val.toPyDate().year)
                if hasattr(val, 'toPython'):
                    py = val.toPython()
                    if isinstance(py, datetime.date):
                        return int(py.year)
            except Exception:
                pass
            # Python date/datetime
            if isinstance(val, datetime.datetime) or isinstance(val, datetime.date):
                return int(val.year)
            # Numeric types
            try:
                if isinstance(val, (int,)):
                    return int(val)
                if isinstance(val, float):
                    return int(val)
            except Exception:
                pass
            # Strings like 'YYYY', 'YYYY-MM-DD', etc.
            try:
                s = str(val).strip()
                m = re.match(r'^(\d{4})', s)
                if m:
                    return int(m.group(1))
            except Exception:
                pass
            return None

        # If mode includes combined, compute combined results
        if mode in ("Combined", "Both"):
            if not begin_year_field or not end_year_field:
                # Combine all overlay geometries across layers and compute intersection once
                overlay_geoms = []
                for overlay in overlay_layers:
                    for feat in overlay.getFeatures():
                        geom = feat.geometry()
                        if geom is None or geom.isEmpty():
                            continue
                        overlay_geoms.append(geom)
                if overlay_geoms:
                    overlay_union = QgsGeometry.unaryUnion(overlay_geoms)
                    if overlay_union is None or overlay_union.isEmpty():
                        overlap_area = 0.0
                    else:
                        inter = base_union.intersection(overlay_union)
                        overlap_area = 0.0 if inter is None or inter.isEmpty() else inter.area()
                else:
                    overlap_area = 0.0
                percent = (overlap_area / base_area * 100.0) if base_area > 0 else 0.0
                results.append({
                    "overlay_layer": "combined",
                    "begin_year": "all",
                    "end_year": "all",
                    "input_area": base_area,
                    "overlap_area": overlap_area,
                    "percent": percent,
                })
            else:
                # Build combined feature_years across all overlays
                combined_feature_years = []
                for overlay in overlay_layers:
                    for feat in overlay.getFeatures():
                        b = feat[begin_year_field]
                        e = feat[end_year_field]
                        by = to_year(b)
                        ey = to_year(e)
                        geom = feat.geometry()
                        if geom is None or geom.isEmpty():
                            continue
                        if by is None or ey is None:
                            continue
                        if ey < by:
                            by, ey = ey, by
                        combined_feature_years.append((by, ey, geom))
                if combined_feature_years:
                    min_year = min(f[0] for f in combined_feature_years)
                    max_year = max(f[1] for f in combined_feature_years)
                    for year in range(min_year, max_year + 1):
                        year_geoms = [geom for (by, ey, geom) in combined_feature_years if by <= year <= ey]
                        if not year_geoms:
                            overlap_area = 0.0
                        else:
                            overlay_union = QgsGeometry.unaryUnion(year_geoms)
                            if overlay_union is None or overlay_union.isEmpty():
                                overlap_area = 0.0
                            else:
                                inter = base_union.intersection(overlay_union)
                                overlap_area = 0.0 if inter is None or inter.isEmpty() else inter.area()
                        percent = (overlap_area / base_area * 100.0) if base_area > 0 else 0.0
                        results.append({
                            "overlay_layer": "combined",
                            "begin_year": year,
                            "end_year": year,
                            "input_area": base_area,
                            "overlap_area": overlap_area,
                            "percent": percent,
                        })

        # Per-overlay layer results (if requested)
        if mode in ("Per overlay layer", "Both"):
            for overlay in overlay_layers:
                # No temporal fields -> single 'all' row per overlay
                if not begin_year_field or not end_year_field:
                    overlay_geoms = [feat.geometry() for feat in overlay.getFeatures() if feat.geometry() is not None and not feat.geometry().isEmpty()]
                    if overlay_geoms:
                        overlay_union = QgsGeometry.unaryUnion(overlay_geoms)
                        if overlay_union is None or overlay_union.isEmpty():
                            overlap_area = 0.0
                        else:
                            inter = base_union.intersection(overlay_union)
                            overlap_area = 0.0 if inter is None or inter.isEmpty() else inter.area()
                    else:
                        overlap_area = 0.0
                    percent = (overlap_area / base_area * 100.0) if base_area > 0 else 0.0
                    results.append({
                        "overlay_layer": overlay.name(),
                        "begin_year": "all",
                        "end_year": "all",
                        "input_area": base_area,
                        "overlap_area": overlap_area,
                        "percent": percent,
                    })
                    continue

                # Temporal fields: collect per-feature years for this overlay
                ov_feature_years = []
                for feat in overlay.getFeatures():
                    b = feat[begin_year_field]
                    e = feat[end_year_field]
                    by = to_year(b)
                    ey = to_year(e)
                    geom = feat.geometry()
                    if geom is None or geom.isEmpty():
                        continue
                    if by is None or ey is None:
                        continue
                    if ey < by:
                        by, ey = ey, by
                    ov_feature_years.append((by, ey, geom))

                if not ov_feature_years:
                    continue

                ov_min = min(f[0] for f in ov_feature_years)
                ov_max = max(f[1] for f in ov_feature_years)
                for year in range(ov_min, ov_max + 1):
                    year_geoms = [geom for (by, ey, geom) in ov_feature_years if by <= year <= ey]
                    if not year_geoms:
                        overlap_area = 0.0
                    else:
                        overlay_union = QgsGeometry.unaryUnion(year_geoms)
                        if overlay_union is None or overlay_union.isEmpty():
                            overlap_area = 0.0
                        else:
                            inter = base_union.intersection(overlay_union)
                            overlap_area = 0.0 if inter is None or inter.isEmpty() else inter.area()
                    percent = (overlap_area / base_area * 100.0) if base_area > 0 else 0.0
                    results.append({
                        "overlay_layer": overlay.name(),
                        "begin_year": year,
                        "end_year": year,
                        "input_area": base_area,
                        "overlap_area": overlap_area,
                        "percent": percent,
                    })

        # Sort results for stable output: by overlay layer then begin_year
        def sort_key(r):
            layer = r.get('overlay_layer') or ''
            by = r.get('begin_year')
            by_key = -1 if isinstance(by, str) and by == 'all' else (by if isinstance(by, int) else -1)
            return (layer, by_key)

        results.sort(key=sort_key)
        return results

    def getUniqueFieldValuePairs(self, layer, begin_field, end_field):
        if not begin_field or not end_field:
            return []
        field_names = layer.fields().names()
        if begin_field not in field_names or end_field not in field_names:
            return []
        values = set()
        for feature in layer.getFeatures():
            values.add((feature[begin_field], feature[end_field]))
        return sorted(values, key=lambda x: (str(x[0]), str(x[1])))

    def calculateOverlapForPeriod(
        self,
        input_layer,
        overlay_layer,
        overlay_begin_field,
        overlay_end_field,
        begin_value,
        end_value,
    ):
        # Legacy method retained for backward-compatibility but not used by the
        # new per-year aggregation logic. Keep here in case other callers exist.
        request_input = QgsFeatureRequest()
        request_overlay = QgsFeatureRequest()

        if overlay_begin_field and overlay_end_field and begin_value is not None and end_value is not None:
            expr = self.buildFieldExpressionPair(
                overlay_layer,
                overlay_begin_field,
                begin_value,
                overlay_end_field,
                end_value,
            )
            request_overlay.setFilterExpression(expr)

        input_geometries = []
        total_input_area = 0.0
        for feature in input_layer.getFeatures(request_input):
            geom = feature.geometry()
            if geom is None or geom.isEmpty():
                continue
            total_input_area += geom.area()
            input_geometries.append(geom)

        overlay_geometries = []
        for feature in overlay_layer.getFeatures(request_overlay):
            geom = feature.geometry()
            if geom is None or geom.isEmpty():
                continue
            overlay_geometries.append(geom)

        overlap_area = 0.0
        if total_input_area > 0 and overlay_geometries:
            overlay_union = QgsGeometry.unaryUnion(overlay_geometries)
            if overlay_union is not None and not overlay_union.isEmpty():
                for input_geom in input_geometries:
                    if not input_geom.intersects(overlay_union):
                        continue
                    intersection = input_geom.intersection(overlay_union)
                    if intersection is None or intersection.isEmpty():
                        continue
                    overlap_area += intersection.area()

        return overlap_area, total_input_area

    def buildFieldExpression(self, layer, field_name, value):
        field_index = layer.fields().indexOf(field_name)
        if field_index < 0:
            return ''
        field = layer.fields().field(field_index)
        if field is None:
            return ''
        field_type = field.typeName().lower()
        safe_field = field_name.replace('"', '""')
        if value is None:
            return ''
        if field_type in ("string", "date", "datetime", "time"):
            safe_value = str(value).replace("'", "''")
            return '"{}" = \'{}\''.format(safe_field, safe_value)
        return '"{}" = {}'.format(safe_field, value)

    def buildFieldExpressionPair(self, layer, begin_field, begin_value, end_field, end_value):
        expr_begin = self.buildFieldExpression(layer, begin_field, begin_value)
        expr_end = self.buildFieldExpression(layer, end_field, end_value)
        if not expr_begin or not expr_end:
            return ''
        return f"({expr_begin}) AND ({expr_end})"

    def getAreaUnitLabel(self, layer):
        if layer is None:
            return "map units²"
        try:
            map_unit = layer.crs().mapUnits()
        except Exception:
            return "map units²"

        if map_unit == QgsUnitTypes.DistanceMeters:
            return "m²"
        if map_unit == QgsUnitTypes.DistanceKilometers:
            return "km²"
        if map_unit == QgsUnitTypes.DistanceFeet:
            return "ft²"
        if map_unit == QgsUnitTypes.DistanceYards:
            return "yd²"
        if map_unit == QgsUnitTypes.DistanceMiles:
            return "mi²"
        if map_unit == QgsUnitTypes.DistanceNauticalMiles:
            return "nm²"
        if map_unit == QgsUnitTypes.DistanceDegrees:
            return "deg²"
        return "map units²"

    def updateAreaHeaders(self, layer):
        if self.outputUnitCombo.currentText():
            self.areaUnitLabel = self.outputUnitCombo.currentText()
        else:
            self.areaUnitLabel = self.getAreaUnitLabel(layer)
        self.resultsTable.setHorizontalHeaderLabels([
            "Overlay layer",
            "Begin year",
            "End year",
            f"Input area ({self.areaUnitLabel})",
            f"Overlap area ({self.areaUnitLabel})",
            "Overlap area (nm²)",
            "Overlap %"
        ])

    def populateResultsTable(self):
        self.resultsTable.clearContents()
        self.resultsTable.setRowCount(len(self.results))
        input_layer = self.getCurrentInputLayer()
        factor = self.getAreaConversionFactor(input_layer, self.outputUnitCombo.currentText())
        # Factor to convert map units² to nautical miles² (nm²)
        nm_factor = self.getAreaConversionFactor(input_layer, "nm²")
        for row, result in enumerate(self.results):
            converted_input_area = result['input_area'] * factor
            converted_overlap_area = result['overlap_area'] * factor
            converted_overlap_nm2 = result['overlap_area'] * nm_factor
            self.resultsTable.setItem(row, 0, QTableWidgetItem(str(result["overlay_layer"])))
            self.resultsTable.setItem(row, 1, QTableWidgetItem(str(result["begin_year"])))
            self.resultsTable.setItem(row, 2, QTableWidgetItem(str(result["end_year"])))
            self.resultsTable.setItem(row, 3, QTableWidgetItem(f"{converted_input_area:.4f}"))
            self.resultsTable.setItem(row, 4, QTableWidgetItem(f"{converted_overlap_area:.4f}"))
            self.resultsTable.setItem(row, 5, QTableWidgetItem(f"{converted_overlap_nm2:.4f}"))
            self.resultsTable.setItem(row, 6, QTableWidgetItem(f"{result['percent']:.2f}%"))
        self.resultsTable.resizeColumnsToContents()

    def onSaveCsv(self):
        if not self.results:
            QMessageBox.information(self, "No results", "There are no results to save. Run a calculation first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save results to CSV", "percentage_overlap.csv", "CSV files (*.csv)")
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as file:
                file.write(f"Overlay layer,Begin year,End year,Input area ({self.areaUnitLabel}),Overlap area ({self.areaUnitLabel}),Overlap area (nm²),Overlap %\n")
                input_layer = self.getCurrentInputLayer()
                factor = self.getAreaConversionFactor(input_layer, self.outputUnitCombo.currentText())
                nm_factor = self.getAreaConversionFactor(input_layer, "nm²")
                for result in self.results:
                    converted_input_area = result['input_area'] * factor
                    converted_overlap_area = result['overlap_area'] * factor
                    converted_overlap_nm2 = result['overlap_area'] * nm_factor
                    file.write(
                        f"{result['overlay_layer']},{result['begin_year']},{result['end_year']},{converted_input_area:.4f},{converted_overlap_area:.4f},{converted_overlap_nm2:.4f},{result['percent']:.2f}\n"
                    )
            QMessageBox.information(self, "Saved", f"Results saved to {path}")
        except Exception as exc:
            QMessageBox.warning(self, "Export failed", f"Could not save the CSV file:\n{exc}")
