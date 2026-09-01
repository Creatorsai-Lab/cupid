import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import ProtectedRoute from "@/components/ProtectedRoute";
import { useAuthStore } from "@/lib/store";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

beforeEach(() => {
  replace.mockReset();
  useAuthStore.setState({ user: null, status: "checking" });
});

it("waits while the backend session is being checked", () => {
  render(<ProtectedRoute>private</ProtectedRoute>);
  expect(screen.queryByText("private")).not.toBeInTheDocument();
  expect(replace).not.toHaveBeenCalled();
});

it("redirects an unauthenticated visitor to signin", async () => {
  useAuthStore.setState({ user: null, status: "unauthenticated" });
  render(<ProtectedRoute>private</ProtectedRoute>);
  await waitFor(() => expect(replace).toHaveBeenCalledWith("/signin"));
});

it("renders children only for an authenticated session", () => {
  useAuthStore.setState({ status: "authenticated" });
  render(<ProtectedRoute>private</ProtectedRoute>);
  expect(screen.getByText("private")).toBeInTheDocument();
});
