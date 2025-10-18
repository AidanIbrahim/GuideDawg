""""
File:    StreetMapSetup.py
Author:  Aidan Ibrahim
Date:    10/18/2025 
Description:
This file contains python code that handles downloading, loading, and setting up street map data using OSMnx 
and converting to  graph ML file for use for pathfinding algorithms.
"""

# Import necessary libraries
import osmnx as ox
import folium
import networkx as nx
import matplotlib.pyplot as plt
import os

# Constants
FILE_TYPE = ".graphml"  # File type for saving street maps
MAP_LOCATION = "University of Maryland, Baltimore County" # Location for map to download
FILE_NAME = "UMBC_StreetMap" + FILE_TYPE    # Filename to save the map as, must end in .graphml
MAP_DOWNLOAD_TYPE = "walk"  # Options include 'walk', 'drive', 'bike', etc.
MODULE_NAME = "Pathing"


"""
Function: downloadStreetMap
Desctiption: Downloads the street map data for a given location using OSMnx, and saves it as a GraphML file.
Parameters:
location (str): The name of the location to download the street map for.
filename (str): The filename to save the street map data as.
Returns: None
"""
def downloadStreetMap(location : str, filename : str) -> None:

    G = ox.graph_from_place(location, network_type=MAP_DOWNLOAD_TYPE)
    ox.save_graphml(G, MODULE_NAME + "/" + filename + ".graphml")
    print(f"Street map for {location} downloaded and saved as '{filename}.graphml'.")


"""
Function: createMapHTML
Desctiption: creates an interactive map HTML file using Folium based on a saved GraphML file.

Parameters:
filename (str): The filename to create the map from.
saveAs (str): The filename to save the HTML map as, does not include .html, It will be added automatically.
Returns: None
"""
def createMapHTML(filename : str, saveAs : str) -> None:

    # Load from an existing grahhml file
    G = ox.load_graphml(MODULE_NAME + "/" + filename)

    # Convert to GeoDataFrames
    nodes, edges = ox.graph_to_gdfs(G)

    # Ensure wheelchair column exists
    if "wheelchair" not in edges.columns:
        edges["wheelchair"] = "unknown"
    else:
        edges["wheelchair"] = edges["wheelchair"].fillna("unknown")

    # Get the center of the graph
    if 'center' in G.graph:
        center_lat, center_lon = G.graph['center']
    else:
        first_node = list(G.nodes)[0]
        center_lat = G.nodes[first_node]['y']
        center_lon = G.nodes[first_node]['x']

    m = folium.Map(location=[center_lat, center_lon], zoom_start=16)

    for _, row in edges.iterrows():
        geom = row['geometry']
        color = "red" if row["wheelchair"] == "yes" else "gray"
        # Handle both LineString and MultiLineString
        if geom.geom_type == 'LineString':
            folium.PolyLine(locations=[(lat, lon) for lon, lat in geom.coords], color=color, weight=3).add_to(m)
        elif geom.geom_type == 'MultiLineString':
            for linestring in geom.geoms:
                folium.PolyLine(locations=[(lat, lon) for lon, lat in linestring.coords], color=color, weight=3).add_to(m)

    m.save(MODULE_NAME + "/" + saveAs + ".html")
    print("Interactive map saved as StreetMap/UMBC_StreetMap.html")

"""
Function: loadGraph
Description: returns a GraphML graph from a given filename
Parameters:
filename (str): The filename to load the graph from. Does not include .graphml, It will be added automatically.
Returns: GraphML graph (nx.MultiDiGraph)
"""
def loadGraph(filename : str) -> nx.MultiDiGraph:
    if not os.path.exists(MODULE_NAME + "/" + filename + FILE_TYPE):
        raise FileNotFoundError(f"The file '{filename}.graphml' does not exist in the '" + MODULE_NAME + "' directory.")
    
    G = ox.load_graphml(MODULE_NAME + "/" + filename + FILE_TYPE)
    print(f"Street map graph '{filename}.{FILE_TYPE}' loaded successfully.")
    return G




    


