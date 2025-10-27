""""
File:    PathingUnitTests.py
Author:  Aidan Ibrahim
Date:    10/18/2025 
Description:
This file contains python code that runs unit tests for the Pathing module functions.
"""

import GPS as gps
import StreetMapSetup as sms
import osmnx as ox
import matplotlib.pyplot as plt

# Constants
FILE_TYPE = ".graphml"  # File type for saving street maps
FILE_NAME = "UMBC_StreetMap" + FILE_TYPE    # Filename to save the map as, FILE_TYPE handles the graphml extension.
MAP = None # Global variable to hold the loaded map graph for testing
MODULE_NAME = "Pathing"
BUILDING_LOCATIONS = None  # Global variable to hold building locations for testing

# Shortcuts for text formatting during testing output
COLOR_RESET = "\033[0m"
COLOR_BLUE = "\033[94m"
COLOR_BOLD_RED = "\033[1;31m"
COLOR_BOLD_GREEN = "\033[1;32m"
TEST_PASSED = COLOR_BOLD_GREEN + "PASSED" + COLOR_RESET
TEST_FAIlED = COLOR_BOLD_RED + "FAILED" + COLOR_RESET


if __name__ == "__main__":
    MAP = ox.load_graphml("./" + MODULE_NAME + '/' + FILE_NAME)
    BUILDING_LOCATIONS = sms.downloadBuildingLocations()
    print(COLOR_BLUE + "***********************************************************************\n" + COLOR_RESET)
    print(COLOR_BLUE + "Running Pathing Unit Tests...\n" + COLOR_RESET)
    print(f"Test 1.1: Loading Map... {TEST_PASSED}\n")
    gps.showMap(FILE_NAME)
    print(f"Test 1.2: Displaying Map... {TEST_PASSED}\n")
    print(f"Test 1.3: Searching for the UMBC Information Technology/Engineering Building...", end='') #No newline so status can be printed after test
    origin = gps.nodeFromName("Information Technology/Engineering", MAP)
    if origin is not None:
        print(f" {TEST_PASSED}\n")
        lat, lon = MAP.nodes[origin]['y'], MAP.nodes[origin]['x']
        print(f"Node coordinates: ({lat}, {lon})")
    else:
        print(f" {TEST_FAIlED}\n")
    print(f"Test 1.4 Pathing from lat/lon to lat/lon...", end='') #No newline so status can be printed after test
    path = gps.pathFromCoords(-76.71517806320851, 39.255243023905805, -76.71162470525437, 39.25684950733026, MAP)
    gps.showPath(path, MAP)



    
