from __future__ import print_function, unicode_literals, division, absolute_import
import sys
import os
from typing import Dict
from pcaspy.alarm import AlarmStrings, SeverityStrings

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
# Truncate as enum can only contain 16 states
ALARM_STAT_PV_FIELDS = {'type': 'enum', 'enums': AlarmStrings[:16]}
ALARM_SEVR_PV_FIELDS = {'type': 'enum', 'enums': SeverityStrings}
EGU_FIELD = {'type': 'string'}


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
    FILENAME = "FILENAME"
    TAKEDATA = "TAKEDATA"
    CORRELATION_FUNCTION = "CORRELATION_FUNCTION"
    LAGS = "LAGS"
    TRACEA = "TRACEA"
    TRACEB = "TRACEB"
    REPETITIONS = "REPETITIONS"
    CURRENT_REPEAT = "CURRENT_REPETITION"
    RUNNING = "RUNNING"
    CONNECTED = "CONNECTED"
    SCATTERING_ANGLE = "SCATTERING_ANGLE"
    SAMPLE_TEMP = "SAMPLE_TEMP"
    SOLVENT_VISCOSITY = "SOLVENT_VISCOSITY"
    SOLVENT_REFRACTIVE_INDEX = "SOLVENT_REFRACTIVE_INDEX"
    LASER_WAVELENGTH = "LASER_WAVELENGTH"


STATIC_PV_DATABASE = {
    PvNames.CORRELATIONTYPE: {'type': 'enum', 'enums': [member.name for member in LSI_Param.CorrelationType]},
    PvNames.NORMALIZATION: {'type': 'enum', 'enums': [member.name for member in LSI_Param.Normalization]},
    PvNames.MEASUREMENTDURATION: FLOAT_AS_INT_PV_FIELDS,
    PvNames.SWAPCHANNELS: {'type': 'enum', 'enums': [member.name for member in LSI_Param.SwapChannels]},
    PvNames.SAMPLINGTIMEMULTIT: {'type': 'enum', 'enums': [member.name for member in LSI_Param.SamplingTimeMultiT]},
    PvNames.TRANSFERRATE: {'type': 'enum', 'enums': [member.name for member in LSI_Param.TransferRate]},
    PvNames.OVERLOADLIMIT: {'type': 'float', 'prec': 0, 'value': 0.0, 'unit': 'Mcps'},
    PvNames.OVERLOADINTERVAL: FLOAT_AS_INT_PV_FIELDS,
    PvNames.ERRORMSG: CHAR_PV_FIELDS,
    PvNames.FILEPATH: CHAR_PV_FIELDS,
    PvNames.FILENAME: CHAR_PV_FIELDS,
    PvNames.TAKEDATA: {'type': 'int'},
    PvNames.CORRELATION_FUNCTION: {'type': 'float', 'count': 400},
    PvNames.LAGS: {'type': 'float', 'count': 400},
    PvNames.REPETITIONS: FLOAT_AS_INT_PV_FIELDS,
    PvNames.CURRENT_REPEAT: FLOAT_AS_INT_PV_FIELDS,
    PvNames.CONNECTED: PARAM_FIELDS_BINARY,
    PvNames.RUNNING: PARAM_FIELDS_BINARY,
    PvNames.SCATTERING_ANGLE: {'type': 'float', 'unit': 'degree'},
    PvNames.SAMPLE_TEMP: {'type': 'float', 'unit': 'C'},
    PvNames.SOLVENT_VISCOSITY: {'type': 'float', 'unit': ''},
    PvNames.SOLVENT_REFRACTIVE_INDEX: {'type': 'float', 'unit': 'mPas'},
    PvNames.LASER_WAVELENGTH: {'type': 'float', 'unit': 'nm'}
}

def add_fields_to_pvs(static_pvs: Dict[str, Dict]):
    """ Creates PVs to allow fields to be read """
    field_database = {}
    for pv_name, pv_definition in static_pvs.items():
        field_database.update({"{pv_name}.VAL".format(pv_name=pv_name): pv_definition})
        field_database.update({"{pv_name}.SEVR".format(pv_name=pv_name): ALARM_SEVR_PV_FIELDS})
        field_database.update({"{pv_name}.STAT".format(pv_name=pv_name): ALARM_STAT_PV_FIELDS})

        if 'count' in pv_definition:
            field_database.update({"{pv_name}.NORD".format(pv_name=pv_name): {'type': 'int', 'value': 0}})
            field_database.update({"{pv_name}.NELM".format(pv_name=pv_name): {'type': 'int', 'value': pv_definition['count']}})

        if 'unit' in pv_definition:
            field_database.update({"{PV_name}.EGU".format(PV_name=pv_name): {'type': 'string', 'value': pv_definition['unit']}})

    return field_database

FIELDS_DATABASE = add_fields_to_pvs(STATIC_PV_DATABASE)
