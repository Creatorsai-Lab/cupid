import { create } from "zustand";
import { persist } from "zustand/middleware";

interface User {
    id: string;
    email: string;
    full_name: string;
}

interface AuthState {
    user: User | null;
    isAuthenticated: boolean;
    _hasHydrated: boolean;
    setUser: (user: User) => void;
    clearUser: () => void;
    setHasHydrated: (state: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set) => ({
            user: null,
            isAuthenticated: false,
            _hasHydrated: false, // both server and client start with the same state

            setUser: (user) => set({ user, isAuthenticated: true }),

            clearUser: () => set({ user: null, isAuthenticated: false }),

            setHasHydrated: (state) => set({ _hasHydrated: state }),
        }),
        {
            name: "cupid-auth",
            partialize: (state) => ({
                user: state.user,
                isAuthenticated: state.isAuthenticated,
            }),
            onRehydrateStorage: () => (state) => {
                state?.setHasHydrated(true);
            },
        }
    )
);
