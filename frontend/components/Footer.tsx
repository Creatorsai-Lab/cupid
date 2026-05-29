import Link from "next/link";

export default function Footer() {
  return (
    // Changed to standard semantic footer tag for better SEO structure
    <footer className="bg-[#1a1c38] px-6 md:px-10 py-10">
      
      {/* First Row: Full-width banner section */}
      <div id="banner" className="text-[#50516e] text-[clamp(3.5rem,9vw,7rem)] font-black text-center tracking-tighter leading-none select-none mb-10">CUPID AGENTS</div>
      <div className="max-w-[1200px] mx-auto grid grid-cols-1 sm:grid-cols-3 gap-8 text-sm text-gray-300 border-t border-white/10 pt-8">
        <div>
          <ul className="space-y-2.5 list-none p-0 m-0">
            <li>
              <Link href="/about" className="hover:text-white transition-colors duration-200">About Us</Link>
            </li>
            <li>
              <Link href="/contact" className="hover:text-white transition-colors duration-200">Contact</Link>
            </li> 
            <li>
              <Link href="/careers" className="hover:text-white transition-colors duration-200">Careers</Link>
            </li>                  
          </ul>
        </div>
        <div>
          <ul className="space-y-2.5 list-none p-0 m-0">
            <li>
              <Link href="/privacy" className="hover:text-white transition-colors duration-200">Privacy Policy</Link>
            </li>
            <li>
              <Link href="/terms" className="hover:text-white transition-colors duration-200">T&C</Link>
            </li> 
            <li>
              <Link href="/cookies" className="hover:text-white transition-colors duration-200">Cookies</Link>
            </li>                  
          </ul>
        </div>
        <div className="sm:text-right text-gray-400 flex items-end sm:justify-end">
          <p>&copy; {new Date().getFullYear()} Cupid. All rights reserved.</p>
        </div>

      </div>
    </footer>
  );
}