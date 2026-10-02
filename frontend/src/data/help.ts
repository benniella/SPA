export interface HelpArticle {
  readonly id: string;
  readonly question: string;
  readonly answer: string;
}

export interface HelpTopic {
  readonly id: string;
  readonly label: string;
  readonly description: string;
  readonly articles: readonly HelpArticle[];
}

export const HELP_TOPICS: readonly HelpTopic[] = [
  {
    id: "account",
    label: "Account access",
    description: "Getting into an existing account, and what to do when a link does not work.",
    articles: [
      {
        id: "reset",
        question: "I forgot my password",
        answer:
          "Open Forgot password and enter the address on the account. A reset link is sent if an account exists for it; the link expires shortly, so use it soon.",
      },
      {
        id: "verify",
        question: "My verification link expired",
        answer:
          "Open Verify email and request a new link. The previous one is retired as soon as a new one is issued.",
      },
      {
        id: "no-link",
        question: "The reset email never arrived",
        answer:
          "Check the spam folder first. The message is sent to the address exactly as it was registered, so a typo in the domain is the usual cause.",
      },
    ],
  },
  {
    id: "workspace",
    label: "Workspaces",
    description: "Organisation boundaries and who can see what.",
    articles: [
      {
        id: "what",
        question: "What is a workspace?",
        answer:
          "A workspace is an organisation. Teams, players, matches, videos and analysis all belong to one, and data is not shared across organisations.",
      },
      {
        id: "slug",
        question: "What is the short name for?",
        answer:
          "The short name is the slug used in URLs. Lowercase letters, numbers and single hyphens.",
      },
      {
        id: "switch",
        question: "How do I switch workspace?",
        answer:
          "Use the workspace menu in the application header. If you belong to one organisation, that is the workspace you are already in.",
      },
    ],
  },
  {
    id: "data",
    label: "Your data",
    description: "Where data lives, and how it is removed.",
    articles: [
      {
        id: "where",
        question: "Where is my data stored?",
        answer:
          "Inside the organisation that collected it. Access is scoped to one organisation, and the browser never talks to the database directly.",
      },
      {
        id: "delete",
        question: "Can I delete my account?",
        answer:
          "Account deletion is not self-service yet. The account surface will name the path once it exists; until then this is an open item, not a hidden one.",
      },
    ],
  },
];

export const HELP_ANSWERS: readonly HelpArticle[] = HELP_TOPICS.flatMap(
  (topic) => topic.articles,
);

export function matchHelpAnswer(message: string): HelpArticle | undefined {
  const normalized = message.trim().toLowerCase();
  if (!normalized) return undefined;

  const scored = HELP_ANSWERS.map((article) => {
    const questionWords = article.question.toLowerCase().split(/\W+/).filter(Boolean);
    const score = questionWords.filter((word) => normalized.includes(word)).length;
    return { article, score };
  }).filter((entry) => entry.score > 0);

  scored.sort((a, b) => b.score - a.score);
  return scored[0]?.article;
}
