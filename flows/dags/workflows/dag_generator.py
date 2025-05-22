# This file handles DAG generation logic
from airflow import DAG
from datetime import datetime
from airflow.operators.python import PythonOperator
import importlib
from airflow.models.param import Param

default_param_values = {
    "string": "",
    "integer": 0,
    "number": 0.0,
    "float": 0.0,
    "boolean": False,
    "object": {},
    "array": [],
    "user_id": "",
    "org_id": "",
}

def create_params(params):
    """Create Airflow Param objects from a list of parameter definitions."""
    airflow_params = {}
    for param in params:
        param_name = param["name"]
        param_type = param["type"]
        # Use the 'default' value from the param dict if provided, otherwise use the global default
        default_value = param.get("default", default_param_values.get(param_type))
        airflow_params[param_name] = Param(default_value, type=param_type)
    return airflow_params

def generate_dag_tasks(dag, workflow_config):
    """Create DAG from workflow configuration"""
    print(workflow_config)

    tasks = {}
    processors = importlib.import_module("workflows.processors")


    for node in workflow_config["nodes"]:
        node_id = node["id"]
        node_type = node["data"]["type"].lower()

        if node_type == "annotation":
            continue
        
        processor_func = getattr(processors, node_type, None)
        if not processor_func:
            processor_func = processors.default

        def failure_callback(context):
            context['task_instance'].xcom_push(
                key='error',
                value=f"{context['exception']}"
            )

        tasks[node_id] = PythonOperator(
            task_id=node_id,
            python_callable=processor_func,
            on_failure_callback=failure_callback,
            
            op_kwargs={
                "data": node["data"].get("data", {}),
                "workflow_id": workflow_config["id"],
                "node_id": node_id,
                "connections": [
                    edge
                    for edge in workflow_config["edges"]
                    if edge["target"] == node_id
                ],
            },
        )

    for edge in workflow_config["edges"]:
        tasks[edge["source"]] >> tasks[edge["target"]]

    return dag
