import type { Metadata } from "next";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "About Us — Cupid",
  description: "What Cupid is and why we build it.",
};

export default function AboutPage() {
  return (
    <div className="flex flex-col min-h-[calc(100vh-60px)]">
    <main className="max-w-5xl w-full mx-auto flex-1 transition-all duration-500 p-3">
      <div className="flex flex-col gap-1 my-8">
        <h1 className="tracking-tight text-[clamp(1.8rem,4vw,2.2rem)]">About Us</h1>
        <p className="text-[var(--color-muted)]">
          The AI agent suite for content creators and influencers.
        </p>
      </div>

      <div className="space-y-8 text-sm leading-relaxed text-[var(--color-text)]">
        <section className="space-y-2">
          <h2 className="text-lg font-medium">Our mission</h2>
          <p>
            Creating consistently is hard. Cupid puts a team of specialised AI
            agents behind every post — researching what matters in your niche,
            matching your voice, and drafting platform-ready content — so you can
            spend less time staring at a blank canvas and more time creating.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-medium">How it works</h2>
          <p>
            Each creation runs through a pipeline of agents: a Personalization
            agent tunes the request to your profile, a Research agent gathers
            current sources, and a Composer agent writes grounded, on-brand
            variants you can edit, score, and publish — alongside trends and
            earnings insights tailored to your channel.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-medium">Who we are</h2>
          <p>
            Cupid is built by a small, independent team obsessed with giving
            creators leverage. We&apos;re shipping fast and listening closely —
            your feedback shapes what we build next.
          </p>
        </section>
      </div>
    </main>
    <Footer />
    </div>
  );
}
