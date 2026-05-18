Recently, and mostly from people who I've never seen before, the opinions about how this project should be run has started flooding in again. In a recent forum thread of such opinions, specifically about:

- The decision to no longer mirror release notes on GitHub.
- Some people feeling there were too many "barriers to entry" to joining RNS development.
- The project not really being "open source" because random strangers couldn't just "contribute".

Joakim posted some very relevant observations about how Reticulum operates, along with the following quote:

> The modern industrial system has a built-in tendency to grow; it cannot really work unless it is growing. The word “stability” has been struck from its dictionary and replaced by “stagnation”. Its continuous growth pursues no particular aims or objectives: it is growth for the sake of growing. No one even enquires after its final shape. There is none; there is no “saturation point”.

That E. F. Schumacher quote perfectly illustrates the ontological schism that makes it so tiresome to deal with stuff like this.

There is, in this day and age, between different people, widely different base conceptual integrations of what "open source" means. For many people, "open source" has become synonymous **not** with skilled people working together in a coordinated and careful way on complex engineering challenges, but a sort of growth- and attention-focused "free-for-all" *behavioral* codex that must be followed above all else; a *social* modus operandi of fake inclusivity where everyone "should have their voice heard", and adherence to that specific process is weighed much higher than the final results.

I do not subscribe to, and consequently do not operate the Reticulum project under *any* versions of that idea.

**Here's the statistical, boring reality:**

- Around 90% of pull requests and "recommendations" I received when people could just submit stuff via GitHub would
   have *severely* broken things, introduced bugs or security issues, created roadblocks for future work, or otherwise
   damaged the software. Usually just for the sake of satisfying a random newcomers "idea" or personal preference.

- Similarly, around 90% "bug reports" were actually people asking for help, because of having failed to read even the
   most basic parts of the documentation.

- The people with the least amount of understanding, skill and effort invested tend to be loudest and most vocal. When
   all you have is "opinions", those are iterated upon ad infinitum, apparently.

Can you imagine how much time that wasted? Can you imagine what we could have accomplished with that time instead?

The only thing that this creates is *noise* and confusion. Clogging up the mental and physical workspaces, of people who are actually investing time and effort on the project with stuff like that is objectively just taking time that could have been used on development, and replacing it with *nothing*.

I was receiving *actual* bug reports, pull requests, proper technical investigations and patches via methods outside GitHub and "public" internet-based channels *way* before GitHub interaction and similar was closed down. That was were almost *all* of the real contributions were coming from, anyway. Apparently, and not unsurprisingly, the people who has invested the time and effort to understand Reticulum also prefer to collaborate in this way. Since leaving the GitHub madhouse behind, the signal-to-noise ratio has **significantly** increased.

Managing a public "issue" tracker with global read/write access is a futile and useless endeavor. Consider this:

- User A reports a "bug" that is really just a failure of understanding.
- User B sees this and seconds is, proposing a "fix" that in continued failure of understanding would actually break functionality X.
- User C joins the bandwagon and asks why this hasn't already been implemented like that? It's obvious!

The sensible response here from the developer is closing the issue with "No. Go RTFM". Today, though, this usually results in hurt feelings, animosity towards the developer and in some cases (as experienced and documented in the case of RNS), months of perfidious personal vendetta against the developer for being so brazen as to suggest the user was wrong and wasting people's time.

When this pattern repeats, over and over, the only sensible, measured and constructive course of action is to shrug your shoulders and say:

*"This system is fundamentally broken. It ain't working. I can give up here, or I can go build something better that has a chance of working."*

So, now it's your turn. Go look at the diffs for the last six months. What does it look like I have been doing?

But I will be damned straight with you all, and say that part of that solution is **absolutely** to erect barriers to entry. You can fucking bet your arse on that. I don't want opinionated man-babies running around in my living-room at 3am. I don't want to clean up the floor after a wannabe "dev-ops stars" with LLMs and a peripheral case of influencitis has puked all over the office.

- If you want to join the fun of changing core networking code that thousands of people rely on for communication
   daily, you better know what the fuck you're doing.

- I'm not here to provide validation and hugs to random strangers. I'm here to make sure the reference implementation
   of Reticulum works.

- If you cannot figure out how to submit a patch or valid bug investigation over RNS, you cannot expect I will take
   you seriously. At all.

If someone can't handle that, they should find their entertainment elsewhere.

I've said it before: I've provided the information and code required to make Reticulum *work*, and build networked systems, protocols and applications on top of it. That information is deep, complex, and requires you to read hundreds of pages, and put in weeks of efforts to get the *full* picture. A lot less is required to get started, but it *will* still be a steep learning experience.

This is a full networking stack, based on some pretty complex principles, for crying out loud. It's **not** a `hello_world` designed to make you feel good about yourself. It turns almost everything you know about networked systems on its head. That's **challenging** for *anyone*. Climb the mountain, and it will be satisfying in the end. Refuse to climb... Well, what do you think will happen?

As for barriers to entry of *using* RNS and related programs, utilities and clients, it's not my task to teach every single user how to do X, Y and Z. The information *is* out there. If it wasn't organized optimally for your way of learning, you can choose to "raise your concerns" about it, discuss "the fact of it" on a forum or chatroom, or: *You can choose to remedy that, and help others along*.

I sure know what *I* would have done.