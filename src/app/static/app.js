const video = document.getElementById('video');  
const startButton = document.getElementById('startButton');  
const stopButton = document.getElementById('stopButton');  
const shareScreenButton = document.getElementById('shareScreenButton');  
const userPromptInput = document.getElementById('userPrompt');  
const sendButton = document.getElementById('sendButton');  
const micButton = document.getElementById('micButton');  
  
let videoStream;  
let screenStream;  
let speechRecognizer;  
let listening = false; // Variable to track the listening state  
const serverAddress = 'http://localhost:8000';  
const userId = generateUserId(); // Generate a unique user ID  
  
const speechsdk = window.SpeechSDK;  
let messageList = [{ role: 'system', content: 'You are a talking AI chatbot. You also user via video camera. Answer very briefly and encode the message with SSML to optimize for speaking.' }];  
const maxMessages = 10;  
const frameBuffer = []; // Buffer to store the last 5 frames  
const maxFrames = 3;  
  
let speechSynthesizer; // Keep a reference to the speech synthesizer  
let player; // Define the player globally  
let isSpeaking = false; // Track if TTS is currently speaking  
  
startButton.addEventListener('click', async () => {  
    try {  
        // Get video stream from camera  
        videoStream = await navigator.mediaDevices.getUserMedia({ video: true });  
        video.srcObject = videoStream;  
  
        // Buffer video frames  
        setInterval(() => {  
            bufferVideoFrame(videoStream, 'camera');  
        }, 4000); // Buffer a frame every 4 seconds  
    } catch (error) {  
        console.error('Error starting session:', error);  
    }  
});  
  
stopButton.addEventListener('click', () => {  
    if (videoStream) {  
        videoStream.getTracks().forEach(track => track.stop());  
    }  
    if (screenStream) {  
        screenStream.getTracks().forEach(track => track.stop());  
    }  
});  
  
shareScreenButton.addEventListener('click', async () => {  
    try {  
        // Get the screen sharing stream  
        screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true });  
        video.srcObject = screenStream;  
  
        // Buffer screen sharing frames  
        setInterval(() => {  
            bufferVideoFrame(screenStream, 'screen');  
        }, 1000); // Buffer a frame every second  
  
        // Handle screen sharing end event  
        screenStream.getVideoTracks()[0].addEventListener('ended', () => {  
            console.log('Screen sharing ended');  
            // Optionally, revert to the original video stream here  
        });  
    } catch (error) {  
        console.error('Error sharing screen:', error);  
    }  
});  
  
async function bufferVideoFrame(stream, type) {  
    const track = stream.getVideoTracks()[0];  
    const imageCapture = new ImageCapture(track);  
    const bitmap = await imageCapture.grabFrame();  
  
    // Define the desired width and height for the resized frames  
    const desiredWidth = 640; // Adjust this value as needed  
    const desiredHeight = 480; // Adjust this value as needed  
  
    // Draw frame onto a smaller canvas  
    const canvas = document.createElement('canvas');  
    canvas.width = desiredWidth;  
    canvas.height = desiredHeight;  
    const context = canvas.getContext('2d');  
    context.drawImage(bitmap, 0, 0, desiredWidth, desiredHeight);  
  
    // Convert canvas to Blob and buffer the frame  
    canvas.toBlob(blob => {  
        const reader = new FileReader();  
        reader.onload = () => {  
            const frame = {  
                type: type,  
                data: reader.result.split(',')[1] // Base64 encoded string without metadata  
            };  
  
            // Add frame to the buffer  
            if (frameBuffer.length >= maxFrames) {  
                frameBuffer.shift(); // Remove the oldest frame  
            }  
            frameBuffer.push(frame);  
        };  
        reader.readAsDataURL(blob); // Read as Data URL to get Base64 encoded string  
    });  
}  
  
sendButton.addEventListener('click', () => {  
    const userPrompt = userPromptInput.value;  
    if (userPrompt) {  
        addMessageToList('user', userPrompt);  
        processAndSynthesize(userPrompt);  
    }  
});  
  
function addMessageToList(role, content) {  
    if (messageList.length > maxMessages) {  
        messageList.splice(1, 1);  
    }  
    messageList.push({ role, content });  
    console.log("Message List:", messageList);  
}  
  
async function processAndSynthesize(prompt) {  
    try {  
        // Prepare the payload with the entire messageList and frame buffer  
        const payload = {  
            user_id: userId,  // Include the user ID  
            messages: messageList,  
            frames: frameBuffer  
        };  
  
        const response = await fetch(`${serverAddress}/process_and_synthesize`, {  
            method: 'POST',  
            headers: {  
                'Content-Type': 'application/json'  
            },  
            body: JSON.stringify(payload)  
        });  
  
        if (response.ok) {  
            const boundary = response.headers.get('Content-Type').split('boundary=')[1];  
            const reader = response.body.getReader();  
            const decoder = new TextDecoder('utf-8');  
            let text = '';  
            let audioChunks = [];  
  
            while (true) {  
                const { done, value } = await reader.read();  
                if (done) break;  
                const chunk = decoder.decode(value, { stream: true });  
                text += chunk;  
            }  
  
            const parts = text.split(`--${boundary}`);  
            for (const part of parts) {  
                if (part.includes('Content-Type: application/json')) {  
                    const jsonPart = part.split('\r\n\r\n')[1];  
                    const jsonResponse = JSON.parse(jsonPart);  
                    console.log("Text Part:", jsonResponse);  
                    addMessageToList('assistant', jsonResponse.text);  
                } else if (part.includes('Content-Type: audio/wav')) {  
                    const audioPart = part.split('\r\n\r\n')[1].split('\r\n')[0];  
                    const audioBuffer = Uint8Array.from(atob(audioPart), c => c.charCodeAt(0));  
                    audioChunks.push(audioBuffer);  
                }  
            }  
  
            console.log("Audio Chunks:", audioChunks);  
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });  
            console.log("Audio Blob:", audioBlob);  
            const audioUrl = URL.createObjectURL(audioBlob);  
            console.log("Audio URL:", audioUrl);  
            const audio = new Audio(audioUrl);  
            audio.play();  
        } else {  
            console.error("Failed to process and synthesize:", response.statusText);  
        }  
    } catch (error) {  
        console.error("Error in process and synthesize:", error);  
    }  
}  
  
// Function to stop the current speech synthesis  
function stopSpeechSynthesis() {  
    if (isSpeaking && player && player.internalAudio) {  
        try {  
            player.internalAudio.currentTime = player.internalAudio.duration; // Fast forward to the end  
            console.log("Text-to-speech stopped.");  
        } catch (error) {  
            console.error("Error stopping text-to-speech:", error);  
        }  
    }  
}  
  
// Toggle Continuous Speech Recognition  
micButton.addEventListener('click', async () => {  
    if (!listening) {  
        // Start listening  
        const tokenObj = await getTokenOrRefresh();  
        const speechConfig = speechsdk.SpeechConfig.fromAuthorizationToken(tokenObj.authToken, tokenObj.region);  
        speechConfig.speechRecognitionLanguage = 'en-US';  
        const audioConfig = speechsdk.AudioConfig.fromDefaultMicrophoneInput();  
        speechRecognizer = new speechsdk.SpeechRecognizer(speechConfig, audioConfig);  
  
        speechRecognizer.recognizing = (s, e) => {  
            console.log(`Recognizing: ${e.result.text}`);  
        };  
  
        speechRecognizer.recognized = (s, e) => {  
            if (e.result.reason === speechsdk.ResultReason.RecognizedSpeech) {  
                const audioPrompt = e.result.text;  
  
                addMessageToList('user', audioPrompt);  
                processAndSynthesize(audioPrompt);  // Call the API with recognized speech text  
            } else {  
                console.error("Speech recognition failed:", e.result.errorDetails);  
            }  
        };  
  
        speechRecognizer.startContinuousRecognitionAsync();  
        micButton.innerHTML = "&#128308;"; // Change to red circle  
        listening = true;  
    } else {  
        // Stop listening  
        if (speechRecognizer) {  
            speechRecognizer.stopContinuousRecognitionAsync();  
        }  
        micButton.innerHTML = "&#127908;"; // Change back to microphone icon  
        listening = false;  
    }  
});  
  
async function getTokenOrRefresh() {  
    try {  
        const response = await fetch(`${serverAddress}/api/get-speech-token`);  
        if (!response.ok) {  
            throw new Error(`Failed to fetch token: ${response.statusText}`);  
        }  
        const tokenResponse = await response.json();  
        return { authToken: tokenResponse.token, region: tokenResponse.region };  
    } catch (error) {  
        console.error("Error fetching token:", error);  
    }  
}  
  
function generateUserId() {  
    return '_' + Math.random().toString(36).substr(2, 9);  
}  
