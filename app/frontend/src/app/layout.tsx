import { Suspense } from "react";
import type { Metadata } from "next";

import { Providers } from "@/components/providers";

import "./globals.css";

export const metadata: Metadata = {
  title: "Superconducting Circuits Workbench",
  description: "Rewrite foundation for the superconducting circuits frontend workspace.",
};

type RootLayoutProps = Readonly<{
  children: React.ReactNode;
}>;

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Suspense fallback={<div className="min-h-screen bg-app" />}>
          <Providers>{children}</Providers>
        </Suspense>
      </body>
    </html>
  );
}
