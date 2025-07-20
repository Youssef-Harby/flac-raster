"""
Core converter functionality for FLAC-Raster
"""
import json
import logging
from pathlib import Path
from typing import Tuple, Dict, Optional
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine
import pyflac
from rich.console import Console

console = Console()


class RasterFLACConverter:
    """Handles conversion between TIFF and FLAC formats for raster data"""
    
    def __init__(self):
        self.metadata_key = "RASTER_METADATA"
        self.logger = logging.getLogger("flac_raster.converter")
        
    def _calculate_audio_params(self, raster_data: np.ndarray, dtype: np.dtype) -> Tuple[int, int]:
        """Calculate appropriate sample rate and bit depth for FLAC based on raster data"""
        self.logger.debug(f"Calculating audio params for dtype: {dtype}")
        
        if dtype == np.uint8:
            bits_per_sample = 16  # Use 16-bit for 8-bit data (pyflac limitation)
        elif dtype == np.uint16 or dtype == np.int16:
            bits_per_sample = 16
        elif dtype == np.uint32 or dtype == np.int32 or dtype == np.float32:
            bits_per_sample = 24
        else:
            bits_per_sample = 24
            self.logger.warning(f"Unhandled dtype {dtype}, defaulting to 24-bit")
            
        # Calculate sample rate based on data dimensions
        # Higher resolution gets higher sample rate for better quality
        total_pixels = raster_data.shape[0] * raster_data.shape[1]
        self.logger.debug(f"Total pixels: {total_pixels:,}")
        
        if total_pixels < 1000000:  # < 1MP
            sample_rate = 44100
        elif total_pixels < 10000000:  # < 10MP
            sample_rate = 48000
        elif total_pixels < 100000000:  # < 100MP
            sample_rate = 96000
        else:
            sample_rate = 192000
        
        self.logger.info(f"Selected audio params: {sample_rate}Hz, {bits_per_sample}-bit")
        return sample_rate, bits_per_sample
    
    def _normalize_to_audio(self, data: np.ndarray, bits_per_sample: int) -> np.ndarray:
        """Normalize raster data to audio range"""
        self.logger.debug(f"Normalizing data of shape {data.shape} and dtype {data.dtype}")
        
        # Handle different data types
        if data.dtype == np.float32 or data.dtype == np.float64:
            # Assume float data is already normalized or in a specific range
            data_norm = data
            self.logger.debug("Float data detected, using as-is")
        else:
            # Normalize integer data to [-1, 1] range
            data_min = np.min(data)
            data_max = np.max(data)
            self.logger.debug(f"Data range: [{data_min}, {data_max}]")
            
            if data_max > data_min:
                data_norm = 2.0 * (data - data_min) / (data_max - data_min) - 1.0
            else:
                data_norm = np.zeros_like(data, dtype=np.float32)
                self.logger.warning("Data has no range (min==max), using zeros")
        
        # Convert to appropriate integer format for FLAC
        if bits_per_sample == 16:
            audio_data = (data_norm * 32767).astype(np.int16)
        elif bits_per_sample == 24:
            audio_data = (data_norm * 8388607).astype(np.int32)
        else:
            audio_data = (data_norm * 2147483647).astype(np.int32)
        
        self.logger.debug(f"Audio data shape: {audio_data.shape}, dtype: {audio_data.dtype}")
        return audio_data
    
    def _denormalize_from_audio(self, audio_data: np.ndarray, original_dtype: np.dtype, 
                               data_min: float, data_max: float) -> np.ndarray:
        """Convert audio data back to original raster range"""
        # Normalize audio data to [-1, 1]
        if audio_data.dtype == np.int8:
            data_norm = audio_data.astype(np.float32) / 127.0
        elif audio_data.dtype == np.int16:
            data_norm = audio_data.astype(np.float32) / 32767.0
        elif audio_data.dtype == np.int32:
            # Assuming 24-bit data in int32
            data_norm = audio_data.astype(np.float32) / 8388607.0
        elif audio_data.dtype in [np.float32, np.float64]:
            # Already normalized
            data_norm = audio_data.astype(np.float32)
        else:
            data_norm = audio_data.astype(np.float32)
        
        # Denormalize to original range
        if original_dtype in [np.float32, np.float64]:
            return data_norm.astype(original_dtype)
        else:
            data_denorm = (data_norm + 1.0) / 2.0 * (data_max - data_min) + data_min
            return np.round(data_denorm).astype(original_dtype)
    
    def tiff_to_flac(self, tiff_path: Path, flac_path: Path, compression_level: int = 5, 
                     spatial_tiling: bool = False, tile_size: int = 512):
        """Convert TIFF raster to FLAC format
        
        Args:
            tiff_path: Input TIFF file path
            flac_path: Output FLAC file path  
            compression_level: FLAC compression level (0-8)
            spatial_tiling: Enable spatial tiling for HTTP range streaming
            tile_size: Size of spatial tiles (default 512x512)
        """
        self.logger.info(f"Starting TIFF to FLAC conversion: {tiff_path} -> {flac_path}")
        self.logger.info(f"Compression level: {compression_level}")
        if spatial_tiling:
            self.logger.info(f"Spatial tiling enabled: {tile_size}x{tile_size} tiles")
            console.print(f"[cyan]Using spatial tiling for HTTP range streaming[/cyan]")
        console.print(f"[cyan]Reading TIFF file: {tiff_path}[/cyan]")
        
        # Use spatial encoder if spatial tiling is enabled
        if spatial_tiling:
            from .spatial_encoder import SpatialFLACEncoder
            encoder = SpatialFLACEncoder(tile_size=tile_size)
            spatial_index = encoder.encode_spatial_flac(tiff_path, flac_path, compression_level)
            return spatial_index
        
        with rasterio.open(tiff_path) as src:
            # Read raster data and metadata
            self.logger.debug("Reading raster data")
            data = src.read()
            meta = src.meta.copy()
            bounds = src.bounds
            crs = src.crs
            
            self.logger.info(f"Raster shape: {data.shape}")
            self.logger.info(f"Raster dtype: {data.dtype}")
            self.logger.info(f"CRS: {crs}")
            self.logger.debug(f"Bounds: {bounds}")
            self.logger.debug(f"Transform: {src.transform}")
            
            # Store original data statistics
            data_min = float(np.min(data))
            data_max = float(np.max(data))
            self.logger.info(f"Data range: [{data_min}, {data_max}]")
            
            # Prepare metadata for FLAC
            raster_metadata = {
                "width": meta["width"],
                "height": meta["height"],
                "count": meta["count"],  # number of bands
                "dtype": str(meta["dtype"]),
                "crs": crs.to_string() if crs else None,
                "transform": list(src.transform) if src.transform else None,
                "bounds": {
                    "left": bounds.left,
                    "bottom": bounds.bottom,
                    "right": bounds.right,
                    "top": bounds.top
                },
                "data_min": data_min,
                "data_max": data_max,
                "nodata": meta.get("nodata"),
                "driver": meta["driver"]
            }
            
            console.print(f"[green]Raster info: {meta['width']}x{meta['height']}, "
                         f"{meta['count']} band(s), dtype: {meta['dtype']}[/green]")
            
            # Calculate audio parameters
            sample_rate, bits_per_sample = self._calculate_audio_params(data, data.dtype)
            console.print(f"[yellow]Using sample rate: {sample_rate}Hz, "
                         f"bit depth: {bits_per_sample}[/yellow]")
            
            # Reshape data for FLAC (interleave bands as channels)
            if data.ndim == 3:
                # Multiple bands: (bands, height, width) -> (height*width, bands)
                channels = data.shape[0]
                data_reshaped = data.transpose(1, 2, 0).reshape(-1, channels)
                self.logger.info(f"Reshaped multi-band data: {data.shape} -> {data_reshaped.shape}")
            else:
                # Single band: (height, width) -> (height*width, 1)
                channels = 1
                data_reshaped = data.reshape(-1, 1)
                self.logger.info(f"Reshaped single-band data: {data.shape} -> {data_reshaped.shape}")
            
            # Normalize to audio range
            audio_data = self._normalize_to_audio(data_reshaped, bits_per_sample)
            
            # Create FLAC encoder
            self.logger.info(f"Creating FLAC encoder: channels={channels}, blocksize=4096")
            encoder = pyflac.StreamEncoder(
                write_callback=self._get_write_callback(flac_path),
                sample_rate=sample_rate,
                compression_level=compression_level,
                blocksize=4096  # Use frames for chunking
            )
            
            # Set channels and bits per sample as attributes
            encoder._channels = channels
            encoder._bits_per_sample = bits_per_sample
            
            # Process and encode data
            console.print("[cyan]Encoding to FLAC...[/cyan]")
            self.logger.info(f"Processing {audio_data.shape[0]:,} samples")
            encoder.process(audio_data)
            encoder.finish()
            
            # Close the output file
            if hasattr(self, 'output_file'):
                self.output_file.close()
                
            # Embed metadata directly in FLAC file (after encoding is complete)
            self._embed_metadata_in_flac(flac_path, raster_metadata)
            
            output_size = flac_path.stat().st_size
            input_size = tiff_path.stat().st_size
            compression_ratio = (1 - output_size / input_size) * 100
            
            self.logger.info(f"Conversion complete: {output_size / 1024 / 1024:.2f} MB")
            self.logger.info(f"Compression ratio: {compression_ratio:.1f}%")
            console.print(f"[green]SUCCESS: Converted to FLAC: {flac_path}[/green]")
            console.print(f"[dim]File size: {output_size / 1024 / 1024:.2f} MB (compression: {compression_ratio:.1f}%)[/dim]")
    
    def flac_to_tiff(self, flac_path: Path, tiff_path: Path):
        """Convert FLAC back to TIFF format"""
        self.logger.info(f"Starting FLAC to TIFF conversion: {flac_path} -> {tiff_path}")
        console.print(f"[cyan]Reading FLAC file: {flac_path}[/cyan]")
        
        # Decode FLAC
        self.logger.debug("Creating FLAC decoder")
        decoder = pyflac.FileDecoder(str(flac_path))
        audio_data, sample_rate = decoder.process()
        self.logger.info(f"Decoded audio shape: {audio_data.shape}, dtype: {audio_data.dtype}, sample_rate: {sample_rate}")
        
        # Load metadata from embedded FLAC metadata or fallback to sidecar
        self.logger.info("Loading metadata from FLAC file")
        metadata = self._read_embedded_metadata(flac_path)
        
        if not metadata:
            self.logger.error("No metadata found in FLAC file or sidecar file")
            raise ValueError("No metadata found in FLAC file or sidecar file")
        
        self.logger.debug(f"Found metadata: {list(metadata.keys())}")
        
        console.print(f"[green]Found raster metadata: {metadata['width']}x{metadata['height']}, "
                     f"{metadata['count']} band(s)[/green]")
        
        # Reshape audio data back to raster format
        width = metadata["width"]
        height = metadata["height"]
        count = metadata["count"]
        
        self.logger.info(f"Reshaping to raster: {width}x{height}, {count} band(s)")
        
        if count > 1:
            # Multiple bands: (height*width, bands) -> (bands, height, width)
            data_reshaped = audio_data.reshape(height, width, count)
            raster_data = data_reshaped.transpose(2, 0, 1)
            self.logger.debug(f"Reshaped multi-band: {audio_data.shape} -> {raster_data.shape}")
        else:
            # Single band: (height*width,) -> (height, width)
            raster_data = audio_data.reshape(height, width)
            self.logger.debug(f"Reshaped single-band: {audio_data.shape} -> {raster_data.shape}")
        
        # Denormalize from audio range
        original_dtype = np.dtype(metadata["dtype"])
        denormalized_data = self._denormalize_from_audio(
            raster_data, 
            original_dtype,
            metadata["data_min"],
            metadata["data_max"]
        )
        
        # Prepare metadata for rasterio
        meta = {
            "driver": "GTiff",
            "width": width,
            "height": height,
            "count": count,
            "dtype": original_dtype,
            "nodata": metadata.get("nodata"),
        }
        
        if metadata.get("crs"):
            meta["crs"] = CRS.from_string(metadata["crs"])
        
        if metadata.get("transform"):
            t = metadata["transform"]
            meta["transform"] = Affine(t[0], t[1], t[2], t[3], t[4], t[5])
        
        # Write TIFF
        console.print("[cyan]Writing TIFF file...[/cyan]")
        self.logger.info(f"Writing TIFF with metadata: {meta}")
        
        with rasterio.open(tiff_path, 'w', **meta) as dst:
            if count == 1:
                dst.write(denormalized_data, 1)
            else:
                dst.write(denormalized_data)
        
        output_size = tiff_path.stat().st_size
        self.logger.info(f"TIFF written successfully: {output_size / 1024 / 1024:.2f} MB")
        console.print(f"[green]SUCCESS: Converted to TIFF: {tiff_path}[/green]")
        
    def _embed_metadata_in_flac(self, flac_path: Path, metadata: Dict):
        """Embed geospatial metadata directly in FLAC file"""
        try:
            from mutagen.flac import FLAC
            
            # Open FLAC file for metadata editing
            flac_file = FLAC(str(flac_path))
            
            # Clear existing comments
            flac_file.clear()
            
            # Standard FLAC metadata
            flac_file["TITLE"] = "Geospatial Raster Data"
            flac_file["DESCRIPTION"] = "TIFF raster converted to FLAC with geospatial metadata"
            flac_file["ENCODER"] = "FLAC-Raster v0.1.0"
            
            # Core geospatial metadata
            flac_file["GEOSPATIAL_CRS"] = str(metadata.get("crs", ""))
            flac_file["GEOSPATIAL_WIDTH"] = str(metadata.get("width", 0))
            flac_file["GEOSPATIAL_HEIGHT"] = str(metadata.get("height", 0))
            flac_file["GEOSPATIAL_COUNT"] = str(metadata.get("count", 1))
            flac_file["GEOSPATIAL_DTYPE"] = str(metadata.get("dtype", ""))
            flac_file["GEOSPATIAL_NODATA"] = str(metadata.get("nodata", ""))
            flac_file["GEOSPATIAL_DATA_MIN"] = str(metadata.get("data_min", ""))
            flac_file["GEOSPATIAL_DATA_MAX"] = str(metadata.get("data_max", ""))
            
            # Transform and bounds as JSON
            flac_file["GEOSPATIAL_TRANSFORM"] = json.dumps(metadata.get("transform", []))
            flac_file["GEOSPATIAL_BOUNDS"] = json.dumps(metadata.get("bounds", []))
            
            # Spatial tiling info
            flac_file["GEOSPATIAL_SPATIAL_TILING"] = str(metadata.get("spatial_tiling", False))
            
            # Save metadata to FLAC file
            flac_file.save()
            
            self.logger.info("[SUCCESS] Embedded complete metadata in FLAC file (no sidecar needed)")
            console.print(f"[green][SUCCESS] All metadata embedded in FLAC file - no sidecar files needed![/green]")
            
        except ImportError:
            self.logger.warning("mutagen not available - falling back to JSON sidecar")
            console.print(f"[yellow][WARNING] Install mutagen for embedded metadata: pip install mutagen[/yellow]")
            
            # Fallback to JSON sidecar
            metadata_json = json.dumps(metadata, indent=2)
            metadata_path = flac_path.with_suffix('.json')
            self.logger.info(f"Saving metadata to: {metadata_path}")
            with open(metadata_path, 'w') as f:
                f.write(metadata_json)
                
        except Exception as e:
            self.logger.error(f"Failed to embed metadata: {e}")
            console.print(f"[red][ERROR] Failed to embed metadata: {e}[/red]")
            
            # Fallback to JSON sidecar
            metadata_json = json.dumps(metadata, indent=2)
            metadata_path = flac_path.with_suffix('.json')
            with open(metadata_path, 'w') as f:
                f.write(metadata_json)
                
    def _read_embedded_metadata(self, flac_path: Path) -> Optional[Dict]:
        """Read embedded metadata from FLAC file"""
        try:
            from mutagen.flac import FLAC
            
            flac_file = FLAC(str(flac_path))
            
            if "GEOSPATIAL_CRS" in flac_file:
                self.logger.info("Reading metadata from embedded FLAC metadata")
                
                metadata = {}
                
                # Extract geospatial fields
                geo_fields = [
                    "GEOSPATIAL_CRS", "GEOSPATIAL_WIDTH", "GEOSPATIAL_HEIGHT",
                    "GEOSPATIAL_COUNT", "GEOSPATIAL_DTYPE", "GEOSPATIAL_NODATA",
                    "GEOSPATIAL_DATA_MIN", "GEOSPATIAL_DATA_MAX", "GEOSPATIAL_TRANSFORM",
                    "GEOSPATIAL_BOUNDS", "GEOSPATIAL_SPATIAL_TILING"
                ]
                
                for field in geo_fields:
                    if field in flac_file:
                        value = flac_file[field][0]
                        key = field.replace("GEOSPATIAL_", "").lower()
                        
                        # Convert types
                        if key in ["width", "height", "count"]:
                            metadata[key] = int(value) if value else 0
                        elif key in ["data_min", "data_max"]:
                            metadata[key] = float(value) if value else 0.0
                        elif key in ["transform", "bounds"]:
                            metadata[key] = json.loads(value) if value else []
                        elif key == "spatial_tiling":
                            metadata[key] = value.lower() == "true"
                        elif key == "nodata":
                            metadata[key] = None if value == "None" else float(value) if value else None
                        else:
                            metadata[key] = value
                            
                return metadata
            else:
                raise ValueError("No embedded metadata found")
                
        except (ImportError, Exception) as e:
            self.logger.warning(f"Failed to read embedded metadata: {e}")
            
            # Fallback to JSON sidecar
            metadata_path = flac_path.with_suffix('.json')
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    return json.load(f)
                    
        return None
    
    def _get_write_callback(self, output_path: Path):
        """Create a write callback for FLAC encoder"""
        self.output_file = open(output_path, 'wb')
        
        def callback(data, num_bytes, num_samples, current_frame):
            self.output_file.write(data[:num_bytes])
            return True
            
        return callback