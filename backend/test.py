from fastapi.testclient import TestClient
from backend.main import app  # Imports your exact FastAPI instance

# Create a dummy client to simulate a user talking to your API
client = TestClient(app)

def test_bs_detector_flags_corporate_jargon():
    # 1. The garbage text we want to test
    payload = {
        "text": "We need to synergize our cross-functional paradigms to maximize agile ROI."
    }
    
    # 2. Simulate sending a POST request to your endpoint
    response = client.post("/detect", json=payload)
    
    # 3. Check if the server responded successfully (Status Code 200 = OK)
    assert response.status_code == 200
    
    # 4. Check if your detector actually caught the BS
    data = response.json()
    
    # (Adjust these assertions based on what your main.py actually returns)
    assert data["is_bs"] == True 
    assert data["bs_score"] > 80
    assert "synergize" in data["flagged_words"]

def test_bs_detector_passes_normal_text():
    # Let's make sure it doesn't flag totally normal sentences
    payload = {
        "text": "The company made 5 million dollars in profit this quarter."
    }
    
    response = client.post("/detect", json=payload)
    data = response.json()
    
    assert response.status_code == 200
    assert data["is_bs"] == False