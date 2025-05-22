import base64
import datetime
import hashlib
import json
import time
import httpx
from openapi_client.api.x_com_api import XComApi
from openapi_client.api.dag_api import DAGApi
from openapi_client.api.task_instance_api import TaskInstanceApi
from openapi_client.api.dag_run_api import DAGRunApi
import inspect
import importlib
from fastapi import FastAPI, HTTPException, Query, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt  # Use PyJWT instead of jose
from openapi_client.models.dag import DAG
from openapi_client.models.update_dag_run_state import UpdateDagRunState
from openapi_client.models.clear_dag_run import ClearDagRun
from openapi_client.models.dag_run import DAGRun
from pydantic import BaseModel
from supabase import create_client
from openapi_client import ApiClient, Configuration
import sys
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text
from typing import Union, Dict

load_dotenv()

BASE = os.environ.get("BASE", "/base/flows/v1")
api = FastAPI(
    title="Smart Flows API",
    version="1.0.0",
    root_path=f"{BASE}",
)

# Create security scheme
security = HTTPBearer()

# Add this to your environment variables or config
JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"  # or whatever algorithm you're using

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    try:
        token = credentials.credentials
        # Using PyJWT instead of jose.jwt
        payload = jwt.decode(
            token, 
            JWT_SECRET, 
            algorithms=[JWT_ALGORITHM], 
            options={"verify_signature": True, "verify_aud": False}  # Disable audience validation
        )
        
        # Extract user_id from sub field in Supabase token
        user_id = payload.get("sub")
        
        # Extract org_id from app_metadata.organizations in Supabase token
        org_id = None
        if "app_metadata" in payload and "organizations" in payload["app_metadata"]:
            # Get the first organization ID from organizations
            org_ids = list(payload["app_metadata"]["organizations"].keys())
            if org_ids:
                org_id = org_ids[0]
        
        if user_id is None or org_id is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials"
            )
            
        return {"user_id": user_id, "org_id": org_id}
        
    except jwt.PyJWTError as e:  # Changed from JWTError to PyJWTError
        print(f"JWT decode error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token"
        )

class AirflowAPI:
    def __init__(self, url: str, username: str, password: str):
        # build basic auth header value
        basic_auth_header = base64.b64encode(f"{username}:{password}".encode()).decode()
        airflow_api_client = ApiClient(
            Configuration(host=url),
            "Authorization",
            f"Basic {basic_auth_header}",
        )
        self.dags = DAGApi(airflow_api_client)
        self.dag_runs = DAGRunApi(airflow_api_client)
        self.task_instances = TaskInstanceApi(airflow_api_client)
        self.xcom = XComApi(airflow_api_client)


airflow = AirflowAPI(
    os.getenv("AIRFLOW_API_URL"),
    os.getenv("AIRFLOW_API_USERNAME"),
    os.getenv("AIRFLOW_API_PASSWORD"),
)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def table_exists(engine, table_name):
    with engine.connect() as connection:
        table_exists = connection.execute(
            text(f"SELECT to_regclass('workflows.\"{table_name}\"')")
        ).fetchone()
        if table_exists[0]:
            print(f"Table workflows.{table_name} already exists.")
            return True
    return False

def check_for_cache(engine, table_name):
    with engine.connect() as connection:
        cache_valid = connection.execute(
            text("""
                SELECT is_valid 
                FROM workflows.cache_entries 
                WHERE table_name = :table_name
                AND is_valid = true
            """),
            {"table_name": table_name}
        ).scalar()
    return cache_valid

def invalidate_cache(engine, table_name):
    """Invalidate cache for a specific table"""
    with engine.connect() as connection:
        connection.execute(
            text("""
                UPDATE workflows.cache_entries 
                SET is_valid = false, 
                    invalidated_at = NOW() 
                WHERE table_name = :table_name
            """),
            {"table_name": table_name}
        )
        connection.commit()

def get_db_engine_workflows():
    """Create and return a database engine for the workflows database using Airflow connection."""
    conn_url = os.environ.get('WORKFLOWS_DB_CONN_URL')
    return create_engine(f'{conn_url}')

def get_smart_market_db():
    """Create and return a database engine for the smart market database using Airflow connection."""
    conn_url = os.environ.get('SMART_MARKET_DB_CONN_URL')
    return create_engine(f'{conn_url}')

def generate_dag_content(workflow_id, config, version, user_id=None, org_id=None):
    """Generate a DAG file for a workflow"""
    # Add user_id and org_id to the config if provided
    if user_id and org_id:
        if "params" not in config:
            config["params"] = []
        
        # Add user_id parameter
        config["params"].append({
            "name": "user_id",
            "type": "string",
            "default": user_id,
            "value": user_id
        })
        
        # Add org_id parameter
        config["params"].append({
            "name": "org_id",
            "type": "string",
            "default": org_id,
            "value": org_id
        })
    
    dag_content = f"""from airflow import DAG
from workflows.dag_generator import generate_dag_tasks, create_params

import json

workflow_config = json.loads({json.dumps(json.dumps(config))})

with DAG(
    f"workflow_{workflow_id}",
    description=f"DAG for workflow {workflow_id}",
    schedule_interval=None,
    catchup=False,
    params=create_params(workflow_config.get("params", [])),
    tags=[f"workflow", f"v{version}"],
) as dag:
    generate_dag_tasks(dag, workflow_config)
"""
    
    return dag_content



def generate_workflow_dag(workflow_id, config, version, prefix="generated_workflow_", user_id=None, org_id=None):
    """Generate a DAG file for a workflow"""
    dag_content = generate_dag_content(workflow_id, config, version, user_id=user_id, org_id=org_id)

    dag_file = os.path.join(
        os.getenv("GENERATED_AIRFLOW_DAGS_DIR"), f"{prefix}{workflow_id}.py"
    )
    print(dag_file)

    with open(dag_file, "w") as f:
        f.write(dag_content)

def update_workflow(workflow_id: str, version: str, config: dict, prefix="generated_workflow_", user_id=None, org_id=None):
    
    generate_workflow_dag(workflow_id, config, version, prefix=prefix, user_id=user_id, org_id=org_id)

    try:
        # Try to pause the DAG, but don't fail if we can't (it might not exist yet)
        try:
            airflow.dags.patch_dag(
                f"workflow_{workflow_id}",
                DAG(is_paused=True)
            )
        except Exception as e:
            print(f"Could not pause DAG (might be first deployment): {e}")
        
        # Wait for the DAG to be detected with retries
        tries = 0
        max_tries = 20
        while tries < max_tries:
            print(f"Checking if the dag exists and version is updated. Try {tries + 1}")
            try:
                dag_details = airflow.dags.get_dag(f"workflow_{workflow_id}")
                
                # If we can get the DAG details and it has a file token, trigger a reparse
                if dag_details.file_token:
                    airflow.dags.reparse_dag_file(dag_details.file_token)
                
                version_tags = [tag.name for tag in dag_details.tags if tag.name.startswith("v")]
                
                if not version_tags:
                    tries += 1
                    time.sleep(1)
                    continue
                    
                current_version = version_tags[0].split("v")[1]
                print(f"Current version: {current_version}, Expected version: {version}")
                
                if version == current_version:
                    # Unpause the DAG after confirming the update
                    airflow.dags.patch_dag(
                        f"workflow_{workflow_id}",
                        DAG(is_paused=False)
                    )
                    return {"status": version}
                    
            except Exception as e:
                print(f"Error during DAG refresh: {e}")
            
            time.sleep(1)
            tries += 1
            
        raise HTTPException(
            status_code=500,
            detail="Failed to update DAG: Version not updated after maximum retries"
        )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update DAG: {str(e)}"
        )

@api.post("/workflows/{workflow_id}/save")
async def save_workflow(
    workflow_id: str, 
    version: str, 
    config: dict,
    current_user: dict = Depends(get_current_user)
):
    # Get user_id and org_id from the authenticated user
    user_id = current_user["user_id"]
    org_id = current_user["org_id"]
    print(user_id, org_id)
    print("current_user", current_user)
    
    # You can use these IDs for authorization checks or logging
    # For example, you might want to verify the workflow belongs to the org:
    
    # Add your authorization logic here
    # For example:
    # if not verify_workflow_access(workflow_id, org_id):
    #     raise HTTPException(status_code=403, detail="Not authorized to modify this workflow")
    
    return update_workflow(workflow_id, version, config, user_id=user_id, org_id=org_id)


@api.post("/workflows/{workflow_id}/run")
def run_workflow(workflow_id: str, run_id: str, version: str):
    dag_run = DAGRun(
        dag_run_id=run_id,
        dag_id=f"workflow_{workflow_id}",
    )
    created_dag_run = airflow.dag_runs.post_dag_run(
        dag_id=f"workflow_{workflow_id}", dag_run=dag_run
    )
    # dag_run_details = airflow.dag_runs.get_dag_run(dag_id=f"workflow_{workflow_id}", dag_run_id=run_id)
    # print(dag_run_details)
    return {"status": "ok", "dag_run_id": created_dag_run.dag_run_id}


@api.get("/registry/nodes")
def get_registry_nodes():
    sys.path.append(os.path.abspath('/app/nodes'))
    processors = importlib.import_module("nodes.workflows.processors")
    # Get all functions in the module
    functions = [
        name
        for name, _ in inspect.getmembers(processors, inspect.isfunction)
    ]
    print(functions)
    return {"status": "ok", "nodes": functions}

@api.get("/cache/delete/{table_name}")
def delete_cache(table_name: str):
    engine = get_db_engine_workflows()
    if check_for_cache(engine, table_name):
        invalidate_cache(engine, table_name)
        return {"status": "ok"}
    return {"status": "not found"}


@api.get("/dataset/{dataset_id}/count")
def get_dataset_count(dataset_id: str):
    if dataset_id == "null":
        return {"status": "ok", "count": 0}
    engine = get_db_engine_workflows()
    with engine.connect() as connection:
        result = connection.execute(text(f'SELECT COUNT(1) FROM "workflows"."{dataset_id}"'))
        return {"status": "ok", "count": result.fetchone()[0]}

@api.get("/dataset/{dataset_id}/attributes")
def get_dataset_attributes(dataset_id: str):
    return {"status": "ok"}

@api.get("/dataset/{dataset_id}/feature/{feature_id}")
def get_feature_by_id(dataset_id: str, feature_id: str, select: str):
    return {"status": "ok"}

@api.get("/dataset/{dataset_id}/tile")
def get_feature_tile(dataset_id: str, feature_id: str, select: str):
    return {"status": "ok"}

@api.get("/dataset/feature/stats")
def get_feature_stats(dataset_id: str, feature_id: str, select: str):
    return {"status": "ok"}

async def wait_for_dag_to_finish(dag_id: str, dag_run_id: str):
    """Asynchronously wait for a DAG run to complete"""
    import asyncio
    import httpx
    
    # Create async HTTP client
    async with httpx.AsyncClient() as client:
        while True:
            # Get the current state of the DAG run asynchronously
            try:
                # Get the Airflow API URL and auth info
                url = f"{os.getenv('AIRFLOW_API_URL')}/dags/{dag_id}/dagRuns/{dag_run_id}"
                auth = httpx.BasicAuth(
                    os.getenv("AIRFLOW_API_USERNAME"), 
                    os.getenv("AIRFLOW_API_PASSWORD")
                )
                
                # Make async request
                response = await client.get(url, auth=auth)
                response.raise_for_status()
                
                dag_run_data = response.json()
                state = dag_run_data.get('state')
                
                # Check for terminal states
                if state == "success":
                    # Convert to expected format or use original airflow client to get the data
                    # This final call is okay to be synchronous since it's just once at the end
                    return airflow.dag_runs.get_dag_run(dag_id=dag_id, dag_run_id=dag_run_id)
                
                if state == "failed":
                    raise HTTPException(status_code=500, detail="DAG failed")
                
                # Add more terminal states if needed
                if state in ["skipped", "upstream_failed"]:
                    raise HTTPException(status_code=500, detail=f"DAG ended with state: {state}")
                
            except httpx.HTTPError as e:
                print(f"Error checking DAG status: {e}")
                # Don't fail immediately on HTTP errors, retry after delay
            
            # Yield control back to the event loop while waiting
            await asyncio.sleep(2)  # Slightly longer sleep to reduce API load

class DAGFlow(BaseModel):
    nodes: list[dict]
    edges: list[dict]
    params: list[dict]
    id: str
    version: str

class DAGConfig(BaseModel):
    flow: DAGFlow
    args: dict
    outputNode: str
    outputPort: str

param_types = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "dict": "object",
    "list": "array",
}

@api.post("/dataset/sync/create_dag")
def create_dag_from_source(source: dict, output_alias: str = "final") -> DAGConfig:
    """Convert a source configuration into a DAG structure.
    
    Args:
        source (str): JSON string containing the source configuration
        
    Returns:
        dict: DAG structure with nodes, edges, and parameters
    """
    source_config = source
    nodes = []
    edges = []
    vars = {}
    params = []
    node_counter = {}
    source_node_map = {}  # Maps source/transform to node id
    
    # Separate transforms from base source
    transforms = source_config.get('transforms', [])
    base_source = {k: v for k, v in source_config.items() if k != 'transforms'}
    
    def create_node(node_type: str, data: dict, node_id: str = None, output: str = "output") -> dict:
        """Create a new node with unique ID and variable references."""
        node_counter[node_type] = node_counter.get(node_type, 0) + 1
        if node_id is None:
            node_id = f"{node_type}__{node_counter[node_type]}"
        
        # Convert data values to variable references
        node_data = {}
        for k, v in data.items():
            var_name = f"{node_id}__{k}"
            vars[var_name] = v
            params.append({
                "name": var_name,
                "type": param_types[type(v).__name__],
            })
            node_data[k] = var_name
            
        return {
            "id": node_id,
            "data": {
                "type": node_type.replace("_", "").lower(),
                "data": node_data
            },
            "output": output
        }
    
    if "type" in base_source and base_source["type"] != "no preprocessor":
        # Create source node
        source_node = create_node("sync_data_source", {"source": base_source}, node_id=base_source["id"])
        nodes.append(source_node)

        # Store source node mapping
        source_node_map[json.dumps(base_source, sort_keys=True)] = source_node

        terminal_node = source_node["id"]
        terminal_port = "output"
        prev_node = source_node
    
    # Process transforms
    for i, transform in enumerate(transforms):
        # Create transform node
        # Use transform.get("output", "output") to provide a default value if "output" key doesn't exist
        transform_node = create_node(transform["type"], transform["params"], node_id=transform["id"], output=transform.get("output", "output"))
        nodes.append(transform_node)
        
        # Connect inputs
        for input_key, input_value in transform["inputs"].items():
            if isinstance(input_value, dict) and "type" in input_value:
                source_key = json.dumps(input_value, sort_keys=True)
                source_node = source_node_map.get(source_key)
                
                if not source_node:
                    new_source_node = create_node("sync_data_source", {"source": input_value})
                    nodes.append(new_source_node)
                    source_node_map[source_key] = new_source_node
                    source_node = new_source_node
                
                if source_node:
                    edges.append({
                        "source": source_node["id"],
                        "sourceHandle": source_node["output"],
                        "target": transform_node["id"],
                        "targetHandle": input_key
                    })
            elif input_value == "__prev__":
                edges.append({
                    "source": prev_node["id"],
                    "sourceHandle": prev_node["output"],
                    "target": transform_node["id"],
                    "targetHandle": input_key
                })
        
        prev_node = transform_node
        
        if i == len(transforms) - 1:
            terminal_node = transform_node["id"]
            terminal_port = transform_node["output"]
    
    
    nodes.append({
        "id": "final",
        "data": {
            "type": "alias",
            "data": {
                "alias": "final__alias"
            }
        }
    })
    params.append({
        "name": "final__alias",
        "type": "string"
    })
    edges.append({
        "source": terminal_node,
        "sourceHandle": terminal_port,
        "target": "final",
        "targetHandle": "input"
    })
    vars["final__alias"] = output_alias
    # Iterate over all the nodes and remove the output property
    for node in nodes:
        if "output" in node:
            del node["output"]

    return DAGConfig(
        args=vars,
        flow=DAGFlow(
            id="",
            version="1.0",
            nodes=nodes,
            edges=edges,
            params=params
        ),
        outputNode="final",
        outputPort="output"
    )


@api.post("/dataset/sync")
async def sync_data_source(source: str, force: bool = Query(False), current_user: dict = Depends(get_current_user)):
    # Get user_id and org_id from the authenticated user
    user_id = current_user["user_id"]
    org_id = current_user["org_id"]
    print(f"Authenticated user: {user_id}, organization: {org_id}")

    # there is an airflow dag called "sync_data_source"
    # it takes a parameter called "source"
    # we need to trigger that dag with the source parameter
    # the dag_run_id should be based on the hash of the source, so we get 
    # a unique run for each source
    # before triggering the dag, we should check if a run with the same source already exists
    # if it does, we should return the dag_run_id of the existing run
    # if it doesn't, we should trigger the dag and return the dag_run_id of the new run
    # with the dag_run_id, we should poll the status of the run until it is finished succesffully
    try:
        data_source_id = get_fn_hash("smartmarket_layer", json.loads(source))
        dag_config = create_dag_from_source(json.loads(source), output_alias=data_source_id)
        dag_flow = dag_config.flow.model_dump()
        dag_id = get_fn_hash("flow", dag_flow)
        dag_config.flow.id = dag_id
        try:
            dag = airflow.dags.get_dag(f"workflow_{dag_id}")
            if not dag.is_active:
                try:
                    update_workflow(dag_id, "1.0", dag_config.flow.model_dump(), "system_workflow_", user_id=user_id, org_id=org_id)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to update DAG: {str(e)}")
        except HTTPException as e:
            raise e
        except Exception as e:
            update_workflow(dag_id, "1.0", dag_config.flow.model_dump(), "system_workflow_", user_id=user_id, org_id=org_id)

        dag_run_id = get_fn_hash("flow_run", { "params": dag_config.args, "dag_id": dag_id })

        try:
            dag_run = airflow.dag_runs.get_dag_run(dag_id=f"workflow_{dag_id}", dag_run_id=dag_run_id)

            # if the dag_run has failed, we should clear the dag run and trigger a new one
            if dag_run.state == "failed" or force:
                print("Clearing dag run", dag_run.state, force)
                airflow.dag_runs.clear_dag_run(dag_id=f"workflow_{dag_id}", dag_run_id=dag_run_id, clear_dag_run=ClearDagRun(dry_run=False))
                dag_run = airflow.dag_runs.get_dag_run(dag_id=f"workflow_{dag_id}", dag_run_id=dag_run_id)
                print("DAG run", dag_run)
                dag_run = await wait_for_dag_to_finish(f"workflow_{dag_id}", dag_run.dag_run_id)
                return {"status": "ok", "dag_id": dag_id, "dag_run_id": dag_run.dag_run_id, "state": dag_run.state, "exists": False}
            
            return {"status": "ok", "dag_id": dag_id, "dag_run_id": dag_run.dag_run_id, "state": dag_run.state, "exists": True}
        
        except HTTPException as e:
            raise e
        except Exception as e:
            print(e)
            dag_run = DAGRun(dag_id=f"workflow_{dag_id}", dag_run_id=dag_run_id, conf=dag_config.args)
            created_dag_run = airflow.dag_runs.post_dag_run(dag_id=f"workflow_{dag_id}", dag_run=dag_run)
            created_dag_run = await wait_for_dag_to_finish(f"workflow_{dag_id}", created_dag_run.dag_run_id)
            return {"status": "ok", "dag_id": dag_id, "dag_run_id": created_dag_run.dag_run_id, "state": created_dag_run.state, "exists": False}
    except HTTPException as e:
        raise e
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Failed to sync data source: {str(e)}")

def get_fn_hash(fn_name: str, inputs: dict):
    sorted_inputs = {k: inputs[k] for k in sorted(inputs.keys())}
    inputs = json.dumps(sorted_inputs, separators=(',', ':'))
    return hashlib.md5((fn_name + inputs).encode()).hexdigest()


def ensure_dataset_exists(id: str):
    # check if the dataset exists in the database
    db = get_db_engine_workflows()
    with db.connect() as connection:
        # check if the table exists by checking the pg schema
        query = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'workflows' 
            AND table_name = '{id}'
        );"""
        result = connection.execute(text(query))
        return result.fetchone()[0]



class DatasetAttribute(BaseModel):
    name: str
    type: str
    id: str

class DatasetMetadata(BaseModel):
    minzoom: int
    maxzoom: int
    bounds: list[float]
    center: list[float]
    attributes: dict[str, DatasetAttribute]

@api.get("/dataset/{id}/tilejson")
async def get_dataset_tilejson(id: str):    
    ensure_dataset_exists(id)
    # use async http call to get the tilejson from vector tile server
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{os.getenv('SMART_FLOWS_TILER_URL')}/workflows.{id}.json")
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to get tilejson")
        
        tile_data = response.json()
        
        # Transform the fields into a fields object for vector_layers
        fields = {}
        for prop in tile_data["properties"]:
            fields[prop["name"]] = prop["type"]
            
        return {
            "tilejson": "3.0.0",
            "name": tile_data["name"],
            "scheme": "xyz",
            "tiles": [tile_data["tileurl"]],
            "minzoom": tile_data["minzoom"],
            "maxzoom": tile_data["maxzoom"],
            "bounds": tile_data["bounds"],
            "center": tile_data["center"] + [tile_data["minzoom"]],  # Add zoom level to center
            "vector_layers": [
                {
                    "id": tile_data["schema"],
                    "description": f"Data from {tile_data['name']} dataset",
                    "minzoom": tile_data["minzoom"],
                    "maxzoom": tile_data["maxzoom"],
                    "fields": fields
                }
            ]
        }


sm_attr_type_map = {
    "text": "string",
    "int8": "number",
    "float8": "number",
    "bool": "boolean",
    "int4": "number",
}

class NumericAttributeStats(BaseModel):
    type: str = "numeric"
    min: float
    max: float
    mean: float
    count: int

class CategoryAttributeStats(BaseModel):
    type: str = "category"
    values: Dict[str, int]  # Maps category values to their counts
    count: int

@api.get("/dataset/{id}/attribute/{attribute}/stats")
async def get_attribute_stats(id: str, attribute: str):
    ensure_dataset_exists(id)
    db = get_db_engine_workflows()
    
    # First, get the column type
    with db.connect() as connection:
        type_query = text("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'workflows' 
            AND table_name = :table 
            AND column_name = :column
        """)
        data_type = connection.execute(type_query, {"table": id, "column": attribute}).scalar()

        # Handle numeric types
        if data_type in ('integer', 'bigint', 'decimal', 'numeric', 'real', 'double precision'):
            query = text(f'SELECT MIN("{attribute}"), MAX("{attribute}"), AVG("{attribute}"), COUNT(1) FROM workflows."{id}"')
            result = connection.execute(query)
            row = result.fetchone()
            return NumericAttributeStats(min=row[0], max=row[1], mean=row[2], count=row[3])
        
        # Handle categorical/string types
        else:
            query = text(f'''
                SELECT "{attribute}", COUNT(1) 
                FROM workflows."{id}" 
                WHERE "{attribute}" IS NOT NULL 
                GROUP BY "{attribute}" 
                ORDER BY COUNT(1) DESC
            ''')
            result = connection.execute(query)
            values = {str(row[0]): row[1] for row in result}
            total_count = sum(values.values())
            return CategoryAttributeStats(values=values, count=total_count)
    
@api.get("/dataset/{id}/metadata")
async def get_dataset_metadata(id: str):    
    ensure_dataset_exists(id)
    # use async http call to get the tilejson from vector tile server
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{os.getenv('SMART_FLOWS_TILER_URL')}/workflows.{id}.json")
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to get tilejson")
        
        tile_data = response.json()
        
        # Transform the fields into a fields object for vector_layers
        fields = {}
        for prop in tile_data["properties"]:
            fields[prop["name"]] = {
                "id": prop["name"],
                "description": "",
                "name": snake_to_title(prop["name"]),
                "type": sm_attr_type_map[prop["type"]]
            }
            
        return {
            "minzoom": tile_data["minzoom"],
            "maxzoom": tile_data["maxzoom"],
            "bounds": tile_data["bounds"],
            "center": tile_data["center"] + [tile_data["minzoom"]],  # Add zoom level to center
            "attributes": fields
        }

def snake_to_title(name: str):
    return " ".join(word.capitalize() for word in name.split("_"))

@api.get("/health")
def health():
    return {"status": "okays"}


@api.get("/cache/get/{table_name}")
def get_cache(table_name: str):
    engine = get_db_engine_workflows()
    if check_for_cache(engine, table_name):
        return {"status": "ok", "is_cached": True}
    return {"status": "not found", "is_cached": False}

def get_formatted_timestamp():
    """Generate a formatted timestamp for backup files"""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def decode_project_data(encoded_data: str) -> dict:
    """Decode base64 encoded project data back to dictionary"""
    try:
        # Input validation
        if not isinstance(encoded_data, str):
            raise ValueError(f"Expected string input, got {type(encoded_data)}")
        
        if not encoded_data:
            raise ValueError("Encoded data is empty")
        
        # Decode base64 to bytes
        try:
            decoded_bytes = base64.b64decode(encoded_data)
        except Exception as e:
            print(f"Base64 decode error: {str(e)}")
            raise ValueError(f"Invalid base64 data: {str(e)}")

        # Convert bytes to string
        try:
            decoded_str = decoded_bytes.decode('utf-8')
        except UnicodeDecodeError as e:
            print(f"UTF-8 decode error: {str(e)}")
            raise ValueError("Invalid UTF-8 encoding in decoded data")

        # Parse JSON
        try:
            decoded_json = json.loads(decoded_str)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            raise ValueError(f"Invalid JSON format: {str(e)}")

        # Validate decoded data is a dictionary
        if not isinstance(decoded_json, dict):
            print(f"Invalid data type: {type(decoded_json)}")
            raise ValueError(f"Expected dictionary, got {type(decoded_json)}")

        return decoded_json

    except Exception as e:
        print(f"Error decoding project data: {str(e)}")
        print(f"Type of encoded_data: {type(encoded_data)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to decode project data: {str(e)}"
        )

class ProjectUpdateRequest(BaseModel):
    """Request model for project update endpoint"""
    encoded_data: str
    workflow_id: str = None
    is_node_update: bool = False
    save_tab_id: str = None
@api.post("/project/{project_id}/update")
async def update_project_json(
    project_id: str,
    request: ProjectUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update project.json with locking mechanism and backup"""
    # Get user_id and org_id from the authenticated user
    user_id = current_user["user_id"]
    org_id = current_user["org_id"]
    print(f"Authenticated user: {user_id}, organization: {org_id}")

    # Decode the project data
    try:
        project_data = decode_project_data(request.encoded_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid project data format: {str(e)}"
        )

    engine = get_smart_market_db()

    # Generate unique identifiers for lock
    unique_lock_id = f"project_{project_id}_{int(time.time() * 1000)}"
    unique_locker_id = f"update_project_{user_id}"
    
    print(project_id)

    # Try to acquire lock
    def acquire_lock():
        if request.is_node_update:
            return True
        connection = None
        try:
            connection = engine.connect()
            print(f"Attempting to acquire lock for project_id: {project_id}, workflow_id: {request.workflow_id}")
            # Check if any active locks exist for this project
            query = text("""
                SELECT COUNT(*) 
                FROM process_locks 
                WHERE project_id = :project_id
                """)
            print(f"Executing query: {query}")
            print(f"With parameters: project_id={project_id}")
            
            result = connection.execute(
                query,
                {"project_id": project_id}
            ).scalar()

            print(f"Current active locks for project: {result}")

            if result > 0:
                print(f"Lock acquisition failed - {result} existing locks found")
                return False

            # Create new lock with optional workflow_id
            if request.workflow_id:
                insert_query = text("""
                    INSERT INTO process_locks (lock_id, locked_by, project_id, workflow_id)
                    VALUES (:lock_id, :locked_by, :project_id, :workflow_id)
                    """)
                params = {
                    "lock_id": unique_lock_id,
                    "locked_by": unique_locker_id,
                    "project_id": project_id,
                    "workflow_id": request.workflow_id
                }
                print(f"Creating workflow lock with params: {params}")
            else:
                insert_query = text("""
                    INSERT INTO process_locks (lock_id, locked_by, project_id, workflow_id)
                    VALUES (:lock_id, :locked_by, :project_id, 'project_update')
                    """)
                params = {
                    "lock_id": unique_lock_id,
                    "locked_by": unique_locker_id,
                    "project_id": project_id
                }
                print(f"Creating frontend lock with params: {params}")
            
            connection.execute(insert_query, params)
            connection.commit()
            print(f"Lock successfully acquired with lock_id: {unique_lock_id}")
            return True
        except Exception as e:
            print(f"Error acquiring lock: {str(e)}")
            print(f"Error type: {type(e)}")
            if connection and not connection.closed:
                connection.rollback()
            return False
        finally:
            if connection and not connection.closed:
                print("Closing connection in acquire_lock")
                connection.close()

    # Release lock
    def release_lock():
        if request.is_node_update:
            return
        connection = None
        try:
            connection = engine.connect()
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
            connection.commit()
            print("Lock released")
        except Exception as e:
            print(f"Error releasing lock: {e}")
            if connection and not connection.closed:
                connection.rollback()
        finally:
            if connection and not connection.closed:
                print("Closing connection in release_lock")
                connection.close()

    # Wait for lock with timeout
    max_attempts = 30  # 30 seconds timeout
    attempt = 0
    while not acquire_lock():
        time.sleep(1)
        attempt += 1
        print(f"Attempt {attempt} of {max_attempts}")
        if attempt >= max_attempts:
            raise HTTPException(status_code=503, detail="Timeout waiting for lock")

    try:
        # Initialize Supabase client
        supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

        # Add timestamp to ensure we get fresh data
        timestamp = int(time.time() * 1000)
        
        # Create backup of current project.json
        backup_timestamp = get_formatted_timestamp()
        backup_path = f"{project_id}/{backup_timestamp}.json"
        
        # First check if the original file exists
        try:
            # Try to get the original file first
            original_file = supabase.storage.from_("projects").download(
                f"{project_id}/project.json"
            )
            if not original_file:
                print(f"Warning: No existing project.json found for project {project_id}")
            else:
                # Only attempt backup if original file exists
                try:
                    result = supabase.storage.from_("projects").copy(
                        f"{project_id}/project.json",
                        backup_path
                    )
                    if result.get("error"):
                        print(f"Warning: Failed to create backup: {result['error']}")
                except Exception as e:
                    print(f"Warning: Failed to create backup: {str(e)}")
        except Exception as e:
            print(f"Warning: Failed to check original file: {str(e)}")

        # Update project.json in Supabase
        try:
            print(f"Attempting to update project.json for project {project_id}")
            
            # Ensure we have valid JSON string with consistent formatting
            print(f"Project data type: {type(project_data)}")
            updated_json_str = json.dumps(project_data, separators=(',', ':'), ensure_ascii=False)
            print(f"JSON string type: {type(updated_json_str)}")
            
            print(f"Uploading content size: {len(updated_json_str)} bytes")
            
            # Create file path
            file_path = f"{project_id}/project.json"
            
            try:
                # Simple direct upload of the JSON string
                supabase.storage.from_("projects").update(
                f"{project_id}/project.json?t={timestamp}", updated_json_str.encode("utf-8")
                )
                
                print(f"Successfully updated project.json for project {project_id}")

                # Insert/Update project data in the projects table
                try:
                    connection = engine.connect()
                    
                    # Check if project already exists
                    check_query = text("""
                        SELECT id FROM public.projects 
                        WHERE id = :project_id
                    """)
                    existing_project = connection.execute(check_query, {"project_id": project_id}).scalar()
                    
                    if existing_project:
                        # Build update query dynamically based on save_tab_id
                        update_fields = [
                            "tinybase = :project_data",
                            "updated_at = NOW()",
                            "saved_by = :saved_by",
                            "organization_id = :org_id"
                        ]
                        params = {
                            "project_data": updated_json_str,
                            "saved_by": user_id,
                            "org_id": org_id,
                            "project_id": project_id
                        }
                        
                        if request.save_tab_id:
                            update_fields.append("save_tab_id = :save_tab_id")
                            params["save_tab_id"] = request.save_tab_id
                            
                        update_query = text("""
                            UPDATE public.projects 
                            SET {}
                            WHERE id = :project_id
                        """.format(", ".join(update_fields)))
                        
                        connection.execute(update_query, params)
                    else:
                        # Build insert query dynamically based on save_tab_id
                        insert_fields = ["id", "tinybase", "user_id", "organization_id", "visibility", "saved_by"]
                        value_fields = [":project_id", ":project_data", ":user_id", ":org_id", ":visibility", ":saved_by"]
                        params = {
                            "project_id": project_id,
                            "project_data": updated_json_str,
                            "user_id": user_id,
                            "org_id": org_id,
                            "visibility": 'private',
                            "saved_by": user_id
                        }
                        
                        if request.save_tab_id:
                            insert_fields.append("save_tab_id")
                            value_fields.append(":save_tab_id")
                            params["save_tab_id"] = request.save_tab_id
                            
                        insert_query = text("""
                            INSERT INTO public.projects 
                            ({}) 
                            VALUES 
                            ({})
                        """.format(
                            ", ".join(insert_fields),
                            ", ".join(value_fields)
                        ))
                        
                        connection.execute(insert_query, params)
                    
                    connection.commit()
                    print(f"Successfully updated projects table for project {project_id}")
                    
                except Exception as e:
                    print(f"Error updating projects table: {str(e)}")
                    connection.rollback()
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to update projects table: {str(e)}"
                    )

                return {
                    "status": "ok",
                    "backup_path": backup_path if original_file else None
                }
                
            except Exception as e:
                print(f"Upload error: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to update project.json: {str(e)}"
                )

        except Exception as e:
            print(f"Error updating project.json: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update project.json: {str(e)}"
            )

    except Exception as e:
        print(f"Unexpected error in update_project_json: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update project.json: {str(e)}"
        )
    finally:
        # Always release the lock when done
        release_lock()
        
class NodeRunRequest(BaseModel):
    node_type: str
    node_params: dict
    input_data: dict
    workflow_id: str = None  # Optional: to track which workflow this node belongs to
    node_id: str

def infer_param_type(value):
    """Infer parameter type from value"""
    if isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "number"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    else:
        return "string"

@api.post("/workflow/run-node")
async def run_single_node(request: NodeRunRequest):
    """Run a single node with provided input data asynchronously"""
    
    current_user = {
        "user_id": "1",
        "org_id": "1"
    }
    
    # Define data source node types
    DATA_SOURCE_NODES = {
        "smartmarketlayer", 
        "boundaries",
        "syncdatasource",
        "upload"
    }
    
    print(request.node_type)
    
    # Filter out null parameters
    filtered_params = {k: v for k, v in request.node_params.items() if v is not None}
    
    # For data source nodes, create a simpler DAG configuration
    if request.node_type.lower() in DATA_SOURCE_NODES:
        # Create parameters list with correct types
        params = [
            {
                "name": f"{request.node_id}__{k}",
                "type": infer_param_type(v)
            } 
            for k, v in filtered_params.items()
        ]
        
        # Add other required parameters
        params.extend([
            {"name": "final__alias", "type": "string"},
            {"name": "workflow_id", "type": "string", "default": request.workflow_id, "value": request.workflow_id},
            {"name": "user_id", "type": "string", "default": current_user["user_id"], "value": current_user["user_id"]},
            {"name": "org_id", "type": "string", "default": current_user["org_id"], "value": current_user["org_id"]}
        ])

        flow = {
            "nodes": [
                {
                    "id": f"{request.node_id}",
                    "data": {
                        "type": request.node_type.lower(),
                        "data": {k: f"{request.node_id}__{k}" for k in filtered_params.keys()}
                    }
                },
                {
                    "id": "final",
                    "data": {
                        "type": "alias",
                        "data": {
                            "alias": "final__alias"
                        }
                    }
                }
            ],
            "edges": [
                {
                    "source": f"{request.node_id}",
                    "sourceHandle": "output",
                    "target": "final",
                    "targetHandle": "input"
                }
            ],
            "params": params,
            "version": "1.0"
        }
        
        # Generate DAG ID
        dag_id = get_fn_hash("flow", flow)
        flow["id"] = dag_id
        
        # Create args dictionary with proper value handling
        args = {
            **{f"{request.node_id}__{k}": v for k, v in filtered_params.items()},
            "final__alias": get_fn_hash(request.node_id, filtered_params)
        }
        
        # Create DAGConfig object
        dag_config = DAGConfig(
            flow=DAGFlow(**flow),
            args=args,
            outputNode="final",
            outputPort="output"
        )
        
    else:
        # For transform nodes, handle null values
        # Filter out null parameters before creating the transform
        dag_config = {
            "transforms": [{
                "id": request.node_id,
                "type": request.node_type,
                "params": {**filtered_params, "workflow_id": request.workflow_id},
                "inputs": request.input_data.get("inputs", {}),
                "output": request.input_data.get("output", "output")
            }],
            "type": "no preprocessor"
        }
        
        # Generate unique IDs for this run
        data_source_id = get_fn_hash(request.node_id, dag_config)
        
        # Create and run the DAG
        dag_config = create_dag_from_source(dag_config, output_alias=data_source_id)
        dag_id = get_fn_hash("flow", dag_config.flow.model_dump())
        dag_config.flow.id = dag_id

    try:
        # Create/update the DAG
        update_workflow(
            dag_id, 
            "1.0", 
            dag_config.flow.model_dump(), 
            "system_workflow_", 
            user_id=current_user["user_id"], 
            org_id=current_user["org_id"]
        )

        # Add timestamp to make run ID unique
        import time
        timestamp = int(time.time() * 1000)  # millisecond timestamp
        
        # Generate run ID with timestamp
        dag_run_id = get_fn_hash("flow_run", {
            "params": dag_config.args,
            "dag_id": dag_id,
            "timestamp": timestamp  # Add timestamp to make it unique
        })

        try:
            # Try to get existing DAG run
            existing_run = airflow.dag_runs.get_dag_run(
                dag_id=f"workflow_{dag_id}", 
                dag_run_id=dag_run_id
            )
            
            # If run exists and is in a failed state, clear it
            if existing_run and existing_run.state in ["failed", "upstream_failed"]:
                airflow.dag_runs.clear_dag_run(
                    dag_id=f"workflow_{dag_id}",
                    dag_run_id=dag_run_id,
                    clear_dag_run=ClearDagRun(dry_run=False)
                )
        except Exception:
            # If run doesn't exist or can't be fetched, proceed with creation
            pass

        # Create a better tracking/logging mechanism
        import asyncio
        
        # Run the synchronous Airflow API calls in a thread pool
        dag_run = DAGRun(
            dag_id=f"workflow_{dag_id}", 
            dag_run_id=dag_run_id, 
            conf=dag_config.args
        )
        
        # Use run_in_executor to prevent blocking
        def trigger_dag():
            try:
                return airflow.dag_runs.post_dag_run(
                    dag_id=f"workflow_{dag_id}", 
                    dag_run=dag_run
                )
            except Exception as e:
                if "already exists" in str(e):
                    return airflow.dag_runs.get_dag_run(
                        dag_id=f"workflow_{dag_id}", 
                        dag_run_id=dag_run_id
                    )
                raise e
        
        # Run the synchronous operation in a thread pool
        created_dag_run = await asyncio.get_event_loop().run_in_executor(None, trigger_dag)
        
        # Create record in database
        insert_query = """
            INSERT INTO workflow_node_runs (
                workflow_id,
                node_type,
                node_params,
                input_data,
                dag_id,
                dag_run_id,
                state,
                data_source_id,
                is_cached,
                user_id,
                org_id,
                node_id,
                original_params
            ) VALUES (
                :workflow_id, 
                :node_type, 
                :node_params, 
                :input_data, 
                :dag_id, 
                :dag_run_id, 
                :state, 
                :data_source_id, 
                :is_cached, 
                :user_id, 
                :org_id,
                :node_id,
                :original_params
            ) RETURNING id;
        """
        
        engine = get_smart_market_db()
        connection = None
        try:
            connection = engine.connect()
            result = connection.execute(
                text(insert_query),
                {
                    "workflow_id": request.workflow_id,
                    "node_type": request.node_type,
                    "node_params": json.dumps(filtered_params),
                    "input_data": json.dumps(request.input_data),
                    "dag_id": dag_id,
                    "dag_run_id": dag_run_id,
                    "state": "success",
                    "data_source_id": args["final__alias"] if request.node_type.lower() in DATA_SOURCE_NODES else data_source_id,
                    "is_cached": False,
                    "user_id": current_user["user_id"],
                    "org_id": current_user["org_id"],
                    "node_id": request.node_id,
                    "original_params": json.dumps(request.node_params)
                }
            )
            connection.commit()
            run_record_id = result.scalar()
        except Exception as e:
            if connection:
                connection.rollback()
            # If we encounter a database schema error (column might not exist yet)
            if "column \"original_params\" of relation" in str(e):
                # Fallback to original query without the new column
                try:
                    connection = engine.connect()
                    fallback_query = """
                        INSERT INTO workflow_node_runs (
                            workflow_id,
                            node_type,
                            node_params,
                            input_data,
                            dag_id,
                            dag_run_id,
                            state,
                            data_source_id,
                            is_cached,
                            user_id,
                            org_id,
                            node_id
                        ) VALUES (
                            :workflow_id, 
                            :node_type, 
                            :node_params, 
                            :input_data, 
                            :dag_id, 
                            :dag_run_id, 
                            :state, 
                            :data_source_id, 
                            :is_cached, 
                            :user_id, 
                            :org_id,
                            :node_id
                        ) RETURNING id;
                    """
                    result = connection.execute(
                        text(fallback_query),
                        {
                            "workflow_id": request.workflow_id,
                            "node_type": request.node_type,
                            "node_params": json.dumps(filtered_params),
                            "input_data": json.dumps(request.input_data),
                            "dag_id": dag_id,
                            "dag_run_id": dag_run_id,
                            "state": "success",
                            "data_source_id": args["final__alias"] if request.node_type.lower() in DATA_SOURCE_NODES else data_source_id,
                            "is_cached": False,
                            "user_id": current_user["user_id"],
                            "org_id": current_user["org_id"],
                            "node_id": request.node_id
                        }
                    )
                    connection.commit()
                    run_record_id = result.scalar()
                except Exception as nested_e:
                    if connection:
                        connection.rollback()
                    raise nested_e
            else:
                raise e
        finally:
            if connection:
                connection.close()

        return {
            "status": "ok",
            "dag_id": dag_id,
            "dag_run_id": created_dag_run.dag_run_id,
            "state": "success",
            "data_source_id": args["final__alias"] if request.node_type.lower() in DATA_SOURCE_NODES else data_source_id,
            "cached": False,
            "run_id": run_record_id
        }

    except Exception as e:
        # If we have a run_record_id, update the record with error
        if 'run_record_id' in locals():
            connection = None
            try:
                connection = engine.connect()
                connection.execute(
                    text("""
                        UPDATE workflow_node_runs
                        SET state = :state,
                            error_message = :error_message,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = :id
                    """),
                    {
                        "state": "failed",
                        "error_message": str(e),
                        "id": run_record_id
                    }
                )
                connection.commit()
            except:
                pass  # Don't let error updating cause another error
            finally:
                if connection:
                    connection.close()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to run node: {str(e)}"
        )