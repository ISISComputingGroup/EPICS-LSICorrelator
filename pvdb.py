from __future__ import print_function, unicode_literals, division, absolute_import
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
from server_common.utilities import char_waveform

sys.path.insert(1, 'C:\\Instrument\\Dev\\LSI-Correlator')
from LSI import LSI_Param


PARAM_FIELDS_BINARY = {'type': 'enum', 'enums': ["NO", "YES"]}
PARAM_IN_MODE = {'type': 'enum', 'enums': ["NO", "YES"]}
PARAM_FIELDS_ACTION = {'type': 'int', 'count': 1, 'value': 0}
OUT_IN_ENUM_TEXT = ["OUT", "IN"]
STANDARD_FLOAT_PV_FIELDS = {'type': 'float', 'prec': 3, 'value': 0.0}
FLOAT_AS_INT_PV_FIELDS = {'type': 'float', 'prec': 0, 'value': 0.0}
CHAR_PV_FIELDS = {'type': 'char', 'count': 400}
#ALARM_STAT_PV_FIELDS = {'type': 'enum', 'enums': AlarmStringsTruncated}
#ALARM_SEVR_PV_FIELDS = {'type': 'enum', 'enums': SeverityStrings}


class PvNames(object):
    CORRELATIONTYPE = "CORRELATIONTYPE"
    NORMALIZATION = "NORMALIZATION"
    MEASUREMENTDURATION = "MEASUREMENTDURATION"
    SWAPCHANNELS = "SWAPCHANNELS"
    SAMPLINGTIMEMULTIT = "SAMPLINGTIMEMULTIT"
    TRANSFERRATE = "TRANSFERRATE"
    OVERLOADLIMIT = "OVERLOADLIMIT"
    OVERLOADINTERVAL = "OVERLOADINTERVAL"
    ERRORMSG = "ERRORMSG"
    FILEPATH = "FILEPATH"
    TAKEDATA = "TAKEDATA"
    CORRELATION_FUNCTION = "CORRELATION_FUNCTION"
    LAGS = "LAGS"
    REPETITIONS = "REPETITIONS"
    CURRENT_REPEAT = "CURRENT_REPETITION"


STATIC_PV_DATABASE = {
    PvNames.CORRELATIONTYPE: {'type': 'enum', 'enums': [member.name for member in LSI_Param.CorrelationType]},
    PvNames.NORMALIZATION: {'type': 'enum', 'enums': [member.name for member in LSI_Param.Normalization]},
    PvNames.MEASUREMENTDURATION: FLOAT_AS_INT_PV_FIELDS,
    PvNames.SWAPCHANNELS: {'type': 'enum', 'enums': [member.name for member in LSI_Param.SwapChannels]},
    PvNames.SAMPLINGTIMEMULTIT: {'type': 'enum', 'enums': [member.name for member in LSI_Param.SamplingTimeMultiT]},
    PvNames.TRANSFERRATE: {'type': 'enum', 'enums': [member.name for member in LSI_Param.TransferRate]},
    PvNames.OVERLOADLIMIT: FLOAT_AS_INT_PV_FIELDS,
    PvNames.OVERLOADINTERVAL: FLOAT_AS_INT_PV_FIELDS,
    PvNames.ERRORMSG: {'type': 'char', 'count': 400},
    PvNames.FILEPATH: {'type': 'char', 'count': 400},
    PvNames.TAKEDATA: {'type': 'int'},
    PvNames.CORRELATION_FUNCTION: {'type': 'float', 'count': 400},
    PvNames.LAGS: {'type': 'float', 'count': 400},
    PvNames.REPETITIONS: FLOAT_AS_INT_PV_FIELDS,
    PvNames.CURRENT_REPEAT: FLOAT_AS_INT_PV_FIELDS
}
