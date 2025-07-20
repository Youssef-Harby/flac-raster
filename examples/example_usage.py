#!/usr/bin/env python3
"""
Example usage of the FLAC-Raster converter
"""
import numpy as np
import rasterio
from rasterio.transform import from_origin
from pathlib import Path

# Create a sample TIFF file for testing
def create_sample_tiff(filename="sample.tif"):
    """Create a sample TIFF file with geographic data"""
    # Create sample data (elevation-like pattern)
    width, height = 100, 100
    x = np.linspace(0, 10, width)
    y = np.linspace(0, 10, height)
    X, Y = np.meshgrid(x, y)
    
    # Create elevation-like data
    Z = 1000 + 100 * np.sin(X) * np.cos(Y) + 50 * np.random.rand(height, width)
    
    # Define transform (georeferencing)
    # Place at arbitrary coordinates
    transform = from_origin(-120.0, 40.0, 0.01, 0.01)
    
    # Write TIFF
    with rasterio.open(
        filename,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=1,
        dtype=Z.dtype,
        crs='EPSG:4326',
        transform=transform,
    ) as dst:
        dst.write(Z, 1)
    
    print(f"Created sample TIFF: {filename}")
    print(f"  Shape: {Z.shape}")
    print(f"  Data range: {Z.min():.2f} - {Z.max():.2f}")
    return filename


if __name__ == "__main__":
    # Create sample data
    tiff_file = create_sample_tiff()
    
    print("\n" + "="*50)
    print("Example commands:")
    print("="*50)
    print(f"\n1. Convert TIFF to FLAC:")
    print(f"   pixi run python flac_raster.py convert {tiff_file} -o sample.flac")
    
    print(f"\n2. Convert FLAC back to TIFF:")
    print(f"   pixi run python flac_raster.py convert sample.flac -o reconstructed.tif")
    
    print(f"\n3. Get file information:")
    print(f"   pixi run python flac_raster.py info {tiff_file}")
    print(f"   pixi run python flac_raster.py info sample.flac")
    
    print(f"\n4. Use different compression levels (0-8):")
    print(f"   pixi run python flac_raster.py convert {tiff_file} -c 8")
    
    print("\nYou can then open 'reconstructed.tif' in QGIS to verify the conversion!")