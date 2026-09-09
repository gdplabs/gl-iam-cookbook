const RESPONSES: Record<string, string> = {
  "UC-GLCHAT-01.1": "Here are your meetings for today. Your calendar was accessed with your delegated user credential.",
  "UC-GLCHAT-01.1-M": "Here are your meetings for today. Your calendar was accessed with your delegated user credential.",
  "UC-GLCHAT-01.2": "I found Nadia's calendar and returned the meetings available through the approved agent credential.",
  "UC-GLCHAT-01.2-M": "I found Nadia's calendar and returned the meetings allowed by your resource whitelist.",
  "UC-GLCHAT-02.1": "The meeting has been added to your calendar.",
  "UC-GLCHAT-02.1-M": "The meeting has been added to your calendar using your delegated user credential.",
};

export function getHypotheticalResponse(scenarioId: string): string {
  return RESPONSES[scenarioId] ?? "The agent completed the permitted steps and returned the tool results shown below.";
}
