import React, { useEffect, useRef, useState } from "react";

/**
 * FaceScanner - uses opencv.js + Haar cascade to detect faces in-browser.
 * Place opencv.js and haarcascade_frontalface_default.xml in public/ folder.
 *
 * Usage:
 *  <FaceScanner
 *     mode="register" // "register" or "match"
 *     userId={userId} // required for register mode
 *  />
 */

type Props = {
  mode?: "register" | "match";
  userId?: string; // required for register mode
  onMatch?: (result: any) => void; // receives backend response for match
};

export default function FaceScanner({ mode = "match", userId, onMatch }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [ready, setReady] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [status, setStatus] = useState<string>("Loading OpenCV...");
  const classifierRef = useRef<any>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    let mounted = true;

    // load opencv.js from public; assumes <script src="/opencv.js"></script> not used.
    // We'll dynamically load opencv.js if not already present
    async function loadOpenCvAndCascade() {
      // if cv is already available and ready, skip loader
      if ((window as any).cv && (window as any).cv['onRuntimeInitialized']) {
        await initCascade();
        return;
      }

      setStatus("Loading opencv.js...");
      await new Promise<void>((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "/opencv.js"; // file in public/opencv.js or CDN path you chose
        script.async = true;
        script.onload = () => {
          // wait for WASM runtime to initialize
          (window as any).cv['onRuntimeInitialized'] = () => {
            resolve();
          };
        };
        script.onerror = (e) => reject(e);
        document.body.appendChild(script);
      });

      await initCascade();
    }

    async function initCascade() {
      try {
        setStatus("Loading Haar cascade...");
        const cv = (window as any).cv as any;

        // fetch cascade xml from public folder
        const resp = await fetch("/haarcascade_frontalface_default.xml");
        const data = await resp.arrayBuffer();
        const dataView = new Uint8Array(data);

        // create file in Emscripten FS so CascadeClassifier can load it
        cv.FS_createDataFile("/", "haarcascade_frontalface_default.xml", dataView, true, false, false);

        const classifier = new cv.CascadeClassifier();
        classifier.load("haarcascade_frontalface_default.xml");
        classifierRef.current = classifier;

        setReady(true);
        setStatus("OpenCV ready — start camera.");
      } catch (err) {
        console.error("cascade load error", err);
        setStatus("Failed to load cascade.");
      }
    }

    loadOpenCvAndCascade().catch((e) => {
      console.error("opencv load error", e);
      setStatus("Failed to load OpenCV.");
    });

    return () => {
      mounted = false;
    };
  }, []);

  // start camera
  const startCamera = async () => {
    if (streamRef.current) return;
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
      streamRef.current = s;
      if (videoRef.current) {
        videoRef.current.srcObject = s;
        await videoRef.current.play();
      }
      setStatus("Camera started");
      requestAnimationFrame(processFrame);
    } catch (err) {
      console.error("camera error", err);
      setStatus("Camera access denied or not available");
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  // main detection loop
  const processFrame = () => {
    if (!ready || !videoRef.current || !canvasRef.current || !classifierRef.current) {
      requestAnimationFrame(processFrame);
      return;
    }

    try {
      const cv = (window as any).cv as any;
      const video = videoRef.current!;
      const canvas = canvasRef.current!;
      const ctx = canvas.getContext("2d")!;
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      // read canvas to mat
      const src = cv.imread(canvas); // CV_8UC4
      const gray = new cv.Mat();
      cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);

      // equalize histogram for better detection
      cv.equalizeHist(gray, gray);

      const faces = new cv.RectVector();
      const msize = new cv.Size(0, 0);

      classifierRef.current.detectMultiScale(gray, faces, 1.1, 3, 0, msize, msize);

      // draw rectangles
      ctx.lineWidth = 3;
      ctx.strokeStyle = "lime";
      for (let i = 0; i < faces.size(); i++) {
        const r = faces.get(i);
        ctx.strokeRect(r.x, r.y, r.width, r.height);
      }

      // cleanup
      src.delete();
      gray.delete();
      faces.delete();
      msize.delete();

      // continue loop
      requestAnimationFrame(processFrame);
    } catch (err) {
      // sometimes opencv may throw while initializing; ignore and continue
      // console.error('processFrame error', err);
      requestAnimationFrame(processFrame);
    }
  };

  // capture and upload frame
  const captureAndUpload = async () => {
    if (!videoRef.current) {
      setStatus("Camera not ready");
      return;
    }
    setDetecting(true);
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);

    // convert to blob
    const blob: Blob | null = await new Promise((resolve) =>
      canvas.toBlob((b) => resolve(b), "image/jpeg", 0.9)
    );

    if (!blob) {
      setStatus("Capture failed");
      setDetecting(false);
      return;
    }

    // choose endpoint
    const url = mode === "register" ? "http://localhost:5000/save_face" : "http://localhost:5000/match_face";
    const fd = new FormData();
    if (mode === "register") {
      if (!userId) {
        alert("userId is required for register mode");
        setDetecting(false);
        return;
      }
      fd.append("user_id", userId);
    }
    fd.append("frame", blob, "frame.jpg");

    setStatus("Uploading frame...");
    try {
      const res = await fetch(url, { method: "POST", body: fd });
      const data = await res.json();
      setStatus("Server response: " + JSON.stringify(data));
      if (mode === "match" && onMatch) onMatch(data);
    } catch (err) {
      console.error("upload error", err);
      setStatus("Upload failed");
    } finally {
      setDetecting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <button
          className="px-3 py-2 bg-blue-600 text-white rounded"
          onClick={startCamera}
          disabled={!ready}
        >
          Start Camera
        </button>
        <button className="px-3 py-2 bg-red-600 text-white rounded" onClick={stopCamera}>
          Stop Camera
        </button>
        <button className="px-3 py-2 bg-green-600 text-white rounded" onClick={captureAndUpload} disabled={detecting}>
          {mode === "register" ? "Capture & Upload (Register)" : "Capture & Match"}
        </button>
      </div>

      <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="border rounded overflow-hidden">
          <video ref={videoRef} className="w-full" playsInline muted />
        </div>

        <div className="border rounded p-2">
          <canvas ref={canvasRef} className="w-full" />
          <p className="text-sm text-gray-600 mt-2">{status}</p>
        </div>
      </div>
    </div>
  );
}
