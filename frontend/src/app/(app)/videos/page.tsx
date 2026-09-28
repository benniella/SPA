import type { Metadata } from "next";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { VideoLibrary } from "@/features/videos";

export const metadata: Metadata = {
  title: "Videos",
  description: "The match recordings in your SPA workspace.",
  robots: { index: false, follow: false },
};

export default function VideosPage() {
  return (
    <>
      <AppPageHeader
        title="Videos"
        description="The recordings that analysis runs are queued against."
      />
      <AppPageBody>
        <VideoLibrary />
      </AppPageBody>
    </>
  );
}
