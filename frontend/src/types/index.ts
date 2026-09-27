export interface User {
  id: string; // This is the face_card_id (FC-XXXX)
  firstName: string;
  lastName: string;
  name: string;
  route: string;
  pickup: string;
  drop: string;
  wallet: number;
  isActive: boolean;
  registeredAt: string;
}

export interface Journey {
  id: string;
  userId: string;
  entryStop: string;
  exitStop: string | null;
  fare: number;
  timestamp: string;
  status: 'in-progress' | 'completed';
}

export interface Transaction {
  id: string;
  userId: string;
  amount: number;
  type: 'load' | 'deduct';
  timestamp: string;
  description: string;
}

export const ROUTES = ["Route A", "Route B", "Route C", "Route D", "Route E", "Route F", "Route G", "Route H", "Route I", "Route J"];
export const STOPS = ["Stop A", "Stop B", "Stop C", "Stop D", "Stop E", "Stop F", "Stop G", "Stop H", "Stop I", "Stop J"];
export const WALLET_OPTIONS = [100, 200, 500, 1000];