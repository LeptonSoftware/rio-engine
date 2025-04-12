# import requestss
# import geopandas as db
# import httpx
# import polyline
import hashlib
import json
from typing import List, Optional, Annotated, Literal, Any
import geopandas as gpd
from sqlalchemy import text
import pandas as pd

def get_db_engine_lepton():
    # import from lib.db and call that
    from lib.db import get_db_engine_lepton as fn
    return fn()

# import concurrent.futures
# from shapely.geometry import Point, LineString
# import googlemaps
# import math
# from geopy.distance import geodesic
# import geojson
# from math import radians, cos, sin
# import numpy as np
# import asyncio
# import os
# import aiohttp
# from datetime import timedelta, datetime
# import shapely
from shapely import from_wkb, Polygon as ShapelyPolygon
# from pydantic import BaseModel


def table_exists(engine, table_name):
    # First check if the table exists in the cache tracking table
    cache_valid = engine.execute("""
        SELECT is_valid 
        FROM workflows.cache_entries 
        WHERE table_name = %s
        AND is_valid = true
    """, (table_name,)).scalar()
    
    if cache_valid:
        # Check if the actual table exists
        table_exists = engine.execute(
            f"SELECT to_regclass('workflows.\"{table_name}\"')"
        ).fetchone()
        if table_exists[0]:
            # Check and update geometry column SRID if needed
            with engine.begin() as connection:
                if check_tile_json(table_name, connection):
                    connection.execute(
                        f'ALTER TABLE workflows."{table_name}" ALTER COLUMN geometry TYPE geometry(geometry, 4326) USING ST_SetSRID(geometry::geometry, 4326);'
                    )
            print(f"Using cached table workflows.{table_name}")
            return True
    return False

def invalidate_cache(engine, table_name):
    """Invalidate cache for a specific table"""
    engine.execute("""
        UPDATE workflows.cache_entries 
        SET is_valid = false, 
            invalidated_at = NOW() 
        WHERE table_name = %s
    """, (table_name,))

def track_cache(connection, table_name):
    """Add or update cache tracking entry"""
    connection.execute("""
        INSERT INTO workflows.cache_entries 
            (table_name, created_at, is_valid) 
        VALUES 
            (%s, NOW(), true)
        ON CONFLICT (table_name) 
        DO UPDATE SET 
            is_valid = true,
            created_at = NOW(),
            invalidated_at = NULL
    """, (table_name,))

def get_column_names(engine, table_name):
    query = f"SELECT column_name FROM information_schema.columns WHERE table_schema = 'workflows' AND table_name = '{table_name}'"
    result = engine.execute(query)
    return [row[0] for row in result]

def check_tile_json(table_name, connection):
    query = f"""SELECT
		Format('%s.%s', n.nspname, c.relname) AS id,
		n.nspname AS schema,
		c.relname AS table,
		coalesce(d.description, '') AS description,
		a.attname AS geometry_column,
		postgis_typmod_srid(a.atttypmod) AS srid,
		rtrim(postgis_typmod_type(a.atttypmod), 'ZM') AS geometry_type,
		coalesce(case when it.typname is not null then ia.attname else null end, '') AS id_column,
		(
			SELECT array_agg(ARRAY[sa.attname, st.typname, coalesce(da.description,''), sa.attnum::text]::text[] ORDER BY sa.attnum)
			FROM pg_attribute sa
			JOIN pg_type st ON sa.atttypid = st.oid
			LEFT JOIN pg_description da ON (c.oid = da.objoid and sa.attnum = da.objsubid)
			WHERE sa.attrelid = c.oid
			AND sa.attnum > 0
			AND NOT sa.attisdropped
			AND st.typname NOT IN ('geometry', 'geography')
		) AS props
	FROM pg_class c
	JOIN pg_namespace n ON (c.relnamespace = n.oid)
	JOIN pg_attribute a ON (a.attrelid = c.oid)
	JOIN pg_type t ON (a.atttypid = t.oid)
	LEFT JOIN pg_description d ON (c.oid = d.objoid and d.objsubid = 0)
	LEFT JOIN pg_index i ON (c.oid = i.indrelid AND i.indisprimary AND i.indnatts = 1)
	LEFT JOIN pg_attribute ia ON (ia.attrelid = i.indexrelid)
	LEFT JOIN pg_type it ON (ia.atttypid = it.oid AND it.typname in ('int2', 'int4', 'int8'))
	WHERE c.relkind IN ('r', 'v', 'm', 'p', 'f')
		AND t.typname = 'geometry'
		AND has_table_privilege(c.oid, 'select')
		AND has_schema_privilege(n.oid, 'usage')
		AND postgis_typmod_srid(a.atttypmod) > 0
		AND c.relname = '{table_name}' AND n.nspname = 'workflows'
	ORDER BY 1"""
    print("query", query)
    result = connection.execute(text(query))
    print("result", result.fetchall())
    if result.rowcount == 0:
        return True
    return False


class Node:
    kwargs = {}

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def params(self, param_name, default=None):
        if 'params' in self.kwargs['dag_run'].conf:
            if param_name in self.kwargs['dag_run'].conf['params']:
                return self.kwargs['dag_run'].conf['params'][param_name]
            
        if param_name in self.kwargs.get("params", {}):
            return self.kwargs["params"][param_name]
        
        return default

    def input(self, input_name, default=None):
        """
        Get input value from either data, connections, or default value.
        
        Priority order:
        1. Direct data input
        2. Connected node output
        3. Default value
        
        Args:
            input_name: Name of the input to retrieve
            default: Default value to return if input is not found
        
        Returns:
            Input value or default
        
        Raises:
            ValueError: If no input source is found and no default is provided
        """
        # Check if input exists in data
        if input_name in self.kwargs.get("data", {}):
            input_value = self.kwargs["data"][input_name]
            # If input value is None, continue to check connections
            if input_value is not None:
                # Handle parameter references
                if isinstance(input_value, str) and input_value in self.kwargs.get("params", {}):
                    return self.kwargs["params"][input_value]
                return input_value
        
        # Check connections
        connections = self.kwargs.get("connections", [])
        if connections:
            # Find matching connection
            for connection in connections:
                if connection["targetHandle"] == input_name:
                    try:
                        input_task_id = connection["source"]
                        input_handle = connection["sourceHandle"]
                        existing_data = self.kwargs["ti"].xcom_pull(task_ids=input_task_id)
                        
                        # Handle case where xcom_pull returns None
                        if existing_data is None:
                            print(f"Warning: No data found for connection from {input_task_id}")
                            continue
                        
                        # Handle case where input_handle doesn't exist in existing_data
                        if input_handle not in existing_data:
                            print(f"Warning: Handle {input_handle} not found in data from {input_task_id}")
                            continue
                        
                        return existing_data[input_handle]
                    except Exception as e:
                        print(f"Warning: Error getting data from connection: {str(e)}")
                        continue
        
        # If we reach here, no valid input was found
        if default is not None:
            return default
        
        # If no default is provided, raise error with helpful message
        error_msg = f"No valid input found for '{input_name}'"
        if input_name in self.kwargs.get("data", {}):
            error_msg += f" (data value was None)"
        if connections:
            error_msg += f" (checked {len(connections)} connections)"
        error_msg += " and no default value was provided"
        
        raise ValueError(error_msg)

    def create_output_table_name(self, func_name, inputs):
        if isinstance(inputs, dict):
            sorted_inputs = {k: inputs[k] for k in sorted(inputs.keys())}
            inputs = json.dumps(sorted_inputs,separators=(',', ':'))

        elif isinstance(inputs, list):
            sorted_inputs = sorted(inputs)
            inputs = json.dumps(sorted_inputs,separators=(',', ':'))

        output_table_name = hashlib.md5((func_name + inputs).encode()).hexdigest()
        return output_table_name

  

    def compute_in_db(
        self,
        func_name,
        inputs,
        query,
        geom_col: Optional[List[str]] = None,
        add_gid: bool = True,
        exclude_col: Optional[List[str]] = [],
        input_table_name: Optional[str] = None,
        replace_query_columns: bool = True
    ):
        engine = get_db_engine_lepton()
        output_table_name = self.create_output_table_name(func_name, inputs)
        exclude_col = exclude_col or []
        exclude_col.append("_gid")
        
        # Check cache validity
        cache_valid = engine.execute("""
            SELECT is_valid 
            FROM workflows.cache_entries 
            WHERE table_name = %s
        """, (output_table_name,)).scalar()
        
        print("cache_valid", cache_valid)
        print("table_exists", table_exists(engine, output_table_name))
        # If cache exists but is invalid, drop the table
        if cache_valid is False:
            engine.execute(f'DROP TABLE IF EXISTS workflows."{output_table_name}"')
        elif table_exists(engine, output_table_name):
            if cache_valid is True:
                print("using value from cache")
                return output_table_name, True
            else:
                print("using value from db")
                return output_table_name, False
            
        try:
            columns = get_column_names(engine, input_table_name)
            print("columns::::::::", columns)
            if exclude_col:
                columns = [
                    f'"{input_table_name}"."{col}"'
                    for col in columns
                    if col not in exclude_col
                ]
                valid_columns = ", ".join(columns)
                
                if valid_columns and replace_query_columns:
                    actual_query = query.replace("SELECT ", f"SELECT {valid_columns}, ")
                    print(actual_query)
                else:
                    actual_query = query
            else:
                actual_query = query
            
            
            # Start a transaction
            with engine.begin() as connection:
                print(f'CREATE TABLE workflows."{output_table_name}" AS ({actual_query})')
                connection.execute(
                    f'CREATE TABLE workflows."{output_table_name}" AS ({actual_query})'
                )
                
                if check_tile_json(output_table_name, connection):
                    connection.execute(
                        f'ALTER TABLE workflows."{output_table_name}" ALTER COLUMN geometry TYPE geometry(geometry, 4326) USING ST_SetSRID(geometry::geometry, 4326);'
                    )
                
                connection.execute(
                    f'GRANT ALL ON TABLE workflows."{output_table_name}" TO authenticated;'
                )
                
                if add_gid:
                    connection.execute(
                        f'ALTER TABLE workflows."{output_table_name}" ADD COLUMN IF NOT EXISTS "_gid" SERIAL;'
                    )
                    # Ensure _gid is always treated as integer type
                    connection.execute(
                        f'ALTER TABLE workflows."{output_table_name}" ALTER COLUMN "_gid" TYPE INTEGER;'
                    )
                    connection.execute(
                        f'CREATE INDEX idx_{output_table_name}_gid ON workflows."{output_table_name}" USING HASH("_gid");'
                    )
                    print("index created for _gid")
                
                if geom_col:
                    for geom in geom_col:
                        print(f"Creating index for {geom}")
                        connection.execute(
                            f'CREATE INDEX IF NOT EXISTS idx_{output_table_name}_{geom} ON workflows."{output_table_name}" USING GIST ({geom})'
                        )
                        print(f"Created index for {geom}")

                # Track the new cache entry within the same transaction
                track_cache(connection, output_table_name)
                print(f"Created table {output_table_name}")
                
                # The transaction will be automatically committed if no exceptions occur
                # If any operation fails, the entire transaction will be rolled back
                
            return output_table_name, False
        except Exception as e:
            raise ValueError(f"Error creating table {output_table_name}: {str(e)}")

    def parse_google_response(self, geocoded):
        """Helper function to parse Google geocoding response"""
        pincode = None
        state = None
        city = None
        district = None
        tehsil = None

        for result in geocoded.get("results", []):
            for component in result.get("address_components", []):
                types = component.get("types", [])
                if "postal_code" in types:
                    pincode = component["short_name"]
                elif "locality" in types and "political" in types:
                    city = component["long_name"]
                elif "administrative_area_level_2" in types and "political" in types:
                    district = component["long_name"]
                elif "administrative_area_level_1" in types and "political" in types:
                    state = component["long_name"]
                elif "administrative_area_level_3" in types and "political" in types:
                    tehsil = component["long_name"]
        return {
            "pincode": pincode,
            "state": state,
            "city": city,
            "district": district,
            "tehsil": tehsil,
        }

    def save_df_to_postgres(self, df: gpd.GeoDataFrame, table_name):
        if df.empty:
            raise ValueError("DataFrame is empty")
        if "_gid" not in df.columns:
            df["_gid"] = range(1, len(df) + 1)
        else:
            # Check for NaN values in _gid column and replace them with new sequential IDs
            if df["_gid"].isna().any():
                # Count existing valid IDs
                max_id = df["_gid"].max()
                if pd.isna(max_id):  # If all are NaN
                    max_id = 0
                else:
                    max_id = int(max_id)
                
                # Create a mask for NaN values
                nan_mask = df["_gid"].isna()
                # Generate new IDs for NaN values
                new_ids = range(max_id + 1, max_id + 1 + nan_mask.sum())
                # Assign new IDs to NaN positions
                df.loc[nan_mask, "_gid"] = list(new_ids)
            
            # Ensure _gid is always integer type
            df["_gid"] = df["_gid"].astype(int)
            
        engine = get_db_engine_lepton()
        
        # Check cache validity
        cache_valid = engine.execute("""
            SELECT is_valid 
            FROM workflows.cache_entries 
            WHERE table_name = %s
        """, (table_name,)).scalar()
        
        # If cache exists but is invalid, drop the table
        if cache_valid is False:
            engine.execute(f'DROP TABLE IF EXISTS workflows."{table_name}"')
        elif cache_valid is True and table_exists(engine, table_name):
            print("using value from cache")
            return table_name, True

        try:
            print(f"Saving data to Postgres table: {table_name}")
            if df.crs is None:
                df.set_crs("EPSG:4326", inplace=True)
            df.to_postgis(table_name, engine, schema="workflows")
            engine.execute(f'GRANT ALL ON TABLE workflows."{table_name}" TO authenticated;')
            # Track the new cache entry
            track_cache(engine, table_name)
            print(f"Saved data to Postgres table: {table_name}")
        except Exception as e:
            raise ValueError(f"ERR: {str(e)}")
        return table_name, False

    def build_gid_query(self, table_name, feature_id=None, additional_conditions=None):
        """
        Build a SQL query with proper type casting for _gid.
        
        Args:
            table_name: The table name to query
            feature_id: Optional feature ID to filter by
            additional_conditions: Optional additional WHERE conditions
            
        Returns:
            SQL query string with proper type casting
        """
        base_query = f'SELECT * FROM workflows."{table_name}"'
        
        conditions = []
        if feature_id is not None:
            conditions.append(f'_gid = {feature_id}::bigint')
            
        if additional_conditions:
            conditions.append(additional_conditions)
            
        if conditions:
            where_clause = ' WHERE ' + ' AND '.join(conditions)
            return base_query + where_clause
        else:
            return base_query


# class Geometry(BaseModel):
#     pass


# class MultiPolygon(Geometry):
#     type: str = "MultiPolygon"
#     coordinates: Any = []

#     # from_shapely = (
#     #     lambda shape: Polygon(coordinates=shape.__geo_interface__["coordinates"])
#     #     if isinstance(shape, ShapelyPolygon)
#     #     else Polygon(coordinates=shape.__geo_interface__["coordinates"])
#     # )

#     # from_wkb = lambda shape: Polygon.from_shapely(from_wkb(shape))


# def geometry_from_wkb(shape):
#     shp = from_wkb(shape)
#     return (
#         Polygon(coordinates=shp.__geo_interface__["coordinates"])
#         if isinstance(shp, ShapelyPolygon)
#         else MultiPolygon(coordinates=shp.__geo_interface__["coordinates"])
#     )


# class Polygon(Geometry):
#     type: str = "Polygon"
#     coordinates: Any = []

#     def from_shapely(shape):
#         return (
#             Polygon(coordinates=shape.__geo_interface__["coordinates"])
#             if isinstance(shape, ShapelyPolygon)
#             else MultiPolygon(coordinates=shape.__geo_interface__["coordinates"])
#         )

#     def from_wkb(shape):
#         return geometry_from_wkb(shape)


# class Point(Geometry):
#     type: str = "Point"
#     coordinates: Any = []


# class LineString(Geometry):
#     type: str = "LineString"
#     coordinates: List[List[float]] = []

#     def from_shapely(shape):
#         return LineString(coordinates=shape.__geo_interface__["coordinates"])


# class Feature(BaseModel):
#     type: str = "Feature"
#     geometry: None | Polygon | Point | MultiPolygon | LineString = {}
#     properties: dict = {}


# class FeatureCollection(BaseModel):
#     type: str = "FeatureCollection"
#     features: List[Feature] = []
#     properties: dict = {}

#     def __dict__(self):
#         return {
#             "type": "FeatureCollection",
#             "features": self.features,
#             "properties": self.properties,
#         }


# class Catchment:
#     GRAPHHOPPER_API_HOST, GRAPHHOPPER_API_PORT = "graphhopper", "8989"
#     # Add the directory containing 'catchment.py' to sys.path
#     # sys.path.append('/app/routes/geojson')
#     # sys.path.append('/home/lepton/github/lepton-maps-prod/apps/api.leptonmaps.com/routes/geojson')
#     gmaps = googlemaps.Client(key="AIzaSyByraLO7WVzW-9K-H6NErKftVydyJK2058")
#     API_URL_GOOGLE = (
#         "https://us-central1-pinsight-ai.cloudfunctions.net/smdemo-drive-time-polygon"
#     )

#     # Now you can import the module
#     # from catchment import get_catchment_from_graphhopper

#     def angle_from_center(center, point):
#         """Calculate the angle of a point from the center."""
#         dx = point[0] - center[0]
#         dy = point[1] - center[1]
#         angle = math.atan2(dy, dx)  # Angle in radians
#         return math.degrees(angle) % 360  # Convert to degrees and normalize to 0-360°

#     def distance_from_center(center, point):
#         """Calculate the Euclidean distance from the center to a point."""
#         dx = point[0] - center[0]
#         dy = point[1] - center[1]
#         return math.sqrt(dx**2 + dy**2)

#     def sort_points_by_angle_and_distance(self, center, points):
#         """Sort points by angle and distance around the center."""
#         return sorted(
#             points,
#             key=lambda point: (
#                 self.angle_from_center(center, point),
#                 self.distance_from_center(center, point),
#             ),
#         )

#     # Function to get directions from Google Maps API, including alternate routes
#     # def get_directions(gmaps, origin, destination, direction_cache, bearing, waypoints=None):
#     # cache_key = f"{bearing}_{origin[0]}_{origin[1]}"
#     # if cache_key in direction_cache:
#     #     print("Not calling Api")
#     #     return direction_cache[cache_key]

#     # Request directions including alternative routes
#     # directions = gmaps.directions(
#     #     origin,
#     #     destination,
#     #     mode="driving",
#     #     waypoints=waypoints,
#     #     alternatives=True  # Fetch alternate routes
#     # )

#     # Store directions in cache
#     # direction_cache[cache_key] = directions
#     # return directions

#     # Function to decode polyline
#     def decode_polyline(polyline_str):
#         return polyline.decode(polyline_str)

#     # Get a point along a line at a given percentage
#     def get_point_along_line(line, percentage):
#         length = line.length
#         point = line.interpolate(percentage * length)
#         return point.y, point.x  # Return as (lat, lng)

#     def parse_directions_for_duration(self, directions, target_duration_minutes):
#         target_duration_seconds = target_duration_minutes * 60
#         points = []

#         for direction in directions:
#             # Check if direction is a list of routes (since alternatives=True)
#             if isinstance(direction, list):
#                 for route in direction:
#                     legs = route["legs"]
#                     for leg in legs:
#                         accumulated_duration = 0
#                         steps = leg["steps"]

#                         for step in steps:
#                             step_duration = step["duration"]["value"]
#                             accumulated_duration += step_duration

#                             if accumulated_duration <= target_duration_seconds:
#                                 # Continue to next step if within target duration
#                                 continue
#                             else:
#                                 # Calculate how much of the current step is needed
#                                 extra_time = (
#                                     accumulated_duration - target_duration_seconds
#                                 )
#                                 percentage_needed = 1 - (extra_time / step_duration)
#                                 polyline_points = self.decode_polyline(
#                                     step["polyline"]["points"]
#                                 )
#                                 line = LineString(polyline_points)
#                                 point_lng, point_lat = self.get_point_along_line(
#                                     line, percentage_needed
#                                 )
#                                 points.append((point_lng, point_lat))
#                                 break

#                         if len(points) < len(legs):
#                             # If no point has been added yet, take the end location of the last step
#                             end_location = steps[-1]["end_location"]
#                             points.append((end_location["lng"], end_location["lat"]))
#                         break
#             else:
#                 # Handle the case where directions is not a list of routes
#                 legs = direction["legs"]
#                 for leg in legs:
#                     accumulated_duration = 0
#                     steps = leg["steps"]

#                     for step in steps:
#                         step_duration = step["duration"]["value"]
#                         accumulated_duration += step_duration

#                         if accumulated_duration <= target_duration_seconds:
#                             # Continue to next step if within target duration
#                             continue
#                         else:
#                             # Calculate how much of the current step is needed
#                             extra_time = accumulated_duration - target_duration_seconds
#                             percentage_needed = 1 - (extra_time / step_duration)
#                             polyline_points = self.decode_polyline(
#                                 step["polyline"]["points"]
#                             )
#                             line = LineString(polyline_points)
#                             point_lng, point_lat = self.get_point_along_line(
#                                 line, percentage_needed
#                             )
#                             points.append((point_lng, point_lat))
#                             break

#                     if len(points) < len(legs):
#                         # If no point has been added yet, take the end location of the last step
#                         end_location = steps[-1]["end_location"]
#                         points.append((end_location["lng"], end_location["lat"]))
#                     break

#         return points[0] if points else (None, None)  # Return the first valid point

#     async def get_directions(
#         session,
#         origin,
#         destination,
#         direction_cache,
#         bearing,
#         api_key,
#         waypoints=None,
#         departure_time=None,
#     ):
#         cache_key = f"{bearing}_{origin[0]}_{origin[1]}"
#         if cache_key in direction_cache:
#             print("Not calling API")
#             return direction_cache[cache_key]

#         # Construct the Google Directions API URL
#         base_url = "https://maps.googleapis.com/maps/api/directions/json"
#         params = {
#             "origin": f"{origin[0]},{origin[1]}",
#             "destination": f"{destination[0]},{destination[1]}",
#             "key": api_key,
#             "mode": "driving",
#             "alternatives": "true",
#         }

#         if departure_time:
#             params["departure_time"] = departure_time

#         # print(params)

#         async with session.get(base_url, params=params) as response:
#             directions = await response.json()
#             direction_cache[cache_key] = directions
#             return directions

#     # Updated function to calculate catchment area using 18 points from GeoJSON
#     async def calculate_catchment_area(
#         self,
#         gmaps_api_key,
#         lat,
#         lng,
#         range_value,
#         is_time_based,
#         direction_cache,
#         points_from_geojson,
#         departure_time,
#     ):
#         points = []
#         original_points = []
#         all_directions = []
#         range_value = range_value * 0.9
#         center_point = (lng, lat)

#         async with aiohttp.ClientSession() as session:
#             tasks = []
#             for i, point in enumerate(points_from_geojson):
#                 destination_lng, destination_lat = point.x, point.y
#                 original_points.append((destination_lng, destination_lat))

#                 # Create async task for each directions call
#                 task = self.get_directions(
#                     session,
#                     (lat, lng),
#                     (destination_lat, destination_lng),
#                     direction_cache,
#                     i,
#                     gmaps_api_key,
#                     departure_time,
#                 )
#                 tasks.append(task)

#             # Run all the get_directions calls concurrently
#             all_directions_results = await asyncio.gather(*tasks)
#             # print(all_directions_results)
#             for directions in all_directions_results:
#                 all_routes = []
#                 if isinstance(directions, dict):  # Ensure the response is a dictionary
#                     routes = directions.get("routes", [])
#                     for route_set in routes:
#                         if isinstance(
#                             route_set, dict
#                         ):  # Ensure route_set is a dictionary
#                             point_lng, point_lat = self.parse_directions_for_duration(
#                                 [route_set], range_value
#                             )
#                             points.append((point_lng, point_lat))
#                             all_routes.append(route_set)
#                 elif isinstance(
#                     directions, list
#                 ):  # Handle case where directions is a list of routes
#                     for route_set in directions:
#                         if isinstance(
#                             route_set, dict
#                         ):  # Ensure route_set is a dictionary
#                             point_lng, point_lat = self.parse_directions_for_duration(
#                                 [route_set], range_value
#                             )
#                             points.append((point_lng, point_lat))
#                             all_routes.append(route_set)

#                 # Append the processed routes for each direction set
#                 all_directions.append(all_routes)

#         # print(len(points))
#         points = list(
#             {(lng, lat) for lng, lat in points if lng is not None and lat is not None}
#         )
#         # print(len(points))

#         sorted_points = self.sort_points_by_angle_and_distance(center_point, points)

#         return sorted_points, original_points, all_directions

#     # Function to create a polygon from points
#     def create_polygon_from_points(points, drive_time, lat, lng):
#         polygon = shapely.geometry.Polygon(points)
#         properties = {
#             "name": "{} mins Catchment of {}, {}".format(drive_time, lat, lng),
#             "drive_time": drive_time,
#         }

#         return geojson.Feature(geometry=polygon, properties=properties)

#     # Function to create features for points
#     def create_points_feature(points, description="Initial Points"):
#         features = []
#         for lng, lat in points:
#             point = Point((lng, lat))
#             features.append(
#                 geojson.Feature(geometry=point, properties={"description": description})
#             )
#         return features

#     # Load directions cache if exists
#     def load_directions_from_cache(filename="directions_cache_1.geojson"):
#         if os.path.exists(filename):
#             with open(filename, "r") as f:
#                 return geojson.load(f)
#         return {}

#     def points_to_geojson(points):
#         """
#         Convert a list of shapely.geometry.Point objects to GeoJSON format.

#         :param points: List of shapely.geometry.Point objects
#         :return: GeoJSON as a dict
#         """
#         features = []
#         for point in points:
#             feature = {
#                 "type": "Feature",
#                 "geometry": {"type": "Point", "coordinates": [point.x, point.y]},
#                 "properties": {},
#             }
#             features.append(feature)

#         geojson = {"type": "FeatureCollection", "features": features}

#         return geojson

#     # Function to replace the API call and use a direct function instead
#     async def get_catchment_graphopper(
#         self, lat, lng, drive_distance, drive_time, api_key=None, speed_kmph=35
#     ):
#         try:
#             # Try calling the local get_catchment_from_graphhopper function instead of the API
#             polygon = await self.get_catchment_from_graphhopper(
#                 lat, lng, "DRIVE_TIME", drive_distance, drive_time
#             )
#             # print(polygon)

#             if polygon is not None:
#                 # Return the feature collection if the polygon is successfully generated
#                 return {
#                     "type": "FeatureCollection",
#                     "features": [
#                         {
#                             "type": "Feature",
#                             "geometry": {"coordinates": polygon.coordinates},
#                             "properties": {
#                                 "name": "GH {}min Catchment of {}, {}".format(
#                                     drive_time, lat, lng
#                                 ),
#                                 "drive_time": drive_time,
#                             },
#                         }
#                     ],
#                 }
#             else:
#                 # If no result, fallback to generate a circle
#                 raise Exception(
#                     "No catchment polygon returned from get_catchment_from_graphhopper"
#                 )

#         except Exception as e:
#             print(
#                 f"Catchment generation failed: {e}. Falling back to circle generation."
#             )

#             # Fallback to generate a circle polygon based on constant speed
#             drive_time_hours = (
#                 drive_time / 60
#             )  # Convert drive time from minutes to hours
#             radius_km = (
#                 speed_kmph * drive_time_hours
#             )  # Distance in km based on speed and time

#             # Generate a circle polygon with a radius in kilometers
#             fallback_polygon = self.generate_circle_polygon(lat, lng, radius_km)
#             return {
#                 "type": "FeatureCollection",
#                 "features": [
#                     {
#                         "type": "Feature",
#                         "geometry": fallback_polygon["geometry"],
#                         "properties": {
#                             "name": "Fallback {}min Catchment of {}, {}".format(
#                                 drive_time, lat, lng
#                             ),
#                             "drive_time": drive_time,
#                         },
#                     }
#                 ],
#             }

#     # Function to replace the API call and use a direct function instead
#     async def get_fallback_graphhopper(
#         self, lat, lng, drive_distance, drive_time, api_key=None, speed_kmph=35
#     ):
#         # Fallback to generate a circle polygon based on constant speed
#         drive_time_hours = drive_time / 60  # Convert drive time from minutes to hours
#         radius_km = (
#             speed_kmph * drive_time_hours
#         )  # Distance in km based on speed and time

#         # Generate a circle polygon with a radius in kilometers
#         fallback_polygon = self.generate_circle_polygon(lat, lng, radius_km)
#         return {
#             "type": "FeatureCollection",
#             "features": [
#                 {
#                     "type": "Feature",
#                     "geometry": fallback_polygon["geometry"],
#                     "properties": {
#                         "name": "Fallback {}min Catchment of {}, {}".format(
#                             drive_time, lat, lng
#                         ),
#                         "drive_time": drive_time,
#                     },
#                 }
#             ],
#         }

#     def generate_circle_polygon(lat, lng, radius_km, num_points=36):
#         """
#         Generate a circle polygon (GeoJSON format) with a given center (lat, lng) and radius in kilometers.
#         The circle will be approximated with `num_points` points.
#         """
#         points = []

#         for i in range(num_points):
#             # Calculate the angle for each point on the circle
#             angle = i * (360 / num_points)

#             # Calculate the destination point at the given angle and radius
#             destination = geodesic(kilometers=radius_km).destination((lat, lng), angle)
#             points.append((destination.longitude, destination.latitude))

#         # Close the polygon by adding the first point again at the end
#         points.append(points[0])

#         # Create a GeoJSON polygon
#         polygon = geojson.Polygon([points])

#         return geojson.Feature(geometry=polygon)

#     def generate_points_on_boundary(polygon, center_point, num_points):
#         """
#         Generate points on the boundary of the polygon based on angular spacing.

#         :param polygon: The polygon (shapely.geometry.Polygon)
#         :param center_point: The center point for radial generation
#         :param num_points: Number of points to generate (e.g., 18 points for 360 degrees / 20 degrees)
#         :return: List of shapely.geometry.Point objects on the boundary
#         """
#         angles = np.linspace(0, 360, num_points, endpoint=False)
#         boundary_points = []
#         # print(center_point)
#         # center_point = polygon.centroid
#         # center_point = Point(center_point)

#         # Maximum distance from the center to a point on the boundary
#         max_distance = polygon.boundary.distance(center_point)

#         for angle in angles:
#             # Convert angle to radians
#             angle_rad = radians(angle)

#             # Calculate x, y offsets using cosine and sine
#             offset_x = cos(angle_rad) * max_distance
#             offset_y = sin(angle_rad) * max_distance

#             # Generate a point based on the angle
#             point = Point(center_point.x + offset_x, center_point.y + offset_y)

#             # Find the nearest point on the boundary
#             nearest_boundary_point = polygon.boundary.interpolate(
#                 polygon.boundary.project(point)
#             )
#             boundary_points.append(nearest_boundary_point)

#         return boundary_points

#     def extract_polygon_from_geojson(geojson_data):
#         """
#         Extracts the Polygon from a GeoJSON object, which can be either a FeatureCollection or a Feature.

#         :param geojson_data: GeoJSON FeatureCollection or Feature
#         :return: shapely.geometry.Polygon
#         """
#         # Check if the GeoJSON is a FeatureCollection or a Feature
#         if "features" in geojson_data:
#             # It's a FeatureCollection, proceed as usual
#             features = geojson_data["features"]
#             if not features:
#                 raise ValueError("No features found in the GeoJSON FeatureCollection.")

#             # Extract the coordinates of the first feature's geometry
#             polygon_coords = features[0]["geometry"]["coordinates"][0]
#         elif "geometry" in geojson_data:
#             # It's a single Feature, extract the geometry directly
#             polygon_coords = geojson_data["geometry"]["coordinates"][0]
#         else:
#             raise ValueError(
#                 "Invalid GeoJSON format. Expected 'features' or 'geometry' key."
#             )

#         # Create and return a Shapely Polygon from the coordinates
#         return shapely.geometry.Polygon(polygon_coords)

#     async def get_catchment_google(
#         self,
#         lat,
#         lng,
#         drive_distance,
#         catchment_type,
#         departure_time,
#         drive_time,
#         lepton_api_key="b856fb22dd97b1e183e32742a33324cd41b7d0b4be4a664ca3af78bf64066865",
#         google_maps_api_key="AIzaSyB1Mgwe75_Gxuw9JAckM8kKnXNeKmVXeGg",
#         is_time_based=True,
#         is_fallback=False,
#     ):
#         """
#         Fetches the catchment area using LeptonMaps API for driving distance and time, generates points around the boundary, and refines them using Google Maps directions.

#         :param lat: Latitude of the central point.
#         :param lng: Longitude of the central point.
#         :param drive_distance: Maximum driving distance (in meters).
#         :param drive_time: Maximum driving time (in minutes).
#         :param lepton_api_key: API key for LeptonMaps.
#         :param google_maps_api_key: API key for Google Maps.
#         :param range_value: The range value in minutes for calculating time-based catchment.
#         :param is_time_based: Boolean flag to indicate whether to calculate catchment based on time (True) or distance (False).

#         :return: GeoJSON FeatureCollection of the catchment area with points.
#         """
#         drive_time_gh = 2 * drive_time
#         # Get the catchment area from LeptonMaps API
#         if is_fallback is True:
#             temp_catch = await self.get_fallback_graphhopper(
#                 lat,
#                 lng,
#                 drive_distance=drive_distance,
#                 drive_time=drive_time_gh,
#                 api_key=lepton_api_key,
#             )
#         else:
#             temp_catch = await self.get_catchment_graphopper(
#                 lat,
#                 lng,
#                 drive_distance=drive_distance,
#                 drive_time=drive_time_gh,
#                 api_key=lepton_api_key,
#             )

#         # print(temp_catch)
#         # Extract the polygon from the GeoJSON response
#         temp_catch = self.extract_polygon_from_geojson(temp_catch)

#         # Define the center point
#         center_point = Point(lng, lat)

#         # Generate 18 points on the boundary of the catchment area polygon
#         boundary_points_geojson = self.generate_points_on_boundary(
#             temp_catch, center_point=center_point, num_points=18
#         )

#         # Convert the generated points into GeoJSON format
#         points_geojson = self.points_to_geojson(boundary_points_geojson)

#         # Initialize the Google Maps API client
#         gmaps = googlemaps.Client(key=google_maps_api_key)

#         # Load existing cache if available
#         direction_cache = self.load_directions_from_cache()

#         # Calculate the catchment area using the Google Maps API for refining the points
#         points, original_points, all_directions = await self.calculate_catchment_area(
#             google_maps_api_key,
#             lat,
#             lng,
#             drive_time,
#             is_time_based,
#             direction_cache,
#             boundary_points_geojson,
#             departure_time,
#         )

#         # Create a GeoJSON polygon feature from the sorted points
#         polygon_feature = self.create_polygon_from_points(points, drive_time, lat, lng)

#         # Create a GeoJSON FeatureCollection combining the polygon and the original points
#         geojson_output = geojson.FeatureCollection([polygon_feature])
#         # + create_points_feature(original_points))

#         # Return the final GeoJSON data
#         return geojson_output

#     # Define the API key
#     gmaps = googlemaps.Client(key="AIzaSyByraLO7WVzW-9K-H6NErKftVydyJK2058")

#     async def get_catchment_with_routes(central_point, radius, num_points):
#         # Function to calculate the coordinates of points around the central point
#         def calculate_coordinates(
#             lat: Annotated[float, "Latitude of the central point"], lon, radius, angle
#         ):
#             """
#             Calculate the coordinates of a point around the central point.

#             :param lat: Latitude of the central point
#             :param lon: Longitude of the central point
#             :param radius: Radius (in kilometers)
#             :param angle: Angle (in degrees)
#             :return: (latitude, longitude)
#             """
#             # Convert latitude and longitude from degrees to radians
#             lat = math.radians(lat)
#             lon = math.radians(lon)

#             # Convert angle from degrees to radians
#             angle = math.radians(angle)

#             # Convert radius from kilometers to radians
#             radius = radius / 6371.01

#             lat2 = math.asin(
#                 math.sin(lat) * math.cos(radius)
#                 + math.cos(lat) * math.sin(radius) * math.cos(angle)
#             lon2 = lon + math.atan2(
#                 math.sin(angle) * math.sin(radius) * math.cos(lat),
#                 math.cos(radius) - math.sin(lat) * math.sin(lat2),
#             )

#             # Convert latitude and longitude from radians to degrees
#             lat2 = math.degrees(lat2)
#             lon2 = math.degrees(lon2)

#             return lat2, lon2

#         # Calculate the coordinates of points around the central point
#         points = [
#             calculate_coordinates(central_point[0], central_point[1], radius, angle)
#             for angle in range(0, 360, 360 // num_points)
#         ]

#         # Function to calculate the distance between two points in UTM
#         def calculate_distance(self, point1, point2):
#             """
#             Calculate the distance between two points in UTM.

#             :param point1: First point (latitude, longitude)
#             :param point2: Second point (latitude, longitude)
#             :return: Distance (in meters)
#             """
#             # Convert latitude and longitude to UTM
#             proj = self.pyproj.Proj(proj="utm", zone=33, ellps="WGS84")
#             x1, y1 = proj(*point1)
#             x2, y2 = proj(*point2)

#             # Calculate the distance
#             distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

#             return distance

#         # Function to interpolate a point along a segment in UTM
#         def interpolate_point(self, point1, point2, ratio):
#             """
#             Interpolate a point along a segment in UTM.

#             :param point1: First point (latitude, longitude)
#             :param point2: Second point (latitude, longitude)
#             :param ratio: Ratio
#             :return: (latitude, longitude)
#             """
#             # Convert latitude and longitude to UTM
#             proj = self.pyproj.Proj(proj="utm", zone=33, ellps="WGS84")
#             x1, y1 = proj(*point1)
#             x2, y2 = proj(*point2)

#             # Interpolate the point
#             x = x1 + (x2 - x1) * ratio
#             y = y1 + (y2 - y1) * ratio

#             # Convert UTM to latitude and longitude
#             lat, lon = proj(x, y, inverse=True)

#             return lat, lon

#         # Function to get the location at a specific distance along the route
#         def get_location_at_distance(route, distance):
#             """
#             Get the location at a specific distance along the route.

#             :param route: Route
#             :param distance: Distance (in meters)
#             :return: (latitude, longitude) or None
#             """
#             # Initialize the cumulative distance
#             cumulative_distance = 0

#             last_point = None

#             # Iterate through the steps of the route
#             for leg in route[0]["legs"]:
#                 for step in leg["steps"]:
#                     # Decode the polyline of the step
#                     line = polyline.decode(step["polyline"]["points"], 5)
#                     # Iterate through the points of the polyline
#                     for i in range(len(line) - 1):
#                         # Calculate the distance between the points
#                         step_distance = calculate_distance(line[i], line[i + 1])

#                         # If the cumulative distance and the distance between the points exceed the specified distance
#                         if cumulative_distance + step_distance >= distance:
#                             # Calculate the ratio of the distances
#                             ratio = (distance - cumulative_distance) / step_distance

#                             # Interpolate the point along the segment
#                             point = interpolate_point(line[i], line[i + 1], ratio)

#                             # Return the point
#                             return point

#                         # Add the distance between the points to the cumulative distance
#                         cumulative_distance += step_distance
#                         last_point = line[i + 1]

#             # If the distance is not reached
#             return last_point

#         def get_route_polyline(route):
#             points = []
#             time = 0
#             for leg in route[0]["legs"]:
#                 for step in leg["steps"]:
#                     # Decode the polyline of the step
#                     line = polyline.decode(step["polyline"]["points"], 5)
#                     curr_time = time
#                     step_size = step["duration"]["value"] / len(line)

#                     i = 0
#                     for x, y in line:
#                         points.append((x, y, curr_time + (i * step_size)))
#                         i += 1
#                     time = time + step["duration"]["value"]

#             return shapely.LineString([(y, x, z) for (x, y, z) in points])

#         # Function to get a route and the location at a specific distance along it
#         def get_route_and_location(self, to_point):
#             # Get the route from the central point to the point
#             route = self.gmaps.directions(central_point, to_point, mode="driving")

#             # Get the location at 1 km along the route
#             location = get_location_at_distance(route, radius * 1000)

#             return route, location

#         # Get the routes and the locations at 1 km along the routes
#         with concurrent.futures.ThreadPoolExecutor() as executor:
#             routes_and_locations = list(executor.map(get_route_and_location, points))

#         # Separate the routes and the locations
#         routes, locations = zip(*routes_and_locations)

#         from scipy.spatial import ConvexHull

#         def order_locations(locations):
#             """
#             Order a list of locations so that each location is next to its nearest neighbor.

#             :param locations: List of locations (each location is a tuple of latitude and longitude)
#             :return: Ordered list of locations
#             """
#             # Create a distance matrix
#             # Compute the convex hull
#             hull = ConvexHull(locations)

#             # Order the locations according to the convex hull
#             ordered_locations = [locations[i] for i in hull.vertices]

#             return ordered_locations

#         # Get the locations at 1 km along the routes
#         # locations = [get_location_at_distance(route, radius * 1000) for route in routes]

#         return (
#             Polygon.from_shapely(shapely.Polygon([(y, x) for (x, y) in locations])),
#             # shapely.Polygon(points),
#             [LineString.from_shapely(get_route_polyline(route)) for route in routes],
#         )

#     # API_URL_GOOGLE = "https://us-central1-sm-trial.cloudfunctions.net/drive-time-polygon"

#     # Latitude, longitude of Connought Place, New Delhi
#     # lat = 28.6315
#     # long = 77.2167

#     async def get_catchment(
#         self,
#         lat: float = 28.6315,
#         long: float = 77.2167,
#         catchment_type: Literal["DRIVE_DISTANCE"]
#         | Literal["DRIVE_TIME"] = "DRIVE_DISTANCE",
#         drive_distance: int = 2000,
#         drive_time: int = 15,
#     ) -> Polygon:
#         request_body = {"center": {"lat": lat, "lng": long}}
#         if catchment_type == "DRIVE_DISTANCE":
#             request_body["driveDistance"] = drive_distance
#         elif catchment_type == "DRIVE_TIME":
#             request_body["driveTime"] = drive_time
#         else:
#             raise ValueError(f"Invalid catchment_type: {catchment_type}")
#         try:
#             async with httpx.AsyncClient() as client:
#                 response = await client.post(self.API_URL_GOOGLE, json=request_body)
#                 result = response.json()
#                 coordinates = [[item["lng"], item["lat"]] for item in result]
#                 polygon_instance = Polygon(coordinates=[coordinates])
#                 return polygon_instance

#         except httpx.HTTPStatusError as http_err:
#             print(f"HTTP error occurred: {http_err}")
#             raise http_err
#         except Exception as err:
#             print(f"Other error occurred: {err}")
#             raise err

#     async def get_catchment_from_old_api(
#         latitude: float = 28.6315,
#         longitude: float = 77.2167,
#         catchment_type: Literal["DRIVE_DISTANCE"]
#         | Literal["DRIVE_TIME"] = "DRIVE_DISTANCE",
#         drive_distance: int = 2000,
#         drive_time: int = 15,
#     ):
#         try:
#             async with httpx.AsyncClient() as client:
#                 response = await client.post(
#                     "http://192.168.1.14:5000/driveTimePolygon",
#                     json={
#                         "center": {"lat": latitude, "lng": longitude},
#                         "driveTime": drive_time,
#                     },
#                 )
#                 result = response.json()
#                 coordinates = [[item["lng"], item["lat"]] for item in result]
#                 polygon_instance = Polygon(coordinates=[coordinates])
#                 return polygon_instance

#         except httpx.HTTPStatusError as http_err:
#             print(f"HTTP error occurred: {http_err}")
#             raise http_err
#         except Exception as err:
#             print(f"Other error occurred: {err}")
#             raise err

#     def is_point_in_geojson(lat, lon):
#         current_directory = os.path.dirname(__file__)
#         # Load GeoJSON file
#         gdf = db.read_file(os.path.join(current_directory, "east.geojson"))
#         mumbai_gdf = db.read_file(os.path.join(current_directory, "mumbai.geojson"))

#         # Create a point based on the latitude and longitude
#         point = Point(lon, lat)

#         # Check if the point is in the GeoDataFrame
#         return any(gdf.contains(point)) or any(mumbai_gdf.contains(point))

#         async def get_catchment_from_graphhopper(
#             self,
#             latitude: float = 28.6315,
#             longitude: float = 77.2167,
#             catchment_type: Literal["DRIVE_DISTANCE"]
#             | Literal["DRIVE_TIME"] = "DRIVE_DISTANCE",
#             drive_distance: int = 2000,
#             drive_time: int = 15,
#             departure_time: datetime = datetime.now(),
#         ):
#             if catchment_type == "DRIVE_DISTANCE":
#                 url = f"http://{self.GRAPHHOPPER_API_HOST}:{self.GRAPHHOPPER_API_PORT}/isochrone?point={latitude},{longitude}&buckets=1&distance_limit={drive_distance}&profile=car"
#                 try:
#                     response = requests.get(url)
#                     if response.status_code == 400:
#                         raise Exception(response.json()["message"])
#                     result = response.json()
#                     coordinates = result["polygons"][0]["geometry"]["coordinates"][0]
#                     polygon_instance = Polygon(coordinates=[coordinates])
#                     return polygon_instance
#                 except httpx.HTTPStatusError as http_err:
#                     print(f"HTTP error occurred: {http_err}")
#                     raise http_err
#             elif catchment_type == "DRIVE_TIME":
#                 if self.is_point_in_geojson(latitude, longitude):
#                     time_divisor = 3
#                 else:
#                     time_divisor = 2.23

#                 print(time_divisor)

#                 url = f"http://{self.GRAPHHOPPER_API_HOST}:{self.GRAPHHOPPER_API_PORT}/isochrone?point={latitude},{longitude}&buckets=1&time_limit={int((drive_time * 60)/time_divisor)}&profile=car"
#                 try:
#                     response = requests.get(url)
#                     if response.status_code == 400:
#                         result = response.json()
#                         if "message" in result and "Point not found" in result["message"]:
#                             # Fallback to Google Maps API if the point is not found
#                             return await self.get_catchment_google(
#                                 lat=latitude,
#                                 lng=longitude,
#                                 catchment_type=catchment_type,
#                                 drive_distance=drive_distance,
#                                 drive_time=drive_time,
#                                 departure_time=departure_time,
#                                 is_fallback=True,
#                             )
#                         raise Exception(response.json()["message"])
#                     result = response.json()
#                     coordinates = result["polygons"][0]["geometry"]["coordinates"][0]
#                     polygon_instance = Polygon(coordinates=[coordinates])
#                     return polygon_instance
#                 except httpx.HTTPStatusError as http_err:
#                     print(f"HTTP error occurred: {http_err}")
#                     raise http_err

#         async def catchment(
#             self,
#             latitude: float,
#             longitude: float,
#             catchment_type: Literal["DRIVE_DISTANCE", "DRIVE_TIME"] = "DRIVE_DISTANCE",
#             accuracy_time_based: Literal["MEDIUM", "HIGH"] = "MEDIUM",
#             drive_distance: int = 1000,
#             drive_time: int = 15,
#             departure_time: str = (datetime.now() + timedelta(minutes=5)).strftime(
#                 "%Y-%m-%d %H:%M:%S"
#             ),
#         ):
#             """
#             The Catchment API is a sophisticated tool designed to generate catchment areas based on two key parameters: drive time and drive distance.
#             This API efficiently calculates the area that can be reached within a specified driving time or distance from a given point,
#             enabling businesses and organizations to analyze and strategize their operations more effectively.
#             """

#             try:
#                 departure_time = int(
#                     datetime.strptime(departure_time, "%Y-%m-%d %H:%M:%S").timestamp()
#                 )
#             except ValueError:
#                 raise ValueError(
#                     "Invalid departure_time format. Use 'YYYY-MM-DD HH:MM:SS'."
#                 )
#             # print("TIMEEEEEEEEEEEEEEEEEEEE",departure_time)
#             lepton_api_key = (
#                 "b856fb22dd97b1e183e32742a33324cd41b7d0b4be4a664ca3af78bf64066865"
#             )
#             google_maps_api_key = "AIzaSyB1Mgwe75_Gxuw9JAckM8kKnXNeKmVXeGg"
#             if accuracy_time_based == "HIGH" and catchment_type == "DRIVE_TIME":
#                 return await self.get_catchment_google(
#                     lat=latitude,
#                     lng=longitude,
#                     catchment_type=catchment_type,
#                     drive_distance=drive_distance,
#                     drive_time=drive_time,
#                     departure_time=departure_time,
#                     lepton_api_key=lepton_api_key,
#                     google_maps_api_key=google_maps_api_key,
#                 )

#             polygon = await self.get_catchment_from_graphhopper(
#                 latitude, longitude, catchment_type, drive_distance, drive_time
#             )

#             if (
#                 isinstance(polygon, dict)
#                 and "features" in polygon
#                 and isinstance(polygon["features"], list)
#             ):
#                 # Ensure that the "features" list contains at least one item with valid geometry
#                 if len(polygon["features"]) > 0 and "geometry" in polygon["features"][0]:
#                     coordinates = polygon["features"][0]["geometry"].get("coordinates")
#                     if coordinates:
#                         return polygon

#             if catchment_type == "DRIVE_DISTANCE":
#                 return {
#                     "geometry": polygon,
#                     "properties": {
#                         "name": "{}km Catchment of {}, {}".format(
#                             drive_distance / 1000, latitude, longitude
#                         ),
#                         "drive_distance": drive_distance,
#                     },
#                 }

#             else:
#                 return {
#                     "geometry": polygon,
#                     "properties": {
#                         "name": "{}min Catchment of {}, {}".format(
#                             drive_time, latitude, longitude
#                         ),
#                         "drive_time": drive_time,
#                     },
#                 }
