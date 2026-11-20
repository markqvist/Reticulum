# Media Conversion in rngit and nomadnet

## Short Overview

A security vulnerability has been discovered in operating-system provided or user-installed libraries that RNS *could* potentially use as external backends for media conversion.

Anyone hosting nodes with `rngit`, `nomadnet` and potentially other programs that *serve* or *convert* untrusted media files using the RNS API-provided `convert_to_webp` and `convert_file_to_webp` media conversion functionality, should upgrade to the latest release update of RNS 1.6.1, **right now**.

The initial discovery information and general shape of the potential exploit was provided to me by Hunter from [Ratspeak](https://ratspeak.org), at `2026-11-19 01:30 CEST`, and when I saw the mail around `02:00`, I started investigating the issue.

The release files were updated on `2026-11-19 18:55 CEST`, and replaced the files uploaded yesterday.

## Where is the vulnerability located?

**This is not a vulnerability in RNS itself**, but in external libraries that RNS can *potentially* invoke while converting media files for serving to `nomadnet` clients. The vulnerabilities therefore become exploitable through services such as `rngit` and `nomadnet`. Whether RNS invokes the specific, vulnerable libraries depends on what is installed on your system. 

Even if your system uses the affected software, not all version are equally vulnerable, **but do not count on your system being unaffected**. The attack surface is complex here, and there is not one single set of versions you can check to ensure your system is patched. The only way currently to protect against this, is to update RNS to a version that actively mitigates the vulnerability. See below for more details.

Additionally, I'd recommend updating your packages and OS fully if you run any kind of software that serves or converts media files that could come from external sources. This affects libraries that are used in a very large amount of packages that serve media files in web-applications, for example.

However, updating the affected packages is **not universally sufficient**. As of this writing, the latest versions are still vulnerable in several distros, which is why I have decided to hot-patch the RNS 1.6.1 release with a full mitigation, that blocks any potential invocation of the vulnerable paths.

## What is exploitable?

On affected systems, it is possible to obtain arbitrary read access to any file that the process-owning user can read, and potentially exfiltrate that data from the system.

## Who is affected?

Anyone running a service with public read access to media files, *if those media files can be supplied from external sources*. That could, for example, be via a `git push` or file uploads. 

If an attacker can upload a malicious file to your system, and later display that file, it can lead to arbitrary data exfiltration.

No networking or core functionality, including the standard utilities and command line tools, are affected, and this vulnerability has no interaction with the networking, transport or cryptography parts of RNS.

If you do not run some kind of service that serves media files while also accepting untrusted uploads, you are not affected. **But**, I would still recommend updating anyway, in case you forget about this, and later decide to host exactly such a service.

## How is it mitigated?

Update RNS to the *latest* upload of RNS 1.6.1:

```sh
# Using pip
pip uninstall rns -y
pip install rns -U --no-cache-dir
```

If updating using `pip`, ensure that the downloaded file is exactly `rns-1.6.1-0-py3-none-any.whl` (note the `-0` in the filename).

```sh
# Using rngit
rngit release rns://7649a50d84610232d1416b41d2896aff/reticulum/reticulum fetch "latest:rns-*.whl"
pip uninstall rns -y
pip install ./rns-1.6.1-py3-none-any.whl
```

Once this update has been installed, the exploitable code paths will be unreachable from RNS applications. Remember to restart any applications that use RNS.

**Very important!** This *only* fixes the exploit path for RNS-based applications. Any other program on your system that uses the vulnerable libraries will still be exploitable.

## How can I determine if my system was exploitable?

It can be relatively easy to determine that your system was *not* affected, but unfortunately, it can also be relatively difficult to determine if it potentially *was*. Please see the following section.

## Some more technical information

Due to the severity of the vulnerability, and how relatively easy it is to exploit it if the system is vulnerable, I will not provide a full description of the exploit path, or any proof-of-concept code. First of all, this is a relatively complex issue, and it has several different exploitable paths, that can lead to different levels of information disclosure from the system.

I was initially made aware of this around 2AM this night, and spent until about 4.15AM investigating the extent to which Reticulum users could potentially be affected. At that point, I had to actually get some sleep, and then spent the entire day today on it as well. It has taken me approximately 10 hours to map the surface of the issue, and unfortunately, the conclusion here is, that there is no clear-cut version number or similar where the package could be considered patched.

The affected software library is the popular `ImageMagick` module, used in basically everything that handles image conversions or processing, for all kinds of applications.

The easy version: **If you do not have `ImageMagick` installed on your system, it has not been vulnerable**

If you do have `ImageMagick` installed, and it was used as the media conversion backend for anything, here is the complicated version:

Whether or not a particular installation of the software is exploitable will be a result of interactions between:

- The installed version of the software itself
- The exact build configuration that was used to compile the distributed binaries
- The particular rendering libraries that the binary was linked and compiled against, and the versions of these
- The configuration and policies shipped as default in the package the software was installed from
- Any potential system or user-side modifications to the above
- Potential other software that was installed on the system, which `ImageMagick` can dynamically call at run-time

As you can see, the amount of combinations here have now exploded, and it is impossible to say whether or not your particular installation is vulnerable. The short version here is, that in many different combinations, `ImageMagick` can be exploited to read arbitrary data and incorporate it into output images. The extent of this, what can be done, what can be read, et cetera, varies wildly with exact situation on a given system.

Several distributions already have patched and updated packages, that block the most severe forms. For example, Debian and Arch provide patched binaries, Ubuntu does not. **But** even on the patched versions, in many cases, I was able to find new exploit paths **that are not yet patched**. I could not find any combination of latest versions and operating systems, where there was not *some* form of exploitable path available in the default, as-installed configuration. Additionally, there are some paths that no amount of settings or policy tweaking can protect against.

Therefore, it is **not** safe to assume that your distribution has been patched and is secure. As I investigated this, it turned out to be a real Pandora's box of hornet nests, and that it is not likely to be reliably patched in any reasonably soonish OS/package update.

The only reasonable way I could find to reliably deal with this, was to ensure that all potential media conversions handled by this particular software can never reach the problematic code paths.