import type { IconName } from "@/data/marketing";

/* Shared types */

export interface ContentSection {
  readonly id: string;
  readonly heading: string;
  readonly paragraphs: readonly string[];
  /** Bullet items, when the section is a list of facts rather than prose. */
  readonly items?: readonly string[];
  /** Rendered as a marked placeholder block instead of final policy language. */
  readonly placeholder?: boolean;
}

/** A control or practice, tagged with whether it exists today. */
export interface StatusItem {
  readonly id: string;
  readonly label: string;
  readonly description: string;
  readonly status: "current" | "planned";
  readonly icon: IconName;
}

/* Contact */

export const CONTACT = {
  emailPlaceholder: "hello@spanalysis.com",
  isPlaceholder: true,
  note: "This address is a placeholder. No public contact mailbox has been configured for this deployment yet, so nothing sent here reaches anyone.",
  responseExpectation:
    "A response-time commitment will be published once a monitored mailbox and an on-call rota exist.",
} as const;

export interface ContactChannel {
  readonly id: string;
  readonly label: string;
  readonly detail: string;
  readonly icon: IconName;
  readonly placeholder?: boolean;
}

export const CONTACT_CHANNELS: readonly ContactChannel[] = [
  {
    id: "general",
    label: "General enquiries",
    detail: CONTACT.emailPlaceholder,
    icon: "ai",
    placeholder: true,
  },
  {
    id: "security",
    label: "Security reports",
    detail: CONTACT.emailPlaceholder,
    icon: "detect",
    placeholder: true,
  },
  {
    id: "api",
    label: "API documentation",
    detail: "http://localhost:8000/docs",
    icon: "analytics",
  },
] as const;

/* About (#20) */

export const ABOUT = {
  eyebrow: "About",
  heading: "Sports video is already there. The information inside it is not.",
  lede: "SPA is a performance-analysis platform. It takes a recording of a match and turns it into structured measurements a coach, analyst or athlete can work with.",
  sections: [
    {
      id: "what-spa-is",
      heading: "What SPA is",
      paragraphs: [
        "SPA — Sport Performance Analysis — is software for turning sports footage into performance data. Video goes in; tracked positions, distances, speeds, workload and movement patterns come out.",
        "It is built for the people who already watch the footage: athletes reviewing their own performance, coaches preparing a unit, analysts answering a specific question, and performance departments measuring a programme across a season.",
      ],
    },
    {
      id: "problem",
      heading: "The problem it addresses",
      paragraphs: [
        "A recording of a match contains far more than a person can watch. A single passage of play is dozens of simultaneous movements, and a full match is hours of them.",
        "Watching it back tells you what happened. It does not reliably tell you how far a player ran, how often they accelerated, where they were when a goal was conceded, or whether that changed between the first half and the second — not for every player, and not consistently from one week to the next.",
        "Measurement is the part human attention cannot do at scale. That gap is what SPA exists to close.",
      ],
    },
    {
      id: "how",
      heading: "How video becomes performance data",
      paragraphs: [
        "SPA is designed around five stages: upload, detect, track, analyse and understand.",
        "Footage is ingested and probed for its properties. Players and the ball are located in each analysed frame. Those detections are associated across frames into stable identities, so a movement becomes a trajectory rather than a series of unrelated positions. Trajectories are converted into metrics — distance, speed, acceleration, workload, position. And those metrics are organised into reports and views.",
        "Each stage produces something the next can use, which is what makes a number traceable: a metric can always be followed back to the tracking data and the frame it came from.",
      ],
    },
    {
      id: "who",
      heading: "Who it is built for",
      paragraphs: [
        "SPA is intended for athletes, coaches, analysts, teams, academies and performance departments. Those groups need different things from the same footage, which is why the platform is organised around questions rather than around a single dashboard.",
      ],
      items: [
        "Athletes — their own numbers, match to match.",
        "Coaches — how far the team ran, where shape was lost, who faded.",
        "Analysts — the underlying data, queryable and exportable.",
        "Teams — one workspace across matches, squads and seasons.",
        "Academies — development tracking across age groups and years.",
        "Performance departments — consistent measurement across a programme.",
      ],
    },
    {
      id: "direction",
      heading: "Where this is going",
      paragraphs: [
        "Football is the first sport modelled. Basketball, rugby, tennis, athletics, volleyball and hockey are planned: the detection, tracking and movement analysis stages are shared, and what changes between sports is the pitch geometry, the movement thresholds and the vocabulary.",
        "The platform is in development. Nothing in this repository is presented as a measured result, and the public pages describe intended capability wherever that differs from what exists today.",
      ],
    },
  ] as const satisfies readonly ContentSection[],
} as const;

/* Privacy (#21) */

export const PRIVACY = {
  eyebrow: "Privacy",
  heading: "Privacy",
  effectiveDate: "Not yet in force",
  lede: "This page describes how SPA handles information and performance data. It is a product-facing description of the intended policy, not a final legal document.",
  notice: {
    title: "This is not yet a final privacy policy",
    body: "SPA is in development and no production deployment is processing real user data. The sections below describe the categories of information the platform is designed to handle and the commitments it is being built to meet. Where a policy decision has not been made, the section says so rather than stating a term that has not been agreed.",
  },
  sections: [
    {
      id: "collected",
      heading: "Information collected",
      paragraphs: ["The platform is designed to handle the following categories of information."],
      items: [
        "Account information — name, email address, and the organisation an account belongs to.",
        "Sports video — footage uploaded for analysis, and the metadata extracted from it such as duration, resolution and frame rate.",
        "Performance data — positions, trajectories and the metrics derived from them.",
        "Organisational records — teams, squads, players, matches and seasons.",
        "Technical information — timestamps, request identifiers and error reports needed to operate the service.",
      ],
    },
    {
      id: "use",
      heading: "How information is used",
      paragraphs: [
        "Information is used to provide the analysis service described on this site: to process footage, produce performance data, present it back to the organisation that uploaded it, and to operate and secure the platform.",
      ],
      items: [
        "Processing footage to produce tracking and performance data.",
        "Displaying results to the organisation that owns the footage.",
        "Maintaining service reliability and diagnosing failures.",
        "Meeting legal obligations where they apply.",
      ],
    },
    {
      id: "video-data",
      heading: "Video and performance data",
      paragraphs: [
        "Sports footage and the performance data derived from it belong to the organisation that uploads it. SPA is a processor of that data, not an owner of it.",
        "Footage may contain identifiable people. Where a deployment processes footage of minors, or footage captured in a jurisdiction with specific requirements around personal data, the organisation uploading it is responsible for having the right to do so and for the consents that apply.",
      ],
    },
    {
      id: "accounts",
      heading: "Account information",
      paragraphs: [
        "Accounts belong to an organisation, and access is scoped to that organisation. Authentication and invitation flows are not implemented in the current build; the account model exists in the domain, and the mechanism for credentials and sessions is an open decision.",
      ],
      placeholder: true,
    },
    {
      id: "cookies",
      heading: "Cookies and analytics",
      paragraphs: [
        "The current build sets no advertising or third-party analytics cookies. One browser storage entry is used to remember the visitor's colour-theme preference, which contains no personal information and is never sent to a server.",
        "If product analytics are introduced, this section will list them individually, and consent will be requested before any non-essential cookie is set.",
      ],
    },
    {
      id: "retention",
      heading: "Data retention",
      paragraphs: [
        "Retention periods for footage, tracking data and derived metrics are not yet finalised. They will be configurable per organisation, because a professional club and an academy have different obligations regarding how long footage of their players is kept.",
      ],
      placeholder: true,
    },
    {
      id: "security",
      heading: "Data security",
      paragraphs: [
        "Access to an organisation's data is scoped to that organisation, and infrastructure is configured so that credentials are held only by the service that needs them. The security page describes the current practices and the controls still planned in more detail.",
      ],
    },
    {
      id: "third-parties",
      heading: "Third-party services",
      paragraphs: [
        "SPA is designed to run on managed infrastructure and, in time, managed object storage for video. Each provider that processes data on behalf of the platform will be listed here with what it processes and where.",
        "No third-party processor is currently listed, because no production deployment is handling real data.",
      ],
      placeholder: true,
    },
    {
      id: "rights",
      heading: "Your rights",
      paragraphs: [
        "Requests to access, correct, export or delete personal data should be addressed to the organisation that operates the SPA workspace holding the data, which is the controller for that data. SPA supports those requests; it does not decide them.",
        "A monitored contact route for data requests is not yet in place. See the contact page for the current position.",
      ],
      placeholder: true,
    },
    {
      id: "contact",
      heading: "Contact",
      paragraphs: [
        "Questions about this page can be directed to the address on the contact page. It is currently a placeholder, as no public mailbox has been configured for this deployment.",
      ],
      placeholder: true,
    },
  ] as const satisfies readonly ContentSection[],
} as const;

/* Terms (#22) */

export const TERMS = {
  eyebrow: "Terms",
  heading: "Terms of service",
  effectiveDate: "Not yet in force",
  lede: "These terms describe the intended basis on which SPA is provided. They are a structural presentation prepared for legal review, not final terms.",
  notice: {
    title: "These are not final terms of service",
    body: "No contract is formed by this page. The sections below set out the structure a final agreement will follow, so the document can be reviewed and completed. Terms marked as open are decisions that have not been made, not terms that have been agreed and omitted.",
  },
  sections: [
    {
      id: "agreement",
      heading: "Agreement",
      paragraphs: [
        "Access to SPA will be governed by an agreement between the organisation using the platform and the provider of the platform. The final wording of that agreement has not been settled.",
      ],
      placeholder: true,
    },
    {
      id: "accounts",
      heading: "Accounts and access",
      paragraphs: [
        "An account belongs to an organisation. Administrators of that organisation control who within it may access its workspaces and data. Users are responsible for keeping their credentials confidential and for activity under their account.",
      ],
    },
    {
      id: "acceptable-use",
      heading: "Acceptable use",
      paragraphs: [
        "The platform may not be used to upload or process content the organisation has no right to hold.",
      ],
      items: [
        "Uploading footage without the rights and consents required to analyse it.",
        "Attempting to access another organisation's data.",
        "Interfering with the operation of the platform or its infrastructure.",
        "Reverse-engineering the service or reselling it without agreement.",
      ],
    },
    {
      id: "customer-data",
      heading: "Customer data and ownership",
      paragraphs: [
        "The organisation that uploads footage retains ownership of it and of the performance data derived from it. SPA processes that data to provide the service and for no other purpose.",
      ],
    },
    {
      id: "availability",
      heading: "Availability and support",
      paragraphs: [
        "A service-level commitment has not been defined. Availability targets, support hours and escalation paths will be agreed with an organisation before a production deployment is relied upon.",
      ],
      placeholder: true,
    },
    {
      id: "liability",
      heading: "Liability",
      paragraphs: [
        "The limitation of liability has not been drafted. It requires legal review and will be part of the final agreement rather than a product decision.",
      ],
      placeholder: true,
    },
    {
      id: "termination",
      heading: "Termination and data return",
      paragraphs: [
        "An organisation will be able to end its agreement and export or delete its data. The export formats, notice period and deletion window have not been finalised.",
      ],
      placeholder: true,
    },
    {
      id: "changes",
      heading: "Changes to these terms",
      paragraphs: [
        "Material changes will be communicated to the organisation's administrators before they take effect. The mechanism for that notification will be defined alongside the final agreement.",
      ],
      placeholder: true,
    },
    {
      id: "law",
      heading: "Governing law",
      paragraphs: [
        "No governing jurisdiction has been selected. Naming one now would be inventing a business fact, so the section is left open until legal review.",
      ],
      placeholder: true,
    },
  ] as const satisfies readonly ContentSection[],
} as const;

/* Compliance (#23) */

export const COMPLIANCE = {
  eyebrow: "Compliance",
  heading: "Data protection and responsible handling",
  lede: "How SPA approaches the data it processes, and an honest separation between the practices that exist today and the controls that are planned.",
  certificationNotice:
    "SPA holds no security or privacy certifications. SOC 2, ISO 27001, HIPAA and PCI DSS are not claimed, and there is no certified GDPR compliance programme. The practices below are engineering decisions, not audited controls.",
  practices: [
    {
      id: "tenant-isolation",
      label: "Organisation-scoped data access",
      description:
        "Every record carries the organisation that owns it, and queries are scoped to one organisation. Enforcement lives in the API layer, which is the only path to the database.",
      status: "current",
      icon: "detect",
    },
    {
      id: "frontend-isolation",
      label: "No database access from the browser",
      description:
        "The frontend holds no database credentials. Its only data path is the versioned HTTP API, so the browser never reaches storage directly.",
      status: "current",
      icon: "vision",
    },
    {
      id: "migrations",
      label: "Versioned schema changes",
      description:
        "Database schema changes are applied through reviewed, ordered migrations rather than ad-hoc edits, so the shape of stored data is reproducible.",
      status: "current",
      icon: "analytics",
    },
    {
      id: "secrets",
      label: "Configuration kept out of source",
      description:
        "Credentials are supplied through environment configuration and are absent from the repository. Only browser-safe values use the public prefix.",
      status: "current",
      icon: "ai",
    },
    {
      id: "audit",
      label: "Provenance on derived data",
      description:
        "Tracking datasets and metrics record the run and the definition version that produced them, so a figure can be traced back to the footage it came from.",
      status: "current",
      icon: "track",
    },
    {
      id: "access-control",
      label: "Role-based access control",
      description:
        "Roles scoped per organisation, so a coach, an analyst and an administrator see different surfaces. The model is defined; enforcement arrives with authentication.",
      status: "planned",
      icon: "user",
    },
    {
      id: "retention",
      label: "Configurable retention and deletion",
      description:
        "Per-organisation retention windows and a deletion path covering footage, tracking data and derived metrics.",
      status: "planned",
      icon: "upload",
    },
    {
      id: "audit-log",
      label: "Access and change audit log",
      description:
        "A record of who accessed or altered which data, exportable by an organisation's administrators.",
      status: "planned",
      icon: "sport",
    },
    {
      id: "certification",
      label: "Independent audit",
      description:
        "An external security assessment and a recognised certification once the platform is processing real customer data at scale.",
      status: "planned",
      icon: "check",
    },
  ] as const satisfies readonly StatusItem[],
  sections: [
    {
      id: "sports-data",
      heading: "Sports and performance data",
      paragraphs: [
        "Performance data is sensitive in a way that is easy to overlook. It can describe a person's physical capability, their workload, and in some cases their medical availability. It is not public information even when the match was.",
        "The platform is designed on the basis that this data belongs to the organisation that collected it, that access is limited to that organisation, and that the organisation decides who inside it may see which players' data.",
      ],
    },
    {
      id: "personal-data",
      heading: "Personal data in footage",
      paragraphs: [
        "Video may contain identifiable individuals, including minors in academy settings. SPA processes footage on the instruction of the organisation that uploads it, and that organisation is responsible for having the right to do so.",
        "Features that would require specific handling — distinguishing a participant who has asked not to be identifiable, or handling a deletion request that touches derived metrics as well as the source footage — are not yet implemented.",
      ],
      placeholder: true,
    },
    {
      id: "data-lifecycle",
      heading: "Data lifecycle",
      paragraphs: [
        "The intended lifecycle is: upload, process, retain for a configured window, then delete on request or on expiry. Storage tiers and the deletion guarantee for derived data still need to be defined.",
      ],
      placeholder: true,
    },
  ] as const satisfies readonly ContentSection[],
} as const;

/* Security (#24) */

export const SECURITY = {
  eyebrow: "Security",
  heading: "Security",
  lede: "The principles SPA is built on, what is in place today, and what is still to come.",
  disclosureNotice:
    "This page describes principles and practices only. It deliberately does not detail infrastructure, internal service boundaries or credential handling, because publishing those details would weaken the thing it describes.",
  principles: [
    {
      id: "by-design",
      label: "Security by design",
      description:
        "Access boundaries are expressed in the architecture rather than added as a check afterwards. The clearest example: the browser has no database credentials to leak, because it has no database access at all.",
      status: "current",
      icon: "detect",
    },
    {
      id: "least-privilege",
      label: "Least privilege",
      description:
        "Each component is given only the access it needs. The API is the single path to stored data, so tenancy enforcement has one implementation instead of several.",
      status: "current",
      icon: "detect",
    },
    {
      id: "transport",
      label: "Encryption in transit",
      description:
        "Production traffic is served over TLS and the API is not exposed over plain HTTP in a deployed environment.",
      status: "current",
      icon: "vision",
    },
    {
      id: "encryption-at-rest",
      label: "Encryption at rest",
      description:
        "Stored footage and database volumes rely on the encryption provided by managed infrastructure. Application-level encryption of video has not been implemented.",
      status: "planned",
      icon: "upload",
    },
    {
      id: "authentication",
      label: "Authentication",
      description:
        "The mechanism for credentials, sessions and token lifetime is an open decision. No authentication is implemented yet, and no sign-in form is presented, because a form that authenticates nothing would be worse than none.",
      status: "planned",
      icon: "ai",
    },
    {
      id: "monitoring",
      label: "Monitoring and alerting",
      description:
        "Service health is checked against a readiness endpoint that verifies database connectivity. Error tracking and alerting on security-relevant events are not yet in place.",
      status: "planned",
      icon: "analytics",
    },
    {
      id: "backups",
      label: "Backup and recovery",
      description:
        "Backup frequency, retention and a tested restore procedure will be defined before any production data is held.",
      status: "planned",
      icon: "track",
    },
    {
      id: "dependency",
      label: "Dependency and build integrity",
      description:
        "Dependencies are pinned and a production build is required to type-check and lint, so a change that breaks the contract does not reach a deployment.",
      status: "current",
      icon: "check",
    },
  ] as const satisfies readonly StatusItem[],
  reporting: {
    heading: "Reporting a vulnerability",
    paragraphs: [
      "If you believe you have found a security issue in SPA, please report it privately. Do not open a public issue, and do not test against data that is not yours.",
    ],
    items: [
      "Describe the issue and the steps to reproduce it.",
      "Include the affected page or endpoint if you know it.",
      "Do not access, modify or exfiltrate data belonging to anyone else.",
      "Give a reasonable window to respond before disclosing publicly.",
    ],
    placeholder: true,
  },
  sections: [] as readonly ContentSection[],
} as const;
