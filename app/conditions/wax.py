"""Map temperature in Fahrenheit to a glide-wax recommendation band."""
from __future__ import annotations
from enum import Enum


class WaxBand(Enum):
    GREEN = ('green', 'Green wax · cold snow')
    BLUE = ('blue', 'Blue wax · firm snow')
    PURPLE = ('purple', 'Purple · transition snow')
    RED = ('red', 'Red wax · klister conditions')

    @property
    def label(self) -> str:
        return self.value[1]

    @property
    def slug(self) -> str:
        return self.value[0]


def recommend_wax(temp_f: float) -> WaxBand:
    if temp_f < 14:
        return WaxBand.GREEN
    if temp_f < 28:
        return WaxBand.BLUE
    if temp_f < 32:
        return WaxBand.PURPLE
    return WaxBand.RED
