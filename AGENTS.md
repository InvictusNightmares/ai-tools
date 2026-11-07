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

## Codex commit attribution

- Only commits created or amended by Codex carry an agent co-author trailer.
  For those commits, retain the user's Git author and committer identity and
  include this trailer exactly once in the commit message:

  ```text
  Co-authored-by: Codex <noreply@openai.com>
  ```

- Do not add an agent trailer to commits created or amended by DeepSeek,
  Claude Code, other agents, or people.
- Separate the trailer block from the message body with a blank line, and
  preserve existing co-author trailers.
