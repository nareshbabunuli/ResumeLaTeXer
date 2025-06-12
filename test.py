from mistralai import mistralai

api_key = 'wM8dditElK9QpjBEotBC2t9XSJupujL0'  # Replace with your actual API key
client = Mistral(api_key=api_key)

response = client.chat.complete(
    model="mistral-large-latest",
    messages=[{"role": "user", "content": "Hello, Mistral AI!"}]
)

print(response.choices[0].message.content)
