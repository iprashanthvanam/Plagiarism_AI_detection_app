

import React, { createContext, useContext, useEffect, useState, ReactNode } from "react";
import api from "@/lib/api";

export type Role = "admin" | "student";

export interface AuthUser {
  id: string;
  username: string;
  role: Role;
}

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string, role: Role) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const restoreSession = async () => {
      try {
        const res = await api.get("/auth/validate-token");
        setUser({
          id: res.data.id,
          username: res.data.username,
          role: res.data.role,
        });
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    restoreSession();
  }, []);

  const login = async (username: string, password: string, role: Role) => {
    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);
    form.append("scope", role);

    const res = await api.post("/auth/login", form);

    setUser({
      id: res.data.user_id,
      username: res.data.username,
      role: res.data.role,
    });
  };

  const logout = async () => {
    await api.post("/auth/logout");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
};
