Perform a visual verification of the dashboard layout using browser automation (claude-in-chrome MCP).

Steps:
1. Open http://localhost:8000 in a new browser tab at 1920x1080 resolution.
2. Verify the 2x2 grid layout on the left side:
   - Top-Left: Control Panel (voice channel, mode buttons, documents)
   - Top-Right: Ask ChatGPT (input textarea, send button, response area)
   - Bottom-Left: Configuration (providers, session spend)
   - Bottom-Right: Context Summary (generate, export)
3. Verify the 2-column layout on the right side:
   - Left column: Live Conversation (transcript container)
   - Right column: AI Insights (observer controls)
4. Check that no panels overlap or are cut off.
5. Verify all interactive elements are clickable and not hidden.
6. Take a screenshot and report findings.
7. Close the tab when done.
