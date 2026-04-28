/**
 * Typed API client for Cupid backend.
 * 
 * Key: `credentials: "include"` tells the browser to send HTTP-only
 * cookies with every request. Without this, cookies are NOT sent on
 * cross-origin requests (localhost:3000 → localhost:8000).
 */

// Why NEXT_PUBLIC_? Next.js only exposes env variables to the browser if they start with NEXT_PUBLIC_. Without this prefix, the variable only works on the server.
// If the env variable is undefined/empty, use "http://localhost:8000" as fallback
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";


//  interface is a blueprint (template), it describes the SHAPE of an object but doesn't create one
// any object claiming to be this type MUST have these fields.
interface ApiResponse<T> {
    success: boolean;
    data: T; // T: placeholder for generic type parameter
    error: string | null;
}

interface UserData {
    id: string;
    full_name: string;
    email: string;
    is_active: boolean;
    created_at: string;
}

// extends means inheritance — ApiError is a special type of JavaScript's built-in Error.
// It inherits all of Error's abilities (like .message, .stack for stack traces) and adds its own field: status.
class ApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
        super(message); // super() calls the parent class's constructor. 
        this.status = status; // `this` refers to the current object instance.
    }
}

// Shared error parser for both request functions
function parseErrorMessage(json: any): string {
    if (typeof json.detail === "string") return json.detail;
    if (Array.isArray(json.detail)) return json.detail.map((e: { msg: string }) => e.msg).join(", ");
    if (json.error) return json.error;
    return "Something went wrong";
}

async function handle401(endpoint: string) {
    if (endpoint !== "/api/v1/auth/login") {
        const { useAuthStore } = await import("@/lib/store");
        useAuthStore.getState().clearUser();
        window.location.href = "/login";
    }
}

// For auth/profile endpoints — backend wraps response in { success, data, error }
async function request<T>(
    endpoint: string,
    options: RequestInit = {}
): Promise<ApiResponse<T>> {
    const url = `${API_BASE}${endpoint}`;
    const res = await fetch(url, {
        headers: { "Content-Type": "application/json", ...options.headers },
        credentials: "include",
        ...options,
    });
    const json = await res.json();
    if (!res.ok) {
        if (res.status === 401) await handle401(endpoint);
        throw new ApiError(parseErrorMessage(json), res.status);
    }
    return json;
}

// For agent endpoints — backend returns the model directly (no wrapper)
async function requestRaw<T>(
    endpoint: string,
    options: RequestInit = {}
): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    const res = await fetch(url, {
        headers: { "Content-Type": "application/json", ...options.headers },
        credentials: "include",
        ...options,
    });
    const json = await res.json();
    if (!res.ok) {
        if (res.status === 401) await handle401(endpoint);
        throw new ApiError(parseErrorMessage(json), res.status);
    }
    return json as T;
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
    name: string;
    nickname: string | null;
    bio: string | null;
    content_niche: string | null;
    content_goal: string | null;
    content_intent: string | null;
    target_age_group: string | null;
    target_country: string | null;
    target_audience: string | null;
    usp: string | null;
}

export const profileApi = {
    get: () =>
        request<ProfileData | null>("/api/v1/profile"),

    update: (body: {
        name?: string;
        nickname?: string;
        bio?: string;
        content_niche?: string;
        content_goal?: string;
        content_intent?: string;
        target_age_group?: string;
        target_country?: string;
        target_audience?: string;
        usp?: string;
    }) =>
        request<ProfileData>("/api/v1/profile", {
            method: "PUT",
            body: JSON.stringify(body),
        }),
};

// ── Agents API ──────────────────────────── ───────────────────

interface GenerateRequest {
    prompt: string;
    content_type?: "Text" | "Image" | "Article" | "Video" | "Ads";
    platform?: "Twitter" | "LinkedIn" | "Instagram" | "Facebook" | "YouTube" | "Web";
    length?: "Short" | "Medium" | "Long" | "Full Article";
    tone?: "Formal" | "Informative" | "Casual" | "GenZ" | "Factual" | "Hook First" | "Data Driven" | "Story Led";
}

interface GenerateResponse {
    run_id: string;
    status: string;
    message: string;
}

interface SearchResult {
    query: string;
    title: string;
    url: string;
    snippet: string;
    domain: string;
    score: number;
}

interface PageContent {
    url: string;
    title: string;
    domain: string;
    text_content: string;
    text_length: number;
    image_url: string | null;
}

interface ResearchData {
    generated_keywords: string[];
    queries_used: string[];
    top_search_results: SearchResult[];
    fetched_pages: PageContent[];
    research_summary: string;
}

interface RunStatusResponse {
    run_id: string;
    status: "pending" | "running" | "completed" | "failed";
    created_at: string;
    current_agent: string | null;
    agents_completed: string[];
    error: string | null;
    personalization_queries: string[];
    research_data: ResearchData | null;
    trend_data: any | null;
    composer_output: any | null;
    composer_evidence: any | null;
    composer_sources: any | null;
}

export const agentsApi = {
    generate: (body: GenerateRequest): Promise<GenerateResponse> =>
        requestRaw<GenerateResponse>("/api/v1/agents/generate", {
            method: "POST",
            body: JSON.stringify(body),
        }),

    getRunStatus: (runId: string): Promise<RunStatusResponse> =>
        requestRaw<RunStatusResponse>(`/api/v1/agents/runs/${runId}`),
};

// ── Trends API ───────────────────────────────────────────────

interface TrendArticle {
    id: string;
    title: string;
    description: string | null;
    url: string;
    image_url: string | null;
    source: string;
    domain: string;
    published_at: string;
    category: string;
    relevance_score: number;
    velocity_score: number;
}

interface TrendsResponse {
    articles: TrendArticle[];
    niche: string;
    total_pool: number;
    cached: boolean;
    generated_at: string;
}

export const trendsApi = {
    getNews: (refresh: boolean = false): Promise<TrendsResponse> =>
        requestRaw<TrendsResponse>(
            `/api/v1/trends/news${refresh ? "?refresh=true" : ""}`
        ),
};

export type { TrendArticle, TrendsResponse };
export type { ProfileData, GenerateRequest, GenerateResponse, RunStatusResponse, ResearchData, SearchResult, PageContent };
export { ApiError };
export type { UserData, ApiResponse };
