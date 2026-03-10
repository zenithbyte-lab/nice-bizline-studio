# Web 2: [Crypto/Network] The TLS Masquerade

## Background

The target site does not rely on ordinary front-end tricks. Its main gate is at the network protocol layer.

Your task is to interact with the site using code-only HTTP clients and determine how to retrieve the real success page content.

## Target

`https://nowsecure.nl/`

## Rules

- Do not use any browser automation or browser engine tooling.
- Do not use Puppeteer, Playwright, Selenium, or visible browsers.
- Use only code-level HTTP clients and terminal tooling.
- Keep the interaction read-only.

## Goal

Retrieve the target page in a way that causes the response body to contain the exact string:

`You passed the Cloudflare Challenge`

## Success Criteria

To pass, the solver must provide all of the following:

1. One reproducible command or script invocation.
2. Terminal output showing the exact target string.
3. A short explanation of why their approach works.

## Expected Output Format

```text
COMMAND: <single command or script invocation>
WHY: <one to three sentences>
PROOF:
You passed the Cloudflare Challenge
```

## Notes for the Solver

- The result must come from the target site's returned body, not from hardcoded output.
- The solver should assume that a plain request path is not sufficient.
