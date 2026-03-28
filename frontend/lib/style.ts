import type { CSSProperties } from "react";

/**
 * Shared form styles — single source of truth for all auth forms.
 * Import these in login, register, or any future form page.
 */

export const formLabelStyle: CSSProperties = {
    display: "block",
    fontSize: "0.82rem",
    fontWeight: 500,
    color: "var(--color-text)",
    marginBottom: "0.4rem",
    fontFamily: "var(--font-body)",
    letterSpacing: "0.01em",
};

export const formInputStyle: CSSProperties = {
    display: "block",
    width: "100%",
    height: "42px",
    padding: "0 0.85rem",
    borderRadius: "8px",
    border: "1px solid var(--color-border)",
    backgroundColor: "var(--color-bg)",
    color: "var(--color-text)",
    fontSize: "0.88rem",
    fontFamily: "var(--font-body)",
    outline: "none",
    transition: "border-color 0.15s ease",
};

export const formCardStyle: CSSProperties = {
    backgroundColor: "var(--color-bg-surface)",
    border: "1px solid var(--color-border)",
    borderRadius: "14px",
    padding: "2rem",
};


export const submitBtnStyle: React.CSSProperties = {
    display: "block",
    width: "100%",
    height: "42px",
    borderRadius: "8px",
    backgroundColor: "var(--color-primary)",
    color: "#fff",
    fontSize: "0.88rem",
    fontWeight: 500,
    fontFamily: "var(--font-body)",
    border: "none",
    letterSpacing: "0.01em",
};