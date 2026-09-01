import { beforeEach, describe, expect, it } from "vitest";
import { useAuthStore } from "@/lib/store";

const user = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "creator@example.com",
  full_name: "Test Creator",
};

describe("authentication store", () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, status: "checking" });
    localStorage.clear();
  });

  it("starts in checking state without trusting browser storage", () => {
    expect(useAuthStore.getState().status).toBe("checking");
    expect(localStorage.getItem("cupid-auth")).toBeNull();
  });

  it("stores a backend-verified user in memory", () => {
    useAuthStore.getState().setAuthenticated(user);

    expect(useAuthStore.getState()).toMatchObject({
      user,
      status: "authenticated",
    });
    expect(localStorage.getItem("cupid-auth")).toBeNull();
  });

  it("clears the user when the backend rejects the session", () => {
    useAuthStore.getState().setAuthenticated(user);
    useAuthStore.getState().setUnauthenticated();

    expect(useAuthStore.getState()).toMatchObject({
      user: null,
      status: "unauthenticated",
    });
  });
});
