import type { Metadata } from "next";
import {
  ClerkProvider,
  Show,
  UserButton,
} from "@clerk/nextjs";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Centro",
  description: "Centro SaaS dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en" className="h-full antialiased">
        <body className="min-h-full bg-zinc-50 text-zinc-950">
          <header className="flex h-16 items-center justify-between border-b border-zinc-200 bg-white px-6">
            <Link className="text-lg font-semibold" href="/">
              Centro
            </Link>
            <nav className="flex items-center gap-3">
              <Show when="signed-out">
                <Link
                  className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800"
                  href="/sign-in"
                >
                  Continue with Google
                </Link>
              </Show>
              <Show when="signed-in">
                <UserButton />
              </Show>
            </nav>
          </header>
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
