# Brandolini’s Reference

> *A little learning is a dang’rous thing;*
> 
> *Drink deep, or taste not the Pierian spring.*
> 
> *There shallow draughts intoxicate the brain,*
> 
> *And drinking largely sobers us again.*
> 
> 
> - Alexander Pope, 1711
> 

This chapter serves as a helpful reference for developers, users and community members living in an Age of Bullshit Manufacture equivalent to the Cambrian Explosion.

As we are surely only at the on-ramp of this trajectory, the chapter will continue to evolve, expand and be updated based on community feedback as events occur.

## What The Reticulum License Is

The [Reticulum License](license.md#license) is the license under which RNS, the Reticulum reference implementation, has been published since **April 15, 2025**, in versioning effective from **0.9.4** and every release since. In practical terms, it covers all of “modern Reticulum”: The current wire format, the cryptographic machinery as it exists today (including the AES-256-based link encryption, ratchets, et cetera), and all protocol additions that distinguish the modern implementation from the earliest pre-1.0.0 beta formats. If an implementation speaks today’s Reticulum protocol, it is, in all relevant respects, built on Reticulum-licensed work.

The license is a permissive license. It grants the full range of rights to use, copy, modify, merge, publish, distribute, sublicense, and sell the software, free of charge; subject to three conditions, which are reproduced here verbatim:

> * The Software shall not be used in any kind of system which includes amongst its
>   functions the ability to purposefully do harm to human beings.
> * The Software shall not be used, directly or indirectly, in the creation of an artificial
>   intelligence, machine learning or language model training dataset, including but not
>   limited to any use that contributes to the training or development of such a model or
>   algorithm.
> * The above copyright notice and this permission notice shall be included in all copies or
>   substantial portions of the Software.

### Why This License Exists

Reticulum was not moved to a custom license casually or quickly. It was licensed under the MIT license for the greater part of its existence, and that served well for a long time. The change came when it became clear that no existing license expressed what the project needed, and that the two most commonly proposed alternatives would either say the wrong thing or say nothing useful at all. Three factors had primary influence on the situation:

**The harm problem**

Reticulum is a tool that was built, deliberately and at great cost, to empower people; to make communication something you own rather than something you are temporarily granted. It has also been, at various times, exactly what certain kinds of organisations would like to use to control people. This is the duality of any powerful tool. A permissive license could not, and cannot, say anything about that; MIT is silent on the question of whether the software may be used to build systems designed to harm human beings. The Reticulum License is not silent. It does not pretend that a license can stop an individual madman; it does assert, however, plainly and in enforceable terms, that corporations and organisations integrated into the legal system cannot consume this software for harm and then claim they never knew. The line is drawn by the creators of the tool, not by an external authority, and it is drawn deliberately. This is covered in more depth in the discussion of the ethics of the tool in the *Zen of Reticulum*.

**The appropriation problem**

The second factor was the machine-learning appropriation of the open-source commons. By 2025 that was no longer hypothetical: The commons was already being systematically ingested by corporate training pipelines, and the code, words, and creativity of the people who built it were being converted into synthetic systems designed to replace them. The license responds to this with an explicit condition: The software shall not be used in the creation of an AI, machine-learning, or language-model training dataset, nor in any use that contributes to the training or development of such a model or algorithm.

It is important to understand what this condition does and does not do, which matters for what follows in this chapter. **The AI-training condition is not the legal basis for protecting the code from machine copying**. That protection *already exists*, in the oldest and most well-tested form of copyright law, and it applies regardless of any license (see [Copyright & The Two Legal Layers](#brandolinis-copyright-and-layers)).

The AI-training condition addresses something *additional*: the appropriation of the code *into the models themselves*; the ingestion of human-made work as raw material for a synthetic replacement, and the use of that ingestion to fabricate “prior work” minefields, patent-troll material, and a wall of slop meant to bury and devalue the actual ecosystem. That danger was foreseeable; the licensing decision was made with full awareness of it. The events of 2026 have since demonstrated, in public and in detail, that the concern was not theoretical.

**The sustainability problem**

Reticulum has been developed and maintained for over a decade by a single person, supported by a small group of contributors and network-building users, without corporate backing, without VC funding, through several serious attempts at commercialization and takeover from both the corporate and the ideological side. The license is part of what makes that sustainable, and possible at all.

It ensures that the specific, painstaking labor of the reference implementation cannot be hijacked to undermine the intent of the project, while leaving the protocol itself, the mathematical rules of how Reticulum works, dedicated to the public domain, where it belongs to humanity and can never be owned. Anyone can implement the protocol, provided they themselves invest the *actual* work and effort. What the license protects is the work, and the intent embodied in it.

### On Freedom

The most persistent mischaracterisation of the Reticulum License is that it is “more restrictive” than the licenses it replaced or than the GPL family. This is backwards, and I’ll state the comparison plainly, because the confusion is the foundation of a great deal of deliberately manufactured controversy examined later in this chapter.

The GPL and AGPL are constructed around a single, self-referential axiom: that “free” is *defined by the terms of the license itself*, and that any use falling outside those terms is not free. In practice, this means the GPL restricts the freedom of **everyone** - you may not write, distribute, link, or (in some cases) even communicate with GPL-covered software without the entire arrangement being pulled under the same terms, which the licensor then controls. The restriction applies to 100% of users, including the ones building purely constructive things.

The Reticulum License restricts the freedom of almost nobody. Its restrictions apply only to:

* Those who wish to use the software in systems that purposefully harm human beings, and
* Those who wish to ingest the software into AI training pipelines.

That is a restriction on a vanishingly small fraction of would-be users - the 0.0000001% - and it is a restriction they can characterise however they like, forever. The bickering is itself a signal that the licensing decision hit exactly the right target.

Everyone else retains the full breadth of use, modification, distribution, and sale, with none of the viral encumbrance of copyleft.

Both licenses contain moral axioms. The difference is that the Reticulum License states its axioms out loud:

* *Intentionally restricting the way that millions of people use and build upon a foundational
  communications technology* - **The mechanism of copyleft**
* *Intentionally restricting a small number of organisations from using the technology to
  violently harm human beings* - **The mechanism of the Reticulum License**

Which of these is more free? The answer is not a matter of committee approval. It is a matter of what the word “free” means to the people *whose freedom is at stake*. The question of whether “open source” requires the blessing of a particular licensing orthodoxy is examined in [Open Source Means Open Source](#brandolinis-opensource).

### The Prediction, And What Happened

When the license change was made and publicly discussed in 2025, the following was said, in public, about the machine-learning threat:

> A generative system could be trained on the Reticulum codebase, and for extremely low cost
> be set to work spewing out millions of source repositories for all kinds of ridiculous
> “Reticulum-based programs”. This is already happening. You can find several examples of this
> on GitHub already. … the point of this kind of trolling is to establish as wide a base for
> “prior work” as possible. By doing that, a patent troll or IP abuser can create an immense
> minefield for real developers.

This was written when the phenomenon was just beginning. It was not a guess; it was a description of a mechanism already in motion, in the specific context of Reticulum, by people who had already begun to appear around the project.

Less than a year and a half later, the prediction has now been demonstrated, in public, exhaustively and to the letter. There are now roughly a dozen machine-generated “Reticulum implementations” of the same shape: fluent, marketing-heavy, some without attribution, and - in several cases - actively harmful to the network. The [Prns case](#brandolinis-prns) is an example documented in this chapter. The pattern that produced it (and the people, mechanisms, and the recycling of falsehoods behind the *wider* phenomenon) is examined in [A Movement Of A Dozen](#brandolinis-movement-of-a-dozen).

The license was written, in part, so that when this happened, the community would not be defenceless.

### What This Means For Other Implementations

Two simple things must be kept separate:

1. **The protocol is public domain.** The mathematical rules of Reticulum - addresses,
   signatures, routing, the wire format as an idea - belong to humanity. A *genuine* clean-room
   implementation of the protocol, written by human beings who reasoned it out themselves, is
   free and welcome, and owes nothing to the Reticulum License. Nothing in this chapter is an
   argument against implementing the protocol. On the contrary: More good implementations,
   honestly made, are good for the network.
2. **The implementation is licensed.** Copying the reference implementation - by machine or
   by silk-screen press - and modifying and redistributing the result, is
   exercising rights granted by the license, and is therefore subject to its conditions: The attribution
   notice, the harm condition, the AI-training condition. A copy that does not follow those
   conditions is **not** licensed, and it is not “open source in spirit”; it is an unauthorized
   derivative work, and therefore a copyright violation.

The distinction is the same one the license itself makes, and it must be held firmly: An implementation that *speaks* Reticulum is exercising the public domain protocol, **if** it was truly created independently. An implementation that was *generated from* RNS, reproduced by a copy process, is a derivative of licensed work.

### Copyright & The Two Legal Layers

The exact legal structure is frequently muddied in public discussion; and in several cases deliberately.

**Layer A - Copyright (license-independent)**

Copyright does not depend on any license. A primarily machine-generated copy of a copyrighted work - a copy not accompanied by demonstrable, substantial, new human creative input - is a derivative work over which the copier holds no copyright whatsoever, and the reproduction of which, without the original author’s permission, is an infringement of the original author’s copyright. This is standard, well-tested law, and it applies with equal force under the MIT license, the GPL, or any other license, because it is not about the license at all; it is about who created what. A process that copies the reference implementation into a machine, produces a transformed derivative, and then claims “Copyright, [name of the process operator]” - with no human able to account for the creative decisions in the result - **is not** asserting a valid copyright over the result. They are openly asserting the absence of one, and reproducing someone else’s work without authorisation. This is probably the cleanest cut copyright violation one could imagine.

**Layer B - License Conditions (Reticulum License specific)**

Where a copy *is* a licensed derivative, the conditions of the Reticulum License apply: The copyright notice and permission notice must be included in all copies and substantial portions; the harm condition must be honoured; the AI-training condition must be honoured. A derivative that follows none of these is unlicensed *a second way over*.

The two layers are often intentionally confused in public discussion - the AI-training condition is waved around as if the entire question of machine copying rested on it, when in fact machine copying of copyrighted work is a copyright violation that would exist even under the most permissive license ever written. The purpose of keeping the layers separate is not rhetorical flourish; it is that Layer A is old, settled law, and does not rely on any novel legal theory, while Layer B is specific to this license. Both matter. Neither is a substitute for the other.

Layer B is the required mechanism for closing the loophole where the work is *first* ingested during model training into the weights of a model itself, which would make any resulting violations almost impossible to detect and enforce.

### The “Clean-Room” Delusion

I regularly receive mail or LXMF messages from people who proudly and happily proclaim that they have created a “clean-room” implementation of one of the software systems I maintain; RNS, Sideband, LXMF or others. The declaration is delivered with the flat certainty of someone who believes they have found the legal lock-pick that settles everything at once: Their production is independent, uncontaminated, and therefore free of any obligation to the work they copied, its license, or its author. The proclamation usually concludes with a request for blessing, or at least acknowledgment. The proclamation is, usually, also generated by an LLM.

This is a delusion, and I’ll cut through it surgically. The word they here invoke as magic is attempting to do a great deal of work it was never able to bear.

**What a clean room actually was**

The legal “clean room” is not folklore, incantation, witchcraft or a claim a person gets to make about their own output. It is a very specific, institutionalized procedure that grew out of the hardware and software litigations of the 1980s, and it existed for exactly one purpose: **Convincingly proving the absence of copying in a court of law**.

The canonical case was Phoenix Technologies and its 1984 reimplementation of the IBM PC BIOS. IBM’s BIOS was copyrighted, which meant that the entire PC-compatible industry depended on being able to show that a compatible BIOS had been written independently, and not from IBM’s code. Phoenix’s answer was a physical and procedural firewall:

* One team, the “dirty room”, read the original code and produced written *functional specifications*: descriptions of what the BIOS did, not how IBM’s code did it.
* A second team, the “clean room”, consisted of engineers who had *never seen the original code at all*, and they wrote the new BIOS from those specifications alone.

This obsessively documented, legally attested separation was not a preference or a willy-nilly show for a kindergarten; it was the entire legal point, and it had to be *solid*. If even one clean-room engineer had *glanced* at IBM’s code, the clone would have been contaminated, and the defense would shatter.

The other landmark case was *Computer Associates v. Altai* (1992), in which Altai had copied CA’s scheduler code into its own product, and (upon being caught) hired outside counsel to run a genuine clean-room procedure: A programmer with no exposure to the original was brought in to rewrite the infringing modules from functional specifications prepared by the team that had seen the code. The court credited the good-faith effort precisely because it was done, as the carefully documented record showed, to the letter of the procedure.

Bear in mind what this procedure entailed in practice, because this is the part the modern claimants never seem to have even *heard* of: Physical separation of teams, legal counsel managing the process, signed and notarised declarations of non-exposure, controlled specification documents that described *behaviour* and never *code*, months of work, and testing against the specification - not against the original, which the implementers were forbidden to consult.

The people on the clean-room side of the wall did not just *claim* they had not read the code. Their non-exposure was institutionally guaranteed, obsessively documented, and legally attestable through every fart and sneeze of the process, because the entire point was that a court - hostile, adversarial, and entitled to discovery - would believe it.

*That* is the process. “Clean-room implementation” is the name of a *certified procedure for proving independent authorship*. It is not a mood, a marketing label, or a property a person gets to declare about their own work.

**The moronic inversion**

Now consider what is actually being described when someone says:  *“I created a clean-room implementation of Reticulum by feeding the source code into a machine.”*

That sentence is the opposite of a clean room. Feeding a copyrighted work into a machine so that it reproduces and transforms the work is **the definition of copying**, and a clean room is the one procedure whose entire purpose is the demonstrated *absence* of copying. This process cannot demonstrate the absence of copying, because the process is *composed of* copying. The cleanest possible room has been replaced by the dirtiest possible room, and the dirt has been installed as the base feature. What these claimants have actually performed is a photocopy with extra steps, and the extra steps, far from cleaning anything, are simply steps that forge a certificate they believe the output has earned.

**Why the word is deployed**

The word “clean-room” is deployed because it sounds like what the speaker wishes were true. It carries the accumulated legal prestige of the 1980s and 1990s - the BIOS clones, the Altai credit - and it sounds like a certificate already issued: *Independent, original, unencumbered*, the work of a person who owes nothing. The claimants want that halo without the procedure: No law firm, no physical separation, no written specifications, no signed declarations, no months of process - just a laptop, a loop, and the word “clean-room” typed into a README. The word must do the work of the process it replaces, and the delusional replacement is the entire point.

**The irony runs deep**

The Reticulum protocol is public domain. Any human being can implement it - from the mathematics, from the documentation, from their own reasoning - and owe nothing whatsoever to the license, to the reference implementation, or to me.

An honestly written implementation needs no incantations, no legal theater, and no special vocabulary; it simply *is* what it claims. It’s plain for everyone to see. **It’s also plain for everyone to see when you’re faking it**. The people who reach for the word “clean-room” are, without exception, the people who need it to create a fantasy - and the people who need that are precisely the people who cannot have it. If what you wrote were genuinely independent work on the public-domain protocol, you would not need to call it anything. The word is not a seal of independence. In this context it is a confession of copying, filed by the copier, in the confident belief that it says the opposite.

## Open Source Means Open Source

An objection regarding the “open source status” of RNS appears occasionally in variations, but always reduces to the same syllogism:

1. “Open source” means *licensed under one of the licenses approved by the Open Source
   Initiative (or, in other variants, compatible with GPL orthodoxy)*.
2. The Reticulum License is not on that list.
3. Therefore Reticulum is not open source, and anything built on it is illegitimate.

The entire argument rests on the first premise, and the first premise is false.

Open source is not a certification conferred by a committee. It is a description of a fact: The source code is available, and the rights to use, copy, modify, merge, publish, distribute, sublicense, and sell it are granted to everyone, free of charge.

The Reticulum License does all of those things. It is, in every substantive respect that concerns the person who wants to use, study, modify, or build upon the software, **an open license**. What it adds - and what disqualifies it in the eyes of the orthodoxy - is two conditions on *who may do what with the original work*, not on what the *user* is allowed to do with it.

The definition being wielded against Reticulum is not even a young one. It is, in essence, the Debian Free Software Guidelines written in 1997, adopted by the OSI in 1998, and treated ever since by certain people as if it had descended from a mountain on tablets. It is an approach that is close to three decades old. Being old is not itself a flaw - but being old is also not a proof of correctness, and the suggestion that the meaning of a word like “open” was settled for all time by a committee in the 1990s, and may never be revisited, is not a position rooted in reason. It is rooted in institutional inertia dressed as principle, maintained by those whose ideologies it serves.

### What The Argument Is Actually Doing

I would like to go into some detail about the rhetorical mechanism, because it is roughly the same mechanism that powers the rest of the campaign described later in this chapter.

The orthodoxy’s argument is self-referential:  *“open source means what we say it means, because we are the ones who define it.”* When the Reticulum License is measured against that definition and found wanting, the conclusion is presented as a property of Reticulum - when in fact it is *a property of the definition*. The definition is treated as neutral and authoritative - as some base fact of raw cosmology - and the license is treated as deviant. But the definition is no more neutral than the license is. It encodes a moral position, and that moral position is exactly the one that this project declines to take.

Consider what the orthodoxy’s definition requires, in the case at hand. The OSI-based definition contains, in its ancestry, the Debian Free Software Guideline of “No discrimination against fields of endeavor”: The software must not restrict who may use it or for what purpose. Taken to its logical end, this means that open source, properly “certified”, must be equally available to those who build hospitals and those who build weapons, those who connect people and those who control them, those who create and those who ingest and replace.

The orthodoxy presents this as neutrality. It is not neutrality; it is a moral position - one that says, in effect, that *harming human beings is a field of endeavor like any other, and software must not discriminate against it*.

The Reticulum License takes a different position, and it has the honesty to state it in the license text: this software is for life, not for death; it is for people, not for the systems that would replace them. That is not a restriction on openness, nor on freedom. It is a restriction on *who may consume the work*, and it is a restriction the orthodoxy’s definition cannot express - which is why the orthodoxy must always attack the license as “not open source” rather than engage with what it actually does.

### Who Is Restricted By Which License?

The arithmetic is simple, so let’s do it out loud, because the orthodoxy’s framing inverts it every time.

The GPL family imposes its conditions on **everyone**: You may not distribute, link, or - in the AGPL case - even *communicate with* GPL-covered software without your own work being pulled under the same terms. “Free” in this system is defined (self-referentially) *by the license’s own terms*; everything outside those terms is, by definition, unfree. The restriction applies to 100% of users. It applies to the hospital, the mesh community, the school, and the hobbyist with the same force it applies to anyone else. That is not freedom for everyone; it is a *specific moral architecture applied to everyone*, presented *as if it were the absence of one*.

The Reticulum License imposes its conditions on a fraction of would-be users so small as to be practically unmeasurable:

* Those whose intended use is to build systems that purposefully harm human beings, and
* Those whose intended use is to ingest the work into AI training pipelines.

That is the entire list. Everyone else - the overwhelming majority, the community, the developers, the users, the downstream projects - receives the full, unrestricted rights to use, copy, modify, merge, publish, distribute, sublicense, and sell the software, with none of the viral encumbrance of copyleft.

So when the claim is made that the Reticulum License “is more restrictive” than the GPL, the claim is not merely wrong; it is the exact inverse of the truth. The GPL restricts the freedom of everyone, in the name of a specific ideology. The Reticulum License restricts the freedom of the harm-doer and the appropriator, and leaves everyone else free. The two approaches do not differ in whether they contain moral axioms - **all licenses do**. They differ in whether the axioms are stated openly, and in *whose* freedom they restrict.

### The Consequences Of The “Not Open Source” Claim

This would be a footnote debate if the mischaracterisation had no practical consequences. It has very large ones, and therefore this section exists.

The claim that “Reticulum is not open source” is the foundation of the takeover narrative it so often accompanies. The sequence is always the same:

* First, declare the reference implementation illegitimate (“not really open source”, “owned by one man”, “not a real community project”)
* Second, conclude that it is therefore acceptable - even necessary - to replace it.
* Third, present the replacement, which is (conveniently) often the speaker’s own machine-generated clone, as the legitimate heir.

This is not speculation about motives; it is the documented structure of the campaign examined in [A Movement Of A Dozen](#brandolinis-movement-of-a-dozen).

The “not open source” claim is the legal-ideological battering ram of that campaign. It is recycled, in article after article, in forum after forum, because it works on people who assume that a committee’s definition is the same thing as the truth.

It is also worth stating the other obvious fact: None of these critics have ever shown that the Reticulum License restricts *them*. They do not build weapons. They are not training models on the codebase. They are free, in every practical sense, to use Reticulum exactly as they would under MIT or GPL. Their objection is not to a restriction on themselves; it is to the *mere existence* of a license that states a moral position they disagree with, or which they can use as leverage for a different goal entirely, and to the institutional fact that it does so outside *their* system of approval and control. The complaint is not that the license makes them unfree. The complaint is that the license is *free of them*.

### The Distribution Argument

A recurring companion claim is that RNS is not properly “distributed”, usually deployed as “it’s not packaged as a .deb” or “it’s not on package manager X”, with the implication that it is somehow unavailable or inaccessible, or hard to install on a given system.

This is simply false, and it has been false for years. The reference implementation is available on practically every platform and architecture with a single command (`pip install rns`). It is packaged in the Arch User Repository, in NixOS, and in a range of other distribution channels, community-maintained and official. It can be installed, updated, and kept current *over Reticulum itself* - the network transports its own software updates. It is used on more than a hundred thousand devices worldwide, is embedded in over a hundred other packages and applications, and carries terabytes of traffic every day.

The claim that Reticulum needs a `.deb` to be “really distributed” mistakes the mechanism for the goal. The goal is that people can obtain and update the software easily, everywhere, **on their own terms**, and distribute it themselves, both offline, online and over Reticulum with full cryptographic verification of the install packages, without any central infrastructure.

That goal is met to an excellence that few software packages can speak of, and met in a way that does not pin the project’s release cadence to the review cycles of distribution maintainers, which is an achievement, not a bug.

A project like RNS that updates continuously, sometimes daily, and has a track-record of shipping security updates mere hours after issues are discovered, would be crippled by packaging that makes every change wait months for approval. The distribution complaint is a strawman generated for the occasion. It has been answered, in public, many times; it is repeated anyway, because the people repeating it are not counting on facts - they are counting on the reader never having heard the answer.

### On The Institutions, In Fairness

None of the above is hostility toward the Open Source Initiative or the Free Software Foundation as institutions, nor toward the individuals who have dedicated decades of work to them. Their contribution to the world of software is **enormous**, and this document does not dispute it. What is disputed is a specific claim of authority: That “open source” is a term whose meaning is reserved to a committee’s approval, and that a license which does not submit itself to that approval is therefore not open.

That claim of authority is not in Reticulum’s interest, and it is not in the interest of the people the movement claims to serve. The current legal and technological landscape - the machine-appropriation of the commons, the weaponisation of “prior work” generation, the  erosion of human agency by synthetic systems - was not anticipated by the DFSG of 1997, and  the institutions have not, as of this writing, produced *any* meaningful answer to it. The choice, as it was put at the time of the license change, is whether developers should sit back and  wait for a solution from a committee that “may or may not ever materialize, before the entire foundation we stand on has been eaten away”.

**Reticulum’s answer was to act**. If we had waited, it would have been too late.

If an OSI-approved license existed that expressed the same constraints - and did not impose the far more severe restrictions of copyleft - the project would have used it. None such exists. That is not Reticulum’s failure. It is the measure of what the definition is missing.

### What “Open” Means Positively

For anyone who wants the positive statement rather than the rebuttal, Open Source, in this project’s understanding, means:

* The source code is available, to everyone, without charge
* Everyone may use, copy, modify, merge, publish, distribute, sublicense, and sell the
  software
* No one is discriminated against as a person - developer, user, community, or project
* The protocol itself is dedicated to the public domain, where no one can own it
* And the single, plainly stated condition of the license is that the work shall not be
  consumed to harm human beings, or ingested to replace the humans who made it

If that is not “open” by a definition written in the 1990s, then the definition is the thing
that has failed - not the software, and not the people who use it.

**Open source means open source**. It was true before the committees existed to certify it, and it will remain true after they are gone.

## Assistance Versus Machine-Substitution

### False Dichotomy

The public discussion around machine learning and software development has been derailed, by the loudest voices on both sides, into a farcical fight between “AI enthusiasts” and “AI haters”.

> **Both positions are absolute caricatures.**

> **The fight is beside the point in the ways that matters most.**

It is not an accident, but a very conscious choice that the initial analysis of the Prns case examined herein, and this very chapter, were themself produced with the assistance of a machine-learning based generative system.

Specifically, it was generated using `lc` managing a `Q8_K_XL` quant of `DeepSeek v4 Flash` running in the `llama.cpp` inference engine. The main context base used to stabilize, ground and inform the generative environment consisted of approximately 100,000 tokens of text material that I personally thought out and wrote (by hand), then archived and organized, over the last eight years.

If you know my writing, and have a hard time discerning where this chapter is me directly, typing manually, and where it is the machine output, it is because of two things: Almost every line in this chapter was either directly edited by my hands on the keyboard or typed by me, and the text corpus that informed the process *is* genuinely me - my thoughts, written by me, over a period of years.

The chapter was produced this way *deliberately and openly*, under a software framework I designed and wrote, with the human directing the inquiry points, flow of investigation, structure of the outputs, contents of every section, making the editorial decisions, reviewing the conclusions, painstakingly adjusting every line, and taking responsibility for the final claims presented, with the goal of reaching a higher level of synthesis and symbolic density than I could have achieved without that assistance.

The tool was *used as tool*, both to structure and produce a complex chapter, and to inspect a repository so preposterous in size, commit velocity and nonsensical wording that it barred any purely human inquiry.

As such, the position is hereby, by personal example and demonstration, stated clearly:

* **Technological assistance is not the problem**

* **It was never the problem**

* **It is the opposite of the problem**

The problems are *substitution* and *usurpation*: The perverse process in which the machine becomes the author of choices, and the human becomes the facade of software, while expecting “reciprocity” or recognition for deeds they never performed.

### The Line

The exact distinction can be reduced neither to how many lines of code a machine produced, nor who pressed the keys. The final distinction has to rest on **who, or what, the real agent of the work is**.

* **Assistance** is when the human retains the full seat of agency: The human decides what to build, judges
  what is correct, rejects what is wrong, understands what is shipped, and can answer for every single line of it.
  The machine writes, suggests, drafts, accelerates *meaningfully* and within reason - but every choice that survives into the
  final work is a choice the human made *consciously*, and understood - or grew to understand - the consequences of.

* **Substitution** is when the machine *becomes* the agency: the machine decides what to build,
  decides what is correct, iterates on its own errors, generates at a scale and speed no single
  human can follow - and the human’s role is reduced to providing the name, the account, the
  signature, and the marketing launch.

> The Line can be stated as a single test, and this is the same test that has always separated authorship from couriership: **Can the person whose name is on the work answer for it fully?** Not “can they describe what it does” - can they account for why it is the way it is, line by line and decision by decision, and the history of how it came to be that way, under questioning, without machine assistance, including by people who know more than they do?

If they cannot, they did not author the work. They wore it, or in more severe cases, they stole it. And a courier who claims authorship is not a writer; they are a fraud.

### What assistance looks like

Assisted work is recognisable, and recognisability is itself part of its value. It has the following observable properties:

1. **The human can explain it.** Under examination, the author can say why this choice was
   made, what was rejected, and what they verified. The ability to explain is not a luxury;
   it is the very demonstration of authorship. On a large project with many contributors this is partial in
   practice - no one can explain every line of a large codebase - but the *full capacity* must
   exist between the authors and the *habit* must be visible.
2. **The human can, and does, reject machine output.** An author who has never rejected the machine’s output is not
   an author, but an open drain. Rejection is not a stylistic flourish; it is the
   mechanism by which any work attains Quality. A record of decisions, including reversals and rejections,
   is a sign of agency. A record without rejection is a record of assent-by-default.
3. **The human’s judgment is directional.** The work contains the human’s actual choices;
   things the machine would not have decided on its own, which the human can defend on their
   merits. This directionality has many names in engineering: Design, architecture, taste,
   judgment. Where it is absent, the work has the uniform, self-consistent texture of
   something that was never doubted, and doubt is exactly what anything important requires.
4. **Provenance is not concealed.** Disclosure of how the work was made is not a legal
   requirement in every jurisdiction; it is not even always a practical requirement. But it
   is a *statement* that matters. A project that discloses its process -
   including its use of machines - is telling the truth about the relationship between the
   human and the work, and that is a property users *are* entitled to know. Concealment of
   provenance is not a stylistic choice; it is deception, made by someone who knows what the
   record would otherwise show.
5. **The human stands behind the failures.** When assisted work fails, the human can say: Yes, I
   chose this, under these assumptions, here is why, here is what I got wrong, here is the fix.
   That sentence is the entire contract between an author and the people who depend on their work.
   A human who cannot say it - because the choices were never theirs - *has nothing to offer anyone*, and
   is by definition entirely replaceable; anyone else could have pressed the same button.

### What substitution looks like

Substitution is equally recognisable, once the pattern is known:

1. **Scope that no human could have authored.** Output that
   structurally cannot have been the product of human authorship, review, and judgment, for
   example when the volume exceeds any reasonable human capacity within the span of the project’s life.
   When the review capacity and the output volume are incommensurable, the output was not
   reviewed. It was generated, then forgotten, and the record was signed blindly.
2. **Uniform generation.** The work carries no trace of a human’s changing mind. No style
   drift, no contested decisions, no “we tried X and it was wrong, so we did Y”. That is, *no
   signs of actual development, growth and learning*. Instead, endless, self-referential
   refactoring, renamed abstractions, and the same fluent register in every commit,
   every document, every reply. A human’s history shows the wear of judgment.
   Pure generation shows the superficial polish of its absence.
3. **Discovery by recursive regeneration.** When errors are found, they are found by the machine’s own
   subsequent runs, not by human scrutiny - and the findings are recorded as planned
   “reviews” and “alignments” rather than as the corrections they are. This is the tell: A
   machine editing its own previous output, while the edit is recorded as if it were a
   scheduled milestone. That’s not review. That’s a continuous generation loop revising itself,
   with the attempt of an illusion-preserving voice-over.
4. **Laundered provenance.** Theatrical concealment machinery: Commit hooks that refuse
   attribution of machine generation, contribution policies that declare machine output
   “yours”, processes that scrub personal traces from the history, fake identities in the
   contributor list. All of these have one function: To make the record say what the “author”
   *wished* had happened, rather than what happened. A project that builds such machinery is
   not making a record of its work; it is using automated software to manufacture one.
5. **Authorship by assignment.** The human’s name is on the work, but the human cannot
   answer for it - because the human did not choose any of it, and knows it. The name is not a
   signature of authorship; it is a *fraudulent claim of ownership* over something the claimant did not
   make and cannot explain. In every field that has ever dealt with such claims - art,
   literature, invention, journalism - *this has a name*. That **forgery** is now cheap in software
   makes it no more forgivable.

### Infrastructure Matters

For a hobby project, the distinction between assistance and substitution is a personal matter. For infrastructure - code that other people’s communications, safety, and freedom run on - it is a matter of life and safety, and any statement about this must be entirely unapologetic.

Infrastructure has one property that distinguishes it from almost all other software: While most of the people who depend on it cannot verify it themselves, **it must be verifiable, auditable and open to human inspection**, and be engineered in such a way that this is as frictionless and straight-forward as possible.

The reference implementation of Reticulum was designed this way, and continues to make that goal a primary one. While it *is* a complex piece of software, with an intricate array of interlocking and moving parts, the core parts of RNS, the entire Reticulum protocol implementation, the transport logic, the cryptographic primitive interfaces, **is less than 15,000 lines of code**. That line count even includes the rather extensive comments, incredibly detailed logging facilities and other choices that makes the code easy to read and understand for humans, and easy to operate, verify and debug. It took real dedication, and *a lot* of hard work to achieve that.

Exactly because not *everyone* can do this, it is a fundamental necessity for infrastructure software that it is designed and authored so that *as many as possible can*, and that the *chain of accountability* - who made it, who reviewed it, who answers for it - is held intact at every link. That chain is not decoration. It is the entire mechanism by which normal users decide to trust a system they cannot fully verify. The transparent foundations and the chain combined *is* the verification for most users.

Substitution breaks the chain both at the foundations, and at its load-bearing link: The human at the top can no longer answer, because they were never the maker. Unfortunately, the chain does not always fail visibly; often it fails silently, at the exact moment a question goes deep, or when routing fails subtly at a critical moment.

For the user, the result is not a project with a normal and humanly flawed author - it is a project *with no author at all*; a signature with no substance behind it, a name that cannot be held to account, and a body of work that nobody on earth can (or wants to) explain, defend, or fix in a crisis.

### The Fluency Trap

It is worth understanding, briefly, why substitution is so attractive and so dangerous at once. Machine-generated output is fluent. It is confident, well-structured, and terminologically *self-consistent*. At the surface, and from the perspective of someone outside a given craft, it is indistinguishable from the output of a knowledgeable human. Fluency of this kind can be a useful property: It makes assisted work fast. But fluency is *not* understanding. It is the *minimal conformal surface* of understanding.

The danger is that the surface is exclusively where the substituter invests; for the simple reason that the surface is where most of the desired audience looks, and what yields attention to the project.

A human who can tell the difference uses the tool well. A human who cannot is being deceived through means they cannot detect from inside, namely through their own inability to account for the limits imposed by what they do not know.

This is why the most important quality for anyone working with systems like Reticulum is not speed, and not vocabulary, but the oldest engineering virtue there is: The honest, uncomfortable, terrorizing knowledge of **what you do not know**. The substitute *never* has it. The substitute’s operator, *if* they ever had it, loses it precisely the moment they accept the fantasy of the substitution process.

The tool is not the hazard, plain old human nature is. The tool is a mirror, and mirrors - as has been observed for rather longer than software has existed - show the truth only to those willing and yearning to see their own shortcomings.

### Disclosed Assistance Or Laundered Generation

The contrast at the centre of this entire discussion can be made clearer with two examples, both of which are a publicly accessible, both produced in the same year, by people using the same class of tools.

The first is this chapter. It was produced with machine assistance, openly: the structure was directed by the human, the material was assembled with the tool’s help, every conclusion, every line, every slight nuance of meaning and semantics was examined, edited, and accepted or rejected by the human, and the process described publicly - including the precise characteristics of the technological assistance framework used. The human can answer for every claim in these documents, because the human made the decisions the claims rest on.

The second is the project examined in [the Prns case](#brandolinis-prns). It was produced by a machine, at a volume no human could review, and the authorship record was engineered to erase the machine’s role: A commit hook that refuses attribution of machine generation, a contribution policy declaring machine output the human’s own, a fictitious contributor identity, 637,000 lines of unreviewed code. The human cannot answer for the code, because the choices were never made by a human - only the conformal surface of the presentation was.

The same tool class. The same technology. Two diametrically opposed relationships to truth and responsibility. **The difference is not the tool**. The difference is the presence or absence of the human as the agent of the work - and the honesty or concealment with which that relationship is recorded.

Assistance leaves the human as the agent and the commons as the source from which the human works and can grow. Substitution removes the human from the loop and converts the commons into fuel for the thing that seeks to replace them, or usurp their work for the profit of the few, human atrophying in the process.

### The License In This Context

The Reticulum License, examined in [What The Reticulum License Is](#brandolinis-what-the-license-is), draws the same line, at the level of the law. Its AI condition does not forbid the use of machine-learning technology to *assist* development - no reading of the license could support that, and no one associated with this project has ever claimed so. What the condition forbids is the *appropriation of the work into the machine itself*: The ingestion of the commons as raw material for synthetic replacement, and the concealed fabrication of “prior work” that would bury the real thing.

As also noted in [Copyright & The Two Legal Layers](#brandolinis-copyright-and-layers), plain old copyright law already protects against the case where a process copies the reference implementation into a machine, produces a transformed derivative, and then claims “Copyright, [name of the process operator]”, with no human able to account for the creative decisions in the result. That is simple, petty theft, as it always has been.

### The General Principle

In these regards, the position of this project can be codensed to something relatively concise:

* Machine assistance in human learning, development, and creation is accepted and useful.
  It is not a shameful secret; but it *is* a tool that needs knowledge, training, understanding,
  and great care to use. It should not make anything easier or more fun, it should make the
  results better, more carefully considered, and arrive at *higher levels of synthesis*, not
  produce endless streams of code churn.
* The line is crossed when the human stops being the agent of the work. When *any* output is
  accepted that the human cannot explain, produced at a scale the human cannot review, or filed under a record
  where the human has arranged to conceal the fact.
* The line is crossed, when a human claims authorship of work they cannot
  answer for or has usurped. Credit follows the ability to answer. It has always worked that way, and
  machines do not change the rule - they only make it cheaper and more tempting to break.
* The people who depend on infrastructure have the right to know which side of the line
  the code they run was made on. That knowledge is the only verification most of
  them will ever be able to perform.

Use assistance, by all means, *and learn*, but don’t substitute. And never sign what you cannot answer for.

Somewhere, within the general shape of the conceptual framework outlined in this section, or realistically, a more refined variant of it, I do believe there is the *potential* of the *beginning* of a constructive outcome to the immense challenge we are faced with as a species in regards to these problems.

At the same time, I reserve my right to revert that position to Butlerian Jihad without prior notice. We are on a knife’s edge, and you know it just as well as I do.

## Evaluating a Reticulum Implementation

### The Intention Of This Guide

Very few user of network infrastructure can verify the software they run. This is true of the reference implementation as well, and it is precisely why it was engineered the way it was: the entire Reticulum protocol implementation - the transport logic, the cryptographic interfaces, the routing - is less than 15,000 lines of code, including its extensive comments and detailed logging. The reference is *designed* to be readable by a human in a reasonable sitting. That is a deliberate decision, and it is the standard against which every other implementation should be measured: An implementation that asks for trust while being structurally unreadable is asking for the absurd.

Because most users cannot verify the code directly, the evaluation of the *project* is the evaluation of the software. The framework below exists so that this evaluation can be performed in minutes, by anyone, without expertise - and so that each new “implementation” does not require the kind of full investigation that would otherwise be if not impossible, prohibitevly expensive.

### Two Questions That Resolve Most Cases

Other considerations in this guide is further corroboration. These two questions allow you to decide the case quickly in most instances, and they should be asked first.

**Question 1: Does this speak the protocol, or was it just generated from the reference?**

The copyright and license realities, described in [What The Reticulum License Is](#brandolinis-what-the-license-is), is the legal foundation of this distinction. The protocol is public domain: A *genuine* [clean-room](#brandolinis-cleanroom-delusion) implementation, reasoned out and written by humans, is free and welcome, and owes nothing to any license. But an implementation that was *directly generated from* the reference - reproduced by a copy process, whether manually or through a machine or software - is a derivative of the licensed work, and is subject to both the license’s conditions, and to the ordinary copyright law examined in [Copyright & The Two Legal Layers](#brandolinis-copyright-and-layers). A primarily machine-generated copy without substantial human creative input is not merely unlicensed; it is a copyright violation that would exist under any license at all.

**Ask**: Does the project say where its protocol knowledge came from? Does it credit the reference implementation, or claim “ground-up” status while its own history shows continuous ingestion of the reference’s source? Does its license carry the original copyright notice? The answers tell you, within minutes, which of two very different kinds of project you are dealing with.

**Question 2: Who, or what, is the agent of the work?**

This distinction, established in [Assistance Versus Machine Substitution](#brandolinis-assistance-versus-substitution), is the trust foundation of everything else. Is there a human who decided what to build, judged what was correct, rejected what was wrong, understands what was shipped - and can answer for it, line by line and decision by decision, *without machine assistance*? Or is the machine the agent, with the human’s role reduced to the name, the account, and the signature?

> This test has a sharper form: **would the project be meaningfully different if someone else had pressed the button?** If the answer is no - if any person could have been the signature and nothing would change - then the “author” is not the agent of the work. They are its facade, and the project is, in the most literal sense, worthless and unowned.

A project with no owner is a project no one can answer for, and infrastructure with no one to answer for it has no place carrying other people’s traffic.

### Other Signals To Look For

Once the first two questions are answered, the following signals determine the verdict. None is alone decisive; together they form a pattern that is difficult to fake in the directions that matter.

#### Provenance and attribution

* **Credit to the reference.** Does the project name Reticulum’s reference implementation
  in its README, its website, its licenses, and the code? Does it present itself as a port
  or as a “ground-up” origin story? Absence of credit, in a field where every implementation
  owes its existence to the reference, is not an oversight; it is a decision.

* **License compliance.** For a derivative, the license conditions apply: the copyright
  notice and permission notice in all copies and substantial portions, the harm condition,
  the AI-training condition. A project whose license file claims a fresh copyright in the
  operator’s name, over work that was generated from the reference, has failed the minimum
  bar of honesty before any code is read.

* **Disclosed provenance.** Is the use of machine assistance stated openly, or does the
  project maintain machinery to conceal it - commit hooks that refuse attribution of
  generation, contribution policies that declare machine output the human’s own, scrubbers
  for personal traces, fictitious contributor identities? The first is the mark of a human
  using a tool. The second is the mark of a record being manufactured.

* **The author’s history.** Is there a prior record - projects, contributions, a body of
  work that a person can look at and reasonably assess? A sudden, fully-formed “decade of experience”
  appearing from nowhere, attached to a project of unprecedented scope, is a story that
  contradicts itself.

#### Agency and answerability

* **Who answers the questions?** When technical questions are asked, does a human answer
  with substance - going deeper, explaining trade-offs, admitting uncertainty - or do
  answers deflect to process (“the CI verifies it”, “the proofs prove it”, “the audit
  covered it”)? Are the answers themself machine generated? Deflection to process is
  the substitute’s answer pattern: It names the machinery instead of the reasoning.

* **Velocity commensurate with authorship.** Is the output volume compatible with human
  authorship, review, and judgment? An implementation ten (or 42!) times the size of the reference,
  produced in a fraction of the time by a single person, is not evidence of brilliance; it
  is evidence of unchecked generation. Churn is part of the same signal: A project that
  deletes half of everything it adds is not building; it is looping.

* **Signs of development, growth and learning.** Do reversals exist? Contested decisions?
  “We tried X and it was wrong, so we did Y”? Humans change their minds, admit mistakes, and
  leave the wear of judgment in their history. Pure generation shows “the polish of its
  absence”: uniform register, endless renaming, and errors discovered by the generator’s own
  later runs, recorded as if they were planned milestones.

* **Standing behind failures.** When something is wrong, does the human say “I chose this,
  here is what I got wrong, here is the fix”? Or do corrections arrive as process language,
  with nobody accepting that a decision was even made? A project whose history contains no
  first-person acceptance of error contains no author.

#### Engineering reality

* **Honest benchmarks, or none.** If performance is claimed, is the baseline real - stock,
  current, interpreted RNS, on the modern interface, at equal policy, with methodology
  published in advance and reproducible by anyone?

* **Interop with reality.** Is compatibility verified against the *current* reference
  implementation - on real hardware, including the radio and serial interfaces this
  protocol family lives on - in both directions, over long transfers, uptimes and edge cases?

* **The readability standard.** Can a competent human read the core of this implementation
  in a reasonable sitting, the way the 15,000-line reference can be read? Was human
  readability a stated design goal, or an afterthought? A project that cannot be inspected
  is a project asking for trust it has not earned and will never attend to.

* **Nonstandard inventions.** Does the project “improve” on the protocol with its own
  modes - new channel behaviour on shared spectrum, new rendezvous mechanisms, new crypto,
  “post-quantum” replacements, “turbo” variants? Inventions that change behaviour on a
  shared network are not features; they are forks of the airwaves, imposed on every other
  node that shares the medium. A project that invents on top of a protocol it has not yet
  correctly implemented is not advanced; it is dangerous to its neighbours.

* **The public record.** The commit history is public. Read it.

#### Network citizenship

* **Honest presence.** Does the project identify itself honestly on the network, or does
  it masquerade as something it is not?

* **Coexistence.** Does it respect the shared medium and network conventions? A node that
  is a bad neighbour on the spectrum is a hazard regardless of how well its code works in isolation.

* **Community participation.** Does the author participate in the community as a member -
  answering questions, contributing, learning - or only appear to advertise? The second is
  not participation; it is exploiting the community as a broadcasting target.

#### Monetary and influence signals

* **Money under the claim.** Donations, funding, or commercial offers premised on claims
  like “89× faster” or “formally proven” convert false marketing into a different category
  of problem. When money changes hands on the strength of fabricated measurements, the
  stakes are no longer theoretical.

* **Tokens and “investment” vehicles.** Any implementation that surrounds itself with a
  crypto token, a “coin”, or an investment pitch should be treated as what it is: A project
  whose primary purpose is to earn the controller a profit, not open networking.

* **Marketing-first ordering.** A polished website on day three, a twelve-language marketing
  presence, a “benchmarks” page and a “get started” funnel existing before the protocol works
  is a massive red flag. Real builders ship, then talk. The inverse order is the signature of
  a project whose goal is attention.

### The Conformal Surface

One warning before the synthesis. When you evaluate any project, assume - as a working hypothesis - that its surface is an investment. The marketing, the design, the badge collection, the “proof records”, the fluent and confident prose: This is exactly where substitution invests, for the simple reason that it is where the audience looks first. Fluency is the *minimal conformal surface* of understanding, and the surface is not evidence of anything except that the author *wanted to look convincing*. If you find yourself impressed by the surface before you have asked Question 1 and Question 2, you are doing the evaluation in the order the substitute operator hoped you would.

### Possible Verdicts

The framework proposed here can yield three different verdicts:

1. **Meets the standard.** A named human who can answer for the work and demonstrably does;
   provenance disclosed; attribution given; honest benchmarks; interop
   demonstrated against current, real RNS on real media; readable code; a maintenance
   history that shows growth and learning. This standard is not high. It is what the
   reference implementation has met, in public, for over a decade, and it is what any
   project that wants other people’s traffic should be willing to meet in turn.
2. **Experimental, but honest.** A project that clearly labels itself as in-progress and
   experimental (“do not use this yet”, in plain words, as the first thing a user sees)
   discloses its provenance, credits the reference, and is being developed in the open by
   humans who answer questions. Such projects should be encouraged. They are how the
   ecosystem grows, new ideas are tested, and the framework above is designed to make an
   honest experimental project *easy* to recognize, not hard.
3. **Does not meet the standard.** Unanswerable authorship, concealed provenance, fabricated
   measurements, invented protocol behaviour, absent interop, marketing ahead of substance.
   Such projects should be treated as unproven regardless of their surface, and as hazards
   if they invite users onto shared networks. The community owes them exactly the
   skepticism they have earned, and not a moment of engagement beyond that; the network’s
   time is better spent elsewhere.

### These Standards Are Reasonable

I’ll close this guide by stating what these standards are *not*: They are neither a demand for perfection, nor a ban on machine assistance. Assistance is useful, when it is used to arrive at *higher levels of synthesis* than unaided work. It is not a requirement that an implementation be a clone of the reference; neither is it a requirement that it invents everything from scratch or aspires to be a [“clean-room”](#brandolinis-cleanroom-delusion) implementation. Good implementations of the protocol are very welcome, *however they come*, but working on one requires *serious* work, considerable skill, and **deep competence**.

The reference implementation has met this standard for years, and its users know what that looks like.

## The Prns Case

### Purpose & Scope

This section provides a concrete example, which future evaluations can use as a template. Its purpose is not to be the last word on this particular subject, but to be an example of how the ideas in this chapter can be applied, and to make the next such examination easier.

The subject of this case study is **Prns**, a project published at the repository `github.com/KenAKAFrosty/Prns`, presented as a “ground-up implementation of Reticulum, written in Rust”, marketed as faster, safer, and more strictly tested than the reference, and widely promoted with the claim of “up to 89× the throughput” of the reference implementation. The record described below is the project’s own, and sourced from its GitHub repository, analyzed locally.

### The Project In Brief

* **Time span.** 3,374 commits between 2026-05-26 and 2026-09-12: approximately 110 days,
  at a mean rate of ~31 commits per day. Monthly: 132 / 1,137 / 1,097 / 805 / 203.

* **Authorship.** 3,252 of 3,374 commits (96.4%) are authored by a single account. A
  second identity, “Prns Tests [tests@example.test](mailto:tests@example.test)” - a fictitious identity on a reserved
  domain - contributed 35 commits, every one of them website and marketing content.

* **Size.** 3,519 tracked files; 1,983 Rust files; 636,226 lines of Rust; approximately
  22.7 MB of Rust source; 69.5 MB of total repository content.

* **Scope claimed.** A daemon (“drop-in replacement” for the reference daemon), embedded
  firmware for three microcontroller families (including six ESP32-S3 board variants and
  nRF52840), SDKs and bindings for nine languages, a browser-based node and web flasher, a
  twelve-language website, a benchmark apparatus with its own publication and “proof”
  pipeline, and a validation hub with oracles, fuzzing, mutation testing, and formal-proof
  claims.

* **Marketing claims.** “Ground-up implementation of Reticulum”; “up to 89× the
  throughput”; “48× smaller peak-memory footprint”; “33× the energy efficiency”;
  “Measured, not just claimed”; “Enforced, then audited”; “byte-for-byte wire parity with
  the reference implementation”; “works with Sideband, NomadNet, MeshChat, etc.”;
  “no_std (no alloc required either)”.

* **Status at the time of writing.** Version 0.3.7; published version history begins at
  0.3.0. The repository continues to receive commits.

### Question 1: Is this a clean implementation, or was it directly generated from the reference?

The first of the two deciding questions from [Evaluating A Reticulum Implementation](#brandolinis-evaluating) is settled by the project’s own record. An actual [clean-room](#brandolinis-cleanroom-delusion) implementation, reasoned out and written by humans, would owe nothing to any license. The data available shows clearly that Prns is not that.

* **The founding state.** The first commit, “Scaffold Personal Reticulum suite”, contains
  the scaffolding of not one but two ports - `personal-rns` and `personal-lxmf`, the latter
  being the reference’s companion messaging protocol - together with a daemon scaffold and
  a 233-line founding document, `docs/build-ethos.md`. That document declares the project’s
  goal as a “performance-focused drop-in-replacement for rnsd” and its governing principle
  as: “Port the contract, not the implementation.” It further states, in the project’s own
  words, that fidelity is owed to the reference “at exactly two boundaries”: “the wire” and
  “the behaviour”.

* **Continuous alignment to the reference.** 506 commits reference RNS or Reticulum
  source behaviour; the word “parity” appears in 49 commit messages. Commits cite the reference
  implementation’s own source locations (for example `Transport.py:1367`) when correcting
  their own divergences and mistakes.

* **Byte-level fidelity as an explicit goal.** Within 48 hours of the first commit, the
  record shows a “crypto adapter - vetted primitives, byte-exact vs RNS 1.3.1”, and a wire
  implementation matching the reference’s packet header layout. The project’s own
  validation apparatus decodes wire vectors using the reference implementation’s own
  packet parser, and the interop suite consists of real, stock-RNS peer nodes - that is,
  the reference itself, used as the ground truth against which this project’s output is
  checked, and committed as accepted verified after 48 hours of the project’s recorded start.

* **The marketing mismatch.** The same record that documents all of the above describes the
  project, publicly, as “a ground-up implementation of Reticulum” - while declining, on its
  website, to link to the reference implementation at all: the entire tree mentions the
  reference’s author in six files, and the website in none.

Conclusion: the project’s own history and commit record establishes that it was generated directly from the reference implementation’s source code, not reasoned out from the public-domain protocol. It is a derivative of licensed work within the meaning of [the Reticulum License](#brandolinis-what-the-license-is) and [general copyright law](#brandolinis-copyright-and-layers). The “ground-up” claim, which carries its entire legal and marketing posture, is disproven by the project’s own history.

### Question 2: Who, or what, is the agent of the work?

The second deciding question is answered by the application of [Assistance Versus Machine Substitution](#brandolinis-assistance-versus-substitution) criteria to the project.

**Scope that no human could have authored**

636,226 lines of Rust in 110 days is approximately 5,800 lines per day, every day, including weekends - with 149 commits recorded between midnight and 06:00, and Saturday the single busiest weekday. No human review or decision capacity is commensurable with this volume; the review capacity and the output volume are structurally incommensurable, which is the definition of unauthored scope.

**Uniform generation**

The record shows no sign of human development, growth, or learning: No contested decisions, no style drift. Instead: endless renaming (in the first 48 hours: `State → EngineState → TickInput → TickOutput`), uniform fluent register in every commit, and the exact same, synthetic voice in code, documentation, and website copy.

**Discovery by regeneration**

Corrections arrived by the machine’s own subsequent runs, recorded as planned milestones. In early July 2026, a series of “core review” commits documented, in the project’s own words:

* announce-ID history “was unbounded per-slot growth” (`54cc8d601`);
* interface announce limiting could “leak a sustained flood” (`9d27af75c`);
* a “phantom-airtime leak” where frames “used to vanish silently” (`4ed75ffdd`);
* Group-packet deduplication “which RNS does not do” - a behaviour the reference never had,
  implemented and later removed (`edd8e72be`);
* “both `unwrap_or(&[])` arms were unreachable dead defaults” (`74bea355e`);
* a benchmark crate “hasn’t compiled since” a prior rename, undetected for weeks because it
  was outside the CI’s workspace (`86240b027`).

Earlier still: the record shows a “>1 MiB RNS-to-Prns interop stall” closed three weeks in
(`cc4d524a3`), and a known send-path hang shipped with the note “typed fast-fail a
candidate for later” (`a010e6613`).

**Laundered provenance**

The repository contains a committed commit-message hook (`.githooks/commit-msg`) that *blocks* any commit containing attribution for machine generation (“generated with claude/codex/copilot/cursor/gemini”, “co-authored-by”), with the explanation “The committer owns the commit”. The contributing guide is explicit: “AI tools … are welcome … what you submit is *yours*”, and describes the contributing population as “both human and automated contributors”. The fictitious “Prns Tests” identity completes the picture: A manufactured, unknowable contributor, used for marketing content.

**Authorship by assignment**

The human whose name is on the work cannot answer for it, because the choices were never made by a human, and only the general shape and constraints of the outward presentation was. Nothing in the project’s history shows an individual explaining a design decision, accepting a mistake in the first person, or going deeper under technical questioning; the record shows process language and marketing instead. Per the earlier mentioned test: any other person could have pressed the same button, and nothing would be different. The project is effectively unowned, and void of value.

By the criteria of [Assistance Versus Machine Substitution](#brandolinis-assistance-versus-substitution), this is substitution. The machine was the agent of the work; the “author” was a facade.

### The performance claims

The project’s central marketing claim - “up to 89× the throughput” of the reference - is also its most completely documented failure, because the project published the evidence of its own measurement. The apparatus, the results, and the problems are all on the record.

**The claim**

The README states “up to 89× the throughput”; the on-network marketing page repeats “up to 89× the throughput, 48× smaller peak-memory footprint, and 33× the energy efficiency of stock RNS 1.4.2”; the website’s front page carries the tagline “Measured, not just claimed”.

**The apparatus**

The reference is loaded through `benchmarks/reference/compiled_reference.py`, which installs `pyximport` and then asserts two things: that `RNS.compiled == True`, and that at least *one* RNS module was loaded from a native extension. The project’s own published “proof” records show exactly what those checks captured, on every platform:

```default
aarch64-apple-darwin: .../RNS.cpython-313-darwin.so,  Cython 3.2.8, Python 3.13.13
x86_64-unknown-linux-gnu: .../RNS.cpython-313-x86_64-linux-gnu.so,  gcc 11.4.0
x86_64-pc-windows-msvc: ~/.prns-oc/lib.win-amd64-cpython-313/RNS.cp313-win_amd64.pyd
```

In every case the recorded native module is the **top-level package only** - `RNS.so`, nothing below it. Nothing named `RNS.Transport`, `RNS.Destination`, `RNS.Packet`, `RNS.Link`, or `RNS.Resource` ever appears, because *nothing below the top level was ever compiled*. Nobody bothered to check or verify *anything* here.

The machine output was simply taken for truth, and a full marketing strategy was spun and produced on it. “RNS 1.4.2 (compiled)” - the label used in every table, chart, and marketing page - *is not a mode of RNS that exists*, but the hallucinations of a machine, which the humans created a marketing strategy on. In reality, it is the old `CRNS` development shim, whose top-level-only, debug-oriented “compilation” is slower than plain interpreted RNS, and which was *defunct for over a year* before these benchmarks were published.

**Interface choices**

The harness writes the reference’s configuration itself (`benchmarks/reference/participant_node.py`): `TCPClientInterface` for the initiator, `TCPServerInterface` for the responder and both relay sides, with `UDPInterface` as the abstract wire. The reference was never given its modern `BackboneInterface` on any platform, forcing the slowest possible interrfaces. The interface selection is never mentioned in any methodology text.

**The policy**

The published default-policy tables record the asymmetry directly: Prns at 500 Mbps / 128 KiB TCP policy against the reference at 10 Mbps / 8 KiB - slyly footnoted as “preserves each implementation’s normal TCP policy” (in the case of RNS, a conservative default policy that was selected to prioritize coexistence on slower, shared links, requiring the user to dial it up to full speed if they knew what they were doing). Raw transport “throughput” ratios of 20.65× (Linux) and 38.84× (Windows) are therefore mostly policy, not engine.

**The cross-host evidence**

The published results show the same scenario producing wildly different ratios by host, and the variance is entirely in the reference artifact:

| Host                    | Prns, single-packet   | “Reference”, single-packet   | Ratio   |
|-------------------------|-----------------------|------------------------------|---------|
| macOS (Apple M4)        | 37.4k/s               | 420/s                        | 89.09×  |
| Linux (i7-1260P)        | 25.3k/s               | 3.5k/s                       | 7.19×   |
| Windows (Ryzen 5 5600X) | 30.8k/s               | 3.9k/s                       | 8.00×   |

Prns is consistent (25–37k/s). The reference artifact collapses to different depths on different hosts, and the single worst collapse - 420 packets per second on macOS - is the cell selected as the global headline. The “89×” is not a measure of Prns; it is a measure of how badly the broken baseline happened to fail on one host.

For reality calibration: Stock, interpreted RNS 1.5.4 on an ordinary mid-range laptop, single core, sustains roughly 30,000 single-packet deliveries per second (including ephemeral-key decryption), ~175,000–280,000 packets per second in transit relay, and on the order of 10 Gbps at 16 KiB payloads. The project’s “compiled” artifact measured 420–3,900 packets per second for its single-packet scenario: An order of magnitude or more *below* stock interpreted RNS. The comparison being marketed was not “Rust vs Python”; **it was “an implementation running under optimal conditions versus a mislabeled, broken shim on a slow legacy interface at a severe policy disadvantage”**.

**The equalized rows**

The project’s own “1 Gbps policy” rows, in which both sides are explicitly configured identically, publish ratios of roughly 2.4–8.4× across all hosts and scenarios - still against the broken baseline, but nowhere near 89×, and consistent with the ordinary, uncontroversial observation that a native implementation tends to outperform an interpreted one in raw throughput. That point needed no fudging to make, and is banal.

Interestingly, though, it seems that Prns is really only *marginally* faster than a Python implementation, running in interpreted mode, on a single CPU core.

**Assessment**

The front page says “Measured, not just claimed.” The record shows the opposite ordering: claimed, and arranged to look measured. No methodology section anywhere states what “compiled” means, that it is a deprecated development shim, that it builds debug targets, or which interface the reference was given; the one statement of the policy asymmetry appears in a footnote of the results tables themselves. If they did not need to fudge it, they would have published the method clearly.

### Overall Evaluation

Evaluated against the conditions of [Evaluating A Reticulum Implementation](#brandolinis-evaluating):

* **Provenance and attribution.** Fails: The fake “ground-up” origin story; zero reference links
  on the website; a single well-hidden link in the README; a license file reading
  “Copyright (c) 2026 The Prns Authors” over work directly generated from the licensed reference;
  no original copyright or permission notice anywhere.

* **Agency and answerability.** Fails on every criterion of [Assistance Versus Machine Substitution](#brandolinis-assistance-versus-substitution):
  unauthored scope, uniform generation, discovery by regeneration, laundered provenance,
  authorship by assignment.

* **Engineering reality.** Fails: The benchmark apparatus above; interop demonstrated only
  against a pinned, outdated reference version (RNS 1.4.2; some published suites against
  1.4.0) over loopback, with the project’s own result tables documenting interop failures
  with stock RNS; the reference version itself drifts across the project’s publication history
  while the marketing claims current parity; a nonstandard “turbo” sub-GHz mode invented for shared spectrum,
  in a codebase whose own history shows it had not yet correctly understood the
  reference’s duty-cycle accounting when the invention was layered on; vendored prebuilt
  binaries and a republished fork of an upstream crate (`nrf-softdevice 0.1.0-prns.1`)
  with no verifiable provenance; committed WASM bundles.

* **Network citizenship.** Fails: Invented spectrum behaviour, and compatibility claims
  about third-party applications of the reference ecosystem (Sideband, NomadNet, MeshChat)
  that are not established by any evidence.

* **Monetary and influence signals.** The marketing apparatus - website before protocol,
  day-three twelve-language marketing, false benchmark headlines, “audited” claims - is the
  conformal surface described in [Evaluating A Reticulum Implementation](#brandolinis-evaluating):
  the surface is where this project invested.

### Licensing Analysis

Applying the two legal layers established in [Copyright & The Two Legal Layers](#brandolinis-copyright-and-layers):

**Layer A - copyright infringement (license-independent)**

The record shows a direct copy roundtrip: the licensed reference implementation fed into a machine, transformed, at a scale and cadence no human could review, with a license file asserting a fresh copyright in the operator’s name and no acknowledgment of the work the project was generated from. No substantial, new human creative input is demonstrated anywhere in the record - the founding document explicitly frames the design as an instructed port of the reference’s contract. A primarily machine-generated copy of a copyrighted work, not accompanied by demonstrable substantial human creative input, is a derivative work over which the copier holds no copyright, and a reproduction of which without the original author’s permission infringes the original author’s copyright. This holds under any license, MIT included. The operator’s copyright claim over the result is, on this evidence, not merely unsubstantiated; it is the absence of one, directly asserted in the project’s own writing.

**Layer B - license conditions (Reticulum License specific)**

Modern Reticulum - the current wire format, the AES-256-based link encryption, ratchets, the cryptographic machinery as it exists today - has been published under the Reticulum License since April 15, 2025, effective from release 0.9.4 and every release since. As a derivative of that work, the license’s conditions attach: The copyright and permission notice must be included in all copies and substantial portions; the AI-training condition must be honoured; the harm condition must be honoured. The record shows none of the notice requirements met, and a production process that consists of the licensed work being ingested into a machine and regurgitated, at industrial scale and cadence.

**The cascading consequence**

Prns is distributed claiming dual MIT/Apache-2.0 licensing. It is, however, a direct derivative of Reticulum-licensed work, and the claimed grant is therefore void. Every downstream project that builds on Prns believing it is MIT/Apache-licensed is building on a grant that does not exist. The users of Prns, and all software developers using it, have in effect, been placed under conditions they were never told about. The “ground-up” claim is not merely false; it is the sole load-bearing element of an entire licensing posture, and it fails spectacularly.

### Consequences

The consequences of this pattern are examined in the following sections - the harm to users and to the network in [A Movement Of A Dozen](#brandolinis-movement-of-a-dozen), and the human dimension in [Network Health & Coexistence](#brandolinis-health-and-coexistence). This section’s contribution is narrower and intended as an instructive example: This is what a substitution project looks like, in full, on its own record. It is a reference example for [Evaluating A Reticulum Implementation](#brandolinis-evaluating), and it demonstrates, in one case, most of the elements this chapter describes.

### Verdict

Applying the three verdicts of [Evaluating A Reticulum Implementation](#brandolinis-evaluating), this project does not meet the standard. It is not “experimental but honest” - it is not labeled as experimental anywhere; the first thing users saw was a polished marketing presence promising a finished, tested, drop-in replacement. It is a project whose central claims are fabricated (the performance apparatus), whose provenance is laundered (the authorship machinery), whose foundation is misrepresented (the “ground-up” story), whose core semantics were learned late and by regeneration, and whose operator cannot possibly answer for any of it. It is also a blatant copyright violation of the reference implementation.

The proposed conclusion, for users and for the network: Treat the Prns project as hostile regardless of its polished surface, and as a hazard insofar as it invites users onto shared networks. Nothing in this section is a judgment about the people involved; it is a reading of the results produced, their history and how they came to be, which in the regrettable lack of any human authorship is the only thing that can be expected to be held to account.

### Dating

This examination reflects the publicly available material as of September 2026; the repository in question continued to receive commits at the time of writing, so readers should treat citations to commits and files as point-in-time evidence. A [forensics snapshot](https://github.com/markqvist/forensics_prns) is publicly available on GitHub.

## The Movement Of A Dozen

### Presentation, Elongated

Whenever Reticulum defends itself, its license, or its community - or simply continues to exist - a familiar chorus appears. The register is always similar: *concern*. Concern about the direction of the project. Concern about its license. Concern about its governance. Concern about its “bullying” of “good-faith contributors”. Concern about the future of the ecosystem at the hands of a single maintainer. The chorus speaks in the plural, presents itself as a body of independent voices, and insists, with some frequency, that it is… *not alone*.

The implicit claim under examination in this section is that there exists a *movement* of concerned individuals, spread across the ecosystem, all worried about Reticulum, and therefore (for some reason) deserving of a place at the table of decisions.

A resolution of this claim requires one step: Count them.

### Headcount

This “movement” does have a headcount. It is not in the hundreds, and it is not in the dozens. It is a small number of people who appear, in various combinations and under various names, in the following roles:

* Creators of the machine-generated “Reticulum implementations” examined in this chapter
* Creators of articles praising those implementations and lamenting the state of the
  reference, its moral shortcomings, its unavailability or lack of something it already has.
* Commenters “defending” the implementations when they are evaluated reasonably and critically,
  most often by attempting simply to derail the discussion.
* Critics of the Reticulum License on “open source” grounds
* “Concerned community members” objecting to the maintainer’s conduct
* Campaigners on online platforms; and
* In some cases, a single individual performing *several* of these roles at once, under
  different names, in the same week.

The overlap is well documented at this point, across time and different platforms. The same phrasing, the same arguments, the same links, the same reactive reflexes, the same handful of accounts appearing in the same threads at the same moments. When the sockpuppet accounts are unmasked (and they frequently unmask themselves) the cast does not grow, but rapidly shrinks.

This is the most interesting single fact about the “movement”: **It isn’t one. It is a synthetic cast**, held together mostly by LLM-glue, reddit handles and hysteria. A cast is not a constituency. It performs; it does not represent. The difference matters quite a bit, because a great deal of this “movement’s” imagined power comes from the assumption that the *plural form* is actual evidence of plurality. If that sentence seemed opaque, notice how many times a statement or article uses “we” instead of “I”, and it will be less so.

### Recycled Wine, Fermenting

The cast is not only small, it is also, by any evidentiary standard, *forgetful*. Every major claim this “movement” advances has been advanced before, answered in public, with evidence, and often years ago - and is then advanced again, unchanged and completely ignoring any rationale or evidence presented previously (to the same people), as if the answer had never been written.

* **The license argument.** Reticulum is “not really open source” because its license is not
  approved by a particular orthodoxy. This is answered (now in a new and updated version, for the
  fifth time) in full in [Open Source Means Open Source](#brandolinis-opensource). It was also
  answered in public, at length, at the time of the license change - including the
  arithmetic of who is actually restricted by which license. It is repeated *ad infinitum* anyway.
  Quite a conversation starter, apparently.

* **The distribution argument.** Reticulum is “not properly distributed” because it is not
  packaged as a `.deb` or on some favoured catalogue. Reality: It is available on practically every
  platform with a single command, packaged by the community in a wide range of channels, and
  capable of updating itself over its own network. The argument has been answered; it is repeated.

* **The “stepped back” narrative.** When the primary mirror of the project moved away from
  a public internet platform, it was spun as the founder leaving for good, or now taking on dictatorial
  powers, or abandoning his creation, or any variation or nonsensical combination thereof.
  Those spins always center around justifying that *a vaccuum now needs to be filled*.
  There was no such vaccuum. The narrative is repeated in various forms whenever convenient.

* **The enclosure narrative.** The license is reframed as a “power grab” or an “enclosure”
  of the commons - as if a license whose protocol is public domain and whose conditions
  restrict only harm and appropriation were a form of enclosure. The [most recent](https://gaggl.com/blogs/2026-09-05-enclosure-by-good-intentions/) (and mostly incoherent)
  expression of this narrative is, once again, fluent, polite, and factually hollow. The
  bizarre arguments supporting the “article” include: Defunct and abandoned forks presented
  as living, community forks bearing the very Reticulum License mislabeled as AGPL license vehicles
  (created by “concerned users”), companion app forks correctly retaining the Creative Commons
  licensing used as further evidence of the same and completely abandoned projects propped up
  as being “the ecosystem”. Another case of LLM generated nonsense that the “author” didn’t bother checking.
  The intent is clear here, simply produce more *mass* of the bullshit, so it can be further
  referenced, regurgitated and linked to.

* **The “bullying” narrative.** Whenever the community declines to treat manufactured
  controversies as legitimate, or calmly documents the falsity of claims, or (Lord forbid)
  moves a forum post for violating clearly stated forum rules,
  the response is the same: The documentation is “bullying”, the community is “excluding” people, the
  maintainer is “unprofessional”. In the most recent example, those accusations were made by someone who, in the
  same week, publically called for the Reticulum maintainer’s “removal from the equation”, forged a moderator’s
  username, attempted to drag unrelated individuals into the campaign, and presented a new
  round of outright falsehoods. Contrary to popular belief, the accusation of incivility
  is not the last resort of the wronged; it is the standard reflex of the exposed.

None of the “arguments” engages the answers given repeatedly, and extensively. That is the point, and the strategy. The arguments are not produced for the purpose of being engaged; they are produced for the purpose of *being repeated* - the same wine, poured into new bottles, on a cycle. Each cycle is short, cheap to produce, and (thanks to freely available fluent text generation) now nearly effortless. The intended audience is not the community, which has heard it all before. The intended audience is the newcomer, who has not.

### The Method, of Madness

The method behind the pattern is consistent and simple enough to be described precisely:

**Bullshit asymmetry**

Producing a fluent, plausibly-sourced smear is now the work of minutes. Refuting it to the standard this manual demands is the work of days, and the refuted smear is replaced by the next one within the week. This asymmetry isn’t just a fine point of the campaign; **it is the campaign**. The goal is exhaustion - the slow conversion of the community’s time and attention from building to defending.

**Weaponized concern**

The register of the campaign is almost always the register of solicitude: “we are worried about the ecosystem”, “we just want what is best for the community”, “this is about the future of the project”. The concern is directed, without exception, at the things the campaign wants changed, and the change it wants is always the same: **The replacement of the reference’s authority with its own**. Concern is the *costume*; capture is the choreography. It is the oldest form of cheap power grab in the book.

**Event seizure**

Any event - a license change, a platform move, a forum moderation decision, a subreddit closure, a security notice, even the most banal messages from maintainers or known contributors - are seized, stripped of their actual context, and re-narrated as evidence of the same pre-written story. The subreddit that was closed after its moderator vanished  and ceased moderating (according to *prior agreement with said moderator*) becomes “the maintainer shutting down dissent”. Moving away from a highly centralized online platform becomes “the founder retreating”. The license becomes “the enclosure”. The pattern is so reliable that the story could be pre-written by by a lightly mechanized quill; only the date changes. The actual real-world context of these events is documented, in public, in each case; the re-narration proceeds regardless.

**The legitimacy circuit**

The campaign invests heavily in the places where legitimacy is minted: Conference talks, blog platforms, social threads, and forums - presented as if these appearances constituted some sort of ecosystem-wide groundswell rather than the same dozen people moving through the same circuit. The LLM-generated articles cite the LLM-generated ports; the ports are praised in the articles; the managers of the ports spread the articles, and echo them on the forums and internet platforms; the conference presentations cite the forums. Random bypassers with the need for a cause watch the conference presentations and take on the holy duty of Internet Soldier. The circuit is closed, self-referential, and (to a reader encountering it fresh) convincing. It is also, entirely, **a loop of bullshit**.

**The prior-work minefield**

The machine-generated implementations have a consequence beyond attention: They flood the space with fake “prior work”. The effect, as the license discussion predicted in the beginning of 2025, is the creation of a minefield of sloppy repositories that can later be matched against any genuine project, and attempt to claim prior art, or even worse: Dissuade actual, honest developers or builders from taking up a real project they might have succeeded with, because they now believe it has already been done. Just as importantly, it also buries real efforts under machine-generated noise. The machine-ports are not failed attempts to contribute. They are (disregarding intentions, but effectively) the campaign’s long game, deployed as inventory.

### A Persistent, But Fragile Triad

This chapter as a whole has documented three fronts: The legal-ideological attack on the license ([Open Source Means Open Source](#brandolinis-opensource)), the substitution and usurpation pattern in machine-generated implementations ([Assistance Versus Machine Substitution](#brandolinis-assistance-versus-substitution)), and the takeover narratives examined in this section. They are three fronts of the same operation, run by the same cast.

* The license attack and other urgency-engineered narratives are the *cover*: They supply
  the ideological justification for treating the reference as illegitimate, and needing replacement.
* The ports are the *inventory*: they supply the “replacements” that the narrative claims
  the ecosystem needs.
* The takeover narrative is the *objective function*: the repeated, persistent, escalating claim that
  the reference should be replaced, and that the speakers themself are the natural heirs.

Each front depends on the others, and all three depend on a single, fragile assumption: That their audience cannot count. Restore the count, and the charade collapses into what it is:

**A small group of people, obsessively orbiting a technology they did not build, synthetically producing the
appearance of a constituency they do not have, in service of a takeover they cannot justify.**

### What The Pattern Is Not

It is important, to also say what this pattern is *not*, exactly because the campaign depends on being mistaken for such things.

**It is not criticism**

The Reticulum community has always had lively, rigorous criticism - of decisions, of priorities, of direction - and it has always engaged that criticism on the merits, and changed course and development priorities many times. The license discussions at the time of the change were extensive, public, and answered in full, including with the critics themselves. Core protocol decisions were always discussed and evaluated in the community. The complex coordination and execution of several protocol upgrades between a loosely organised group of developers, node operators and users have succeeded surprisingly fluidly. All of these are success stories that the “critics” **always** ignore. Real criticism engages the content and accepts evidence. The campaign engages nothing.

**It is not a community**

Communities *build things*, maintain them, and have skin in the game; long-term users, operators of nodes, authors of real applications, people whose traffic flows through the network every day. A community has a stake. The “movement” only has an agenda.

**It is not a debate**

A debate has parties who evaluate arguments and evidence, and as a function of that, the debate moves forward, perpetually. The campaign’s arguments, as shown above, are not designed to survive contact with answers, but to be repeated past them. You cannot debate a loop. You can decline to perform for it, though.

### Intent & Consequence

While it would provide for interesting speculation, we do not need to know what the individuals in the cast *intend*, and this document will not speculate about their inner lives. People may believe their own narratives entirely, or partly, or not at all; **the pattern is the same in any case**, and the pattern is what matters here, since it is the exact thing that has been so insidiously destructive and resource wasting for the actual Reticulum project and community, ever since Reticulum was more widely discovered, popularized, and became a prime target for all sorts of grift known to man.

The consequences are very real:

* **Time**. The community’s scarcest resource is the attention of skilled people who actually build
  and maintain the network. The campaign converts that attention into reactive defence, on a cycle
  with no end.

* **Harm**. Hastily machine-generated implementations, marketed as drop-in replacements and carrying
  traffic onto shared networks, mislead users and can damage the network and its neighbours.
  We, the actual reticulum community, all rely on these networks every day, and it is my belief
  that we need to defend them. The fabricated measurements and laundered authorship examined in this chapter are not
  editorial embellishments; they are the mechanism by which real users are induced to run
  unverified, and often destructive software.

* **Erosion of the currency of trust**. Every manufactured scandal, every fluently polite smear, every
  fabricated “movement” debases the currency of trust and degrades it for **everyone**;
  including, most of all, the honest projects that come after. This is deep harm, and
  it is the primary reason this chapter exists.

Whatever the intent - profit, control, attention, or a simple, obsessive inability to stop - the mechanism is the same, and the response should be *calibrated to the mechanism as a whole*, not to the individual person acting as the current avatar for it.

### Recognition & Response

For anyone who encounters the pattern fresh, here is a proposal on how to recognise it, and what to do about it.

**Recognition:** The pattern is recognisable in minutes, once the signs are known:

* Claims that have been answered before, repeated as if never answered.
* The register of solemn concern applied, without exception, in one direction.
* A severe allergic reaction to answering any questions posed.
* A cast that is small, overlapping, and frequently anonymous, with the *plural form* doing the
  work of plurality.
* Sockpuppet theater: The same person or footsoldiers thereof appearing as several “supporters”
  (and occasionally slipping up mid-performance).
* Articles, ports, and forum threads that cite and reference each other in a closed loop.
* The immediate, reflexive turn to “bullying”, “exclusion” and “toxicity” whenever the record is
  documented.
* A complete absence of engagement with the substance of the answers given, and a complete
  absence of stake in the network itself.

**Response:** A constructive response is one that is proportionate, and does not cost the
community its resources, sanity and dignity:

* Engage the content once, on its merits (if any), with evidence, in public, and then refer to the
  existing records. The answers already exist; they do not need to be re-derived for every new
  bottle of piss-sour burgundy served from a man behind the curtains. I will do my best to keep this
  chapter up to date with such answers and records, for easy reference, but other great resources
  exist.
* Do not become part of the theater performance. The “movement” feeds on engagement in *any* form;
  attention is its fuel, and outrage is as good as endorsement for them, if not better.
* Do the headcount. When the audience is reminded that a “movement” is a dozen people
  recycling answered falsehoods, its projected power dissipates. The power was never real;
  only the audience’s own assumption of scale can make the illusion effective. A polished-looking
  “ground up” implementation might look like the work of many people, but is most likely
  just the result of an LLM looping on a laptop for a couple of months (this is weird, but it is
  the reality we now live in). Four different users suddenly singing in unison may look like the
  representatives of a broader sentiment, but is most likely the same person hiding behind the same keyboard.
* Then, spend the saved time on the networks: On building real infrastructure, putting up nodes
  and antennas, on real development, real maintenance, real coexistence, and on the people
  *who actually use Reticulum*. The things that we can only do *together*, as humans. That is
  what the fake “movement” cannot do, no matter how fluent and smooth its productions become.

## Network Health & Coexistence

### Substance Of The Networks

Before examining health, we should consider what is being protected. The networks are not a repository. They are not a website, a social presence, or a set of marketing pages. They are a habitat: A living commons of communication, carried by, from a catious estimate, an intermesh now consisting of over a hundred thousand physical devices, embedded in a plethora of applications and packages, transporting terabytes of traffic every single day - real messages, real coordination, real people - across radios, serial lines, phones, laptops, and backbone servers, in cities, places and ways that no other network reaches.

The protocol belongs to humanity; no one owns it. The network belongs to everyone on it, and its membership is defined by nothing other than participation: A node on a mast, a phone in a pocket, a server routing for its neighbourhood, a developer building on the commons. The network has no gatekeepers because it needs none; it is held together by the same physics and mathematics everywhere, and by a shared expectation of how members behave. That expectation - unwritten, unenforced by any central authority, and just as important as any code - is the subject of this section. The *Zen of Reticulum* calls the software a habitat. A habitat is healthy or unhealthy as a whole, and the health of this one is decided, every day, by the people who live in it.

### Health Is A Property Of The Whole

A network is not made healthy by the excellence of any single part. It is made healthy by the behaviour of every part on the shared medium, and how they interact. And the shared medium is the point. When your node transmits, it transmits into the same spectrum, the same line, the same time, the same mathematical address space, the same bandwidth that its neighbours depend on. Duty cycles, channel etiquette, retry behaviour, announce discipline: These are not private performance details. They are the terms of coexistence, and they bind every member as tightly as the protocol itself.

This is why the health of the network cannot be certified by any single project’s claims, and why the evaluation framework of [Evaluating A Reticulum Implementation](#brandolinis-evaluating) includes respectful citizenship as a core category. A node that is a bad neighbour - that invents its own channel behaviour on shared spectrum, that announces without discipline, that spawns tens of thousands of links to scrape the network, that floods and retries without mercy - is a hazard to every node that shares its medium, regardless of how well its “creator” imagines its own code to work in isolation. On a shared medium, “my software works” is not a complete sentence. The complete sentence is “my software works *and coexists*”. A network’s health deteriorates with its worst-behaved member, and every member has a responsibility to not be *that* member. There is no final, technical solution for this; the solutions are human.

### A History Of What Works

Let’s recall, because it is the ground truth this entire thing rests on, that the coexistence model has *worked* - is working, right now, **at scale**. Reticulum’s protocol decisions have been discussed and evaluated in the community, openly, for years. Protocol upgrades have been designed, coordinated, and executed between a loosely organised group of independent developers, node operators, and users - and have succeeded, repeatedly, without any corporate board, without any central command, and without the collapse that the skeptics predict every second week (while screaming for *GOVERNANCE*). The reference implementation has been developed in the open for over a decade, by a maintainer who answers for it, fixes bugs or issues within hours of their discovery, and is set down in code deliberately kept small enough (the entire protocol implementation under 15,000 lines, including its comments) for a human to read, verify, *and challenge*.

This is the empirical baseline that every narrative examined in [A Movement Of A Dozen](#brandolinis-movement-of-a-dozen) conveniently ignores, in order to justify:

* The claim that the project is a one-man dictatorship
* The claim that the community is excluded
* The claim that the networks need saving from their own founders

The **reality**, documented and reproducible, is that a loose community of humans coordinates complex technical evolution *without* the apparatus the narratives insist is missing. The health of the networks is not a promise for the future; it is a demonstrated property of the past and present, under the leadership and community model that brought it into existence and navigated it through difficult decisions and situations over a decade. **My job is to keep it that way**, and you can be damned certain that I take it seriously.

### The Role Of The Individual

The networks are built by physical acts and human coordination. You cannot prompt an antenna into existence. No model can string up a dipole, or stand in the rain aligning a radio, or coordinate with a neighbour three valleys away about who covers which repeater frequency, or sit down with a newcomer and explain why their first node didn’t announce. These are the acts that make a network *organic* - present in the physical world, resilient because it is *real*, valuable because it is *human*. The machines and technology we use are tools aimed at a well-defined, openly described goal. But the networks themself are composed of intentional human actions, and every node operator is infrastructure for other humans.

This has a corollary for the individual: You do not need permission, and you do not need to be an expert, to participate. Run a node. Help a neighbour. Ask questions in the community, and answer the questions you can. Build something small at first. The network grows by these acts, and they are the most meaningful ones - the things that can only be done together, as humans, in the physical world. The parasitic “movement” that haunts the peripheries of this ecosystem cannot do any of this. It cannot build a node because it does not exist, in any real connected and human sense; only people can, and people are precisely what a self-recurrent loop lacks.

### The Place Of New Implementations

The future of the network includes more implementations - and they are welcome. This chapter is not an argument against implementing Reticulum. The protocol is public domain, by design, and the network is made stronger by genuine diversity: More *good* implementations, honestly made, mean more resilience, more experimentation, more people who understand the protocol deeply *because they have built it themselves*. That is the goal: **For people to understand and own the technology they rely on**. Not to spew out a 637,000 line rust port that fills no meaningful gap or purpose.

What the ecosystem needs, from every implementation, is the ordinary floor that [Evaluating A Reticulum Implementation](#brandolinis-evaluating) establishes, and that the reference has met for over a decade: A human who made it and answers for it; provenance disclosed; attribution given; benchmarks honest or absent; interop demonstrated against the real network; code a human can read. And it needs the one thing that costs nothing and changes everything: **Honest labeling**.

An experimental implementation that says, plainly, as the first thing a user sees: “This is in-progress, experimental, do not depend on it yet, but help if you can”, that is a gift to the ecosystem. It contributes, it invites participation, and it protects users.

The opposite, the polished “drop-in replacement” with fabricated measurements and laundered authorship, does damage far beyond its own users: It dissuades the honest developers who might have built *the real thing*, because the polished slop persuades them the work is already done. That dissuasion is one of the quietest and most expensive harms in this entire affair, and the antidote is honesty at every project’s door.

### Expanding The Commons

Coexistence, reduced to its essentials, is a short formula; the duties of membership in a network no one owns:

* **Be honest.** Say what you are, what you built, how you built it, and what you used to
  build it. Label experimental work as experimental. Credit the work you build on, including
  the reference implementation, in the licenses and in the prose. Concealment is not a
  defence; it is a very clear diagnosis marker.

* **Be owned.** Have a human who made the work and can answer for it. Use assistance, don’t
  substitute. Never sign what you cannot answer for. The chain of accountability is the
  community’s only verification at scale, and every link in it is a *person*, not a facade.

* **Be a good neighbour.** Respect the shared mediums. Do not invent new behaviour in our
  shared space and call it progress. The network belongs to its other members as much as
  to you.

* **Measure honestly, or not at all.** An unfudged measurement is worth more than a headline.
  If you compare, compare against reality - stock, current, real - and publish the methodology
  first. That way, we can *all* learn and improve.

* **Verify against the network.** Compatibility is a property demonstrated with actual nodes,
  on actual media, against the actual current protocol, over a period of *years*, not 48 hours.
  And not a claim pinned to an old snapshot over loopback.

* **Participate as a member.** Ask, answer, help, build. *Advertising at* the community is not
  the same as being part of it, and it is **not** the first thing you should do.

None of this is a high bar. It is the bar the reference implementation has met, in public, for over a decade, and the bar the ecosystem has adopted organically itself, successfully, through every protocol upgrade it has ever coordinated, and everything running on Reticulum today, that people actually use. It is not a new requirement; it is the existing, working culture of the networks, now written down so that newcomers can find it and so that those who would exploit us cannot claim they never saw it.

### Defence Of The Commons

The networks need defending - not because they are under severe physical attacks (yet), but because attention, talent and resources is being stolen from them, trust is being mined against them, and its newcomers are being harvested by the machinery documented in this chapter. Defence, for a commons, has specific shapes, and it is not what the theater would like it to be.

* Defence is **documentation**: Records, kept public, of what was claimed, what was
  answered, and what turned out true.
* Defence is **a headcount**: Calm, unexcited reminders that a “movement” might just be a dozen
  people having a tantrum.
* Defence is **honesty in action**: The visible, ordinary practice of the good behaviour
  by the people who actually run the networks.
* And defence is **building**: Every node raised, every page of *real* documentation, every
  honest implementation, every new user helped into the community with the knowledge to know
  what they are doing is more durable than any rebuttal, because it adds to the thing being
  defended.

---

**The theatre cannot keep up with a network.**

**It can only orbit it, while it recycles its own sour piss.**

---

A lot of us rely on these networks every day. They carry our messages, our coordination, our friendships, and in some places, our safety. That is exactly why they are a target:

They are valuable, free, and very hard to shut down. The response is not to become aggressive. It is to be *more* of what the network already is: Real, open, owned, and shared.