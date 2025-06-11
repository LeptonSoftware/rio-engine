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
import base64
import jwt
from sqlalchemy import text
import base64
import jwt


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
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            """
        elif "latitude" in columns:
            query = f"""
                SELECT {select_columns} latitude, ST_X(geometry) as longitude
                FROM workflows."{feature_collection_key}"
                WHERE latitude IS NOT NULL AND geometry IS NOT NULL
            """
        elif "longitude" in columns:
            query = f"""
                SELECT {select_columns} ST_Y(geometry) as latitude, longitude
                FROM workflows."{feature_collection_key}"
                WHERE longitude IS NOT NULL AND geometry IS NOT NULL
            """
        else:
            query = f"""
                SELECT {select_columns} 
                    ST_X(ST_Centroid(geometry)) as longitude, 
                    ST_Y(ST_Centroid(geometry)) as latitude
                FROM workflows."{feature_collection_key}"
                WHERE geometry IS NOT NULL
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
            # Get API key using the user-based method
            api_key = node.get_api_key_from_user()
            print("API key for geocode: ", api_key)
            
            response = requests.post(
                "https://api.leptonmaps.com/v1/detect/locality",
                json=post_data,
                headers={"X-API-Key": api_key},
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
    from lib.node import track_cache
    node = Node(**kwargs)
    db = get_db_engine_lepton()
    alias = node.input("alias")
    input_table = node.input("input")

    # if alias is already a table, leave it as is
    if table_exists(db, alias):
        return {"output": alias, "is_cached": False}
    
    # Use a connection context manager to ensure proper cleanup
    with db.connect() as connection:
        # Drop existing view if it exists
        connection.execute(f'DROP VIEW IF EXISTS workflows."{alias}"')
        # Create new view
        connection.execute(f'CREATE VIEW workflows."{alias}" AS SELECT * FROM workflows."{input_table}"')
        # Track the cache entry for the view
        track_cache(connection, alias)

    return {"output": alias, "is_cached": False}

def buffer(**kwargs):
    node = Node(**kwargs)
    input_table = node.input("featureCollection")
    output_table_name, is_cached = node.compute_in_db(
        func_name="buffer",
        inputs={
            "distance": node.input("distance"),
            "featureCollection": input_table,
        },
        query=f'''
            SELECT 
                CASE 
                    WHEN "{input_table}".geometry IS NULL THEN NULL
                    ELSE ST_Buffer("{input_table}".geometry::geography, {node.input("distance", 100)})
                END AS geometry
            FROM workflows."{input_table}"
            WHERE "{input_table}".geometry IS NOT NULL
        ''',
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
    
    print("features_list: ", features_list)
    # Create GeoDataFrame
    df = gpd.GeoDataFrame(features_list, geometry='geometry', crs="EPSG:4326")
    # df = gpd.GeoDataFrame(geojson_data, geometry='geometry', crs="EPSG:4326")
    if "_gid" not in df.columns:
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
    with engine.connect() as connection:
        # Execute and fetch all results within the context
        result = connection.execute(query, (table_name,)).fetchall()
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

    engine = get_db_engine_lepton()
    output_table_name = node.create_output_table_name(
        func_name="catchment",
        inputs={
            "points": input_table_name,
            "catchmentType": catchment_type,
            "accuracy": accuracy_level,
            "date": analysis_datetime,
            "slider": drive_time_dist,
        },
    )
    if table_exists(engine, output_table_name):
        print("using value from cache")
        return {"output": output_table_name, "is_cached": True}
    print(catchment_type)
    if "buffer" in catchment_type.lower():
        output_table_name, is_cached = node.compute_in_db(
            func_name="buffer",
            inputs={
                "distance": drive_time_dist * 1000,
                "featureCollection": input_table_name,
            },
            query=f'SELECT ST_Buffer("{input_table_name}".geometry::geography, {node.input("distance")}) AS geometry FROM workflows."{input_table_name}"',
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
        # Get API key using new method that supports user_id and org_id
        api_key = node.get_api_key_from_user()
        print("api_key: ", api_key)
        params = {k: v for k, v in all_params.items() if v is not None}
        print("paramas: ", params)
        url = base_url + "?" + urlencode(params)
        print(url, params)
        response = requests.get(
            url,
            headers={"x-api-key": api_key},
        )

        if response.ok:
            data = response.json()
            features = data.get("features", [])
            if features:
                geometry = features[0].get("geometry")
                if geometry is None:
                    # Create an empty geometry using shapely
                    from shapely.geometry import Polygon
                    return Polygon([])  # Empty polygon instead of None
                return shape(geometry)
            return None
        return None

    df = gpd.read_postgis(
        f'SELECT * FROM workflows."{input_table_name}"', engine, geom_col="geometry"
    )
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
    is_cached = node.save_df_to_postgres(df, output_table_name)

    return {"output": output_table_name, "is_cached": is_cached}


def createsmartmarketlayer(**kwargs):
    from airflow.models import Variable
    import base64
    import jwt
    import time
    from sqlalchemy import text
    import base64
    import jwt

    node = Node(**kwargs)
    project_id = node.input("project_id")
    style = node.input("style", {})
    workflow_id = node.input("workflow_id", "")
    replace_existing = node.input("replaceExisting", False)

    if(workflow_id == ""):
        workflow_id = kwargs.get("workflow_id")
    # Get user_id and org_id from the node parameters
    user_id = node.params("user_id")
    org_id = node.params("org_id")

    if not user_id or not org_id:
        raise RuntimeError("User ID and Organization ID are required")

    # Initialize engine for lock management
    engine = get_db_engine_workflows()
    
    # Generate unique lock identifiers
    unique_lock_id = f"project_{project_id}_{int(time.time() * 1000)}"
    unique_locker_id = f"createsmartmarketlayer_{user_id}"

    def acquire_lock():
        try:
            with engine.begin() as connection:
                print(f"Attempting to acquire lock for project_id: {project_id}")
                
                # Check for existing locks
                query = text("""
                    SELECT COUNT(*) 
                    FROM process_locks 
                    WHERE project_id = :project_id
                    """)
                
                result = connection.execute(
                    query,
                    {"project_id": project_id}
                ).scalar()

                if result > 0:
                    print(f"Lock acquisition failed - {result} existing locks found")
                    return False

                # Create new lock
                insert_query = text("""
                    INSERT INTO process_locks (lock_id, locked_by, project_id, workflow_id)
                    VALUES (:lock_id, :locked_by, :project_id, :workflow_id)
                    """)
                
                connection.execute(
                    insert_query,
                    {
                        "lock_id": unique_lock_id,
                        "locked_by": unique_locker_id,
                        "project_id": project_id,
                        "workflow_id": workflow_id
                    }
                )
                # Transaction will be committed automatically when the with block exits
                print(f"Lock successfully acquired with lock_id: {unique_lock_id}")
                return True
                
        except Exception as e:
            print(f"Error acquiring lock: {str(e)}")
            return False

    def release_lock():
        try:
            with engine.begin() as connection:
                connection.execute(
                    text("""
                    DELETE FROM process_locks 
                    WHERE lock_id = :lock_id AND locked_by = :locked_by
                    """),
                    {
                        "lock_id": unique_lock_id,
                        "locked_by": unique_locker_id
                    }
                )
                # Transaction will be committed automatically when the with block exits
                print("Lock released")
        except Exception as e:
            print(f"Error releasing lock: {e}")

    # Wait for lock with timeout
    max_attempts = 300
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

        print(f"feature_collection_key: {feature_collection_key}")
        # Initialize Supabase client
        supabase = create_client(
            Variable.get("SUPABASE_URL"), 
            Variable.get("SUPABASE_KEY")
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

        # Initialize layer groups if not present
        if "layerGroups" not in project_data:
            project_data["layerGroups"] = {}

        # Add flows layer group if it doesn't exist
        if "flows" not in project_data["layerGroups"]:
            project_data["layerGroups"]["flows"] = {
                "id": "flows",
                "name": "Flows",
                "open": True,
                "defaultOpen": True,
                "order": -1
            }

        # Handle layer ID and name
        base_layer_id = layer_name
        layer_id = base_layer_id
        if layer_id in project_data["layers"]:
            if replace_existing:
                # Keep the same layer_id, it will be overwritten
                pass
            else:
                # Find next available suffix
                suffix = 1
                while f"{layer_id}_{suffix}" in project_data["layers"]:
                    suffix += 1
                layer_id = f"{layer_id}_{suffix}"
                layer_name = f"{layer_name} ({suffix})"

        # Create layer source and new layer
        layer_source = {
            "type": "geojson_postgrest",
            "db": {
                "url": Variable.get("SMART_FLOWS_DB_URL"),
                "key": "",
                "table": f"{feature_collection_key}",
                "select": "*",
                "schema": "workflows",
            },
            "workflow_id": workflow_id,
        }

        print(f"layer_source: {layer_source}")

        # Parse style to check for featureType property
        feature_type = "geojson"  # Default value
        if style and isinstance(style, dict) and "featureType" in style:
            feature_type = style["featureType"]

        new_layer = {
            "id": layer_id,
            "name": layer_name,
            "source": json.dumps(layer_source, separators=(',', ':')),
            "style": json.dumps(style, separators=(',', ':')),
            "featureType": feature_type,
            "layerGroupId": "flows",
            "geometryType": "polygon",
            "visible": True,
        }

        # Add layer to project data
        project_data["layers"][layer_id] = new_layer

        # Create JWT token
        jwt_secret = Variable.get("JWT_SECRET")
        jwt_claims = {
            "sub": user_id,
            "app_metadata": {
                "organizations": {
                    org_id: {
                        "id": org_id,
                        "role": "owner"
                    }
                }
            },
            "exp": int(time.time()) + 3600
        }
        access_token = jwt.encode(jwt_claims, jwt_secret, algorithm="HS256")

        # Convert project data to base64
        encoded_data = base64.b64encode(
            json.dumps(project_data, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        ).decode('utf-8')

        # Make request to project update API
        response = requests.post(
            f"{Variable.get('SMART_FLOWS_API_URL')}/project/{project_id}/update",
            json={
                "encoded_data": encoded_data,
                "workflow_id": workflow_id,
                "is_node_update": True
            },
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            timeout=300
        )

        if not response.ok:
            raise RuntimeError(f"Failed to update project: {response.text}")

        return {"result": layer_id}

    except Exception as e:
        raise RuntimeError(f"Failed to create smart market layer: {str(e)}")
    finally:
        # Always release the lock
        release_lock()


def bbox(**kwargs):
    print("Creating bounding box")
    node = Node(**kwargs)
    input_table = node.input("input")
    
    # First, create a table with a single row containing the bounding box for all geometries
    query = f'''
        WITH bbox AS (
            -- Get the bounding box of all geometries combined
            SELECT 
                ST_Envelope(ST_Extent(geometry)) AS bbox_geometry
            FROM workflows."{input_table}"
            WHERE geometry IS NOT NULL
        ),
        -- Get first row from input to preserve attributes (excluding geometry)
        first_feature AS (
            SELECT 
                {', '.join([f'"{col}"' for col in get_column_names(get_db_engine_lepton(), input_table) if col != 'geometry'])}
            FROM workflows."{input_table}" 
            LIMIT 1
        )
        -- Combine them
        SELECT 
            f.*, -- All columns from first feature (except geometry)
            b.bbox_geometry AS geometry -- Use the bounding box as the geometry
        FROM first_feature f
        CROSS JOIN bbox b
    '''
    
    output_table_name, is_cached = node.compute_in_db(
        func_name="bbox",
        inputs={"input": input_table},
        query=query,
        geom_col=["geometry"],
        input_table_name=input_table,
        replace_query_columns=False
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
                CASE 
                    WHEN a.geometry IS NULL OR b.geometry IS NULL THEN NULL
                    ELSE ST_Intersection(a.geometry, b.geometry)
                END AS geometry
            FROM workflows."{input_table_name_a}" a
            JOIN workflows."{input_table_name_b}" b
                ON ST_Intersects(a.geometry, b.geometry)
            WHERE a.geometry IS NOT NULL AND b.geometry IS NOT NULL
            """
    else:
        input_table_name = input_table_name_b
        columns = get_column_names(engine, input_table_name_b)
        columns = [col for col in columns if col != 'geometry']
        select_cols = ', '.join([f'b."{col}"' for col in columns])
        query = f"""
            SELECT 
                {select_cols},
                CASE 
                    WHEN a.geometry IS NULL OR b.geometry IS NULL THEN NULL
                    ELSE ST_Intersection(a.geometry, b.geometry)
                END AS geometry
            FROM workflows."{input_table_name_a}" a
            JOIN workflows."{input_table_name_b}" b
                ON ST_Intersects(a.geometry, b.geometry)
            WHERE a.geometry IS NOT NULL AND b.geometry IS NOT NULL
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
        query=f'''
            SELECT 
                CASE 
                    WHEN "{input_table}".geometry IS NULL THEN NULL
                    ELSE ST_Centroid("{input_table}".geometry)
                END AS geometry
            FROM workflows."{input_table}"
            WHERE geometry IS NOT NULL
        ''',
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

    print(f"Grid type: {grid_type}")
    
    # Create output table name
    output_table_name = node.create_output_table_name(
        func_name="generategrid",
        inputs={
            "featureCollection": feature_collection,
            "grid_type": grid_type,
            "cell_size": cell_size,
            "avoid_boundaries": avoid_boundaries,
            "h3Resolution": node.input("h3Resolution", 10) if grid_type == "h3" else None,
            "geohashPrecision": node.input("geohashPrecision", 8) if grid_type == "geohash" else None,
        },
    )

    # Check if cached result exists
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        return {"output": output_table_name, "is_cached": True}

    try:
        # Read input geometries
        df = gpd.read_postgis(
            f'SELECT * FROM workflows."{feature_collection}"',
            engine,
            geom_col='geometry'
        )
        
        # Dissolve all geometries into one
        dissolved_geom = df.unary_union
        
        # Apply buffer if avoiding boundaries
        # if avoid_boundaries:
        #     buffer_size = -cell_size * 0.5  # 500m buffer for each km
        #     dissolved_geom = dissolved_geom.buffer(buffer_size/111.0)

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
            with engine.connect() as connection:
                # Execute and fetch result within the context
                column_type = connection.execute(
                    'SELECT data_type FROM information_schema.columns WHERE table_name = %s AND column_name = %s',
                    (feature_collection, attribute)
                ).scalar()
                
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

    # Get API key using the user-based method
    api_key = node.get_api_key_from_user()

    # Call Lepton API
    try:
        response = requests.post(
            "https://api.leptonmaps.com/v1/geojson/residential/demographics/get_demo",
            headers={
                "X-API-Key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if not response.ok:
            raise RuntimeError(
                f"API request failed with status {response.status_code}: {response.text}"
            )

        data = response.json()

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

    # Get API key using the user-based method
    api_key = node.get_api_key_from_user()

    # Call Lepton API
    try:
        response = requests.post(
            "https://api.leptonmaps.com/v1/geojson/places/place_insights",
            headers={
                "X-API-Key": api_key,
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
    states = [state.get("value") for state in states_input] if states_input else []
    districts = [district.get("value") for district in districts_input] if districts_input else []

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
        # Get API key using the user-based method
        api_key = node.get_api_key_from_user()
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
            WHEN b.geometry IS NULL THEN 0
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
        CASE 
            WHEN b.geometry IS NULL THEN NULL
            ELSE ST_Difference(
                b.geometry, 
                COALESCE(ST_Union(s.geometry::geometry), ST_GeomFromText('POLYGON EMPTY', 4326))
            )
        END AS geometry
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
        WHERE b.geometry IS NOT NULL
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
    node = Node(**kwargs)
    base_layer = node.input("baseLayer")
    dissolve_columns = node.input("dissolveColumns", [])  # Optional: columns to dissolve by
    aggregations = node.input("aggregations", [])  # Optional: list of aggregation objects
    is_touched = node.input("isTouched", False)  # Optional: dissolve touching polygons
    
    # Get API key using the user-based method
    api_key = node.get_api_key_from_user()

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
    
    # Drop rows with null geometries
    if df['geometry'].isna().any():
        print(f"Warning: Dropping {df['geometry'].isna().sum()} rows with null geometries")
        df = df.dropna(subset=['geometry'])
        
    if len(df) == 0:
        raise ValueError("No valid geometries found in the input layer after removing null values")
    
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
        "X-API-Key": node.get_api_key_from_user()
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
    country = node.input("country", "places_insights___in")

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
            "includeReviewRatings": include_review_ratings,
            "country": country
        }
    )

    # Check if cached result exists
    engine = get_db_engine_lepton()
    if table_exists(engine, output_table_name):
        return {"output": output_table_name, "is_cached": True}

    # Get API key using the user-based method
    api_key = node.get_api_key_from_user()
    if not api_key:
        raise ValueError("No API key available. Please check your authentication.")

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
                "geoId": str(idx),
            },
            "geometry": geom.__geo_interface__
        }
        features.append(feature)

    # Prepare API request payload
    payload = {
        "subcategories": selected_categories,
        "aggregate_by": aggregate_by,
        "include_review_ratings": str(include_review_ratings).lower(),
        "country": country,
        "input_geometry": [{
            "type": "FeatureCollection",
            "features": features
        }],
        **filter_params,
        "table_name": country
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
    is_drive_distance = node.input("isDriveDistance", False)

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
            "unit": unit,
            "isDriveDistance": is_drive_distance
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
            "layerId": "_gid",
            "is_drive_distance": is_drive_distance
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
            "attrs_layer2": attributes,
            "is_drive_distance": is_drive_distance
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
    
    # Get API key using the user-based method
    api_key = node.get_api_key_from_user()
    
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
            headers={"X-API-Key": api_key}
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
