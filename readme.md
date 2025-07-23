# 🚀 Enhanced Freedcamp MCP Server

A comprehensive **Model Context Protocol (MCP) server** for seamless integration with the **Freedcamp API**. This server provides enterprise-level project management capabilities with advanced filtering, full CRUD operations, and extensive customization options.

## ✨ Features

### 🏗️ **Project Management**
- **List projects** with optional recent project tracking
- **Detailed project information** including users, notifications, and capabilities
- **Create/Update/Delete projects** with user management
- **Manage project teams** (add, update, remove users)
- **Group management** and project organization

### 📋 **Advanced Task Management**
- **Comprehensive task filtering** with 15+ filter options:
  - Status filtering (not started, completed, in progress)
  - User assignment filtering (assigned to, created by)
  - Date range filtering (due dates, creation dates)
  - Priority-based filtering and ordering
  - Custom fields and tags support
- **Full task lifecycle** - Create, Read, Update, Delete
- **Subtask support** with parent-child relationships
- **File attachments** and media management
- **Recurring tasks** with iCalendar format support
- **Pagination and ordering** for large datasets

### 👥 **User Management**
- **Complete user profiles** with detailed information
- **Current user management** and profile updates
- **User task assignments** and workload tracking
- **Email and password management** with secure token handling

### 💬 **Comment System**
- **Add/Update/Delete comments** on tasks and items
- **File attachments** in comments
- **Rich text support** with HTML formatting
- **Comment threading** and user attribution

### 📁 **File Management**
- **File details** and metadata access
- **File deletion** and cleanup
- **Multi-format support** (images, documents, etc.)
- **Temporary file handling** for uploads

## 🛠️ Installation & Setup

### Prerequisites
- Docker and Docker Compose
- Freedcamp API credentials (API Key)

### Quick Start

1. **Clone the repository:**
```bash
git clone https://github.com/yourusername/freedcamp-mcp-server.git
cd freedcamp-mcp-server
```

2. **Set up environment variables:**
```bash
cp env-example.sh .env
# Edit .env and add your Freedcamp credentials
```

3. **Start the services:**
```bash
docker-compose up -d
```

4. **Access the API:**
- **MCP Server**: http://localhost:8000/mcp/
- **OpenAPI Proxy**: http://localhost:8111
- **API Documentation**: http://localhost:8111/docs

## 🔧 Configuration

### Environment Variables

Create a `.env` file with your Freedcamp credentials:

```bash
FREEDCAMP_API_KEY=your_api_key_here
FREEDCAMP_API_SECRET=your_api_secret_here  # Optional for some endpoints
```

### Docker Configuration

The included `docker-compose.yml` provides:
- **Health checks** for service monitoring
- **Restart policies** for reliability
- **Resource limits** for optimal performance
- **Network isolation** for security

## 📚 API Reference

### 🏗️ Project Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_projects` | List all projects with grouping | `include_recent: bool` |
| `get_project_details` | Detailed project information | `project_id: str` |
| `create_project` | Create new project with team | `name, description, color, users...` |
| `update_project` | Update project and manage users | `project_id, name, users_to_add...` |
| `delete_project` | Remove project | `project_id: str` |

### 📋 Task Tools

| Tool | Description | Key Features |
|------|-------------|--------------|
| `get_all_tasks` | Advanced task filtering | 15+ filter options, pagination |
| `get_project_tasks` | Project-specific tasks | Status filtering, custom fields |
| `get_user_tasks` | User assignment tracking | Completed task inclusion |
| `get_task_details` | Complete task information | Comments, files, custom fields |
| `create_task` | Enhanced task creation | Subtasks, files, recurring rules |
| `update_task` | Full task modification | All properties, custom fields |
| `delete_task` | Task removal | Cascade handling |

### 👥 User Tools

| Tool | Description | Capabilities |
|------|-------------|--------------|
| `get_users` | List all workspace users | Full profile data |
| `get_current_user` | Current user information | Profile details |
| `get_user_details` | Specific user data | `user_id: str` |
| `update_current_user` | Profile management | Email, password, timezone |

### 💬 Comment Tools

| Tool | Description | Features |
|------|-------------|----------|
| `add_comment` | Create comments | File attachments, HTML support |
| `update_comment` | Modify comments | Rich text editing |
| `delete_comment` | Remove comments | Clean deletion |

### 📁 File Tools

| Tool | Description | Capabilities |
|------|-------------|--------------|
| `get_file_details` | File information | Metadata, URLs, thumbnails |
| `delete_file` | File removal | Clean deletion |

## 🔍 Usage Examples

### Advanced Task Filtering

```python
# Get overdue high-priority tasks assigned to specific users
await get_all_tasks(
    status_filter=["0", "2"],  # Not started or in progress
    assigned_to_ids=["123", "456"],
    due_date_to="2024-01-01",  # Overdue
    order_by="priority",
    order_direction="desc",
    limit=50
)
```

### Project Team Management

```python
# Add users to a project
await update_project(
    project_id="789",
    users_to_add=[
        {"email": "user@example.com", "first_name": "John", "last_name": "Doe"},
        {"email": "admin@example.com", "first_name": "Jane", "last_name": "Admin"}
    ]
)
```

### Task Creation with Subtasks

```python
# Create a parent task with subtasks and files
parent_task = await create_task(
    title="Main Project Phase",
    project_id="123",
    priority=3,  # High priority
    due_date="2024-12-31"
)

# Create subtask
await create_task(
    title="Subtask 1",
    project_id="123",
    parent_task_id=parent_task["task"]["id"],
    attached_file_ids=[456, 789]
)
```

## 🏗️ Architecture

### Components

- **FastMCP Core**: High-performance MCP server framework
- **Freedcamp API Client**: Secure, authenticated API wrapper
- **MCPO Proxy**: OpenAPI generation and REST interface
- **Docker Environment**: Containerized deployment with health monitoring

### Key Features

- **Robust Error Handling**: Comprehensive error management and logging
- **Data Formatting**: Consistent response structures across all endpoints
- **Security**: Secure credential management and API authentication
- **Performance**: Optimized queries with pagination and filtering
- **Reliability**: Health checks, restart policies, and connection management

## 🐳 Deployment

### Production Deployment

1. **Environment Setup:**
```bash
# Production environment file
FREEDCAMP_API_KEY=prod_api_key
FREEDCAMP_API_SECRET=prod_api_secret
```

2. **Service Scaling:**
```bash
docker-compose up -d --scale freedcamp-fastapi=3
```

3. **Health Monitoring:**
```bash
docker-compose ps  # Check service health
docker-compose logs -f  # Monitor logs
```

### Development Mode

```bash
# Start with hot-reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## 🔧 Development

### Project Structure

```
freedcamp-mcp-server/
├── freedcamp_mcp.py          # Main MCP server implementation
├── docker-compose.yml        # Docker services configuration
├── Dockerfile               # Container definition
├── requirements.txt         # Python dependencies
├── healthcheck.py          # Health monitoring
├── .env                    # Environment variables
├── .gitignore             # Git ignore rules
└── README.md              # This file
```

### Adding New Features

1. **Implement the method** in `FreedcampMCP` class
2. **Add the tool decorator** in `_setup_tools()`
3. **Update documentation** and examples
4. **Test with Docker Compose**

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/freedcamp-mcp-server/issues)
- **Documentation**: [Freedcamp API Docs](https://freedcamp.com/api-docs)
- **MCP Protocol**: [Model Context Protocol](https://github.com/modelcontextprotocol/specification)

## 🎯 Roadmap

- [ ] **File Upload Support**: Direct file upload capabilities
- [ ] **Webhook Integration**: Real-time notifications
- [ ] **Advanced Reporting**: Analytics and reporting tools
- [ ] **Bulk Operations**: Mass task and project management
- [ ] **Custom Field Templates**: Dynamic custom field management
- [ ] **Integration Tests**: Comprehensive test suite
- [ ] **Performance Optimization**: Query caching and optimization

---

**⭐ Star this repository if it helps you manage your Freedcamp projects more effectively!**

Made with ❤️ for the Freedcamp and MCP communities.
