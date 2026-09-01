import { create } from "zustand";

interface User {
  id: string;
  email: string;
  full_name: string;
}

type AuthStatus  = "checking" | "authenticated" | "unauthenticated";


interface AuthState {
  user: User | null;
  status: AuthStatus;
  setAuthenticated: (user: User) => void;
  setUnauthenticated: () => void;
}

export const useAuthStore = create<AuthState>()(
);
