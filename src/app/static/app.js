const video = document.getElementById('video');  
const startButton = document.getElementById('startButton');  
const shareScreenButton = document.getElementById('shareScreenButton');  
  
let mediaRecorder;  
let audioStream;  
let videoStream;  
let screenStream;  
  
const serverAddress = 'https://studious-tribble-jr7v797gwj6fq57w-8000.app.github.dev';  
  
startButton.addEventListener('click', async () => {  
    // Get audio and video streams  
    audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });  
    videoStream = await navigator.mediaDevices.getUserMedia({ video: true });  
    video.srcObject = videoStream;  
  
    // Combine audio and video streams  
    const combinedStream = new MediaStream([...audioStream.getTracks(), ...videoStream.getTracks()]);  
    mediaRecorder = new MediaRecorder(combinedStream);  
    mediaRecorder.ondataavailable = handleDataAvailable;  
    mediaRecorder.start(1000); // Record in chunks of 1 second  
  
    // Establish WebSocket connection for sending video frames  
    const ws = new WebSocket(`${serverAddress.replace('https', 'wss')}/ws`);  
    ws.binaryType = 'arraybuffer';  
    ws.onopen = () => {  
        setInterval(() => {  
            // Capture video frame  
            const track = combinedStream.getVideoTracks()[0];  
            const imageCapture = new ImageCapture(track);  
            imageCapture.grabFrame().then(bitmap => {  
                // Draw frame onto canvas  
                const canvas = document.createElement('canvas');  
                canvas.width = bitmap.width;  
                canvas.height = bitmap.height;  
                const context = canvas.getContext('2d');  
                context.drawImage(bitmap, 0, 0, bitmap.width, bitmap.height);  
                  
                // Convert canvas to Blob and send via WebSocket  
                canvas.toBlob(blob => {  
                    const reader = new FileReader();  
                    reader.onload = () => {  
                        ws.send(reader.result);  
                    };  
                    reader.readAsArrayBuffer(blob);  
                });  
            });  
        }, 1000); // Send a frame every second  
    };  
});  
  
shareScreenButton.addEventListener('click', async () => {  
    // Handle screen sharing  
    screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true });  
    screenStream.getVideoTracks()[0].addEventListener('ended', () => {  
        console.log('Screen sharing ended');  
    });  
});  
  
function handleDataAvailable(event) {  
    // Handle audio data availability  
    if (event.data.size > 0) {  
        console.log("Sending audio data to server...");  
        sendAudioToServer(event.data);  
    }  
}  
  
async function sendAudioToServer(audioBlob) {  
    // Convert audio Blob to ArrayBuffer  
    const audioBuffer = await audioBlob.arrayBuffer();  
    const audioData = new Uint8Array(audioBuffer);  
  
    console.log("Audio data length:", audioData.length);  
  
    // Send audio data to server  
    const response = await fetch(`${serverAddress}/process_audio`, {  
        method: 'POST',  
        headers: { 'Content-Type': 'application/octet-stream' },  
        body: audioData  
    });  
  
    // Handle server response and play received audio  
    if (response.ok) {  
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();  
        const audioBuffer = await response.arrayBuffer();  
        const decodedAudio = await audioContext.decodeAudioData(audioBuffer);  
  
        const source = audioContext.createBufferSource();  
        source.buffer = decodedAudio;  
        source.connect(audioContext.destination);  
        source.start();  
    } else {  
        const textResponse = await response.json();  
        console.log(textResponse);  
    }  
}  
