""""
File:    GPS.py
Author:  Aidan Ibrahim
Date:    10/18/2025 
Description:
This file contains python code that handles pathfinding algorithms using street map data with wheelchair accessibility considerations. 
Requires a pre-loaded street map graph G from StreetMapSetup.py.
"""

# Import necessary libraries
import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
import os
import StreetMapSetup as sms
 
# Constants
FILE_TYPE = ".graphml"  # File type for saving street maps
FILE_NAME = "UMBC_StreetMap" + FILE_TYPE    # Filename to save the map as, FILE_TYPE handles the graphml extension.
MODULE_NAME = "Pathing"



"""
Function: showMap
Description: Displays a map static utilizing matplotlib based on a saved GraphML file.

Parameters:
filename (str): The filename to show
Returns: None
"""
def showMap(filename : str) -> None:
    path = os.path.join(MODULE_NAME, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Map file not found: {path!r})")

    G = ox.load_graphml(path)

    # Convert to GeoDataFrames
    nodes, edges = ox.graph_to_gdfs(G)

    # Ensure wheelchair column exists
    if "wheelchair" not in edges.columns:
        edges["wheelchair"] = "unknown"
    else:
        edges["wheelchair"] = edges["wheelchair"].fillna("unknown")

    # Map wheelchair values to colors
    colors = edges["wheelchair"].map(lambda x: "green" if str(x).lower() == "yes" else "gray")

    # Plot edges then nodes on top
    ax = edges.plot(figsize=(10, 10), linewidth=2, color=colors)
    nodes.plot(ax=ax, markersize=5, color="black")

    plt.axis("off")
    plt.show(block=False) #Block set to false to prevent halting execution
    plt.pause(3) #allow the loop to run
    # Save as an HTML file

"""
Function: costWheelchair(u, v, data))
A pathing function that avoids all paths that do not have WHEELCHAIR = YES
"""
def costWheelchair(u, v, data):
    if data.get("wheelchair") == "yes":
        return data.get("length", 1)  # Use length as weight if wheelchair accessible
    else:
        return float('inf')  # Infinite weight if not wheelchair accessible, ensuring it will never be taken

"""
Function: searchNodeName
Description: Searches for a node by its 'name' attribute in the graph.
Parameters:
name (str): The name of the node to search for. 
G (networkx.MultiDiGraph): The graph representing the street map.

Returns a node given its name, or None if not found.
"""
def searchNodeName(name: str, G: nx.MultiDiGraph):
    for node, data in G.nodes(data=True):
        if data.get('name') == name:
            return node
            break
    return None

"""
Function: euclidianDistNode(u, v, G)
Description: A heuristic function that calculates the Euclidean distance between two nodes.
Parameters:
u (int): The first node ID.
v (int): The second node ID.
G (networkx.MultiDiGraph): The graph representing the street map.
"""   
def euclidianDistNode(u: int, v: int, G: nx.MultiDiGraph) -> float:
    from math import sqrt

    x1, y1 = G.nodes[u]['x'], G.nodes[u]['y']
    x2, y2 = G.nodes[v]['x'], G.nodes[v]['y']
    return sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


"""
Function: wheelchairAStar
Description: A* pathfinding algorithm that considers wheelchair accessibility.
Parameters:
G (networkx.MultiDiGraph): The graph representing the street map.
origin (int): The starting node ID.
endpoint (int): The target node ID.

Returns:
list: A list of node IDs representing the path from origin to destination.
"""
def wheelchairPath(origin: int, endpoint: int, G: nx.MultiDiGraph) -> list:

    try:
        path = nx.astar_path(G, origin, endpoint, heuristic=lambda u, v: euclidianDistNode(u, v, G), weight=costWheelchair)
        return path
    except nx.NetworkXNoPath:
        print("No path found that is wheelchair accessible.")
        return []

