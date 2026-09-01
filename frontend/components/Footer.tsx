import Link from "next/link";

export default function Footer() {
  return (
    // Changed to standard semantic footer tag for better SEO structure
    <footer className="bg-[#1a1c38] px-6 py-10 md:px-10">
      {/* First Row: Full-width banner section */}
      <div
        id="banner"
        className="mb-10 text-center text-[clamp(3.5rem,9vw,7rem)] leading-none font-black tracking-tighter text-[#50516e] select-none"
      >
        CUPID AGENTS
      </div>
      <div className="mx-auto grid max-w-[1200px] grid-cols-1 gap-8 border-t border-white/10 pt-8 text-sm text-gray-300 sm:grid-cols-4">
        <div>
          <ul className="m-0 list-none space-y-2.5 p-0">
            <li>
              <Link href="/about" className="transition-colors duration-200 hover:text-white">
                About Us
              </Link>
            </li>
            <li>
              <Link href="/contact" className="transition-colors duration-200 hover:text-white">
                Contact
              </Link>
            </li>
            <li>
              <Link href="/careers" className="transition-colors duration-200 hover:text-white">
                Careers
              </Link>
            </li>
          </ul>
        </div>
        <div>
          <ul className="m-0 list-none space-y-2.5 p-0">
            <li>
              <Link href="/privacy" className="transition-colors duration-200 hover:text-white">
                Privacy Policy
              </Link>
            </li>
            <li>
              <Link href="/terms" className="transition-colors duration-200 hover:text-white">
                T&C
              </Link>
            </li>
            <li>
              <Link href="/cookies" className="transition-colors duration-200 hover:text-white">
                Cookies
              </Link>
            </li>
          </ul>
          </div>
          <div>
          <ul className="m-0 list-none space-y-2.5 p-0">
            <li>
              <Link href="/docs" className="transition-colors duration-200 hover:text-white">
                Docs
              </Link>
            </li>
          </ul>
        </div>
        <div className="flex items-end text-gray-400 sm:justify-end sm:text-right">
          <p>&copy; {new Date().getFullYear()} Cupid. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}
