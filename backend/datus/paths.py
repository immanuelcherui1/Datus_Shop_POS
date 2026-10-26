"""Keep immutable installed resources separate from user-owned business data."""
import os
import sys
from pathlib import Path


def resource_root():
    return Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[2]


def data_root():
    override = os.getenv('DATUS_DATA_DIR')
    if override:
        return Path(override).resolve()
    if getattr(sys, 'frozen', False):
        return Path(os.environ['LOCALAPPDATA']) / 'DATUS'
    return resource_root()
