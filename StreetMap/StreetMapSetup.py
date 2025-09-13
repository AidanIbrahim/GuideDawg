import osmnx as ox


def downloadStreetMap(location : str, filename : str) -> None:
    """
    Downloads the street map data for a given location using OSMnx.

    Parameters:
    location (str): The name of the location to download the street map for.
    filename (str): The filename to save the street map data as.
    """

    G = ox.graph_from_place(location, network_type='all')
    ox.save_graphml(G, "StreetMap/" + filename + ".graphml")
    print(f"Street map for {location} downloaded and saved as '{filename}.graphml'.")


if __name__ == "__main__":
    # Example usage
    downloadStreetMap("	University of Maryland Baltimore County", "UMBC_StreetMap")   
    G = ox.load_graphml("StreetMap/UMBC_StreetMap.graphml") 
    ox.plot_graph(G)