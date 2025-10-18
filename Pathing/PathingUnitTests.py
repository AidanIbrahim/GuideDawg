""""
File:    GPS.py
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
MAP = sms.loadGraph("UMBC_StreetMap")

# Shortcuts for text formatting during testing output
COLOR_RESET = "\033[0m"
COLOR_BLUE = "\033[94m"
COLOR_BOLD_RED = "\033[1;31m"
COLOR_BOLD_GREEN = "\033[1;32m"
TEST_PASSED = COLOR_BOLD_GREEN + "PASSED" + COLOR_RESET
TEST_FAIlED = COLOR_BOLD_RED + "FAILED" + COLOR_RESET


if __name__ == "__main__":
    print(COLOR_BLUE + "Running Pathing Unit Tests...\n" + COLOR_RESET)
    gps.showMap(FILE_NAME)
    print(f"Test 1.1: Displaying Map... {TEST_PASSED}\n")
