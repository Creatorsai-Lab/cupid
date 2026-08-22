import type { Metadata } from "next";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "Terms & Conditions — Cupid",
  description: "The terms that govern your use of Cupid.",
};

const LAST_UPDATED = "June 6, 2026";

export default function TermsPage() {
  return (
    <div className="flex min-h-[calc(100vh-60px)] flex-col">
      <main className="mx-auto w-full max-w-5xl flex-1 p-3 transition-all duration-500">
        <div className="my-8 flex flex-col gap-1">
          <h1 className="text-[clamp(1.8rem,4vw,2.2rem)] tracking-tight">Terms &amp; Conditions</h1>
          <p className="text-[var(--color-muted)]">Last updated: {LAST_UPDATED}</p>
        </div>

        <div className="space-y-8 text-sm leading-relaxed text-[var(--color-text)]">
          <section className="space-y-2">
            <h2 className="text-lg font-medium">Acceptance</h2>
            <p>
              By creating an account or using Cupid, you agree to these terms. If you don&apos;t
              agree, please don&apos;t use the service.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-medium">Your account</h2>
            <p>
              You&apos;re responsible for keeping your login secure and for activity under your
              account. Provide accurate information and don&apos;t share your credentials.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-medium">Acceptable use</h2>
            <p>
              Don&apos;t use Cupid to create unlawful, harmful, hateful, or deceptive content, to
              infringe others&apos; rights, or to abuse the platform or its providers. We may
              suspend accounts that violate these rules.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-medium">Your content</h2>
            <p>
              You own the content you create with Cupid. You grant us the limited rights needed to
              operate the service — for example, to store, process, and display your content back to
              you.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-medium">AI-generated output</h2>
            <p>
              Cupid uses AI and can make mistakes. Generated content may be inaccurate or incomplete
              — always review it before publishing. You are responsible for what you choose to post.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-medium">Disclaimer &amp; liability</h2>
            <p>
              The service is provided &quot;as is&quot; without warranties. To the extent permitted
              by law, Cupid is not liable for indirect or consequential damages arising from your
              use of the service.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-medium">Changes</h2>
            <p>
              We may update these terms as the product evolves. Continued use after changes means
              you accept the updated terms.
            </p>
          </section>
        </div>
      </main>
      <Footer />
    </div>
  );
}
