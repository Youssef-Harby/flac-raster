import rasterio
import numpy as np

# Read original and reconstructed
with rasterio.open('testing_dataset/multiband_test.tif') as src1:
    data1 = src1.read()  # Read all bands
    
with rasterio.open('testing_dataset/multiband_reconstructed.tif') as src2:
    data2 = src2.read()  # Read all bands

# Compare
print(f'Original shape: {data1.shape}')
print(f'Reconstructed shape: {data2.shape}')
print(f'Arrays equal: {np.array_equal(data1, data2)}')
print(f'Max difference: {np.max(np.abs(data1 - data2))}')
print(f'Mean difference: {np.mean(np.abs(data1 - data2)):.6f}')

# Check each band
for i in range(data1.shape[0]):
    print(f'\nBand {i+1}:')
    print(f'  Original range: [{data1[i].min()}, {data1[i].max()}]')
    print(f'  Reconstructed range: [{data2[i].min()}, {data2[i].max()}]')
    print(f'  Band equal: {np.array_equal(data1[i], data2[i])}')