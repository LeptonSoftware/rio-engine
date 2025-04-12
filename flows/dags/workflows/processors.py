# This file contains all node processing functions
import os
from urllib.parse import urlencode
from shapely.geometry import shape
import pandas as pd
import geopandas as gpd
import requests
from lib.node import Node, table_exists, get_column_names
import json
from supabase import create_client
import time
from shapely import wkt
from shapely.geometry import Point
import re
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.geometry import LineString
import math
import polyline
import numpy as np
from datetime import datetime, timedelta
from shapely.ops import cascaded_union


def get_db_engine_workflows():
    # import from lib.db and call that
    from lib.db import get_db_engine_workflows as fn

    return fn()


def get_db_engine_lepton():
    # import from lib.db and call that
    from lib.db import get_db_engine_lepton as fn

    return fn()
# import asyncio


def sql(**kwargs):
    node = Node(**kwargs)
    query = node.input("query")
    print(query)
    # the query will include table names like $t0, $t1, $t2, etc.
    # we need to replace them with the actual table names from the node.input, we should only request the tables that are used in the query
    # we can do this by parsing the query and replacing the table names with the actual table names
    # we can use the re module to do this
    import re

    pattern = r"\$(t\d+)"
    query, _ = re.subn(
        pattern,
        lambda x: f'workflows."{node.input(x.group(1))}" as {x.group(1)}',
        query,
    )
    print(query)
    table_name, is_cached = node.compute_in_db(
        func_name="sql", query=query, inputs={"query": query}
    )
    return {
        "output": table_name,
        "is_cached": is_cached,
    }


# Node processors
def geocode(**kwargs):
    """
    Process geocoding requests using either Lepton or Google provider
    Returns geocoded data including administrative boundaries and postal codes
    """
    from airflow.models import Variable

    node = Node(**kwargs)
    feature_collection_key = node.input("featureCollection")
    provider = node.input("provider", "lepton")
    # Get the API key from data or environment
    if provider == "google":
        # Query to get coordinates from input features
        engine = get_db_engine_lepton()
        columns = get_column_names(engine, f'workflows."{feature_collection_key}"')
        select_columns = ", ".join(
            [col for col in columns if col not in ["latitude", "longitude"]]
        )
        print("columnsLLLLL::::", columns)
        if "latitude" in columns and "longitude" in columns:
            query = f"""
                SELECT {select_columns} latitude, longitude
                FROM workflows."{feature_collection_key}"
            """
        elif "latitude" in columns:
            query = f"""
                SELECT {select_columns} latitude, ST_X(geometry) as longitude
                FROM workflows."{feature_collection_key}"
            """
        elif "longitude" in columns:
            query = f"""
                SELECT {select_columns} ST_Y(geometry) as latitude, longitude
                FROM workflows."{feature_collection_key}"
            """
        else:
            query = f"""
                SELECT {select_columns} 
                    ST_X(ST_Centroid(geometry)) as longitude, 
                    ST_Y(ST_Centroid(geometry)) as latitude
                FROM workflows."{feature_collection_key}"
            """
        df = gpd.read_postgis(query, engine, geom_col="geometry")
        print(df.head())
        print(df.columns)
        df["pincode"] = ""
        df["state"] = ""
        df["city"] = ""
        df["district"] = ""
        df["tehsil"] = ""
        for _, row in df.iterrows():
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "address": f"{row.latitude},{row.longitude}",
                "key": "AIzaSyByraLO7WVzW-9K-H6NErKftVydyJK2058",
            }
            response = requests.get(url, params=params)
            if response.ok:
                geocoded = response.json()
                # Extract address components
                address_data = node.parse_google_response(geocoded)
                df.at[_, "pincode"] = address_data.get("pincode", "")
                df.at[_, "state"] = address_data.get("state", "")
                df.at[_, "city"] = address_data.get("city", "")
                df.at[_, "district"] = address_data.get("district", "")
                df.at[_, "tehsil"] = address_data.get("tehsil", "")
        output_table_name = node.create_output_table_name(
            func_name="geocode",
            inputs={"featureCollection": feature_collection_key, "provider": provider},
        )
        try:
            print(df.head())
            print(df.columns)
            # results_df = gpd.GeoDataFrame(results, geometry="geometry")
            node.save_df_to_postgres(df, output_table_name)
        except Exception as e:
            print(f"table exists: {str(e)}")
    else:  # Lepton provider
        import re

        print("geocode, lepton")
        # Updated query to handle properties as a JSONB column
        # query = f"""
        #     WITH output AS (
        #         SELECT *
        #         FROM workflows."{feature_collection_key}"
        #     ),
        #     filtered_pincode AS (
        #         SELECT DISTINCT ON (t."_gid")
        #             t.*,
        #             p.pincode,
        #             p.state_name,
        #             p.city,
        #             p.district_name,
        #             p.tehsil_name
        #         FROM output t
        #         JOIN pincode p ON p.geom && t.geometry
        #             AND ST_Intersects(p.geom, t.geometry)
        #     ),
        #     filtered_locality AS (
        #         SELECT DISTINCT ON (t."_gid")
        #             t.*,
        #             l.locality,
        #             l.sub_locality,
        #             l.sub_sub_locality
        #         FROM output t
        #         JOIN raw.locality_v2 l ON l.geom && t.geometry
        #             AND ST_Intersects(l.geom, t.geometry)
        #     )
        #     SELECT
        #         p.pincode,
        #         p.state_name AS state,
        #         p.city,
        #         p.district_name AS district,
        #         p.tehsil_name AS tehsil,
        #         l.locality,
        #         l.sub_locality,
        #         l.sub_sub_locality,
        #         t."_gid",
        #         t.geometry
        #     FROM output t
        #     LEFT JOIN filtered_pincode p ON p."_gid" = t."_gid"
        #     LEFT JOIN filtered_locality l ON l."_gid" = t."_gid"
        # """
        output_table_name = node.create_output_table_name(
            func_name="geocode",
            inputs={"featureCollection": feature_collection_key, "provider": provider},
        )
        if table_exists(get_db_engine_lepton(), output_table_name):
            print("using value from cache")
            return {"output": output_table_name, "is_cached": True}
        # output_table_name, is_cached = node.compute_in_db(
        #     func_name="geocode",
        #     inputs={"featureCollection": feature_collection_key, "provider": provider},
        #     query=query,
        #     geom_col=["geometry"],
        # )
        previous_data = gpd.read_postgis(
            f'SELECT * FROM workflows."{feature_collection_key}"',
            get_db_engine_lepton(),
            geom_col="geometry",
        )
        geocode_post_data = previous_data[["_gid", "geometry"]]
        geocode_post_data.rename(columns={"_gid": "id"}, inplace=True)
        
        # Get centroid for polygon geometries, keep points as-is
        geocode_post_data[["latitude", "longitude"]] = geocode_post_data["geometry"].apply(
            lambda x: pd.Series([
                x.centroid.y if x.geom_type in ['Polygon', 'MultiPolygon'] else x.y,
                x.centroid.x if x.geom_type in ['Polygon', 'MultiPolygon'] else x.x
            ])
        )
        post_data = geocode_post_data[["id", "latitude", "longitude"]].to_dict("records")
        print(post_data)

        def rename_conflicting_columns(previous_data, locality_data):
            print("previous_data: ", previous_data.columns)
            print("locality_data: ", locality_data.columns)

            # Initialize seen dictionary with existing column names from previous_data
            seen = {}
            for col in previous_data.columns:
                seen[col.rsplit("_", 1)[0]] = (
                    seen.get(col.rsplit("_", 1)[0], 0) + 1
                )

            new_columns = []

            for col in locality_data.columns:
                if col == "_gid":  # Keep join key unchanged
                    new_columns.append(col)
                    continue

                base_col = col.rsplit("_", 1)[
                    0
                ]  # Remove any existing suffix (_x/_y or _1/_2)

                if base_col in seen:
                    # Check if the column already has a numeric suffix
                    match = re.search(r"_(\d+)$", col)
                    if match:
                        num = int(match.group(1))  # Extract existing number
                        seen[base_col] = max(
                            seen.get(base_col, 0), num
                        )  # Ensure correct numbering

                    # Increment suffix for conflict resolution
                    seen[base_col] += 1
                    new_col = f"{base_col}_{seen[base_col]}"
                else:
                    seen[base_col] = 0  # Initialize if not in previous_data
                    new_col = col

                new_columns.append(new_col)

            locality_data.columns = new_columns  # Apply updated column names
            return locality_data

        try:
            response = requests.post(
                "https://api.leptonmaps.com/v1/detect/locality",
                json=post_data,
                headers={"X-API-Key": Variable.get("LEPTON_API_KEY")},
                timeout=30,  # Set timeout to prevent hanging requests
            )
            response.raise_for_status()  # Raise error for non-200 responses
            api_response = response.json()
            print("API Response:", api_response)

            if "data" in api_response:
                locality_data = pd.DataFrame(api_response["data"]).drop(
                    columns=["gmap_direction_link"], errors="ignore"
                )

                # Ensure data consistency before merging
                if not locality_data.empty:
                    locality_data.rename(columns={"id": "_gid"}, inplace=True)
                    locality_data["_gid"] = locality_data["_gid"].astype(int)
                    print("Locality Data:", locality_data.columns)
                    locality_data = rename_conflicting_columns(
                        previous_data, locality_data
                    )
                    merged_data = previous_data.merge(
                        locality_data, on="_gid", how="left"
                    )
                    print("Merged Data:", merged_data)
                else:
                    print("No locality data returned from API.")
                    merged_data = (
                        geocode_post_data.copy()
                    )  # Fallback in case of empty response

            else:
                print("Unexpected API response format:", api_response)
                merged_data = (
                    geocode_post_data.copy()
                )  # Handle cases where 'data' key is missing

        except requests.RequestException as e:
            print(f"API Request Failed: {e}")
            merged_data = (
                geocode_post_data.copy()
            )  # Use original data in case of failure

    # def rename_conflicts(columns):
    #     seen = {}
    #     new_columns = []

    #     print("Old columns: ", columns)

    #     for col in columns:
    #         base_col = col.rsplit("_", 1)[0]  # Remove _x/_y to get base name
    #         print("Base column: ", base_col)
    #         # Check if base_col already has a numeric suffix (e.g., "column_2")
    #         match = re.search(r"_(\d+)$", base_col)
    #         if match:
    #             num = int(match.group(1))  # Extract the existing number
    #             base_col = base_col.rsplit("_", 1)[0]  # Remove the existing number
    #             seen[base_col] = max(
    #                 seen.get(base_col, 0), num
    #             )  # Ensure we continue from the highest number
    #             print("Seen: ", seen)
    #         if col.endswith(("_x", "_y")) or base_col in seen:
    #             #     # If column is a duplicate or has _x/_y, increase the suffix
    #             seen[base_col] = seen.get(base_col, 0) + 1
    #             new_col = f"{base_col}_{seen[base_col]}"
    #         else:
    #             new_col = col

    #         new_columns.append(new_col)

    #     print("New columns: ", new_columns)
    #     return new_columns

    # merged_data.columns = rename_conflicts(merged_data.columns)

    # Save results to new table
    node.save_df_to_postgres(merged_data, output_table_name)
    return {"output": output_table_name, "is_cached": False}


def alias(**kwargs):
    node = Node(**kwargs)
    db = get_db_engine_lepton()
    alias = node.input("alias")
    input_table = node.input("input",[])

    # if alias is already a table, leave it as is
    if table_exists(db, alias):
        return {"output": alias, "is_cached": False}
    # if a view with the same name already exists, drop it
    if(input_table == [] or input_table == None):
        return { "output":"","is_cached": False}
    db.execute(f'DROP VIEW IF EXISTS workflows."{alias}"')
    db.execute(f'CREATE VIEW workflows."{alias}" AS SELECT * FROM workflows."{input_table}"')
    db.execute(f'GRANT ALL ON workflows."{alias}" TO authenticated;')
    return {"output": alias, "is_cached": False}

def buffer(**kwargs):
    """
    Creates a buffer around geometries in the provided feature collection.
    
    Args:
        featureCollection: Input feature collection
        distance: Buffer distance in meters
        featureId: Optional ID of a specific feature to process (processes all features if not provided)
    """
    node = Node(**kwargs)
    # columns = node.get_column_names(get_db_engine_lepton(), f'{node.input('featureCollection')}')
    # valid_columns = [f'"{col}"' for col in columns if col not in ['geometry']]
    input_table = node.input("featureCollection")
    feature_id = node.input("featureId", None)  # Get feature_id if provided
    
    # Build query based on whether feature_id is provided
    if feature_id is not None:
        # Query for a specific feature with proper type casting
        query = f'''
            SELECT ST_Buffer(geometry::geography, {node.input("distance", 100)}) AS geometry 
            FROM workflows."{input_table}"
            WHERE _gid = {feature_id}::bigint
        '''
    else:
        # Query for all features
        query = f'SELECT ST_Buffer(geometry::geography, {node.input("distance", 100)}) AS geometry FROM workflows."{input_table}"'
    
    output_table_name, is_cached = node.compute_in_db(
        func_name="buffer",
        inputs={
            "distance": node.input("distance"),
            "featureCollection": input_table,
            "featureId": feature_id,
        },
        query=query,
        geom_col=["geometry"],
        exclude_col=["geometry"],
        input_table_name=input_table,
    )
    return {"buffer": output_table_name, "is_cached": is_cached}


def area(**kwargs):
    node = Node(**kwargs)
    input_table = node.input("featureCollection")
    output_table_name, is_cached = node.compute_in_db(
        func_name="area",
        inputs={"featureCollection": input_table},
        query=f'SELECT ST_Area("{input_table}".geometry::geography) AS area, * FROM workflows."{input_table}"',
        geom_col=["geometry"],
        input_table_name=input_table,
    )
    return {
        "output": output_table_name,
        "is_cached": is_cached,
    }

def syncdatasource(**kwargs):
    node = Node(**kwargs)
    print(kwargs)
    return _import_data_source(node, node.input("source"))

def default(**kwargs):
    node = Node(**kwargs)
    raise ValueError(f"No processor found for node type")

def _import_data_source(node, source: str):
    layer_source = source
    # Now get the data field from the parsed JSON
    output_table_name = node.create_output_table_name(
        func_name="smartmarket_layer", inputs=layer_source
    )
    if table_exists(get_db_engine_lepton(), output_table_name):
        print("using value from cache")
        return {"output": output_table_name, "is_cached": True}

    # Get the GeoJSON data
        print(f"Fetching GeoJSON from URL: {layer_source['url']}")
        response = requests.get(layer_source["url"])
        if not response.ok:
            raise RuntimeError(f"Failed to fetch GeoJSON from URL: {response.status_code}")
        geojson_data = response.json()
        response = requests.get(layer_source["url"])
        if not response.ok:
            raise RuntimeError(f"Failed to fetch GeoJSON from URL: {response.status_code}")
        geojson_data = response.json()
        response = requests.get(layer_source["url"])
        if not response.ok:
            raise RuntimeError(f"Failed to fetch GeoJSON from URL: {response.status_code}")
        geojson_data = response.json()
        response = requests.get(layer_source["url"])
        if not response.ok:
            raise RuntimeError(f"Failed to fetch GeoJSON from URL: {response.status_code}")
        geojson_data = response.json()
        response = requests.get(layer_source["url"])
        if not response.ok:
            raise RuntimeError(f"Failed to fetch GeoJSON from URL: {response.status_code}")
        geojson_data = response.json()
    if layer_source["type"] == "geojson_url":
        geojson_data = requests.get(layer_source["url"]).json()
    else:
        # Call the data loader API
        print("calling data loader api with layer source: ", layer_source)
        # can we stream the response from the data loader api to a file and then read it into a dataframe?
        from airflow.models import Variable
        response = requests.post(
            Variable.get("SMART_MARKET_API_URL") + "/api/smart-market/data-loader",
            json=layer_source,
            headers={"Content-Type": "application/json"},
        )
        print("response: ", response.json())
        if not response.ok:
            raise RuntimeError(
                f"Data loader API request failed: {response.status_code}"
            )

        geojson_data = response.json()

    # # # stream the response to a file
    # with open(f"geojson_data_{output_table_name}.geojson", "w") as f:
    #     json.dump(geojson_data, f, separators=(',', ':'))
    
    # Create DataFrame from GeoJSON features while preserving properties and geometry
    features_list = []
    for feature in geojson_data['features']:
        # Extract properties
        properties = feature.get('properties', {})
        # Extract geometry
        geometry = shape(feature['geometry'])
        # Combine properties and geometry into a single dict
        feature_dict = {**properties, 'geometry': geometry}
        features_list.append(feature_dict)
    
    # Create GeoDataFrame
    try:
        # First try the standard approach
        df = gpd.GeoDataFrame(features_list, geometry='geometry', crs="EPSG:4326")
    except Exception as e:
        print(f"Error creating GeoDataFrame: {e}")
        # Try alternative approaches here...
        
    # Ensure _gid column contains numeric values
    if "_gid" not in df.columns:
        df["_gid"] = range(1, len(df) + 1)
    else:
        # Convert _gid to numeric, handling any strings
        try:
            df["_gid"] = pd.to_numeric(df["_gid"], errors='coerce')
            # Fill any NaN values with sequential numbers starting from max+1
            max_val = df["_gid"].max() if not df["_gid"].isna().all() else 0
            nan_mask = df["_gid"].isna()
            new_ids = range(int(max_val) + 1, int(max_val) + 1 + nan_mask.sum())
            df.loc[nan_mask, "_gid"] = list(new_ids)
        except Exception as e:
            print(f"Error converting _gid to numeric: {e}")
            # If conversion fails, just recreate the column
            df["_gid"] = range(1, len(df) + 1)
    is_cached = node.save_df_to_postgres(df, output_table_name)
    print("is_cached: ", is_cached)
    # os.remove(f"geojson_data_{output_table_name}.geojson")
    return {"output": output_table_name, "is_cached": is_cached}

def smartmarketlayer(**kwargs):
    from airflow.models import Variable

    node = Node(**kwargs)

    project_id = node.input("project_id")
    layer_id = node.input("layer_id")

    supabase = create_client(Variable.get("SUPABASE_URL"), Variable.get("SUPABASE_KEY"))
    try:
        # Download and decode project.json
        timestamp = int(time.time() * 1000)  # Current timestamp in milliseconds
        project_json_bytes = supabase.storage.from_("projects").download(
            f"{project_id}/project.json?t={timestamp}"
        )
        project_json_str = project_json_bytes.decode("utf-8")
        project_data = json.loads(project_json_str)
        print(project_data)
        # Get the layer data
        if layer_id not in project_data.get("layers", {}):
            raise ValueError(f"Layer {layer_id} not found in project")
        print(project_data["layers"])
        layer_info = project_data["layers"][layer_id]
        print(layer_info)
        # Parse the source string directly since it's already JSON
        layer_source = json.loads(layer_info["source"])
        # Now get the data field from the parsed JSON
        return _import_data_source(node, layer_source)

    except Exception as e:
        raise RuntimeError(f"Failed to process smart market layer: {str(e)}")


def merge(**kwargs):
    node = Node(**kwargs)
    
    # Get all potential input collections
    collections = {
        'a': node.input('featureCollectionA', ""),
        'b': node.input('featureCollectionB', ""),
        'c': node.input('featureCollectionC', ""),
        'd': node.input('featureCollectionD', ""),
        'e': node.input('featureCollectionE', "")
    }
    
    # Filter out empty strings
    valid_collections = {k: v for k, v in collections.items() if v}
    
    if not valid_collections:
        raise ValueError("At least one feature collection must be provided")
    
    # Get column definitions for all tables
    all_columns = {}
    column_types = {}
    for alias, table in valid_collections.items():
        cols = get_column_defs(table)
        all_columns[alias] = cols
        # Track all unique columns and their types
        for col, type_ in cols.items():
            # Skip empty column names
            if not col.strip():
                continue
            if col not in column_types:
                column_types[col] = set()
            column_types[col].add(type_)
    
    # Build column list handling type conflicts
    final_columns = {}
    for col, types in column_types.items():
        # Skip empty or invalid column names
        if not col.strip():
            continue
        
        if col == '_gid':
            continue
        
        if len(types) == 1:
            # No type conflict, use original column name and type
            type_name = next(iter(types))
            final_columns[col] = type_name
        else:
            # For conflicting types, choose the most compatible type
            if 'double precision' in types:
                final_columns[col] = 'double precision'
            elif 'numeric' in types:
                final_columns[col] = 'numeric'
            elif 'integer' in types:
                final_columns[col] = 'integer'
            elif 'text' in types:
                final_columns[col] = 'text'
            else:
                # Default to text for other type conflicts
                final_columns[col] = 'text'
    
    # Build UNION ALL query
    union_parts = []
    for alias, table in valid_collections.items():
        table_cols = all_columns[alias]
        select_parts = []
        
        # Handle each column from the combined set of columns
        for col, target_type in final_columns.items():
            if col == 'geometry':
                select_parts.append(f'{alias}.geometry')
                continue
                
            if col in table_cols:
                # Column exists in this table - cast if needed
                source_type = table_cols[col]
                if source_type != target_type:
                    select_parts.append(f'CAST({alias}."{col}" AS {target_type}) AS "{col}"')
                else:
                    select_parts.append(f'{alias}."{col}"')
            else:
                # Column doesn't exist in this table, add NULL with the appropriate type
                select_parts.append(f'CAST(NULL AS {target_type}) AS "{col}"')
        
        select_clause = ',\n            '.join(select_parts)
        union_parts.append(f"""
            (SELECT {select_clause}
             FROM workflows."{table}" {alias})
        """)
    
    query = f"""
        SELECT 
            ROW_NUMBER() OVER () as _gid,
            merged.*
        FROM (
            {" UNION ALL ".join(union_parts)}
        ) as merged
    """
    
    # Execute the merge
    output_table, is_cached = node.compute_in_db(
        "merge",
        valid_collections,
        query,
        geom_col=["geometry"] if "geometry" in column_types else None
    )
    
    return {
        "featureCollection": output_table,
        "is_cached": is_cached
    }

def get_column_defs(table_name):
    """
    Get column definitions for a table.
    Returns a dictionary of column names and their types.
    """
    engine = get_db_engine_lepton()
    query = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'workflows' 
        AND table_name = %s
    """
    result = engine.execute(query, (table_name,))
    return {row[0]: row[1] for row in result}

def catchment(**kwargs):
    from airflow.models import Variable

    print("Creating catchment")
    node = Node(**kwargs)
    # catchment_obj = Catchment()
    catchment_type = (
        "DRIVE_DISTANCE"
        if node.input("catchmentType") == "Drive Distance Polygon"
        else "DRIVE_TIME"
        if node.input("catchmentType") == "Drive Time Polygon"
        else "BUFFER"
    )
    input_table_name = node.input("points")
    accuracy_level = node.input("accuracy","MEDIUM")
    analysis_datetime = node.input("date","2025-03-11 00:00:00")
    drive_time_dist = node.input("slider",10)
    feature_id = node.input("featureId", None)  # Get feature_id if provided

    engine = get_db_engine_lepton()
    output_table_name = node.create_output_table_name(
        func_name="catchment",
        inputs={
            "points": input_table_name,
            "catchmentType": catchment_type,
            "accuracy": accuracy_level,
            "date": analysis_datetime,
            "slider": drive_time_dist,
            "featureId": feature_id,
        },
    )
    if table_exists(engine, output_table_name):
        print("using value from cache")
        return {"output": output_table_name, "is_cached": True}
    print(catchment_type)
    if "buffer" in catchment_type.lower():
        # Build query based on whether feature_id is provided
        if feature_id is not None:
            # Query for a specific feature with proper type casting
            query = f'''
                SELECT ST_Buffer("{input_table_name}".geometry::geography, {node.input("distance")}) AS geometry 
                FROM workflows."{input_table_name}"
                WHERE _gid = {feature_id}::bigint
            '''
        else:
            # Query for all features
            query = f'SELECT ST_Buffer("{input_table_name}".geometry::geography, {node.input("distance")}) AS geometry FROM workflows."{input_table_name}"'
            
        output_table_name, is_cached = node.compute_in_db(
            func_name="buffer",
            inputs={
                "distance": drive_time_dist * 1000,
                "featureCollection": input_table_name,
                "featureId": feature_id,
            },
            query=query,
            geom_col=["geometry"],
            exclude_col=["geometry"],
            input_table_name=input_table_name,
        )
        return {
            "output": output_table_name,
            "is_cached": is_cached,
        }

    def get_catchment(
        lat,
        lng,
        catchment_type,
        accuracy_time_based,
        is_drive_time,
        drive_time_dist,
        departure_time,
    ):
        if is_drive_time:
            key = "drive_time"
        else:
            key = "drive_distance"
        base_url = "https://api.leptonmaps.com/v1/geojson/catchment"
        all_params = {
            "latitude": lat,
            "longitude": lng,
            "catchment_type": catchment_type,
            key: drive_time_dist,
            "accuracy_time_based": accuracy_time_based,
            "departure_time": departure_time,
        }
        params = {k: v for k, v in all_params.items() if v is not None}
        print("paramas: ", params)
        url = base_url + "?" + urlencode(params)
        print(url, params)
        response = requests.get(
            url,
            headers={"x-api-key": Variable.get("LEPTON_API_KEY")},
        )

        if response.ok:
            data = response.json()
            print(data)
            features = data.get("features", [])
            if features:
                return shape(features[0]["geometry"])
            return None
        return None

    # Build query based on whether feature_id is provided
    if feature_id is not None:
        # Query for a specific feature
        query = f'''
            SELECT * FROM workflows."{input_table_name}" 
            WHERE _gid = {feature_id}::bigint
        '''
    else:
        # Query for all features
        query = f'SELECT * FROM workflows."{input_table_name}"'
    
    # Read input geometries
    df = gpd.read_postgis(
        query,
        engine, 
        geom_col="geometry"
    )
    
    # Check if we found any features
    if df.empty:
        if feature_id is not None:
            raise ValueError(f"No feature found with ID {feature_id}")
        else:
            raise ValueError("No features found in the points collection")
            
    df["latitude"] = df.geometry.y
    df["longitude"] = df.geometry.x
    if "drive_time" in catchment_type.lower():
        key = "drive_time"
        df[key] = drive_time_dist

    else:
        key = "drive_distance"
        df[key] = drive_time_dist * 1000
    df["departure_time"] = analysis_datetime
    df["catchment_type"] = catchment_type
    import concurrent.futures

    def parallel_catchment(row):
        return get_catchment(
            row["latitude"],
            row["longitude"],
            catchment_type,
            accuracy_level,
            False if catchment_type == "DRIVE_DISTANCE" else True,
            drive_time_dist * 1000
            if catchment_type == "DRIVE_DISTANCE"
            else drive_time_dist,
            analysis_datetime,
        )

    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(executor.map(parallel_catchment, (r for _, r in df.iterrows())))

    df["geometry"] = results
    print(df["geometry"])
    is_cached = node.save_df_to_postgres(df, output_table_name)

    return {"output": output_table_name, "is_cached": is_cached}


def createsmartmarketlayer(**kwargs):
    from airflow.models import Variable

    node = Node(**kwargs)
    project_id = node.input("project_id")
    workflow_id = kwargs.get("workflow_id")
    replace_existing = node.input("replaceExisting", False)  # New input parameter
    engine = get_db_engine_workflows()

    # Generate unique identifiers
    unique_lock_id = f"smartmarket_{project_id}_{int(time.time() * 1000)}"
    unique_locker_id = f"{kwargs.get('node_id')}"

    # Try to acquire lock
    def acquire_lock():
        try:
            # Check if any active locks exist
            result = engine.execute(
                """
                SELECT COUNT(*) 
                FROM process_locks 
                WHERE workflow_id = %s
            """,
                (workflow_id),
            ).scalar()

            print(result)

            if result > 0:
                return False

            # Create new lock
            engine.execute(
                """
                INSERT INTO process_locks (lock_id, locked_by, project_id, workflow_id)
                VALUES (%s, %s, %s, %s)
            """,
                (unique_lock_id, unique_locker_id, project_id, workflow_id),
            )

            return True
        except Exception as e:
            print(f"Error acquiring lock: {e}")
            return False

    # Release lock
    def release_lock():
        try:
            engine.execute(
                """
                DELETE FROM process_locks 
                WHERE lock_id = %s AND locked_by = %s
            """,
                (unique_lock_id, unique_locker_id),
            )
            print("Lock released")
        except Exception as e:
            print(f"Error releasing lock: {e}")

    # Wait for lock with timeout
    max_attempts = 30  # 30 seconds timeout
    attempt = 0
    while not acquire_lock():
        time.sleep(1)
        attempt += 1
        print(f"Attempt {attempt} of {max_attempts}")
        if attempt >= max_attempts:
            raise RuntimeError("Timeout waiting for lock")

    try:
        # Get inputs
        layer_name = node.input("layer_name")
        feature_collection_key = node.input("data")

        # Generate a base layer ID using the layer name
        base_layer_id = layer_name

        # Initialize Supabase client
        supabase = create_client(
            Variable.get("SUPABASE_URL"), Variable.get("SUPABASE_KEY")
        )

        # Download and decode existing project.json
        timestamp = int(time.time() * 1000)
        project_json_bytes = supabase.storage.from_("projects").download(
            f"{project_id}/project.json?t={timestamp}"
        )
        project_json_str = project_json_bytes.decode("utf-8")
        project_data = json.loads(project_json_str)
        

        # Initialize layers if not present
        if "layers" not in project_data:
            project_data["layers"] = {}

        # Handle duplicate layer names
        layer_id = base_layer_id
        if layer_id in project_data["layers"]:
            if replace_existing:
                # Keep the same layer_id, it will be overwritten
                pass
            else:
                # Find the next available suffix
                suffix = 1
                while f"{layer_id}_{suffix}" in project_data["layers"]:
                    suffix += 1
                layer_id = f"{layer_id}_{suffix}"
                layer_name = f"{layer_name} ({suffix})"

        # Create layer source data
        layer_source = {
            "type": "geojson_postgrest",
            "db": {
                "url": Variable.get("SMART_FLOWS_DB_URL"),
                "key": "",
                "table": f"{feature_collection_key}",
                "select": "*",
                "schema": "workflows",
            },
            "workflow_id": kwargs["workflow_id"],
        }

        # Create new layer info
        new_layer = {
            "id": layer_id,
            "name": layer_name,
            "source": json.dumps(layer_source,separators=(',', ':')),
            "style": json.dumps(
                {
                    "strokeWidth": 2,
                    "strokeColor": "#3B82F6",
                    "fillColor": "#93C5FD",
                    "fillOpacity": 0.5,
                    "strokeOpacity": 1,
                    "tooltipProperties": [],
                }, separators=(',', ':')
            ),
            "featureType": "geojson",
            "layerGroupId": "flows",
            "geometryType": "polygon",
            "visible": True,
        }

        # Add or update layer in project data
        project_data["layers"][layer_id] = new_layer

        # Update project.json in Supabase
        updated_json_str = json.dumps(project_data, separators=(',', ':'))
        supabase.storage.from_("projects").update(
            f"{project_id}/project.json?t={timestamp}", updated_json_str.encode("utf-8")
        )

        return {"result": layer_id}

    except Exception as e:
        raise RuntimeError(f"Failed to create smart market layer: {str(e)}")
    finally:
        # Always release the lock when done
        release_lock()


def bbox(**kwargs):
    print("Creating bounding box")
    node = Node(**kwargs)
    input_table = node.input("input")
    output_table_name, is_cached = node.compute_in_db(
        func_name="bbox",
        inputs={"input": input_table},
        query=f'SELECT ST_Envelope(geometry) AS geometry FROM workflows."{input_table}"',
        geom_col=["geometry"],
        input_table_name=input_table,
        exclude_col=["geometry"],
    )
    return {
        "output": output_table_name,
        "is_cached": is_cached,
    }


def intersection(**kwargs):
    print("Creating intersection")
    node = Node(**kwargs)
    attr_of = node.input("layerToPreserve","A")
    input_table_name_a = node.input("featureCollectionA")
    input_table_name_b = node.input("featureCollectionB")

    # Get all columns except geometry from the preserved layer
    engine = get_db_engine_lepton()
    if "A" == attr_of[-1]:
        input_table_name = input_table_name_a
        columns = get_column_names(engine, input_table_name_a)
        columns = [col for col in columns if col != 'geometry']
        select_cols = ', '.join([f'a."{col}"' for col in columns])
        query = f"""
            SELECT 
                {select_cols},
                ST_Intersection(a.geometry, b.geometry) AS geometry
            FROM workflows."{input_table_name_a}" a
            JOIN workflows."{input_table_name_b}" b
                ON ST_Intersects(a.geometry, b.geometry)
            """
    else:
        input_table_name = input_table_name_b
        columns = get_column_names(engine, input_table_name_b)
        columns = [col for col in columns if col != 'geometry']
        select_cols = ', '.join([f'b."{col}"' for col in columns])
        query = f"""
            SELECT 
                {select_cols},
                ST_Intersection(a.geometry, b.geometry) AS geometry
            FROM workflows."{input_table_name_a}" a
            JOIN workflows."{input_table_name_b}" b
                ON ST_Intersects(a.geometry, b.geometry)
            """
    print(query)
    output_table_name, is_cached = node.compute_in_db(
        func_name="intersection",
        query=query,
        inputs={
            "featureCollectionA": input_table_name_a,
            "featureCollectionB": input_table_name_b,
            "attr_of": attr_of,
        },
        geom_col=["geometry"],
        input_table_name=input_table_name,
        exclude_col=["geometry"],
        replace_query_columns=False
    )
    return {
        "output": output_table_name,
        "is_cached": is_cached,
    }


def centroid(**kwargs):
    print("Creating centroid")
    node = Node(**kwargs)
    input_table = node.input("input")
    output_table_name, is_cached = node.compute_in_db(
        func_name="centroid",
        query=f'SELECT ST_Centroid("{input_table}".geometry) AS geometry FROM workflows."{input_table}"',
        inputs={"input": input_table},
        geom_col=["geometry"],
        input_table_name=input_table,
        exclude_col=["geometry"],
    )
    return {
        "centroid": output_table_name,
        "is_cached": is_cached,
    }


def generategrid(**kwargs):
    """
    Generates a grid using H3 for hexagons, polygon-geohasher for geohashes, 
    and efficient Shapely operations for squares
    
    Args:
        featureCollection: Input feature collection
        gridType: Type of grid (hexagon, square, h3, geohash)
        cellSize: Size of grid cells in kilometers
        avoidTouchingBoundaries: Whether to avoid cells that touch boundaries
        h3Resolution: Resolution for H3 grid (if gridType is h3)
        geohashPrecision: Precision for geohash grid (if gridType is geohash)
        featureId: Optional ID of a specific feature to process (processes all features if not provided)
    """
    from shapely.geometry import Polygon
    from shapely.prepared import prep
    import numpy as np
    
    node = Node(**kwargs)

    # Get inputs
    feature_collection = node.input("featureCollection")
    grid_type = node.input("gridType")
    cell_size = node.input("cellSize")  # in kilometers
    avoid_boundaries = node.input("avoidTouchingBoundaries", False)
    feature_id = node.input("featureId", None)  # Get feature_id if provided

    print(f"Grid type: {grid_type}")
    
    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="generategrid",
        inputs={
            "featureCollection": feature_collection,
            "grid_type": grid_type,
            "cell_size": cell_size,
            "avoid_boundaries": avoid_boundaries,
            "featureId": feature_id,
            "h3Resolution": node.input("h3Resolution", 10) if grid_type == "h3" else None,
            "geohashPrecision": node.input("geohashPrecision", 8) if grid_type == "geohash" else None,
        },
    )

    # Check if cached result exists
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        return {"output": output_table_name, "is_cached": True}

    try:
        # Build query based on whether feature_id is provided
        if feature_id is not None:
            # Query for a specific feature with proper type casting
            query = f'''
                SELECT * FROM workflows."{feature_collection}" 
                WHERE _gid = {feature_id}::bigint
            '''
        else:
            # Query for all features
            query = f'SELECT * FROM workflows."{feature_collection}"'
        
        # Read input geometries
        df = gpd.read_postgis(
            query,
            engine,
            geom_col='geometry'
        )
        
        # Check if we found any features
        if df.empty:
            if feature_id is not None:
                raise ValueError(f"No feature found with ID {feature_id}")
            else:
                raise ValueError("No features found in the feature collection")
        
        # Dissolve all geometries into one
        dissolved_geom = df.unary_union
        
        if grid_type.lower() == "geohash":
            # Import polygon-geohasher
            from polygon_geohasher.polygon_geohasher import polygon_to_geohashes, geohashes_to_polygon
            
            precision = node.input("geohashPrecision", 8)
            
            
            print(f"Precision: {precision}")
            # Generate geohashes
            geohashes = polygon_to_geohashes(
                dissolved_geom, 
                precision,
                inner=avoid_boundaries  # Use inner=True if avoiding boundaries
            )
            print(f"Geohashes: {geohashes}")
            # Convert geohashes to polygons
            grid_geom = geohashes_to_polygon(geohashes)
            
            # Create properties for each cell
            properties = []
            grid_cells = []

            print(f"Grid geometry type: {grid_geom.geom_type}")
            
             # Process each geohash individually
            for idx, geohash in enumerate(sorted(geohashes), 1):
                # Convert single geohash to polygon
                geohash_poly = geohashes_to_polygon([geohash])
                
                # Handle both single polygon and multipolygon cases
                if geohash_poly.geom_type == 'Polygon':
                    grid_cells.append(geohash_poly)
                elif geohash_poly.geom_type == 'MultiPolygon':
                    # Take the first polygon if multiple are returned
                    grid_cells.append(geohash_poly.geoms[0])
                
                # Get centroid for property information
                centroid = geohash_poly.centroid
                properties.append({
                    'grid_id': idx,
                    'geohash': geohash,
                    'longitude': centroid.x,
                    'latitude': centroid.y,
                    '_gid': idx
                })
            print(f"Number of grid cells: {len(grid_cells)}")
            print(f"Number of properties: {len(properties)}")
            
            # Create GeoDataFrame
            grid_gdf = gpd.GeoDataFrame(
                properties,
                geometry=grid_cells,
                crs="EPSG:4326"
            )
            print(f"Grid GeoDataFrame shape: {grid_gdf.shape}")
        if grid_type.lower() == "h3":
            # Import h3pandas
            import h3pandas
            
            resolution = node.input("h3Resolution", 10)
            
            # Create GeoDataFrame with the input geometry
            input_gdf = gpd.GeoDataFrame(geometry=[dissolved_geom], crs="EPSG:4326")
            
            # Generate hexagons using h3pandas
            hexagons = input_gdf.h3.polyfill_resample(resolution)
            
            if hexagons.empty:
                raise ValueError("No hexagons found for the input geometry")
            
            # Convert H3 indices to geometries and create properties
            properties = []
            grid_cells = []
            
            for idx, hex_id in enumerate(hexagons.index, 1):
                # Get the geometry from the hexagon
                grid_cells.append(hexagons.loc[hex_id, 'geometry'])
                
                # Get the centroid coordinates
                centroid = hexagons.loc[hex_id, 'geometry'].centroid
                properties.append({
                    'grid_id': idx,
                    'h3_index': hex_id,
                    'latitude': centroid.y,
                    'longitude': centroid.x,
                    '_gid': idx
                })
            
            # Create GeoDataFrame with all properties
            grid_gdf = gpd.GeoDataFrame(
                properties,
                geometry=grid_cells,
                crs="EPSG:4326"
            )
            
        if grid_type.lower() == "hexagon":
         # Import PyTurf functions
            from turf.distance import distance
            from turf.bbox import bbox
            from turf.boolean_intersects import boolean_intersects
            from turf.helpers import feature_collection, polygon, FeatureCollection
            import math
            
            bounds = dissolved_geom.bounds
            print(f"Input geometry bounds: {bounds}")  # Debug print
            
            prepared_geom = prep(dissolved_geom)
            grid_cells = []
            properties = []
            
            # Calculate cell size in degrees (approximate)
            # 1 degree is roughly 111km at the equator
            cell_size_deg = cell_size / 111.0
            print(f"Cell size in degrees: {cell_size_deg}")  # Debug print
            
            # Define the hex_grid and helper functions
            def hexagon(center, rx, ry, properties, cosines, sines):
                vertices = []
                for i in range(6):
                    x = center[0] + rx * cosines[i]
                    y = center[1] + ry * sines[i]
                    vertices.append([x, y])

                vertices.append(vertices[0])
                return polygon([vertices], properties)

            def hex_triangles(center, rx, ry, properties, cosines, sines):
                triangles = []
                for i in range(6):
                    vertices = []
                    vertices.append(center)
                    vertices.append([center[0] + rx * cosines[i], center[1] + ry * sines[i]])
                    vertices.append(
                        [center[0] + rx * cosines[(i + 1) % 6], center[1] + ry * sines[(i + 1) % 6]]
                    )
                    vertices.append(center)
                    triangles.append(polygon([vertices], properties))

                return triangles

            def hex_grid(bbox_coords, cell_side, options={}):
                """
                Takes a bounding box and the diameter of the cell and returns a FeatureCollection of flat-topped
                hexagons aligned in an "odd-q" vertical grid.
                """
                has_triangles = options.get("triangles", None)

                results = []
                west = bbox_coords[0]
                south = bbox_coords[1]
                east = bbox_coords[2]
                north = bbox_coords[3]

                # Expand bounds slightly to ensure coverage
                width_buffer = (east - west) * 0.1
                height_buffer = (north - south) * 0.1
                
                west -= width_buffer
                east += width_buffer
                south -= height_buffer
                north += height_buffer
                
                print(f"Expanded bounds: W:{west}, S:{south}, E:{east}, N:{north}")  # Debug print

                center_y = (south + north) / 2
                center_x = (west + east) / 2

                x_fraction = (cell_side * 2) / (
                    distance([west, center_y], [east, center_y], options)
                )
                cell_width_deg = x_fraction * (east - west)
                y_fraction = (
                    cell_side * 2 / (distance([center_x, south], [center_x, north], options))
                )
                cell_height_deg = y_fraction * (north - south)
                radius = cell_width_deg / 2

                hex_width = radius * 2
                hex_height = math.sqrt(3) / 2 * cell_height_deg

                # rows & columns
                bbox_width = east - west
                bbox_height = north - south

                x_interval = 3 / 4 * hex_width
                y_interval = hex_height

                x_span = (bbox_width - hex_width) / (hex_width - radius / 2)
                x_count = max(1, int(x_span))  # Ensure at least 1 column

                x_adjust = (
                    ((x_count * x_interval - radius / 2) - bbox_width) / 2
                    - radius / 2
                    + x_interval / 2
                )

                y_count = max(1, int((bbox_height - hex_height) / hex_height))  # Ensure at least 1 row
                y_adjust = (bbox_height - y_count * hex_height) / 2

                has_offset_y = (y_count * hex_height - bbox_height) > (hex_height / 2)

                if has_offset_y:
                    y_adjust -= hex_height / 4

                cosines = []
                sines = []

                for i in range(6):
                    angle = 2 * math.pi / 6 * i
                    cosines.append(math.cos(angle))
                    sines.append(math.sin(angle))

                print(f"Grid dimensions: {x_count+1} columns x {y_count+1} rows")  # Debug print

                for x in range(x_count + 1):
                    for y in range(y_count + 1):
                        is_odd = x % 2 == 1

                        if (y == 0) and is_odd:
                            continue

                        if (y == 0) and has_offset_y:
                            continue

                        center_x = x * x_interval + west - x_adjust
                        center_y = y * y_interval + south + y_adjust

                        if is_odd:
                            center_y -= hex_height / 2

                        hex_poly = hexagon(
                            [center_x, center_y],
                            cell_width_deg / 2,
                            cell_height_deg / 2,
                            options.get("properties", {}).copy(),
                            cosines,
                            sines,
                        )

                        if "mask" in options:
                            if boolean_intersects(options["mask"], hex_poly):
                                results.append(hex_poly)
                        else:
                            results.append(hex_poly)

                print(f"Generated {len(results)} hexagons")  # Debug print
                return feature_collection(results)

            # Generate PyTurf hexagonal grid
            minx, miny, maxx, maxy = bounds
            bbox_coords = [minx, miny, maxx, maxy]
            
            # Define options for hex_grid
            options = {
                "units": "kilometers",
                "properties": {}
            }
            
            # Generate the hexagonal grid
            hexagons = hex_grid(bbox_coords, cell_size, options)
            
            # # Convert PyTurf features to Shapely geometries
            # grid_cells = []
            # properties = []  # Add this to store properties for each cell
            
            for idx, feature in enumerate(hexagons['features'], 1):
                coords = feature['geometry']['coordinates'][0]
                hex_poly = Polygon(coords)
                
                # Only include cells that intersect with our area of interest
                if prepared_geom.intersects(hex_poly):
                    if avoid_boundaries:
                        if prepared_geom.contains(hex_poly):
                            grid_cells.append(hex_poly)
                            # Get centroid coordinates
                            centroid = hex_poly.centroid
                            properties.append({
                                'grid_id': idx,
                                'longitude': centroid.x,
                                'latitude': centroid.y,
                                '_gid': idx  # Add _gid to match existing format
                            })
                    else:
                        grid_cells.append(hex_poly)
                        # Get centroid coordinates
                        centroid = hex_poly.centroid
                        properties.append({
                            'grid_id': idx,
                            'longitude': centroid.x,
                            'latitude': centroid.y,
                            '_gid': idx  # Add _gid to match existing format
                        })

            if not grid_cells:
                print("Warning: No grid cells generated. Input geometry may be too small relative to cell size.")
                print(f"Input geometry area: {dissolved_geom.area}")
                raise ValueError("No grid cells intersect with the input geometry. Try reducing the cell size.")

            # Create GeoDataFrame with all properties
            grid_gdf = gpd.GeoDataFrame(
                properties,  # Now includes grid_id, latitude, longitude, and _gid
                geometry=grid_cells,
                crs="EPSG:4326"
            )
            
        if grid_type.lower() == "square":  # Square grid - keep existing functionality
            def grid_bounds(geom, delta):
                """Create a grid of squares covering the geometry bounds"""
                minx, miny, maxx, maxy = geom.bounds
                nx = int((maxx - minx)/delta)
                ny = int((maxy - miny)/delta)
                
                # Ensure at least one cell in each direction
                nx = max(1, nx)
                ny = max(1, ny)
                
                # Create coordinate arrays
                gx = np.linspace(minx, maxx, nx + 1)
                gy = np.linspace(miny, maxy, ny + 1)
                
                grid = []
                for i in range(len(gx)-1):
                    for j in range(len(gy)-1):
                        poly_ij = Polygon([
                            [gx[i], gy[j]],
                            [gx[i], gy[j+1]],
                            [gx[i+1], gy[j+1]],
                            [gx[i+1], gy[j]]
                        ])
                        grid.append(poly_ij)
                return grid

            def partition(geom, delta):
                """Filter grid cells that intersect with the geometry"""
                prepared_geom = prep(geom)
                grid = list(filter(prepared_geom.intersects, grid_bounds(geom, delta)))
                return grid

            # Convert cell_size from km to degrees (approximate)
            cell_size_deg = cell_size / 111.0
            
            # Generate grid cells that intersect with the geometry
            grid_cells = partition(dissolved_geom, cell_size_deg)
            
            # Create properties for each cell
            properties = []
            for idx, cell in enumerate(grid_cells):
                centroid = cell.centroid
                properties.append({
                    'grid_id': idx + 1,
                    'longitude': centroid.x,
                    'latitude': centroid.y
                })

        if not grid_cells:
            raise ValueError("No grid cells intersect with the input geometry")

        # Create GeoDataFrame
        grid_gdf = gpd.GeoDataFrame(
            properties,
            geometry=grid_cells,
            crs="EPSG:4326"
        )

        # Save to database
        is_cached = node.save_df_to_postgres(grid_gdf, output_table_name)
        
        return {
            "output": output_table_name,
            "is_cached": is_cached
        }

    except Exception as e:
        raise RuntimeError(f"Error generating grid: {str(e)}")
# def generate_heatmap(**kwargs):
#     ...


# def isocrone_analysis(**kwargs):
#     ...


def join(**kwargs):
    """
    Performs spatial join between two feature collections with customizable join type,
    spatial predicate, and column selection
    """
    node = Node(**kwargs)

    # Get inputs
    base_layer = node.input("baseLayer")
    join_layer = node.input("joinLayer")
    join_type = node.input("joinType", "inner").lower()  # Default to inner join
    spatial_predicate = node.input("spatialPredicate", "intersects")
    columns_base = node.input("columnsBase", [])  # Optional: list of columns to select from base layer
    columns_join = node.input("columnsJoin", [])  # Optional: list of columns to select from join layer
    print("columns_join", columns_join, "columns_base", columns_base)
    # Maps for join types and spatial predicates
    join_type_map = {
        "inner": "INNER JOIN",
        "left": "LEFT JOIN",
        "right": "RIGHT JOIN"  # Removed FULL OUTER JOIN option
    }

    predicate_map = {
        "contains": "ST_Contains",
        "intersects": "ST_Intersects",
        "within": "ST_Within",
        "touches": "ST_Touches",
        "crosses": "ST_Crosses",
        "overlaps": "ST_Overlaps"
    }

    # Validate inputs
    if not base_layer or not join_layer:
        raise ValueError("Both base layer and join layer must be provided")
    if join_type not in join_type_map:
        raise ValueError(f"Invalid join type. Must be one of: {', '.join(join_type_map.keys())}")
    if spatial_predicate not in predicate_map:
        raise ValueError(f"Invalid spatial predicate. Must be one of: {', '.join(predicate_map.keys())}")

    # Get column information from both tables
    engine = get_db_engine_lepton()
    base_columns = get_column_names(engine, base_layer)
    join_columns = get_column_names(engine, join_layer)

    # Helper function to build column selection with aliases
    def build_column_list(table_alias, columns, available_columns, exclude_geometry=False):
        if columns:
            # Extract column names from the dictionary objects
            column_names = [col['column'] for col in columns if isinstance(col, dict) and 'column' in col]
            # Use only specified columns that exist in the table
            valid_columns = [col for col in column_names if col in available_columns]
            if not valid_columns:
                raise ValueError(f"No valid columns specified for {table_alias}")
        else:
            # Use all columns except geometry if excluded
            valid_columns = [col for col in available_columns 
                           if not exclude_geometry or col != "geometry"]
        
        return [f'{table_alias}."{col}" AS "{col}_{table_alias}"' 
                for col in valid_columns]

    # Build column selections
    base_cols = build_column_list("b", columns_base, base_columns, exclude_geometry=True)
    join_cols = build_column_list("j", columns_join, join_columns, exclude_geometry=True)
    
    # Add geometry column based on join type
    if join_type == "right":
        geometry_col = 'j.geometry'  # Use join layer geometry for right joins
        query = f"""
            SELECT 
                {', '.join(join_cols)},
                {', '.join(base_cols)},
                {geometry_col} as geometry
            FROM workflows."{join_layer}" j
            RIGHT JOIN workflows."{base_layer}" b
                ON {predicate_map[spatial_predicate]}(b.geometry, j.geometry)
        """
    else:
        geometry_col = 'b.geometry'  # Use base layer geometry for other joins
        query = f"""
            SELECT 
                {', '.join(base_cols)},
                {', '.join(join_cols)},
                {geometry_col} as geometry
            FROM workflows."{base_layer}" b
            {join_type_map[join_type]} workflows."{join_layer}" j
                ON {predicate_map[spatial_predicate]}(b.geometry, j.geometry)
        """

    # Execute query and save results
    output_table_name, is_cached = node.compute_in_db(
        func_name="join",
        inputs={
            "baseLayer": base_layer,
            "joinLayer": join_layer,
            "joinType": join_type,
            "spatialPredicate": spatial_predicate,
            "columnsBase": columns_base,
            "columnsJoin": columns_join
        },
        query=query,
        geom_col=["geometry"],
        input_table_name=base_layer,
        replace_query_columns=False
    )

    return {
        "output": output_table_name,
        "is_cached": is_cached
    }


def filters(**kwargs):
    """
    Filters features from a feature collection based on attribute, operator, and value
    Supports numeric and string comparisons
    """
    node = Node(**kwargs)

    # Get inputs
    feature_collection = node.input("featureCollection")
    attribute = node.input("attribute")
    operator = node.input("operator")
    value = node.input("value")

    # Map operators to SQL syntax
    operator_map = {
        "equals": "=",
        "not_equals": "!=",
        "greater_than": ">",
        "less_than": "<",
        "greater_than_equals": ">=",
        "less_than_equals": "<=",
        "contains": "LIKE",
        "starts_with": "LIKE",
        "ends_with": "LIKE",
    }

    # Modify value based on operator type
    if operator in ["contains", "starts_with", "ends_with"]:
        if operator == "contains":
            value = f"%{value}%"
        elif operator == "starts_with":
            value = f"{value}%"
        elif operator == "ends_with":
            value = f"%{value}"
        # Use string concatenation for LIKE operations
        where_clause = f"\"{attribute}\" LIKE '{value}'"
    else:
        # For numeric comparisons, don't use quotes around value
        try:
            # get type of field column from postgres
            engine = get_db_engine_lepton()
            column_type = engine.execute(f'SELECT data_type FROM information_schema.columns WHERE table_name = \'{feature_collection}\' AND column_name = \'{attribute}\'').scalar()
            if column_type in ['numeric', 'integer', 'float']:
                float(value)  # Check if value can be converted to number
                where_clause = f'"{attribute}" {operator_map[operator]} {value}'
            else:
                where_clause = f"\"{attribute}\" {operator_map[operator]} '{value}'"
        except ValueError:
            # If not numeric, treat as string
            where_clause = f"\"{attribute}\" {operator_map[operator]} '{value}'"

    query = f"""
        SELECT *
        FROM workflows."{feature_collection}"
        WHERE {where_clause}
    """

    output_table_name, is_cached = node.compute_in_db(
        func_name="filter",
        inputs={
            "featureCollection": feature_collection,
            "attribute": attribute,
            "operator": operator,
            "value": value,
        },
        query=query,
        geom_col=["geometry"],
    )

    return {
        "output": output_table_name,
        "is_cached": is_cached,
    }


def demographic(**kwargs):
    """
    Processes demographic data for given geometries using Lepton API
    Returns demographic data based on specified subcategories
    """
    from airflow.models import Variable
    import requests

    node = Node(**kwargs)

    # Get inputs
    feature_collection = node.input("featureCollection")
    subcategories = node.input(
        "subcategories"
    )  # List of demographic subcategories to fetch

    if not subcategories:
        raise ValueError("Please select at least one subcategory")

    # Handle special case for HIG/MIG/LIG
    if "hig/mig/lig" in subcategories:
        index = subcategories.index("hig/mig/lig")
        subcategories[index : index + 1] = ["hig", "mig", "lig"]

    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="demographic",
        inputs={
            "featureCollection": feature_collection,
            "subcategories": subcategories,
        },
    )

    # Check if cached result exists
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        return {"output": output_table_name, "is_cached": True}

    # Get data as GeoJSON
    query = f"""
        SELECT jsonb_build_object(
            'type', 'FeatureCollection',
            'features', jsonb_agg(
                jsonb_build_object(
                    'type', 'Feature',
                    'geometry', ST_AsGeoJSON(geometry)::jsonb,
                    'properties', jsonb_build_object('id', _gid)
                )
            )
        ) as geojson
        FROM workflows."{feature_collection}"
    """

    with engine.connect() as connection:
        result = connection.execute(query).fetchone()
        geojson_data = result[0]

    # Prepare features for API request
    features = []
    for feature in geojson_data["features"]:
        geom = feature["geometry"]
        coordinates = geom["coordinates"]
        geom_type = geom["type"]

        # Convert MultiPolygon to Polygon if needed
        if geom_type == "Polygon" and len(coordinates[0][0]) != 2:
            coordinates = coordinates[0]
        elif geom_type == "MultiPolygon" and len(coordinates[0][0][0]) != 2:
            geom_type = "Polygon"
            coordinates = coordinates[0]

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": geom_type, "coordinates": coordinates},
                "properties": {"id": str(feature["properties"]["id"])},
            }
        )

    if not features:
        raise ValueError("No valid geometries found in input feature collection")

    # Prepare API request payload
    payload = {"features": features, "subcategories": subcategories}
    print("payload", payload)

    # Call Lepton API
    try:
        response = requests.post(
            "https://api.leptonmaps.com/v1/geojson/residential/demographics/get_demo",
            headers={
                "X-API-Key": Variable.get("LEPTON_API_KEY"),
                "Content-Type": "application/json",
            },
            json=payload,
        )

        if not response.ok:
            raise RuntimeError(
                f"API request failed with status {response.status_code}: {response.text}"
            )

        data = response.json()

        print("demographic data", data)

        if not isinstance(data, list) or not data:
            raise ValueError("Invalid response format from API")

        # Create a DataFrame with the demographic data
        df = gpd.read_postgis(
            f'SELECT * FROM workflows."{feature_collection}"',
            engine,
            geom_col="geometry",
        )

        # Process API response and update dataframe
        for item in data:
            try:
                feature_id = int(item["id"])
                counts = item.get("counts", {})

                # Add demographic data to dataframe
                for subcat in subcategories:
                    value = counts.get(subcat, 0)
                    # Convert to float if possible
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        value = 0
                    # Check if grid_id exists in the DataFrame
                    if 'grid_id' in df.columns:
                        # For grid-based feature collections, match on grid_id
                        df.loc[df['_gid'] == feature_id, subcat] = value
                    else:
                        # For regular feature collections, use _gid-based indexing
                        matching_row = df.loc[df['_gid'] == feature_id]
                        if not matching_row.empty:
                            # If found by _gid, update using loc
                            df.loc[df['_gid'] == feature_id, subcat] = value
                        else:
                            # Fallback to index-based access (legacy behavior)
                            df.at[feature_id - 1, subcat] = value

            except (KeyError, ValueError, IndexError) as e:
                print(f"Warning: Error processing item {item}: {str(e)}")
                continue

        # Save results to database
        is_cached = node.save_df_to_postgres(df, output_table_name)

        return {"output": output_table_name, "is_cached": is_cached}

    except Exception as e:
        raise RuntimeError(f"Failed to process demographic data: {str(e)}")


def countpoi(**kwargs):
    """
    Counts Points of Interest (POIs) within given geometries using Lepton API
    Returns count data based on specified categories and subcategories
    """
    from airflow.models import Variable
    import requests

    node = Node(**kwargs)

    # Get inputs
    feature_collection = node.input("featureCollection")
    categories = node.input("categories")  # List of POI categories
    subcategories = node.input("subcategories")  # List of POI subcategories

    if not categories and not subcategories:
        raise ValueError("Please select at least one Category or Subcategory")

    # Decode subcategories (handle 'others' case)
    decoded_subcategories = [
        subcat.split(":")[0] if ":" in subcat else subcat for subcat in subcategories
    ]

    print("decoded_subcategories", decoded_subcategories)

    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="countpoi",
        inputs={
            "featureCollection": feature_collection,
            "categories": categories,
            "subcategories": decoded_subcategories,
        },
    )

    # Check if cached result exists
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        return {"output": output_table_name, "is_cached": True}

    # Get data as GeoJSON
    query = f"""
        SELECT jsonb_build_object(
            'type', 'FeatureCollection',
            'features', jsonb_agg(
                jsonb_build_object(
                    'type', 'Feature',
                    'geometry', ST_AsGeoJSON(geometry)::jsonb,
                    'properties', jsonb_build_object('id', _gid)
                )
            )
        ) as geojson
        FROM workflows."{feature_collection}"
    """

    with engine.connect() as connection:
        result = connection.execute(query).fetchone()
        geojson_data = result[0]

    # Prepare features for API request
    features = []
    for feature in geojson_data["features"]:
        geom = feature["geometry"]
        print("feature------", feature)
        coordinates = geom["coordinates"]
        geom_type = geom["type"]

        # Convert MultiPolygon to Polygon if needed
        if geom_type == "Polygon" and len(coordinates[0][0]) != 2:
            coordinates = coordinates[0]
        elif geom_type == "MultiPolygon" and len(coordinates[0][0][0]) != 2:
            geom_type = "Polygon"
            coordinates = coordinates[0]

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": geom_type, "coordinates": coordinates},
                "properties": {"id": str(feature["properties"]["id"])},
            }
        )

    if not features:
        raise ValueError("No valid geometries found in input feature collection")

    # Prepare API request payload
    payload = {
        "features": features,
        "categories": categories,
        "subcategories": decoded_subcategories,
    }

    # Call Lepton API
    try:
        response = requests.post(
            "https://api.leptonmaps.com/v1/geojson/places/place_insights",
            headers={
                "X-API-Key": Variable.get("LEPTON_API_KEY"),
                "Content-Type": "application/json",
            },
            json=payload,
        )

        if not response.ok:
            raise RuntimeError(
                f"API request failed with status {response.status_code}: {response.text}"
            )

        data = response.json()
        print("API Response:", data)  # Debug print

        if not isinstance(data, list) or not data:
            raise ValueError(
                "POI data is temporarily unavailable. Please try again later."
            )

        # Create a DataFrame with the POI count data
        df = gpd.read_postgis(
            f'SELECT * FROM workflows."{feature_collection}"',
            engine,
            geom_col="geometry",
        )

        # Process API response and update dataframe
        for item in data:
            try:
                feature_id = int(item["id"])
                counts = item.get("counts", {})

                # Add count data to dataframe
                for key, value in counts.items():
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        value = 0
                    df.at[
                        feature_id - 1, key
                    ] = value  # Adjust index since API returns 1-based IDs

            except (KeyError, ValueError, IndexError) as e:
                print(f"Warning: Error processing item {item}: {str(e)}")
                continue

        # Save results to database
        is_cached = node.save_df_to_postgres(df, output_table_name)

        return {"output": output_table_name, "is_cached": is_cached}

    except Exception as e:
        raise RuntimeError(f"Failed to process POI count data: {str(e)}")


def boundaries(**kwargs):
    """
    Fetches boundary data (states, districts, tehsils, towns, villages, pincodes)
    from Lepton API
    """
    from airflow.models import Variable
    import requests

    node = Node(**kwargs)

    # Get inputs
    boundary_type = node.input("boundaryType")
    states_input = node.input("state", [])  # List of state dictionaries
    districts_input = node.input("district", [])  # List of district dictionaries

    # Extract values from the input dictionaries
    states = [state if type(state) == str else state.get("value") for state in states_input] if states_input else []
    districts = [district if type(district) == str else district.get("value") for district in districts_input] if districts_input else []

    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="boundaries",
        inputs={
            "boundaryType": boundary_type,
            "states": states,
            "districts": districts,
        },
    )

    # Check if cached result exists
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        return {"output": output_table_name, "is_cached": True}

    try:
        api_key = Variable.get("LEPTON_API_KEY")
        base_url = "https://api.leptonmaps.com/v1/geojson/regions"

        # Configure endpoint and parameters based on boundary type
        if boundary_type == "state":
            url = f"{base_url}/state"
            params = {"key": api_key}
        
        elif boundary_type == "district":
            if not states:
                raise ValueError("Please select at least one state for district boundaries")
            url = f"{base_url}/districts"
            params = {"state": ",".join(states), "key": api_key}
        
        elif boundary_type == "rto":
        # Handle RTO boundaries
            if districts:
                url = f"{base_url}/rto"
                params = {
                    "district": ",".join(districts),
                    "state": ",".join(states),
                    "key": api_key
                }
            elif states:
                url = f"{base_url}/rto"
                params = {
                    "state": ",".join(states),
                    "key": api_key
                }
            else:
                raise ValueError("Please select either states or districts for RTO boundaries")
            
        elif boundary_type in ["tehsil", "town", "village", "pincode"]:
            # Map boundary types to API endpoints
            endpoint_map = {
                "tehsil": "tehsil",
                "town": "town",
                "village": "villages",
                "pincode": "pincode"
            }
            
            url = f"{base_url}/{endpoint_map[boundary_type]}"
            
            # Set query parameters based on provided inputs
            if districts:
                params = {"district": ",".join(districts), "key": api_key}
            elif states:
                params = {"state": ",".join(states), "key": api_key}
            else:
                raise ValueError("Please select either states or districts")
        
        else:
            raise ValueError(f"Invalid boundary type: {boundary_type}")

        # Make API request
        response = requests.get(url, params=params)

        if not response.ok:
            error_message = response.text
            try:
                error_json = response.json()
                if isinstance(error_json, dict):
                    error_message = error_json.get('message', error_message)
            except:
                pass
            raise RuntimeError(f"API request failed: {error_message}")

        geojson_data = response.json()
        print("geojson_data", geojson_data)
        # Convert GeoJSON to GeoDataFrame
        df = gpd.GeoDataFrame.from_features(geojson_data["features"])

        # Save to database
        is_cached = node.save_df_to_postgres(df, output_table_name)

        return {"output": output_table_name, "is_cached": is_cached}

    except Exception as e:
        raise RuntimeError(f"Failed to fetch boundary data: {str(e)}")


def dbconnection(**kwargs):
    """
    Creates a database connection node that returns the provided connection_id
    """
    node = Node(**kwargs)

    # Get the connection_id input
    connection_id = node.input("connectionId")

    if not connection_id:
        raise ValueError("Please provide a connection ID")

    return {"connection": connection_id, "is_cached": False}


def aggregation(**kwargs):
    """
    Performs spatial aggregation with customizable grouping, functions, and spatial predicates
    Includes crosstab functionality when split_by is present
    """
    node = Node(**kwargs)

    # Get inputs
    base_layer = node.input("baseLayer")
    join_layer = node.input("joinLayer")
    spatial_predicate = node.input("spatialPredicate","intersects")
    split_by = node.input("splitBy",[])
    aggregations = node.input("aggregations",[])

    # Maps for predicates and functions
    predicate_map = {
        "contains": "ST_Contains",
        "intersects": "ST_Intersects",
        "within": "ST_Within",
        "touches": "ST_Touches",
        "crosses": "ST_Crosses",
        "overlaps": "ST_Overlaps"
    }

    function_map = {
        "count": "COUNT",
        "sum": "SUM",
        "avg": "AVG",
        "min": "MIN",
        "max": "MAX"
    }

    # Validate inputs
    if not base_layer or not join_layer:
        raise ValueError("Both base layer and join layer must be provided")
    if spatial_predicate not in predicate_map:
        raise ValueError(f"Invalid spatial predicate. Must be one of: {', '.join(predicate_map.keys())}")
    if not aggregations:
        raise ValueError("At least one aggregation must be specified")

    engine = get_db_engine_lepton()
    base_columns = get_column_names(engine, base_layer)
   

    if split_by:
        # Crosstab query with SRID handling
        split_col = split_by[0].get("column")
        base_select_cols = [f'b."{col}"' for col in base_columns if col != "geometry"]
        agg_func = aggregations[0].get("function", "count").upper()
        agg_attr = aggregations[0].get("attribute", "*")
        
        if agg_func == "COUNT" and (not agg_attr or agg_attr == "*"):
            count_expr = f'j."{agg_attr}"' if agg_attr and agg_attr != "*" else "j.*"
            agg_expression = f"COALESCE(COUNT({count_expr}), 0)"
        else:
            agg_expression = f'{agg_func}(j."{agg_attr}")'

        subquery = f"""
            SELECT 
                {', '.join(base_select_cols)},
                j."{split_col}" as category,
                {agg_expression} as value
            FROM workflows."{base_layer}" b
            LEFT JOIN workflows."{join_layer}" j
                ON {predicate_map[spatial_predicate]}(b.geometry, j.geometry)
            GROUP BY {', '.join(base_select_cols)}, j."{split_col}"
        """

        # Get unique categories
        categories_query = f"""
            SELECT DISTINCT "{split_col}"
            FROM workflows."{join_layer}"
            WHERE "{split_col}" IS NOT NULL
            ORDER BY "{split_col}"
        """
        with engine.connect() as conn:
            categories = [row[0] for row in conn.execute(categories_query)]

        category_columns = [
            f"COALESCE(MAX(CASE WHEN category = '{cat}' THEN value END), 0) as \"{cat}\""
            for cat in categories
        ]

        query = f"""
            SELECT 
                {', '.join(base_select_cols)},
                {', '.join(category_columns)},
                b.geometry as geometry
            FROM ({subquery}) as sub
            RIGHT JOIN workflows."{base_layer}" b 
                ON {' AND '.join(f'sub."{col}" = b."{col}"' for col in base_columns if col != "geometry")}
            GROUP BY {', '.join(f'b."{col}"' for col in base_columns)}
        """

    else:
        # Original aggregation query with SRID handling
        select_cols = [f'b."{col}"' for col in base_columns if col != "geometry"]
        select_cols.append('b.geometry as geometry')
        group_by_cols = [f'b."{col}"' for col in base_columns]

        # Build aggregation expressions
        agg_expressions = []
        for agg in aggregations:
            print(agg, "agg")
            func = function_map.get(agg.get("function", "").lower())
            print("func", func)
            if not func:
                raise ValueError(f"Invalid aggregate function. Must be one of: {', '.join(function_map.keys())}")
            
            attr = agg.get("attribute")
            alias = agg.get("alias") or func.lower()
            if func == "COUNT" and (not attr or attr == "*"):
                # agg_expressions.append(f"COUNT(*) AS {alias}")
                count_expr = f'j."{attr}"' if attr and attr != "*" else "j.*"
                agg_expressions.append(f"COALESCE(COUNT({count_expr}), 0) AS {alias}")
            else:
                agg_expressions.append(f'{func}(j."{attr}") AS {alias}')

        # Combine all SELECT columns
        select_clause = ",\n    ".join(select_cols + agg_expressions)
        group_by_clause = ",\n    ".join(group_by_cols)

        query = f"""
            SELECT 
                {select_clause}
            FROM workflows."{base_layer}" b
            LEFT JOIN workflows."{join_layer}" j
                ON {predicate_map[spatial_predicate]}(b.geometry, j.geometry)
            GROUP BY {group_by_clause}
            ORDER BY {group_by_clause}
        """

    # Execute query and save results
    output_table_name, is_cached = node.compute_in_db(
        func_name="aggregation",
        inputs={
            "baseLayer": base_layer,
            "joinLayer": join_layer,
            "spatialPredicate": spatial_predicate,
            "splitBy": split_by,
            "aggregations": aggregations
        },
        query=query,
        geom_col=["geometry"],
        input_table_name=base_layer,
        replace_query_columns=False
    )

    return {
        "output": output_table_name,
        "is_cached": is_cached
    }

def difference(**kwargs):
    """
    Performs spatial difference between two polygon layers and optionally scales numeric
    columns based on the area ratio of the difference
    """
    node = Node(**kwargs)

    # Get inputs
    base_layer = node.input("baseLayer")
    subtract_layer = node.input("subtractLayer")
    # Get optional inputs, checking both data and connections
    try:
        scale_columns = node.input("scaleColumns")
    except ValueError:  # No connection found
        scale_columns = []
    
    try:
        carry_columns = node.input("carryColumns")
    except ValueError:  # No connection found
        carry_columns = []

    engine = get_db_engine_lepton()
    
    # Get column information from base layer
    base_columns = get_column_names(engine, base_layer)

    # Validate columns
    if scale_columns:
        invalid_cols = [col for col in scale_columns if col not in base_columns]
        if invalid_cols:
            raise ValueError(f"Invalid scale columns: {invalid_cols}")
    
    if carry_columns:
        invalid_cols = [col for col in carry_columns if col not in base_columns]
        if invalid_cols:
            raise ValueError(f"Invalid carry columns: {invalid_cols}")
    
    # If no columns specified, carry forward all non-geometry columns
    if not scale_columns and not carry_columns:
        carry_columns = [col for col in base_columns if col != "geometry"]

    # Build SELECT expressions
    select_parts = []

    # Add carry-forward columns
    for col in carry_columns:
        if col != "geometry":  # Skip geometry as we'll handle it separately
            select_parts.append(f'b."{col}"')

    # Build area ratio expression
    ratio_expr = """
        CASE 
            WHEN ST_Area(b.geometry::geography) = 0 THEN 0 
            ELSE ST_Area(
                ST_Difference(
                    b.geometry, 
                    COALESCE(ST_Union(s.geometry::geometry), ST_GeomFromText('POLYGON EMPTY', 4326))
                )::geography
            ) / ST_Area(b.geometry::geography)
        END
    """

    # Add scaled columns
    for col in scale_columns:
        scaled_expr = f'(b."{col}" * ({ratio_expr})) AS "{col}"'
        select_parts.append(scaled_expr)

    # Add the new geometry
    geom_expr = """
        ST_Difference(
            b.geometry, 
            COALESCE(ST_Union(s.geometry::geometry), ST_GeomFromText('POLYGON EMPTY', 4326))
        ) AS geometry
    """
    select_parts.append(geom_expr)
    
    select_clause = ',\n            '.join(select_parts)

    # Build the complete query
    query = f"""
        SELECT 
            {select_clause}
        FROM workflows."{base_layer}" b
        LEFT JOIN workflows."{subtract_layer}" s
            ON ST_Intersects(b.geometry, s.geometry)
        GROUP BY {', '.join(f'b."{col}"' for col in base_columns)}
    """

    # Execute query and save results
    output_table_name, is_cached = node.compute_in_db(
        func_name="difference",
        inputs={
            "baseLayer": base_layer,
            "subtractLayer": subtract_layer,
            "scaleColumns": scale_columns,
            "carryColumns": carry_columns
        },
        query=query,
        geom_col=["geometry"],
        input_table_name=base_layer,
        replace_query_columns=False
    )

    return {
        "output": output_table_name,
        "is_cached": is_cached
    }


def dissolve(**kwargs):
    from airflow.models import Variable
    """
    Performs dissolve operation on polygon features with optional attribute-based dissolving
    and aggregation of numeric columns
    """
    node = Node(**kwargs)

    # Get inputs
    base_layer = node.input("baseLayer")
    dissolve_columns = node.input("dissolveColumns", [])  # Optional: columns to dissolve by
    aggregations = node.input("aggregations", [])  # Optional: list of aggregation objects
    is_touched = node.input("isTouched", False)  # Optional: dissolve touching polygons
    api_key = Variable.get("LEPTON_API_KEY")  # Get from variable

    print("aggregations", aggregations)
    print("dissolve_columns", dissolve_columns)
    print("is_touched", is_touched)
    print("base_layer", base_layer)
    if not base_layer:
        raise ValueError("Base layer must be provided")

    engine = get_db_engine_lepton()
    
    # Get data from postgres and convert to CSV 
    query = f'SELECT * FROM workflows."{base_layer}"'
    df = gpd.read_postgis(query, engine, geom_col='geometry')
    
    # Convert geometry to WKT
    df['geometry'] = df['geometry'].apply(lambda x: x.wkt)
    
    # Remove columns starting with '$' or '_'
    df = df.loc[:, ~df.columns.str.startswith(('$', '_'))]
    
    # Convert to CSV
    csv_data = df.to_csv(index=False)

    # Prepare API request
    url = "https://api.leptonmaps.com/v1/geojson/GIS/dissolve"
    
    # Build request payload
    payload = {
        "csv_dataset": csv_data,
        "dissolve_touching": is_touched
    }

    # Add optional parameters if provided
    if dissolve_columns:
        payload["dissolve_columns"] = dissolve_columns

    if aggregations:
        # Convert aggregations from array format to object format
        agg_dict = {}
        for agg in aggregations:
            # Each agg should be like {"attribute": "column_name", "function": "sum"}
            column = agg.get("attribute")
            operation = agg.get("function")
            if column and operation:
                agg_dict[column] = operation
        
        if agg_dict:  # Only add if we have valid aggregations
            payload["aggregation_columns"] = agg_dict

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }

    try:
        # Make API request
        response = requests.post(
            url,
            headers=headers,
            json=payload
        )

        # Check for errors
        if not response.ok:
            error_msg = response.text
            try:
                error_json = response.json()
                if isinstance(error_json, dict):
                    error_msg = error_json.get('message', error_msg)
            except:
                pass
            raise RuntimeError(f"Dissolve API request failed: {error_msg}")

        # Parse response
        try:
            # Get the response content as text first
            response_text = response.text
            
            # Parse the JSON response - handle both string and dict formats
            if isinstance(response_text, str):
                try:
                    result_geojson = json.loads(response_text)
                except json.JSONDecodeError:
                    print("Failed to parse response as JSON")
                    raise
            else:
                result_geojson = response_text

            
            # Convert string to dictionary if needed
            if isinstance(result_geojson, str):
                result_geojson = json.loads(result_geojson)
            
            # Create list of features for GeoDataFrame
            if not isinstance(result_geojson, dict):
                raise ValueError(f"Unexpected GeoJSON format. Got type: {type(result_geojson)}")
            
            features = result_geojson.get("features", [])
            if not features:
                raise ValueError("No features found in GeoJSON response")
            
            clean_features = []
            for feature in features:
                if isinstance(feature, str):
                    feature = json.loads(feature)
                
                # Extract properties and geometry
                properties = feature.get("properties", {})
                if isinstance(properties, str):
                    properties = json.loads(properties)
                
                geometry = feature.get("geometry", {})
                if isinstance(geometry, str):
                    geometry = json.loads(geometry)
                
                # Create clean feature dictionary
                clean_feature = {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": properties
                }
                clean_features.append(clean_feature)
            
            # Create GeoDataFrame from cleaned features
            gdf = gpd.GeoDataFrame.from_features(
                clean_features,
                crs="EPSG:4326"
            )
            
            # Ensure geometry column is properly set
            if "geometry" not in gdf.columns:
                raise ValueError("No geometry column found in response")
            
            # Set geometry column explicitly
            gdf = gdf.set_geometry("geometry")

            
        except Exception as e:
            print("Error details:", str(e))
            print("Response type:", type(response_text))
            print("Response content:", response_text[:1000])  # Print first 1000 chars
            raise RuntimeError(f"Failed to process GeoJSON response: {str(e)}")
        
        output_table_name = node.create_output_table_name(
            func_name="dissolve",
            inputs={
                "baseLayer": base_layer,
                "dissolveColumns": dissolve_columns,
                "aggregations": aggregations,
                "isTouched": is_touched
            }
        )
        
        # Save to database
        is_cached = node.save_df_to_postgres(gdf, output_table_name)

        return {
            "output": output_table_name,
            "is_cached": is_cached
        }

    except Exception as e:
        raise RuntimeError(f"Error in dissolve operation: {str(e)}")


def upload(**kwargs):
    """
    Processes uploaded files from Supabase storage and saves them to PostgreSQL
    Supports GeoJSON, CSV, and Excel file formats with flexible geometry handling
    """
    from airflow.models import Variable
    import tempfile
    import pandas as pd
    from supabase import create_client

    node = Node(**kwargs)
    
    # Get upload ID from node input
    upload_id = node.input("uploadId")
    if not upload_id:
        raise ValueError("Upload ID is required")

    # Initialize Supabase client
    supabase = create_client(Variable.get("SUPABASE_URL"), Variable.get("SUPABASE_KEY"))

    try:
        # Fetch upload metadata from database
        response = supabase.table("workflow_uploads").select("*").eq("id", upload_id).execute()
        if not response.data:
            raise ValueError(f"No upload found with ID: {upload_id}")
        
        metadata = response.data[0]
        file_path = metadata["file_path"]
        file_type = metadata["file_type"]

        # Create output table name
        output_table_name = node.create_output_table_name(
            func_name="upload",
            inputs={"uploadId": upload_id}
        )

        # Check if cached result exists
        engine = get_db_engine_lepton()
        if table_exists(engine, output_table_name):
            return {"output": output_table_name, "is_cached": True}

        # Download file to temporary location
        with tempfile.NamedTemporaryFile(suffix=f".{file_type}") as temp_file:
            file_data = supabase.storage.from_("workflows").download(file_path)
            temp_file.write(file_data)
            temp_file.flush()

            # Read file based on type
            if file_type == "geojson":
                df = gpd.read_file(temp_file.name)
            elif file_type in ["csv", "xlsx"]:
                # Read the file into a pandas DataFrame
                df = pd.read_csv(temp_file.name) if file_type == "csv" else pd.read_excel(temp_file.name)
                
                # Check for different possible geometry column combinations
                if "geometry" in df.columns:
                    # Try to convert WKT geometry string to geometry object
                    try:
                        df["geometry"] = df["geometry"].apply(wkt.loads)
                        df = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
                    except Exception as e:
                        print(f"Failed to parse geometry column: {e}")
                        df["geometry"] = None
                
                # Check for various latitude/longitude column combinations
                lat_cols = ["latitude", "lat", "y", "Latitude", "Lat", "Y"]
                lon_cols = ["longitude", "long", "lon", "lng", "x","Longitude", "Long", "Lng", "X"]
                
                lat_col = next((col for col in lat_cols if col in df.columns), None)
                lon_col = next((col for col in lon_cols if col in df.columns), None)
                
                if lat_col and lon_col:
                    try:
                        # Convert to numeric, replacing invalid values with NaN
                        df[lat_col] = pd.to_numeric(df[lat_col], errors='coerce')
                        df[lon_col] = pd.to_numeric(df[lon_col], errors='coerce')
                        
                        # Drop rows with NaN coordinates
                        valid_coords = df[[lat_col, lon_col]].notna().all(axis=1)
                        if not valid_coords.all():
                            print(f"Warning: {(~valid_coords).sum()} rows had invalid coordinates and were dropped")
                        df = df[valid_coords]
                        
                        # Create geometry from coordinates
                        geometry = gpd.points_from_xy(df[lon_col], df[lat_col])
                        df = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
                    except Exception as e:
                        print(f"Failed to create geometry from coordinates: {e}")
                        raise ValueError("Could not create valid geometries from coordinate columns")
                
                if not isinstance(df, gpd.GeoDataFrame) or df.geometry.isna().all():
                    raise ValueError("Input file must contain valid geometry data or coordinate columns")
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

            # Ensure we have a GeoDataFrame
            if not isinstance(df, gpd.GeoDataFrame):
                raise ValueError("Input file must contain geometry data")

            # Add metadata columns
            # df["_upload_id"] = upload_id
            # df["_file_name"] = metadata["file_name"]
            # df["_uploaded_at"] = metadata["uploaded_at"]
            
            # Save to PostgreSQL
            is_cached = node.save_df_to_postgres(df, output_table_name)

            return {
                "output": output_table_name,
                "is_cached": is_cached
            }

    except Exception as e:
        raise RuntimeError(f"Failed to process upload: {str(e)}")


def placesinsights(**kwargs):
    """
    Processes Places Insights data for geographic areas and saves results to PostgreSQL
    Supports filtering by categories, ratings, and various place attributes
    """
    from airflow.models import Variable
    import requests
    import json

    node = Node(**kwargs)
    
    # Get required inputs
    base_layer = node.input("geometry")  # Changed from "baseLayer" to "geometry"
    if not base_layer:
        raise ValueError("Base layer must be provided")

    # Get data from node.data instead of individual inputs
    selected_categories = node.input("selectedCategories", [])
    active_filters = node.input("activeFilters", [])
    filter_values = node.input("filterValues", {})
    aggregate_by = node.input("aggregateBy", [])
    place_types = node.input("placeTypes", [])
    include_review_ratings = node.input("include_review_ratings", False)

    # Validate inputs
    if not selected_categories:
        raise ValueError("At least one category must be selected")

     # Create output table name for cache checking
    output_table_name = node.create_output_table_name(
        func_name="places_insights",
        inputs={
            "baseLayer": base_layer,
            "selectedCategories": selected_categories,
            "activeFilters": active_filters,
            "aggregateBy": aggregate_by,
            "placeTypes": place_types,
            "includeReviewRatings": include_review_ratings
        }
    )

    # Check if cached result exists
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        return {"output": output_table_name, "is_cached": True}


    # Get API key
    api_key = Variable.get("LEPTON_API_KEY")
    if not api_key:
        raise ValueError("LEPTON_API_KEY not found in Airflow variables")

    # Initialize database connection
    engine = get_db_engine_lepton()

    # Get data from postgres
    query = f'SELECT * FROM workflows."{base_layer}"'
    df = gpd.read_postgis(query, engine, geom_col='geometry')

    # Process filters
    filter_params = {}
    if active_filters:
        for filter_id in active_filters:
            filter_value = filter_values.get(filter_id, {})
            
            if filter_id == "rating":
                # Handle rating with comparison operators
                if filter_value.get("minValue") is not None:
                    min_comparison = filter_value.get("minComparison")
                    if min_comparison == "greaterThan":
                        filter_params["min_rating_exclusive"] = filter_value["minValue"]
                    elif min_comparison == "greaterThanEqual":
                        filter_params["min_rating"] = filter_value["minValue"]
                
                if filter_value.get("maxValue") is not None:
                    max_comparison = filter_value.get("maxComparison")
                    if max_comparison == "lessThan":
                        filter_params["max_rating_exclusive"] = filter_value["maxValue"]
                    elif max_comparison == "lessThanEqual":
                        filter_params["max_rating"] = filter_value["maxValue"]
            
            elif filter_id == "minUserRating":
                if filter_value.get("minValue") is not None:
                    filter_params["min_user_ratings"] = filter_value["minValue"]
            
            elif filter_id == "priceLevel":
                if filter_value:
                    filter_params["price_level"] = filter_value
            
            elif filter_id == "businessStatus":
                if filter_value:
                    filter_params["business_status"] = filter_value

    # Process place types (empty in this case, but keeping for future use)
    if place_types:
        place_type = place_types[0]
        filter_params["place_types"] = "primary" if place_type.get("isPrimary") else "types"

    # Prepare features for API request
    features = []
    for idx, row in df.iterrows():
        geom = row.geometry
        
        feature = {
            "type": "Feature",
            "properties": {
                "uniqueId": str(idx),
                "geoId": str(idx)
            },
            "geometry": geom.__geo_interface__
        }
        features.append(feature)

    # Prepare API request payload
    payload = {
        "subcategories": selected_categories,
        "aggregate_by": aggregate_by,
        "include_review_ratings": str(include_review_ratings).lower(),
        "input_geometry": [{
            "type": "FeatureCollection",
            "features": features
        }],
        **filter_params
    }

    # Make API request
    url = "https://api.leptonmaps.com/v1/geojson/places/advanced_area_insights"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        # Parse response
        result = response.json()
        
        if not result.get("data"):
            raise ValueError("No data received from API")

        # Create GeoDataFrame from response
        gdf = df.copy()
        
        # Add response data to GeoDataFrame
        for item in result["data"]:
            idx = int(item["geoId"])
            for key, value in item.items():
                if key != "geoId":
                    gdf.loc[idx, key] = value

        # # Generate output table name
        # output_table_name = node.create_output_table_name(
        #     func_name="places_insights",
        #     inputs={
        #         "baseLayer": base_layer,
        #         "selectedCategories": selected_categories,
        #         "activeFilters": active_filters,
        #         "aggregateBy": aggregate_by,
        #         "placeTypes": place_types,
        #         "includeReviewRatings": include_review_ratings
        #     }
        # )

        # Save to database
        is_cached = node.save_df_to_postgres(gdf, output_table_name)

        return {
            "output": output_table_name,
            "is_cached": is_cached
        }

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"API request failed: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error in places insights operation: {str(e)}")
    
def proximity(**kwargs):
    """
    Performs proximity analysis between two layers and saves results to PostgreSQL.
    Supports distance calculations in kilometers or meters and attribute transfer.
    """
    from airflow.models import Variable
    import requests

    node = Node(**kwargs)

    # Get inputs
    base_layer = node.input("baseLayer")
    target_layer = node.input("targetLayer")
    attributes = node.input("attributes", [])  # Optional list of attributes to transfer
    unit = node.input("unit", "km")  # Default to kilometers

    if not base_layer:
        raise ValueError("Base layer must be provided")
    if not target_layer:
        raise ValueError("Target layer must be provided")
    if unit not in ["km", "m"]:
        raise ValueError("Unit must be either 'km' or 'm'")

    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="proximity",
        inputs={
            "baseLayer": base_layer,
            "targetLayer": target_layer,
            "attributes": attributes,
            "unit": unit
        }
    )

    # Check if cached result exists
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        return {"output": output_table_name, "is_cached": True}

    # Get data from postgres for both layers
    base_df = gpd.read_postgis(
        f'SELECT * FROM workflows."{base_layer}"',
        engine,
        geom_col="geometry"
    )
    target_df = gpd.read_postgis(
        f'SELECT * FROM workflows."{target_layer}"',
        engine,
        geom_col="geometry"
    )

    # Check if it's the same layer
    is_same_layer = base_layer == target_layer

    # Prepare API request
    api_key = Variable.get("LEPTON_API_KEY")
    
    if is_same_layer:
        # Use proximity_check API for same layer analysis
        url = "https://api.leptonmaps.com/v1/geojson/GIS/proximity_check"
        payload = {
            "geojson_data": {
                "type": "FeatureCollection",
                "features": json.loads(base_df.to_json())["features"]
            },
            "unit": unit,
            "layerId": "_gid"
        }
    else:
        # Use nearest_with_details API for different layers
        url = "https://api.leptonmaps.com/v1/nearby/nearest_with_details"
        payload = {
            "layer1": {
                "type": "FeatureCollection",
                "features": json.loads(base_df.to_json())["features"]
            },
            "layer2":{
                "type": "FeatureCollection",
                "features": json.loads(target_df.to_json())["features"]
            },
            "unit": unit,
            "layer1_id": "_gid",
            "attrs_layer2": attributes
        }

    try:
        # Make API request
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key
            },
            json=payload
        )
        response.raise_for_status()
        
        # Process response
        result = response.json()
        
        if not result:
            raise ValueError("No data received from API")

        # Create output DataFrame starting with base layer
        output_df = base_df.copy()
        
        # Process each feature's results
        for gid, data in result.items():
            idx = int(gid)
            
            # Get distance value based on unit
            distance_value = data.get(
                'nearest_point_distance_km' if unit == 'km' else 'nearest_point_distance_m',
                None
            )
            
            # Add distance column
            target_suffix = f"_{target_layer}" if is_same_layer else ""
            distance_col = f"nearest_{unit}_distance{target_suffix}"
            output_df.loc[output_df['_gid'] == idx, distance_col] = distance_value
            
            # Add attribute columns if present
            if attributes:
                for key, value in data.items():
                    if key not in ['nearest_point_distance_km', 'nearest_point_distance_m']:
                        # Add suffix for same layer to avoid column conflicts
                        col_name = f"{key}_{target_layer}" if is_same_layer else key
                        output_df.loc[output_df['_gid'] == idx, col_name] = value

        # Save to database
        is_cached = node.save_df_to_postgres(output_df, output_table_name)

        return {
            "output": output_table_name,
            "is_cached": is_cached
        }

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"API request failed: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error in proximity analysis: {str(e)}")
    
def weightage(**kwargs):
    """
    Performs weighted calculations on numeric columns with optional normalization methods.
    Supports Min-Max, Z-Score, Robust, MaxAbs, Mean normalization, and Log transformation.
    """
    node = Node(**kwargs)

    # Get inputs
    feature_collection = node.input("featureCollection")
    categories = node.input("categories", {})  # Dictionary of attribute configurations
    weightage_name = node.input("weightageName")

    if not feature_collection:
        raise ValueError("Feature collection must be provided")
    if not categories:
        raise ValueError("At least one attribute must be selected for weightage calculation")
    if not weightage_name:
        raise ValueError("Weightage name must be provided")

    # Parse categories input
    try:
        categories = {
            attr_id: {
                "normalizationType": config.get("normalizationType", "None"),
                "value": float(config.get("value", 0))
            }
            for attr_id, config in categories.items()
            if float(config.get("value", 0)) != 0  # Skip attributes with zero weight
        }
    except ValueError as e:
        raise ValueError(f"Invalid weight value: {str(e)}")

    if not categories:
        raise ValueError("At least one attribute must have a non-zero weight")
    
    output_table_name = node.create_output_table_name(
        func_name="weightage",
        inputs={
            "featureCollection": feature_collection,
            "categories": categories,
            "weightageName": weightage_name
        }
    )

    # Check if cached result exists
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        return {"output": output_table_name, "is_cached": True}

    # Build the SQL query
    attr_expressions = []
    weight_sum = sum(config["value"] for config in categories.values())
    
    base_columns = get_column_names(engine, feature_collection)
    
    columns_list = ", ".join([f'"{col}"' for col in base_columns])

    for attr_id, config in categories.items():
        # weight = config["value"] / weight_sum  # Normalize weights to sum to 1
        weight = config["value"]
        norm_type = config["normalizationType"]

        # Build normalization expression based on type
        if norm_type == "MinMax":
            # (x - min(x)) / (max(x) - min(x))
            norm_expr = f"""
                CASE 
                    WHEN MAX("{attr_id}") OVER () = MIN("{attr_id}") OVER () THEN 0
                    ELSE (("{attr_id}" - MIN("{attr_id}") OVER ()) / 
                          NULLIF(MAX("{attr_id}") OVER () - MIN("{attr_id}") OVER (), 0))::float
                END
            """
        elif norm_type == "ZScore":
            # (x - mean(x)) / stddev(x)
            norm_expr = f"""
                CASE 
                    WHEN STDDEV("{attr_id}") OVER () = 0 THEN 0
                    ELSE (("{attr_id}" - AVG("{attr_id}") OVER ()) / 
                          NULLIF(STDDEV("{attr_id}") OVER (), 0))::float
                END
            """
        elif norm_type == "RobustScaling":
            # (x - median(x)) / (Q3 - Q1)
             norm_expr = f"""
            (
                SELECT
                    CASE 
                        WHEN (q3_{attr_id} - q1_{attr_id}) = 0 THEN 0
                        ELSE (("{attr_id}" - median_{attr_id}) /
                              NULLIF(q3_{attr_id} - q1_{attr_id}, 0))::float
                    END
                FROM (
                    SELECT 
                        percentile_cont(0.25) WITHIN GROUP (ORDER BY "{attr_id}") as q1_{attr_id},
                        percentile_cont(0.5) WITHIN GROUP (ORDER BY "{attr_id}") as median_{attr_id},
                        percentile_cont(0.75) WITHIN GROUP (ORDER BY "{attr_id}") as q3_{attr_id}
                    FROM workflows."{feature_collection}"
                ) as quartiles
            )
        """
        elif norm_type == "MaxAbsScaling":
            # x / max(|x|)
            norm_expr = f"""
                CASE 
                    WHEN MAX(ABS("{attr_id}")) OVER () = 0 THEN 0
                    ELSE ("{attr_id}" / NULLIF(MAX(ABS("{attr_id}")) OVER (), 0))::float
                END
            """
        elif norm_type == "MeanNormalization":
            # (x - mean(x)) / (max(x) - min(x))
            norm_expr = f"""
                CASE 
                    WHEN (MAX("{attr_id}") OVER () - MIN("{attr_id}") OVER ()) = 0 THEN 0
                    ELSE (("{attr_id}" - AVG("{attr_id}") OVER ()) /
                          NULLIF(MAX("{attr_id}") OVER () - MIN("{attr_id}") OVER (), 0))::float
                END
            """
        elif norm_type == "LogTransformation":
            # log(x + 1)
            norm_expr = f"""
                CASE 
                    WHEN "{attr_id}" < 0 THEN NULL
                    ELSE LN(NULLIF("{attr_id}" + 1, 0))::float
                END
            """
        else:  # No normalization
            norm_expr = f"""
            "{attr_id}"::float
        """

        # Add weighted normalized expression
        attr_expressions.append(f"({norm_expr} * {weight})")

    # Combine all weighted expressions
    weightage_expr = " + ".join(attr_expressions)

    # Build final query
    query = f"""
        WITH normalized_data AS (
            SELECT 
                {columns_list},
                CASE 
                    WHEN {weightage_expr} IS NULL THEN 0
                    ELSE {weightage_expr}
                END AS "{weightage_name}"
            FROM workflows."{feature_collection}"
        )
        SELECT * FROM normalized_data
    """

    # Execute query and save results
    output_table_name, is_cached = node.compute_in_db(
        func_name="weightage",
        inputs={
            "featureCollection": feature_collection,
            "categories": categories,
            "weightageName": weightage_name
        },
        query=query,
        geom_col=["geometry"],
        input_table_name=feature_collection,
        replace_query_columns=False
    )

    return {
        "output": output_table_name,
        "is_cached": is_cached
    }

def tolls(**kwargs):
    """
    Calculates toll costs and routes between origin and destination points
    with support for different vehicle types and journey types.
    """
    from airflow.models import Variable
    import requests

    node = Node(**kwargs)

    # Get inputs
    origin = node.input("origin")  # Should be lat,lng format
    destination = node.input("destination")  # Should be lat,lng format
    vehicle_type = node.input("vehicleType")  # e.g., "2W", "PV", etc.
    journey_type = node.input("journeyType")  # "SJ", "RJ", or "MP"

    # Validate inputs
    if not origin or not destination:
        raise ValueError("Both origin and destination must be provided")
    if not vehicle_type:
        raise ValueError("Vehicle type must be provided")
    if not journey_type:
        raise ValueError("Journey type must be provided")

    # Validate vehicle type
    valid_vehicle_types = ["2W", "PV", "LCV", "BUS", "3AX", "4TO6AX", "HCM_EME", "7AX"]
    if vehicle_type not in valid_vehicle_types:
        raise ValueError(f"Invalid vehicle type. Must be one of: {', '.join(valid_vehicle_types)}")

    # Validate journey type
    valid_journey_types = ["SJ", "RJ", "MP"]
    if journey_type not in valid_journey_types:
        raise ValueError(f"Invalid journey type. Must be one of: {', '.join(valid_journey_types)}")

    # Create combined journey parameter
    journey_param = f"{vehicle_type}_{journey_type}"

    try:
        # Make API request
        response = requests.get(
            "https://api.leptonmaps.com/v1/toll",
            params={
                "origin": origin,
                "destination": destination,
                "journey_type": journey_param,
                "include_route": "true",
                "include_booths": "true",
                "include_booths_locations": "true"
            },
            headers={"X-API-Key": Variable.get("LEPTON_API_KEY")}
        )
        response.raise_for_status()
        data = response.json()

        # Extract route coordinates and create LineString
        if "route" in data and isinstance(data["route"], list):
            route_coords = data["route"]
            route_geom = {"type": "LineString", "coordinates": route_coords}
            route_df = gpd.GeoDataFrame(
                {
                    "geometry": [shape(route_geom)],
                    "total_distance": data.get("toll_booths", [{}])[-1].get("distance_to_origin", 0),
                    "total_toll": data.get("total_toll_price", 0),
                    "toll_count": data.get("toll_count", 0),
                    "vehicle_type": vehicle_type,
                    "journey_type": journey_type
                },
                crs="EPSG:4326"
            )

            # Create toll booths GeoDataFrame if available
            booth_geometries = []
            booth_properties = []
            
            if "toll_booths" in data and isinstance(data["toll_booths"], list):
                for booth in data["toll_booths"]:
                    if "latitude" in booth and "longitude" in booth:
                        # Create Point geometry for each toll booth
                        point_geom = {"type": "Point", "coordinates": [booth["longitude"], booth["latitude"]]}
                        booth_geometries.append(shape(point_geom))
                        
                        # Store all properties for the booth
                        properties = {
                            "name": booth.get("name", ""),
                            "route_name": booth.get("route_name", ""),
                            "price": booth.get("price", 0),
                            "dynamic_entry": booth.get("dynamic_entry", False),
                            "dynamic_exit": booth.get("dynamic_exit", False),
                            "distance_to_origin": booth.get("distance_to_origin", 0),
                            "type": "Toll Booth"  # Add type for FE compatibility
                        }
                        booth_properties.append(properties)
            
            # Add origin and destination points
            if route_coords and len(route_coords) > 1:
                # Origin point
                origin_point = {"type": "Point", "coordinates": route_coords[0]}
                booth_geometries.append(shape(origin_point))
                booth_properties.append({
                    "name": "Origin",
                    "type": "Origin",
                    "price": 0,
                    "distance_to_origin": 0
                })
                
                # Destination point
                dest_point = {"type": "Point", "coordinates": route_coords[-1]}
                booth_geometries.append(shape(dest_point))
                booth_properties.append({
                    "name": "Destination",
                    "type": "Destination",
                    "price": 0,
                    "distance_to_origin": data.get("toll_booths", [{}])[-1].get("distance_to_origin", 0)
                })
            
            if booth_geometries:
                booths_df = gpd.GeoDataFrame(
                    booth_properties,
                    geometry=booth_geometries,
                    crs="EPSG:4326"
                )
            else:
                booths_df = None

            # Save route to database
            route_table_name = node.create_output_table_name(
                func_name="tolls_route",
                inputs={
                    "origin": origin,
                    "destination": destination,
                    "vehicleType": vehicle_type,
                    "journeyType": journey_type
                }
            )
            is_cached_route = node.save_df_to_postgres(route_df, route_table_name)

            # Save booths to database if available
            if booths_df is not None:
                booths_table_name = node.create_output_table_name(
                    func_name="tolls_booths",
                    inputs={
                        "origin": origin,
                        "destination": destination,
                        "vehicleType": vehicle_type,
                        "journeyType": journey_type
                    }
                )
                is_cached_booths = node.save_df_to_postgres(booths_df, booths_table_name)
            else:
                booths_table_name = None
                is_cached_booths = False
            print(route_table_name, booths_table_name, "route_table_name")
            return {
                "route":route_table_name,
                "booths": booths_table_name
            }

        else:
            raise ValueError("No route found in API response")

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"API request failed: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error in toll calculation: {str(e)}")

def kmeans(**kwargs):
    """
    Performs K-means clustering on geospatial data.
    Always calculates optimal points in a separate API call.
    
    Args:
        featureCollection: Input feature collection
        n_clusters: Number of clusters to create
        weight_attr: Optional weight attribute for weighted clustering
        clustering_algorithm: The clustering algorithm to use ('kmeans' or 'constrained_kmeans')
        cluster_col: Column name to store cluster assignment
        size_min: Minimum size constraint for clusters (default: 0)
        size_max: Maximum size constraint for clusters (default: 0)
        optimal_points_count: Number of optimal points to calculate per cluster (default: 1)
        optimal_points_weight_attr: Weight attribute for optimal points calculation
        optimal_points_even_dist: Whether to distribute optimal points evenly (default: false)
    
    Returns:
        Dictionary with output table names for clusters and optimal points
    """
    from airflow.models import Variable
    import requests
    import json
    import re
    
    # Initialize node
    node = Node(**kwargs)
    
    # Helper function to determine the next cluster column name
    def get_next_cluster_column_name(features):
        """
        Determines the next cluster column name based on existing cluster columns.
        
        Args:
            features: List of features to analyze for existing cluster columns
            
        Returns:
            String with the next cluster column name (e.g., "cluster", "cluster-1", etc.)
        """
        if not features or len(features) == 0:
            return "cluster"
        
        # Create a regex to match cluster keys like "cluster", "cluster-1", "cluster-2", etc.
        regex = re.compile(r"^cluster(?:-(\d+))?$")
        
        # Collect all matching cluster keys and their numbers from all features
        cluster_numbers = []
        for feature in features:
            properties = feature.get("properties", {})
            for key in properties.keys():
                match = regex.match(key)
                if match:
                    # Extract the number part, if present
                    number = match.group(1)
                    # Return 0 for "cluster" and numbers for "cluster-x"
                    cluster_numbers.append(0 if number is None else int(number))
        
        # If no clusters are found, return base "cluster"
        if len(cluster_numbers) == 0:
            return "cluster"
        
        # Return the highest cluster number + 1
        return f"cluster-{max(cluster_numbers) + 1}"
    
    # Get required parameters
    feature_collection = node.input("featureCollection")
    
    try:
        n_clusters = int(node.input("n_clusters", 1))
    except (ValueError, TypeError):
        raise ValueError("n_clusters must be an integer")
        
    weight_attr = node.input("weight_attr", "")
    
    # Get size constraints with proper parsing
    size_min = node.input("size_min", 0)
    size_max = node.input("size_max", 0)
    
    # Convert to integers or None if zero
    if size_min == 0:
        size_min = None
    else:
        try:
            size_min = int(size_min)
        except (ValueError, TypeError):
            size_min = None
            
    if size_max == 0:
        size_max = None
    else:
        try:
            size_max = int(size_max)
        except (ValueError, TypeError):
            size_max = None
    
    # Get clustering algorithm parameters
    clustering_algorithm = node.input("clustering_algorithm", "kmeans")
    kmeans_algo = "lloyd"
    return_bounding_box = False
    
    # Get optimal points parameters
    optimal_points_count = node.input("optimal_points_count", 1)
    try:
        optimal_points_count = int(optimal_points_count)
    except (ValueError, TypeError):
        optimal_points_count = 1
        
    optimal_points_weight_attr = node.input("optimal_points_weight_attr", "")
    optimal_points_even_dist = node.input("optimal_points_even_dist", False)
    if isinstance(optimal_points_even_dist, str):
        optimal_points_even_dist = optimal_points_even_dist.lower() == 'true'
    
    # Validate required parameters
    if not feature_collection:
        raise ValueError("Feature collection is required")
    
    if n_clusters < 1:
        raise ValueError("Number of clusters must be at least 1")
    
    # Get database engine
    engine = get_db_engine_lepton()
    
    # Load feature collection from database to get data
    query = f'SELECT * FROM workflows."{feature_collection}"'
    import pandas as pd
    import geopandas as gpd
    input_df = gpd.read_postgis(query, engine, geom_col="geometry")
    
    # Convert the GeoDataFrame to GeoJSON for API call
    geojson_features = json.loads(input_df.to_json())["features"]
    
    # Determine cluster column name if not explicitly provided
    cluster_col = node.input("cluster_col", get_next_cluster_column_name(geojson_features))
    print(f"Using cluster column: {cluster_col}")
    
    # Create output table name for clusters
    clusters_table_name = node.create_output_table_name(
        func_name="kmeans_clusters",
        inputs={
            "featureCollection": feature_collection,
            "n_clusters": n_clusters,
            "weight_attr": weight_attr,
            "size_min": size_min,
            "size_max": size_max,
            "clustering_algorithm": clustering_algorithm,
            "cluster_col": cluster_col
        }
    )
    
    # Create output table name for optimal points
    optimal_points_table_name = node.create_output_table_name(
        func_name="kmeans_optimal_points",
        inputs={
            "featureCollection": feature_collection,
            "n_clusters": n_clusters,
            "clustering_algorithm": clustering_algorithm,
            "optimal_points_count": optimal_points_count,
            "optimal_points_weight_attr": optimal_points_weight_attr,
            "optimal_points_even_dist": optimal_points_even_dist
        }
    )
    
    # Check if cached results exist
    clusters_cached = table_exists(engine, clusters_table_name)
    optimal_points_cached = table_exists(engine, optimal_points_table_name)
    
    if clusters_cached and optimal_points_cached:
        print(f"Using cached results for kmeans clustering: {clusters_table_name}")
        print(f"Using cached results for optimal points: {optimal_points_table_name}")
        
        return {
            "output": clusters_table_name,
            "optimal": optimal_points_table_name,
            "is_cached": True
        }
    
    # Validate input parameters
    if n_clusters > len(input_df):
        raise ValueError(f"Number of clusters ({n_clusters}) must be less than or equal to number of data points ({len(input_df)})")
    
    if size_max is not None and n_clusters is not None and clustering_algorithm == "constrained_kmeans":
        if size_max * n_clusters < len(input_df):
            raise ValueError(
                f"Error: The product of maximum size ({size_max}) and number of clusters ({n_clusters}), "
                f"which equals {size_max * n_clusters}, must be greater than or equal to the total number "
                f"of data points ({len(input_df)}). This error occurs because K-Means Constrained requires "
                f"enough cluster capacity to cover all data points. Please increase the maximum cluster size "
                f"or increase the number of clusters."
            )
    
    try:
        # Get API key from Airflow variables
        api_key = Variable.get("LEPTON_API_KEY")
        
        # 1. First API call: clustering
        # Prepare API payload for clustering
        clustering_payload = {
            "features": geojson_features,
            "size_min": size_min,
            "size_max": size_max,
            "weight_attr": weight_attr,
            "n_clusters": n_clusters,
            "clustering_algorithm": clustering_algorithm,
            "kmeans_algo": kmeans_algo,
            "return_bounding_box": return_bounding_box,
            "cluster_col": cluster_col
        }
        
        print(f"Making clustering API request with {len(geojson_features)} features")
        
        # Make API request for clustering with timeout
        try:
            clustering_response = requests.post(
                "https://api.leptonmaps.com/v1/geojson/clustering/cluster",
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": api_key
                },
                json=clustering_payload,
                timeout=120  # 2 minute timeout for clustering request
            )
        except requests.exceptions.Timeout:
            raise RuntimeError("Clustering API request timed out. The dataset may be too large or the service may be experiencing high load.")
        
        # Check for errors
        if not clustering_response.ok:
            error_msg = clustering_response.text
            try:
                error_json = clustering_response.json()
                if isinstance(error_json, dict):
                    error_msg = error_json.get('message', error_msg)
            except:
                pass
            raise RuntimeError(f"Clustering API request failed: {error_msg}")
        
        # Parse response
        clustering_result = clustering_response.json()
        
        # Extract the clusters data
        if not ("clusters" in clustering_result and clustering_result["clusters"].get("features")):
            raise ValueError("No cluster features found in API response")
            
        # Convert to GeoDataFrame
        clusters_df = gpd.GeoDataFrame.from_features(
            clustering_result["convex_hulls"]["features"], 
            crs="EPSG:4326"
        )
        
        # Save clusters to database
        is_cached_clusters = node.save_df_to_postgres(clusters_df, clusters_table_name)
        
        # 2. Second API call: optimal points
        # Prepare API payload for optimal points
        optimal_points_payload = {
            "features": clustering_result["clusters"]["features"],
            "optimal": optimal_points_count,
            "weight_attr": optimal_points_weight_attr,
            "cluster_col": cluster_col,
            "even_dist": optimal_points_even_dist
        }
        
        print(f"Making optimal points API request for {n_clusters} clusters")
        print("optimal points payload", optimal_points_payload)
        
        # Make API request for optimal points with timeout
        try:
            optimal_points_response = requests.post(
                "https://api.leptonmaps.com/v1/geojson/clustering/optimal_points",
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": api_key
                },
                json=optimal_points_payload,
                timeout=60  # 1 minute timeout for optimal points request
            )
        except requests.exceptions.Timeout:
            raise RuntimeError("Optimal points API request timed out.")
        
        # Check for errors in optimal points response
        if not optimal_points_response.ok:
            error_msg = optimal_points_response.text
            try:
                error_json = optimal_points_response.json()
                if isinstance(error_json, dict):
                    error_msg = error_json.get('message', error_msg)
            except:
                pass
            print(f"Warning: Optimal points API request failed: {error_msg}")
            # Create dummy optimal points if the API call fails
            from shapely.geometry import Point
            dummy_points = []
            for i in range(n_clusters):
                dummy_points.append({
                    "_gid": i + 1,
                    "cluster": i,
                    "geometry": Point(0, 0)
                })
            optimal_points_df = gpd.GeoDataFrame(dummy_points, geometry="geometry", crs="EPSG:4326")
        else:
            # Parse optimal points response
            optimal_points_result = optimal_points_response.json()
            
            # Extract optimal points
            if "optimal_points" in optimal_points_result and optimal_points_result["optimal_points"].get("features"):
                # Convert to GeoDataFrame
                optimal_points_df = gpd.GeoDataFrame.from_features(
                    optimal_points_result["optimal_points"]["features"],
                    crs="EPSG:4326"
                )
            else:
                # Create empty optimal points if not found in response
                print("Warning: No optimal points found in API response. Creating dummy points.")
                from shapely.geometry import Point
                dummy_points = []
                for i in range(n_clusters):
                    dummy_points.append({
                        "_gid": i + 1,
                        "cluster": i,
                        "geometry": Point(0, 0)
                    })
                optimal_points_df = gpd.GeoDataFrame(dummy_points, geometry="geometry", crs="EPSG:4326")
        
        # Save optimal points to database
        is_cached_optimal = node.save_df_to_postgres(optimal_points_df, optimal_points_table_name)
        
        # Return both table names
        return {
            "output": clusters_table_name,
            "optimal": optimal_points_table_name,
            "is_cached": is_cached_clusters and is_cached_optimal
        }
        
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"API request failed: {str(e)}")
    except ValueError as e:
        raise ValueError(f"Invalid input or parameter: {str(e)}")  
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse API response as JSON: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error in kmeans clustering: {str(e)}")

def donut(**kwargs):
    """
    Creates concentric ring buffers (donuts) around point geometries.
    
    Args:
        featureCollection: Input point feature collection
        steps: Number of concentric rings to create
        maxRadius: Maximum radius in meters
        featureId: Optional ID of a specific feature to process (processes all features if not provided)
    
    Returns:
        Dictionary with the output table name containing donut polygon features
    """
    import geopandas as gpd
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union
    
    node = Node(**kwargs)
    
    # Get inputs
    feature_collection = node.input("featureCollection")
    steps = int(node.input("steps", 3))
    max_radius = float(node.input("maxRadius", 200))
    feature_id = node.input("featureId", None)
    
    # Validate inputs
    if not feature_collection:
        raise ValueError("Feature collection is required")
    
    if steps < 1:
        raise ValueError("Steps must be at least 1")
    
    if max_radius <= 0:
        raise ValueError("Maximum radius must be greater than 0")
    
    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="donut",
        inputs={
            "featureCollection": feature_collection,
            "steps": steps,
            "maxRadius": max_radius,
            "featureId": feature_id
        }
    )
    
    # Check if cached results exist
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        print(f"Using cached donut results: {output_table_name}")
        return {
            "output": output_table_name,
            "is_cached": True
        }
    
    # Build query based on whether feature_id is provided
    if feature_id is not None:
        # Query for a specific feature
        query = f'''
            SELECT * FROM workflows."{feature_collection}" 
            WHERE _gid = {feature_id}::bigint
        '''
    else:
        # Query for all features
        query = f'SELECT * FROM workflows."{feature_collection}"'
    
    # Load input features
    df = gpd.read_postgis(
        query,
        engine,
        geom_col='geometry'
    )
    
    # Check if we found any features
    if df.empty:
        if feature_id is not None:
            raise ValueError(f"No feature found with ID {feature_id}")
        else:
            raise ValueError("No features found in the feature collection")
    
    # Check if input contains points
    if not all(geom.geom_type == 'Point' for geom in df.geometry):
        # Extract centroids for non-point geometries
        df['geometry'] = df['geometry'].apply(lambda geom: geom.centroid)
        print("Warning: Non-point geometries converted to centroids")
    
    # Calculate radius increment
    radius_increment = max_radius / steps
    
    # Create empty list to store donut features
    donut_features = []
    
    # Process each point feature
    for idx, row in df.iterrows():
        point = row.geometry
        properties = row.to_dict()
        
        # Get identifier from properties or use index
        if '_gid' in properties:
            identifier = properties['_gid']
        elif 'id' in properties:
            identifier = properties['id']
        else:
            identifier = idx
        
        # Get point coordinates for reference
        latitude = point.y
        longitude = point.x
        
        # Store original properties for reference
        orig_props = {
            k: v for k, v in properties.items() 
            if k != 'geometry' and not isinstance(v, (list, dict))
        }
        
        # Create donuts for each step
        for i in range(steps):
            inner_radius = i * radius_increment
            outer_radius = (i + 1) * radius_increment
            
            # Convert meters to approximate degrees (at the equator, 1 degree is ~111km)
            inner_radius_deg = inner_radius / 111000
            outer_radius_deg = outer_radius / 111000
            
            # Create the donut geometries
            if i == 0:
                # First step: create a simple buffer (circle)
                donut_geom = point.buffer(outer_radius_deg)
            else:
                # Create inner and outer circles
                inner_circle = point.buffer(inner_radius_deg)
                outer_circle = point.buffer(outer_radius_deg)
                
                # Create donut by subtracting inner circle from outer circle
                donut_geom = outer_circle.difference(inner_circle)
            
            # Ensure the geometry is valid
            if not donut_geom.is_valid:
                donut_geom = donut_geom.buffer(0)  # This often fixes invalid geometries
            
            # Skip empty geometries
            if donut_geom.is_empty:
                continue
            
            # Create properties for this donut
            donut_props = orig_props.copy()
            donut_props.update({
                "donut": f"{identifier} ({inner_radius:.1f}-{outer_radius:.1f})",
                "innerRadius": float(inner_radius),
                "outerRadius": float(outer_radius),
                "donutStep": i + 1,
                "center_lat": latitude,
                "center_lon": longitude,
                "_gid": len(donut_features) + 1  # Ensure unique _gid for each donut
            })
            
            # Add to features list with the donut polygon geometry
            donut_features.append({
                "geometry": donut_geom,
                **donut_props
            })
    
    # Create GeoDataFrame from polygon features
    donut_gdf = gpd.GeoDataFrame(donut_features, geometry="geometry", crs="EPSG:4326")
    
    # Save to database
    is_cached = node.save_df_to_postgres(donut_gdf, output_table_name)
    
    return {
        "output": output_table_name,
        "is_cached": is_cached
    }

def nearbyplaces(**kwargs):
    """
    Retrieves nearby places (POIs) around point geometries using either Google Places API or Lepton API.
    
    Args:
        featureCollection: Input point feature collection
        radius: Search radius in kilometers
        category: Main category for POI search
        subcategory: Subcategory or keyword for more specific search
        provider: API provider ("google" or "lepton")
        featureId: Optional ID of a specific feature to process (processes all features if not provided)
    
    Returns:
        Dictionary with the output table name containing nearby places as point features
    """
    from airflow.models import Variable
    import requests
    import json
    import pandas as pd
    import geopandas as gpd
    from shapely.geometry import Point
    
    node = Node(**kwargs)
    
    # Get inputs
    feature_collection = node.input("featureCollection")
    radius = float(node.input("radius", 1.0))  # Default to 1 km
    category = node.input("category", "")
    subcategory = node.input("subcategory", "")
    provider = node.input("provider", "lepton")  # Default to Lepton API
    
    # Validate inputs
    if not feature_collection:
        raise ValueError("Feature collection is required")
    
    if radius <= 0:
        raise ValueError("Radius must be greater than 0")
    
    if not category and provider == "google":
        raise ValueError("Category is required for Google Places API")
    
    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="nearbyplaces",
        inputs={
            "featureCollection": feature_collection,
            "radius": radius,
            "category": category,
            "subcategory": subcategory,
            "provider": provider
        }
    )
    
    # Check if cached results exist
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        print(f"Using cached nearby places results: {output_table_name}")
        return {
            "output": output_table_name,
            "is_cached": True
        }
    
    # Get API key
    try:
        api_key = Variable.get("LEPTON_API_KEY")
    except Exception as e:
        raise RuntimeError(f"Failed to get API key: {str(e)}")
    
    # Load input features
    df = gpd.read_postgis(
        f'SELECT * FROM workflows."{feature_collection}"',
        engine,
        geom_col="geometry"
    )
    
    # Check if input contains points
    if not all(geom.geom_type == 'Point' for geom in df.geometry):
        # Extract centroids for non-point geometries
        df['geometry'] = df['geometry'].apply(lambda geom: geom.centroid)
        print("Warning: Non-point geometries converted to centroids")
    
    # Convert radius from km to meters
    radius_meters = radius * 1000
    
    # Create empty list to store all nearby place features
    all_features = []
    
    # Process each point
    for idx, row in df.iterrows():
        point = row.geometry
        
        # Get point coordinates
        latitude = point.y
        longitude = point.x
        
        try:
            print("Fetching nearby places based on provider", provider)
            # Fetch nearby places based on provider
            if provider.lower() == "google":
                # Google Places API
                url = "https://api.leptonmaps.com/v1/google/places/nearby"
                params = {
                    "location": f"{latitude},{longitude}",
                    "radius": f"{radius_meters}",
                    "type": category
                }
                
                if subcategory:
                    params["keyword"] = subcategory
                
                response = requests.get(
                    url,
                    params=params,
                    headers={"X-API-Key": api_key},
                    timeout=30
                )
                
                if not response.ok:
                    print(f"Warning: API request failed for point {idx}: {response.text}")
                    continue
                
                result = response.json()
                
                # Parse Google Places response
                if "results" in result:
                    for place in result["results"]:
                        # Skip places without valid location
                        if not place.get("geometry") or not place.get("geometry").get("location"):
                            continue
                            
                        place_lat = place["geometry"]["location"]["lat"]
                        place_lng = place["geometry"]["location"]["lng"]
                        
                        # Skip invalid coordinates
                        if not (isinstance(place_lat, (int, float)) and isinstance(place_lng, (int, float))):
                            continue
                            
                        # Create Point geometry
                        place_geom = Point(place_lng, place_lat)
                        
                        # Create properties dict
                        place_props = {
                            "name": place.get("name", ""),
                            "address": place.get("vicinity", ""),
                            "place_id": place.get("place_id", ""),
                            "source_lat": latitude,
                            "source_lng": longitude,
                            "rating": place.get("rating", None),
                            "types": ", ".join(place.get("types", [])),
                            "provider": "google",
                            "_gid": len(all_features) + 1
                        }
                        
                        # Add to features list
                        all_features.append({
                            "geometry": place_geom,
                            **place_props
                        })
            else:
                # Lepton API
                url = "https://api.leptonmaps.com/v1/geojson/places/nearby"
                params = {
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": radius_meters,
                    "key": api_key
                }
                
                if category:
                    params["category"] = category
                    
                if subcategory:
                    params["subcategory"] = subcategory
                
                response = requests.get(url, params=params, timeout=30)
                
                if not response.ok:
                    print(f"Warning: API request failed for point {idx}: {response.text}")
                    continue
                
                result = response.json()
                
                # Parse Lepton API response
                if "features" in result:
                    for feature in result["features"]:
                        # Skip features without valid geometry
                        if not feature.get("geometry") or not feature.get("geometry").get("coordinates"):
                            continue
                            
                        coords = feature["geometry"]["coordinates"]
                        
                        # Skip invalid coordinates
                        if len(coords) < 2 or not all(isinstance(c, (int, float)) for c in coords[:2]):
                            continue
                            
                        # Create Point geometry
                        place_geom = Point(coords[0], coords[1])
                        
                        # Get properties or initialize empty dict
                        properties = feature.get("properties", {})
                        
                        # Create properties dict with source location added
                        place_props = {
                            **properties,
                            "source_lat": latitude,
                            "source_lng": longitude,
                            "provider": "lepton",
                            "_gid": len(all_features) + 1
                        }
                        
                        # Add to features list
                        all_features.append({
                            "geometry": place_geom,
                            **place_props
                        })
        except Exception as e:
            print(f"Error processing point {idx}: {str(e)}")
            continue
    
    # Check if we found any places
    if not all_features:
        print("Warning: No nearby places found for any points")
        # Create a dummy point to avoid empty dataframe issues
        dummy_geom = Point(0, 0)
        dummy_props = {
            "name": "No places found",
            "provider": provider,
            "_gid": 1,
            "error": "No nearby places found within the specified radius and categories"
        }
        all_features.append({
            "geometry": dummy_geom,
            **dummy_props
        })
    
    # Create GeoDataFrame from features
    places_gdf = gpd.GeoDataFrame(all_features, geometry="geometry", crs="EPSG:4326")
    
    # Save to database
    is_cached = node.save_df_to_postgres(places_gdf, output_table_name)
    
    return {
        "output": output_table_name,
        "is_cached": is_cached
    }

def distancebetweenpoints(**kwargs):
    """
    Calculates the distance and route between two points using either aerial distance or
    routing services (Lepton or Google).
    
    Args:
        originFeatureCollection: Input feature collection containing origin point(s)
        destinationFeatureCollection: Input feature collection containing destination point(s)
        distance_provider: Provider for distance calculation ("lepton" or "google")
        travel_mode: Travel mode for routing (driving, walking, bicycling, transit)
        aerial_distance: Whether to calculate straight-line distance instead of routing
        traffic_model: Traffic model to use (best_guess, pessimistic, optimistic)
        transit_mode: Transit mode preferences (bus, subway, train, tram, rail)
        avoid_mode: Features to avoid (tolls, highways, ferries, indoor)
        alternative_route: Whether to request alternative routes
        sourceFeatureId: Optional ID of a specific feature to use from origin collection
        destinationFeatureId: Optional ID of a specific feature to use from destination collection
    
    Returns:
        Dictionary with the output table name containing route features
    """
    from airflow.models import Variable
    import requests
    import json
    import pandas as pd
    import geopandas as gpd
    from shapely.geometry import Point, LineString
    import math
    
    node = Node(**kwargs)
    
    # Get inputs
    origin_collection = node.input("originFeatureCollection")
    destination_collection = node.input("destinationFeatureCollection")
    distance_provider = node.input("distance_provider", "lepton").lower()
    travel_mode = node.input("travel_mode", "driving").lower()
    aerial_distance = node.input("aerial_distance", False)
    traffic_model = node.input("traffic_model", "")
    transit_mode = node.input("transit_mode", "")
    avoid_mode = node.input("avoid_mode", "")
    alternative_route = node.input("alternative_route", False)
    source_feature_id = node.input("sourceFeatureId", None)
    destination_feature_id = node.input("destinationFeatureId", None)
    
    # Validate inputs
    if not origin_collection:
        raise ValueError("Origin feature collection is required")
    
    if not destination_collection:
        raise ValueError("Destination feature collection is required")
    
    if distance_provider not in ["lepton", "google"]:
        raise ValueError("Distance provider must be either 'lepton' or 'google'")
    
    if travel_mode not in ["driving", "walking", "bicycling", "transit"]:
        travel_mode = "driving"
    
    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="distancebetweenpoints",
        inputs={
            "originFeatureCollection": origin_collection,
            "destinationFeatureCollection": destination_collection,
            "distance_provider": distance_provider,
            "travel_mode": travel_mode,
            "aerial_distance": aerial_distance,
            "traffic_model": traffic_model,
            "transit_mode": transit_mode,
            "avoid_mode": avoid_mode,
            "alternative_route": alternative_route,
            "sourceFeatureId": source_feature_id,
            "destinationFeatureId": destination_feature_id
        }
    )
    
    # Check if cached results exist
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        print(f"Using cached distance results: {output_table_name}")
        return {
            "output": output_table_name,
            "is_cached": True
        }
    
    # Get API key
    try:
        api_key = Variable.get("LEPTON_API_KEY")
    except Exception as e:
        raise RuntimeError(f"Failed to get API key: {str(e)}")
    
    # Build query for origin features based on whether source_feature_id is provided
    if source_feature_id is not None:
        # Query for a specific origin feature with proper type casting
        origin_query = f'''
            SELECT * FROM workflows."{origin_collection}" 
            WHERE _gid = {source_feature_id}::bigint
        '''
    else:
        # Query for all origin features
        origin_query = f'SELECT * FROM workflows."{origin_collection}" LIMIT 1'
    
    # Build query for destination features based on whether destination_feature_id is provided
    if destination_feature_id is not None:
        # Query for a specific destination feature with proper type casting
        destination_query = f'''
            SELECT * FROM workflows."{destination_collection}" 
            WHERE _gid = {destination_feature_id}::bigint
        '''
    else:
        # Query for all destination features
        destination_query = f'SELECT * FROM workflows."{destination_collection}" LIMIT 1'
    
    # Load origin features
    origin_df = gpd.read_postgis(
        origin_query,
        engine,
        geom_col='geometry'
    )
    
    # Load destination features
    destination_df = gpd.read_postgis(
        destination_query,
        engine,
        geom_col='geometry'
    )
    
    # Check if we found any origin features
    if origin_df.empty:
        if source_feature_id is not None:
            raise ValueError(f"No origin feature found with ID {source_feature_id}")
        else:
            raise ValueError("No features found in the origin feature collection")
    
    print(destination_df, ":::::----    ")
    # Check if we found any destination features
    if destination_df.empty:
        if destination_feature_id is not None:
            raise ValueError(f"No destination feature found with ID {destination_feature_id}")
        else:
            raise ValueError("No features found in the destination feature collection")
    
    # Check if inputs contain points
    if not all(geom.geom_type == 'Point' for geom in origin_df.geometry):
        origin_df['geometry'] = origin_df['geometry'].apply(lambda geom: geom.centroid)
        print("Warning: Non-point origin geometries converted to centroids")
    
    if not all(geom.geom_type == 'Point' for geom in destination_df.geometry):
        destination_df['geometry'] = destination_df['geometry'].apply(lambda geom: geom.centroid)
        print("Warning: Non-point destination geometries converted to centroids")
    
    # Function to decode Google polyline without external dependency
    def decode_google_polyline(encoded):
        """
        Decode a Google polyline string into a list of coordinates.
        Based on the algorithm described in:
        https://developers.google.com/maps/documentation/utilities/polylinealgorithm
        """
        if not encoded:
            return []
            
        # Initialize variables
        coords = []
        index = 0
        lat = 0
        lng = 0
        
        while index < len(encoded):
            # Process latitude
            result = 1
            shift = 0
            while True:
                b = ord(encoded[index]) - 63 - 1
                index += 1
                result += b << shift
                shift += 5
                if b < 0x1f:
                    break
            lat += (~(result >> 1) if (result & 1) else (result >> 1))
            
            # Process longitude
            result = 1
            shift = 0
            while True:
                b = ord(encoded[index]) - 63 - 1
                index += 1
                result += b << shift
                shift += 5
                if b < 0x1f:
                    break
            lng += (~(result >> 1) if (result & 1) else (result >> 1))
            
            # Convert to decimal and add to coordinates array
            coords.append([lng * 1e-5, lat * 1e-5])  # Convert to lng,lat format for GeoJSON
            
            if index >= len(encoded):
                break
        
        return coords
    
    # Function to calculate haversine distance (aerial distance)
    def haversine_distance(lat1, lon1, lat2, lon2):
        """Calculate the great circle distance between two points in kilometers."""
        R = 6371  # Radius of the Earth in km
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)
        a = (math.sin(dLat/2) * math.sin(dLat/2) +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dLon/2) * math.sin(dLon/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        return distance
    
    # Create empty list to store route features
    route_features = []
    
    # Function to prefix properties with origin_ or destination_
    def prefix_properties(properties, prefix):
        """Add prefix to property names, filtering out system properties."""
        return {
            f"{prefix}{key}": value for key, value in properties.items()
            if not key.startswith('$') and not key.startswith('_') and key != 'geometry'
        }
    
    # Process a single origin-destination pair
    # Get the first origin and destination
    origin_row = origin_df.iloc[0]
    dest_row = destination_df.iloc[0]
    
    # Get coordinates
    origin_point = origin_row.geometry
    dest_point = dest_row.geometry
    
    origin_lat = origin_point.y
    origin_lng = origin_point.x
    dest_lat = dest_point.y
    dest_lng = dest_point.x
    
    # Get and prefix properties
    origin_props = prefix_properties(origin_row.to_dict(), 'origin_')
    dest_props = prefix_properties(dest_row.to_dict(), 'destination_')
    
    # Store original IDs for reference
    if '_gid' in origin_row:
        origin_props['origin_feature_id'] = origin_row['_gid']
    elif 'id' in origin_row:
        origin_props['origin_feature_id'] = origin_row['id']
    
    if '_gid' in dest_row:
        dest_props['destination_feature_id'] = dest_row['_gid']
    elif 'id' in dest_row:
        dest_props['destination_feature_id'] = dest_row['id']
    
    # If aerial distance is requested, calculate straight-line distance
    if aerial_distance:
        # Calculate aerial distance in kilometers
        distance_km = haversine_distance(origin_lat, origin_lng, dest_lat, dest_lng)
        distance_m = distance_km * 1000  # Convert to meters
        
        # Create LineString for direct path
        line_geom = LineString([(origin_lng, origin_lat), (dest_lng, dest_lat)])
        
        # Create properties
        route_props = {
            **origin_props,
            **dest_props,
            "distance_km": round(distance_km, 2),
            "distance_m": round(distance_m, 2),
            "distance_text": f"{round(distance_km, 2)} km",
            "duration_text": "N/A (aerial)",
            "route_type": "aerial",
            "provider": "direct",
            "_gid": len(route_features) + 1
        }
        
        # Add to features list
        route_features.append({
            "geometry": line_geom,
            **route_props
        })
    
    # If routing is requested
    else:
        # Prepare API request based on provider
        if distance_provider == "google":
            success = False
            # Google Directions API
            try:
                url = "https://api.leptonmaps.com/v1/google/directions"
                params = {
                    "origin": f"{origin_lat},{origin_lng}",
                    "destination": f"{dest_lat},{dest_lng}",
                    "mode": travel_mode,
                    "alternatives": "true" if alternative_route else "false",
                    "departure_time": "now"
                }
                
                # Add optional parameters if provided
                if traffic_model and travel_mode == "driving":
                    params["traffic_model"] = traffic_model
                if transit_mode and travel_mode == "transit":
                    params["transit_mode"] = transit_mode
                if avoid_mode:
                    params["avoid"] = avoid_mode
                
                response = requests.get(
                    url,
                    params=params,
                    headers={"X-API-Key": api_key},
                    timeout=30
                )
                
                if not response.ok:
                    print(f"Warning: Google Directions API request failed: {response.text}")
                else:
                    result = response.json()
                    
                    # Process routes from the response
                    if "routes" in result and result["routes"]:
                        for route_idx, route in enumerate(result["routes"]):
                            # Skip invalid routes
                            if (not route.get("overview_polyline") or 
                                not route.get("legs") or 
                                not route["legs"][0].get("distance")):
                                continue
                            
                            # Decode polyline
                            coordinates = decode_google_polyline(route["overview_polyline"]["points"])
                            
                            if not coordinates:
                                continue
                            
                            # Create LineString geometry
                            line_geom = LineString(coordinates)
                            
                            # Get route details
                            leg = route["legs"][0]
                            distance_text = leg.get("distance", {}).get("text", "Unknown")
                            distance_value = leg.get("distance", {}).get("value", 0)
                            duration_text = leg.get("duration", {}).get("text", "Unknown")
                            duration_value = leg.get("duration", {}).get("value", 0)
                            
                            # Create properties
                            route_props = {
                                **origin_props,
                                **dest_props,
                                "distance_text": distance_text,
                                "distance_m": distance_value,
                                "distance_km": round(distance_value / 1000, 2),
                                "duration_text": duration_text,
                                "duration_seconds": duration_value,
                                "start_address": leg.get("start_address", ""),
                                "end_address": leg.get("end_address", ""),
                                "route_index": route_idx,
                                "is_alternative": route_idx > 0,
                                "route_type": travel_mode,
                                "provider": "google",
                                "_gid": len(route_features) + 1
                            }
                            
                            # Add traffic info if available
                            if "duration_in_traffic" in leg:
                                route_props["duration_in_traffic_text"] = leg["duration_in_traffic"]["text"]
                                route_props["duration_in_traffic_seconds"] = leg["duration_in_traffic"]["value"]
                            
                            # Add to features list
                            route_features.append({
                                "geometry": line_geom,
                                **route_props
                            })
                        
                        success = True
                    else:
                        print(f"Warning: No routes found in Google Directions API response")
            except Exception as e:
                print(f"Error processing Google route: {str(e)}")
        
        else:
            # Lepton Directions API
            success = False
            try:
                url = "https://api.leptonmaps.com/v1/geojson/routes/main"
                params = {
                    "origin": f"{origin_lat},{origin_lng}",
                    "destination": f"{dest_lat},{dest_lng}",
                    "mode": travel_mode
                }
                response = requests.get(
                    url,
                    params=params,
                    headers={"X-API-Key": api_key},
                    timeout=30
                )
                
                if not response.ok:
                    print(f"Warning: Lepton Directions API request failed: {response.text}")
                else:
                    result = response.json()
                    
                    # Process features from the response
                    if "features" in result:
                        for feature_idx, feature in enumerate(result["features"]):
                            # Skip features without valid geometry
                            if not feature.get("geometry") or not feature.get("geometry").get("coordinates"):
                                continue
                            
                            coordinates = feature["geometry"]["coordinates"]
                            
                            if not coordinates or len(coordinates) < 2:
                                continue
                            
                            # Create LineString geometry
                            line_geom = LineString(coordinates)
                            
                            # Get properties - first try from feature, then from top-level if needed
                            properties = feature.get("properties", {})
                            
                            # Check if we have all essential properties, if not try to get them from the response
                            if "distance" not in properties and "properties" in result:
                                # Add any missing properties from the top level
                                for key, value in result["properties"].items():
                                    if key not in properties:
                                        properties[key] = value
                            
                            # Extract distance and time from properties if available
                            distance_text = properties.get("distance", "Unknown")
                            duration_text = properties.get("time", "Unknown")
                            
                            # Ensure origin and destination are captured
                            if "origin" in properties and "origin" not in origin_props:
                                origin_props["origin"] = properties["origin"]
                            if "destination" in properties and "destination" not in dest_props:
                                dest_props["destination"] = properties["destination"]
                            
                            # Create properties
                            route_props = {
                                **origin_props,
                                **dest_props,
                                "distance_text": distance_text,
                                "distance_m": 0,
                                "distance_km": 0,
                                "duration_text": duration_text,
                                "duration_seconds": 0,
                                "route_type": travel_mode,
                                "provider": "lepton",
                                "is_alternative": feature_idx > 0,
                                "route_index": feature_idx,
                                "_gid": len(route_features) + 1
                            }
                            
                            # Add to features list
                            route_features.append({
                                "geometry": line_geom,
                                **route_props
                            })
                        
                        success = True
                    else:
                        print("Warning: No features found in Lepton Directions API response")
            except Exception as e:
                print(f"Error processing Lepton route: {str(e)}")
    
    # Check if we found any routes
    if not route_features:
        print("Warning: No routes found for the origin-destination pair")
        # Create a dummy line to avoid empty dataframe issues
        dummy_geom = LineString([(0, 0), (0.1, 0.1)])
        dummy_props = {
            "error": "No routes found for the given parameters",
            "provider": distance_provider,
            "_gid": 1
        }
        route_features.append({
            "geometry": dummy_geom,
            **dummy_props
        })
    
    # Create GeoDataFrame from features
    routes_gdf = gpd.GeoDataFrame(route_features, geometry="geometry", crs="EPSG:4326")
    
    # Save to database
    is_cached = node.save_df_to_postgres(routes_gdf, output_table_name)
    
    return {
        "output": output_table_name,
        "is_cached": is_cached
    }

def isochrone(**kwargs):
    """
    Creates isochrone (travel time) polygons around point geometries.
    
    Args:
        featureCollection: Input point feature collection
        featureId: Optional ID of a specific feature to process (processes all features if not provided)
    
    Returns:
        Dictionary with the output table name containing isochrone polygon features
    """
    import geopandas as gpd
    from shapely.geometry import shape
    import requests
    import json
    from airflow.models import Variable
    
    node = Node(**kwargs)
    
    # Get inputs - only feature_collection and feature_id
    feature_collection = node.input("featureCollection")
    feature_id = node.input("featureId", None)
    
    # Hardcoded parameters
    drive_time_values = [15, 30, 45, 60]
    catchment_type = "DRIVE_TIME"
    travel_mode = "driving"
    
    # Validate inputs
    if not feature_collection:
        raise ValueError("Feature collection is required")
    
    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="isochrone",
        inputs={
            "featureCollection": feature_collection,
            "featureId": feature_id
        }
    )
    
    # Check if cached results exist
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        print(f"Using cached isochrone results: {output_table_name}")
        return {
            "output": output_table_name,
            "is_cached": True
        }
    
    # Build query based on whether feature_id is provided
    if feature_id is not None:
        # Query for a specific feature with proper type casting
        query = f'''
            SELECT * FROM workflows."{feature_collection}" 
            WHERE _gid = {feature_id}::bigint
        '''
    else:
        # Query for all features
        query = f'SELECT * FROM workflows."{feature_collection}"'
    
    # Load input features
    df = gpd.read_postgis(
        query,
        engine,
        geom_col='geometry'
    )
    
    # Check if we found any features
    if df.empty:
        if feature_id is not None:
            raise ValueError(f"No feature found with ID {feature_id}")
        else:
            raise ValueError("No features found in the feature collection")
    
    # Check if input contains points
    if not all(geom.geom_type == 'Point' for geom in df.geometry):
        # Extract centroids for non-point geometries
        df['geometry'] = df['geometry'].apply(lambda geom: geom.centroid)
        print("Warning: Non-point geometries converted to centroids")
    
    # Get API key
    try:
        api_key = Variable.get("LEPTON_API_KEY")
    except Exception as e:
        raise RuntimeError(f"Failed to get API key: {str(e)}")
    
    # Create empty list to store isochrone features
    all_features = []
    
    # Process each point feature
    for idx, row in df.iterrows():
        point = row.geometry
        properties = row.to_dict()
        
        # Get identifier from properties or use index
        if '_gid' in properties:
            identifier = properties['_gid']
        elif 'id' in properties:
            identifier = properties['id']
        else:
            identifier = idx
        
        # Get point coordinates
        latitude = point.y
        longitude = point.x
        
        # Store original properties for reference
        orig_props = {
            k: v for k, v in properties.items() 
            if k != 'geometry' and not isinstance(v, (list, dict))
        }
        
        # Fetch isochrones for each drive time
        for drive_time in drive_time_values:
            url = f"https://api.leptonmaps.com/v1/geojson/catchment"
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "catchment_type": catchment_type,
                "drive_time": drive_time
            }
            
            # Add travel mode parameter
            params["travel_mode"] = travel_mode
            
            headers = {"X-Api-Key": api_key}
            
            try:
                response = requests.get(url, params=params, headers=headers)
                response.raise_for_status()
                geojson_data = response.json()
                
                # Process features from the API response
                if "features" in geojson_data and geojson_data["features"]:
                    for feature in geojson_data["features"]:
                        # Create a Shapely geometry from the GeoJSON
                        geom = shape(feature["geometry"])
                        
                        # Ensure the geometry is valid
                        if not geom.is_valid:
                            geom = geom.buffer(0)  # Fix invalid geometries
                        
                        # Skip empty geometries
                        if geom.is_empty:
                            continue
                        
                        # Merge API response properties with original feature properties
                        isochrone_props = orig_props.copy()
                        
                        # Add properties from the API response
                        if "properties" in feature:
                            for key, value in feature["properties"].items():
                                isochrone_props[key] = value
                        
                        # Add additional properties
                        isochrone_props.update({
                            "isochrone_id": f"{identifier}_{drive_time}",
                            "drive_time": drive_time,
                            "catchment_type": catchment_type,
                            "center_lat": latitude,
                            "center_lon": longitude,
                            "travel_mode": travel_mode,
                            "_gid": len(all_features) + 1  # Ensure unique _gid for each isochrone
                        })
                        
                        # Add feature to the list
                        all_features.append({
                            "geometry": geom,
                            **isochrone_props
                        })
                else:
                    print(f"No isochrone data returned for point {identifier} with drive time {drive_time}")
                    
            except Exception as e:
                print(f"Error fetching isochrone for point {identifier} with drive time {drive_time}: {str(e)}")
                continue
    
    # Create GeoDataFrame from isochrone features
    if not all_features:
        raise ValueError("Failed to generate any valid isochrones")
    
    isochrone_gdf = gpd.GeoDataFrame(all_features, geometry="geometry", crs="EPSG:4326")
    
    # Save to database
    is_cached = node.save_df_to_postgres(isochrone_gdf, output_table_name)
    
    return {
        "output": output_table_name,
        "is_cached": is_cached
    }

def union(**kwargs):
    """
    Performs union operations on geometries and calculates attribute values
    based on the intersection area ratios.
    
    Args:
        baseLayer: The base feature collection to union with
        selectedFeatures: Feature collection containing selected objects
        unionType: Type of aggregation for attribute values (sum, average, max, min)
        
    Returns:
        Dictionary with the output table name containing union features
    """
    import geopandas as gpd
    from shapely.geometry import shape, mapping
    from shapely.ops import unary_union
    import pandas as pd
    import json
    import numpy as np
    
    # Initialize node
    node = Node(**kwargs)
    
    # Get required parameters
    base_layer = node.input("baseLayer")
    selected_features = node.input("selectedFeatures")
    union_type = node.input("unionType", "sum").lower()
    
    # Validate required parameters
    if not base_layer:
        raise ValueError("Base layer is required")
    if not selected_features:
        raise ValueError("Selected features are required")
    
    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="union",
        inputs={
            "baseLayer": base_layer,
            "selectedFeatures": selected_features,
            "unionType": union_type
        }
    )
    
    # Check if cached results exist
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        print(f"Using cached union results: {output_table_name}")
        return {
            "output": output_table_name,
            "is_cached": True
        }
    
    # Queries to retrieve all features from collections
    base_query = f'SELECT * FROM workflows."{base_layer}"'
    selected_query = f'SELECT * FROM workflows."{selected_features}"'
    
    # Load the base layer data
    base_df = gpd.read_postgis(base_query, engine, geom_col="geometry")
    
    # Load the selected features
    selected_df = gpd.read_postgis(selected_query, engine, geom_col="geometry")
    
    # Check if either collection is empty
    if base_df.empty and selected_df.empty:
        raise ValueError("Both input collections cannot be empty")
    
    # If one collection is empty, return the other
    if base_df.empty:
        is_cached = node.save_df_to_postgres(selected_df, output_table_name)
        return {
            "output": output_table_name,
            "is_cached": is_cached
        }
    elif selected_df.empty:
        is_cached = node.save_df_to_postgres(base_df, output_table_name)
        return {
            "output": output_table_name,
            "is_cached": is_cached
        }
    
    # Helper function to convert MultiPolygon to individual Polygons
    def convert_multipolygon_to_polygon(gdf):
        """Split MultiPolygon geometries into individual Polygon geometries"""
        rows = []
        for idx, row in gdf.iterrows():
            if row.geometry.geom_type == 'MultiPolygon':
                for geom in row.geometry.geoms:
                    new_row = row.copy()
                    new_row.geometry = geom
                    rows.append(new_row)
            else:
                rows.append(row)
        return gpd.GeoDataFrame(rows, crs=gdf.crs)
    
    # Helper function to compute attribute values based on selections
    def compute_attribute_values(features, property_names, calc_type='sum'):
        """Calculate attribute values based on calculation type"""
        results = {}
        
        for prop in property_names:
            values = [feat.get(prop, 0) for feat in features]
            values = [v for v in values if isinstance(v, (int, float))]
            
            if not values:
                continue
                
            if calc_type == 'sum':
                results[prop] = sum(values)
            elif calc_type == 'average':
                results[prop] = sum(values) / len(values) if values else 0
            elif calc_type == 'max':
                results[prop] = max(values) if values else 0
            elif calc_type == 'min':
                results[prop] = min(values) if values else 0
        
        return results
    
    try:
        print("Performing union of all features")
        
        # Convert MultiPolygons to Polygons if needed
        base_polygons = convert_multipolygon_to_polygon(base_df)
        selected_polygons = convert_multipolygon_to_polygon(selected_df)
        
        # Combine all geometries from both sources
        all_geometries = list(base_polygons.geometry) + list(selected_polygons.geometry)
        
        # Perform unary union of all geometries
        union_geom = unary_union(all_geometries)
        
        # Gather all property columns from both DataFrames (excluding geometry and system columns)
        property_names = []
        for col in set(base_df.columns).union(set(selected_df.columns)):
            if col != 'geometry' and not col.startswith('_'):
                property_names.append(col)
        
        # Calculate attribute values based on all features
        base_features = [row.to_dict() for _, row in base_df.iterrows()]
        selected_features = [row.to_dict() for _, row in selected_df.iterrows()]
        all_features = base_features + selected_features
        
        # Compute attributes
        attr_values = compute_attribute_values(
            all_features,
            property_names,
            union_type
        )
        
        # Create result feature with combined properties
        if not union_geom.is_empty:
            # Create result DataFrame with the union geometry and calculated attributes
            result_feature = {
                "geometry": union_geom,
                "_gid": 1
            }
            result_feature.update(attr_values)
            
            # Create GeoDataFrame with the single union feature
            results_df = gpd.GeoDataFrame([result_feature], geometry="geometry", crs="EPSG:4326")
        else:
            # Handle empty result case
            from shapely.geometry import Point
            dummy_df = gpd.GeoDataFrame(
                [{"message": "Union result is empty", "_gid": 1}],
                geometry=[Point(0, 0)],
                crs="EPSG:4326"
            )
            results_df = dummy_df
        
        # Save to database
        is_cached = node.save_df_to_postgres(results_df, output_table_name)
        
        return {
            "output": output_table_name,
            "is_cached": is_cached
        }
        
    except Exception as e:
        raise RuntimeError(f"Error processing union operation: {str(e)}")

def routeplanner(**kwargs):
    """
    Plans a route using Google Maps API and returns both route and point data.
    
    Args:
        origin: Starting point (coordinates array [lon, lat] or address string)
        destination: End point (coordinates array [lon, lat] or address string)
        waypoints: Intermediate waypoints (array of objects with location property)
        round_trip: Whether the route should return to origin
        optimize_route: Whether to optimize the order of waypoints
        route_modifiers: Dictionary with boolean flags for avoiding tolls, highways, ferries
        travel_mode: Travel mode (DRIVE, WALK, etc.)
        
    Returns:
        Dictionary with output table names for route and points
    """
    import json
    import requests
    import pandas as pd
    import geopandas as gpd
    from shapely.geometry import Point, LineString
    from datetime import datetime, timedelta
    from airflow.models import Variable
    
    # Initialize node
    node = Node(**kwargs)
    
    # Helper function to decode Google's polyline format
    def decode_polyline(encoded):
        """
        Decodes Google's encoded polyline format.
        
        Args:
            encoded: String in Google's polyline format
            
        Returns:
            Array of [longitude, latitude] coordinates
        """
        points = []
        index = 0
        length = len(encoded)
        lat = 0
        lng = 0

        while index < length:
            result = 1
            shift = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result += (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break

            dlat = ~(result >> 1) if (result & 1) else (result >> 1)
            lat += dlat

            result = 1
            shift = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result += (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break

            dlng = ~(result >> 1) if (result & 1) else (result >> 1)
            lng += dlng

            # Convert to [longitude, latitude] format
            points.append([lng * 1e-5, lat * 1e-5])

        return points
    
    # Get required parameters
    origin_param = node.input("origin")
    destination_param = node.input("destination")
    waypoints_param = node.input("waypoints", [])
    round_trip = node.input("round_trip", False)
    optimize_route = node.input("optimize_route", True)
    route_modifiers = node.input("route_modifiers", {})
    travel_mode = node.input("travel_mode", "DRIVE")
    
    # Convert boolean string values
    if isinstance(round_trip, str):
        round_trip = round_trip.lower() == 'true'
    if isinstance(optimize_route, str):
        optimize_route = optimize_route.lower() == 'true'
    
    # Extract route modifiers with defaults
    avoid_tolls = False
    avoid_highways = False
    avoid_ferries = False
    
    if route_modifiers:
        if isinstance(route_modifiers, str):
            try:
                route_modifiers = json.loads(route_modifiers)
            except:
                # If it's a string that can't be parsed as JSON, use default values
                route_modifiers = {}
                
        avoid_tolls = route_modifiers.get("avoid_tolls", False)
        avoid_highways = route_modifiers.get("avoid_highways", False)
        avoid_ferries = route_modifiers.get("avoid_ferries", False)
    
    # Parse string values for route modifiers
    if isinstance(avoid_tolls, str):
        avoid_tolls = avoid_tolls.lower() == 'true'
    if isinstance(avoid_highways, str):
        avoid_highways = avoid_highways.lower() == 'true'
    if isinstance(avoid_ferries, str):
        avoid_ferries = avoid_ferries.lower() == 'true'
    
    # Validate required parameters
    if not origin_param:
        raise ValueError("Origin is required")
    if not destination_param and not round_trip:
        raise ValueError("Destination is required unless round_trip is true")
    
    # Create output table names
    route_table_name = node.create_output_table_name(
        func_name="route_planner_routes",
        inputs={
            "origin": str(origin_param),
            "destination": str(destination_param) if destination_param else None,
            "waypoints_count": len(waypoints_param),
            "round_trip": round_trip,
            "optimize_route": optimize_route,
            "avoid_tolls": avoid_tolls,
            "avoid_highways": avoid_highways,
            "avoid_ferries": avoid_ferries
        }
    )
    
    point_table_name = node.create_output_table_name(
        func_name="route_planner_points",
        inputs={
            "origin": str(origin_param),
            "destination": str(destination_param) if destination_param else None,
            "waypoints_count": len(waypoints_param),
            "round_trip": round_trip
        }
    )
    
    # Check if cached results exist
    engine = get_db_engine_lepton()
    if table_exists(engine, route_table_name) and table_exists(engine, point_table_name):
        print(f"Using cached route planning results: {route_table_name} and {point_table_name}")
        return {
            "route": route_table_name,
            "points": point_table_name,
            "is_cached": True
        }
    
    # Format origin for API exactly like the client side does
    origin = {}
    if isinstance(origin_param, list):
        # Handle array format [lng, lat]
        origin = {
            "location": {
                "latLng": {
                    "latitude": origin_param[1],
                    "longitude": origin_param[0]
                }
            }
        }
    elif isinstance(origin_param, str):
        # Try to detect if it's a coordinate string like "lat,lng"
        import re
        coord_match = re.match(r'^(\d+\.\d+),(\d+\.\d+)$', origin_param.strip())
        if coord_match:
            # It's a coordinate string, parse it
            lat, lng = map(float, coord_match.groups())
            origin = {
                "location": {
                    "latLng": {
                        "latitude": lat,
                        "longitude": lng
                    }
                }
            }
        else:
            # It's a regular address
            origin = {
                "address": origin_param
            }
    else:
        origin = {
            "address": str(origin_param)
        }

    # Format destination for API exactly like the client side does
    destination = {}
    if isinstance(destination_param, list):
        # Handle array format [lng, lat]
        destination = {
            "location": {
                "latLng": {
                    "latitude": destination_param[1],
                    "longitude": destination_param[0]
                }
            }
        }
    elif isinstance(destination_param, str):
        # Try to detect if it's a coordinate string like "lat,lng"
        import re
        coord_match = re.match(r'^(\d+\.\d+),(\d+\.\d+)$', destination_param.strip())
        if coord_match:
            # It's a coordinate string, parse it
            lat, lng = map(float, coord_match.groups())
            destination = {
                "location": {
                    "latLng": {
                        "latitude": lat,
                        "longitude": lng
                    }
                }
            }
        else:
            # It's a regular address
            destination = {
                "address": destination_param
            }
    else:
        destination = {
            "address": str(destination_param)
        }
    
    # Format waypoints for API exactly like the client side does
    intermediates = []
    import re  # Import regex here for all coordinate parsing

    for waypoint in waypoints_param:
        if not waypoint:
            continue
        
        # Check if waypoint has a location property
        if hasattr(waypoint, 'get') and waypoint.get("location") is not None:
            waypoint_location = waypoint.get("location")
            
            # Format based on whether location is coordinates or address
            if isinstance(waypoint_location, list):
                # Handle array format [lng, lat]
                intermediates.append({
                    "location": {
                        "latLng": {
                            "latitude": waypoint_location[1],
                            "longitude": waypoint_location[0]
                        }
                    }
                })
            elif isinstance(waypoint_location, str):
                # Try to detect if it's a coordinate string like "lat,lng"
                coord_match = re.match(r'^(\d+\.\d+),(\d+\.\d+)$', waypoint_location.strip())
                if coord_match:
                    # It's a coordinate string, parse it
                    lat, lng = map(float, coord_match.groups())
                    intermediates.append({
                        "location": {
                            "latLng": {
                                "latitude": lat,
                                "longitude": lng
                            }
                        }
                    })
                else:
                    # It's a regular address
                    intermediates.append({
                        "address": waypoint_location
                    })
            else:
                intermediates.append({
                    "address": str(waypoint_location)
                })
        else:
            # Handle direct waypoint format (not wrapped in location property)
            if isinstance(waypoint, list):
                # Handle array format [lng, lat]
                intermediates.append({
                    "location": {
                        "latLng": {
                            "latitude": waypoint[1],
                            "longitude": waypoint[0]
                        }
                    }
                })
            elif isinstance(waypoint, str):
                # Try to detect if it's a coordinate string like "lat,lng"
                coord_match = re.match(r'^(\d+\.\d+),(\d+\.\d+)$', waypoint.strip())
                if coord_match:
                    # It's a coordinate string, parse it
                    lat, lng = map(float, coord_match.groups())
                    intermediates.append({
                        "location": {
                            "latLng": {
                                "latitude": lat,
                                "longitude": lng
                            }
                        }
                    })
                else:
                    # It's a regular address
                    intermediates.append({
                        "address": waypoint
                    })
            else:
                intermediates.append({
                    "address": str(waypoint)
                })
    
    # Calculate departure time (5 minutes from now)
    departure_time = datetime.now() + timedelta(minutes=5)
    # Format as ISO 8601 with UTC timezone indicator (Z)
    departure_time_iso = departure_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    # Build request body for Google Maps API - match client format exactly
    request_body = {
        "origin": origin,
        "destination": origin if round_trip else destination,
        "intermediates": intermediates,
        "travelMode": travel_mode,
        "routingPreference": "TRAFFIC_AWARE",
        "departureTime": departure_time_iso,
        "computeAlternativeRoutes": False,
        "routeModifiers": {
            "avoidTolls": avoid_tolls,
            "avoidHighways": avoid_highways,
            "avoidFerries": avoid_ferries
        },
        "languageCode": "en-US",
        "units": "IMPERIAL"
    }
    
    print("request_body: -----", request_body)
    
    try:
        # Get Google Maps API key from Airflow variables
        api_key = Variable.get("GOOGLE_MAPS_API_KEY", "AIzaSyB9hPt6CJudym8BiGFwkRzF-uyFwK2yKY4")
        
        # Optimize route if requested and there are enough waypoints
        optimized_intermediates = intermediates
        
        if optimize_route and len(intermediates) > 2:
            # Make API request to get optimized order
            optimize_response = requests.post(
                "https://routes.googleapis.com/directions/v2:computeRoutes",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": api_key,
                    "X-Goog-FieldMask": "routes.optimizedIntermediateWaypointIndex"
                },
                json={
                    **request_body,
                    "optimizeWaypointOrder": "true"
                },
                timeout=60  # 1 minute timeout
            )
            
            if not optimize_response.ok:
                raise RuntimeError(f"Failed to optimize route: {optimize_response.text}")
            
            optimize_result = optimize_response.json()
            
            if not optimize_result.get("routes") or not isinstance(optimize_result["routes"], list):
                raise ValueError("Invalid optimize response: missing routes")
            
            # Reorder intermediates based on optimized indices
            optimized_indices = optimize_result["routes"][0]["optimizedIntermediateWaypointIndex"]
            optimized_intermediates = [intermediates[i] for i in optimized_indices]
        
        # Make API request for final route
        route_response = requests.post(
            "https://routes.googleapis.com/directions/v2:computeRoutes",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.legs"
            },
            json={
                **request_body,
                "intermediates": optimized_intermediates
            },
            timeout=60  # 1 minute timeout
        )
        
        if not route_response.ok:
            raise RuntimeError(f"Failed to get route: {route_response.text}")
        
        route_data = route_response.json()
        print("route_data: -----", route_data)
        # Process route data into GeoJSON features
        route_features = []
        point_coordinates = {}  # Use a dict to track unique coordinates
        
        for route in route_data.get("routes", []):
            for leg_index, leg in enumerate(route.get("legs", [])):
                # Extract polyline and decode
                polyline = leg.get("polyline", {}).get("encodedPolyline", "")
                coordinates = decode_polyline(polyline)
                
                if len(coordinates) > 1:
                    # Get duration value, which could be a string or dict
                    duration_value = leg.get("duration", 0)
                    if isinstance(duration_value, dict):
                        # Handle dictionary case (extract seconds)
                        duration_seconds = duration_value.get("seconds", 0)
                    elif isinstance(duration_value, str):
                        # Handle string case (try to extract number from string like "1128s")
                        import re
                        duration_match = re.match(r'^(\d+)s$', duration_value)
                        duration_seconds = int(duration_match.group(1)) if duration_match else 0
                    else:
                        # Fallback
                        duration_seconds = 0
                    
                    # Create line feature for the route leg
                    route_features.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": coordinates
                        },
                        "properties": {
                            "leg_index": leg_index,
                            "distance_meters": leg.get("distanceMeters", 0),
                            "duration_seconds": duration_seconds,
                            "name": f"Route {leg_index + 1}"
                        }
                    })
                
                # Extract start and end points
                start_location = leg.get("startLocation", {}).get("latLng", {})
                end_location = leg.get("endLocation", {}).get("latLng", {})
                
                if start_location and "latitude" in start_location and "longitude" in start_location:
                    coord_key = f"{start_location['longitude']},{start_location['latitude']}"
                    point_coordinates[coord_key] = [
                        start_location["longitude"],
                        start_location["latitude"]
                    ]
                
                if end_location and "latitude" in end_location and "longitude" in end_location:
                    coord_key = f"{end_location['longitude']},{end_location['latitude']}"
                    point_coordinates[coord_key] = [
                        end_location["longitude"],
                        end_location["latitude"]
                    ]
        
        # Check if we have any route features
        if not route_features:
            raise ValueError("No route could be generated with the provided inputs")
            
        # Create GeoJSON feature collections
        route_geojson = {
            "type": "FeatureCollection",
            "features": route_features
        }
        
        # Create point features from unique coordinates
        point_features = []
        for idx, (key, coords) in enumerate(point_coordinates.items()):
            # Determine the address property
            address = ""
            if idx == 0:
                address = origin.get("address", "")
            elif idx == len(point_coordinates) - 1 and not round_trip:
                address = destination.get("address", "")
            elif idx - 1 < len(optimized_intermediates):
                address = optimized_intermediates[idx - 1].get("address", "")
            
            point_features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": coords
                },
                "properties": {
                    "name": f"Point {idx + 1}",
                    "coordinates": json.dumps(coords),
                    "address": address
                }
            })
        
        point_geojson = {
            "type": "FeatureCollection",
            "features": point_features
        }
        
        # Convert GeoJSON to GeoDataFrames
        try:
            # Explicitly use from_features to handle GeoJSON properly
            route_df = gpd.GeoDataFrame.from_features(route_features, crs="EPSG:4326")
            point_df = gpd.GeoDataFrame.from_features(point_features, crs="EPSG:4326")
            
            # Verify that the geometry column exists
            if 'geometry' not in route_df.columns and hasattr(route_df, 'geometry'):
                # GeoDataFrame.from_features creates geometry as an attribute, not column
                print("Route geometry is an attribute, not a column (this is normal)")
            
            if 'geometry' not in point_df.columns and hasattr(point_df, 'geometry'):
                print("Point geometry is an attribute, not a column (this is normal)")
                
            # Save to database
            is_cached_route = node.save_df_to_postgres(route_df, route_table_name)
            is_cached_point = node.save_df_to_postgres(point_df, point_table_name)
            
            # Return the table names
            return {
                "route": route_table_name,
                "points": point_table_name,
                "is_cached": is_cached_route and is_cached_point
            }
        except Exception as gdf_error:
            # If there's an error creating the GeoDataFrame, try alternative approach
            print(f"Error creating GeoDataFrame: {str(gdf_error)}")
            
            # Create route DataFrame directly using shapely objects
            route_rows = []
            from shapely.geometry import LineString
            
            for feat in route_features:
                geom = LineString(feat["geometry"]["coordinates"])
                props = feat["properties"].copy()
                props["geometry"] = geom
                route_rows.append(props)
                
            route_df = gpd.GeoDataFrame(route_rows, geometry="geometry", crs="EPSG:4326")
            
            # Create point DataFrame directly using shapely objects
            point_rows = []
            from shapely.geometry import Point
            
            for feat in point_features:
                coords = feat["geometry"]["coordinates"]
                geom = Point(coords[0], coords[1])
                props = feat["properties"].copy()
                props["geometry"] = geom
                point_rows.append(props)
                
            point_df = gpd.GeoDataFrame(point_rows, geometry="geometry", crs="EPSG:4326")
            
            # Save to database
            is_cached_route = node.save_df_to_postgres(route_df, route_table_name)
            is_cached_point = node.save_df_to_postgres(point_df, point_table_name)
            
            # Return the table names
            return {
                "route": route_table_name,
                "points": point_table_name,
                "is_cached": is_cached_route and is_cached_point
            }
        
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"API request failed: {str(e)}")
    except ValueError as e:
        raise ValueError(f"Invalid input or parameter: {str(e)}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse API response as JSON: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error in route planning: {str(e)}")

def contains(**kwargs):
    """
    Filters features to include only those contained within a specified geometry.
    
    Args:
        featureCollection: Input feature collection to filter
        containingGeometry: Geometry or feature to check containment against
        
    Returns:
        Dictionary with the output table name containing filtered features
    """
    import geopandas as gpd
    from shapely.geometry import shape, Point
    import pandas as pd
    
    # Initialize node
    node = Node(**kwargs)
    
    # Get required parameters
    feature_collection = node.input("featureCollection")
    # Support both parameter names for backward compatibility
    containing_geometry = node.input("containedLayer", None) or node.input("containingGeometry", None)
    
    # Validate required parameters
    if not feature_collection:
        raise ValueError("Feature collection is required")
    if not containing_geometry:
        raise ValueError("Containing geometry is required")
    
    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="contains",
        inputs={
            "featureCollection": feature_collection,
            "containingGeometry": containing_geometry
        }
    )
    
    # Check if cached results exist
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        print(f"Using cached containment results: {output_table_name}")
        return {
            "output": output_table_name,
            "is_cached": True
        }
    
    # Load the input feature collection
    input_query = f'SELECT * FROM workflows."{feature_collection}"'
    input_df = gpd.read_postgis(input_query, engine, geom_col="geometry")
    print(f"input_df: ----- {input_df}")
    
    # Load the containing geometry/feature
    containing_query = f'SELECT * FROM workflows."{containing_geometry}"'
    containing_df = gpd.read_postgis(containing_query, engine, geom_col="geometry")
    
    if containing_df.empty:
        raise ValueError(f"Containing geometry table '{containing_geometry}' is empty")
    
    # Get the first geometry from the containing table
    # If there are multiple geometries, we just use the first one
    containing_geom = containing_df.geometry.iloc[0]
    print(f"containing_geom: ----- {containing_geom}")
    
    # Filter input features to only include those contained within the containing geometry
    # Using within() from shapely for this spatial relationship check
    contained_df = input_df[input_df.geometry.within(containing_geom)]
    
    # If no features are contained, create a dummy GeoDataFrame with a single point
    if contained_df.empty:
        print("No features were found within the containing geometry")
        # Still need to maintain the same schema as the input
        contained_df = input_df.iloc[0:0].copy()
    
    # Save the results to database
    is_cached = node.save_df_to_postgres(contained_df, output_table_name)
    
    # Return the output table name
    return {
        "output": output_table_name,
        "is_cached": is_cached
    }

def trafficinsights(**kwargs):
    """
    Sends input geometries to Lepton API's traffic insights endpoint and returns traffic data
    
    Args:
        featureCollection: Input feature collection containing geometries to analyze
        
    Returns:
        Dictionary with the output table name containing traffic data
    """
    from airflow.models import Variable
    import requests
    import json
    import pandas as pd
    import geopandas as gpd
    from shapely.geometry import shape
    
    # Initialize node
    node = Node(**kwargs)
    
    # Get required parameters
    feature_collection = node.input("featureCollection")
    
    # Validate required parameters
    if not feature_collection:
        raise ValueError("Feature collection is required")
    
    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="trafficinsights",
        inputs={
            "featureCollection": feature_collection
        }
    )
    
    # Check if cached results exist
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        print(f"Using cached traffic insights results: {output_table_name}")
        return {
            "output": output_table_name,
            "is_cached": True
        }
    
    # Load the input feature collection
    input_query = f'SELECT jsonb_build_object(\'type\', \'FeatureCollection\', \'features\', jsonb_agg(jsonb_build_object(\'type\', \'Feature\', \'geometry\', ST_AsGeoJSON(geometry)::jsonb, \'properties\', jsonb_build_object(\'id\', _gid)))) as geojson FROM workflows."{feature_collection}"'
    
    with engine.connect() as connection:
        result = connection.execute(input_query).fetchone()
        input_geojson = result[0]
    
    # Prepare API request payload
    post_data = {
        "input_geometry": input_geojson
    }
    
    # Get Lepton API key
    try:
        api_key = Variable.get("LEPTON_API_KEY")
    except Exception as e:
        raise RuntimeError(f"Failed to get API key: {str(e)}")
    
    # Make the API request
    try:
        print("Sending request to Lepton API traffic insights endpoint...")
        response = requests.post(
            "https://api.leptonmaps.com/v1/geojson/routes/traffic",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key
            },
            json=post_data,
            timeout=300  # 5-minute timeout for potentially long operations
        )
        
        # Check for errors
        if not response.ok:
            raise RuntimeError(f"API request failed with status {response.status_code}: {response.text}")
        
        # Parse the response
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            traffic_data = response.json()
        else:
            raise ValueError(f"Unexpected response format: {response.text[:500]}...")
        
        print("Successfully received traffic insights data")
        
        # Process the response into a GeoDataFrame
        if not traffic_data or not isinstance(traffic_data, dict):
            raise ValueError("Invalid response format: Expected GeoJSON object")
        
        # Convert GeoJSON to GeoDataFrame
        try:
            features = traffic_data.get("features", [])
            if not features:
                # Create a dummy GeoDataFrame with a message if no features are returned
                from shapely.geometry import Point
                dummy_df = gpd.GeoDataFrame(
                    [{"message": "No traffic data available for provided geometries", "_gid": 1}],
                    geometry=[Point(0, 0)],
                    crs="EPSG:4326"
                )
                results_df = dummy_df
            else:
                # Create a list to hold the processed features
                processed_features = []
                
                for feature in features:
                    # Extract properties and geometry
                    properties = feature.get("properties", {})
                    geometry = shape(feature.get("geometry", {}))
                    
                    # Combine into a single dictionary
                    feature_dict = {**properties, "geometry": geometry}
                    processed_features.append(feature_dict)
                
                # Create GeoDataFrame from features
                results_df = gpd.GeoDataFrame(processed_features, geometry="geometry", crs="EPSG:4326")
                
                # Ensure _gid column exists
                if "_gid" not in results_df.columns:
                    results_df["_gid"] = range(1, len(results_df) + 1)
            
            # Save to database
            is_cached = node.save_df_to_postgres(results_df, output_table_name)
            
            return {
                "output": output_table_name,
                "is_cached": is_cached
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to process traffic insights response: {str(e)}")
        
    except requests.RequestException as e:
        raise RuntimeError(f"API request failed: {str(e)}")
    except ValueError as e:
        raise ValueError(f"Invalid input or response format: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error in traffic insights processing: {str(e)}")

def landuse(**kwargs):
    """
    Retrieves land use data for geographic features by making API requests to a land use service.
    The function normalizes geometry inputs and enriches features with land use percentage data.
    
    Args:
        featureCollection: Input feature collection containing geometries to analyze
        
    Returns:
        Dictionary with the output table name containing features enriched with land use data
    """
    from airflow.models import Variable
    import requests
    import json
    import pandas as pd
    import geopandas as gpd
    from shapely.geometry import shape, mapping
    import os
    from datetime import datetime
    
    # Initialize node
    node = Node(**kwargs)
    
    # Get required parameters
    feature_collection = node.input("featureCollection")
    identifier_property = "_gid"
    
    # Validate required parameters
    if not feature_collection:
        raise ValueError("Feature collection is required")
    
    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="landuse",
        inputs={
            "featureCollection": feature_collection,
            "identifierProperty": identifier_property
        }
    )
    
    # Check if cached results exist
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        print(f"Using cached land use results: {output_table_name}")
        return {
            "output": output_table_name,
            "is_cached": True
        }
    
    # Load the input feature collection
    input_query = f'SELECT * FROM workflows."{feature_collection}"'
    features_df = gpd.read_postgis(input_query, engine, geom_col="geometry")
    
    if features_df.empty:
        raise ValueError("Feature collection cannot be empty")
    
    # Process features to normalize geometries
    processed_features = []
    
    for idx, row in features_df.iterrows():
        feature_id = row[identifier_property] if identifier_property in row else row["_gid"]
        geom = row.geometry
        
        # Create a normalized GeoJSON feature
        if geom.geom_type == "Polygon":
            geometry = {"type": "Polygon", "coordinates": [list(geom.exterior.coords)]}
        elif geom.geom_type == "MultiPolygon":
            # Convert MultiPolygon to Polygon if it has only one polygon
            if len(geom.geoms) == 1:
                geometry = {"type": "Polygon", "coordinates": [list(geom.geoms[0].exterior.coords)]}
            else:
                geometry = mapping(geom)
        else:
            geometry = mapping(geom)
        
        processed_features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "id": feature_id
            }
        })
    
    # Prepare request payload
    request_body = {"features": processed_features}
    
    # Get API key from Airflow variables
    try:
        api_key = Variable.get("LEPTON_API_KEY")
    except Exception as e:
        raise RuntimeError(f"Failed to get API key: {str(e)}")
    
    # Land use API URL - corrected endpoint
    land_use_api_url = "https://api.leptonmaps.com/v1/geojson/get_landuse"
    
    # Make the API request
    try:
        print("Sending request to Land Use API...")
        print(f"Request contains {len(processed_features)} features")
        
        # Use session for better connection handling
        session = requests.Session()
        
        # Set a longer timeout (10 minutes)
        response = session.post(
            land_use_api_url,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key
            },
            json=request_body,
            timeout=600  # 10-minute timeout for potentially long operations
        )
        
        # Check for errors
        if not response.ok:
            error_msg = f"API request failed with status {response.status_code}"
            try:
                error_details = response.text
                error_msg += f": {error_details}"
            except:
                pass
            
            raise RuntimeError(error_msg)
        
        # Parse the response
        try:
            land_use_data = response.json()
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse API response as JSON: {str(e)}. Response content: {response.text[:500]}...")
        
        if not isinstance(land_use_data, list):
            if isinstance(land_use_data, dict) and "error" in land_use_data:
                raise ValueError(f"API returned error: {land_use_data['error']}")
            raise ValueError(f"Unexpected response format: {response.text[:500]}...")
        
        if len(land_use_data) == 0:
            print("Warning: API returned empty list. Features will not have land use data.")
        else:
            print(f"Successfully received land use data for {len(land_use_data)} features")
        
        # Get all possible land use keys
        all_land_use_keys = set()
        for item in land_use_data:
            if item and isinstance(item, dict) and item.get("land_use"):
                all_land_use_keys.update(item["land_use"].keys())
        
        # Process the features with land use data
        enriched_features = []
        
        for _, feature in features_df.iterrows():
            feature_id = feature[identifier_property] if identifier_property in feature else feature["_gid"]
            
            # Find corresponding land use data
            api_data_item = next((item for item in land_use_data if str(item.get("id", "")) == str(feature_id)), None)
            
            # Create a new properties dictionary
            new_properties = {}
            
            # Copy original properties
            for key, value in feature.items():
                if key != "geometry":
                    new_properties[key] = value
            
            # Add land use properties if available
            if api_data_item and api_data_item.get("land_use"):
                land_use = api_data_item["land_use"]
                
                # Normalize land use keys
                for key in all_land_use_keys:
                    new_key = (key.replace("percentage_of_", "").replace("_", " ") + " %")
                    new_properties[new_key] = land_use.get(key, 0)
            
            # Add to enriched features
            enriched_features.append({
                **new_properties,
                "geometry": feature.geometry
            })
        
        # Convert back to GeoDataFrame
        results_df = gpd.GeoDataFrame(enriched_features, geometry="geometry", crs="EPSG:4326")
        
        # Ensure _gid column exists
        if "_gid" not in results_df.columns:
            results_df["_gid"] = range(1, len(results_df) + 1)
        
        # Save to database
        is_cached = node.save_df_to_postgres(results_df, output_table_name)
        
        return {
            "output": output_table_name,
            "is_cached": is_cached
        }
        
    except requests.RequestException as e:
        raise RuntimeError(f"API request failed: {str(e)}")
    except ValueError as e:
        raise ValueError(f"Invalid input or response format: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error in land use processing: {str(e)}")

def fuelingstations(**kwargs):
    """
    Retrieves fueling stations along a route between origin and destination coordinates.
    Route data is always included in the response.
    
    Args:
        origin: Starting point coordinates [lat, lng] or comma-separated string "lat,lng"
        destination: End point coordinates [lat, lng] or comma-separated string "lat,lng"
        fuelType: Type of fuel (e.g., "Petrol", "Diesel", "CNG", "Electric")
        
    Returns:
        Dictionary with output table names for stations and route data
    """
    from airflow.models import Variable
    import requests
    import json
    import pandas as pd
    import geopandas as gpd
    from shapely.geometry import Point, LineString
    
    # Initialize node
    node = Node(**kwargs)
    
    # Get required parameters
    origin = node.input("origin")
    destination = node.input("destination")
    fuel_type = node.input("fuelType", "Petrol")
    
    # Validate required parameters
    if not origin:
        raise ValueError("Origin coordinates are required")
    if not destination:
        raise ValueError("Destination coordinates are required")
    
    # Store original values for API call
    origin_param = origin
    destination_param = destination
    
    # Format origin and destination as comma-separated strings if they're arrays
    if isinstance(origin_param, list) and len(origin_param) == 2:
        origin_param = f"{origin_param[0]},{origin_param[1]}"
    if isinstance(destination_param, list) and len(destination_param) == 2:
        destination_param = f"{destination_param[0]},{destination_param[1]}"
    
    # Create output table names
    stations_table_name = node.create_output_table_name(
        func_name="fuelingStations",
        inputs={
            "origin": origin,
            "destination": destination,
            "fuelType": fuel_type
        }
    )
    
    route_table_name = f"{stations_table_name}_route"
    
    # Check if cached results exist
    engine = get_db_engine_lepton()
    stations_cached = table_exists(engine, stations_table_name)
    route_cached = table_exists(engine, route_table_name)
    
    if stations_cached and route_cached:
        print(f"Using cached fueling stations results: {stations_table_name}")
        return {
            "stations": stations_table_name,
            "route": route_table_name,
            "is_cached": True
        }
    
    # Get API key from Airflow variables
    try:
        api_key = Variable.get("LEPTON_API_KEY")
    except Exception as e:
        raise RuntimeError(f"Failed to get API key: {str(e)}")
    
    # Build API request URL
    fueling_stations_api_url = "https://api.leptonmaps.com/v1/route/fueling_stations"
    
    # Build query parameters with the formatted coordinate strings
    params = {
        "origin": origin_param,
        "destination": destination_param,
        "type": fuel_type,
        "include_route": "true"  # Always include route
    }
    
    # Make the API request
    try:
        print(f"Requesting fueling stations along route from {origin_param} to {destination_param} for {fuel_type} fuel type")
        print(f"Request parameters: {params}")
        
        # Use session for better connection handling
        session = requests.Session()
        
        # Set a reasonable timeout
        response = session.get(
            fueling_stations_api_url,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key
            },
            params=params,
            timeout=300  # 5-minute timeout
        )
        
        # Check for errors
        if not response.ok:
            error_msg = f"API request failed with status {response.status_code}"
            try:
                error_details = response.text
                error_msg += f": {error_details}"
            except:
                pass
            
            raise RuntimeError(error_msg)
        
        # Parse the response
        try:
            api_data = response.json()
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse API response as JSON: {str(e)}. Response content: {response.text[:500]}...")
        
        # Validate response structure
        if not isinstance(api_data, dict):
            raise ValueError(f"Unexpected response format: Expected dictionary, got {type(api_data).__name__}")
        
        # Process stations data
        stations_data = api_data.get("stations", [])
        if not stations_data:
            print("Warning: No fueling stations found along the route")
            
        # Create GeoDataFrame for stations
        stations_records = []
        for idx, station in enumerate(stations_data):
            station_record = {
                "_gid": idx + 1,
                "geometry": Point(station.get("longitude", 0), station.get("latitude", 0))
            }
            
            # Add all station properties
            for key, value in station.items():
                if key not in ["latitude", "longitude"]:
                    station_record[key] = value
            
            stations_records.append(station_record)
        
        # Create stations GeoDataFrame
        if stations_records:
            stations_df = gpd.GeoDataFrame(stations_records, geometry="geometry", crs="EPSG:4326")
        else:
            # Create empty GeoDataFrame with proper schema if no stations
            stations_df = gpd.GeoDataFrame(
                columns=["_gid", "RO_name", "brand", "side", "City", "District", "distance", "geometry"],
                geometry="geometry",
                crs="EPSG:4326"
            )
        
        # Save stations to database
        is_cached = node.save_df_to_postgres(stations_df, stations_table_name)
        
        # Process route data
        route_coords = api_data.get("route", [])
        if not route_coords:
            raise ValueError("Route data is missing from the API response")
            
        # Create LineString from route coordinates
        route_line = LineString(route_coords)
        
        # Create route GeoDataFrame
        route_df = gpd.GeoDataFrame(
            [{"_gid": 1, "geometry": route_line}],
            geometry="geometry",
            crs="EPSG:4326"
        )
        
        # Save route to database
        route_cached = node.save_df_to_postgres(route_df, route_table_name)
        
        return {
            "stations": stations_table_name,
            "route": route_table_name,
            "is_cached": is_cached
        }
        
    except requests.RequestException as e:
        raise RuntimeError(f"API request failed: {str(e)}")
    except ValueError as e:
        raise ValueError(f"Invalid input or response format: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error in fueling stations processing: {str(e)}")

def routepois(**kwargs):
    """
    Retrieves points of interest (POIs) along a route between origin and destination coordinates.
    Returns both the route and the POIs as separate tables.
    
    Args:
        origin: Starting point coordinates [lat, lng] or comma-separated string "lat,lng"
        destination: End point coordinates [lat, lng] or comma-separated string "lat,lng"
        category: Category of POIs to search for along the route
        
    Returns:
        Dictionary with output table names for POIs and route data
    """
    from airflow.models import Variable
    import requests
    import json
    import pandas as pd
    import geopandas as gpd
    from shapely.geometry import Point, LineString
    
    # Initialize node
    node = Node(**kwargs)
    
    # Get required parameters
    origin = node.input("origin")
    destination = node.input("destination")
    category = node.input("category", "")  # Default to empty string if not provided
    
    # Validate required parameters
    if not origin:
        raise ValueError("Origin coordinates are required")
    if not destination:
        raise ValueError("Destination coordinates are required")
    
    # Store original values for API call
    origin_param = origin
    destination_param = destination
    
    # Format origin and destination as comma-separated strings if they're arrays
    if isinstance(origin_param, list) and len(origin_param) == 2:
        origin_param = f"{origin_param[0]},{origin_param[1]}"
    if isinstance(destination_param, list) and len(destination_param) == 2:
        destination_param = f"{destination_param[0]},{destination_param[1]}"
    
    # Create output table names
    pois_table_name = node.create_output_table_name(
        func_name="routePOIs",
        inputs={
            "origin": origin,
            "destination": destination,
            "category": category
        }
    )
    
    route_table_name = f"{pois_table_name}_route"
    
    # Check if cached results exist
    engine = get_db_engine_lepton()
    pois_cached = table_exists(engine, pois_table_name)
    route_cached = table_exists(engine, route_table_name)
    
    if pois_cached and route_cached:
        print(f"Using cached route POIs results: {pois_table_name}")
        return {
            "pois": pois_table_name,
            "route": route_table_name,
            "is_cached": True
        }
    
    # Get API key from Airflow variables
    try:
        api_key = Variable.get("LEPTON_API_KEY")
    except Exception as e:
        raise RuntimeError(f"Failed to get API key: {str(e)}")
    
    # Build API request URL
    route_pois_api_url = "https://api.leptonmaps.com/v1/route/pois"
    
    # Build query parameters with the formatted coordinate strings
    params = {
        "origin": origin_param,
        "destination": destination_param,
        "subcategory": category,
        "include_route": "true"  # Always include route
    }
    print("params----", params)
    # Make the API request
    try:
        print(f"Requesting POIs along route from {origin_param} to {destination_param} for category: {category}")
        print(f"Request parameters: {params}")
        
        # Use session for better connection handling
        session = requests.Session()
        
        # Set a reasonable timeout
        response = session.get(
            route_pois_api_url,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key
            },
            params=params,
            timeout=300  # 5-minute timeout
        )
        
        # Check for errors
        if not response.ok:
            error_msg = f"API request failed with status {response.status_code}"
            try:
                error_details = response.text
                error_msg += f": {error_details}"
            except:
                pass
            
            raise RuntimeError(error_msg)
        
        # Parse the response
        try:
            api_data = response.json()
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse API response as JSON: {str(e)}. Response content: {response.text[:500]}...")
        
        # Validate response structure
        if not isinstance(api_data, dict):
            raise ValueError(f"Unexpected response format: Expected dictionary, got {type(api_data).__name__}")
        
        # Extract route data
        route_coords = api_data.get("route", [])
        if not route_coords:
            raise ValueError("Route data is missing from the API response")
        
        # Create LineString from route coordinates
        route_line = LineString(route_coords)
        
        # Create route GeoDataFrame with additional properties
        route_properties = {}
        for key, value in api_data.items():
            if key != "route" and not isinstance(value, list):
                route_properties[key] = value
        
        route_record = {
            "_gid": 1,
            "geometry": route_line,
            "name": "Route",
            **route_properties
        }
        
        route_df = gpd.GeoDataFrame([route_record], geometry="geometry", crs="EPSG:4326")
        
        # Save route to database
        route_cached = node.save_df_to_postgres(route_df, route_table_name)
        
        # Process POIs
        pois_records = []
        
        # Determine POI category from first key that is not 'route'
        poi_category = None
        for key in api_data.keys():
            if key != "route" and isinstance(api_data[key], list):
                poi_category = key
                break
        
        if not poi_category or not api_data.get(poi_category):
            print("Warning: No POIs found along the route")
            
            # Create empty POIs GeoDataFrame with proper schema
            pois_df = gpd.GeoDataFrame(
                columns=["_gid", "name", "type", "distance", "geometry"],
                geometry="geometry",
                crs="EPSG:4326"
            )
        else:
            # Create start point (first point in route)
            start_point = {
                "_gid": 1,
                "geometry": Point(route_coords[0]),
                "name": "Start",
                "type": "Origin"
            }
            pois_records.append(start_point)
            
            # Create end point (last point in route)
            end_point = {
                "_gid": 2,
                "geometry": Point(route_coords[-1]),
                "name": "End",
                "type": "Destination"
            }
            pois_records.append(end_point)
            
            # Process POIs from API response
            for idx, poi in enumerate(api_data[poi_category]):
                lat = poi.get("latitude", 0)
                lng = poi.get("longitude", 0)
                
                # Skip POIs without valid coordinates
                if not lat or not lng:
                    continue
                
                poi_record = {
                    "_gid": idx + 3,  # Start at 3 (after start and end points)
                    "geometry": Point(lng, lat),
                    "type": "Poi along the route"
                }
                
                # Add all POI properties
                for key, value in poi.items():
                    if key not in ["latitude", "longitude"]:
                        poi_record[key] = value
                        
                pois_records.append(poi_record)
            
            # Create POIs GeoDataFrame
            pois_df = gpd.GeoDataFrame(pois_records, geometry="geometry", crs="EPSG:4326")
        
        # Save POIs to database
        pois_cached = node.save_df_to_postgres(pois_df, pois_table_name)
        
        return {
            "pois": pois_table_name,
            "route": route_table_name,
            "is_cached": pois_cached and route_cached
        }
        
    except requests.RequestException as e:
        raise RuntimeError(f"API request failed: {str(e)}")
    except ValueError as e:
        raise ValueError(f"Invalid input or response format: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error in route POIs processing: {str(e)}")

def cannibalization(**kwargs):
    """
    Calculates intersection areas between features in a feature collection and computes
    property values for intersections based on area ratios.
    
    Args:
        featureCollection: Input feature collection containing features to analyze
        identifierProperty: Property name to be preserved and not averaged (default: "_gid")
        
    Returns:
        Dictionary with the output table name containing the intersections
    """
    import geopandas as gpd
    from shapely.geometry import shape, mapping
    import pandas as pd
    import json
    import numpy as np
    from shapely.ops import unary_union
    
    # Initialize node
    node = Node(**kwargs)
    
    # Get required parameters
    feature_collection = node.input("featureCollection")
    identifier_property = node.input("identifierProperty", "_gid")
    
    # Validate required parameters
    if not feature_collection:
        raise ValueError("Feature collection is required")
    
    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="cannibalization",
        inputs={
            "featureCollection": feature_collection,
            "identifierProperty": identifier_property
        }
    )
    
    # Check if cached results exist
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        print(f"Using cached cannibalization results: {output_table_name}")
        return {
            "output": output_table_name,
            "is_cached": True
        }
    
    # Load the input feature collection
    query = f'SELECT * FROM workflows."{feature_collection}"'
    gdf = gpd.read_postgis(query, engine, geom_col="geometry")
    
    if gdf.empty:
        raise ValueError("Feature collection cannot be empty")
    
    # List to store intersection features
    intersection_features = []
    
    # Calculate intersections between all pairs of features
    for i in range(len(gdf)):
        current_feature = gdf.iloc[i]
        current_geom = current_feature.geometry
        current_area = current_geom.area
        
        # Skip invalid geometries
        if not current_geom.is_valid or current_area <= 0:
            continue
            
        for j in range(i + 1, len(gdf)):
            next_feature = gdf.iloc[j]
            next_geom = next_feature.geometry
            next_area = next_geom.area
            
            # Skip invalid geometries
            if not next_geom.is_valid or next_area <= 0:
                continue
            
            # Calculate intersection
            intersection = current_geom.intersection(next_geom)
            
            # If there is an intersection
            if not intersection.is_empty and intersection.area > 0:
                # Calculate area metrics
                intersection_area = intersection.area
                current_feature_area_ratio = intersection_area / current_area
                next_feature_area_ratio = intersection_area / next_area
                
                # Create properties for the intersection
                properties = {}
                
                # Copy original properties and calculate new values based on area ratio
                for key in gdf.columns:
                    if key == 'geometry':
                        continue
                    
                    current_value = current_feature[key]
                    next_value = next_feature[key]
                    
                    # Handle identifier property differently
                    if key == identifier_property:
                        properties[key] = current_value
                        continue
                    
                    # Handle numeric properties - weighted average by area ratio
                    if pd.api.types.is_numeric_dtype(gdf[key]):
                        try:
                            weighted_value = (current_value * current_feature_area_ratio + 
                                             next_value * next_feature_area_ratio) / 2
                            properties[key] = weighted_value
                        except (TypeError, ValueError):
                            # If calculation fails, just use the current value
                            properties[key] = current_value
                    # Handle string properties - concatenate with slash
                    elif isinstance(current_value, str) and isinstance(next_value, str):
                        properties[key] = f"{current_value}/{next_value}"
                    else:
                        # For other types, just use the current value
                        properties[key] = current_value
                
                # Add intersection area in square kilometers
                properties["intersectedArea"] = f"{intersection_area / 1000000} km²"
                properties["_gid"] = len(intersection_features) + 1  # Ensure each feature has unique _gid
                
                # Create the intersection feature
                intersection_feature = {
                    "geometry": intersection,
                    **properties
                }
                
                intersection_features.append(intersection_feature)
    
    # Check if we found any intersections
    if not intersection_features:
        print("No intersections found between features")
        # Create a dummy dataframe with empty geometry to represent no intersections
        from shapely.geometry import Polygon
        dummy_df = gpd.GeoDataFrame(
            [{"_gid": 1, "message": "No intersections found", "geometry": Polygon()}],
            geometry="geometry",
            crs="EPSG:4326"
        )
        is_cached = node.save_df_to_postgres(dummy_df, output_table_name)
        return {
            "output": output_table_name,
            "is_cached": is_cached
        }
    
    # Create GeoDataFrame from intersection features
    intersections_df = gpd.GeoDataFrame(intersection_features, geometry="geometry", crs=gdf.crs)
    
    # Save to database
    is_cached = node.save_df_to_postgres(intersections_df, output_table_name)
    
    return {
        "output": output_table_name,
        "is_cached": is_cached
    }

def hull(**kwargs):
    """
    Calculates a hull (convex or concave) around features in a feature collection.
    
    Args:
        featureCollection: Input feature collection containing features
        hullType: Type of hull to generate ('convex' or 'concave')
        
    Returns:
        Dictionary with the output table name containing the hull polygon
    """
    import geopandas as gpd
    from shapely.geometry import shape, mapping, Point, Polygon, MultiPolygon, LineString
    import pandas as pd
    import json
    import numpy as np
    from shapely.ops import unary_union
    
    # Initialize node
    node = Node(**kwargs)
    
    # Get required parameters
    feature_collection = node.input("featureCollection")
    hull_type = node.input("hullType", "convex").lower()  # Default to convex hull
    
    # Validate hull type
    if hull_type not in ['convex', 'concave']:
        raise ValueError("Hull type must be either 'convex' or 'concave'")
    
    # Validate required parameters
    if not feature_collection:
        raise ValueError("Feature collection is required")
    
    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="hull",
        inputs={
            "featureCollection": feature_collection,
            "hullType": hull_type
        }
    )
    
    # Check if cached results exist
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        print(f"Using cached hull results: {output_table_name}")
        return {
            "output": output_table_name,
            "is_cached": True
        }
    
    # Load the input feature collection
    features_query = f'SELECT * FROM workflows."{feature_collection}"'
    features_df = gpd.read_postgis(features_query, engine, geom_col="geometry")
    
    if features_df.empty:
        raise ValueError("Feature collection cannot be empty")
    
    # Use all features from the feature collection
    points_gdf = features_df
    
    # Get points from geometries
    points = []
    for idx, row in points_gdf.iterrows():
        geom = row.geometry
        
        # Handle different geometry types
        if geom.geom_type == 'Point':
            points.append((geom.x, geom.y))
        elif geom.geom_type == 'MultiPoint':
            for point in geom.geoms:
                points.append((point.x, point.y))
        elif geom.geom_type in ['LineString', 'MultiLineString', 'Polygon', 'MultiPolygon']:
            # Extract points from more complex geometries
            if hasattr(geom, 'geoms'):
                # Handle multi-geometries
                for subgeom in geom.geoms:
                    if hasattr(subgeom, 'exterior'):
                        for point in subgeom.exterior.coords:
                            points.append((point[0], point[1]))
                    else:
                        for point in subgeom.coords:
                            points.append((point[0], point[1]))
            else:
                # Handle single geometries
                if hasattr(geom, 'exterior'):
                    for point in geom.exterior.coords:
                        points.append((point[0], point[1]))
                else:
                    for point in geom.coords:
                        points.append((point[0], point[1]))
    
    # Get unique points
    unique_points = list(set(points))
    num_points = len(unique_points)
    print(f"Found {num_points} unique points")
    
    # Create appropriate geometry based on number of points
    hull_geom = None
    
    if num_points == 0:
        # No points case (shouldn't happen due to empty check above)
        print("Warning: No points found in feature collection")
        hull_geom = Polygon()
    
    elif num_points == 1:
        # Single point case
        print("Creating buffer around single point")
        # Create a circular buffer around the point
        pt = Point(unique_points[0])
        buffer_size = 0.01  # Adjust based on your data's scale
        hull_geom = pt.buffer(buffer_size)
    
    elif num_points == 2:
        # Two points case
        print("Creating buffer around line between two points")
        # Create a buffer around the line between the two points
        line = LineString(unique_points)
        buffer_size = 0.01  # Adjust based on your data's scale
        hull_geom = line.buffer(buffer_size)
    
    else:
        # Three or more points case - calculate actual hull
        try:
            print(f"Calculating {hull_type} hull with {num_points} points")
            
            # Create a GeoSeries of Points
            points_polygon = gpd.GeoSeries([Point(xy) for xy in unique_points])
            
            # Create the hull using unary_union and convex_hull
            hull_geom = unary_union(points_polygon.buffer(0.0001)).convex_hull
            
            if hull_type == 'concave' and num_points > 3:
                # For concave hulls, we'll make a simplified approximation by creating
                # a buffer around the points and then extracting the exterior
                # This isn't a true concave hull but provides a more fitting shape than convex hull
                # Buffer size affects how "tight" the hull fits around the points
                buffer_size = 0.01  # Adjust based on your data's scale
                buffered = unary_union([Point(xy).buffer(buffer_size) for xy in unique_points])
                
                # If the buffer results in a MultiPolygon, use the largest polygon
                if isinstance(buffered, MultiPolygon):
                    buffered = max(buffered.geoms, key=lambda a: a.area)
                
                # Use the buffered geometry as the hull
                hull_geom = buffered
        except Exception as e:
            print(f"Hull calculation failed: {str(e)}")
            # Fall back to basic convex hull
            points_polygon = gpd.GeoSeries([Point(xy) for xy in unique_points])
            hull_geom = unary_union(points_polygon).convex_hull
    
    # Create output GeoDataFrame
    hull_properties = {
        "_gid": 1,
        "name": f"{hull_type.capitalize()} Hull"
    }
    
    # Handle case where hull_geom might be empty or None
    if hull_geom is None or hull_geom.is_empty:
        print("Warning: Hull calculation resulted in an empty geometry")
        # Create a dummy polygon
        hull_geom = Polygon()
    
    # Create GeoDataFrame
    hull_df = gpd.GeoDataFrame([{**hull_properties, "geometry": hull_geom}], 
                               geometry="geometry", 
                               crs=points_gdf.crs)
    
    # Save to database
    is_cached = node.save_df_to_postgres(hull_df, output_table_name)
    
    return {
        "output": output_table_name,
        "is_cached": is_cached
    }
