export type IconName =
  | "vision"
  | "ai"
  | "analytics"
  | "sport"
  | "video"
  | "motion"
  | "upload"
  | "detect"
  | "track"
  | "analyse"
  | "understand"
  | "arrow-right"
  | "arrow-down"
  | "chevron-up"
  | "chevron-down"
  | "user"
  | "menu"
  | "close"
  | "eye"
  | "eye-off"
  | "play"
  | "check";

/* Navigation */

export interface NavItem {
  readonly id: string;
  readonly label: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { id: "platform", label: "Platform" },
  { id: "ai-engine", label: "How it Works" },
  { id: "sports", label: "Sports" },
  { id: "insights", label: "Insights" },
] as const;

export const NAV_ACTIONS = {
  signIn: { label: "Sign In", href: "/sign-in" },
  primary: { label: "Get Started", href: "/sign-up" },
} as const;

export const PUBLIC_ROUTE_FOR: Record<string, string> = {
  platform: "about",
  "ai-engine": "about",
  sports: "about",
  insights: "compliance",
} as const;

export const BRAND = {
  name: "SPA",
  expansion: "Sport Performance Analysis",
  proposition: "Turn sports video into performance data",
} as const;

/* Hero */

export const HERO = {
  /** Split into two lines so the break is a design decision, not a viewport
   * accident: the second line carries the payoff and must not wrap. */
  headlineLines: ["Turn sports video", "into performance data"] as const,
  supporting: "AI-powered performance analysis for athletes, coaches, teams and analysts.",
  explanation: {
    lineOne: "Upload your sports footage.",
    lineTwo: "SPA detects, tracks and analyses performance.",
  },
  primaryCta: { label: "Start Analysing" },
  secondaryCta: { label: "See How It Works", href: "#ai-engine" },
} as const;

export const HERO_VIDEO = {
  src: "/assets/videos/video.mp4",
  poster: "/assets/videos/video-poster.jpg",
  width: 864,
  height: 496,
  description: "Sports footage awaiting analysis in SPA.",
} as const;

/* Capabilities (#22) */

export interface Capability {
  readonly id: string;
  readonly label: string;
  readonly icon: IconName;
}

/** No superlatives: SPA has no measurement that would justify "most accurate" or
 * "proven to improve performance". */
export const CAPABILITIES: readonly Capability[] = [
  { id: "computer-vision", label: "Computer Vision", icon: "vision" },
  { id: "ai", label: "AI", icon: "ai" },
  { id: "performance-analytics", label: "Performance Analytics", icon: "analytics" },
  { id: "multi-sport", label: "Multi-Sport", icon: "sport" },
  { id: "video-analysis", label: "Video Analysis", icon: "video" },
  { id: "motion-intelligence", label: "Motion Intelligence", icon: "motion" },
] as const;

/* The problem (#23) */

export interface ProblemStage {
  readonly id: string;
  readonly label: string;
  readonly detail: string;
}

export const PROBLEM = {
  headline: "Your video contains more information than the human eye can capture.",
  body: "A single passage of play is hundreds of simultaneous movements across a frame. Watching it back tells you what happened. It does not tell you how far, how fast, how often or how it compares — not consistently, and not for twenty-two players at once.",
  stages: [
    {
      id: "video",
      label: "Video",
      detail: "Footage as recorded, one continuous frame sequence.",
    },
    {
      id: "movements",
      label: "Millions of movements",
      detail: "Player and ball positions across every frame of the recording.",
    },
    {
      id: "insights",
      label: "Performance insights",
      detail: "Distances, speeds, positions, workload and shape over time.",
    },
  ] as const satisfies readonly ProblemStage[],
} as const;

/* How it works (#24) */

export interface ProcessStep {
  readonly id: string;
  readonly label: string;
  readonly title: string;
  readonly description: string;
  readonly icon: IconName;
}

export const PROCESS_STEPS: readonly ProcessStep[] = [
  {
    id: "upload",
    label: "Upload",
    title: "Upload",
    description: "Footage is ingested and probed for resolution, frame rate and duration.",
    icon: "upload",
  },
  {
    id: "detect",
    label: "Detect",
    title: "Detect",
    description: "Players and the ball are located in each analysed frame.",
    icon: "detect",
  },
  {
    id: "track",
    label: "Track",
    title: "Track",
    description: "Detections are associated across frames into stable identities.",
    icon: "track",
  },
  {
    id: "analyse",
    label: "Analyse",
    title: "Analyse",
    description: "Trajectories become distance, speed, position and workload metrics.",
    icon: "analyse",
  },
  {
    id: "understand",
    label: "Understand",
    title: "Understand",
    description: "Metrics are organised into reports and views you can act on.",
    icon: "analytics",
  },
] as const satisfies readonly ProcessStep[];

/* AI engine (#25) */

export interface EngineStage {
  readonly id: string;
  readonly label: string;
  readonly output: string;
  readonly icon: IconName;
  /** 'analysis' stages are computation over tracking data; 'vision' stages need a
   * model. */
  readonly kind: "vision" | "analysis";
}

/** The design, not shipped capability: no model has been selected
 * ('ml/models/README.md'). */
export const ENGINE_STAGES: readonly EngineStage[] = [
  {
    id: "detection",
    label: "Detection",
    output: "Per-frame objects",
    icon: "detect",
    kind: "vision",
  },
  { id: "tracking", label: "Tracking", output: "Stable track ids", icon: "track", kind: "vision" },
  { id: "pose", label: "Pose", output: "Body keypoints", icon: "motion", kind: "vision" },
  { id: "events", label: "Events", output: "Timed incidents", icon: "analytics", kind: "analysis" },
  {
    id: "movement",
    label: "Movement",
    output: "Distance and speed",
    icon: "motion",
    kind: "analysis",
  },
  {
    id: "performance",
    label: "Performance",
    output: "Named metrics",
    icon: "analytics",
    kind: "analysis",
  },
  {
    id: "tactical",
    label: "Tactical",
    output: "Shape and spacing",
    icon: "sport",
    kind: "analysis",
  },
  {
    id: "intelligence",
    label: "Intelligence",
    output: "Reports and views",
    icon: "ai",
    kind: "analysis",
  },
] as const satisfies readonly EngineStage[];

/* Performance metrics (#26) */

export interface PerformanceMetric {
  readonly id: string;
  readonly label: string;
  readonly unit: string;
  /** A short definition, so the metric means something to a reader. */
  readonly definition: string;
}

/** Names mirror the backend's 'MetricCategory' values
 * ('backend/app/domain/analysis/metrics.py'). */
export const PERFORMANCE_METRICS: readonly PerformanceMetric[] = [
  {
    id: "speed",
    label: "Speed",
    unit: "km/h",
    definition: "Velocity between consecutive positions, with sprint thresholds.",
  },
  {
    id: "distance",
    label: "Distance",
    unit: "m",
    definition: "Ground covered, split by period, player and movement band.",
  },
  {
    id: "acceleration",
    label: "Acceleration",
    unit: "m/s²",
    definition: "Rate of change in velocity, including high-intensity efforts.",
  },
  {
    id: "position",
    label: "Position",
    unit: "m",
    definition: "Location on the pitch, normalised to a canonical field.",
  },
  {
    id: "workload",
    label: "Workload",
    unit: "%",
    definition: "Accumulated effort and intensity share across a session.",
  },
  {
    id: "movement",
    label: "Movement",
    unit: "",
    definition: "Distribution of activity across walking, running and sprinting bands.",
  },
] as const satisfies readonly PerformanceMetric[];

/** The metric whose illustrative value is emphasised in the athlete panel. */
export const HIGHLIGHT_METRIC_ID = "speed" as const;

/* Multi-sport (#27) */

export interface Sport {
  readonly id: string;
  readonly label: string;
  /** Whether the sport is modelled in the domain at all today. */
  readonly status: "modelled" | "planned";
}

/** Statuses are honest: football is the only one with a domain entry today
 * ('types/domain.ts', 'ml/README.md'). */
export const SPORTS: readonly Sport[] = [
  { id: "football", label: "Football", status: "modelled" },
  { id: "basketball", label: "Basketball", status: "planned" },
  { id: "rugby", label: "Rugby", status: "planned" },
  { id: "tennis", label: "Tennis", status: "planned" },
  { id: "athletics", label: "Athletics", status: "planned" },
  { id: "volleyball", label: "Volleyball", status: "planned" },
  { id: "hockey", label: "Hockey", status: "planned" },
] as const satisfies readonly Sport[];

export const SPORTS_STATEMENT = {
  headline: "Built for sport",
  supporting: "One platform. Multiple sports.",
} as const;

/* Visual analysis (#28) */

export interface AnalysisView {
  readonly id: string;
  readonly label: string;
  readonly description: string;
}

/** Four views over one pitch coordinate space. */
export const ANALYSIS_VIEWS: readonly AnalysisView[] = [
  {
    id: "trajectory",
    label: "Movement",
    description: "Tracked positions joined into paths across a period of play.",
  },
  {
    id: "heatmap",
    label: "Heatmap",
    description: "Spatial density — where time was spent on the pitch.",
  },
  {
    id: "shape",
    label: "Team shape",
    description: "Formation, width, depth and compactness at an instant.",
  },
  {
    id: "events",
    label: "Events",
    description: "Timed incidents placed at the position they occurred.",
  },
] as const satisfies readonly AnalysisView[];

/* Audience (#29) */

export interface Audience {
  readonly id: string;
  readonly label: string;
  readonly need: string;
}

/** Derived from 'docs/product/README.md'. */
export const AUDIENCES: readonly Audience[] = [
  {
    id: "athletes",
    label: "Athletes",
    need: "Their own numbers, match to match.",
  },
  {
    id: "coaches",
    label: "Coaches",
    need: "How far we ran, where we lost shape, who faded.",
  },
  {
    id: "analysts",
    label: "Analysts",
    need: "The underlying data, queryable and exportable.",
  },
  {
    id: "teams",
    label: "Teams",
    need: "One workspace across matches, squads and seasons.",
  },
  {
    id: "academies",
    label: "Academies",
    need: "Development tracking across age groups and years.",
  },
  {
    id: "performance-departments",
    label: "Performance Departments",
    need: "Consistent measurement across an entire programme.",
  },
] as const satisfies readonly Audience[];

/* Insights (#30) */

export interface InsightStage {
  readonly id: string;
  readonly label: string;
  readonly description: string;
}

export const INSIGHTS = {
  headline: "Data that helps you act",
  body: "A number on its own changes nothing. SPA is built to carry a measurement through to the decision it informs — for a player, a unit or a squad.",
  chain: [
    {
      id: "performance",
      label: "Performance",
      description: "What happened on the pitch, measured.",
    },
    {
      id: "analysis",
      label: "Analysis",
      description: "Compared against the player, the unit and the season.",
    },
    {
      id: "insight",
      label: "Insight",
      description: "A statement a coach can act on this week.",
    },
  ] as const satisfies readonly InsightStage[],
} as const;

/* Disclosure */

/** The single disclosure every illustrative visualization must render, so the
 * wording cannot drift between sections. */
export const ILLUSTRATIVE_NOTE = "Illustrative visualization. Not a measured result." as const;

export const ILLUSTRATIVE_NOTE_SHORT = "Illustrative" as const;

/* Final CTA and footer (#31, #32) */

export const FINAL_CTA = {
  headlineLines: ["Your next performance", "starts with better data."] as const,
  body: "Upload footage, run the analysis and read the numbers behind the performance.",
  cta: { label: "Start Analysing" },
} as const;

export interface FooterColumn {
  readonly id: string;
  readonly heading: string;
  readonly links: readonly { readonly label: string; readonly href: string }[];
}

/** Only routes and documents that exist; no '#' placeholders. */
export const FOOTER_COLUMNS: readonly FooterColumn[] = [
  {
    id: "platform",
    heading: "Platform",
    links: [
      { label: "Overview", href: "#platform" },
      { label: "How it Works", href: "#ai-engine" },
      { label: "Sports", href: "#sports" },
      { label: "Insights", href: "#insights" },
    ],
  },
  {
    id: "capabilities",
    heading: "Capabilities",
    links: [
      { label: "Computer Vision", href: "#platform" },
      { label: "Performance Analytics", href: "#performance" },
      { label: "Visual Analysis", href: "#visual-analysis" },
      { label: "AI Engine", href: "#ai-engine" },
    ],
  },
  {
    id: "company",
    heading: "Company",
    links: [
      { label: "About", href: "/about" },
      { label: "Contact", href: "/contact" },
    ],
  },
  {
    id: "trust",
    heading: "Trust",
    links: [
      { label: "Privacy", href: "/privacy" },
      { label: "Terms", href: "/terms" },
      { label: "Compliance", href: "/compliance" },
      { label: "Security", href: "/security" },
    ],
  },
  {
    id: "developers",
    heading: "Developers",
    links: [
      { label: "API Documentation", href: "http://localhost:8000/docs" },
      { label: "OpenAPI Document", href: "http://localhost:8000/openapi.json" },
    ],
  },
] as const;

export const FOOTER_LEGAL = {
  /** Business facts that have not been supplied. A fabricated registration line is
   * worse than an obvious gap. */
  copyright: `© ${new Date().getFullYear()} SPA — Sport Performance Analysis`,
  note: "SPA is in development. Marketing content describes intended capability unless otherwise stated.",
} as const;
