import json
import numpy as np
import geopandas as gpd
import contextily as cx
import geopy.distance
from shapely.geometry import MultiPolygon, Polygon, Point, LineString
import osmnx as ox
import pyproj
import os
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib import patches
import argparse

from map_utils import *

# Command line argument parser
parser = argparse.ArgumentParser()  
parser.add_argument("--places", "-p", help="Path to json file containing location info", default="nation_lakes.json")
parser.add_argument("--osm", "-o", help="Path to json file containing osm tags to get", default="osm_tags.json")
parser.add_argument("--tiles", "-t", help="Path to json file containing map backgroud tiles urls", default="tiles.json")
parser.add_argument("--background", "-b", 
                    help="Name of background tile to use, one of: \n\t'StamenToner', 'StamenTonerLite', 'StamenTerrain', 'StamenWatercolor', 'GoogleMaps', 'GoogleSatellite', 'GoogleSatelliteHybrid', 'EsriSatellite'", 
                    default="StamenTonerLite")
args=parser.parse_args()

if __name__=="__main__":
    with open(args.places) as f:
        lakes = json.load(f)
    with open(args.osm) as f:
        desired_tags = json.load(f)
    with open(args.tiles) as f:
        tiles = json.load(f)
    # Ensure tiles are available
    if "stamen" in args.background.lower():
        if "STAMEN_API_KEY" in os.environ:
            STAMEN_API_KEY = os.environ["STAMEN_API_KEY"]  
            print("Stamen API key found in environment variables")
            tiles_source = tiles[args.background].replace("API_KEY", STAMEN_API_KEY)
        else:
            print("No Stamen API key found in environment variables\nChoose from one of the following free tiles")
            free_tiles = [tile for tile in tiles if "stamen" not in tile.lower()]
            for i,tile in enumerate(free_tiles):
                print(f"{i}\t{tile}")
            usr_input = input("Select a tile by number: ")
            usr_input = int(usr_input)
            try:
                tiles_source = tiles[free_tiles[usr_input]]
            except:
                print("Error: Number selected is not available")
                return
        print(f"selected tile source: {tiles_source}")

    
