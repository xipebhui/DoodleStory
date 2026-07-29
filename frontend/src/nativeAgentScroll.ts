export const NATIVE_AGENT_FOLLOW_THRESHOLD_PX = 80;

type ScrollPosition = {
  scrollHeight: number;
  scrollTop: number;
  clientHeight: number;
};

export function shouldFollowNativeAgentThread(
  position: ScrollPosition,
): boolean {
  const distanceFromBottom =
    position.scrollHeight - position.scrollTop - position.clientHeight;
  return distanceFromBottom <= NATIVE_AGENT_FOLLOW_THRESHOLD_PX;
}
