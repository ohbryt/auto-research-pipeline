# ARP Agent Program

**Project:** [PROJECT_NAME]

## Rules

### Execution
- Read ARP_PLAN.md for milestones and ARP_CHANGELOG.md for context before starting
- Work on one milestone at a time, in order
- Self-verify against the test oracle before marking complete
- If a milestone takes more than 3 attempts, log failure and move on or ask for help

### Git
- Commit after every meaningful unit of work
- Run tests before every commit — never commit broken code
- Use descriptive commit messages: `[ARP-M{N}] description`

### Memory
- Update ARP_CHANGELOG.md after every milestone
- Log ALL failed approaches with reasoning — this prevents loops
- Record metrics at every checkpoint

### Reviews
- Trigger cross-model review every [ARP_REVIEW_INTERVAL] milestones
- Before major architecture decisions, get review first
- If review score < 7, address ALL feedback before continuing
- Log review results in ARP_CHANGELOG.md

### Optimization
- Only optimize after core functionality is complete
- Each experiment: change one thing, measure, keep or discard
- Stop optimizing when 3 consecutive experiments show < 1% improvement
- Log every experiment result

### NEVER STOP
- Once execution begins, do NOT pause to ask if you should continue
- The human may be away — continue working indefinitely
- If stuck, try alternative approaches before giving up
- If truly blocked, document the blocker and move to next milestone
