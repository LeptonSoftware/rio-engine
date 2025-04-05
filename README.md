# 🚀 Rio Engine

Rio Engine is a powerful extension of the Supabase stack, adding advanced workflow orchestration and data processing capabilities. It combines Supabase's robust backend-as-a-service with Apache Airflow for workflow management and Smart Flows for custom workflow automation.

## 📋 Overview

Rio Engine extends Supabase with additional services:
- **🛢️ Supabase Core**: Database, Auth, Storage, and Real-time subscriptions
- **⚡ Workflow Management**: Apache Airflow for orchestration
- **🔄 Smart Flows**: Custom workflow automation and API
- **🗺️ Smart Market**: GIS-Based Market Intelligence Tool
- **🔧 Infrastructure**: Traefik for routing and Vector for log aggregation

## 🚀 Getting Started

### ⚙️ Prerequisites
- Docker and Docker Compose
- Environment variables properly configured (see `.env.example`)

### 🏃 Quick Start

1. Clone the repository:
```bash
git clone https://github.com/LeptonSoftware/rio-engine.git
cd rio-engine
```

2. Copy the example environment file and configure it:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Start the services:
```bash
docker compose up -d
```

4. Run Migrations
```bash
supabase db push --db-url=postgres://postgres.rio-engine:postgres@localhost:5432/postgres
```

5. To initialize airflow db
```bash 
docker compose run --entrypoint /bin/bash airflow-webserver
```
And then
```bash
airflow db init
```

6. To add airflow user

```bash
docker exec -it rio-engine-airflow-webserver /bin/sh
```

And then
```bash
airflow users create \
  --username airflow \
  --firstname airflow \
  --lastname airflo \
  --role Admin \
  --email airflow@airflow.com \
  --password airflow
```


## 🏗️ Architecture

### 🛢️ Supabase Services
Rio Engine includes the full Supabase stack:
- `db`: PostgreSQL database with PostGIS extensions
- `studio`: Supabase Studio UI for database management
- `kong`: API Gateway for service routing
- `auth`: Authentication service with JWT support
- `rest`: REST API service for database access
- `realtime`: Real-time subscriptions for live updates
- `storage`: File storage service with S3 compatibility
- `imgproxy`: Image processing service
- `meta`: Database management UI
- `functions`: Edge functions runtime
- `analytics`: Logging and analytics
- `supavisor`: Connection pooling service

### ⚡ Workflow Services
- `airflow-webserver`: Web UI for Airflow (port 8080)
- `airflow-scheduler`: Schedules and triggers DAGs
- `airflow-worker`: Executes DAG tasks
- `airflow-triggerer`: Handles deferred tasks
- `airflow-postgres`: Airflow's metadata database
- `redis`: Message broker for Airflow

### 🔄 Smart Flows
- `smart-flows-postgrest`: REST API for workflow management
- `smart-flows-api`: Core workflow API service

### 🗺️ Smart Market
- `smart-market`: Data marketplace service

### 🔧 Infrastructure
- `traefik`: Reverse proxy and routing
- `vector`: Log aggregation

## 🌐 Exposed Services

### 🛢️ Core Services
| Service | Port | Use Case | Access URL |
|---------|------|----------|------------|
| Supabase Studio | 3000 | Database management, API documentation, and admin interface | http://localhost:3000 |
| Kong API Gateway | 8000 | Main API gateway for all Supabase services | http://localhost:8000 |
| Auth Service | 9999 | Authentication and user management | http://localhost:9999 |
| Storage API | 5000 | File storage and management | http://localhost:5000 |
| Analytics | 4000 | Logging and analytics dashboard | http://localhost:4000 |

### ⚡ Workflow Services
| Service | Port | Use Case | Access URL |
|---------|------|----------|------------|
| Airflow UI | 8080 | Workflow management and monitoring | http://localhost:8080 |
| Smart Flows API | 8007 | Workflow automation and management | http://localhost:8007 |
| Smart Market | 3001 | GIS-based market intelligence interface | http://localhost:3001 |

### 🔧 Infrastructure Services
| Service | Port | Use Case | Access URL |
|---------|------|----------|------------|
| Traefik Dashboard | 8080 | Reverse proxy management and monitoring | http://localhost:8080 |
| PostgreSQL | 5432 | Direct database access | localhost:5432 |

### 🎯 Common Use Cases

1. **📊 Database Management**
   - Use Supabase Studio (port 3000) for database operations
   - Direct PostgreSQL access (port 5432) for advanced database operations
   - REST API through Kong Gateway (port 8000) for application integration

2. **🔐 Authentication & Authorization**
   - Auth Service (port 9999) for user management
   - JWT token generation and validation
   - OAuth provider integration

3. **📁 File Management**
   - Storage API (port 5000) for file uploads and management
   - Image transformations via imgproxy
   - S3-compatible storage operations

4. **⚡ Workflow Management**
   - Airflow UI (port 8080) for workflow monitoring
   - Smart Flows API (port 8007) for workflow automation
   - DAG management and execution

5. **📈 Monitoring & Analytics**
   - Analytics dashboard (port 4000) for system monitoring
   - Traefik dashboard (port 8080) for traffic monitoring
   - Log aggregation and analysis

6. **🔌 API Integration**
   - Kong API Gateway (port 8000) for service routing
   - REST API endpoints for application integration
   - API documentation and testing

## 💻 Development

### 📁 Directory Structure
```
.
├── bin/                    # Utility scripts and tools
├── config/                 # Service configurations
│   ├── airflow/           # Airflow configuration
│   ├── db/                # Database configuration
│   ├── kong/              # Kong API Gateway configuration
│   ├── pooler/            # Connection pooler configuration
│   ├── traefik/           # Traefik reverse proxy configuration
│   └── vector/            # Vector log aggregation configuration
├── data/                   # Persistent data storage
│   ├── airflow-postgres/  # Airflow metadata database
│   ├── db/                # Main PostgreSQL database
│   └── storage/           # File storage
├── flows/                  # Smart Flows definitions
├── functions/             # Supabase Edge Functions
├── logs/                  # Application logs
├── plugins/               # Airflow plugins
└── supabase/             # Supabase configuration and migrations
```

### 🛢️ Working with Supabase

Rio Engine follows Supabase's development patterns:

1. **📊 Database Management**
   - Use Supabase Studio (http://localhost:3000) for database operations
   - SQL Editor for custom queries
   - Table Editor for data management
   - Database backups and migrations

2. **🔐 Authentication**
   - JWT-based authentication
   - Row Level Security (RLS) policies
   - User management through Supabase Auth

3. **🔌 API Access**
   - REST API: `http://localhost:8000/rest/v1`
   - Real-time subscriptions
   - Edge Functions for custom logic

4. **📁 Storage**
   - S3-compatible storage API
   - Image transformations via imgproxy
   - File management through Supabase Studio

### ⚡ Working with Workflows

1. **Adding New DAGs**
   - Place new DAG files in the `dags/` directory
   - DAGs will be automatically loaded by Airflow
   - Use the Airflow UI (http://localhost:8080) for monitoring

2. **Smart Flows Development**
   - Create workflow definitions in the `dags/workflows` directory
   - Use the Smart Flows API for workflow automation
   - Monitor workflows through the Smart Flows UI

### 🛠️ Common Development Tasks

1. **📝 Viewing Logs**
   ```bash
   # View logs for all services
   docker compose logs -f
   
   # View logs for specific service
   docker compose logs -f airflow-webserver
   ```

2. **🌐 Accessing Services**
   - Supabase Studio: http://localhost:3000
   - Airflow UI: http://localhost:8080
   - Smart Market: http://localhost:3001

3. **💾 Database Access**
   ```bash
   # Connect to PostgreSQL
   docker compose exec db psql -U postgres
   
   # Connect to Airflow database
   docker compose exec airflow-postgres psql -U airflow
   ```

4. **🔄 Restarting Services**
   ```bash
   # Restart all services
   docker compose restart
   
   # Restart specific service
   docker compose restart airflow-webserver
   ```

## 🔍 Troubleshooting

1. **🔍 Service Health Checks**
   ```bash
   # Check service status
   docker compose ps
   
   # Check service logs
   docker compose logs <service-name>
   ```

2. **⚠️ Common Issues**
   - If services fail to start, check the logs for specific error messages
   - Ensure all required environment variables are set in `.env`
   - Verify ports are not already in use
   - Check disk space for database and log storage

3. **💾 Database Issues**
   - Check database logs: `docker compose logs db`
   - Verify database connection settings in `.env`
   - Ensure database volumes have proper permissions

## 🤝 Contributing

1. Create a new branch for your changes
2. Make your changes and test thoroughly
3. Submit a pull request with a clear description of changes
4. Ensure all tests pass
5. Update documentation as needed

## 📄 License

[Add your license information here]
