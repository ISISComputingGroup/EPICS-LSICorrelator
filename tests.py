import unittest

from correlator_driver_functions import LSiCorrelatorDriver
from pvdb import Records

macros = {"SIMULATE": "1"}
pv_prefix = "TE:NDW1836"
ioc_name = "LSICORR_01"


class LSICorrelatorTests(unittest.TestCase):
    """
    Unit tests for the LSi Correlator
    """

    def setUp(self):
        self.driver = LSiCorrelatorDriver("127.0.0.1", "", "", macros)

        self.mocked_api = self.driver.device
        self.mocked_api.disconnected = False

    def test_GIVEN_device_disconnected_WHEN_data_taken_THEN_deivce_reads_no_data_and_disconnected(self):
        self.assertTrue(self.driver.is_connected)
        self.mocked_api.disconnected = True

        self.driver.take_data()

        self.assertFalse(self.driver.has_data)
        self.assertFalse(self.driver.is_connected)
