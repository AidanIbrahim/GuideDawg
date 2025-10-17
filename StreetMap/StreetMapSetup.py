import osmnx as ox
import folium
import matplotlib.pyplot as plt


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

if __name__ == "__main__":
    showTestMap("University of Maryland, Baltimore County", "UMBC_StreetMap")


