import rasterio
import numpy as np

# Read original and reconstructed
with rasterio.open('testing_dataset/dem-raw.tif') as src1:
    data1 = src1.read(1)
    
with rasterio.open('testing_dataset/dem-reconstructed.tif') as src2:
    data2 = src2.read(1)

# Compare
print(f'Original shape: {data1.shape}')
print(f'Reconstructed shape: {data2.shape}')
print(f'Arrays equal: {np.array_equal(data1, data2)}')
print(f'Max difference: {np.max(np.abs(data1 - data2))}')
print(f'Mean difference: {np.mean(np.abs(data1 - data2)):.6f}')
print(f'Original range: [{data1.min()}, {data1.max()}]')
print(f'Reconstructed range: [{data2.min()}, {data2.max()}]')