import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[1] / ".env")




DATABRICKS_TOKEN = os.environ.get('DATABRICKS_TOKEN')

client = OpenAI(
  api_key=DATABRICKS_TOKEN,
  base_url="https://adb-2549848299256377.17.azuredatabricks.net/serving-endpoints"
)

chat_completion = client.chat.completions.create(
  messages=[
    {"role": "user", "content": "Hello!"},
    {"role": "assistant", "content": "Hello! How can I assist you today?"},
    {"role": "user", "content": "What is Databricks?"},
  ],
  model="system.ai.claude-opus-4-8",
  max_tokens=1024
)

print(chat_completion.choices[0].message.content)