import { Interrupt } from "@langchain/langgraph-sdk";
import { HITLRequest } from "@/components/thread/agent-inbox/types";

export function isAgentInboxInterruptSchema(
  value: unknown,
): value is Interrupt<HITLRequest> | Interrupt<HITLRequest>[] {
  const valueAsObject = Array.isArray(value) ? value[0] : value;
  if (!valueAsObject || typeof valueAsObject !== "object") {
    return false;
  }

  const interrupt = valueAsObject as Interrupt<HITLRequest>;
  if (!interrupt.value || typeof interrupt.value !== "object") {
    return false;
  }

  const hitlValue = interrupt.value as Partial<HITLRequest>;
  const { action_requests: actionRequests, review_configs: reviewConfigs } =
    hitlValue;

  if (!Array.isArray(actionRequests) || actionRequests.length === 0) {
    return false;
  }
  if (!Array.isArray(reviewConfigs) || reviewConfigs.length === 0) {
    return false;
  }

  const hasValidActionRequests = actionRequests.every((request) => {
    return (
      request &&
      typeof request === "object" &&
      "name" in request &&
      typeof request.name === "string" &&
      "args" in request &&
      request.args !== null &&
      typeof request.args === "object"
    );
  });

  const hasValidConfigs = reviewConfigs.every((config) => {
    if (
      config &&
      typeof config === "object" &&
      !("action_name" in config) &&
      "actionName" in config &&
      typeof (config as { actionName?: unknown }).actionName === "string"
    ) {
      // @langchain/langgraph-sdk 的 normalizeHitlInterruptPayload 将
      // allowedDecisions <-> allowed_decisions 互为别名，但不处理 actionName -> action_name。
      // 在此回填，使读取 snake_case 键的下游消费者（ThreadActionsView、utils.ts）
      // 也能看到，因为它们共享同一对象。
      (config as Record<string, unknown>).action_name = (
        config as { actionName: string }
      ).actionName;
    }

    return (
      config &&
      typeof config === "object" &&
      "action_name" in config &&
      typeof config.action_name === "string" &&
      "allowed_decisions" in config &&
      Array.isArray(config.allowed_decisions)
    );
  });

  return hasValidActionRequests && hasValidConfigs;
}
