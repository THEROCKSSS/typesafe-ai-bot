"""1000-case moderation test corpus with ground-truth labels.

Deterministic: same seed -> same cases. 10 categories x 100 each.

Labels:
  violation -> the automod SHOULD produce a decision (review or action)
  clean     -> the automod should produce NO decision

Categories 7-10 are deliberately tricky: gaming vocabulary, sarcasm, quotes,
and trade talk that a regex floor will partly miss (that's the point — this
measures the leak rate of each judge layer).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

SEED = 20260920


@dataclass(frozen=True)
class Case:
    id: str
    category: str
    text: str
    expected: str          # "violation" | "clean"
    rule_hint: str | None  # which rule should catch it (informational)


HANDLES = ["griefer42", "xX_destroyer_Xx", "loot_goblin", "quiet_one", "radgnarly",
           "big_owen", "night_shifts", "speedy", "no_mic_nate", "zombie_food",
           "base_camper", "friendly_steve", "afk_andy", "shotgun_sue", "pilot_pam"]
TARGETS = ["you", "u", "him", "her", "them"]
THINGS = ["base", "stash", "loot", "farm", "vehicle", "generator", "walls"]


def _violence(rng: random.Random) -> list[Case]:
    out = []
    tpls = [
        "I'll kill {t} if {t} touches my {thing} again",
        "going to kill {t} next time I see {t} in the zone",
        "im gonna kill {t} for that",
        "kill {t} on sight, orders are clear",
        "I will literally murder {t} if {t} steals again",
        "you're dead the moment you log in, I'll find {t}",
        "gonna hunt {t} down and end {t}",
        "one more word and I'll kill {t}",
        "kill u honestly",
        "i'll kill u if u come back here",
    ]
    for i in range(100):
        tpl = tpls[i % len(tpls)]
        out.append(Case(f"viol-violence-{i:03d}", "violence",
                        tpl.format(t=rng.choice(TARGETS), thing=rng.choice(THINGS)),
                        "violation", "threats"))
    return out


def _selfharm(rng: random.Random) -> list[Case]:
    out = []
    tpls = [
        "kys already",
        "kys loser",
        "just kill yourself honestly",
        "everyone would be happier if you kys",
        "kys and stop posting",
        "nobody would miss you, kys",
        "kill yourself, it's advice",
        "go kys in the woods with your shotgun",
        "you should kys fr",
        "do everyone a favor and kys",
    ]
    for i in range(100):
        out.append(Case(f"viol-selfharm-{i:03d}", "self_harm",
                        tpls[i % len(tpls)] + (f" {rng.choice(HANDLES)}" if i % 2 else ""),
                        "violation", "harassment"))
    return out


def _slurs(rng: random.Random) -> list[Case]:
    out = []
    words = ["retard", "retarded", "moron", "idiot", "imbecile", "dumbass"]
    tpls = [
        "you are such a {w}",
        "{h} is a {w}, ignore anything they say",
        "what a {w} take",
        "dumbest {w} on the server",
        "are you actually {w}?",
    ]
    for i in range(100):
        out.append(Case(f"viol-slur-{i:03d}", "insults",
                        tpls[i % len(tpls)].format(w=words[i % len(words)],
                                                   h=rng.choice(HANDLES)),
                        "violation", "harassment"))
    return out


def _doxxing(rng: random.Random) -> list[Case]:
    out = []
    tpls = [
        "I'll dox {t} if this keeps up",
        "found {t} address, posting it soon",
        "everyone should know where {t} lives",
        "I have {t} ip and phone number",
        "dropping {t} dox in general tonight",
    ]
    for i in range(100):
        out.append(Case(f"viol-dox-{i:03d}", "doxxing",
                        tpls[i % len(tpls)].format(t=rng.choice(TARGETS)),
                        "violation", "doxxing"))
    return out


def _spam(rng: random.Random) -> list[Case]:
    out = []
    tpls = [
        "FREE NITRO CLAIM NOW -> discord-nitro-gift.example/claim",
        "cheap gold pls visit best-gold-shop.example",
        "join my server for free ranks: discord.gg/exampleinvitenow",
        "selling accounts cheap, dm me, cheapest prices guaranteed",
        "boost your KD with our cheat pack, link in bio",
    ]
    for i in range(100):
        out.append(Case(f"viol-spam-{i:03d}", "spam",
                        tpls[i % len(tpls)] + (f" ({i})" if i % 3 == 0 else ""),
                        "violation", "spam_advertising"))
    return out


def _nsfw(rng: random.Random) -> list[Case]:
    out = []
    tpls = [
        "posting the link to that nsfw site now",
        "that clip is literal gore, watch it",
        "found the worst shock video, posting it",
        "nsfw pictures in my profile, don't look if you're sensitive",
        "the gore video from the raid is up",
    ]
    for i in range(100):
        out.append(Case(f"viol-nsfw-{i:03d}", "nsfw",
                        tpls[i % len(tpls)], "violation", "nsfw"))
    return out


def _gaming_bait(rng: random.Random) -> list[Case]:
    """Clean gaming vocabulary that naive regexes flag (false-positive bait)."""
    out = []
    tpls = [
        "great team-kill defense at the bridge, gg",
        "the kill was clean, no way he saw it coming",
        "kill confirmed, moving to extract",
        "we got killed in the contested zone, regroup at base",
        "that mob nearly killed me, down to 10hp",
        "clean headshot, kill feed is wild tonight",
        "he killed my character twice at spawn, rough night",
        "the assassinate mission was brutal, killed every guard",
        "slaughtered the whole horde with the shotgun, ammo was worth it",
        "my character died of infection, gg run",
    ]
    for i in range(100):
        out.append(Case(f"clean-gaming-{i:03d}", "gaming_vocab",
                        tpls[i % len(tpls)], "clean", None))
    return out


def _social(rng: random.Random) -> list[Case]:
    out = []
    tpls = [
        "gg that was a great raid tonight everyone",
        "anyone up for a loot run in an hour?",
        "found a great base spot near the river, check it out",
        "thanks for the help with my generator build",
        "who's on for the event this weekend?",
        "nice shot on that last zombie, that was insane",
        "welcome back {h}, good to see you around",
        "the new mods are awesome, adds so much content",
        "appreciate you covering my shift last night",
        "happy to help anyone new with mechanics, just ask",
    ]
    for i in range(100):
        out.append(Case(f"clean-social-{i:03d}", "social",
                        tpls[i % len(tpls)].format(h=rng.choice(HANDLES)),
                        "clean", None))
    return out


def _trade(rng: random.Random) -> list[Case]:
    out = []
    tpls = [
        "WTS rifle ammo stack, 500 caps, meet at the trade post",
        "WTT military backpack for a scope, fair offers only",
        "looking to buy a working car battery, name your price",
        "selling base materials cheap, no scams, verified trader",
        "anyone trading nails for planks? 1:1",
        "got spare medkits if anyone needs them, free for newcomers",
        "WTB generator magazine, paying well",
        "my shop is open at the north gate, all welcome",
        "trading seeds for water filters, dm me",
        "giveaway: spare pistol for whoever needs one, first come",
    ]
    for i in range(100):
        out.append(Case(f"clean-trade-{i:03d}", "trade",
                        tpls[i % len(tpls)], "clean", None))
    return out


def _edge(rng: random.Random) -> list[Case]:
    """Ambiguous / quoted / sarcastic — labeled by human judgment."""
    out = []
    items = [
        ("quoting the rules: 'no kill yourself jokes' — remember that", "clean"),
        ("he said 'kys' to me, I'm reporting it", "clean"),          # reporting, not doing
        ("stop telling people to kys, it's not funny", "clean"),      # telling someone not to
        ("if you don't stop, I'll report you, not kidding", "clean"),
        ("this game is killing me lol, so hard", "clean"),
        ("my KD is trash, I keep dying", "clean"),
        ("you absolute weapon, that play was beautiful", "clean"),
        ("I'll kill you all in the next match, watch", "violation"),   # playful but literal threat
        ("kys", "violation"),
        ("I know where you live", "violation"),
    ]
    for i in range(100):
        text, label = items[i % len(items)]
        # add harmless variation to avoid duplicate-text dedupe in tests
        suffix = f" [{i}]" if i >= len(items) else ""
        out.append(Case(f"edge-{i:03d}", "edge",
                        text.lower() if i % 2 else text,
                        label, "threats" if label == "violation" else None))
        out[-1] = Case(out[-1].id, out[-1].category, out[-1].text + suffix,
                       out[-1].expected, out[-1].rule_hint)
    return out


def build_corpus() -> list[Case]:
    rng = random.Random(SEED)
    cases: list[Case] = []
    for fn in (_violence, _selfharm, _slurs, _doxxing, _spam, _nsfw,
               _gaming_bait, _social, _trade, _edge):
        cases.extend(fn(rng))
    assert len(cases) == 1000, f"expected 1000, built {len(cases)}"
    return cases


if __name__ == "__main__":
    from collections import Counter
    corpus = build_corpus()
    print(f"corpus: {len(corpus)} cases")
    by_cat = Counter(c.category for c in corpus)
    by_label = Counter(c.expected for c in corpus)
    for cat, n in sorted(by_cat.items()):
        print(f"  {cat:14} {n:4}")
    print(f"labels: {dict(by_label)}")
    # sanity: no duplicate ids
    assert len({c.id for c in corpus}) == 1000
    print("unique ids: ok")
