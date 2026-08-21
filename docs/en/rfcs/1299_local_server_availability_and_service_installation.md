- Proposal Name: local_server_availability_and_service_installation
- Start Date: 2026-08-21
- RFC PR: [oceanbase/powercontext#1299](https://github.com/oceanbase/powercontext/pull/1299)
- Tracking Issue: [oceanbase/powercontext#1298](https://github.com/oceanbase/powercontext/issues/1298)

# Summary

PowerContext will separate local Server execution from installation and deployment lifecycle. The Server CLI will
continue to provide the explicit foreground command powercontext server run. Agent integrations will fail open while
making Server unavailability visible, and powercontext doctor will explain whether the installed service registration,
native service manager, Server liveness, and Server readiness agree.

For a personal installation, an opt-in distribution-owned service-install layer will register the existing foreground
Server command with the operating system's native per-user service manager. It will not live under the Server CLI,
enable itself during setup, require administrator privileges, or create a second PowerContext supervisor. Managed
deployments will continue to use containers or administrator-managed system services. The RFC defines one contract for
Linux, macOS, and Windows while allowing the accepted implementation to be split into independently reviewed changes.

# Motivation

Agent integrations depend on a reachable PowerContext Server but do not own its process lifecycle. The normal local
entry point is intentionally foreground:

~~~text
powercontext server run
~~~

That default is inspectable and reversible, but it disappears when the terminal closes or the machine restarts. A
later agent session can continue without recall or capture because integrations fail open. Existing structured
diagnostics may be written to logs or stderr, but the user can still experience the failure as silent loss of
PowerContext behavior.

Putting login autostart directly under powercontext server would mix two responsibilities. The Server package owns how
to run one configured process. Installation and distribution own whether an operating system should persistently
launch that process. The distinction also separates two deployment profiles:

- A personal installation can use a native service owned by the current user.
- A managed deployment should use a container or an administrator-managed system service with deployment-specific
  configuration, credentials, health checks, and restart policy.

PowerContext needs a durable design for that boundary before implementation. It also needs diagnostics that help a
user distinguish an uninstalled service, an inactive native service, an unreachable Server, and a live but unready
Runtime.

# Guide-level explanation

## Deployment profiles

PowerContext documents three ways to run the Server.

### Interactive personal use

The existing command remains the default and keeps its current behavior:

~~~text
powercontext server run
~~~

It runs in the foreground, prints logs to the terminal, and stops on Ctrl-C. Installing PowerContext or an agent
integration does not create persistent operating-system state.

### Persistent personal use

A user who wants the local Server after login explicitly installs a per-user service through the distribution layer:

~~~text
powercontext service install
powercontext service status
~~~

The proposed service command group is not part of powercontext server. It manages only PowerContext-owned
registration artifacts for the current user. Installation is off by default and does not require root, SYSTEM, or an
administrator account.

The installed service still executes the same Server entry point. It does not introduce a daemon inside PowerContext:

~~~text
powercontext server run
~~~

To remove the registration:

~~~text
powercontext service uninstall
~~~

Uninstalling the registration stops a Server instance owned by that registration and removes only artifacts created
by PowerContext. It does not terminate an unrelated foreground Server.

### Managed deployment

The personal service installer is not a production deployment manager. A managed installation uses the project's
container image or an administrator-managed systemd system unit, launch daemon, Windows service, or equivalent
orchestrator. PowerContext does not install those privileged resources through powercontext service.

## What users see when the Server is unavailable

Agent integrations remain fail-open: failure to recall or capture does not block the host task. They must nevertheless
surface a content-free server_unavailable diagnostic through the host's warning or diagnostic channel. An integration
must not attempt to install, start, or restart the Server from a prompt hook.

The warning directs the user to:

~~~text
powercontext doctor
~~~

Doctor reports separate facts rather than collapsing them into one connection error:

- whether a personal service registration exists;
- whether the native service manager reports it active;
- whether the configured Server endpoint is live;
- whether the live Server is ready;
- a recovery action appropriate to the observed state.

Examples include:

~~~text
service_registration  not_installed  optional: run powercontext service install
server_liveness       failed         run powercontext server run, or install the personal service
server_readiness      skipped        not checked because Server liveness failed
~~~

and:

~~~text
service_registration  installed
service_manager       inactive       inspect the native user-service logs
server_liveness       failed         registered service did not become reachable
server_readiness      skipped        not checked because Server liveness failed
~~~

Service status is narrower than doctor. It reports registration and manager state plus Server liveness, but it does
not replace the Server's readiness diagnostics.

# Reference-level explanation

## Responsibility boundaries

The accepted design assigns one owner to each concern:

| Concern | Owner | Required behavior |
| --- | --- | --- |
| Construct and run the ASGI process | Server role | Keep powercontext server run foreground and independently usable |
| Recall and capture during an agent task | Integration | Fail open and surface Server unavailability without owning lifecycle |
| Diagnose an installed environment | CLI diagnostics | Correlate registration, manager state, liveness, and readiness |
| Register a personal background process | Distribution/service-install layer | Manage native per-user artifacts and execute the Server entry point |
| Run a managed deployment | Operator or orchestrator | Use containers or administrator-managed system services |

No integration imports a platform service adapter. No platform service adapter belongs to
src/powercontext/server or changes Server application startup. The distribution layer may expose its user contract
through the top-level powercontext CLI, but command placement does not transfer ownership to the Server role.

## CLI contract

The initial distribution contract is:

~~~text
powercontext service install
powercontext service uninstall
powercontext service status
~~~

The commands apply only to the current user's personal service. There is no --system, --machine, --root, or
administrator installation mode.

### Install

Install performs these steps:

1. Select the supported native user-service adapter for the current operating system.
2. Resolve an absolute, non-shell command for the installed PowerContext entry point.
3. Render and validate the registration artifact before changing native state.
4. Create or update only the artifact identified as PowerContext's personal Server registration.
5. Enable the registration for future user logins.
6. Start it immediately only when the configured Server endpoint is not already live.
7. Report registration, native manager state, and liveness after the operation.

Repeated installation with the same desired definition is successful and makes no semantic change. Installation with
a stale PowerContext-owned definition replaces it atomically where the native manager permits. If the endpoint is
already live, installation must not start a competing process. The registration remains enabled for the next login.

Install fails without partial ownership when the platform is unsupported, the selected artifact is not owned by
PowerContext, the executable cannot be resolved, or the native manager rejects the operation. It must not overwrite a
foreign unit, task, or launch agent that happens to use a similar display name.

### Uninstall

Uninstall disables and removes the PowerContext-owned registration. It stops the manager-owned process when active,
but does not kill a process solely because it listens on the configured port. Repeated uninstall when no registration
exists succeeds.

If removal is incomplete, the command reports the remaining artifact and a native recovery command. It must never
broaden cleanup to a directory, an arbitrary task name, or an unverified process identifier.

### Status

Status is read-only and has human-readable and JSON output. Its stable state model contains:

~~~text
support: supported | unsupported
registration: installed | not_installed | invalid | unknown
manager: active | inactive | failed | unknown
server_liveness: live | unreachable | unknown
~~~

Registration is the state of the exact PowerContext-owned native artifact. Manager state comes from the native
manager. Liveness comes from the configured health endpoint. These values are deliberately independent: a foreground
Server can be live while registration is absent, and a registration can exist while the Server is unreachable.

The JSON output must not include credentials, complete process environments, or unrelated native-service metadata.

## Native personal-service adapters

All adapters register the current user, execute the same absolute PowerContext Server command without a shell, and
write logs to an operating-system-native location surfaced by status and doctor.

### Linux

The supported adapter is systemd --user. It owns a unit under the user's systemd configuration directory and uses the
user service manager for enable, start, stop, status, and logs. It never writes under /etc/systemd/system and never
enables linger. A Linux environment without an available user systemd manager reports unsupported; the first
implementation does not silently fall back to a shell startup file or desktop-specific autostart entry.

### macOS

The supported adapter is a per-user LaunchAgent under the user's Library/LaunchAgents directory. It uses launchd's
current-user domain and never creates a LaunchDaemon or privileged helper.

### Windows

The supported adapter is a Task Scheduler task triggered when the current user logs on. It runs as that user and never
as SYSTEM. A hidden process window is acceptable. The adapter does not install a Windows Service.

Native identifiers and paths are project constants. Each artifact carries enough static identity for status and
uninstall to distinguish a PowerContext-owned definition from a foreign resource.

## Configuration and credentials

The service installer records the executable, required arguments, and non-secret service metadata. It does not copy
the caller's complete environment, shell profile, API keys, bearer tokens, or provider credentials into a native
registration artifact.

The initial personal-service profile therefore relies on configuration that is available to the native user-service
environment. Status and doctor must detect common configuration divergence where it can be observed without reading
secrets. Deployments that require injected credentials or environment management beyond the native user-service
contract remain operator-managed.

A portable credential store, environment snapshot, or cross-platform secret-file format is not introduced by this
RFC. If personal service installation cannot support the project's documented inference configuration without one of
those contracts, that configuration handoff must be resolved before the service-install implementation is declared
generally available.

## Integration availability signal

Each integration already has a host-specific execution model, so the display mechanism is adapter-specific. The
common semantic contract is:

- transport failure, timeout, or HTTP 503 maps to server_unavailable;
- recall and capture remain independently fail-open;
- the diagnostic contains no prompt, recalled content, token, or credential;
- the host task proceeds without injected PowerContext content;
- the integration provides a discoverable path to powercontext doctor;
- the hook never starts or installs a Server.

Authentication failure, version mismatch, invalid response, an empty successful result, and Server unavailability
remain distinct outcomes. Implementations should use a host-native warning channel when available and retain
structured diagnostics for troubleshooting.

## Doctor diagnostics

Powercontext doctor remains the authoritative installed-environment diagnostic. When the service-install capability is
present, it adds:

| Check | Meaning |
| --- | --- |
| service_support | A native personal-service adapter is available |
| service_registration | The exact PowerContext-owned registration is installed and valid |
| service_manager | The native manager's state for that registration |
| server_liveness | The configured endpoint answers the liveness contract |
| server_readiness | The live Server reports ready, degraded, or not ready |

Doctor does not infer registration from an open port and does not infer liveness from a manager process identifier.
When facts disagree, its detail names the disagreement and gives the next safe action. JSON diagnostics preserve the
same check names and status vocabulary used by human output.

## Upgrade and executable drift

The registration points to a resolved installed entry point rather than a shell alias. Status validates that the
recorded command still exists. Doctor reports a stale command or definition mismatch after an installation moves or
changes materially.

Updating the Python distribution does not silently rewrite operating-system state. Running service install again
reconciles the registration with the currently installed distribution. Documentation must include that reconciliation
step until the distribution has a transactional upgrade hook.

## Failure handling and observability

Native start failures remain visible in native logs. Service status and doctor identify how to inspect those logs.
Platform adapters return structured failures without including secret environment values.

The registered command must not create a duplicate Server when the configured endpoint is already live. Native restart
policy must be bounded and must not turn a persistent configuration error into an unbounded rapid restart loop.
Specific restart intervals may differ by platform, but tests must cover the rendered policy.

## Security and compatibility

- Personal service installation is opt-in and per-user.
- Setup commands never enable it implicitly.
- No operation requests privilege elevation.
- The registered Server retains its configured bind address; the installer does not change it to a public address.
- The feature introduces no new HTTP, MCP, persistence, or authentication contract.
- Server run retains its current foreground behavior.
- Uninstall removes only verified PowerContext-owned artifacts.
- Diagnostics and logs never expose credentials or captured content.

## Delivery and testing

Acceptance of this RFC does not require one implementation pull request. The tracking issue may split work into:

1. host-visible integration diagnostics;
2. correlated doctor diagnostics and the shared service state model;
3. the distribution-owned CLI and adapter protocol;
4. Linux, macOS, and Windows adapters;
5. documentation and platform integration tests.

The shared state model and security rules apply to every platform adapter. Documentation must state the actual support
available in a release rather than implying that an adapter exists before it ships.

Focused tests cover rendering, ownership verification, idempotent install and uninstall, executable drift, status
disagreement, redaction, and the already-live short circuit. Platform tests run only on the matching operating system
and verify register, query, start where safe, stop, and remove. CI need not simulate an interactive login, but it must
assert the native trigger and exact command that will run after login.

Integration tests verify that unavailable, authentication failure, version mismatch, invalid response, and empty
success remain distinct, content-free, fail-open outcomes. Doctor tests cover each independent combination of
registration, manager, liveness, and readiness that produces a different recovery action.

# Drawbacks

- A distribution layer with three native adapters is more code and operational surface than a foreground command.
- Native user-service environments differ, especially in how they receive configuration and credentials.
- Host-visible warnings can become noisy if a Server stays unavailable; integrations need host-appropriate
  presentation without hiding the condition.
- A split implementation can temporarily produce different platform support across releases.
- A top-level service command adds CLI vocabulary for a lifecycle that some users will never need.
- Personal service installation does not solve managed deployment, remote access, multi-user isolation, or production
  secret management.

# Rationale and alternatives

## Put autostart under the Server CLI

Commands such as powercontext server autostart enable are discoverable beside server run, but they make the Server
role own installation and operating-system persistence. This RFC keeps process construction and service installation
separate.

## Start the Server from an integration hook

This removes a setup step but makes short-lived, latency-sensitive hooks own process lifecycle. Concurrent hosts can
race, cold startup can delay a prompt, and credentials or configuration may not match. Hooks remain consumers that
surface unavailability.

## Enable a service during setup

Implicit installation surprises users with persistent processes and operating-system state. Setup continues to install
integrations and recommend explicit next steps; service installation remains opt-in.

## Publish manual recipes only

Manual systemd, launchd, and Task Scheduler instructions avoid adapter code but drift across releases and provide no
shared status, ownership, uninstall, or doctor contract. Native managers remain the mechanism, but PowerContext owns
the reversible personal registration.

## Install a privileged system service everywhere

Machine-wide services start outside the user's normal trust and configuration boundary and require elevation.
Personal installation does not need that authority. Managed operators can still define privileged services
explicitly.

## Build a PowerContext supervisor

A cross-platform supervisor would duplicate native restart, logging, and lifecycle facilities. The service-install
layer registers the existing foreground process and does not supervise it itself.

## Require one pull request for all platforms

One change avoids temporary support differences but couples independent native integrations and makes review and
rollback harder. The RFC fixes the shared contract; the tracking issue can split implementation while documentation
reports actual availability.

## Make no change

Users can keep a terminal open or create their own service definitions, but unavailable integrations can remain
confusing and personal registrations will continue to lack a supported diagnostic and uninstall path.

# Prior art

systemd user services, macOS LaunchAgents, and per-user Task Scheduler tasks provide native login-session lifecycle,
logging, and status without a project-specific supervisor. Developer tools commonly keep an interactive foreground
command while offering a separate install or service command for persistent personal use.

Containers and administrator-managed services are established deployment boundaries for managed workloads because
they make identity, configuration, credentials, restart policy, and observability explicit. This RFC applies that
separation to PowerContext instead of treating every local or managed Server as the same autostart problem.

# Unresolved questions

- Should the public distribution command remain powercontext service, or fit under an existing setup-oriented command
  without implying that the Server role owns installation?
- What host-native presentation satisfies visible but non-blocking Server-unavailable diagnostics for Codex, Claude
  Code, and DeepSeek Harness without producing warning fatigue?
- Which documented personal configurations are guaranteed to be available inside each native user-service
  environment, and does that require a separate non-secret configuration contract before general availability?
- Should install start the service immediately by default, or only register it for the next login unless an explicit
  start option is provided?
- What stable native identifiers should be reserved on each platform to make ownership checks compatible with future
  package renames?

These questions must be resolved in RFC review or explicitly narrowed before the corresponding implementation is
declared complete. Managed deployment automation, public binding, remote multi-user service profiles, privileged
installation, and a portable secret store are out of scope.

# Future possibilities

- Add distribution-specific container manifests or administrator templates without changing the personal service
  contract.
- Add a stable non-secret Server configuration file and platform credential integrations in separate proposals.
- Reconcile a personal service registration during a transactional package upgrade.
- Add native desktop status surfaces after the CLI and diagnostic contracts are stable.
- Extend doctor with bounded log excerpts when they can be collected without exposing secrets.
