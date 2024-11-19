# DL4TO



<img src="https://dl4to.github.io/dl4to/images/logo_with_text.png" width="800" style="max-width: 800px">

**DL4TO** (short for "deep learning for topology optimization") is a Python library for three-dimensional topology optimization that is based on [PyTorch](https://pytorch.org/) and allows easy integration with neural networks. 

The library focuses on linear elasticity on structured grids and provides a flexible and easy-to-use framework. You can use DL4TO e.g. to
- solve the PDE for linear elasticity
- solve topology optimization problems with the "solid isotropic material with penalization" (SIMP) method using differentiable physics
- generate and import custom and public datasets for topology optimization
- build, train and evaluate deep learning pipelines in a wide range of use cases
- visualize three-dimensional voxel meshes with interactive plots

DL4TO enables research in the intersection of topology optimization and deep learning. The primary motivation for developing DL4TO is the need for a flexible and easy-to-use basis to conduct deep learning experiments for topology optimization in Python. This makes it especially useful for data scientists who are used to Numpy or PyTorch syntax. DL4TO will continue to be expanded, and the community is welcome to contribute.

<div style="display: flex; justify-content: row;">
   <img src="https://dl4to.github.io/dl4to/sample_2.gif" style="width:250px;height:auto;" />
   <img src="https://dl4to.github.io/dl4to/sample_2_2.gif" style="width:250px;height:auto;" />
   <img src="https://dl4to.github.io/dl4to/sample_3.gif" style="width:250px;height:auto;" />
</div>

# Features

The goal of this library is to create a basic framework for three-dimensional topology optimization that can be used in many different applications and with different deep learning methods. 

To this end, DL4TO aims at a:

- modular and expandable structure
- easy to understand code and clean documentation
- intuitive and compact way to transfer the mathematical problem into code
- reliable and well tested code basis

Some built-in features are:
- a custom PDE solver for linear elasticity that uses the finite differences method (FDM)
- an implementation of the SIMP algorithm for a wide variety of objective functions. Our SIMP uses PyTorch's autograd and makes use of the adjoint method for efficient backpropagation
- a framework that allows for learned topology optimization with any neural network architecture built in PyTorch
- an implementation of a UNet, as well as several preprocessing strategies and evaluation criteria
- an easy and straightforward implementation of an equivariance wrapper that makes use of group averaging for a variety of transformation groups
- easy generation of custom topology optimization problems
- easy generation of custom datasets for topology optimization, as well as support of the SELTO datasets [3]

A selection of deep learning-related problems that you can adress with DL4TO:
- **Supervised learning:** You can either learn the whole density mapping with one network ("end-to-end learning") or you can use a neural network to reduce the number of SIMP iterations. For instance, you could perform a few SIMP iterations and put the output into a trainable topo solver that performs basically a deblurring task.
- **Unsupervised learning:** Our library comes with several unsupervised criteria that can be used for unsupervised learning. Additionally, it is also easy to implement new custom criteria.
- **Neural reparameterization:** Learn an implicit density representation that reparameterizes the density field. Since these models are mesh-independent, they can represent the density function at arbitrary resolutions.
- **Learn the PDE solver:** You can implement a neural network that learns a mapping from densities to displacements or stresses and use this as a substitute for the FDM solver, for instance in the SIMP method.

<div style="display: flex; justify-content: row;">
    <img src="https://dl4to.github.io/dl4to/simp_animation2.gif" style="width:300px;height:auto;" />
</div>

# Getting Started

To learn the functionality and usage of DL4TO we recommend to have a look at the following sections:
- [Paper: We published a conference paper on DL4TO that explains the fundamentals of our framework](https://doi.org/10.1007/978-3-031-38271-0_54) [2]
- [Tutorial: Understand the structure of DL4TO](https://dl4to.github.io/dl4to/tutorial_overview.html)
- [Documentation](https://dl4to.github.io/dl4to/) 

For a comprehensive introduction to topology optimization and its applications in deep learning, refer to the dissertation of David Erzmann titled ["Equivariant deep learning for 3D topology optimization"](https://doi.org/10.26092/elib/3439) [4].

If you use any of these resources, please remember to cite them!

# Installation

DL4TO can be installed by using:

`pip install git+https://github.com/dl4to/dl4to`

If you want to change or add something to the code you should clone the repository and install it locally:

`git clone https://github.com/dl4to/dl4to`

`cd dl4to`

`pip install .`

Note: One of our plotting engines, pyvista, has recently deprecated support of the `pythreejs` backend that we use in the library. For that reason, we recommend installing a specific version of pyvista:

`pip install pyvista==0.38.1`

<div style="display: flex; justify-content: row;">
    <img src="https://dl4to.github.io/dl4to/simp_animation.gif" style="width:300px;height:auto;" />
</div>

# About

DL4TO was developed by David Erzmann and Sören Dittmer from the [University of Bremen](https://www.uni-bremen.de/en/) in Germany. In our research on deep learning-based topology optimization we found a substancial lack in a reliable yet flexible code base. We therefore started developing our own library, which we used for instance in our SELTO paper [1]. We then expanded the library such that it can be used by the community for a wide range of tasks, including supervised and unsupervised learning of density mappings or PDE solvers, as well as neural reparameterization. In our opinion, the PyTorch-based implementation smoothly connects the world of topology optimization with the world of deep learning. To our knowledge, only two Python libraries for topology optimization exist ([TopOpt](https://github.com/zfergus/topopt) and [ToPy](https://github.com/williamhunter/topy)), and neither allows for easy integration with neural networks.

# Contribute

DL4TO will continue to be expanded, and the community is welcome to contribute. If you are missing a feature or detect a bug or unexpected behaviour while using this library, feel free to open an issue or a pull request in [GitHub](https://github.com/dl4to/dl4to) or contact the authors.

# License

DL4TO uses an Apache License, see the [LICENSE](LICENSE) file.

# References

[1] Dittmer, Sören, et al. "SELTO: Sample-Efficient Learned Topology Optimization." arXiv preprint arXiv:2209.05098 (2023).

[2] Erzmann, David, et al. "DL4TO : A Deep Learning Library for Sample-Efficient Topology Optimization". Springer. https://doi.org/10.1007/978-3-031-38271-0_54 (2023)

[3] Dittmer, Sören, et al. "SELTO Dataset". Zenodo. https://doi.org/10.5281/zenodo.7781392 (2023)

[4] Erzmann, David. "Equivariant deep learning for 3D topology optimization". Diss. Universität Bremen. https://doi.org/10.26092/elib/3439 (2024)
