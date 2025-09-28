import os
from dotenv import load_dotenv

load_dotenv()  # This loads the .env file into os.environ

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

for m in genai.list_models():
    print(m.name)
