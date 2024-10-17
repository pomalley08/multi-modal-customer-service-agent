from fastapi import FastAPI, WebSocket, Request  
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse  
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
import asyncio  
  
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
  
    user_sessions[user_id]['images'] = []  # Clear user images after sending to OpenAI  
  
    async def stream_openai_responses():  
        try:  
            response = client.chat.completions.create(  
                model=chat_deployment,  
                messages=[{"role": "user", "content": message_content}],  
                temperature=0,  
                stream=True  
            )  
            assistant_response = ""  
            spoken_sentence = ""  
            sentence_level_punctuations = ['.', '?', '!', ':', ';']  
  
            for chunk in response:  
                if len(chunk.choices) > 0:  
                    delta = chunk.choices[0].delta  
                    if delta.content:  
                        assistant_response += delta.content  
                        print("assistance reponse ",assistant_response )
                        # Aggregate response by sentence  
                        spoken_sentence += delta.content  
                        if any(punct in delta.content for punct in sentence_level_punctuations): 
 
                            yield json.dumps({"text": spoken_sentence}) + "\n"  
                              
                            # Synthesize the accumulated sentence  
                            speech_config = speechsdk.SpeechConfig(subscription=speech_api_key, region=speech_region)  
                            speech_config.speech_synthesis_language = "en-US"  
                            speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"  
  
                            pull_stream = speechsdk.audio.PullAudioOutputStream()  
                            audio_config = speechsdk.audio.AudioOutputConfig(stream=pull_stream)  
                            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)  
  
                            result = synthesizer.speak_text_async(spoken_sentence).get()  
                            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:  
                                audio_data = base64.b64encode(result.audio_data).decode('utf-8')  
                                print("send audio data")
                                yield json.dumps({"audio_data": audio_data})  + "\n"  
                            else:  
                                raise HTTPException(status_code=500, detail="Speech synthesis failed")  
                              
                            spoken_sentence = ""  
  
            # Yield any remaining spoken_sentence  
            if spoken_sentence:  
                yield json.dumps({"text": spoken_sentence}) + "\n"  
                  
                # Synthesize the remaining sentence  
                speech_config = speechsdk.SpeechConfig(subscription=speech_api_key, region=speech_region)  
                speech_config.speech_synthesis_language = "en-US"  
                speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"  
  
                pull_stream = speechsdk.audio.PullAudioOutputStream()  
                audio_config = speechsdk.audio.AudioOutputConfig(stream=pull_stream)  
                synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)  
  
                result = synthesizer.speak_text_async(spoken_sentence).get()  
                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:  
                    audio_data = base64.b64encode(result.audio_data).decode('utf-8')  
                    yield json.dumps({"audio_data": audio_data})  
                else:  
                    raise HTTPException(status_code=500, detail="Speech synthesis failed")  
  
        except Exception as e:  
            print(f"Error processing text with Azure OpenAI: {e}")  
            yield json.dumps({"error": "Failed to process text"})  
  
    return StreamingResponse(stream_openai_responses(), media_type="application/json")  
  
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
