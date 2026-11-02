function setBusy(b) {
    document.querySelectorAll(".actions button").forEach(button => {
        button.disabled = b;
    });
}

// Keep expanded AI assessments available when the live dashboard re-renders.
const aiAnalysisCache = new Map();


async function runDemo(kind) {
    setBusy(true);

    document.getElementById("demoMessage").textContent =
        "Starting " + kind.toUpperCase() + " failure demo...";

    try {
        let response = await fetch("/api/demo/" + kind, {
            method: "POST"
        });

        let data = await response.json();

        document.getElementById("demoMessage").textContent =
            data.message || "Demo started.";

    } catch (error) {
        document.getElementById("demoMessage").textContent =
            "Could not start demo: " + error;
    }

    setTimeout(() => setBusy(false), 1500);

    refresh();
}


function statusText(p) {
    if (!p) {
        return "NO POD";
    }

    if (p.waiting_reason) {
        return p.waiting_reason;
    }

    if (p.last_reason) {
        return p.last_reason;
    }

    if (p.ready && p.phase === "Running") {
        return "RUNNING";
    }

    return p.phase || "UNKNOWN";
}


function esc(v) {
    return String(v ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    }[c]));
}


async function loadAiAnalysis(incidentId) {
    const target = document.getElementById("ai-analysis-" + incidentId);
    if (!target) return;
    aiAnalysisCache.set(incidentId, "Loading AI assessment...");
    target.textContent = "Loading AI assessment...";

    try {
        const response = await fetch("/api/incidents/" + encodeURIComponent(incidentId), {
            cache: "no-store"
        });
        const data = await response.json();
        if (!response.ok) {
            target.textContent = data.message || "AI assessment is not available yet.";
            return;
        }

        const analysis = data.analysis || {};
        const lifecycle = data.lifecycle || {};
        const diagnosis = analysis.diagnosis || {};
        const health = analysis.health_check || {};
        const proposal = analysis.proposal;
        const proposedAction = proposal?.action;
        const proposalReason = proposal?.reason;

        const analysisHtml = `
            <div><b>AI status:</b> ${esc(analysis.status || "Not available")}</div>
            <div><b>Lifecycle:</b> ${esc(lifecycle.current_status || "Not recorded")}</div>
            <div><b>Diagnosis:</b> ${esc(diagnosis.root_cause || diagnosis.summary || diagnosis.description || "Not available")}</div>
            <div><b>Recommended diagnostic action:</b> ${esc(diagnosis.recommended_action || "-")}</div>
            <div><b>Live health:</b> ${esc(health.status || "Not available")}</div>
            <div><b>Health reason:</b> ${esc(health.reason || "-")}</div>
            <div><b>Proposed remediation:</b> ${esc(proposedAction || "None")}</div>
            <div><b>Proposal reason:</b> ${esc(proposalReason || "-")}</div>
            <div><b>Risk:</b> ${esc(proposal?.risk || "-")}</div>
            <div><b>Human approval:</b> ${proposal?.approval_required ? "Required before remediation" : "Not required / no proposal"}</div>
            <div class="muted">Execution performed: ${analysis.execution_performed ? "Yes" : "No"}</div>
        `;
        aiAnalysisCache.set(incidentId, analysisHtml);
        const currentTarget = document.getElementById("ai-analysis-" + incidentId);
        if (currentTarget) currentTarget.innerHTML = analysisHtml;
    } catch (error) {
        const errorMessage = "Could not load AI assessment: " + error;
        aiAnalysisCache.set(incidentId, errorMessage);
        const currentTarget = document.getElementById("ai-analysis-" + incidentId);
        if (currentTarget) currentTarget.textContent = errorMessage;
    }
}


function render(d) {
    let c = d.cluster || {};
    let p = (c.pods || [])[0];

    let running = p && p.ready && p.phase === "Running";
    let triggerAvailable = c.available && c.trigger_available === true;

    // Keep demo controls unavailable unless Kubernetes reports a running,
    // non-terminating application pod.
    document.querySelectorAll(".actions button").forEach(button => {
        button.disabled = !triggerAvailable || d.demo?.state === "running";
        button.title = triggerAvailable
            ? ""
            : "No running application pod is available to trigger an incident.";
    });


    // Overall cluster status
    document.getElementById("overall").textContent =
        c.available ? "CLUSTER CONNECTED" : "CLUSTER UNAVAILABLE";


    // Application status
    document.getElementById("appState").textContent =
        running ? "RUNNING" : statusText(p);

    document.getElementById("appDetail").textContent =
        p ? "Pod name : " + p.name: (c.error || "No pod found");

    // Kubernetes status
    document.getElementById("k8sState").textContent =
        c.available ? "CONNECTED" : "OFFLINE";

    document.getElementById("k8sDetail").textContent =
        c.available
            ? (
                (c.deployment?.ready || 0) +
                "/" +
                (c.deployment?.desired || 0) +
                " deployment replicas ready"
            )
            : c.error;


    // Watcher status
    document.getElementById("watcherState").textContent =
        d.demo?.state === "running" ? "PROCESSING" : "READY";

    document.getElementById("watcherDetail").textContent =
        d.demo?.state === "running"
            ? "Collecting failure evidence"
            : "Deterministic failure detection";


    // Demo status
    document.getElementById("demoState").textContent =
        (d.demo?.state || "idle").toUpperCase();

    document.getElementById("demoMessage").textContent =
        d.demo?.state === "running"
            ? (d.demo?.message || "Demo is running...")
            : (!c.available
                ? "Kubernetes is unavailable. Connect to the cluster before triggering an incident."
                : (!c.trigger_available
                    ? ((c.pods || []).length === 0
                        ? "No pods available for this application. Start or restore the application before triggering an incident."
                        : "No running pods available to trigger an incident. Wait for a pod to become Running, then try again.")
                    : (d.demo?.message || "Ready for a controlled failure.")));


    // Pod badge
    document.getElementById("podBadge").textContent =
        p ? statusText(p) : "UNKNOWN";


    // Pod information
    document.getElementById("podInfo").innerHTML = p
        ? `
            <div><b>Name:</b> ${esc(p.name)}</div>
            <div><b>Phase:</b> ${esc(p.phase)}</div>
            <div><b>Ready:</b> ${p.ready ? "Yes" : "No"}</div>
            <div><b>Restarts:</b> ${p.restarts}</div>
            <div><b>Waiting reason:</b> ${esc(p.waiting_reason || "-")}</div>
            <div><b>Last termination:</b> ${esc(p.last_reason || "-")}</div>
            <div><b>Last exit code:</b> ${p.last_exit ?? "-"}</div>
        `
        : "No pod data yet.";


    // Incident list
    let list = d.incidents || [];

    document.getElementById("incidents").innerHTML = list.length
        ? list.map(i => `
            <div class="incident">
                <strong>
                    ${esc(i.failure_type || "Unknown failure")}
                    · ${esc(i.severity || "")}
                </strong>

                <div class="meta">
                    ID: ${esc(i.incident_id || "-")}
                </div>

                <div class="meta">
                    Status: ${esc(i.status || "-")}
                    · Pod: ${esc(i.pod || "-")}
                    · Restarts: ${i.restarts ?? "-"}
                </div>

                <div class="meta">
                    Reason: ${esc(i.reason || "-")}
                    · Exit: ${i.exit_code ?? "-"}
                </div>

                <div class="meta">
                    AI: ${esc(i.ai_status || "Not run")}
                    · Lifecycle: ${esc(i.lifecycle_status || "Not recorded")}
                </div>

                <button class="secondary-button" onclick="loadAiAnalysis('${esc(i.incident_id)}')"
                    ${i.analysis_available ? "" : "disabled"}>
                    View AI Analysis
                </button>
                <div class="ai-analysis" id="ai-analysis-${esc(i.incident_id)}"></div>
            </div>
        `).join("")
        : "No incidents yet.";

    // Restore expanded AI panels after each live incident-list update.
    for (const [incidentId, html] of aiAnalysisCache) {
        const panel = document.getElementById("ai-analysis-" + incidentId);
        if (panel) {
            if (html.startsWith("Could not load") || html === "Loading AI assessment...") {
                panel.textContent = html;
            } else {
                panel.innerHTML = html;
            }
        }
    }




    // Demo logs
    document.getElementById("log").textContent =
        d.log || "No demo has been run yet.";
}


async function refresh() {
    try {
        let response = await fetch("/api/status", {
            cache: "no-store"
        });

        let data = await response.json();

        render(data);

    } catch (error) {
        document.getElementById("overall").textContent =
            "DASHBOARD ERROR";
    }
}


// Initial dashboard load
refresh();


// Refresh live cluster and incident data every ten seconds.
// Expanded AI assessments are cached and remain visible between refreshes.
setInterval(refresh, 15000);