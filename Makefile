install:
	@echo Nothing to be done for lsicorr as pure python

clean:
	-del *.pyc *.pyd *.pyo

.DEFAULT:
	@echo Nothing to be done for lsicorr as pure python

.PHONY:
	runtests

runtests:
	$(PYTHON3) tests.py
