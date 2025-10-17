import osmnx as ox
import folium
import networkx as nx
import matplotlib.pyplot as plt
import os

def downloadStreetMap(location : str, filename : str) -> None:
    """
    Downloads the street map data for a given location using OSMnx.

    Parameters:
    location (str): The name of the location to download the street map for.
    filename (str): The filename to save the street map data as.
    """

    G = ox.graph_from_place(location, network_type='walk')
    ox.save_graphml(G, "StreetMap/" + filename + ".graphml")
    print(f"Street map for {location} downloaded and saved as '{filename}.graphml'.")

def showTestMap(location : str, filename : str) -> None:
    """
    Creates an interactive test map using Foliuym and OSMnx

    Parameters:
    location (str): The name of the location to download the street map for.
    filename (str): The filename to save the street map data as.
    """

    # Dowload the street map from OMSnx and create a graph
    downloadStreetMap(location, filename)   
    G = ox.load_graphml("StreetMap/UMBC_StreetMap.graphml")

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
        color = "green" if row["wheelchair"] == "yes" else "gray"
        # Handle both LineString and MultiLineString
        if geom.geom_type == 'LineString':
            folium.PolyLine(locations=[(lat, lon) for lon, lat in geom.coords], color=color, weight=3).add_to(m)
        elif geom.geom_type == 'MultiLineString':
            for linestring in geom.geoms:
                folium.PolyLine(locations=[(lat, lon) for lon, lat in linestring.coords], color=color, weight=3).add_to(m)

    m.save("StreetMap/UMBC_StreetMap.html")
    print("Interactive map saved as StreetMap/UMBC_StreetMap.html")

    # Save as an HTML file

def loadGraph(filename : str) -> nx.MultiDiGraph:
    """
    Loads a street map graph from a GraphML file.

    Parameters:
    filename (str): The filename of the GraphML file to load.

    Returns:
    nx.MultiDiGraph: The loaded street map graph.
    """

    if not os.path.exists("StreetMap/" + filename + ".graphml"):
        raise FileNotFoundError(f"The file '{filename}.graphml' does not exist in the 'StreetMap' directory.")
    
    G = ox.load_graphml("StreetMap/" + filename + ".graphml")
    print(f"Street map graph '{filename}.graphml' loaded successfully.")
    return G

"""
Function: costWheelchair(u, v, data))
A pathing function that avoids all functions that do not have WHEELCHAIR = YES
"""
def costWheelchair(u, v, data):


    if data.get("wheelchair") == "yes":
        return data.get("length", 1)  # Use length as weight if wheelchair accessible
    else:
        return float('inf')  # Infinite weight if not wheelchair accessible, as wheelchairs cannot use these paths

"""
Function: searchNodeName(name: str)
Returns a node given its name
"""
def searchNodeName(name: str):
    for node, data in G.nodes(data=True):
        if data.get('name') == name:
            return node
            break
    return None

"""
Function: euclidianDist(u, v, G)
A heuristic function that calculates the Euclidean distance between two nodes.
"""   
def euclidianDist(u, v, G):
    from math import sqrt

    x1, y1 = G.nodes[u]['x'], G.nodes[u]['y']
    x2, y2 = G.nodes[v]['x'], G.nodes[v]['y']
    return sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


"""
A* pathfinding algorithm that considers wheelchair accessibility.

Parameters:
G (networkx.MultiDiGraph): The graph representing the street map.
origin (int): The starting node ID.
destination (int): The target node ID.

Returns:
list: A list of node IDs representing the path from origin to destination.
"""
def wheelchairAStar(G, origin, endpoint):

    try:
        path = nx.astar_path(G, origin, endpoint, heuristic=lambda u, v: euclidianDist(u, v, G), weight=costWheelchair)
        return path
    except nx.NetworkXNoPath:
        print("No path found that is wheelchair accessible.")
        return []


if __name__ == "__main__":
    showTestMap("University of Maryland, Baltimore County", "UMBC_StreetMap")
    G = loadGraph("UMBC_StreetMap")

        # convert lon/lat coordinates to nearest graph nodes
    origin_node = ox.distance.nearest_nodes(G, X=76.545, Y=39.070)
    dest_node   = ox.distance.nearest_nodes(G, X=76.520, Y=-39.060)

    route = wheelchairAStar(G, origin_node, dest_node)

    # plot the route with matplotlib using OSMnx helper
    if route:
        fig, ax = ox.plot_graph_route(G, route,
                                     route_color="red",
                                     route_linewidth=3,
                                     node_size=0)
        plt.show()
    else:
        print("No route to plot.")

    


