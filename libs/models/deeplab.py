#!/usr/bin/env python
# coding: utf-8
#
# Author:   Kazuto Nakashima
# URL:      http://kazuto1011.github.io
# Created:  2017-11-19

from collections import OrderedDict

import torch
import torch.nn as nn
import torch.nn.functional as F

from .resnet import _ConvBatchNormReLU, _ResBlock

class _ASPPModule(nn.Module):
    """Atrous Spatial Pyramid Pooling"""

    def __init__(self, in_channels, out_channels, pyramids):
        super(_ASPPModule, self).__init__()
        self.stages = nn.Module()
        for i, (dilation, padding) in enumerate(zip(pyramids, pyramids)):
            self.stages.add_module(
                'c{}'.format(i),
                nn.Conv2d(
                    in_channels=in_channels,
                    out_channels=out_channels,
                    kernel_size=3,
                    stride=1,
                    padding=padding,
                    dilation=dilation,
                    bias=True
                )
            )

        for m in self.stages.children():
            nn.init.normal(m.weight, mean=0, std=0.01)
            nn.init.constant(m.bias, 0)

    def forward(self, x):
        h = 0
        for stage in self.stages.children():
            h += stage(x)
        return h


class DeepLabV2(nn.Sequential):
    """DeepLab v2"""

    def __init__(self, n_classes, n_blocks, pyramids):
        super(DeepLabV2, self).__init__()
        self.add_module(
            'layer1',
            nn.Sequential(
                OrderedDict([
                    ('conv1', _ConvBatchNormReLU(3, 64, 7, 2, 3, 1)),
                    ('pool', nn.MaxPool2d(3, 2, 1, ceil_mode=True)),
                ])
            )
        )
        self.add_module('layer2', _ResBlock(n_blocks[0], 64, 64, 256, 1, 1))
        self.add_module('layer3', _ResBlock(n_blocks[1], 256, 128, 512, 2, 1))
        self.add_module('layer4', _ResBlock(n_blocks[2], 512, 256, 1024, 1, 2))
        self.add_module('layer5', _ResBlock(n_blocks[3], 1024, 512, 2048, 1, 4))
        self.add_module('aspp', _ASPPModule(2048, n_classes, pyramids))

    def forward(self, x):
        return super(DeepLabV2, self).forward(x)

    def freeze_bn(self):
        for m in self.modules():
            if isinstance(m, nn.BatchNorm2d):
                m.eval()


class MSC(nn.Module):
    """Multi-Scale Inputs"""

    def __init__(self, model):
        super(MSC, self).__init__()
        self.scale = model

    def forward(self, x):
        output100 = self.scale(x)
        input_size = x.size(2)
        size100 = output100.size(2)
        size075 = int(input_size * 0.75)
        size050 = int(input_size * 0.5)

        self.interp075 = nn.Upsample(size=(size075, ) * 2, mode='bilinear')
        self.interp050 = nn.Upsample(size=(size050, ) * 2, mode='bilinear')
        self.interp100 = nn.Upsample(size=(size100, ) * 2, mode='bilinear')

        output075 = self.scale(self.interp075(x))
        output050 = self.scale(self.interp050(x))

        outputMAX = torch.max(
            torch.stack((
                output100,
                self.interp100(output075),
                self.interp100(output050),
            )), dim=0
        )[0]

        if self.training:
            return [output100, output075, output050, outputMAX]
        else:
            return outputMAX


def DeepLabV2_ResNet101_MSC(n_classes):
    return MSC(DeepLabV2(n_classes=n_classes, n_blocks=[3, 4, 23, 3], pyramids=[6, 12, 18, 24]))


if __name__ == '__main__':
    model = DeepLabV2_ResNet101_MSC(n_classes=21)
    print(list(model.named_children()))
    model.eval()
    image = torch.autograd.Variable(torch.randn(1, 3, 513, 513))
    print(model(image)[0].size())
