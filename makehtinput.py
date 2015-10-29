# -*- coding: utf-8 -*-
"""
Created on Wed Oct 21 13:44:47 2015

To test this function, first change the two paths below in "temporary set up." 
Then run from command line: 
>>python makehtinput.py 24.8044 87.9331 Farakka

[those three inputs are latitude, longitude and point name of the watershed outlet]

If successful, this will create a number of files in the user home director:
    pointName.shp: shapefile with single dot showing user-inputted location (e.g., Teesta.shp)
    pointNameMoved.shp: shapefile with single dot showing outlet after it was moved to stream grid (e.g., TeestaMoved.shp)
    pointNameMask.tif: mask of in (1) or out (-1) of watershed (e.g., TeestaMask.tif)
    pointNameDEM.tif: (e.g., TeestaDEM.tif)
    plus associated dbf and projection files for each shapefile,
    plus the HydroTrend input file, HYDRO0.HYPS.

@author: Stephanie Higgins
"""

import gdal
import osr
import numpy as np
import shapefile #note to Elchin - this is easy_install pyshp (https://code.google.com/p/pyshp/)
import pyproj
import os
import argparse

#============================= TEMPORARY SET-UP: ====================================
#These will eventually be hard-coded, but for now need to point to those folders where I put the Asia test data (my home directory)
USER_HOME_FOLDER='C:\\elchinTest\\' #where your output will be written. Default to user home directory?
PATH_TO_TIFS_STORED_ON_BEACH='V:\\DEMProcess\\' #where the preprocessed DEMs are permanently stored on Beach
#==============================================================================

def fixMonotonic(cumulative): #Ensures HYDRO0.HYPS monotonically increases. See note in README.
    counter=1
    for i in xrange(len(cumulative)-1):
            if cumulative[i]==cumulative[i+1]:
                counter=counter+1
            if counter>1 and cumulative[i]!=cumulative[i+1]: 
                replaceChunk=np.linspace(cumulative[i-counter+1],cumulative[i+1],counter+1)
                cumulative[i-counter+1:i+1]=replaceChunk[:-1]
                counter=1
    return cumulative


def line_prepender(filename, line): #adds lines to the top of a text file
    with open(filename, 'r+') as f:
        content = f.read()
        f.seek(0, 0)
        f.write(line.rstrip('\r\n') + '\n' + content)

def makeShapefile(lon1,lat1,pointname,filename,spatialref=None,LATITUDE_OF_ORIGIN=None,CENTRAL_MERIDIAN=None): 
    w=shapefile.Writer(shapefile.POINT)
    w.field('Name','C','40')
    w.point(lon1,lat1)
    w.record(pointname)
    w.save(filename)
    if spatialref!=None: #make a .prj to go with the shapefile
        prjname=filename[:-4]+'.prj'       
        prj=open(prjname,'w')
        if spatialref=='WGS':
            epsg = 'GEOGCS["WGS 84",'
            epsg += 'DATUM["WGS_1984",'
            epsg += 'SPHEROID["WGS 84",6378137,298.257223563]]'
            epsg += ',PRIMEM["Greenwich",0],'
            epsg += 'UNIT["degree",0.0174532925199433]]'
        elif spatialref=='USNAEA':
            epsg='PROJCS["US National Atlas Equal Area",'
            epsg+='GEOGCS["Unspecified datum based upon the Clarke 1866 Authalic Sphere",'
            epsg+='DATUM["D_Sphere_Clarke_1866_Authalic",'
            epsg+='SPHEROID["Clarke_1866_Authalic_Sphere",6370997,0]],'
            epsg+='PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]],'
            epsg+='PROJECTION["Lambert_Azimuthal_Equal_Area"],'
            epsg+='PARAMETER["LATITUDE_OF_ORIGIN",'+str(LATITUDE_OF_ORIGIN)+'],'
            epsg+='PARAMETER["CENTRAL_MERIDIAN",'+str(CENTRAL_MERIDIAN)+'],'
            epsg+='PARAMETER["false_easting",0],'
            epsg+='PARAMETER["false_northing",0],'
            epsg+='UNIT["Meter",1]]'
        elif spatialref !='WGS' and spatialref !='USNAEA':
            print('Error: Unknown spatial reference. PRJ file will be empty.')
            epsg=('')
        prj.write(epsg)
        prj.close()
               
def intToFlowDir(intIn):
    if intIn in range(1,9):
        if intIn==1:
            plusX=1
            plusY=0
        if intIn==2:
            plusX=1
            plusY=-1
        if intIn==3:
            plusX=0
            plusY=-1
        if intIn==4:
            plusX=-1
            plusY=-1
        if intIn==5:
            plusX=-1
            plusY=0
        if intIn==6:
            plusX=-1
            plusY=1
        if intIn==7:
            plusX=0
            plusY=1
        if intIn==8:
            plusX=1
            plusY=1      
    elif intIn not in range(1,9):
        #sys.exit('Error: flow direction must be between 1 and 8')
        print('Error: flow direction must be between 1 and 8')
        plusX=None
        plusY=None
    return plusX,plusY
   
def moveOutletsToStream_mine(DEMP,DEMSRC,DEMGORD,lon1,lat1):
#My own Move Outlets To Stream. Note to self: your big stream thing isn't gonna work for small stream order areas.
#note to self: right now you are dropping on a corner. Does that matter?

    dataset_p=gdal.Open(DEMP)
    p=dataset_p.ReadAsArray()
    dataset_p=None

    dataset_gord=gdal.Open(DEMGORD)
    gord=dataset_gord.ReadAsArray()
    bigStreams=gord.max()
    dataset_gord=None
    
    dataset_src=gdal.Open(DEMSRC)
    src=dataset_src.ReadAsArray()
           
    gt=dataset_src.GetGeoTransform()
    gdal.UseExceptions()
    dataset_src=None
    
    #what pixel is your outlet on?
    pxo=int((lon1-gt[0])/gt[1]) #x pixel
    pyo=int((lat1-gt[3])/gt[5]) #y pixel
    if src[pyo,pxo] ==1 or gord[pyo,pxo] in range(bigStreams-1,bigStreams+1):
        print('Outlet already on a stream. Point is not moved.')
        return 0,0
    if src[pyo,pxo] != 1 and gord[pyo,pxo] not in range(bigStreams-1,bigStreams+1):    
        counter=0
        px,py=pxo,pyo
        while src[py,px] != 1 and gord[py,px] not in range(bigStreams-1,bigStreams+1) and counter < 50:#on src and within 50 pixels of the original point
            plusxx,plusyy=intToFlowDir(p[py,px])#get flow direction:
            px=px+plusxx #x pixel
            py=py+plusyy #y pixel
            counter=counter+1
        if counter ==50:
            print('Error: outlet is too far from stream (limit reached). Outlet is not moved.')
            return 0,0
        if counter <50:
            xChange=abs((px-pxo)*gt[1])
            yChange=abs((py-pyo)*gt[5])
            movedDist=str(int(np.sqrt(xChange**2+yChange**2)))
            print('Outlet moved '+movedDist+' meters.')  
            lonNew=px*gt[1]+gt[0]
            latNew=py*gt[5]+gt[3]
            return lonNew,latNew

   
def array2raster(rasterfn,newRasterfn,array,nodatavalue):  
    raster = gdal.Open(rasterfn)
    geotransform = raster.GetGeoTransform()
    originX = geotransform[0]
    originY = geotransform[3]
    pixelWidth = geotransform[1]
    pixelHeight = geotransform[5]
    cols = raster.RasterXSize
    rows = raster.RasterYSize

    driver = gdal.GetDriverByName('GTiff')
    outRaster = driver.Create(newRasterfn, cols, rows, 1, gdal.GDT_Float32)
    outRaster.SetGeoTransform((originX, pixelWidth, 0, originY, 0, pixelHeight))
    outband = outRaster.GetRasterBand(1)
    outband.WriteArray(array)
    outband.SetNoDataValue(nodatavalue)
    outRasterSRS = osr.SpatialReference()
    outRasterSRS.ImportFromWkt(raster.GetProjectionRef())
    outRaster.SetProjection(outRasterSRS.ExportToWkt())
    outband.FlushCache()
    raster=None
    
def array2maskraster(rasterfn,newRasterfn,array):  
    raster = gdal.Open(rasterfn)
    geotransform = raster.GetGeoTransform()
    originX = geotransform[0]
    originY = geotransform[3]
    pixelWidth = geotransform[1]
    pixelHeight = geotransform[5]
    cols = raster.RasterXSize
    rows = raster.RasterYSize

    driver = gdal.GetDriverByName('GTiff')
    outRaster = driver.Create(newRasterfn, cols, rows, 1, gdal.GDT_Int16)
    outRaster.SetGeoTransform((originX, pixelWidth, 0, originY, 0, pixelHeight))
    outband = outRaster.GetRasterBand(1)
    outband.WriteArray(array)
    outband.SetNoDataValue(-1)
    outRasterSRS = osr.SpatialReference()
    outRasterSRS.ImportFromWkt(raster.GetProjectionRef())
    outRaster.SetProjection(outRasterSRS.ExportToWkt())
    outband.FlushCache()
    
def maskRasterWithRaster(infile,inmask,outfile):
    ftdArray=raster2array(infile)
    ftmArray=raster2array(inmask)
    noDataValue=getNoDataValue(inmask)
    counter=0
    for row in ftdArray:
        row[ftmArray[counter]==noDataValue]=55555
        counter=counter+1
#    ftdArray[ftmArray==noDataValue]=55555 this had memory problems, so I looped it above.
    array2raster(infile,outfile,ftdArray,55555)      
    
def raster2array(rasterfn):
    raster = gdal.Open(rasterfn)
    band = raster.GetRasterBand(1)
    return band.ReadAsArray()
    raster=None

def getNoDataValue(rasterfn):
    raster = gdal.Open(rasterfn)
    band = raster.GetRasterBand(1)
    return band.GetNoDataValue()
    
def fixProjection(rasterfn,newRasterfn,stealRaster):  
    raster = gdal.Open(stealRaster)
    geotransform = raster.GetGeoTransform()
    originX = geotransform[0]
    originY = geotransform[3]
    pixelWidth = geotransform[1]
    pixelHeight = geotransform[5]
    cols = raster.RasterXSize
    rows = raster.RasterYSize

    array=raster2array(rasterfn)
    
    driver = gdal.GetDriverByName('GTiff')
    outRaster = driver.Create(newRasterfn, cols, rows, 1, gdal.GDT_UInt16)
    outRaster.SetGeoTransform((originX, pixelWidth, 0, originY, 0, pixelHeight))
    outband = outRaster.GetRasterBand(1)
    outband.WriteArray(array)
    outband.SetNoDataValue(55555)
    outRasterSRS = osr.SpatialReference()
    outRasterSRS.ImportFromWkt(raster.GetProjectionRef())
    outRaster.SetProjection(outRasterSRS.ExportToWkt())
    outband.FlushCache()
    raster=None
    
def fixSeaLevel(tiffIn,tiffOut):
    dataset = gdal.Open(tiffIn)
    band = dataset.GetRasterBand(1)
    array=band.ReadAsArray()

    for row in array:
        row[row==55537]=55555
        row[(row>32767) & (row!=55555)]=0
        
    geotransform = dataset.GetGeoTransform()
    originX = geotransform[0]
    originY = geotransform[3]
    pixelWidth = geotransform[1]
    pixelHeight = geotransform[5]
    cols = dataset.RasterXSize
    rows = dataset.RasterYSize
    
    driver = gdal.GetDriverByName('GTiff')
    outRaster = driver.Create(tiffOut, cols, rows, 1, gdal.GDT_UInt16)
    outRaster.SetGeoTransform((originX, pixelWidth, 0, originY, 0, pixelHeight))
    outband = outRaster.GetRasterBand(1)
    outband.WriteArray(array)
    outband.SetNoDataValue(55555)
    outRasterSRS = osr.SpatialReference()
    outRasterSRS.ImportFromWkt(dataset.GetProjectionRef())
    outRaster.SetProjection(outRasterSRS.ExportToWkt())
    outband.FlushCache()
    dataset=None
    
def hydroflow2tauDEMflow(inhydrofn,outtiffn):
    array=raster2array('euroFlowDir.tif')
    counter=0
    for row in array:
        row[row==247]=512
        row[row==255]=512
        row[row==0]=512
        array[counter]=np.uint16(np.log2(row))
        counter=counter+1
    array=array+1
    array2raster(inhydrofn,outtiffn,array,9)    
   
if __name__ == "__main__":   

    #==============================================================================
    #============================= CONFIGURE ======================================
    #============================================================================== 
    
    #parse command-line arguments
    parser=argparse.ArgumentParser()
    parser.add_argument("USER_INPUT_LATITUDE")
    parser.add_argument("USER_INPUT_LONGITUDE")
    parser.add_argument("USER_INPUT_POINT_NAME")
    args=parser.parse_args()
    USER_INPUT_LATITUDE=args.USER_INPUT_LATITUDE
    USER_INPUT_LONGITUDE=args.USER_INPUT_LONGITUDE
    USER_INPUT_POINT_NAME=args.USER_INPUT_POINT_NAME
        
    #Maybe these will be options, but maybe they will stay as defaults. 
    overwriteOutput = True
    nP='8'; #options are 1 to your max number, or just type 'max'
    streamThreshold='300'
    HYDRO0_HYPS_FILENAME='HYDRO0.HYPS' #We could let them change this if they wanted to have names like "waipaoa.hyps"
    
    #Which CONTINENT will later be determined from lat and long. For the moment, it's just set here because all the DEMs aren't on Beach to check yet:
    CONTINENT='Asia' 
    DEMDATAPATH=PATH_TO_TIFS_STORED_ON_BEACH+CONTINENT+'\\'
    
    #TAUDEM variables - located on Beach (pre-processed)
    DEMPREFIX=CONTINENT
    DEM=DEMPREFIX+'.tif' #Elevation grid" (DEM)
    DEMFEL=DEMPREFIX+'fel.tif' #"Pit filled elevation grid"
    DEMP=DEMPREFIX+'p.tif' #"D8 flow direction grid"
    DEMSD8=DEMPREFIX+'sd8.tif' #"D8 slope grid"
    DEMAD8=DEMPREFIX+'ad8.tif' #"D8 contributing area grid"
    DEMGORD=DEMPREFIX+'gord.tif' #"Strahler network order grid"
    DEMPLEN=DEMPREFIX+'plen.tif' #"Longest upslope length grid"
    DEMTLEN=DEMPREFIX+'tlen.tif' #"Total upslope length grid"
    DEMSRC=DEMPREFIX+'src.tif' #"Stream raster grid"
    
    #A temporary TAUDEM file that will be created in the User's home directory and then removed
    DEMSSA=USER_INPUT_POINT_NAME+'ssa.tif'
    
    #Files to be created and will remain in user's home directory
    GAUGE=USER_INPUT_POINT_NAME+'.shp' #"Outlet shapefile"
    GAUGEWGS=USER_INPUT_POINT_NAME+'WGS.shp'
    GAUGEMOVED=USER_INPUT_POINT_NAME+'Moved.shp' #"Moved outlet shapefile"
    GAUGEMOVEDWGS=USER_INPUT_POINT_NAME+'MovedWGS.shp' #"Moved outlet shapefile"
    GAUGEDEM=USER_INPUT_POINT_NAME+'DEM.tif'
    GAUGEMASK=USER_INPUT_POINT_NAME+'Mask.tif' #"D8 specific catchement area grid"
    
    #defining projections
    WGS84=pyproj.Proj("+init=EPSG:4326") # LatLon with WGS84 datum used by GPS units and Google Earth
    
    if CONTINENT == 'Africa':
        LATITUDE_OF_ORIGIN=5
        CENTRAL_MERIDIAN=20
    elif CONTINENT == 'Asia':
        LATITUDE_OF_ORIGIN=45
        CENTRAL_MERIDIAN=100    
    elif CONTINENT == 'Australasia':
        LATITUDE_OF_ORIGIN=-15
        CENTRAL_MERIDIAN=135   
    elif CONTINENT == 'Europe':
        LATITUDE_OF_ORIGIN=55
        CENTRAL_MERIDIAN=20    
    elif CONTINENT == 'northAmerica':
        LATITUDE_OF_ORIGIN=45
        CENTRAL_MERIDIAN=-100
    elif CONTINENT =='southAmerica':
        LATITUDE_OF_ORIGIN=-15
        CENTRAL_MERIDIAN=-60
       
    USNAEA=pyproj.Proj("+proj=laea +lat_0="+str(LATITUDE_OF_ORIGIN)+" +lon_0="+str(CENTRAL_MERIDIAN)+" x_0=0 +y_0=0 +a=6370997 +b=6370997 +units=m +no_defs")
    
    #==============================================================================
    #============================= MAKE TIFS ======================================
    #============================================================================== 
    
    os.chdir(USER_HOME_FOLDER)
    
    #transform user input to USGS projection. Import WGS to assign to shapefile.
    lon1,lat1=pyproj.transform(WGS84,USNAEA,USER_INPUT_LONGITUDE,USER_INPUT_LATITUDE)
    spatialRef = osr.SpatialReference()
    spatialRef.ImportFromEPSG(4326)
    
    #Make shapefile of inputted lat/long        
    makeShapefile(lon1,lat1,USER_INPUT_POINT_NAME,USER_HOME_FOLDER+GAUGE,spatialref='USNAEA',LATITUDE_OF_ORIGIN=LATITUDE_OF_ORIGIN,CENTRAL_MERIDIAN=CENTRAL_MERIDIAN)
        
    #Move points to streams: my own routine (not TauDEM)
    os.chdir(PATH_TO_TIFS_STORED_ON_BEACH)
    lonNew,latNew=moveOutletsToStream_mine(DEMP,DEMSRC,DEMGORD,lon1,lat1)
    lonNewWGS,latNewWGS=pyproj.transform(USNAEA,WGS84,str(lonNew),str(latNew))
    
    #create the shapefile with the moved outlet 
    os.chdir(USER_HOME_FOLDER)
    if lonNew !=0 and latNew !=0:
        makeShapefile(lonNew,latNew,USER_INPUT_POINT_NAME,USER_HOME_FOLDER+GAUGEMOVED,spatialref='USNAEA',LATITUDE_OF_ORIGIN=LATITUDE_OF_ORIGIN,CENTRAL_MERIDIAN=CENTRAL_MERIDIAN)
    else:
        makeShapefile(lon1,lat1,USER_INPUT_POINT_NAME,USER_HOME_FOLDER+GAUGEMOVED,spatialref='USNAEA',LATITUDE_OF_ORIGIN=LATITUDE_OF_ORIGIN,CENTRAL_MERIDIAN=CENTRAL_MERIDIAN)
            
    #Calculate the contributing area to the moved outlet
    os.chdir(PATH_TO_TIFS_STORED_ON_BEACH)
    os.system('mpiexec -n '+str(nP)+' Aread8 -p '+DEMP+' -o '+USER_HOME_FOLDER+GAUGEMOVED+' -ad8 '+USER_HOME_FOLDER+DEMSSA)
    
    #Cut DEM with contributing area 
    maskRasterWithRaster(DEM,USER_HOME_FOLDER+DEMSSA,USER_HOME_FOLDER+GAUGEDEM)
    
    #Make a 1/-1 watershed mask (because it may be more useful for cutting other datasets)
    os.chdir(USER_HOME_FOLDER)
    dataset=gdal.Open(DEMSSA)
    imarray=dataset.ReadAsArray()
    for row in imarray:
        row[row!=-1]=1
    array2maskraster(DEMSSA,GAUGEMASK,imarray)
    dataset=None
    
    #Remove the contributing # of pixels file from the User's home directory
    os.system('rm '+DEMSSA)
    
    #==============================================================================
    #=========================== MAKE HYDRO0.HYPS =================================
    #============================================================================== 
    
    os.chdir(USER_HOME_FOLDER)
    
    #open DEM tif and read info
    dataset=gdal.Open(GAUGEDEM)
    geotransform=dataset.GetGeoTransform()
    cellsizex=abs(geotransform[1])
    cellsizey=abs(geotransform[5])
    cellarea=cellsizex*cellsizey/(1e6) #convert to area in sq km.
    imarray=dataset.ReadAsArray()
    
    #set no data to -1, row by row to prevent memory error
    for row in imarray:
        row[row==55555]=-1
    
    #Make array of bins. Not sleek, but I believe you have to do it this way w/ np.histogram 
    counter=1
    a=np.array([counter])
    while counter<np.nanmax(imarray):
        counter=counter+50
        a=np.append(a,[counter])
    
    #bin the cells by 50s and create running total
    hypsometry=np.histogram(imarray,bins=a)
    hist=hypsometry[0]
    bins=hypsometry[1]
    cumulative=np.cumsum(hist)*cellarea
    
    #Check for monotonically increasing cells. See header for explanation.
    cumulative=fixMonotonic(cumulative)
    
    n=np.size(bins)-1
    binsFinal=np.reshape(bins[:-1],(n,1))
    cumulativeFinal=np.reshape(cumulative,(n,1))
    
    #Write the HYDRO0.HYPS file
    writeOut=np.concatenate((binsFinal,cumulativeFinal),axis=1)
    np.savetxt(USER_HOME_FOLDER+HYDRO0_HYPS_FILENAME,writeOut,fmt='%i\t%.2f')
    line_prepender(USER_HOME_FOLDER+HYDRO0_HYPS_FILENAME,str(n))
    line_prepender(USER_HOME_FOLDER+HYDRO0_HYPS_FILENAME,'-------------------------------------------------')
    line_prepender(USER_HOME_FOLDER+HYDRO0_HYPS_FILENAME,'Other lines: altitude (m) and area in (km^2) data')
    line_prepender(USER_HOME_FOLDER+HYDRO0_HYPS_FILENAME,'First line: number of hypsometric bins')
    line_prepender(USER_HOME_FOLDER+HYDRO0_HYPS_FILENAME,'Hypsometry input file for HYDROTREND')
    line_prepender(USER_HOME_FOLDER+HYDRO0_HYPS_FILENAME,'-------------------------------------------------')
