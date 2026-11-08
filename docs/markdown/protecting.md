# Protecting Open Networks

#### IMPORTANT
Reticulum is currently transitioning towards full, on-network stamp verification and enforcement via a phased transition:

- The `1.6.0` release completely implements the required mechanisms, and will start excercising the verification system in the transport backend. By default, `1.6.0` does not enable full stamp generation, emission and enforcement, but all of these options can be early-enabled in the configuration.
- The `1.6.1` release will enable full stamp generation and emission of all types by default, but will leave the *enforcement* a configurable option.
- The `1.6.2` release will complete the transition, activating full stamp enforcement across all the systems.

The stated version numbers are the *intended* release sequence. If any issues or implementation problems are found during the initial network deployments, the transition points may be pushed later than this plan by interim releases.

While you can create entirely closed-off and private networks with Reticulum, the protocol itself is open and permissionless. On widely interconnected networks, anyone can create identities and globally reachable destinations without external permission or approval, and establish links anonymously over the network.

Such capabilities are powerful, and a required characteristic of a truly functional communications fabric, but also raise very large challenges, that have been almost impossible to solve in legacy networking technologies.

Reticulum approaches this particular problem, like most others, by employing cryptographic principles. This provides a comprehensive, multi-layered repertoire of defense mechanisms, which can be composed and employed in very effective ways.

In contrast to other networking paradigms, these mechanisms do not have to be bolted on to the application layer in hindsight, but are a core part of the protocol itself, which means that they can be applied universally and effectively:

> All nodes help combat spam and network abuse, according to the rules *set by the actual owners of supplied resources* - not by any bureaucracy or external authority.

> Rules and requirements can be adjusted live, dynamically and directly, and by those that actually operate and run the infrastructure and services.

The system has been designed so that it becomes very cheap computationally for resource-providing nodes to verify or reject traffic, and very expensive for malicious nodes to abuse the shared resources provided by the network’s operators.

## Cryptographic Stamps

All networking primitives that consume shared network resources are gated by *stamps*. A stamp is compact, cryptographic token that proves that a certain amount of computation and energy has been expended in its creation.

The amount of such computation required for a stamp to be considered valid can be configured individually by the operator of the resource being made available, whether that is network transport, a node providing information for retrieval, a shared voice room, or something else entirely.

While the core functionality is completely automatic, and handled by Reticulum itself, the primitives are made available at the application layer API as well, so that developers can use them to implement further protections, if required by their usage scenarios. In most cases, however, simply setting the target *values* and required *costs* for the built-in mechanisms will be sufficient.

The *value* of a stamp is a decimal representation of how difficult a stamp was to create, on a scale from `0.0` to `100.0`. The scale is **exponential**. An increase of one point is equal to *doubling* the average compute time required. Fractional values are supported, such as `14.125`.

Internally, the fractional part is quantized to `256` different values, giving an approximately `0.27%` difficulty increase per step. You can use any decimal number when configuring stamps, such as `9.3691` and you do not have to worry about “landing on” the correct step values. Reticulum will automatically handle the quantization, wire-transport representation and value comparisons.

The term *cost* is used everywhere a stamp value *requirement* is configured or specified. In general, *value* refers to the actual, determined value of a given stamp, *cost* refers to a value requirement.

### Base Primitives

Reticulum provides two types of base stamp primitives:

> * **Detached stamps** can be tied to any external information, and are useful for stamping both static information and for one-time verification purposes. The stamp itself is a detached, short binary sequence, typically 14 to 32 bytes, that can be verified directly against the stamped material.

>   They can be configured from relatively easy to compute, even for embbedded systems and microcontrollers, all the way to something that is practically impossible, even with all the compute and memory on the planet.
> * **Embedded stamps** are tied directly to a Reticulum Identity keyset, and embedded within it. The keyset itself *contains* the stamp, and there is no external, detached byte sequence for them.

>   Anyone can verify the value of an identity-embedded stamp simply from the public key material of the identity.

### On-Network Types

The base primitives are used to implement scenario-specific network-level primitives that, if configured correctly, make spam and network abuse expensive, but validation and enforcement cheap and efficient.

> * **Destination Stamps** are detached stamps associated with reticulum destinations. They are included in all announces sent by a destination, and by verifying that their value matches a transport node’s cost requirement, they can be either accepted for rebroadcast onto the network, or rejected and dropped.

>   Destination stamps are *one-time* generations, and are reusable across announces. They limit the number of *new* destinations that can be created, and makes it expensive to spam a network with destinations that do not provide anything meaningful. As such, these stamps will typically target relatively high values, and their cost requirements should be set accordingly.

>   A generation time for such stamps in *minutes* rather than seconds can very well be reasonable on large, open-access networks. Due to their detached nature, they can also be pre-generated off-device (and do not require the private key material for generation), so that even low-powered nodes, such as microcontrollers, can use high-value destination stamps, by having them generated and loaded externally as a one-time procedure.
> * **Path Request Stamps** are also detached stamps, but generated *individually* for every path request emitted on the network. These will typically have a much lower cost requirement than destination stamps, but if a node is overwhelmed by path requests, it can be tuned higher.

>   The stamp is generated against the individually unique *emission*, so that unstamped or low-value path requests for a destination cannot disrupt the resolution of legitimate ones toward that same destination.
> * **Link Request Stamps** are embedded stamps, carried in the ephemeral link request keyset. They are therefore completely transparent to the network, but can still be verified extremely quickly by any node along the link request path, who can then make a decision on whether or not to transport it.

>   Link request cost targets are set by the *endpoint destinations individually*. Every destination that includes a stamp in its announces will also include link request cost signalling. This means that any node that hears an announce from the destination will also know what link request stamp value to target, when establishing links to that destination.

>   Furthermore, spam and link request abuse can be filtered before even reaching the destination, if at least one node along the path validates the link request stamp value and cost requirement.

All of the stamp primitives, functionality and on-wire signalling is *transparent and backwards-compatible* with older versions of Reticulum transport nodes. This means, that even if a node doesn’t itself understand stamp functionality, it will still transport all the required information. Stamped announces, path and link requests can cross older, non stamp-aware network segments transparently and unaffected.

### Configuring Stamps

Reticulum, and its included utilities, provide sane default cost requirements and value targets for the different types of network stamps, but it is entirely up to the operator whether to follow the defaults. All of them are configurable on a per-node, per-application and per-destination basis.

#### Instance Configuration

In reality, different kinds of networks will want to configure different kinds of costs and value targets for their use. For instance-wide defaults and settings, you can configure these in the `[stamps]` section of the Reticulum configuration file:

> * The `destination_cost` option sets the default required stamp
>   cost for announced destinations to be accepted, and have their
>   announces propagated by this node. Defaults to `23.5`.
>   
> * The `destination_value` option sets the default stamp value that
>   this instance will target when generating new destination stamps.
>   An application can request higher targets for destinations that it
>   creates, but a requested lower value will always be clamped to the
>   configured default as a minimum. Defaults to `25.0`.
>   
>   > *Destination stamps are one-time generations per destination, so it
>   > is generally a good idea to target a slightly higher value than the
>   > minimum required cost of the networks you want the destination to
>   > be reachable on.*
> * The `pr_cost` option sets the required stamp cost for incoming
>   path requests. Defaults to `15.8`.
>   
> * The `pr_value` option sets the target stamp value for path
>   request stamps generated by this instance. Defaults to `15.8`.
>   
> * The `lr_cost` option sets the default link request stamp cost,
>   that destinations created on this instance will require. This
>   value can be freely overridden by applications that specify their
>   own link request cost requirements, and is solely used as the
>   default if no such specification is provided. Defaults to `12.5`.
>   
> * The `lr_stamp_timeout` and `pr_stamp_timeout` options set the
>   maximum amount of time, in seconds, to spend while attempting to
>   generate link and path request stamps respectively. If a stamp is
>   not generated within this timespan, the generation is cancelled,
>   and the link request or path request fails. Defaults to `15`
>   seconds for both options.
>   
> * The `stamp_destinations` option enables generation and emission
>   of destination stamps in announces. This is a transitory option.
>   It will become mandatory and enabled by default in RNS `1.6.1`.
>   
> * The `stamp_prs` option enables stamping of path requests emitted
>   by this instance. This is a transitory option. It will become
>   mandatory and enabled by default in RNS `1.6.1`.
>   
> * The `always_stamp_lrs` option will stamp *all* outgoing link
>   requests, even to destinations that have not announced a link
>   request cost (and will, in that case, use the configured or
>   default link request cost). This option is mostly useful for
>   testing and diagnostics. In general use, Reticulum will handle
>   link request stamping and cost targets automatically.
>   
> * The `enforce_stamps` option allows early activation of stamp
>   enforcement. When enabled, announces and path requests that do
>   not meet the configured cost requirements are dropped, and link
>   requests with insufficient stamps are ignored. This is a transitory
>   option. It will become mandatory and enabled by default in RNS
>   `1.6.2`.
>   

An example of customised stamp cost and value configuration follows below:

```ini
[stamps]
  stamp_destinations = yes
  stamp_prs = yes

  destination_cost = 24.8
  destination_value = 26.25

  pr_cost = 15.8
  pr_value = 16.45
```

Stamp cost requirements can also be configured on a per-interface basis:

```ini
[[Public Gateway]]
  type = BackboneInterface
  mode = gateway
  listen_on = 0.0.0.0
  port = 4242

  destination_cost = 25.0
  pr_cost = 17.2

[[Local RNode]]
  type = RNodeInterface
  port = /dev/ttyUSB0

  # Much lower requirements
  # for the local network.
  destination_cost = 11.2
  pr_cost = 5.0
```

#### For Developers

Applications can dynamically set their own stamp values and required link requests costs at runtime. Whenever the values are adjusted, the destination will have to send an announce for the updated information to become known by the rest of the network.

If you are setting these values at destination creation time, ensure that they are set *immediately* after the destination is instantiated, as Reticulum may queue internal, instance-local announces for the destination shortly after creation, so that the local shared instance and its clients are aware of the newly created destination.

```python
# Create a new destination
my_destination = RNS.Destination(
    my_identity,
    RNS.Destination.IN,
    RNS.Destination.SINGLE,
    "myapp", "service"
)

# Configure stamps
my_destination.set_value(30.0)
my_destination.set_link_cost(15.0)
```

Dynamically adjusting link request costs is a viable and intended mechanism for mitigating resource abuse, scraping, DoS attempts and other malicious behaviour. An application may implement mechanisms to statically or dynamically raise link request costs under certain conditions.

It is also possible for application code to directly get the destination value and link request cost for any known destination:

```python
# Get the value of a known destination
RNS.Identity.recall_stamp_value(destination_hash)

# Get the current link cost requirement
# of a known destination
RNS.Identity.recall_link_cost(destination_hash)
```

An `Identity` can be created with an embedded stamp value, by passing the target value at instantiation time:

```python
# Create a new, stamped identity
my_identity = RNS.Identity(value=24.0)

# Get the value of any known identity
another_identity.get_value()
```

As with destination stamps, this is a one-time generation procedure, that happens at Identity creation. Once an identity is created with an embedded stamp, its value *cannot* be upgraded at a later point as with detached stamps.

## Filtering & QoS

In addition to the stamp functionality explored above, Reticulum includes filtering options that allow operators to explicitly deny or allow certain destination *types* across an entire instance.

After filtering, all packets that are ultimately allowed into the transport engine, are sorted into prioritized QoS queues, which are drained and processed in priority order.

This provides a powerful system for both filtering, classifying and ensuring latency and service quality for the traffic and application types a node operator wants to provide.

### Instance Configuration

The filtering subsystem can operate in two modes:

> * **Ignored Mode** will allow any destination type in the instance, *except* for those that have been explicitly added to the `ignored_types` list. This mode is useful for blocking the traffic of specific destination types from being transported across the instance.
>   
> * **Required Only Mode** will allow *only* the destination types explicitly defined as required, and ignore *all* other types. A base set of required destination types can be defined instance-wide in the `allowed_types` list.
>   
>   In addition, any application using the shared instance can temporarily request required destination types for its use. Applications that request required destination types will automatically have them granted, unless they are included in the `ignored_types` list.
>   

The filtering defaults and base settings are configured in the `[filter]` section of the configuration file. For example, it is possible to explicitly ignore a series of destination types, while also limiting hop reach to a more local topology:

```ini
[filter]
  hop_limiter = 14
  ignored_types = application.that.spams, traffic.heavy.service
```

In some situations, you may want to allow *only* certain destination types. If, for example, you are creating a high-performance transport node intended to handle thousands of simultaneous voice calls at minimal latency, a configuration might look something like:

```ini
[filter]
  required_only = yes
  allowed_types = lxst.telephony
```

The filtering subsystem provided in RNS `1.6.0` is functional and useful, but at an early stage, and relatively basic. In the upcoming releases, it will be expanded into a much more comprehensive and flexible system, that will include custom QoS and traffic class tagging, advanced rule definitions and more.

#### IMPORTANT
As the filtering and QoS system is developed and matures, the `required_only` mode will become the default operating mode for non-transport instances, since applications can already now dynamically request what destination types they are interested in.

This ensures that a local, non-transport node (running on resource-limited hardware, for example), does not have to process announces for, and waste CPU and memory on destination types that are completely irrelevant to it. It also greatly reduces power consumption on battery-powered and mobile devices, while they are connected to large and busy networks.

If you are a developer, see the following section.

### For Developers

At some point during the `1.6.x` release cycle, RNS will move to using the `required_only` mode for *non-transport* instances by default. This means that applications will, in most cases, have to request what types of destinations they are interested in receiving announces from.

If your application is only using the utility primitives included in RNS, or established protocols such as LXMF or LXST, **there is nothing you have to do**. The protocol primitives *themselves* request their required destination types, and this is the general pattern to follow here:

- If an application uses a common protocol or primitive, it is the importable primitive, protocol module, or relevant internal functionality that should request destination type requirements, at the point where they are actually needed.
- Higher level application layers should not have to guess at or request destination types, unless it explicitly creates outbound destinations that are not covered by any already-used protocols or primitives.

If your protocol or application needs to receive announces for a specific destination type, it is very easy to register it. For example, at startup (or when the destination type is actually required), simply run something like:

```python
RNS.Reticulum.get_instance().wants_destination_type("my_app.service")
```

You do not *have to* explicitly deregister destination type requirements. Reticulum automatically deregisters when the shared instance connection for the application is torn down, but you may *want* to in certain cases, which follows the same pattern:

```python
RNS.Reticulum.get_instance().unwants_destination_type("my_app.service")
```

That’s really all there is to it. If you already now want to make you application more CPU, memory and battery efficient, you can tell Reticulum to start serving only required destinations to it with only a few lines of additional code. A full setup of this functionality might look something like:

```python
for destination_type in self.REQUIRED_DESTINATION_TYPES:
    RNS.Reticulum.get_instance().wants_destination_type(destination_type)

RNS.Reticulum.get_instance().required_announces_only(True)
```

Your application will now only receive, and have to process, the announces and paths that it actually cares about.

## Ingress & Burst Control

In addition to the economic incentives created by stamps, Reticulum enforces a set of hydraulic limits on how much announce traffic any peer or destination can inject into the network. These mechanisms work automatically, require no operator configuration (but can be tuned, if required), and apply equally to all peers.

At the most basic level, the `announce_cap` mechanism limits the bandwidth any interface will allocate to propagating announces and other network upkeep traffic, and prioritises the local topology. Destinations that rapidly re-announce are down-prioritised in the transmission queue, so attempting to gain reach through announce spam has the exact *opposite* effect.

On top of this, per-destination announce rate control can be configured on any interface, or as instance-wide defaults. Once configured, announces *received* for any one destination will only be re-broadcast to other interfaces at the configured target rate, no matter how often they are received. The grace option allows occasional rate violations, and a configurable penalty extends the interval between propagated announces for destinations that repeatedly exceed their target.

The final layer protects against bursts of announces for *newly created* destinations. If an interface receives a large influx of announces for previously unknown destinations in a short amount of time, these are held in a bounded queue, while announces for known and established destinations continue to be processed without interruption. After the burst subsides, and an additional waiting period has passed, held announces are released slowly until the queue is cleared.

A node that connects to a public interface, announces a large number of bogus destinations, and then disconnects, will therefore never get those destinations into path tables at all. When the interface they arrived on disappears, the held announces are simply dropped and forgotten.

Ingress control operates at the level of individual sub-interfaces, so one misbehaving client cannot disrupt announce processing for other clients connected to the same listener. Combined with stamps, these mechanisms are complementary:

Rate limiting bounds the *rate* at which abuse can occur, for everyone, while stamps make the *volume* of abuse from any actor computationally expensive.

Full configuration details are available in the [Announce Rate Control](interfaces.md#interfaces-announcerates) and [New Destination Rate Limiting](interfaces.md#interfaces-ingress-control) sections.

## Blackhole Management

The *blackhole* system allows any node operator or individual user to block specific identities at the transport layer.

Once an identity has been blackholed on a node, announces originating from *any* destination associated with that identity are dropped, and the node will refuse to transport traffic, or establish and maintain links, to the blackholed identity’s destinations.

It is important to understand the scope of this mechanism corrrectly. There is fundamentally **no way** to *globally* block or censor any identity or destination in Reticulum networks. A blackhole entry only applies on the network segments that enforce it, which is the exact intention. Operators retain full control over what is allowed on their own segments, while no one can impose restrictions on segments they do not operate.

Blackholes can be managed directly with the `rnpath` utility. Identities can be blocked (optionally with an expiry duration and a human-readable reason), unblocked, and the current local blocklist can be inspected at any time. This is well suited for immediate responses to announce spam, unwanted content or malicious behaviour observed on your own networks.

For anything larger than a few nodes, manual blocklist maintenance quickly becomes impractical. Reticulum therefore allows an instance to subscribe to blackhole lists published by trusted transport identities, periodically retrieving and merging them into the local list, and conversely to publish its own list to subscribers.

This makes it possible to federate community-maintained blocklists across large networks, with the important caveat that subscribing to a list is an act of trust in its maintainer. See the [Blackhole Management](using.md#using-blackhole-management) section for full details on local management, automated list sourcing and publishing.

## Fast-Flap Blocking

High-performance listener interfaces, such as [BackboneInterface](interfaces.md#interfaces-backbone), will automatically block *fast-flapping* clients; remote peers that repeatedly connect for a very short amount of time, and then disconnect.

This behaviour usually stems from attempts to dump announce or path request spam onto the network in short bursts, while rotating connections in an attempt to evade per-interface rate limits, but it can also be caused by broken implementations or automated scanning tools.

Such bypass attempts generally have very limited effect. Ingress limiters trigger *immediately* once rate limits are exceeded, but the behaviour still causes needless interface rotation and wasted resources on the transport instance.

With fast-flap blocking enabled, a client that exceeds the allowed flap grace is simply not allocated an actual interface again, for the configured block duration.

On the `BackboneInterface` type, fast-flap blocking is enabled by default, with sensible standard settings. All parameters can be adjusted if necessary. See the [Automated Blocking](interfaces.md#interfaces-fastflap) section of the Interfaces chapter.