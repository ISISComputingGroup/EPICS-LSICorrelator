from __future__ import print_function, unicode_literals, division, absolute_import
import sys
import os
from typing import Dict
from pcaspy.alarm import AlarmStrings, SeverityStrings

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

sys.path.insert(1, 'C:\\Instrument\\Dev\\LSI-Correlator')
from LSI import LSI_Param

PARAM_FIELDS_BINARY = {'type': 'enum', 'enums': ["NO", "YES"], 'info_field': {'archive': 'VAL', 'INTEREST': 'HIGH'}}
INT_AS_FLOAT_PV = {'type': 'float', 'prec': 0, 'value': 0.0, 'info_field': {'archive': 'VAL', 'INTEREST': 'HIGH'}}
CHAR_PV_FIELDS = {'type': 'char', 'count': 400, 'info_field': {'archive': 'VAL', 'INTEREST': 'HIGH'}}
# Truncate as enum can only contain 16 states
ALARM_STAT_PV_FIELDS = {'type': 'enum', 'enums': AlarmStrings[:16]}
ALARM_SEVR_PV_FIELDS = {'type': 'enum', 'enums': SeverityStrings}


def float_pv_with_unit(unit: str):
    """
    Returns a float PV definition with given unit filled in.
    Args:
        unit: The PV's unit
    Returns:
        pv_definition (Dict): Contains the fields which define the PV
    """

    return {'type': 'float', 'unit': unit, 'info_field': {'archive': 'VAL', 'INTEREST': 'HIGH'}}


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
    START = "START"
    STOP = "STOP"
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
    SIM = "SIM"
    DISABLE = "DISABLE"


STATIC_PV_DATABASE = {
    PvNames.CORRELATIONTYPE: {'type': 'enum', 'enums': [member.name for member in LSI_Param.CorrelationType]},
    PvNames.NORMALIZATION: {'type': 'enum', 'enums': [member.name for member in LSI_Param.Normalization]},
    PvNames.MEASUREMENTDURATION: INT_AS_FLOAT_PV,
    PvNames.SWAPCHANNELS: {'type': 'enum', 'enums': [member.name for member in LSI_Param.SwapChannels]},
    PvNames.SAMPLINGTIMEMULTIT: {'type': 'enum', 'enums': [member.name for member in LSI_Param.SamplingTimeMultiT]},
    PvNames.TRANSFERRATE: {'type': 'enum', 'enums': [member.name for member in LSI_Param.TransferRate]},
    PvNames.OVERLOADLIMIT: {'type': 'float', 'prec': 0, 'value': 0.0, 'unit': 'Mcps'},
    PvNames.OVERLOADINTERVAL: INT_AS_FLOAT_PV,
    PvNames.ERRORMSG: CHAR_PV_FIELDS,
    PvNames.FILEPATH: CHAR_PV_FIELDS,
    PvNames.FILENAME: CHAR_PV_FIELDS,
    PvNames.START: PARAM_FIELDS_BINARY,
    PvNames.STOP: PARAM_FIELDS_BINARY,
    PvNames.CORRELATION_FUNCTION: {'type': 'float', 'count': 400},
    PvNames.LAGS: {'type': 'float', 'count': 400},
    PvNames.REPETITIONS: INT_AS_FLOAT_PV,
    PvNames.CURRENT_REPEAT: INT_AS_FLOAT_PV,
    PvNames.CONNECTED: PARAM_FIELDS_BINARY,
    PvNames.RUNNING: PARAM_FIELDS_BINARY,
    PvNames.SCATTERING_ANGLE: float_pv_with_unit('degree'),
    PvNames.SAMPLE_TEMP: float_pv_with_unit('K'),
    PvNames.SOLVENT_VISCOSITY: float_pv_with_unit('mPas'),
    PvNames.SOLVENT_REFRACTIVE_INDEX: float_pv_with_unit(''),
    PvNames.LASER_WAVELENGTH: float_pv_with_unit('nm'),
    PvNames.SIM: {'type': 'enum', 'enums': ["NO", "YES"]},
    PvNames.DISABLE: {'type': 'enum', 'enums': ["NO", "YES"]}
}


def add_setpoint_pvs(static_pvs: Dict[str, Dict]):
    """ Adds :SP PV for each record in the given dict """
    setpoints_database = {}
    for pv_name, pv_definition in static_pvs.items():
        setpoints_database.update({"{pv_name}:SP".format(pv_name=pv_name): pv_definition})

    return setpoints_database


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


STATIC_PV_DATABASE.update(add_setpoint_pvs(STATIC_PV_DATABASE))
FIELDS_DATABASE = add_fields_to_pvs(STATIC_PV_DATABASE)
