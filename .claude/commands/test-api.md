Run only the API smoke tests against the running server.

Steps:
1. Verify the web server is running on port 8000. If not, warn the user and stop.
2. Run `npx playwright test tests/e2e/api-smoke.spec.ts` from the project root.
3. Report results: total passed, failed, and skipped.
4. If any tests fail, read the failure output and summarize what broke.
