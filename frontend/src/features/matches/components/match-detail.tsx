"use client";

import Link from "next/link";

import { DataCell, DataRow, DataTable } from "@/components/ui/data-table";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PlannedState } from "@/components/ui/states";
import { Tabs } from "@/components/ui/tabs";
import { useOrganizationId } from "@/features/auth/session";
import { useApiQuery } from "@/hooks/use-api-query";
import { formatDate, formatDateTime, formatDuration, formatMatch, formatBytes } from "@/lib/format";
import { getMatch } from "@/services/matches";
import { listVideos } from "@/services/videos";
import { videoStatusLabels } from "@/types/domain";
import type { Match } from "@/types/api";

const MAX_PAGE = 200;

export function MatchDetail({ matchId }: { matchId: string }) {
  const organizationId = useOrganizationId();

  const match = useApiQuery(
    (options) => getMatch(matchId, organizationId ?? "", options),
    `match:${organizationId}:${matchId}`,
    organizationId !== null,
  );

  if (organizationId === null) {
    return (
      <PlannedState
        title="No workspace selected"
        description="A match belongs to an organization. Choose a workspace to open this fixture."
      />
    );
  }

  if (match.state.status === "loading") return <LoadingState label="Loading match" rows={4} />;
  if (match.state.status === "error") {
    return <ErrorState error={match.state.error} onRetry={match.reload} />;
  }

  const record = match.state.data;

  return (
    <div className="stack stack-7">
      <div className="detail-grid">
        <div className="stack stack-5">
          <h2 className="heading-subsection">Fixture</h2>
          <dl className="fact-list">
            <Fact label="Home" value={record.home_team_name ?? "—"} />
            <Fact label="Away" value={record.away_team_name ?? "—"} />
            <Fact label="Date played" value={formatDate(record.played_on)} />
            <Fact label="Competition" value={record.competition ?? "Not set"} />
            <Fact label="Venue" value={record.venue_name ?? "Not set"} />
            <Fact label="Our side" value={record.is_home ? "Home" : "Away"} />
            <Fact label="Created" value={formatDateTime(record.created_at)} />
          </dl>
        </div>

        <div className="stack stack-4">
          <PlannedState
            title="No result recorded"
            description="SPA does not model a scoreline, so none is shown. Performance analysis is about what happened physically and positionally, not about the goals — and a score the backend cannot store would be a fabricated field."
          />
        </div>
      </div>

      <Tabs
        label={`${formatMatch(record)} sections`}
        items={[
          {
            id: "videos",
            label: "Videos",
            content: <MatchVideos match={record} organizationId={organizationId} />,
          },
          {
            id: "analysis",
            label: "Analysis",
            content: (
              <PlannedState
                title="No analysis for this match"
                description="Analysis runs are created against a video, and the pipeline that would produce tracking and metrics is not implemented. Once a recording exists for this fixture, its runs will be listed here."
                note="Not available yet. This needs the analysis pipeline."
              />
            ),
          },
          {
            id: "players",
            label: "Players",
            content: (
              <PlannedState
                title="Squad is not linked to the match"
                description="The backend has no match-squad model, so there is no per-match line-up to show. Squad membership is dated against the organization, not against a fixture."
                note="Not available yet. This needs tracking to identify players in a recording."
              />
            ),
          },
          {
            id: "reports",
            label: "Reports",
            content: (
              <PlannedState
                title="No reports for this match"
                description="Reports are generated asynchronously from an analysis run. With no run, there is nothing to render."
                note="Not available yet. This needs reporting."
              />
            ),
          },
        ]}
      />
    </div>
  );
}

function MatchVideos({ match, organizationId }: { match: Match; organizationId: string }) {
  const videos = useApiQuery(
    (options) => listVideos(organizationId, { limit: MAX_PAGE }, options),
    `match-videos:${organizationId}`,
  );

  if (videos.state.status === "loading") return <LoadingState label="Loading videos" rows={3} />;
  if (videos.state.status === "error") {
    return <ErrorState error={videos.state.error} onRetry={videos.reload} />;
  }

  const page = videos.state.data;
  const attached = page.items.filter((video) => video.match_id === match.id);

  if (attached.length === 0) {
    return (
      <PlannedState
        title="No video attached to this match"
        description="Attaching a recording to a fixture needs video processing. The library, the metadata model and the storage contract all exist; the upload flow does not."
        note="Not available yet. This needs video processing."
      />
    );
  }

  return (
    <div className="stack stack-4">
      <DataTable
        caption={`Videos attached to ${formatMatch(match)}`}
        columns={[
          { id: "file", header: "File" },
          { id: "status", header: "Status" },
          { id: "duration", header: "Duration", numeric: true, secondary: true },
          { id: "size", header: "Size", numeric: true, secondary: true },
        ]}
      >
        {attached.map((video) => (
          <DataRow key={video.id}>
            <DataCell primary>
              <Link className="app-row-link" href={`/videos/${encodeURIComponent(video.id)}`}>
                {video.original_filename}
              </Link>
            </DataCell>
            <DataCell>{videoStatusLabels[video.status]}</DataCell>
            <DataCell numeric secondary>
              {formatDuration(video.duration_seconds)}
            </DataCell>
            <DataCell numeric secondary>
              {formatBytes(video.size_bytes)}
            </DataCell>
          </DataRow>
        ))}
      </DataTable>

      {page.meta.count >= MAX_PAGE ? (
        <p className="text-caption">
          Showing the first {MAX_PAGE} videos in the workspace. This list is filtered in the browser
          because the videos endpoint has no match filter yet.
        </p>
      ) : null}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="fact">
      <dt className="fact-label">{label}</dt>
      <dd className="fact-value">{value}</dd>
    </div>
  );
}
