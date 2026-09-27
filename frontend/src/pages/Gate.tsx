import React, { useEffect, useState } from "react";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import LiveCam from "@/components/LiveCam";
import { apiFetch } from "@/utils/storage";

const Gate: React.FC = () => {
  const [status, setStatus] = useState<any>({});

  useEffect(() => {
    // Poll backend status
    const interval = setInterval(() => {
      apiFetch("/status").then(setStatus).catch(() => setStatus({ status: "disconnected" }));
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-6 space-y-6">
      <Card className="shadow">
        <CardHeader>
          <CardTitle>System Status</CardTitle>
        </CardHeader>
        <CardContent>
          <p><strong>Backend:</strong> {status.status || "Connecting..."}</p>
          <p><strong>Arduino Connected:</strong> {status.arduino_connected ? "Yes" : "No"}</p>
          <p><strong>Gate Mode:</strong> {status.arduino_mode?.toUpperCase() || "Connecting..."}</p>
          <p><strong>Arduino Port:</strong> {status.arduino_port || "N/A"}</p>
          <p><strong>Arduino Baud:</strong> {status.arduino_baud || "N/A"}</p>
          <p><strong>Uptime:</strong> {status.uptime_seconds || 0} seconds</p>
          <p><strong>Registered Faces:</strong> {status.registered_faces || 0}</p>
        </CardContent>
      </Card>

      <LiveCam />
    </div>
  );
};

export default Gate;
