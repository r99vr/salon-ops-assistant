import type { Metadata, Viewport } from "next";
import "@fontsource/readex-pro/300.css";
import "@fontsource/readex-pro/400.css";
import "@fontsource/readex-pro/500.css";
import "@fontsource/readex-pro/600.css";
import "@fontsource/el-messiri/500.css";
import "@fontsource/el-messiri/700.css";
import "./globals.css";
import Shell from "@/components/Shell";

export const metadata: Metadata = {
  title: "مساعد تشغيل الصالون",
  description: "لوحة تشغيل الصالون: المخزون، النظافة، الطلبيات، والأعطال — والعاملات يرسلن بالواتساب.",
};

export const viewport: Viewport = { themeColor: "#6b2d5c", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
