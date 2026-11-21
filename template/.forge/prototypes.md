# Prototypes and experiments never land on main

Throwaway code that answers a question (a library trial, a spike, a UI variation, a proof of concept) lives on its own `prototype/<name>` branch.
The issue it serves points at the branch and records the verdict.
The decision lands on `main`; the prototype's code never does, and the branch is deleted once the verdict is captured.

A prototype wanted for real is rebuilt through the feature pipeline, never promoted.

## Why

An experiment left on `main` behind a flag bends the real code around itself: every change keeps both sides of the flag working, reviewers read code that may never ship, and nobody schedules its removal.
