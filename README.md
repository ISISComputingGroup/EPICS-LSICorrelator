# EPICS-LSICorrelator
EPICS PCASpy IOC for the LSi Correlator

Please see relevant recourses listed below :

- [Dev Manual](https://github.com/ISISComputingGroup/ibex_developers_manual/wiki/LSi-Correlator)
- [Support Repository](https://github.com/ISISComputingGroup/EPICS-LSICorrelator)
- [IOC Directory](https://github.com/ISISComputingGroup/EPICS-ioc/tree/master/LSICORR)
- [PCASPy](https://pcaspy.readthedocs.io/en/latest/)
- [LSI Correlator](https://lsinstruments.ch/en/products/lsi-correlator)
- Shared Drive documents: `\\isis\shares\ISIS_Experiment_Controls\Manuals\LSI Correlator`
- LSI Correlator Manual: `\\isis\shares\ISIS_Experiment_Controls\Manuals\LSI Correlator\LSI.Correlator.Manual_v3.2.1`
- UML Class Diagram: `master\design\LSICorrelator.drawio.png`

### Testing
To test, please run `master\tests.py` using the command `python tests.py` from an epics environment (`C:\Instrument\Apps\EPICS\config_env.bat`).


It is also good practice to test the IOC whenever making changes to the support directory using the command `python C:\Instrument\Apps\EPICS\support\EPICS-IOC_Test_Framework\run_tests.py -t lsicorr` from an epics enviroment (`C:\Instrument\Apps\EPICS\config_env.bat`)

