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
    file_path: Path = typer.Argument(..., help="FLAC or TIFF file to inspect")
):
    """Display information about a FLAC or TIFF file"""
    
    if not file_path.exists():
        console.print(f"[red]Error: File does not exist: {file_path}[/red]")
        raise typer.Exit(1)
    
    suffix = file_path.suffix.lower()
    
    if suffix in ['.tif', '.tiff']:
        import rasterio
        with rasterio.open(file_path) as src:
            console.print(f"[cyan]TIFF Information:[/cyan]")
            console.print(f"  Dimensions: {src.width} x {src.height}")
            console.print(f"  Bands: {src.count}")
            console.print(f"  Data type: {src.dtypes[0]}")
            console.print(f"  CRS: {src.crs}")
            console.print(f"  Bounds: {src.bounds}")
            console.print(f"  File size: {file_path.stat().st_size / 1024 / 1024:.2f} MB")
            
    elif suffix == '.flac':
        import pyflac
        console.print(f"[cyan]FLAC Information:[/cyan]")
        
        try:
            # Use the same approach as converter to get FLAC info
            decoder = pyflac.FileDecoder(str(file_path))
            audio_data, sample_rate = decoder.process()
            
            console.print(f"  Sample rate: {sample_rate} Hz")
            console.print(f"  Channels: {audio_data.shape[1] if len(audio_data.shape) > 1 else 1}")
            console.print(f"  Audio shape: {audio_data.shape}")
            console.print(f"  Data type: {audio_data.dtype}")
            console.print(f"  File size: {file_path.stat().st_size / 1024 / 1024:.2f} MB")
        except Exception as e:
            console.print(f"  [red]Error reading FLAC file: {e}[/red]")
            console.print(f"  File size: {file_path.stat().st_size / 1024 / 1024:.2f} MB")
        
        # Try to read embedded metadata first, then fall back to sidecar
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
                    num_tiles = flac_file.get('GEOSPATIAL_NUM_TILES', ['N/A'])[0]
                    tile_size = flac_file.get('GEOSPATIAL_TILE_SIZE', ['N/A'])[0]
                    console.print(f"  Spatial tiling: {num_tiles} tiles of {tile_size}x{tile_size}")
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
            metadata_path = file_path.with_suffix('.json')
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
def spatial_info(
    flac_file: Path = typer.Argument(..., help="Spatial FLAC file to analyze")
):
    """Show spatial index information for FLAC file"""
    
    # Validate input
    if not flac_file.exists():
        console.print(f"[red]Error: FLAC file does not exist: {flac_file}[/red]")
        raise typer.Exit(1)
        
    try:
        from .spatial_encoder import SpatialFLACStreamer
        from rich.table import Table
        
        # Create streamer
        streamer = SpatialFLACStreamer(flac_file)
        spatial_index = streamer.spatial_index
        
        # Display overview
        console.print(f"[green]Spatial FLAC File: {flac_file.name}[/green]")
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


if __name__ == "__main__":
    app()