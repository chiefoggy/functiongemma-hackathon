from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# 1. Define the exact structure of the JSON we expect the user to send
class BSRequest(BaseModel):
    text: str

# 2. Create the POST endpoint at /detect
@app.post("/detect")
def detect_bs(request: BSRequest):
    # Grab the text the user sent and make it lowercase for easy checking
    text = request.text.lower()
    
    # 3. A very basic mock BS-detection logic
    corporate_buzzwords = ["synergize", "paradigm", "agile", "roi", "cross-functional"]
    
    # Find which buzzwords are in the user's text
    flagged = [word for word in corporate_buzzwords if word in text]
    
    # 4. If we found garbage jargon, flag it as BS
    if len(flagged) > 0:
        return {
            "is_bs": True,
            "bs_score": 85,  # Arbitrary high score for the test
            "flagged_words": flagged
        }
    
    # 5. Otherwise, pass it as normal text
    return {
        "is_bs": False,
        "bs_score": 0,
        "flagged_words": []
    }