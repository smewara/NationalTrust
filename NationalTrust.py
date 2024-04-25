import ee
import folium
from IPython.display import display, Image
import geopandas as gpd
from shapely.geometry import mapping
import json

ee.Authenticate()

# Initialize Earth Engine
ee.Initialize(project='uk-nationaltrust')

NT_sites = gpd.read_file(r'C:\NationalTrust\NT Land Files\NT_Land_Always_Open.shp').to_crs(epsg=4326)
england_sites = gpd.read_file(r'C:\NationalTrust\England_ct_1991\england_ct_1991.shp').to_crs(epsg=4326)
wales_sites = gpd.read_file(r'C:\NationalTrust\Wales_ct_1991\wales_ct_1991.shp').to_crs(epsg=4326)

centroid = england_sites.geometry.centroid
map_center = [centroid.y.mean(), centroid.x.mean()]
m = folium.Map(location=map_center, zoom_start=5)

# Define a function to add Earth Engine image tiles to folium map
def add_ee_layer(self, ee_image_object, vis_params, name):
    map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
    folium.raster_layers.TileLayer(
        tiles=map_id_dict['tile_fetcher'].url_format,
        attr='Google Earth Engine',
        name=name,
        overlay=True,
        control=True
    ).add_to(self)

def style_function(feature):
    return {
        'color': 'purple',  # Set the boundary color to purple
        'weight': 0.5,         # Set the boundary weight (thickness)
        'fillOpacity': 0.0   # Set the fill opacity to 0 (transparent)
    }

def style_function_nt_sites(feature):
    return {
        'color': 'yellow',  # Set the boundary color to purple
    }

# Add the Earth Engine function to folium
folium.Map.add_ee_layer = add_ee_layer

folium.GeoJson(NT_sites.to_json(), style_function=style_function_nt_sites).add_to(m)
folium.GeoJson(england_sites.to_json(), style_function=style_function).add_to(m)
folium.GeoJson(wales_sites.to_json(), style_function=style_function).add_to(m)
#folium.LayerControl().add_to(m)
m

def add_forest_gain_loss(geometry_str, name):
    # Convert the list of geometries to an Earth Engine MultiPolygon
    geometry = ee.Geometry(geometry_str)

    # Load the Hansen Global Forest Change dataset
    hansenImage = ee.Image("UMD/hansen/global_forest_change_2023_v1_11").clip(geometry)

    # Define tree cover, loss, gain, and loss year layers
    treeCover = hansenImage.select(['treecover2000'])
    lossImage = hansenImage.select(['loss'])
    gainImage = hansenImage.select(['gain'])
    lossYear = hansenImage.select(['lossyear'])
    gainAndLoss = gainImage.And(lossImage)

    # Calculate tree cover pixel areas
    treeCoverPixelAreas = treeCover.gte(30).selfMask().multiply(ee.Image.pixelArea())

    # Calculate tree cover area in 2000
    treeCoverArea2000 = treeCoverPixelAreas.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=geometry,
        scale=30,
        maxPixels=1e9
    )

    # Calculate forest loss area since 2000
    lossAreaImage = lossImage.multiply(ee.Image.pixelArea())
    totalLossArea = lossAreaImage.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=geometry,
        scale=30,
        maxPixels=1e9
    )

    # Convert forest cover and loss areas to kilo hectares
    area2000KiloHectares = ee.Number(treeCoverArea2000.get('treecover2000')).divide(1e7)    
    totalLossAreaKiloHectares = ee.Number(totalLossArea.get('loss')).divide(1e7)
    percentageLoss = (totalLossAreaKiloHectares.round()).divide(area2000KiloHectares.round()).multiply(100)

    if (percentageLoss.getInfo() > 10.0):
        m.add_ee_layer(treeCover.updateMask(treeCover),
                    {'palette': '000000, 00FF00', 'max': 100}, 'Forest Cover')

        m.add_ee_layer(lossImage.updateMask(lossImage),
                    {'palette': 'FF0000'}, 'Loss')

        m.add_ee_layer(gainImage.updateMask(gainImage),
                    {'palette': '0000FF'}, 'Gain')
        
        #m.add_ee_layer(gainAndLoss.updateMask(gainAndLoss),
                   # {'palette': 'yellow'}, 'Gain and Loss')

        # Prepare the HTML popup content
        popup_html = f"""
            <h4>Forest Cover Statistics for {name}</h4>
            <ul>
                <li>Total Tree Cover in 2000: {area2000KiloHectares.getInfo():.2f} KHa</li>
                <li>Total Forest Loss Since 2000: {totalLossAreaKiloHectares.getInfo():.2f} KHa</li>
                <li>Percentage Forest Loss Since 2000: {percentageLoss.getInfo():.2f}%</li>
            </ul>
        """
        # Create a Folium popup
        popup = folium.Popup(html=popup_html, max_width=500)
        centroid_coords = geometry.centroid().coordinates().reverse().getInfo()
        folium.Marker(location=centroid_coords, popup=popup).add_to(m)

def get_feature_collection(gdf):
    features = []
    for idx, row in gdf.iterrows():
        feature = {
            "type": "Feature",
            "properties": {"name": row['name']},
            "geometry": mapping(row['geometry'])
        }
        features.append(feature)

    feature_collection = {
        "type": "FeatureCollection",
        "features": features
    }
    return feature_collection

def process_feature(feature):
  geom = feature['geometry']
  name = feature['properties']['name']
  print('\nProcessing:', name)
  add_forest_gain_loss(geom, name)


def process_countries(region):
  feature_coll = get_feature_collection(region)
  for feature in feature_coll['features']:
    process_feature(feature=feature)
    save_map()
    
def save_map():
   m.save('NT_forest_loss.html')

feature_coll = get_feature_collection(england_sites)
#process_feature(feature_coll['features'][1])
process_countries(england_sites)
process_countries(wales_sites)
save_map()

display(m)

