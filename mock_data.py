"""De-identified, deterministic telecom incident data for demonstration only."""

from __future__ import annotations

SCENARIOS: dict[str, dict] = {
    "fiber-aggregation-loss": {
        "id": "fiber-aggregation-loss",
        "title": "Fiber aggregation loss in Bangkok metro ring",
        "aliases": ["fiber", "fibre", "aggregation", "los", "bangkok", "metro ring"],
        "incident_ref": "SIM-SP-2026-0916-017",
        "severity": "P1",
        "confidence": 87,
        "start_time": "2026-09-16T09:18:00Z",
        "summary": "Loss of signal and transport failures converge on the same aggregation site and affect enterprise and mobile-backhaul services.",
        "primary_asset": "AGG-BKK-17",
        "region": "Bangkok Metro — North Ring",
        "alarms": [
            {"time": "09:18:02Z", "source": "OLT-BKK-17", "event": "PON_LOS", "detail": "Uplink optical receive power below threshold on both ring directions."},
            {"time": "09:18:11Z", "source": "PE-BKK-17", "event": "BFD_SESSION_DOWN", "detail": "Three transport peers unreachable through aggregation path."},
            {"time": "09:19:08Z", "source": "NPM-BKK", "event": "PACKET_LOSS_ANOMALY", "detail": "Packet loss rose from 0.1% to 96.4% across the north ring."},
            {"time": "09:20:14Z", "source": "MOBILE-BH-12", "event": "BACKHAUL_DEGRADED", "detail": "Four mobile sites entered reduced-capacity backhaul state."},
        ],
        "affected_services": [
            {"service": "DIA-EASTBANK-01", "customer": "Eastbank Financial Services", "class": "Enterprise DIA", "impact": "Hard down", "sla": "Gold"},
            {"service": "MPLS-CITYHOSP-07", "customer": "City General Hospital", "class": "Managed MPLS", "impact": "Hard down", "sla": "Platinum"},
            {"service": "MBH-NORTH-04", "customer": "Internal mobile network", "class": "4G/5G backhaul", "impact": "Degraded", "sla": "Critical"},
            {"service": "BB-RES-BKK-N-22", "customer": "Consumer aggregate", "class": "Broadband aggregation", "impact": "Intermittent", "sla": "Standard"},
        ],
        "change_context": "No approved maintenance or change record overlaps the incident window.",
        "hypotheses": [
            {"rank": 1, "cause": "Physical fiber impairment on the north-ring aggregation span", "confidence": 87, "evidence": "Simultaneous optical loss on both ring directions, transport peer failure, and no overlapping planned work."},
            {"rank": 2, "cause": "Aggregation-site power or optical line-card failure", "confidence": 31, "evidence": "The shared-site blast radius is consistent, but environmental alarms remain normal and dual-direction optical loss favors an outside-plant fault."},
            {"rank": 3, "cause": "Control-plane routing issue", "confidence": 12, "evidence": "Could explain transport symptoms but does not explain the optical-loss alarms."},
        ],
        "historical": {
            "reference": "SIM-SP-2026-0712-004",
            "similarity": 82,
            "outcome": "Third-party civil works damaged a north-ring feeder cable. Restoration took 142 minutes after field confirmation and fiber-splice repair.",
        },
        "runbook": [
            "Confirm the alarm correlation and service-impact list with the transport engineer.",
            "Request an outside-plant dispatch to inspect the north-ring feeder route and the AGG-BKK-17 optical handoff.",
            "Validate alternate-path capacity before any traffic restoration or reroute is proposed.",
            "Capture pre- and post-restoration optical levels, BFD status, and customer-service reachability in the incident record.",
        ],
        "ticket_draft": "P1 service problem: correlated optical loss and transport failure at AGG-BKK-17 are causing hard-down impact to Platinum and Gold enterprise services and degraded mobile backhaul. No approved change overlaps the event. Recommended next step: validate impact with transport engineering and dispatch outside-plant investigation for the north-ring feeder span.",
        "approval_gates": [
            "An incident commander must approve P1 declaration and external escalation.",
            "A network engineer must approve any protection switch, reroute, or configuration change.",
            "A service manager must approve customer notification content and timing.",
        ],
    },
    "mobile-ran-congestion": {
        "id": "mobile-ran-congestion",
        "title": "5G RAN congestion around a stadium event",
        "aliases": ["mobile", "ran", "5g", "stadium", "congestion", "radio"],
        "incident_ref": "SIM-SP-2026-0916-023",
        "severity": "P2",
        "confidence": 81,
        "start_time": "2026-09-16T11:40:00Z",
        "summary": "A concentrated traffic surge is degrading 5G user experience across adjacent sites without signs of hardware or transport failure.",
        "primary_asset": "RAN-CLUSTER-STAD-03",
        "region": "Bangkok Metro — Stadium precinct",
        "alarms": [
            {"time": "11:40:17Z", "source": "gNB-STAD-03", "event": "PRB_UTILIZATION_HIGH", "detail": "Downlink PRB utilization sustained above 94%."},
            {"time": "11:42:05Z", "source": "CQI-ANALYTICS", "event": "USER_THROUGHPUT_DEGRADED", "detail": "Median downlink throughput fell 61% from baseline."},
            {"time": "11:43:41Z", "source": "EVENT-FEED", "event": "VENUE_EVENT", "detail": "Ticketed event attendance forecast: 48,000."},
        ],
        "affected_services": [
            {"service": "MBB-STAD-03", "customer": "Mobile subscribers", "class": "5G mobile broadband", "impact": "Degraded", "sla": "Standard"},
            {"service": "FWA-ARENA-02", "customer": "Venue operations", "class": "Fixed wireless access", "impact": "At risk", "sla": "Gold"},
        ],
        "change_context": "A capacity upgrade is scheduled for next month; no active network change is in progress.",
        "hypotheses": [
            {"rank": 1, "cause": "Event-driven radio-capacity exhaustion", "confidence": 81, "evidence": "Utilization, throughput degradation, and venue event timing align across adjacent sites."},
            {"rank": 2, "cause": "Local backhaul capacity constraint", "confidence": 24, "evidence": "Transport remains within normal utilization, reducing likelihood."},
            {"rank": 3, "cause": "Radio hardware fault", "confidence": 9, "evidence": "No hardware alarms or sector-specific anomalies are present."},
        ],
        "historical": {"reference": "SIM-SP-2026-0604-011", "similarity": 74, "outcome": "Temporary capacity policy was approved and venue traffic recovered to the expected event baseline."},
        "runbook": [
            "Confirm event attendance and compare utilization across the neighboring cell cluster.",
            "Ask RAN engineering to assess pre-approved event capacity measures.",
            "Prioritize venue-operations service verification before event start.",
            "Track throughput and utilization at fifteen-minute intervals until the event window closes.",
        ],
        "ticket_draft": "P2 service problem: event-correlated RAN congestion is degrading 5G throughput in the stadium precinct. No hardware or transport fault evidence is present. Recommended next step: request RAN engineering assessment of approved event-capacity measures and monitor venue-operations FWA service.",
        "approval_gates": ["A RAN engineer must approve any capacity-policy or parameter change.", "A service manager must approve customer-facing impact notices."],
    },
    "enterprise-sdwan-latency": {
        "id": "enterprise-sdwan-latency",
        "title": "Enterprise SD-WAN latency risk across cloud interconnect",
        "aliases": ["sd-wan", "sdwan", "latency", "cloud", "interconnect", "enterprise"],
        "incident_ref": "SIM-SP-2026-0916-029",
        "severity": "P2",
        "confidence": 78,
        "start_time": "2026-09-16T13:05:00Z",
        "summary": "Latency and packet loss are rising on a shared cloud-interconnect path and put a premium enterprise SLA at risk.",
        "primary_asset": "PE-BKK-CLOUD-02",
        "region": "Bangkok Metro — Cloud interconnect",
        "alarms": [
            {"time": "13:05:11Z", "source": "NPM-CLOUD", "event": "LATENCY_ANOMALY", "detail": "Median RTT increased from 18 ms to 96 ms."},
            {"time": "13:06:09Z", "source": "NPM-CLOUD", "event": "PACKET_LOSS_ANOMALY", "detail": "Packet loss reached 4.8% on the shared egress path."},
            {"time": "13:09:24Z", "source": "SLA-WATCH", "event": "SLA_RISK", "detail": "Platinum customer threshold projected to breach in 24 minutes if trend persists."},
        ],
        "affected_services": [
            {"service": "SDWAN-ORBIT-09", "customer": "Orbit Retail Group", "class": "Managed SD-WAN", "impact": "Degraded", "sla": "Platinum"},
            {"service": "CLOUD-CONNECT-KITE-02", "customer": "Kite Logistics", "class": "Cloud Connect", "impact": "At risk", "sla": "Gold"},
        ],
        "change_context": "A third-party cloud provider reported no maintenance affecting this interconnect.",
        "hypotheses": [
            {"rank": 1, "cause": "Congestion on the shared cloud-interconnect egress", "confidence": 78, "evidence": "Shared-path latency and loss move together while access circuits remain within normal baselines."},
            {"rank": 2, "cause": "Upstream cloud provider impairment", "confidence": 42, "evidence": "The fault domain is consistent, but no external incident has been confirmed."},
            {"rank": 3, "cause": "Customer-site WAN fault", "confidence": 8, "evidence": "Multiple customers with different access locations are affected through the same interconnect."},
        ],
        "historical": {"reference": "SIM-SP-2026-0819-006", "similarity": 76, "outcome": "Capacity saturation on a shared egress was confirmed; engineer-approved traffic balancing restored SLA performance."},
        "runbook": [
            "Validate the common egress path and compare unaffected interconnect paths.",
            "Engage the cloud-interconnect and transport teams with the attached latency evidence.",
            "Prepare, but do not send, a Platinum SLA-risk notification for Orbit Retail Group.",
            "Obtain network-change approval before any traffic balancing or routing adjustment.",
        ],
        "ticket_draft": "P2 service problem: shared cloud-interconnect latency and loss are putting a Platinum SD-WAN SLA at risk. Evidence points to common egress congestion; no customer-site fault evidence is present. Recommended next step: validate alternate-path capacity and obtain approval for any traffic-balancing change.",
        "approval_gates": ["A network engineer must approve any traffic-balancing or routing change.", "An account or service manager must approve SLA-risk communications."],
    },
}


def public_scenarios() -> list[dict]:
    """Return a compact safe-to-display representation of the mock scenarios."""
    return [
        {
            "id": scenario["id"],
            "title": scenario["title"],
            "severity": scenario["severity"],
            "region": scenario["region"],
            "summary": scenario["summary"],
        }
        for scenario in SCENARIOS.values()
    ]
