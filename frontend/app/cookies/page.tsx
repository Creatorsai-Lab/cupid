import type { Metadata } from "next";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "Cookie Policy — Cupid",
  description: "How and why Cupid uses cookies.",
};

const LAST_UPDATED = "June 6, 2026";

export default function CookiesPage() {
  return (
    <div className="flex min-h-[calc(100vh-60px)] flex-col">
      <main className="mx-auto w-full max-w-5xl flex-1 p-3 transition-all duration-500">
        <div className="my-8 flex flex-col gap-1">
          <h1 className="text-[clamp(1.8rem,4vw,2.2rem)] tracking-tight">Cookie Policy</h1>
          <p className="text-[var(--color-muted)]">Last updated: {LAST_UPDATED}</p>
        </div>

        <div className="space-y-8 text-sm leading-relaxed text-[var(--color-text)]">
          <section className="space-y-2">
            <h2 className="text-lg font-medium">What cookies are</h2>
            <p>
              Cookies are small files stored by your browser. We use them sparingly, mainly to keep
              you signed in and to make the app work.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-medium">Cookies we use</h2>
            <ul className="list-none space-y-3 p-0">
              <li className="rounded-xl border border-[var(--color-border)] p-4">
                <p className="font-medium">Essential — authentication</p>
                <p className="text-[var(--color-muted)]">
                  A secure, HTTP-only session cookie keeps you logged in. Without it the app
                  can&apos;t verify who you are. It can&apos;t be read by JavaScript and isn&apos;t
                  used for advertising.
                </p>
              </li>
              <li className="rounded-xl border border-[var(--color-border)] p-4">
                <p className="font-medium">Preferences</p>
                <p className="text-[var(--color-muted)]">
                  Lightweight local storage remembers things like your session so the interface
                  behaves consistently between visits.
                </p>
              </li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-medium">No third-party ad tracking</h2>
            <p>We do not use advertising or cross-site tracking cookies.</p>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-medium">Managing cookies</h2>
            <p>
              You can clear or block cookies in your browser settings. Note that blocking the
              essential session cookie will sign you out and prevent the app from working.
            </p>
          </section>
        </div>
      </main>
      <Footer />
    </div>
  );
}
