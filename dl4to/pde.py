# AUTOGENERATED! DO NOT EDIT! File to edit: notebooks/pde/5_fdm_solver.ipynb (unless otherwise specified).

__all__ = ['AutogradLinearSolver', 'LinearSolver', 'SparseLinearSolver', 'PDESolver', 'FDMDerivatives',
           'FDMAdjointDerivatives', 'FDMAssembly', 'UnpaddedFDM', 'FDM']

# Cell
import torch
import numpy as np
import time
import importlib.util
import warnings
from scipy.sparse.linalg import factorized, use_solver, spsolve
from scipy.sparse import csc_matrix
from typing import Callable

use_solver(assumeSortedIndices=True)

# Cell
class AutogradLinearSolver(torch.autograd.Function):
    @staticmethod
    def forward(ctx, θ, A_op, b, solver, A_mat, factorize=True):
        """
        In the forward pass we receive a tensor containing the input and return
        a tensor containing the output. `ctx` is a context object that can be used
        to stash information for backward computation. You can cache arbitrary
        objects for use in the backward pass using the `ctx.save_for_backward` method.

        Returns
        torch.Tensor
        """
        np_b = b.cpu().numpy()

        if factorize:
            solver = factorized(A_mat)
            x = solver(np_b)
        else:
            x = solver(A_mat, np_b)

        x = torch.from_numpy(x.astype(np_b.dtype))
        ctx.save_for_backward(θ, x, b)
        ctx.intermediate = (A_mat, solver, A_op, factorize)
        return x


    @staticmethod
    def backward(ctx, grad_output):
        """
        In the backward pass we receive a tensor containing the gradient of the loss
        with respect to the output, and we need to compute the gradient of the loss
        with respect to the input.

        Returns
        ----------
        (torch.Tensor, None, None, None, None, None)
        """
        torch.set_grad_enabled(True)
        θ, x, b = ctx.saved_tensors
        A_mat, solver, A_op, factorize = ctx.intermediate
        θ = θ.clone().detach()
        θ.requires_grad_(True)

        with torch.no_grad():
            flat_np_grad_output = grad_output.flatten().cpu().numpy()

            if factorize:
                y = solver(flat_np_grad_output)
            else:
                y = solver(A_mat, flat_np_grad_output)

            y = torch.from_numpy(y).clone().requires_grad_(False)
            x = x.clone().requires_grad_(False)

        expr = torch.sum(y * (b - A_op(x, θ).flatten()))
        grad_input = torch.autograd.grad(expr, θ)
        return grad_input[0], None, None, None, None, None

# Cell
class LinearSolver():
    """
    A parent class for linear solvers that are used to solve the linear system that solves the PDE.
    We compute the gradients via `torch.autograd` and with the adjoint method in the backwards pass.
    """
    def __init__(self,
                 factorize:bool=True # Whether the system matrix should be factorized.
                ):
        self.autograd_linear_solver = AutogradLinearSolver.apply
        self.factorize = factorize


    def _solver(self):
        raise NotImplementedError("Solver must be overridden.")


    def __call__(self,
                 θ:torch.Tensor, # The density for which the PDE is solved.
                 A_op:Callable[[torch.Tensor, torch.Tensor], torch.Tensor], # A function that takes `u` and `θ` as input and outputs the right hand side of the PDE. In other words, this is an operator representing the system matrix.
                 b:torch.Tensor, # A flattened version of the right side of the PDE.
                 A_mat:csc_matrix # The system matrix in sparse format.
                ):
        """
        Solves the PDE for the density `θ`. Returns the solution as a `torch.Tensor` object.
        """
        x = self.autograd_linear_solver(θ, A_op, b, self._solver(), A_mat, self.factorize)
        return x

# Cell
class SparseLinearSolver(LinearSolver):
    """
    A sparse linear solver implementation based on the `scipy.sparse.linalg.solve()` method that is used to solve the PDE of linear elasticity.
    """
    def __init__(self,
                 use_umfpack:bool=True, # Whether to use umfpack. If false, then the LU solver from `scipy.sparse` is used, which is usually slower.
                 factorize:bool=False # Whether the system matrix should be factorized.
                ):
        if use_umfpack or factorize:
            if importlib.util.find_spec('scikits') is None:
                warnings.warn("The package scikits.umfpack is not installed.Therefore, the LU solver from scipy.sparse is used, which is usually slower.")

        self.use_umfpack = use_umfpack
        super().__init__(factorize)


    def _solver(self):
        return lambda A, b: spsolve(A, b, use_umfpack=self.use_umfpack)

# Internal Cell
import copy
import torch

# Cell
class PDESolver:
    """
    A parent class that inherits all PDE solvers.
    """
    def __init__(self,
                 assemble_tensors_when_passed_to_problem:bool=False # Whether the PDE solver methods pre-assembles any tensors or arrays before solving the PDE for a concrete problem.
                ):
        self.assemble_tensors_when_passed_to_problem = assemble_tensors_when_passed_to_problem


    def __call__(self,
                 solution:"dl4to.solution.Solution", # The solution for which the PDE should be solved.
                 p:float=1., # The SIMP exponent when solving the PDE. Should usually be left at its default value of `1.`.
                 binary:bool=False # Whether the densities in the solution should be binarized before solving the PDE.
                ):
        """
        Does the same as the `solve_pde` method. Solves the pde for `solution` and SIMP exponent `p`. Returns three `torch.Tensor` objects: displacements `u`, stresses `σ` and von Mises stresses `σ_vm`.
        """
        return self.solve_pde(solution, p=p, binary=binary)


    def solve_pde(self,
                 solution:"dl4to.solution.Solution", # The solution for which the PDE should be solved.
                 p:float=1., # The SIMP exponent when solving the PDE. Should usually be left at its default value of `1.`.
                 binary:bool=False # Whether the densities in the solution should be binarized before solving the PDE.
                ):
        """
        Solves the pde for `solution` and SIMP exponent `p`. Returns three `torch.Tensor` objects: displacements `u`, stresses `σ` and von Mises stresses `σ_vm`.
        """
        raise NotImplementedError("Must be overridden.")


    def clone(self):
        """
        Returns a `dl4to.pde.PDESolver` object, which is a deepcopy of the PDE solver.
        """
        return copy.deepcopy(self)

# Internal Cell
import torch
import torch.autograd.functional as F

# Cell
class FDMDerivatives():
    @staticmethod
    def du_dx_central(u, h):
        du = torch.zeros_like(u)
        du[:, 1:-1, :,:] = (u[:,  2:, :,:] - u[:, 0:-2, :,:]) / (2 * h[0])
        du[:,  0  , :,:] = (u[:,  1 , :,:] - u[:,  0  , :,:]) / h[0]
        du[:, -1  , :,:] = (u[:, -1 , :,:] - u[:, -2  , :,:]) / h[0]
        return du


    @staticmethod
    def du_dy_central(u, h):
        du = torch.zeros_like(u)
        du[:,:, 1:-1, :] = (u[:,:,  2:, :] - u[:,:, 0:-2, :]) / (2 * h[1])
        du[:,:,  0  , :] = (u[:,:,  1 , :] - u[:,:,  0  , :]) / h[1]
        du[:,:, -1  , :] = (u[:,:, -1 , :] - u[:,:, -2  , :]) / h[1]
        return du


    @staticmethod
    def du_dz_central(u, h):
        du = torch.zeros_like(u)
        du[:,:,:, 1:-1] = (u[:,:,:,  2:] - u[:,:,:, 0:-2]) / (2 * h[2])
        du[:,:,:,  0  ] = (u[:,:,:,  1 ] - u[:,:,:,  0  ]) / h[2]
        du[:,:,:, -1  ] = (u[:,:,:, -1 ] - u[:,:,:, -2  ]) / h[2]
        return du


    @staticmethod
    def du_dx_forward(u, h):
        du = torch.zeros_like(u)
        du[:, 0:-1,:,:] = (u[:,  1:,:,:] - u[:, 0:-1,:,:]) / h[0]
        du[:, -1  ,:,:] = (u[:, -1 ,:,:] - u[:, -2  ,:,:]) / h[0]
        return du


    @staticmethod
    def du_dy_forward(u, h):
        du = torch.zeros_like(u)
        du[:,:, 0:-1,:] = (u[:,:,  1:,:] - u[:,:, 0:-1,:]) / h[1]
        du[:,:, -1  ,:] = (u[:,:, -1 ,:] - u[:,:, -2  ,:]) / h[1]
        return du


    @staticmethod
    def du_dz_forward(u, h):
        du = torch.zeros_like(u)
        du[:,:,:, 0:-1] = (u[:,:,:,  1:] - u[:,:,:, 0:-1]) / h[2]
        du[:,:,:, -1  ] = (u[:,:,:, -1 ] - u[:,:,:, -2  ]) / h[2]
        return du


    @staticmethod
    def du_dx(u, h, use_forward_differences=True):
        assert len(u.shape) == 4
        assert u.shape[1] > 2
        if use_forward_differences:
            return FDMDerivatives.du_dx_forward(u, h)
        return FDMDerivatives.du_dx_central(u, h)


    @staticmethod
    def du_dy(u, h, use_forward_differences=True):
        assert len(u.shape) == 4
        assert u.shape[2] > 2
        if use_forward_differences:
            return FDMDerivatives.du_dy_forward(u, h)
        return FDMDerivatives.du_dy_central(u, h)


    @staticmethod
    def du_dz(u, h, use_forward_differences=True):
        assert len(u.shape) == 4
        assert u.shape[3] > 2
        if use_forward_differences:
            return FDMDerivatives.du_dz_forward(u, h)
        return FDMDerivatives.du_dz_central(u, h)

# Cell
class FDMAdjointDerivatives():
    @staticmethod
    def du_dx_adj_for_a_sufficiently_large_number_of_voxels(ε, h):
        u = torch.zeros_like(ε)
        u[:,   0,:,:] = -(2 * ε[:,   0,:,:] + ε[:,   1,:,:]) / (2 * h[0])
        u[:,   1,:,:] =  (2 * ε[:,   0,:,:] - ε[:,   2,:,:]) / (2 * h[0])
        u[:,2:-2,:,:] =  (    ε[:,1:-3,:,:] - ε[:,3:-1,:,:]) / (2 * h[0])
        u[:,  -2,:,:] = -(2 * ε[:,  -1,:,:] - ε[:,  -3,:,:]) / (2 * h[0])
        u[:,  -1,:,:] =  (2 * ε[:,  -1,:,:] + ε[:,  -2,:,:]) / (2 * h[0])
        return u


    @staticmethod
    def du_dy_adj_for_a_sufficiently_large_number_of_voxels(ε, h):
        u = torch.zeros_like(ε)
        u[:,:,   0,:] = -(2 * ε[:,:,   0,:] + ε[:,:,   1,:]) / (2 * h[1])
        u[:,:,   1,:] =  (2 * ε[:,:,   0,:] - ε[:,:,   2,:]) / (2 * h[1])
        u[:,:,2:-2,:] =  (    ε[:,:,1:-3,:] - ε[:,:,3:-1,:]) / (2 * h[1])
        u[:,:,  -2,:] = -(2 * ε[:,:,  -1,:] - ε[:,:,  -3,:]) / (2 * h[1])
        u[:,:,  -1,:] =  (2 * ε[:,:,  -1,:] + ε[:,:,  -2,:]) / (2 * h[1])
        return u


    @staticmethod
    def du_dz_adj_for_a_sufficiently_large_number_of_voxels(ε, h):
        u = torch.zeros_like(ε)
        u[:,:,:,   0] = -(2 * ε[:,:,:,   0] + ε[:,:,:,   1]) / (2 * h[2])
        u[:,:,:,   1] =  (2 * ε[:,:,:,   0] - ε[:,:,:,   2]) / (2 * h[2])
        u[:,:,:,2:-2] =  (    ε[:,:,:,1:-3] - ε[:,:,:,3:-1]) / (2 * h[2])
        u[:,:,:,  -2] = -(2 * ε[:,:,:,  -1] - ε[:,:,:,  -3]) / (2 * h[2])
        u[:,:,:,  -1] =  (2 * ε[:,:,:,  -1] + ε[:,:,:,  -2]) / (2 * h[2])
        return u


    @staticmethod
    def du_dx_adj_for_a_sufficiently_small_number_of_voxels(ε, h):
        u = torch.zeros_like(ε)

        if u.shape[1] == 2:
            u[:, 0,:,:] = -(ε[:, 0,:,:] +  ε[:, 1,:,:]) / h[0]
            u[:, 1,:,:] = - u[:, 0,:,:]

        if u.shape[1] == 3:
            u[:,0,:,:] = -(2 * ε[:,0,:,:] + ε[:,1,:,:]) / (2 * h[0])
            u[:,1,:,:] =  (    ε[:,0,:,:] - ε[:,2,:,:]) /  h[0]
            u[:,2,:,:] =  (2 * ε[:,2,:,:] + ε[:,1,:,:]) / (2 * h[0])

        return u


    @staticmethod
    def du_dy_adj_for_a_sufficiently_small_number_of_voxels(ε, h):
        u = torch.zeros_like(ε)

        if u.shape[2] == 2:
            u[:,:, 0,:] = -(ε[:,:, 0,:] +  ε[:,:, 1,:]) / h[1]
            u[:,:, 1,:] = - u[:,:, 0,:]

        if u.shape[2] == 3:
            u[:,:,0,:] = -(2 * ε[:,:,0,:] + ε[:,:,1,:]) / (2 * h[1])
            u[:,:,1,:] =  (    ε[:,:,0,:] - ε[:,:,2,:]) /  h[1]
            u[:,:,2,:] =  (2 * ε[:,:,2,:] + ε[:,:,1,:]) / (2 * h[1])

        return u


    @staticmethod
    def du_dz_adj_for_a_sufficiently_small_number_of_voxels(ε, h):
        u = torch.zeros_like(ε)

        if u.shape[3] == 2:
            u[:,:,:, 0] = -(ε[:,:,:, 0] +  ε[:,:,:, 1]) / h[2]
            u[:,:,:, 1] = - u[:,:,:, 0]

        if u.shape[3] == 3:
            u[:,:,:,0] = -(2 * ε[:,:,:,0] + ε[:,:,:,1]) / (2 * h[2])
            u[:,:,:,1] =  (    ε[:,:,:,0] - ε[:,:,:,2]) /  h[2]
            u[:,:,:,2] =  (2 * ε[:,:,:,2] + ε[:,:,:,1]) / (2 * h[2])

        return u


    @staticmethod
    def du_dx_adj_forward(ε, h):
        u = torch.zeros_like(ε)
        u[:,   0   ,:,:] =  (                 - ε[:,      0,:,:]) / h[0]
        u[:,   1:-2,:,:] =  (ε[:,   0:-3,:,:] - ε[:,   1:-2,:,:]) / h[0]
        u[:,     -2,:,:] =  (ε[:,  -3,:,:] - ε[:,  -2,:,:] - ε[:,  -1,:,:]) / h[0]
        u[:,     -1,:,:] =  (ε[:,     -2,:,:] + ε[:,     -1,:,:]) / h[0]
        return u


    @staticmethod
    def du_dy_adj_forward(ε, h):
        u = torch.zeros_like(ε)
        u[:,:,   0   ,:] =  (                 - ε[:,:,      0,:]) / h[1]
        u[:,:,   1:-2,:] =  (ε[:,:,   0:-3,:] - ε[:,:,   1:-2,:]) / h[1]
        u[:,:,     -2,:] =  (ε[:,:,  -3,:] - ε[:,:,  -2,:] - ε[:,:,  -1,:]) / h[1]
        u[:,:,     -1,:] =  (ε[:,:,     -2,:] + ε[:,:,     -1,:]) / h[1]
        return u


    @staticmethod
    def du_dz_adj_forward(ε, h):
        u = torch.zeros_like(ε)
        u[:,:,:,   0   ] =  (                 - ε[:,:,:,      0]) / h[2]
        u[:,:,:,   1:-2] =  (ε[:,:,:,   0:-3] - ε[:,:,:,   1:-2]) / h[2]
        u[:,:,:,     -2] =  (ε[:,:,:,  -3] - ε[:,:,:,  -2] - ε[:,:,:,  -1]) / h[2]
        u[:,:,:,     -1] =  (ε[:,:,:,     -2] + ε[:,:,:,     -1]) / h[2]
        return u


    @staticmethod
    def du_dx_adj(ε, h, use_forward_differences=True):
        assert len(ε.shape) == 4
        if use_forward_differences:
            return FDMAdjointDerivatives.du_dx_adj_forward(ε, h)


        if ε.shape[1] > 3:
            return FDMAdjointDerivatives.du_dx_adj_for_a_sufficiently_large_number_of_voxels(ε, h)
        return FDMAdjointDerivatives.du_dx_adj_for_a_sufficiently_small_number_of_voxels(ε, h)


    @staticmethod
    def du_dy_adj(ε, h, use_forward_differences=True):
        assert len(ε.shape) == 4
        if use_forward_differences:
            return FDMAdjointDerivatives.du_dy_adj_forward(ε, h)


        if ε.shape[2] > 3:
            return FDMAdjointDerivatives.du_dy_adj_for_a_sufficiently_large_number_of_voxels(ε, h)
        return FDMAdjointDerivatives.du_dy_adj_for_a_sufficiently_small_number_of_voxels(ε, h)


    @staticmethod
    def du_dz_adj(ε, h, use_forward_differences=True):
        assert len(ε.shape) == 4
        if use_forward_differences:
            return FDMAdjointDerivatives.du_dz_adj_forward(ε, h)


        if ε.shape[3] > 3:
            return FDMAdjointDerivatives.du_dz_adj_for_a_sufficiently_large_number_of_voxels(ε, h)
        return FDMAdjointDerivatives.du_dz_adj_for_a_sufficiently_small_number_of_voxels(ε, h)

# Internal Cell
import torch
import numpy as np
from scipy.sparse import csc_matrix, hstack
import time

# Cell
class FDMAssembly():
    """
    This class contains methods that are used for the assembly of the FDM stiffness matrix.
    """

    @staticmethod
    def apply_dirichlet_zero_rows_to_operator(operator, Ω_dirichlet):
        """
        Returns a version of `operator` that fulfills the dirichlet conditions in the output.

        Returns
        -------
        torch.Tensor
        """
        def operator_with_dirichlet_rows_zero(x):
            assert len(Ω_dirichlet.shape) == len(x.shape) == 4
            y = operator(x)
            y[Ω_dirichlet] = 0
            return y

        return operator_with_dirichlet_rows_zero


    @staticmethod
    def apply_dirichlet_zero_columns_to_operator(operator, Ω_dirichlet):
        """
        Returns a version of `operator` that fulfills the dirichlet conditions in the input.

        Returns
        -------
        torch.Tensor
        """
        def operator_with_dirichlet_columns_zero(x):
            assert len(Ω_dirichlet.shape) == len(x.shape) == 4
            x = x.clone()
            x[Ω_dirichlet] = 0
            y = operator(x)
            return y

        return operator_with_dirichlet_columns_zero


    @staticmethod
    def _get_graph(operator, shape, channels_in, filter_shape):
        operator_graph = []

        for i in range(filter_shape[0]):
            for j in range(filter_shape[1]):
                for k in range(filter_shape[2]):
                    for c in range(channels_in):
                        x = torch.zeros(channels_in, *shape)
                        x[c, i::filter_shape[0], j::filter_shape[1], k::filter_shape[2]] = 1
                        operator_graph.append((x.numpy(), operator(x).numpy()))

        return operator_graph


    @staticmethod
    def _get_nbh_coordinates(pos_in_nbhs, channels_in, channels_out):
        assert pos_in_nbhs.shape[1:] == (4,)
        channels_prod = channels_in * channels_out
        nbh_coordinates = -2 * np.ones([pos_in_nbhs.shape[0], channels_prod*channels_out, 4])
        centroids = np.zeros([pos_in_nbhs.shape[0], channels_prod*channels_out, 4])

        if pos_in_nbhs.shape[0] > 0:
            centroids[:] = pos_in_nbhs[0]

        for c in range(channels_out):
            nbh_coordinates[:, channels_prod*c:channels_prod*(c+1), 0] = c

        for i in range(-1, 2):
            for j in range(-1, 2):
                for k in range(-1, 2):
                    if [i,j,k].count(0) >= 2:
                        rhs = pos_in_nbhs[:, 1:] + np.array([i, j, k])
                        t = channels_out * (i + 1) + channels_in * (j + 1) + (k + 1)
                        nbh_coordinates[:, t::channels_prod, 1:] = rhs.reshape(pos_in_nbhs.shape[0], 1, 3)
                        centroids[:, t::channels_prod, 1:] = pos_in_nbhs[:, 1:].reshape(pos_in_nbhs.shape[0], 1, 3)

        assert nbh_coordinates.shape[1:] == (channels_prod*channels_out, 4)
        return nbh_coordinates.reshape(-1, 4), centroids.reshape(-1, 4)


    @staticmethod
    def _remove_out_of_bounds_rows(nbh_coordinates, centroids, shape):
        mask0 = np.all(nbh_coordinates >=0, axis=1, keepdims=True).flatten()
        mask1 = nbh_coordinates[:,1] < shape[0]
        mask2 = nbh_coordinates[:,2] < shape[1]
        mask3 = nbh_coordinates[:,3] < shape[2]

        mask = mask0 & mask1 & mask2 & mask3
        return nbh_coordinates[mask].astype(int), centroids[mask].astype(int)


    @staticmethod
    def _get_1d_coordinates(positions, shape):
        assert positions.shape[1:] == (4,)
        coords_1d = positions[:,3] + shape[2]*positions[:,2] + shape[1] * shape[2] * positions[:,1] +  shape[0] * shape[1] * shape[2] * positions[:,0]
        return coords_1d.astype(int)


    @staticmethod
    def assemble_operator(operator, shape, channels_in=3, channels_out=9, filter_shape=3, Ω_dirichlet=None, column_wise=True):
        """
        Returns a sparse assembly of `operator`.

        Returns
        -------
        scipy.sparse.csc_matrix
        """
        if type(filter_shape) is int:
            filter_shape = [filter_shape, filter_shape, filter_shape]

        if Ω_dirichlet is not None:
            if column_wise:
                operator = FDMAssembly.apply_dirichlet_zero_columns_to_operator(operator, Ω_dirichlet)
            else:
                operator = FDMAssembly.apply_dirichlet_zero_rows_to_operator(operator, Ω_dirichlet)

        op_graph = FDMAssembly._get_graph(operator, shape, channels_in, filter_shape)
        col_indices = []
        row_indices = []
        values = []

        for x, y in op_graph:
            pos_in_nbhs = np.where(x)
            pos_in_nbhs = np.stack(pos_in_nbhs).transpose()

            nbh_3d, centroids = FDMAssembly._get_nbh_coordinates(pos_in_nbhs, channels_in, channels_out)
            nbh_3d, centroids = FDMAssembly._remove_out_of_bounds_rows(nbh_3d, centroids, shape)

            col_idx = FDMAssembly._get_1d_coordinates(centroids, shape)
            row_idx = FDMAssembly._get_1d_coordinates(nbh_3d, shape)

            col_indices.extend(col_idx)
            row_indices.extend(row_idx)

            vals = np.take(y.flatten(), row_idx, axis=0)
            values.extend(vals)

        return csc_matrix((values, (row_indices, col_indices)), shape=(channels_out*np.prod(shape), channels_in*np.prod(shape)))

# Internal Cell
import torch
import warnings
import numpy as np
from scipy.sparse import diags, csc_matrix

from .pde import SparseLinearSolver, PDESolver, FDMDerivatives, FDMAdjointDerivatives, FDMAssembly
from .utils import get_σ_vm

# Cell
class UnpaddedFDM(PDESolver):
    """
    A PDE solver for linear elasticity that uses the finite differences method (FDM) with padding.
    """
    def __init__(self, θ_min:float=1e-6, # The minimal value in the stiffness matrix. For numerical reasons we can not allow 0s, since they may lead to singular matrices.
                 use_forward_differences:bool=True, # Whether to use forward differences or central differences.
                 assemble_tensors_when_passed_to_problem:bool=True, # Whether the PDE solver methods pre-assembles any tensors or arrays before solving the PDE for a concrete problem.
                 ):
        self._θ_min = θ_min
        self._linear_solver = SparseLinearSolver(use_umfpack=True, factorize=True)
        self.use_forward_differences = use_forward_differences
        self.assemble_tensors_when_passed_to_problem = assemble_tensors_when_passed_to_problem
        self.assembled_tensors = False
        super().__init__(assemble_tensors_when_passed_to_problem)


    @property
    def problem(self):
        return self._problem


    @property
    def shape(self):
        return self.problem.shape


    @property
    def Ω_dirichlet(self):
        return self.problem.Ω_dirichlet


    @property
    def θ_min(self):
        return self._θ_min


    @property
    def b(self):
        return self._b


    @property
    def h(self):
        return self.problem.h


    @property
    def linear_solver(self):
        return self._linear_solver


    def assemble_tensors(self,
                         problem:"dl4to.problem.Problem" # The problem for which the tensors should be assembled.
                        ):
        """
        Assembles all FDM tensors from the problem object that can be pre-built without knowledge of the density distribution `θ`. This may take some time but makes future PDE evaluations for this problem much faster.
        """
        self._problem = problem.clone()
        GJ = lambda u: self._G(self._J(u))
        self._Ω_dirichlet_diags = diags(self.Ω_dirichlet.flatten().int().numpy())
        self._Jt_mat = FDMAssembly.assemble_operator(
            operator=self._J, shape=self.shape,
            Ω_dirichlet=self.Ω_dirichlet,
            filter_shape=3).transpose()
        self._GJ_mat = FDMAssembly.assemble_operator(
            operator=GJ, shape=self.shape, Ω_dirichlet=self.Ω_dirichlet, filter_shape=3)
        self._b = self._get_b()
        self.assembled_tensors = True


    def _get_θ_from_solution(self, solution, binary=False, clone=False):
        if clone:
            θ = solution.get_θ(binary).clone()
        else:
            θ = solution.get_θ(binary)
        return θ


    def _J(self, u, dirichlet=False):
        J = lambda u: torch.cat([
            FDMDerivatives.du_dx(u, self.h, self.use_forward_differences),
            FDMDerivatives.du_dy(u, self.h, self.use_forward_differences),
            FDMDerivatives.du_dz(u, self.h, self.use_forward_differences)
        ], dim=0)

        if dirichlet:
            return FDMAssembly.apply_dirichlet_zero_columns_to_operator(J, self.Ω_dirichlet)(u)
        return J(u)


    def _J_adj(self, σ, dirichlet=False):
        Jt = lambda σ: FDMAdjointDerivatives.du_dx_adj(σ[:3],  self.h, self.use_forward_differences) + \
                       FDMAdjointDerivatives.du_dy_adj(σ[3:6], self.h, self.use_forward_differences) + \
                       FDMAdjointDerivatives.du_dz_adj(σ[6:],  self.h, self.use_forward_differences)

        if dirichlet:
            return FDMAssembly.apply_dirichlet_zero_rows_to_operator(Jt, self.Ω_dirichlet)(σ)
        return Jt(σ)


    def _get_G(self):
        ν = self.problem.ν

        G = torch.tensor([
            [1-ν,  0-0,  0-0,    0-0,  ν-0,  0-0,    0-0,  0-0,  ν-0],
            [0-0, .5-ν,  0-0,   .5-ν,  0-0,  0-0,    0-0,  0-0,  0-0],
            [0-0,  0-0, .5-ν,    0-0,  0-0,  0-0,   .5-ν,  0-0,  0-0],

            [0-0, .5-ν,  0-0,   .5-ν,  0-0,  0-0,    0-0,  0-0,  0-0],
            [ν-0,  0-0,  0-0,    0-0,  1-ν,  0-0,    0-0,  0-0,  ν-0],
            [0-0,  0-0,  0-0,    0-0,  0-0, .5-ν,    0-0, .5-ν,  0-0],

            [0-0,  0-0, .5-ν,    0-0,  0-0,  0-0,   .5-ν,  0-0,  0-0],
            [0-0,  0-0,  0-0,    0-0,  0-0, .5-ν,    0-0, .5-ν,  0-0],
            [ν-0,  0-0,  0-0,    0-0,  ν-0,  0-0,    0-0,  0-0,  1-ν]
        ], dtype=self.problem.dtype)

        G = G.to(self.problem.device)
        return G / ((1 + ν) * (1 - 2 * ν))


    def _G(self, ε):
        ε = ε.type(self.problem.dtype)
        return torch.einsum('ij, jlmn -> ilmn', self._get_G(), ε)


    def _G_adj(self, σ):
        σ = σ.type(self.problem.dtype)
        return torch.einsum('ij, jlmn -> ilmn', self._get_G().t(), σ)


    def _GJ(self, u, dirichlet=False):
        apply_GJ = lambda u: self._G(self._J(u))

        if dirichlet:
            return FDMAssembly.apply_dirichlet_zero_columns_to_operator(apply_GJ, self.Ω_dirichlet)(u)
        return apply_GJ(u)


    def _GJ_adj(self, σ, dirichlet=False):
        apply_GJ_adj = lambda σ: self._J_adj(self._G_adj(σ))

        if dirichlet:
            return FDMAssembly.apply_dirichlet_zero_rows_to_operator(apply_GJ_adj, self.Ω_dirichlet)(σ)
        return apply_GJ_adj(σ)


    def _apply_θp(self, σ, θ, p=1., normalize=True):
        E = 1. if normalize else self.problem.E
        E_min = E * self.θ_min
        θ_ = E_min + θ**p * (E - E_min)
        return θ_ * σ


    def _assemble_θ(self, θ, p=1.):
        E = 1.
        E_min = E * self.θ_min
        θ_ = E_min + (θ**p).flatten().repeat(9).detach().numpy() * (E - E_min)
        return diags(θ_)


    def _A(self, u, θ, dirichlet=True, p=1.):
        u = u.view(3, θ.shape[-3], θ.shape[-2], θ.shape[-1])
        y = self._GJ(u, dirichlet)
        y = self._apply_θp(y, θ, p)
        y = self._J_adj(y, dirichlet)

        if dirichlet:
            y[self.Ω_dirichlet] = u.clone()[self.Ω_dirichlet]
        return y


    def _A_adj(self, y, θ, dirichlet=True, p=1.):
        y = y.view(3, θ.shape[-3], θ.shape[-2], θ.shape[-1])
        u = self._J(y, dirichlet)
        u = self._apply_θp(u, θ, p)
        u = self._GJ_adj(u, dirichlet)

        if dirichlet:
            u[self.Ω_dirichlet] = y.clone()[self.Ω_dirichlet]
        return u


    def _assemble_A(self, θ, p=1.):
        θ_mat = self._assemble_θ(θ, p)
        A = self._Jt_mat.dot(θ_mat.dot(self._GJ_mat)) + self._Ω_dirichlet_diags
        return csc_matrix(A)


    def _get_b(self):
        b = self.problem.F
        b[self.Ω_dirichlet] = 0
        b /= self.problem.E
        return b


    def _get_u(self, solution, p=1., binary=False):
        if binary and (solution.u_binary is not None):
            return solution.u_binary

        if (not binary) and (solution.u is not None):
            return solution.u

        if not self.assembled_tensors:
            self.assemble_tensors(solution.problem)

        θ = self._get_θ_from_solution(solution, binary=binary, clone=True)
        θ = θ.clamp(self.θ_min, 1)
        A_op = lambda u, θ: self._A(u, θ, p=p)
        A_mat = self._assemble_A(θ.cpu(), p)
        u = self._linear_solver(θ.cpu(), A_op, self.b.flatten(), A_mat)
        u = u.view(3, θ.shape[-3], θ.shape[-2], θ.shape[-1]).to(θ.device)

        if binary:
            solution.u_binary = u.clone()
        else:
            solution.u = u.clone()

        return u


    def _get_σ(self, solution, p=1., u=None, binary=False):
        if u is None:
            u = self._get_u(solution, p=p, binary=binary)

        θ = self._get_θ_from_solution(solution, binary=binary, clone=False)
        ε = self._J(u)
        σ = self._G(ε)
        σ = self._apply_θp(σ, θ, p=1., normalize=False)
        return σ


    def _stack_if_tensor_else_return_none(self, list):
        if any(type(entry) is not torch.Tensor for entry in list):
            return None
        return torch.stack(list)


    def solve_pde(self,
                 solution:"dl4to.solution.Solution", # The solution for which the PDE should be solved.
                 p:float=1., # The SIMP exponent when solving the PDE. Should usually be left at its default value of `1.`.
                 binary:bool=False # Whether the densities in the solution should be binarized before solving the PDE.
                ):
        """
        Solves the pde for `solution` and SIMP exponent `p`. Returns three `torch.Tensor` objects: displacements `u`, stresses `σ` and von Mises stresses `σ_vm`.
        """
        u = self._get_u(solution, p=p, binary=binary)
        σ = self._get_σ(solution, p=p, u=u, binary=binary)
        σ_vm = get_σ_vm(σ)
        return u, σ, σ_vm

# Internal Cell
import torch
import warnings
import numpy as np
from scipy.sparse import diags, csc_matrix

from .utils import get_σ_vm
from .pde import SparseLinearSolver, PDESolver, FDMDerivatives, FDMAdjointDerivatives, FDMAssembly, UnpaddedFDM

# Cell
class FDM(UnpaddedFDM):
    """
    A PDE solver for linear elasticity that uses the finite differences method (FDM) with padding.
    """
    def __init__(self, θ_min:float=1e-6, # The minimal value in the stiffness matrix. For numerical reasons we can not allow 0s, since they may lead to singular matrices.
                 use_forward_differences:bool=True, # Whether to use forward differences or central differences.
                 assemble_tensors_when_passed_to_problem:bool=True, # Whether the PDE solver methods pre-assembles any tensors or arrays before solving the PDE for a concrete problem.
                 padding_depth:int=2 # The depth of the padding surrounding the design space. Padding of 2 improves numerical performance.
                ):
        self.padding_depth = padding_depth
        super().__init__(
            θ_min=θ_min,
            use_forward_differences=use_forward_differences,
            assemble_tensors_when_passed_to_problem=assemble_tensors_when_passed_to_problem
        )


    @property
    def shape(self):
        return self.Ω_dirichlet.shape[-3:]


    @property
    def Ω_dirichlet(self):
        return self._get_padded_tensor(self.problem.Ω_dirichlet)


    def _get_padded_tensor(self, tensor):
        p_d = int(self.padding_depth)
        if p_d == 0:
            return tensor

        shape = tensor.shape
        assert len(shape) == 4
        padded_tensor = torch.zeros(
            shape[0], shape[1]+2*p_d, shape[2]+2*p_d, shape[3]+2*p_d, dtype=tensor.dtype
        )
        padded_tensor[:, p_d:-p_d, p_d:-p_d, p_d:-p_d] = tensor
        return padded_tensor


    def _remove_padding(self, tensor):
        p_d = int(self.padding_depth)
        if p_d == 0:
            return tensor

        shape = tensor.shape
        assert len(shape) == 4
        return tensor[:, p_d:-p_d, p_d:-p_d, p_d:-p_d]


    def _get_θ_from_solution(self, solution, binary=False, clone=False):
        θ = super()._get_θ_from_solution(solution, binary=binary, clone=clone)
        return self._get_padded_tensor(θ)


    def _A(self, u, θ, dirichlet=True, p=1.):
        if θ.shape[-3:] == self.shape[-3:]:
            return super()._A(u=u, θ=θ, dirichlet=dirichlet, p=p)
        θ_padded = self._get_padded_tensor(θ)
        assert θ_padded.shape[-3:] == self.shape[-3:]
        return super()._A(u=u, θ=θ_padded, dirichlet=dirichlet, p=p)


    def _A_adj(self, y, θ, dirichlet=True, p=1.):
        if θ.shape[-3:] == self.shape[-3:]:
            return super()._A_adj(y=y, θ=θ, dirichlet=dirichlet, p=p)
        θ_padded = self._get_padded_tensor(θ)
        assert θ_padded.shape[-3:] == self.shape[-3:]
        return super()._A_adj(y=y, θ=θ_padded, dirichlet=dirichlet, p=p)


    def _get_b(self):
        b = self.problem.F
        b = self._get_padded_tensor(b)
        b[self.Ω_dirichlet] = 0
        b /= self.problem.E
        return b


    def _get_u(self, solution, p=1., binary=False, get_padded=False):
        u = super()._get_u(solution, p=p, binary=binary)
        if get_padded:
            return u
        return self._remove_padding(u)


    def _get_σ(self, solution, p=1., u=None, binary=False, get_padded=False):
        if u is None:
            u = self._get_u(solution, p=p, binary=binary, get_padded=True)
        σ = super()._get_σ(solution, p=p, u=u, binary=binary)
        if get_padded:
            return σ
        return self._remove_padding(σ)


    def solve_pde(self,
                 solution:"dl4to.solution.Solution", # The solution for which the PDE should be solved.
                 p:float=1., # The SIMP exponent when solving the PDE. Should usually be left at its default value of `1.`.
                 binary:bool=False, # Whether the densities in the solution should be binarized before solving the PDE.
                 get_padded:bool=False # Whether the density should be padded before the PDE is solved. Takes a bit longer to solve, but is more accurate.
                ):
        """
        Solves the pde for `solution` and SIMP exponent `p`. Returns three `torch.Tensor` objects: displacements `u`, stresses `σ` and von Mises stresses `σ_vm`.
        """
        u = self._get_u(solution, p=p, binary=binary, get_padded=True)
        σ = self._get_σ(solution, p=p, u=u, binary=binary, get_padded=True)
        σ_vm = get_σ_vm(σ)
        if get_padded:
            return u, σ, σ_vm
        return self._remove_padding(u), self._remove_padding(σ), self._remove_padding(σ_vm)