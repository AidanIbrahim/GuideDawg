""""
File:    StreetMapSetup.py
Author:  Aidan Ibrahim
Date:    10/18/2025 
Description:
This file contains python code that handles downloading, loading, and setting up street map data using OSMnx 
and converting to  graph ML file for use for pathfinding algorithms.
"""

# Import necessary libraries
import json
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
BUILDING_CACHE_FILE = "umbc_buildings.json"  # Cache file for building locations


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
Function: downloadBuildingLocations
Desctiption: This funtion downloads building locations for a given place using OSMnx and caches the results in a JSON file for later use.
Parameters:
    placeName (str): name of the location to downlaod building locations for
    cacheFile (str): name of the json file to cache building locations to
Returns:
"""
def downloadBuildingLocations(placeName: str = MAP_LOCATION, cacheFile: str =  BUILDING_CACHE_FILE) -> dict:
    # use the provided cacheFile parameter
    if os.path.exists(cacheFile):
        with open(cacheFile, 'r', encoding='utf-8') as f:
            return json.load(f)

    #Download the building locations using OSMnx
    buildings = ox.features_from_place(placeName, tags={"building": True})

    buildings = buildings.to_crs(ox.settings.default_crs)

    # Create dictionary of building names and coordinates
    buildingCoords = {}
    for _, building in buildings.iterrows():
        name = building.get('name')
        geom = building.geometry
        if name and geom is not None:
            centroid = geom.centroid
            buildingCoords[name] = (centroid.y, centroid.x)  # Store as (lat, lon)
           
           # Convert centroid back to lat/lon (EPSG:4326)
            centroid4326 = ox.projection.project_geometry(centroid, crs=buildings.crs, to_crs="EPSG:4326")[0]

            buildingCoords[name] = (centroid4326.y, centroid4326.x)
    # Cache the results to cacheFile
    with open(cacheFile, 'w', encoding='utf-8') as f:
        json.dump(buildingCoords, f, ensure_ascii=False, indent=2)
    return buildingCoords


"""
Function: createMapHTML
Desctiption: creates an interactive map HTML file using Folium based on a saved GraphML file.

Parameters:
filename (str): The filename to create the map from.
saveAs (str): The filename to save the HTML map as, does not include .html, It will be added automatically.
path (list, optional): A list of nodes representing a path to highlight on the map. Default is None.
Returns: None
"""
def createMapHTML(filename : str, saveAs : str, path = None) -> None:

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

        # If path is provided, draw it on top
    if path and len(path) > 1:
        # Get coordinates for each node in the path
        path_coords = []
        for node in path:
            lat = G.nodes[node]['y']
            lon = G.nodes[node]['x']
            path_coords.append([lat, lon])
        
        # Draw the path in red, slightly thicker
        folium.PolyLine(locations=path_coords, 
                       color='red', 
                       weight=4,
                       opacity=0.8).add_to(m)


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




    


