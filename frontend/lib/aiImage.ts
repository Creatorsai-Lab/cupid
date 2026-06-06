/**
 * aiImage — client for AI image generation.
 *
 * This is the FRONTEND client only. It must never hold provider API keys.
 * The real generation (provider SDK, keys, billing) lives in the backend
 * (planned: `backend/app/images/` → POST /api/v1/images/generate). This file
 * only calls that endpoint and returns the resulting image URL.
 *
 * Status: STUB. Not wired to a backend yet. The ImagePickerModal's "AI image"
 * button stays disabled until `generateImage` is backed by a real endpoint.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface GenerateImageOptions {
  /** Aspect ratio hint, e.g. "16:9" | "1:1" | "9:16". */
  aspectRatio?: string;
  /** Platform the image is for (lets the backend pick sensible defaults). */
  platform?: string;
}

export interface GeneratedImage {
  url: string;
  prompt: string;
}

/**
 * Generate an image from a text prompt via the backend.
 *
 * Throws until the backend endpoint exists — callers should keep their entry
 * point (the "AI image" button) disabled until then.
 */
export async function generateImage(
  prompt: string,
  options: GenerateImageOptions = {},
): Promise<GeneratedImage> {
  const res = await fetch(`${API_BASE}/api/v1/images/generate`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, ...options }),
  });

  if (!res.ok) {
    throw new Error(`Image generation failed (${res.status})`);
  }

  return (await res.json()) as GeneratedImage;
}
