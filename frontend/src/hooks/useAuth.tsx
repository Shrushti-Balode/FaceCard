import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { User } from "@/types";
import { getUserSession, saveUserSession, clearUserSession } from "@/utils/storage";

interface AuthContextType {
  user: User | null;
  login: (user: User) => void;
  logout: () => void;
  updateUser: (updates: Partial<User>) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const savedUser = getUserSession();
    if (savedUser) {
      setUser(savedUser);
    }
  }, []);

  const login = (userData: User) => {
    setUser(userData);
    saveUserSession(userData);
  };

  const logout = () => {
    setUser(null);
    clearUserSession();
  };

  const updateUser = (updates: Partial<User>) => {
    if (user) {
      const updatedUser = { ...user, ...updates };
      setUser(updatedUser);
      saveUserSession(updatedUser);
    }
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};