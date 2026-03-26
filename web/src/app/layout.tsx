import type { Metadata } from "next";
import { IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import "./maze.css";

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "600"],
});

export const metadata: Metadata = {
  title: "Deadlight 2003 — Chapter One",
  description:
    "Interactive techno-horror teaser for the AI Labyrinth project. FastAPI delivers the maze, Next.js renders the bleed-through.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${plexMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
