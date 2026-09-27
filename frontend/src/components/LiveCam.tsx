import React, { useEffect, useRef, useState } from "react";
import { apiFetch, getSettingsRoutes } from "@/utils/storage";

export default function LiveCam() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [status, setStatus] = useState<string>("Initializing camera...");
  const [user, setUser] = useState<any>(null);
  
  const [isRecognizing, setIsRecognizing] = useState(false);

  // Trip management state
  const [currentStop, setCurrentStop] = useState<string>("Stop A");
  const [stops, setStops] = useState<string[]>([]);
  const [isEntry, setIsEntry] = useState(true);

  const [arduinoConnected, setArduinoConnected] = useState(false);

  useEffect(() => {
    // Load stops for simulation
    getSettingsRoutes().then(data => {
      const allStops = new Set<string>();
      Object.values(data.routes).forEach((r: any) => {
        r.stops.forEach((s: string) => allStops.add(s));
      });
      setStops(Array.from(allStops));
      setCurrentStop(current => allStops.has(current) ? current : Array.from(allStops)[0] || "");
    }).catch(console.error);

    // Fetch initial arduino status
    apiFetch("/status").then((res: any) => {
      setArduinoConnected(res.arduino_connected);
    }).catch(console.error);
  }, []);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setStatus("Ready to scan");
    } catch (err: any) {
      if (err.name === 'NotAllowedError') {
        setStatus("Camera permission denied. Allow camera access in your browser.");
      } else if (err.name === 'NotFoundError') {
        setStatus("No camera was found.");
      } else if (err.name === 'NotReadableError') {
        setStatus("Camera is already being used by another application.");
      } else {
        setStatus(`Unable to access webcam: ${err.message || 'Unknown error'}`);
      }
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setStatus("Camera stopped");
  };

  useEffect(() => {
    // Automatically start camera on mount if possible, but allow manual control
    startCamera();
    return () => {
      stopCamera();
    };
  }, []);

  async function captureFrameBlob(): Promise<Blob | null> {
    const video = videoRef.current;
    if (!video || video.readyState < 2) return null;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.8));
  }

  async function sendFrameForMatch() {
    if (isRecognizing) return;
    const video = videoRef.current;
    if (!video || video.readyState < 2) {
      setStatus("Camera is not ready yet.");
      return;
    }
    
    setIsRecognizing(true);
    setStatus("Recognizing...");
    
    const blob = await captureFrameBlob();
    if (!blob) {
      setStatus("Failed to capture frame.");
      setIsRecognizing(false);
      return;
    }

    const fd = new FormData();
    fd.append("frame", blob, "frame.jpg");

    try {
      const data = await apiFetch("/recognize", { method: "POST", body: fd });

      if (!data.recognized) {
        setStatus(data.reason === 'no_face' ? "No face detected" : "Not recognized (unknown)");
        setUser(null);
        setIsRecognizing(false);
        return;
      }

      setStatus(`Recognized: ${data.name} (${data.user_id})`);
      setUser(data.user);
      
      // Process trip
      if (isEntry) {
        await handleTripStart(data.user_id, data.name);
      } else {
        await handleTripEnd(data.user_id, data.name);
      }
    } catch (err) {
      setStatus("Recognition error");
    } finally {
      setIsRecognizing(false);
    }
  }

  async function handleTripStart(userId: string, name: string) {
    try {
      setStatus(`Starting trip for ${name}...`);
      const data = await apiFetch("/trips/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, boarding_stop: currentStop })
      });
      if (data.status === "granted") {
        setStatus(`ACCESS GRANTED. Trip started from ${currentStop}`);
      } else {
        setStatus(`DENIED: ${data.message || data.reason}`);
      }
    } catch (err: unknown) {
      const status = typeof err === "object" && err !== null && "status" in err ? err.status : undefined;
      const message = err instanceof Error ? err.message : "Unknown error";
      setStatus(status === 402 || status === 403 ? `DENIED: ${message}` : `Error starting trip: ${message}`);
    }
  }

  async function handleTripEnd(userId: string, name: string) {
    try {
      setStatus(`Ending trip for ${name}...`);
      const data = await apiFetch("/trips/end", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, exit_stop: currentStop })
      });
      if (data.status === "success") {
        setStatus(`EXIT GRANTED. Fare: ₹${data.fare}. New Balance: ₹${data.balance_after}`);
      } else {
        setStatus(`ERROR: ${data.message || data.reason}`);
      }
    } catch (err: unknown) {
      const status = typeof err === "object" && err !== null && "status" in err ? err.status : undefined;
      const message = err instanceof Error ? err.message : "Unknown error";
      setStatus(status === 402 || status === 403 ? `DENIED: ${message}` : `Error ending trip: ${message}`);
    }
  }

  return (
    <div className="p-4">
      <h2 className="text-2xl font-semibold mb-4">Gate Scanner Interface</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <video ref={videoRef} autoPlay playsInline muted className="w-full max-w-xl border rounded bg-black" />
          <div className="mt-4 flex gap-4">
            <button className="px-4 py-2 bg-green-600 text-white rounded w-full" onClick={startCamera}>
              Start Camera
            </button>
            <button className="px-4 py-2 bg-red-600 text-white rounded w-full" onClick={stopCamera}>
              Stop Camera
            </button>
            <button 
              className={`px-4 py-2 text-white rounded w-full ${isRecognizing ? 'bg-blue-400' : 'bg-blue-600'}`} 
              onClick={sendFrameForMatch}
              disabled={isRecognizing}
            >
              {isRecognizing ? "Recognizing..." : "Recognize Face"}
            </button>
          </div>
        </div>

        <div className="space-y-4">
          <div className="px-4 py-3 border rounded bg-white">
            <p className="text-sm text-gray-600 font-bold">Terminal Status</p>
            <p className="text-lg">{status}</p>
          </div>

          {user && (
            <div className="px-4 py-3 border rounded bg-white">
              <p className="text-sm text-gray-600 font-bold">Matched User</p>
              <p className="text-lg font-medium">{user.name} ({user.id})</p>
              <p className="text-sm">Wallet Balance: ₹{user.wallet}</p>
            </div>
          )}

          <div className="px-4 py-3 border rounded bg-gray-50">
            <p className="text-sm text-gray-600 font-bold mb-2">
              Gate Controls {arduinoConnected ? "(Arduino Connected)" : "(Simulation Mode)"}
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-sm block mb-1">Current Stop location</label>
                <select className="w-full p-2 border rounded" value={currentStop} onChange={e => setCurrentStop(e.target.value)}>
                  {stops.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="flex gap-4">
                <button 
                  className={`px-4 py-2 rounded flex-1 ${isEntry ? 'bg-green-600 text-white' : 'bg-gray-200'}`}
                  onClick={() => setIsEntry(true)}
                >
                  Entry Mode
                </button>
                <button 
                  className={`px-4 py-2 rounded flex-1 ${!isEntry ? 'bg-red-600 text-white' : 'bg-gray-200'}`}
                  onClick={() => setIsEntry(false)}
                >
                  Exit Mode
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
