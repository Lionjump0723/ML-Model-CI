#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Author: Li Yuanming
Email: yli056@e.ntu.edu.sg
Date: 2021/1/22

Computer vision example on Transfer Learning.

This computer vision example illustrates how one could fine-tune a pre-trained
network (by default, a ResNet50 is used) using pytorch-lightning. For the sake
of this example, the 'cats and dogs dataset' (~60MB, see `DATA_URL` below) and
the proposed network (denoted by `TransferLearningModel`, see below) is
trained for 15 epochs.

The training consists of three stages.

From epoch 0 to 4, the feature extractor (the pre-trained network) is frozen except
maybe for the BatchNorm layers (depending on whether `train_bn = True`). The BatchNorm
layers (if `train_bn = True`) and the parameters of the classifier are trained as a
single parameters group with lr = 1e-2.

From epoch 5 to 9, the last two layer groups of the pre-trained network are unfrozen
and added to the optimizer as a new parameter group with lr = 1e-4 (while lr = 1e-3
for the first parameter group in the optimizer).

Eventually, from epoch 10, all the remaining layer groups of the pre-trained network
are unfrozen and added to the optimizer as a third parameter group. From epoch 10,
the parameters of the pre-trained network are trained with lr = 1e-5 while those of
the classifier is trained with lr = 1e-4.

Note:
    See: https://pytorch.org/tutorials/beginner/transfer_learning_tutorial.html

Reference:
    https://github.com/PyTorchLightning/pytorch-lightning/blob/master/pl_examples/domain_templates/computer_vision_fine_tuning.py
"""

from typing import Generator, Optional, Callable

import pytorch_lightning as pl
import torch
from torch import optim
from torch.nn import Module
from torch.optim.lr_scheduler import StepLR
from torch.optim.optimizer import Optimizer

BN_TYPES = (torch.nn.BatchNorm1d, torch.nn.BatchNorm2d, torch.nn.BatchNorm3d)


#  --- Utility functions ---


def _make_trainable(module: Module) -> None:
    """Unfreezes a given module.

    Args:
        module: The module to unfreeze
    """
    for param in module.parameters():
        param.requires_grad = True
    module.train()


def _recursive_freeze(module: Module, train_bn: bool = True) -> None:
    """Freezes the layers of a given module.

    Args:
        module: The module to freeze
        train_bn: If True, leave the BatchNorm layers in training mode
    """
    children = list(module.children())
    if not children:
        if not (isinstance(module, BN_TYPES) and train_bn):
            for param in module.parameters():
                param.requires_grad = False
            module.eval()
        else:
            # Make the BN layers trainable
            _make_trainable(module)
    else:
        for child in children:
            _recursive_freeze(module=child, train_bn=train_bn)


def freeze(module: Module, n: Optional[int] = None, train_bn: bool = True) -> None:
    """Freezes the layers up to index n (if n is not None).

    Args:
        module: The module to freeze (at least partially)
        n: Max depth at which we stop freezing the layers. If None, all
            the layers of the given module will be frozen.
        train_bn: If True, leave the BatchNorm layers in training mode
    """
    children = list(module.children())
    n_max = len(children) if n is None else int(n)

    for child in children[:n_max]:
        _recursive_freeze(module=child, train_bn=train_bn)

    for child in children[n_max:]:
        _make_trainable(module=child)


def filter_params(module: Module, train_bn: bool = True) -> Generator:
    """Yields the trainable parameters of a given module.

    Args:
        module: A given module
        train_bn: If True, leave the BatchNorm layers in training mode

    Returns:
        Generator
    """
    children = list(module.children())
    if not children:
        if not (isinstance(module, BN_TYPES) and train_bn):
            for param in module.parameters():
                if param.requires_grad:
                    yield param
    else:
        for child in children:
            for param in filter_params(module=child, train_bn=train_bn):
                yield param


def _unfreeze_and_add_param_group(
        module: Module, optimizer: Optimizer, lr: Optional[float] = None, train_bn: bool = True
):
    """Unfreezes a module and adds its parameters to an optimizer."""
    _make_trainable(module)
    params_lr = optimizer.param_groups[0]["lr"] if lr is None else float(lr)
    optimizer.add_param_group(
        {
            "params": filter_params(module=module, train_bn=train_bn),
            "lr": params_lr / 10.0,
        }
    )


#  --- Pytorch-lightning module ---


class FineTuneModule(pl.LightningModule):
    """Transfer Learning with pre-trained model"""

    def __init__(
            self,
            net: torch.nn.Module,
            loss: Callable,
            batch_size: int = 8,
            lr: float = 1e-2,
            lr_scheduler_gamma: float = 1e-1,
            step_size: int = 7,
            num_workers: int = 6,
            **kwargs,
    ) -> None:
        super().__init__()
        self.net = net
        self.loss = loss
        self.batch_size = batch_size
        self.lr = lr
        self.lr_scheduler_gamma = lr_scheduler_gamma
        self.step_size = step_size
        self.num_workers = num_workers

        self.train_acc = pl.metrics.Accuracy()
        self.valid_acc = pl.metrics.Accuracy()
        self.save_hyperparameters('loss', 'batch_size', 'lr', 'lr_scheduler_gamma', 'step_size', 'num_workers')

    def forward(self, x):

        return self.net(x)

    def training_step(self, batch, batch_idx):

        # 1. Forward pass:
        x, y = batch
        outputs = self.forward(x)
        preds = torch.argmax(outputs, dim=1)

        # 2. Compute loss & accuracy:
        train_loss = self.loss(outputs, y)
        accuracy = self.train_acc(preds, y)

        # 3. Outputs:
        tqdm_dict = {'train_loss': train_loss, 'train_acc': accuracy}
        self.log_dict(tqdm_dict, prog_bar=True)
        return {"loss": train_loss}

    def training_epoch_end(self, outputs):
        """Compute and log training loss and accuracy at the epoch level."""

        train_loss_mean = torch.stack([output['loss'] for output in outputs]).mean()
        train_acc_mean = self.train_acc.compute()
        self.log_dict({'train_loss': train_loss_mean, 'train_acc': train_acc_mean, 'step': self.current_epoch})

    def validation_step(self, batch, batch_idx):

        # 1. Forward pass:
        x, y = batch
        outputs = self.forward(x)
        preds = torch.argmax(outputs, dim=1)

        # 2. Compute loss & accuracy:
        val_loss = self.loss(outputs, y)
        accuracy = self.valid_acc(preds, y)

        return {"val_loss": val_loss, 'val_acc': accuracy}

    def validation_epoch_end(self, outputs):
        """Compute and log validation loss and accuracy at the epoch level."""

        val_loss_mean = torch.stack([output['val_loss'] for output in outputs]).mean()
        train_acc_mean = self.valid_acc.compute()
        log_dict = {'val_loss': val_loss_mean, 'val_acc': train_acc_mean}
        self.log_dict(log_dict, prog_bar=True)
        self.log_dict({'step': self.current_epoch})

    def configure_optimizers(self):
        optimizer = optim.Adam(filter(lambda p: p.requires_grad, self.parameters()), lr=self.lr)

        scheduler = StepLR(optimizer, step_size=self.step_size, gamma=self.lr_scheduler_gamma)

        return [optimizer], [scheduler]
