"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/lib/store";


import {
    CircleFadingPlus,
    Flame,
    History,
    CalendarCheck,
    Settings,
    CircleDollarSign,
} from "lucide-react";
import Image from "next/image";

const NAV_ITEMS = [
    { href: "/create", icon: CircleFadingPlus, label: "Create" },
    { href: "/trends", icon: Flame, label: "Trends" },
    { href: "/history", icon: History, label: "History" },
    { href: "/schedule", icon: CalendarCheck, label: "Schedule" },
    { href: "/earn", icon: CircleDollarSign, label: "Earn" },
    { href: "/settings", icon: Settings, label: "Settings" },
] as const;

export default function Header() {
    const pathname = usePathname();
    const { isAuthenticated, clearUser } = useAuthStore();
    return (
        <header
            style={{
                position: "sticky",
                top: 0,
                zIndex: 50,
                backgroundColor: "var(--color-background)",
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
                <Link href="/" className="flex items-center gap-2 no-underline"><Image src="/cupid_logo.webp" alt="Cupid Logo" width={800} height={764} className="w-10 h-auto" priority/></Link>

                {/* Right side — conditional on auth */}
                {isAuthenticated ? (
                    /* Authenticated — show icon nav */
                    <>
<svg width="0" height="0" style={{ position: "absolute", visibility: "hidden" }}>
    <defs>
        <linearGradient id="activeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#f6d365" />   /* Replace with your start color */
            <stop offset="100%" stopColor="#fda085" />  /* Replace with your end color */
        </linearGradient>
    </defs>
</svg>

<nav>
    <ul className="flex flex-row gap-4 list-none px-2 bg-(--inline-bg) rounded-lg">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
            const isActive = pathname.startsWith(href);
            return (
                <li key={href}>
                    <Link
                        href={href}
                        aria-label={label}
                        title={label}
                        // 2. Add the dynamic class name here
                        className={`nav-item ${isActive ? "active-item" : ""}`}
                        style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            width: "40px",
                            height: "40px",
                            // transition moved to CSS
                        }}
                    >
                        <Icon size={22} strokeWidth={2} />
                    </Link>
                </li>
            );
        })}
    </ul>
</nav>
                        </>
                ) : (
                    /* Unauthenticated — show login / register */
                    <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                        <Link href="/login" className="btn-secondary">Login</Link>
                        <Link href="/register" className="btn-primary">Get started</Link>
                    </div>
                )}
            </div>
        </header>
    );
}