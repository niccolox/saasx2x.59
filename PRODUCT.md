# SaaSX2X product requirements

SaaSX2X is an uptime and site reliability monitor for websites and servers. The first user is the owner, who monitors their own apps and sites. Later, SaaSX2X becomes a paid service with self-service plans, in the same market as Site24x7 and Uptime.com.

This file records the product decisions. `PLAN.md` will record how to build them.

## Users and accounts

| Stage | Who uses it | What they can do |
| --- | --- | --- |
| Stage 1 | The owner only | Add targets, see results, get alerts. |
| Stage 2 | Paying customers | Buy a plan, sign in, add targets, see results, get alerts. |

Every target, check, result, and alert belongs to one account. One account never sees the data of another account. Stage 1 uses the same account model as stage 2, with one account.

## Two monitor modes

A customer adds a target in one of two modes.

### Website mode

The target is a fully qualified domain name (FQDN) or a URL. Website mode has these check types:

| Check type | What it checks | Where it runs |
| --- | --- | --- |
| HTTP and HTTPS | Status code, response time, optional keyword in the body | Probe servers |
| TCP | A connection opens on a port that the customer names | Probe servers |
| DNS | The record resolves, and optionally matches an expected value | Probe servers |
| SSL expiry | Days until the certificate expires, and whether the chain is valid | Probe servers |
| Ping | ICMP echo reply and round-trip time | Probe servers |
| Heartbeat | The customer's job calls a SaaSX2X URL on a schedule. A missed call is a failure. | Control plane |
| Web Vitals | LCP, CLS, and INP from a real browser load | Browser probe servers |
| Page test | A full page load with a waterfall and a screenshot | Browser probe servers |

### IP mode

The target is an IPv4 or IPv6 address. IP mode finds open ports and reports how exposed the server is.

| Ownership state | What SaaSX2X does |
| --- | --- |
| Not verified | Up or down checks only, on ports that the customer names. No port discovery. |
| Verified | Port discovery scans, service identification, and an exposure report. |

A customer proves ownership in one of these ways:

1. A DNS TXT record with a SaaSX2X token, on a name that resolves to the IP.
2. A token file at a SaaSX2X path on an HTTP server at the IP.
3. A token that the server returns on a port that the customer names.

SaaSX2X checks the proof again on a schedule. If the proof is gone, the target goes back to "not verified".

IP mode does not scan an IP address that belongs to Cloudflare or another CDN edge. For a target behind a CDN, the edge IP shows the CDN and not the origin server. SaaSX2X tells the customer to add the origin IP instead.

## Targets behind Cloudflare

Many targets sit behind Cloudflare. Probes must not trigger Cloudflare blocks. SaaSX2X does this by identifying itself, not by hiding.

- Every HTTP probe sends one fixed User-Agent that names SaaSX2X and links to a page about the probes.
- Probes send requests only from a published list of IP addresses.
- The request rate to one target stays low. The shortest interval for each plan is an open question.
- SaaSX2X gives each customer a guide to add a Cloudflare WAF skip rule for the probe IPs.
- SaaSX2X applies to the Cloudflare verified bots program.

SaaSX2X does not rotate IP addresses through proxies, copy browser fingerprints, or solve challenges. If Cloudflare challenges a probe, the check reports "blocked by Cloudflare" as its own state. That state is not "down", and it does not send a down alert.

## Reliability targets

The project has two 99.999% targets.

| Target | Definition | Budget |
| --- | --- | --- |
| Alert accuracy | Wrong verdicts divided by all verdicts. A wrong verdict is a false down alert or a missed outage. | At most 1 wrong verdict in 100,000 |
| Service availability | Time when the dashboard, the API, the probes, or the alert path is down | At most 5.26 minutes in each year |

Each target needs a measurement in the product. The design for the measurements is in `PLAN.md`.

Several rules follow from the accuracy target:

- One failed probe never sends an alert. An alert needs agreement from probes in more than one region.
- Each outage sends one down alert and one recovery alert, not one alert for each failed check.
- A failure of the probe itself, for example the probe's own network, is not a failure of the target.

## Alerts

The first version sends alerts by email only. Other channels are out of scope for the first version.

## Open questions

The answers to these questions change the design. Each one needs a decision before the plan uses it.

| Question | Why it matters |
| --- | --- |
| Which plans, prices, and limits are there? | Sets the number of targets, the shortest check interval, and the data retention for each plan. |
| Which payment provider? | Sets the billing integration. |
| How many probe regions, and on which hosting providers? | More than one provider removes a single point of failure for the availability target. |
| Where does the control plane run? | Affects the availability target and the cost. |
| How long does SaaSX2X keep raw check results? | Sets the storage size and the cost. |
| Do customers get public status pages? | Status pages are common in this market. They add a public part of the product. |
| What are the SSL expiry warning thresholds? | For example, warnings at 30, 14, and 7 days. |
