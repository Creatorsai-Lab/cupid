import Link from "next/link";

export default function Footer() {
    return (
        <div className="bg-[#1a1c38] px-10 py-3">
            <div id="banner" className="text-[#50516e] text-[8rem] font-black text-center">CUPID GANG!</div>
            <div className="block">
            <div className="grid grid-cols-3 gap-4 text-white">
                <div><ul>
                    <li>About Us</li>
                    <li>Contact</li> 
                    <li>Career</li>                   
                    </ul></div>
                <div><ul>
                    <li>Privacy Policy</li>
                    <li>T&C</li> 
                    <li>Cookies</li>                   
                    </ul></div>
                <div className="text-white">&copy; {new Date().getFullYear()} Cupid. All rights reserved.</div>
            </div>
            </div>
        </div>
    )
}