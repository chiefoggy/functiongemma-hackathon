# Launch Guide for Deep-Focus Webapp

## Quick Start

### Option 1: Use the Launch Script (Recommended)

```bash
./launch.sh
```

This will:
- Check and install dependencies if needed
- Start the backend server on http://localhost:8000
- Start the frontend server on http://localhost:3000
- Open your browser to http://localhost:3000

### Option 2: Manual Launch

#### Terminal 1: Start Backend
```bash
cd /Users/weidong/Documents/development/cactus-gemini
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

#### Terminal 2: Start Frontend
```bash
cd /Users/weidong/Documents/development/cactus-gemini/frontend
npm run dev
```

Then open http://localhost:3000 in your browser.

## Prerequisites

### 1. Python Dependencies
```bash
pip3 install -r backend/requirements.txt
```

Required packages:
- fastapi
- uvicorn
- python-multipart (for file uploads)
- pypdf (for PDF parsing)
- python-docx (for DOCX parsing)
- openpyxl (for Excel parsing)

### 2. Node.js Dependencies
```bash
cd frontend
npm install
```

### 3. Environment Variables

Make sure `.env` file exists in the project root with:
```bash
GEMINI_API_KEY=your_gemini_api_key_here
CACTUS_API_KEY=your_cactus_api_key_here
```

## Verification

### Check Backend
- Backend API: http://localhost:8000/health
- API Docs: http://localhost:8000/docs

### Check Frontend
- Frontend: http://localhost:3000
- The frontend proxies API calls to the backend automatically

## Troubleshooting

### Backend won't start
1. Check if port 8000 is already in use: `lsof -i :8000`
2. Make sure Python dependencies are installed
3. Check `.env` file exists and has valid API keys

### Frontend won't start
1. Check if port 3000 is already in use: `lsof -i :3000`
2. Make sure Node.js dependencies are installed: `cd frontend && npm install`
3. Check that backend is running first

### RAG not working
1. Set a library root in the UI
2. Click "Re-index" to index your files
3. Check backend logs for indexing errors
4. Verify corpus: http://localhost:8000/api/library/verify-corpus

## Development Tips

- Backend auto-reloads on file changes (--reload flag)
- Frontend hot-reloads on file changes
- Check backend logs in Terminal 1 for debugging
- Use browser DevTools for frontend debugging
