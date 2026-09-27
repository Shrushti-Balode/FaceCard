import React, { useEffect, useRef, useState } from "react";
import { apiFetch, getSettingsRoutes } from "@/utils/storage";

export default function LiveCam() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [status, setStatus] = useState<string>("Initializing camera...");
  const [user, setUser] = useState<any>(null);
  
  // Trip management state
  const [currentStop, setCurrentStop] = useState<string>("Stop A");
  const [stops, setStops] = useState<string[]>([]);
  const [isEntry, setIsEntry] = useState(true);

  const lastActionRef = useRef<number>(0);

  useEffect(() => {
    // Load stops for simulation
    getSettingsRoutes().then(data => {
      const allStops = new Set<string>();
      Object.values(data.routes).forEach((r: any) => {
        r.stops.forEach((s: string) => allStops.add(s));
      });
      setStops(Array.from(allStops));
    }).catch(console.error);

    async function startCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
        setStatus("Camera ready");
      } catch (err) {
        setStatus("Camera access denied");
      }
    }
    startCamera();

    return () => {
      if (videoRef.current && videoRef.current.srcObject) {
        const tracks = (videoRef.current.srcObject as MediaStream).getTracks();
        tracks.forEach(t => t.stop());
      }
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
    const now = Date.now();
    if (now - lastActionRef.current < 2000) return;
    
    const blob = await captureFrameBlob();
    if (!blob) return;

    setStatus("Detecting...");
    const fd = new FormData();
    fd.append("frame", blob, "frame.jpg");

    try {
      lastActionRef.current = Date.now();
      const res = await fetch("http://localhost:5001/api/recognize", { method: "POST", body: fd });
      const data = await res.json();

      if (!data.recognized) {
        setStatus(`Not recognized (${data.reason})`);
        setUser(null);
        return;
      }

      setStatus(`Recognized: ${data.name}`);
      setUser(data.user);
      
      // Process trip
      if (isEntry) {
        await handleTripStart(data.user_id, data.name);
      } else {
        await handleTripEnd(data.user_id, data.name);
      }
    } catch (err) {
      setStatus("Error contacting backend");
    }
  }

  async function handleTripStart(userId: string, name: string) {
    try {
      setStatus(`Starting trip for ${name}...`);
      const res = await fetch("http://localhost:5001/api/trips/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, boarding_stop: currentStop })
      });
      const data = await res.json();
      if (data.status === "granted") {
        setStatus(`ACCESS GRANTED. Trip started from ${currentStop}`);
      } else {
        setStatus(`DENIED: ${data.message || data.reason}`);
      }
    } catch (err) {
      setStatus("Error starting trip");
    }
  }

  async function handleTripEnd(userId: string, name: string) {
    try {
      setStatus(`Ending trip for ${name}...`);
      const res = await fetch("http://localhost:5001/api/trips/end", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, exit_stop: currentStop })
      });
      const data = await res.json();
      if (data.status === "success") {
        setStatus(`EXIT GRANTED. Fare: ₹${data.fare}. New Balance: ₹${data.balance_after}`);
      } else {
        setStatus(`ERROR: ${data.message || data.reason}`);
      }
    } catch (err) {
      setStatus("Error ending trip");
    }
  }

  return (
    <div className="p-4">
      <h2 className="text-2xl font-semibold mb-4">Gate Scanner Interface</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <video ref={videoRef} autoPlay playsInline muted className="w-full max-w-xl border rounded bg-black" />
          <div className="mt-4 flex gap-4">
            <button className="px-4 py-2 bg-blue-600 text-white rounded w-full" onClick={sendFrameForMatch}>
              Scan Face Now
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
            <p className="text-sm text-gray-600 font-bold mb-2">Gate Controls (Simulation)</p>
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
