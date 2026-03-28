"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const router = useRouter();
  const { isAuthenticated, _hasHydrated } = useAuthStore();

  useEffect(() => {
    if (_hasHydrated && !isAuthenticated) {
      router.replace("/login");
    }
  }, [_hasHydrated, isAuthenticated, router]);

  // Wait for Zustand to rehydrate from localStorage
  if (!_hasHydrated) {
    return null;
  }

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
