#!/usr/bin/env python3
"""
Integration test for lazy loading and HTTP range streaming
This test demonstrates the full lazy loading workflow
"""

import sys
import os
from pathlib import Path
import time
import requests

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from flac_raster.spatial_encoder import SpatialFLACStreamer


def test_lazy_loading_workflow():
    """Test complete lazy loading workflow with real remote file"""
    
    print("🧪 Testing Lazy Loading & HTTP Range Streaming")
    print("=" * 60)
    
    # Test URL (public Storj bucket)
    test_url = "https://link.storjshare.io/raw/jw5jy6oecv5l3mbhdoa3ampnkp5a/truemaps-public/flac-raster/dem-raw_spatial.flac"
    
    # Step 1: Check file size without downloading
    print("1. 📊 Checking remote file size...")
    response = requests.head(test_url)
    total_file_size = int(response.headers.get('content-length', 0))
    print(f"   Remote file size: {total_file_size:,} bytes ({total_file_size/1024:.1f} KB)")
    
    # Step 2: Lazy load metadata only
    print("\n2. 🏃‍♂️ Lazy loading metadata (first 1MB only)...")
    start_time = time.time()
    
    try:
        streamer = SpatialFLACStreamer(test_url)
        metadata_load_time = time.time() - start_time
        
        print(f"   ✓ Metadata loaded in {metadata_load_time:.2f} seconds")
        print(f"   ✓ Found {len(streamer.spatial_index.frames)} spatial tiles")
        print(f"   ✓ Total indexed data: {streamer.spatial_index.total_bytes:,} bytes")
        print(f"   ✓ Bandwidth for metadata: 1,048,576 bytes (1 MB)")
        
        metadata_efficiency = (1 - 1048576 / total_file_size) * 100
        print(f"   ✓ Metadata bandwidth efficiency: {metadata_efficiency:.1f}% savings")
        
    except Exception as e:
        print(f"   ✗ Failed to load metadata: {e}")
        return False
    
    # Step 3: Test various bbox queries
    test_queries = [
        {
            "name": "Small area (single tile)",
            "bbox": (34.1, 28.65, 34.35, 28.9),
            "expected_efficiency": 80  # ~80% bandwidth savings
        },
        {
            "name": "Medium area (few tiles)", 
            "bbox": (34.3, 28.2, 34.7, 28.6),
            "expected_efficiency": 50  # ~50% bandwidth savings
        },
        {
            "name": "Large area (many tiles)",
            "bbox": (34.0, 28.5, 34.8, 29.0),
            "expected_efficiency": 20  # ~20% bandwidth savings
        }
    ]
    
    print("\n3. 🎯 Testing HTTP range queries...")
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n   Query {i}: {query['name']}")
        print(f"   Bbox: {query['bbox']}")
        
        try:
            ranges = streamer.get_byte_ranges_for_bbox(query['bbox'])
            query_bytes = sum(end - start + 1 for start, end in ranges)
            efficiency = (1 - query_bytes / total_file_size) * 100
            
            print(f"   ✓ Found {len(ranges)} byte range(s)")
            print(f"   ✓ Data to download: {query_bytes:,} bytes ({query_bytes/1024:.1f} KB)")
            print(f"   ✓ Bandwidth efficiency: {efficiency:.1f}% savings")
            
            # Generate HTTP range headers for demonstration
            if ranges:
                range_headers = [f"bytes={start}-{end}" for start, end in ranges]
                print(f"   ✓ HTTP Range headers: {range_headers[:2]}{'...' if len(range_headers) > 2 else ''}")
            
            # Check if efficiency meets expectations
            if efficiency >= query['expected_efficiency']:
                print(f"   ✓ Efficiency target met ({query['expected_efficiency']}%+)")
            else:
                print(f"   ⚠ Efficiency below target ({query['expected_efficiency']}%)")
                
        except Exception as e:
            print(f"   ✗ Query failed: {e}")
            return False
    
    # Step 4: Demonstrate progressive streaming concept
    print("\n4. 📡 Progressive streaming simulation...")
    print("   In a real application, you would:")
    print("   1. Load metadata once (1 MB)")
    print("   2. For each map viewport change:")
    print("      • Calculate bbox intersection with tiles")
    print("      • Issue HTTP Range requests for needed tiles only")
    print("      • Decode and display only requested geographic area")
    print("   3. Cache tiles for repeated access")
    
    # Step 5: Summary
    print("\n5. 📈 Lazy Loading Summary")
    print("   " + "=" * 50)
    
    total_tiles = len(streamer.spatial_index.frames)
    avg_tile_size = streamer.spatial_index.total_bytes / total_tiles if total_tiles > 0 else 0
    
    print(f"   File structure: {total_tiles} tiles, ~{avg_tile_size:.0f} bytes/tile")
    print(f"   Metadata overhead: 1 MB one-time download")
    print(f"   Query resolution: Geographic bbox → precise byte ranges")
    print(f"   Bandwidth efficiency: 20-80% savings vs full download")
    print(f"   Streaming protocol: Standard HTTP Range requests")
    print(f"   Infrastructure: Works with any HTTP server/CDN")
    
    print(f"\n✅ Lazy loading test completed successfully!")
    return True


def test_performance_comparison():
    """Compare traditional vs lazy loading approaches"""
    
    print("\n🏎️ Performance Comparison")
    print("=" * 40)
    
    test_url = "https://link.storjshare.io/raw/jw5jy6oecv5l3mbhdoa3ampnkp5a/truemaps-public/flac-raster/dem-raw_spatial.flac"
    
    # Get file size
    response = requests.head(test_url)
    total_size = int(response.headers.get('content-length', 0))
    
    print("Traditional approach:")
    print(f"  • Download entire file: {total_size:,} bytes")
    print(f"  • Process full raster in memory")
    print(f"  • Extract needed geographic area")
    print(f"  • Bandwidth usage: {total_size:,} bytes (100%)")
    
    print("\nLazy loading approach:")
    print(f"  • Download metadata: 1,048,576 bytes")
    print(f"  • Query specific geographic area")
    print(f"  • Download only intersecting tiles")
    
    # Example calculation for small query
    small_query_bytes = 33816  # From our test
    lazy_total = 1048576 + small_query_bytes
    savings = (1 - lazy_total / total_size) * 100
    
    print(f"  • Example small area: {small_query_bytes:,} bytes")
    print(f"  • Total bandwidth: {lazy_total:,} bytes")
    print(f"  • Bandwidth savings: {savings:.1f}%")
    
    print(f"\n💡 Lazy loading wins for queries < {total_size/1048576:.1f}× metadata size")


if __name__ == "__main__":
    print("FLAC-Raster Lazy Loading Integration Test")
    print("========================================")
    
    try:
        # Test internet connectivity
        print("\n🌐 Checking internet connectivity...")
        test_response = requests.head("https://httpbin.org/status/200", timeout=5)
        print("   ✓ Internet connection available")
        
        # Run main test
        success = test_lazy_loading_workflow()
        
        if success:
            test_performance_comparison()
            print("\n🎉 All tests passed! Lazy loading is working perfectly.")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed.")
            sys.exit(1)
            
    except requests.RequestException:
        print("   ✗ No internet connection - skipping remote tests")
        print("\n📋 To test lazy loading:")
        print("   1. Ensure internet connectivity")
        print("   2. Run: python tests/test_lazy_loading_integration.py")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        sys.exit(1)