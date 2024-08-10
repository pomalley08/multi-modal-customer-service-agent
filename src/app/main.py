from fastapi import FastAPI, File, UploadFile, WebSocket  
from fastapi.responses import HTMLResponse, JSONResponse  
from fastapi.staticfiles import StaticFiles  
from fastapi.templating import Jinja2Templates  
import azure.cognitiveservices.speech as speechsdk  
import openai  
import cv2  
import numpy as np  
from starlette.requests import Request  
from dotenv import load_dotenv  
import os  
import requests  
  
# Load environment variables from .env file  
load_dotenv()  
  
app = FastAPI()  
  
# Mount static files  
app.mount("/static", StaticFiles(directory="static"), name="static")  
  
templates = Jinja2Templates(directory="templates")  
  
# Retrieve keys from environment variables  
azure_subscription_key = os.getenv("AZURE_SUBSCRIPTION_KEY")  
azure_region = os.getenv("AZURE_REGION")  
azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")  
azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")  
  
speech_config = speechsdk.SpeechConfig(subscription=azure_subscription_key, region=azure_region)  
  
@app.get("/", response_class=HTMLResponse)  
async def get(request: Request):  
    return templates.TemplateResponse("index.html", {"request": request})  
  
@app.post("/process_audio")  
async def process_audio(file: UploadFile = File(...)):  
    try:  
        audio_data = await file.read()  
        print(f"Received audio data of length: {len(audio_data)}")  
          
        audio_input = speechsdk.AudioConfig(stream=speechsdk.audio.PushAudioInputStream())  
        stream = speechsdk.audio.PushAudioInputStream()  
        stream.write(audio_data)  
        stream.close()  
  
        audio_config = speechsdk.audio.AudioConfig(stream=stream)  
        recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)  
        result = recognizer.recognize_once()  
          
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:  
            text = result.text  
            response = await process_with_azure_openai(text)  
            return JSONResponse(content={"text": text, "response": response})  
        else:  
            return JSONResponse(content={"error": "Speech not recognized"})  
    except Exception as e:  
        print(f"Error processing audio: {e}")  
        return JSONResponse(content={"error": "Failed to process audio"}, status_code=500)  
  
async def process_with_azure_openai(text: str):  
    headers = {  
        "Content-Type": "application/json",  
        "api-key": azure_openai_api_key  
    }  
  
    data = {  
        "prompt": text,  
        "max_tokens": 150  
    }  
  
    response = requests.post(  
        f"{azure_openai_endpoint}/openai/deployments/text-davinci-002/completions?api-version=2022-12-01",  
        headers=headers,  
        json=data  
    )  
  
    if response.status_code == 200:  
        return response.json()["choices"][0]["text"].strip()  
    else:  
        print(f"Error with Azure OpenAI API: {response.status_code}, {response.text}")  
        return "Error processing with Azure OpenAI"  
  
@app.websocket("/ws")  
async def websocket_endpoint(websocket: WebSocket):  
    await websocket.accept()  
    while True:  
        data = await websocket.receive_bytes()  
        frame = np.frombuffer(data, np.uint8).reshape((480, 640, 3))  # Adjust shape as needed  
        edges = analyze_frame(frame)  
        if detect_significant_change(edges):  
            # Send frame to Azure OpenAI  
            pass  
  
def analyze_frame(frame):  
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  
    edges = cv2.Canny(gray_frame, 50, 150)  
    return edges  
  
def detect_significant_change(edges):  
    # Implement your logic to detect significant changes  
    return np.sum(edges) > 1000  # Example threshold  
