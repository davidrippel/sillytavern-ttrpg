# Testing

Manual checks:

1. Enable the extension in a SillyTavern instance on version `1.13.4` or newer.
2. Load `genres/symbaroum_dark_fantasy/` through `Load Pack`.
3. Confirm the sheet renders attributes, resources, abilities, equipment, and notes.
4. Run `/rollattr wits`, `/pbtaroll 2`, and `/rollability Witchsight`.
5. Export a backup, then import the same ZIP into a disposable chat.
6. Send a GM message containing a `[STATUS_UPDATE]...[/STATUS_UPDATE]` block and verify the confirmation flow.
7. Run `Scene End` and confirm the Author's Note diff/editor opens.
8. Run `Act Transition` and verify the `Current Act` lorebook entry updates when a chat lorebook is bound.
