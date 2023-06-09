# AUTOGENERATED! DO NOT EDIT! File to edit: notebooks/utils/utils.ipynb (unless otherwise specified).

__all__ = ['infect', 'get_current_datetime_as_string', 'create_dir', 'save_dict_as_txt', 'cast_to_problem',
           'cast_to_solution', 'cast_to_problems', 'cast_to_solutions', 'get_dataloader', 'get_σ_vm']

# Internal Cell
import torch

# Internal Cell
def _infect_step(start_points):
    m, n, k = start_points.shape

    padded = torch.zeros((2 + m, 2 + n, 2 + k), dtype=start_points.dtype, device=start_points.device)
    padded[1:-1, 1:-1, 1:-1] = start_points

    max_of_neighbors = padded[1:-1, 1:-1, 1:-1] | \
                       padded[2:  , 1:-1, 1:-1] | \
                       padded[ :-2, 1:-1, 1:-1] | \
                       padded[1:-1, 2:  , 1:-1] | \
                       padded[1:-1,  :-2, 1:-1] | \
                       padded[1:-1, 1:-1, 2:  ] | \
                       padded[1:-1, 1:-1,  :-2]
    return max_of_neighbors

# Cell
def infect(start_points, infectable):
    """
    An infection algorithm that starts from a set points and iteratively infects neighboring points.

    Returns
    -------
    torch.Tensor
    """
    infected_old = torch.zeros_like(start_points)
    assert start_points.dtype == infectable.dtype, f"{start_points.dtype} != {infectable.dtype}"
    assert start_points.device == infectable.device, f"{start_points.device} != {infectable.device}"
    infected = start_points.clone() & infectable

    while torch.any(infected_old != infected):
        infected_old = infected
        neighbors = _infect_step(infected)
        infected = neighbors & infectable
    return infected

# Internal Cell
import os
import json
import datetime
from collections import defaultdict
from typing import Union
import torch

# Cell
def get_current_datetime_as_string():
    """
    Determines and returns a string containing the current date and time.
    """
    now = datetime.datetime.today()
    return now.strftime('%Y-%m-%d--%H:%M:%S')


def create_dir(
    name:str, # The name of the directory that should be created.
    path:str=".", # The path where the directory should be created.
    prepend_date:bool=False # Whether to preprend the directory name with the date and time of its creation. Ensures unique directory names.
):
    """
    Creates a new directory, optionally prepended with the current datetime. If the directory already exists, then nothing happens. Returns a string that is the path to the directory.
    """
    if prepend_date:
        cdt = get_current_datetime_as_string()
        name = f"{cdt}_{name}"

    dir_path = f"{path}/{name}"

    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    return dir_path


def save_dict_as_txt(
    my_dict:dict, # The dictionary that should be saved.
    dir_path:str, # The path where the directory should be saved.
    file_name:str # The name of the txt file that should be created.
):
    """
    Saves a python dictionary as a txt file.
    """
    path = f"{dir_path}/{file_name}"
    if path[-4:] != ".txt":
        path += ".txt"
    with open(path, 'w') as f:
        json.dump(my_dict, f, indent=2)

# Cell
def cast_to_problem(
    problem_or_solution:Union["dl4to.problem.Problem","dl4to.solution.Solution"] # A problem or solution object.
):
    """
    Accepts a problem or a solution object as input and returns a problem. If the input is a problem, then the problem is simply returned without modification.
    If it is a solution, then `solution.problem` is returned.
    """
    assert type(problem_or_solution) != list, type(problem_or_solution)
    try:
        return problem_or_solution.problem
    except:
        return problem_or_solution


def cast_to_solution(
    problem_or_solution:Union["dl4to.problem.Problem","dl4to.solution.Solution"] # A problem or solution object.
):
    """
    Accepts a problem or a solution object as input and returns a solution. If the input is a problem, then `problem.trivial_solution`.
    If the input is a solution, then it is simply returned without modification.
    """
    assert type(problem_or_solution) != list, type(problem_or_solution)
    try:
        return problem_or_solution.trivial_solution
    except:
        return problem_or_solution


def cast_to_problems(
    problems_or_solutions:list # A list containing problem and solution objects.
):
    """
    Accepts as input a list containing problem and solutions object. Returns a list that only contains problem objects, where the solution objects have been
    transformed into problems via `solution.problem`.
    """
    return [cast_to_problem(p_or_s) for p_or_s in problems_or_solutions]


def cast_to_solutions(
    problems_or_solutions:list # A list containing problem and solution objects.
):
    """
    Accepts as input a list containing problem and solutions object. Returns a list that only contains solution objects, where the problem objects have been
    transformed into solutions via `problem.trivial_solution`.
    """
    return [cast_to_solution(p_or_s) for p_or_s in problems_or_solutions]

# Cell
def get_dataloader(
    dataset:"dl4to.datasets.TopoDataset", # The dataset for which the dataloader should be created.
    batch_size:int=1, # The batch size for the dataloader.
    shuffle:bool=True, # Whether the dataloader should shuffle the samples.
    num_workers:int=0 # The number of GPU workers, if trained on a GPU.
):
    """
    Returns a `torch.utils.data.DataLoader` object for `dataset`.
    """
    return torch.utils.data.DataLoader(
        dataset=dataset,
        batch_size=batch_size,
        collate_fn=lambda batch: list(zip(*batch)),
        shuffle=shuffle,
        num_workers=num_workers
    )

# Cell
def get_σ_vm(
    σ:torch.Tensor, # The stress tensor from which the von Mises stresses should be computed.
    ε:float=1e-9 # A small value that ensures numerically stable results.
):
    """
    Calculates the von Mises stresses from the 9-channel stress tensor `σ` and returns them in a 1-channel `torch.Tensor` object.
    """
    if len(σ.shape) == 4:
        assert σ.shape[0] == 9
        σ_vm = (.5 * ((σ[0] - σ[4]) ** 2
                    + (σ[4] - σ[8]) ** 2
                    + (σ[8] - σ[0]) ** 2
                    + 6 * (σ[1] ** 2 + σ[2] ** 2 + σ[5] ** 2)
                      ) + ε
               ) ** .5
        return σ_vm.unsqueeze(0)
    if len(σ.shape) == 5:
        assert σ.shape[1] == 9
        σ_vm = (.5 * ((σ[:,0] - σ[:,4]) ** 2
                    + (σ[:,4] - σ[:,8]) ** 2
                    + (σ[:,8] - σ[:,0]) ** 2
                    + 6 * (σ[:,1] ** 2 + σ[:,2] ** 2 + σ[:,5] ** 2)
                      ) + ε
               ) ** .5
        return σ_vm.unsqueeze(1)
    else:
        raise ValueError("The shape of σ must either be 4 or 5 channels.")