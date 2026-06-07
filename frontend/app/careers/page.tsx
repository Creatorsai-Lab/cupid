import type { Metadata } from "next";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "Careers — Cupid",
  description: "Build the future of creator tooling with us.",
};

export default function CareersPage() {
  return (
    <div className="flex min-h-[calc(100vh-60px)] flex-col">
      <main className="mx-auto w-full max-w-5xl flex-1 p-3 transition-all duration-500">
        <div className="my-8 flex flex-col gap-1">
          <h1 className="text-[clamp(1.8rem,4vw,2.2rem)] tracking-tight">Careers</h1>
          <p className="text-[var(--color-muted)]">
            Help us give every creator a team of AI agents.
          </p>
        </div>

        <div className="space-y-8 text-sm leading-relaxed text-[var(--color-text)]">
          <section className="space-y-2">
            <h2 className="text-lg font-medium">Why Cupid</h2>
            <p>
              We&apos;re a small team building at the intersection of AI agents and the creator
              economy. You&apos;ll ship real features to real creators every week, own problems end
              to end, and see your work in production fast.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-medium">Open roles</h2>
            <div className="rounded-xl border border-[var(--color-border)] p-5 text-[var(--color-muted)]">
              No open positions right now — but we&apos;re always glad to meet sharp builders. If
              you love this space, tell us what you&apos;d want to work on.
            </div>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-medium">Reach out</h2>
            <p>
              Send a note and anything you&apos;re proud of to{" "}
              <a
                href="mailto:careers@cupidagents.com"
                className="text-[var(--color-primary)] underline underline-offset-2"
              >
                careers@cupidagents.com
              </a>
              .
            </p>
          </section>
        </div>
      </main>
      <Footer />
    </div>
  );
}
