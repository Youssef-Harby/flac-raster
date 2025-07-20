# FLAC-Raster: Experimental Raster to FLAC Converter

[![CI/CD](https://github.com/Youssef-Harby/flac-raster/actions/workflows/ci.yml/badge.svg)](https://github.com/Youssef-Harby/flac-raster/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/flac-raster.svg)](https://badge.fury.io/py/flac-raster)
[![Python versions](https://img.shields.io/pypi/pyversions/flac-raster.svg)](https://pypi.org/project/flac-raster/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An experimental CLI tool that converts TIFF raster data files into FLAC audio format while preserving all geospatial metadata, CRS, and bounds information. This proof-of-concept explores using FLAC's lossless compression for geospatial data storage and introduces **revolutionary HTTP range streaming** for efficient geospatial data access - "Zarr for geospatial data using audio compression".

## 🚀 **NEW: Lazy Loading & HTTP Range Streaming**

FLAC-Raster now supports **lazy loading** with HTTP range request streaming - like "Zarr for geospatial data" but using audio compression! 

- **🏃‍♂️ Lazy loading**: Load only metadata first (1MB), stream tiles on-demand
- **Web-optimized**: Upload FLAC files to any HTTP server, query by bbox with range requests
- **Spatial indexing**: Each tile has bbox metadata for efficient spatial queries  
- **Streaming**: Download only the data you need, not entire files (80%+ bandwidth savings)
- **Precise**: Query specific geographic areas with pixel-perfect accuracy
- **HTTP compatible**: Works with standard web servers, CDNs, and browsers
- **URL support**: Query remote FLAC files directly via HTTPS URLs

## Features

- **Bidirectional conversion**: TIFF → FLAC and FLAC → TIFF
- **Complete metadata preservation**: CRS, bounds, transform, data type, nodata values
- **🆕 Embedded metadata**: All geospatial metadata stored directly in FLAC files (no sidecar files!)
- **🆕 Spatial tiling**: Convert rasters to tiled FLAC with bbox metadata per tile
- **🆕 HTTP range streaming**: Query and stream data by bounding box with 90%+ bandwidth savings
- **🆕 Exceptional compression**: 7-15× file size reduction while maintaining lossless quality
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
pip install rasterio numpy typer rich tqdm pyflac mutagen

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

### 🆕 Spatial Tiling & HTTP Range Streaming

5. **Create spatial FLAC with tiling**:
   ```bash
   # Enable spatial tiling with 512x512 tiles (default)
   flac-raster convert input.tif --spatial -o spatial.flac
   
   # Custom tile size (256x256)
   flac-raster convert input.tif --spatial --tile-size 256 -o spatial.flac
   ```

6. **Query spatial FLAC by bounding box**:
   ```bash
   # Query local file
   flac-raster query spatial.flac --bbox "xmin,ymin,xmax,ymax"
   
   # Query remote file (lazy loading!)
   flac-raster query https://example.com/data.flac --bbox "34.1,28.6,34.3,28.8"
   
   # Example with real coordinates
   flac-raster query spatial.flac --bbox "-105.3,40.3,-105.1,40.5"
   ```

7. **View spatial index information**:
   ```bash
   flac-raster spatial-info spatial.flac
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
2. **Spatial tiling** (if enabled): Divide raster into configurable tile sizes
3. **Calculate audio parameters**:
   - Sample rate: Based on image resolution (44.1kHz to 192kHz)
   - Bit depth: Matches the raster's bit depth (16 or 24-bit, minimum 16-bit due to FLAC decoder limitations)
4. **Normalize data** to audio range (-1 to 1)
5. **Reshape data**: Bands become audio channels, pixels become samples
   - Single-band → Mono audio
   - Multi-band (RGB, multispectral) → Multi-channel audio
6. **Encode to FLAC** with configurable compression
7. **Embed metadata** directly in FLAC using VORBIS_COMMENT blocks
8. **Generate spatial index** with bbox and byte range information for each tile

### FLAC to TIFF Conversion

1. **Decode FLAC** file and extract audio samples
2. **Load metadata** from embedded FLAC metadata (with JSON sidecar fallback)
3. **Reconstruct spatial index** for tiled data
4. **Reshape audio** back to raster dimensions
   - Mono → Single-band raster
   - Multi-channel → Multi-band raster
5. **Denormalize** to original data range
6. **Write GeoTIFF** with all original metadata preserved

## Metadata Preservation

The tool preserves all geospatial metadata **directly embedded in FLAC files**:
- Width and height dimensions
- Number of bands  
- Data type (uint8, int16, float32, etc.)
- Coordinate Reference System (CRS)
- Geospatial transform (affine transformation matrix)
- Bounding box coordinates
- Original data min/max values
- NoData values
- **Spatial index**: Compressed tile bbox and byte range information
- Original driver information

### Embedded Metadata Format

Metadata is stored in FLAC VORBIS_COMMENT blocks:
```
GEOSPATIAL_CRS=EPSG:4326
GEOSPATIAL_WIDTH=1201
GEOSPATIAL_HEIGHT=1201
GEOSPATIAL_SPATIAL_INDEX=<base64(gzip(spatial_index_json))>
...
```

## Lazy Loading & HTTP Range Streaming for Web GIS

### Concept: "Zarr for Geospatial Data using Audio Compression"

The lazy loading feature transforms FLAC-Raster into a **web-native geospatial format** that enables efficient HTTP range request streaming:

```
FLAC URL: https://cdn.example.com/elevation.flac
        ↓
🏃‍♂️ Lazy Load: Download first 1MB for metadata only
        ↓
Query Spatial Index: Find intersecting tiles for bbox
        ↓
HTTP Range Request: bytes=48152-73513,87850-113211
        ↓  
⬇️ Smart Download: Only 76KB instead of 189KB (60% savings!)
        ↓
Decode FLAC: Get pixels for visible area only
```

### Lazy Loading Workflow

1. **Metadata First**: Download only 1MB to read embedded spatial index
2. **On-Demand Streaming**: Query specific geographic areas
3. **Precise Downloads**: HTTP Range requests for intersecting tiles only
4. **Progressive Loading**: Cache tiles for repeated access

### Use Cases

1. **Interactive Web Maps**
   - Progressive loading as users pan/zoom
   - Only download visible area data  
   - Works with any HTTP server/CDN

2. **Cloud-Native GIS**
   - Stream large rasters without specialized servers
   - Compatible with S3, CloudFront, etc.
   - No need for complex tiling servers

3. **Bandwidth-Constrained Applications** 
   - Mobile mapping apps
   - Satellite/field data collection
   - IoT sensor networks

### Web Server Integration

```javascript
// JavaScript lazy loading client example
async function loadRasterData(bbox) {
    const flacUrl = '/data/elevation.flac';
    
    // 1. Lazy load: get metadata only (first 1MB)
    const metadataResponse = await fetch(flacUrl, {
        headers: { 'Range': 'bytes=0-1048575' }
    });
    const spatialIndex = extractEmbeddedMetadata(metadataResponse);
    
    // 2. Find byte ranges for bbox
    const ranges = calculateRanges(bbox, spatialIndex);
    
    // 3. Stream only needed tiles via HTTP ranges
    const rangeHeader = ranges.map(r => `${r.start}-${r.end}`).join(',');
    const dataResponse = await fetch(flacUrl, {
        headers: { 'Range': `bytes=${rangeHeader}` }
    });
    
    // 4. Decode FLAC data for bbox
    return decodeFLACTiles(dataResponse.body, bbox);
}
```

## Technical Details

- **FLAC frames**: Utilizes FLAC's frame structure for efficient chunking (4096 samples/frame)
- **🆕 Spatial tiling**: Each tile becomes a separate FLAC stream with bbox metadata
- **🆕 HTTP byte ranges**: Precise byte offsets enable partial downloads
- **🆕 Embedded metadata**: All geospatial info stored in FLAC VORBIS_COMMENT blocks
- **Multi-band support**: Each raster band becomes an audio channel (up to 8 channels supported by FLAC)
- **Lossless conversion**: Data is normalized but the process is completely reversible
- **Exceptional compression**: Leverages FLAC's compression algorithms (7-15× size reduction)
- **Self-contained files**: No external dependencies or sidecar files required
- **Data type mapping**:
  - uint8 → 16-bit FLAC (due to decoder limitations)
  - int16/uint16 → 16-bit FLAC
  - int32/uint32/float32 → 24-bit FLAC

## Performance Examples

From comprehensive testing against `report.md` analysis:

### Compression Results
- **DEM file** (1201×1201, int16): 2.8 MB → 185 KB FLAC (**15.25× compression**)
- **Multispectral** (200×200×6, uint8): 235 KB → 32 KB FLAC (**7.38× compression**)
- **RGB** (256×256×3, uint8): 193 KB → 27 KB FLAC (**7.26× compression**)

### HTTP Range Streaming Efficiency
- **Small area queries**: Up to **98.8% bandwidth savings** vs full download
- **Geographic precision**: Query exact areas with pixel-perfect accuracy
- **Optimized ranges**: Smart merging of contiguous tiles reduces HTTP requests

All conversions are perfectly lossless (verified with numpy array comparison)

## Limitations

- Maximum 8 bands (FLAC channel limitation)
- Minimum 16-bit encoding (pyflac decoder limitation)
- Large rasters may take time to process
- FLAC format limitations apply (specific bit depths: 16, 24-bit)
- Requires mutagen library for embedded metadata support
- Experimental: Not recommended for production use without thorough testing

## Project Structure

```
flac-raster/
├── src/flac_raster/          # Main package
│   ├── __init__.py           # Package initialization
│   ├── cli.py                # Command-line interface
│   ├── converter.py          # Core conversion logic
│   ├── spatial_encoder.py    # 🆕 Spatial tiling & HTTP range streaming
│   ├── metadata_encoder.py   # 🆕 Embedded metadata handling
│   └── compare.py            # Comparison utilities
├── examples/                 # Example scripts
│   ├── create_test_data.py   # Generate test datasets
│   └── spatial_streaming_example.py  # 🆕 HTTP range streaming demo
├── test_data/               # Test datasets
│   ├── dem-raw.tif          # Large DEM for testing
│   ├── sample_multispectral.tif  # 6-band multispectral
│   └── sample_rgb.tif       # RGB test data
├── report.md                # 🆕 Comprehensive analysis & benchmarks
├── main.py                  # Main entry point
├── pyproject.toml           # Project configuration
├── README.md                # This file
└── pixi.toml               # Pixi package configuration
```

## CI/CD & Publishing

This project uses GitHub Actions for:
- **Continuous Integration**: Tests on Python 3.9-3.12 across Windows, macOS, and Linux
- **Automated Building**: Package building and validation
- **PyPI Publishing**: Automatic publishing on release creation
- **Quality Assurance**: Integration testing via CLI commands

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

- **Adaptive tiling**: Variable tile sizes based on data complexity
- **Temporal support**: Time-series data with temporal indexing  
- **Band selection**: Spectral subsetting for multispectral data
- **Compression tuning**: Automatic optimization of FLAC parameters
- **Caching strategy**: Intelligent tile caching for frequently accessed areas
- **JavaScript client**: Browser-based FLAC decoder for web mapping
- **Parallel processing**: Multi-threaded encoding/decoding
- **More formats**: Support for HDF5, NetCDF, Zarr integration
- **Performance optimization**: Memory usage and processing speed improvements