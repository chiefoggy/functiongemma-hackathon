from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
import tempfile
import yfinance as yf

from main import generate_hybrid, generate_cactus, transcribe_audio

app = FastAPI()

# Mount the static directory to serve index.html
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_stock_price(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
        name = info.get('shortName', ticker.upper())
        if price:
            return {"type": "stock_widget", "data": {"ticker": ticker.upper(), "name": name, "price": price}}
        else:
            return {"type": "text", "data": f"Could not retrieve the current price for {ticker.upper()}."}
    except Exception as e:
        return {"type": "text", "data": f"Error fetching data for {ticker.upper()}: {str(e)}"}

def get_company_news(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        if not news:
            return {"type": "text", "data": f"No recent news found for {ticker.upper()}."}
        
        headlines = []
        for item in news[:3]:
            if 'title' in item:
                link = item.get('link', '#')
                headlines.append({"title": item['title'], "link": link})
        if headlines:
            return {"type": "news_widget", "data": {"ticker": ticker.upper(), "headlines": headlines}}
        return {"type": "text", "data": f"No recent headlines found for {ticker.upper()}."}
    except Exception as e:
        return {"type": "text", "data": f"Error fetching news for {ticker.upper()}: {str(e)}"}

def calculate_roi(initial_value: float, final_value: float):
    roi = ((final_value - initial_value) / initial_value) * 100
    return f"The Return on Investment (ROI) is {roi:.2f}%."

def get_exchange_rate(base_currency: str, target_currency: str):
    rates = {"USD_EUR": 0.85, "EUR_USD": 1.18, "USD_GBP": 0.75, "GBP_USD": 1.33}
    pair = f"{base_currency.upper()}_{target_currency.upper()}"
    rate = rates.get(pair, 1.0)
    return f"The exchange rate from {base_currency.upper()} to {target_currency.upper()} is {rate}."

def calculate_compound_interest(principal: float, rate: float, years: int):
    amount = principal * (1 + rate / 100) ** years
    return f"The compound interest amount after {years} years is ${amount:.2f}."

def get_crypto_price(symbol: str):
    prices = {"BTC": 60000.0, "ETH": 4000.0, "SOL": 150.0}
    price = prices.get(symbol.upper(), 1000.0)
    return f"The current price for {symbol.upper()} is ${price:.2f}."

def calculate_mortgage_payment(principal: float, annual_rate: float, years: int):
    monthly_rate = annual_rate / 100 / 12
    num_payments = years * 12
    if monthly_rate == 0:
        payment = principal / num_payments
    else:
        payment = principal * (monthly_rate * (1 + monthly_rate) ** num_payments) / ((1 + monthly_rate) ** num_payments - 1)
    return f"The monthly mortgage payment is ${payment:.2f}."

# Finance specific tools
FINANCE_TOOLS = [
    {
        "name": "get_stock_price",
        "description": "Get the current stock price for a given ticker symbol.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol, e.g., AAPL.",
                }
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_company_news",
        "description": "Get the latest news headlines for a company.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol.",
                }
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "calculate_roi",
        "description": "Calculate Return on Investment (ROI) given initial and final values.",
        "parameters": {
            "type": "object",
            "properties": {
                "initial_value": {
                    "type": "number",
                    "description": "The starting value of the investment.",
                },
                "final_value": {
                    "type": "number",
                    "description": "The ending value of the investment.",
                }
            },
            "required": ["initial_value", "final_value"],
        },
    },
    {
        "name": "get_exchange_rate",
        "description": "Get the exchange rate between two currencies.",
        "parameters": {
            "type": "object",
            "properties": {
                "base_currency": {"type": "string", "description": "Base currency code, e.g., USD"},
                "target_currency": {"type": "string", "description": "Target currency code, e.g., EUR"}
            },
            "required": ["base_currency", "target_currency"],
        },
    },
    {
        "name": "calculate_compound_interest",
        "description": "Calculate the compound interest amount.",
        "parameters": {
            "type": "object",
            "properties": {
                "principal": {"type": "number", "description": "Initial investment amount"},
                "rate": {"type": "number", "description": "Annual interest rate in percent"},
                "years": {"type": "integer", "description": "Number of years"}
            },
            "required": ["principal", "rate", "years"],
        },
    },
    {
        "name": "get_crypto_price",
        "description": "Get the current price for a given cryptocurrency symbol.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "The cryptocurrency symbol, e.g., BTC.",
                }
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "calculate_mortgage_payment",
        "description": "Calculate the monthly mortgage payment.",
        "parameters": {
            "type": "object",
            "properties": {
                "principal": {"type": "number", "description": "Loan principal amount"},
                "annual_rate": {"type": "number", "description": "Annual interest rate in percent"},
                "years": {"type": "integer", "description": "Loan term in years"}
            },
            "required": ["principal", "annual_rate", "years"],
        },
    }
]

# Simple in-memory session (for demonstration)
conversation_history = []

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    with open("static/index.html", "r") as f:
        return f.read()

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    global conversation_history
    data = await request.json()
    user_msg = data.get("message", "")
    force_local = data.get("force_local", False)
    
    if user_msg.lower() == "clear":
        conversation_history = []
        return {"response": "Conversation cleared!", "metrics": None}

    conversation_history.append({"role": "user", "content": user_msg})
    
    if force_local:
        result = generate_cactus(conversation_history, FINANCE_TOOLS)
        result["source"] = "on-device (forced)"
    else:
        # Run our hybrid router!
        result = generate_hybrid(conversation_history, FINANCE_TOOLS)
    
    # The result contains function_calls, let's format a response back
    calls = result.get("function_calls", [])
    
    if calls:
        blocks = [{"type": "text", "content": "Here are the results of my financial tool calls:\\n"}]
        text_for_history = "Here are the results of my financial tool calls:\\n"
        
        for c in calls:
            name = c["name"]
            args = c["arguments"]
            try:
                if name == "get_stock_price":
                    res = get_stock_price(**args)
                elif name == "get_company_news":
                    res = get_company_news(**args)
                elif name == "calculate_roi":
                    res = {"type": "text", "data": calculate_roi(**args)}
                elif name == "get_exchange_rate":
                    res = {"type": "text", "data": get_exchange_rate(**args)}
                elif name == "calculate_compound_interest":
                    res = {"type": "text", "data": calculate_compound_interest(**args)}
                elif name == "get_crypto_price":
                    res = {"type": "text", "data": get_crypto_price(**args)}
                elif name == "calculate_mortgage_payment":
                    res = {"type": "text", "data": calculate_mortgage_payment(**args)}
                else:
                    res = {"type": "text", "data": "Unknown tool."}
                
                if isinstance(res, dict) and "type" in res:
                    blocks.append(res)
                    if res.get("type") == "text":
                        text_for_history += f"- **{name}**: {res.get('data')}\\n"
                    elif res.get("type") == "stock_widget":
                        text_for_history += f"- **{name}**: Stock {res['data']['ticker']} is at ${res['data']['price']:.2f}\\n"
                    elif res.get("type") == "news_widget":
                        text_for_history += f"- **{name}**: Pulled top {len(res['data']['headlines'])} news headlines for {res['data']['ticker']}\\n"
                else:
                    blocks.append({"type": "text", "content": f"- **{name}**: {res}"})
                    text_for_history += f"- **{name}**: {res}\\n"
            except Exception as e:
                msg = f"- **{name}**: Error executing tool - {str(e)}"
                blocks.append({"type": "text", "content": msg})
                text_for_history += f"{msg}\\n"
                
        conversation_history.append({"role": "assistant", "content": text_for_history})
        agent_reply = blocks
    else:
        msg = "I couldn't determine a financial tool to use for that query."
        conversation_history.append({"role": "assistant", "content": msg})
        agent_reply = msg
        
    return {
        "response": agent_reply,
        "metrics": {
            "source": result.get("source", "unknown"),
            "confidence": result.get("confidence", 0.0),
            "latency_ms": result.get("total_time_ms", 0.0)
        }
    }

@app.post("/api/transcribe")
async def transcribe_endpoint(audio: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        text = transcribe_audio(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return {"text": text.strip()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
