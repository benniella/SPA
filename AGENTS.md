# SPA Engineering Guidelines

This file defines the engineering standards for the SPA codebase.

These rules apply to all development work unless a more specific directory-level 'AGENTS.md' explicitly overrides them.

## 1. General Engineering Standard

Write production-quality code that looks like it was written and maintained by an experienced senior engineer.

Prioritize:

* correctness
* simplicity
* maintainability
* security
* clear architecture
* strong typing
* testability
* minimal unnecessary code
* consistency with the existing codebase

Do not optimize for code volume.

Do not optimize for the number of files created.

Do not introduce abstractions simply because they are theoretically reusable.

Prefer the simplest design that satisfies the actual requirement.

## 2. Read Before Changing

Before modifying code:

1. Inspect the relevant existing implementation.
2. Understand the existing architecture.
3. Identify existing abstractions that can be reused.
4. Check existing tests.
5. Check existing API contracts.
6. Check existing types and domain models.
7. Check whether the requested functionality already exists.

Do not create a second implementation of functionality that already exists.

Do not replace an existing abstraction without a concrete technical reason.

Do not assume the repository is missing functionality before inspecting it.

## 3. Preserve Existing Architecture

The existing architecture is authoritative unless the task explicitly requires a change.

Current core stack:

* Next.js
* React
* TypeScript
* FastAPI
* Pydantic
* SQLAlchemy
* PostgreSQL
* Alembic
* Vitest

Respect the existing:

* feature structure
* domain boundaries
* service boundaries
* API client
* type system
* design system
* configuration system
* testing conventions
* database architecture

Do not introduce a competing architecture.

Do not create duplicate:

* API clients
* state-management systems
* service layers
* authentication systems
* validation systems
* design systems
* utility libraries

unless the existing implementation is demonstrably inadequate.

## 4. No Speculative Engineering

Implement what the current phase requires.

Do not add infrastructure, dependencies, services, tables, abstractions, or features merely because they may be useful in the future.

Do not implement future-phase functionality early.

Examples:

* Do not add WebSockets before the realtime phase requires them.
* Do not add KeyDB before there is a concrete requirement for it.
* Do not add Prometheus before metrics infrastructure is required.
* Do not add Grafana before the Ops/observability phase.
* Do not implement ML before the ML phase.
* Do not create speculative database tables for future features.

Prepare clean boundaries for future functionality without implementing it prematurely.

## 5. Minimal Change Principle

Make the smallest correct change that satisfies the task.

Avoid unrelated refactoring.

Avoid opportunistic rewrites.

Avoid renaming working code without a concrete reason.

Avoid restructuring directories merely for personal preference.

If unrelated technical debt is discovered:

* document it if relevant
* fix it only if it blocks the current task
* otherwise leave it for a dedicated task

A feature implementation should not become a codebase rewrite.

## 6. Comments

The default is to write no comment.

SPA uses very few comments. The code should explain itself through:

* good naming
* clear structure
* small functions
* appropriate types
* sensible abstractions

Do not write comments that merely describe what the code obviously does.

Bad:

'''ts
// Check if the user is authenticated
if (user) {
'''

Bad:

'''ts
// Set the loading state to true
setLoading(true)
'''

Bad:

'''ts
// Loop through the players
for (const player of players) {
'''

These comments add no value.

Python Module Docstrings

Do not add module-level docstrings to ordinary application .py files unless they are genuinely required by the module's public API, tooling, or framework behavior.

Do not use module docstrings to explain:

application architecture
request or processing flows
state machines or lifecycles
worker behavior
database workflows
authentication flows
business logic
why the module exists
how multiple services interact

Do not write architecture essays, implementation explanations, workflow descriptions, or multi-line prose at the top of Python files.

Bad:

"""Processing jobs: the durable record of asynchronous video work.

A job is the bridge between a synchronous API request and a worker process.
The API writes the row and enqueues an identifier; the worker reads the row,
does the work, and records the outcome...
"""

Preferred:

No module docstring when the filename and code are already clear.
If a module docstring is genuinely required, keep it to one short sentence.
Put important behavior in clear names, types, enums, function boundaries, and tests instead of explanatory prose.

The default for a new Python application file is no module docstring.

Do not add a module docstring merely because a new .py file was created.
Do not add docstrings to ordinary functions, classes, tests, or helpers unless the behavior is genuinely non-obvious or documentation is required by the public API.

Before completing a task, review newly created and modified Python files and remove unnecessary module docstrings, verbose docstrings, architecture explanations, and generated prose.

### Only comment genuinely non-obvious information.

A comment is allowed only when it explains something that cannot reasonably be understood from the code itself, such as:

* security reasoning
* an intentional workaround
* browser, runtime, or framework behavior that is not obvious from the code
* an important architectural constraint
* a subtle invariant that future maintainers genuinely need to know

Prefer explaining **why**, not **what**.

Example:

'''ts
// Keep the token hash rather than the raw token so a database read cannot be used to authenticate a reset request.
'''

That is useful because the security reasoning is not obvious from the surrounding code.

Even a comment like:

'''ts
// Browser upload uses XHR because fetch does not expose upload progress.
'''

should only exist when the reason is not already obvious from the implementation.

Keep any necessary comment short and specific.

### Do not document ordinary code

Do not add comments to ordinary functions, components, tests, helpers, or obvious implementation details.

Do not add a comment simply because a file, function, class, hook, component, or endpoint is new.

Do not add comments to make generated code appear documented.

Do not use multiline explanatory comments for normal implementation.

Do not add:

'''text
/**
 * ...
 */
'''

or:

'''text
/*
 * ...
 */
'''

for obvious code behavior.

Bad:

'''text
/**
 * The video library: upload and delete.
 *
 * The upload path is exercised against...
 */
'''

when the code and test names already communicate that information.

Prefer no comment.

### Absolutely prohibited comment patterns

Do not generate decorative separators:

'''text
// ===== Authentication =====
'''

'''text
// ------------------------
'''

'''text
// Video upload
// ------------------------
'''

'''text
/* ========================
 * Video Upload
 * ======================== */
'''

Do not generate story-like comments.

Do not narrate the implementation.

Do not write comments explaining every step of a function.

## 7. Absolutely No Story Comments

Do not write comments as explanations, tutorials, narratives, or essays.

Never add comments like:

'''text
// First we need to check the user's session.
// Once we have confirmed that the user is authenticated,
// we can safely continue with the request.
// This is important because...
'''

Do not narrate implementation steps inside source code.

Do not write comments explaining the entire feature.

Do not write comments that read like documentation embedded inside functions.

Documentation belongs in:

* README files
* architecture documentation
* ADRs
* dedicated technical documentation

not inside ordinary implementation code.

## 8. No Decorative Comment Separators

Never use decorative comment separators.

Do not add:

'''text
// ----
'''

'''text
// ---- Authentication ----
'''

'''text
// =========================
'''

'''text
// ===== Authentication =====
'''

'''text
/* ======================== */
'''

'''text
# --------------------------
'''
or similar visual separators.

Do not use comments as visual section headings inside source files.

### Quote characters

Use the plain ASCII apostrophe ' for quoting identifiers, filenames and phrases inside comments, never a backtick `.

Backticks are reserved for Markdown code formatting in documentation files, not for ordinary source comments. Mixing the two produces comments that read like generated Markdown and renders inconsistently across editors.

Bad:

'''ts
// The ' 'storage_key' ' is resolved by the storage port.
'''

Good:

'''ts
// The 'storage_key' is resolved by the storage port.
'''

## 9. No Generated-Looking Comment Blocks

Do not produce large blocks of comments at the top of files explaining the file's contents.

### No file-header docblocks

Do not open a source file with a '/** ... */' block that narrates what the file is, what it contains, or how it works. This is the single most common form of generated noise and it is not permitted.

Bad:

'''text
/**
 * The upload control for the video library.
 *
 * The flow is the two-step one the API publishes: reserve a storage key and get a
 * presigned URL, PUT the bytes straight to storage, then confirm.
 */
'''

Good: no header at all. The file's name, its exports and its code state what it is.

A file header is permitted only when it carries a genuinely non-obvious constraint that a reader cannot recover from the code — a security decision, a licensing obligation, or a framework limitation. One or two lines, never a paragraph, and never a description of the file's contents.

Bad:

'''text
/**
 * Authentication Service
 *
 * This service is responsible for...
 *
 * Responsibilities:
 * - ...
 * - ...
 * - ...
 */
'''

unless the project specifically requires formal API documentation.

Normal source files should remain clean.

### Multi-line docblocks

A multi-line '/** ... */' or '/* ... */' comment above a function, class, type or constant is discouraged. It is acceptable only when the reasoning genuinely needs several sentences to be correct — a security argument, a compatibility workaround, a non-obvious invariant.

If the reasoning fits in one line, use one line:

'''ts
/** Stub the direct-to-storage PUT, which goes through XMLHttpRequest. */
'''

If it does not fit in one line, first ask whether the code can be made clearer so that it does not need to be explained. Only then write the multi-line block, and keep it to what the code cannot say.

## 10. JSDoc Policy

Do not add JSDoc automatically.

JSDoc is allowed only when it provides meaningful API or documentation value that cannot be communicated clearly through naming and types, or when it is genuinely required by the public API or tooling.

For internal functions, components, test helpers, hooks, services, and ordinary application code: prefer no JSDoc.

A JSDoc block that only restates the signature, the parameter names, or the obvious purpose of the code adds no value and is not permitted.

## 11. String Syntax

Use the simplest valid string syntax.

For ordinary strings, use single quotes:

'''ts
const name = 'video';
'''

Use template literals only when they are actually required:

'''ts
const path = `/videos/${videoId}`;
'''

The rule is:

* no interpolation or template behavior required → single quotes
* interpolation or template behavior required → template literal

Do not use template literals merely because they are available.

Do not replace template literals with single quotes when interpolation is required.

Never turn:

'''ts
`/videos/${videoId}`
'''

into:

'''ts
'/videos/${videoId}'
'''

because that changes the runtime value.

Do not mechanically convert one quote type to another, and do not convert ordinary strings into template literals without a reason.

Follow the repository's existing formatter/linter configuration where it establishes the exact quote convention.

## 12. Do Not Mechanically Modify Unrelated Files

When implementing a feature:

* modify only the files required for the task
* do not reformat unrelated files
* do not perform repository-wide quote conversions
* do not perform repository-wide comment cleanup unless explicitly requested
* do not run broad automated transformations that can alter semantics

If an existing defect blocks the requested phase, fix only the minimum necessary scope and report it.

## 13. No Comment Inflation

Do not add comments simply because a function, class, hook, component, or endpoint is new.

New code does not automatically require comments.

Before adding a comment, ask:

> Would an experienced engineer understand this from the code itself?

If yes, do not add the comment.

## 14. No Redundant Documentation

Do not repeat information that is already obvious from:

* function names
* variable names
* types
* schemas
* route names
* class names

Bad:

'''ts
// Email address of the user
const userEmail: string
'''

Good:

'''ts
const userEmail: string
'''

## 15. Code Should Communicate Intent

Prefer:

'''ts
const verifiedUsers = users.filter((user) => user.emailVerified)
'''

over:

'''ts
// Filter users that have verified emails
const result = users.filter((user) => user.emailVerified)
'''

Use meaningful names instead of explanatory comments.

## 16. Avoid Over-Abstraction

Do not create:

* factories for one implementation
* interfaces for one implementation without a real boundary
* wrappers around simple functions
* utility functions used once without a meaningful reason
* generic frameworks inside the application
* configuration systems for one value

Abstractions should exist because they solve a real problem.

## 17. Avoid Over-Engineering

Do not implement hypothetical requirements.

Do not create:

* unused feature flags
* unused configuration
* unused interfaces
* unused services
* unused database fields
* unused API endpoints
* unused event systems

Do not build infrastructure for a future requirement before that requirement exists.

## 18. Dependencies

Before adding a dependency:

1. Check whether the functionality already exists in the project.
2. Check whether the platform/framework already provides it.
3. Check whether a small local implementation is more appropriate.
4. Add the dependency only when it provides meaningful value.

Do not add dependencies merely for convenience.

After adding a dependency, ensure it is actually used.

## 19. Frontend Standards

Prefer:

* server components where appropriate
* client components only when required
* typed API responses
* reusable feature components
* existing design tokens
* existing UI primitives
* semantic HTML

Avoid:

* unnecessary client components
* duplicated API requests
* inline business logic scattered across pages
* giant page components
* global state for local state
* arbitrary CSS values when design tokens already exist

## 20. Backend Standards

Follow the existing domain/application/infrastructure separation.

Keep:

* domain logic in appropriate domain/application layers
* API concerns in API layers
* persistence concerns in infrastructure
* schemas separate from persistence models
* external providers behind appropriate boundaries

Do not place business logic directly into route handlers when it belongs in the application/domain layer.

## 21. API Standards

Reuse the existing API client on the frontend.

Do not scatter raw 'fetch()' calls throughout components.

Backend endpoints should:

* validate input
* authorize access
* return appropriate status codes
* use typed schemas
* avoid leaking internal errors
* follow existing API conventions

Do not expose internal implementation details through API responses.

## 22. Security

Security-sensitive code must be conservative.

Never log:

* passwords
* password hashes
* authentication tokens
* reset tokens
* verification tokens
* API keys
* session secrets
* authorization headers

Never commit secrets.

Never expose backend secrets to frontend bundles.

Do not weaken security controls to make tests pass.

Do not bypass authorization because the frontend already hides a resource.

Backend authorization is authoritative.

## 23. Authorization

Never assume that because a user is authenticated they are authorized to access a resource.

For organization-scoped resources, verify:

'''text
authenticated user
        ↓
organization membership
        ↓
required permission
        ↓
resource access
'''

Do not trust organization IDs supplied by the client without server-side verification.

Always consider cross-organization access when implementing resource endpoints.

## 24. Error Handling

Errors should be intentional and useful.

Do not expose:

* stack traces
* SQL errors
* internal file paths
* infrastructure details
* secret values
* implementation details

Use existing application error-handling patterns.

Do not create a different error-handling approach for each feature.

## 25. Logging

Logs should contain useful operational information without sensitive data.

Do not add logs merely to show that each line of code executed.

Avoid noisy logs.

Prefer structured logging where supported by the existing architecture.

## 26. Database Changes

Do not modify existing historical migrations.

Create a new migration when a schema change is required.

Do not reset the database to avoid migration problems.

Do not add speculative tables or columns.

Use database constraints for important invariants where appropriate.

## 27. Testing

Write tests for behavior, not implementation details.

Prioritize:

* security boundaries
* authorization
* business rules
* API behavior
* important frontend interactions
* failure cases
* regression-prone functionality

Do not add tests merely to increase the test count.

Do not mock everything unnecessarily.

Existing tests must continue passing.

### Test comments

Tests follow the same comment discipline as production code.

Do not add comments explaining what a test does when the test name already explains it.

Prefer:

'''ts
it('reserves, uploads directly to storage, then confirms', async () => {
'''

without a large explanatory block above it.

Only comment a test when the test captures a non-obvious constraint that would otherwise be easy to misunderstand.

## 28. Test Before Declaring Completion

Before reporting a task as complete:

Run the relevant checks.

At minimum, use the project's existing:

* formatter
* linter
* type checker
* unit tests
* integration tests where relevant
* production build where relevant

Do not claim a check passed if it was not actually run.

If a check fails:

1. Investigate it.
2. Fix it if it belongs to the current task.
3. Report it clearly if it cannot be resolved.

## 29. Do Not Hide Failures

Never:

* delete failing tests to make the suite pass
* weaken assertions without justification
* disable lint rules unnecessarily
* suppress type errors without understanding them
* ignore migration failures
* hide runtime errors
* mark incomplete work as complete

If a workaround is genuinely necessary, document the reason briefly in the appropriate documentation.

## 30. Existing Functionality Is Sacred

Before changing existing behavior, determine:

* why it exists
* what depends on it
* what tests cover it
* whether it is part of a previous completed phase

Do not break completed functionality to simplify a new feature.

Regression prevention is part of every task.

## 31. UI Consistency

Use existing SPA design language.

Do not create a new visual system for every feature.

Reuse:

* typography
* colors
* spacing
* buttons
* cards
* forms
* navigation
* loading states
* empty states
* error states

Do not introduce generic SaaS styling when a SPA component already exists.

## 32. Accessibility

New UI should support:

* keyboard navigation
* visible focus
* semantic structure
* accessible labels
* appropriate contrast
* reduced motion
* screen-reader-compatible interaction

Do not use color as the only state indicator.

## 33. Responsive Design

Do not implement desktop-only interfaces unless explicitly required.

Consider:

* desktop
* tablet
* mobile
* narrow mobile

Do not add horizontal scrolling as a shortcut for fixing layout problems.

## 34. Naming

Use names that communicate intent.

Avoid vague names such as:

'''text
data
thing
item
temp
stuff
helper
manager
process
result
'''

unless their meaning is genuinely clear from context.

Prefer domain-specific names.

## 35. Function Size

Keep functions focused.

If a function becomes difficult to understand, first consider whether its responsibilities should be separated.

Do not split every small operation into a separate abstraction merely to reduce line count.

## 36. TypeScript

Maintain strict typing.

Do not use:

'''ts
any
'''

as an escape hatch.

Do not suppress TypeScript errors without understanding the underlying issue.

Prefer precise types.

Do not duplicate types when an existing domain/API type can be reused.

## 37. Python

Follow the project's existing Python conventions.

Use type hints.

Avoid unnecessary dynamic behavior.

Do not suppress type-checking errors without understanding why they occur.

Keep domain logic testable.

## 38. API and Domain Types

Do not allow API response shapes to drift from frontend types.

When an API contract changes:

* update the appropriate schema
* update the appropriate frontend type
* update affected services
* update tests

Do not solve contract mismatches with unsafe casts.

## 39. Configuration

Configuration should come from environment/configuration where appropriate.

Do not hardcode:

* secrets
* production credentials
* deployment-specific URLs
* provider keys
* environment-specific infrastructure settings

Do not expose server-only environment variables to the client.

## 40. Environment Awareness

Distinguish:

'''text
development
test
staging
production
'''

Do not make development shortcuts silently affect production.

Do not disable security controls globally simply because local development is inconvenient.

## 41. Future Architecture

SPA will eventually include infrastructure such as:

'''text
app.spanalysis.com
ops.spanalysis.com
api.spanalysis.com
ws.spanalysis.com
KeyDB
Resend
Prometheus
Grafana
Object Storage
Workers
Computer Vision
ML
'''

These should be introduced when their respective phases require them.

Do not implement future architecture prematurely.

## 42. Phase Discipline

Every implementation task belongs to a phase.

Before implementing a feature, determine:

* Is it required by the current phase?
* Does it already exist?
* Does it belong to a later phase?
* Will implementing it now create unnecessary coupling?

If it belongs to a later phase, do not implement it unless explicitly instructed.

## 43. Documentation Discipline

Documentation should explain things that future developers genuinely need to know.

Good documentation:

* architecture decisions
* setup requirements
* security decisions
* external service configuration
* deployment requirements
* non-obvious constraints

Do not document obvious code line-by-line.

## 44. Generated Code

Code should look like it was written by a senior engineer, not generated by an AI assistant.

Avoid:

* verbose comments
* repetitive explanations
* obvious documentation
* unnecessary abstractions
* unnecessary wrappers
* repetitive validation
* decorative code structure
* excessive type indirection
* unnecessary helper functions
* comments explaining straightforward tests
* comments explaining obvious assertions

Prefer:

* clear names
* small functions
* strong types
* existing abstractions
* direct control flow
* minimal comments
* minimal dependencies

The code itself should communicate what it does.

If a tool generates code, review it before accepting it.

Do not blindly keep:

* verbose comments
* redundant abstractions
* unnecessary wrappers
* unused imports
* duplicate types
* generated-looking prose
* decorative separators
* speculative functionality

Generated code must conform to this file.

## 45. AI Coding Agent Behavior

When using an AI coding agent:

1. Inspect before modifying.
2. Reuse existing architecture.
3. Make focused changes.
4. Avoid speculative work.
5. Avoid unnecessary comments.
6. Avoid unnecessary files.
7. Avoid unnecessary dependencies.
8. Run relevant tests.
9. Review the diff.
10. Remove generated noise before completion.

Do not treat a large diff as evidence of better implementation.

A smaller, correct diff is preferable.

## 46. Diff Review

Before declaring a task complete, review the resulting diff.

Look specifically for:

* unnecessary files
* unrelated changes
* generated comments
* verbose comments
* decorative comment separators
* unnecessary comments
* JSDoc that adds no real value
* multiline explanatory comments
* unnecessary template literals
* incorrect quote conversions
* generated-looking prose
* unrelated formatting changes
* duplicated code
* unused imports
* unused dependencies
* accidental API changes
* accidental database changes
* weakened security
* debug logging
* temporary code
* TODOs that should not have been introduced

Clean these up before completion.

Do not claim the work is complete until this review has been performed.

## 47. TODO Discipline

Do not add TODO comments simply because something could be improved later.

Only add a TODO when:

* the deferred work is intentional
* it is relevant to the architecture
* it cannot reasonably be completed in the current task
* the TODO provides useful context

Do not use TODOs as a substitute for completing required work.

## 48. No Fake Completion

Never claim:

'''text
implemented
tested
verified
production-ready
complete
'''

unless the implementation and verification actually support the claim.

The final report must distinguish:

* implemented
* verified
* deferred
* known limitations

## 49. Final Standard

The desired codebase should feel:

* deliberate
* clean
* restrained
* secure
* maintainable
* strongly typed
* well tested
* architecturally consistent

It should NOT feel:

* AI-generated
* over-commented
* over-engineered
* verbose
* repetitive
* speculative
* cluttered
* unnecessarily abstract

When choosing between more code and clearer code, prefer clearer code.

When choosing between more comments and better naming, prefer better naming.

When choosing between a new abstraction and an existing suitable abstraction, prefer the existing abstraction.

When choosing between implementing future functionality and preserving phase boundaries, preserve phase boundaries.
