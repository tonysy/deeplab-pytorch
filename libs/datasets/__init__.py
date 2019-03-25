from libs.datasets.cocostuff import CocoStuff10k
from libs.datasets.cityscapes import CityScapes

def get_dataset(name):
    return {
        'cocostuff': CocoStuff10k,
        'cityscapes': CityScapes,
    }[name]
