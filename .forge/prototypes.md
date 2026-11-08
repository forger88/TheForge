# Prototypes and experiments never land on main

Throwaway code written to answer a question (a library trial, a spike, a UI variation, a proof of concept) lives on its own `prototype/<name>` branch.
The issue it serves points at the branch, and the verdict is recorded on that issue.
The decision the prototype produced lands on `main`; the prototype's code never does.
The branch is deleted once the verdict is captured.

A prototype that proves out and is wanted for real is rebuilt through the feature pipeline, never promoted.

## Why

An experiment left on `main` behind a flag bends the real code around itself for as long as it stays.
Every later change has to keep the flag's both sides working, reviewers read code that may never ship, and removing it later is a change of its own that nobody schedules.
