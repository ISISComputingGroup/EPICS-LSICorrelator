import unittest

from LSi_Correlator import LSiCorrelatorDriver, serve_forever
from pvdb import Records, STATIC_PV_DATABASE
from pcaspy import SimpleServer

macros = {"SIMULATE": 1}
pv_prefix = "TE:NDW1836"
ioc_name = "LSICORR_01"


class LSICorrelatorTests(unittest.TestCase):
    """
    Unit tests for the LSi Correlator
    """

    def setUp(self):
        self.server_thread, self.driver = serve_forever(ioc_name, pv_prefix, macros)

        self.mocked_api = self.driver.device

        self.addModuleCleanup(self.server_thread.stop)


    def test_GIVEN_device_disconnected_WHEN_data_taken_THEN_connected_is_false_and_PVs_go_into_alarm(self):
        # self.assertEqual(self.driver.read(Records.CONNECTED.name), "YES")
        print(self.driver.read(Records.CONNECTED.name))

        self.mocked_api.disconnected = True

        self.driver.take_data()

        self.assertEqual(self.driver.read(Records.CONNECTED.name), "NO")
