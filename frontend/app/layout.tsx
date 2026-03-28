import type { Metadata } from "next";
import { DM_Sans, Instrument_Serif } from "next/font/google";
import Header from "@/components/Header";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
});

const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-instrument-serif",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Cupid — Post like yourself",
  description:
    "Multi-agent social media automation that learns your voice and posts authentically on your behalf.",
  icons: {
    icon: "/favicon/favicon.ico",
    apple: "/favicon/apple-touch-icon.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${dmSans.variable} ${instrumentSerif.variable}`} data-scroll-behavior="smooth">
      <body>
        <Header />
        {children}
      </body>
    </html>
  );
}