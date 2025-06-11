import os
from psycopg2 import pool
from sqlalchemy import create_engine


db_conn_id = os.getenv('DB_CONN_ID', 'neo360')

def get_db_connection_pool():
    """Create and return a database connection pool."""
    from airflow.hooks.base import BaseHook
    conn = BaseHook.get_connection(db_conn_id)
    return pool.ThreadedConnectionPool(
        minconn=5,
        maxconn=40,
        host=conn.host,
        port=conn.port,
        dbname=conn.schema,
        user=conn.login,
        password=conn.password
    )

def get_db_engine():
    """Create and return a database engine."""
    from airflow.hooks.base import BaseHook
    conn = BaseHook.get_connection(db_conn_id)
    return create_engine(f'postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}?client_encoding=UTF8')

def get_db_engine_open_nw():
    from airflow.hooks.base import BaseHook
    conn = BaseHook.get_connection("open_network")
    return create_engine(f'postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}?client_encoding=UTF8')

def get_db_engine_lepton() : 
    """Create and return a database engine for the lepton database."""
    from airflow.hooks.base import BaseHook
    conn = BaseHook.get_connection('workflows_db')
    return create_engine(f'postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}?client_encoding=UTF8')

def get_db_engine_workflows() : 
    """Create and return a database engine for the workflows database."""
    from airflow.hooks.base import BaseHook
    conn = BaseHook.get_connection('smart_market_db')
    return create_engine(f'postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}?client_encoding=UTF8')
