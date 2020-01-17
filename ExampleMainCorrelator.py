import sys
sys.path.append(lsi_path)


import LSI.LSI_Param as pr
from  LSICorrelator import LSICorrelator
import time
import matplotlib.pyplot as plt
#from setPlot import setPlot 
import numpy as np

obj=LSICorrelator(device_ip, device_firmware_version)

#pl_obj=setPlot()

obj.setCorrelationType(pr.CorrelationType.AUTO)
obj.setNormalization(pr.Normalization.COMPENSATED)
obj.setMeasurementDuration(300)
obj.setSwapChannels(pr.SwapChannels.ChA_ChB)
obj.setSamplingTimeMultiT(pr.SamplingTimeMultiT.ns200)
obj.setTransferRate(pr.TransferRate.ms100)
obj.setOverloadLimit(20)
obj.setOverloadTimeInterval(400)

deltat=0.0524288

obj.configure()


for i in range(8):
    print "Measurement "+str(i+1)
    obj.start()

    while obj.MeasurementOn():
    
       time.sleep(0.5)
       obj.update()
       timeTr=np.arange(len(obj.TraceChA))*deltat
       TrA= np.asarray(obj.TraceChA)/(1000*deltat)
       TrB= np.asarray(obj.TraceChB)/(1000*deltat)

       #print TrA
       #print TrB
       
    #plt.plot(timeTr, TrA)
    #plt.plot(timeTr, TrB)
    #plt.title('Raw data')
    #plt.show()
       
    #plt.plot(np.asarray(obj.Correlation))
    #plt.title('Correlated data')
    #plt.show()
    #pl_obj.myplot(timeTr, TrA , TrB, np.asarray(obj.Lags), np.asarray(obj.Correlation), 2)
    
    rmpt = 2# number of point removed from Correlation plot  
    #
    Corr = np.asarray(obj.Correlation)
    Corr = Corr[np.isfinite(Corr)]
    Lags = np.asarray(obj.Lags)
    Lags = Lags[np.isfinite(Corr)]
    #plt.plot(Lags[rmpt:], Corr[rmpt:])
    #plt.semilogx()
    #plt.show()
    
    np.savez(output_filepath, TrA=TrA, TrB=TrB, timeTr=timeTr, Lags=obj.Lags, Corr=obj.Correlation)
    
    #time.sleep(30)



obj.close()