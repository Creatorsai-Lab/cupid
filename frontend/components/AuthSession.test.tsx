import { render, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import AuthSession from "@/components/AuthSession";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

vi.mock("@/lib/api", () => ({
  authApi: { me: vi.fn() },
}));

beforeEach(() => {
  useAuthStore.setState({ user: null, status: "checking" });
});

it("hydrates a valid backend session", async () => {
  vi.mocked(authApi.me).mockResolvedValue({
    success: true,
    data: {
      id: "00000000-0000-0000-0000-000000000001",
      email: "creator@example.com",
      full_name: "Test Creator",
      is_active: true,
      created_at: "2026-09-01T00:00:00Z",
    },
    error: null,
  });

  render(<AuthSession />);

  await waitFor(() =>
    expect(useAuthStore.getState().status).toBe("authenticated"),
  );
});

it("marks a missing or expired session unauthenticated", async () => {
  vi.mocked(authApi.me).mockRejectedValue(new Error("401"));

  render(<AuthSession />);

  await waitFor(() =>
    expect(useAuthStore.getState().status).toBe("unauthenticated"),
  );
});
