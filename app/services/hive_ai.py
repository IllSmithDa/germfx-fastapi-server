from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv
import os

# have to declare another env path for the api folder
env_path = Path("api/.env")
# Load the .env file
load_dotenv(dotenv_path=env_path)

hive_ai_api_key = os.getenv("HIVE_AI_API_KEY")

# Configure the client with custom base URL and API key
client = OpenAI(
    base_url="https://api.thehive.ai/api/v3/",  # Hive AI's endpoint
    api_key=hive_ai_api_key  # Replace with your API key
)

async def get_completion(prompt, model="meta-llama/llama-3.2-1b-instruct"):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1000
    )

    # Extract the response content
    return response.choices[0].message.content

async def effect_summary(effect_paragraph: str):
    result = await get_completion(f"I need to summarize the following side effects into a sideffect and summary key pair values as a object. The text will most likely have more than one side effect and so return it is a list of side effects and summary key pair object. Here is the summary: {effect_paragraph}")
    return {"side_effects": result}