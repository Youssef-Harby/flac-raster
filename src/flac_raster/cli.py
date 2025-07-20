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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging")
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
            converter.tiff_to_flac(input_file, output_file, compression_level)
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
        decoder = pyflac.FileDecoder(str(file_path))
        
        # Get stream info
        info = decoder.process_metadata()
        console.print(f"  Sample rate: {decoder.sample_rate} Hz")
        console.print(f"  Channels: {decoder.channels}")
        console.print(f"  Bits per sample: {decoder.bits_per_sample}")
        console.print(f"  Total samples: {decoder.total_samples}")
        console.print(f"  File size: {file_path.stat().st_size / 1024 / 1024:.2f} MB")
        
        # Check for sidecar metadata file
        metadata_path = file_path.with_suffix('.json')
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                console.print(f"\n[yellow]Raster Metadata (from {metadata_path.name}):[/yellow]")
                console.print(f"  Original dimensions: {metadata['width']} x {metadata['height']}")
                console.print(f"  Original bands: {metadata['count']}")
                console.print(f"  Original dtype: {metadata['dtype']}")
                console.print(f"  CRS: {metadata.get('crs', 'None')}")
                if metadata.get('bounds'):
                    b = metadata['bounds']
                    console.print(f"  Bounds: ({b['left']}, {b['bottom']}, {b['right']}, {b['top']})")
        else:
            console.print(f"\n[yellow]No metadata file found[/yellow]")
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
            console.print(f"\n[green]✓ Comparison results exported to: {export_json}[/green]")
            
    except Exception as e:
        logger.exception("Comparison failed")
        console.print(f"[red]Error during comparison: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()