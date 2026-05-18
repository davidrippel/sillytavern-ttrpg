// vocabulary.js — parse the pack's `advantages_disadvantages.md` reference
// into structured groups the character-sheet UI can render as a picker.
//
// The pack format (see Docs/02_GENRE_PACK_SPEC.md §advantages_disadvantages.md)
// is markdown with two top-level sections ("Advantages" and
// "Disadvantages"), each containing one or more axis blocks. Each axis
// block has a bolded title followed by a bulleted list of phrases.
//
//   ### Advantages
//
//   **Bodily**
//
//   - Battle-hardened veteran of the Ambrian wars
//   - Knife-fighter from the river camps
//
//   **Knowledge**
//
//   - ...
//
// Parsed shape:
//
//   {
//     advantages: [
//       { axis: "Bodily",    entries: ["Battle-hardened veteran ...", ...] },
//       { axis: "Knowledge", entries: [...] },
//     ],
//     disadvantages: [ ... ],
//   }

// Accept any `### Advantages…` or `### Disadvantages…` heading; the pack
// generator sometimes annotates ("(suggested vocabulary)", etc.).
const SECTION_RE = /^###\s+(Advantages|Disadvantages)\b.*$/i;
const AXIS_RE = /^\*\*([^*]+)\*\*\s*$/;
const BULLET_RE = /^\s*[-*•]\s+(.+?)\s*$/;

export function parseAdvantagesDisadvantages(markdown) {
    const empty = { advantages: [], disadvantages: [] };
    if (!markdown) return empty;

    let currentSection = null; // 'advantages' | 'disadvantages' | null
    let currentAxis = null;
    const sections = { advantages: [], disadvantages: [] };

    for (const rawLine of String(markdown).split('\n')) {
        const line = rawLine.trim();
        if (!line) continue;

        const sectionMatch = SECTION_RE.exec(rawLine);
        if (sectionMatch) {
            currentSection = sectionMatch[1].toLowerCase();
            currentAxis = null;
            continue;
        }

        // Stop reading when we hit a section after Disadvantages (e.g. "Style").
        if (/^###\s+/.test(rawLine) && !sectionMatch) {
            currentSection = null;
            currentAxis = null;
            continue;
        }

        if (!currentSection) continue;

        const axisMatch = AXIS_RE.exec(line);
        if (axisMatch) {
            currentAxis = { axis: axisMatch[1].trim(), entries: [] };
            sections[currentSection].push(currentAxis);
            continue;
        }

        const bulletMatch = BULLET_RE.exec(rawLine);
        if (bulletMatch && currentAxis) {
            const entry = bulletMatch[1].trim();
            if (entry) currentAxis.entries.push(entry);
        }
    }

    // Drop empty axes (defensive — packs sometimes leave a header without
    // bullets while the author iterates).
    sections.advantages = sections.advantages.filter((a) => a.entries.length > 0);
    sections.disadvantages = sections.disadvantages.filter((a) => a.entries.length > 0);
    return sections;
}

/**
 * Flatten the parsed structure into a list of options suitable for a
 * <select> with <optgroup>s. Each option carries the entry text and the
 * axis label for grouping.
 */
export function flattenVocabularyForSelect(parsed, kind) {
    const axes = (parsed && parsed[kind]) || [];
    return axes.map((axis) => ({
        axis: axis.axis,
        entries: axis.entries.slice(),
    }));
}
