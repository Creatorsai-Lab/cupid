"use client";

import { useEffect, useState } from "react";
import { Youtube, Plus, Loader2, RefreshCw, Trash2, AlertCircle, CheckCircle2 } from "lucide-react";
import { connectionsApi, type ConnectionResponse } from "@/lib/api";


/**
 * ConnectionsPanel — manages user's connected social media accounts.
 *
 * Currently supports: YouTube only (Phase 1 MVP).
 * Future: LinkedIn, Instagram, etc. (Phase 2).
 *
 * OAuth flow uses a popup window:
 *   1. User clicks "Connect YouTube"
 *   2. Backend returns Google's auth URL
 *   3. Frontend opens it in a popup window
 *   4. User completes consent on Google
 *   5. Google redirects popup to our callback
 *   6. Callback page sends `postMessage` to the parent (this component)
 *   7. We listen for the message, refresh the connections list, close popup
 */
export function ConnectionsPanel() {
    const [connections, setConnections] = useState<ConnectionResponse[] | null>(null);
    const [loading, setLoading] = useState(true);
    const [connecting, setConnecting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Load connections on mount
    useEffect(() => {
        loadConnections();
    }, []);

    // Listen for OAuth completion from popup
    useEffect(() => {
        const handler = (event: MessageEvent) => {
            if (event.data?.type !== "oauth-result") return;
            // Re-fetch list when popup signals completion
            loadConnections();
            setConnecting(false);
        };
        window.addEventListener("message", handler);
        return () => window.removeEventListener("message", handler);
    }, []);

    const loadConnections = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await connectionsApi.list();
            setConnections(data);
        } catch (err: any) {
            setError(err?.message ?? "Failed to load connections");
        } finally {
            setLoading(false);
        }
    };

    const handleConnectYouTube = async () => {
        setConnecting(true);
        setError(null);
        try {
            const res = await connectionsApi.startYouTube();
            // Open Google's consent in a popup (centered)
            const width = 600;
            const height = 720;
            const left = window.screen.width / 2 - width / 2;
            const top = window.screen.height / 2 - height / 2;
            const popup = window.open(
                res.authorization_url,
                "youtube-oauth",
                `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no`
            );

            // If popup blocked, fall back to current tab
            if (!popup) {
                window.location.href = res.authorization_url;
                return;
            }

            // Watch for popup close — covers the case where user closes it
            // without completing OAuth (no postMessage fired)
            const watcher = setInterval(() => {
                if (popup.closed) {
                    clearInterval(watcher);
                    setConnecting(false);
                    loadConnections();
                }
            }, 500);
        } catch (err: any) {
            setError(err?.message ?? "Failed to start connection");
            setConnecting(false);
        }
    };

    const handleDisconnect = async (id: string) => {
        if (!confirm("Disconnect this YouTube account? Your insights will stop updating.")) {
            return;
        }
        try {
            await connectionsApi.disconnect(id);
            await loadConnections();
        } catch (err: any) {
            setError(err?.message ?? "Failed to disconnect");
        }
    };

    const youtubeConnection = connections?.find((c) => c.platform === "youtube");

    return (
        <section className="space-y-4">
            <header className="flex items-center justify-between">
                <div>
                    <h3
                        className="text-base font-medium"
                        style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
                    >
                        Connected accounts
                    </h3>
                    <p
                        className="text-xs mt-0.5"
                        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                    >
                        Connect platforms to unlock analytics and trends
                    </p>
                </div>
                {connections && connections.length > 0 && (
                    <button
                        onClick={loadConnections}
                        className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md hover:bg-[#fff6ed]"
                        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                        title="Refresh"
                    >
                        <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
                    </button>
                )}
            </header>

            {error && (
                <div
                    className="flex items-start gap-2 p-3 rounded-lg text-sm"
                    style={{
                        backgroundColor: "#fef2f2",
                        border: "1px solid #fecaca",
                        color: "#dc2626",
                        fontFamily: "var(--font-body)",
                    }}
                >
                    <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                    <span>{error}</span>
                </div>
            )}

            {/* YouTube connection card */}
            <div
                className="flex items-center gap-4 p-4 rounded-xl border bg-white"
                style={{ borderColor: "var(--color-border)" }}
            >
                <div
                    className="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: "#fff6ed" }}
                >
                    <Youtube size={20} style={{ color: "#FF0000" }} />
                </div>

                <div className="flex-1 min-w-0">
                    <p
                        className="text-sm font-medium"
                        style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
                    >
                        YouTube
                    </p>
                    {loading && !connections && (
                        <p
                            className="text-xs mt-0.5"
                            style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                        >
                            Loading...
                        </p>
                    )}
                    {!loading && youtubeConnection && (
                        <div className="flex items-center gap-2 mt-0.5">
                            <CheckCircle2 size={11} style={{ color: "#10b981" }} />
                            <p
                                className="text-xs"
                                style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                            >
                                Connected as {youtubeConnection.handle ?? youtubeConnection.platform_user_id}
                                {youtubeConnection.sync_status === "syncing" && " · syncing..."}
                                {youtubeConnection.sync_status === "failed" && " · sync failed"}
                            </p>
                        </div>
                    )}
                    {!loading && !youtubeConnection && (
                        <p
                            className="text-xs mt-0.5"
                            style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                        >
                            Not connected
                        </p>
                    )}
                </div>

                {/* Action button */}
                {!loading && !youtubeConnection && (
                    <button
                        onClick={handleConnectYouTube}
                        disabled={connecting}
                        className="flex items-center gap-1.5 px-3.5 py-1.5 text-sm rounded-md text-white disabled:opacity-50"
                        style={{ backgroundColor: "var(--color-primary)", fontFamily: "var(--font-body)" }}
                    >
                        {connecting ? (
                            <>
                                <Loader2 size={12} className="animate-spin" />
                                Connecting
                            </>
                        ) : (
                            <>
                                <Plus size={12} />
                                Connect
                            </>
                        )}
                    </button>
                )}

                {!loading && youtubeConnection && (
                    <button
                        onClick={() => handleDisconnect(youtubeConnection.id)}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md hover:bg-red-50"
                        style={{ color: "#dc2626", fontFamily: "var(--font-body)" }}
                    >
                        <Trash2 size={12} />
                        Disconnect
                    </button>
                )}
            </div>

            {/* Soon-to-come placeholders */}
            <div
                className="flex items-center gap-4 p-4 rounded-xl border bg-white opacity-60"
                style={{ borderColor: "var(--color-border)" }}
            >
                <div
                    className="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: "#f3f4f6" }}
                >
                    <span style={{ color: "var(--color-muted)", fontSize: "10px", fontWeight: 600 }}>
                        in
                    </span>
                </div>
                <div className="flex-1">
                    <p className="text-sm font-medium" style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}>
                        LinkedIn
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>
                        Coming soon
                    </p>
                </div>
            </div>
        </section>
    );
}