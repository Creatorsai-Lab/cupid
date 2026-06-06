import type { Metadata } from "next";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "Privacy Policy — Cupid",
  description: "How Cupid collects, uses, and protects your data.",
};

const LAST_UPDATED = "June 6, 2026";

export default function PrivacyPage() {
  return (
    <div className="flex flex-col min-h-[calc(100vh-60px)]">
    <main className="max-w-5xl w-full mx-auto flex-1 transition-all duration-500 p-3">
      <div className="flex flex-col gap-1 my-8">
        <h1 className="tracking-tight text-[clamp(1.8rem,4vw,2.2rem)]">Privacy Policy</h1>
        <p className="text-[var(--color-muted)]">Last updated: {LAST_UPDATED}</p>
      </div>

      <div className="space-y-8 text-sm leading-relaxed text-[var(--color-text)]">
        <section className="space-y-2">
          <h2 className="text-lg font-medium">What we collect</h2>
          <p>
            We collect the information you give us to run your account: your name
            and email, the profile and personalization details you enter, the
            prompts and content you generate, and — if you connect a social
            account — the access tokens needed to read your channel&apos;s public
            stats.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-medium">How we use it</h2>
          <p>
            Your data powers the product: personalising content, generating
            posts, surfacing trends, and showing your insights. We do not sell
            your personal data, and we do not use the private contents of your
            account to train third-party models.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-medium">How we protect it</h2>
          <p>
            Authentication uses signed, HTTP-only session cookies. Connected
            social tokens are encrypted at rest, so a database leak alone cannot
            expose them. We restrict access to production data to what&apos;s
            needed to operate the service.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-medium">Third-party services</h2>
          <p>
            We rely on infrastructure and AI providers to deliver features (for
            example, language-model and search providers). They process data only
            to perform the requested task on our behalf.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-medium">Your choices</h2>
          <p>
            You can edit or delete your profile, disconnect a social account at
            any time, and request deletion of your account and associated data by
            emailing us.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-medium">Contact</h2>
          <p>
            Questions about privacy? Reach us at{" "}
            <a
              href="mailto:privacy@cupidagents.com"
              className="text-[var(--color-primary)] underline underline-offset-2"
            >
              privacy@cupidagents.com
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
