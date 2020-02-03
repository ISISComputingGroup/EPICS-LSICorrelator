from collections import namedtuple
from functools import partial
import os

from genie_python import genie as g
from LSI import LSI_Param
from pvdb import STATIC_PV_DATABASE, PvNames

g.set_instrument(None)


def get_default_filename():
    """ Returns a default filename from the current run number and title """
    return "{run_number}_{title}".format(run_number=g.get_runnumber(), title=g.get_title())


def check_filename_valid(filename):
    """ Removes non-ascii and other characters which prevent using the supplied filename """
    if filename == "":
        filename = get_default_filename()

    # Remove anything other than alphanumerics and dashes/underscores
    parsed_filename = [char for char in filename if char.isalnum() or char in '-_']
    return ''.join(parsed_filename)


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
    """ Calls the stop procedure on the device"""
    device.stop()


def do_nothing(value):
    """
    No-op for outputs which do not need modifying
    """
    return value


# SettingPVConfig is a data type to store information about the PVs used to set parameters in the LSi driver.
# convert_from_pv is a function which takes in the raw PV value and returns it in a form which can be accepted by the driver.
# convert_to_pv is a function which takes in the locally held PV value and returns a form which can be sent to the PV.
# set_on_device is the function in the LSICorrelator class which writes the requested setting.
SettingPVConfig = namedtuple("SettingPVConfig", ["convert_from_pv", "convert_to_pv", "set_on_device"])


# A 'BasicPV' does not require any conversions/treatments when reading or writing to the PV.
# The data is only held in this driver not in LSI code, so does not require a device setter.
BasicPVConfig = SettingPVConfig(convert_from_pv=do_nothing,
                                convert_to_pv=do_nothing,
                                set_on_device=do_nothing)


BoolPVConfig = SettingPVConfig(convert_from_pv=bool,
                               convert_to_pv=int,
                               set_on_device=do_nothing)


def get_pv_configs(device):
    """
    Returns a dictionary of PVConfigs which define how the data is handled when PVs get or set

    Args:
        device (LSICorrelator): Instance of LSICorrelator which is used to set/get parameters on the device
    """

    SettingPVs = {
        PvNames.CORRELATIONTYPE: SettingPVConfig(convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.CorrelationType),
                                                 convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.CorrelationType),
                                                 set_on_device=device.setCorrelationType),

        PvNames.NORMALIZATION: SettingPVConfig(convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.Normalization),
                                               convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.Normalization),
                                               set_on_device=device.setNormalization),

        PvNames.MEASUREMENTDURATION: SettingPVConfig(convert_from_pv=round, convert_to_pv=do_nothing,
                                                     set_on_device=device.setMeasurementDuration),

        PvNames.SWAPCHANNELS: SettingPVConfig(convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.SwapChannels),
                                              convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.SwapChannels),
                                              set_on_device=device.setSwapChannels),

        PvNames.SAMPLINGTIMEMULTIT: SettingPVConfig(convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.SamplingTimeMultiT),
                                                    convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.SamplingTimeMultiT),
                                                    set_on_device=device.setSamplingTimeMultiT),

        PvNames.TRANSFERRATE: SettingPVConfig(convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.TransferRate),
                                              convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.TransferRate),
                                              set_on_device=device.setTransferRate),

        PvNames.OVERLOADLIMIT: SettingPVConfig(convert_from_pv=round,
                                               convert_to_pv=do_nothing,
                                               set_on_device=device.setOverloadLimit),

        PvNames.OVERLOADINTERVAL: SettingPVConfig(convert_from_pv=round,
                                                  convert_to_pv=do_nothing,
                                                  set_on_device=device.setOverloadTimeInterval),

        PvNames.ERRORMSG: BasicPVConfig,

        PvNames.FILENAME: SettingPVConfig(convert_from_pv=check_filename_valid,
                                          convert_to_pv=check_filename_valid,
                                          set_on_device=do_nothing),

        PvNames.FILEPATH: SettingPVConfig(convert_from_pv=do_nothing,
                                          convert_to_pv=do_nothing,
                                          set_on_device=do_nothing),

        PvNames.START: BoolPVConfig,
        PvNames.STOP: SettingPVConfig(convert_from_pv=do_nothing,
                                      convert_to_pv=do_nothing,
                                      set_on_device=partial(stop_device, device)),
        PvNames.CORRELATION_FUNCTION: BasicPVConfig,
        PvNames.LAGS: BasicPVConfig,
        PvNames.REPETITIONS: BasicPVConfig,
        PvNames.CURRENT_REPEAT: BasicPVConfig,
        PvNames.CONNECTED: BoolPVConfig,
        PvNames.RUNNING: BoolPVConfig,
        PvNames.SCATTERING_ANGLE: BasicPVConfig,
        PvNames.SAMPLE_TEMP: BasicPVConfig,
        PvNames.SOLVENT_VISCOSITY: BasicPVConfig,
        PvNames.SOLVENT_REFRACTIVE_INDEX: BasicPVConfig,
        PvNames.LASER_WAVELENGTH: BasicPVConfig,
        PvNames.SIM: BoolPVConfig,
        PvNames.DISABLE: BoolPVConfig
    }

    for pv in STATIC_PV_DATABASE.keys():
        # Ignore PV fields and set points
        if not pv.endswith(":SP") and pv not in SettingPVs:
            raise AttributeError("No config supplied for PV {}".format(pv))

    return SettingPVs
