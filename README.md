# FLAC-Raster: Experimental Raster to FLAC Converter

[![CI/CD](https://github.com/Youssef-Harby/flac-raster/actions/workflows/ci.yml/badge.svg)](https://github.com/Youssef-Harby/flac-raster/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/flac-raster.svg)](https://badge.fury.io/py/flac-raster)
[![Python versions](https://img.shields.io/pypi/pyversions/flac-raster.svg)](https://pypi.org/project/flac-raster/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An experimental CLI tool that converts TIFF raster data files into FLAC audio format while preserving all geospatial metadata, CRS, and bounds information. This proof-of-concept explores using FLAC's lossless compression for geospatial data storage.

## Features

- **Bidirectional conversion**: TIFF → FLAC and FLAC → TIFF
- **Complete metadata preservation**: CRS, bounds, transform, data type, nodata values
- **Intelligent audio parameters**: Automatically selects sample rate and bit depth based on raster properties
- **Multi-band support**: Seamlessly handles multi-band rasters (RGB, multispectral) as multi-channel audio
- **Lossless compression**: Perfect reconstruction verified - no data loss
- **FLAC chunking**: Uses FLAC's frame-based compression (4096 samples/frame)
- **Comprehensive logging**: Verbose mode with detailed progress tracking
- **Colorful CLI**: Built with Typer and Rich for an intuitive experience

## Installation

### Prerequisites
First, install pixi:
```bash
# Install pixi (cross-platform package manager)
curl -fsSL https://pixi.sh/install.sh | bash
# or via conda: conda install -c conda-forge pixi
```

### Clone and Setup
```bash
git clone https://github.com/Youssef-Harby/flac-raster.git
cd flac-raster
pixi install  # Install all dependencies
```

### Install the CLI tool
```bash
# For regular use:
pixi run pip install .

# For development (editable install):
pixi run pip install -e .
```

### Alternative: Direct pip installation
```bash
pip install rasterio numpy typer rich tqdm pyflac

# Or install from PyPI (when published):
pip install flac-raster
```

## Usage

### Basic Commands

After installation, you can use the CLI directly:

1. **Convert TIFF to FLAC**:
   ```bash
   flac-raster convert input.tif -o output.flac
   ```

2. **Convert FLAC back to TIFF**:
   ```bash
   flac-raster convert input.flac -o output.tif
   ```

3. **Get file information**:
   ```bash
   flac-raster info file.tif
   flac-raster info file.flac
   ```

4. **Compare two TIFF files**:
   ```bash
   flac-raster compare original.tif reconstructed.tif
   ```

**Alternative**: Use `python main.py` if you haven't installed the package:
```bash
python main.py convert input.tif  # Direct script usage
```

### Options

#### Convert command:
- `--output, -o`: Specify output file path (auto-generates if not provided)
- `--compression, -c`: FLAC compression level 0-8 (default: 5)
- `--force, -f`: Overwrite existing output files
- `--verbose, -v`: Enable verbose logging for detailed progress

#### Compare command:
- `--show-bands/--no-bands`: Show per-band statistics (default: True)
- `--export, -e`: Export comparison results to JSON file
- `--help`: Show help message

### Example Workflow

```bash
# Create sample data
python examples/create_test_data.py

# Convert DEM to FLAC
flac-raster convert test_data/sample_dem.tif -v

# Check the FLAC file info
flac-raster info test_data/sample_dem.flac

# Convert back to TIFF
flac-raster convert test_data/sample_dem.flac -o test_data/dem_reconstructed.tif

# Compare original and reconstructed
flac-raster compare test_data/sample_dem.tif test_data/dem_reconstructed.tif

# Export comparison to JSON
flac-raster compare test_data/sample_dem.tif test_data/dem_reconstructed.tif --export comparison.json

# Test with multi-band data
flac-raster convert test_data/sample_rgb.tif
flac-raster convert test_data/sample_rgb.flac -o test_data/rgb_reconstructed.tif
flac-raster compare test_data/sample_rgb.tif test_data/rgb_reconstructed.tif

# Open in QGIS to verify
# The reconstructed files should be viewable in QGIS with all metadata intact
```

## How It Works

### TIFF to FLAC Conversion

1. **Read raster data** and extract all metadata (CRS, bounds, transform, etc.)
2. **Calculate audio parameters**:
   - Sample rate: Based on image resolution (44.1kHz to 192kHz)
   - Bit depth: Matches the raster's bit depth (16 or 24-bit, minimum 16-bit due to FLAC decoder limitations)
3. **Normalize data** to audio range (-1 to 1)
4. **Reshape data**: Bands become audio channels, pixels become samples
   - Single-band → Mono audio
   - Multi-band (RGB, multispectral) → Multi-channel audio
5. **Encode to FLAC** with configurable compression
6. **Save metadata** as sidecar JSON file
7. **Use FLAC frames** for natural chunking of the data

### FLAC to TIFF Conversion

1. **Decode FLAC** file and extract audio samples
2. **Load metadata** from sidecar JSON file
3. **Reshape audio** back to raster dimensions
   - Mono → Single-band raster
   - Multi-channel → Multi-band raster
4. **Denormalize** to original data range
5. **Write GeoTIFF** with all original metadata

## Metadata Preservation

The tool preserves:
- Width and height dimensions
- Number of bands
- Data type (uint8, int16, float32, etc.)
- Coordinate Reference System (CRS)
- Geospatial transform
- Bounding box coordinates
- Original data min/max values
- NoData values
- Original driver information

## Technical Details

- **FLAC frames**: Utilizes FLAC's frame structure for efficient chunking (4096 samples/frame)
- **Multi-band support**: Each raster band becomes an audio channel (up to 8 channels supported by FLAC)
- **Lossless conversion**: Data is normalized but the process is completely reversible
- **Compression**: Leverages FLAC's compression algorithms for size reduction
- **Metadata storage**: Sidecar JSON files ensure all geospatial information is preserved
- **Data type mapping**:
  - uint8 → 16-bit FLAC (due to decoder limitations)
  - int16/uint16 → 16-bit FLAC
  - int32/uint32/float32 → 24-bit FLAC

## Performance Examples

From testing:
- **DEM file** (1201x1201, int16): 2.75 MB → 1.60 MB FLAC (41.7% compression)
- **Multi-band** (256x256x3, uint8): 0.19 MB → 0.25 MB FLAC (small files may increase due to overhead)
- All conversions are perfectly lossless (verified with numpy array comparison)

## Limitations

- Maximum 8 bands (FLAC channel limitation)
- Minimum 16-bit encoding (pyflac decoder limitation)
- Large rasters may take time to process
- FLAC format limitations apply (specific bit depths: 16, 24-bit)
- Metadata stored separately in JSON sidecar files
- Experimental: Not recommended for production use

## Project Structure

```
flac-raster/
├── src/flac_raster/          # Main package
│   ├── __init__.py           # Package initialization
│   ├── cli.py                # Command-line interface
│   ├── converter.py          # Core conversion logic
│   └── compare.py            # Comparison utilities
├── examples/                 # Example scripts
│   ├── create_test_data.py   # Generate test datasets
│   └── example_usage.py      # Usage examples
├── tests/                    # Test scripts
│   ├── compare_tiffs.py      # TIFF comparison script
│   └── compare_multiband.py  # Multi-band comparison
├── testing_dataset/          # Test data
├── main.py                   # Main entry point
├── pyproject.toml            # Project configuration
├── README.md                 # This file
└── requirements.txt          # Dependencies
```

## CI/CD & Publishing

This project uses GitHub Actions for:
- ✅ **Continuous Integration**: Tests on Python 3.9-3.12 across Windows, macOS, and Linux
- ✅ **Automated Building**: Package building and validation
- ✅ **PyPI Publishing**: Automatic publishing on release creation
- ✅ **Quality Assurance**: Integration testing via CLI commands

### Publishing to PyPI
See [PUBLISHING.md](PUBLISHING.md) for detailed instructions on publishing releases.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test them
4. Commit your changes: `git commit -am 'Add feature'`
5. Push to the branch: `git push origin feature-name`
6. Create a Pull Request

## Future Improvements

- Support for more raster formats (HDF5, NetCDF, etc.)
- Streaming support for large files
- Parallel processing for faster conversion
- Better handling of special data types
- Integration with Zarr-like chunking strategies
- Enhanced unit test coverage