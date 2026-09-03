import type { Metadata } from "next";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: "Arche Paper Studio",
  description: "Create consistently formatted exam papers.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-HK">
      <body className="font-sans">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
