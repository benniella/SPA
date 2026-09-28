import { Footer } from "@/components/marketing/footer";
import { Navbar } from "@/components/navigation/navbar";
import { MotionScope } from "@/components/motion/primitives";

export default function PublicLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <MotionScope>
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <div className="page-shell">
        <Navbar />
        <main id="main" className="page-main">
          {children}
        </main>
        <Footer />
      </div>
    </MotionScope>
  );
}
