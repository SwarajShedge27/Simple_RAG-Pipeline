import logging
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from kubernetes import client, config
import os

logger = logging.getLogger(__name__)

# Try to load Kubernetes config (in-cluster or local ~/.kube/config)
try:
    if "KUBERNETES_SERVICE_HOST" in os.environ:
        config.load_incluster_config()
        logger.info("Loaded in-cluster Kubernetes config.")
    else:
        config.load_kube_config()
        logger.info("Loaded local Kubernetes config.")
except Exception as e:
    logger.warning(f"Could not load Kubernetes config (this is normal in simple Docker tests): {e}")

# Define the State for our LangGraph Workflow
class AlertState(TypedDict):
    alert_name: str
    service_label: str
    namespace: str
    severity: str
    status: str
    action_taken: str

# Node 1: Investigate the alert
def investigate_alert(state: AlertState) -> AlertState:
    logger.info(f"[AIOps] Investigating alert: {state['alert_name']} on service: {state['service_label']}")
    if state["severity"] == "critical" or state["severity"] == "high":
        state["status"] = "requires_healing"
    else:
        state["status"] = "ignored"
    return state

# Node 2: Execute Healing (Kubernetes Pod Restart)
def heal_service(state: AlertState) -> AlertState:
    logger.info(f"[AIOps] Attempting to heal service: {state['service_label']} in namespace: {state['namespace']}")
    state["action_taken"] = "Attempted Pod Restart"
    
    try:
        v1 = client.CoreV1Api()
        # Find pods matching the service label
        label_selector = f"app={state['service_label']}"
        pods = v1.list_namespaced_pod(namespace=state["namespace"], label_selector=label_selector)
        
        if not pods.items:
            logger.warning(f"[AIOps] No pods found with label {label_selector} in namespace {state['namespace']}")
            state["action_taken"] = "Failed: No Pods Found"
            return state

        # Delete (restart) the pods
        for pod in pods.items:
            logger.info(f"[AIOps] Restarting pod: {pod.metadata.name}")
            v1.delete_namespaced_pod(name=pod.metadata.name, namespace=state["namespace"])
            
        state["action_taken"] = f"Successfully restarted {len(pods.items)} pod(s)"
    except Exception as e:
        logger.error(f"[AIOps] Failed to execute Kubernetes heal action: {e}")
        state["action_taken"] = f"Failed Kubernetes API Call: {e}"
        
    return state

# Conditional Edge
def routing_logic(state: AlertState) -> str:
    if state["status"] == "requires_healing":
        return "heal"
    return "end"

# Build the Graph
workflow = StateGraph(AlertState)

workflow.add_node("investigate", investigate_alert)
workflow.add_node("heal", heal_service)

workflow.set_entry_point("investigate")
workflow.add_conditional_edges(
    "investigate",
    routing_logic,
    {
        "heal": "heal",
        "end": END
    }
)
workflow.add_edge("heal", END)

aiops_agent = workflow.compile()

def process_alert(payload: dict) -> dict:
    """Entrypoint called by the FastAPI Webhook"""
    initial_state = {
        "alert_name": payload.get("alertname", "UnknownAlert"),
        "service_label": payload.get("service", "unknown-service"),
        "namespace": payload.get("namespace", "default"),
        "severity": payload.get("severity", "critical"),
        "status": "pending",
        "action_taken": "none"
    }
    
    result = aiops_agent.invoke(initial_state)
    return result
