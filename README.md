# Discord RAG Pipeline

Visualize and interact with your Discord data by combining scraping, vector embeddings, and LLM. Ask questions and let the AI automatically decide the best approach: RAG (semantic similarity) or SQL (structured queries).

## Overview

This application allows you to:

- Scrape a Discord server to retrieve text messages
- Generate OpenAI embeddings for each message (vectorization for RAG)
- Store messages and embeddings in SQLite with a vector table
- Ask questions in natural language and let the LLM decide between RAG or SQL
- Visualize the complete pipeline: query analysis, chosen approach, generated SQL (if applicable), full history

The frontend provides an intuitive interface to launch scraping, ask questions, and visualize results and data flow.

## Technical Architecture

- **Frontend**: React + Tailwind + Shadcn/ui
  - Scraping form → `/discord/{guild_id}`
  - Question form → `/ask`
  - Pipeline and history visualization
  
- **Backend**: FastAPI + Modal
  - `/discord/{guild_id}` → scrape, embeddings, storage
  - `/ask` → LLM decides RAG/SQL → backend executes → final result
  
- **Database**: SQLite + sqlite-vec extension `vec_discord_messages`

- **LLM**: Azure OpenAI GPT-4o for generation and function calling

- **Embeddings**: text-embedding-ada-002

- **Infrastructure**: Modal Volume for data persistence between serverless executions


## Code Structure
```
discord-rag-pipeline/
│
├── backend_service/                 
│   └── src/modal_app/
│       ├── main.py                  
│       │   ├── init_db()           # Create SQLite tables
│       │   ├── similarity_search() # Vector search (RAG)
│       │   ├── do_sql_query()      # Execute SQL
│       │   ├── /ask                # Endpoint for questions
│       │   └── /discord/{id}       # Endpoint for scraping
│       │
│       ├── discord.py              
│       │   ├── fetch_and_store_channel_messages()
│       │   └── scrape_discord_server()
│       │
│       └── common.py                
│           ├── TOOLS               # Function calling definition
│           ├── serialize()         # Convert vectors to bytes
│           └── get_db_conn()       # Database connection
│
└── frontend/                        
    └── src/
        └── App.tsx                  # Main component
            ├── Scraping form
            ├── Search bar
            └── Results display
```

## Database

### Table 1: Raw Messages
```sql
CREATE TABLE discord_messages (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);
```

### Table 2: Vectors (sqlite-vec)
```sql
CREATE VIRTUAL TABLE vec_discord_messages USING vec0(
    id TEXT PRIMARY KEY,
    embedding FLOAT[1536]  -- Vector of 1536 numbers
);
```

### Why Two Tables?

- **Table 1**: Stores textual data and metadata (messages, dates, authors)
- **Table 2**: Stores vectors for similarity search (RAG) via sqlite-vec

## Technologies Used

### Backend

- **FastAPI**: Modern and fast Python web framework
- **Modal**: Serverless platform for deploying Python
- **SQLite**: Lightweight and portable database
- **sqlite-vec**: Extension for vector support
- **Azure OpenAI**:
  - `text-embedding-ada-002` for generating embeddings
  - `gpt-4o` for text generation and function calling

### Frontend

- **React**: JavaScript library for UI
- **Vite**: Fast build tool
- **TailwindCSS**: Utility-first CSS framework
- **Shadcn/ui**: Pre-built UI components

### APIs

- **Discord API**: Message retrieval
- **OpenAI SDK / Azure OpenAI**: Interface for embeddings and text generation

## Usage / Demo

- The video shows complete usage: scraping, questions, and pipeline visualization
- Watch the demo here: [Discord RAG Pipeline Demo](https://drive.google.com/file/d/1ftKpU5cg5e7DkCRExCyLB5NZs0bcskC_/view?usp=sharing)

### Typical Flow:

1. Scrape a Discord server with its ID and a message limit
2. Ask a question in natural language about the scraped data
3. The AI automatically chooses RAG or SQL
4. Display the final answer and complete pipeline
5. Steps: Query Analysis → Processing Approach → Generated SQL (if applicable) → Interaction Flow
6. Tabs to view message history and raw JSON

## Notes

- All sensitive data processing (DB, embeddings) happens on the backend
- The LLM never directly touches the database
