# Hydrotrend-Input-Maker

To test this function, first change the two paths in "temporary set up." These will eventually be hard-coded, but for now have to point to the test files I put on beach in my own account. 

Then run from command line: 
>>python makehtinput.py 24.8044 87.9331 Farakka

[those three inputs are latitude, longitude and point name of the watershed outlet. Test case: Farakka Barrage in Bangladesh]

If successful, this will create a number of files in the specified directory (ultimately user home directory):
    Farakka.shp: shapefile with single dot at user-inputted location (23.8044,87.9331)
    FarakkaMoved.shp: shapefile with single dot showing user-inputted location after it was moved to stream grid 
    FarakkaMask.tif: mask of in (1) or out (-1) of watershed, useful for cutting other datasets of interest
    FarakkaDEM.tif: elevation of all points within watershed,
      plus associated dbf and projection files for each shapefile.
    It will also create the HydroTrend hypsometery input file, HYDRO0.HYPS.

This should work for any latitude and longitude roughly on or near a stream in Asia, or anywhere on Earth once all the files are on Beach... except for Australia, beacause Hydro1K was not generated for Australia due to insufficient data. 

To-Do list:
-This won't work on beach until the os.system calls to the mpiexecs are changed to pyDEM calls
-Clean up the way the main function is organized?
-Add all of the other desired input file functions (lithology, precip, lapse rate...)
-Should this be a command line call that doesnt use "python xxx"? I thought that was what Mark said.  

A note about the function "fixMonotonic": 
This script contains a rough correction for areas where topography is not
monotonically increasing due to bin size or grid resolution limitations. 
An explanation by way of an example: 
The Farakka (test) watershed contains Mt. Everest (elevation: 8848 meters), which is more than 50 meters
higher than the eight cells surrounding it. Imagine that the surrounding cells are all at elevation 8700 m.
The DEM might look like this:
8700 8700 8700
8700 8848 8700
8700 8700 8700
The corresponding portion of the HYDRO0.HYPS file binned at 50 m intervals would then look like this:
8700    8
8750    8
8800    8
8850    9
This is not monotonically increasing, so HydroTrend will fail with this input file.
The fixMonotonic function spreads the elevation gain linearly across the bins, so that the above example becomes:
8700    8
8750    8.333
8800    8.666
8850    9
