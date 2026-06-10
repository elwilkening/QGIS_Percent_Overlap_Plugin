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
    QgsDistanceArea,
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
            return ["m²", "km²", "cm²", "mm²", "ha", "ft²", "yd²", "mi²", "nm²", "in²", "deg²", "map units²"]
        return ["map units²"]

    def getAreaConversionFactor(self, layer, output_unit):
        if layer is None or not output_unit:
            return 1.0
        try:
            map_unit = layer.crs().mapUnits()
        except Exception:
            return 1.0

        # If the layer is geographic (degrees) we measure areas with QgsDistanceArea
        # which returns square meters; for conversion purposes treat degrees as meters.
        if map_unit == QgsUnitTypes.DistanceDegrees:
            map_unit = QgsUnitTypes.DistanceMeters

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
        try:
            self.results = self.calculateOverlap(input_layer, overlay_layers, begin_year_field, end_year_field, mode)
        except Exception as exc:
            QMessageBox.warning(self, "Calculation failed", f"An error occurred during calculation:\n{exc}")
            return

        # If both year fields blank but results contain per-year numeric rows,
        # surface diagnostics and replace with a single combined 'all' row.
        if begin_year_field == "" and end_year_field == "":
            has_year_rows = any(isinstance(r.get('begin_year'), int) for r in (self.results or []))
            if has_year_rows:
                # Build diagnostic summary
                base_count = sum(1 for _ in input_layer.getFeatures())
                overlay_count = sum(sum(1 for _ in ol.getFeatures()) for ol in overlay_layers)
                try:
                    base_geoms = [f.geometry() for f in input_layer.getFeatures() if f.geometry() is not None and not f.geometry().isEmpty()]
                    base_union = QgsGeometry.unaryUnion(base_geoms) if base_geoms else None
                    if base_union is None or base_union.isEmpty():
                        base_area = 0.0
                    else:
                        dah = QgsDistanceArea()
                        try:
                            dah.setSourceCrs(input_layer.crs(), QgsProject.instance().transformContext())
                        except Exception:
                            try:
                                dah.setSourceCrs(input_layer.crs())
                            except Exception:
                                pass
                        try:
                            ell = QgsProject.instance().ellipsoid()
                            if ell:
                                dah.setEllipsoid(ell)
                        except Exception:
                            pass
                        try:
                            base_area = dah.measureArea(base_union)
                        except Exception:
                            base_area = 0.0
                except Exception:
                    base_area = 0.0
                details = (
                    f"Detected unexpected per-year rows while year fields were blank.\n"
                    f"Input features: {base_count}\n"
                    f"Overlay features (total across selected layers): {overlay_count}\n"
                    f"Base union area (map units²): {base_area:.4f}\n"
                    f"Forcing a single combined result row (Begin/End = all)."
                )
                QMessageBox.information(self, "Calculation details", details)
                # Force a single combined result
                overlay_geoms = []
                for overlay in overlay_layers:
                    for feat in overlay.getFeatures():
                        geom = feat.geometry()
                        if geom is None or geom.isEmpty():
                            continue
                        overlay_geoms.append(geom)
                if overlay_geoms:
                    overlay_union = QgsGeometry.unaryUnion(overlay_geoms)
                    inter = base_union.intersection(overlay_union) if base_union is not None else None
                    if inter is None or inter.isEmpty():
                        overlap_area = 0.0
                    else:
                        if 'dah' in locals():
                            try:
                                overlap_area = dah.measureArea(inter)
                            except Exception:
                                overlap_area = inter.area()
                        else:
                            overlap_area = inter.area()
                else:
                    overlap_area = 0.0
                percent = (overlap_area / base_area * 100.0) if base_area > 0 else 0.0
                self.results = [{
                    "overlay_layer": "combined",
                    "begin_year": "all",
                    "end_year": "all",
                    "input_area": base_area,
                    "overlap_area": overlap_area,
                    "percent": percent,
                }]

        if not self.results:
            # Provide diagnostics to help user debug empty results
            base_count = sum(1 for _ in input_layer.getFeatures())
            overlay_count = sum(sum(1 for _ in ol.getFeatures()) for ol in overlay_layers)
            overlay_geom_count = 0
            field_presence = {}
            for ol in overlay_layers:
                geom_ct = sum(1 for f in ol.getFeatures() if f.geometry() is not None and not f.geometry().isEmpty())
                overlay_geom_count += geom_ct
                fields = ol.fields().names()
                field_presence[ol.name()] = {
                    'fields': fields,
                    'has_begin': begin_year_field in fields if begin_year_field else None,
                    'has_end': end_year_field in fields if end_year_field else None,
                }
            try:
                base_geoms = [f.geometry() for f in input_layer.getFeatures() if f.geometry() is not None and not f.geometry().isEmpty()]
                base_union = QgsGeometry.unaryUnion(base_geoms) if base_geoms else None
                if base_union is None or base_union.isEmpty():
                    base_area = 0.0
                else:
                    dah = QgsDistanceArea()
                    try:
                        dah.setSourceCrs(input_layer.crs(), QgsProject.instance().transformContext())
                    except Exception:
                        try:
                            dah.setSourceCrs(input_layer.crs())
                        except Exception:
                            pass
                    try:
                        ell = QgsProject.instance().ellipsoid()
                        if ell:
                            dah.setEllipsoid(ell)
                    except Exception:
                        pass
                    try:
                        base_area = dah.measureArea(base_union)
                    except Exception:
                        base_area = 0.0
            except Exception:
                base_area = 0.0
            details = (
                f"Calculation completed but produced no results.\n"
                f"Input features: {base_count}\n"
                f"Overlay features (total across selected layers): {overlay_count}\n"
                f"Overlay geometries with valid geometry: {overlay_geom_count}\n"
                f"Base union area (map units²): {base_area:.4f}\n"
                f"Selected begin field: '{begin_year_field}'\n"
                f"Selected end field: '{end_year_field}'\n"
                f"Overlay layer field presence: {field_presence}\n"
                f"Check CRS, field names, and that features have valid geometries."
            )
            QMessageBox.information(self, "No results", details)
            self.results = []
            self.resultsTable.clearContents()
            self.resultsTable.setRowCount(0)
            self.saveCsvButton.setEnabled(False)
            return

        self.populateResultsTable()
        self.saveCsvButton.setEnabled(True)

    def calculateOverlap(self, input_layer, overlay_layers, begin_year_field, end_year_field, mode="Combined"):
        results = []

        # Helper: parse many date input types into a year (int) or None
        def to_year(val):
            if val is None:
                return None
            try:
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

            def parse_excel_serial(serial_value):
                try:
                    serial = int(serial_value)
                except Exception:
                    return None
                if serial <= 0:
                    return None
                base_date = datetime.date(1899, 12, 30)
                try:
                    return int((base_date + datetime.timedelta(days=serial)).year)
                except Exception:
                    return None

            if isinstance(val, (int, float)):
                if isinstance(val, float) and not val.is_integer():
                    serial_year = parse_excel_serial(val)
                    if serial_year is not None:
                        return serial_year
                integer_value = int(val)
                current_year = datetime.datetime.now().year
                if 1000 <= integer_value <= current_year + 10:
                    return integer_value
                if 10000 <= integer_value <= 60000:
                    serial_year = parse_excel_serial(integer_value)
                    if serial_year is not None:
                        return serial_year
                return integer_value if integer_value > 0 else None

            s = str(val).strip()
            if not s:
                return None

            # Normalize Excel-style datetime strings with slash separators in the time component.
            normalized = s
            parts = s.split(None, 1)
            if len(parts) == 2 and re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}$", parts[0]) and '/' in parts[1]:
                normalized = f"{parts[0]} {parts[1].replace('/', ':')}"

            if re.fullmatch(r"\d+(\.\d+)?", s):
                try:
                    serial_value = float(s)
                    if 10000 <= serial_value <= 60000:
                        serial_year = parse_excel_serial(serial_value)
                        if serial_year is not None:
                            return serial_year
                    integer_value = int(serial_value)
                    current_year = datetime.datetime.now().year
                    if 1000 <= integer_value <= current_year + 10:
                        return integer_value
                except Exception:
                    pass

            def try_formats(text, formats):
                for fmt in formats:
                    try:
                        dt = datetime.datetime.strptime(text, fmt)
                        return int(dt.year)
                    except Exception:
                        continue
                return None

            formats = [
                "%m/%d/%Y %H:%M:%S",
                "%m/%d/%Y %H:%M",
                "%m/%d/%Y %I:%M:%S %p",
                "%m/%d/%Y %I:%M %p",
                "%m/%d/%y %H:%M:%S",
                "%m/%d/%y %H:%M",
                "%m/%d/%y %I:%M:%S %p",
                "%m/%d/%y %I:%M %p",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%d-%m-%Y %H:%M:%S",
                "%d-%m-%Y %H:%M",
                "%m/%d/%Y",
                "%m/%d/%y",
                "%Y-%m-%d",
                "%Y/%m/%d",
                "%d/%m/%Y",
                "%d-%m-%Y",
                "%b %d %Y",
                "%B %d %Y",
                "%d %b %Y",
                "%d %B %Y",
                "%b %d, %Y",
                "%B %d, %Y",
            ]
            year = try_formats(normalized, formats)
            if year is not None:
                return year

            try:
                if 'T' in normalized:
                    dt = datetime.datetime.fromisoformat(normalized.replace('Z', '+00:00'))
                    return int(dt.year)
            except Exception:
                pass

            m = re.search(r"(?<!\d)(19|20)\d{2}(?!\d)", normalized)
            if m:
                try:
                    return int(m.group(0))
                except Exception:
                    pass
            m = re.search(r"(\d{4})", normalized)
            if m:
                try:
                    return int(m.group(1))
                except Exception:
                    pass
            return None

        def union_geoms(geoms):
            if not geoms:
                return None
            union = QgsGeometry.unaryUnion(geoms)
            if union is None or union.isEmpty():
                return None
            return union

        # Distance/area helper using layer CRS and project ellipsoid
        def make_area_helper(layer):
            d = QgsDistanceArea()
            try:
                d.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
            except Exception:
                try:
                    d.setSourceCrs(layer.crs())
                except Exception:
                    pass
            try:
                ell = QgsProject.instance().ellipsoid()
                if ell:
                    d.setEllipsoid(ell)
            except Exception:
                pass
            return d

        # Build static base geometry from the input layer.
        base_geoms = []
        for feat in input_layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            base_geoms.append(geom)
        if not base_geoms:
            return results
        base_union = union_geoms(base_geoms)
        area_helper = make_area_helper(input_layer)

        # Build overlay-year geometry mapping
        overlay_year_geoms = {}
        overlay_year_geoms_per_layer = {}
        if begin_year_field and end_year_field:
            for overlay in overlay_layers:
                per_layer = {}
                for feat in overlay.getFeatures():
                    geom = feat.geometry()
                    if geom is None or geom.isEmpty():
                        continue
                    by = to_year(feat[begin_year_field])
                    ey = to_year(feat[end_year_field])
                    if by is None or ey is None:
                        continue
                    if ey < by:
                        by, ey = ey, by
                    for year in range(by, ey + 1):
                        overlay_year_geoms.setdefault(year, []).append(geom)
                        per_layer.setdefault(year, []).append(geom)
                overlay_year_geoms_per_layer[overlay.name()] = per_layer
        else:
            all_overlay_geoms = []
            for overlay in overlay_layers:
                geoms = []
                for feat in overlay.getFeatures():
                    geom = feat.geometry()
                    if geom is None or geom.isEmpty():
                        continue
                    geoms.append(geom)
                all_overlay_geoms.extend(geoms)
                overlay_year_geoms_per_layer[overlay.name()] = {"all": geoms}
            if all_overlay_geoms:
                overlay_year_geoms["all"] = all_overlay_geoms

        if not overlay_year_geoms:
            return results

        def get_years_for_result():
            if begin_year_field:
                return sorted(overlay_year_geoms.keys(), key=lambda v: (str(v) != "all", v))
            return ["all"]

        years = get_years_for_result()

        # Combined results
        if mode in ("Combined", "Both"):
            for year in years:
                overlay_geoms = overlay_year_geoms.get(year, [])
                overlay_union = union_geoms(overlay_geoms)
                base_area = 0.0 if base_union is None or base_union.isEmpty() else area_helper.measureArea(base_union)
                if base_area > 0 and overlay_union is not None and not overlay_union.isEmpty():
                    inter = base_union.intersection(overlay_union)
                    overlap_area = 0.0 if inter is None or inter.isEmpty() else area_helper.measureArea(inter)
                else:
                    overlap_area = 0.0
                percent = (overlap_area / base_area * 100.0) if base_area > 0 else 0.0
                results.append({
                    "overlay_layer": "combined",
                    "begin_year": year,
                    "end_year": year,
                    "input_area": base_area,
                    "overlap_area": overlap_area,
                    "percent": percent,
                })

        # Per-overlay layer results
        if mode in ("Per overlay layer", "Both"):
            for overlay in overlay_layers:
                overlay_years = overlay_year_geoms_per_layer.get(overlay.name(), {})
                if begin_year_field:
                    years_for_overlay = sorted(overlay_years.keys(), key=lambda v: (str(v) != "all", v))
                else:
                    years_for_overlay = ["all"]

                for year in years_for_overlay:
                    overlay_geoms = overlay_years.get(year, [])
                    overlay_union = union_geoms(overlay_geoms)
                    base_area = 0.0 if base_union is None or base_union.isEmpty() else area_helper.measureArea(base_union)
                    if base_area > 0 and overlay_union is not None and not overlay_union.isEmpty():
                        inter = base_union.intersection(overlay_union)
                        overlap_area = 0.0 if inter is None or inter.isEmpty() else area_helper.measureArea(inter)
                    else:
                        overlap_area = 0.0
                    percent = (overlap_area / base_area * 100.0) if base_area > 0 else 0.0
                    results.append({
                        "overlay_layer": overlay.name(),
                        "begin_year": year,
                        "end_year": year,
                        "input_area": base_area,
                        "overlap_area": overlap_area,
                        "percent": percent,
                    })

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
        for feature in input_layer.getFeatures(request_input):
            geom = feature.geometry()
            if geom is None or geom.isEmpty():
                continue
            input_geometries.append(geom)

        # Compute total input area using a proper area helper (ellipsoidal if needed)
        total_input_area = 0.0
        if input_geometries:
            base_union = QgsGeometry.unaryUnion(input_geometries)
            if base_union is not None and not base_union.isEmpty():
                dah = QgsDistanceArea()
                try:
                    dah.setSourceCrs(input_layer.crs(), QgsProject.instance().transformContext())
                except Exception:
                    try:
                        dah.setSourceCrs(input_layer.crs())
                    except Exception:
                        pass
                try:
                    ell = QgsProject.instance().ellipsoid()
                    if ell:
                        dah.setEllipsoid(ell)
                except Exception:
                    pass
                try:
                    total_input_area = dah.measureArea(base_union)
                except Exception:
                    total_input_area = 0.0

        overlay_geometries = []
        for feature in overlay_layer.getFeatures(request_overlay):
            geom = feature.geometry()
            if geom is None or geom.isEmpty():
                continue
            overlay_geometries.append(geom)

        overlap_area = 0.0
        if total_input_area > 0 and overlay_geometries:
            overlay_union = QgsGeometry.unaryUnion(overlay_geometries)
            if overlay_union is not None and not overlay_union.isEmpty() and base_union is not None and not base_union.isEmpty():
                dah = QgsDistanceArea()
                try:
                    dah.setSourceCrs(input_layer.crs(), QgsProject.instance().transformContext())
                except Exception:
                    try:
                        dah.setSourceCrs(input_layer.crs())
                    except Exception:
                        pass
                try:
                    ell = QgsProject.instance().ellipsoid()
                    if ell:
                        dah.setEllipsoid(ell)
                except Exception:
                    pass
                inter = base_union.intersection(overlay_union)
                if inter is not None and not inter.isEmpty():
                    try:
                        overlap_area = dah.measureArea(inter)
                    except Exception:
                        overlap_area = 0.0

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
