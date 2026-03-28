/**
 * Typed API client for Cupid backend.
 * 
 * Key: `credentials: "include"` tells the browser to send HTTP-only
 * cookies with every request. Without this, cookies are NOT sent on
 * cross-origin requests (localhost:3000 → localhost:8000).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ApiResponse<T> {
    success: boolean;
    data: T;
    error: string | null;
}

interface UserData {
    id: string;
    full_name: string;
    email: string;
    is_active: boolean;
    created_at: string;
}

class ApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
        super(message);
        this.status = status;
    }
}

async function request<T>(
    endpoint: string,
    options: RequestInit = {}
): Promise<ApiResponse<T>> {
    const url = `${API_BASE}${endpoint}`;

    const res = await fetch(url, {
        headers: { "Content-Type": "application/json", ...options.headers },
        credentials: "include",    // ← sends cookies cross-origin
        ...options,
    });

    const json = await res.json();
    if (!res.ok) {
        // FastAPI returns detail as a string (401, 409) or array of objects (422)
        let message = "Something went wrong";
        if (typeof json.detail === "string") {
            message = json.detail;
        } else if (Array.isArray(json.detail)) {
            // 422 validation errors — extract the first human-readable message
            message = json.detail.map((e: { msg: string }) => e.msg).join(", ");
        } else if (json.error) {
            message = json.error;
        }
        throw new ApiError(message, res.status);
    }

    return json;
}


// ── Auth API ─────────────────────────────────────────────────

export const authApi = {
    register: (body: { full_name: string; email: string; password: string }) =>
        request<UserData>("/api/v1/auth/register", {
            method: "POST",
            body: JSON.stringify(body),
        }),

    login: (body: { email: string; password: string }) =>
        request<UserData>("/api/v1/auth/login", {
            method: "POST",
            body: JSON.stringify(body),
        }),

    logout: () =>
        request<null>("/api/v1/auth/logout", { method: "POST" }),

    me: () => request<UserData>("/api/v1/auth/me"),
};

// ── Profile API ──────────────────────────────────────────────

interface ProfileData {
    bio: string | null;
    field: string | null;
    skills: string | null;
    geography: string | null;
    audience: string | null;
}

export const profileApi = {
    get: () =>
        request<ProfileData | null>("/api/v1/profile"),

    update: (body: {
        bio?: string;
        field?: string;
        skills?: string;
        geography?: string;
        audience?: string;
    }) =>
        request<ProfileData>("/api/v1/profile", {
            method: "PUT",
            body: JSON.stringify(body),
        }),
};

export type { ProfileData };
export { ApiError };
export type { UserData, ApiResponse };
