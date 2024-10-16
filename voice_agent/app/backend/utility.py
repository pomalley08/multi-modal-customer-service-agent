import yaml  
from typing import Any  
import os  
from sqlalchemy.ext.declarative import declarative_base  
from sqlalchemy.orm import sessionmaker, relationship  
from datetime import datetime  
import random  
from dotenv import load_dotenv  
from openai import AsyncAzureOpenAI  
from pathlib import Path  
import json  
from scipy import spatial  # for calculating vector similarities for search  
# Load YAML file  
import yaml
# Load YAML file  
def load_entity(file_path, entity_name):  
    with open(file_path, 'r') as file:  
        data = yaml.safe_load(file)  
    for entity in data['agents']:  
        if entity.get('name') == entity_name:  
            return entity  
    return None  
  
# Load environment variables  
env_path = Path('./') / '.env'  
load_dotenv(dotenv_path=env_path)  
async_client = AsyncAzureOpenAI(  
    api_key=os.environ.get("AZURE_OPENAI_API_KEY"),  
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),  
    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),  
)  
chat_deployment=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT")
prompt_template = load_entity('prompt.yaml', "classifier_agent")["persona"]

async def detect_intent_change(job_description, conversation):
        
        conversation= [{"role":"user", "content":prompt_template.format(job_description=job_description, conversation=conversation)}]

        response = await async_client.chat.completions.create(  
            model=chat_deployment,  
            messages=conversation,  
        )  
        return response.choices[0].message.content.lower()
