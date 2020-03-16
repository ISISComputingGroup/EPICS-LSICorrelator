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
from LSICorrelator import LSICorrelator
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


def stop_device(device, _):
    """
    Sends the stop device command
    """
    device.stop()


def null_device_setter(*args, **kwargs):
    """
    Function to call when device has no setter
    """
    pass


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
                 device_setter: Optional[Callable] = null_device_setter):
        self.name = name
        self.pv_definition = pv_definition
        self.extra_fields = extra_fields
        self.convert_from_pv = convert_from_pv
        self.convert_to_pv = convert_to_pv
        self.set_on_device = device_setter
        self.has_setpoint = has_setpoint
        self.database_entries = self.generate_database_entries(has_setpoint)

    def generate_database_entries(self, has_setpoint: bool):
        """
        Combines the PV definitions for the base PV and all extra fields needed
        """

        database = {}
        database.update({self.name: self.pv_definition})
        database.update(self.add_standard_fields())
        if has_setpoint:
            database.update({"{base_pv}:SP".format(base_pv=self.name): self.pv_definition})
            database.update({"{base_pv}:SP.VAL".format(base_pv=self.name): self.pv_definition})
            database.update({"{base_pv}:SP.SEVR".format(base_pv=self.name): ALARM_SEVR_PV_FIELDS})
            database.update({"{base_pv}:SP.STAT".format(base_pv=self.name): ALARM_STAT_PV_FIELDS})

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
    @staticmethod
    def keys():
        return [member.name for member in Records]

    CORRELATIONTYPE = PvDefinition("CORRELATIONTYPE",
                                   populate_enum_pv(LSI_Param.CorrelationType),
                                   convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.CorrelationType),
                                   convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.CorrelationType),
                                   device_setter=LSICorrelator.setCorrelationType,
                                   has_setpoint=True
                                   )

    NORMALIZATION = PvDefinition("NORMALIZATION",
                                 populate_enum_pv(LSI_Param.Normalization),
                                 convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.Normalization),
                                 convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.Normalization),
                                 device_setter=LSICorrelator.setNormalization,
                                 has_setpoint=True
                                 )

    MEASUREMENTDURATION = PvDefinition("MEASUREMENTDURATION",
                                       INT_AS_FLOAT_PV,
                                       convert_from_pv=round,
                                       convert_to_pv=do_nothing,
                                       device_setter=LSICorrelator.setMeasurementDuration,
                                       has_setpoint=True
                                       )

    SWAPCHANNELS = PvDefinition("SWAPCHANNELS",
                                populate_enum_pv(LSI_Param.SwapChannels),
                                convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.SwapChannels),
                                convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.SwapChannels),
                                device_setter=LSICorrelator.setSwapChannels,
                                has_setpoint=True
                                )

    SAMPLINGTIMEMULTIT = PvDefinition("SAMPLINGTIMEMULTIT",
                                      populate_enum_pv(LSI_Param.SamplingTimeMultiT),
                                      convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.SamplingTimeMultiT),
                                      convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.SamplingTimeMultiT),
                                      device_setter=LSICorrelator.setSamplingTimeMultiT,
                                      has_setpoint=True
                                      )

    TRANSFERRATE = PvDefinition("TRANSFERRATE",
                                populate_enum_pv(LSI_Param.TransferRate),
                                convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.TransferRate),
                                convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.TransferRate),
                                device_setter=LSICorrelator.setTransferRate,
                                has_setpoint=True
                                )

    OVERLOADLIMIT = PvDefinition("OVERLOADLIMIT",
                                 {'type': 'float', 'prec': 0, 'value': 0.0, 'unit': 'Mcps'},
                                 convert_from_pv=round,
                                 convert_to_pv=do_nothing,
                                 device_setter=LSICorrelator.setOverloadLimit,
                                 has_setpoint=True
                                 )

    OVERLOADINTERVAL = PvDefinition("OVERLOADINTERVAL",
                                    INT_AS_FLOAT_PV,
                                    convert_from_pv=round,
                                    convert_to_pv=do_nothing,
                                    device_setter=LSICorrelator.setOverloadTimeInterval,
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
                        device_setter=stop_device,
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

    CURRENT_REPETITION = PvDefinition("CURRENT_REPETITION",
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


STATIC_PV_DATABASE = {}
for record in Records:
    STATIC_PV_DATABASE.update(record.value.database_entries)
