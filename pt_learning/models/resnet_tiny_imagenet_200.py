import torch.nn as nn
import torch
import math
import torch.utils.model_zoo as model_zoo
from torch.autograd import Variable
from PIL import Image
import matplotlib.pyplot as plt
import torchvision
import torch.nn.functional as F
import os
import numpy as np

#定义一个3×3的卷积层，后面多次调用，方便使用，尺寸不变，plane是深度的意思
def conv3x3(in_planes, out_planes, stride=1):
    "3x3 convolution with padding"
    return nn.Conv2d(in_channels=in_planes, out_channels=out_planes, kernel_size=3, stride=stride,
                     padding=1, bias=False)

#BasicBlock是基本的Resnet结构，搭建18层和34层的Resnet，输入深度和输出深度不变
class BasicBlock(nn.Module):
    #输出深度/输入深度
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super(BasicBlock, self).__init__()
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = nn.BatchNorm2d(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = nn.BatchNorm2d(planes)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        #保存x，后面用于融合
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        #当输入深度不等于输出深度，定义downsample为内核为1的卷积层加上正则层，扩大residual使之匹配x的大小
        if self.downsample is not None:
            residual = self.downsample(x)

        out += residual
        out = self.relu(out)

        return out


class Bottleneck(nn.Module):
    # 输出深度/输入深度,每次调用这个，深度增长4倍
    expansion = 4

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super(Bottleneck, self).__init__()
        self.conv1 = nn.Conv2d(inplanes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride,
                               padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        #深度增长4倍，源码self.expansion直接写了4，改了这个，就可以自己调整了
        self.conv3 = nn.Conv2d(planes, planes * self.expansion, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(planes * self.expansion)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out += residual
        out = self.relu(out)

        return out


#定义整个网络
class ResNet(nn.Module):
    #block就是你要调用的基本单元BasicBlock/Bottleneck
    #layer is [,,,]，其中的元素就是4次构建基本模块的时候分别调用几次
    def __init__(self, block, layers, image_size, num_classes=1000):
        self.inplanes = 64
        super(ResNet, self).__init__()
        #[,3,image_size,image_size]->[,64,image_size/2,image_size/2]
        self.conv1 = nn.Conv2d(in_channels=3, out_channels=64, kernel_size=7, stride=2, padding=3,
                               bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        #[,64,image_size/2,image_size/2]->[,64,image_size/4,image_size/4]
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        ## _make_layer就是利用基本单元BasicBlock/Bottleneck构建网络
        self.layer1 = self._make_layer(block, 64, layers[0])
        # [,64,image_size/4,image_size/4]->[,128,image_size/8,image_size/8]
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        # [,128,image_size/8,image_size/8]->[,256,image_size/16,image_size/16]
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2)
        # [,256,image_size/16,image_size/16]->[,512,image_size/32,image_size/32]
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2)
        #平均池化层
        # [,512,image_size/32,image_size/32]->[,512,image_size/224,image_size/224]
        self.avgpool = nn.AvgPool2d(7, stride=1)
        # [, 512, image_size / 224, image_size / 224]->[,1000]
        self.fc = nn.Linear(512 * block.expansion, num_classes)

        #遍历神经网络，初始化参数
        for m in self.modules():
            #如果遇到nn.Conv2d，则正则化
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
            #如果遇到nn.BatchNorm2d，将其weight填充1,bias清零
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        #如果卷积层需要扩大block.expansion倍或者stride=2，则定义downsample为内核为1的卷积层加上正则层
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(
                    in_channels=self.inplanes,
                    out_channels=planes * block.expansion,
                    kernel_size=1,
                    stride=stride,
                    bias=False),
                nn.BatchNorm2d(planes * block.expansion),
            )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes))
        #nn.Sequential可以用layers list构建，简单方便
        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        #
        x = self.avgpool(x)
        #平铺x
        x = x.view(x.size(0), -1)
        x = self.fc(x)

        return x


def load_training_images(image_dir, batch_size=500):
    image_index = 0

    images = np.ndarray(shape=(NUM_IMAGES, IMAGE_ARR_SIZE))
    names = []
    labels = []

    print("Loading training images from ", image_dir)
    # Loop through all the types directories
    for type in os.listdir(image_dir):
        if os.path.isdir(image_dir + type + '/images/'):
            type_images = os.listdir(image_dir + type + '/images/')
            # Loop through all the images of a type directory
            batch_index = 0;
            # print ("Loading Class ", type)
            for image in type_images:
                image_file = os.path.join(image_dir, type + '/images/', image)

                # reading the images as they are; no normalization, no color editing
                image_data = mpimg.imread(image_file)
                # print ('Loaded Image', image_file, image_data.shape)
                if (image_data.shape == (IMAGE_SIZE, IMAGE_SIZE, NUM_CHANNELS)):
                    images[image_index, :] = image_data.flatten()

                    labels.append(type)
                    names.append(image)

                    image_index += 1
                    batch_index += 1
                if (batch_index >= batch_size):
                    break;

    print("Loaded Training Images", image_index)
    return (images, np.asarray(labels), np.asarray(names))

BATCH_SIZE = 20
NUM_CLASSES = 200
NUM_IMAGES_PER_CLASS = 500
NUM_IMAGES = NUM_CLASSES * NUM_IMAGES_PER_CLASS
TRAINING_IMAGES_DIR = '/home/gong/tiny-imagenet-200/train/'
TRAIN_SIZE = NUM_IMAGES

NUM_VAL_IMAGES = 9832
VAL_IMAGES_DIR = '/home/gong/tiny-imagenet-200/val/'
IMAGE_SIZE = 64
NUM_CHANNELS = 3
IMAGE_ARR_SIZE = IMAGE_SIZE * IMAGE_SIZE * NUM_CHANNELS

#load the image dir
# DATA_DIR, IMAGE_DIRECTORY, TRAINING_IMAGES_DIR, VAL_IMAGES_DIR = get_directories()
# print(DATA_DIR, IMAGE_DIRECTORY, TRAINING_IMAGES_DIR, VAL_IMAGES_DIR)