# 💡 Implementation Tips for Your Pipeline

To get the most out of this Orchestrator prompt, structure your backend pipeline like this:

1. **The Loop**: Run your debate in a 'while' loop.

2. **The Router**: At the end of every turn, pass the updated transcript to the Orchestrator.

3. **Parsing**: Parse the Orchestrator's JSON response.

- If 'debate_status == CONCLUDE', break the loop and call the **Moderator** to write the final executive summary.
- If 'debate_status == DEADLOCK', break the loop or inject a **Mediator** to force a compromise.

4. **Dynamic Prompt Injection**: When you call the 'next_agent', dynamically append the Orchestrator's 'contextual_directive' and 'injection_context' to that agent's base prompt.

- *Example:* If the Orchestrator selects the **Fact Checker** and provides the directive "Verify the historical dates mentioned by the Strategist," your backend should append that specific instruction to the Fact Checker's system prompt for that single turn. This keeps agents highly focused and prevents them from rambling.

5. **Phase Management**: Use the 'phase_transition' key to update the global state of your application. You can use this to change the UI (e.g., changing the background color or displaying a "Phase 3: Stress-Testing" banner to human observers).
