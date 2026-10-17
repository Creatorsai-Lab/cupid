import { beforeEach, expect, it, vi } from "vitest";
import { agentsApi, authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

beforeEach(() => {
  useAuthStore.setState({
    user: {
      id: "00000000-0000-0000-0000-000000000001",
      email: "creator@example.com",
      full_name: "Test Creator",
    },
    status: "authenticated",
  });
});

it("clears auth state on 401 without redirecting to a removed route", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not authenticated" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  await expect(authApi.me()).rejects.toMatchObject({ status: 401 });
  expect(useAuthStore.getState().status).toBe("unauthenticated");
  expect(window.location.pathname).not.toBe("/login");
});

it("shows the backend's message for its standard error shape", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "conflict", message: "Only a failed run can be resumed." },
        }),
        { status: 409, headers: { "Content-Type": "application/json" } },
      ),
    ),
  );

  await expect(agentsApi.resume("run-1")).rejects.toMatchObject({
    status: 409,
    message: "Only a failed run can be resumed.",
  });
});
