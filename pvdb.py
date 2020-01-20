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
#ALARM_STAT_PV_FIELDS = {'type': 'enum', 'enums': AlarmStringsTruncated}
#ALARM_SEVR_PV_FIELDS = {'type': 'enum', 'enums': SeverityStrings}


class SettingsPvNames(object):
    CORRELATIONTYPE = "CORRELATIONTYPE"
    NORMALIZATION = "NORMALIZATION"
    MEASUREMENTDURATION = "MEASUREMENTDURATION"
    SWAPCHANNELS = "SWAPCHANNELS"
    SAMPLINGTIMEMULTIT = "SAMPLINGTIMEMULTIT"
    TRANSFERRATE = "TRANSFERRATE"
    OVERLOADLIMIT = "OVERLOADLIMIT"
    OVERLOADTIMEINTERVAL = "OVERLOADINTERVAL"


STATIC_PV_DATABASE = {
    SettingsPvNames.CORRELATIONTYPE: {'type': 'enum', 'enums': [member.name for member in LSI_Param.CorrelationType]},
    SettingsPvNames.NORMALIZATION: {'type': 'enum', 'enums': [member.name for member in LSI_Param.Normalization]},
    SettingsPvNames.MEASUREMENTDURATION: STANDARD_FLOAT_PV_FIELDS,
    SettingsPvNames.SWAPCHANNELS: {'type': 'enum', 'enums': [member.name for member in LSI_Param.SwapChannels]},
    SettingsPvNames.SAMPLINGTIMEMULTIT: {'type': 'enum', 'enums': [member.name for member in LSI_Param.SamplingTimeMultiT]},
    SettingsPvNames.TRANSFERRATE: {'type': 'enum', 'enums': [member.name for member in LSI_Param.TransferRate]},
    SettingsPvNames.OVERLOADLIMIT: {'type': 'int'},
    SettingsPvNames.OVERLOADTIMEINTERVAL: {'type': 'int'}
}
