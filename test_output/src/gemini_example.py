import os
import openai

openai.api_key = os.environ["OPENAI_API_KEY"]

# Create the model
model_engine = "gpt-3.5-turbo"

with open("system_prompt.md", "r") as f:
    system_prompt = f.read()

messages = [
    {"role": "system", "content": system_prompt},
]

response = openai.ChatCompletion.create(
    model=model_engine,
    messages=messages,
    temperature=0,
    max_tokens=8192,
    n=1,
    stop=None,
)

print(response.choices[0].message.content)