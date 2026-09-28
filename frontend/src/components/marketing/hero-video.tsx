import { HERO_VIDEO } from "@/data/marketing";

export function HeroVideo() {
  return (
    <video
      className="hero-video"
      src={HERO_VIDEO.src}
      poster={HERO_VIDEO.poster}
      width={HERO_VIDEO.width}
      height={HERO_VIDEO.height}
      style={{ objectFit: "contain" }}
      autoPlay
      loop
      muted
      playsInline
      preload="metadata"
      aria-label={HERO_VIDEO.description}
    />
  );
}
