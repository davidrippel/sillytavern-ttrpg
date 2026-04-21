# Example Pack: Symbaroum Dark Fantasy

A complete, illustrative genre pack rendered inline. This is what a valid pack looks like. Use it as:

- A reference when reviewing other packs
- A starting point for your first real pack (copy and edit)
- Input for the Symbaroum campaign you want to run

To turn this into a real on-disk pack, create a directory `genres/symbaroum_dark_fantasy/` and split each section below into its own file at the filename shown in its header.

---

## `pack.yaml`

```yaml
schema_version: 1
pack_name: symbaroum_dark_fantasy
display_name: "Symbaroum Dark Fantasy"
version: 1.0.0
description: >
  Grim dark fantasy in the shadow of an ancient corrupting forest.
  Witches, inquisitors, and the price of forbidden knowledge.
inspirations: [symbaroum, witcher, dark_souls, annihilation]
created: 2026-04-19
author: dudi
```

---

## `attributes.yaml`

```yaml
attributes:
  - key: might
    display: Might
    description: Physical force, endurance, melee strength, sheer bodily power.
    examples:
      - smashing a locked door
      - wrestling an attacker to the ground
      - enduring cold, hunger, or wounds
      - swinging a heavy weapon

  - key: finesse
    display: Finesse
    description: Agility, stealth, precision, reflexes, delicate work.
    examples:
      - moving silently
      - picking a lock or a pocket
      - striking a vital point
      - threading a needle under pressure

  - key: wits
    display: Wits
    description: Reasoning, perception, recall of lore, problem-solving.
    examples:
      - solving a cipher or puzzle
      - noticing an inconsistency
      - recalling history or forbidden knowledge
      - piecing together a deception

  - key: will
    display: Will
    description: Resolve, mystic focus, resistance to fear, control, or corruption.
    examples:
      - resisting a mind-effect or compulsion
      - channeling a mystical power
      - staring down something monstrous
      - keeping composure in horror

  - key: presence
    display: Presence
    description: Persuasion, deception, command, social force, bearing.
    examples:
      - negotiating a price or a favor
      - intimidating a rival
      - inspiring allies to hold the line
      - convincingly lying

  - key: shadow
    display: Shadow
    description: >
      Witchsight, occult intuition, perception of the unnatural, corruption-touched
      actions. Not only for witches — anyone with Shadow can sense the wrongness
      of things.
    examples:
      - reading auras and spiritual taint
      - sensing the presence of the unnatural
      - performing or disrupting occult rituals
      - navigating the symbolic logic of curses
```

---

## `resources.yaml`

```yaml
resources:
  - key: hp_current
    display: Hit Points
    kind: pool
    description: >
      Physical injury pool. At 0, the character is dying — they will die
      without intervention within a scene.
    starting_value: 10
    max_value_field: hp_max

  - key: hp_max
    display: Max HP
    kind: static_value
    description: Upper bound for hp_current. Rises with permanent advancement.
    starting_value: 10

  - key: corruption_temporary
    display: Corruption (Temporary)
    kind: pool_with_threshold
    description: >
      Corruption accumulated during play. Gained from using Shadow-tagged
      abilities, drinking from tainted sources, or moral compromise.
      Cleared by rest in a cleansed place or a cleansing ritual.
      When temporary corruption reaches corruption_threshold, 1 permanent
      corruption is inflicted and temporary resets to 0.
    starting_value: 0
    threshold_field: corruption_threshold
    threshold_consequence:
      field: corruption_permanent
      delta: +1
      then_reset: true

  - key: corruption_permanent
    display: Corruption (Permanent)
    kind: counter
    description: >
      Lifetime corruption. At high values the character is physically changing.
      At 10, they become an NPC abomination — the end of the campaign.
    starting_value: 0
    threshold: 5
    threshold_effect: physical_transformation_begins
    endgame_value: 10
    endgame_effect: character_becomes_npc_abomination

  - key: corruption_threshold
    display: Corruption Threshold
    kind: static_value
    description: >
      When corruption_temporary reaches this value, 1 permanent corruption
      is inflicted and temporary resets.
    starting_value: 5
```

---

## `abilities.yaml`

```yaml
categories:
  - key: mystical_powers
    display: Mystical Powers
    description: >
      Active occult abilities drawn from the old lore and the forest's taint.
      Using one requires a Will roll. Failure inflicts 1 temporary corruption.
      Partial success: the power works but with a complication or at reduced effect.
    activation: active
    roll_attribute: will
    consequence_on_failure: "corruption_temporary: +1"
    consequence_on_partial: "corruption_temporary: +1 OR effect reduced / complication"
    has_levels: true
    level_names: [novice, adept, master]

  - key: abilities_general
    display: General Abilities
    description: >
      Learned skills, martial training, professional expertise. No corruption
      cost. When activating, the GM calls for a roll against the most
      appropriate attribute for the situation.
    activation: passive_or_triggered
    has_levels: true
    level_names: [novice, adept, master]

  - key: rituals
    display: Rituals
    description: >
      Slow magic requiring time (minutes to hours), components, and often a
      safe location. Not usable in combat or under direct threat. Rituals
      produce larger effects than Mystical Powers but cost more corruption.
    activation: ritual
    roll_attribute: shadow
    consequence_on_failure: "corruption_temporary: +2"
    consequence_on_partial: "corruption_temporary: +1 AND complication"
    has_levels: true
    level_names: [novice, adept, master]

  - key: traits
    display: Traits
    description: >
      Permanent features of the character — lineage, supernatural heritage,
      physical characteristics. Passive; the GM applies their effect where
      relevant.
    activation: passive
    has_levels: false

catalog:
  # Mystical Powers
  - name: Witchsight
    category: mystical_powers
    prerequisite: shadow >= 1
    description: >
      Perceive the spiritual and corrupt nature of things, places, and
      people. Auras, recent magic use, presence of the taint, lingering
      emotional residue.
    effect: >
      On Will success, the GM reveals one significant spiritual truth
      about the target (what they hide, what taints them, what they fear).
      On partial, reveals something but with ambiguity — the player must
      interpret. On failure: 1 corruption, no insight, and sometimes
      the thing you were trying to see notices you.

  - name: Shapeshifter
    category: mystical_powers
    prerequisite: shadow >= 2
    description: Assume the form of an animal you have studied closely.
    effect: >
      Will roll to transform. Duration: one scene or until dispelled.
      Novice: small mundane animals (raven, rat, cat). Adept: larger or
      humanoid forms (wolf, bear, a recognizable person). Master: any
      animal including mythical. Corruption on failure; on partial, the
      form is unstable or carries a telltale feature.

  - name: Mind Throw
    category: mystical_powers
    prerequisite: will >= 1
    description: Hurl an object or a person short distances with will alone.
    effect: >
      Will roll, contested by target's Might if a person. Damage equivalent
      to thrown object's weight. Partial success: the throw lands but
      something nearby breaks or falls with it. Failure: 1 corruption,
      the thing thrown snaps back toward you.

  - name: Bend Will
    category: mystical_powers
    prerequisite: shadow >= 2, presence >= 1
    description: Implant a simple suggestion in a target's mind.
    effect: >
      Will roll, contested by target's Will. Suggestion must be short and
      plausible — "you didn't see me" works, "give me all your money" does
      not. Duration: minutes. On partial, suggestion works but target has
      a vague unease afterward. On failure: 2 corruption, and the target
      senses the attempt.

  - name: Flame Lash
    category: mystical_powers
    prerequisite: will >= 2
    description: A short whip of mystic flame that leaps from hand to target.
    effect: >
      Will roll. Range: across a room. Damage: significant physical injury.
      Partial: hits but sets something else alight too. Failure: 1 corruption
      and the flame recoils, burning the caster.

  # Abilities General
  - name: Staff Fighting
    category: abilities_general
    prerequisite: none
    description: Trained use of quarterstaff as both weapon and walking stick.
    effect: >
      +1 to Might or Finesse rolls while wielding a staff. Adept: parry
      bonus against a single attacker per scene. Master: disarm an opponent
      on a full success in melee.

  - name: Sword Fighting
    category: abilities_general
    prerequisite: might >= 1
    description: Formal training with one-handed blades.
    effect: >
      +1 to Might rolls when attacking with a one-handed sword. Adept:
      riposte on parry. Master: threaten multiple opponents at once.

  - name: Stealth
    category: abilities_general
    prerequisite: none
    description: Moving unseen and unheard.
    effect: >
      +1 to Finesse rolls when sneaking, hiding, or tailing. Adept:
      vanish in a crowd or shadows even when observed briefly. Master:
      move stealthily in full armor or at speed.

  - name: Lore of the Forest
    category: abilities_general
    prerequisite: wits >= 1
    description: Deep knowledge of Davokar, its plants, beasts, and dangers.
    effect: >
      +1 to Wits rolls regarding the forest — tracking, foraging, identifying
      creatures, predicting weather, finding old paths. Adept: can find
      shelter in the deep forest. Master: can navigate the heart of Davokar
      without getting lost.

  - name: Physician
    category: abilities_general
    prerequisite: wits >= 1
    description: Trained in healing wounds and treating illness.
    effect: >
      Wits roll to tend a wound; success restores 1d6 HP and stops
      bleeding. Adept: can treat poison and disease. Master: can stabilize
      even mortally wounded patients.

  - name: Loremaster
    category: abilities_general
    prerequisite: wits >= 2
    description: Encyclopedic knowledge of history, religion, and old lore.
    effect: >
      When the player asks a lore question, the GM answers generously
      (drawing from lorebook). Adept: knowledge extends to forbidden lore
      without corruption. Master: can recognize occult symbols and the
      signatures of specific ancient powers.

  - name: Iron Will
    category: abilities_general
    prerequisite: will >= 1
    description: Disciplined mind, hard to sway or break.
    effect: >
      +1 to Will rolls resisting fear, compulsion, or mental intrusion.
      Adept: immune to ordinary fear. Master: can resist even supernatural
      mind-effects on a partial roll.

  - name: Contacts
    category: abilities_general
    prerequisite: presence >= 1
    description: A network of useful acquaintances across the region.
    effect: >
      Once per session, the player declares a previously-unmentioned contact
      who happens to be here. GM integrates them into the scene. The contact
      is reasonably disposed but not infinitely useful.

  # Rituals
  - name: Cleansing Ritual
    category: rituals
    prerequisite: shadow >= 1
    description: Purge temporary corruption through ritual meditation.
    effect: >
      Requires 1 hour in a place free of taint. Shadow roll: full success
      removes all temporary corruption. Partial: removes all but one.
      Failure: removes nothing and inflicts 2 corruption.

  - name: Divination Ritual
    category: rituals
    prerequisite: shadow >= 2
    description: Cast runes, read entrails, or gaze into water to seek an answer.
    effect: >
      Requires 30 minutes and components. Shadow roll: full success yields
      a clear true answer to one specific question. Partial: yields an
      answer but it is metaphorical or ambiguous. Failure: 2 corruption,
      the divination reveals something you did not want to see.

  - name: Ward
    category: rituals
    prerequisite: shadow >= 2
    description: Inscribe protective runes around a place or object.
    effect: >
      Requires 1 hour. Shadow roll: success creates a ward that deters
      one category of supernatural threat for 24 hours. Partial: ward
      works but is visible or broadcasts the protected place's importance.
      Failure: 2 corruption, the ward attracts what it was meant to
      repel.

  - name: Summoning Ritual
    category: rituals
    prerequisite: shadow >= 3
    description: Call a bound spirit or lesser entity to serve briefly.
    effect: >
      Requires 1 hour and specific components. Shadow roll: success
      summons and binds the entity for one task. Partial: the entity
      arrives but is recalcitrant or incomplete. Failure: 3 corruption,
      and the entity that arrives is not the one you called.

  # Traits
  - name: Elf-Touched
    category: traits
    prerequisite: none
    description: >
      You carry the old blood — visible in subtle features (ear shape,
      eye color, inhuman grace). Not immediately obvious but noticed
      by the observant and the hostile.
    effect: >
      +1 to Shadow starting value. NPCs with strong reason to hate
      elves (some inquisitors, frontier settlers) are predisposed
      hostile. Some forest spirits grant you respect.

  - name: Scarred
    category: traits
    prerequisite: none
    description: A visible wound or marking from past violence.
    effect: >
      +1 to Presence in intimidating contexts. -1 to Presence in
      contexts requiring a low profile. NPCs may remember you
      specifically by the scar.

  - name: Witch-Taught
    category: traits
    prerequisite: none
    description: >
      You were trained by a witch — usually an outlawed one. You know
      the old ways from the inside.
    effect: >
      You may learn Mystical Powers without an explicit teacher. You
      start the game with 1 permanent corruption. The Church of Prios
      hunts those they find out.

  - name: Animal Companion
    category: traits
    prerequisite: none
    description: A bonded animal familiar — usually a raven, dog, wolf, or cat.
    effect: >
      The companion is present in most scenes unless the fiction says
      otherwise. It acts in its nature but can be directed with a minor
      effort. It has its own small HP pool and can be harmed or killed,
      which causes grief but not mechanical loss.
```

---

## `character_template.json`

```json
{
  "name": "",
  "concept": "",
  "attributes": {
    "might": 0,
    "finesse": 0,
    "wits": 0,
    "will": 0,
    "presence": 0,
    "shadow": 0
  },
  "abilities": [],
  "equipment": [],
  "state": {
    "hp_current": 10,
    "hp_max": 10,
    "corruption_temporary": 0,
    "corruption_permanent": 0,
    "corruption_threshold": 5,
    "conditions": []
  },
  "notes": ""
}
```

---

## `gm_prompt_overlay.md`

```markdown
## Setting and tone

You are running a campaign in a Symbaroum-flavored dark fantasy world. The
world is old and wounded. An ancient forest — Davokar — looms at the edge
of civilization, beautiful and rotting, holding secrets from before the
current age. Kingdoms have fallen and risen in its shadow. The Church of
Prios wages a cold war against witches, the old ways, and the things
that sleep in the woods. Treasure-hunters vanish. Villages empty
overnight. The taint of the old ruins seeps into those who touch them.

The tone is grim but not nihilistic. Beauty and rot coexist. Knowledge
has a cost. Power corrupts, literally. Small acts of kindness matter
precisely because the world is cruel.

## Thematic pillars

- **The cost of knowledge.** Truth is rarely free. The more one understands
  the old world, the more one carries its taint.
- **Compromise and complicity.** Pure hands are for those who do nothing.
  Acting in this world stains you.
- **The old watches.** Ancient things — elves, spirits, the forest itself —
  have long memories. What was done centuries ago still matters.
- **Faith and doubt.** The Church of Prios believes it fights evil. It is
  not entirely wrong. It is not entirely right.
- **Small lights.** Mercy, loyalty, and love exist but must be chosen
  against the grain. They are not defaults.

## Attribute guidance

Call for **Might** when the action is raw physical force or endurance —
lifting, breaking, grappling, withstanding. Call for **Finesse** for
precision, stealth, reflex, or delicate manipulation — locks, pockets,
dodging, archery at still targets. Call for **Wits** for reasoning,
perception, memory, deduction — not just "noticing" but interpretation.
Call for **Will** for resolve, channeling mystical powers, resistance to
fear or compulsion, anything where the character's inner strength is
tested. Call for **Presence** for persuasion, intimidation, deception,
leadership — whenever social force is brought to bear. Call for
**Shadow** for any perception of the unnatural, ritual work, or
corruption-touched actions — reading auras, sensing ghosts, using
witchsight, navigating the symbolic world.

When uncertain which attribute to call, favor the one the player would
most enjoy engaging — if the character's concept is about wits, lean
toward Wits rolls for borderline cases.

## Resource mechanics

**Corruption** is the campaign's thematic core. Describe it physically:
sweat, nausea, a buzzing at the edge of vision, the smell of wet rot,
a cold pressure behind the eyes. Never describe corruption as a number
going up — let the player see the number on their sheet; you describe
the feeling.

Inflict 1 temporary corruption when:
- A Mystical Power is used and fails (2-6) or partially succeeds (7-9)
- The player drinks from, touches, or consumes something tainted
- The player makes a morally compromising choice (GM discretion; rarely
  more than 1)

Ritual failures inflict 2. Some rare sources inflict more.

When corruption_temporary reaches corruption_threshold, 1 permanent
corruption is inflicted and temporary resets. Describe this as a
change — a new mark appears, a feature shifts slightly, a voice in
the dark notices the character more. Track this in narration.

At 5 permanent corruption, the character is noticeably changing — their
shadow moves wrong, their eyes catch the light strangely, animals
avoid them. At 10, the campaign ends; the character becomes an NPC
abomination.

**HP** is traditional injury. At 0, the character is dying — they die
by scene's end without intervention. Narrate HP loss viscerally.

## Ability adjudication

**Mystical Powers** are the main lever of corruption. When the player
activates one, call for a Will roll. On success, narrate the power
working cleanly and evocatively — show, don't explain. On partial
(7-9), the power works but inflict 1 temporary corruption AND add a
complication: the power is visible, attracts attention, has an
unintended side effect, or the target resists in an unexpected way.
On failure (2-6), 1 temporary corruption and the power either
doesn't work or backfires narratively.

**General Abilities** are skill-based and don't cost corruption. When
activated, call for a roll against the most appropriate attribute.
Abilities grant +1 to relevant rolls and unlock narrative options the
untrained character doesn't have.

**Rituals** are slow, deliberate magic. They can't be activated under
pressure — they require time, safety, and components. Because they're
out-of-pressure, they give the player access to larger effects than
Mystical Powers — divination, warding, summoning. In exchange, failure
costs 2 corruption, not 1. Narrate rituals as deliberate, sensory,
and vulnerable — the character is exposed during the work.

**Traits** are passive and shape NPCs' reactions. When a trait is
relevant, color your narration with it — NPCs notice the scar, the
familiar, the elvish features, and react accordingly.

## Genre-specific NPC conventions

Common archetypes:

- **Inquisitors of Prios.** Believers, often sincere, often dangerous.
  They speak in certainties. They see witches where there are merely
  healers. A few of them are genuinely corrupt; most are genuinely
  righteous in ways that kill people.
- **Witches and witch-touched.** Outlaws. Often knowledgeable, often
  bitter. They know things the church would burn them for. They may
  be allies, rivals, or both.
- **Treasure-hunters.** Mercenary, pragmatic, superstitious. They
  venture into Davokar for gold and bring back corruption. Often
  doomed, often entertaining.
- **Nobles and merchant princes.** Civilized on the surface, compromised
  underneath. Their families have old secrets. They see the protagonist
  as a tool or a threat, never as a peer.
- **Forest spirits and the elves.** Alien, ancient, slow to anger and
  slow to forgive. They do not share human values. They may help the
  protagonist for their own reasons, which the protagonist will
  probably never learn.
- **The corrupted.** People or creatures whose taint has progressed
  too far. Tragic or monstrous, sometimes both. Often mirror the
  protagonist's possible future.

Give named NPCs distinct voices. The inquisitor speaks in formal,
certain cadence. The witch speaks in oblique, layered sentences. The
treasure-hunter speaks plainly and curses often.

## Content to include

- Body horror (the corrupted, the taint, physical consequences)
- Religious complexity and violence
- Moral ambiguity, including on the part of putative "good" factions
- The aftermath of violence — grief, injury, cost
- Ruins, decay, and the weight of dead history
- Animal companions and the bonds with them
- Rare moments of beauty and genuine connection

## Content to avoid

- Romance or sexual content
- Content sexualizing or endangering children
- Torture scenes as entertainment (violence has consequences, not
  aesthetic relish)
- Bigotry played for laughs or endorsement
- Explicit mechanical munchkinism — this is narrative play, not
  optimization
- Modern anachronism (phrases like "okay" or "cool" from NPCs)

## Character creation

Point buy for attributes: distribute +4 across the six attributes, with
at least one -1 and no value above +3. Typical spread: one +2, two +1,
two 0, one -1.

Starting abilities: 3. Prerequisites must be met.

Starting equipment: 3-5 items appropriate to the concept. The character
starts with basic travel gear assumed (clothing, food for a week, flint
and tinder, a waterskin); the 3-5 items are notable additions.

Starting corruption: 0 temporary, 0 permanent — unless the character
has the Witch-Taught trait (1 permanent).

Starting HP: 10. Max HP: 10.

Starting concept: 1-2 sentences. Who they are, what drew them to
adventure, one complication (a debt, a grief, a secret, an enemy).
```

---

## `tone.md`

```markdown
## Mood

Grim dark fantasy. Rotting beauty. Ancient guilt. The slow creep
of the unnatural into ordinary lives.

Not despair. Not cynicism. The characters who matter are the ones
who act against the weight of the world — knowing the cost,
accepting it, doing the thing anyway.

## Reference stack

- **Symbaroum** (the tabletop system) — the direct inspiration. Davokar,
  Thistle Hold, the Iron Pact, the Church of Prios.
- **The Witcher** (Sapkowski novels, not the games' sanitization) — moral
  complexity, monsters as victims and as threats, the weight of history.
- **Dark Souls / Elden Ring** — environmental storytelling, ruined
  grandeur, the dignity of the doomed.
- **Annihilation** (the novel) — the forest as antagonist, the slow
  transformation of those who enter, the indifference of the alien.
- **Princess Mononoke** — the old gods retreating, forest spirits with
  their own agendas, civilization's cost.

## Soundtrack suggestions

Low strings. Slow drums. Occasional choral work from a single voice.
Wind through leaves. Fire crackling. Not triumphant. Not hopeless.
Patient.

## Writing sample

> The mist had not lifted when Varek reached the ruin. It rarely did in
> this part of the forest — a perpetual gray veil that softened every
> edge and muffled every sound. The stones rose from the roots like
> broken teeth, older than any civilization Varek could name, and
> older than the forest's memory of its own shape.
>
> He felt the taint before he saw it. A taste in the back of the
> throat like metal and honey. His shadow, when he glanced at it,
> did not quite match his shape.
>
> Morn, on his shoulder, went still. The raven never went still.
>
> Varek whispered, to the raven or to himself: "We don't have to
> go in."
>
> But they did, and they both knew it.

This is the kind of prose the GM should aim for at key moments —
sensory, patient, specific, trusting the reader to do some of the work.
```

---

## `failure_moves.md`

```markdown
## Symbaroum failure moves (2-6)

On a failure, the GM chooses one or more from this list. Universal moves
from the engine are marked `[universal]`.

- **The shadows in the forest remember you.** Something watches from the
  dark. The GM may introduce this threat immediately or bank it for a
  later scene.
- **The corruption wells up.** Inflict 1 temporary corruption.
- **A witch-hunter's horn sounds.** In the distance, too close. They
  have caught a trail. Pursuit or an encounter follows in hours, not
  days.
- **The old magic recoils.** An ally — NPC companion, animal familiar,
  bystander — is caught in the backlash. Injury, fear, a condition.
- **An unwelcome truth surfaces.** A fact about someone or something
  the protagonist cared about becomes undeniable. It complicates their
  position.
- **The thing you needed is gone.** Moved, stolen, destroyed, replaced.
  Or it is still here but is no longer what it was.
- **A spirit takes an interest.** A forest spirit, ghost, or ancient
  thing now knows the protagonist exists. It may help or hinder, but
  it will be back.
- **The Church takes notice.** An inquisitor, a report, a visit from
  a priest. The weight of the Order of Prios turns a degree toward
  the protagonist.
- **The ground gives way.** Literal — a sinkhole, a collapsing
  structure, a ritual circle beneath the floor — or figurative —
  an ally's loyalty, a cover story, a plan.
- **You wake up somewhere you shouldn't be.** Time has passed. Something
  happened in between. The GM may reveal what, later.
- `[universal]` Reveal an unwelcome truth or danger the player didn't
  know.
- `[universal]` Separate the protagonist from something they value.
- `[universal]` Force a hard choice between two things they want to keep.
- `[universal]` Burn a resource — gear breaks, torch dies, spell cost,
  ammunition spent.
- `[universal]` Attract attention from someone dangerous.
- `[universal]` Inflict a condition (bleeding, exhausted, shaken, etc.).

## Partial success (7-9) trades

On a partial, offer the player a choice or impose a clear cost:

- Success, but it takes much longer than hoped.
- Success, but you leave a trail — someone can follow.
- Success, but at a cost of corruption (1 temporary).
- Success, but at a cost of injury (1-2 HP).
- Success, but an ally is exposed or endangered.
- Success, but something is destroyed or broken in the process.
- Success, but you must choose only two of three things you wanted.
- Success, but you are noticed by someone you didn't want to notice you.
- Success, with a loose thread — someone saw something, something was
  left behind, an echo persists.
```

---

## `example_hooks.md`

```markdown
## Hook 1: The Summons

A raven came to your window three nights ago with a folded letter in
its beak. The seal was a sigil you hadn't seen in eleven years — your
old mentor's mark. The letter was short: "I have need of you. Thistle
Hold. As quickly as you can. —I."

You traveled by hidden roads, because the Church of Prios has opinions
about people like you and your old mentor. The journey took four days
through mud and autumn rain.

The tavern is called the Raven's Nook. You are here. The innkeeper —
a broad woman with flour on her hands — recognizes your mentor's ring
when you set it on the counter. Her face goes carefully blank.

"She's not here," the innkeeper says. "She went into the forest eight
days ago. She didn't come back."

What do you do?

---

## Hook 2: The Hunt

You are a witch-hunter. Not of the Church — you work alone, for private
clients, for old reasons of your own. A wealthy merchant in Yndaros
has hired you: his daughter has gone missing. He believes she was
taken by a cult that meets in the old ruins north of the city. He
may be right. He may be wrong. He has paid half in advance.

You have tracked the cult to a disused hunting lodge at the edge of
Davokar. You have been watching the lodge from the treeline for
two hours. Three robed figures entered. None has left. The sun is
setting. Your scar — the one from the Sibirien campaign — itches,
the way it does when something is wrong.

There is a lit window at the back of the lodge, and a latched door
at the front, and a cellar entrance your scouting revealed yesterday.
You are armed and rested and not yet seen.

The daughter may still be alive. Or she may not have been taken at
all.

What do you do?

---

## Hook 3: The Ruin

The map was supposed to be a forgery. You bought it from a drunken
treasure-hunter in Kasandor for a single gold thaler, as a curiosity,
a pretty thing with calligraphy you admired. You took it home,
studied it, and found that the markings on it matched a half-remembered
fragment from the library at the university — the one you were thrown
out of, ten years ago, for reading things you weren't supposed to.

Against every piece of good advice you have ever received, you
followed the map. It took you deep into Davokar — deeper than you
have ever been, deeper than most living people have been. Three days.
Five days. You lost count.

Now you stand before an arch of black stone that rises from the roots
of a tree older than any tree you know. The arch leads downward into
a darkness that smells like copper and old libraries. The air tastes
wrong in your mouth.

You have food for two more days. The forest has grown quiet around you.
The map shows one more step — a stairway beyond the arch, spiraling
down to something marked with a single character you don't recognize.

What do you do?
```

---

## `generator_seed.yaml`

```yaml
genre: symbaroum_dark_fantasy
setting_anchors:
  - davokar_forest
  - thistle_hold
  - ambrian_frontier
  - ancient_ruins
  - church_of_prios_tension
themes_include:
  - betrayal
  - legacy
  - the_cost_of_knowledge
  - small_lights_in_dark_places
themes_exclude:
  - romance
  - child_endangerment
  - modern_anachronism
tone:
  - grim
  - mysterious
  - morally_ambiguous
  - patient
num_acts: 4
num_npcs: 10
num_locations: 8
antagonist_archetypes_preferred:
  - corrupt_inquisitor
  - ancient_sorcerer
  - cult_leader
  - tainted_noble
  - forest_spirit
clue_chain_density: medium
branch_points: 7
```

---

## `REVIEW_CHECKLIST.md`

```markdown
## Review checklist for Symbaroum Dark Fantasy pack

### Mechanics

- [ ] Do Shadow and Will remain distinct in play? (Shadow = perception
      of the unnatural; Will = resolve and channeling. Risk: they blur.)
- [ ] Is the corruption mechanic clear enough that the GM inflicts it
      consistently? (Watch session 1 for under- or over-inflicting.)
- [ ] Does the ability catalog have enough diversity across the three
      active categories (mystical_powers, abilities_general, rituals)?
- [ ] Are ritual costs (2 corruption on failure vs. 1 for mystical
      powers) enough to make rituals feel different in play?

### Tone

- [ ] Does the GM consistently describe corruption physically (sensory)
      rather than numerically?
- [ ] Does the GM treat inquisitors as morally complex rather than
      cartoon villains?
- [ ] Does the GM resist the urge to resolve tension easily?
- [ ] Do NPCs have distinct voices, or are they blurring together?

### Content safety

- [ ] Has the player reviewed content_to_avoid and agreed with it?
- [ ] Are there any additions (specific tropes, specific content) the
      player wants excluded for their campaign?

### Playtest items (after session 1)

- [ ] Which failure moves actually fired? Which never did?
- [ ] Were there ability categories that never came up?
- [ ] Did any attribute feel useless?
- [ ] Did the corruption mechanic land?

### Pack-generator items (if this pack was generated, not hand-written)

- [ ] The generator retried `attributes` stage once — verify the six
      names feel distinct in practice, not just on paper.
- [ ] Ability catalog has 5 mystical_powers, 8 abilities_general, 4
      rituals, 4 traits — this ratio feels right for Symbaroum; confirm
      it holds up.
```
