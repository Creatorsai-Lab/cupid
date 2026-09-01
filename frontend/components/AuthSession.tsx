"use client";

import { useEffect } from "react";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

export default function AuthSession() {
  const setAuthenticated = useAuthStore((state) => state.setAuthenticated);
  const setUnauthenticated = useAuthStore((state) => state.setUnauthenticated);

  useEffect(() => {
    localStorage.removeItem("cupid-auth");

    authApi
      .me()
      .then((response) =>
        setAuthenticated({
          id: response.data.id,
          email: response.data.email,
          full_name: response.data.full_name,
        }),
      )
      .catch(setUnauthenticated);
  }, [setAuthenticated, setUnauthenticated]);

  return null;
}
