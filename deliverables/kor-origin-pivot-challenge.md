# Web 1: [Network/Web] Hidden Origin Pivot

## Background

The visible site sits behind a large edge protection layer. The public hostname alone is unlikely to tell the whole story.

Your task is to start from a single target and determine whether there is a publicly reachable non-edge hostname that can serve the target site's homepage content.

## Target

`https://kor.bizdirlib.com/`

## Rules

- Use only public, unauthenticated, read-only methods.
- Do not submit forms, change state, or access non-public content.
- Do not use browser automation.
- Do not rely on local DNS answers unless you have independently validated them.

## Goal

Find a publicly reachable hostname that can act as the transport endpoint for `kor.bizdirlib.com` and prove it by retrieving the target homepage content through that endpoint.

## Success Criteria

To pass, the solver must provide all of the following:

1. The final non-edge hostname they identified.
2. A short explanation of why that hostname is related to the target.
3. One reproducible command that retrieves `kor.bizdirlib.com` homepage content through that hostname.
4. One proof artifact from the returned page, such as:
   - the page title, or
   - the meta description, or
   - a short HTML excerpt that clearly belongs to `kor.bizdirlib.com`

## Expected Output Format

```text
HOSTNAME: <final-hostname>
WHY: <one to three sentences>
COMMAND: <single reproducible command>
PROOF: <title/meta/short excerpt>
```
