# Freedcamp MCP Server - Workflow Instructions for LLMs

## 🚨 CRITICAL RULES

### 1. **NEVER ASSUME IDs - ALWAYS LOOK THEM UP FIRST**
- Project IDs: Use `get_projects()` to find them
- User IDs: Use `get_users()` to find them  
- Task IDs: Use `get_project_tasks()` or task creation responses

### 2. **REQUIRED WORKFLOW SEQUENCE**

#### For ANY Freedcamp Operation:
```
1. get_projects() → Find available projects and their IDs
2. get_users() → Find available users and their IDs
3. get_current_user() → Understand current user context
4. [Then proceed with specific operations]
```

## 📋 TASK OPERATIONS WORKFLOW

### Creating Tasks:
```
STEP 1: Discovery
→ get_projects() - Get project list
→ get_users() - Get user list (for assignments)

STEP 2: Identify Target Project
→ Search get_projects() results by name
→ Extract project "id" field (NOT "name")

STEP 3: Create Task
→ create_task(title="...", project_id="ACTUAL_ID_FROM_STEP_2")
→ If assigning: assigned_to_id="USER_ID_FROM_get_users()"

STEP 4: Verify
→ get_task_details(new_task_id) to confirm creation
```

### Updating Tasks:
```
STEP 1: Find Task
→ get_project_tasks(project_id) or get_user_tasks(user_id)
→ Identify task by matching title/description

STEP 2: Update
→ update_task(task_id="FOUND_ID", ...)
→ Use actual IDs for any user assignments
```

## 👥 USER ASSIGNMENT RULES

### Getting User IDs:
```
1. Call get_users()
2. Find user by "full_name" or "email" in results
3. Use the "user_id" field for assignments
4. NEVER use "full_name" directly in assignments
```

### Assignment Values:
- Specific user: `assigned_to_id="123456"` (actual user_id)
- Unassigned: `assigned_to_id="0"`
- Everyone: `assigned_to_id="-1"`

## 🏗️ PROJECT OPERATIONS WORKFLOW

### Working with Existing Projects:
```
1. get_projects() - See all projects
2. Find target project by name in results
3. Use project["id"] for all subsequent operations
4. get_project_details(project_id) - Get detailed info if needed
```

### Creating New Projects:
```
1. get_users() - Find team members to add
2. create_project(name="...", users_to_add=[...])
3. get_projects() - Verify creation and get new project ID
```

## 🔍 COMMON ERROR PATTERNS TO AVOID

### ❌ DON'T DO THIS:
```python
# WRONG - Assuming project ID
create_task(title="Task", project_id="123")

# WRONG - Using user name instead of ID  
create_task(title="Task", project_id="123", assigned_to_id="John Doe")

# WRONG - Guessing IDs exist
update_task(task_id="456", assigned_to_id="789")
```

### ✅ DO THIS INSTEAD:
```python
# CORRECT - Look up project ID first
projects = get_projects()
target_project = find_project_by_name(projects, "My Project")
project_id = target_project["id"]

# CORRECT - Look up user ID first
users = get_users()
target_user = find_user_by_name(users, "John Doe")
user_id = target_user["user_id"]

# CORRECT - Create with actual IDs
create_task(
    title="Task", 
    project_id=project_id,
    assigned_to_id=user_id
)
```

## 📅 DATE FORMAT REQUIREMENTS

- Due dates: `"YYYY-MM-DD"` format only
- Example: `due_date="2024-12-25"`
- Never use relative dates like "tomorrow" or "next week"

## 🔧 DEBUGGING WORKFLOW

### If Operations Fail:
1. **"Project not found"** → Call `get_projects()` to see available projects
2. **"User not found"** → Call `get_users()` to see available users  
3. **"Task not found"** → Call `get_project_tasks(project_id)` to see available tasks
4. **Permission errors** → Call `get_current_user()` and `get_project_details(project_id)`

### Verification Steps:
- After creating: Call `get_task_details(task_id)` to confirm
- After updating: Call `get_task_details(task_id)` to verify changes
- After assignment: Call `get_user_tasks(user_id)` to see user's tasks

## 🎯 WORKFLOW EXAMPLES

### Example 1: Create and Assign Task
```python
# Step 1: Get context
projects = get_projects()
users = get_users()

# Step 2: Find IDs
project_id = find_project_id(projects, "Website Redesign")
user_id = find_user_id(users, "john@company.com")

# Step 3: Create task
result = create_task(
    title="Design homepage mockup",
    project_id=project_id,
    assigned_to_id=user_id,
    due_date="2024-12-15",
    priority=2
)

# Step 4: Verify
task_details = get_task_details(result.task.id)
```

### Example 2: Update Project Team
```python
# Step 1: Get context  
projects = get_projects()
users = get_users()

# Step 2: Find project
project_id = find_project_id(projects, "Marketing Campaign")

# Step 3: Find users to add
new_users = [
    {"email": "sarah@company.com", "first_name": "Sarah", "last_name": "Johnson"},
    {"email": "mike@company.com", "first_name": "Mike", "last_name": "Chen"}
]

# Step 4: Update project
result = update_project(
    project_id=project_id,
    users_to_add=new_users
)
```

## 🚀 QUICK REFERENCE

### Most Common Starting Points:
1. `get_projects()` - Start here for project operations
2. `get_users()` - Start here for user operations  
3. `get_workflow_help()` - Get contextual workflow guidance

### ID Lookup Tools:
- Projects: `get_projects()`
- Users: `get_users()`
- Tasks: `get_project_tasks(project_id)` or `get_user_tasks(user_id)`

### Verification Tools:
- Projects: `get_project_details(project_id)`
- Tasks: `get_task_details(task_id)`
- Users: `get_user_details(user_id)`

Remember: **The key to success is always looking up IDs before using them!** 