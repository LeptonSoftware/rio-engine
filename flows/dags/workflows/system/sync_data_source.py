from airflow import DAG
from workflows.dag_generator import generate_dag_tasks
import json

from airflow.models.param import Param
workflow_config = {
    "id": "sync_data_source",
    "nodes": [
        {
            "id": "sync_data_source",
            "type": "node",
            "data": {
                "type": "SyncDataSource",
                "data": {
                    "source": "{{ params.source }}"
                }
            }
        }
    ],
    "edges": [
       
    ]
}

with DAG(
    f"sync_data_source",
    description=f"Sync data source",
    schedule_interval=None,
    catchup=False,
    params = {
        "source": Param(type="string", default="")
    },
    tags=[f"workflow", f"v1"],
) as dag:
    generate_dag_tasks(dag, workflow_config)
