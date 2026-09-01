import { create } from "zustand";

export type AuthStatus  = "checking" | "authenticated" | "unauthenticated";

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
}


interface AuthState {
  user: AuthUser | null;
  status: AuthStatus;
  setChecking: () => void;
  setAuthenticated: (user: AuthUser) => void;
  setUnauthenticated: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  status: "checking",
  setChecking: () => set({ status: "checking" }),
  setAuthenticated: (user) => set({ user, status: "authenticated" }),
  setUnauthenticated: () => set({ user: null, status: "unauthenticated" }),
}));
