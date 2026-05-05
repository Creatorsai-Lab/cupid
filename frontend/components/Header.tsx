"use client";
import React from "react";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import {
  CircleFadingPlus,
  Flame,
  History,
  Settings,
  CircleDollarSign,
  ChartLine,
} from "lucide-react";
import Image from "next/image";

const NAV_ITEMS = [
  { href: "/create",   icon: CircleFadingPlus, label: "Create"   },
  { href: "/trends",   icon: Flame,            label: "Trends"   },
  { href: "/history",  icon: History,          label: "History"  },
  { href: "/insights", icon: ChartLine,        label: "Insights" },
  { href: "/earn",     icon: CircleDollarSign, label: "Earn"     },
  { href: "/settings", icon: Settings,         label: "Settings" },
    // { href: "/automation", icon: Bot, label: "Automation" },
    // { href: "/schedule", icon: Calendar, label: "Schedule" },
    // { href: "/notepad", icon: SquarePen, labe
] as const;

/** Wide flame designed to host a 1–3 digit number in its belly. */
function StreakFlame({ count }: { count: number }) {
  // Auto-shrink for 3-digit numbers so they still fit comfortably.
  const display = count > 999 ? "999+" : String(count);
  
  // Slightly larger, bolder text for improved readability
  const fontSize = display.length >= 3 ? 10 : display.length === 2 ? 12 : 15;

  return (
    <svg
      viewBox="0 0 56 56"
      width="36"
      height="36"
      aria-hidden="true"
      className="overflow-visible"
    >
      <defs>
        <linearGradient id="flameBody" x1="10%" y1="0%" x2="90%" y2="100%">
          <stop offset="0%" stopColor="#fdbd47" />   
          <stop offset="30%" stopColor="#fbbf24" />  
          <stop offset="70%" stopColor="#df7a31" />  
          <stop offset="100%" stopColor="#ea580c" /> 
        </linearGradient>

        <filter id="textShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="1" stdDeviation="1" floodColor="#9a3412" floodOpacity="0.5" />
        </filter>
      </defs>

      {/* Solid outer flame shape extracted from your SVG code */}
      <path
        d="M 8.1836 37.3984 C 8.1836 47.1484 15.6367 53.6406 26.8164 53.6406 C 39.4023 53.6406 47.8164 45.1562 47.8164 32.3828 C 47.8164 11.1718 29.7227 2.3594 17.4180 2.3594 C 14.9570 2.3594 13.3633 3.2266 13.3633 4.9375 C 13.3633 5.5937 13.6445 6.2969 14.1602 6.8828 C 16.9023 10.1875 19.6914 14.0078 19.7617 18.4844 C 19.7617 18.9062 19.7617 19.3047 19.7149 19.7266 C 18.4023 17.2656 16.1992 15.5078 13.9492 15.5078 C 12.8242 15.5078 12.0273 16.3281 12.0273 17.5703 C 12.0273 18.1562 12.2149 19.6094 12.2149 20.6172 C 12.2149 25.5156 8.1836 28.8203 8.1836 37.3984 Z"
        fill="url(#flameBody)"
      />

      {/* Centered text in the new 56x56 coordinate system */}
      <text
        x="28"
        y="37"
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={fontSize}
        fill="#ffffff"
        style={{ fontVariantNumeric: "tabular-nums" }}
        filter="url(#textShadow)"      >
        {display}
      </text>
    </svg>
  );
}

export default function Header() {
  const pathname = usePathname();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const streak = useAuthStore((s) => (s as { streak?: number }).streak ?? 0);

  return (
    <header className="sticky top-0 z-50 bg-(--color-background)">
      <div className="max-w-[1200px] mx-auto px-6 h-[60px] flex items-center gap-3">
        {/* Left cluster: logo + streak */}
        <div className="flex items-center gap-3 shrink-0">
          <Link href="/" className="flex items-center no-underline">
            <Image
              src="/cupid_logo.webp"
              alt="Cupid Logo"
              width={800}
              height={764}
              className="w-10 h-auto"
              priority
            />
          </Link>

          {isAuthenticated && (
            <Link
              href="#"
              aria-label={`${streak}-day streak`}
              title={`${streak}-day streak`}
              className="inline-flex items-center justify-center"
            >
              <StreakFlame count={streak} />
            </Link>
          )}
        </div>

        {/* Right cluster */}
        {isAuthenticated ? (
          <nav className="flex-1 min-w-0 flex justify-end">
            <ul
              className="
                flex flex-row flex-nowrap gap-4 list-none
                px-2 py-1 pb-1
                w-max max-w-full
                bg-(--inline-bg) rounded-lg
                overflow-x-auto overflow-y-hidden
                [scrollbar-width:thin]
                [scrollbar-color:rgba(120,120,120,0.5)_transparent]
                [&::-webkit-scrollbar]:h-[3px]
                [&::-webkit-scrollbar-track]:bg-transparent
                [&::-webkit-scrollbar-thumb]:bg-gray-400/60
                [&::-webkit-scrollbar-thumb]:rounded-full
                md:overflow-visible
                md:[scrollbar-width:none]
                md:[&::-webkit-scrollbar]:hidden
              "
            >
              {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
                const isActive = pathname.startsWith(href);
                return (
                  <li key={href} className="shrink-0">
                    <Link
                      href={href}
                      aria-label={label}
                      title={label}
                      aria-current={isActive ? "page" : undefined}
                      className={`flex items-center justify-center w-10 h-10 nav-item ${isActive ? "active-item" : ""}`}
                    >
                      <Icon size={22} strokeWidth={2} />
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        ) : (
          <div className="flex items-center gap-2 ml-auto">
            <Link href="/login" className="btn-secondary">Login</Link>
            <Link href="/register" className="btn-primary">Get started</Link>
          </div>
        )}
      </div>
    </header>
  );
}