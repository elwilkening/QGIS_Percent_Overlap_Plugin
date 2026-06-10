"""
QGIS plugin package for temporal overlay calculation.
"""


def classFactory(iface):
    """Load OverlapPlugin class and return plugin object.
    
    Args:
        iface: QGIS interface instance
        
    Returns:
        OverlapPlugin instance
    """
    from .Overlap import OverlapPlugin
    return OverlapPlugin(iface)
