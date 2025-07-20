# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of FLAC-Raster
- TIFF to FLAC conversion with metadata preservation
- FLAC to TIFF conversion with perfect reconstruction
- Multi-band raster support (up to 8 bands/channels)
- CLI tool with convert, info, and compare commands
- Beautiful table-based comparison output
- Comprehensive logging with verbose mode
- Automatic audio parameter selection based on raster properties
- JSON sidecar metadata files
- FLAC frame-based chunking (4096 samples/frame)
- Support for multiple data types (uint8, int16, float32, etc.)
- Cross-platform support (Windows, macOS, Linux)

### Features
- **Convert Command**: Bidirectional TIFF ↔ FLAC conversion
- **Info Command**: Display file information and metadata
- **Compare Command**: Statistical comparison with rich tables
- **Metadata Preservation**: CRS, bounds, transform, data ranges
- **Lossless Compression**: Perfect reconstruction verified
- **Smart Audio Params**: Sample rate and bit depth selection
- **Export Options**: JSON export for comparison results

## [0.1.0] - 2024-XX-XX

### Added
- Initial public release

### Technical Details
- Minimum Python 3.8 support
- Dependencies: numpy, rasterio, typer, rich, tqdm, pyflac
- MIT License
- GitHub Actions CI/CD pipeline
- PyPI publishing automation