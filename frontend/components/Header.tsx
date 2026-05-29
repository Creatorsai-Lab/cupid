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
  BarChart3,
} from "lucide-react";
import Image from "next/image";

const NAV_ITEMS = [
  { href: "/create",   icon: CircleFadingPlus, label: "Create"   },
  { href: "/trends",   icon: Flame,            label: "Trends"   },
  { href: "/insights", icon: BarChart3,        label: "Insights" },
  { href: "/history",  icon: History,          label: "History"  },
  { href: "/earn",     icon: CircleDollarSign, label: "Earn"     },
  { href: "/settings", icon: Settings,         label: "Settings" },
] as const;

export default function Header() {
  const pathname = usePathname();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const streak = useAuthStore((s) => (s as { streak?: number }).streak ?? 0);

  return (
    <header className="sticky top-0 z-50 bg-(--color-background)">
      <div className="max-w-[1200px] mx-auto py-2 px-3 flex items-center gap-6">
        <div className="flex items-center gap-3 shrink-0">
          {/* Logo */}
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
        </div>
        {/* 59534e */}
        
        {/* Menu Items */}
        {isAuthenticated ? (
          <nav className="flex-1 min-w-0 flex justify-end">
            <ul
              className="
                flex flex-row flex-nowrap gap-3 list-none
                px-1 py-0.5
                w-max max-w-full
                bg-(--color-inline-bg)
                rounded-lg
                overflow-x-auto overflow-y-hidden
                [scrollbar-width:thin]
                [scrollbar-color:#635e58_#bd8f77]
                hover:[scrollbar-color:#57453b_#eae6e1]
                [&::-webkit-scrollbar]:h-[6px]
                [&::-webkit-scrollbar-track]:bg-[#eae6e1] 
                [&::-webkit-scrollbar-track]:rounded-full
                [&::-webkit-scrollbar-thumb]:rounded-full
                [&::-webkit-scrollbar-thumb:hover]:bg-(--color-inline-bg)
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
                      className={`
                        flex items-center justify-center w-11 h-11 rounded-xl transition-all duration-300
                        ${isActive 
                          ? "text-(--color-primary) drop-shadow-[-1px_1px_1px_rgba(158,68,38,0.4)]" 
                          /* FIX: Changed from hover:shadow to hover:drop-shadow and reduced the translate-y slightly for a cleaner icon lift */
                          : "text-(--color-text) hover:-translate-y-[2px] hover:drop-shadow-[-1px_1px_1px_rgba(158,68,38,0.4)]"
                        }
                      `}
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