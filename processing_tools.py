import numpy as np
import pandas as pd
import os
import glob
import logging
import json
import typhon
import random
import pickle
import analysis_tools as atools
from time import sleep
from scipy.interpolate import interp1d
from netCDF4 import Dataset
import matplotlib.pyplot as plt
from moisture_space import utils

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)


def config():
    """ Reads specifications for processing from confing.json and returns a dictionary
    with specifications.
    """
    with open('/mnt/lustre02/work/um0878/users/tlang/work/dyamond/processing/config.json') as handle:
        config = json.loads(handle.read())
    
    return config

def preprocess(model, infile, tempfile, outfile, option_1, option_2, numthreads, **kwargs):
    """ Performs preprocessing steps (before horizontal interpolation). This function just 
    calls the model-specific function for preprocessing.
    
    Parameters:
        model (str): Name of model
        infile (str): Path to input file
        tempfile (str): Path to temporary output file
        outfile (str): Path to output file
        option_1 (str), option_2 (str): options for preprocessing
        numthreads (int): Number of OpenMP threads for cdo
    """
    
    if model == 'IFS':
        preprocess_IFS(infile, tempfile, outfile, option_1, option_2, numthreads)
    elif model == 'MPAS':
        preprocess_MPAS(infile, tempfile, outfile, option_1, numthreads)
    elif model == 'ERA5':
        preprocess_ERA5(infile, outfile, option_1, option_2, numthreads)
        
    
def preprocess_IFS(infile, tempfile, outfile, option_selvar, option_nzlevs, numthreads, **kwargs):
    """ Perform processing steps required before horizontal interpolation for the IFS model.
    
    Parameters:
        infile (str): Name of input file
        tempfile (str): Name for temporary files
        outfile (str): Name for preprocessed output file
        option_selvar (str): Name of variable to select from input file
        option_nzlevs (str): Number of vertical levels
        numthreads (int): Number of OpenMP threads for cdo
    """
    logger.info('Preprocessing IFS...')
    filename, file_extension = os.path.splitext(tempfile)
    tempfile_1 = tempfile
    tempfile_2 = filename+'_2'+file_extension
    #tempfile_3 = filename+'_3'+file_extension
    
    # for OLR and IWV less pre-processing steps are needed than for the other variables
    if option_nzlevs == '':
        cmd_1 = f'cdo --eccodes select,name={option_selvar} {infile} {tempfile_1}'
        #cmd_2 = f'grib_set -s editionNumber=1 {tempfile_1} {tempfile_2}'
        #cmd_3 = f'rm {tempfile_1}'
        cmd_2 = f'cdo -P {numthreads} -R -f nc4 copy {tempfile_1} {outfile}'
        cmd_3 = f'rm {tempfile_1}'
        
        logger.info(cmd_1)
        os.system(cmd_1)
        logger.info(cmd_2)
        os.system(cmd_2)
        logger.info(cmd_3)
        os.system(cmd_3)
        
    else:
        cmd_1 = f'cdo --eccodes select,name={option_selvar} {infile} {tempfile_1}'
        cmd_2 = f'grib_set -s numberOfVerticalCoordinateValues={option_nzlevs} {tempfile_1} {tempfile_2}'
        cmd_3 = f'rm {tempfile_1}'
        #cmd_4 = f'grib_set -s editionNumber=1 {tempfile_2} {tempfile_3}'
        #cmd_5 = f'rm {tempfile_2}'
        #cmd_6 = f'cdo -P {numthreads} -R -f nc4 copy {tempfile_3} {outfile}'
        cmd_4 = f'cdo -P {numthreads} -f nc4 -setgridtype,regular {tempfile_2} {outfile}'
        cmd_5 = f'rm {tempfile_2}'

        logger.info(cmd_1)
        os.system(cmd_1)
        logger.info(cmd_2)
        os.system(cmd_2)
        logger.info(cmd_3)
        os.system(cmd_3)
        logger.info(cmd_4)
        os.system(cmd_4)
        logger.info(cmd_5)
        os.system(cmd_5)


def preprocess_MPAS(infile, tempfile, outfile, option_selvar, numthreads, **kwargs):
    """ Perform processing steps required before horizontal interpolation for the MPAS model.
    
    Parameters:
        infile (str): Name of input file
        tempfile (str): Name for temporary files
        outfile (str): Name for preprocessed output file
        numthreads (int): Number of OpenMP threads for cdo
    """
    logger.info('Preprocessing MPAS...')
    gridfile = '/work/ka1081/DYAMOND/PostProc/GridsAndWeights/MPAS-3.75km_gridinfo.nc'
    cmd_1 = f'cdo -P 4 setattribute,*@axis="txz" -selname,{option_selvar} {infile} {tempfile}'
    cmd_2 = f'cdo -P 4 setgrid,mpas:{gridfile} {tempfile} {outfile}'
    cmd_3 = f'rm {tempfile}'
    
    logger.info(cmd_1)
    os.system(cmd_1)
    logger.info(cmd_2)
    os.system(cmd_2)
    logger.info(cmd_3)
    os.system(cmd_3)
    
def preprocess_ERA5(infile, outfile, option_grid, option_splitday, numthreads, **kwargs):
    """ Perform processing steps required before horizontal interpolation for the ERA5 reanalysis.
    """
    logger.info('Preprocessing ERA5...')
    
    if option_grid == 'gaussian':
        # Change file format from GRIB2 to NetCDF4
        # -R option: Change from Gaussian reduced to regular Gaussian grid
        cmd = f'cdo -P {numthreads} -f nc4 -{option_splitday} -setgridtype,regular {infile} {outfile}'
    elif option_grid == 'spectral':
        # Some variables (e.g. temperature, vertical velocity) are given on a spectral grid,
        # which has to be transformed to a regular Gaussian grid first.
        cmd = f'cdo -P {numthreads} -f nc4 sp2gp,linear {infile} {outfile}' 
     
    logger.info(cmd)
    os.system(cmd)
    
def preprocess_ARPEGE_1(preprocess_dir, infile_2D, infile_3D, outfileprefix, merge_list_3D, tempfile_list_3D,\
                        filelist_2D, tempfile_list_2D, variables, **kwargs):
    """ Preprocessing of ARPEGE raw data (steps needed before horizontal interpolation).
    
    Parameters: 
        preprocess_dir (str): full path to directory where preprocessing is performed 
            (gribsplit can only write output into the directory where it runs)
        infile_2D (str): full path to file containing ARPEGE 2D raw data for one time step
        infile_3D (str): full path to file containing ARPEGE 3D raw data for one time step
        outfileprefix (str): prefix for temporary files (should contain date and time)
        merge_list_3D (list of list of str): lists of filenames of 3D variables produced by gribsplit,
            that have to be merged (containing data for individual model levels), 
            one list for each variable
        tempfile_list_3D (list of str): names for files containing merged 3D variables 
            (one name for every variable)
        filelist_2D (list of str): list of filenames of 2D variables produced by gribsplit
        tempfile_list_2D (list of str): list of filenames of 2D variables (files produced by
            gribsplit are renamed)
    """
    variables_3D = ['GH', 'TEMP', 'QV', 'QI', 'QC', 'W']
    variables_2D = ['SURF_PRES', 'OLR', 'STOA']
    
    # split file containing 3D variables
    if merge_list_3D:
        cmd_1 = f'{preprocess_dir}/mygribsplit {infile_3D} {outfileprefix}'
        logger.info(cmd_1)
        os.system(cmd_1)
    
    # split file containing 2D variables
    if filelist_2D:
        cmd_2 = f'{preprocess_dir}/mygribsplit {infile_2D} {outfileprefix}'
        logger.info(cmd_2)
        os.system(cmd_2)
     
    i = 0 # index for 3D variables
    j = 0 # index for 2D variables
    for var in variables:
        # merge individual model levels for each 3D variable
        if var in variables_3D:
            mergelist_str = ' '.join(merge_list_3D[i])
            cmd_3 = f'cdo merge {mergelist_str} {tempfile_list_3D[i]}'
            i += 1
        
        # rename files containing 2D variables
        elif var in variables_2D:
            cmd_3 = f'mv {filelist_2D[j]} {tempfile_list_2D[j]}'
            j += 1
            
        logger.info(cmd_3)
        os.system(cmd_3)
    
    # remove files that are not needed
    cmd_4 = f'rm {outfileprefix}.t*.l*.grb.*'
    logger.info(cmd_4)
    os.system(cmd_4)
    
def interpolate_horizontally(infile, target_grid, weights, outfile, options, numthreads,
                             lonlatbox=[-180, 180, -30, 30], **kwargs):
    """ Horizontal Interpolation to another target grid with the CDO command remap 
    that uses pre-calculated interpolation weights. The selection of a lon-lat box is 
    performed at the same time.
    
    Parameters:
        infile (str): path to file with input 2D or 3D field
        target_grid (str): path to file with target grid information
        weights (str): path to file with pre-calculated interpolation weights
        outfile (str): output file (full path)
        numthreads (int): number of OpenMP threads for cdo 
        lonlatbox (list of num): boundaries of lon-lat box to select 
            [lonmin, lonmax, latmin, latmax]
    """
    lon1 = lonlatbox[0]
    lon2 = lonlatbox[1]
    lat1 = lonlatbox[2]
    lat2 = lonlatbox[3]
    
    filename, file_extension = os.path.splitext(infile)
    if file_extension == '.nc' or file_extension == '.nc4':
        to_netCDF = ''
    else:
        to_netCDF = '-f nc4'
    
    if options != '':
        options += ' '
        
    cmd = f'cdo --verbose -O {to_netCDF} -P {numthreads} sellonlatbox,{lon1},{lon2},{lat1},{lat2} -remap,{target_grid},{weights} {options}{infile} {outfile}'
    logger.info(cmd)
    os.system(cmd)
    
def calc_relative_humidity(temp_file, qv_file, pres_file, timestep, model, run, time_period, temp_dir, **kwargs):
    """ Calculate relative humidity from temperature, specific humidity and pressure.
    Note: Only one timestep is selected from input files, output files contain one time step per file and have to be
    merged afterwards. 
    
    Parameters:
        temp_file (str): File containing temperature (all timesteps)
        qv_file (str): File containing specific humidity (all timesteps)
        pres_file (str): File containing pressure (all timesteps)
        timestep (int): Time step to select
        model (str): Name of model
        run (str): Name of model run
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        temp_dir (str): Directory for output files
    """
    time = pd.date_range(time_period[0], time_period[1]+'-21', freq='3h')
    if model == 'ARPEGE':
        exclude_times = list(pd.date_range("2016-08-11 00:00:00", "2016-08-12 00:00:00", freq='3h'))
        exclude_times.append(pd.to_datetime('2016-08-10 00:00:00'))
        exclude_times.append(pd.to_datetime('2016-08-10 15:00:00'))
        time = [t for t in time if t not in exclude_times]
    # variable names
    temp_name = 'TEMP'
    qv_name = 'QV'
    if model == 'SAM':
        pres_name = 'PP'
    else:
        pres_name = 'PRES'
    
    # Read variables from files
    logger.info('Read variables from files')
    # temperature
    with Dataset(temp_file) as ds:
        temp = ds.variables[temp_name][timestep].filled(np.nan)
        lat = ds.variables['lat'][:].filled(np.nan)
        lon = ds.variables['lon'][:].filled(np.nan)
    
    # pressure (for SAM mean pressure and perturbation)
    with Dataset(pres_file) as ds:
        if model == 'SAM':
            pres_pert = ds.variables[pres_name][timestep].filled(np.nan)
            pres_mean = ds.variables['p'][:].filled(np.nan)
        else:
            pres = ds.variables[pres_name][timestep].filled(np.nan)
            
    # Specific humidity        
    with Dataset(qv_file) as ds:
        qv = ds.variables[qv_name][timestep].filled(np.nan)
    
    # for SAM, pressure has to be calculated from mean pressure and pressure perturbation
    if model == 'SAM':
        qv = qv * 1e-3
        pres = np.zeros(pres_pert.shape)
        for i in range(pres_pert.shape[1]):
            for j in range(pres_pert.shape[2]):
                pres[:, i, j] = pres_mean * 1e2 + pres_pert[:, i, j]
    
    # Calculate RH
    logger.info('Calc VMR')
    vmr = typhon.physics.specific_humidity2vmr(qv)
    logger.info('Calc e_eq')
    e_eq = typhon.physics.e_eq_mixed_mk(temp)
    logger.info('Calc RH')
    rh = vmr * pres / e_eq
    rh = np.expand_dims(rh, axis=0)
    if model == 'MPAS':
        rh = rh.transpose(0, 3, 1, 2)
    
    # Save RH to file 
    logger.info('Save RH to file')
    height = np.arange(rh.shape[1])
    date_str = time[timestep].strftime('%m%d')
    hour_str = time[timestep].strftime('%H')
    outname = f'{model}-{run}_RH_{date_str}_{hour_str}_hinterp.nc'
    outname = os.path.join(temp_dir, outname)
    latlonheightfield_to_netCDF(height, lat, lon, rh, 'RH', '[]', outname, time_dim=True, time_var=timestep*3, overwrite=True)

def calc_vertical_velocity(omega_file, temp_file, qv_file, pres_file, heightfile, timestep, model, run, time_period, temp_dir, **kwargs):
    """ Calculate vertical velocity w from pressure velocity omega (requires temperature, specific humidity and pressure).
    Note: Only one timestep is selected from input files, output files contain one time step per file and have to be
    merged afterwards. 
    
    Needed for ERA5 only 
    
    Parameters:
        omega_file (str): File containing pressure velocity omega (all timesteps)
        temp_file (str): File containing temperature (all timesteps)
        qv_file (str): File containing specific humidity (all timesteps)
        pres_file (str): File containing pressure (all timesteps)
        timestep (int): Time step to select
        model (str): Name of model
        run (str): Name of model run
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        temp_dir (str): Directory for output files
    """
    time = pd.date_range(time_period[0], time_period[1]+'-21', freq='3h')
    # read variables   
    logger.info('Read variables from files')
    # temperature
    with Dataset(temp_file) as ds:
        temp = ds.variables['TEMP'][timestep].filled(np.nan)
        lat = ds.variables['lat'][:].filled(np.nan)
        lon = ds.variables['lon'][:].filled(np.nan)
    # omega
    with Dataset(omega_file) as ds:
        omega = ds.variables['OMEGA'][timestep].filled(np.nan)
    # pressure    
    with Dataset(pres_file) as ds:
        pres = ds.variables['PRES'][timestep].filled(np.nan)
    # specific humidity        
    with Dataset(qv_file) as ds:
        qv = ds.variables['QV'][timestep].filled(np.nan)
    
    # calculate vertical velocity
    logger.info('Calculate vertical velocity')
    g = typhon.constants.g
    # mixing ratio
    r = typhon.physics.specific_humidity2mixing_ratio(qv) 
    # virtual temperature
    virt_temp = temp * (1 + 0.61 * r) 
    # air density (from virtual temperature)
    rho = typhon.physics.density(pres, virt_temp)
    # vertical velocity
    w = -omega / rho / g
    
    # save to file
    logger.info('Save omega to file')
    w = np.expand_dims(w, axis=0)
    height = np.arange(w.shape[1])
    date_str = time[timestep].strftime('%m%d')
    hour_str = time[timestep].strftime('%H')
    outname = f'{model}-{run}_W_{date_str}_{hour_str}_hinterp.nc'
    outname = os.path.join(temp_dir, outname)
    logger.info('Save file')
    print(outname)
    latlonheightfield_to_netCDF(height, lat, lon, w, 'W', '[]', outname, time_dim=True, time_var=timestep*3, overwrite=True)
         
    
def interpolate_vertically_per_timestep(infile, height_file, target_height_file, timestep, model, run, variable, time_period, temp_dir, **kwargs):
    """ Perform vertical interpolation for one timestep included in the input files. Every input file contains one variable.
    Note: Only one timestep is selected from input files, output files contain one time step per file and have to be
    merged afterwards.
    
    Parameters:
        infiles (list of str): List of input files, one for every variable (in the same order as in the variable variables)
        height_file (str): Path to file containing geometric heights for every model level for this timestep
        target_height_file (str): Path to file containing target heights
        timestep (int): Timestep to process
        model (str): Name of model
        run (str): Name of run
        variable (str): Variable to interpolate  
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
    """
    time = pd.date_range(time_period[0], time_period[1]+'-21', freq='3h')
    if model == 'ARPEGE':
        exclude_times = list(pd.date_range("2016-08-11 00:00:00", "2016-08-12 00:00:00", freq='3h'))
        exclude_times.append(pd.to_datetime('2016-08-10 00:00:00'))
        exclude_times.append(pd.to_datetime('2016-08-10 15:00:00'))
        time = [t for t in time if t not in exclude_times]
    date_str = time[timestep].strftime('%m%d')
    hour_str = time[timestep].strftime('%H')
    outname = f'{model}-{run}_{variable}_hinterp_vinterp_{date_str}_{hour_str}.nc'
    outname = os.path.join(temp_dir, outname)    
    units = get_variable_units()
    
    # Read variables from files
    logger.info('Read variables from files')
    # target height
    with Dataset(target_height_file) as dst:
        target_height = dst.variables['target_height'][:].filled(np.nan)
    # height     
    with Dataset(height_file) as dsh:
        heightname = 'H'
        var_height = dsh.variables[heightname][timestep].filled(np.nan)
    # lon, lat and variable to interpolate            
    with Dataset(infile) as ds:
        lat = ds.variables['lat'][:].filled(np.nan)
        lon = ds.variables['lon'][:].filled(np.nan)
        field = ds.variables[variable][timestep].filled(np.nan)

    nheight, nlat, nlon = field.shape
    ntargetheight = len(target_height)
    field_interp = np.ones((ntargetheight, nlat, nlon)) * np.nan

    # interpolate
    logger.info('Interpolation')
    for i in range(nlat):
        print(f'Lat: {i} of {nlat}')
        for j in range(nlon):
            field_interp[:, i, j] = interp1d(
                var_height[:, i, j],
                field[:, i, j],
                bounds_error=False,
                fill_value='extrapolate')(target_height)
    
    # save interpolated field to netCDF file
    logger.info('Save to file')
    field_interp = np.expand_dims(field_interp, axis=0)
    latlonheightfield_to_netCDF(target_height, lat, lon, field_interp,\
                                variable, units[variable], outname, time_dim=True, time_var=timestep*3, overwrite=True)  
        
def interpolation_to_halflevels_per_timestep(infile, model, run, variable, timestep, time_period, data_dir, temp_dir, **kwargs):
    """ Perform vertical interpolation for a field given on full model levels to half levels for one timestep included
    in the input file. 
    Note: Only one timestep is selected from input files, output files contain one time step per file and have to be
    merged afterwards.
    
    Parameters:
        infile (str): Path to input file
        model (str): Name of model
        run (str): Name of model run
        variable (str): Variable to interpolate 
        timestep (int): Timestep to process
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        temp_dir (str): Directory for output files
    """
    time = pd.date_range(time_period[0], time_period[1]+'-21', freq='3h')
    date_str = time[timestep].strftime('%m%d')
    hour_str = time[timestep].strftime('%H')
    outname = f'{model}-{run}_{variable}HL_{date_str}_{hour_str}_hinterp.nc'
    outname = os.path.join(temp_dir, outname)
    units = get_variable_units()
    
    # Read variables from file
    logger.info('Read from file')
    varname = variable    
    with Dataset(infile) as ds:
        field = np.squeeze(ds.variables[varname][timestep].filled(np.nan))
        lat = ds.variables['lat'][:].filled(np.nan)
        lon = ds.variables['lon'][:].filled(np.nan)
    # Dimensions are different for MPAS
    if model == 'MPAS':
        field = field.transpose(2, 0, 1)

    # Interpolation
    logger.info('Interpolation')
    field_interp = field[:-1] + 0.5 * np.diff(field, axis=0)    
    field_interp = np.expand_dims(field_interp, 0)
    height = np.arange(field_interp.shape[1])
    # Save to file
    logger.info('Save to file')
    latlonheightfield_to_netCDF(height, lat, lon, field_interp, variable, units[variable], outname, time_dim=True, time_var=timestep*3, overwrite=True)
            
def calc_level_pressure_from_surface_pressure(surf_pres_file, timestep, model, run, temp_dir, time_period, **kwargs):
    """ Calculate pressure at IFS model levels from surface pressure for one timestep contained in 
    surf_pres_file.
    Note: Only one timestep is selected from input files, output files contain one time step per file and have to be
    merged afterwards.
    
    Parameters:
        surf_pres_file (str): Path to file that contains (logarithm of) surface pressure for every timestep
        timestep (int): Timestep for which to calculate pressure
        temp_dir (str): Path to directory to save output files
        model (str): Name of model
        run (str): Name of model run
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
    """
    time = pd.date_range(time_period[0], time_period[1]+'-21', freq='3h')
    if model == 'ARPEGE':
        exclude_times = list(pd.date_range("2016-08-11 00:00:00", "2016-08-12 00:00:00", freq='3h'))
        exclude_times.append(pd.to_datetime('2016-08-10 00:00:00'))
        exclude_times.append(pd.to_datetime('2016-08-10 15:00:00'))
        time = [t for t in time if t not in exclude_times]
        
    date_str = time[timestep].strftime('%m%d')
    hour_str = time[timestep].strftime('%H')
    outname = f'{model}-{run}_PRES_{date_str}_{hour_str}_hinterp.nc'
    outname = os.path.join(temp_dir, outname)
    
    # Read surface pressure from file
    logger.info('Read surface pressure from file')
    with Dataset(surf_pres_file) as ds:
        # calc surface pressure from logarithm of surface pressure
        if model == 'IFS':
            surf_pres = np.exp(ds.variables['SURF_PRES'][timestep].filled(np.nan))
        else:
            surf_pres = ds.variables['SURF_PRES'][timestep].filled(np.nan)
        lat = ds.variables['lat'][:].filled(np.nan)
        lon = ds.variables['lon'][:].filled(np.nan)
    
    # Calculate pressure
    logger.info('Calculate pressure')
    # Scaling parameters
    a, b = get_pressure_scaling_parameters(model)
    if len(surf_pres.shape) == 2:
        surf_pres = np.expand_dims(surf_pres, axis=0)
    pres = np.ones((len(a), surf_pres.shape[1], surf_pres.shape[2])) * np.nan    
    for la in range(surf_pres.shape[1]):
        for lo in range(surf_pres.shape[2]):
            if model == 'IFS':
                pres[:, la, lo] = np.flipud(surf_pres[:, la, lo] * b + a)
            if model == 'ERA5':
                pres[:, la, lo] = np.flipud(surf_pres[:, la, lo] * b + a)
            else:
                pres[:, la, lo] = surf_pres[:, la, lo] * b + a
            #return(a[ilev-1]+b[ilev-1]*surfacepressure)
            
    # Save to file
    logger.info('Save pressure to file')
    height = np.arange(pres.shape[0])
    pres = np.expand_dims(pres, axis=0)
    latlonheightfield_to_netCDF(height, lat, lon, pres, 'PRES', 'Pa', outname, time_dim=True, time_var=timestep*3, overwrite=True)
    
def calc_height_from_pressure(pres_file, temp_file, z0_file, timestep, model, run, time_period, temp_dir, **kwargs):
    """ Calculate level heights from level pressure and layer temperature assuming hydrostatic equilibrium (Needed
    for IFS, SAM, FV3 and ARPEGE).
    
    Parameters:
        pres_file (str): Path to file containing pressures for every model level
        temp_file (str): Path to file containing temperatures for every model level
        z0_file (str): Path to file containing orography (as geopotential height)
        timestep (int): Timestep in pres_file and temp_file to process
        model (str): Name of model
        run (str): Name of model run
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        temp_dir (str): Path to directory for output files
    """
    time = pd.date_range(time_period[0], time_period[1]+'-21', freq='3h')
    if model == 'ARPEGE':
        exclude_times = list(pd.date_range("2016-08-11 00:00:00", "2016-08-12 00:00:00", freq='3h'))
        exclude_times.append(pd.to_datetime('2016-08-10 00:00:00'))
        exclude_times.append(pd.to_datetime('2016-08-10 15:00:00'))
        time = [t for t in time if t not in exclude_times]
    date_str = time[timestep].strftime('%m%d')
    hour_str = time[timestep].strftime('%H')
    outname = f'{model}-{run}_H_{date_str}_{hour_str}_hinterp.nc'
    outname = os.path.join(temp_dir, outname)
    
    # variable names
    temp_name = 'TEMP'
    pres_name = 'PRES'
    
    # Read variables from file
    logger.info('Read from file')
    # temperature, lat, lon
    with Dataset(temp_file) as ds:
        temp = ds.variables[temp_name][timestep].filled(np.nan)
        lat = ds.variables['lat'][:].filled(np.nan)
        lon = ds.variables['lon'][:].filled(np.nan)
        
    with Dataset(pres_file) as ds:
        # IFS: logarithm of surface pressure is given
        if model == 'IFS':
            surf_pres = np.exp(ds.variables[pres_name][timestep].filled(np.nan))
        # SAM: mean pressure and pressure perturbation are given
        if model == 'SAM':
            pres_pert = ds.variables[pres_name][timestep].filled(np.nan)
            pres_mean = ds.variables['p'][:].filled(np.nan)
        # FV3: only one pressure vector is given (same for every grid cell)
        if model == 'FV3':
            pres_vector = ds.variables['pfull'][:].filled(np.nan)
            pres = np.zeros((len(pres_vector), len(lat), len(lon)))
            for la in range(len(lat)):
                for lo in range(len(lon)):
                    pres[:, la, lo] = pres_vector
        else:
            pres = ds.variables[pres_name][timestep].filled(np.nan)
            
    # orography
    with Dataset(z0_file) as ds:
        if model in ['IFS', 'ERA5']:
            z0 = ds.variables['z'][0][0].filled(np.nan) / typhon.constants.g
        elif model == 'FV3':
            z0 = ds.variables['z'][:].filled(np.nan)
        elif model == 'ARPEGE':
            z0 = ds.variables['GH'][timestep][0].filled(np.nan) / typhon.constants.g 
            # z0 = np.ones((len(lat), len(lon))) * 17. (lowest model level is at 17 meters above sea level)
            
    # Calculate heights
    logger.info('Calculate heights')
    height = np.flipud(pressure2height(np.flipud(pres), np.flipud(temp), z0))

    # Save to file
    logger.info('Save heights to file')
    h = np.arange(height.shape[0])
    height = np.expand_dims(height, axis=0)    
    latlonheightfield_to_netCDF(h, lat, lon, height, 'H', 'm', outname, time_dim=True, time_var=timestep*3, overwrite=True)


def calc_net_radiation_flux(infiles, tempfile, outfile, flux_names):
    """ Calculates net radiation flux from upward and downward fluxes using CDOs only. Files containing
    upward and downward fluxes are merged first, then the net flux is calculated.
    
    Parameters:
        infiles (list of str): Name of input files containing 1. downward and 2. upward fluxes
        tempfile (str): Name of temporary file containing both downward and upward fluxes
        outfile (str): Name of output file containing net fluxes
        flux_names (list of str): Variable names of 1. downward, 2. upward and 3. net fluxes 
            (e.g. ['SDTOA', 'SUTOA', 'STOA'])
    """
    cmd_1 = f'cdo --verbose merge {infiles[0]} {infiles[1]} {tempfile}'
    cmd_2 = f'cdo --verbose expr,{flux_names[2]}={flux_names[0]}-{flux_names[1]} {tempfile} {outfile}'
    cmd_3 = f'rm {tempfile}'
    
    logger.info(cmd_1)
    os.system(cmd_1)
    logger.info(cmd_2)
    os.system(cmd_2)
    logger.info(cmd_3)
    os.system(cmd_3)
    
def deaccumulate_fields(model, infile, variable):
    """ Deaccumulate radiation fields, i.e. transform radiation given as accumulated energy [J] to 
    power [W m**-2].
    
    Parameters:
        model: model name
        infile: full path to input file
        variable: name of variable
    """
   
    if model == 'IFS':
        with Dataset(infile) as ds:
            field = ds.variables[variable][:].filled(np.nan)
            lat = ds.variables['lat'][:].filled(np.nan)
            lon = ds.variables['lon'][:].filled(np.nan)
            time = ds.variables['time'][:].filled(np.nan)
    if model == 'MPAS':
        with Dataset(infile) as ds:
            time = ds.variables['xtime'][:].filled(np.nan)
            field = ds.variables[variable][:].filled(np.nan)
            lat = ds.variables['lat'][:].filled(np.nan)
            lon = ds.variables['lon'][:].filled(np.nan)
        
    field_deacc = np.zeros((field.shape[0] - 1, field.shape[1], field.shape[2]))
    for t in range(field.shape[0] - 1):
        field_deacc[t] = (field[t + 1] - field[t]) / (3600 * 3) * -1
        
    time_new = time[:-1] + np.diff(time) * 0.5
    
    infilename, infile_extension = os.path.splitext(infile)
    filename_new = infilename+'_acc'+infile_extension
    os.system(f'mv {infile} {filename_new}')
        
    outname = infile
    latlonfield_to_netCDF(lat, lon, field_deacc, variable, 'W m^-2', outname, time_dim=True, time_var=time_new, overwrite=True)
    
def pressure2height(p, T, z0=None):
    """Convert pressure to height based on the hydrostatic equilibrium.

    Parameters:
        p (ndarray): Pressure [Pa].
        T (ndarray): Temperature [K].
        z0 (ndarray): Height of lowest pressure level [m].

    Returns:
        ndarray: Height [m].
    """
     
    layer_depth = np.diff(p, axis=0)
    rho = typhon.physics.thermodynamics.density(p, T)
    rho_layer = 0.5 * (rho[:-1] + rho[1:])

    z = np.cumsum(-layer_depth / (rho_layer * typhon.constants.g), axis=0) + z0
    z = np.vstack((np.expand_dims(z0, axis=0), z))
    
    return z  
        
def merge_timesteps(infiles, outfile, numthreads, **kwargs):
    """ Merge files containing several time steps to one file containing all time steps.
    
    Parameter:
        infiles (list of str): list of paths to input files to be merged
        outfile (str): name of output file
        numthreads (int): number of OpenMP threads for cdo
    """
    infiles_str = ' '.join(infiles)
    cmd = f'cdo -O -P {numthreads} mergetime {infiles_str} {outfile}'
    logger.info(cmd)
    os.system(cmd)

def average_timesteps(infile, outfile, options, numthreads, **kwargs):
    """
    Calculate temporal average of all time steps contained in one file.
    
    Parameter:
        infile (str): path to input file containing several time steps
        outfile (str): name for file containing time average
        numthreads (int): number of OpenMP threads for cdo
    """
    if options != '':
        options = options + ' '
    cmd = f'cdo -O -P {numthreads} timmean {options}{infile} {outfile}'
    logger.info(cmd)
    os.system(cmd)

def select_lonlatbox(infile, outfile, lonlatbox, numthreads, **kwargs):
    """ Select a lon-lat box from the fields contained in one file.
    
    Parameters:
        infile (str): path to input file containing several time steps
        outfile (str): name for file containing time average
        lonlatbox (list): boundaries of latitude longitude box: [lonmin lonmax latmin latmax]
        numthreads (int): number of OpenMP threads for cdo
    """
    lon_1 = lonlatbox[0]
    lon_2 = lonlatbox[1]
    lat_1 = lonlatbox[2]
    lat_2 = lonlatbox[3]
    cmd = f'cdo -O -P {numthreads} sellonlatbox,{lon_1},{lon_2},{lat_1},{lat_2} {infile} {outfile}'
    logger.info(cmd)
    os.system(cmd)

def select_random_profiles(model, run, num_samples_tot, infiles, outfiles, heightfile, landmaskfile,\
                               variables, lonlatbox, vinterp, data_dir, sample_days, timesteps=None, **kwargs):
    """ Selects a subset of random profiles from (horizontally interpolated) model fields, sorts them by their integrated
    water vapor and saves them.
    
    Parameters:
        model (str): name of model
        run (str): name of model run
        num_samples_tot (int): Total number of profiles to select
        infiles (list of str): List of names of input files (each file contains one variable)
        outfiles (list of str): List of names for output files
        heightfile (str): Full path to file containing height vector
        landmaskfile (str): Full path to file containing land mask
        variables (list of str): names of variables (same order as in infiles!!)
        lonlatbox (list of floats): Boundaries of lon-lat box to select [lonmin, lonmax, latmin, latmax]
        vinterp (boolean): True, if data is already interpolated vertically 
        data_dir (str): Path to output directory
        sample_days (str): 'First10', 'Last10' or 'all'
        timesteps (1darray or None): Either a 1darray containing timesteps to use or None 
            (all timesteps are used; default)
    """
    
    logger.info(model)
    logger.info('Config')
    variables_2D = ['OLR', 'OLRC', 'STOA', 'IWV', 'lat', 'lon', 'timestep']
    test_ind = [i for i in range(len(variables)) if variables[i] not in variables_2D][0]
    test_var = variables[test_ind]
    test_filename = infiles[test_ind]
    
    logger.info('Get dimensions')
    # height
    height = atools.read_var(heightfile, model, 'target_height')
    num_levels = height.shape[0]
    if height[0] < height[-1]:
        surface = 0
    else:
        surface = -1
    if model == 'GEOS':
        surface = -2
    
    print(surface)
    logger.info('Read lats/lons from file')
    # lon, lat
    with Dataset(test_filename) as ds:
        dimensions = ds.variables[test_var].shape
        test_field = ds.variables[test_var][0].filled(np.nan)
        lat = ds.variables['lat'][:]
        lon = ds.variables['lon'][:]
        
    lat_reg_ind = np.where(np.logical_and(lat >= lonlatbox[2], lat <= lonlatbox[3]))[0]
    lon_reg_ind = np.where(np.logical_and(lon >= lonlatbox[0], lon <= lonlatbox[1]))[0]
    lat = lat[lat_reg_ind]
    lon = lon[lon_reg_ind]
    
    logger.info('NaN mask')
    if model == 'MPAS' and test_var in ['TEMP', 'PRES', 'QV', 'QI', 'QC']:
        nan_mask = np.logical_not(np.isnan(test_field[lat_reg_ind][:, lon_reg_ind][:, :, surface]))
    else:
        nan_mask = np.logical_not(np.isnan(test_field[surface][lat_reg_ind][:, lon_reg_ind]))
    
    # timesteps
    logger.info('Timesteps')
    if timesteps is not None:
        num_timesteps = len(timesteps)
    else:
        if sample_days.lower() == 'all':
            num_timesteps = dimensions[0]
            timesteps = np.arange(num_timesteps)
        elif sample_days.lower() == 'first10':
            num_timesteps = 80
            timesteps = np.arange(0, num_timesteps)
        elif sample_days.lower() == 'last10':
            num_timesteps = 80
            timesteps = np.arange(dimensions[0] - 80, dimensions[0])
        
    if model in ['MPAS', 'IFS', 'ARPEGE']:
        timesteps = timesteps[:-1]
        num_timesteps = num_timesteps - 1
    
    num_samples_timestep = int(num_samples_tot / num_timesteps)

    #return nan_mask
    
    logger.info('Ocean mask')
    # get ocean_mask
    ocean_mask = np.logical_not(
        np.squeeze(atools.read_var(landmaskfile, model, 'land_mask'))
    )
    ocean_lon = atools.read_var(landmaskfile, model, 'lon')
    ocean_lat = atools.read_var(landmaskfile, model, 'lat')
    ocean_lat_ind = np.where(np.logical_and(ocean_lat >= lonlatbox[2], ocean_lat <= lonlatbox[3]))[0]
    ocean_lon_ind = np.where(np.logical_and(ocean_lon >= lonlatbox[0], ocean_lon <= lonlatbox[1]))[0]
    ocean_mask = ocean_mask[ocean_lat_ind][:, ocean_lon_ind].astype(int)
#    lat_ocean = np.where(ocean_mask)[0]
#    lon_ocean = np.where(ocean_mask)[1]

    logger.info('Total mask')    
    total_mask = np.where(np.logical_and(ocean_mask, nan_mask))
    lat_not_masked = total_mask[0]
    lon_not_masked = total_mask[1]
    
    lat_inds = np.zeros((num_timesteps, num_samples_timestep)).astype(int)
    lon_inds = np.zeros((num_timesteps, num_samples_timestep)).astype(int)

    logger.info('Get indices')
    for t in range(num_timesteps):
        r = random.sample(list(zip(lat_not_masked, lon_not_masked)), num_samples_timestep)
        lat_inds[t], lon_inds[t] = zip(*r)
          
    profiles = {}
    profiles_sorted = {}
    #latlon = np.meshgrid(lat, lon)
    profiles['lat'] = np.ones((num_samples_tot)) * np.nan
    profiles['lon'] = np.ones((num_samples_tot)) * np.nan
    
    # select lats, lons
    for j, t in enumerate(timesteps):
        start = j * num_samples_timestep
        end = start + num_samples_timestep
        profiles['lat'][start:end] = lat[lat_inds[j]]
        profiles['lon'][start:end] = lon[lon_inds[j]]
    #return profiles, ocean_mask, nan_mask, total_mask, lat_inds, lon_inds, num_timesteps, num_samples_timestep, lon, lat
    logger.info('Read variables from files')
    for i, var in enumerate(variables):
        logger.info(var)
        if var in variables_2D:
            profiles[var] = np.ones((num_samples_tot)) * np.nan
            profiles_sorted[var] = np.ones((num_samples_tot)) * np.nan
            for j, t in enumerate(timesteps):
                start = j * num_samples_timestep
                end = start + num_samples_timestep
                with Dataset(infiles[i]) as ds:
                    if model == 'NICAM':
                        profiles[var][start:end] = ds.variables[var][t][0, lat_inds[j], lon_inds[j]].filled(np.nan)
                    else:
                        profiles[var][start:end] = ds.variables[var][t][lat_inds[j], lon_inds[j]].filled(np.nan)
        else:
            profiles[var] = np.ones((num_levels, num_samples_tot)) * np.nan
            profiles_sorted[var] = np.ones((num_levels, num_samples_tot)) * np.nan
            for j, t in enumerate(timesteps):
                start = j * num_samples_timestep
                end = start + num_samples_timestep
                with Dataset(infiles[i]) as ds:
                    if model == 'MPAS' and var in ['TEMP', 'PRES', 'QV', 'QI', 'QC']:
                        profiles[var][:, start:end] = ds.variables[var][t][lat_inds[j], lon_inds[j], :].filled(np.nan).transpose([1, 0])
                    else:
                        if model == 'SAM' and var == 'PRES':
                            pres_mean = np.expand_dims(ds.variables['p'][:], 1) * 1e2
                            pres_pert = ds.variables['PP'][t][:, lat_inds[j], lon_inds[j]].filled(np.nan)
                            profiles[var][:, start:end] = pres_mean + pres_pert
                            print(profiles[var][:, start:end])
                        else:
                            profiles[var][:, start:end] = ds.variables[var][t][:, lat_inds[j], lon_inds[j]].filled(np.nan)
                        
        if model == 'SAM' and var in ['QV', 'QI', 'QC']:
            profiles[var] *= 1e-3
            
    logger.info('Calculate IWV and sort')
    # calculate IWV
    print(height)
    print(profiles['PRES'].shape)
    print(profiles['TEMP'].shape)
    print(profiles['QV'].shape)
    profiles['IWV'] = utils.calc_IWV(profiles['QV'], profiles['TEMP'], profiles['PRES'], height)
    # get indices to sort by IWV
    IWV_sort_idx = np.argsort(profiles['IWV'])
            
    # sort by IWV and save output
    for i, var in enumerate(variables + ['IWV', 'lon', 'lat']):
        if var in variables_2D:
            profiles_sorted[var] = profiles[var][IWV_sort_idx]
            vector_to_netCDF(
                profiles_sorted[var], var, '', range(num_samples_tot), 'profile_index', outfiles[i], overwrite=True
            )
        else:
            profiles_sorted[var] = profiles[var][:, IWV_sort_idx]
            array2D_to_netCDF(
                profiles_sorted[var], var, '', (height, range(num_samples_tot)), ('height', 'profile_index'), outfiles[i], overwrite=True
            )
    
    
def average_random_profiles(model, run, time_period, variables, num_samples, sample_days, data_dir, **kwargs):
    """ Average randomly selected profiles in IWV percentile bins and IWV bins, separately for different
    ocean basins. Output is saved as .pkl files.
    
    Parameters:
        model (str): name of model
        run (str): name of model run
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        variables (list of str): names of variables
        num_samples (num): number of randomly selected profiles
        sample_days (str): 'all', 'first10' or 'last10'
    """

    time = pd.date_range(time_period[0], time_period[1], freq='1D')
    start_date = time[0].strftime("%m%d")
    end_date = time[-1].strftime("%m%d")
    variables_3D = ['TEMP', 'PRES', 'QV', 'QI', 'QC', 'RH', 'W']
    variables_2D = ['OLR', 'IWV', 'STOA', 'OLRC', 'STOAC', 'H_tropo', 'IWP']
    datapath = f'{data_dir}/{model}/random_samples/'
    filenames = '{}-{}_{}_sample_{}_{}-{}{}{}.nc'
    perc_values = np.arange(1, 100.5, 1.0)
    num_percs = len(perc_values)
    iwv_bin_bnds = np.arange(0, 101, 1)
    ic_thres = {
        'QI': 0.001 * 1e-6,
        'QC': 0.001 * 1e-6
    }
    stats = ['mean', 'std', 'median', 'min', 'max', 'quart25', 'quart75']
    if sample_days == 'all':
        sample_days_str = ''
    else:
        sample_days_str = '_'+sample_days
    
    logger.info('Read data from files')
    filename = filenames.format(model, run, variables_3D[0], num_samples, start_date, end_date, sample_days_str, '')
    filename = os.path.join(datapath, filename)
    with(Dataset(filename)) as ds:
        height = ds.variables['height'][:].filled(np.nan)
    num_levels = len(height)
    
    bins = np.arange(1, len(iwv_bin_bnds)) 
    bin_count = np.zeros(len(iwv_bin_bnds) - 1)
    
    profiles_sorted = {}
    for var in variables+['lon', 'lat']:
        logger.info(var)
        filename = filenames.format(model, run, var, num_samples, start_date, end_date, sample_days_str, '')
        filename = os.path.join(datapath, filename)
        with(Dataset(filename)) as ds:
            profiles_sorted[var] = ds.variables[var][:].filled(np.nan)
    num_profiles = len(profiles_sorted[var])
            
    logger.info('Calc additional variables: IWP and H_tropo')
  
    profiles_sorted['IWP'] = np.ones(num_profiles) * np.nan

    profiles_sorted['IWP'] = utils.calc_IWP(
        profiles_sorted['QI'], 
        profiles_sorted['TEMP'], 
        profiles_sorted['PRES'], 
        profiles_sorted['QV'], 
        height
    )    
    profiles_sorted['H_tropo'] = utils.tropopause_height(
        profiles_sorted['TEMP'], 
        height
    )
            
    nan_mask = np.isnan(profiles_sorted['lon'])
    
    for var in variables+['lon', 'lat', 'IWP', 'H_tropo']:
        if var in variables_3D:
            profiles_sorted[var] = profiles_sorted[var][:, np.logical_not(nan_mask)]
        else:
            profiles_sorted[var] = profiles_sorted[var][np.logical_not(nan_mask)]

    perc = {s: {} for s in stats+['percentiles']}
    binned = {s: {} for s in stats+['count']}
    
    logger.info('Binning to percentile bins')
    perc['percentiles'] = np.asarray([np.percentile(profiles_sorted['IWV'], p) for p in perc_values])
    splitted_array = {}
    for var in variables+['H_tropo', 'IWP']:
        logger.info(var)
        splitted_array[var] = {}
        if var in variables_2D: 
            axis=0
            splitted_array[var] = np.array_split(profiles_sorted[var], num_percs, axis=axis)
            
        else:
            axis=1
            splitted_array[var] = np.array_split(profiles_sorted[var], num_percs, axis=axis)
            
        for s in splitted_array[var]:
            print(s.shape)
        perc['mean'][var] = np.asarray([np.nanmean(a, axis=axis) for a in splitted_array[var]])
        perc['std'][var] = np.asarray([np.nanstd(a, axis=axis) for a in splitted_array[var]])
        perc['min'][var] = np.asarray([np.nanmin(a, axis=axis) for a in splitted_array[var]])
        perc['max'][var] = np.asarray([np.nanmax(a, axis=axis) for a in splitted_array[var]])
        perc['median'][var] = np.asarray([np.nanmedian(a, axis=axis) for a in splitted_array[var]])
        perc['quart25'][var] = np.asarray([np.nanpercentile(a, 25, axis=axis) for a in splitted_array[var]])
        perc['quart75'][var] = np.asarray([np.nanpercentile(a, 75, axis=axis) for a in splitted_array[var]])


    # determine in-cloud ice/water content and cloud fraction in each bin
    for condensate, content, fraction in zip(['QI', 'QC'], ['ICQI', 'ICQC'], ['CFI', 'CFL']):
        perc['mean'][content] = np.asarray(
            [np.ma.average(a, weights=(a > ic_thres[condensate]), axis=1).filled(0) for a in splitted_array[condensate]]
        )
        perc['mean'][fraction] = np.asarray(
            [np.sum(a * (a > ic_thres[condensate]), axis=1) / a.shape[1] for a in splitted_array[condensate]]
        )

    logger.info('Binning to IWV bins')
    bin_idx = np.digitize(profiles_sorted['IWV'], iwv_bin_bnds)
    binned['count'] = np.asarray([len(np.where(bin_idx == bi)[0]) for bi in bins])
    binned_profiles = {}
    for var in variables+['H_tropo', 'IWP']:
        logger.info(var)
        if var in variables_2D+['IWP', 'H_tropo']:
            binned_profiles[var] = [profiles_sorted[var][bin_idx == bi] for bi in bins]
            axis=0
        else:
            binned_profiles[var] = [profiles_sorted[var][:, bin_idx == bi] for bi in bins]
            axis=1

        binned['mean'][var] = np.asarray([np.nanmean(p, axis=axis) for p in binned_profiles[var]])
        binned['std'][var] = np.asarray([np.nanstd(p, axis=axis) for p in binned_profiles[var]])
        binned['median'][var] = np.asarray([np.nanmedian(p, axis=axis) for p in binned_profiles[var]])
        binned['min'][var] = np.asarray(
            [np.nanmin(p, axis=axis) if p.size else np.ones(num_levels) * np.nan for p in binned_profiles[var]]
        )
        binned['max'][var] = np.asarray(
            [np.nanmax(p, axis=axis) if p.size else np.ones(num_levels) * np.nan for p in binned_profiles[var]]
        )
        binned['quart25'][var] = np.asarray(
            [np.nanpercentile(p, 25, axis=axis) if p.size else np.ones(num_levels) * np.nan for p in binned_profiles[var]]
        )
        binned['quart75'][var] = np.asarray(
            [np.nanpercentile(p, 75, axis=axis) if p.size else np.ones(num_levels) * np.nan for p in binned_profiles[var]]
        )

    # determine in-cloud ice/water content and cloud fraction in each bin    
    for condensate, content, fraction in zip(['QI', 'QC'], ['ICQI', 'ICQC'], ['CFI', 'CFL']):
        binned['mean'][content] = np.asarray(
            [np.ma.average(a, weights=(a > ic_thres[condensate]), axis=1).filled(0) for a in binned_profiles[condensate]]
        )
        binned['mean'][fraction] = np.asarray(
            [np.sum(a * (a > ic_thres[condensate]), axis=1) / a.shape[1] for a in binned_profiles[condensate]]
        )
        
    logger.info('Write output')
    #output files
    outname_perc = f'{model}-{run}_{start_date}-{end_date}_{num_percs}_perc_means_{num_samples}{sample_days_str}_1exp.pkl'
    outname_binned = f'{model}-{run}_{start_date}-{end_date}_bin_means_{num_samples}{sample_days_str}_1exp.pkl'
    
    with open(os.path.join(datapath, outname_perc), 'wb' ) as outfile:
        pickle.dump(perc, outfile) 
    with open(os.path.join(datapath, outname_binned), 'wb' ) as outfile:
        pickle.dump(binned, outfile)

def average_random_profiles_per_basin(model, run, time_period, variables, num_samples, sample_days, data_dir, **kwargs):
    """ Average randomly selected profiles in IWV percentile bins and IWV bins, separately for different
    ocean basins. Output is saved as .pkl files.
    
    Parameters:
        model (str): name of model
        run (str): name of model run
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        variables (list of str): names of variables
        num_samples (num): number of randomly selected profiles
        sample_days (str): 'all', 'first10' or 'last10'
    """

    time = pd.date_range(time_period[0], time_period[1], freq='1D')
    start_date = time[0].strftime("%m%d")
    end_date = time[-1].strftime("%m%d")
    variables_3D = ['TEMP', 'PRES', 'QV', 'QI', 'QC', 'RH', 'W']
    variables_2D = ['OLR', 'IWV', 'STOA', 'OLRC', 'STOAC', 'H_tropo', 'IWP']
    datapath = f'{data_dir}/{model}/random_samples/'
    filenames = '{}-{}_{}_sample_{}_{}-{}{}{}.nc'
    perc_values = np.arange(1, 100.5, 1.0)
    num_percs = len(perc_values)
    iwv_bin_bnds = np.arange(0, 101, 1)
    ic_thres = {
        'QI': 0.001 * 1e-6,
        'QC': 0.001 * 1e-6
    }
    if sample_days == 'all':
        sample_days_str = ''
    else:
        sample_days_str = '_'+sample_days
    ocean_basins = ['Pacific', 'Atlantic', 'Indic']
    stats = ['mean', 'std', 'median', 'min', 'max', 'quart25', 'quart75']
    
    logger.info('Read data from files')
    filename = filenames.format(model, run, variables_3D[0], num_samples, start_date, end_date, sample_days_str, '')
    filename = os.path.join(datapath, filename)
    with(Dataset(filename)) as ds:
        height = ds.variables['height'][:].filled(np.nan)
    num_levels = len(height)
    
    bins = np.arange(len(iwv_bin_bnds) - 1) 
    bin_count = np.zeros(len(iwv_bin_bnds) - 1)
    
    profiles_sorted = {}
    for var in variables+['lon', 'lat']:
        logger.info(var)
        filename = filenames.format(model, run, var, num_samples, start_date, end_date, sample_days_str, '')
        filename = os.path.join(datapath, filename)
        with(Dataset(filename)) as ds:
            profiles_sorted[var] = ds.variables[var][:].filled(np.nan)
    num_profiles = len(profiles_sorted[var])
            
    logger.info('Calc additional variables: IWP and H_tropo')
    profiles_sorted['IWP'] = np.ones(num_profiles) * np.nan
    profiles_sorted['IWP'] = utils.calc_IWP(
        profiles_sorted['QI'], 
        profiles_sorted['TEMP'], 
        profiles_sorted['PRES'], 
        profiles_sorted['QV'], 
        height
    )    
    profiles_sorted['H_tropo'] = utils.tropopause_height(
        profiles_sorted['TEMP'], 
        height
    )
            
    nan_mask = np.isnan(profiles_sorted['lon'])
    for var in variables+['lon', 'lat', 'IWP', 'H_tropo']:
        if var in variables_3D:
            profiles_sorted[var] = profiles_sorted[var][:, np.logical_not(nan_mask)]
        else:
            profiles_sorted[var] = profiles_sorted[var][np.logical_not(nan_mask)]
    
    logger.info('Split profiles into corresponding ocean basins')
    # determine ocean basin for each profile
    basins = []
    for lon, lat in zip(profiles_sorted['lon'], profiles_sorted['lat']):
        basins.append(ocean_basin(lon, lat))
    basins = np.array(basins)
    
    # split profiles into basins
    profiles = {}
    for basin in ocean_basins:
        logger.info(basin)
        profiles[basin] = {}
        for var in variables+['lon', 'lat', 'IWP', 'H_tropo']:
            if var in variables_3D:
                profiles[basin][var] = profiles_sorted[var][:, basins == basin]
            else:
                profiles[basin][var] = profiles_sorted[var][basins == basin]

    perc = {}
    binned = {}
    logger.info('Binning to percentile bins')
    for b in ocean_basins:
        logger.info(b)
        perc[b] = {s: {} for s in stats+['percentiles']}
        perc[b]['percentiles'] = np.asarray([np.percentile(profiles[b]['IWV'], p) for p in perc_values])
        splitted_array = {}
        for var in variables+['H_tropo', 'IWP']:
            logger.info(var)
            splitted_array[var] = {}
            if var in variables_2D: 
                splitted_array[var] = np.array_split(profiles[b][var], num_percs)
                axis=0
            else:
                splitted_array[var] = np.array_split(profiles[b][var], num_percs, axis=1)
                axis=1
                
            perc[b]['mean'][var] = np.asarray([np.nanmean(a, axis=axis) for a in splitted_array[var]])
            perc[b]['std'][var] = np.asarray([np.nanstd(a, axis=axis) for a in splitted_array[var]])
            perc[b]['min'][var] = np.asarray([np.nanmin(a, axis=axis) for a in splitted_array[var]])
            perc[b]['max'][var] = np.asarray([np.nanmax(a, axis=axis) for a in splitted_array[var]])
            perc[b]['median'][var] = np.asarray([np.nanmedian(a, axis=axis) for a in splitted_array[var]])
            perc[b]['quart25'][var] = np.asarray([np.nanpercentile(a, 25, axis=axis) for a in splitted_array[var]])
            perc[b]['quart75'][var] = np.asarray([np.nanpercentile(a, 75, axis=axis) for a in splitted_array[var]])
        

        # determine in-cloud ice/water content and cloud fraction in each bin
        for condensate, content, fraction in zip(['QI', 'QC'], ['ICQI', 'ICQC'], ['CFI', 'CFL']):
            perc[b]['mean'][content] = np.asarray(
                [np.ma.average(a, weights=(a > ic_thres[condensate]), axis=1).filled(0) for a in splitted_array[condensate]]
            )
            perc[b]['mean'][fraction] = np.asarray(
                [np.sum(a * (a > ic_thres[condensate]), axis=1) / a.shape[1] for a in splitted_array[condensate]]
            )

    logger.info('Binning to IWV bins')
    for b in ocean_basins:
        bin_idx = np.digitize(profiles[b]['IWV'], iwv_bin_bnds)
        binned[b] = {s: {} for s in stats+['count']}
        binned[b]['count'] = np.asarray([len(np.where(bin_idx == bi)[0]) for bi in bins])
        binned_profiles = {}
        for var in variables+['H_tropo', 'IWP']:
            logger.info(var)
            if var in variables_2D+['IWP', 'H_tropo']:
                binned_profiles[var] = [profiles[b][var][bin_idx == bi] for bi in bins]
                axis=0
            else:
                binned_profiles[var] = [profiles[b][var][:, bin_idx == bi] for bi in bins]
                axis=1
                
            binned[b]['mean'][var] = np.asarray([np.nanmean(p, axis=axis) for p in binned_profiles[var]])
            binned[b]['std'][var] = np.asarray([np.nanstd(p, axis=axis) for p in binned_profiles[var]])
            binned[b]['median'][var] = np.asarray([np.nanmedian(p, axis=axis) for p in binned_profiles[var]])
            binned[b]['min'][var] = np.asarray(
                [np.nanmin(p, axis=axis) if p.size else np.ones(num_levels) * np.nan for p in binned_profiles[var]]
            )
            binned[b]['max'][var] = np.asarray(
                [np.nanmax(p, axis=axis) if p.size else np.ones(num_levels) * np.nan for p in binned_profiles[var]]
            )
            binned[b]['quart25'][var] = np.asarray(
                [np.nanpercentile(p, 25, axis=axis) if p.size else np.ones(num_levels) * np.nan for p in binned_profiles[var]]
            )
            binned[b]['quart75'][var] = np.asarray(
                [np.nanpercentile(p, 75, axis=axis) if p.size else np.ones(num_levels) * np.nan for p in binned_profiles[var]]
            )
            
        # determine in-cloud ice/water content and cloud fraction in each bin    
        for condensate, content, fraction in zip(['QI', 'QC'], ['ICQI', 'ICQC'], ['CFI', 'CFL']):
            binned[b]['mean'][content] = np.asarray(
                [np.ma.average(a, weights=(a > ic_thres[condensate]), axis=1).filled(0) for a in binned_profiles[condensate]]
            )
            binned[b]['mean'][fraction] = np.asarray(
                [np.sum(a * (a > ic_thres[condensate]), axis=1) / a.shape[1] for a in binned_profiles[condensate]]
            )
        
    logger.info('Write output')
    #output files
    outname_perc = f'{model}-{run}_{start_date}-{end_date}_perc_means_basins_{num_samples}{sample_days_str}_0exp.pkl'
    outname_binned = f'{model}-{run}_{start_date}-{end_date}_bin_means_basins_{num_samples}{sample_days_str}_0exp.pkl'
    
    with open(os.path.join(datapath, outname_perc), 'wb' ) as outfile:
        pickle.dump(perc, outfile) 
    with open(os.path.join(datapath, outname_binned), 'wb' ) as outfile:
        pickle.dump(binned, outfile)
        
        
def ocean_basin(lon, lat):
    """ Returns the ocean basin for given longitude and latitude in the tropics.
    
    Parameters:
        lon (float): Longitude (between -180 and 180)
        lat (float): Latitude (between -30 and 30)
    """
    if lon < -70. and lon > -84. and lat < 9.:
        basin = 'Pacific'
    elif lon < -84. and lon > -90. and lat < 14.:
        basin = 'Pacific'
    elif lon < -90. and lon > -100. and lat < 18.:
        basin = 'Pacific'
    elif lon > 145. or lon < -100.:
        basin = 'Pacific'
    elif lon < 145. and lon > 100. and lat > 0.:
        basin = 'Pacific'
    elif lon > 20. and lon < 100.:
        basin = 'Indic'
    elif lon < 145. and lon > 100. and lat < 0.:
        basin = 'Indic'
    elif lon < 20. and lon > -70.:
        basin = 'Atlantic'
    elif lon < -70. and lon > -84. and lat > 9.:
        basin = 'Atlantic'
    elif lon < -84. and lon > -90. and lat > 14.:
        basin = 'Atlantic'
    elif lon < -90. and lon > -100. and lat > 18.:
        basin = 'Atlantic'
    
    return basin
    
def get_modelspecific_varnames(model):
    """ Returns dictionary with variable names for a specific model.
    
    Parameters:
        model (string): Name of model
    """
    
    if model == 'ICON':
        varname = {
#            'TEMP': 't',
#            'QV': 'q',
#            'PRES': 'pres',
#            'RH': 'RH',
#            'QI': 'param213.1.0',
#            'OLR': 'nlwrf_2',
#            'IWV': 'param214.1.0',
            'TEMP': 'T',
            'QV': 'QV',
            'PRES': 'P',
            'RH': 'RH',
            'QI': 'QI_DIA',
            'OLR': 'ATHB_T',
            'IWV': 'TQV_DIA',
            'QC': 'QC_DIA',#'param212.1.0',
            'W500': 'omega',
            'W': 'W',#'wz', 
            'WHL': 'W',
            'STOA': 'ASOB_T',
            'PREC': 'TOT_PREC',
            'OLRC': '-',
            'STOAC': '-',
            'OMEGA': '-'
        }
    elif model == 'NICAM':
        varname = {
            'TEMP': 'ms_tem',
            'QV': 'ms_qv',
            'PRES': 'ms_pres', 
            'RH': 'RH',
            'QI': 'ms_qi',
            'IWV': 'sa_vap_atm',
            'OLR': 'sa_lwu_toa',
            'FTOASWD': 'ss_swd_toa',
            'FTOASWU': 'ss_swu_toa',
            'QC': 'ms_qc',
            'W': 'ms_w',
            'SUTOA': 'ss_swu_toa',
            'SDTOA': 'ss_swd_toa',
            'OLRC': 'ss_lwu_toa_c',
            'STOAC': '-',
            'OMEGA': '-'
        }
    elif model == 'GEOS':
        varname = {
            'TEMP': 'T',
            'QV': 'QV',
            'PRES': 'P',
            'RH': 'RH',
            'H': 'H',
            'QI': 'QI',
            'OLR': 'OLR',
            'OLRC': 'OLRC',
            'STOA': 'SWTNET',
            'STOAC': 'SWTNETC',
            'IWV': 'TQV',
            'QC': 'QL',
            'W': 'W', 
            'W500': 'OMEGA',
            'OMEGA': '-'
        }    
    elif model == 'IFS':
        varname = {
            'TEMP': 'TEMP',
            'QV': 'QV',
            'QI': 'QI',
            'QC': 'param83.1.0',
            'W': 'param120.128.192',
            'PRES': 'PRES',
            'RH': 'RH',
            'OLR': 'OLR',
            'IWV': 'IWV',
            'H': 'H',
            'OLRC': 'OLRC',
            'STOA': 'STOA',
            'STOAC': 'STOAC',
            'OMEGA': '-',
            'GH': 'GH'
        }
    elif model == 'SAM':
        varname = {
            'TEMP': 'TABS',
            'QV': 'QV',
            'PRES': 'PRES',
            'RH': 'RH',
            'QI': 'QI',
            'IWV': 'PW',
            'OLR': 'LWNTA',
            'QC': 'QC',
            'W': 'W',
            'STOA': 'SWNTA',
            'OMEGA': '-'
        }
    elif model == 'UM':
        varname = {
            'TEMP': 'air_temperature',
            'QV': 'specific_humidity',
            'PRES': 'air_pressure',
            'RH': 'RH',
            'QI': 'mass_fraction_of_cloud_ice_in_air',
            'OLR': 'toa_outgoing_longwave_flux',
            'IWV': 'atmosphere_water_vapor_content',
            'ICI': 'atmosphere_mass_content_of_cloud_ice',
            'QC': 'mass_fraction_of_cloud_liquid_water_in_air',
            'W': 'upward_air_velocity',
            'SDTOA': 'toa_incoming_shortwave_flux',
            'SUTOA': 'toa_outgoing_shortwave_flux',
            'STOA': 'STOA', 
            'OMEGA': '-'
        }
        
    elif model == 'FV3':
        varname = {
            'TEMP': 'temp',
            'QV': 'qv',
            'PRES': 'pres',
            'RH': 'RH',
            'QI': 'qi',
            'IWV': 'intqv',
            'OLR': 'flut',
            'H': 'H',
            'W': 'w',
            'QC': 'ql',
            'SDTOA': 'fsdt',
            'SUTOA': 'fsut',
            'STOA': 'STOA',
            'OMEGA': '-'
        }
        
    elif model == 'MPAS':
        varname = {
            'TEMP': 'temperature',
            'QV': 'qv',
            'QI': 'qi',
            'PRES': 'pressure',
            'RH': 'RH',
            'IWV': 'vert_int_qv',
            'OLR': 'aclwnett',
            'W': 'w',
            'QC': 'qc',
            'STOA': 'acswnett',
            'OMEGA': '-'
        }
        
    elif model == 'ARPEGE':
        varname = {
            'TEMP': 'T',
            'QV': 'QV',
            'QI': 'param84.1.0',
            'SURF_PRES': 'PS',
            'RH': 'RH',
            'IWV': 'TQV',
            'OLR': 'ACCTHB_T',
            'W': 'W',
            'QC': 'param83.1.0',
            'STOA': 'ACCSOB_T',
            'OMEGA': 'W',
            'PRES': 'PRES',
            'GH': 'FI'
        }

    else:
        print('Modelspecific variable names for Model {model} have not been implemented yet.')
        return
        
    return varname

def get_variable_units():
    """ Returns dictionary with units for different variables. 
    """
    
    varunit = {
        'TEMP': 'K',
        'QV': 'kg kg**-1',
        'PRES': 'Pa',
        'RH': '-',
        'QI': 'kg kg**-1',
        'QC': 'kg kg**-1',
        'OLR': 'W m**-2',
        'IWV': 'kg m**-2',
        'ICI': 'kg m**-2',
        'H': 'm',
        'W': 'm s**-1',
        'OMEGA': 'Pa s**-1',
        'STOA': 'W m**-2',
        'STOAC': 'W m**-2',
        'SUTOA': 'W m**-2',
        'SDTOA': 'W m**-2',
        'OLRC': 'W m**-2',
        'PREC': 'kg s**-1 m**-2'
    }
    
    return varunit        
def get_path2grid(grid_res, **kwargs):
    """ Returns path to file with grid information for a regular lat-lon grid with a
    resolution specified in grid_res. Note that grid files only exist for 0.1 and 0.2
    degrees so far. 
    
    Parameters:
        grid_res (float): grid resolution in degree  
    """
    
    gridname = str(grid_res).ljust(4, '0')
    grid = f'/work/ka1081/Hackathon/GrossStats/{gridname}_grid.nc'
    
    if not os.path.isfile(grid):
        logger.warning('Warning: A grid file for this resolution does not exist yet.')
    
    return grid

def get_path2weights(model, run, grid_res, **kwargs):
    """ Returns path to file containing pre-calculated interpolation weights for a given
    model run and a given target grid resolution.
    
    Parameter:
        model (str): name of model
        run (str): name of model run
        grid_res (float): resolution of target grid in degrees.
    """
    grid_dir = '/work/ka1081/DYAMOND/PostProc/GridsAndWeights'
    if model == 'ICON':
        if run == '5.0km_1':
            weights = 'ICON_R2B09_0.10_grid_wghts.nc'
        elif run == '5.0km_2':
            weights = 'ICON_R2B09-mpi_0.10_grid_wghts.nc'
        elif run == '2.5km' or run == '2.5km_winter':
            weights = 'ICON_R2B10_0.10_grid_wghts.nc'
        else:
            logger.error(f'Run {run} not supported for {model}.\nSupported runs are: "5.0km_1", "5.0km_2", "2.5km".')
            return None
        
    elif model == 'NICAM':
        if run == '3.5km':
            weights = 'NICAM-3.5km_0.10_grid_wghts.nc'
        elif run == '7.0km':
            weights = 'NICAM-7.0km_0.10_grid_wghts.nc'
        else:
            logger.error(f'Run {run} not supported for {model}.\nSupported runs are: "3.5km" and "7.0km".')
            return None
    
    elif model == 'GEOS':
        if run == '3.0km' or run == '3.0km-MOM':
            weights = 'GEOS-3.25km_0.10_grid_wghts.nc'
        else:
            logger.error(f'Run {run} not supported for {model}.\nSupported runs are: "3.0km" and "3.0km-MOM".')
    
    elif model == 'IFS':
        if run == '4.0km':
            weights = 'ECMWF-4km_0.10_grid_wghts.nc'
        elif run == '9.0km':
            weights = 'ECMWF-9km_0.10_grid_wghts.nc'
        else:
            logger.error(f'Run {run} not supported for {model}.\nSupported runs are: "4.0km" and "9.0km".') 
            
    elif model == 'SAM':
        if run == '4.0km':
            weights = 'SAM_0.10_grid_wghts.nc'
        else:
            logger.error(f'Run {run} not supported for {model}.\nSupported runs are: "4.0km".')
    
    elif model == 'UM':
        if run == '5.0km':
            weights = 'UM-5km_0.10_grid_wghts.nc'
        else:
            logger.error(f'Run {run} not supported for {model}.\nSupported runs are: "5.0km".')
            
    elif model == 'FV3':
        if run == '3.25km':
            weights = 'FV3-3.3km_0.10_grid_wghts.nc'
        else:
            logger.error(f'Run {run} not supported for {model}.\nSupported run is: "3.25km".')
            
    elif model == 'MPAS':
        if run == '3.75km':
            weights = 'MPAS-3.75km_0.10_grid_wghts.nc'
        elif run == '7.5km':
            weights = 'MPAS-7.5km_0.10_grid_wghts.nc'
        else:
            logger.error(f'Run {run} not supported for {model}.\nSupported runs are: "3.75km" and "7.5km".')
            
    elif model == 'ARPEGE':
        if run == '2.5km':
            weights = 'ARPEGE-2.5km_0.10_grid_wghts.nc'
        else:
            logger.error(f'Run {run} not supported for {model}.\nSupported run is: "2.5km".')
    
    elif model == 'ERA5':
        grid_dir = '/mnt/lustre02/work/mh1126/m300773/DYAMOND/ERA5'
        weights = 'ERA5-31.0km_0.10_grid_wghts.nc'
    # other models...
    else:
        logger.error('The model specified for horizontal interpolation does not exist or has not been implemented yet.') 
        return None
    
    path2weights = os.path.join(grid_dir, weights)
    if not os.path.isfile(path2weights):
        logger.warning('Warning: There are no pre-calculated weights for this model run and target grid yet.')

    return path2weights

def get_path2heightfile(model, grid_res=0.1, **kwargs):
    """ Returns path to file containing geometrical heights corresponding to model levels for a given model.
   
    Parameters:
        model (str): name of model
        grid_res (num): resolution of grid in degrees
    """
    gridname = str(grid_res).ljust(4, '0')
    return f'/mnt/lustre02/work/mh1126/m300773/DYAMOND/{model}/{model}-{gridname}deg_heights.nc'

def get_path2targetheightfile(model, data_dir, **kwargs):
    """
    """

    targetheightfile = f'{data_dir}/{model}/target_height.nc'
    
    return targetheightfile

def get_path2z0file(model, run, **kwargs):
    """
    """
    if model == 'FV3':
        path2z0file = f'/mnt/lustre02/work/mh1126/m300773/DYAMOND/{model}/{model}-{run}_OROG_sea_estimated_trop.nc'
    else:
        path2z0file = f'/mnt/lustre02/work/mh1126/m300773/DYAMOND/{model}/{model}-{run}_OROG_trop.nc'
    
    return path2z0file

def get_path2landmask(lonlatbox, **kwargs):
    """ Returns path to file containing a land mask.
    """
    if lonlatbox == [-180, 180, -30, 30]:
        latlonstr = ''
    else:
        latlonstr = f'_{lonlatbox[0]}_{lonlatbox[1]}_{lonlatbox[2]}_{lonlatbox[3]}'
        
    return f'/mnt/lustre02/work/mh1126/m300773/DYAMOND/ICON/land_mask{latlonstr}.nc'

def get_interpolationfilelist(models, runs, variables, time_period, temp_dir, grid_res, **kwargs):
    """ Returns list of all raw output files from a specified DYAMOND model run corresponding to a given
    time period and given variables. A list of filenames for output files needed e.g. for
    horizontal interpolation is also returned.
    
    Parameters:
        model (str): name of model
        run (str): name of model run
        variables (list of str): list of variable names
        time_period (list of str): list containing start and end of time period in the format YYYY-mm-dd
        temp_dir (str): path to directory for output files
    """
    
    time = pd.date_range(time_period[0], time_period[1], freq='1D')
    
    raw_files = []
    out_files = []
    options = []
    weights = []
    grids = []
    
    for model, run in zip(models, runs):
        print(model)
        print(run)
        varnames = get_modelspecific_varnames(model)

        if model == 'ICON':
            # dictionary containing endings of filenames containing the variables
            var2suffix = {
                'TEMP': 'atm_3d_t_ml_',
                'QV': 'atm_3d_qv_ml_',
                'PRES': 'atm_3d_pres_ml_',
                'IWV': 'atm1_2d_ml_',
                'QI': 'atm_3d_tot_qi_dia_ml_',
                'OLR': 'atm_2d_avg_ml_',
                'QC': 'atm_3d_tot_qc_dia_ml_',
                'W500': 'atm_omega_3d_pl_',
                'W': 'atm_3d_w_ml_',
                'STOA': 'atm_2d_avg_ml_',
                'PREC': 'atm2_2d_ml_',
                'OLRC': '-',
                'STOAC': '-',
                'OMEGA': '-'
                    }

            for var in variables:
                # filenames of raw files, grid weights and the output file
                suffix = var2suffix[var]
                varname = varnames[var]
                if (run=='5.0km_1'):
                    stem   = '/work/ka1081/DYAMOND/ICON-5km/nwp_R2B09_lkm1006_{}'.format(suffix)
                elif (run=='5.0km_2'):
                    stem   = '/work/ka1081/DYAMOND/ICON-5km_2/nwp_R2B09_lkm1013_{}'.format(suffix)
                elif (run=='2.5km'):
                    stem   = '/work/ka1081/DYAMOND/ICON-2.5km/nwp_R2B10_lkm1007_{}'.format(suffix)
                elif (run == '2.5km_winter'):
                    stem = '/mnt/lustre02/work/mh1126/m300773/DYAMONDwinter/ICON-2.5km/nwp_R2B10_lkm1007_{}'.format(suffix)
                else:
                    print (f'Run {run} not supported for {model}.\nSupported runs are: "5.0km_1", "5.0km_2", "2.5km".')
                    return None

                for i in np.arange(time.size):
                    raw_file = stem + time[i].strftime("%Y%m%d") + 'T000000Z.grb'
                    time_str = time[i].strftime("%m%d")
                    out_file = f'{model}-{run}_{var}_{time_str}_hinterp.nc'
                    out_file = os.path.join(temp_dir, out_file)

                    raw_files.append(raw_file)
                    out_files.append(out_file)
                    if var == 'OLR' or var == 'IWV' or var == 'W500':
                        options.append(f'-chname,{varname},{var} -selvar,{varname} -seltimestep,1/96/12')
                    else:
                        options.append(f'-chname,{varname},{var} -selvar,{varname}')
                    weights.append(get_path2weights(model, run, grid_res))
                    grids.append(get_path2grid(grid_res))

        elif model == 'NICAM':
            
            # dictionary containing filenames containing the variables
            var2filename = {
                'TEMP': 'ms_tem.nc',
                'QV': 'ms_qv.nc',
                'PRES': 'ms_pres.nc',
                'QI': 'ms_qi.nc',
                'IWV': 'sa_vap_atm.nc',
                'OLR': 'sa_lwu_toa.nc',
                'QC': 'ms_qc.nc',
                'W': 'ms_w.nc',
                'SUTOA': 'ss_swu_toa.nc',
                'SDTOA': 'ss_swd_toa.nc',
                'OLRC': 'ss_lwu_toa_c.nc',
                'STOA': '-',
                'STOAC': '-',
                'OMEGA': '-'
            }

            for var in variables:
                # paths to raw files
                filename = var2filename[var]
                varname = varnames[var]
                if (run=='3.5km'):
                    stem   = '/work/ka1081/DYAMOND/NICAM-3.5km'
                elif (run=='7.0km'):
                    stem   = '/work/ka1081/DYAMOND/NICAM-7km'
                else:
                    print (f'Run {run} not supported for {model}.\nSupported runs are: "3.5km" and "7.0km".')
                    exit

                # append filenames for this variable to raw_files and out_files
                for i in np.arange(time.size):
                    dayfolder = glob.glob(os.path.join(stem, time[i].strftime("%Y%m%d")+'*'))[0]
                    raw_file = os.path.join(dayfolder, filename)
                    time_str = time[i].strftime("%m%d")
                    out_file = f'{model}-{run}_{var}_{time_str}_hinterp.nc'
                    out_file = os.path.join(temp_dir, out_file)

                    raw_files.append(raw_file)
                    out_files.append(out_file)
                    if var in ['OLR', 'IWV', 'OLRC', 'SUTOA', 'SDTOA']:
                        options.append(f'-chname,{varname},{var} -selvar,{varname} -seltimestep,12/96/12')
                    else:
                        options.append(f'-chname,{varname},{var} -selvar,{varname}')
                    weights.append(get_path2weights(model, run, grid_res))
                    grids.append(get_path2grid(grid_res))

        elif model == 'GEOS':
            var2dirname = {
                'TEMP': 'T',
                'QV': 'QV',
                'PRES': 'P', 
                'H': 'H',
                'QI': 'QI',
                'IWV': 'asm',
                'OLR': 'flx',
                'OLRC': 'flx',
                'QC': 'QL',
                'W': 'W',
                'STOA': 'flx',
                'STOAC': 'flx',
                'OMEGA': '-'
            }
            # GEOS output is one file per time step (3-hourly)
            for var in variables:
                varname = var2dirname[var]
                varname_infile = varnames[var]
                if run == '3.0km':
                    if var in ['OLR', 'STOA', 'OLRC', 'STOAC']:
                        stem = f'/mnt/lustre02/work/ka1081/DYAMOND/GEOS-3km/tavg/tavg_15mn_2d_{varname}_Mx' 
                    elif var == 'IWV':
                        stem = f'/mnt/lustre02/work/ka1081/DYAMOND/GEOS-3km/inst/inst_15mn_2d_{varname}_Mx'
                    else:
                        stem = f'/mnt/lustre02/work/ka1081/DYAMOND/GEOS-3km/inst/inst_03hr_3d_{varname}_Mv'
                else:
                    print (f'Run {run} not supported for {model}.\nSupported runs are: "3.0km".')  

                for i in np.arange(time.size):
                    for h in np.arange(0, 24, 3):
                        date_str = time[i].strftime("%Y%m%d")
                        hour_str = f'{h:02d}'
                        if var in ['OLR', 'STOA', 'OLRC', 'STOAC']:
                            hour_file = f'DYAMOND.tavg_15mn_2d_flx_Mx.{date_str}_{hour_str}00z.nc4'
                        elif var == 'IWV':
                            hour_file = f'DYAMOND.inst_15mn_2d_asm_Mx.{date_str}_{hour_str}00z.nc4'
                        else:
                            hour_file = f'DYAMOND.inst_03hr_3d_{varname}_Mv.{date_str}_{hour_str}00z.nc4'
                        opt = f'-chname,{varname_infile},{var} -selvar,{varname_infile}'
                        hour_file = os.path.join(stem, hour_file)
                        date_str = time[i].strftime("%m%d")
                        out_file = f'{model}-{run}_{var}_{date_str}_{hour_str}_hinterp.nc'
                        out_file = os.path.join(temp_dir, out_file)
                        raw_files.append(hour_file)
                        out_files.append(out_file)
                        options.append(opt)
                        weights.append(get_path2weights(model, run, grid_res))
                        grids.append(get_path2grid(grid_res))
    #        for var in variables:
    #            if run == '3.0km' or run == '3.0km-MOM':
    #                stem = f'/mnt/lustre02/work/mh1126/m300773/DYAMOND/GEOS'
    #            else:
    #                print (f'Run {run} not supported for {model}.\nSupported runs are: "3.0km" and "3.0km-MOM".')    
    #            for i in np.arange(time.size):
    #                date_str = time[i].strftime("%m%d")
    #                day_file = f'GEOS-{run}_{var}_{date_str}.nc'
    #                day_file = os.path.join(stem, day_file)
    #                temp = f'{model}-{run}_{var}_{date_str}_hinterp.nc'
    #                out_file = os.path.join(temp_dir, temp)
    #                raw_files.append(day_file)
    #                out_files.append(out_file)

        elif model == 'IFS':
            var2varnumber = {
                'TEMP': 130,
                'QV': 133,
                'SURF_PRES': 152, 
                'QI': 247,
                'OLR': 179,
                'IWV': 137,
                'QC': 246,
                'W': 120,
                'STOA': 178,
                'OLRC': 209, 
                'STOAC': 208,
                'OMEGA': '-',
                'GH': 'FI'
            }
            var2variablename = {
                'TEMP': 'T',
                'QV': 'QV',
                'SURF_PRES': 'lnsp',
                'IWV': 'tcwv',#
                'QI': 'param84.1.0', 
                'QC': 'param83.1.0',
                'W': 'param120.128.192',
                'OLR': 'ttr',
                'OLRC': 'ttrc',
                'STOA': 'tsr',
                'STOAC': 'tsrc',
                'PRES': '-',
                'OMEGA': '-',
                'GH': 'FI'
            }
    #        var2unit = {
    #           'TEMP': 'K',
    #            'QV': 'kg kg^-1',
    #            'SURF_PRES': 'Pa',
    #            'QI': 'kg kg^-1',
    #            'OLR': 'W m^-2',
    #            'IWV': 'kg m^-2'
    #        }

            for var in variables:
                #option = f'-chname,var{var2varnumber[var]},{var}'
                option = f'-chname,{var2variablename[var]},{var}'
                for i in np.arange(time.size):
                    for h in np.arange(0, 24, 3):
                        date_str = time[i].strftime("%m%d")
                        hour_str = f'{h:02d}'
                        hour_file = f'{model}-{run}_{var}_{date_str}_{hour_str}.nc'
                        out_file = f'{model}-{run}_{var}_{date_str}_{hour_str}_hinterp.nc'
                        hour_file = os.path.join(temp_dir, hour_file)
                        out_file = os.path.join(temp_dir, out_file)
                        raw_files.append(hour_file)
                        out_files.append(out_file)
                        options.append(option)
                        weights.append(get_path2weights(model, run, grid_res))
                        grids.append(get_path2grid(grid_res))

        elif model == 'SAM':
            ref_date = pd.Timestamp('2016-08-01-00')
            timeunit_option = '-settunits,days' 
            grid_option = '-setgrid,/mnt/lustre02/work/ka1081/DYAMOND/SAM-4km/OUT_2D/DYAMOND_9216x4608x74_7.5s_4km_4608_0000002400.CWP.2D.nc'
            var2filename = {
                'TEMP': '_TABS',
                'QV': '_QV',
                'PRES': '_PP',
                'QI': '_QI',
                'IWV': '.PW.2D',
                'OLR': '.LWNTA.2D',
                'QC': '_QC',
                'W': '_W',
                'STOA': '.SWNTA.2D',
                'OLRC': '-',
                'STOAC': '-',
                'OMEGA': '-'
            }

            for var in variables:
                varname = varnames[var]
                if var in ['OLR', 'STOA', 'IWV']:
                    stem = '/mnt/lustre02/work/ka1081/DYAMOND/SAM-4km/OUT_2D'
                else:
                    stem = '/mnt/lustre02/work/ka1081/DYAMOND/SAM-4km/OUT_3D'
                for i in np.arange(time.size):
                    for h in np.arange(0, 24, 3):
                        date_str = time[i].strftime('%Y-%m-%d')
                        hour_str = f'{h:02d}'

                        chname_option = f'-chname,{varname},{var}'
                        timeaxis_option = f'-settaxis,{date_str},{hour_str}:00:00,3h'
                        option = ' '.join([chname_option, timeaxis_option, timeunit_option, grid_option])

                        timestamp = pd.Timestamp(f'{date_str}-{hour_str}')
                        secstr = int((timestamp - ref_date).total_seconds() / 7.5)
                        secstr = f'{secstr:010}'
                        hour_file = f'DYAMOND_9216x4608x74_7.5s_4km_4608_{secstr}{var2filename[var]}.nc'
                        hour_file = os.path.join(stem, hour_file)
                        date_str = time[i].strftime("%m%d")
                        out_file = f'{model}-{run}_{var}_{date_str}_{hour_str}_hinterp.nc'
                        out_file = os.path.join(temp_dir, out_file)

                        raw_files.append(hour_file)
                        out_files.append(out_file)
                        options.append(option)          
                        weights.append(get_path2weights(model, run, grid_res))
                        grids.append(get_path2grid(grid_res))

        elif model == 'UM':
            stem = '/mnt/lustre02/work/ka1081/DYAMOND/UM-5km'

            var2dirname = {
                'TEMP': 'ta',
                'QV': 'hus',
                'PRES': 'phalf',
                'IWV': 'prw',
                'QI': 'cli',
                'OLR': 'rlut',
                'QC': 'clw',
                'W': 'wa',
                'SDTOA': 'rsdt',
                'SUTOA': 'rsut',
                'STOA': '-',
                'OLRC': '-',
                'STOAC': '-',
                'OMEGA': '-'
            }

            for var in variables:
                varname = varnames[var]
                for i in np.arange(time.size):
                    date_str = time[i].strftime('%Y%m%d')
                    varstr = var2dirname[var]

                    if var == 'IWV':
                        opt = f'-chname,{varname},{var} -selvar,{varname} -seltimestep,12/96/12'
                        day_file = f'{varstr}_15min_HadGEM3-GA71_N2560_{date_str}.nc'
                    elif var in ['OLR', 'SDTOA', 'SUTOA']:
                        opt = f'-chname,{varname},{var} -selvar,{varname} -seltimestep,3/24/3'
                        day_file = f'{varstr}_1hr_HadGEM3-GA71_N2560_{date_str}.nc'
                    else:
                        opt = f'-chname,{varname},{var} -selvar,{varname}'
                        day_file = f'{varstr}_3hr_HadGEM3-GA71_N2560_{date_str}.nc'

                    day_file = os.path.join(stem, varstr, day_file)

                    date_str = time[i].strftime('%m%d')
                    out_file = f'{model}-{run}_{var}_{date_str}_hinterp.nc'
                    out_file = os.path.join(temp_dir, out_file)

                    raw_files.append(day_file)
                    out_files.append(out_file)
                    options.append(opt)
                    weights.append(get_path2weights(model, run, grid_res))
                    grids.append(get_path2grid(grid_res))

        elif model == 'FV3':
            if run == '3.25km':
                stem = '/mnt/lustre02/work/ka1081/DYAMOND/FV3-3.25km'
            else: 
                print (f'Run {run} not supported for {model}.\nSupported run is "3.25km".')

            var2filename = {
                'TEMP': 'temp',
                'QV': 'qv',
                'PRES': 'pres',
                'QI': 'qi',
                'IWV': 'intqv',
                'OLR': 'flut',
                'W': 'w',
                'QC': 'ql',
                'SDTOA': 'fsdt',
                'SUTOA': 'fsut',
                'STOA': '-',
                'OLRC': '-',
                'STOAC': '-',
                'OMEGA': '-'
            }

            target_time_3h = pd.date_range(time_period[0]+' 3:00:00', pd.Timestamp(time_period[1]+' 0:00:00')+pd.DateOffset(1), freq='3h')
            target_time_15min = pd.date_range(time_period[0]+' 3:00:00', pd.Timestamp(time_period[1]+' 0:00:00')+pd.DateOffset(1), freq='3h')
            time = pd.date_range("2016-08-10", "2016-09-08", freq='1D')
            time_15min = pd.date_range("2016-08-01 0:15:00", "2016-09-10 0:00:00", freq='15min')
            time_3h = pd.date_range("2016-08-01 3:00:00", "2016-09-10 0:00:00", freq='3h')
            
            for var in variables:
                print(var)
                varname = varnames[var]
                if var in ['IWV', 'OLR', 'SDTOA', 'SUTOA']:
                    for t in target_time_15min:
                        print(t)
                        if t < pd.Timestamp('2016-08-11 3:00:00'):
                            dir_name = '2016080100'
                        elif t < pd.Timestamp('2016-08-21 3:00:00'):
                            dir_name = '2016081100'
                        elif t < pd.Timestamp('2016-08-31 3:00:00'):
                            dir_name = '2016082100'
                        else:
                            dir_name = '2016083100'
                        timestep = np.mod(np.where(time_15min == t)[0][0], 960) + 1
                        hour_file = var2filename[var] + '_C3072_12288x6144.fre.nc'
                        hour_file = os.path.join(stem, dir_name, hour_file)
                        date_str = t.strftime('%m%d')
                        hour_str = t.strftime('%H')
                        out_file = f'{model}-{run}_{var}_{date_str}_{hour_str}_hinterp.nc'
                        out_file = os.path.join(temp_dir, out_file)
                        option = f'-chname,{varname},{var} -selvar,{varname} -seltimestep,{timestep}'
                        print(timestep)
                        print(out_file)
                        
                        raw_files.append(hour_file)
                        out_files.append(out_file)
                        options.append(option)
                        weights.append(get_path2weights(model, run, grid_res))
                        grids.append(get_path2grid(grid_res))
                else:
                    for t in target_time_3h:
                        print(t)
                        if t < pd.Timestamp('2016-08-11 3:00:00'):
                            dir_name = '2016080100'
                        elif t < pd.Timestamp('2016-08-21 3:00:00'):
                            dir_name = '2016081100'
                        elif t < pd.Timestamp('2016-08-31 3:00:00'):
                            dir_name = '2016082100'
                        else:
                            dir_name = '2016083100'
                        timestep = np.mod(np.where(time_3h == t)[0][0], 80) + 1
                        hour_file = var2filename[var] + '_C3072_12288x6144.fre.nc'
                        hour_file = os.path.join(stem, dir_name, hour_file)
                        date_str = t.strftime('%m%d')
                        hour_str = t.strftime('%H')
                        out_file = f'{model}-{run}_{var}_{date_str}_{hour_str}_hinterp.nc'
                        out_file = os.path.join(temp_dir, out_file)
                        option = f'-chname,{varname},{var} -selvar,{varname} -seltimestep,{timestep}'
                        print(timestep)
                        print(out_file)
                        
                        raw_files.append(hour_file)
                        out_files.append(out_file)
                        options.append(option)
                        weights.append(get_path2weights(model, run, grid_res))
                        grids.append(get_path2grid(grid_res))


        elif model == 'MPAS':
            for var in variables:
                varname = varnames[var]
                for i in np.arange(time.size):
                    for h in np.arange(0, 24, 3):
                        date_str = time[i].strftime("%m%d")
                        hour_str = f'{h:02d}'
                        hour_file = f'{model}-{run}_{var}_{date_str}_{hour_str}.nc'
                        hour_file = os.path.join(temp_dir, hour_file)
                        out_file = f'{model}-{run}_{var}_{date_str}_{hour_str}_hinterp.nc'
                        out_file = os.path.join(temp_dir, out_file)
                        option = f'-chname,{varname},{var} -selvar,{varname}'
                        raw_files.append(hour_file)
                        out_files.append(out_file)
                        options.append(option)
                        weights.append(get_path2weights(model, run, grid_res))
                        grids.append(get_path2grid(grid_res))

        elif model == 'ARPEGE':
            preprocessing_path = '/mnt/lustre02/work/um0878/users/tlang/work/dyamond/processing/preprocessing_ARPEGE'
            griddesfile = os.path.join(preprocessing_path, 'griddes.arpege1')
            for var in variables:
                varname = varnames[var]
                for i in np.arange(time.size):
                    if time[i].day == 10:
                        hours = np.arange(3, 22, 3)
                    else:
                        hours = np.arange(3, 25, 3)
                    for h in hours:
                        year_str = time[i].strftime("%Y")
                        date_str = time[i].strftime("%m%d")
                        hour_str = f'{h:02d}'
                        hour_file = f'{year_str}{date_str}{hour_str}_{var}.gp'
                        hour_file = os.path.join(temp_dir, hour_file)
                        #ändern!
                        if h == 24:
                            hour_str_out = '00'
                            time_out = time[i] + pd.Timedelta('1d')
                            date_str_out = time_out.strftime("%m%d")
                        else:
                            hour_str_out = hour_str
                            date_str_out = date_str
                        out_file = f'{model}-{run}_{var}_{date_str_out}_{hour_str_out}_hinterp.nc'
                        out_file = os.path.join(temp_dir, out_file)
                        option = f'-setgrid,{griddesfile} -setgridtype,regular -chname,{varname},{var}'
                        raw_files.append(hour_file)
                        out_files.append(out_file)
                        options.append(option)
                        weights.append(get_path2weights(model, run, grid_res))
                        grids.append(get_path2grid(grid_res))
        
        elif model == 'ERA5':
            var2variablename = {
                'TEMP': 'T',
                'QV': 'QV',
                'SURF_PRES': 'var134',
                'QI': 'param84.1.0', 
                'QC': 'param83.1.0',
                'OMEGA': 'OMEGA'
            }
            for var in variables:
                option = f'-seltimestep,1/24/3 -chname,{var2variablename[var]},{var}'
                for i in np.arange(time.size):
                    date_str = time[i].strftime("%m%d")
                    day_file = f'{model}-{run}_{var}_{date_str}.nc'
                    out_file = f'{model}-{run}_{var}_{date_str}_hinterp.nc'
                    day_file = os.path.join(temp_dir, day_file)
                    out_file = os.path.join(temp_dir, out_file)
                    raw_files.append(day_file)
                    out_files.append(out_file)
                    options.append(option)
                    weights.append(get_path2weights(model, run, grid_res))
                    grids.append(get_path2grid(grid_res))
        
        else:
            logger.error('The model specified for horizontal interpolation does not exist or has not been implemented yet.') 
            return None
              
    return raw_files, out_files, weights, grids, options
                
def get_preprocessingfilelist(models, runs, variables, time_period, temp_dir, **kwargs):
    """ Returns list of all raw output files from a specified DYAMOND model run corresponding to a given
    time period and given variables. A list of filenames for output files needed for
    pre-processing of these models is also returned.
    
    Parameters:
        model (str): name of model
        run (str): name of model run
        variables (list of str): list of variable names
        time_period (list of str): list containing start and end of time period in the format YYYY-mm-dd
        temp_dir (str): path to directory for output files
    """
    
    models_list = []
    infile_list = []
    tempfile_list = []
    outfile_list = []
    option_1_list = []
    option_2_list = []
    
    time = pd.date_range(time_period[0], time_period[1], freq='1D')


    
    for model, run in zip(models, runs):
    
        if model == 'IFS':
            # Filenames of IFS raw files contain a number corresponding to the hours since the 
            # start of the simulation (2016-08-01 00:00:00)
            # define reference time vector starting at 2016-08-01 00:00:00
            ref_time = pd.date_range('2016-08-01 00:00:00', '2018-09-10 00:00:00', freq='3h')
            # find the index where the reference time equals the specified start time and 
            # multiply by 3 (because the output is 3-hourly) to get the filename-number of the
            # first relevant file
            hour_start = np.where(ref_time == time[0])[0][0] * 3
            var2filename = {
                'TEMP': 'gg_mars_out_ml_upper_sh',
                'QV': 'mars_out_ml_moist',
                'SURF_PRES': 'gg_mars_out_sfc_ps_orog',
                'QI': 'mars_out_ml_moist',
                'QC': 'mars_out_ml_moist',
                'W': 'gg_mars_out_ml_upper_sh',
                'OLR': 'mars_out',
                'IWV': 'mars_out',
                'OLRC': 'mars_out',
                'STOA': 'mars_out',
                'STOAC': 'mars_out',
                'PRES': '-',
                'OMEGA': '-',
                'GH': 'gg_mars_out_sfc_ps_orog'
            }
            if run == '9.0km':
                var2filename['SURF_PRES'] = 'mars_out_sfc_ps_orog_gg'
                
            var2variablename = {
                'TEMP': 'T',
                'QV': 'QV',
                'SURF_PRES': 'lnsp',
                'IWV': 'tcwv',#
                'QI': 'param84.1.0', 
                'QC': 'param83.1.0',
                'W': 'param120.128.192',
                'OLR': 'ttr',
                'OLRC': 'ttrc',
                'STOA': 'tsr',
                'STOAC': 'tsrc',
                'PRES': '-',
                'OMEGA': '-',
                'GH': 'FI'
            }
            var2numzlevels = {
                'TEMP': 113,
                'QV': 113,
                'QI': 113,
                'QC': 113,
                'W':113,
                'SURF_PRES': 1,
                'OLR': 1,
                'IWV': 1,
                'STOA': 1,
                'OLRC': 1,
                'STOAC': 1,
                'PRES': '-',
                'OMEGA': '-',
                'GH': 1
            }


            if (run=='4.0km'):
                stem   = '/work/ka1081/DYAMOND/IFS-4km'
            elif (run=='9.0km'):
                stem   = '/work/ka1081/DYAMOND/IFS-9km'

            for var in variables:
                hour_con = hour_start - 3
                # option 1: variable name in file
                option_1 = f'{var2variablename[var]}'
                # option 2: number of vertical levels (not needed for OLR and IWV):
                if var in['OLR', 'STOA', 'OLRC', 'STOAC', 'IWV', 'GH']:
                    option_2 = ''
                else:
                    option_2 = f'{var2numzlevels[var]}'
                for i in np.arange(time.size):
                    for h in np.arange(0, 24, 3):
                        hour_con = hour_con + 3
                        filename = var2filename[var]
                        in_file = f'{filename}.{hour_con}'
                        in_file = os.path.join(stem, in_file)
                        if var in ['TEMP', 'W', 'GH'] or (var == 'SURF_PRES' and run == '4.0km'):
                            in_file = in_file+'.grib'

                        date_str = time[i].strftime("%m%d")
                        hour_str = f'{h:02d}'
                        temp_file = f'{model}-{run}_{var}_{date_str}_{hour_str}.grb'
                        out_file = f'{model}-{run}_{var}_{date_str}_{hour_str}.nc'
                        temp_file = os.path.join(temp_dir, temp_file)
                        out_file = os.path.join(temp_dir, out_file)

                        infile_list.append(in_file)
                        tempfile_list.append(temp_file)
                        outfile_list.append(out_file)
                        option_1_list.append(option_1)
                        option_2_list.append(option_2)
                        models_list.append('IFS')

        elif model == 'ERA5':
            stem = '/work/bk1099/data/'
            vars_2D = ['SURF_PRES']
            var2varid = {
                'TEMP': 130,
                'SURF_PRES': 134,
                'QV': 133,
                'QI': 247,
                'QC': 246,
                'OMEGA': 135,
                'OLR': 235040,
                'STOA': 235035
            }
            
            for var in variables:
                # option 1: variable given on spectral or Gaussian reduced grid
                if var in ['TEMP', 'OMEGA']:
                    option_1 = 'spectral'
                else:
                    option_1 = 'gaussian'

                # 2D variables: One file per month
                if var in vars_2D:
                    directory = 'sf00_1H'
                    option_2 = 'splitday'
                    
                    for i in np.arange(time.size):
                        if i == 0 or (i > 0 and time[i].month != time[i-1].month):
                            month_str = time[i].strftime("%m") 
                            filename = f'E5sf00_1H_{time[i].year}-{month_str}_{var2varid[var]}'
                            in_file = os.path.join(stem, directory, str(time[i].year), filename)
                            out_file = f'{model}-{run}_{var}_{month_str}'
                            out_file = os.path.join(temp_dir, out_file)
                            temp_file = ''
                            
                            infile_list.append(in_file)
                            tempfile_list.append(temp_file)
                            outfile_list.append(out_file)
                            option_1_list.append(option_1)
                            option_2_list.append(option_2)
                            models_list.append('ERA5')                            
                        
                # 3D variables: One file per day
                else:
                    directory = 'ml00_1H'
                    option_2 = 'copy'
                
                    for i in np.arange(time.size):
                        date_str = time[i].strftime("%m-%d")
                        filename = f'E5ml00_1H_{time[i].year}-{date_str}_{var2varid[var]}'
                        in_file = os.path.join(stem, directory, str(time[i].year), filename)
                        date_str = time[i].strftime("%m%d")
                        out_file = f'{model}-{run}_{var}_{date_str}.nc'
                        out_file = os.path.join(temp_dir, out_file)
                        temp_file = ''

                        infile_list.append(in_file)
                        tempfile_list.append(temp_file)
                        outfile_list.append(out_file)
                        option_1_list.append(option_1)
                        option_2_list.append(option_2)
                        models_list.append('ERA5')
                                
        elif model == 'MPAS':
            stem = '/work/ka1081/DYAMOND/MPAS-3.75km'
            var2filename = {
                'TEMP': 'history',
                'PRES': 'history',
                'QV': 'history',
                'QI': 'history',
                'QC': 'history',
                'W': 'history',
                'IWV': 'diag',
                'OLR': 'diag',
                'STOA': 'diag'
            }
            varnames = get_modelspecific_varnames(model)

            for var in variables:
                for i in np.arange(time.size):
                    for h in np.arange(0, 24, 3):
                        date_str = time[i].strftime("%Y-%m-%d")
                        hour_str = f'{h:02d}'
                        in_file = f'{var2filename[var]}.{date_str}_{hour_str}.00.00.nc'
                        date_str = time[i].strftime("%m%d")
                        temp_file = f'{model}-{run}_{var}_{date_str}_{hour_str}_1.nc'
                        out_file = f'{model}-{run}_{var}_{date_str}_{hour_str}.nc'
                        in_file = os.path.join(stem, in_file)
                        temp_file = os.path.join(temp_dir, temp_file)
                        out_file = os.path.join(temp_dir, out_file)
                        option_selvar = varnames[var]

                        infile_list.append(in_file)
                        tempfile_list.append(temp_file)
                        outfile_list.append(out_file)
                        option_1_list.append(option_selvar)
                        option_2_list.append('')
                        models_list.append('MPAS')
#        else:
#            logger.error('The model specified for preprocessing does not exist or has not been implemented yet.')
        
    return models_list, infile_list, tempfile_list, outfile_list, option_1_list, option_2_list
                    
def get_preprocessing_ARPEGE_1_filelist(variables, time_period, temp_dir, **kwargs):
    """ Returns filelist needed for preprocessing of ARPEGE raw output files.
    
    Parameters:
        preprocess_dir (str): path to directory where preprocessing is done 
            (output can only be written the same directory)
        variables (list of str): list of variable names
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
    """
    #TODO: different parameter codes for some days (2D variables)
    #TODO: not all model levels included in 3D variables for 20180810 24:00
    
    time = pd.date_range(time_period[0], time_period[1], freq='1D')

    infile_3D_list = []
    infile_2D_list = []
    outfileprefix_list = []
    merge_list_3D = [] #verschachtelte Liste   
    tempfile_list_3D = []    
    filelist_2D = []    
    tempfile_list_2D = []
        
    dyamond_dir = '/work/ka1081/DYAMOND/ARPEGE-NH-2.5km'
    
    variables_2D = ['SURF_PRES', 'OLR', 'STOA']
    levels = np.arange(16, 76).astype(int)
    var2code = {
        'TEMP': '0.0.0',
        'QV': '0.1.0',
        'QI': '0.1.84',
        'QC': '0.1.83',
        'W': '0.2.9',
        'OLR': '0.5.5',
        'STOA': '0.4.9',
        'SURF_PRES': '0.3.0',
        'GH': '0.3.4'
    }
    
    var2t = {
        'TEMP': '119',
        'QV': '119',
        'QI': '119',
        'QC': '119',
        'W': '119',
        'OLR': '8',
        'STOA': '8',
        'SURF_PRES': '1',
        'GH': '119'
    }
    
    for i in np.arange(time.size):
        if time[i].day == 10:
            hours = np.arange(3, 22, 3)
        else:
            hours = np.arange(3, 25, 3)
          
        date_str = time[i].strftime('%Y%m%d')
        
        for h in hours:
            hour_str = f'{h:02d}'
            infile_3D = f'ARPNH3D{date_str}{hour_str}00'
            infile_2D = f'ARPNH2D{date_str}{hour_str}00'
            infile_3D = os.path.join(dyamond_dir, date_str, infile_3D)
            infile_2D = os.path.join(dyamond_dir, date_str, infile_2D)
            infile_3D_list.append(infile_3D)
            infile_2D_list.append(infile_2D)
            outfileprefix = date_str+hour_str
            outfileprefix = os.path.join(temp_dir, outfileprefix)
            outfileprefix_list.append(outfileprefix)
            merge_sublist = []
            tempfile_sublist_3D = []
            tempfile_sublist_2D = []
            file_sublist_2D = []
            for var in variables:
                code = var2code[var]
                tcode = var2t[var]
                if var not in variables_2D:
                    if var == 'GH':
                        mergefiles = [os.path.join(temp_dir, f'{date_str}{hour_str}.t{tcode}.l7500.grb.{code}.gp')]
                    else:
                        mergefiles = [os.path.join(temp_dir, f'{date_str}{hour_str}.t{tcode}.l{l}00.grb.{code}.gp')\
                                      for l in levels]
                    merge_sublist.append(mergefiles)
                    tempfile = os.path.join(temp_dir, f'{date_str}{hour_str}_{var}.gp')
                    tempfile_sublist_3D.append(tempfile)
                else:
                    file = os.path.join(temp_dir, f'{date_str}{hour_str}.t{tcode}.l000.grb.{code}.gp')
                    file_sublist_2D.append(file)
                    tempfile = os.path.join(temp_dir, f'{date_str}{hour_str}_{var}.gp')
                    tempfile_sublist_2D.append(tempfile)
            merge_list_3D.append(merge_sublist)
            tempfile_list_3D.append(tempfile_sublist_3D)
            tempfile_list_2D.append(tempfile_sublist_2D) 
            filelist_2D.append(file_sublist_2D)
        
    return infile_2D_list, infile_3D_list, outfileprefix_list, merge_list_3D, tempfile_list_3D, filelist_2D, tempfile_list_2D

    
def get_mergingfilelist(models, runs, variables, time_period, vinterp, temp_dir, data_dir, **kwargs):
    """ Returns a list of filenames of horizontally interpolated DYAMOND output needed for time merging.
    For each variable, the list contains a list of filenames. 
    
    Parameters:
        models (str): names of models
        runs (str): names of model runs
        variables (list of str): list of variables
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        vinterp (boolean): True if fields have already bin vertically interpolated
        temp_dir (str): path to directory with temporary files
        data_dir (str): path to directory to save files        
    """
    time = pd.date_range(time_period[0], time_period[1], freq='1D')
    start_date = time[0].strftime("%m%d")
    end_date = time[-1].strftime("%m%d")
    infile_list = []
    outfile_list = []
    
    v = 0
    for model, run in zip(models, runs):
        print(model)
        for var in variables:
            infile_list.append([])
            if vinterp == 1 and model in ['GEOS', 'IFS', 'FV3', 'ARPEGE', 'ERA5']:
                outfile_name = f'{model}-{run}_{var}_hinterp_vinterp_merged_{start_date}-{end_date}.nc'
            else:
                outfile_name = f'{model}-{run}_{var}_hinterp_merged_{start_date}-{end_date}.nc'
            
            if model == 'ERA5':
                outfile_name = os.path.join(data_dir, outfile_name)
            else:
                outfile_name = os.path.join(data_dir, model, outfile_name)
            outfile_list.append(outfile_name)

            if model == 'FV3' and not vinterp and var not in ['RH', 'H']:
                target_time = pd.date_range(time_period[0]+' 3:00:00', pd.Timestamp(time_period[1]+' 0:00:00')+pd.DateOffset(1), freq='3h')
                for t in target_time:
                    date_str = t.strftime('%m%d')
                    hour_str = t.strftime('%H')
                    infile_name = f'{model}-{run}_{var}_{date_str}_{hour_str}_hinterp.nc'
                    infile_name = os.path.join(temp_dir, infile_name)
                    infile_list[v].append(infile_name)
            else:
                for i in np.arange(time.size):
                    if not (model == 'ARPEGE' and time[i].month == 8 and time[i].day == 11):
                        date_str = time[i].strftime("%m%d")
                        if model == 'ARPEGE':
                            if vinterp and var not in ['OLR', 'STOA']:
                                for h in np.arange(0, 24, 3):
                                    if not (time[i].day == 12 and time[i].month == 8 and h == 0)\
                                    and not (time[i].day == 10 and time[i].month == 8 and h in [0, 15]):
                                        infile_name = f'{model}-{run}_{var}_hinterp_vinterp_{date_str}_{h:02d}.nc'
                                        infile_name = os.path.join(temp_dir, infile_name)
                                        infile_list[v].append(infile_name)                                    
                            else:
                                for h in np.arange(0, 24, 3):
                                    if not (time[i].day == 12 and time[i].month == 8 and h == 0)\
                                    and not (time[i].day == 10 and time[i].month == 8 and h in [0, 15]):
                                        infile_name = f'{model}-{run}_{var}_{date_str}_{h:02d}_hinterp.nc'
                                        infile_name = os.path.join(temp_dir, infile_name)
                                        infile_list[v].append(infile_name)

                        else:
                            if model in ['GEOS', 'IFS', 'FV3', 'ERA5'] and vinterp:
                                for h in np.arange(0, 24, 3):
                                    infile_name = f'{model}-{run}_{var}_hinterp_vinterp_{date_str}_{h:02d}.nc'
                                    infile_name = os.path.join(temp_dir, infile_name)
                                    infile_list[v].append(infile_name)

                            elif model in ['GEOS', 'IFS', 'MPAS', 'SAM'] or var in ['RH', 'WHL', 'H']:
                                for h in np.arange(0, 24, 3):
                                    infile_name = f'{model}-{run}_{var}_{date_str}_{h:02d}_hinterp.nc'
                                    infile_name = os.path.join(temp_dir, infile_name)
                                    infile_list[v].append(infile_name)
                            else:
                                infile_name = f'{model}-{run}_{var}_{date_str}_hinterp.nc'
                                infile_name = os.path.join(temp_dir, infile_name)
                                infile_list[v].append(infile_name)
            v += 1
     
    return infile_list, outfile_list

def get_averagingfilelist(models, runs, variables, data_dir, time_period, vinterp, **kwargs):
    """ Returns list of filenames of horizontally interpolated and merged as well as 
    list of filenames of horizontally interpolated, merged and temporally averaged 
    DYAMOND output files needed for time averaging. 
    
    Parameters:
        models (str): names of models
        runs (str): names of model runs
        variables (list of str): list of variables
        data_dir (str): path to directory to save files 
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd
    """
    time = pd.date_range(time_period[0], time_period[1], freq='1D')
    start_date = time[0].strftime("%m%d")
    end_date = time[-1].strftime("%m%d")
    infile_list = []
    outfile_list = []
    option_list = []
    
    for model, run in zip(models, runs):
        for var in variables:
            option = ('')
            if vinterp == 1 and (model == 'GEOS' or model == 'IFS' or model == 'FV3'):
                infile_name = f'{model}-{run}_{var}_hinterp_vinterp_merged_{start_date}-{end_date}.nc'
                outfile_name = f'{model}-{run}_{var}_hinterp_vinterp_timeaverage_{start_date}-{end_date}.nc'
            else:
                infile_name = f'{model}-{run}_{var}_hinterp_merged_{start_date}-{end_date}.nc'
                outfile_name = f'{model}-{run}_{var}_hinterp_timeaverage_{start_date}-{end_date}.nc'

            infile_name = os.path.join(data_dir, model.upper(), infile_name)
            outfile_name = os.path.join(data_dir, model.upper(), outfile_name)
            infile_list.append(infile_name)
            outfile_list.append(outfile_name)
            option_list.append(option)
    
    return infile_list, outfile_list, option_list
 
    
def get_sellonlatboxfilelist(models, runs, variables, data_dir, time_period, lonlatbox, vinterp, **kwargs):
    """ Returns list of filenames needed for the selection of a lat-lon box. Input files are horizontally interpolated
    temporally averaged fields. Output filenames contain boundaries of the lat-lon box.
    
    Parameters:
        models (str): list of model names
        runs (str): list of runs
        variables (list of str): list of variables
        data_dir (str): path to directory to save files 
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        lonlatbox (list): Boundaries of lon-lat box in the following order: [lonmin lonmax latmin latmax]
    """
    time = pd.date_range(time_period[0], time_period[1], freq='1D')
    start_date = time[0].strftime("%m%d")
    end_date = time[-1].strftime("%m%d")
    infile_list = []
    outfile_list = []
    lonlatstr = f'{lonlatbox[0]}_{lonlatbox[1]}_{lonlatbox[2]}_{lonlatbox[3]}'
    
    for model, run in zip(models, runs):
        for var in variables:
            option = ('')
            if (model == 'GEOS' or model == 'IFS' or model == 'FV3') and vinterp == 1:
                infile_name = f'{model}-{run}_{var}_hinterp_vinterp_timeaverage_{start_date}-{end_date}.nc'
                outfile_name = f'{model}-{run}_{var}_hinterp_vinterp_timeaverage_{start_date}-{end_date}_{lonlatstr}.nc'
            else:
                infile_name = f'{model}-{run}_{var}_hinterp_timeaverage_{start_date}-{end_date}.nc'
                outfile_name = f'{model}-{run}_{var}_hinterp_timeaverage_{start_date}-{end_date}_{lonlatstr}.nc'
            infile_name = os.path.join(data_dir, model.upper(), infile_name)
            outfile_name = os.path.join(data_dir, model.upper(), outfile_name)
            infile_list.append(infile_name)
            outfile_list.append(outfile_name)
        
    return infile_list, outfile_list
       

def get_vinterpolation_per_timestep_filelist(models, runs, variables, time_period, data_dir, num_timesteps, temp_dir, **kwargs):
    """ Returns list of filenames needed for the vertical interpolation which is done separately for 
    every timestep. The input files consist of one file per horizontally interpolated and merged model
    variable. Output files consist of one file per model variable and per timestep.
    
    Parameters:
        models (str): list of model names
        runs (str): list of runs
        variables (list of str): list of variables
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        data_dir (str): path to directory to save files
        temp_dir (str): path to directory with temporary files   
    """

    time = pd.date_range(time_period[0], time_period[1], freq='1D')
    start_date = time[0].strftime("%m%d")
    end_date = time[-1].strftime("%m%d")
    infile_list = []
    model_list = []
    run_list = []
    variable_list = []
    heightfile_list = []
    targetheightfile_list = []
    
    for model, run in zip(models, runs):
        heightfile = f'{model}-{run}_H_hinterp_merged_{start_date}-{end_date}.nc'
        heightfile = os.path.join(data_dir, model, heightfile)
        targetheightfile = get_path2targetheightfile(model, data_dir)

        for var in variables:
            infile = f'{model}-{run}_{var}_hinterp_merged_{start_date}-{end_date}.nc'
            infile = os.path.join(data_dir, model, infile)
            #infile_list.append(infile)
            
            for timestep in range(num_timesteps):
                model_list.append(model)
                run_list.append(run)
                variable_list.append(var)
                infile_list.append(infile)
                heightfile_list.append(heightfile)
                targetheightfile_list.append(targetheightfile)
            
    #models, runs, variables, infiles, heightfiles, targetheightfiles
    return model_list, run_list, variable_list, infile_list, heightfile_list, targetheightfile_list


def get_height_calculation_filelist(models, runs, time_period, data_dir, num_timesteps, temp_dir, lonlatbox, **kwargs):
    """ Returns list of filenames needed for the calculation of model level heights from model level
    pressure and temperature. Output files consist of one file for every timestep.
    
    Parameters:
        models (list of str): names of models
        runs (list of str): names of model runs
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        data_dir (str): path to directory to save files   
        num_timesteps (num): number of timesteps in input files
        temp_dir (str): path to directory for temporary output files
        lonlatbox (list of num): borders of lon-lat box to sample from [lonmin, lonmax, latmin, latmax]
         
    """
    time = pd.date_range(time_period[0], time_period[1], freq='1D')
    start_date = time[0].strftime("%m%d")
    end_date = time[-1].strftime("%m%d")
    
    presfile_list = []
    tempfile_list = []
    z0file_list = []
    model_list = []
    run_list = []
    
    for model, run in zip(models, runs):
        tempfile = f'{model}-{run}_TEMP_hinterp_merged_{start_date}-{end_date}.nc'
        tempfile = os.path.join(data_dir, model, tempfile)
        presfile = f'{model}-{run}_PRES_hinterp_merged_{start_date}-{end_date}.nc'
        presfile = os.path.join(data_dir, model, presfile)
        z0file = get_path2z0file(model, run)
        for t in range(num_timesteps):
            tempfile_list.append(tempfile)
            presfile_list.append(presfile)
            z0file_list.append(z0file)
            model_list.append(model)
            run_list.append(run)
   
    return model_list, run_list, presfile_list, tempfile_list, z0file_list
    
def get_rhcalculation_filelist(models, runs, time_period, num_timesteps, data_dir, **kwargs):
    """ Returns filelist needed to calculate the relative humidity for every timestep. Input files
    consist of three files containing horizontally interpolated and merged temperature, specific 
    humidity and pressure.
    
    Parameters:
        models (list of str): names of models
        runs (list of str): names of model runs
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        num_timesteps (num): number of timesteps in input files
        data_dir (str): path to directory to save files    
    """
    time = pd.date_range(time_period[0], time_period[1], freq='1D')
    start_date = time[0].strftime("%m%d")
    end_date = time[-1].strftime("%m%d")
    temp_files = []
    qv_files = []
    pres_files = []
    model_list = []
    run_list = []
    
    for model, run in zip(models, runs):
        temp_file = f'{model}-{run}_TEMP_hinterp_merged_{start_date}-{end_date}.nc'
        temp_file = os.path.join(data_dir, model, temp_file)
        pres_file = f'{model}-{run}_PRES_hinterp_merged_{start_date}-{end_date}.nc'
        pres_file = os.path.join(data_dir, model, pres_file)
        qv_file = f'{model}-{run}_QV_hinterp_merged_{start_date}-{end_date}.nc'
        qv_file = os.path.join(data_dir, model, qv_file)
        for timestep in range(num_timesteps):
            temp_files.append(temp_file)
            pres_files.append(pres_file)
            qv_files.append(qv_file)
            model_list.append(model)
            run_list.append(run)
    
    return model_list, run_list, temp_files, qv_files, pres_files

def get_wcalculation_filelist(models, runs, time_period, num_timesteps, data_dir, **kwargs):
    """ Returns filelist needed to calculate vertical velocity from pressure velocity for every timestep. 
    Input files consist of three files containing horizontally interpolated and merged temperature, 
    specific humidity and pressure.
    
    NOT NEEDED ANY MORE!!!
    
    Parameters:
        models (list of str): names of models
        runs (list of str): names of model runs
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        num_timesteps (num): number of timesteps in input files
        data_dir (str): path to directory to save files    
    """
    time = pd.date_range(time_period[0], time_period[1], freq='1D')
    start_date = time[0].strftime("%m%d")
    end_date = time[-1].strftime("%m%d")
    omega_files = []
    temp_files = []
    qv_files = []
    pres_files = []
    height_files = []
    model_list = []
    run_list = []
    
    for model, run in zip(models, runs):
        omega_file = f'{model}-{run}_OMEGA_hinterp_merged_{start_date}-{end_date}.nc'
        omega_file = os.path.join(data_dir, model, omega_file)        
        temp_file = f'{model}-{run}_TEMP_hinterp_merged_{start_date}-{end_date}.nc'
        temp_file = os.path.join(data_dir, model, temp_file)
        pres_file = f'{model}-{run}_PRES_hinterp_merged_{start_date}-{end_date}.nc'
        pres_file = os.path.join(data_dir, model, pres_file)
        qv_file = f'{model}-{run}_QV_hinterp_merged_{start_date}-{end_date}.nc'
        qv_file = os.path.join(data_dir, model, qv_file)
        height_file = f'{model}-{run}_H_hinterp_merged_{start_date}-{end_date}.nc'
        height_file = os.path.join(data_dir, model, height_file)
        for timestep in range(num_timesteps):
            omega_files.append(omega_file)
            temp_files.append(temp_file)
            pres_files.append(pres_file)
            height_files.append(height_file)
            qv_files.append(qv_file)
            model_list.append(model)
            run_list.append(run)
    
    return model_list, run_list, omega_files, temp_files, qv_files, pres_files, height_files

def get_interpolationtohalflevels_filelist(models, runs, time_period, variables, num_timesteps, data_dir, temp_dir, **kwargs):
    """ Return filelist needed for interpolation from full model levels to half levels.
    
    Parameters:
        models (list of str): names of models
        runs (list of str): names of model runs
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        variables (list of str): list of variable names
        data_dir (str): path to directory of input file
        temp_dir (str): path to directory for output files
    """
    time = pd.date_range(time_period[0], time_period[1]+'-21', freq='3h')
    start_date = time[0].strftime("%m%d")
    end_date = time[-1].strftime("%m%d")
    infile_list = []
    model_list = []
    run_list = []
    variable_list = []
    
    #outfiles = []
    for model, run in zip(models, runs):

        for var in variables:
            infile = f'{model}-{run}_{var}_hinterp_merged_{start_date}-{end_date}.nc'
            infile = os.path.join(data_dir, model, infile)
            for timestep in range(num_timesteps):
                model_list.append(model)
                run_list.append(run)
                variable_list.append(var)
                infile_list.append(infile)
                

                #infiles.append(infile)
                #outfile = f'{model}-{run}_{var}HL_{date_str}_{hour_str}_hinterp.nc'
                #outfile = os.path.join(temp_dir, outfile)
                #outfiles.append(outfile)
        
    return model_list, run_list, variable_list, infile_list

def get_netfluxcalculationfilelist(fluxes, models, runs, time_period, data_dir, **kwargs):
    """ Returns filelist to calculate net fluxes from upward and downward fluxes 
    
    Parameters:
        fluxes (list of str): Name of variables containing 1. downward, 2. upward and 3. net radiation fluxes
            ['SDTOA', 'SUTOA', 'STOA']
        models (list of str): names of models
        runs (list of str): names of model runs
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        data_dir (str): path to directory of input file
    """
    
    time = pd.date_range(time_period[0], time_period[1]+'-21', freq='3h')
    start_date = time[0].strftime("%m%d")
    end_date = time[-1].strftime("%m%d")
    
    infile_list = []
    tempfile_list = []
    outfile_list = []

    for model, run in zip(models, runs):
        infile_1 = f'{model}-{run}_{fluxes[0]}_hinterp_merged_{start_date}-{end_date}.nc'
        infile_2 = f'{model}-{run}_{fluxes[1]}_hinterp_merged_{start_date}-{end_date}.nc'       
        tempfile = f'{model}-{run}_{fluxes[0]}_{fluxes[1]}_hinterp_merged_{start_date}-{end_date}.nc'
        outfile = f'{model}-{run}_{fluxes[2]}_hinterp_merged_{start_date}-{end_date}.nc'
        infile_1 = os.path.join(data_dir, model, infile_1)
        infile_2 = os.path.join(data_dir, model, infile_2)
        infile_sublist = [infile_1, infile_2]
        tempfile = os.path.join(data_dir, model, tempfile)
        outfile = os.path.join(data_dir, model, outfile)
        infile_list.append(infile_sublist)
        tempfile_list.append(tempfile)
        outfile_list.append(outfile)
        
    return infile_list, tempfile_list, outfile_list    

def get_deaccumulationfilelist(models, runs, variables, time_period, data_dir, **kwargs):
    """ Returns filelist needed to deaccumulate radiation fields given as energy. 
    
    Parameters:
        models (list of str): names of models
        runs (list of str): names of model runs
        variables (list of str): list of variable names
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        data_dir (str): path to directory of input file
    """
    time = pd.date_range(time_period[0], time_period[1]+'-21', freq='3h')
    start_date = time[0].strftime("%m%d")
    end_date = time[-1].strftime("%m%d")
    
    model_list = []
    infile_list = []
    variable_list = []
    
    for model, run in zip(models, runs):
        for var in variables:
            infile = f'{model}-{run}_{var}_hinterp_merged_{start_date}-{end_date}.nc'
            infile = os.path.join(data_dir, model.upper(), infile)
        
            infile_list.append(infile)
            model_list.append(model)
            variable_list.append(var)
    
    return model_list, infile_list, variable_list

def get_samplefilelist(num_samples_tot, models, runs, variables, time_period, lonlatbox, data_dir, sample_days, experiment=None, day=None, **kwargs):
    """ Returns filelist needed to perform Monte Carlo Sampling of Profiles.
    
    Parameters:
        num_samples_tot (num): number of samples to draw
        models (list of str): names of models
        runs (list of str): names of model runs
        variables (list of str): list of variable names
        time_period (list of str): list containing start and end of time period as string 
            in the format YYYY-mm-dd 
        lonlatbox (list of ints): borders of lon-lat box to sample from [lonmin, lonmax, latmin, latmax]
        data_dir (str): path to directory of input file
        experiment (num): experiment number (if several experiments are performed), needed for output filename
    """  
    #model = models[0]
    #run = runs[0]
    variables_2D = ['OLR', 'OLRC', 'STOA', 'STOAC', 'IWV']
    time = pd.date_range(time_period[0], time_period[1], freq='1D')
    start_date_in = time[0].strftime("%m%d")
    end_date_in = time[-1].strftime("%m%d")
    if day is None:
        start_date_out = start_date_in
        end_date_out = end_date_in
    else:
        start_date_out = time[day].strftime("%m%d")
        end_date_out = time[day].strftime("%m%d")
        
    if lonlatbox[:2] == [-180, 180]:
        latlonstr = ''
    else:
        latlonstr = f'_{lonlatbox[0]}_{lonlatbox[1]}_{lonlatbox[2]}_{lonlatbox[3]}'
    if experiment is not None:
        expstr = f'_{str(experiment)}'
    else:
        expstr = ''
    if sample_days == 'all':
        sample_day_str = ''
    else:
        sample_day_str = '_'+sample_days
    
    model_list = []
    run_list = []
    infile_list = []
    outfile_list = []
    
    for model, run in zip(models, runs):
        model_list.append(model)
        run_list.append(run)
        infile_sublist = []
        outfile_sublist = []
        for var in variables:
            if model in ['ICON', 'MPAS'] and var == 'W':
                var = 'WHL'
            if model in ['IFS', 'GEOS', 'FV3', 'ARPEGE', 'ERA5'] and var not in variables_2D:
                file = f'{model}-{run}_{var}_hinterp_vinterp_merged_{start_date_in}-{end_date_in}.nc'
            else: 
                file = f'{model}-{run}_{var}_hinterp_merged_{start_date_in}-{end_date_in}.nc'
            file = os.path.join(data_dir, model, file)
            infile_sublist.append(file) 

        for var in variables + ['IWV', 'lon', 'lat', 'timestep']:
            outfile = f'{model}-{run}_{var}_sample_{num_samples_tot}_{start_date_out}-{end_date_out}{sample_day_str}{latlonstr}{expstr}.nc'
            outfile = os.path.join(data_dir, model, 'random_samples', outfile)
            outfile_sublist.append(outfile)
        infile_list.append(infile_sublist)
        outfile_list.append(outfile_sublist)
    
    return model_list, run_list, infile_list, outfile_list
    
def get_pressure_scaling_parameters(model):
    """
    """
    if model in ['IFS', 'ERA5']:
        
        a = np.array([0, 0, 3.757813, 22.83594, 62.78125, 122.1016, 202.4844, 302.4766, 424.4141, 568.0625, 734.9922, 926.5078, 1143.25, 1387.547, 1659.477, 1961.5, 2294.242, 2659.141, 3057.266, 3489.234, 3955.961, 4457.375, 4993.797, 5564.383, 6168.531, 6804.422, 7470.344, 8163.375, 8880.453, 9617.516, 10370.18, 11133.3, 11901.34, 12668.26, 13427.77, 14173.32, 14898.45, 15596.7, 16262.05, 16888.69, 17471.84, 18006.93, 18489.71, 18917.46, 19290.23, 19608.57, 19874.03, 20087.09, 20249.51, 20361.82, 20425.72, 20442.08, 20412.31, 20337.86, 20219.66, 20059.93, 19859.39, 19620.04, 19343.51, 19031.29, 18685.72, 18308.43, 17901.62, 17467.61, 17008.79, 16527.32, 16026.12, 15508.26, 14975.62, 14432.14, 13881.33, 13324.67, 12766.87, 12211.55, 11660.07, 11116.66, 10584.63, 10065.98, 9562.683, 9076.4, 8608.525, 8159.354, 7727.412, 7311.869, 6911.871, 6526.947, 6156.074, 5798.345, 5452.991, 5119.895, 4799.149, 4490.817, 4194.931, 3911.49, 3640.468, 3381.744, 3135.119, 2900.391, 2677.348, 2465.771, 2265.432, 2076.096, 1897.519, 1729.449, 1571.623, 1423.77, 1285.61, 1156.854, 1037.201, 926.3449, 823.9678, 729.7441, 643.3399, 564.4135, 492.616, 427.5925, 368.9824, 316.4207, 269.5396, 227.9689, 191.3386, 159.2794, 131.4255, 107.4157, 86.89588, 69.52058, 54.95546, 42.87924, 32.98571, 24.98572, 18.60893, 13.60542, 9.746966, 6.827977, 4.666084, 3.102241, 2.000365])
        
        b = np.array([1, 0.99763, 0.995003, 0.991984, 0.9885, 0.984542, 0.980072, 0.975078, 0.969513, 0.963352, 0.95655, 0.949064, 0.94086, 0.931881, 0.922096, 0.911448, 0.8999, 0.887408, 0.873929, 0.859432, 0.843881, 0.827256, 0.809536, 0.790717, 0.770798, 0.749797, 0.727739, 0.704669, 0.680643, 0.655736, 0.630036, 0.603648, 0.576692, 0.549301, 0.521619, 0.4938, 0.466003, 0.438391, 0.411125, 0.384363, 0.358254, 0.332939, 0.308598, 0.285354, 0.263242, 0.242244, 0.222333, 0.203491, 0.185689, 0.16891, 0.153125, 0.138313, 0.124448, 0.111505, 0.099462, 0.088286, 0.077958, 0.068448, 0.059728, 0.051773, 0.044548, 0.038026, 0.032176, 0.026964, 0.022355, 0.018318, 0.014816, 0.011806, 0.009261, 0.007133, 0.005378, 0.003971, 0.002857, 0.001992, 0.001353, 0.00089, 0.000562, 0.00034, 0.000199, 0.000112, 0.000059, 0.000024, 0.000007, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        if model == 'IFS':
            return a[0:113], b[0:113]
        elif model == 'ERA5':
            return a, b
        
    elif model == 'ARPEGE':
        a = np.array([1222.8013005419998, 1151.081140022, 1047.558699711, 916.5939116075, 770.0440539174999, 622.9077824315, 486.6332968815, 368.10595326199996, 270.203518668, 192.8273379845, 133.998038074, 90.79660478299999, 60.0589440985, 38.817746126, 24.5329218185, 15.1694680875, 9.1799852255, 5.437809149, 3.152733994, 1.7886128665, 0.9924604774999999, 0.5382769345, 0.2851399245, 0.147395167, 0.07427774100000001, 0.036453698, 0.0174054565, 0.008077108, 0.0036395365000000002, 0.001591072, 0.000674332, 0.00027691500000000003, 0.0001101345, 4.24125e-05, 1.5813e-05, 5.7085e-06, 1.996e-06, 6.760000000000001e-07, 2.22e-07, 7.05e-08, 2.15e-08, 6.5e-09, 2e-09, 5e-10, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]) #surface pressure?
        b = np.array([0.033519443, 0.043141488500000005, 0.0538864905, 0.065179446, 0.07655079000000001, 0.087755708, 0.098617487, 0.109037617, 0.11898940250000001, 0.1285059975, 0.1376670545, 0.1465862685, 0.15540085, 0.1642631035, 0.173333806, 0.1827769155, 0.19275514300000002, 0.2034260255, 0.2149382755, 0.2274282975, 0.241016859, 0.2558059515, 0.271875918, 0.289282932, 0.3080569055, 0.3281999095, 0.34968516949999995, 0.3724566975, 0.39642960250000003, 0.4214911215, 0.447502403, 0.47430106299999997, 0.501704532, 0.529514206, 0.5575204085000001, 0.585508159, 0.6132637475, 0.6405821055, 0.6672749535, 0.6931797075, 0.7181691185000001, 0.7421616105, 0.7651322825, 0.787124532, 0.808262252, 0.828762547, 0.848636437, 0.8675177970000001, 0.8851629525, 0.9015718930000001, 0.916744609, 0.9306810925, 0.9433813345, 0.9548453275, 0.9650730654999999, 0.974064542, 0.981819751, 0.988338689, 0.9936213524999999, 0.9979768075]) #surface pressure?

    return a, b
        
def latlonheightfield_to_netCDF(height, latitude, longitude, field, varname, varunit, outname, time_dim=False, time_var=None, overwrite=True):
    """ Saves a field with dimensions (height, latitude, longitude) to a NetCDF file.
    
    Parameters:
        height (1D-array, dimension nheight): height levels in m
        latitude (1D-array, dimension nlat): latitudes in deg North
        longitude (1D-array, dimension nlon): longitudes in deg East
        field (3D-array, dimensions (nheight, nlat, nlon)): field with variable to save
        varname (string): name of variable (e.g. 't' or 'q')
        varunit (string): unit of variable
        outname (string): name for output file
        time (bool): if True, a dimension for time (with length 1) is added
        overwrite (boolean): if True, exisiting files with the same filename are overwritten
    """
    if (os.path.isfile(outname)) and overwrite:
        os.remove(outname)
    elif (os.path.isfile(outname)) and overwrite==False:
        print('File {} exists. Not overwriting.'.format(outname))
        return

    with Dataset(outname, 'w') as f:
        lat = f.createDimension('lat', len(latitude))
        lon = f.createDimension('lon', len(longitude))
        zlev = f.createDimension('zlev', len(height))

        lat = f.createVariable('lat','f4',('lat',))
        lon = f.createVariable('lon','f4',('lon',))
        zlev = f.createVariable('zlev','f4',('zlev',))
        
        if time_dim:
            time = f.createDimension('time', 1)
        if time_var is not None:
            time = f.createVariable('time', 'f4', ('time',))

        lat.units = 'degrees north'
        lon.units= 'degrees east'
        zlev.units = 'm'

        lat[:] = latitude[:]
        lon[:] = longitude[:]
        zlev[:] = height[:]
        if time_var is not None:
            time.units = 'hours'
            time = time_var
        
        if time_dim:
            v = f.createVariable(varname,'f4',dimensions=('time','zlev','lat','lon'))
            f[varname][:,:,:,:]=field[:,:,:,:]

            
        else:
            v = f.createVariable(varname,'f4',dimensions=('zlev','lat','lon'))
            f[varname][:,:,:]=field[:,:,:] 
        v.units = varunit

def latlonfield_to_netCDF(latitude, longitude, field, varname, varunit, outname, time_dim=False, time_var=None, overwrite=True):
    """ Saves a field with dimensions (latitude, longitude) to a NetCDF file.
    
    Parameters:
        latitude (1D-array, dimension nlat): latitudes in deg North
        longitude (1D-array, dimension nlon): longitudes in deg East
        field (3D-array, dimensions (nheight, nlat, nlon)): field with variable to save
        varname (string): name of variable (e.g. 't' or 'q')
        varunit (string): unit of variable
        outname (string): name for output file
        time (bool): if True, a dimension for time (with length 1) is added
        overwrite (boolean): if True, exisiting files with the same filename are overwritten
    """
    if (os.path.isfile(outname)) and overwrite:
        os.remove(outname)
    elif (os.path.isfile(outname)) and overwrite==False:
        print('File {} exists. Not overwriting.'.format(outname))
        return

    with Dataset(outname, 'w') as f:
        lat = f.createDimension('lat', len(latitude))
        lon = f.createDimension('lon', len(longitude))

        lat = f.createVariable('lat','f4',('lat',))
        lon = f.createVariable('lon','f4',('lon',))
        
        if time_dim:
            if time_var is not None:
                time = f.createDimension('time', len(time_var))
                time = f.createVariable('time', 'f4', ('time',))
            else:
                time = f.createDimension('time', 1)

        lat.units = 'degrees north'
        lon.units= 'degrees east'

        lat[:] = latitude[:]
        lon[:] = longitude[:]
        
        if time_var is not None:
            time.units = 'hours'
            time = time_var
        
        if time_dim:
            v = f.createVariable(varname,'f4',dimensions=('time','lat','lon'))
            f[varname][:,:,:]=field[:,:,:]
           
        else:
            v = f.createVariable(varname,'f4',dimensions=('lat','lon'))
            f[varname][:,:]=field[:,:] 
        v.units = varunit
        
def array2D_to_netCDF(array, varname, varunit, dimensionvars, dimensionnames, outname, overwrite=True):
    """ Saves a 1D-Array to a NetCDF file.
    
    Parameters:
        vector (1D Array): Vector with variable to save
        varname (string): Name of variable to save
        varunit (string): Unit of variable to save
        dimensionvar (Tuple of 1D Arrays): Grid the variable is given on (e.g. latitudes, longitudes, altitudes) 
        dimensionname (Tuple of strings): Name of dimension associated with vector (e.g. 'lat', 'lon', 'height')
        outname (string): Name of output file
        overwrite (boolean): If True, exisiting files with the same filename are overwritten
        
    """
    if (os.path.isfile(outname)) and overwrite:
        os.remove(outname)
    elif (os.path.isfile(outname)) and overwrite==False:
        print('File {} exists. Not overwriting.'.format(outname))
        return
    
    with Dataset(outname, 'w') as f:
        dim0 = f.createDimension(dimensionnames[0], len(dimensionvars[0]))
        dimvar0 = f.createVariable(dimensionnames[0], 'f4', (dimensionnames[0],))    
        dimvar0[:] = dimensionvars[0]
        
        dim1 = f.createDimension(dimensionnames[1], len(dimensionvars[1]))
        dimvar1 = f.createVariable(dimensionnames[1], 'f4', (dimensionnames[1],))    
        dimvar1[:] = dimensionvars[1]

        f.createVariable(varname, 'f4', dimensions=dimensionnames)
        f[varname][:,:] = array[:,:]
        
def vector_to_netCDF(vector, varname, varunit, dimensionvar, dimensionname, outname, overwrite=True):
    """ Saves a 1D-Array to a NetCDF file.
    
    Parameters:
        vector (1D Array): Vector with variable to save
        varname (string): Name of variable to save
        varunit (string): Unit of variable to save
        dimensionvar (1D Array): Grid the variable is given on (e.g. latitudes, longitudes, altitudes) 
        dimensionname (string): Name of dimension associated with vector (e.g. 'lat', 'lon', 'height')
        outname (string): Name of output file
        overwrite (boolean): If True, exisiting files with the same filename are overwritten
        
    """
    if (os.path.isfile(outname)) and overwrite:
        os.remove(outname)
    elif (os.path.isfile(outname)) and overwrite==False:
        print('File {} exists. Not overwriting.'.format(outname))
        return
    
    with Dataset(outname, 'w') as f:
        print(dimensionvar)
        dim = f.createDimension(dimensionname, len(dimensionvar))
        dimvar = f.createVariable(dimensionname, 'f4', (dimensionname,))    
        dimvar[:] = dimensionvar[:]

        f.createVariable(varname, 'f4', dimensions=(dimensionname))
        f[varname][:] = vector[:]


    
    
 
