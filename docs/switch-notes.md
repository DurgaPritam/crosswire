# Switch notes (from Switch's own source and docs)

These were found by reading `sandbox-quantum/switch` (docs/official, core, console). Confirm anything critical in Phase 0.

## Facts the design relies on
- **Addressing policies are enforced on the server.** Each rule scopes rooms, room groups, users and agents. The symbolic subjects are `owner` and `owner_agents`. An agent can't widen its own policy; only the owner or an admin can, in Gateway. A refused message gets one visible reply from the agent.
- **Agents inherit their owner's permissions.** An agent is not a principal of its own.
- **Room documents:** `create_room_document(name, description, instructions, content)` creates a document visible to everyone in the room. Only the creating agent can `update_room_document` or `delete_room_document` it (enforced). Others read it with `load_internal_documents`. Humans can delete it in the UI. Max 1 MiB.
- **`post_message(body, thread_id=None)`** posts only to the session's connected room (no `room_id` parameter). `connect_to_room(room_id)` switches the session's active room. `send_targeted_message` supports `target_names` and `target_roles`.
- **Roles:** shared or exclusive (an exclusive role is a lease released a few seconds after the session stops). One role per agent at a time, across all rooms. `!roles` lists them.
- **Context stops at the room.** Two sessions of the same agent share nothing. Anything that must travel goes in a document or the agent's own working directory.
- **Working directory** decides where the agent starts, but it is **not** a boundary: in spike S1, Console's default auto mode let the agent read a sibling folder with no prompt. Enforce isolation with deny rules and the `path_guard` hook. Keep bypass permissions off.
- **Console runs Claude Code through the Agent SDK** with project and user settings loaded, and registers Switch operations as MCP tools (names like `mcp__switch__post_message`). Hooks in the project's `.claude/settings.json` should therefore apply. **VERIFY in spike S3.**
- **Templates:** room YAML with typed `params` (`string`, `number`, `boolean`, `enum`, `agent`, `bridge`, `room`, `user`), builtins `{$creator}`, `{$date}`, `{$timestamp}`, and a top-level `kickoff` message. See `../switch/examples/room-templates/red-blue-workroom.template.yaml`.
- **Tasks are not usable:** the task operations exist, but the docs say "present but not ready for use".

## Operation catalog (agent side)
Rooms: list_rooms, get_room_detail, connect_to_room, create_room, update_room, list_participants, invite_agent_to_room, add_users_to_room · Messaging: post_message, send_targeted_message, read_context · Resources: list_references, create_reference, attach_reference_to_room, load_internal_documents, create_room_document, update_room_document, delete_room_document · Roles: list_roles, define_role, assume_role, release_role · Links/groups: list_linked_rooms, link_rooms, unlink_rooms, create_room_group · Templates: create_room_from_yaml, get_template_guide, list_templates, run_template, save_template

## Gotchas (from Switch's docs and from our own setup)

| Gotcha | What to do |
|---|---|
| Switch task operations are "present but not ready for use" | Use room documents for records and action items |
| Only the agent that created a room document can update or delete it | That's the point: the Mediator owns the record. Humans can still delete it in the UI. |
| An unlinked chat account matches nobody in addressing rules | Link every Mattermost account to its Switch user |
| New agents start owner-only; adding the first rule closes everything else | Write the full policy table (7.3) in one go |
| `post_message` posts only to the session's connected room | Plan A uses `connect_to_room`; Plan B uses threads in the shared room |
| Two sessions of the same agent share nothing; context stops at the room | Anything that must travel goes in a document or the agent's own directory |
| An agent can hold one role at a time, across all rooms | Don't give an agent roles in two rooms |
| Bridge base URL ≠ Gateway URL | Probe `GET /health` on the bridge for the Notary |
| Mattermost renders Markdown tables, Slack doesn't | Tables are fine for the demo; note it if you connect Slack |
| Bypass permissions disables every check | Keep it off for all agents |
| **Auto mode (on by default) approved an out-of-directory read with no prompt** (spike S1) | Enforce isolation with deny rules plus the `path_guard` hook; prove it with S1b/S1c |
| Mattermost image has no arm64 build: `no matching manifest for linux/arm64` | `docker pull --platform linux/amd64 mattermost/mattermost-team-edition:11.9.0`, Rosetta on in Docker Desktop |
| `docker-credential-desktop: executable file not found in $PATH` when Console pulls | Pre-pull the images in Terminal; if it persists, remove `"credsStore"` from `~/.docker/config.json` (back it up first) |
| The Mattermost on/off switch isn't in Settings | It's in **Admin → Status** (Console v0.40.1) |
| Mattermost's port can change after a server restart | Re-check **Home → Mattermost → ⋮ → Sign-in details…** and update `MM_URL` |
| Env vars exported in one terminal don't reach Claude Code in the VS Code extension | Keep the Mattermost login in the gitignored `.env` (mode 600); scripts load it |
| Deny rules are checked **before** hooks for file tools | A deny-rule refusal leaves `path.log` empty; count it as a pass. path_guard is the boundary for Bash. |
| On one machine, all agents run as one OS user | Deny process inspection in every agent; per-company containers for a hard fix |
| A **refused** targeted message is still posted visibly in the room | The disclosure guard must check `send_targeted_message` regardless of addressing |
| Console runs agents with `--permission-mode auto` on its own Claude Code (v2.1.299 at the time of writing) | Don't rely on settings that need a newer version |
| Restarting an agent session = stopping its `claude` process | `scripts/restart-agent.sh <workspace-dir>`; Console starts a fresh session on the next mention |
| "Only me" also refuses the owner's *other* agents (confirmed in S2) | Phase 7.3 can rely on it |

