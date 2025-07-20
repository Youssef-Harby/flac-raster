"""
FLAC-Raster: Experimental Raster to FLAC Converter
"""
from .converter import RasterFLACConverter
from .compare import compare_tiffs, display_comparison_table

__version__ = "0.1.0"
__all__ = ["RasterFLACConverter", "compare_tiffs", "display_comparison_table"]