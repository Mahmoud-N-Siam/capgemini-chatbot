# Capgemini Generative Engine Chatbot

A chatbot with document processing (PDF, DOCX, TXT) using Capgemini's Generative Engine API.

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure API key:
   ```bash
   cp .env.example .env
   # Edit .env with your CAPGEMINI_API_KEY
   ```

3. Run:
   ```bash
   python run.py
   ```

4. Open: http://localhost:5000

## Features
- Document upload (PDF, DOCX, TXT, MD)
- Context-aware chat
- REST API
- Vector search