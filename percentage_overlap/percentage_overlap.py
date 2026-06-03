from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsProject

from .percentage_overlap_dialog import PercentageOverlapDialog


class PercentageOverlapPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        self.action = QAction("Percentage Overlap", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&Percentage Overlap", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu("&Percentage Overlap", self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None

    def run(self):
        if self.dialog is None:
            self.dialog = PercentageOverlapDialog(self.iface)
        self.dialog.refreshLayerList()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
