---
name: consolidated-decisions
description: "The consolidated decision thread: gather everything waiting on the owner across the repos the coordinator serves, check each item against current state, and post one self-contained decision card per item, grouped by urgency. Run by a one-off thread the coordinator starts."
disable-model-invocation: true
---

# Consolidated decisions

A consolidated decision thread puts everything waiting on the owner in front of them at once, one decision card per item.
The owner reads each card cold: assume they remember nothing about the ticket behind it.
The coordinator starts the thread, at build-tier, and its trigger lives in `.forge/coordinator-core.md`, "Owner approvals".

The thread is **read-only** on the tracker and the repos: its only writes are its own messages, its cards and a background file.
It relays every answer to the coordinator (step 5), which records it and routes the follow-up.

## 1. Gather

Collect candidates from every source below, for every repo the coordinator serves:

- open `needs-decision` tickets (`queue-sweep` check 9 has the query);
- pending owner approvals: wording a ticket or design comment asks the owner to approve, and spec-only or lifecycle-doc PRs waiting on that approval (`.forge/requirements-driven-changes.md`, `.forge/process-and-evidence.md`);
- open PRs whose merge is reserved for the owner, such as one built with `implement`;
- held work: a ticket or thread blocked on something only the owner can do, and any decision card still unanswered in another thread;
- the items the coordinator listed in this thread's brief.

Done when every source is queried and each candidate links to where it lives.

## 2. Verify against current state

Re-read each candidate's ticket or PR and its latest comments now, never a summary.
Drop an item that is already settled: closed, its card answered, its owner quote already posted, or its question overtaken by a later change.
A settled standing fact of the project (how often CI runs, who merges in a given repo) is context for a card, never a card of its own.
An owner task that has no choice in it, such as a hands-on check only the owner can run, gets a line in the summary (step 4), not a card.
Note each item that waits on another one, and which.

Done when every candidate is marked keep, drop (with the reason) or owner task.

## 3. Write one card per item

Each card carries:

- **a question**, numbered in posting order and verb-first, naming the ticket, for example "3. Retry failed invoice exports automatically? (#<n>)";
- **background** in plain language: its urgency group and any review grade first, then what the thing is, what goes wrong or what is at stake, and a link;
  wording the owner is asked to approve is quoted verbatim with a link to where it lives (`.forge/feature-pipeline.md`, "Every approval request links to the wording it asks about");
- **two to four options**, each with the consequence of picking it, including what happens next and who does it;
- **a recommendation** with a one-line reason;
- **a dependency mark** when the item waits on another card or task ("best decided after card <n>").

When an item's background will not fit the card, put the fuller version in one background file, linked from the summary.

Done when every kept item has one drafted card.

## 4. Post

First post one summary message:

- how many decisions are waiting, grouped as **Urgent** (work is blocked on it, or it carries a Must grade), then **Soon**, then **Later** (it waits on something else first), numbered in that order;
- each dropped item, with why it was dropped;
- each owner task from step 2;
- the link to the background file, when there is one.

Then post the cards in that order, one per item.

Done when the summary and every drafted card are posted.

## 5. Relay each answer

When the owner answers a card, send the coordinator the record in the form `.forge/process-and-evidence.md` gives: `Owner chose "<option label>" on decision card <id>, <date>`, plus any free text the owner added, and the ticket it belongs to.
When the owner answers in words instead, relay their exact words and record against the card the option they chose.
The coordinator posts the quote on the ticket and routes the follow-up (`.forge/coordinator-core.md`, "Owner approvals").

A card is answered only by the owner.
The thread is finished when every card is answered or the owner says they are done with it.
