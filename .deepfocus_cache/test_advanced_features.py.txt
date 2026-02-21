import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_tool(name, prompt):
    print(f"\n--- Testing Feature: {name} ---")
    print(f"Prompt: {prompt}")
    try:
        requests.post(f"{BASE_URL}/api/chat", json={"message": "clear"})
        response = requests.post(f"{BASE_URL}/api/chat", json={"message": prompt})
        if response.status_code == 200:
            data = response.json()
            print(f"Source: {data.get('metrics', {}).get('source')}")
            print(f"Response: {json.dumps(data.get('response'), indent=2)}")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    print("Verifying if backend is up...")
    try:
        requests.get(f"{BASE_URL}/health")
        print("Server is UP.")
    except:
        print("Server is DOWN. Please start it with: python3 -m backend.main")
        exit(1)

    # Test Feature A: Amnesia Search (assuming SOLUTION.md exists)
    test_tool("Amnesia Search", "Search for 'SOLUTION.md' and tell me what the project structure looks like.")
    
    # Test Feature B: Distraction Heatmap
    test_tool("Distraction Heatmap", "Am I being productive right now?")
    
    # Test Feature C: Ghost-Writer
    test_tool("Ghost-Writer", "Find SOLUTION.md and copy its path to my clipboard.")
