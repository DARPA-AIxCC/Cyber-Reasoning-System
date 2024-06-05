from abc import ABC, abstractmethod

import numpy as np
from scipy.spatial import distance


class DistanceMetric(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def compute(self, x: np.ndarray, y: np.ndarray):
        raise NotImplementedError


class L2Distance(DistanceMetric):
    def __init__(self):
        super().__init__()

    @staticmethod
    def compute(x, y):
        """
        Compute L2 distance between two numpy array.
        """
        return np.linalg.norm(x - y)

    def __repr__(self):
        return "L2Distance"


class CosineDistance(DistanceMetric):
    def __init__(self):
        super().__init__()

    @staticmethod
    def compute(x, y):
        """
        Compute Cosine distance between two numpy array.
        """
        return distance.cosine(x, y)

    def __repr__(self):
        return "CosineDistance"
