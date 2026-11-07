# Repository guidance

## Personal proxy documentation privacy

- No generated or revised documentation may disclose personal proxy servers'
  real addresses, domains, providers, locations, access ports, SSH aliases,
  account identifiers, subscription URLs, credentials, deployment paths, quotas,
  or billing cycles.
- Use generic roles and explicit placeholders. Keep actual deployment values in
  access-controlled private configuration, outside published documentation.
- Apply the same rule to screenshots, examples, reports, and commit messages.
  Do not copy private configuration, environment files, or diagnostic snapshots
  into tracked artifacts.
- Preserve working routing and subscription behavior when editing documentation;
  never replace operational values with placeholders in live configuration.

## Agent commit attribution

- Commits created or amended by an AI agent carry that agent's own co-author
  trailer exactly once, while retaining the user's Git author and committer
  identity:
  - Codex: `Co-authored-by: Codex <noreply@openai.com>`
  - Claude Code: its default Claude co-author trailer
- DeepSeek commits and commits created or amended by people carry no agent
  trailer.
- Never attribute one agent's commit to another agent.
- Separate the trailer block from the message body with a blank line, and
  preserve existing co-author trailers.
