import yaml  
from typing import Any  
from rtmt import RTMiddleTier, Tool, ToolResult, ToolResultDirection  
import os  
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey  
from sqlalchemy.ext.declarative import declarative_base  
from sqlalchemy.orm import sessionmaker, relationship  
from datetime import datetime  
import random  
from dotenv import load_dotenv  
from openai import AzureOpenAI  
from pathlib import Path  
from flight_tools import query_flights, search_airline_knowledgebase,load_user_flight_info, confirm_flight_change,check_change_booking
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
  
def transform_tools(tools):  
    transformed_tools = []  
    for tool in tools:  
        transformed_tool = {  
            "type": "function",  
            "function": {  
                "name": tool['name'],  
                "description": tool['description'],  
                "parameters": tool.get('parameters', {})  
            }  
        }  
        transformed_tools.append(transformed_tool)  
    return transformed_tools    
# Load environment variables  
env_path = Path('./') / '.env'  
load_dotenv(dotenv_path=env_path)  
index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")  
  
# SQLAlchemy setup  
Base = declarative_base()  
engine = create_engine('sqlite:///../../../data/hotel.db')  
Session = sessionmaker(bind=engine)  
session = Session()  
client = AzureOpenAI(  
    api_key=os.environ.get("AZURE_OPENAI_API_KEY"),  
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),  
    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),  
)  
chat_deployment=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT")
flight_agent =load_entity('smart_prompt.yaml', "flight_agent")
flight_function_spec = transform_tools(flight_agent.get('tools', []))
flight_agent_system_message = flight_agent.get('persona', "")
flight_function_map={
"query_flights":query_flights, 
"search_airline_knowledgebase":search_airline_knowledgebase,
"load_user_flight_info":load_user_flight_info,
"confirm_flight_change":confirm_flight_change,
"check_change_booking":check_change_booking

}

def agent_function(user_request, system_message, function_spec, function_map):
        conversation= [{"role":"system", "content":system_message},{"role":"user", "content":user_request}]

        response = client.chat.completions.create(  
            model=chat_deployment,  
            messages=conversation,  
            tools=function_spec,  
            tool_choice='auto',  
        )  
        response_message = response.choices[0].message  
        if response_message.content is None:  
            response_message.content = ""  
        tool_calls = response_message.tool_calls  

        if tool_calls:  
            conversation.append(response_message)  # extend conversation with assistant's reply  
            for tool_call in tool_calls:  
                function_name = tool_call.function.name  
                function_to_call = function_map[function_name] 
                function_args = json.loads(tool_call.function.arguments) 
                function_response = str(function_to_call(**function_args))
                conversation.append(  
                    {  
                        "tool_call_id": tool_call.id,  
                        "role": "tool",  
                        "name": function_name,  
                        "content": function_response,  
                    })
        assistant_response = dict(response_message).get('content')
        print("assistant response", assistant_response)

        return assistant_response

def flight_super_tool(request_details):

    return agent_function(request_details,flight_agent_system_message,flight_function_spec, flight_function_map)


    
agent = load_entity('smart_prompt.yaml', "front_desk_agent")

# Define your functions  
def smart_tool(request_details):  
    print("user request\n", request_details)  
    return flight_super_tool(request_details) 


  
  
async def smart_tool_async(args: Any) -> ToolResult:  
    user_request = args['request_details']  
    result = smart_tool(user_request)  
    return ToolResult(result, ToolResultDirection.TO_SERVER)  
  

def get_system_message():
    return agent.get('persona', "")
# Attach tools  
def attach_tools(rtmt: RTMiddleTier) -> None:  
    
    for tool in agent.get('tools', []):
        tool_name = tool['name']  
        tool_schema = {  
            "type": tool['type'],  
            "name": tool['name'],  
            "description": tool['description'],  
            "parameters": tool['parameters']  
        }  
        if tool_name == "smart_tool":  
            rtmt.tools[tool_name] = Tool(schema=tool_schema, target=smart_tool_async)  

