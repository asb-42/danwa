Phase layout (horizontal flow from left to right):
                                                                                    ┌─────────┐
                                                                                    │ output  │
                                                                                    └─────────┘
                                                                                       ▲
                                                                                 conditional
                                                                              "consensus_reached"
                                                                                       ▲
                                                                                  ┌─────────┐
                                                                                  │  gate   │
                                                                                  └─────────┘
                                                                                       ▲
                                                                                  sequential
                                                                                       ▲
Phase 1               Phase 2               Phase 3               Phase 4               Phase 5
┌────────────────┐   ┌────────────────┐   ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
│ analyst        │   │ strategist     │   │ devils-advocate│   │ mediator       │   │ moderator      │
│ creative-thinker│  │ expert-reviewer│   │ fact-checker   │   │ ethicist       │   │ critic         │
│ socratic-quest.│   │ steel-manner   │   │ troll          │   │ synthesizer    │   │ optimizer      │
└────────────────┘   └────────────────┘   └────────────────┘   └────────────────┘   └────────────────┘
       ▲                    ▲                    ▲                    ▲                    ▲
       └──── sequential ────┴──── sequential ────┴──── sequential ────┴──── sequential ────┘
                                                                                        
┌─────────┐    ┌──────────┐    ▲
│ input   │───▶│  init    │────┘ (sequential)
└─────────┘    └──────────┘

Edges (preamble):
1. input-1 → init-1 (sequential)
Phase 1 → Phase 2 (edges from last P1 agent to first P2 agent):
2. init-1 → analyst-1 (sequential)
3. analyst-1 → creative-thinker-1 (sequential)
4. creative-thinker-1 → socratic-questioner-1 (sequential)
5. socratic-questioner-1 → strategist-2 (sequential) — Phase 1→2 transition
Phase 2 → Phase 3:
6. strategist-2 → expert-reviewer-2 (sequential)
7. expert-reviewer-2 → steel-manner-2 (sequential)
8. steel-manner-2 → devils-advocate-3 (sequential) — Phase 2→3 transition
Phase 3 → Phase 4:
9. devils-advocate-3 → fact-checker-3 (sequential)
10. fact-checker-3 → troll-3 (sequential)
11. troll-3 → mediator-4 (sequential) — Phase 3→4 transition
Phase 4 → Phase 5:
12. mediator-4 → ethicist-4 (sequential)
13. ethicist-4 → synthesizer-4 (sequential)
14. synthesizer-4 → moderator-5 (sequential) — Phase 4→5 transition
Phase 5 → Gate:
15. moderator-5 → critic-5 (sequential)
16. critic-5 → optimizer-5 (sequential)
17. optimizer-5 → gate-1 (sequential)
Gate decisions:
18. gate-1 → output-1 (conditional, condition: "consensus_reached")
19. gate-1 → init-1 (feedback, "next round") — loop back for more rounds
Feedback edges within phases (for round-based iteration within each phase):
20. socratic-questioner-1 → analyst-1 (feedback, "deepen analysis")
21. steel-manner-2 → strategist-2 (feedback, "refine position")
22. troll-3 → devils-advocate-3 (feedback, "strengthen challenge")
23. synthesizer-4 → mediator-4 (feedback, "re-integrate")
24. optimizer-5 → moderator-5 (feedback, "polish closure")
