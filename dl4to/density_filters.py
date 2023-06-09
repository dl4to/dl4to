# AUTOGENERATED! DO NOT EDIT! File to edit: notebooks/density_representers/0_density_filters.ipynb (unless otherwise specified).

__all__ = ['DensityFilter', 'MaxPoolDensityFilter', 'ConvolutionDensityFilter', 'UniformDensityFilter',
           'RadialDensityFilter']

# Internal Cell
import torch
import warnings
import numpy as np
from torch.nn import Conv3d, Module

# Cell
class DensityFilter(Module):
    """
    A parent class that inherits several different filters for smoothing.
    """
    def __init__(self,
                 filter_size:int, # The size of the filter.
                 dtype:torch.dtype=torch.float32 # The datatype of the filter.
                ):
        self._filter_size = filter_size
        self.dtype = dtype
        super().__init__()


    @property
    def filter_size(self):
        return self._filter_size


    def _filtering(self, θ):
        raise NotImplementedError("Must be overridden.")


    def __call__(self,
                 θ:torch.Tensor # The input of the filter.
                ):
        """
        Apply the filtering to the input. Returns a `torch.Tensor`.
        """
        θ = self._filtering(θ)
        assert torch.all(0 <= θ)
        assert torch.all(θ <= 1)
        return θ

# Cell
class MaxPoolDensityFilter(DensityFilter):
    """
    A filter that applies max pooling.
    """
    def __init__(self,
                 filter_size:int, # The size of the filter.
                 dtype:torch.dtype=torch.float32 # The datatype of the filter.
                ):
        super().__init__(filter_size, dtype)


    def _filtering(self, θ):
        θ = torch.nn.functional.max_pool3d(θ, kernel_size=self._filter_size, stride=1, padding=self._filter_size//2)

        if self._filter_size % 2:
            return θ

        θ = torch.nn.functional.interpolate(θ, size=θ.shape[2:], mode='nearest')
        return θ

# Cell
class ConvolutionDensityFilter(DensityFilter):
    """
    A parent class that inherits convolutional filters.
    """
    def __init__(self,
                 filter_size:int, # The size of the filter.
                 dtype:torch.dtype=torch.float32 # The datatype of the filter.
                ):
        super().__init__(filter_size, dtype)
        self.kernel = self._get_kernel()
        self.conv = Conv3d(
            in_channels=1,
            out_channels=1,
            kernel_size=3*[filter_size],
            padding=int((filter_size-1)/2),
            padding_mode='replicate',
            bias=False,
            dtype=dtype,
        )
        self.conv.weight.data = self.kernel.clone()
        self.conv.requires_grad_(False)


    def _normalize_kernel(self, kernel):
        assert torch.all(0 <= kernel)
        kernel = kernel / kernel.sum()
        assert torch.all(kernel <= 1)
        assert torch.all(kernel >= 0)
        return kernel


    def _get_kernel(self):
        raise NotImplementedError("Must be overridden.")


    def _filtering(self, θ):
        assert torch.all(self.conv.weight.data <= 1)
        assert torch.all(self.conv.weight.data >= 0)
        assert torch.allclose(self.conv.weight.data, self.kernel)
        return self.conv(θ)

# Cell
class UniformDensityFilter(ConvolutionDensityFilter):
    """
    A class that performs convolution with a uniform filter, which is also refered to as mean pooling.
    """
    def __init__(self,
                 filter_size:int, # The size of the filter.
                 dtype:torch.dtype=torch.float32 # The datatype of the filter.
                ):
        if not filter_size % 2:
            filter_size += 1
            warnings.warn(f"filter_size must be an even number. Automatically setting filter_size to {filter_size}.")

        super().__init__(filter_size, dtype)


    def _get_kernel(self):
        kernel_ = torch.ones(self.filter_size, self.filter_size, dtype=self.dtype)
        kernel = torch.stack(self.filter_size * [kernel_])
        return self._normalize_kernel(kernel).unsqueeze(0).unsqueeze(0)

# Cell
class RadialDensityFilter(ConvolutionDensityFilter):
    """
    A class that performs convolution with a radial filter. A radial filter is a filter that has its maximal value in the center and decays radially to the outside.
    All values of the filter sum up to one.
    """
    def __init__(self,
                 filter_size:int, # The size of the filter.
                 dtype:torch.dtype=torch.float32 # The datatype of the filter.
                ):
        super().__init__(filter_size, dtype)


    def _get_kernel(self):
        filter_size = self.filter_size + 2
        r = filter_size // 2
        kernel = torch.zeros(3 * [filter_size], dtype=self.dtype)
        center = torch.ones(3, dtype=self.dtype) * r

        for i in range(filter_size):
            for j in range(filter_size):
                for k in range(filter_size):
                    position = torch.tensor([i, j, k], dtype=self.dtype)
                    dist = torch.norm(center - position, p=1)
                    kernel[i,j,k] = torch.relu(r - dist)

        kernel = kernel[1:-1, 1:-1, 1:-1]
        return self._normalize_kernel(kernel).unsqueeze(0).unsqueeze(0)