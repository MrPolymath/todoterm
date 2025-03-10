#!/bin/bash

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Create symbolic link with the virtual environment's Python
ln -sf $(pwd)/venv/bin/python3 /usr/local/bin/todo-python
ln -sf $(pwd)/todo.py /usr/local/bin/todo

echo "Setup complete! You can now use the 'todo' command from anywhere."
