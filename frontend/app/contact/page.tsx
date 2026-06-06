import type { Metadata } from "next";
import { Mail, MessageCircle, MapPin } from "lucide-react";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "Contact — Cupid",
  description: "Get in touch with the Cupid team.",
};

export default function ContactPage() {
  return (
    <div className="flex flex-col min-h-[calc(100vh-60px)]">
    <main className="max-w-5xl w-full mx-auto flex-1 transition-all duration-500 p-3">
      <div className="flex flex-col gap-1 my-8">
        <h1 className="tracking-tight text-[clamp(1.8rem,4vw,2.2rem)]">Contact</h1>
        <p className="text-[var(--color-muted)]">
          Questions, feedback, or partnership ideas — we&apos;d love to hear from you.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm text-[var(--color-text)]">
        <a
          href="mailto:hello@cupidagents.com"
          className="flex items-start gap-3 p-5 rounded-xl border border-[var(--color-border)] hover:border-[var(--color-primary)] transition-colors"
        >
          <Mail size={18} className="text-[var(--color-primary)] flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium">Email us</p>
            <p className="text-[var(--color-muted)]">hello@cupidagents.com</p>
          </div>
        </a>

        <a
          href="mailto:support@cupidagents.com"
          className="flex items-start gap-3 p-5 rounded-xl border border-[var(--color-border)] hover:border-[var(--color-primary)] transition-colors"
        >
          <MessageCircle size={18} className="text-[var(--color-primary)] flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium">Support</p>
            <p className="text-[var(--color-muted)]">support@cupidagents.com</p>
          </div>
        </a>

        <div className="flex items-start gap-3 p-5 rounded-xl border border-[var(--color-border)] sm:col-span-2">
          <MapPin size={18} className="text-[var(--color-primary)] flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium">Where we are</p>
            <p className="text-[var(--color-muted)]">
              Remote-first. We typically reply within 1–2 business days.
            </p>
          </div>
        </div>
      </div>
    </main>
    <Footer />
    </div>
  );
}
