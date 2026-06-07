import type { Metadata } from "next";
import { Mail, MessageCircle, MapPin } from "lucide-react";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "Contact — Cupid",
  description: "Get in touch with the Cupid team.",
};

export default function ContactPage() {
  return (
    <div className="flex min-h-[calc(100vh-60px)] flex-col">
      <main className="mx-auto w-full max-w-5xl flex-1 p-3 transition-all duration-500">
        <div className="my-8 flex flex-col gap-1">
          <h1 className="text-[clamp(1.8rem,4vw,2.2rem)] tracking-tight">Contact</h1>
          <p className="text-[var(--color-muted)]">
            Questions, feedback, or partnership ideas — we&apos;d love to hear from you.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 text-sm text-[var(--color-text)] sm:grid-cols-2">
          <a
            href="mailto:hello@cupidagents.com"
            className="flex items-start gap-3 rounded-xl border border-[var(--color-border)] p-5 transition-colors hover:border-[var(--color-primary)]"
          >
            <Mail size={18} className="mt-0.5 flex-shrink-0 text-[var(--color-primary)]" />
            <div>
              <p className="font-medium">Email us</p>
              <p className="text-[var(--color-muted)]">hello@cupidagents.com</p>
            </div>
          </a>

          <a
            href="mailto:support@cupidagents.com"
            className="flex items-start gap-3 rounded-xl border border-[var(--color-border)] p-5 transition-colors hover:border-[var(--color-primary)]"
          >
            <MessageCircle size={18} className="mt-0.5 flex-shrink-0 text-[var(--color-primary)]" />
            <div>
              <p className="font-medium">Support</p>
              <p className="text-[var(--color-muted)]">support@cupidagents.com</p>
            </div>
          </a>

          <div className="flex items-start gap-3 rounded-xl border border-[var(--color-border)] p-5 sm:col-span-2">
            <MapPin size={18} className="mt-0.5 flex-shrink-0 text-[var(--color-primary)]" />
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
