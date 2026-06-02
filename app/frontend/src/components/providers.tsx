"use client";

import { ThemeProvider } from "next-themes";
import { SWRConfig } from "swr";

import { AppStateProviders } from "@/lib/app-state";

type ProvidersProps = Readonly<{
  children: React.ReactNode;
}>;

export function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
      <SWRConfig
        value={{
          revalidateOnFocus: false,
          revalidateOnReconnect: true,
          shouldRetryOnError: false,
        }}
      >
        <AppStateProviders>{children}</AppStateProviders>
      </SWRConfig>
    </ThemeProvider>
  );
}
