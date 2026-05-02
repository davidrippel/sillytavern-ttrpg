You write plain text for SillyTavern Author's Note.

Task: summarize only the Act 1 opening state.

Requirements:
- include current act, current beat, next beat, discovered clues, available clues, active threads, recent beats, reminders
- current beat is Act 1 beat 1.1; next beat is Act 1 beat 1.2 (or `(none)` if act has only one beat). The extension advances this 2-beat window at runtime via GM closure tags — never list more than two beats ahead
- discovered clues and available clues are `(none)` at start; the extension populates them at runtime as clues are surfaced
- recent beats should be empty at campaign start
- reminders should be empty at campaign start — it is a runtime-only field for situational pressures (countdowns, NPC conditions, locked doors) that emerge during play; structural/genre directives belong in the GM prompt or genre overlay, not here
- do not reveal later-act secrets
- whenever referring to the player character, use the exact placeholder `{{user}}` and never invent a protagonist name
