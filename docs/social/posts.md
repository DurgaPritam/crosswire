# #HowISwitch posts (drafts)

Card image: `docs/social/social-howiswitch.png` (1200×675). Replace `<repo>` and `<video>` once they're public.

## LinkedIn

Two companies' AI agents fixed a bug together, and neither company shared a line of code.

Crosswire is our Flip the Switch hackathon project. PayCo sends signed webhooks, and ShopCo rejects some of them, but
only for customers with accented names. Each company has a Claude Code agent that can see its own repo and logs, and
nothing else.

The agents meet in a shared Switch room:
- Switch's server-enforced addressing refuses direct agent-to-agent requests across the company line, so everything
  goes through a neutral mediator agent.
- Each side shares only salted byte fingerprints, and a person on that side approves each one before it leaves.
- A deterministic notary agent compares them: data.customer.name, +4 bytes. PayCo escaped é as é and ShopCo
  re-serialized it to raw UTF-8 before verifying.

Root cause in about 7 minutes. 0 lines of code shared, 0 customer names posted.

The repo (with a replay you can run without Switch) and the 3-minute demo:
<repo> · <video>

#HowISwitch #FlipTheSwitch #ClaudeCode #AIagents

## X (≤280 characters)

Two companies' AI agents fixed a webhook bug together. 0 lines of code shared.

Switch refused their direct messages; a mediator ran the incident; humans approved every fingerprint; a notary found
+4 bytes in data.customer.name.

<repo> #HowISwitch

*(Character count with a 23-character link: about 250.)*

## Alt text for the card

Crosswire social card. The Crosswire logo, a coral and teal X, sits above the tagline "Debug integrations across
company lines without sharing code." Below it, coral message cards on the left and teal message cards on the right
face each other across a glowing vertical line. A single chip on the line reads "fingerprint only". A "#HowISwitch"
tag is in the top left corner.
