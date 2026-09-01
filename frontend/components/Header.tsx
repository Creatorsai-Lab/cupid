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
  { href: "/create", icon: CircleFadingPlus, label: "Create" },
  { href: "/trends", icon: Flame, label: "Trends" },
  { href: "/insights", icon: BarChart3, label: "Insights" },
  { href: "/history", icon: History, label: "History" },
  { href: "/earn", icon: CircleDollarSign, label: "Earn" },
  { href: "/settings", icon: Settings, label: "Settings" },
] as const;

export default function Header() {
  const pathname = usePathname();
  const status = useAuthStore((state) => state.status);
  const isAuthenticated = status === "authenticated";
  const streak = useAuthStore((s) => (s as { streak?: number }).streak ?? 0);

  return (
    <header className="sticky top-0 z-50 bg-(--color-background)">
      <div className="mx-auto flex max-w-5xl items-center gap-6 px-3 py-2">
        <div className="flex shrink-0 items-center gap-3">
          {/* Logo */}
          <Link href="/" className="flex items-center no-underline">
            <Image
              src="/cupid_logo.webp"
              alt="Cupid Logo"
              width={870}
              height={833}
              className="h-auto w-10"
              priority
            />
          </Link>
        </div>
        {/* 59534e */}

        {/* Menu Items */}
        {isAuthenticated ? (
          <nav className="flex min-w-0 flex-1 justify-end">
            <ul className="flex w-max max-w-full list-none flex-row flex-nowrap gap-3 overflow-x-auto overflow-y-hidden rounded-lg bg-(--color-inline-bg) px-1 py-0.5 [scrollbar-color:#635e58_#bd8f77] [scrollbar-width:thin] hover:[scrollbar-color:#57453b_#eae6e1] md:overflow-visible md:[scrollbar-width:none] [&::-webkit-scrollbar]:h-[6px] md:[&::-webkit-scrollbar]:hidden [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb:hover]:bg-(--color-inline-bg) [&::-webkit-scrollbar-track]:rounded-full [&::-webkit-scrollbar-track]:bg-[#eae6e1]">
              {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
                const isActive = pathname.startsWith(href);
                return (
                  <li key={href} className="shrink-0">
                    <Link
                      href={href}
                      aria-label={label}
                      title={label}
                      aria-current={isActive ? "page" : undefined}
                      className={`flex h-11 w-11 items-center justify-center rounded-4xl transition-all duration-300 ${
                        isActive
                          ? "text-(--color-primary) drop-shadow-[-1px_1px_1px_rgba(158,68,38,0.4)]"
                          : "text-(--color-text) hover:-translate-y-[2px] hover:drop-shadow-[-1px_1px_1px_rgba(158,68,38,0.4)]"
                      } `}
                    >
                      <Icon size={26} strokeWidth={2} />
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        ) : (
          <div className="ml-auto flex items-center gap-2">
            <Link href="/signin" className="btn-primary">
              Get started
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
