"""
Command-line interface for FLAC-Raster
"""
import json
import logging
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.logging import RichHandler

from .converter import RasterFLACConverter
from .compare import compare_tiffs, display_comparison_table

app = typer.Typer(
    name="flac-raster",
    help="Convert between TIFF raster and FLAC audio formats while preserving geospatial metadata",
    add_completion=False,
)
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger("flac_raster")


@app.command()
def convert(
    input_file: Path = typer.Argument(..., help="Input file (TIFF or FLAC)"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    compression_level: int = typer.Option(5, "--compression", "-c", min=0, max=8, 
                                         help="FLAC compression level (0-8)"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing output file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    spatial_tiling: bool = typer.Option(False, "--spatial", "-s", help="Enable spatial tiling for HTTP range streaming"),
    tile_size: int = typer.Option(512, "--tile-size", help="Size of spatial tiles (default: 512x512)")
):
    """Convert between TIFF and FLAC formats"""
    
    # Set logging level
    if verbose:
        logging.getLogger("flac_raster").setLevel(logging.DEBUG)
    
    logger.info(f"Starting conversion of {input_file}")
    
    # Validate input
    if not input_file.exists():
        console.print(f"[red]Error: Input file does not exist: {input_file}[/red]")
        raise typer.Exit(1)
    
    # Determine conversion direction
    input_suffix = input_file.suffix.lower()
    if input_suffix in ['.tif', '.tiff']:
        conversion_type = "tiff_to_flac"
        default_output_suffix = ".flac"
    elif input_suffix == '.flac':
        conversion_type = "flac_to_tiff"
        default_output_suffix = ".tif"
    else:
        console.print(f"[red]Error: Unsupported file format: {input_suffix}[/red]")
        console.print("[yellow]Supported formats: .tif, .tiff, .flac[/yellow]")
        raise typer.Exit(1)
    
    # Set output path
    if output_file is None:
        output_file = input_file.with_suffix(default_output_suffix)
    
    # Check if output exists
    if output_file.exists() and not force:
        console.print(f"[red]Error: Output file already exists: {output_file}[/red]")
        console.print("[yellow]Use --force to overwrite[/yellow]")
        raise typer.Exit(1)
    
    # Create converter and perform conversion
    converter = RasterFLACConverter()
    
    try:
        if conversion_type == "tiff_to_flac":
            result = converter.tiff_to_flac(input_file, output_file, compression_level, 
                                          spatial_tiling, tile_size)
            if spatial_tiling and result:
                console.print(f"[green]Spatial index created with {len(result.frames)} tiles[/green]")
        else:
            converter.flac_to_tiff(input_file, output_file)
    except Exception as e:
        logger.exception("Conversion failed")
        console.print(f"[red]Error during conversion: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def info(
    file_path: str = typer.Argument(..., help="FLAC or TIFF file to inspect (local path or HTTP URL)")
):
    """Display information about a FLAC or TIFF file"""
    
    # Check if it's a URL
    is_url = file_path.startswith(('http://', 'https://'))
    
    if not is_url:
        # Local file path
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            console.print(f"[red]Error: File does not exist: {file_path}[/red]")
            raise typer.Exit(1)
        suffix = file_path_obj.suffix.lower()
    else:
        # URL - extract suffix from URL
        from urllib.parse import urlparse
        parsed_url = urlparse(file_path)
        suffix = Path(parsed_url.path).suffix.lower()
    
    if suffix in ['.tif', '.tiff']:
        import rasterio
        
        if is_url:
            console.print(f"[red]Error: URL-based TIFF inspection not supported yet[/red]")
            raise typer.Exit(1)
            
        with rasterio.open(file_path) as src:
            console.print(f"[cyan]TIFF Information:[/cyan]")
            console.print(f"  Dimensions: {src.width} x {src.height}")
            console.print(f"  Bands: {src.count}")
            console.print(f"  Data type: {src.dtypes[0]}")
            console.print(f"  CRS: {src.crs}")
            console.print(f"  Bounds: {src.bounds}")
            console.print(f"  File size: {Path(file_path).stat().st_size / 1024 / 1024:.2f} MB")
            
    elif suffix == '.flac':
        console.print(f"[cyan]FLAC Information:[/cyan]")
        
        if is_url:
            # For URLs, use SpatialFLACStreamer to get info without downloading the entire file
            try:
                import requests
                from .spatial_encoder import SpatialFLACStreamer
                
                # Get file size from HTTP HEAD request
                response = requests.head(file_path)
                file_size = int(response.headers.get('content-length', 0))
                console.print(f"  Remote file size: {file_size / 1024 / 1024:.2f} MB")
                
                # Load spatial metadata (lazy loading)
                console.print(f"  [cyan]Loading metadata (lazy loading)...[/cyan]")
                streamer = SpatialFLACStreamer(file_path)
                
                console.print(f"  Spatial tiles: {len(streamer.spatial_index.frames)}")
                console.print(f"  Total indexed data: {streamer.spatial_index.total_bytes:,} bytes")
                
                # Show embedded metadata from streamer
                if hasattr(streamer, 'spatial_index') and streamer.spatial_index:
                    # Get metadata from the first frame or spatial index metadata
                    console.print(f"\n[green]Spatial FLAC Metadata:[/green]")
                    console.print(f"  Spatial format: Yes")
                    console.print(f"  Total frames/tiles: {len(streamer.spatial_index.frames)}")
                    console.print(f"  CRS: {streamer.spatial_index.crs}")
                    console.print(f"  Transform: {streamer.spatial_index.transform}")
                
            except Exception as e:
                console.print(f"  [red]Error reading remote FLAC file: {e}[/red]")
                
        else:
            # Local file processing
            try:
                import pyflac
                # Use the same approach as converter to get FLAC info
                decoder = pyflac.FileDecoder(str(file_path))
                audio_data, sample_rate = decoder.process()
                
                console.print(f"  Sample rate: {sample_rate} Hz")
                console.print(f"  Channels: {audio_data.shape[1] if len(audio_data.shape) > 1 else 1}")
                console.print(f"  Audio shape: {audio_data.shape}")
                console.print(f"  Data type: {audio_data.dtype}")
                console.print(f"  File size: {Path(file_path).stat().st_size / 1024 / 1024:.2f} MB")
            except Exception as e:
                console.print(f"  [red]Error reading FLAC file: {e}[/red]")
                console.print(f"  File size: {Path(file_path).stat().st_size / 1024 / 1024:.2f} MB")
            
            # Try to read embedded metadata for local files only
            metadata = None
            try:
                from mutagen.flac import FLAC
                flac_file = FLAC(str(file_path))
                
                if "GEOSPATIAL_CRS" in flac_file:
                    console.print(f"\n[green]Embedded Geospatial Metadata:[/green]")
                    width = flac_file.get('GEOSPATIAL_WIDTH', ['N/A'])[0]
                    height = flac_file.get('GEOSPATIAL_HEIGHT', ['N/A'])[0] 
                    count = flac_file.get('GEOSPATIAL_COUNT', ['N/A'])[0]
                    dtype = flac_file.get('GEOSPATIAL_DTYPE', ['N/A'])[0]
                    crs = flac_file.get('GEOSPATIAL_CRS', ['N/A'])[0]
                    data_min = flac_file.get('GEOSPATIAL_DATA_MIN', ['N/A'])[0]
                    data_max = flac_file.get('GEOSPATIAL_DATA_MAX', ['N/A'])[0]
                    
                    console.print(f"  Original dimensions: {width} x {height}")
                    console.print(f"  Original bands: {count}")
                    console.print(f"  Original dtype: {dtype}")
                    console.print(f"  CRS: {crs}")
                    console.print(f"  Data range: [{data_min}, {data_max}]")
                    
                    # Check for spatial tiling
                    spatial_tiling = flac_file.get('GEOSPATIAL_SPATIAL_TILING', ['false'])[0].lower() == 'true'
                    if spatial_tiling:
                        console.print(f"  Spatial tiling: Yes")
                    else:
                        console.print(f"  Spatial tiling: No")
                        
                    # Show bounds if available
                    bounds_str = flac_file.get('GEOSPATIAL_BOUNDS', [None])[0]
                    if bounds_str:
                        bounds = json.loads(bounds_str)
                        console.print(f"  Bounds: ({bounds[0]:.6f}, {bounds[1]:.6f}, {bounds[2]:.6f}, {bounds[3]:.6f})")
                        
                    metadata = True
                else:
                    raise ValueError("No embedded metadata")
                    
            except Exception:
                # Fall back to sidecar file
                metadata_path = Path(file_path).with_suffix('.json')
                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        metadata_json = json.load(f)
                        console.print(f"\n[yellow]Raster Metadata (from {metadata_path.name}):[/yellow]")
                        console.print(f"  Original dimensions: {metadata_json['width']} x {metadata_json['height']}")
                        console.print(f"  Original bands: {metadata_json['count']}")
                        console.print(f"  Original dtype: {metadata_json['dtype']}")
                        console.print(f"  CRS: {metadata_json.get('crs', 'None')}")
                        if metadata_json.get('bounds'):
                            b = metadata_json['bounds']
                            console.print(f"  Bounds: ({b['left']}, {b['bottom']}, {b['right']}, {b['top']})")
                    metadata = True
                    
            if not metadata:
                console.print(f"\n[yellow]No embedded or sidecar metadata found[/yellow]")
                
    else:
        console.print(f"[red]Error: Unsupported file format: {suffix}[/red]")
        raise typer.Exit(1)


@app.command()
def compare(
    file1: Path = typer.Argument(..., help="First TIFF file"),
    file2: Path = typer.Argument(..., help="Second TIFF file"),
    show_bands: bool = typer.Option(True, "--show-bands/--no-bands", help="Show per-band statistics"),
    export_json: Optional[Path] = typer.Option(None, "--export", "-e", help="Export comparison results to JSON")
):
    """Compare two TIFF files and display statistics"""
    
    # Validate inputs
    if not file1.exists():
        console.print(f"[red]Error: File does not exist: {file1}[/red]")
        raise typer.Exit(1)
        
    if not file2.exists():
        console.print(f"[red]Error: File does not exist: {file2}[/red]")
        raise typer.Exit(1)
    
    # Check file formats
    if file1.suffix.lower() not in ['.tif', '.tiff']:
        console.print(f"[red]Error: {file1} is not a TIFF file[/red]")
        raise typer.Exit(1)
        
    if file2.suffix.lower() not in ['.tif', '.tiff']:
        console.print(f"[red]Error: {file2} is not a TIFF file[/red]")
        raise typer.Exit(1)
    
    try:
        # Perform comparison
        results = compare_tiffs(file1, file2, show_bands)
        
        # Display results
        display_comparison_table(results)
        
        # Export to JSON if requested
        if export_json:
            with open(export_json, 'w') as f:
                json.dump(results, f, indent=2)
            console.print(f"\n[green]SUCCESS: Comparison results exported to: {export_json}[/green]")
            
    except Exception as e:
        logger.exception("Comparison failed")
        console.print(f"[red]Error during comparison: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def query(
    flac_file: str = typer.Argument(..., help="Spatial FLAC file to query (local path or HTTP URL)"),
    bbox: str = typer.Option(..., "--bbox", "-b", help="Bounding box as 'xmin,ymin,xmax,ymax'"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file for extracted data"),
    format: str = typer.Option("ranges", "--format", "-f", help="Output format: 'ranges' or 'data'")
):
    """Query spatial FLAC file by bounding box for HTTP range streaming"""
    
    # Check if it's a URL or local file
    is_url = flac_file.startswith(('http://', 'https://'))
    
    if not is_url:
        # Local file validation
        flac_path = Path(flac_file)
        if not flac_path.exists():
            console.print(f"[red]Error: FLAC file does not exist: {flac_file}[/red]")
            raise typer.Exit(1)
        flac_file_obj = flac_path
    else:
        # URL validation
        flac_file_obj = flac_file
        
    # Parse bbox
    try:
        bbox_coords = [float(x.strip()) for x in bbox.split(',')]
        if len(bbox_coords) != 4:
            raise ValueError("Bbox must have 4 coordinates")
        bbox_tuple = tuple(bbox_coords)
    except (ValueError, IndexError) as e:
        console.print(f"[red]Error: Invalid bbox format. Use 'xmin,ymin,xmax,ymax': {e}[/red]")
        raise typer.Exit(1)
    
    try:
        from .spatial_encoder import SpatialFLACStreamer
        
        # Create streamer
        streamer = SpatialFLACStreamer(flac_file_obj)
        
        if format == "ranges":
            # Get HTTP byte ranges
            ranges = streamer.get_byte_ranges_for_bbox(bbox_tuple)
            
            console.print(f"[green]Found {len(ranges)} byte ranges for bbox {bbox}[/green]")
            
            # Create ranges table
            from rich.table import Table
            if is_url:
                file_display = flac_file.split('/')[-1]  # Show just filename for URLs
            else:
                file_display = flac_file_obj.name
            table = Table(title=f"HTTP Byte Ranges for {file_display}")
            table.add_column("Range #", style="cyan")
            table.add_column("Start Byte", style="green")
            table.add_column("End Byte", style="yellow") 
            table.add_column("Size (bytes)", style="blue")
            table.add_column("HTTP Range Header", style="magenta")
            
            total_bytes = 0
            for i, (start, end) in enumerate(ranges, 1):
                size = end - start + 1
                total_bytes += size
                range_header = f"bytes={start}-{end}"
                table.add_row(
                    str(i),
                    f"{start:,}",
                    f"{end:,}",
                    f"{size:,}",
                    range_header
                )
                
            console.print(table)
            console.print(f"[bold]Total data to fetch: {total_bytes:,} bytes[/bold]")
            
            # Save ranges to file if requested
            if output:
                ranges_data = {
                    "bbox": bbox_coords,
                    "total_ranges": len(ranges),
                    "total_bytes": total_bytes,
                    "ranges": [{"start": start, "end": end, "size": end - start + 1} 
                              for start, end in ranges],
                    "http_headers": [f"bytes={start}-{end}" for start, end in ranges]
                }
                
                with open(output, 'w') as f:
                    json.dump(ranges_data, f, indent=2)
                console.print(f"[green]Ranges saved to: {output}[/green]")
                
        elif format == "data":
            # Stream actual data
            console.print(f"[cyan]Streaming data for bbox {bbox}...[/cyan]")
            data = streamer.stream_bbox_data(bbox_tuple)
            
            console.print(f"[green]Extracted {len(data):,} bytes of FLAC data[/green]")
            
            if output:
                with open(output, 'wb') as f:
                    f.write(data)
                console.print(f"[green]Data saved to: {output}[/green]")
            else:
                console.print("[yellow]Use --output to save extracted data to file[/yellow]")
                
        else:
            console.print(f"[red]Error: Unknown format '{format}'. Use 'ranges' or 'data'[/red]")
            raise typer.Exit(1)
            
    except FileNotFoundError as e:
        console.print(f"[red]Error: Spatial index not found. File may not have spatial tiling enabled: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        logger.exception("Query failed")
        console.print(f"[red]Error during query: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def extract_tile(
    flac_file: str = typer.Argument(..., help="Spatial FLAC file (local path or HTTP URL)"),
    bbox: str = typer.Option(..., "--bbox", "-b", help="Bounding box as 'xmin,ymin,xmax,ymax'"),
    output: Path = typer.Option(..., "--output", "-o", help="Output TIFF file path")
):
    """Extract a specific tile from spatial FLAC as TIFF file"""
    
    # Check if it's a URL or local file
    is_url = flac_file.startswith(('http://', 'https://'))
    
    if not is_url:
        # Local file validation
        flac_path = Path(flac_file)
        if not flac_path.exists():
            console.print(f"[red]Error: FLAC file does not exist: {flac_file}[/red]")
            raise typer.Exit(1)
            
    # Parse bbox
    try:
        bbox_coords = [float(x.strip()) for x in bbox.split(',')]
        if len(bbox_coords) != 4:
            raise ValueError("Bbox must have 4 coordinates")
        bbox_tuple = tuple(bbox_coords)
    except (ValueError, IndexError) as e:
        console.print(f"[red]Error: Invalid bbox format. Use 'xmin,ymin,xmax,ymax': {e}[/red]")
        raise typer.Exit(1)
    
    try:
        from .spatial_encoder import SpatialFLACStreamer
        import tempfile
        import rasterio
        import numpy as np
        from rasterio.transform import from_bounds
        
        console.print(f"[cyan]Loading spatial index from: {flac_file}[/cyan]")
        streamer = SpatialFLACStreamer(flac_file)
        
        # Find tiles that intersect with the bbox
        console.print(f"[cyan]Finding tiles for bbox: {bbox}[/cyan]")
        ranges = streamer.get_byte_ranges_for_bbox(bbox_tuple)
        
        if not ranges:
            console.print(f"[red]Error: No tiles found for bbox {bbox}[/red]")
            raise typer.Exit(1)
            
        console.print(f"[green]Found {len(ranges)} tile(s) for extraction[/green]")
        
        # For remote URLs, we'll extract the raw FLAC data and decode it
        if is_url:
            # Stream the raw FLAC data
            console.print(f"[cyan]Streaming FLAC data from remote URL...[/cyan]")
            tile_data = streamer.stream_bbox_data(bbox_tuple)
            
            # Save to temporary file and decode
            with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as temp_flac:
                temp_flac.write(tile_data)
                temp_flac_path = temp_flac.name
                
            try:
                import pyflac
                console.print(f"[cyan]Decoding FLAC audio data...[/cyan]")
                decoder = pyflac.FileDecoder(temp_flac_path)
                audio_data, sample_rate = decoder.process()
                
                # Find the specific frame that matches our bbox
                matching_frames = []
                for frame in streamer.spatial_index.frames:
                    frame_bbox = frame.bbox
                    if (bbox_tuple[0] >= frame_bbox[0] and bbox_tuple[1] >= frame_bbox[1] and
                        bbox_tuple[2] <= frame_bbox[2] and bbox_tuple[3] <= frame_bbox[3]):
                        matching_frames.append(frame)
                
                if not matching_frames:
                    console.print(f"[red]Error: Could not find exact frame for bbox[/red]")
                    raise typer.Exit(1)
                    
                # Use the first matching frame
                target_frame = matching_frames[0]
                console.print(f"[green]Using frame {target_frame.frame_id} with bbox {target_frame.bbox}[/green]")
                
                # Reshape audio data to raster format
                expected_pixels = target_frame.window.width * target_frame.window.height
                audio_samples = len(audio_data) if len(audio_data.shape) == 1 else len(audio_data[:, 0])
                
                if audio_samples != expected_pixels:
                    console.print(f"[yellow]Warning: Audio samples ({audio_samples}) != expected pixels ({expected_pixels})[/yellow]")
                    # Try to crop or pad to match expected size
                    if audio_samples > expected_pixels:
                        audio_data = audio_data[:expected_pixels]
                    else:
                        # Pad with the last value
                        if len(audio_data.shape) == 1:
                            padding = np.full(expected_pixels - audio_samples, audio_data[-1])
                            audio_data = np.concatenate([audio_data, padding])
                        else:
                            padding = np.full((expected_pixels - audio_samples, audio_data.shape[1]), audio_data[-1, :])
                            audio_data = np.concatenate([audio_data, padding], axis=0)
                
                if len(audio_data.shape) == 1:
                    raster_data = audio_data.reshape(target_frame.window.height, target_frame.window.width)
                else:
                    raster_data = audio_data[:, 0].reshape(target_frame.window.height, target_frame.window.width)
                
                # Create transform for the tile
                xmin, ymin, xmax, ymax = target_frame.bbox
                transform = from_bounds(xmin, ymin, xmax, ymax,
                                      target_frame.window.width, target_frame.window.height)
                
                # Write as TIFF
                console.print(f"[cyan]Writing TIFF to: {output}[/cyan]")
                with rasterio.open(
                    output,
                    'w',
                    driver='GTiff',
                    height=target_frame.window.height,
                    width=target_frame.window.width,
                    count=1,
                    dtype=raster_data.dtype,
                    crs=streamer.spatial_index.crs,
                    transform=transform,
                    compress='lzw'
                ) as dst:
                    dst.write(raster_data, 1)
                    
            finally:
                # Clean up temp file
                import os
                if os.path.exists(temp_flac_path):
                    os.remove(temp_flac_path)
        else:
            # Local file - use the converter approach
            console.print(f"[cyan]Converting local spatial FLAC to extract tile...[/cyan]")
            from .converter import RasterFLACConverter
            
            # Convert full FLAC to temporary TIFF
            with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as temp_tif:
                temp_tif_path = temp_tif.name
                
            try:
                converter = RasterFLACConverter()
                converter.flac_to_tiff(Path(flac_file), Path(temp_tif_path))
                
                # Find the specific frame for the bbox
                matching_frames = []
                for frame in streamer.spatial_index.frames:
                    frame_bbox = frame.bbox
                    if (bbox_tuple[0] >= frame_bbox[0] and bbox_tuple[1] >= frame_bbox[1] and
                        bbox_tuple[2] <= frame_bbox[2] and bbox_tuple[3] <= frame_bbox[3]):
                        matching_frames.append(frame)
                
                if not matching_frames:
                    console.print(f"[red]Error: Could not find exact frame for bbox[/red]")
                    raise typer.Exit(1)
                    
                target_frame = matching_frames[0]
                console.print(f"[green]Using frame {target_frame.frame_id} with bbox {target_frame.bbox}[/green]")
                
                # Extract the tile window from full reconstructed TIFF
                with rasterio.open(temp_tif_path) as src:
                    from rasterio.windows import Window
                    tile_window = Window(
                        col_off=target_frame.window.col_off,
                        row_off=target_frame.window.row_off,
                        width=target_frame.window.width,
                        height=target_frame.window.height
                    )
                    
                    tile_data = src.read(1, window=tile_window)
                    tile_transform = src.window_transform(tile_window)
                    
                    # Write the tile as new TIFF
                    console.print(f"[cyan]Writing TIFF to: {output}[/cyan]")
                    with rasterio.open(
                        output,
                        'w',
                        driver='GTiff',
                        height=tile_data.shape[0],
                        width=tile_data.shape[1],
                        count=1,
                        dtype=tile_data.dtype,
                        crs=src.crs,
                        transform=tile_transform,
                        compress='lzw'
                    ) as dst:
                        dst.write(tile_data, 1)
                        
            finally:
                # Clean up temp file
                import os
                if os.path.exists(temp_tif_path):
                    os.remove(temp_tif_path)
        
        console.print(f"[green]SUCCESS: Tile extracted to: {output}[/green]")
        
        # Show verification info
        with rasterio.open(output) as src:
            console.print(f"[cyan]Verification:[/cyan]")
            console.print(f"  Dimensions: {src.width} x {src.height}")
            console.print(f"  CRS: {src.crs}")
            console.print(f"  Bounds: {src.bounds}")
            console.print(f"  Data type: {src.dtypes[0]}")
            data = src.read(1)
            console.print(f"  Data range: [{data.min()}, {data.max()}]")
            
    except Exception as e:
        logger.exception("Tile extraction failed")
        console.print(f"[red]Error during tile extraction: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def create_streaming(
    input_file: Path = typer.Argument(..., help="Input TIFF file to convert"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output streaming FLAC file"),
    tile_size: int = typer.Option(1024, "--tile-size", help="Size of streaming tiles (default: 1024x1024)"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing output file")
):
    """Create Netflix-style streaming FLAC with self-contained tiles"""
    
    # Validate input
    if not input_file.exists():
        console.print(f"[red]Error: Input file does not exist: {input_file}[/red]")
        raise typer.Exit(1)
    
    if input_file.suffix.lower() not in ['.tif', '.tiff']:
        console.print(f"[red]Error: Input must be a TIFF file, got: {input_file.suffix}[/red]")
        raise typer.Exit(1)
    
    # Set output path
    if output_file is None:
        output_file = input_file.with_suffix('.flac').with_name(input_file.stem + '_streaming.flac')
    
    # Check if output exists
    if output_file.exists() and not force:
        console.print(f"[red]Error: Output file already exists: {output_file}[/red]")
        console.print("[yellow]Use --force to overwrite[/yellow]")
        raise typer.Exit(1)
    
    try:
        console.print(f"[cyan]Creating Netflix-style streaming FLAC...[/cyan]")
        console.print(f"  Input: {input_file}")
        console.print(f"  Output: {output_file}")
        console.print(f"  Tile size: {tile_size}×{tile_size}")
        
        # Import streaming function
        import sys
        import os
        from pathlib import Path as PathLib
        import tempfile
        import rasterio
        from rasterio.windows import Window
        import json
        
        # Import our converter for tile creation
        from .converter import RasterFLACConverter
        
        console.print(f"\n[cyan]Processing input TIFF...[/cyan]")
        
        with rasterio.open(input_file) as src:
            console.print(f"  Dimensions: {src.width}×{src.height}")
            console.print(f"  CRS: {src.crs}")
            console.print(f"  Data type: {src.dtypes[0]}")
            
            # Calculate tiles
            total_tiles = 0
            tile_data_chunks = []
            total_offset = 0
            
            # Create spatial index header
            spatial_index = {
                "crs": str(src.crs),
                "transform": list(src.transform),
                "width": src.width,
                "height": src.height,
                "tile_size": tile_size,
                "frames": []
            }
            
            console.print(f"\n[cyan]Creating self-contained FLAC tiles...[/cyan]")
            
            frame_id = 0
            for row_start in range(0, src.height, tile_size):
                for col_start in range(0, src.width, tile_size):
                    # Calculate actual tile dimensions
                    tile_width = min(tile_size, src.width - col_start)
                    tile_height = min(tile_size, src.height - row_start)
                    
                    # Read tile data
                    window = Window(col_start, row_start, tile_width, tile_height)
                    tile_data = src.read(1, window=window)
                    
                    # Calculate geographic bounds
                    tile_transform = src.window_transform(window)
                    xmin = tile_transform.c
                    ymax = tile_transform.f
                    xmax = xmin + (tile_width * tile_transform.a)
                    ymin = ymax + (tile_height * tile_transform.e)
                    
                    console.print(f"  Processing tile {frame_id}: {tile_width}×{tile_height} at ({col_start},{row_start})")
                    
                    # Create complete FLAC for this tile
                    with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as temp_tif:
                        temp_tif_path = temp_tif.name
                    
                    with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as temp_flac:
                        temp_flac_path = temp_flac.name
                    
                    try:
                        # Write tile as temporary TIFF
                        with rasterio.open(
                            temp_tif_path, 'w',
                            driver='GTiff',
                            height=tile_height,
                            width=tile_width,
                            count=1,
                            dtype=tile_data.dtype,
                            crs=src.crs,
                            transform=tile_transform
                        ) as dst:
                            dst.write(tile_data, 1)
                        
                        # Convert TIFF to FLAC
                        converter = RasterFLACConverter()
                        converter.tiff_to_flac(PathLib(temp_tif_path), PathLib(temp_flac_path), compression_level=5)
                        
                        # Read the complete FLAC file
                        with open(temp_flac_path, 'rb') as f:
                            complete_flac_data = f.read()
                            
                    finally:
                        # Clean up temp files
                        for temp_path in [temp_tif_path, temp_flac_path]:
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                    
                    tile_size_bytes = len(complete_flac_data)
                    
                    # Add to spatial index
                    spatial_index["frames"].append({
                        "frame_id": frame_id,
                        "bbox": [xmin, ymin, xmax, ymax],
                        "window": {
                            "col_off": col_start,
                            "row_off": row_start,
                            "width": tile_width,
                            "height": tile_height
                        },
                        "byte_offset": total_offset,
                        "byte_size": tile_size_bytes
                    })
                    
                    tile_data_chunks.append(complete_flac_data)
                    total_offset += tile_size_bytes
                    frame_id += 1
        
        console.print(f"\n[cyan]Writing streaming FLAC file...[/cyan]")
        console.print(f"  Total tiles: {len(tile_data_chunks)}")
        
        # Write the streaming spatial FLAC file
        with open(output_file, 'wb') as f:
            # Write spatial index as JSON header (with length prefix)
            index_json = json.dumps(spatial_index, separators=(',', ':')).encode('utf-8')
            index_size = len(index_json)
            
            # Write: [4 bytes index size][JSON index][FLAC tiles...]
            f.write(index_size.to_bytes(4, 'big'))
            f.write(index_json)
            
            # Write all complete FLAC tiles
            for chunk in tile_data_chunks:
                f.write(chunk)
        
        # Show results
        file_size_mb = os.path.getsize(output_file) / 1024 / 1024
        avg_tile_size_kb = (total_offset / len(tile_data_chunks)) / 1024
        
        console.print(f"\n[green]SUCCESS: Netflix-style streaming FLAC created![/green]")
        console.print(f"  📁 File: {output_file}")
        console.print(f"  📊 Size: {file_size_mb:.2f} MB")
        console.print(f"  🧩 Tiles: {len(tile_data_chunks)}")
        console.print(f"  📏 Avg tile size: {avg_tile_size_kb:.1f} KB")
        console.print(f"  📋 Index size: {index_size:,} bytes")
        
        console.print(f"\n[yellow]💡 Usage examples:[/yellow]")
        console.print(f"  # Test local streaming")
        console.print(f"  python test_streaming.py {output_file} --last")
        console.print(f"  # Extract specific tile")
        console.print(f"  python test_streaming.py {output_file} --tile-id=0")
        console.print(f"  # Query by bbox")
        console.print(f"  python test_streaming.py {output_file} --bbox=\"xmin,ymin,xmax,ymax\"")
        
    except Exception as e:
        logger.exception("Streaming FLAC creation failed")
        console.print(f"[red]Error creating streaming FLAC: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def spatial_info(
    flac_file: str = typer.Argument(..., help="Spatial FLAC file to analyze (local path or HTTP URL)")
):
    """Show spatial index information for FLAC file"""
    
    # Validate input
    is_url = flac_file.startswith(('http://', 'https://'))
    if not is_url:
        flac_path = Path(flac_file)
        if not flac_path.exists():
            console.print(f"[red]Error: FLAC file does not exist: {flac_file}[/red]")
            raise typer.Exit(1)
        
    try:
        from .spatial_encoder import SpatialFLACStreamer
        from rich.table import Table
        
        # Create streamer
        streamer = SpatialFLACStreamer(flac_file)
        spatial_index = streamer.spatial_index
        
        # Display overview
        file_display_name = Path(flac_file).name if not is_url else flac_file
        console.print(f"[green]Spatial FLAC File: {file_display_name}[/green]")
        console.print(f"CRS: {spatial_index.crs}")
        console.print(f"Transform: {spatial_index.transform}")
        console.print(f"Total frames/tiles: {len(spatial_index.frames)}")
        
        # Create frames table
        table = Table(title="Spatial Frames")
        table.add_column("Frame ID", style="cyan")
        table.add_column("Bbox (xmin, ymin, xmax, ymax)", style="green")
        table.add_column("Window (col, row, width, height)", style="yellow")
        table.add_column("Byte Range", style="blue")
        table.add_column("Size", style="magenta")
        
        total_bytes = 0
        for frame in spatial_index.frames[:10]:  # Show first 10 frames
            bbox_str = f"({frame.bbox[0]:.6f}, {frame.bbox[1]:.6f}, {frame.bbox[2]:.6f}, {frame.bbox[3]:.6f})"
            window_str = f"({frame.window.col_off}, {frame.window.row_off}, {frame.window.width}, {frame.window.height})"
            byte_range = f"{frame.byte_offset}-{frame.byte_offset + frame.byte_size - 1}"
            
            table.add_row(
                str(frame.frame_id),
                bbox_str,
                window_str,
                byte_range,
                f"{frame.byte_size:,} bytes"
            )
            total_bytes += frame.byte_size
            
        console.print(table)
        
        if len(spatial_index.frames) > 10:
            console.print(f"[yellow]... and {len(spatial_index.frames) - 10} more frames[/yellow]")
            
        console.print(f"[bold]Total indexed data: {total_bytes:,} bytes[/bold]")
        
    except FileNotFoundError as e:
        console.print(f"[red]Error: Spatial index not found. File may not have spatial tiling enabled: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        logger.exception("Spatial info failed")
        console.print(f"[red]Error reading spatial info: {e}[/red]")
        raise typer.Exit(1)


@app.command("extract-streaming")
def extract_streaming(
    flac_url: str = typer.Argument(..., help="Streaming FLAC file (local path or HTTP URL)"),
    bbox: Optional[str] = typer.Option(None, "--bbox", "-b", help="Bounding box as 'xmin,ymin,xmax,ymax'"),
    tile_id: Optional[int] = typer.Option(None, "--tile-id", help="Extract specific tile by ID"),
    output: Path = typer.Option(..., "--output", "-o", help="Output TIFF file path"),
    center: bool = typer.Option(False, "--center", help="Extract center tile"),
    last: bool = typer.Option(False, "--last", help="Extract last tile")
):
    """Extract tiles from Netflix-style streaming FLAC files"""
    
    try:
        import struct
        import json
        import requests
        import tempfile
        from .converter import RasterFLACConverter
        
        console.print(f"[cyan]Loading streaming FLAC metadata from: {flac_url}[/cyan]")
        
        # Determine if it's a URL or local file
        is_url = isinstance(flac_url, str) and flac_url.startswith(('http://', 'https://'))
        
        # Read streaming metadata
        if is_url:
            # Get index size (first 4 bytes)
            response = requests.get(flac_url, headers={'Range': 'bytes=0-3'})
            if response.status_code != 206:
                raise ValueError(f"Server doesn't support range requests: {response.status_code}")
            
            index_size = struct.unpack('>I', response.content)[0]
            
            # Get the spatial index JSON
            response = requests.get(flac_url, headers={'Range': f'bytes=4-{3 + index_size}'})
            if response.status_code != 206:
                raise ValueError(f"Failed to get spatial index: {response.status_code}")
            
            metadata = json.loads(response.content.decode('utf-8'))
        else:
            # Local file
            with open(flac_url, 'rb') as f:
                index_size_bytes = f.read(4)
                index_size = struct.unpack('>I', index_size_bytes)[0]
                json_data = f.read(index_size)
                metadata = json.loads(json_data.decode('utf-8'))
        
        console.print(f"[green]Loaded metadata with {len(metadata['frames'])} tiles[/green]")
        
        # Determine which tile to extract
        target_frame = None
        
        if tile_id is not None:
            # Extract by tile ID
            for frame in metadata['frames']:
                if frame['frame_id'] == tile_id:
                    target_frame = frame
                    break
            if not target_frame:
                console.print(f"[red]Error: Tile ID {tile_id} not found[/red]")
                raise typer.Exit(1)
                
        elif last:
            # Extract last tile
            target_frame = max(metadata['frames'], key=lambda f: f['frame_id'])
            
        elif center:
            # Extract center tile
            frames = metadata['frames']
            all_bboxes = [frame['bbox'] for frame in frames]
            min_x = min(bbox[0] for bbox in all_bboxes)
            min_y = min(bbox[1] for bbox in all_bboxes)
            max_x = max(bbox[2] for bbox in all_bboxes)
            max_y = max(bbox[3] for bbox in all_bboxes)
            
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            
            # Find closest tile to center
            min_distance = float('inf')
            for frame in frames:
                frame_center_x = (frame['bbox'][0] + frame['bbox'][2]) / 2
                frame_center_y = (frame['bbox'][1] + frame['bbox'][3]) / 2
                distance = ((frame_center_x - center_x) ** 2 + (frame_center_y - center_y) ** 2) ** 0.5
                if distance < min_distance:
                    min_distance = distance
                    target_frame = frame
                    
        elif bbox:
            # Extract by bounding box
            try:
                bbox_coords = [float(x.strip()) for x in bbox.split(',')]
                if len(bbox_coords) != 4:
                    raise ValueError("Bbox must have exactly 4 coordinates")
            except (ValueError, IndexError) as e:
                console.print(f"[red]Error: Invalid bbox format. Use 'xmin,ymin,xmax,ymax': {e}[/red]")
                raise typer.Exit(1)
            
            # Find intersecting tiles
            intersecting_frames = []
            for frame in metadata['frames']:
                frame_bbox = frame['bbox']
                if (bbox_coords[0] < frame_bbox[2] and bbox_coords[2] > frame_bbox[0] and
                    bbox_coords[1] < frame_bbox[3] and bbox_coords[3] > frame_bbox[1]):
                    intersecting_frames.append(frame)
            
            if not intersecting_frames:
                console.print(f"[red]Error: No tiles intersect with bbox {bbox}[/red]")
                raise typer.Exit(1)
            
            if len(intersecting_frames) > 1:
                console.print(f"[yellow]Warning: Multiple tiles ({len(intersecting_frames)}) intersect. Using first one.[/yellow]")
            
            target_frame = intersecting_frames[0]
        else:
            console.print(f"[red]Error: Must specify --tile-id, --bbox, --center, or --last[/red]")
            raise typer.Exit(1)
        
        console.print(f"[cyan]Extracting tile {target_frame['frame_id']}:[/cyan]")
        console.print(f"  Bbox: {target_frame['bbox']}")
        console.print(f"  Size: {target_frame['byte_size']:,} bytes ({target_frame['byte_size']/1024/1024:.1f} MB)")
        
        # Download the specific tile
        header_size = 4 + index_size
        abs_start = header_size + target_frame['byte_offset']
        abs_end = abs_start + target_frame['byte_size'] - 1
        
        if is_url:
            console.print(f"[cyan]Downloading tile from remote URL...[/cyan]")
            response = requests.get(flac_url, headers={'Range': f'bytes={abs_start}-{abs_end}'})
            if response.status_code != 206:
                raise ValueError(f"Failed to download tile: {response.status_code}")
            tile_data = response.content
        else:
            console.print(f"[cyan]Reading tile from local file...[/cyan]")
            with open(flac_url, 'rb') as f:
                f.seek(abs_start)
                tile_data = f.read(target_frame['byte_size'])
        
        console.print(f"[green]Retrieved {len(tile_data):,} bytes[/green]")
        
        # Save as temporary FLAC file and convert
        with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as temp_flac:
            temp_flac.write(tile_data)
            temp_flac_path = temp_flac.name
        
        try:
            console.print(f"[cyan]Converting to TIFF: {output}[/cyan]")
            converter = RasterFLACConverter()
            converter.flac_to_tiff(Path(temp_flac_path), output)
            
            console.print(f"[bold green]SUCCESS: Extracted tile to {output}[/bold green]")
            console.print(f"[green]Geographic bounds: {target_frame['bbox']}[/green]")
            
            # Show bandwidth savings
            total_bytes = sum(frame['byte_size'] for frame in metadata['frames'])
            savings_percent = (1 - target_frame['byte_size'] / total_bytes) * 100
            console.print(f"[blue]Bandwidth savings: {savings_percent:.1f}% ({target_frame['byte_size']/1024/1024:.1f} MB vs {total_bytes/1024/1024:.1f} MB)[/blue]")
            
        finally:
            Path(temp_flac_path).unlink()
            
    except Exception as e:
        logger.exception("Streaming extraction failed")
        console.print(f"[red]Error during streaming extraction: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()