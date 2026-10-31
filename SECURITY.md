# Security and safety reporting

## Safety-critical issues

If you find a condition that can cause unexpected motor torque, failure to stop, runaway control,
thermal damage or another physical hazard, do not publish exploit details first. Use a private
channel:

- GitHub Security Advisory for this repository, or
- contact the maintainer through the repository's private security contact.

Include:

- PyFFB version and commit;
- operating system and Python version;
- firmware/board/motor/encoder/PSU details;
- exact settings and profile;
- serial log and steps to reproduce;
- whether the hardware E-stop worked;
- any injury or damage (do not risk further injury to reproduce).

We will prioritize a safe mitigation and document the limitation. This project is not a certified
machine-safety system; report issues even if you are unsure.

## Software vulnerabilities

In scope:

- command injection into serial framing;
- path traversal/file overwrite through config/profile import;
- unsafe deserialization (we use JSON only);
- denial of service via malformed profile/replies;
- local privilege issues in installers/launchers;
- accidental bypass of the app power cap through a UI/API path.

Out of scope:

- physical access attacks;
- malicious firmware on the wheel;
- game/anti-cheat behavior;
- bypassing vendor licenses (we do not implement such functionality);
- vulnerabilities in OpenFFBoard, Python, pyserial or Tkinter itself (report upstream, but tell us
  if PyFFB makes exploitation materially easier).

## Handling secrets

PyFFB has no accounts or license keys. Do not put personal information in profiles or logs. Logs
may include COM port names, executable names and device identity; review before posting publicly.

## Supported versions

Security fixes target the latest released 0.1.x line. Pre-release or unreleased snapshots may be
asked to update first.

## Disclosure

We aim to acknowledge reports promptly and coordinate disclosure after a fix or mitigation is
available. Avoid public disclosure of unresolved safety issues.
