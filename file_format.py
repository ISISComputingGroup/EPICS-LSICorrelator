FILE_SCHEME = """{datetime}
Pseudo Cross Correlation
Scattering angle:\t{scattering_angle:.1f}
Duration (s):\t{duration:d}
Wavelength (nm):\t{wavelength:.1f}
Refractive index:\t{refractive_index:.3f}
Viscosity (mPas):\t{viscosity:.3f}
Temperature (K):\t{temperature:.1f}
Laser intensity (mW):\t0.0
Average Count rate A (kHz):\t{avg_count_A:.1f}
Average Count rate B (kHz):\t{avg_count_B:.1f}
Intercept:\t1.0000
Cumulant 1st\t-Inf
Cumulant 2nd\t-Inf\tNaN
Cumulant 3rd\t-Inf\tNaN

Lag time (s)         g2-1
{correlation_function}

Count Rate History (KHz)  CR CHA / CR CHB
{count_rate_history}"""