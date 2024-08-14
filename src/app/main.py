from fastapi import FastAPI, WebSocket, Request  
from fastapi.responses import StreamingResponse, JSONResponse,HTMLResponse
import azure.cognitiveservices.speech as speechsdk  

from fastapi.staticfiles import StaticFiles  
from fastapi.templating import Jinja2Templates  
import openai  
import cv2  
import numpy as np  
from dotenv import load_dotenv  
from fastapi.middleware.cors import CORSMiddleware  
import os  
import requests  
from fastapi import FastAPI, HTTPException  
import json  
import base64  
  
# Load environment variables from .env file  
load_dotenv()  
  
app = FastAPI()  
  
# Mount static files  
app.mount("/static", StaticFiles(directory="static"), name="static")  
  
templates = Jinja2Templates(directory="templates")  
  
# Retrieve keys from environment variables  
azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")  
azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")  
speech_api_key = os.getenv("SPEECH_API_KEY")  
speech_region = os.getenv("SPEECH_REGION")  
chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")  
client = openai.AzureOpenAI(  
    azure_endpoint=azure_openai_endpoint,  
    api_key=azure_openai_api_key,  
    api_version="2024-02-01"  
)  
  
# Allow CORS  
origins = [  
    "http://localhost",  
    "http://localhost:8000",  
    "http://127.0.0.1:8000",  
    "https://studious-tribble-jr7v797gwj6fq57w-8000.app.github.dev"  
]  
  
app.add_middleware(  
    CORSMiddleware,  
    allow_origins=["*"],  
    allow_credentials=True,  
    allow_methods=["*"],  
    allow_headers=["*"],  
)  
  
# Dictionary to store user sessions  
user_sessions = {}  
  
@app.get("/", response_class=HTMLResponse)  
async def get(request: Request):  
    return templates.TemplateResponse("index.html", {"request": request})  
  
@app.post("/process_and_synthesize")  
async def process_and_synthesize(request: Request):  
    data = await request.json()  
    user_id = data.get("user_id")  
    messages = data.get("messages")  
    frames = data.get("frames", [])  # Get frames from the request  
  
    if not messages or not user_id:  
        return JSONResponse(content={"error": "No messages or user ID provided"}, status_code=400)  
  
    # Retrieve user session  
    user_session = user_sessions.get(user_id, {'images': []})  
  
    try:  
        # Append new frames to the user session  
        user_session['images'].extend(frames)  
        user_sessions[user_id] = user_session  # Update the session with new frames  
  
        # Prepare the message content  
        message_content = [{"type": "text", "text": messages[-1]['content']}]  
  
        # Append images to the message content  
        images = user_session["images"]  
        if len(images) > 0:  
            message_content.append({"type": "text", "text": "here are images from the camera: "})  
        for base64_image in user_session['images']:  
            image_bytes = base64.b64decode(base64_image['data'])  
            base64_image_str = base64.b64encode(image_bytes).decode('utf-8')  
            message_content.append({  
                "type": "image_url",  
                "detail": "low",  
                "image_url": {  
                    "url": f"data:image/jpeg;base64,{base64_image_str}",  
                },  
            })  
  
        response = client.chat.completions.create(  
            model=chat_deployment,  
            messages=[  
                {  
                    "role": "user",  
                    "content": message_content,  
                }  
            ],  
        )  
  
        # Clear user images after sending to OpenAI  
        user_sessions[user_id]['images'] = []  
  
        assistant_response = response.choices[0].message.content  
  
        # Set up the speech config  
        speech_config = speechsdk.SpeechConfig(subscription=speech_api_key, region=speech_region)  
        speech_config.speech_synthesis_language = "en-US"  
        speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"  
  
        # Create a pull audio output stream  
        pull_stream = speechsdk.audio.PullAudioOutputStream()  
        audio_config = speechsdk.audio.AudioOutputConfig(stream=pull_stream)  
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)  
  
        # Synthesize the text to the pull stream  
        result = synthesizer.speak_text_async(assistant_response).get()  
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:  
            # Stream the audio data to the client  
            def audio_stream():  
                audio_buffer = bytes(32000)  
                filled_size = pull_stream.read(audio_buffer)  
                while filled_size > 0:  
                    yield audio_buffer[:filled_size]  
                    filled_size = pull_stream.read(audio_buffer)  
  
            # Create a multipart response  
            boundary = "speech_boundary"  
            headers = {  
                "Content-Type": f"multipart/mixed; boundary={boundary}"  
            }  
  
            def multipart_stream():  
                # Text part  
                yield f"--{boundary}\r\n"  
                yield "Content-Type: application/json\r\n\r\n"  
                yield json.dumps({"text": assistant_response})  
                yield "\r\n"  
  
                # Audio part  
                yield f"--{boundary}\r\n"  
                yield "Content-Type: audio/wav\r\n\r\n"  
                for chunk in audio_stream():  
                    yield base64.b64encode(chunk).decode('utf-8')  
                yield "\r\n"  
  
                # End boundary  
                yield f"--{boundary}--\r\n"  
  
            return StreamingResponse(multipart_stream(), headers=headers)  
        else:  
            raise HTTPException(status_code=500, detail="Speech synthesis failed")  
  
    except Exception as e:  
        print(f"Error processing text with Azure OpenAI: {e}")  
        return JSONResponse(content={"error": "Failed to process text"}, status_code=500)  
  
@app.get("/api/get-speech-token")  
async def get_speech_token():  
    if not speech_api_key or not speech_region:  
        raise HTTPException(status_code=400, detail="You forgot to add your speech key or region to the .env file.")  
  
    headers = {  
        'Ocp-Apim-Subscription-Key': speech_api_key,  
        'Content-Type': 'application/x-www-form-urlencoded'  
    }  
  
    try:  
        token_response = requests.post(f"https://{speech_region}.api.cognitive.microsoft.com/sts/v1.0/issueToken", headers=headers)  
        token_response.raise_for_status()  
        token = token_response.text  
        return JSONResponse(content={"token": token, "region": speech_region})  
    except requests.exceptions.RequestException as e:  
        raise HTTPException(status_code=401, detail="There was an error authorizing your speech key.")  
