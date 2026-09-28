import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { VideoDetail } from "@/features/videos";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Video",
  robots: { index: false, follow: false },
};

export default async function VideoDetailPage({
  params,
}: {
  params: Promise<{ videoId: string }>;
}) {
  const { videoId } = await params;
  if (!isUuid(videoId)) notFound();

  return (
    <>
      <AppPageHeader
        title="Video"
        breadcrumb={
          <>
            <Link className="app-row-link" href="/videos">
              Videos
            </Link>
            <span className="breadcrumb-separator" aria-hidden="true">
              /
            </span>
            <span className="breadcrumb-current">Video detail</span>
          </>
        }
      />
      <AppPageBody>
        <VideoDetail videoId={videoId} />
      </AppPageBody>
    </>
  );
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}
