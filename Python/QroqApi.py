import requests
import os

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

url = "https://api.groq.com/openai/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "model": "deepseek-v3",
    "messages": [
        {
            "role": "system",
            "content": "You are a professional English lexicographer."
        },
        {
            "role": "user",
            "content": "Clean and normalize this definition: abandon (verb)."
        }
    ],
    "temperature": 0.3,
    "max_tokens": 400
}

response = requests.post(url, headers=headers, json=payload)
response.raise_for_status()

print(response.json()["choices"][0]["message"]["content"])
