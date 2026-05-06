<a id="understanding-destinationnaming"></a>

#### Destination Naming

Destinations are created and named in an easy to understand dotted notation of *aspects*, and
represented on the network as a hash of this value. The hash is a SHA-256 truncated to 128 bits. The
top level aspect should always be a unique identifier for the application using the destination.
The next levels of aspects can be defined in any way by the creator of the application.

Aspects can be as long and as plentiful as required, and a resulting long destination name will not
impact efficiency, as names are always represented as truncated SHA-256 hashes on the network.

As an example, a destination for a environmental monitoring application could be made up of the
application name, a device type and measurement type, like this:

```text
app name  : environmentlogger
aspects   : remotesensor, temperature

full name : environmentlogger.remotesensor.temperature
hash      : 4faf1b2e0a077e6a9d92fa051f256038
```

For the *single* destination, Reticulum will automatically append the associated public key as a
destination aspect before hashing. This is done to ensure only the correct destination is reached,
since anyone can listen to any destination name. Appending the public key ensures that a given
packet is only directed at the destination that holds the corresponding private key to decrypt the
packet.
