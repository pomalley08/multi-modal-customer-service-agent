import httpx  
import json  
import asyncio  
import base64  
from pydub import AudioSegment  
from pydub.playback import play  
import os  
  
async def process_and_synthesize(prompt):  
    url = "http://127.0.0.1:8000/process_and_synthesize"  
    headers = {"Content-Type": "application/json"}  
  
    # Sample data  
    user_id = "test_user"  
    messages = [{"role": "user", "content": prompt}]  
    image_path = "img.png"  # Replace with the path to your image file  
  
    # Read and encode the image to base64  
    with open(image_path, "rb") as image_file:  
        image_bytes = image_file.read()  
        base64_image_str = base64.b64encode(image_bytes).decode('utf-8')  
      
    frames = [{"data": base64_image_str}]  
  
    data = {  
        "user_id": user_id,  
        "messages": messages,  
        "frames": frames  
    }  
    
    async with httpx.AsyncClient() as client:  
        response = await client.post(url, headers=headers, data=json.dumps(data))  
  
        if response.status_code == 200:  
            text = ''  
            audio_chunks = []  
  
            async for message in response.aiter_lines(): 
                print(message) 
                try:  
                    json_response = json.loads(message)  
                except json.JSONDecodeError:  
                    print("error")
                    continue  # If line is not valid JSON, skip it  
                if 'text' in json_response:  
                    text += json_response['text']  
                    print(f"Assistant: {json_response['text']}")  
  
                if 'audio_data' in json_response:  
                    audio_data = base64.b64decode(json_response['audio_data'])  
                    audio_chunks.append(audio_data)  
  
                    if audio_chunks:  
                        combined_audio = AudioSegment.from_raw(  
                            io.BytesIO(b''.join(audio_chunks)),  
                            sample_width=2,  # 16-bit audio  
                            frame_rate=24000,  # or the appropriate frame rate  
                            channels=1  # mono audio  
                        )  
                        play(combined_audio)  
                        audio_chunks = []  # Clear audio chunks for the next part  
        else:  
            print(f"Failed to process and synthesize: {response.status_code} - {response.text}")  
  
async def main():  
    prompt = "Hello, tell me a long story"  
    await process_and_synthesize(prompt)  
  
if __name__ == "__main__":  
    asyncio.run(main())  
