# Hermes Conduit Notifier

Hermes Conduit Notifier is the open-source Hermes plugin that connects a Hermes host to the [Hermes Conduit](https://github.com/kaishi00/hermes-conduit) iPhone, iPad and Apple Watch app. It started as the notification sender and now carries most of what Conduit needs from the host:

- **Notifications and calls**: approval, input, reply, failure and background-task notifications, Hermes calling you (CallKit on the phone and Watch), and Lock Screen progress while a turn runs, all delivered through the Conduit push relay, end-to-end encrypted where APNs allows.
- **Phone data the user opts into**: Apple Health, location, maps, calendar, reminders, Focus, phone status, contacts and alarms, sent by the phone straight to this host and sealed end to end, with the `conduit_health`, `conduit_location`, `conduit_maps`, `conduit_calendar`, `conduit_phone` and `conduit_contacts` tools for the agent.
- **Conduit extras**: rich cards and on-screen cards during calls, Artifacts, group pictures, chat takeover, cron notification settings, Conduit settings the agent can change, and one-tap pairing and updates from the app.

Every route sits behind the Hermes dashboard's own auth. The plugin holds no Apple Push Notification service key and no dashboard credentials: Apple credentials stay on the push relay, so self-hosted users never need to copy a shared signing key onto their gateway, and provider keys and sign-ins never leave this host. What each party can see is in the [privacy policy](https://kaishi00.github.io/hermes-conduit-notifier/privacy/).

## Install

Run these commands on the machine where Hermes is installed:

```bash
hermes plugins install kaishi00/hermes-conduit-notifier --enable
hermes gateway restart
```

In Hermes Conduit, open **Settings > Notifications**, enable notifications, and create a pairing code. Claim it from the matching Hermes profile:

```bash
hermes conduit-push pair XXXXX-XXXXX
```

Pair additional profiles independently:

```bash
hermes -p coder plugins enable conduit_push
hermes -p coder conduit-push pair YYYYY-YYYYY
```

Pairing codes expire after ten minutes and can only be claimed once.

With plugin 0.24+ Conduit pairs the active dashboard's profile by itself: it
creates the code and hands it to `POST /api/plugins/conduit_push/pair?profile=`
over your signed-in dashboard connection (see [Pairing from Conduit](#pairing-from-conduit-plugin-024)).

## Manage the pairing

```bash
# Show status without printing the credential
hermes conduit-push status

# Send a local test event through the relay
hermes conduit-push test

# Redact chat text from pushes (see Privacy and security)
hermes conduit-push redact on

# Revoke this profile's credential
hermes conduit-push unpair
```

Update the plugin and restart Hermes:

```bash
hermes plugins update conduit_push
hermes gateway restart
```

The dashboard imports the plugin's routes once, so restart the dashboard as
well (or let Conduit do it: Settings > Conduit plugin > Update runs Hermes' own
plugin update, the gateway restart and [the dashboard restart](#updating-from-conduit-plugin-024)).

## Events

The plugin currently emits notifications for:

- approval needed
- clarification or other input needed
- response ready, once the turn has ended: a turn that failed sends only its failure notice, not Hermes' error text as a reply (plugin 0.35+)
- failed turns
- completed background tasks: a delegated task that ends while the turn that started it is still running is part of that turn's reply and sends nothing of its own (plugin 0.35+)
- calendar and reminder changes Hermes asks your phone to make (see [Calendar, Reminders, Focus and phone status](#calendar-reminders-focus-and-phone-status-from-conduit-plugin-027)): a notification to approve, or a silent wake for adds you let Hermes make without asking
- call requests: a job you asked to be called about has ended, Hermes asked to call you, or (alert calls) Hermes has waited a minute on your approval or answer, or a turn failed (see [Hermes calls you](#hermes-calls-you-plugin-013))

An exact `[Silent]` assistant response does not emit a completion notification. Reply and task bodies are sent as plain text: Markdown fences, emphasis, headings, link targets and table rules are dropped (plugin 0.35+).

### Cron runs (plugin 0.33+)

A cron run notifies like any other turn, with two exceptions:

- A run whose reply is Hermes' cron silence marker doesn't notify, by the same rule Hermes uses to skip delivering it: `[SILENT]` (or `SILENT` / `NO_REPLY`) as the whole reply, on its own first or last line, or opening the reply (`[SILENT] No changes since yesterday`). A marker mid-sentence is real content and still notifies.
- You can turn a job's notifications off in Conduit's Cron tab. Its runs then send no reply or failure notification (and no automatic alert call; a call you asked for on the job still rings). The muted job ids live in the profile's `conduit-cron.json`; `GET /api/plugins/conduit_push/cron/notifications` lists them (`{"ok": true, "muted": [...]}`) and `PUT` with `{"job_id": "...", "notify": false}` changes one. Capability `cron-notifications`.

The plugin tells a cron run by its task id (`cron:<job id>:…`) or its classic session id (`cron_<job id>_<date>_<time>`).

Beside notifications, the plugin keeps a Live Activity up to date while a turn you sent from Conduit runs (see [Lock Screen progress](#lock-screen-progress-plugin-032)).

Each notification is titled with the session's title when it has one (for example a Telegram topic name), so you can tell which chat it came from: a reply shows the session title, and the others prefix it (`Approval needed · Infra`). A Conduit Bot Chat, whose title is always `Bot Chat`, is titled with its bot's profile name instead, so you can tell which bot replied. Untitled sessions keep the generic copy. With previews off the title is not shown; `redact on` or end-to-end encryption keeps it from reaching the relay.

The iOS app controls which categories are enabled, whether notification previews are shown, whether completion sounds play, and whether approval and input-needed notifications play a sound (on by default).

## Privacy and security

- Pairing creates a revocable, profile-scoped credential.
- The credential is stored in the profile-aware Hermes home as `conduit-push.json` with mode `0600` on supported systems.
- Authorization credentials are never written to logs or printed by `status`.
- Hook callbacks enqueue bounded events; HTTPS delivery runs on a background worker and does not block the agent loop.
- A delivery that fails on the way (no connection, a timeout, `408`, `429` or a `5xx` from the relay) is sent again with the same event ID after 1, 2 and 4 seconds, for at most about 30 seconds per event; the relay drops the repeats it already accepted. Other refusals are not retried. A `401` means the relay no longer knows this gateway (Conduit removed it, or the relay lost its data): the pairing is kept, and `status` says to pair again from Conduit until a delivery is accepted again. A `401` or `403` also parks notifications for that pairing (plugin 0.55.1+): events are dropped for 1 minute, doubling with each refusal in a row up to 30 minutes, then the next event goes out as the probe and an accepted one (or an accepted `test`) ends the pause; a clarify question asked meanwhile uses the native prompt at once (Live Activity reports pause 30 minutes on their own). A `403` with no JSON body comes from something in front of the relay (a firewall or rate limiter) blocking this host's address: `status` says so instead of telling you to pair again, since a pairing claim meets the same block, and Conduit's pairing status reports it as `relay_blocked`.
- Disabling or reloading the plugin (on a Hermes with plugin unload callbacks) stops its background work: notifications still queued and replies waiting for their turn's end are dropped, the delivery and Lock Screen threads end, and a call held until your call ends is kept for the next load instead of going out.
- The health, location, maps, calendar, phone, contacts, calls and display tools refuse delegated subagents, including one whose session id a compaction replaced (`compression.in_place: false`): the plugin asks Hermes' delegation flag (Hermes 0.22+) and follows the compaction links in Hermes' session store back to the subagent it was (plugin 0.51.6+).
- Event titles and bodies are length-limited before delivery.
- Lock Screen previews are disabled by default in Hermes Conduit.
- **End-to-end encryption** (plugin 0.5+, relay 0.5+, a Conduit build with encrypted notifications): Conduit creates a secret for each pairing on the phone and hands it to this profile over your Hermes dashboard connection, so it never passes through the relay. From then on every notification's title, body, profile, session and decision card is sealed with it (ChaCha20-Poly1305, keys derived with HKDF-SHA256), the phone decrypts it in a Notification Service Extension, and clarify answers come back sealed for this profile. The relay and APNs see only routing data: the event type, opaque ids, a keyed thread token and timing. A pairing that has a key never sends plaintext content again, and only accepts clarify answers sealed by the phone. `hermes conduit-push status` shows whether it's on; Conduit turns it on by itself when it connects to this host. Run `hermes conduit-push test --corrupt` to check that the phone shows only generic text for a push it can't verify. The secret is only as private in transit as your dashboard connection (HTTPS or a private tunnel is recommended).
- `hermes conduit-push redact on` keeps chat content from leaving the gateway: events carry no title or body text, approval cards say "Hermes needs your approval. Open Conduit for details.", and clarify cards replace question text with generic copy. The fields needed to answer stay (session key or request id, question ids, choice labels), so cards raised while the app is backgrounded remain recoverable and answerable. Clarify choice labels still transit the relay because the answer is one of them. `status` shows the current setting; `redact off` restores full content, including for events still waiting in the local delivery queue.

- Besides notifications, the relay carries call pushes (sealed like notifications, except the "stopped ringing" notice), Lock Screen progress (phase, a tool category from a fixed list, tool count and context percentage, never chat text; `redact on` drops the category) and the one-time codes that prove a phone holds its APNs token. Health, location, calendar, phone and contacts data never pass through it.

The public relay URL is part of the client protocol. APNs signing material (the `.p8` key) is never committed.

## Push relay

The push relay is the server component that receives events from Hermes gateways and delivers them to iOS devices via APNs.

**Architecture:** Hermes plugin → HTTPS → relay → APNs → Conduit app

The relay handles device registration, pairing codes, per-installation preferences, rate limiting, and idempotent event delivery. It uses only the Node.js standard library (no npm dependencies).

## Lock Screen progress (plugin 0.32+)

When you send a message from Conduit, it starts a Live Activity on the Lock
Screen and in the Dynamic Island: what Hermes is doing (thinking, running a
kind of tool, waiting for your approval or answer), how long the turn has run,
how many tools it used and how full its context is. Conduit updates it itself
while it is open; once you leave it, the plugin keeps it current through the
relay (relay 0.15+), and the end of the turn ends it.

- The phone registers the activity's push token with the relay under the
  chat's session ids. The plugin reports each turn it runs: phase changes,
  tool starts, approvals and clarify questions, and each model request's
  context use (`pre_api_request` / `post_api_request`, which older Hermes
  versions may not have; the rest still works without them).
- Reports are coalesced: at most one every 5 seconds per watched turn, the end
  at once. The relay answers whether the phone is watching; a turn nobody
  watches is asked about again only every 15 seconds, and a relay without the
  route turns reporting off for half an hour.
- Live Activity payloads are rendered by iOS itself, so they can't be sealed
  end to end like notifications. What reaches the relay and APNs is coarse on
  purpose: the session id, a phase, a tool category from a fixed list
  (`terminal`, `files`, `web`, `browser`, `connector`…, never a tool's name,
  arguments or output), a tool count and a context percentage. The chat's
  title stays on the phone. With `redact on` the tool category is left out
  too.
- The relay keeps registrations in memory only (at most 8 hours, the longest
  iOS runs an activity). A relay restart stops updates; the activity then
  shows as out of date on the phone and Conduit ends it when you open it.

## Batch clarify decisions (plugin 0.3+)

Current Hermes lets one `clarify` call ask several questions
(`questions: [{qid, question, choices, multi_select}]`). The plugin relays
the FULL batch to Conduit instead of collapsing it to the first question:

- The pushed decision carries `questions[]` with the gateway qids, choices,
  and `multi_select` flags. The old collapsed `question`/`choices` summary
  still rides along, so pre-0.3 Conduit builds keep rendering an answerable
  first-question card.
- The relay stores per-question answers with **first-answer-wins per qid**:
  two devices answering the same qid resolve to one lock (the loser gets a
  409), and the decision completes only when every qid is locked.
- Devices answer per question with
  `POST /v1/decisions/:id/respond {"question_id": "q…", "answer": "…"}`
  and receive the remaining open qids back (`POST /v1/decisions/:id` is
  kept as a backward-compatible alias running the same handler). The
  legacy whole-decision body (`{"answer": "…"}`) still works for
  single-question cards, and on a batch it counts as the collapsed first
  question only.
- Duplicate qid answers and released decisions are distinct outcomes:
  `409 already_answered` settles only that qid as answered elsewhere,
  while `410 decision_released` (the native Desktop/TUI path resolved the
  whole clarify) tells Conduit to retire the entire pushed card. An
  unknown qid on a live decision is `400 invalid_question_id`, not a
  missing decision.
- An answer is kept whole or refused, never cut: plaintext is trimmed and
  may be up to 2,000 characters, a sealed answer (`e2e1.…`, encrypted
  pairings) up to 11,000. A longer one is `413 answer_too_large` and the
  question stays open; a sealed answer too short to hold its tag is
  `400 invalid_answer`.
- The structured decision and the notification are independent: when the
  card cannot be delivered (decision_cards disabled, or an oversized batch
  stripped by the APNs size guard, or APNs rejecting the send), the
  ordinary input.needed banner is still delivered and the parked decision
  is marked `deliverable=false`, so the plugin immediately falls back to
  Hermes' native clarify path.
- Bounds: the plugin and relay accept at most 8 questions × 8 choices per
  batch (validation mirrored on both sides). That is the protocol/store
  ceiling, NOT a guarantee that every valid batch fits an answerable card:
  answerable-card capacity is bounded by Apple's ~4 KB APNs payload limit,
  and therefore by the actual byte size of the question and choice text. A
  valid batch whose serialized decision exceeds the payload budget is
  never truncated or split — Hermes is still waiting on every qid, so a
  partial card would collect answers for a batch that can never complete —
  instead the WHOLE structured decision is dropped from the push (plain
  input.needed banner, decision parked `deliverable=false`) and the plugin
  falls back to Hermes' native clarify path.
- The plugin returns the batch to Hermes exactly in the built-in tool's
  result shape (`{"responses": [...]}`, multi-select answers parsed back to
  lists). Protocol provenance comes from the original invocation: a
  one-entry `questions[]` call is batch protocol even though it has a
  single question, while legacy scalar calls keep the scalar result shape.
- Releasing a decision (native path won) is fired off the answer's critical
  path on a daemon thread, so a slow or unreachable relay can never delay
  the user's native answer.

Known limitation: the relay cannot see answers made natively (Hermes
Desktop/TUI answer through the gateway), and the gateway cannot see relay
answers. Whichever surface completes the WHOLE batch first wins the tool
call; the plugin then releases the parked decision (`DELETE
/v1/decisions/:id`) so late device answers are rejected rather than
reported as accepted. A batch answered partly natively and partly by relay
stays open until the gateway's configured clarify timeout bounds it.

### Decision retention limits

The relay allows up to 32 active unresolved decisions per installation and
1,024 across the relay (`RELAY_MAX_ACTIVE_DECISIONS`). A scalar decision is active until answered or cancelled;
a batch remains active until every question is answered or the decision is
cancelled. Completed and cancelled decisions preserve their answers and locks
for the two-hour decision TTL, within separate retained-record caps of 128 per
installation and 4,096 across the relay (`RELAY_MAX_RETAINED_DECISIONS`).
Active decisions count toward both retained caps. Since settled records stay
for two hours, those retained caps also impose a maximum admission throughput
of 64 records per installation per hour and 2,048 records per hour across the
relay, averaged over a full retention window. Decisions are stored in the data
file and a full batch record can reach about 13 KB, so the relay-wide caps
also bound how large a flood can make that file.

When any limit is full, a new clarify event receives HTTP `429`
`decision_capacity_exceeded`. The relay sends no push and does not consume the
event ID. The shipped plugin sends a `429` again a few times within about 30
seconds (the same event ID, like any other transient failure), then logs the
rejection and gives up; a caller may explicitly retry the same event ID
after capacity becomes available and before the event is accepted. Hermes'
native clarify path remains available, and existing decisions remain
answerable, pollable, and cancellable.

The global limits apply across every installation. Because installation
self-registration is open to anyone with a phone running the app, one actor
can create multiple installations,
occupy the global active and retained pools, and keep refreshing them as
records expire, denying new relay clarifies indefinitely. The relay cannot
identify a shared actor or enforce fairness from installation IDs alone.
Existing answers and Hermes' native clarify path remain available during
saturation; the global caps are a bounded storage tradeoff, not a tenant
fairness boundary.

## Chat takeover

Hermes lets one app own a chat at a time. Hermes Desktop claims a chat on its
first turn and keeps the claim until the chat is closed there, so sending to
the same chat from Conduit is refused with "This chat is open in another Hermes
window/terminal". This route is what Conduit's **Take over** does: it drops the
other app's claim in `runtime/active_sessions.json`, under Hermes' own registry
lock, and Conduit's next send claims the chat.

| Method | Route | Returns |
| --- | --- | --- |
| POST | `/api/plugins/conduit_push/sessions/takeover` with `{session_ids: [..]}` | `{ok, status, surface?}` |

- `status` is `taken_over` (send again), `free` (nobody else holds it),
  `busy` (the other app is running a turn on it, or it's a live worker or
  gateway whose turns can't be seen; ask again shortly, nothing
  is interrupted; a marker that can't be read counts as running, and only a marker whose writer is provably dead, or a gone owner's marker that names no writer, is ignored) or
  `same_host` (this dashboard process still holds it, for example Conduit on
  another device; that claim is left alone).
- The other app writes its turn marker without the registry lock, so a turn
  it starts in the instant between the check and the takeover still loses
  its claim. That turn keeps running there; nothing is interrupted.
- Only Desktop and TUI claims are dropped while their owner is alive: they are
  the surfaces that write turn markers. A live claim from a CLI or kanban
  worker, a gateway, or with no surface answers `busy`, since a running turn there can't be
  seen. A claim whose owner process is gone is dropped whatever its surface,
  as long as no live claim of that kind also holds the chat.
- Only another process's claim is dropped; a claim without a valid pid is
  kept, since it can't be attributed. The other app isn't told: if you
  go back and send from Hermes Desktop, it still believes it owns the chat
  and doesn't see what you sent from Conduit until you reopen the chat there.
- `session_ids` takes 1 to 4 ids of one chat (its stored id and its live id),
  never ids of different chats.
  400 for a bad body, 501 on a Hermes without the ownership registry or turn markers, 503
  when the registry can't be read (ownership is never guessed), 429 past 60
  requests a minute, 504 if the takeover doesn't finish within 20 seconds (ask again: nothing is written after that, short of a write already under way).

The other way round (plugin 0.58.1+): a chat Conduit opened in the dashboard
holds its claim for as long as Conduit stays connected, which used to refuse
the same chat in Hermes Desktop's own process long after Conduit's turn ended.
The dashboard now lets go of Conduit's claim once the chat has been idle for a
minute: no turn running, nothing waiting on an answer, no delegated work, wake-up
or background process still to report, and no turn marker. The chat stays open
in Conduit, and its next send claims it again, or meets the usual refusal and
**Take over** if Desktop took it meanwhile. Only chats whose every client here
is Conduit count; a chat Desktop or the web dashboard also has open in this
process, and Bot Chats, keep their claim.

## Chats opened on Desktop (plugin 0.12+)

Conduit's Unread filter can count a chat as read when you have it open in
Hermes Desktop or the web dashboard on the same host. Hermes has no hook for
a client opening a chat, so the plugin wraps the gateway's `session.activate`
and `session.resume` handlers in the dashboard process. Per chat it keeps the
newest open (`opened_at`) and how long that chat then stayed the one its
Desktop connection had selected (`seen_through`), in
`<hermes home>/conduit-desktop-views.json` (at most 2,000 chats). It never
writes Hermes' own read flag, so Desktop's unread dots don't change.

| Method | Route | Returns |
| --- | --- | --- |
| GET | `/api/plugins/conduit_push/sessions/desktop-views?profile=&since=` | `{ok, observing, reason, views: {stored id: {opened_at, seen_through, client, open?}}}` |

- An open counts when it comes over the gateway's WebSocket from a browser
  engine (Desktop's renderer or the web dashboard: a `Mozilla/` User-Agent);
  `client` is `desktop` when it also says `Electron/`, else `browser`.
  Conduit's own socket, the TUI and hosted rooms never count. The
  User-Agent is the client's own claim, so this is best-effort sorting
  among clients that already hold a dashboard login.
- A connection's selection moves with its next open and ends when its socket
  closes (noticed within 5 seconds). `open: true` marks a chat that is
  selected right now; its `seen_through` is the moment of the read. The host
  can't tell whether anyone is looking at the window, and Desktop also
  re-attaches chats after a reconnect.
- `observing` is false, with a `reason`, while the gateway hasn't loaded
  (`gateway-not-in-process`, also what `plugins.isolation: host` reports) or
  when a Hermes update moved those handlers or the socket's headers
  (`gateway-unsupported`). The
  wrapper never fails a call and always returns Hermes' own response.
- `since` returns only chats seen after that time (seconds since the epoch);
  a value that isn't a finite number returns every chat. 429 past 60 reads a
  minute per profile.
- An open is skipped when the gateway can't say which profile its chat
  belongs to, rather than guessed onto the default profile.

## Quiet while you read in Desktop (plugin 0.20+)

A reply that comes back within 2 minutes in a chat Hermes Desktop (or the
web dashboard) has selected on this host sends no "response ready" push:
you most likely watched it arrive there. A longer turn still pushes, since
you have likely walked away, and every other notification stays as it was:
other chats, background jobs, approvals, questions, failed turns and calls.
There is nothing to set up.

- The selection is the one [Chats opened on Desktop](#chats-opened-on-desktop-plugin-012)
  follows: each Desktop connection's selected chat, ended when it switches
  chats or its socket closes. The host can't see whether the window is in
  front, so a short reply in a chat left selected on an unattended Mac stays
  quiet on the phone (Desktop's own notification still shows on the Mac
  when its window is in the background).
- The dashboard publishes the selected stored chat ids, per Hermes home, in
  `<hermes home>/conduit-desktop-selected.json` (private to the user) when
  they change, and renews the file every 30 seconds while anything is
  selected. The turn hooks trust it for 45 seconds, so a stopped dashboard
  stops quieting anything.
- A turn's 2 minutes run from its `pre_llm_call` to its `post_llm_call`. A
  turn with no start time, a file that can't be read, or `plugins.isolation:
  host` (where Desktop views aren't observed) all push as before.

## Quiet while you read in Conduit (plugin 0.60+)

A reply that lands in a chat you have open in Conduit sends no "response
ready" push, on whichever device you have it open: chatting on a Mac or an
iPad no longer buzzes the paired iPhone and the Apple Watch for each answer
you just watched arrive. Conduit knows when it is in front, so a long turn
stays quiet as long as you keep using Conduit; one left running with nobody
touching or typing for 2 minutes pushes, like Desktop's rule. Every other
notification stays as it was: other chats, background jobs, approvals,
questions, failed turns and calls. There is nothing to set up.

- While a turn runs in the open chat, with Conduit's window active and the
  chat not covered by the list, Conduit holds the chat as on screen with
  `PUT /api/plugins/conduit_push/notifications/on-screen?profile=…` and
  `{"device": "mac", "session_ids": ["<runtime id>", "<stored id>"],
  "hold_s": 90}`, renewing it every 30 seconds while the turn runs and
  someone used Conduit in the last 2 minutes, and sending `"hold_s": 0` once
  nobody has. Low Power Mode and Low Data Mode stretch the renewal like
  Conduit's other polls, and the hold stays three renewals long. Nothing is
  sent while no turn runs.
- After the turn ends the last hold runs out on its own, so the reply's own
  hooks still see it. Leaving the chat or the app sends `"hold_s": 0`, and
  the next reply there pushes as before.
- Each device kind (`iphone`, `ipad`, `mac`, `vision`, `watch`) keeps its own
  file in `<hermes home>/conduit-on-screen/` (private to the user), so one
  device leaving never ends another's hold (two devices of the same kind
  share a file, and the later report wins). A turn longer than 30 minutes
  pushes whatever Conduit says. A hold longer than 10 minutes, a
  file that can't be read, or a turn whose hooks don't share the profile's
  home with the dashboard pushes as before. Capability `chat-on-screen`.

## Reply notifications by source (plugin 0.35+)

If you also talk to Hermes in Desktop, a messaging app or the terminal, you
already see those replies there. In Conduit's Settings > Notifications you
choose, per profile, which sources send a "response ready" push: Conduit,
Hermes Desktop and the web dashboard, messaging apps (Telegram, Discord,
Slack, plugin platforms…), and the terminal. Everything is on until you turn
it off. Approvals, questions, failed turns, background tasks, cron runs (they
have their own switch) and calls don't follow this.

- The source is where the message that started the reply's turn was sent,
  not where the chat began: a Telegram chat you continue in Conduit is a
  Conduit reply. Hermes binds each turn to the connection that submitted
  last before it started, so a message queued meanwhile belongs to the
  next turn, not to the reply already running.
- Conduit's socket carries `X-Conduit-Client` (Watch jobs count as Conduit);
  another browser-engine socket is Desktop or the web dashboard. A turn
  with no app connection is placed by its Hermes platform: `cli` is the
  terminal, a Hermes messaging platform is a messaging app.
- A turn that can't be placed (an app connection run under `plugins.isolation:
  host`, the stdio TUI, a Hermes that moved these) pushes as before.
- The choice lives in the profile's `conduit-notifications.json`.
  `GET /api/plugins/conduit_push/notifications/reply-sources` reads it
  (`{"ok": true, "sources": {"conduit": true, "desktop": false, …}}`) and
  `PUT` with `{"source": "desktop", "notify": false}` changes one.
  Capability `reply-sources`.

## Files in group chats (plugin 0.38+)

A group chat room isn't a session, so Hermes' attach RPCs can't take a file
for it. Conduit uploads photos and files picked in a room's composer with
`POST /api/plugins/conduit_push/room-files` (`{"name": "photo.jpg",
"data_base64": "…"}`, up to 50 MB) and puts the `@file:` reference it gets
back (`{"ok": true, "path": "…", "ref_text": "@file:…"}`) on its own line
above the message, as Hermes Desktop does for a chat. The room's members run
on this host and read the file from there. Uploads go to
`<hermes home>/conduit/room-files/<id>/` and are deleted a month later, or
sooner, oldest first, once they pass 2 GB together (checked hourly). An
upload that would leave under 1 GB free on the host is refused (507).
Capability `room-files`.

## Group pictures (plugin 0.41+)

Hermes' gateway-hosted group rooms carry no picture, so Conduit keeps a
room's custom picture here. `GET /api/plugins/conduit_push/room-images`
returns each room's revision (`{"ok": true, "revisions": {"<room id>":
"<rev>"}}`), so Conduit fetches only pictures it hasn't cached with
`GET /room-images/<room id>` (`{"rev": "…", "mime": "image/jpeg",
"data_base64": "…"}`). `PUT /room-images/<room id>` with `{"data_base64":
"…"}` sets a JPEG or PNG of up to 512 KB; `DELETE` clears it. Records live in
`<hermes home>/conduit/room-images/` (a small record plus the picture per
room, so listing never reads picture bytes), up to 500 rooms (the
oldest go first). Capability `room-images`.

## Group rooms and memory (plugin 0.62+)

In a gateway-hosted group room, each member's turn runs on its own host in a
hidden session (`source: bot_room`, titled `Group: <room id>`), and the
turn's message is the room's new messages, from several people and bots.
Hermes hands that turn to the profile's external memory provider (Honcho,
Hindsight and the like) with no author, so the provider would file everything
said in the room as the owner's own words. The plugin keeps room sessions
from saving into the provider: the per-turn sync, the session-end extraction
and the provider's part of the summary before a compaction are skipped for
them, also after a compaction moves the session to a new id. Recall still
runs, and `MEMORY.md` and `USER.md` still load, so a member knows its owner
in the room; it just doesn't learn from what others say there. The memory and
skill tools work as before. If Hermes' memory manager lacks one of the
methods the plugin guards, the plugin guards the rest and logs a warning
naming what's missing. If Hermes' session store (`state.db`) can't be read
when the plugin needs it to tell whether a session is a room, the plugin logs
a warning and treats that session as an ordinary chat.

## Artifacts (plugin 0.40+)

Conduit's Artifacts screens list what a profile's chats produced:
`GET /api/plugins/conduit_push/artifacts` reads the profile's `state.db`
(read only) newest message first and returns
`{"ok": true, "items": [...], "next_before": 1234}`. Each item has a `kind`
(`image`, `video`, `audio`, `page`, `document`, `file` or `link`), a `source`
(`delivered` for a `MEDIA:` file, `preview` for a `::preview` page, `written`
for a document or media file a tool wrote, `attached` for a file the user sent
with `@file:`, `link` for a web link in a reply), a `name`, the chat's
`session_id` and `session_title`, the `message_id` it came from and its
`timestamp`; a file has its `path`, whether it still `exists` and its `size`,
a link its `url` and `host`. Within a page one path or URL is listed once, at
its newest mention (a later page can list it again at an older one). Query: `session_id` (one chat; repeat it for each id the chat is
known by, and the sessions it continues from or spawned are read too), `kind` (`images`, `pages`, `files` or
`links`), `q` (words in the name, chat title, path or URL), `limit` (up to
200) and `before` (the previous page's `next_before`; `null` once the history
is read to its start). A request reads a bounded window of rows, so a page can
come back short with a `next_before` to keep going. One message adds at most 200
artifacts to a page (a page ends after the message that fills it, so it can
run past `limit`); the rest of a message naming more than that isn't listed. With `session_id` (plugin
0.43.2+) only that chat's own rows are read, so a chat under a long history
of other chats, cron runs say, lists in one request. `missing=hide` (plugin
0.51.8+) leaves out files no longer on the host, so a history of deleted files
doesn't leave pages mostly empty; links always stay, and an older plugin
ignores it and lists them. Capability `artifacts`.

## Hermes calls you (plugin 0.13+)

When a watched job ends (see Hermes asks to call), the plugin sends a
**call request** through the relay instead of the usual "Response ready" or "Turn failed" push: a
"Hermes wants to talk" notification whose Talk button opens Live Voice in the
job's chat, where Hermes opens with how the job went. With relay 0.9+ and a
Conduit build that rings, it arrives as a native incoming call (CallKit)
instead, and the notification is the fallback. With relay 0.10+ and a Watch
app that rings, the Apple Watch rings too, and answering on either stops the
other.

Calls are off until you turn them on in Conduit's Settings, under Calls from
Hermes. Settings and watches live per profile in
`<hermes home>/conduit-calls.json` (mode `0600`), shared by the turn-end hooks
and the dashboard routes under one file lock, so they survive restarts:

| Setting | Default | Range |
| --- | --- | --- |
| `enabled` (Hermes can call me) | off | |
| `when_asked` (call when I explicitly ask) | on | |
| `decides` (Hermes decides when to call, 0.14+) | off | |
| `alerts` (approval, question and failure calls, 0.14+) | off | |
| `min_gap_s` (time between calls) | 120 s | 30–3600 s |
| `per_hour` | 6 | 1–30 |
| `per_day` | 20 | 1–60 |
| `rules` (what's worth a call, 0.16+) | empty | up to 500 characters |

| Method | Route | Body | Returns |
| --- | --- | --- | --- |
| GET | `/api/plugins/conduit_push/calls?profile=` | | `{ok, paired, settings, bounds, rules_max, watches}` |
| PUT | `/api/plugins/conduit_push/calls?profile=` | `{settings: {...}}` (any subset) | `{ok, settings}` |
| POST | `/api/plugins/conduit_push/calls/outcomes?profile=` (0.15+) | `{call_id, session_ids: [...], outcome: "declined" or "missed", kind?, title?, reason?, age_s?}` | `{ok, status: "recorded"}` |

- A watch names up to 4 session ids (the job's runtime and stored ids) and a
  title of up to 120 characters. It fires once, on the first turn end of any
  of them: `done` (the turn finished), `failed`, or `stopped` (interrupted).
  A replayed hook finds nothing left, so a job calls at most once. Watches
  expire after 24 hours; a profile holds at most 20 (429 past that).
- 409 when the profile isn't paired with Conduit, or calls (or "call when I
  ask") are off. 400 for an unknown setting or a value outside its range.
  429 past 30 requests a minute per profile.
- A call held back by your limits, or calls turned off after the watch was
  made, consumes the watch and sends the usual push instead. So does a relay
  that refuses the call request (relays before 0.8 don't know it; 0.8 caps
  call requests at 60 a day per installation, `call_limit`), one that took
  the request but couldn't reach Apple, or one that stays unreachable or keeps
  failing (5xx) after three tries (2 s and 4 s apart, same event id). One
  malformed session id drops the job details from the request, on the host
  and on the relay alike; it still opens the chat.
- **Declined and missed calls (0.15+):** when you decline a call, or it
  rings out, reaches a phone that was offline or is silenced by Do Not
  Disturb, Conduit reports it here with the call's id, session ids, kind,
  title and reason, and `age_s` (how long ago, on the phone's clock). The
  next turn of one of those sessions gets a one-line note through the
  `pre_llm_call` hook, for example "the user declined the phone call you
  placed 12 minutes ago", and takes it, so Hermes hears it once, even if a
  late retry of the report arrives after. Nothing rings again. A retried
  report keeps the first; a profile keeps at most 20 waiting, each for a
  day. 409 when the profile isn't paired, 400 for anything malformed.
- **Conduit first (0.36+):** every turn of a main conversation also gets one
  line naming what the phone shares with this profile (calendar and
  reminders, health, location, phone status, contacts) and saying to use
  the Conduit tool before other tools, skills or CLIs for the same data,
  such as gog. Each of those tools' descriptions ends the same way. Hermes
  drops `pre_llm_call` context after the turn, so the line never piles up;
  what's shared is looked up at most once a minute. Subagents don't get it.
- The call request carries the job's id, outcome, title and session ids so
  Conduit can open the right chat. With end-to-end encryption they are sealed
  like any other content; with `redact on` the title is dropped.
- **Ringing (relay 0.9+):** a phone that registered a PushKit token
  (`voip_token`) gets the call request as a VoIP push on the app's `.voip`
  topic, with no alert, the same routing or sealed envelope, and `sent_at`,
  so it rings as a native call. Like a notification, APNs tries to keep it
  for a phone that's offline (for up to a day; best effort, and only the
  newest one per app), and Conduit shows one that arrives late as a missed
  call rather than ringing. Anything that stops it ringing
  (APNs refusing or unreachable, a call with no chat to open) sends the usual
  "Hermes wants to talk" notification instead, and a PushKit token APNs calls
  gone is forgotten until the phone registers a new one. The
  relay answers `rang: true` when APNs took the VoIP push. Calls carry a `reason` of up to
  200 characters (dropped with previews off, like the title), and the kinds
  `approval` and `question` besides how a job ended.

### Hermes asks to call (plugin 0.14+)

The plugin gives Hermes a `conduit_call_user` tool (toolset `conduit`) and a
bundled skill, `conduit_push:calling-the-user` (plugin skills aren't listed in
the skill index, so the tool's description points to it). Hermes calls it
with a `reason` (one spoken sentence, up to 200 characters) and
`asked_by_user`:

- The call rings when the asking turn ends, so it opens on the finished
  result: the turn's final reply is in the chat the call opens, and the
  reason is said first. This works from any chat Hermes runs in (typed
  chats in Conduit or Desktop, other platforms, cron jobs), not only Live
  Voice.
- `asked_by_user: true` needs "call when I ask"; `false` needs "Hermes
  decides". Either way the limits apply, and a session
  already watched keeps one watch (it takes the reason).
- **What's worth a call (0.16+):** with `rules` written (the user's own
  words, such as "only if production is down"), a call Hermes decides on
  first answers `check_rules` with them. It goes only when Hermes calls again
  with `fits_rules: true` in the same chat, within 10 minutes, while the rules
  are unchanged. Calls the user asked for skip the rules, and Hermes can read
  them but not change them. The rules are checked when Hermes confirms the
  call, not when it rings, and they steer Hermes rather than bind it:
  `asked_by_user` is Hermes' own word (0.14+), so a call it marks as asked
  for skips them.
- **Call watches (0.17+):** the rules only filter the calls Hermes makes;
  they don't watch anything. When the user asks to be called if something
  happens ("call me if the homelab is down for more than 10 minutes"),
  Hermes uses `conduit_call_watch` and only describes the watch: `what`,
  `how` a run checks it, `for_minutes` it must last, and optional `hours`
  (HH:MM-HH:MM) and `unless`. The plugin writes the cron job through
  Hermes's own `cronjob` function: named "Call watch: <what>", checked every
  few minutes (picked from `for_minutes`), with a fixed run prompt. The same
  `what` is the same watch, so asking again changes it instead of adding
  another. `sync` takes every watch the What's worth a call note describes
  (Conduit's "Have Hermes watch for this"): it changes and adds watches to
  match and lists the ones the note no longer mentions, which Hermes asks
  about before removing.
- **A watch's runs:** each run checks and calls `conduit_watch_report` with
  whether it's happening. The plugin keeps the incident per job in
  `conduit-call-watches.json`, waits out `for_minutes` and the allowed hours,
  calls once per incident with the run's sentence as the reason, and tells
  the run what to reply (`[SILENT]` while there's nothing to send).
  `conduit_call_user` refuses in such a run. Watches set up by 0.16.x (jobs
  that load the skill and keep their own state) keep running as written, and
  setting one again by name or id moves it onto the report.
- A call the user asked for while calls are off answers `calls_off` with a
  `conduit://settings/calls` link for Hermes' reply, which opens Calls from
  Hermes in Conduit.
- The tool shows only while this profile is paired and one of those is on.
  Subagents can't call; their parent can. `conduit_call_watch` shows while
  the profile is paired on a Hermes with scheduled jobs, and
  `conduit_watch_report` while it's paired (it only works in a watch's run).
  When `conduit` is off for cron in `hermes tools`, each watch's job gets
  its own toolset list (cron's, plus `conduit`) so its runs can report.
- If `hermes tools` lists the `conduit` toolset as off for a platform, turn
  it on there.

### Alert calls (plugin 0.14+)

With `alerts` on, Hermes also calls when it waits on you:

- **Approval:** an approval request still unanswered after a minute rings
  (kind `approval`, the request's description as the reason), beside its
  usual answerable notification. Answering it anywhere first
  (`post_approval_response`) or the turn ending cancels the call.
- **Question:** the same for a clarify question (kind `question`), answered
  through Conduit's card, Desktop or the CLI. Needs the clarify middleware
  (Hermes with `register_middleware`).
- **Failed turn:** a turn that fails calls in place of its "Turn failed"
  push (kind `failed`).

Alert calls count against the same limits. In the call, Conduit can read the
approval out and answer it by voice.

## Hermes changes Conduit settings (plugin 0.19+)

Ask Hermes to set Conduit up ("make live calls more relaxed", "use Gemini
Live with my memory") and it can, through the `conduit_settings` tool, within
what Conduit allows:

- **Conduit decides what Hermes sees.** Each Conduit uploads the settings it
  shares (key, plain-language title and meaning, choices, value and tier) and
  the user's **Let Hermes change settings** mode to
  `PUT /api/plugins/conduit_push/conduit-settings` when it connects, comes to
  the foreground, changes a shared setting, or a turn used the tool. Anything
  it doesn't list (keys, wake phrase setup, Calls from Hermes, Watch access,
  the mode itself) is out of Hermes' reach.
- **Hermes only asks.** `get` lists the settings; `change` keeps a request
  with the value Hermes saw and a reason; `cancel` takes back one Conduit
  hasn't picked up. Requests wait in the profile's `conduit-settings.json`
  for a day.
- **Conduit applies or asks.** It checks every request against its own list
  again. With the default mode, **Ask me every time**, each change waits for
  the user's Apply. With **Small changes without asking**, the small tier
  (how calls sound, voices) applies with an Undo and the rest still asks.
  **Off** refuses everything. A setting the user changed after Hermes read it
  keeps the user's value. Conduit reports each outcome (applied, dismissed,
  conflict, refused, undone) on its next sync, and `get` shows it to Hermes.
- Speech providers and their keys, `voice.gpt_live` and models are Hermes
  settings, not Conduit's: the tool tells Hermes to change those in its own
  config.

The tool shows only once a Conduit has synced with the profile. Limits: 20
requested changes per device per hour, 10 per call, 8 devices per profile.

## Hermes asks you to confirm (plugin 0.34+)

Before an action you should OK (sending a message for you, buying, deleting),
Hermes can ask on your phone with the `conduit_present` tool:

- **Tool.** `confirm` keeps a prompt (title up to 80 characters, a Markdown
  preview up to 2,000, a button label up to 24, up to 5 `spoken_yes`
  phrases, `ttl_minutes` 30 by default and at most 1,440) and wakes the phone
  with a `phone.changes` push (`present:<id>`). `wait_seconds` (up to 120)
  waits for the answer. `status` returns waiting prompts and answers Hermes
  hasn't seen yet (or one by `id`); `cancel` takes one back. States:
  `waiting`, `confirmed`, `declined`, `edit`, `expired`, `cancelled`. Only
  `confirmed` means go ahead; on `edit` you send the corrected request
  yourself.
- **Conduit answers.** It shows a panel over everything, calls included, and
  you confirm by tap or, in a call, by voice. It reports answers and fetches
  waiting prompts with
  `POST /api/plugins/conduit_push/present/exchange?profile=`:
  `{"installation_id", "device", "app_version", "results": [{"id", "outcome": "confirmed|declined|edit", "edit_text"?, "via": "tap|voice"}]}`
  answers `{"ok": true, "prompts": [{"id", "title", "preview", "action_label", "spoken_yes", "session_id", "created_at", "expires_at"}]}`.
  The first answer wins; answers for unknown or finished prompts are ignored.

The tool shows only once a Conduit with `present-v1` has exchanged with the
profile; subagents can't use it. Prompts live in the profile's
`conduit-present.json` (answers are kept a week). Limits: 20 prompts an
hour, 20 waiting at once, 60 exchanges a minute per profile.

## Hermes shows things during a voice call (plugin 0.44+)

In a Conduit voice conversation (Local Live, Classic voice, or a live call
that hands work to Hermes), a table, steps, a chart or links are better seen
than heard. Hermes puts them on the call's screen with `conduit_show`
(`title` up to 80 characters, `markdown` up to 8,000) and says in a sentence
that they're there. Voice turns get a note saying so while a Conduit that
shows cards is connected.

- **No push.** The card is kept in `conduit-present.json` and listed in the
  same `present/exchange` answer as `"cards": [{"id", "title", "markdown", "session_id", "created_at", "expires_at"}]`
  (only when there are any). Conduit exchanges as soon as it sees the tool
  in the turn and again when the reply ends, and shows each card once.
- **Short-lived.** A card is dropped after ten minutes: it belongs to the
  conversation it was shown in.

The tool shows only while a Conduit that says `show-cards` in its exchange's
`features` has exchanged with the profile in the last six hours, and only
that phone gets the cards; subagents can't use it. Limits:
60 cards an hour, the newest 20 kept.

### Map and place cards (plugin 0.45+)

`conduit_show` also takes `cards`: up to four maps, places and other cards Conduit draws
natively, in a typed chat as well as on a call. `markdown` is optional with
cards; without it, the cards' own Markdown (each place with an Apple Maps
link) is what a phone that doesn't draw cards, or another client, shows.
A call-screen card whose Markdown is only that text carries `"fallback": true`
in the exchange (0.45.1+), so a phone that draws the cards leaves it out.

- **One schema.** [`cards/card-schema.json`](cards/card-schema.json) is the
  only definition. The tool's `cards` parameter is built from it and
  `card_schema.py` normalizes against it. Conduit ships a byte-identical copy
  for the live models' `show_on_screen` and fails its CI when the copy
  differs from main; [`cards/card-vectors.json`](cards/card-vectors.json)
  holds examples both test suites run. Change both files together and merge
  here first.
- **Sourced facts only.** The phone adds address, category, phone, website,
  travel time and Look Around from Apple Maps when it draws a card; the
  schema has no fields for them. A rating, hours, price or photo needs a
  `source`, or it's dropped; a place's or person's photo also needs an https
  `url`.
- **Kept in history.** The tool's answer carries the normalized cards
  (`{"ok": true, "cards": [...]}`), so the chat's history keeps them and
  Conduit draws them whenever the chat is opened. With no call screen, a
  Conduit that says `chat-cards` in its exchange's `features` still gets
  the tool, and the card shows in the chat only. A turn that isn't from
  Conduit (Desktop, or a messaging app through Hermes' gateway) is refused
  with `not_conduit`. A classic `hermes` terminal turn can't be told apart
  yet (Hermes doesn't bind its platform for tools), so it isn't refused.

### Information cards (plugin 0.46+)

Cards can also be `stats` (big numbers with a change and a small line),
`chart` (line, area, bar or pie, drawn with Swift Charts), `weather` (now,
the next hours and days), `comparison` (two to four options, one
recommended at most) and `steps` (what you need, then steps the user can
tick off, with timers). Each type has its own field, and the schema's rules
keep only that field.

- **Where it's from.** These cards take a card-level `source` (`name`, and
  a `url` if any), shown on the card. A forecast needs one or it's dropped;
  without one, the other cards read as Hermes' own.
- **Only where they're drawn.** A Conduit says `info-cards` in its
  exchange's `features` when it draws them. Unless every Conduit that
  draws cards (`show-cards` or `chat-cards`) and exchanged with the profile
  in the last 30 days says it, the tool leaves them out (`unsupported_cards`
  when nothing else is left): the chat keeps the cards, and an older build
  opening it would show them as nothing. Each phone's exchange
  also leaves out the cards it can't draw and shows the Markdown instead.

### Media, contact and live cards (plugin 0.47+)

- **`media`**: up to 12 photos, videos or audio clips, as direct https links
  (`kind`, `url`, and `title`, `by`, `caption`, `duration`, `artwork`,
  `page`). Conduit shows photos in a gallery and plays video and audio
  itself. A media card needs a `source`.
- **`contact`**: up to six people (`people`: `name`, `detail`, `phone`,
  `email`, `url`, `address`, `note`, and a `photo` with its source). Conduit
  offers Call, Message, Email and Add to Contacts, and says "In your
  contacts" when the person matches one the user already has (checked on
  the phone, only when Conduit already has access). A phone or email that
  doesn't read as one is dropped. A person can carry a `message`, a text
  Hermes wrote for the user to send them (plugin 0.67+, only with their
  `phone`): Conduit shows it with Send text, which opens Messages filled in,
  and only the user's tap sends it. A Conduit that says `text-drafts` in its
  exchange gets it; for any other, the tool leaves the text off the card and
  tells Hermes to give it in its reply.
- **`status`**: where something in progress stands (`state`, `phase`
  waiting/active/done/problem, `progress` 0–1, `detail`, `eta`,
  `milestones`).
- **Live names.** Any card can carry `live`, a name Hermes picks. Showing a
  card with the same live name again in the conversation replaces the
  earlier one, on the call screen and in the chat, so Hermes keeps a
  delivery, a score or a job's progress up to date by showing it again.
  Cards shown beside the earlier one stay.
- A Conduit says `media-cards` and `live-cards` in its exchange when it
  draws them; the same gating as information cards applies.

## Health data from Conduit (plugin 0.23+)

Conduit can share Apple Health data with a Hermes profile so the agent can
answer "how did I sleep?" or "how active was I this week?". It's off until
the user turns it on in Conduit, per category (activity, heart, sleep,
workouts, body, vitals, fitness), with how far back to start.

- **Straight to this host.** The phone posts to
  `POST /api/plugins/conduit_push/health/ingest` over your dashboard
  connection. Health data never passes through the push relay or any
  Conduit server.
- **Sealed end to end.** Each phone agrees a key with the profile once
  (`POST /health/key`, X25519: only public keys cross the wire, so watching
  that exchange doesn't reveal the key). Every batch is sealed with
  ChaCha20-Poly1305 under an HKDF-SHA256 key from it, on top of any TLS, so
  even a dashboard on plain http in your LAN never carries health data in
  the clear. Like any plain-http service, someone actively tampering with
  the connection while the key is set up could still intercept it: use
  HTTPS or a private tunnel when you can.
- **Who can use these routes.** Anyone signed in to your dashboard, as
  for every other dashboard route; push pairing isn't needed. A signed-in
  client could register a new key under a phone's device id and send data
  in its name (the phone notices on its next sync and sets up a new key),
  so treat dashboard access as access to your health data. A new device key
  for a device id drops what the earlier key sent (the phone sends it all
  again), so a re-key can't be used to read a phone's data back; the same
  device key again keeps it, since only that phone can use it.
- **Refusals.** A request the store refuses answers with its HTTP status
  and `{"detail": "<message>", "code": "<word>"}`. `unknown_key` and
  `bad_seal` (409) mean this host doesn't have the phone's key (the phone
  sets up a new one); `too_many_devices` and `schema` (also 409) don't. The
  location routes answer the same way. Other errors carry only `detail`.
- **Summaries first.** Conduit sends the hourly and daily totals Apple
  Health computes on the phone (iPhone and Watch already merged), a summary
  per night of sleep, sleep stage segments and workouts. Raw readings go
  only for categories where the user turns on detailed readings.
- **Stored here only.** The profile's `conduit-health.sqlite3`, mode `0600`.
  A newer computation of a window replaces the older one; a deleted workout
  or reading stays deleted. `GET /health/status` reports counts and dates,
  never values; `POST /health/wipe` deletes one device's data and key (or
  everything with `{"all": true}`), and Conduit's "Delete health data on
  this host" calls it. No route returns health data.
- **Read-only tool.** `conduit_health` (actions `overview`, `daily`,
  `hourly`, `sleep`, `workouts`, `samples`; at most 92 days per call) with
  its skill `conduit_push:reading-health-data`. It shows only once a phone
  has synced data, and subagents can't use it. What it returns goes to your
  agent's model like any tool result, which Conduit tells the user before
  they turn sharing on.

Limits: 4 devices per profile, 6,000 items and 4 MiB per batch, 120 uploads
a minute per profile.

## Location from Conduit (plugin 0.26+)

Conduit can tell a Hermes profile where the user is. It's a building block
rather than one feature: the agent can answer "how far am I from work?",
follow place rules ("call me with my brief when I leave home on weekdays"),
use it from any scheduled job or skill the user teaches it ("check I'm on my
way before each appointment"), and Calls can skip places the user picked.
Two separate opt-ins in Conduit:

- **While talking** (When In Use): one fix when the user sends a message or
  starts a voice call, and again when they've moved over 200 m during a call.
  Precise by default.
- **In the background** (Always): arriving at and leaving saved places
  (up to 20), visits and significant moves. Area by default.

Each layer has its own precision: `places` (saved place names only), `area`
(about 1 km: neighbourhood and town, coordinates rounded to 2 decimals) or
`precise`. The phone applies it before sending and the host applies it again.
Saved places live on the phone: this host gets their names and kinds, never
their coordinates, and each fix carries distances to them instead. A place
marked private is reported only as "at a private place".

- **Straight to this host, sealed.** Same scheme as health with its own key
  and labels (`POST /location/key`, `POST /location/ingest`): X25519, then
  ChaCha20-Poly1305 under an HKDF-SHA256 key. Location never passes through
  the push relay; the relay only carries the on-demand request (below).
- **Stored here only.** The profile's `conduit-location.sqlite3`, mode
  `0600`. History is kept as long as the user picks in Conduit (latest only,
  1, 7 by default, 30 or 365 days). `GET /location/status` reports counts,
  never locations, and `locate.available` (whether `locate` can reach the
  phone: this profile is paired for notifications); `GET /location/reads` lists when the agent read location
  (kept 30 days, without the locations); `POST /location/wipe` deletes one
  device's data and key, or everything with `{"all": true}`. A new device
  key for a device id (a reinstall, sharing turned off and on, a new
  pairing) drops that device's fixes, visits and saved places; the phone
  sends its places again with the new key.
- **Tool.** `conduit_location` (actions `now`, `locate`, `places`,
  `history`, `distance_to`, `rules`, `set_rule`, `remove_rule`) with its
  skill `conduit_push:using-location`. It answers "paused" or "off" when the
  user has paused sharing, logs every read, and subagents can't use it.
- **On-demand locate.** `locate` asks the phone for a fresh fix through the
  relay as a silent location push (Apple's Location Push Service Extension),
  which the phone answers only while background sharing is on and not
  paused. At most one every 5 minutes and 30 a day per location store
  (profiles reading a shared one spend its budget).
- **Place rules.** `set_rule` keeps a Hermes cron job named
  `Place rule: <what>` that never runs on its own schedule; an arrive or
  leave event that matches the rule's place (one saved place or any), move
  (arrive, leave or either), days and hours triggers it with a line naming
  the place and move (`GET /location/rules`, `DELETE /location/rules/<id>`).
  The task is anything a cron run can do. A rule fires once a day, or every
  time at least 30 minutes apart (`repeat: "every"`), never for an event
  over 15 minutes old, and never while sharing is paused.
- **Other profiles on this host** (plugin 0.58+). Conduit binds sharing to
  one profile, which keeps the store, key and place rules. With "Share with
  this host's other profiles" on (`sharing.other_profiles: true`), every
  other profile on the same host that is paired with the same iPhone (the
  same relay installation in its `conduit-push.json`) reads that store:
  `now`, `places`, `history`, `distance_to`, `locate` and maps lookups. A
  locate or phone maps lookup goes through the asking profile's own pairing
  and names the sharing profile, so the phone answers it as that profile's.
  Reads are logged in the sharing profile's store as `<profile>: <chat>`.
  `rules`, `set_rule` and `remove_rule` answer `other_profile`: rules stay
  with the sharing profile. A profile that shares location itself (talking
  or background on) always reads its own, and if several profiles share
  with the others the first wins (default, then named ones alphabetically).
  The fresh-position and maps budgets belong to the sharing profile's
  store, so every profile reading it spends the same ones. Calls placed
  from a reading profile are held back by the shared position, but the
  places to avoid are that profile's own calls settings.
- **No calls at places.** Calls settings `avoid_places` (place ids) and
  `avoid_unknown_place` (also hold calls when there's no recent location,
  or sharing is paused or off): a call that would ring while the user is at an
  avoided place goes out as a notification (status `limited`, reason
  `place`). The latest fix counts for 24 hours with background sharing on,
  otherwise 1 hour.

Limits: 4 devices per profile, 20 places, 256 KiB per batch.

## Maps (plugin 0.31+)

`conduit_maps` gives Hermes Google Maps, looked up from this host: `search`
(places or categories near the user, a place or an address), `lookup` (one
place or address), `reverse_geocode`, `directions` (routes with traffic and
steps, by car, on foot, by transit or bike, and `leave_by` for `arrive_by`)
and `travel_times` (up to 10 destinations at once). Places can be `"me"`, a
saved place's name, an address or a name, `place_id:<id>` from an earlier
answer, or `lat,lon`. It's a building block like location: crons, place
rules and skills can use it. Lookups are logged in the location read log
(action and chat, never the query).

`navigate` (plugin 0.37+) opens Maps on the phone with directions to a
place. It's a confirm prompt (`conduit_present`'s store and exchange)
carrying `maps: {to, mode}`: Conduit opens Maps at once when the user is in
that chat with Conduit open, and otherwise shows a Go button and a
notification, answered by tap or by saying "go" in a call. Conduit says it
can do this with `features: ["maps-navigate"]` in its present exchange;
without one that said so in the last 30 days the tool returns a Maps link
for a text chat. Only a Conduit that says so gets the Go prompt, and only
its answer counts.

### Google Maps on the host (plugin 0.69.1+)

The host answers lookups with its own Google Maps Platform key, and needs no
relay for them: put the key in Hermes' `.env` as `GOOGLE_MAPS_API_KEY`;
without one the tool is hidden. Search and places use Places API (New),
directions and travel times the Routes API (with traffic when driving), and
what's at a spot the Geocoding API, so the key's project needs those three
enabled. Saved places can't be looked up here: their coordinates live on the
phone (a trip from "me" to one gets a labelled straight-line guess). "me" is
the last shared fix at its detail. The key stays on this host: no phone,
relay or app build carries it. Restrict it to those three APIs (and, if the
host has a fixed address, to that address), and set a budget alert: Google
bills the key's project. Each host makes at most 200 calls a day. `navigate`
to a `place_id` from a Google answer sends the place's coordinates, which any
phone's Maps opens, and the link for a text chat is a Google Maps one. A
phone that turned on "Keep maps lookups on this iPhone" turns the tool off
for that profile.

## Calendar, Reminders, Focus and phone status from Conduit (plugin 0.27+)

Conduit can share the user's iPhone calendars (every account on the phone),
Reminders, which Focus is on and a snapshot of the phone (battery, charging,
Low Power Mode, CarPlay, audio route, network, motion) with a Hermes profile,
so the agent can answer "what's on today?", find a free slot, add the
dentist on Thursday, remind them to call mum when they get home, or keep it
short when the battery is low. Each kind is off until the user turns it on
in Conduit, with which calendars and lists, how far back and ahead, and
whether notes and attendees are included (off by default).

- **Straight to this host, sealed end to end.** The phone posts to
  `POST /api/plugins/conduit_push/phone/ingest` over your dashboard
  connection, never through the push relay. It agrees its own key with the
  profile (`POST /phone/key`, X25519, separate from health and location, so
  each can be on alone and wiping one never touches another), and every
  body is sealed with ChaCha20-Poly1305 under HKDF-SHA256 keys from it, on
  top of any TLS. The same caveats as health apply: use HTTPS or a private
  tunnel when you can, and treat dashboard access as access to this data.
- **What the user chose, enforced here too.** The phone says what it
  shares in every batch and the store holds it to that: no notes,
  attendees or links without "Include notes and attendees", no attendee
  emails without that switch, no events at all when the calendar is
  "add only" (write-only) or off, and status or Focus forgotten as soon as
  either is turned off. Only the shared window is kept (past days to
  future days); a batch whose events leave out the range stays inside the
  last one shared. `calendars` is the user's current selection, replaced
  whole: events and reminders on a calendar or list it leaves out are
  deleted. Status and Focus are the latest value only. A batch, status or
  Focus time more than 5 minutes ahead of this host's clock is refused
  with code `clock_skew`, so a future-dated batch can't make the real ones
  after it (a sharing change included) look out of date. What a refused
  batch turns off is still forgotten. A calendar or reminders shared
  "read only" (`calendar_read_only` / `reminders_read_only`, plugin
  0.52.0+) are read but never written: every change to them is refused
  with `shared_read_only`, changes already waiting fail at the phone's
  next exchange (as do those whose calendar or list is no longer shared),
  and a refused batch can't lift read-only.
- **Writes are changes the phone applies.** Hermes can't touch the phone's
  calendar, so `conduit_calendar`'s write actions queue a pending change.
  The plugin nudges the phone with a `phone.changes` relay event (sealed
  like any notification when the pairing has end-to-end encryption): a
  visible notification for a change the user approves on the phone
  (`mode: "alert"`), or a silent background push for an add the user lets
  Hermes make without asking (`mode: "background"`); updates, deletes and
  completions always ask, and adds to shared calendars or lists always ask.
  The phone picks the queue up and reports outcomes (applied, edited,
  dismissed, failed, expired) with one sealed `POST /phone/exchange`. The
  notification carries no calendar data beyond the sealed title and body:
  the change itself comes from this host. Pending changes expire after 7
  days, at most 50 per profile. A relay without `phone.changes` refuses
  the nudge; the phone still finds the change on its next exchange.
- **Stored here only.** The profile's `conduit-phone.sqlite3`, mode `0600`.
  `GET /phone/status` reports counts and dates, never content;
  `POST /phone/wipe` deletes one device's data, key and pending changes (or
  everything with `{"all": true}`).
- **Tools.** `conduit_calendar` (reads `overview`, `calendars`, `events`,
  `free_busy`, `next`, `reminders`; writes `add_event`, `update_event`,
  `delete_event`, `add_reminder`, `update_reminder`, `complete_reminder`,
  `delete_reminder` (Conduit builds before it leave that one waiting until
  it expires; deletes and completions carry the item's title and time so
  the phone's card names it);
  `pending` for how changes went) and `conduit_phone` (`status`), with the
  skill `conduit_push:using-calendar`. Each shows only once a phone shares
  what it reads; subagents can't use them. Reads say how fresh the copy is
  ("as of" the last sync). What they return goes to your agent's model like
  any tool result, which Conduit tells the user before they turn sharing on.

- **Alarms and timers (plugin 0.30+).** When the user lets Hermes set them
  (AlarmKit, iOS 26), `conduit_phone` gains `alarms` (the alarms and timers
  Hermes set that are still on: iOS shows an app only its own), `set_alarm`
  (one-off `at`, or `time` HH:MM with `repeats` days), `set_timer`
  (`seconds`) and `cancel_alarm`, as pending changes like calendar writes.
  They ring through Silent and Focus. Setting one goes without asking when
  the user lets Hermes add without asking; cancelling always asks.
- **Contacts (plugin 0.30+).** Only the people the user picks in Conduit
  (no address book permission): name, nickname, a relation the user types
  ("wife"), phone numbers, emails, birthday and organization, read with
  `conduit_contacts` (`people`, with an optional `query`). Turned off, they
  are deleted here.

Limits: 4 devices per profile, 5,000 items and 4 MiB per batch, 50 alarms and
200 contacts per device, 120 uploads and 60 exchanges a minute per profile,
64 KiB per exchange.

## Capabilities (plugin 0.4+)

`GET /api/plugins/conduit_push/capabilities` returns the plugin version and
the Conduit features its routes serve:

```json
{"ok": true, "version": "0.24.1", "loaded_version": "0.24.1", "restart_needed": false, "boot_id": "9f2c41d07a3b5e68", "capabilities": ["session-takeover", "e2e-notifications", "...", "pairing", "self-restart"]}
```

Conduit reads it on connect. When a feature it uses is missing, or the route
itself is (a plugin older than 0.4), Settings asks you to run
`hermes plugins update conduit_push` and restart the gateway. Every new route
family adds its name here.

## Pairing from Conduit (plugin 0.24+)

`POST /api/plugins/conduit_push/pair?profile=` with
`{"pairing_code": "ABCDE-FGHJK", "relay_url": "https://push.milim.dev"}`
makes the same claim as `hermes conduit-push pair` for that profile and saves
the credential in its `conduit-push.json`. `relay_url` is optional (the
profile's current relay, else push.milim.dev) and must be a bare http(s) URL;
the claim carries only the code and the gateway name, never follows redirects,
and the answer never includes the credential:
`{ok, paired, installation_id, gateway_id, gateway_name, relay_url}`. A
re-pair keeps the profile's redaction choice; it keeps the encryption key when
the same phone and gateway pair again, and otherwise drops it (Conduit
provisions a new one). 400 for a malformed code or URL, 410 when the
code expired or was used, 429 past 10 requests a minute, 502 when the relay
can't be reached.

## Updating from Conduit (plugin 0.24+)

Conduit updates the plugin with Hermes' own dashboard routes
(`POST /api/dashboard/agent-plugins/install` and
`POST /api/dashboard/agent-plugins/conduit_push/update`), then restarts the
gateway (`POST /api/gateway/restart`), then this dashboard:

- `GET /capabilities` also reports `loaded_version` (the version this
  dashboard process imported), `restart_needed` (the version on disk is
  different) and `boot_id` (new with every dashboard process).
- `POST /api/plugins/conduit_push/self/restart` answers
  `{ok, restarting, boot_id, loaded_version, version}` and a second later
  re-executes the dashboard with the command line it started with, keeping its
  pid, so systemd, launchd and terminal launches carry on. 409 while a chat
  turn this process runs is still going (from Hermes' turn markers); 501 on
  Windows, inside a plugin host, and for Hermes Desktop's own backend, where
  you restart Hermes yourself.

The first update to 0.24 still runs the old code, which has no restart route:
restart the dashboard by hand once.

Every version is listed in [CHANGELOG.md](CHANGELOG.md), which Conduit's update
notice reads.

## Conduit support and privacy

The repository also hosts the public Hermes Conduit support and privacy pages:

- [Hermes Conduit support](https://kaishi00.github.io/hermes-conduit-notifier/support/)
- [Hermes Conduit privacy policy](https://kaishi00.github.io/hermes-conduit-notifier/privacy/)

## Development

The runtime uses only the Python standard library plus Hermes APIs. CI ([`.github/workflows/tests.yml`](.github/workflows/tests.yml)) runs the plugin tests on every PR and every push to main. To run them locally:

```bash
pip install -r tests/requirements.txt
python -m pytest --rootdir=tests tests
```

Working on a feature with siblings in the app? See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
