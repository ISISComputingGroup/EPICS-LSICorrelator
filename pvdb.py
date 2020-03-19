from __future__ import print_function, unicode_literals, division, absolute_import
import sys
import os
from functools import partial
from enum import Enum

sys.path.insert(1, os.path.join(os.getenv("EPICS_KIT_ROOT"), "Support", "lsicorr_vendor", "master"))
from LSICorrelator import LSICorrelator
from LSI import LSI_Param

from record import (Record, populate_enum_pv, float_pv_with_unit, do_nothing,
                    PARAM_FIELDS_BINARY, INT_AS_FLOAT_PV, CHAR_PV_FIELDS)


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


class Records(Enum):
    @staticmethod
    def keys():
        return [member.name for member in Records]

    CORRELATIONTYPE = Record("CORRELATIONTYPE",
                             populate_enum_pv(LSI_Param.CorrelationType),
                             convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.CorrelationType),
                             convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.CorrelationType),
                             device_setter=LSICorrelator.setCorrelationType,
                             has_setpoint=True
                             )

    NORMALIZATION = Record("NORMALIZATION",
                           populate_enum_pv(LSI_Param.Normalization),
                           convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.Normalization),
                           convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.Normalization),
                           device_setter=LSICorrelator.setNormalization,
                           has_setpoint=True
                           )

    MEASUREMENTDURATION = Record("MEASUREMENTDURATION",
                                 INT_AS_FLOAT_PV,
                                 convert_from_pv=round,
                                 convert_to_pv=do_nothing,
                                 device_setter=LSICorrelator.setMeasurementDuration,
                                 has_setpoint=True
                                 )

    SWAPCHANNELS = Record("SWAPCHANNELS",
                          populate_enum_pv(LSI_Param.SwapChannels),
                          convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.SwapChannels),
                          convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.SwapChannels),
                          device_setter=LSICorrelator.setSwapChannels,
                          has_setpoint=True
                          )

    SAMPLINGTIMEMULTIT = Record("SAMPLINGTIMEMULTIT",
                                populate_enum_pv(LSI_Param.SamplingTimeMultiT),
                                convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.SamplingTimeMultiT),
                                convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.SamplingTimeMultiT),
                                device_setter=LSICorrelator.setSamplingTimeMultiT,
                                has_setpoint=True
                                )

    TRANSFERRATE = Record("TRANSFERRATE",
                          populate_enum_pv(LSI_Param.TransferRate),
                          convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.TransferRate),
                          convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.TransferRate),
                          device_setter=LSICorrelator.setTransferRate,
                          has_setpoint=True
                          )

    OVERLOADLIMIT = Record("OVERLOADLIMIT",
                           {'type': 'float', 'prec': 0, 'value': 0.0, 'unit': 'Mcps'},
                           convert_from_pv=round,
                           convert_to_pv=do_nothing,
                           device_setter=LSICorrelator.setOverloadLimit,
                           has_setpoint=True
                           )

    OVERLOADINTERVAL = Record("OVERLOADINTERVAL",
                              INT_AS_FLOAT_PV,
                              convert_from_pv=round,
                              convert_to_pv=do_nothing,
                              device_setter=LSICorrelator.setOverloadTimeInterval,
                              has_setpoint=True
                              )

    ERRORMSG = Record("ERRORMSG",
                      CHAR_PV_FIELDS,
                      convert_from_pv=do_nothing,
                      convert_to_pv=do_nothing
                      )

    FILEPATH = Record("FILEPATH",
                      CHAR_PV_FIELDS,
                      convert_from_pv=do_nothing,
                      convert_to_pv=do_nothing,
                      has_setpoint=True
                      )

    FILENAME = Record("FILENAME",
                      CHAR_PV_FIELDS,
                      convert_from_pv=do_nothing,
                      convert_to_pv=do_nothing
                      )

    START = Record("START",
                   PARAM_FIELDS_BINARY,
                   convert_from_pv=bool,
                   convert_to_pv=do_nothing,
                   has_setpoint=True
                   )

    STOP = Record("STOP",
                  PARAM_FIELDS_BINARY,
                  convert_from_pv=bool,
                  convert_to_pv=do_nothing,
                  device_setter=stop_device,
                  has_setpoint=True
                  )

    CORRELATION_FUNCTION = Record("CORRELATION_FUNCTION",
                                  {'type': 'float', 'count': 400},
                                  convert_from_pv=do_nothing,
                                  convert_to_pv=do_nothing,
                                  )

    LAGS = Record("LAGS",
                  {'type': 'float', 'count': 400},
                  convert_from_pv=do_nothing,
                  convert_to_pv=do_nothing,
                  )

    TRACEA = Record("TRACEA",
                    {'type': 'float', 'count': 400},
                    convert_from_pv=do_nothing,
                    convert_to_pv=do_nothing,
                    )

    TRACEB = Record("TRACEB",
                    {'type': 'float', 'count': 400},
                    convert_from_pv=do_nothing,
                    convert_to_pv=do_nothing,
                    )

    REPETITIONS = Record("REPETITIONS",
                         INT_AS_FLOAT_PV,
                         convert_from_pv=round,
                         convert_to_pv=do_nothing,
                         has_setpoint=True
                         )

    CURRENT_REPETITION = Record("CURRENT_REPETITION",
                                INT_AS_FLOAT_PV,
                                convert_from_pv=do_nothing,
                                convert_to_pv=do_nothing
                                )

    RUNNING = Record("RUNNING",
                     PARAM_FIELDS_BINARY,
                     convert_from_pv=bool,
                     convert_to_pv=do_nothing
                     )

    CONNECTED = Record("CONNECTED",
                       PARAM_FIELDS_BINARY,
                       convert_from_pv=bool,
                       convert_to_pv=do_nothing
                       )

    SCATTERING_ANGLE = Record("SCATTERING_ANGLE",
                              float_pv_with_unit("degree"),
                              convert_from_pv=do_nothing,
                              convert_to_pv=do_nothing,
                              has_setpoint=True
                              )

    SAMPLE_TEMP = Record("SAMPLE_TEMP",
                         float_pv_with_unit("K"),
                         convert_from_pv=do_nothing,
                         convert_to_pv=do_nothing,
                         has_setpoint=True
                         )

    SOLVENT_VISCOSITY = Record("SOLVENT_VISCOSITY",
                               float_pv_with_unit("mPas"),
                               convert_from_pv=do_nothing,
                               convert_to_pv=do_nothing,
                               has_setpoint=True
                               )

    SOLVENT_REFRACTIVE_INDEX = Record("SOLVENT_REFRACTIVE_INDEX",
                                      float_pv_with_unit(""),
                                      convert_from_pv=do_nothing,
                                      convert_to_pv=do_nothing,
                                      has_setpoint=True
                                      )

    LASER_WAVELENGTH = Record("LASER_WAVELENGTH",
                              float_pv_with_unit("nm"),
                              convert_from_pv=do_nothing,
                              convert_to_pv=do_nothing,
                              has_setpoint=True
                              )

    SIM = Record("SIM",
                 {'type': 'enum', 'enums': ["NO", "YES"]},
                 convert_from_pv=bool
                 )

    DISABLE = Record("DISABLE",
                     {'type': 'enum', 'enums': ["NO", "YES"]},
                     convert_from_pv=bool
                     )


STATIC_PV_DATABASE = {}
for record in Records:
    STATIC_PV_DATABASE.update(record.value.database_entries)
