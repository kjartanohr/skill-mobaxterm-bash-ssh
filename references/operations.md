# MobaXterm SSH: operational guide

Read after `SKILL.md`, not instead of its target, authentication and approval
rules. All example targets below are documentation-only names. Replace them
with the confirmed user-authorized target; never run the examples unchanged.

## Diagnosis without repeated login attempts

| Observation | Next action |
| --- | --- |
| MobaXterm Bash not found | Inspect the running executable's directory; otherwise ask for `cygpath -w /bin/bash.exe` from the user's local MobaXterm terminal. |
| Wrong client in `type -a ssh` | Explain the mismatch; do not switch SSH clients or modify startup files. |
| No matching session function | Confirm the session name or non-secret UI connection details. This is not an authentication failure. |
| Timeout / no output | Read pending output, stop that invocation, and distinguish startup, transport, prompts and output capture. No automatic retry. |
| `Permission denied`, password prompt or askpass error | Stop. Have the user verify the same account/target in MobaXterm. Do not collect a password, generate keys or install askpass. |
| Unknown or changed host key | Stop for independent verification; do not auto-accept or disable checking. |
| Algorithm negotiation error | Record the offered algorithms. Prefer server modernization; any temporary downgrade requires scoped approval. |
| Switch prompt but no command output | Distinguish SSH exec from interactive CLI/PTy. Test new prompt-handling code locally, not with repeated live logins. |

Saved-password authentication in the investigated MobaXterm build involved its
own SSH backend and IPC to the running application. Session launcher functions
and `SSH_ASKPASS` are not interchangeable with that mechanism. Do not extract
credentials, assume every build behaves identically, or interpret an empty
SSH agent as proof that saved-password authentication cannot work.

## Quoting, scripts and output

PowerShell starts MobaXterm Bash; Bash starts SSH; the remote shell/CLI handles
the remote command. Keep local redirection separate from remote execution.
Quote the Bash command as one PowerShell argument and the remote command as
one SSH argument. Example for a confirmed Linux host:

```powershell
& $bash -lic 'ssh operator@server.example.invalid "hostname && id -un"; rc=$?; exit "$rc"'
$sshExit = $LASTEXITCODE
```

Do not interpolate raw user input into this template. Prefer a reviewed local
script rather than increasingly complex nested quotes.

For local orchestration, source a trusted UTF-8-without-BOM, LF script inside
the same Bash `-lic` shell so SSH alias resolution is preserved:

```text
source <quoted local POSIX path>
```

For a reviewed remote Linux Bash script, redirect a local script file to:

```text
ssh <confirmed target> bash -s < <quoted local POSIX path>
```

This requires remote Bash. CRLF and UTF-8 BOM have caused command failures;
inspect encoding before transmission. Do not send UTF-16 as a Bash script.
Do not mix script bytes and interactive `read` input on the same stdin.
A switch CLI is not Bash.

Convert local Windows paths with the discovered MobaXterm `cygpath`. Quote the
converted path, especially when it contains spaces; never assume drive letters
or a fixed skill installation directory.

Bulk output captured through PowerShell variables/pipes has hung in prior
tests. If needed, redirect output to a new local file inside Bash and inspect
it after completion. Do not overwrite existing backups. Check expected
content/completeness as well as the exit code. This is a tested workaround for
specific payloads, not a universal streaming fix. Stopping local SSH does not
guarantee remote child processes have stopped.

## Cisco and Expect boundaries

Use a known platform's read-only command, typically `show version`, rather than
`hostname` or a Linux script. Some older switches require a PTY and interactive
CLI instead of SSH exec. An extra `User Name:` / `Password:` after SSH
connects is an application/CLI dialogue, not necessarily failed SSH transport.
Unexpected credential prompts on real devices are a stop condition.

SG300-specific commands seen on an older lab firmware included
`ip ssh password-auth` and `passwords aging 0`. They change device security
policy and are not generic login fixes. Never apply them, disable aging, save
configuration, or answer password-change prompts on another device without
the operator's explicit decision and a platform-appropriate change procedure.

Do not distribute or reuse an Expect wrapper hardcoded to someone else's
switch. A production wrapper must preserve MobaXterm Bash `-lic` and bare SSH,
target only the approved account/host, bound all waits, reject unexpected
credential prompts, check CLI errors, and close the session. A prompt match
or EOF alone does not establish command success.

## Optional loopback emulator

This is a development tool, not a prerequisite for normal SSH. No real switch
or saved MobaXterm credential is involved. The scripts bind/connect only to
`127.0.0.1`, default port `22222`, with dummy credentials
`cisco` / `sg300-test-only`. Do not use real credentials or expose it on a LAN.
Its generated host key changes each start; the test client's relaxed host-key
checking is allowed only for this disposable loopback test.

For full installation acceptance, [INSTALL.md](../INSTALL.md) requires these
local tests and dependency checks. Missing dependencies must be reported and
installed only with approval. The standalone examples below are not a
substitute for that complete OK/FAIL checklist.

Prerequisites: Windows Python 3.10+ with Paramiko **5.0.0**, MobaXterm Bash
and its `expect` command (previously tested with Expect **5.45**).
No dependency installation is needed for the normal SSH workflow.

Set `$skillRoot` to the actual directory containing this skill's `SKILL.md`
and `$bash` to the discovered MobaXterm Bash. Then, in one PowerShell window:

```powershell
python -m pip install -r (Join-Path $skillRoot 'scripts\requirements-sg300-emulator.txt')
python (Join-Path $skillRoot 'scripts\sg300_ssh_emulator.py') --secondary-login --password-expiry
```

Wait for `READY 127.0.0.1:22222`. In another window, use `cygpath` to convert
the actual `scripts\test_sg300_emulator.exp` path, quote that path for Bash,
and run this command inside the discovered Bash `-lic` shell:

```text
expect <quoted converted script path> "show version" "show passwords configuration"
```

Do not run `expect` in PowerShell directly. For another port, pass
`--port <port>` to the server and before the client command list. Stop the
emulator with `Ctrl+C` after testing; do not leave a background listener.

This intentionally small emulator rejects SSH exec, implements only a subset
of CLI commands, and does not reproduce Cisco firmware, legacy cryptography,
network interfaces, persistence or AAA policy. Its `write`/`startup-config`
responses are synthetic, not backup validation. The test client reports
prompt-flow completion, not general command correctness; inspect actual output.
It only supports `N` at the synthetic password-expiry question.

Sources for the approach:
[Paramiko server API](https://docs.paramiko.org/en/stable/api/server.html) and
[MockSSH](https://github.com/ncouture/MockSSH). The included server is a small
independent implementation, not bundled MockSSH or Cisco software.
