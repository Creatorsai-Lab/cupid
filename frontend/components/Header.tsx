"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    PenLine,
    TrendingUp,
    Layers,
    CalendarDays,
    Settings2,
} from "lucide-react";

const NAV_ITEMS = [
    { href: "/create", icon: PenLine, label: "Create" },
    { href: "/trends", icon: TrendingUp, label: "Trends" },
    { href: "/queue", icon: Layers, label: "Queue" },
    { href: "/schedule", icon: CalendarDays, label: "Schedule" },
    { href: "/settings", icon: Settings2, label: "Settings" },
] as const;

export default function Header() {
    const pathname = usePathname();

    return (
        <header
            style={{
                position: "sticky",
                top: 0,
                zIndex: 50,
                backgroundColor: "var(--color-bg)",
                borderBottom: "1px solid var(--color-border)",
                backdropFilter: "blur(12px)",
                WebkitBackdropFilter: "blur(12px)",
            }}
        >
            <div
                style={{
                    maxWidth: "1200px",
                    margin: "0 auto",
                    padding: "0 1.5rem",
                    height: "60px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                }}
            >
                {/* Logo */}
                <Link
                    href="ublic/cupid_logo.png"
                    style={{
                        fontFamily: "var(--font-display)",
                        fontSize: "1.35rem",
                        color: "var(--color-primary)",
                        letterSpacing: "-0.02em",
                        fontStyle: "italic",
                        userSelect: "none",
                    }}
                >
                    cupid
                </Link>

                {/* Navigation Icons */}
                <nav aria-label="Main navigation">
                    <ul
                        style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "0.25rem",
                            listStyle: "none",
                        }}
                    >
                        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
                            const isActive = pathname === href;
                            return (
                                <li key={href}>
                                    <Link
                                        href={href}
                                        aria-label={label}
                                        title={label}
                                        style={{
                                            display: "flex",
                                            alignItems: "center",
                                            justifyContent: "center",
                                            width: "40px",
                                            height: "40px",
                                            borderRadius: "var(--radius-md)",
                                            color: isActive
                                                ? "var(--color-primary)"
                                                : "var(--color-text-muted)",
                                            backgroundColor: isActive
                                                ? "var(--color-primary-subtle)"
                                                : "transparent",
                                            transition: "color 0.15s ease, background-color 0.15s ease",
                                        }}
                                        onMouseEnter={(e) => {
                                            if (!isActive) {
                                                (e.currentTarget as HTMLElement).style.color =
                                                    "var(--color-text)";
                                                (e.currentTarget as HTMLElement).style.backgroundColor =
                                                    "var(--color-border)";
                                            }
                                        }}
                                        onMouseLeave={(e) => {
                                            if (!isActive) {
                                                (e.currentTarget as HTMLElement).style.color =
                                                    "var(--color-text-muted)";
                                                (e.currentTarget as HTMLElement).style.backgroundColor =
                                                    "transparent";
                                            }
                                        }}
                                    >
                                        <Icon size={18} strokeWidth={1.5} />
                                    </Link>
                                </li>
                            );
                        })}
                    </ul>
                </nav>
            </div>
        </header>
    );
}