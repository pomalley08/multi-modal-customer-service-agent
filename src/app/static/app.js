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
  
let audioQueue = []; // Queue to store the audio chunks  
let isPlayingAudio = false; // Track if an audio chunk is currently playing  
let currentAudio = null; // Keep track of the currently playing audio element  
  
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
            for await (const jsonResponse of readNDJSONStream(response.body)) {  
                console.log("Response:", jsonResponse);  
  
                if (jsonResponse.text) {  
                    addMessageToList('assistant', jsonResponse.text);  
                }  
  
                if (jsonResponse.audio_data) {  
                    console.log("receive audio data")  
                    const audioBuffer = Uint8Array.from(atob(jsonResponse.audio_data), c => c.charCodeAt(0));  
                    const audioBlob = new Blob([audioBuffer], { type: 'audio/wav' });  
                    const audioUrl = URL.createObjectURL(audioBlob);  
                    audioQueue.push(audioUrl); // Add audio to the queue  
                    playNextAudio(); // Attempt to play the next audio chunk  
                }  
            }  
        } else {  
            console.error("Failed to process and synthesize:", response.statusText);  
        }  
    } catch (error) {  
        console.error("Error in process and synthesize:", error);  
    }  
}  
  
function playNextAudio() {  
    if (isPlayingAudio || audioQueue.length === 0) {  
        return; // Return if already playing or no audio in queue  
    }  
  
    isPlayingAudio = true;  
    const audioUrl = audioQueue.shift();  
    const audio = new Audio(audioUrl);  
    currentAudio = audio; // Set the current audio element  
    audio.onended = () => {  
        isPlayingAudio = false; // Mark as not playing when done  
        currentAudio = null; // Clear the current audio element  
        playNextAudio(); // Play next audio chunk if available  
    };  
    audio.play();  
}  
  
function stopAndClearAudioQueue() {  
    // Stop the currently playing audio  
    if (currentAudio) {  
        currentAudio.pause();  
        currentAudio.currentTime = 0;  
        currentAudio = null;  
    }  
  
    // Clear the audio queue  
    audioQueue = [];  
    isPlayingAudio = false; // Ensure the flag is reset so new audio can be played  
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
  
                // Stop the currently playing audio and clear the queue  
                stopAndClearAudioQueue();  
  
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
