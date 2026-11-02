import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/providers/auth-provider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AI Research Agent",
  description: "Advanced RAG-based research assistant",
};

// Runs before paint to set the theme from localStorage / OS preference,
// preventing a flash of the wrong theme on load.
const themeInitScript = `
(function() {
  try {
    var t = localStorage.getItem('theme') || 'light';
    var dark = t === 'dark' || (t === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    var r = document.documentElement;
    r.classList.toggle('dark', dark);
    r.setAttribute('data-theme', dark ? 'dark' : 'light');
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className={inter.className}>
        <AuthProvider>
          {/* Pages own their own <header>/<main>/<footer> landmarks + theme toggle. */}
          <div className="relative z-10 flex min-h-screen flex-col">
            {children}
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
