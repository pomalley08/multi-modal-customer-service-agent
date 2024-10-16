import os
import json
from dotenv import load_dotenv
from aiohttp import web
# from ragtools import attach_rag_tools
from hotel_tools import attach_hotel_tools, attach_hotel_tools_as_backup, get_system_message as get_hotel_system_message
from flight_tools import attach_flight_tools, attach_flight_tools_as_backup, get_system_message as get_flight_system_message
from rtmt import RTMiddleTier
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential


if __name__ == "__main__":
    load_dotenv()
    llm_endpoint = os.environ.get("AZURE_OPENAI_RT_ENDPOINT")
    llm_deployment = os.environ.get("AZURE_OPENAI_RT_DEPLOYMENT")
    llm_key = os.environ.get("AZURE_OPENAI_RT_API_KEY")
    search_endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
    search_index = os.environ.get("AZURE_SEARCH_INDEX")
    search_key = os.environ.get("AZURE_SEARCH_API_KEY")

    credentials = DefaultAzureCredential() if not llm_key or not search_key else None

    app = web.Application()

    rtmt = RTMiddleTier(llm_endpoint, llm_deployment, AzureKeyCredential(llm_key) if llm_key else credentials)
    with open('../../../data/user_profile.json') as f:
        user_profile = json.load(f)
    # print(user_profile)
    system_message = get_hotel_system_message().format(customer_name =user_profile['name'], customer_id=user_profile['customer_id'])
    backup_system_message = get_flight_system_message().format(customer_name =user_profile['name'], customer_id=user_profile['customer_id'])

    rtmt.system_message = system_message
    rtmt.backup_system_message = backup_system_message

    attach_hotel_tools(rtmt)
    attach_flight_tools_as_backup(rtmt)

    rtmt.attach_to_app(app, "/realtime")

    app.add_routes([web.get('/', lambda _: web.FileResponse('./static/index.html'))])
    app.router.add_static('/', path='./static', name='static')
    web.run_app(app, host='localhost', port=8765)
