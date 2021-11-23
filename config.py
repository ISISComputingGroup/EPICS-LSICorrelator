from enum import Enum


class Constants:
    """
    Constants used by the LSICorrelator
    """
    
    DELTA_T = 0.0524288 # Magic number, seems to be time between measurements.
    SLEEP_BETWEEN_MEASUREMENTS = 0.5
    DATA_DIR = r"c:\Data"

class Macro(Enum):
    
    SIMULATE = {"macro": "SIMULATE"}
    ADDRESS = {"macro": "ADDR"}
    FILEPATH = {"macro": "FILEPATH"}
    FIRMWARE_REVISION = {"macro": "FIRMWARE_REVISION", "default": "4.0.0.3"}

    @property
    def name(self):
        return self.value["macro"]


class PV(Enum):

    # PVs from the DAE to get information about instrument
    RUNNUMBER = "DAE:RUNNUMBER"
    TITLE = "DAE:TITLE"
    INSTNAME = "DAE:INSTNAME"

    def add_prefix(self, prefix):
        return f"{prefix}{self.value}"

class LSiPVSeverity(Enum):

    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"
    INVALID = "INVALID"
