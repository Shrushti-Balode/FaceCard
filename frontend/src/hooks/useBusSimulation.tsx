import { useState, useEffect, useRef } from "react";

const STOPS = ["Stop A", "Stop B", "Stop C", "Stop D", "Stop E", "Stop F", "Stop G", "Stop H", "Stop I", "Stop J"];

export const useBusSimulation = () => {
  const [currentStop, setCurrentStop] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const startSimulation = () => {
    if (intervalRef.current) return;
    
    setIsRunning(true);
    intervalRef.current = setInterval(() => {
      setCurrentStop(prev => (prev + 1) % STOPS.length);
    }, 3000); // Move to next stop every 3 seconds
  };

  const stopSimulation = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsRunning(false);
  };

  const toggleSimulation = () => {
    if (isRunning) {
      stopSimulation();
    } else {
      startSimulation();
    }
  };

  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  return {
    currentStop,
    currentStopName: STOPS[currentStop],
    isRunning,
    toggleSimulation,
    stops: STOPS,
    stopIndex: currentStop
  };
};