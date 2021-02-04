#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Author: Li Yuanming
Email: yli056@e.ntu.edu.sg
Date: 1/31/2021

ML model structure related API
"""
import torch
from fastapi import APIRouter
from modelci.hub.manager import get_remote_model_weight

from modelci.types.bo import Engine

from modelci.persistence.service import ModelService

from modelci.experimental.model.model_structure import Structure

router = APIRouter()


@router.get('/{id}', response_model=Structure)
async def get_model_structure(id: str):  # noqa
    """
    Get model structure as a model structure graph (connection between layer as edge, layers as nodes)

    Arguments:
        id (str): Model object ID.
    """
    # return model DAG
    model = ModelService.get_model_by_id(id)
    if model.engine != Engine.PYTORCH:
        raise ValueError(f'model {id} is not supported for editing. '
                         f'Currently only support model with engine=PYTORCH')

    # download model as local cache
    cache_path = get_remote_model_weight(model=model)
    net = torch.load(cache_path)
    return Structure.from_model(net)


@router.patch('/{id}')  # TODO: add response_model
def update_model_structure_as_new(id: str, structure: Structure, dry_run: bool = False):  # noqa
    """
    TODO: Update model structure by adjusting layers (add, modify, delete) or rewiring the
        connections between layers.

    Examples:
        Fine-tune the model by modify the layer with name 'fc' (last layer). The layer
        has a changed argument out_features = 10. op_='M' indicates the operation to this layer ('fc')
        is 'Modify'. There is no changes in layer connections.
        Therefore, the structure change summary is
            [M] fc: (...) out_features=10

        >>> from collections import OrderedDict
        >>> structure_data = {
        ...     'layer': OrderedDict({'fc': {'out_features': 10, 'op_': 'M', 'type_': 'torch.nn.Linear'}})
        ... }
        >>> update_model_structure_as_new(id=..., structure=Structure.parse_obj(structure_data))

        Use original model as a feature extractor. The new model delete the last layer named 'fc', and add two
        layers as following:
            fc1: (nn.Linear) in_features=1024, out_features=512
            fc2: (nn.Linear) in_features=512, out_features=10
        The node change summary is
            [D] fc
            [A] fc1: (nn.Linear) in_features=1024, out_features=512
            [A] fc2: (nn.Linear) in_features=512, out_features=10
        Besides, we have connection changes:
            [D] conv1 -> fc
            [A] conv1 -> fc1
            [A] fc1 -> fc2

        >>>
        ... structure_data = {
        ...     'layer': {
        ...         'fc': {'op_': 'D'},
        ...         'fc1': {'in_features': 1024, 'out_features': 512, 'type_': 'torch.nn.Linear', 'op_': 'A'},
        ...         'fc2': {'in_features': 512, 'out_features': 10, 'type_': 'torch.nn.Linear', 'op_': 'A'},
        ...     },
        ...     'connection': {
        ...         'conv1': {'fc': 'D', 'fc1': 'A'},
        ...         'fc1': {'fc2': 'A'},
        ...     }
        ... }

    Args:
        id (str): Model object ID of the original structure.
        structure: A model structure graph indicating changed layer (node) and layer connection (edge).
        dry_run (bool): Dry run update for validation.

    Returns:

    """
    raise NotImplementedError('Method `update_model_structure_as_new` not implemented.')
