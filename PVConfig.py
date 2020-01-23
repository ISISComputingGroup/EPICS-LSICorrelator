#import sys
#import os
#import traceback
from collections import namedtuple
from enum import Enum
from functools import partial
#
#import six
#
#from pcaspy import SimpleServer, Driver
#from concurrent.futures import ThreadPoolExecutor
#
#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
#sys.path.insert(1, 'C:\\Instrument\\Dev\\LSI-Correlator')
#sys.path.insert(2, 'C:\\Instrument\\Apps\\EPICS\\ISIS\\inst_servers\\master\\')
#
from LSI import LSI_Param
#
from pvdb import STATIC_PV_DATABASE, PvNames
#from BlockServer.core.file_path_manager import FILEPATH_MANAGER
#from server_common.utilities import print_and_log
#from server_common.ioc_data_source import IocDataSource
#from server_common.mysql_abstraction_layer import SQLAbstraction

# SettingPVConfig is a data type to store information about the PVs used to set parameters in the LSi driver.
# convert_from_pv is a function which takes in the raw PV value and returns it in a form which can be accepted by the driver.
# convert_to_pv is a function which takes in the locally held PV value and returns a form which can be sent to the PV.
# set_on_device is the function in the LSICorrelator class which writes the requested setting.
SettingPVConfig = namedtuple("SettingPVConfig", ["convert_from_pv", "convert_to_pv", "set_on_device"])


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

    return [enum for enum in enum_class].index(current_state)


def do_nothing(value):
    """
    No-op for outputs which do not need modifying
    """
    return value


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

        PvNames.OVERLOADLIMIT: SettingPVConfig(convert_from_pv=round, convert_to_pv=do_nothing,
                                               set_on_device=device.setOverloadLimit),

        PvNames.OVERLOADINTERVAL: SettingPVConfig(convert_from_pv=round, convert_to_pv=do_nothing,
                                                  set_on_device=device.setOverloadTimeInterval),

        PvNames.ERRORMSG: SettingPVConfig(convert_from_pv=do_nothing, convert_to_pv=do_nothing, set_on_device=do_nothing)
    }

    for pv in STATIC_PV_DATABASE.keys():
        if pv not in SettingPVs:
            raise AttributeError("No config supplied for PV {}".format(pv))

    return SettingPVs
