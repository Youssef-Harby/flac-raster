#!/usr/bin/env python3
"""
Example: Spatial FLAC Streaming with HTTP Range Requests

This example demonstrates how to:
1. Convert a TIFF to spatial FLAC with tiling
2. Query specific bounding boxes 
3. Simulate HTTP range request streaming
4. Use the spatial index for efficient data access

This enables serving geospatial data over HTTP with client-side bbox queries!
"""

import json
import sys
from pathlib import Path

# Add src to path for examples
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flac_raster.spatial_encoder import SpatialFLACEncoder, SpatialFLACStreamer


def create_spatial_flac_demo():
    """Create a spatial FLAC file from sample data"""
    
    # Use sample DEM data
    tiff_path = Path("test_data/sample_dem.tif")
    flac_path = Path("demo_spatial.flac")
    
    if not tiff_path.exists():
        print(f"Sample data not found: {tiff_path}")
        print("Run: python examples/create_test_data.py first")
        return None
        
    # Create spatial FLAC with 256x256 tiles
    print("[INFO] Creating spatial FLAC with 256x256 tiles...")
    encoder = SpatialFLACEncoder(tile_size=256)
    spatial_index = encoder.encode_spatial_flac(tiff_path, flac_path, compression_level=5)
    
    print(f"[SUCCESS] Created {len(spatial_index.frames)} spatial tiles")
    print(f"[FILE] FLAC file: {flac_path}")
    print(f"[INDEX] Spatial index: {flac_path.with_suffix('.spatial.json')}")
    
    return flac_path


def demonstrate_bbox_queries(flac_path: Path):
    """Demonstrate different bbox queries"""
    
    print(f"\n[QUERY] Querying spatial FLAC: {flac_path}")
    
    # Create streamer
    streamer = SpatialFLACStreamer(flac_path)
    
    # Test different bounding boxes
    test_bboxes = [
        (-105.5, 39.988, -105.244, 40.244),  # Bottom-left tile
        (-105.244, 40.244, -104.988, 40.5),  # Top-right tile  
        (-105.4, 40.1, -105.1, 40.4),        # Overlapping area
        (-105.5, 39.988, -104.988, 40.5),    # Full extent
    ]
    
    for i, bbox in enumerate(test_bboxes, 1):
        print(f"\n[QUERY] Query {i}: BBOX {bbox}")
        
        # Get byte ranges
        ranges = streamer.get_byte_ranges_for_bbox(bbox)
        total_bytes = sum(end - start + 1 for start, end in ranges)
        
        print(f"   [DATA] {len(ranges)} byte ranges, {total_bytes:,} bytes total")
        
        # Show HTTP headers that would be used
        if ranges:
            http_headers = [f"bytes={start}-{end}" for start, end in ranges]
            print(f"   [HTTP] HTTP Range Headers: {http_headers}")
            
        # Extract data (simulate streaming)
        data = streamer.stream_bbox_data(bbox)
        print(f"   [EXTRACT] Extracted {len(data):,} bytes of FLAC data")


def simulate_http_range_requests(flac_path: Path):
    """Simulate HTTP range requests for a web server scenario"""
    
    print(f"\n[SERVER] Simulating HTTP Range Request Server...")
    
    # This would be your web server endpoint
    def serve_spatial_flac_range(bbox_str: str, flac_file: Path):
        """Simulate a web server endpoint that serves FLAC data by bbox"""
        
        # Parse bbox from URL parameter
        bbox = tuple(map(float, bbox_str.split(',')))
        
        # Load spatial index
        streamer = SpatialFLACStreamer(flac_file)
        
        # Get byte ranges for bbox
        ranges = streamer.get_byte_ranges_for_bbox(bbox)
        
        # Simulate HTTP response with byte ranges
        response_data = {
            "bbox": bbox,
            "content_type": "audio/flac",
            "content_length": sum(end - start + 1 for start, end in ranges),
            "accept_ranges": "bytes",
            "http_ranges": [f"bytes={start}-{end}" for start, end in ranges],
            "data": streamer.stream_bbox_data(bbox)  # In real scenario, this would be the response body
        }
        
        return response_data
    
    # Example client requests
    bbox_queries = [
        "-105.3,40.3,-105.1,40.5",     # Small area (northeast tile)
        "-105.5,39.988,-105.244,40.244", # Bottom-left tile
    ]
    
    for bbox_str in bbox_queries:
        print(f"\n[CLIENT] Client request: GET /spatial.flac?bbox={bbox_str}")
        
        # Server processes request
        response = serve_spatial_flac_range(bbox_str, flac_path)
        
        print(f"   [RESPONSE] Content-Type: {response['content_type']}")
        print(f"   [SIZE] Content-Length: {response['content_length']:,} bytes")
        print(f"   [RANGE] Accept-Ranges: {response['accept_ranges']}")
        print(f"   [HEADERS] HTTP Ranges: {response['http_ranges']}")
        print(f"   [DATA] Data size: {len(response['data']):,} bytes")
        
        # Client could now use these ranges for partial downloads
        print(f"   [SUCCESS] Client receives {len(response['data']):,} bytes of spatial FLAC data")


def demonstrate_web_use_case():
    """Show a complete web mapping use case"""
    
    print(f"\n[MAP] Web Mapping Use Case Example")
    print("="*50)
    
    print("""
Scenario: Interactive Web Map with On-Demand DEM Data

1. Server Setup:
   - Large DEM file converted to spatial FLAC with 256x256 tiles
   - Web server hosts FLAC file at: https://example.com/data/elevation.flac
   - Spatial index available at: https://example.com/data/elevation.spatial.json

2. Client Application (Web Map):
   - User pans/zooms to area of interest
   - JavaScript calculates viewport bbox: [-105.3, 40.3, -105.1, 40.5] 
   - App fetches spatial index to determine needed byte ranges
   - App makes HTTP range requests for only the visible tiles

3. HTTP Requests:
   GET /data/elevation.flac
   Range: bytes=0-16907
   
   Response: 206 Partial Content
   Content-Range: bytes 0-16907/33816
   Content-Type: audio/flac
   [FLAC data for visible area only]

4. Benefits:
   [+] Only download data for visible area (not entire file)
   [+] Works with standard HTTP servers (no special GIS server needed)
   [+] FLAC compression reduces bandwidth usage
   [+] Metadata preserved for accurate geographic positioning
   [+] Can be cached by CDNs and browsers
   [+] Progressive loading as user pans/zooms
   
This is like a "Zarr for geospatial data" but using audio compression!
    """)


if __name__ == "__main__":
    print("[DEMO] FLAC-Raster Spatial Streaming Demo")
    print("="*40)
    
    # Create spatial FLAC
    flac_path = create_spatial_flac_demo()
    
    if flac_path and flac_path.exists():
        # Demonstrate bbox queries
        demonstrate_bbox_queries(flac_path)
        
        # Simulate HTTP range requests  
        simulate_http_range_requests(flac_path)
        
        # Show web use case
        demonstrate_web_use_case()
        
        print(f"\n[COMPLETE] Demo complete! Check out:")
        print(f"   [FILE] {flac_path}")
        print(f"   [INDEX] {flac_path.with_suffix('.spatial.json')}")
        print(f"   [OUTPUT] extracted_data.flac")
        
    else:
        print("[ERROR] Demo failed - check sample data availability")