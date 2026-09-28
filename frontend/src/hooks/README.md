# Hooks

Reusable React hooks that are **not specific to one feature**.

Feature-specific hooks live in 'features/<capability>/hooks/' so they can change
with the feature. A hook is promoted here only when a second feature genuinely
needs it — putting it here first would create a shared surface nobody owns.

## What belongs here (Phase 1+)

| Hook                | Purpose                                                                 |
| ------------------- | ----------------------------------------------------------------------- |
| 'useApiQuery'       | Fetch-and-cache against the API, with abort-on-unmount and error typing |
| 'usePollingQuery'   | Poll a resource until a terminal status — the analysis-progress pattern |
| 'useDebouncedValue' | Keep a filter input responsive without a request per keystroke          |
| 'useMediaQuery'     | Responsive behaviour for the video and pitch views                      |

## What deliberately does not

- **A general-purpose data-fetching library.** TanStack Query or SWR will likely
  be the right answer once there is data to cache. Adding one now, with no
  queries to make, would be choosing a library by guesswork.
- **Anything that fetches on mount without an abort path.** Analysis polling can
  take minutes; a hook that cannot be cancelled leaks updates into unmounted
  components.

Empty in Phase 0: there is nothing to fetch yet.
