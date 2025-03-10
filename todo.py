#!/usr/bin/env python3
import os
import sqlite3
import click
from datetime import datetime
import dateparser
import logging
from rich.console import Console
from rich.table import Table, Column
from rich.prompt import Prompt, Confirm
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, DataTable, Button, Select, Input, Label, Static
from textual.binding import Binding
from textual import events
from textual.screen import Screen
from textual.message import Message
import humanize

# Initialize rich console
console = Console()

# Set up logging
log_file = os.path.expanduser("~/.todo.log")
debug_file = os.path.expanduser("~/.todo.debug")


def debug_print(message):
    """Write debug message to both log and debug files."""
    with open(debug_file, 'a') as f:
        f.write(f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
    logging.info(message)


# Clean up old files if they exist
for file in [log_file, debug_file]:
    if os.path.exists(file):
        os.remove(file)

# Task statuses
STATUSES = {
    "todo": "Todo",
    "doing": "Doing",
    "done": "Done"
}


def init_db():
    """Initialize the SQLite database and create tables if they don't exist."""
    db_path = os.path.expanduser("~/.todo.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Create tasks table
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            deadline DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'todo'
        )
    ''')

    # Create tags table
    c.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')

    # Create task_tags junction table
    c.execute('''
        CREATE TABLE IF NOT EXISTS task_tags (
            task_id INTEGER,
            tag_id INTEGER,
            FOREIGN KEY (task_id) REFERENCES tasks (id),
            FOREIGN KEY (tag_id) REFERENCES tags (id),
            PRIMARY KEY (task_id, tag_id)
        )
    ''')

    conn.commit()
    conn.close()


def get_tasks():
    """Get all tasks from the database."""
    conn = sqlite3.connect(os.path.expanduser("~/.todo.db"))
    c = conn.cursor()

    c.execute('''
        SELECT t.id, t.title, t.description, t.deadline, t.status,
               GROUP_CONCAT(DISTINCT tag.name) as tags
        FROM tasks t
        LEFT JOIN task_tags tt ON t.id = tt.task_id
        LEFT JOIN tags tag ON tt.tag_id = tag.id
        GROUP BY t.id, t.title, t.description, t.deadline, t.status
        ORDER BY t.created_at DESC
    ''')

    tasks = c.fetchall()
    conn.close()
    return tasks


def update_task_status(task_id, new_status):
    """Update the status of a task."""
    debug_print(f"Updating task {task_id} status to {new_status}")
    conn = sqlite3.connect(os.path.expanduser("~/.todo.db"))
    c = conn.cursor()
    try:
        c.execute('UPDATE tasks SET status = ? WHERE id = ?',
                  (new_status, task_id))
        conn.commit()

        # Verify the update
        c.execute('SELECT status FROM tasks WHERE id = ?', (task_id,))
        result = c.fetchone()
        if result and result[0] == new_status:
            debug_print(
                f"Successfully updated task {task_id} status to {new_status}")
        else:
            debug_print(
                f"Failed to update task {task_id} status. Current status: {result[0] if result else 'not found'}")
    except Exception as e:
        debug_print(f"Error updating task status: {str(e)}")
        raise
    finally:
        conn.close()


class RefreshMessage(Message):
    """Message to request a table refresh."""


def format_deadline(deadline_str):
    """Format deadline in a human-readable format."""
    if not deadline_str:
        return ""

    try:
        deadline = datetime.fromisoformat(deadline_str)
        now = datetime.now()

        if deadline < now:
            return f"⚠️ {humanize.naturaltime(deadline)}"
        else:
            return humanize.naturaltime(deadline, when=now, future=True)
    except (ValueError, TypeError):
        return ""


class TodoApp(App):
    """A Textual app to manage todo tasks."""

    CSS = """
    #task-table {
        height: 1fr;
        border: solid green;
    }
    Button {
        margin: 1 2;
        width: 20;
    }
    Select {
        margin: 1 2;
        width: 20;
    }
    Footer {
        background: $surface;
        color: $text;
        text-align: center;
        padding: 1;
        height: 3;
    }
    Screen {
        height: 100%;
    }
    .hidden {
        visibility: hidden;
        width: 0;
    }
    .status-menu {
        dock: right;
        width: 30;
        height: auto;
        background: $panel;
        border: solid $primary;
        padding: 1;
    }
    Header {
        background: $primary;
        color: $text;
        text-align: center;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "new_task", "New Task"),
        Binding("enter", "select_task", "Change Status"),
        Binding("d", "delete_task", "Delete Task"),
    ]

    def __init__(self):
        super().__init__()
        self.current_task_id = None
        self.message = ""

    def on_refresh_message(self, message: RefreshMessage) -> None:
        """Handle refresh message."""
        debug_print("Received refresh message")
        self.refresh_table()

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header("📝 Todo App - Press [Enter] to change status, [N] new task, [D] delete, [Q] quit")
        yield DataTable(id="task-table")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the application on mount."""
        table = self.query_one("#task-table", DataTable)
        table.cursor_type = "row"

        # Add columns (without ID)
        table.add_columns(
            "Title", "Description", "Deadline", "Tags", "Status"
        )

        # Add rows
        for task in get_tasks():
            id_, title, desc, deadline, status, tags = task
            deadline_str = format_deadline(deadline) if deadline else ""
            tags_str = tags if tags else ""
            tags_str = ", ".join(f"#{tag}" for tag in tags_str.split(
                ",")) if tags_str else ""
            status_text = STATUSES.get(status, "Todo")

            # Add row without key
            table.add_row(
                title,
                desc or "",
                deadline_str,
                tags_str,
                status_text
            )

    def action_select_task(self) -> None:
        """Handle task selection."""
        table = self.query_one("#task-table", DataTable)
        if table.cursor_row is not None:
            # Get the task data from get_tasks() using the row index
            tasks = get_tasks()
            task_id = tasks[table.cursor_row][0]  # First element is ID
            self.current_task_id = task_id
            self.show_status_menu()

    def show_status_menu(self) -> None:
        """Show a menu to change task status."""
        if self.current_task_id is None:
            debug_print("No task selected for status change")
            return

        debug_print(f"Showing status menu for task {self.current_task_id}")

        status_select = Select(
            options=[
                ("Todo", "todo"),
                ("Doing", "doing"),
                ("Done", "done")
            ],
            prompt="Change status to:",
            classes="status-menu"
        )

        async def handle_status_change(status_select: Select) -> None:
            status = status_select.value
            debug_print(f"Status selected: {status}")
            update_task_status(self.current_task_id, status)
            debug_print(
                f"Updated task {self.current_task_id} status to {status}")
            await self.refresh_table()
            status_select.remove()

        status_select.on_select_option = handle_status_change
        self.mount(status_select)

    def refresh_table(self) -> None:
        """Refresh the task table."""
        debug_print("Refreshing table")
        table = self.query_one("#task-table", DataTable)

        # Clear both rows and columns
        table.clear()
        table.columns.clear()
        debug_print("Cleared table rows and columns")

        # Add columns
        table.add_columns(
            "Title", "Description", "Deadline", "Tags", "Status"
        )
        debug_print("Added fresh columns")

        tasks = get_tasks()
        debug_print(f"Got {len(tasks)} tasks from database")

        for task in tasks:
            id_, title, desc, deadline, status, tags = task
            deadline_str = format_deadline(deadline) if deadline else ""
            tags_str = tags if tags else ""
            tags_str = ", ".join(f"#{tag}" for tag in tags_str.split(
                ",")) if tags_str else ""
            status_text = STATUSES.get(status, "Todo")
            debug_print(
                f"Adding row for task {id_} with status {status} (display: {status_text})")

            table.add_row(
                title,
                desc or "",
                deadline_str,
                tags_str,
                status_text
            )

    def action_new_task(self) -> None:
        """Handle new task creation."""
        debug_print("Pushing new task screen")
        self.push_screen(NewTaskScreen())

    def show_message(self, message: str, is_error: bool = False) -> None:
        """Show a message in the footer."""
        self.message = message
        footer = self.query_one(Footer)
        footer.content = message
        if is_error:
            footer.styles.color = "red"
        else:
            footer.styles.color = "green"

    def action_delete_task(self) -> None:
        """Handle task deletion."""
        table = self.query_one("#task-table", DataTable)
        if table.cursor_row is not None:
            current_row = table.cursor_row
            # Get the task data from get_tasks() using the row index
            tasks = get_tasks()
            task_id = tasks[table.cursor_row][0]  # First element is ID
            delete_task(task_id)
            self.show_message(f"Task {task_id} deleted successfully!")
            self.refresh_table()

            # After refresh, set cursor to the same position or last item
            total_rows = len(table.rows)
            if total_rows > 0:
                # If we deleted the last row, move cursor to the new last row
                new_position = min(current_row, total_rows - 1)
                table.move_cursor(row=new_position)
                # Ensure the cursor is visible
                table.scroll_to(0, new_position)
            else:
                # If no tasks left, show a message
                self.show_message("No tasks remaining")


class NewTaskScreen(Screen):
    def __init__(self):
        super().__init__()
        self.title = "New Task"
        debug_print("NewTaskScreen initialized")

    def compose(self) -> ComposeResult:
        with Container(id="form-container"):
            yield Label("Task details:")
            yield Input(id="task", placeholder="e.g., Buy groceries for tomorrow #shopping")
            yield Label("Description (optional):")
            yield Input(id="description", placeholder="Enter description")
            with Horizontal(classes="buttons"):
                yield Button("Add", id="add", variant="primary")
                yield Button("Cancel", id="cancel")
            yield Static(id="status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        debug_print(f"Button pressed: {event.button.id}")
        status = self.query_one("#status", Static)

        if event.button.id == "add":
            try:
                debug_print("Getting input values...")
                task_input = self.query_one("#task", Input)
                desc_input = self.query_one("#description", Input)

                command = task_input.value.strip()
                description = desc_input.value.strip()

                debug_print(f"Command received: '{command}'")
                debug_print(f"Description received: '{description}'")

                if command:
                    debug_print("Parsing command...")
                    title, deadline, tags = parse_command(command)
                    debug_print(
                        f"Parsed: title='{title}', deadline='{deadline}', tags='{tags}'")
                    try:
                        debug_print("Adding task to database...")
                        add_task(title, description, deadline, tags)
                        debug_print("Task added successfully!")
                        status.update("Task added successfully!")
                        debug_print("Popping screen...")
                        self.app.pop_screen()
                        debug_print("Refreshing table...")
                        self.app.refresh_table()
                    except Exception as e:
                        debug_print(f"Error adding task: {str(e)}")
                        status.update(f"Error: {str(e)}")
                else:
                    debug_print("No command provided (empty string)")
                    status.update("Please enter task details")
            except Exception as e:
                debug_print(f"Error in button handler: {str(e)}")
                debug_print(f"Error type: {type(e)}")
                import traceback
                debug_print(f"Traceback: {traceback.format_exc()}")
                status.update(f"Error: {str(e)}")
        elif event.button.id == "cancel":
            debug_print("Cancel button pressed")
            self.app.pop_screen()

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.app.pop_screen()


def parse_command(command):
    """Parse the command string to extract title, deadline, and tags."""
    debug_print(f"Parsing command: {command}")
    # Split the command into parts
    parts = command.split()
    debug_print(f"Split parts: {parts}")

    # Extract tags (starting with #)
    tags = [part[1:] for part in parts if part.startswith('#')]
    parts = [part for part in parts if not part.startswith('#')]
    debug_print(f"After tag extraction - parts: {parts}, tags: {tags}")

    # Try to find a deadline with keywords first
    deadline = None
    deadline_keywords = ['for', 'due', 'by', 'on']
    for i, part in enumerate(parts):
        if part.lower() in deadline_keywords and i + 1 < len(parts):
            date_str = ' '.join(parts[i+1:])
            debug_print(f"Trying to parse date with keyword: {date_str}")
            deadline = dateparser.parse(date_str)
            if deadline:
                debug_print(f"Found deadline with keyword: {deadline}")
                parts = parts[:i]
                break

    # If no deadline found with keywords, try parsing from the end with increasing chunks
    if not deadline:
        # Try parsing from largest possible chunk to smallest
        best_deadline = None
        best_i = len(parts)
        best_chunk_size = 0

        # Start from a minimum of 2 words (to catch phrases like "next week")
        for chunk_size in range(min(5, len(parts)), 1, -1):
            for i in range(len(parts) - chunk_size + 1):
                date_str = ' '.join(parts[i:i + chunk_size])
                debug_print(f"Trying to parse date chunk: {date_str}")
                parsed_date = dateparser.parse(date_str)
                if parsed_date:
                    debug_print(f"Found valid date in chunk: {parsed_date}")
                    # Keep track of the earliest (leftmost) and largest valid date phrase
                    if i <= best_i:
                        best_deadline = parsed_date
                        best_i = i
                        best_chunk_size = chunk_size
                        debug_print(
                            f"New best date found: {best_deadline} at position {best_i}")

        if best_deadline:
            deadline = best_deadline
            parts = parts[:best_i] + parts[best_i + best_chunk_size:]
            debug_print(f"Using best found deadline: {deadline}")

    # The rest is the title
    title = ' '.join(parts)
    debug_print(
        f"Final result - title: '{title}', deadline: {deadline}, tags: {tags}")

    return title, deadline, tags


def add_task(title, description, deadline=None, tags=None):
    """Add a new task to the database."""
    debug_print(
        f"Adding task: title='{title}', description='{description}', deadline='{deadline}', tags='{tags}'")
    conn = sqlite3.connect(os.path.expanduser("~/.todo.db"))
    c = conn.cursor()

    try:
        # Insert task
        c.execute('''
            INSERT INTO tasks (title, description, deadline, status)
            VALUES (?, ?, ?, 'todo')
        ''', (title, description, deadline))

        task_id = c.lastrowid
        debug_print(f"Task inserted with ID: {task_id}")

        # Handle tags
        if tags:
            for tag in tags:
                # Insert or get tag
                c.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (tag,))
                c.execute('SELECT id FROM tags WHERE name = ?', (tag,))
                tag_id = c.fetchone()[0]
                debug_print(f"Tag '{tag}' has ID: {tag_id}")

                # Link tag to task
                c.execute('INSERT INTO task_tags (task_id, tag_id) VALUES (?, ?)',
                          (task_id, tag_id))
                debug_print(f"Linked tag {tag_id} to task {task_id}")

        conn.commit()
        conn.close()
        debug_print("Database connection closed")

        # Verify the task was added
        conn = sqlite3.connect(os.path.expanduser("~/.todo.db"))
        c = conn.cursor()
        c.execute('SELECT id FROM tasks WHERE id = ?', (task_id,))
        if not c.fetchone():
            debug_print("Task verification failed")
            raise Exception("Failed to add task")
        debug_print("Task verification successful")
        conn.close()
    except Exception as e:
        debug_print(f"Database error: {str(e)}")
        conn.close()
        raise Exception(f"Database error: {str(e)}")


def delete_task(task_id):
    """Delete a task and its associated tags from the database."""
    conn = sqlite3.connect(os.path.expanduser("~/.todo.db"))
    c = conn.cursor()
    try:
        # Delete task tags first (due to foreign key constraint)
        c.execute('DELETE FROM task_tags WHERE task_id = ?', (task_id,))
        # Delete the task
        c.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
    finally:
        conn.close()


@click.command()
@click.argument('command', nargs=-1)
def main(command):
    """A simple terminal-based todo application."""
    # Initialize database
    init_db()

    if not command:
        # If no command provided, show interactive UI
        app = TodoApp()
        app.run()
        return

    # Join command parts and parse
    command_str = ' '.join(command)
    title, deadline, tags = parse_command(command_str)

    if not title:
        console.print("[red]Error: Please provide a title for the task[/red]")
        return

    # Get description using rich prompt
    description = Prompt.ask("Description (optional)")

    # Add the task
    add_task(title, description, deadline, tags)
    console.print("[green]Task added successfully![/green]")


if __name__ == '__main__':
    main()
