import json
import numpy as np
import geopandas as gpd
import contextily as cx
# import geopy.distance
from shapely.geometry import MultiPolygon, Polygon, Point, LineString
import osmnx as ox
# import pyproj
import os
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib import patches
import argparse

from map_utils import *

# Command line argument parser
parser = argparse.ArgumentParser()  
parser.add_argument("--dim", help="Maximum dimension (inches) of map when printed", type=float, default=10)
parser.add_argument("--places", help="Path to json file containing location info", default="nation_lakes.json")
parser.add_argument("--bg", 
                    help="Name of background tile to use, one of: 'StamenToner', 'StamenTonerLite', 'StamenTerrain', 'StamenWatercolor', 'GoogleMaps', 'GoogleSatellite', 'GoogleSatelliteHybrid', 'EsriSatellite'", 
                    default="StamenTonerLite")
parser.add_argument("--tags", help="Path to json file containing osm tags to get", default="tags_osm.json")
parser.add_argument("--styles", help="Path to json file containing style types for each tag", default="tag_styles.json")
parser.add_argument("--tiles", help="Path to json file containing map backgroud tile urls", default="tiles.json")

args=parser.parse_args()

if __name__=="__main__":
    
    # load settings from file
    with open(args.places) as f:
        places = json.load(f)
    with open(args.tags) as f:
        desired_tags = json.load(f)
    with open(args.styles) as f:
        tag_styles = json.load(f)
    with open(args.tiles) as f:
        tiles = json.load(f)
    

    # Load tile URL, checking for Stamen API key if needed
    background = args.bg
    if "stamen" in background.lower():
        if "STAMEN_API_KEY" in os.environ:
            STAMEN_API_KEY = os.environ["STAMEN_API_KEY"]  
            tiles_source = tiles[background].replace("API_KEY", STAMEN_API_KEY)
        else:
            print("Can't use '{background}' tiles, no Stamen API key found in environment variables")
            print("You can create one at https://stadiamaps.com/stamen/onboarding/create-account")
            print("Using 'GoogleMaps' tiles instead")
            background = "GoogleMaps"
            tiles_source = tiles[background]
    print(f"Selected background: {background}")

    # set general map parameters
    plot_dim = args.dim
    styles = build_style_dict(plot_dim)
    annotation_text_size = plot_dim * 0.5

    # make folder for maps
    map_folder = "maps"
    if not os.path.exists(map_folder):
        os.makedirs(map_folder)

    for place in places:
        print(f"Making map for: {place}")
        # parse location info
        place_name = place["name"] 
        west,east,south,north = place["west"], place["east"], place["south"], place["north"]

        # convert lon,lat to EPSG3857 (x,y)
        x_min, y_min = lonlat_to_xy(west, south)
        x_max, y_max = lonlat_to_xy(east, north) 
        dy = y_max - y_min
        dx = x_max - x_min
        figsize = calculate_plot_dimensions(plot_dim, dx, dy)

        # get OSM info for place with tags
        gdf = ox.features.features_from_bbox(north, south, east, west, desired_tags)
        gdf = gdf.to_crs(epsg=3857) # project to spherical mercator to match tiles
        gdf.reset_index(inplace=True)
        cols_to_keep = ['element_type', 'geometry', 'name'] + [key for key in desired_tags.keys() if key in gdf.columns]
        gdf = gdf[cols_to_keep]
        
        # extract each row of dataframe as a dict
        elements = gdf.to_dict(orient = "records")

        # make fig with backgound tiles
        fig,ax = plt.subplots(1, figsize=figsize, linewidth=1, edgecolor="#04253a")
        ax.set(xlim=(x_min, x_max), ylim=(y_min, y_max))
        ax.set_axis_off() # don't display axes with coordinates
        # add background tiles
        zoom_level = cx.tile._calculate_zoom(west,south,east,north) + 1  # get a bit more detail than calculated with +1
        cx.add_basemap(ax, source = tiles_source, zoom=zoom_level)

        # Plot features from OSM
        for element in elements:
            # get coordinates to plot for this element
            element_type = element["element_type"]
            coords_list = extract_coords(element["geometry"])
            for coords in coords_list:
                x,y = zip(*coords)
                ax.plot(x,y,**get_style(element, tag_styles, styles))
            # annotate nodes with names
            if (element_type == "node" and type(element["name"])!=float):
                ax.annotate(element["name"], (x[0],y[0]), 
                            size=annotation_text_size, 
                            xycoords='data', 
                            xytext=(0, annotation_text_size*0.75), 
                            textcoords='offset points', 
                            ha='center');
        # Add legend
        legend_items = ["campsite", "point_of_interest", "barrier", "mountain", 
                        "main_road", "secondary_road", "tertiary_road", 
                        "trail", "park_boundary"]
        legend_styles = {name: styles[name] for name in legend_items}
        legend_loc = (0.,0)
        ax = add_legend(ax, annotation_text_size, legend_styles, legend_loc)

        # Add distance scale bar
        plot_width_km = get_plot_width_km(west, east, south, north)
        scale_max_width_pct = 0.15
        scale_anchor_fig_x = 1-scale_max_width_pct
        scale_anchor_fig_y = 0.025
        scale_anchor_xy = fig_to_xy(scale_anchor_fig_x, scale_anchor_fig_y,x_min,x_max,y_min,y_max)
        ax = add_scale_bar(ax, scale_max_width_pct, scale_anchor_xy, 
                           plot_width_km, dx, dy, annotation_text_size)

        # Add map title
        ax.annotate(place["name"], fig_to_xy(0.5, 0.9, x_min, x_max, y_min, y_max), 
                    ha='center', 
                    va = "baseline", 
                    size=annotation_text_size*4);
        plt.tight_layout(pad=1)

        # save map
        path = f"{map_folder}/{place_name.replace(' ', '')}.png"
        plt.savefig(path, dpi=300, bbox_inches='tight', edgecolor=fig.get_edgecolor()) 
        print(f"Map saved to {path}")





    
