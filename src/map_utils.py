import pandas as pd
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

###### Coordinate transformations
def lonlat_to_xy(lon: float, lat: float) -> tuple:
    """Converts coordinates from EPSG4326 (lon,lat) to EPSG3857(x,y)
    Args:
        lon (float): latitude
        lat (float): longitude
    Returns:
        tuple: (x,y) coordinates in EPSG3857
    """
    proj = pyproj.Transformer.from_crs(4326, 3857, always_xy=True)
    return proj.transform(lon,lat)


def xy_to_lonlat(x: float,y: float) -> tuple:
    """Converts coordinates from EPSG3857(x,y) to EPSG4326 (lon,lat)
    Args:
        x (float): latitude
        y (float): longitude
    Returns:
        tuple: (lon,lat)) coordinates in EPSG4386
    """
    proj = pyproj.Transformer.from_crs(3857, 4326, always_xy=True)
    return proj.transform(x,y)


def xy_to_fig(x: float, y: float, x_min: float, x_max: float, y_min: float, y_max: float) -> tuple:
    """Converts coordinates from EPSG3857(x,y) to figure coordinates (x,y):[0.0,1.0]
    Args:
        x (float): x coordinate of point in EPSG3857 coordinates
        y (float): x coordinate of point in EPSG3857 coordinates
        x_min (float): x coordinate of west edge of map
        x_max (float): x coordinate of east edge of map
        y_min (float): y coordinate of south edge of map
        y_max (float): y coordinate of north edge of map
    Returns:
        tuple: (x_fig, y_fig) coordinates in figure space
    """
    x_fig = (x - x_min)/(x_max - x_min)
    y_fig = (y - y_min)/(y_max - y_min)
    return x_fig, y_fig


def fig_to_xy(x_fig: float, y_fig: float, x_min: float, x_max: float, y_min: float, y_max: float) -> tuple:
    """Converts from figure coordinates (x,y):[0.0,1.0], to EPSG3857(x,y) to 
    Args:
        x_fig (float): x coordinate of point in figure coordinates
        y_fig (float): x coordinate of point in figure coordinates
        x_min (float): x coordinate of west edge of map
        x_max (float): x coordinate of east edge of map
        y_min (float): y coordinate of south edge of map
        y_max (float): y coordinate of north edge of map
    Returns:
        tuple: (x_fig, y_fig) coordinates in figure space
    """
    x = x_fig * (x_max - x_min) + x_min
    y = y_fig * (y_max - y_min) + y_min
    return x,y


##### plotting
def calculate_plot_dimensions(plot_max_dim: float, dx: float, dy: float) -> tuple:
    """Caluclates figure dimensions (inches) to be used to create Matplotlib Figure
    Args:
        max_dim: maximum height or width desired for figure (inches)
        dx:      range of data's x dimension
        dy:      range of data's y dimension
    Returns:
        tuple:   (width, height) in inches
    """
    if dx >= dy:
        plot_width_in = plot_max_dim
        plot_height_in = plot_width_in * dy / dx
    else:
        plot_height_in = plot_max_dim
        plot_width_in = plot_height_in * dx / dy

    return (plot_width_in, plot_height_in)

def extract_coords(geom) -> list:
    """Extracts a list of coordinates ((x,y) tuples) for the geometry
    Args:
        geom(Shapely Geometry object): contains one or many geometries
    Returns:
        list: each item is itself a list of coordinate tuples, eg[[(x1,y1),(x2,y2)...],[(x1,y1),(x2,y2)...], ....]]
    """
    coords = []
    
    if geom.geom_type in ["Point", "LineString"]:
        coords.append(geom.coords[:])
    elif geom.geom_type == "Polygon":
        polygon_coords = extract_polygon_coords(geom)
        # print(f"polygon coords: {len(polygon_coords)}")
        coords.extend(polygon_coords)
    elif geom.geom_type == "MultiPolygon":
        polygons = [polygon for polygon in geom.geoms]
        for polygon in polygons:
            coords.extend(extract_polygon_coords(polygon))
    return coords


def extract_polygon_coords(geom) -> list:
    """Extracts a list of coordinates ((x,y) tuples) for exterior and interiors of Shapely Polygon
    Args:
        geom: Shapely Polygon object
    Returns:  
        list: each item is itself a list of coordinate tuples, eg[[(x1,y1),(x2,y2)...],[(x1,y1),(x2,y2)...], ....]]
    """
    coords = []
    if geom.geom_type == 'Polygon':
        coords.append(geom.exterior.coords[:])
        for interior in geom.interiors:
            coords.append(interior.coords[:])
    else:
        raise ValueError('Unhandled geometry type: ' + repr(geom.geom_type))
    return coords


def get_style(element: dict, tag_styles: dict, styles: dict) -> dict:
    """Extracts a list of coordinates ((x,y) tuples) for exterior and interiors of Shapely Polygon
    Args:
        element:     contains OSM tags (key:value) for specific element (node,way, or relation)
        tag_styles:  links OSM tags to the style settings contained in `style`
        styles:      style settings used by matplotlib for lines and markers
    Returns:  
        dict:    contains kwargs to be used by ax.plot()
    """
    style = {}
    for key,value in element.items():
        if key in tag_styles:
            if value in tag_styles[key]:
                style = styles[tag_styles[key][value]]
    return style


def add_legend(ax: matplotlib.axes._axes.Axes, text_size: float, 
               legend_styles: dict, loc: tuple=(0,0)) -> matplotlib.axes._axes.Axes:
    """Adds legend to map
    Args:
        ax:           axis to draw lengend onto
        text_size:    size of legend text  
        legend_styles: dict with keys=text, values=dict containing matplolib style kwargs for symbol
        loc:          location to place legend in figure corrdinates (0.0-1.0), default=(0,0) (lower left)
    Returns:
        matplotlib.axes._axes.Axes: axis object now with legend
    """
    ax.legend(
        handles=[Line2D([0], [0], label=name.capitalize().replace("_", " "), **style) for name,style in legend_styles.items()], 
        title = " Legend", 
        alignment='left', # position of legend title
        title_fontsize = text_size + 1, # make title a little bigger than text
        loc=loc,          # location of legend on map
        fontsize=text_size,
        borderpad=1.5,
        framealpha=1      # make legend box opaque
    ) 
    return ax


#### Scale bar functions
# def add_scale_bar(ax: matplotlib.axes._axes.Axes, max_width_pct: float, 
#                   anchor: tuple, plot_width_km, dx:float, dy:float,
#                   text_size: float) -> matplotlib.axes._axes.Axes:
#     """Adds horizontal bar indicating distance scale on map in kilometers
#     Args:
#         ax (matplotlib.axes._axes.Axes): ax containing map
#         max_width_pct (float): the maximum size of scale bar as fraction of map width
#         anchor (tuple): (x,y) coordinates for lower left corner of scale bar (in data coordinates)
#         plot_width_km (float): distance represented by map width (in km)
#         dx (float): width of map in data coordinates
#         dy (float): height of map in data coordinates
#         text_size (float): 
#     Returns:
#         matplotlib.axes._axes.Axes: ax with scale bar on it
#     """
#     # get height and width of bar in data coordinates
#     scale_dimesion_km = get_scale_dimesion_km(plot_width_km,max_width_pct)
#     width = scale_dimesion_km / plot_width_km * dx 
#     height = max(dx,dy)*0.0025 
#     print(f"scale_dimesion_km={scale_dimesion_km}\nwidth={width}\nheight={height}")
#     anchor_x, anchor_y = anchor # unpack anchor point into x,y in data

#     # Create a Rectangle patch for scale bar
#     bar = patches.Rectangle(
#         xy=anchor, 
#         width = width, 
#         height = height, 
#         linewidth=0.5,
#         edgecolor='black',
#         facecolor='lightgrey',
#         fill=True
#     )
#     ax.add_patch(bar)
    
#     # Add annotation
#     ax.annotate(
#         f"{scale_dimesion_km} km", 
#         xy=(anchor_x + width/2 , anchor_y), 
#         xycoords='data', 
#         size=text_size, 
#         xytext = (0,-text_size),
#         textcoords = "offset points",
#         ha='center',
#     )
#     return ax
def add_scale_bar(ax: matplotlib.axes._axes.Axes, max_width_pct: float, 
                  anchor: tuple, plot_width_km, dx:float, dy:float,
                  text_size: float) -> matplotlib.axes._axes.Axes:
    """Adds horizontal bar indicating distance scale on map in kilometers
    Args:
        ax (matplotlib.axes._axes.Axes): ax containing map
        max_width_pct (float): the maximum size of scale bar as fraction of map width
        anchor (tuple): (x,y) coordinates for lower left corner of scale bar (in data coordinates)
        plot_width_km (_type_): distance represented by map width (in km)
        dx (float): width of map in data coordinates
        dy (float): height of map in data coordinates
        text_size (float): 
    Returns:
        matplotlib.axes._axes.Axes: ax with scale bar on it
    """
    # get height and width of bar in data coordinates
    scale_dimesion_km = get_scale_dimesion_km(plot_width_km, max_width_pct)
    width = scale_dimesion_km / plot_width_km * dx 
    height = max(dx,dy)*0.0025 

    anchor_x, anchor_y = anchor # unpack anchor point into x,y in data
    
    # Create a Rectangle patch for scale bar
    bar = patches.Rectangle(
        xy=anchor, 
        width = width, 
        height = height, 
        linewidth=0.5,
        edgecolor='black',
        facecolor='lightgrey',
        fill=True
    )
    ax.add_patch(bar)
    
    # Add annotation
    ax.annotate(
        f"{scale_dimesion_km} km", 
        xy=(anchor_x + width/2 , anchor_y), 
        xycoords='data', 
        size=text_size, 
        xytext = (0,-text_size),
        textcoords = "offset points",
        ha='center',
    )
    return ax

def get_scale_dimesion_km(plot_width_km: float, max_width_pct: float) -> int:
    """Determines the size (in kilomaters) that scale bar will represent on the map
    Only rounded values starting with 1,2,5 (multiplied by 10**x) allowed
    Args:
        plot_width_km (float): distance in kilometers represented by the width of the map
        max_width_pct (float): the maximum size of scale bar as fraction of map width  

    Returns:
        int: the number of km that scale bar will represent on the map
    """
    scale_dimesions = [0.1,0.2,0.5,1,2,5,10,20,50,100,200,500] # hard-coded values typical for canoe trips
    max_scale_dimension = plot_width_km * max_width_pct
    for scale_dimesion in scale_dimesions[::-1]:
        if scale_dimesion <= max_scale_dimension:
            break
    return scale_dimesion

def get_plot_width_km(west: float,east: float,south: float,north: float) -> float:
    """Calculates the width represented by the map at its center latitude
    Args:
        west (float): longitude of west edge of map
        east (float): longitude of east edge of map
        south (float): latitude of south edge of map
        north (float): latitude of north edge of map
    Returns:
        float: width in km
    """
    lat = (north + south) / 2 # central latitude to minimize errors
    return geopy.distance.geodesic((lat,east), (lat,west)).km


