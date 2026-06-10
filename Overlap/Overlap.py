"""
Main plugin class for temporal overlay calculation in QGIS.
"""

from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsProject

from .Overlap_dialog import OverlapDialog


class OverlapPlugin:
    """Main plugin class that integrates with QGIS."""

    def __init__(self, iface):
        """Initialize the plugin.
        
        Args:
            iface: QGIS interface instance
        """
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        """Create action that will start the plugin."""
        self.action = QAction("Temporal Overlay Calculator", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&Temporal Overlap", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        """Remove the plugin menu item and icon."""
        if self.action:
            self.iface.removePluginMenu("&Temporal Overlap", self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None

    def run(self):
        """Open the plugin dialog."""
        if self.dialog is None:
            self.dialog = OverlapDialog(self.iface)
        self.dialog.refreshLayerList()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
