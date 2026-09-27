import { User, Journey, Transaction } from "@/types";

const API_BASE = "http://localhost:5001/api";

export const apiFetch = async (endpoint: string, options?: RequestInit) => {
  const res = await fetch(`${API_BASE}${endpoint}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || `API Error: ${res.status}`);
  }
  return res.json();
};

export const getUsers = async (): Promise<User[]> => {
  return apiFetch("/users");
};

export const getUserById = async (id: string): Promise<User> => {
  return apiFetch(`/users/${id}`);
};

export const getJourneys = async (userId?: string): Promise<Journey[]> => {
  if (userId) {
    return apiFetch(`/users/${userId}/journeys`);
  }
  return apiFetch("/journeys");
};

export const getTransactions = async (userId?: string): Promise<Transaction[]> => {
  if (userId) {
    return apiFetch(`/users/${userId}/transactions`);
  }
  return apiFetch("/transactions");
};

export const getSettingsRoutes = async () => {
  return apiFetch("/settings/routes");
};

// Local storage for current user session
export const StorageKeys = {
  CURRENT_USER: "facecard_user_session",
} as const;

export const saveUserSession = (user: User) => {
  localStorage.setItem(StorageKeys.CURRENT_USER, JSON.stringify(user));
};

export const getUserSession = (): User | null => {
  const data = localStorage.getItem(StorageKeys.CURRENT_USER);
  return data ? JSON.parse(data) : null;
};

export const clearUserSession = () => {
  localStorage.removeItem(StorageKeys.CURRENT_USER);
};