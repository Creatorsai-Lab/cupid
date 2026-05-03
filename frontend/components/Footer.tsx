import Link from "next/link";

export default function Footer() {
    return (
        <div className="bg-black p-10">
            <div id="banner" className="text-white">CUPID GANG!</div>
            <div className="block">
            <div className="grid grid-cols-3 gap-4">
                <div>Column 1</div>
                <div>Column 2</div>
                <div className="text-white">&copy; {new Date().getFullYear()} Cupid. All rights reserved.</div>
            </div>
            </div>
        </div>
    )
}