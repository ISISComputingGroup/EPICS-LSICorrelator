from typing import Dict, Optional, Callable
from enum import Enum
from pcaspy.alarm import AlarmStrings, SeverityStrings

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


class Record(object):
    """
    Contains information used to define a PCASpy PV, its fields and how its values are read and set

    Args:
        name: The name of the base PV
        pv_definition: Dict containing the fields specified in the PCASpy database field definition
        has_setpoint: If True, this record will also have a setpoint PV (ending in :SP).
        convert_from_pv: Callable which converts the supplied value (e.g. an enum value) to a value more easily handled.
                         Defaults to do_nothing (no-op)
        convert_to_pv: Callable which converts an internal/easily interpreted value to one that can be written to a pv.
                       Defaults to do_nothing (no-op)
        device_setter: Function which is called when the PV is written do. Defaults to do_nothing (no-op)
    """

    def __init__(self, name: str, pv_definition: Dict,
                 has_setpoint: Optional[bool] = False,
                 convert_from_pv: Optional[Callable] = do_nothing,
                 convert_to_pv: Optional[Callable] = do_nothing,
                 device_setter: Optional[Callable] = null_device_setter):
        self.name = name
        self.pv_definition = pv_definition
        self.convert_from_pv = convert_from_pv
        self.convert_to_pv = convert_to_pv
        self.set_on_device = device_setter
        self.has_setpoint = has_setpoint
        self.database_entries = self.generate_database_entries()

    def generate_database_entries(self) -> Dict:
        """
        Compiles the list of PV definitions for fields required in this record
        """

        database = {}
        database.update({self.name: self.pv_definition})
        database.update(self.add_standard_fields())

        database.update(self.add_val_and_alarm_fields(self.name))

        if self.has_setpoint:
            database.update({"{base_pv}:SP".format(base_pv=self.name): self.pv_definition})
            database.update(self.add_val_and_alarm_fields("{}:SP".format(self.name)))

        return database

    def add_standard_fields(self) -> Dict:
        """ Uses the optionals present in self.pv_definition to add typical fields required for this record """
        new_fields = {}

        if 'count' in self.pv_definition:
            new_fields.update({"{pv}.NORD".format(pv=self.name): {'type': 'int', 'value': 0}})
            new_fields.update({"{pv}.NELM".format(pv=self.name): {'type': 'int', 'value': self.pv_definition['count']}})

        if 'unit' in self.pv_definition:
            new_fields.update({"{pv}.EGU".format(pv=self.name): {'type': 'string', 'value': self.pv_definition['unit']}})

        return new_fields

    def add_val_and_alarm_fields(self, base_pv: str) -> Dict:
        """
        Makes base_pv.VAL, base_pv.SEVR and base_pv.STAT fields

        Args:
            base_pv: The name of the PV to add fields to

        Returns:
            new_fields: Dictionary of new fields and their pv_definitions
        """

        new_fields = {}

        new_fields.update({"{base_pv}.VAL".format(base_pv=base_pv): self.pv_definition})
        new_fields.update({"{base_pv}.SEVR".format(base_pv=base_pv): ALARM_SEVR_PV_FIELDS})
        new_fields.update({"{base_pv}.STAT".format(base_pv=base_pv): ALARM_STAT_PV_FIELDS})

        return new_fields