.. _distributed-development:

***********************
Distributed Development
***********************

This chapter of the manual provides the conceptual basis for understanding *why* ``rngit`` exists, what it aims to achieve, and the kinds of spaces it seeks to reestablish. For the practical details of operating the system, refer to the :ref:`Git Over Reticulum<git-main>` chapter.


The Original Architecture
=========================

When Torvalds created Git in 2005, he designed a tool that reflected a specific philosophy of collaboration. Every copy of a repository would be a complete, sovereign instance. There was no central server, no single point of failure, no gatekeeper. Developers would be able to work independently, exchange patches directly, and maintain their own branches indefinitely. This concept was - and is - both beautiful and revolutionary. It's execution is peer-to-peer not as a marketing term, but in the most foundational sense: As fundamental, structural reality.

Such a design emerged from necessity. The Linux kernel development process operated across geographical boundaries, time zones, and organizational affiliations. Contributors did not "log in" to a shared server to do their work; they maintained their own trees, and the flow of code between these trees was negotiated through patches, reviews, and merge decisions. The architecture of Git mirrored the social architecture of the community: Autonomous, competent, and fundamentally distributed in its technical operation.

*The result of that work is, in the most direct sense, what makes it possible for you to read this today.*

There's something very important to take note of here: With Git, developers could collaborate effectively and perfectly well without any central server being present, without platform-mediated visibility into each other's work, and without a centralized authority validating their contributions. They needed *only* a protocol for exchanging differences and a mechanism for verification of authorship. Everything else - social organization, quality control, release management - was handled by careful *human judgment* operating on top of the technical substrate.

What Git provided was not a development environment, but a **language for versioning**. It specified how to represent history, how to compute differences, how to merge divergent branches. It did not specify who could participate, how they should communicate, or what workflows they should follow. These were left to the competence and discretion of the creators using the system.

The Platform Interregnum
========================

What followed represents a very familiar pattern: Tools designed to distribute power were re-centralized by platforms that offered convenience in exchange for control. GitHub, GitLab, and similar services reintroduced the centralization that Git had eliminated architecturally. The activity feed replaced durable artifacts with ephemeral notifications. The social graph and open interaction became as important as the code itself, if not more.

This re-centralization was not technical, as such. It was **ontological**. When every developer pushes to the same server, when every merge is in theory controllable by a platform, when every issue is tracked in a database controlled by a corporation, the nature of collaboration changes. The platform, and its social dynamics, becomes the ground of reality. The platform mediates not just the technical exchange of information and the programmatics, but the social recognition and codices of contribution, the future archival prospects of the work, and the very identity of the project itself.

The consequences extend beyond individual inconvenience. Centralized platforms create single points of failure for entire ecosystem. When a platform changes its terms of service, suspends accounts, removes repositories or ceases operation, entire project histories and community relationships can be disrupted or destroyed. The extractive economics of platform capitalism mean that value created by open-source communities is captured by corporations, while communities remain dependent on infrastructure they do not control. And the surveillance inherent in platform operation means that every action - every commit, every comment, every page view - is logged, analyzed, and potentially monetized or weaponized.

More insidiously, platforms have completely reshaped the culture of development itself. They have created what we could call the **Teahouse Developer**: A participant who treats engineering projects as social venues for opinion-sharing rather than sites of disciplined and careful production. These personages have no actual stakes in the projects they act as leeches upon, and only a very base consciousness of the damage they are incurring in order to feed their attention and external validation dependencies.

When platforms optimize for engagement, when growth is the only metric, when every user with an opinion must have their voice heard, when a random social process is elevated to higher importance than results, the signal-to-noise ratio collapses catastrophically. Competent engineers find themselves drowning in feedback from the incompetent, managing the emotional needs and dysregulations of drive-by commentators rather than solving technical problems.

The platform model is predicated on **unsaturable expansion**. Like almost any industrial system, it cannot function without growth. It pursues no particular aims; it is growth for the sake of growing. There is no saturation point, no concept of "enough". Every barrier to entry must be put down to the very lowest common denominator, every voice must be amplified, every interaction must be converted into content that feeds the machine. This is fundamentally incompatible with the nature of social beings itself. It is also incompatible with serious engineering, which requires focus, discernment, and the right of people who know better to say "no".

Restoration
===========

The ``rngit`` system represents a return to Git's original architectural principles, fortified with cryptographic networking capabilities that were not available in 2005. The ``rngit`` system *is* Git - but running over Reticulum. Welcome back to a world where your work is your own, but where everyone can still reach you - if you want them to.

Just as Git eliminated the need for a central version control server, ``rngit`` eliminates the need for a central hosting platform, "servers" or any kinds of middle-men between the people actually doing the work. By operating over Reticulum, it eliminates the visibility of development activity to platform operators, network observers, state actors and other malicious third-parties.

In this model, the repository node is a **sovereign entity**. It is reachable from anywhere in the Reticulum network but owned, operated, and controlled by the developer or community that runs it. It is an actual home for creative output, not an extraction mechanism to which dues are paid. The node operator decides who may contribute, what standards must be met, and which voices are worth listening to. This is not exclusion; it is **discernment**. It is the necessary exercise of judgment that separates engineering from theatrics.

I did not create this in a fit of nostalgia. I created it because it is a necessary response to the failures of the centralized model. Git's technical architecture was - and *is* - correct. It was the social and economic superstructure built atop it that introduced fragility, exploitation, and environments toxic to actual creativity. By returning to first principles - distributed version control on distributed infrastructure - we recover not just a technical capability, but a mode of collaboration that respects the autonomy of individual developers and the sovereignty of actual communities.


Protocols Over Platforms
========================

The distinction between platforms and protocols is fundamental to understanding the architecture of sovereignty in networked systems. A platform is a service you access; a protocol is a grammar you speak; actions you live. A platform requires permission to enter, a protocol requires only *comprehension* to employ. A platform can change its rules, suspend your account, or cease operation entirely, a protocol persists as long as there are participants who *understand* and *use* it. A protocol is an *idea*, a platform is a machine that turns its users into products.

Platforms operate on a client-server model that inherently creates power asymmetry. Even when platforms are built atop open-source software, the operational instance remains a black box of corporate control. You *may* be able to download *some* of your data, but you cannot download the connections to the people that are the true value-base of the platform, or take them with you if you want to leave.

Protocols, by contrast, are agreements. They specify how systems should communicate, but not who may communicate or on what terms. Email is a protocol; Gmail is a platform. HTTP is a protocol; Facebook is a platform. Git is a protocol; GitHub is a platform. The protocol persists regardless of any particular implementation's success or failure.

The power of protocols lies in their **permissionlessness**. Anyone can implement a protocol without approval. Anyone can extend it, fork it, or use it for purposes unforeseen by its creators. This creates resilience: protocols cannot be easily censored, monopolized, or shut down because they exist as shared understanding rather than centralized infrastructure.

Reticulum is a protocol in this strict sense. It specifies how packets should be formatted, how paths should be discovered, how encryption should be applied. The ``rngit`` system extends this protocol approach to development workflows. It is not an external platform that hosts your repositories; it is a protocol for exchanging repository data, release artifacts, and work documents over Reticulum's encrypted transport. But with a few commands and an old computer, it creates your own infrastructure for hosting repositories, or sharing them with who you choose. *That* is how tools should function, in case we had forgotten.

Unlike platforms, which extract value by creating dependency, there is no entity that can grant or deny you the privilege of running ``rngit``. Your Reticulum identity is not endowed by any platform; it is generated locally and certified by its own cryptographic properties. Your repositories are hosted on nodes you control or nodes operated by communities you trust. Your relationships with other developers are peer-to-peer connections established through cryptographic addressing, not social graph connections managed by recommendation algorithms.

On a platform, exit means abandonment: you lose your history, your relationships, your visibility. With protocols, exit is just migration. When you change your infrastructure, your identity and your work travel with you. There are no middlemen between you and your collaborators. If push comes to shove, you can write your entire life's work and connections to an SD card, swim across the lake, and set up camp on the other side.


Sovereignty Through Infrastructure
==================================

The concept of sovereignty - supreme authority within a territory - has traditionally been applied to nation-states. But in an age where creative work is conducted through digital infrastructure, sovereignty is essential for individuals and communities. **Creative sovereignty** means having supreme authority over the artifacts you produce, the processes by which you produce them, and the terms under which they are distributed. It means not merely legal ownership of copyright, but operational control of the infrastructure that mediates creation, collaboration, and dissemination.

Centralized development platforms strip away most layers of sovereignty. When you host code on a corporate platform, you retain *some* legal ownership of copyright, but you surrender complete operational control. The platform decides what content is acceptable, who can access it, and how it is presented. They can delete your repository, suspend your account, or change the visibility of your work without consent. In reality, legal ownership becomes meaningless as operational control is ceded.

Running your own ``rngit`` node restores this sovereignty. You control the hardware, the network configuration, the backup strategies, and the access permissions. You decide what constitutes acceptable use, who may contribute, and how contributions are evaluated. Taking this responsibility on yourself is an assertion that your creative work is not a product to be harvested by platform economics, but an autonomous activity to be conducted on your own terms.

This sovereignty and responsibility extends to the entry barriers you establish. The ``rngit`` system allows you to configure access controls that filter participants based on cryptographic identity and demonstrated competence. If, for example, someone cannot navigate a command line, or use Reticulum to submit a patch, they most likely lack the required competence to modify your code. In a world that apparently labels this as "exclusion", I would simply refer to it as a minimally acceptable level of quality control.

Such a stance protects projects from the noise that so often overwhelms and completely dilutes platform-based development, where every user with an opinion believes themselves entitled to attention and access to the decision process.


Artifact-Centered Workflows
===========================

Contemporary platform-based development has shifted focus from durable artifacts to ephemeral *activity*. It does not matter what constitutes this activity, as long as it's there. The primary interface is not the repository itself, not the produced artifacts, but the activity feed: *Notifications* of commits, comments, pull requests, and social interactions. Work is measured by velocity, throughput, and the constant stream of updates. This activity-centric model creates constant urgency, discourages discernment, encourages reactive rather than reflective work patterns, and produces vast quantities of ephemeral and useless communication that obscures actual project state and productivity.

The ``rngit`` system enables a return to **artifact-centered workflows**, where the focus is on durable, attributable, versioned outputs rather than the stream of notifications surrounding them. The fundamental unit of work is the commit - signed, immutable records of change. The fundamental unit of production is the signed artifact - a self-verifying package of functionality. The fundamental unit of discussion is the work document - a structured, threaded conversation attached to repositories.

Artifacts can persist independently of any platform's continued operation. A commit signed with your Reticulum identity is attributable to you regardless of where it is stored. A release signed with your private key is verifiable as authentic regardless of which network it traverses, and can be verified offline on any system running Reticulum. The work exists as **cryptographic fact**, distributed over the planet, not as database entries in a corporate cloud.

Such a shift has real psychological consequences. When work is measured in artifacts rather than activity, the pace changes. There is no need for constant visibility, no pressure to perform busyness. Developers can work deeply, reflectively, and submit complete solutions rather than incremental updates designed to maintain presence in an activity feed. The work becomes **substantial**, in the physical sense of the word, rather than performative.

Composable Primitives
=====================

The ``rngit`` system is not a monolithic application prescribing a specific workflow; it is a collection of **composable primitives** that can be arranged to support diverse creative processes. Understanding these primitives as separate, orthogonal capabilities enables users to construct workflows suited to their specific needs and to recombine these primitives in ways unforeseen by the system's designers.

The core primitives include:

* **Repository Hosting**: Bare Git repositories served over Reticulum links, accessible via standard Git commands through the ``rns://`` URL scheme.
* **Identity-Based Access Control**: Fine-grained permissions managed through cryptographically verifiable identity hashes, configurable at the group, repository, or document level.
* **Release Distribution**: Cryptographically signed release artifacts with embedded provenance information, verifiable offline and distributable through any Reticulum or physical path.
* **Work Document Tracking**: Structured, threaded work management attached to repositories, with precise permission controls, and the ability to contain updates or discussions.
* **Forking and Mirroring**: Automated replication of repositories from any accessible Git URL, with metadata tracking upstream relationships for synchronization.
* **Nomad Network Integration**: Page node functionality for browsing repository contents, commit history, and release information through the Nomad Network protocol.

These primitives can be composed into workflows ranging from single-developer projects to complex multi-organizational collaborations. A solo developer might use only repository hosting and release distribution. A research group might add work document tracking for structured peer review. A software distribution network might combine mirroring with cryptographic release verification to create resilient update channels.

The entire system is incredibly light-weight, and can host hundreds of repositories on a Raspberry Pi.

Composability is essential because **creative work is diverse**. Software development, academic research, technical writing, hardware design, music production and data analysis all have different requirements for collaboration, review, and distribution. A platform prescribes a single workflow and forces all users to conform. A protocol provides primitives and allows users to construct workflows appropriate to their domain.

With ``rngit``, you can re-build the system into anything you can imagine. Everything can be modified, extended and hooked into. Adding functionality or automation is never further away than a shell script, a cron-job, or a Python modification of the source.

Distribution Without Intermediaries
===================================

Creating software is only part of the work. Then comes actually getting it to the people needing to use it. Centralized platforms handle distribution through their own infrastructure: Content delivery networks, central package registries, and download servers accessed through platform-controlled interfaces. This convenience masks a fundamental dependency: Your ability to distribute depends on the platform's continued operation, their policies regarding your content, and their technical infrastructure's reach.

The ``rngit`` release system enables distribution strategies **decoupled from any single infrastructure provider**. Releases are cryptographically signed using Ed25519 signatures and packaged in signed release manifests (``.rsm`` files). These manifests contain embedded signatures for each artifact. The manifest provides full verifiability of all release information, and contains embedded release artifact lists, per-file ``.rsg`` signatures, origin information, and the creator's Reticulum Identity. It can also be used to fetch verified updates of the software package over the network, and can always be verified completely offline.

Because releases are self-verifying, they can traverse any network or physical path that Reticulum can establish. A release can travel over LoRa radio, be carried on USB drives through areas without internet connectivity, disseminated over a mirror network, or be distributed through store-and-forward mechanisms on intermittent infrastructure. Recipients can verify authenticity regardless of how they obtained the files. This is particularly valuable in low-connectivity environments where Reticulum may be the only available communication channel.

The ``rngit release`` command provides tools for creating, publishing, fetching, and verifying releases. When fetching a release using an ``.rsm`` manifest, the system validates the manifest signature against the required Reticulum Identity, extracts the origin node and repository path, connects to the origin over Reticulum, retrieves the latest release manifest, and verifies each downloaded artifact against the signatures embedded in the manifest. If any verification fails, the fetch aborts, preventing installation of corrupted or tampered files.

This cryptographic verification replaces the trust model of platform distribution. Instead of trusting that a platform has not been compromised, users verify that artifacts match the signatures created by the developer's identity. It doesn't matter *how* they obtained the artifacts, they can **always** be verified. This security model shifts from **institutional trust** (just believe in the goodness of the platform) to **cryptographic proof** (verify the signatures).

Long Archive
============

Software development is often conceived as an activity of the present only: Solving today's problems, meeting current deadlines, responding to immediate feedback. But the artifacts produced - code, documentation, releases - have lifespans extending *far* beyond their creation. They may be used for decades, studied by future developers, depended upon by systems not yet imagined, or preserved as historical records of technological development.

The ``rngit`` system is designed with this **extended timeframe** in mind, supporting the creation of archives that are durable, portable, and intelligible across generational timescales. Git repositories are always internally complete; they contain full history and can be migrated to new infrastructure without loss of information. Everything that ``rngit`` adds on top of this is stored in normal files in standard formats right next to the Git repository folders, not an esoteric database-cluster two thousand kilometers away. Because releases are cryptographically signed, they remain verifiable as authentic regardless of when or where they are retrieved. Because the system operates over Reticulum, it can function over communication mediums that may outlast the internet as we know it.

This long-term perspective influences technical decisions. The use of well-established cryptographic primitives ensures that signatures will remain verifiable for centuries. The use of standard formats ensures that repositories will remain readable by future tools. The protocol-based architecture ensures that the system can evolve without losing compatibility with existing data.

For critical infrastructure, this archival durability is not optional; it is essential. Communication systems, cryptographic libraries, and safety-critical code must remain available and verifiable for the lifespans of the systems that depend on them. The ``rngit`` system provides the tools to create such archives: distributed across multiple nodes, cryptographically verified, and independent of any corporate or governmental infrastructure, which as history has shown repeatedly, does *not* persist.

Start Of The Road
=================

Distributed development and production over Reticulum is a *different mode of existence* for creative work. It restores the autonomy originally created by Git. It provides local sovereignty over production infrastructure, composability of workflow, and durability of artifact. It lets you filter participation through competence and cryptography rather than incentives of platform operators, raising the quality and enjoyment of work, and protecting the focus of real engineering and creative expression.

This is not a system for everyone, and that is the point. It requires investment - in understanding Reticulum, in configuring infrastructure, in establishing workflows. It requires accepting responsibility for your own tools rather than delegating them to platform operators. It requires the discipline to maintain your own node, manage your own backups, and nurture your own community.

But for those who make this investment, the returns are substantial. You gain **immunity from platform failure**; your work persists regardless of corporate decisions or service outages. You gain **shelter from surveillance**; your development activity is visible only to those that *you* choose to involve. You gain **control over process**; you decide how work is conducted, reviewed, and released, unmediated by terms of service, algorithmic feeds and thousands of uninformed and irrelevant opinions.

Most importantly, though, you regain the **dignity of craft**. Development becomes an activity conducted among peers, equals among equals, mediated by skill and cryptographic proof rather than corporate permission, producing artifacts that stand as independent testimony to competence, functionality or beauty rather than as content feeding engagement metrics. The *work* becomes the point. The artifacts become durable. And the network becomes *one* of the tools you wield in this endeavor.
