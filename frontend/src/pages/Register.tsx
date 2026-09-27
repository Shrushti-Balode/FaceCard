import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";
import { WALLET_OPTIONS } from "@/types";
import { getSettingsRoutes, apiFetch } from "@/utils/storage";
import { Camera, CreditCard, User, RefreshCw } from "lucide-react";

interface FormData {
  firstName: string;
  lastName: string;
  route: string;
  pickup: string;
  drop: string;
  walletAmount: number;
}

const Register: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const { toast } = useToast();

  const [formData, setFormData] = useState<FormData>({
    firstName: "",
    lastName: "",
    route: "",
    pickup: "",
    drop: "",
    walletAmount: 100,
  });

  const [availableRoutes, setAvailableRoutes] = useState<any>({});
  const [routeOptions, setRouteOptions] = useState<string[]>([]);
  const [stopOptions, setStopOptions] = useState<string[]>([]);

  const [errors, setErrors] = useState<Partial<FormData>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  useEffect(() => {
    // Load dynamic routes from backend
    getSettingsRoutes().then((data) => {
      setAvailableRoutes(data.routes);
      setRouteOptions(Object.keys(data.routes));
    }).catch(err => {
      console.error("Failed to load routes", err);
      toast({ title: "Error loading routes", variant: "destructive" });
    });

    startCamera();
    return () => stopCamera();
  }, []);

  const startCamera = async () => {
    try {
      if (streamRef.current) return;
      const mediaStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        videoRef.current.play();
      }
      streamRef.current = mediaStream;
    } catch (err: any) {
      toast({ title: "Camera Access Denied", variant: "destructive" });
    }
  };

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach(track => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  };

  const capturePhoto = () => {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0) return;

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (blob) {
        setCapturedBlob(blob);
        setPreviewUrl(URL.createObjectURL(blob));
        stopCamera();
        toast({ title: "Face captured!", description: "Ready to submit" });
      }
    }, "image/jpeg", 0.95);
  };

  const retakePhoto = () => {
    setCapturedBlob(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    startCamera();
  };

  const validateForm = () => {
    const newErrors: Partial<FormData> = {};
    if (!formData.firstName.trim()) newErrors.firstName = "Required";
    if (!formData.lastName.trim()) newErrors.lastName = "Required";
    if (!formData.route) newErrors.route = "Required";
    if (!formData.pickup || !formData.drop) newErrors.pickup = "Required";
    if (formData.pickup === formData.drop) newErrors.drop = "Can't be same";

    if (!capturedBlob) {
      toast({ title: "Capture your face first!", variant: "destructive" });
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0 && capturedBlob !== null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;
    setIsSubmitting(true);

    try {
      // 1. Register user
      const userRes = await apiFetch("/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      const fcId = userRes.face_card_id;

      // 2. Upload face
      const fd = new FormData();
      fd.append("user_id", fcId);
      fd.append("image", capturedBlob!, "face.jpg");

      await apiFetch("/register-face", {
        method: "POST",
        body: fd,
      });

      // 3. Login
      login(userRes.user);
      toast({ title: "Registration Successful! 🎉", description: `Your ID: ${fcId}` });
      navigate("/registration-success");

    } catch (err: any) {
      toast({ title: "Registration failed", description: err.message, variant: "destructive" });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRouteSelect = (r: string) => {
    setFormData(prev => ({ ...prev, route: r, pickup: "", drop: "" }));
    setStopOptions(availableRoutes[r]?.stops || []);
  };

  const handleChange = (field: keyof FormData, value: string | number) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors(prev => ({ ...prev, [field]: undefined }));
  };

  return (
    <div className="min-h-screen bg-muted/30 py-12">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
        <Card className="shadow-xl">
          <CardHeader className="text-center">
            <CardTitle className="text-3xl font-bold flex items-center justify-center gap-3">
              <User className="h-9 w-9 text-primary" />
              FaceCard Registration
            </CardTitle>
            <CardDescription>Face Card ID will be generated automatically</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>First Name *</Label>
                  <Input value={formData.firstName} onChange={e => handleChange("firstName", e.target.value)} />
                  {errors.firstName && <p className="text-red-500 text-sm">{errors.firstName}</p>}
                </div>
                <div>
                  <Label>Last Name *</Label>
                  <Input value={formData.lastName} onChange={e => handleChange("lastName", e.target.value)} />
                  {errors.lastName && <p className="text-red-500 text-sm">{errors.lastName}</p>}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label>Route *</Label>
                  <Select onValueChange={handleRouteSelect}>
                    <SelectTrigger><SelectValue placeholder="Select route" /></SelectTrigger>
                    <SelectContent>
                      {routeOptions.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Pickup *</Label>
                  <Select value={formData.pickup} onValueChange={v => handleChange("pickup", v)}>
                    <SelectTrigger><SelectValue placeholder="From" /></SelectTrigger>
                    <SelectContent>
                      {stopOptions.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Drop *</Label>
                  <Select value={formData.drop} onValueChange={v => handleChange("drop", v)}>
                    <SelectTrigger><SelectValue placeholder="To" /></SelectTrigger>
                    <SelectContent>
                      {stopOptions.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-3">
                <Label>Capture Your Face *</Label>
                <div className="grid md:grid-cols-2 gap-6 bg-gray-50 p-4 rounded-lg">
                  <div className="space-y-3">
                    {!previewUrl ? (
                      <video ref={videoRef} className="w-full rounded-lg bg-black" playsInline />
                    ) : (
                      <img src={previewUrl} alt="Captured" className="w-full rounded-lg border-4 border-green-500" />
                    )}
                    <div className="flex gap-2 justify-center">
                      {!previewUrl ? (
                        <Button type="button" onClick={capturePhoto}><Camera className="mr-2" /> Capture</Button>
                      ) : (
                        <Button type="button" variant="secondary" onClick={retakePhoto}><RefreshCw className="mr-2" /> Retake</Button>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <Label>Load Wallet Amount *</Label>
                <Select onValueChange={v => handleChange("walletAmount", parseInt(v))}>
                  <SelectTrigger><SelectValue placeholder="Choose amount" /></SelectTrigger>
                  <SelectContent>
                    {WALLET_OPTIONS.map(amt => <SelectItem key={amt} value={String(amt)}>₹{amt}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>

              <Button type="submit" size="lg" className="w-full text-lg" disabled={isSubmitting || !capturedBlob}>
                {isSubmitting ? "Registering..." : <><CreditCard className="mr-2" /> Complete Registration</>}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Register;