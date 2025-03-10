# TodoTerm

A simple terminal-based todo application that makes it easy to manage tasks from the command line.

## Installation

1. Clone this repository
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Make the script executable:

```bash
chmod +x todo.py
```

4. Create a symbolic link to make it available as `todo`:

```bash
ln -s $(pwd)/todo.py /usr/local/bin/todo
```

## Usage

### View all tasks

```bash
todo
```

### Add a new task

```bash
todo "Task title"
```

### Add a task with a deadline

```bash
todo "Task title" for tomorrow
todo "Task title" due next week
todo "Task title" by Friday
```

### Add a task with tags

```bash
todo "Task title" #work #urgent
```

### Combine deadline and tags

```bash
todo "Task title" for tomorrow #work
```

## Features

- Natural language date parsing (e.g., "tomorrow", "next week", "in 2 days")
- Tag support using #hashtags
- Beautiful terminal output with rich formatting
- SQLite storage for persistence
- Simple and intuitive interface

## Examples

```bash
# Add a task for tomorrow
todo "Call client" for tomorrow #work

# Add a task with multiple tags
todo "Buy groceries" #shopping #personal

# Add a task with a specific deadline
todo "Project deadline" due next Friday #work #urgent

# View all tasks
todo
```
