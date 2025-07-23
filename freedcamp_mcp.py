#!/usr/bin/env python3
"""
Freedcamp MCP Server
A Model Context Protocol server for interacting with the Freedcamp API
"""

import asyncio
import json
import logging
import time
import hmac
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlencode

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "https://freedcamp.com/api/v1"

class FreedcampConfig(BaseModel):
    """Configuration for Freedcamp API"""
    api_key: str = Field(description="Freedcamp API key")
    api_secret: str = Field(description="Freedcamp API secret")

class FreedcampMCP:
    def __init__(self, config: FreedcampConfig):
        self.config = config
        self.client = httpx.AsyncClient()
        
        # Create FastMCP server
        self.mcp = FastMCP(
            name="freedcamp-mcp",
            instructions="""
            Freedcamp Project Management MCP Server
            
            IMPORTANT WORKFLOW INSTRUCTIONS:
            
            1. ALWAYS start by getting project context:
               - Use get_projects() to see available projects
               - Use get_project_details(project_id) for specific project info
               - Never assume project IDs - always look them up first
            
            2. For task operations, follow this sequence:
               - Get projects first to identify correct project_id
               - Use get_project_tasks(project_id) to see existing tasks
               - Use get_users() to find correct user IDs for assignments
               - Then create/update tasks with proper IDs
            
            3. When creating tasks:
               - ALWAYS specify project_id (required)
               - Look up user IDs before assigning tasks
               - Use proper date format: YYYY-MM-DD
               - Check project permissions before creating
            
            4. For user management:
               - Use get_users() to find user IDs before task assignment
               - Use get_current_user() to understand current user context
               - User IDs are required for task assignments, not names
            
            5. Error handling:
               - If you get a "project not found" error, use get_projects() first
               - If user assignment fails, verify user ID with get_users()
               - Always validate IDs exist before using them in operations
            
            Remember: This system requires explicit ID lookups - never guess or assume IDs exist.
            """
        )
        self._setup_tools()
    
    def _generate_auth(self) -> Dict[str, str]:
        """Generate authentication parameters"""
        timestamp = int(time.time())
        
        # Create HMAC using SHA1
        message = f"{self.config.api_key}{timestamp}".encode()
        secret = self.config.api_secret.encode()
        hash_value = hmac.new(secret, message, hashlib.sha1).hexdigest()
        
        return {
            "timestamp": str(timestamp),
            "hash": hash_value
        }
    
    def _get_headers(self) -> Dict[str, str]:
        """Get common headers for API requests"""
        return {
            "X-API-KEY": self.config.api_key,
            "Content-Type": "application/x-www-form-urlencoded"
        }
    
    async def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """Make an authenticated request to Freedcamp API"""
        url = f"{BASE_URL}/{endpoint}"
        auth_params = self._generate_auth()
        
        if params:
            params.update(auth_params)
        else:
            params = auth_params
        
        headers = self._get_headers()
        
        try:
            if method == "GET":
                response = await self.client.get(url, params=params, headers=headers)
            elif method == "POST":
                # For POST requests, Freedcamp expects data wrapped in 'data' parameter
                if data:
                    form_data = {"data": json.dumps(data)}
                    response = await self.client.post(url, params=params, data=form_data, headers=headers)
                else:
                    response = await self.client.post(url, params=params, headers=headers)
            elif method == "DELETE":
                response = await self.client.delete(url, params=params, headers=headers)
            
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
    
    def _format_timestamp(self, ts: Union[int, str]) -> str:
        """Convert Unix timestamp to readable format"""
        if ts:
            try:
                timestamp = int(ts) if isinstance(ts, str) else ts
                return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                return ""
        return ""
    
    def _format_date(self, ts: Union[int, str]) -> str:
        """Convert Unix timestamp to date format"""
        if ts:
            try:
                timestamp = int(ts) if isinstance(ts, str) else ts
                return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                return ""
        return ""

    # ====== SUMMARY FORMATTING METHODS ======
    
    def _format_task_summary(self, task: Dict) -> Dict:
        """Format a task with only essential fields for summary display"""
        return {
            "id": task["id"],
            "title": task["title"],
            "status": task.get("status_title", "Not Started"),
            "priority": task.get("priority_title", "None"),
            "assigned_to": task.get("assigned_to_fullname", "Unassigned"),
            "due_date": self._format_date(task.get("due_ts", 0)) or "No due date",
            "project_id": task.get("project_id"),
            "url": task.get("url", ""),
            "comments": task.get("comments_count", 0),
            "can_edit": task.get("can_edit", False)
        }
    
    def _format_project_summary(self, project: Dict) -> Dict:
        """Format a project with only essential fields for summary display"""
        return {
            "id": project["id"],
            "name": project["project_name"],
            "group": project.get("group_name", "Ungrouped"),
            "active": project.get("f_active", True),
            "tasks_count": project.get("tasks_count", 0),
            "users_count": len(project.get("users", [])),
            "url": project.get("url", "")
        }
    
    def _format_user_summary(self, user: Dict) -> Dict:
        """Format a user with only essential fields for summary display"""
        return {
            "user_id": user["user_id"],
            "name": user["full_name"],
            "email": user.get("email", "")
        }
    
    def _create_tasks_summary_text(self, tasks: List[Dict], total_count: int = None, project_name: str = None) -> str:
        """Create a human-readable summary of tasks optimized for token efficiency"""
        if not tasks:
            return "📋 No tasks found"
        
        # Group tasks by status and priority
        by_status = {"Not Started": [], "In Progress": [], "Completed": []}
        urgent_tasks = []
        overdue_tasks = []
        due_soon = []
        
        today = datetime.now().date()
        
        for task in tasks:
            status = task.get("status", "Not Started")
            if status not in by_status:
                by_status[status] = []
            by_status[status].append(task)
            
            # Check urgency
            due_date_str = task.get("due_date")
            if due_date_str and due_date_str != "No due date":
                try:
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                    days_until_due = (due_date - today).days
                    
                    if days_until_due < 0:
                        overdue_tasks.append(task)
                    elif days_until_due <= 2:
                        due_soon.append(task)
                    
                    if task.get("priority") in ["High", "Critical"]:
                        urgent_tasks.append(task)
                except ValueError:
                    pass
        
        # Build summary text
        lines = []
        
        # Header
        context = f" in {project_name}" if project_name else ""
        count_text = f" ({len(tasks)}" + (f" of {total_count}" if total_count else "") + ")"
        lines.append(f"📋 Tasks{context}{count_text}")
        lines.append("")
        
        # Critical items first
        if overdue_tasks:
            lines.append("🚨 OVERDUE:")
            for task in overdue_tasks[:3]:
                lines.append(f"  • {task['title']} → {task['assigned_to']} (due {task['due_date']})")
            if len(overdue_tasks) > 3:
                lines.append(f"  ... and {len(overdue_tasks) - 3} more overdue")
            lines.append("")
        
        if due_soon:
            lines.append("⏰ DUE SOON:")
            for task in due_soon[:3]:
                lines.append(f"  • {task['title']} → {task['assigned_to']} (due {task['due_date']})")
            if len(due_soon) > 3:
                lines.append(f"  ... and {len(due_soon) - 3} more due soon")
            lines.append("")
        
        if urgent_tasks:
            urgent_not_shown = [t for t in urgent_tasks if t not in overdue_tasks and t not in due_soon]
            if urgent_not_shown:
                lines.append("🔥 HIGH PRIORITY:")
                for task in urgent_not_shown[:3]:
                    lines.append(f"  • {task['title']} → {task['assigned_to']} ({task['priority']})")
                if len(urgent_not_shown) > 3:
                    lines.append(f"  ... and {len(urgent_not_shown) - 3} more high priority")
                lines.append("")
        
        # Status breakdown
        for status, status_tasks in by_status.items():
            if status_tasks:
                emoji = {"Not Started": "📝", "In Progress": "⚡", "Completed": "✅"}.get(status, "📌")
                lines.append(f"{emoji} {status.upper()} ({len(status_tasks)}):")
                
                # Show first few tasks
                shown = 0
                for task in status_tasks:
                    if shown >= 3:
                        break
                    if task not in overdue_tasks and task not in due_soon and task not in urgent_tasks:
                        due_text = f" (due {task['due_date']})" if task['due_date'] != "No due date" else ""
                        lines.append(f"  • {task['title']} → {task['assigned_to']}{due_text}")
                        shown += 1
                
                if len(status_tasks) > shown:
                    lines.append(f"  ... and {len(status_tasks) - shown} more")
                lines.append("")
        
        # Quick actions
        lines.append("💡 QUICK ACTIONS:")
        lines.append("  • get_task_details(task_id) - See full task details")
        if project_name:
            lines.append("  • get_project_tasks(project_id, include_details=true) - See all details")
        lines.append("  • get_user_tasks(user_id) - See user's tasks")
        
        return "\n".join(lines)
    
    def _create_projects_summary_text(self, grouped_projects: List[Dict]) -> str:
        """Create a human-readable summary of projects optimized for token efficiency"""
        if not grouped_projects:
            return "📂 No projects found"
        
        lines = []
        total_projects = sum(len(group.get("projects", [])) for group in grouped_projects if "projects" in group)
        lines.append(f"📂 Projects ({total_projects} total)")
        lines.append("")
        
        for group_data in grouped_projects:
            if "projects" not in group_data:
                continue
                
            group_name = group_data["group"]
            projects = group_data["projects"]
            
            lines.append(f"📁 {group_name} ({len(projects)} projects):")
            
            for project in projects[:5]:  # Limit to 5 per group
                status = "🟢" if project.get("active") else "🔴"
                task_info = f" ({project['tasks_count']} tasks)" if project.get('tasks_count') else ""
                user_info = f" • {project['users_count']} users" if project.get('users_count') else ""
                lines.append(f"  {status} {project['name']}{task_info}{user_info}")
            
            if len(projects) > 5:
                lines.append(f"  ... and {len(projects) - 5} more projects")
            lines.append("")
        
        lines.append("💡 QUICK ACTIONS:")
        lines.append("  • get_project_details(project_id) - See project details")
        lines.append("  • get_project_tasks(project_id) - See project tasks")
        
        return "\n".join(lines)

    # ====== PROJECT MANAGEMENT ======
    
    async def get_all_projects(self, include_recent: bool = False) -> List[Dict]:
        """Get all projects grouped by their group name"""
        params = {}
        if include_recent:
            params["f_recent_projects_ids"] = "1"
            
        response = await self._make_request("GET", "projects", params)
        
        grouped_projects = {}
        recent_projects = []
        
        if response.get("data"):
            # Handle recent project IDs
            if include_recent and response["data"].get("recent_project_ids"):
                recent_projects = response["data"]["recent_project_ids"]
            
            if response["data"].get("projects"):
                for project in response["data"]["projects"]:
                    group_name = project.get("group_name", "Ungrouped")
                    
                    simplified_project = {
                        "id": project["id"],
                        "name": project["project_name"],
                        "description": project.get("project_description", ""),
                        "color": project.get("project_color", ""),
                        "group_name": group_name,
                        "group_id": project.get("group_id", ""),
                        "active": project.get("f_active", True),
                        "created_at": self._format_timestamp(project.get("created_ts", 0)),
                        "url": project.get("url", ""),
                        "users_count": len(project.get("users", [])),
                        "tasks_count": project.get("tasks_count", 0)
                    }
                    
                    if group_name not in grouped_projects:
                        grouped_projects[group_name] = []
                    grouped_projects[group_name].append(simplified_project)
        
        result = [{"group": group, "projects": projects} for group, projects in grouped_projects.items()]
        
        if include_recent and recent_projects:
            result.append({"recent_project_ids": recent_projects})
            
        return result
    
    async def get_project_details(self, project_id: str) -> Dict:
        """Get detailed information about a specific project"""
        response = await self._make_request("GET", f"projects/{project_id}")
        
        if response.get("data") and response["data"].get("projects"):
            project = response["data"]["projects"][0]
            
            # Format project users
            users = []
            if project.get("users"):
                for user in project["users"]:
                    users.append({
                        "user_id": user["user_id"],
                        "full_name": user["full_name"],
                        "email": user.get("email"),
                        "role_id": user.get("role_id"),
                        "role_name": user.get("role_name"),
                        "avatar_url": user.get("avatar_url")
                    })
            
            # Format notifications if present
            notifications = []
            if project.get("notifications"):
                for notif in project["notifications"]:
                    notifications.append({
                        "id": notif.get("id"),
                        "type": notif.get("type"),
                        "message": notif.get("message"),
                        "created_at": self._format_timestamp(notif.get("created_ts", 0))
                    })
            
            return {
                "id": project["id"],
                "name": project["project_name"],
                "description": project.get("project_description", ""),
                "color": project.get("project_color", ""),
                "group_name": project.get("group_name", ""),
                "group_id": project.get("group_id", ""),
                "active": project.get("f_active", True),
                "created_at": self._format_timestamp(project.get("created_ts", 0)),
                "url": project.get("url", ""),
                "users": users,
                "notifications": notifications,
                "can_add_tasks": project.get("f_can_add_tasks", False),
                "advanced_subtasks": project.get("f_subtasks_adv", False),
                "todo_view_type": project.get("todo_view_type", "default")
            }
        
        return {}
    
    async def create_project(self, 
                           name: str,
                           description: Optional[str] = None,
                           color: Optional[str] = None,
                           group_id: Optional[str] = None,
                           group_name: Optional[str] = None,
                           todo_view_type: str = "default",
                           users_to_add: Optional[List[Dict]] = None) -> Dict:
        """Create a new project"""
        data = {
            "project_name": name,
            "todo_view_type": todo_view_type
        }
        
        if description:
            data["project_description"] = description
        if color:
            data["project_color"] = color
        if group_id:
            data["group_id"] = group_id
        if group_name:
            data["group_name"] = group_name
        
        # Add users if provided
        if users_to_add:
            data["changed_users"] = {"added": users_to_add}
        
        response = await self._make_request("POST", "projects", data=data)
        
        if response.get("data"):
            return {
                "success": True,
                "project": response["data"],
                "message": "Project created successfully"
            }
        
        return {"success": False, "message": "Failed to create project"}
    
    async def update_project(self,
                           project_id: str,
                           name: Optional[str] = None,
                           description: Optional[str] = None,
                           color: Optional[str] = None,
                           group_id: Optional[str] = None,
                           group_name: Optional[str] = None,
                           active: Optional[bool] = None,
                           users_to_add: Optional[List[Dict]] = None,
                           users_to_update: Optional[List[Dict]] = None,
                           users_to_delete: Optional[List[Dict]] = None,
                           only_update_users: bool = False) -> Dict:
        """Update an existing project"""
        data = {}
        
        if not only_update_users:
            if name:
                data["project_name"] = name
            if description is not None:
                data["project_description"] = description
            if color:
                data["project_color"] = color
            if group_id:
                data["group_id"] = group_id
            if group_name:
                data["group_name"] = group_name
            if active is not None:
                data["f_active"] = active
        else:
            data["f_only_users_update"] = True
        
        # Handle user changes
        changed_users = {}
        if users_to_add:
            changed_users["added"] = users_to_add
        if users_to_update:
            changed_users["updated"] = users_to_update
        if users_to_delete:
            changed_users["deleted"] = users_to_delete
        
        if changed_users:
            data["changed_users"] = changed_users
        
        response = await self._make_request("POST", f"projects/{project_id}", data=data)
        
        if response.get("data"):
            return {
                "success": True,
                "project": response["data"],
                "message": "Project updated successfully"
            }
        
        return {"success": False, "message": "Failed to update project"}
    
    async def delete_project(self, project_id: str) -> Dict:
        """Delete a project"""
        response = await self._make_request("DELETE", f"projects/{project_id}")
        
        if response.get("data"):
            return {
                "success": True,
                "message": "Project deleted successfully"
            }
        
        return {"success": False, "message": "Failed to delete project"}

    # ====== TASK MANAGEMENT ======
    
    def _format_task(self, task: Dict, include_custom_fields: bool = False) -> Dict:
        """Format a task object with consistent structure"""
        formatted_task = {
            "id": task["id"],
            "title": task["title"],
            "description": task.get("description", ""),
            "status": task.get("status"),
            "status_title": task.get("status_title", ""),
            "priority": task.get("priority", 0),
            "priority_title": task.get("priority_title", ""),
            "assigned_to_id": task.get("assigned_to_id"),
            "assigned_to_fullname": task.get("assigned_to_fullname", ""),
            "created_by_id": task.get("created_by_id"),
            "project_id": task.get("project_id"),
            "task_group_id": task.get("task_group_id"),
            "task_group_name": task.get("task_group_name"),
            "created_at": self._format_timestamp(task.get("created_ts", 0)),
            "due_date": self._format_date(task.get("due_ts", 0)),
            "start_date": self._format_date(task.get("start_ts", 0)),
            "completed_at": self._format_timestamp(task.get("completed_ts", 0)) if task.get("completed_ts") else None,
            "comments_count": task.get("comments_count", 0),
            "files_count": task.get("files_count", 0),
            "url": task.get("url", ""),
            "order": task.get("order", 0),
            "recurring_rule": task.get("r_rule", ""),
            "archived_list": task.get("f_archived_list", False),
            "hierarchy_level": task.get("h_level", 0),
            "parent_id": task.get("h_parent_id", ""),
            "top_parent_id": task.get("h_top_id", ""),
            "advanced_subtask": task.get("f_adv_subtask", False),
            "can_delete": task.get("can_delete", False),
            "can_edit": task.get("can_edit", False),
            "can_assign": task.get("can_assign", False),
            "can_progress": task.get("can_progress", False),
            "can_comment": task.get("can_comment", False)
        }
        
        # Add custom fields if requested and available
        if include_custom_fields and task.get("custom_fields"):
            formatted_task["custom_fields"] = task["custom_fields"]
            formatted_task["cf_tpl_id"] = task.get("cf_tpl_id")
        
        # Add tags if available
        if task.get("tags"):
            formatted_task["tags"] = task["tags"]
        
        # Add comments and files if available (for single task requests)
        if task.get("comments"):
            formatted_task["comments"] = [self._format_comment(comment) for comment in task["comments"]]
        
        if task.get("files"):
            formatted_task["files"] = task["files"]
        
        return formatted_task
    
    def _format_comment(self, comment: Dict) -> Dict:
        """Format a comment object"""
        return {
            "id": comment["id"],
            "description": comment["description"],
            "description_processed": comment.get("description_processed", ""),
            "created_by_id": comment["created_by_id"],
            "created_at": self._format_timestamp(comment.get("created_ts", 0)),
            "user_full_name": comment.get("user_full_name", ""),
            "likes_count": comment.get("likes_count", 0),
            "liked": comment.get("f_liked", False),
            "unread": comment.get("f_unread", False),
            "can_edit": comment.get("can_edit", False),
            "files": comment.get("files", []),
            "url": comment.get("url", "")
        }
    
    async def get_all_tasks(self, 
                          limit: int = 200, 
                          offset: int = 0,
                          status_filter: Optional[List[str]] = None,
                          assigned_to_ids: Optional[List[str]] = None,
                          created_by_ids: Optional[List[str]] = None,
                          due_date_from: Optional[str] = None,
                          due_date_to: Optional[str] = None,
                          created_date_from: Optional[str] = None,
                          created_date_to: Optional[str] = None,
                          include_archived: bool = False,
                          lists_status: str = "active",
                          order_by: Optional[str] = None,
                          order_direction: str = "asc",
                          include_custom_fields: bool = False,
                          include_tags: bool = False) -> Dict:
        """Get all tasks with advanced filtering and pagination"""
        params = {
            "limit": str(limit),
            "offset": str(offset)
        }
        
        # Status filter (0=not started, 1=completed, 2=in progress)
        if status_filter:
            for status in status_filter:
                params[f"status[]"] = status
        
        # Assignment filters
        if assigned_to_ids:
            for user_id in assigned_to_ids:
                params[f"assigned_to_id[]"] = user_id
        
        if created_by_ids:
            for user_id in created_by_ids:
                params[f"created_by_id[]"] = user_id
        
        # Date filters (YYYY-MM-DD format)
        if due_date_from:
            params["due_date[from]"] = due_date_from
        if due_date_to:
            params["due_date[to]"] = due_date_to
        if created_date_from:
            params["created_date[from]"] = created_date_from
        if created_date_to:
            params["created_date[to]"] = created_date_to
        
        # Archive and list status
        if include_archived:
            params["f_with_archived"] = "1"
        params["lists_status"] = lists_status
        
        # Ordering (priority, due_date)
        if order_by:
            params[f"order[{order_by}]"] = order_direction
        
        # Custom fields and tags
        if include_custom_fields:
            params["f_cf"] = "1"
        if include_tags:
            params["f_include_tags"] = "1"
        
        response = await self._make_request("GET", "tasks", params)
        
        tasks = []
        meta = {}
        cf_templates = []
        
        if response.get("data"):
            # Extract metadata
            if response["data"].get("meta"):
                meta = response["data"]["meta"]
            
            # Extract custom field templates
            if response["data"].get("cf_templates"):
                cf_templates = response["data"]["cf_templates"]
            
            # Format tasks
            if response["data"].get("tasks"):
                for task in response["data"]["tasks"]:
                    formatted_task = self._format_task(task, include_custom_fields)
                    tasks.append(formatted_task)
        
        return {
            "tasks": tasks,
            "meta": meta,
            "cf_templates": cf_templates
        }
    
    async def get_project_tasks(self, project_id: str, 
                              status: Optional[str] = None,
                              limit: int = 200,
                              offset: int = 0,
                              include_custom_fields: bool = False,
                              include_tags: bool = False) -> Dict:
        """Get tasks for a specific project with enhanced filtering"""
        params = {
            "limit": str(limit),
            "offset": str(offset)
        }
        
        # Add status filter if provided
        if status == "incomplete":
            params["status[]"] = "0"
        elif status == "complete":
            params["status[]"] = "1"
        elif status == "in_progress":
            params["status[]"] = "2"
        
        # Custom fields and tags
        if include_custom_fields:
            params["f_cf"] = "1"
        if include_tags:
            params["f_include_tags"] = "1"
        
        response = await self._make_request("GET", f"tasks?project_id={project_id}", params)
        
        tasks = []
        meta = {}
        cf_templates = []
        
        if response.get("data"):
            # Extract metadata
            if response["data"].get("meta"):
                meta = response["data"]["meta"]
            
            # Extract custom field templates
            if response["data"].get("cf_templates"):
                cf_templates = response["data"]["cf_templates"]
            
            # Format tasks
            if response["data"].get("tasks"):
                for task in response["data"]["tasks"]:
                    formatted_task = self._format_task(task, include_custom_fields)
                    tasks.append(formatted_task)
        
        return {
            "tasks": tasks,
            "meta": meta,
            "cf_templates": cf_templates
        }
    
    async def get_user_tasks(self, user_id: str, 
                           include_completed: bool = False,
                           limit: int = 200,
                           offset: int = 0,
                           include_custom_fields: bool = False) -> Dict:
        """Get tasks assigned to a specific user with enhanced filtering"""
        params = {
            "assigned_to_id[]": user_id,
            "limit": str(limit),
            "offset": str(offset)
        }
        
        # Filter out completed tasks if not requested
        if not include_completed:
            params["status[]"] = ["0", "2"]  # not started and in progress
        
        if include_custom_fields:
            params["f_cf"] = "1"
        
        response = await self._make_request("GET", "tasks", params)
        
        tasks = []
        meta = {}
        cf_templates = []
        
        if response.get("data"):
            # Extract metadata
            if response["data"].get("meta"):
                meta = response["data"]["meta"]
            
            # Extract custom field templates
            if response["data"].get("cf_templates"):
                cf_templates = response["data"]["cf_templates"]
            
            # Format tasks
            if response["data"].get("tasks"):
                for task in response["data"]["tasks"]:
                    formatted_task = self._format_task(task, include_custom_fields)
                    tasks.append(formatted_task)
        
        return {
            "tasks": tasks,
            "meta": meta,
            "cf_templates": cf_templates
        }
    
    async def get_task_details(self, task_id: str, include_custom_fields: bool = True) -> Dict:
        """Get detailed information about a task including comments and files"""
        params = {}
        
        if include_custom_fields:
            params["f_cf"] = "1"
        
        response = await self._make_request("GET", f"tasks/{task_id}", params)
        
        if response.get("data") and response["data"].get("tasks"):
            task = response["data"]["tasks"][0]
            return self._format_task(task, include_custom_fields)
        
        return {}
    
    async def create_task(self, 
                         title: str,
                         project_id: str,
                         description: Optional[str] = None,
                         task_group_id: Optional[str] = None,
                         priority: Optional[int] = None,
                         assigned_to_id: Optional[str] = None,
                         due_date: Optional[str] = None,
                         start_date: Optional[str] = None,
                         recurring_rule: Optional[str] = None,
                         parent_task_id: Optional[str] = None,
                         attached_file_ids: Optional[List[int]] = None,
                         custom_fields: Optional[List[Dict]] = None,
                         cf_template_id: Optional[str] = None) -> Dict:
        """Create a new task with enhanced options"""
        data = {
            "title": title,
            "project_id": project_id
        }
        
        if description:
            data["description"] = description
        if task_group_id:
            data["task_group_id"] = task_group_id
        if priority is not None:
            data["priority"] = str(priority)
        if assigned_to_id:
            data["assigned_to_id"] = assigned_to_id
        if due_date:
            data["due_date"] = due_date
        if start_date:
            data["start_date"] = start_date
        if recurring_rule:
            data["r_rule"] = recurring_rule
        if parent_task_id:
            data["h_parent_id"] = parent_task_id
        if attached_file_ids:
            data["attached_ids"] = attached_file_ids
        
        # Handle custom fields
        if custom_fields and cf_template_id:
            data["cf_tpl_id"] = cf_template_id
            data["custom_fields"] = custom_fields
        
        response = await self._make_request("POST", "tasks", data=data)
        
        if response.get("data"):
            return {
                "success": True,
                "task": response["data"],
                "message": "Task created successfully"
            }
        
        return {"success": False, "message": "Failed to create task"}
    
    async def update_task(self,
                         task_id: str,
                         title: Optional[str] = None,
                         description: Optional[str] = None,
                         task_group_id: Optional[str] = None,
                         priority: Optional[int] = None,
                         assigned_to_id: Optional[str] = None,
                         due_date: Optional[str] = None,
                         start_date: Optional[str] = None,
                         status: Optional[int] = None,
                         parent_task_id: Optional[str] = None,
                         attached_file_ids: Optional[List[int]] = None,
                         custom_fields: Optional[List[Dict]] = None,
                         cf_template_id: Optional[str] = None) -> Dict:
        """Update an existing task"""
        data = {}
        
        if title:
            data["title"] = title
        if description is not None:
            data["description"] = description
        if task_group_id:
            data["task_group_id"] = task_group_id
        if priority is not None:
            data["priority"] = str(priority)
        if assigned_to_id is not None:
            data["assigned_to_id"] = assigned_to_id
        if due_date is not None:
            data["due_date"] = due_date
        if start_date is not None:
            data["start_date"] = start_date
        if status is not None:
            data["status"] = str(status)
        if parent_task_id is not None:
            data["h_parent_id"] = parent_task_id
        if attached_file_ids:
            data["attached_ids"] = attached_file_ids
        
        # Handle custom fields
        if custom_fields is not None:
            if cf_template_id is not None:
                data["cf_tpl_id"] = cf_template_id
            data["custom_fields"] = custom_fields
        
        response = await self._make_request("POST", f"tasks/{task_id}", data=data)
        
        if response.get("data"):
            return {
                "success": True,
                "task": response["data"],
                "message": "Task updated successfully"
            }
        
        return {"success": False, "message": "Failed to update task"}
    
    async def delete_task(self, task_id: str) -> Dict:
        """Delete a task"""
        response = await self._make_request("DELETE", f"tasks/{task_id}")
        
        if response.get("data"):
            return {
                "success": True,
                "message": "Task deleted successfully"
            }
        
        return {"success": False, "message": "Failed to delete task"}
    
    # ====== USER MANAGEMENT ======
    
    async def get_all_users(self) -> List[Dict]:
        """Get all users in the Freedcamp workspace"""
        response = await self._make_request("GET", "users")
        
        users = []
        if response.get("data") and response["data"].get("users"):
            for user in response["data"]["users"]:
                users.append({
                    "user_id": user["user_id"],
                    "full_name": user["full_name"],
                    "first_name": user.get("first_name", ""),
                    "last_name": user.get("last_name", ""),
                    "email": user.get("email"),
                    "avatar_url": user.get("avatar_url"),
                    "timezone": user.get("timezone")
                })
        
        return users
    
    async def get_current_user(self) -> Dict:
        """Get current user information"""
        response = await self._make_request("GET", "users/current")
        
        if response.get("data") and response["data"].get("users"):
            user = response["data"]["users"][0]
            return {
                "user_id": user["user_id"],
                "full_name": user["full_name"],
                "first_name": user.get("first_name", ""),
                "last_name": user.get("last_name", ""),
                "email": user.get("email"),
                "avatar_url": user.get("avatar_url"),
                "timezone": user.get("timezone")
            }
        
        return {}
    
    async def get_user_details(self, user_id: str) -> Dict:
        """Get detailed information about a specific user"""
        response = await self._make_request("GET", f"users/{user_id}")
        
        if response.get("data") and response["data"].get("users"):
            user = response["data"]["users"][0]
            return {
                "user_id": user["user_id"],
                "full_name": user["full_name"],
                "first_name": user.get("first_name", ""),
                "last_name": user.get("last_name", ""),
                "email": user.get("email"),
                "avatar_url": user.get("avatar_url"),
                "timezone": user.get("timezone")
            }
        
        return {}
    
    async def update_current_user(self,
                                 email: Optional[str] = None,
                                 password: Optional[str] = None,
                                 first_name: Optional[str] = None,
                                 last_name: Optional[str] = None,
                                 confirmation_password: Optional[str] = None,
                                 timezone: Optional[str] = None) -> Dict:
        """Update current user information"""
        data = {}
        
        if email:
            data["email"] = email
        if password:
            data["password"] = password
        if first_name:
            data["first_name"] = first_name
        if last_name:
            data["last_name"] = last_name
        if confirmation_password:
            data["confirmation_password"] = confirmation_password
        if timezone:
            data["timezone"] = timezone
        
        response = await self._make_request("POST", "users/current", data=data)
        
        if response.get("data"):
            result = {
                "success": True,
                "user": response["data"].get("users", [{}])[0] if response["data"].get("users") else {},
                "message": "User updated successfully"
            }
            
            # Include new token if provided (happens when email/password changes)
            if response["data"].get("token"):
                result["new_token"] = response["data"]["token"]
                result["message"] += " - New authentication token provided"
            
            return result
        
        return {"success": False, "message": "Failed to update user"}
    
    # ====== COMMENT MANAGEMENT ======
    
    async def add_comment(self,
                         item_id: str,
                         app_id: str,
                         description: str,
                         attached_file_ids: Optional[List[int]] = None) -> Dict:
        """Add a comment to an item (task, file, etc.)"""
        data = {
            "item_id": item_id,
            "app_id": app_id,
            "description": description
        }
        
        if attached_file_ids:
            data["attached_ids"] = attached_file_ids
        
        response = await self._make_request("POST", "comments", data=data)
        
        if response.get("data") and response["data"].get("comments"):
            comment = response["data"]["comments"][0]
            return {
                "success": True,
                "comment": self._format_comment(comment),
                "message": "Comment added successfully"
            }
        
        return {"success": False, "message": "Failed to add comment"}
    
    async def update_comment(self, comment_id: str, description: str) -> Dict:
        """Update an existing comment"""
        data = {"description": description}
        
        response = await self._make_request("POST", f"comments/{comment_id}", data=data)
        
        if response.get("data") and response["data"].get("comments"):
            comment = response["data"]["comments"][0]
            return {
                "success": True,
                "comment": self._format_comment(comment),
                "message": "Comment updated successfully"
            }
        
        return {"success": False, "message": "Failed to update comment"}
    
    async def delete_comment(self, comment_id: str) -> Dict:
        """Delete a comment"""
        response = await self._make_request("DELETE", f"comments/{comment_id}")
        
        if response.get("data"):
            return {
                "success": True,
                "message": "Comment deleted successfully"
            }
        
        return {"success": False, "message": "Failed to delete comment"}
    
    # ====== FILE MANAGEMENT ======
    
    async def get_file_details(self, file_id: str) -> Dict:
        """Get detailed information about a file"""
        response = await self._make_request("GET", f"files/{file_id}")
        
        if response.get("data") and response["data"].get("files"):
            file_info = response["data"]["files"][0]
            return {
                "id": file_info["id"],
                "name": file_info["name"],
                "url": file_info.get("url", ""),
                "thumb_url": file_info.get("thumb_url"),
                "size": file_info["size"],
                "file_type": file_info["file_type"],
                "project_id": file_info["project_id"],
                "item_id": file_info["item_id"],
                "comment_id": file_info["comment_id"],
                "user_id": file_info["user_id"],
                "is_image": file_info.get("f_image", False),
                "is_temporary": file_info.get("f_temporary", False),
                "created_at": self._format_timestamp(file_info.get("created_ts", 0)),
                "location": file_info.get("location", "storage")
            }
        
        return {}
    
    async def delete_file(self, file_id: str) -> Dict:
        """Delete a file"""
        response = await self._make_request("DELETE", f"files/{file_id}")
        
        if response.get("data"):
            return {
                "success": True,
                "message": "File deleted successfully"
            }
        
        return {"success": False, "message": "Failed to delete file"}
    
    def _setup_tools(self):
        """Setup FastMCP tools using decorators"""
        
        # ====== WORKFLOW GUIDANCE TOOL ======
        
        @self.mcp.tool
        async def get_workflow_help(task_type: str = "general") -> str:
            """Get workflow instructions and best practices for using this Freedcamp MCP server
            
            Args:
                task_type: Type of task you want help with (general, create_task, assign_users, project_setup)
            """
            workflows = {
                "general": """
                GENERAL WORKFLOW FOR FREEDCAMP MCP SERVER:
                
                1. DISCOVERY PHASE (Always start here):
                   → get_projects() - See all available projects
                   → get_users() - See all available users
                   → get_current_user() - Understand current user context
                
                2. PROJECT SELECTION:
                   → Use project names from get_projects() to identify target project
                   → get_project_details(project_id) for detailed project info
                   → NEVER assume project IDs - always look them up
                
                3. TASK OPERATIONS:
                   → get_project_tasks(project_id) to see existing tasks
                   → get_user_tasks(user_id) to see user workload
                   → create_task() with proper project_id and user IDs
                
                4. ID MANAGEMENT:
                   → Project IDs: from get_projects()
                   → User IDs: from get_users() (use user_id field, not names)
                   → Task IDs: from get_project_tasks() or task creation response
                
                CRITICAL: Always look up IDs before using them!
                """,
                
                "create_task": """
                TASK CREATION WORKFLOW:
                
                1. PREREQUISITES:
                   → get_projects() - Find target project
                   → get_project_details(project_id) - Verify permissions
                   → get_users() - Find assignee user IDs
                
                2. TASK CREATION:
                   → create_task(title, project_id, ...)
                   → REQUIRED: title, project_id
                   → OPTIONAL: description, assigned_to_id, due_date, priority
                
                3. VALIDATION:
                   → get_task_details(task_id) to confirm creation
                   → Check task appears in get_project_tasks(project_id)
                
                EXAMPLE SEQUENCE:
                1. projects = get_projects()
                2. users = get_users()  
                3. create_task(title="New Task", project_id="123", assigned_to_id="456")
                """,
                
                "assign_users": """
                USER ASSIGNMENT WORKFLOW:
                
                1. GET USER INFORMATION:
                   → get_users() - Get all available users
                   → Note: Use 'user_id' field for assignments, NOT 'full_name'
                
                2. FIND TARGET USER:
                   → Search by full_name or email in get_users() response
                   → Extract the corresponding user_id
                
                3. ASSIGNMENT OPTIONS:
                   → assigned_to_id: specific user ID
                   → assigned_to_id: "0" (unassigned)
                   → assigned_to_id: "-1" (assigned to everyone)
                
                4. VERIFY ASSIGNMENT:
                   → get_user_tasks(user_id) to see user's tasks
                   → get_task_details(task_id) to confirm assignment
                
                CRITICAL: Never use user names directly - always convert to user_id first!
                """,
                
                "project_setup": """
                PROJECT SETUP WORKFLOW:
                
                1. DISCOVERY:
                   → get_projects() - See existing projects and groups
                   → get_current_user() - Understand your permissions
                
                2. PROJECT CREATION:
                   → create_project(name, description, ...)
                   → Consider: group_name, color, users_to_add
                
                3. TEAM SETUP:
                   → get_users() - Find team members
                   → update_project(project_id, users_to_add=[...])
                
                4. TASK STRUCTURE:
                   → get_project_details(project_id) - Confirm setup
                   → create_task() - Add initial tasks
                
                5. VERIFICATION:
                   → get_project_tasks(project_id) - Verify task creation
                   → get_project_details(project_id) - Check team membership
                """
            }
            
            return workflows.get(task_type, workflows["general"])
        
        # ====== PROJECT TOOLS ======
        
        @self.mcp.tool
        async def get_projects(include_recent: bool = False, include_details: bool = False) -> str:
            """Get all Freedcamp projects grouped by their group name
            
            🔥 START HERE: This is usually the FIRST tool you should call when working with projects!
            🔥 TOKEN OPTIMIZED: Returns concise summaries by default for better performance
            Use this to discover available projects and get their IDs for other operations.
            
            Args:
                include_recent: Include recently visited project IDs (default: False)
                include_details: Include full project details (default: False - shows summary)
            """
            try:
                result = await self.get_all_projects(include_recent)
                
                if include_details:
                    return json.dumps(result, indent=2)
                else:
                    # Create summary version
                    summary_text = self._create_projects_summary_text(result)
                    return summary_text
                    
            except Exception as e:
                logger.error(f"Error getting projects: {e}")
                return f"❌ Error: {str(e)}"
        
        @self.mcp.tool(name="get_project_details")
        async def get_project_details_tool(project_id: str) -> str:
            """Get detailed information about a specific project
            
            Args:
                project_id: The project ID
            """
            try:
                result = await self.get_project_details(project_id)
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error getting project details: {e}")
                return f"Error: {str(e)}"
        
        @self.mcp.tool(name="create_project")
        async def create_project_tool(
            name: str,
            description: Optional[str] = None,
            color: Optional[str] = None,
            group_id: Optional[str] = None,
            group_name: Optional[str] = None,
            todo_view_type: str = "default",
            users_to_add: Optional[List[Dict]] = None
        ) -> str:
            """Create a new project in Freedcamp
            
            Args:
                name: Project name
                description: Project description (optional)
                color: Project color (optional)
                group_id: Group ID where the project will be created (optional)
                group_name: Group name where the project will be created (optional)
                todo_view_type: Type of todo view (default: "default")
                users_to_add: List of users to add to the project (optional)
            """
            try:
                result = await self.create_project(
                    name=name,
                    description=description,
                    color=color,
                    group_id=group_id,
                    group_name=group_name,
                    todo_view_type=todo_view_type,
                    users_to_add=users_to_add
                )
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error creating project: {e}")
                return f"Error: {str(e)}"
        
        @self.mcp.tool(name="update_project")
        async def update_project_tool(
            project_id: str,
            name: Optional[str] = None,
            description: Optional[str] = None,
            color: Optional[str] = None,
            group_id: Optional[str] = None,
            group_name: Optional[str] = None,
            active: Optional[bool] = None,
            users_to_add: Optional[List[Dict]] = None,
            users_to_update: Optional[List[Dict]] = None,
            users_to_delete: Optional[List[Dict]] = None,
            only_update_users: bool = False
        ) -> str:
            """Update an existing project in Freedcamp
            
            Args:
                project_id: The project ID to update
                name: New project name (optional)
                description: New project description (optional)
                color: New project color (optional)
                group_id: New group ID (optional)
                group_name: New group name (optional)
                active: New active status (optional)
                users_to_add: List of users to add (optional)
                users_to_update: List of users to update (optional)
                users_to_delete: List of users to delete (optional)
                only_update_users: If True, only update users (default: False)
            """
            try:
                result = await self.update_project(
                    project_id=project_id,
                    name=name,
                    description=description,
                    color=color,
                    group_id=group_id,
                    group_name=group_name,
                    active=active,
                    users_to_add=users_to_add,
                    users_to_update=users_to_update,
                    users_to_delete=users_to_delete,
                    only_update_users=only_update_users
                )
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error updating project: {e}")
                return f"Error: {str(e)}"
        
        @self.mcp.tool(name="delete_project")
        async def delete_project_tool(project_id: str) -> str:
            """Delete a project from Freedcamp
            
            Args:
                project_id: The project ID to delete
            """
            try:
                result = await self.delete_project(project_id)
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error deleting project: {e}")
                return f"Error: {str(e)}"
        
        # ====== TASK TOOLS ======
        
        @self.mcp.tool(name="get_all_tasks")
        async def get_all_tasks_tool(
            limit: int = 200,
            offset: int = 0,
            status_filter: Optional[List[str]] = None,
            assigned_to_ids: Optional[List[str]] = None,
            created_by_ids: Optional[List[str]] = None,
            due_date_from: Optional[str] = None,
            due_date_to: Optional[str] = None,
            created_date_from: Optional[str] = None,
            created_date_to: Optional[str] = None,
            include_archived: bool = False,
            lists_status: str = "active",
            order_by: Optional[str] = None,
            order_direction: str = "asc",
            include_custom_fields: bool = False,
            include_tags: bool = False
        ) -> str:
            """Get all tasks with advanced filtering and pagination
            
            Args:
                limit: Maximum number of tasks to return (default: 200)
                offset: Offset for pagination (default: 0)
                status_filter: Filter by status (0=not started, 1=completed, 2=in progress)
                assigned_to_ids: Filter by assigned user IDs
                created_by_ids: Filter by creator user IDs
                due_date_from: Filter by due date from (YYYY-MM-DD)
                due_date_to: Filter by due date to (YYYY-MM-DD)
                created_date_from: Filter by creation date from (YYYY-MM-DD)
                created_date_to: Filter by creation date to (YYYY-MM-DD)
                include_archived: Include archived projects (default: False)
                lists_status: Task list status (active, archived, all)
                order_by: Order by field (priority, due_date)
                order_direction: Order direction (asc, desc)
                include_custom_fields: Include custom fields data
                include_tags: Include tags data
            """
            try:
                result = await self.get_all_tasks(
                    limit=limit, offset=offset, status_filter=status_filter,
                    assigned_to_ids=assigned_to_ids, created_by_ids=created_by_ids,
                    due_date_from=due_date_from, due_date_to=due_date_to,
                    created_date_from=created_date_from, created_date_to=created_date_to,
                    include_archived=include_archived, lists_status=lists_status,
                    order_by=order_by, order_direction=order_direction,
                    include_custom_fields=include_custom_fields, include_tags=include_tags
                )
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error getting all tasks: {e}")
                return f"Error: {str(e)}"
        
        @self.mcp.tool(name="get_project_tasks")
        async def get_project_tasks_tool(
            project_id: str,
            status: Optional[str] = None,
            limit: int = 50,
            offset: int = 0,
            include_custom_fields: bool = False,
            include_tags: bool = False,
            include_details: bool = False
        ) -> str:
            """Get tasks for a specific project with enhanced filtering
            
            🔥 TOKEN OPTIMIZED: Returns concise summaries by default for better performance
            
            Args:
                project_id: The project ID
                status: Filter by status (incomplete, complete, in_progress)
                limit: Maximum number of tasks to return (default: 50, reduced from 200)
                offset: Offset for pagination (default: 0)
                include_custom_fields: Include custom fields data
                include_tags: Include tags data
                include_details: Include full task details (default: False - shows summary)
            """
            try:
                result = await self.get_project_tasks(
                    project_id=project_id, status=status, limit=limit, offset=offset,
                    include_custom_fields=include_custom_fields, include_tags=include_tags
                )
                
                if include_details:
                    return json.dumps(result, indent=2)
                else:
                    # Get project name for context
                    project_name = f"Project {project_id}"  # Default
                    try:
                        project_details = await self.get_project_details(project_id)
                        if project_details.get("name"):
                            project_name = project_details["name"]
                    except:
                        pass
                    
                    # Create summary version
                    tasks = result.get("tasks", [])
                    summary_tasks = [self._format_task_summary(task) for task in tasks]
                    total_count = result.get("meta", {}).get("total", len(tasks))
                    
                    summary_text = self._create_tasks_summary_text(summary_tasks, total_count, project_name)
                    
                    # Add pagination info
                    if total_count > limit:
                        summary_text += f"\n\n📄 Showing {len(tasks)} of {total_count} tasks"
                        if offset + limit < total_count:
                            summary_text += f"\n💡 Use get_project_tasks('{project_id}', limit={limit}, offset={offset + limit}) for more"
                    
                    return summary_text
                    
            except Exception as e:
                logger.error(f"Error getting project tasks: {e}")
                return f"❌ Error: {str(e)}"
        
        @self.mcp.tool(name="get_user_tasks")
        async def get_user_tasks_tool(
            user_id: str,
            include_completed: bool = False,
            limit: int = 50,
            offset: int = 0,
            include_custom_fields: bool = False,
            include_details: bool = False
        ) -> str:
            """Get tasks assigned to a specific user with enhanced filtering
            
            🔥 TOKEN OPTIMIZED: Returns concise summaries by default for better performance
            
            Args:
                user_id: The user ID
                include_completed: Include completed tasks (default: False)
                limit: Maximum number of tasks to return (default: 50, reduced from 200)
                offset: Offset for pagination (default: 0)
                include_custom_fields: Include custom fields data
                include_details: Include full task details (default: False - shows summary)
            """
            try:
                result = await self.get_user_tasks(
                    user_id=user_id, include_completed=include_completed,
                    limit=limit, offset=offset, include_custom_fields=include_custom_fields
                )
                
                if include_details:
                    return json.dumps(result, indent=2)
                else:
                    # Get user name for context
                    user_name = f"User {user_id}"  # Default
                    try:
                        user_details = await self.get_user_details(user_id)
                        if user_details.get("full_name"):
                            user_name = user_details["full_name"]
                    except:
                        pass
                    
                    # Create summary version
                    tasks = result.get("tasks", [])
                    summary_tasks = [self._format_task_summary(task) for task in tasks]
                    total_count = result.get("meta", {}).get("total", len(tasks))
                    
                    summary_text = self._create_tasks_summary_text(summary_tasks, total_count, f"{user_name}'s workspace")
                    
                    # Add pagination info
                    if total_count > limit:
                        summary_text += f"\n\n📄 Showing {len(tasks)} of {total_count} tasks"
                        if offset + limit < total_count:
                            summary_text += f"\n💡 Use get_user_tasks('{user_id}', limit={limit}, offset={offset + limit}) for more"
                    
                    return summary_text
                    
            except Exception as e:
                logger.error(f"Error getting user tasks: {e}")
                return f"❌ Error: {str(e)}"
        
        @self.mcp.tool(name="get_task_details")
        async def get_task_details_tool(task_id: str, include_custom_fields: bool = True, include_details: bool = True) -> str:
            """Get detailed information about a task including comments and files
            
            Args:
                task_id: The task ID
                include_custom_fields: Include custom fields data (default: True)
                include_details: Include full task details (default: True for this tool)
            """
            try:
                result = await self.get_task_details(task_id, include_custom_fields)
                
                if include_details:
                    return json.dumps(result, indent=2)
                else:
                    # Create summary version for single task
                    if not result:
                        return f"❌ Task {task_id} not found"
                    
                    summary_task = self._format_task_summary(result)
                    
                    lines = []
                    lines.append(f"📋 Task: {summary_task['title']}")
                    lines.append(f"🆔 ID: {summary_task['id']}")
                    lines.append(f"📊 Status: {summary_task['status']}")
                    lines.append(f"⚡ Priority: {summary_task['priority']}")
                    lines.append(f"👤 Assigned: {summary_task['assigned_to']}")
                    lines.append(f"📅 Due: {summary_task['due_date']}")
                    if summary_task['comments'] > 0:
                        lines.append(f"💬 Comments: {summary_task['comments']}")
                    if summary_task['url']:
                        lines.append(f"🔗 URL: {summary_task['url']}")
                    
                    lines.append("")
                    lines.append("💡 Use get_task_details(task_id, include_details=true) for full details")
                    
                    return "\n".join(lines)
                    
            except Exception as e:
                logger.error(f"Error getting task details: {e}")
                return f"❌ Error: {str(e)}"
        
        @self.mcp.tool(name="create_task")
        async def create_task_tool(
            title: str,
            project_id: str,
            description: Optional[str] = None,
            task_group_id: Optional[str] = None,
            priority: Optional[int] = None,
            assigned_to_id: Optional[str] = None,
            due_date: Optional[str] = None,
            start_date: Optional[str] = None,
            recurring_rule: Optional[str] = None,
            parent_task_id: Optional[str] = None,
            attached_file_ids: Optional[List[int]] = None,
            custom_fields: Optional[List[Dict]] = None,
            cf_template_id: Optional[str] = None
        ) -> str:
            """Create a new task in Freedcamp with enhanced options
            
            ⚠️ WORKFLOW REMINDER: Before creating tasks:
            1. Call get_projects() to find the correct project_id
            2. Call get_users() to find correct assigned_to_id (if assigning)
            3. Never assume or guess IDs - always look them up first!
            
            Args:
                title: Task title
                project_id: Project ID where the task will be created (get from get_projects())
                description: Task description (optional)
                task_group_id: Task group/list ID (optional)
                priority: Task priority (0=none, 1=low, 2=medium, 3=high)
                assigned_to_id: User ID to assign the task to (get from get_users(), use user_id field)
                due_date: Due date in YYYY-MM-DD format (optional)
                start_date: Start date in YYYY-MM-DD format (optional)
                recurring_rule: Recurrence rule in iCalendar format (optional)
                parent_task_id: Parent task ID for subtasks (optional)
                attached_file_ids: List of file IDs to attach (optional)
                custom_fields: Custom fields data (optional)
                cf_template_id: Custom fields template ID (optional)
            """
            try:
                result = await self.create_task(
                    title=title, project_id=project_id, description=description,
                    task_group_id=task_group_id, priority=priority, assigned_to_id=assigned_to_id,
                    due_date=due_date, start_date=start_date, recurring_rule=recurring_rule,
                    parent_task_id=parent_task_id, attached_file_ids=attached_file_ids,
                    custom_fields=custom_fields, cf_template_id=cf_template_id
                )
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error creating task: {e}")
                return f"Error: {str(e)}"
        
        @self.mcp.tool(name="update_task")
        async def update_task_tool(
            task_id: str,
            title: Optional[str] = None,
            description: Optional[str] = None,
            task_group_id: Optional[str] = None,
            priority: Optional[int] = None,
            assigned_to_id: Optional[str] = None,
            due_date: Optional[str] = None,
            start_date: Optional[str] = None,
            status: Optional[int] = None,
            parent_task_id: Optional[str] = None,
            attached_file_ids: Optional[List[int]] = None,
            custom_fields: Optional[List[Dict]] = None,
            cf_template_id: Optional[str] = None
        ) -> str:
            """Update an existing task
            
            Args:
                task_id: The task ID to update
                title: New task title (optional)
                description: New task description (optional)
                task_group_id: New task group/list ID (optional)
                priority: New task priority (0=none, 1=low, 2=medium, 3=high)
                assigned_to_id: New user ID to assign the task to (optional)
                due_date: New due date in YYYY-MM-DD format (optional)
                start_date: New start date in YYYY-MM-DD format (optional)
                status: New task status (0=not started, 1=completed, 2=in progress)
                parent_task_id: New parent task ID for subtasks (optional)
                attached_file_ids: New list of file IDs to attach (optional)
                custom_fields: New custom fields data (optional)
                cf_template_id: New custom fields template ID (optional)
            """
            try:
                result = await self.update_task(
                    task_id=task_id, title=title, description=description,
                    task_group_id=task_group_id, priority=priority, assigned_to_id=assigned_to_id,
                    due_date=due_date, start_date=start_date, status=status,
                    parent_task_id=parent_task_id, attached_file_ids=attached_file_ids,
                    custom_fields=custom_fields, cf_template_id=cf_template_id
                )
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error updating task: {e}")
                return f"Error: {str(e)}"
        
        @self.mcp.tool(name="delete_task")
        async def delete_task_tool(task_id: str) -> str:
            """Delete a task
            
            Args:
                task_id: The task ID to delete
            """
            try:
                result = await self.delete_task(task_id)
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error deleting task: {e}")
                return f"Error: {str(e)}"
        
        # ====== USER TOOLS ======
        
        @self.mcp.tool
        async def get_users(include_details: bool = False) -> str:
            """Get all users in the Freedcamp workspace
            
            💡 ID LOOKUP: Call this BEFORE assigning tasks to users!
            🔥 TOKEN OPTIMIZED: Returns concise summaries by default for better performance
            Use the 'user_id' field from results for task assignments, NOT the 'full_name'.
            
            Args:
                include_details: Include full user details (default: False - shows summary)
            """
            try:
                result = await self.get_all_users()
                
                if include_details:
                    return json.dumps(result, indent=2)
                else:
                    # Create summary version
                    if not result:
                        return "👥 No users found"
                    
                    lines = []
                    lines.append(f"👥 Users ({len(result)} total)")
                    lines.append("")
                    
                    for user in result:
                        lines.append(f"• {user['full_name']} (ID: {user['user_id']})")
                        if user.get('email'):
                            lines.append(f"  📧 {user['email']}")
                    
                    lines.append("")
                    lines.append("💡 QUICK ACTIONS:")
                    lines.append("  • Use user_id field for task assignments")
                    lines.append("  • get_user_tasks(user_id) - See user's tasks")
                    lines.append("  • get_users(include_details=true) - See full details")
                    
                    return "\n".join(lines)
                    
            except Exception as e:
                logger.error(f"Error getting users: {e}")
                return f"❌ Error: {str(e)}"
        
        @self.mcp.tool(name="get_current_user")
        async def get_current_user_tool() -> str:
            """Get current user information"""
            try:
                result = await self.get_current_user()
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error getting current user: {e}")
                return f"Error: {str(e)}"
        
        @self.mcp.tool(name="get_user_details")
        async def get_user_details_tool(user_id: str) -> str:
            """Get detailed information about a specific user
            
            Args:
                user_id: The user ID
            """
            try:
                result = await self.get_user_details(user_id)
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error getting user details: {e}")
                return f"Error: {str(e)}"
        
        @self.mcp.tool(name="update_current_user")
        async def update_current_user_tool(
            email: Optional[str] = None,
            password: Optional[str] = None,
            first_name: Optional[str] = None,
            last_name: Optional[str] = None,
            confirmation_password: Optional[str] = None,
            timezone: Optional[str] = None
        ) -> str:
            """Update current user information
            
            Args:
                email: New email address (optional)
                password: New password (optional)
                first_name: New first name (optional)
                last_name: New last name (optional)
                confirmation_password: Current password for confirmation (required when changing email/password)
                timezone: New timezone (optional)
            """
            try:
                result = await self.update_current_user(
                    email=email, password=password, first_name=first_name,
                    last_name=last_name, confirmation_password=confirmation_password,
                    timezone=timezone
                )
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error updating current user: {e}")
                return f"Error: {str(e)}"
        
        # ====== COMMENT TOOLS ======
        
        @self.mcp.tool(name="add_comment")
        async def add_comment_tool(
            item_id: str,
            app_id: str,
            description: str,
            attached_file_ids: Optional[List[int]] = None
        ) -> str:
            """Add a comment to an item (task, file, etc.)
            
            Args:
                item_id: The item ID to comment on
                app_id: The application ID (2=tasks, see documentation for others)
                description: The comment text (HTML supported)
                attached_file_ids: List of file IDs to attach (optional)
            """
            try:
                result = await self.add_comment(
                    item_id=item_id, app_id=app_id, description=description,
                    attached_file_ids=attached_file_ids
                )
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error adding comment: {e}")
                return f"Error: {str(e)}"
        
        @self.mcp.tool(name="update_comment")
        async def update_comment_tool(comment_id: str, description: str) -> str:
            """Update an existing comment
            
            Args:
                comment_id: The comment ID to update
                description: The new comment text (HTML supported)
            """
            try:
                result = await self.update_comment(comment_id, description)
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error updating comment: {e}")
                return f"Error: {str(e)}"
        
        @self.mcp.tool(name="delete_comment")
        async def delete_comment_tool(comment_id: str) -> str:
            """Delete a comment
            
            Args:
                comment_id: The comment ID to delete
            """
            try:
                result = await self.delete_comment(comment_id)
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error deleting comment: {e}")
                return f"Error: {str(e)}"
        
        # ====== FILE TOOLS ======
        
        @self.mcp.tool(name="get_file_details")
        async def get_file_details_tool(file_id: str) -> str:
            """Get detailed information about a file
            
            Args:
                file_id: The file ID
            """
            try:
                result = await self.get_file_details(file_id)
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error getting file details: {e}")
                return f"Error: {str(e)}"
        
        @self.mcp.tool(name="delete_file")
        async def delete_file_tool(file_id: str) -> str:
            """Delete a file
            
            Args:
                file_id: The file ID to delete
            """
            try:
                result = await self.delete_file(file_id)
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error deleting file: {e}")
                return f"Error: {str(e)}"
    
    async def run_stdio(self):
        """Run the MCP server with stdio transport"""
        await self.mcp.run_async(transport="stdio")
    
    async def run_http(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the MCP server with HTTP transport"""
        await self.mcp.run_async(transport="http", host=host, port=port)

# Load environment variables
load_dotenv()
config = FreedcampConfig(
    api_key=os.getenv("FREEDCAMP_API_KEY", ""),
    api_secret=os.getenv("FREEDCAMP_API_SECRET", "")
)

if not config.api_key or not config.api_secret:
    raise RuntimeError("FREEDCAMP_API_KEY and FREEDCAMP_API_SECRET environment variables must be set")

freedcamp_mcp = FreedcampMCP(config)

# Expose the FastMCP server for use with FastMCP CLI
mcp = freedcamp_mcp.mcp

if __name__ == "__main__":
    # Use FastMCP's built-in HTTP transport
    freedcamp_mcp.mcp.run(transport="http", host="0.0.0.0", port=8000)
