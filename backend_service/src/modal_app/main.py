import sqlite3
from modal import asgi_app
from .common import DB_PATH, VOLUME_DIR, app, fastapi_app, volume
import sqlite_vec
from openai import AzureOpenAI
from .common import DB_PATH, VOLUME_DIR, app, fastapi_app, get_db_conn, serialize, volume, TOOLS
import os
import json
from fastapi import Request
from .discord import scrape_discord_server, DEFAULT_LIMIT

#init db et fastapi
#Le volume (volume) est monté dans le conteneur pour persister la base SQLite entre les exécutions.
@app.function(
    volumes={VOLUME_DIR: volume},
)
def init_db():
    """Initialize the SQLite database with a simple table."""
    #Rechargement du volume
    volume.reload()
    #Connexion à SQLite
    conn = sqlite3.connect(DB_PATH)

    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    #Curseur SQL: Permet d’exécuter des requêtes SQL.
    cursor = conn.cursor()

    # Create tables
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS discord_messages (
            id TEXT PRIMARY KEY,
            channel_id TEXT NOT NULL,
            author_id TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_discord_messages USING vec0(
            id TEXT PRIMARY KEY,
            embedding FLOAT[1536]
        );
        """
    )


    conn.commit()
    conn.close()
    volume.commit()

@app.function(
    volumes={VOLUME_DIR: volume},
    timeout=2000 # increase the initial timeout (default is 5 mins), as the discord scrape done in the future takes a while
)
@asgi_app()
def fastapi_entrypoint():
    # Modal, lance la fonction init_db maintenant.
    init_db.remote()
    return fastapi_app



#--------------------------------------------
















def similarity_search(message: str, top_k: int = 15):
    # Client pour les embeddings (Ressource 1)
    embedding_client = AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_EMBEDDING_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        azure_endpoint=os.environ["AZURE_OPENAI_EMBEDDING_ENDPOINT"]
    )
    
    conn = get_db_conn(DB_PATH)
    cursor = conn.cursor()

    query_vec = embedding_client.embeddings.create(
        model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME"],
        input=message
    ).data[0].embedding
    
    query_bytes = serialize(query_vec)

    results = cursor.execute(
        """
        SELECT
            vec_discord_messages.id,
            distance,
            discord_messages.channel_id,
            discord_messages.author_id,
            discord_messages.content,
            discord_messages.created_at
        FROM vec_discord_messages
        LEFT JOIN discord_messages USING (id)
        WHERE embedding MATCH ?
          AND k = ?
        ORDER BY distance
        """,
        [query_bytes, top_k],
    ).fetchall()

    conn.close()
    return results



















 

def do_sql_query(sql_query: str):
    conn = get_db_conn(DB_PATH)
    cursor = conn.cursor()

    try:
        rows = cursor.execute(sql_query).fetchall()
        conn.close()
        return rows
    except Exception as e:
        return {"error": str(e)}
    







@fastapi_app.post("/ask")
async def ask_discord(request: Request):
    """
    This endpoint uses Azure OpenAI function calling to decide if we should:
    1) Do RAG (similarity search)
    2) Generate & execute SQL
    to answer the user's question.
    """
    # Client pour le chat (Ressource 2)
    chat_client = AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_CHAT_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        azure_endpoint=os.environ["AZURE_OPENAI_CHAT_ENDPOINT"]
    )
    
    body = await request.json()
    user_query = body.get("query", "")

    if not user_query:
        return {"error": "No query provided."}

    system_message = {
        "role": "system",
        "content":
            """
            You are a helpful assistant. You can answer user questions using either:

            1) RAG-based similarity search (when the user wants summarized info from the actual conversation content), OR
            2) Generating a SQL query if the user wants structured data queries.

            Please do not mix them. Decide which approach is best for the user's question.
            If you choose SQL, provide a valid SQL SELECT statement that references the 'discord_messages' table.
            here is the schema for the `discord_messages` table that we have:
            discord_messages (
                        id TEXT PRIMARY KEY,
                        channel_id TEXT NOT NULL,
                        author_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL
                    )
            """
    }

    user_message = {
        "role": "user",
        "content": user_query
    }


    messages = [system_message, user_message]



    # 1)CADRAGE  Ask the model to call our function
    completion = chat_client.chat.completions.create(
        model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
        messages=messages,
        tools=TOOLS,
        tool_choice={"type": "function", "function": {"name": "decide_approach"}}
    )
    


    completion_message = completion.choices[0].message
    messages.append(completion_message)
    #tool_calls contient la décision du modèle
    tool_calls = completion_message.tool_calls

    # 2) Parse the function call
    if not tool_calls:
        return {
            "answer": "No function call was produced by the LLM. Could not proceed."
        }
        

    for tool_call in tool_calls:
        fn_name = tool_call.function.name
        fn_args = json.loads(tool_call.function.arguments)
        approach = fn_args.get("approach", "rag")
        print(f"approach: {approach}")

        # 3) If approach == 'rag', do the existing similarity_search
        if approach == "rag":
            rag_data = similarity_search(user_query)
            #Injection des résultats dans la conversation, tool → résultat d’une action externe
            messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": fn_name,
                    "content": str(rag_data),
                }
            )
            final_response = chat_client.chat.completions.create(
                model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
                messages=messages,
            )
            messages.append(final_response.choices[0].message)
            return {
                "answer": final_response.choices[0].message.content,
                "chat_history": messages
            }

        # 4) If approach == 'sql', let's run the sql_query
        elif approach == "sql":
            sql_query = fn_args.get("sql_query", "")
            if not sql_query.strip():
                return {"answer": "No SQL query provided by LLM."}

            # Attempt to run it
            sql_data = do_sql_query(sql_query)
            messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": fn_name,
                    "content": str(sql_data),
                }
            )
            final_response = chat_client.chat.completions.create(
                model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
                messages=messages,
            )
            messages.append(final_response.choices[0].message)
            return {
                "answer": final_response.choices[0].message.content,
                "chat_history": messages,
            }     


@fastapi_app.post("/discord/{guild_id}")
async def scrape_server(guild_id: str, limit: int = DEFAULT_LIMIT):
    discord_token = os.environ["DISCORD_TOKEN"]
    headers = {
        "Authorization": discord_token,
        "Content-Type": "application/json"
    }
    volume.reload()
    scrape_discord_server(guild_id, headers, limit)
    volume.commit()
    return {"status": "ok", "message": f"Scraped guild_id={guild_id}, limit={limit}"}