from enum import Enum
from LSI import LSI_Param
from pvdb import STATIC_PV_DATABASE, Records


class Constants:
    """
    Constants used by the LSICorrelator
    """
    
    DELTA_T = 0.0524288 # Magic number, seems to be time between measurements.
    SLEEP_BETWEEN_MEASUREMENTS = 0.5
    DATA_DIR = r"c:\Data"
    SIMULATE_ARCHIVE_DAT_FILE_NAME = "LSICORR_IOC_test_archive_save.dat"
    SIMULATE_USER_DAT_FILE_NAME = "LSICORR_IOC_test_user_save.dat"


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

class Defaults:
    """
    Default values for the LSICorrelator
    """
    # Set up the PV database
    defaults = {
        Records.CORRELATIONTYPE.value: LSI_Param.CorrelationType.AUTO,
        Records.NORMALIZATION.value: LSI_Param.Normalization.COMPENSATED,
        Records.MEASUREMENTDURATION.value: 10,
        Records.SWAPCHANNELS.value: LSI_Param.SwapChannels.ChA_ChB,
        Records.SAMPLINGTIMEMULTIT.value: LSI_Param.SamplingTimeMultiT.ns200,
        Records.TRANSFERRATE.value: LSI_Param.TransferRate.ms100,
        Records.OVERLOADLIMIT.value: 20,
        Records.OVERLOADINTERVAL.value: 400,
        Records.REPETITIONS.value: 2,
        Records.CURRENT_REPETITION.value: 0,
        Records.CONNECTED.value: None,
        Records.RUNNING.value: False,
        Records.WAITING.value: False,
        Records.WAIT.value: 0,
        Records.WAIT_AT_START.value: False,
        Records.SCATTERING_ANGLE.value: 110,
        Records.SAMPLE_TEMP.value: 298,
        Records.SOLVENT_VISCOSITY.value: 1,
        Records.SOLVENT_REFRACTIVE_INDEX.value: 1.33,
        Records.LASER_WAVELENGTH.value: 642,
        Records.OUTPUTFILE.value: "No data taken yet",
        Records.SIM.value: 0,
        Records.DISABLE.value: 0,
        Records.MIN_TIME_LAG.value: 200
    }

    metadata_records = [
            Records.SCATTERING_ANGLE,
            Records.MEASUREMENTDURATION,
            Records.LASER_WAVELENGTH,
            Records.SOLVENT_REFRACTIVE_INDEX,
            Records.SOLVENT_VISCOSITY,
            Records.SAMPLE_TEMP
        ]

class Schema:
    FILE_SCHEME = """{datetime}
    Pseudo Cross Correlation
    Scattering angle:\t{scattering_angle:.1f}
    Duration (s):\t{duration:d}
    Wavelength (nm):\t{wavelength:.1f}
    Refractive index:\t{refractive_index:.3f}
    Viscosity (mPas):\t{viscosity:.3f}
    Temperature (K):\t{temperature:.1f}
    Laser intensity (mW):\t0.0
    Average Count rate  A (kHz):\t{avg_count_A:.1f}
    Average Count rate  B (kHz):\t{avg_count_B:.1f}
    Intercept:\t1.0000
    Cumulant 1st\t-Inf
    Cumulant 2nd\t-Inf\tNaN
    Cumulant 3rd\t-Inf\tNaN

    Lag time (s)         g2-1
    {correlation_function}
    Count Rate History (KHz)  CR CHA / CR CHB
    {count_rate_history}"""
    