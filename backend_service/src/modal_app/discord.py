import sqlite3
import requests
import os
from .common import DB_PATH, DEFAULT_LIMIT, volume, get_db_conn, serialize
from typing import Dict
from openai import AzureOpenAI
DISCORD_BASE_URL = "https://discord.com/api/v10"

#écupérer les messages d’un channel Discord, les enregistrer dans la base, générer leurs embeddings
def fetch_and_store_channel_messages(
    channel_id: str, headers: Dict, limit: int = DEFAULT_LIMIT
) -> None:
    """Fetch up to limit messages from the given channel and store in SQLite."""
    # Client pour les embeddings (Ressource 1)
    embedding_client = AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_EMBEDDING_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        azure_endpoint=os.environ["AZURE_OPENAI_EMBEDDING_ENDPOINT"]
    )
    
    url = f"{DISCORD_BASE_URL}/channels/{channel_id}/messages?limit={limit}"

    #Envoie une requête HTTP GET
    resp = requests.get(url, headers=headers)



    # Handle permissions errors
    if resp.status_code == 403:
        print(f"[403 Forbidden] Skipping channel {channel_id} — no permission.")
        return

    resp.raise_for_status()
    #Transforme la réponse Discord en liste Python
    messages = resp.json()

#----------------------------------------

    # Connect to the database
    conn = get_db_conn(DB_PATH)
    cursor = conn.cursor()

    for msg in messages:
        message_id = msg["id"]
        author_id = msg["author"]["id"]
        content = msg["content"]
        timestamp = msg["timestamp"]
        
        # Skip empty messages
        if not content.strip():
            continue
        #--------------------------------------------------------- 
        # Insert or ignore if row already exists
        cursor.execute(
            """
                INSERT OR IGNORE INTO discord_messages (id, channel_id, author_id, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
            (message_id, channel_id, author_id, content, timestamp),
        )
        #-----------------------------------------------------
        # Generate embeddings using embedding client
        embedding = (
            embedding_client.embeddings.create(
                model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME"],
                input=content
            )
            .data[0]
            .embedding
        )
        
        cursor.execute(
            "SELECT id FROM vec_discord_messages WHERE id = ?", (message_id,)
        )
        row = cursor.fetchone()

        if row is None:
            cursor.execute(
                """
                INSERT INTO vec_discord_messages (id, embedding)
                VALUES (?, ?)
                """,
                (message_id, serialize(embedding)),
            )
        else:
            cursor.execute(
                """
                UPDATE vec_discord_messages
                SET embedding = ?
                WHERE id = ?
                """,
                (serialize(embedding), message_id),
            )

    conn.commit()
    conn.close()







def scrape_discord_server(guild_id: str, headers: Dict, limit: int = DEFAULT_LIMIT) -> None:
    """
    Fetch all channels from the given Discord server (guild),
    filter for text channels, and then fetch recent messages
    for each one, storing them in the database.
    """
    # 1) Get all channels
    channels_url = f"{DISCORD_BASE_URL}/guilds/{guild_id}/channels"
    response = requests.get(channels_url, headers=headers)
    response.raise_for_status()

    channels = response.json()

    # 2) Iterate over channels and scrape if it's a text channel
    for channel in channels:
        # Discord 'type=0' => GUILD_TEXT : seuls les channels texte ont des messages exploitables
        if channel.get("type") == 0:
            channel_id = channel["id"]
            print(f"Scraping channel: {channel['name']} (ID: {channel_id})")
            fetch_and_store_channel_messages(channel_id, headers, limit=limit)

    print(f"Done scraping up to {limit} messages from all text channels in guild {guild_id}.")