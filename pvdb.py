from __future__ import print_function, unicode_literals, division, absolute_import
import sys
import os
from typing import Dict, List, Optional, Callable
from functools import partial
from enum import Enum
from abc import ABC
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


def populate_enum_pv(enum: Enum):
    """
    Creates an enum PV definition
    """
    return {'type': 'enum', 'enums': [member.name for member in enum]}


def float_pv_with_unit(unit: str):
    """
    Returns a float PV definition with given unit filled in.
    Args:
        unit: The PV's unit
    Returns:
        pv_definition (Dict): Contains the fields which define the PV
    """

    return {'type': 'float', 'unit': unit, 'info_field': {'archive': 'VAL', 'INTEREST': 'HIGH'}}


def convert_pv_enum_to_lsi_enum(enum_class, pv_value):
    """
    Takes the value of the enum from the PV and returns the LSI_Param associated with this value

    Args:
        enum_class (Enum): The LSI_Param Enum containing the device parameters
        pv_value (int): The enumerated value from the PV
    """
    return [enum for enum in enum_class][pv_value]


def convert_lsi_enum_to_pv_value(enum_class, current_state):
    """
    Takes a driver parameter and returns its associated enum value for the PV

    Args:
        enum_class (Enum): The LSI_Param Enum containing the device parameters
        current_state: The Enum member to be looked up and written to the PV
    """
    state_name = enum_class(current_state)
    enum_as_list = [member for member in enum_class]
    return enum_as_list.index(state_name)


def do_nothing(value):
    """
    No-op for outputs which do not need modifying
    """
    return value

class PvDefinition(object):
    """
    Contains information used to define and build PCASpy PVs
    """

    def __init__(self, name: str, pv_definition: Dict,
                 extra_fields: Optional[List] = [],
                 has_setpoint: Optional[bool] = False,
                 convert_from_pv: Optional[Callable] = do_nothing,
                 convert_to_pv: Optional[Callable] = do_nothing,
                 device_setter: Optional[Callable] = do_nothing):
        self.name = name
        self.pv_definition = pv_definition
        self.extra_fields = extra_fields
        self.convert_from_pv = convert_from_pv
        self.convert_to_pv = convert_to_pv
        self.set_on_device = device_setter
        self.database_entries = self.generate_database_entries(has_setpoint)

    def set_device_setter(self, device_setter: Callable):
        """
        Assigns the function which is called when this parameter needs to be set on the device
        """

        self.set_on_device = device_setter

    def generate_database_entries(self, has_setpoint: bool):
        """
        Combines the PV definitions for the base PV and all extra fields needed
        """

        database = {}
        database.update({self.name: self.pv_definition})
        database.update(self.add_standard_fields())
        if has_setpoint:
            database.update({"{base_pv}:SP".format(base_pv=self.name): self.pv_definition})

        for field in self.extra_fields:
            if field.definition is None:
                field_definition = self.pv_definition
            else:
                field_definition = field.definition

            database.update({"{base_pv}.{field}".format(base_pv=self.name, field=field.name): field_definition})

        return database

    def add_standard_fields(self) -> Dict:
        """ Creates PVs to allow fields to be read """
        new_fields = {}

        new_fields.update({"{pv}.VAL".format(pv=self.name): self.pv_definition})
        new_fields.update({"{pv}.SEVR".format(pv=self.name): ALARM_SEVR_PV_FIELDS})
        new_fields.update({"{pv}.STAT".format(pv=self.name): ALARM_STAT_PV_FIELDS})

        if 'count' in self.pv_definition:
            new_fields.update({"{pv}.NORD".format(pv=self.name): {'type': 'int', 'value': 0}})
            new_fields.update({"{pv}.NELM".format(pv=self.name): {'type': 'int', 'value': self.pv_definition['count']}})

        if 'unit' in self.pv_definition:
            new_fields.update({"{pv}.EGU".format(pv=self.name): {'type': 'string', 'value': self.pv_definition['unit']}})

        return new_fields


class Records(Enum):
    CORRELATIONTYPE = PvDefinition("CORRELATIONTYPE",
                                   {'type': 'enum', 'enums': [member.name for member in LSI_Param.CorrelationType]},
                                   convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.CorrelationType),
                                   convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.CorrelationType),
                                   has_setpoint=True
                                   )

    NORMALIZATION = PvDefinition("NORMALIZATION",
                                 {'type': 'enum', 'enums': [member.name for member in LSI_Param.Normalization]},
                                 convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.Normalization),
                                 convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.Normalization),
                                 has_setpoint=True
                                 )

    MEASUREMENTDURATION = PvDefinition("MEASUREMENTDURATION",
                                       INT_AS_FLOAT_PV,
                                       convert_from_pv=round,
                                       convert_to_pv=do_nothing,
                                       has_setpoint=True
                                       )

    SWAPCHANNELS = PvDefinition("SWAPCHANNELS",
                                {'type': 'enum', 'enums': [member.name for member in LSI_Param.SwapChannels]},
                                convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.SwapChannels),
                                convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.SwapChannels),
                                has_setpoint=True
                                )

    SAMPLINGTIMEMULTIT = PvDefinition("SAMPLINGTIMEMULTIT",
                                      {'type': 'enum', 'enums': [member.name for member in LSI_Param.SamplingTimeMultiT]},
                                      convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.SamplingTimeMultiT),
                                      convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.SamplingTimeMultiT),
                                      has_setpoint=True
                                      )

    TRANSFERRATE = PvDefinition("TRANSFERRATE",
                                {'type': 'enum', 'enums': [member.name for member in LSI_Param.TransferRate]},
                                convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.TransferRate),
                                convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.TransferRate),
                                has_setpoint=True
                                )

    OVERLOADLIMIT = PvDefinition("OVERLOADLIMIT",
                                 {'type': 'float', 'prec': 0, 'value': 0.0, 'unit': 'Mcps'},
                                 convert_from_pv=round,
                                 convert_to_pv=do_nothing,
                                 has_setpoint=True
                                 )

    OVERLOADINTERVAL = PvDefinition("OVERLOADINTERVAL",
                                    INT_AS_FLOAT_PV,
                                    convert_from_pv=round,
                                    convert_to_pv=do_nothing,
                                    has_setpoint=True
                                    )

    ERRORMSG = PvDefinition("ERRORMSG",
                            CHAR_PV_FIELDS,
                            convert_from_pv=do_nothing,
                            convert_to_pv=do_nothing
                            )

    FILEPATH = PvDefinition("FILEPATH",
                            CHAR_PV_FIELDS,
                            convert_from_pv=do_nothing,
                            convert_to_pv=do_nothing,
                            has_setpoint=True
                            )

    FILENAME = PvDefinition("FILENAME",
                            CHAR_PV_FIELDS,
                            convert_from_pv=do_nothing,
                            convert_to_pv=do_nothing
                            )

    START = PvDefinition("START",
                         PARAM_FIELDS_BINARY,
                         convert_from_pv=bool,
                         convert_to_pv=do_nothing,
                         has_setpoint=True
                         )

    STOP = PvDefinition("STOP",
                        PARAM_FIELDS_BINARY,
                        convert_from_pv=bool,
                        convert_to_pv=do_nothing,
                        has_setpoint=True
                        )

    CORRELATION_FUNCTION = PvDefinition("CORRELATION_FUNCTION",
                                        {'type': 'float', 'count': 400},
                                        convert_from_pv=do_nothing,
                                        convert_to_pv=do_nothing,
                                        )

    LAGS = PvDefinition("LAGS",
                        {'type': 'float', 'count': 400},
                        convert_from_pv=do_nothing,
                        convert_to_pv=do_nothing,
                        )

    TRACEA = PvDefinition("TRACEA",
                          {'type': 'float', 'count': 400},
                          convert_from_pv=do_nothing,
                          convert_to_pv=do_nothing,
                          )

    TRACEB = PvDefinition("TRACEB",
                          {'type': 'float', 'count': 400},
                          convert_from_pv=do_nothing,
                          convert_to_pv=do_nothing,
                          )

    REPETITIONS = PvDefinition("REPETITIONS",
                               INT_AS_FLOAT_PV,
                               convert_from_pv=round,
                               convert_to_pv=do_nothing,
                               has_setpoint=True
                               )

    CURRENT_REPEAT = PvDefinition("CURRENT_REPETITION",
                                  INT_AS_FLOAT_PV,
                                  convert_from_pv=do_nothing,
                                  convert_to_pv=do_nothing
                                  )

    RUNNING = PvDefinition("RUNNING",
                           PARAM_FIELDS_BINARY,
                           convert_from_pv=bool,
                           convert_to_pv=do_nothing
                           )

    CONNECTED = PvDefinition("CONNECTED",
                             PARAM_FIELDS_BINARY,
                             convert_from_pv=bool,
                             convert_to_pv=do_nothing
                             )

    SCATTERING_ANGLE = PvDefinition("SCATTERING_ANGLE",
                                    float_pv_with_unit("degree"),
                                    convert_from_pv=do_nothing,
                                    convert_to_pv=do_nothing,
                                    has_setpoint=True
                                    )

    SAMPLE_TEMP = PvDefinition("SAMPLE_TEMP",
                               float_pv_with_unit("K"),
                               convert_from_pv=do_nothing,
                               convert_to_pv=do_nothing,
                               has_setpoint=True
                               )

    SOLVENT_VISCOSITY = PvDefinition("SOLVENT_VISCOSITY",
                                     float_pv_with_unit("mPas"),
                                     convert_from_pv=do_nothing,
                                     convert_to_pv=do_nothing,
                                     has_setpoint=True
                                     )

    SOLVENT_REFRACTIVE_INDEX = PvDefinition("SOLVENT_REFRACTIVE_INDEX",
                                            float_pv_with_unit(""),
                                            convert_from_pv=do_nothing,
                                            convert_to_pv=do_nothing,
                                            has_setpoint=True
                                            )

    LASER_WAVELENGTH = PvDefinition("LASER_WAVELENGTH",
                                    float_pv_with_unit("nm"),
                                    convert_from_pv=do_nothing,
                                    convert_to_pv=do_nothing,
                                    has_setpoint=True
                                    )

    SIM = PvDefinition("SIM",
                       {'type': 'enum', 'enums': ["NO", "YES"]},
                       convert_from_pv=bool
                       )

    DISABLE = PvDefinition("DISABLE",
                           {'type': 'enum', 'enums': ["NO", "YES"]},
                           convert_from_pv=bool
                           )

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


def generate_static_pv_database(records):
    for record in records:
        print(record.value.name)


STATIC_PV_DATABASE = {}
for record in Records:
    STATIC_PV_DATABASE.update(record.value.database_entries)

#STATIC_PV_DATABASE.update(add_setpoint_pvs(STATIC_PV_DATABASE))
#FIELDS_DATABASE = add_fields_to_pvs(STATIC_PV_DATABASE)
