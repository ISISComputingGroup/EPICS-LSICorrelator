from enum import Enum


class Config:
    SIMULATE_MACRO = "SIMULATE"
    ADDRESS_MACRO = "ADDR"
    FILEPATH_MACRO = "FILEPATH"
    FIRMWARE_REVISION_MACRO = "FIRMWARE_REVISION"
    FIRMWARE_REVISION_DEFAULT = "4.0.0.3"
    DELTA_T = 0.0524288 # Magic number, seems to be time between measurements.
    SLEEP_BETWEEN_MEASUREMENTS = 0.5
    DATA_DIR = r"c:\Data"

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
