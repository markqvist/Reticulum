## Void Grants: Legal Foundations of Machine-Generated Code
*From the [Brandolini's Reference](https://reticulum.network/manual/brandolinis.html) chapter of the Reticulum Manual.*

A grant of rights is only as real as the rights behind it. A license conveys what its issuer holds, and nothing more. A derivative may be distributed only under whatever license covers what it took. And over a work that a machine originated, no human holds anything at all.

Each of these statements is a matter of settled statute and case law, and this document sets out the authorities. The conclusions they support are:

1. A software implementation generated from a licensed work by a machine, published under its operator's claimed copyright and license, **conveys rights the operator never possessed**.
2. **Its grant is void**. The projects, products, and promises built upon such grants stand on nothing. A field of void grants is a minefield for everyone who crosses it.

This document is a general examination of copyright law as it applies to machine-generated code. It is not legal advice.

### I. The Foundational Statute: Translation Is Copying

The starting point is the statutory definition of the class of works at issue. Title 17, United States Code, section 101 provides the definition of a derivative work:

> A "derivative work" is a work based upon one or more preexisting works, such as a *translation*, musical arrangement, dramatization, fictionalization, motion picture version, sound recording, art reproduction, abridgment, condensation, or *any other form in which a work may be recast, transformed, or adapted*.

Section 101 further provides that *"the terms 'including' and 'such as' are illustrative and not limitative"*. As such, the list is a list of *examples*, and the very first example is translation. The definition also reaches, in its own words, *"any other form in which a work may be recast, transformed, or adapted"*.

The exclusive right at issue is defined in section 106:

> Subject to sections 107 through 122, the owner of copyright under this title has the exclusive rights to do and to authorize any of the following:
> (1) to reproduce the copyrighted work in copies or phonorecords;
> (2) to prepare derivative works based upon the copyrighted work;
> (3) to distribute copies or phonorecords of the copyrighted work to the public by sale or other transfer of ownership, or by rental, lease, or lending;

Violation of any of these rights is infringement. 17 U.S.C. § 501(a).

Taken together, the provisions yield a construction that is difficult to improve upon and impossible to escape:

1. **A port is a translation.** A work that takes a program written in one language and from it produces a program written in another language, implementing the same behavior, is a translation of the original - whatever mechanism performed it, and however the surface presentation differs.
2. **A translation is a derivative work.** Section 101 says so, explicitly.
3. **Preparing a derivative work is the copyright owner's exclusive right.** Section 106(2) says so explicitly. A derivative work prepared without authorization, or outside the scope of any authorization, infringes that right.

The common objection - "the code is in a different language, so it is completely different" - is not a legal argument; it is the definition of what the statute already classifies.

Translation *is the paradigm* of derivative authorship, not an exception to it. If translating a work without permission was a defense, the derivative-work right would be meaningless; every infringing adaptation would simply need to be "different enough" to count as a translation of its source.

Nor does the identity of the translator change the analysis. The statute asks whether the work is "based upon" a preexisting work. It does not ask who or what performed the translation. A machine that ingests a licensed work and reproduces a translated transformation of it has performed mechanical translation; the output is a derivative of the ingested work, and the law governing derivative works applies to it exactly as it applies to a translation made by hand.

### II. Ideas Are Free, Expressions Protected

The second foundation is the distinction between what a work *is* - its ideas, its processes, its systems - and the *expression* in which those ideas are embodied. The distinction is codified in section 102(b):

> In no case does copyright protection for an original work of authorship extend to any idea, procedure, process, system, method of operation, concept, principle, or discovery, regardless of the form in which it is described, explained, illustrated, or embodied in such work.

The principle is older than the statute, and its application to software is settled. An author may own the particular code in which a method is expressed; the method itself, the process, the algorithm, belongs to no one - because *"the sine qua non of copyright is originality"* (*Feist Publications, Inc. v. Rural Telephone Service Co.*, 499 U.S. 340, 345. 1991). And ideas are not original to anyone in particular, *Baker v. Selden*, 101 U.S. 99 (1879), established the line: Copyright in a book describing a system does not prevent others from practicing the system.

Applied to a communications protocol, the structure is clean:

---

**An implementation of a public-domain protocol, honestly reasoned and written by humans, is welcome and unencumbered, and owes nothing to any license. An implementation generated from a licensed implementation is a derivative of licensed work, subject to its conditions and to the ordinary copyright of its source.**

---

The public-domain status of the protocol's ideas changes nothing about the copyright in an implementation's expression. A person who copies an implementation - by machine or by hand - cannot defend the copying by pointing to the protocol, because the protocol covers the ideas, not the symbols in which someone expressed them.

A further misconception can be dismissed here; the recently popularized "clean-room" claim about the absence of copying. A [clean-room](https://reticulum.network/manual/brandolinis.html#the-clean-room-delusion) is a not a magic label achievable by LLM, but a specific, institutionalized procedure for proving to a court that copying did not occur: Physically separated teams, written functional specifications, attestable non-exposure, and no access to the original by the implementers (*Altai*, 982 F.2d at 709–11).

*"I created a clean-room implementation by feeding the original source code into a machine"* attempts to *claim* the certified, legally established procedure for proving the absence of copying by describing, in the same breath, a process **composed entirely of copying**. The word is deployed because the procedure it names is what the claimant would *need to have happened*.

### III. Machine Output Has No Author

The third foundation is the human authorship requirement. It is settled at both levels of the federal courts and in the Copyright Office's administering practice.

In *Thaler v. Perlmutter*, the district court held that *"copyright law protects only works of human creation,"* and that *"human authorship is a bedrock requirement of copyright"* (687 F. Supp. 3d 140, 146, D.D.C. 2023). On appeal, the United States Court of Appeals for the District of Columbia Circuit affirmed, holding that the Copyright Act *"requires all eligible works to be authored in the first instance by a human being"* (No. 23-5233, D.C. Cir. Mar. 18, 2025).

The requirement traces to the ordinary meaning of the statutory term. In *Burrow-Giles Lithographic Co. v. Sarony*, the Supreme Court defined an "author" as *"he to whom anything owes its origin; originator; maker; one who completes a work of science or literature"* (111 U.S. 53, 57–58, 1884), and more recently described the author as *"the person who translates an idea into a fixed, tangible expression entitled to copyright protection"* (*Community for Creative Non-Violence v. Reid*, 490 U.S. 730, 737, 1989).

---

**A machine does not owe expression its origin; it reproduces it. No court has recognized copyright in material created by non-humans, and the courts that have addressed the question have rejected it. If you create by machine generation, you do not own the output.**

---

The Copyright Office's registration guidance applies the requirement to generative systems in terms that are directly on point. The Office asks:

> whether the "work" is basically one of human authorship, with the computer [or other device] merely being an assisting instrument, or whether the traditional elements of authorship in the work (literary, artistic, or musical expression or elements of selection, arrangement, etc.) were actually conceived and executed not by man but by a machine.

- *Copyright Registration Guidance: Works Containing Material Generated by Artificial Intelligence*, 88 Fed. Reg. 16190, 16192 (Mar. 16, 2023)

And it states the consequence: *"If a work's traditional elements of authorship were produced by a machine, the work lacks human authorship and the Office will not register it"* (*Id.*).

On the role of prompts, the Office is equally explicit: when a system receives a prompt and produces a work in response, *"these prompts function more like instructions to a commissioned artist - they identify what the prompter wishes to have depicted, but the machine determines how those instructions are implemented in its output"* (*Id.*).

The agency applied this standard and excluded machine-originated material from registration in the leading administrative case. In *Zarya of the Dawn* (Cancellation Decision, Feb. 21, 2023, Registration No. VAu001480196), the Office cancelled registration of images generated by the Midjourney service, holding that *"it was Midjourney-not [the author]-that originated the 'traditional elements of authorship' in the images"*, while preserving protection for the human-authored text and the human selection and arrangement of the work.

The Copyright Office's 2025 report on AI copyrightability reaches the same conclusion:

> Based on the functioning of current generally available technology, prompts do not alone provide sufficient control.

- U.S. Copyright Office, *Copyright and Artificial Intelligence, Part 2: Copyrightability*, at iii (Jan. 29, 2025)

The report's analysis is explicit: *"The Office concludes that, given current generally available technology, prompts alone do not provide sufficient human control to make users of an AI system the authors of the output. Prompts essentially function as instructions that convey unprotectible ideas"* (*Id.* at 18).

Its guiding distinction is stated plainly: *"The use of AI tools to assist rather than stand in for human creativity does not affect the availability of copyright protection for the output"* while *"Copyright does not extend to purely AI-generated material, or material where there is insufficient human control over the expressive elements"* (*Id.* at iii).

The boundary is therefore not "AI or no AI". It is *assistance or substitution*: Whether a human exercised sufficient creative control over the expressive elements and can answer for them, or whether the machine originated them and the human merely supplied instructions and a signature. That is a question of fact in each case, determined from the record of how the work was made.

Two facts follow, and stated together, they form the base legal reality:

1. **A work whose expressive elements were originated by a machine contains no valid new copyright: It has no human author. To the extent that the same work reproduces a preexisting copyrighted work without explicit license, it is at the same time an unauthorized derivative. It is unowned for anything new it contains, and unlicensed for everything taken.**
2. **Its operator therefore holds no copyright in it and no grant over it - and a person who holds neither copyright nor grant can convey neither.**

The first fact makes the work **unownable** by its operator. The second makes it infringing against its source. Neither replaces the other:

- The absence of copyright in machine output does not make the output free for anyone to take; it makes it unowned.
- This is a different thing entirely, especially when what it contains is someone else's expression.

### IV. License Conditions Bound the Grant

The fourth foundation governs what a license *is*. A copyright owner may grant permission to use the work on conditions. The conditions define the scope of the permission. Use outside the scope is use that was never authorized.

In *Jacobsen v. Katzer*, 535 F.3d 1373 (Fed. Cir. 2008), the Federal Circuit held that the conditions of an open-source license are *conditions of the copyright license itself*, not mere contractual promises, and that a licensee operating outside them is an infringer:

> Copyright holders who engage in open source licensing have the right to control the modification and distribution of copyrighted material.

> The choice to exact consideration in the form of compliance with the open source requirements of disclosure and explanation of changes, rather than as a dollar-denominated fee, is entitled to no less legal recognition.

> It is outside the scope of the [license] to modify and distribute the copyrighted materials without copyright notices and a tracking of modifications from the original computer files.

- *Id.* at 1381–82

The doctrinal mechanism is settled: *"A copyright owner who grants a nonexclusive license to use his copyrighted material waives his right to sue the licensee for copyright infringement"* within the scope of the license. If, however *"the licensee acts outside the scope, the licensor can bring an action for copyright infringement"*: An act outside the granted scope **is infringement** (*Sun Microsystems, Inc. v. Microsoft Corp.*, 188 F.3d 1115, 1121, 9th Cir. 1999; *Graham v. James*, 144 F.3d 229, 236, 2d Cir. 1998; *S.O.S., Inc. v. Payday, Inc.*, 886 F.2d 1081, 1087, 9th Cir. 1989).

Whether a given license term is a condition of the grant or a mere covenant is determined from the license's own language; conditions that limit what may be copied, modified, and distributed - the attribution terms, the notice terms, the modification-tracking terms, the field-of-use terms - are the boundaries of the copyright grant (*MDY Industries, LLC v. Blizzard Entertainment, Inc.*, 629 F.3d 928, 940, 9th Cir. 2010).

Three consequences follow for the analysis at hand. They are not hypothetical.

**First, the conditions are measured at the moment of copying**

A work is licensed under whatever conditions applied when the reproduction, adaptation, and distribution occurred. There is **no** period in which copying a licensed work is "free" because the copy was made by a machine; the machine is the *licensee's tool*, and the licensee is bound by the conditions regardless. A derivative generated without satisfying the conditions - without the attribution, without authorization for the manner of use - was never within the scope of the license, from the first instant of its existence.

**Second, breach does not restore rights that never attached**

The district court in *Artifex Software, Inc. v. Hancom, Inc.*, No. 16-cv-06982-JSC (N.D. Cal. Sept. 12, 2017), analyzing the GPL's termination provisions, observed that *"the language of the GPL suggests that [the licensee's] obligations persisted beyond termination of its rights to propagate software using Ghostscript,"* because the source-code obligation recurs each time a covered work is conveyed. The same structure operates a fortiori where a derivative was produced *outside* the license entirely: No grant ever attached, and no subsequent event creates one.

**Third, the settled conditions are the enforceable core**

The attribution and notice conditions rest on the settled doctrine above. Novel conditions  (restrictions on field of use, restrictions on how the work may be consumed) are enforceable as conditions of the grant when clearly drafted, but their enforcement history is thinner. The argument that a derivative is unlicensed does *not* depend on the novel conditions being vindicated; it needs **only** the settled ones, and the ordinary law of derivative works, to stand.

### V. The Void Grant

The preceding sections assemble into a single structure. Let us apply it to an example situation: 

- A project presented as an independent implementation of a protocol; "ground-up", "from scratch" or "clean-room" work.
- The actual history shows continuous, machine-mediated ingestion of a licensed reference implementation.
- The output is generated at a scale no human could produce or review, with the provenance of the process obscured.

**Step One: The derivative**

The project's output is a translation of the licensed implementation: A derivative work, produced by a copy process. 17 U.S.C. §§ 101, 106(2). Preparing it without authorization infringed from the first moment of its existence. *Id.* § 501(a).

**Step Two: The license**

The derivative was produced outside the conditions of the license; without the notices, without the attribution. The license never attached (*Jacobsen*, 535 F.3d at 1381–82).

**Step Three: Authorship**

The expression was originated by a machine. No human can account for its creative decisions, and no human authored it. It contains no valid new copyright (*Thaler*, 687 F. Supp. 3d at 146; No. 23-5233, D.C. Cir. 2025; 88 Fed. Reg. at 16192).

**Consequence: Void Grant**

The statute supplies the consequence. Section 103(a) provides:

> The subject matter of copyright as specified by section 102 includes compilations and derivative works, but protection for a work employing preexisting material in which copyright subsists does not extend to any part of the work in which such material has been used unlawfully.

And section 103(b) provides that copyright in a derivative work *"extends only to the material contributed by the author of such work."* The legislative history states the point without ambiguity: *"An unauthorized translation of a novel could not be copyrighted at all"* (H.R. Rep. No. 94-1476, at 57, 1976).

In our example, the operator of the derivative's copy process decides to assert copyright over the output, and licenses it to the world under terms of the operator's choosing, for example the Apache License.

But the operator holds no copyright in machine-originated content (section III) and no license over the source from which it was derived (sections I and IV).

For the derived material, the operator's copyright claim **is an assertion of a right that never existed**. The material was used unlawfully, and section 103(a) withholds protection from *every* part of the work in which it appears. For the machine-originated remainder, the operator holds no copyright either, for lack of any human author.

The operator's license to the world is a promise the operator had no power to make. Every person who receives the work believing they received a valid grant has received **a void grant**, and stands, as a matter of settled law, in the position of a downstream user of an unauthorized derivative, whatever they were told at the time.

This is a cascading consequence, and it is why the pattern is a hazard. No combination of self-granted licenses - "MIT," "Apache," "public domain," anything at all - can transfer rights the operator never held. Every downstream project, product, or deployment built on the derivative is built on unlicensed reproduction of a third party's work, whether or not it knew, whether or not it was told, and whether or not the marketing was plausible.

The longer the derivative circulates unexamined, the more it becomes embedded, forked, vendored, depended upon, and the more expensive its correction becomes for everyone who trusted it. A field of superficially real projects, repositories, and licenses that **in reality confer nothing on anyone who relies on them is a minefield**, in the most precise sense the law allows: The rights they purport to grant *were never possessed*.

The law defines what may be asserted, not what will be. The copyright owner may choose whether and how to assert these rights, and at what point in time. The exposure exists regardless, and for *every* downstream that trusted the void grant. This is the scope of the hazard that the conduct exemplified here produces.

### VI. Fair Use Does Not Rescue This Pattern

Every defendant raises fair use. It is an essential and important limitation in the service of free speech, accountability, criticism, education and other important domains. Therefore, it must be considered, and in the case exemplified here, it fails.

Fair use is a limitation on the exclusive rights, evaluated case by case under four factors: The purpose and character of the use; the nature of the copyrighted work; the amount and substantiality of the portion used; and the effect of the use on the potential market for or value of the work (17 U.S.C. § 107).

On the first factor, the governing standard is *Andy Warhol Foundation for the Visual Arts, Inc. v. Goldsmith*, 598 U.S. 508 (2023), in which the Supreme Court held that:

> In sum, the first fair use factor considers whether the use of a copyrighted work has a further purpose or different character, which is a matter of degree, and the degree of difference must be balanced against the commercial nature of the use

The question is whether the use serves a further purpose, not whether the surface changed. A derivative that exists to serve as the same thing as the original, marketed to the people who would otherwise use the original, has not acquired a further purpose by being translated; the surface changed, the function did not, and the use is commercial.

The remaining factors resolve the same way. Source code is expressive creative work, not bare fact. The pattern under examination copies the whole; a complete implementation, ingested and translated in its entirety. And the market effect is the decisive factor, because it is engineered: A derivative marketed as a drop-in replacement for the work it was copied from is not a complement to the original's market, it is a substitute for it. The Supreme Court has long held that use of a work to satisfy the market demand for the original is the paradigm of an *unfair* use (*Harper & Row, Publishers, Inc. v. Nation Enterprises*, 471 U.S. 539, 566–67, 1985).

The one case that is always raised in response, *Google LLC v. Oracle America, Inc.*, 593 U.S. 1 (2021), holds less than it is believed to. The Court there assumed *"for argument's sake, that the material was copyrightable"* and held *"that the copying here at issue nonetheless constituted a fair use"* (*Id.* at 11).

The material in question was a thin slice of *declaring code*, which the Court found sits, *"if copyrightable at all, further than are most computer programs (such as the implementing code) from the core of copyright"* (*id.*), in a use that built a new platform for a new environment, with the copier **having written the vast majority of its own code**. By comparison: A wholesale translation of an entire implementation, marketed as a substitute for it, is **not** that case; it is the other end of every factor.

The valuable zones of fair use remain, and they are important. **Commentary and criticism**, quoting from a work to review, discuss or criticize it. **Teaching and scholarship**, explaining concepts and quoting excerpts, is its traditional beneficiary.

### Conclusion

The law is neither obscure nor new. The conclusion it yields can now be stated:

- A machine translation of a protected implementation **is a derivative work**, and an unauthorized derivative **is an infringement**, whatever language it speaks and whatever machinery produced it.
- A work whose expression a machine originated has no human author, no valid new copyright, and without valid copyright **no license can be granted on it**.
- § 103 withholds protection from every part of a derivative in which protected material was used unlawfully. A license is a grant with conditions, and a derivative made outside the conditions **never received a grant**.
- A person who holds no copyright and no grant **can convey neither**, and *every* downstream consumer who received from them received a **void grant**.

This is a *catastrophic* failure state for all who want to create things good and useful: The projects that inherit only void grants and liability believing they have inherited foundations, the users who depend on code that no one on earth can answer for, the honest builders whose work is buried under a field of plausible-looking impostors.

### Sources and Authorities

Statutory references are to Title 17, United States Code. Case citations are to the official or generally cited reporters. Online links are for reference only. Section numbers refer to the sections of this document in which each authority is principally relied upon.

**Statutes**

- [17 U.S.C. § 101 (definitions: "derivative work," "including," "publication") - I, II](https://www.law.cornell.edu/uscode/text/17/101)
- [17 U.S.C. § 102(b) (idea/expression) - II](https://www.law.cornell.edu/uscode/text/17/102)
- [17 U.S.C. § 103(a)–(b) (derivative works employing unlawfully used preexisting material) - V](https://www.law.cornell.edu/uscode/text/17/103)
- [17 U.S.C. § 106(1)–(3) (exclusive rights: reproduction, derivative works, distribution) - I](https://www.law.cornell.edu/uscode/text/17/106)
- [17 U.S.C. § 107 (fair use) - VI](https://www.law.cornell.edu/uscode/text/17/107)
- [17 U.S.C. § 501(a) (infringement) - I, V](https://www.law.cornell.edu/uscode/text/17/501)

**Judicial decisions**

- [*Jacobsen v. Katzer*, 535 F.3d 1373 (Fed. Cir. 2008) - IV, V](https://www.casemine.com/judgement/us/5914b290add7b04934760a54)
- [*Sun Microsystems, Inc. v. Microsoft Corp.*, 188 F.3d 1115 (9th Cir. 1999) - IV](https://law.justia.com/cases/federal/appellate-courts/F3/188/1115/629501/)
- [*Graham v. James*, 144 F.3d 229 (2d Cir. 1998) - IV](https://caselaw.findlaw.com/court/us-2nd-circuit/1011522.html)
- [*S.O.S., Inc. v. Payday, Inc.*, 886 F.2d 1081 (9th Cir. 1989) - IV](https://law.justia.com/cases/federal/appellate-courts/F2/886/1081/19091/)
- [*MDY Industries, LLC v. Blizzard Entertainment, Inc.*, 629 F.3d 928 (9th Cir. 2010) - IV](https://law.justia.com/cases/federal/appellate-courts/ca9/09-15932/09-15932-2011-02-25.html)
- [*Artifex Software, Inc. v. Hancom, Inc.*, No. 16-cv-06982-JSC (N.D. Cal. Sept. 12, 2017) (settled; dismissed with prejudice Jan. 2018) - IV](https://storage.courtlistener.com/recap/gov.uscourts.cand.305835/gov.uscourts.cand.305835.54.0_1.pdf)
- [*Thaler v. Perlmutter*, 687 F. Supp. 3d 140 (D.D.C. 2023), aff'd, No. 23-5233 (D.C. Cir. Mar. 18, 2025) - III, V](https://www.bitlaw.com/source/cases/copyright/Thaler-Perlmutter-Dct.html)
- [*Burrow-Giles Lithographic Co. v. Sarony*, 111 U.S. 53 (1884) - III](https://supreme.justia.com/cases/federal/us/111/53/)
- [*Community for Creative Non-Violence v. Reid*, 490 U.S. 730 (1989) - III](https://supreme.justia.com/cases/federal/us/490/730/)
- [*Feist Publications, Inc. v. Rural Telephone Service Co.*, 499 U.S. 340 (1991) - II](https://supreme.justia.com/cases/federal/us/499/340/)
- [*Baker v. Selden*, 101 U.S. 99 (1879) - II](https://supreme.justia.com/cases/federal/us/101/99/)
- [*Computer Associates International, Inc. v. Altai, Inc.*, 982 F.2d 693 (2d Cir. 1992) - II](https://law.justia.com/cases/federal/appellate-courts/F2/982/693/137252/)
- [*Andy Warhol Foundation for the Visual Arts, Inc. v. Goldsmith*, 598 U.S. 508 (2023) - VI](https://www.supremecourt.gov/opinions/22pdf/21-869_87ad.pdf)
- [*Google LLC v. Oracle America, Inc.*, 593 U.S. 1 (2021) - VI](https://supreme.justia.com/cases/federal/us/593/18-956/)
- [*Harper & Row, Publishers, Inc. v. Nation Enterprises*, 471 U.S. 539 (1985) - VI](https://supreme.justia.com/cases/federal/us/471/539/)

**Administrative and policy authorities**

- [*Copyright Registration Guidance: Works Containing Material Generated by Artificial Intelligence*, 88 Fed. Reg. 16190 (Mar. 16, 2023) - III](https://www.federalregister.gov/documents/2023/03/16/2023-05321/copyright-registration-guidance-works-containing-material-generated-by-artificial-intelligence)
- [*Zarya of the Dawn*, U.S. Copyright Office (Cancellation Decision, Feb. 21, 2023), Registration No. VAu001480196 - III](https://www.copyright.gov/docs/zarya-of-the-dawn.pdf)
- [U.S. Copyright Office, *Copyright and Artificial Intelligence, Part 2: Copyrightability* (Jan. 29, 2025) - III](https://www.copyright.gov/ai/Copyright-and-Artificial-Intelligence-Part-2-Copyrightability-Report.pdf)
- [H.R. Rep. No. 94-1476 (1976) - V](https://law.resource.org/pub/us/works/aba/ibr/H.Rep.94-1476.pdf)
