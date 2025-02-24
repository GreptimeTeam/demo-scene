import random
import time
import requests
import os

# Configuration
base_url = os.getenv("BASE_URL")
BASE_URL = base_url or "http://localhost:8000"  # Replace with your Django app's URL
TODO_API_URL = f"{BASE_URL}/todos/"

# Helper function to create a TODO item
def create_todo():
    task = f"Task {random.randint(1, 1000)}"
    response = requests.post(TODO_API_URL, json={"task": task})
    if response.status_code == 201:
        print(f"Created TODO: {task}")
        return response.json()["id"]
    else:
        print(f"Failed to create TODO: {response.status_code}")
        return None

# Helper function to read all TODO items
def read_todos():
    response = requests.get(TODO_API_URL)
    if response.status_code == 200:
        todos = response.json()
        print(f"Read {len(todos)} TODOs")
        return todos
    else:
        print(f"Failed to read TODOs: {response.status_code}")
        return []

# Helper function to update a TODO item
def update_todo(todo_id):
    new_task = f"Updated Task {random.randint(1, 1000)}"
    response = requests.put(f"{TODO_API_URL}{todo_id}/", json={"task": new_task})
    if response.status_code == 200:
        print(f"Updated TODO {todo_id}: {new_task}")
    else:
        print(f"Failed to update TODO {todo_id}: {response.status_code}")

# Main function to generate traffic
def generate_traffic():
    while True:
        try:
            # Randomly choose an action: create, read, or update
            action = random.choice(["create", "read", "update"])

            if action == "create":
                create_todo()
            elif action == "read":
                read_todos()
            elif action == "update":
                todos = read_todos()
                if todos:
                    todo_id = random.choice(todos)["id"]
                    update_todo(todo_id)
        except Exception as e:
            print(f"Failed to request server: {e}")

        # Wait for a random interval before the next action
        time.sleep(random.uniform(0.5, 2.0))

if __name__ == "__main__":
    generate_traffic()
