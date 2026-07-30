export type NativeAgentResourceKind =
  | "skill"
  | "creation_channel"
  | "style"
  | "youtube_channel"
  | "publishable_video";

export type NativeAgentResource = {
  kind: NativeAgentResourceKind;
  id: string;
  displayName: string;
  secondaryText: string;
  searchText: string;
  disabledReason?: string;
};

const SINGLETON_KINDS = new Set<NativeAgentResourceKind>([
  "skill",
  "creation_channel",
  "style",
  "youtube_channel",
  "publishable_video",
]);

export function filterNativeAgentResources(
  resources: NativeAgentResource[],
  query: string,
): NativeAgentResource[] {
  const normalizedQuery = query.trim().toLocaleLowerCase("zh-CN");
  if (!normalizedQuery) return resources;
  return resources.filter((resource) =>
    `${resource.displayName} ${resource.secondaryText} ${resource.searchText}`
      .toLocaleLowerCase("zh-CN")
      .includes(normalizedQuery),
  );
}

export function selectNativeAgentResource(
  current: NativeAgentResource[],
  next: NativeAgentResource,
): NativeAgentResource[] {
  if (next.disabledReason) return current;

  let selected = current;
  if (next.kind === "creation_channel") {
    selected = selected.filter(
      (resource) =>
        resource.kind !== "creation_channel" && resource.kind !== "style",
    );
  } else if (next.kind === "style") {
    selected = selected.filter(
      (resource) =>
        resource.kind !== "creation_channel" && resource.kind !== "style",
    );
  } else if (next.kind === "youtube_channel") {
    selected = selected.filter(
      (resource) =>
        resource.kind !== "youtube_channel"
        && resource.kind !== "publishable_video",
    );
  } else if (SINGLETON_KINDS.has(next.kind)) {
    selected = selected.filter((resource) => resource.kind !== next.kind);
  }

  return [...selected, next];
}

export function removeNativeAgentResource(
  current: NativeAgentResource[],
  resource: NativeAgentResource,
): NativeAgentResource[] {
  if (resource.kind === "youtube_channel") {
    return current.filter(
      (item) =>
        item.kind !== "youtube_channel" && item.kind !== "publishable_video",
    );
  }
  return current.filter(
    (item) => !(item.kind === resource.kind && item.id === resource.id),
  );
}

export function nativeAgentResourceId(
  resources: NativeAgentResource[],
  kind: NativeAgentResourceKind,
): string {
  return resources.find((resource) => resource.kind === kind)?.id || "";
}

export function clearNativeAgentPublishingResources(
  resources: NativeAgentResource[],
): NativeAgentResource[] {
  return resources.filter(
    (resource) =>
      resource.kind !== "youtube_channel"
      && resource.kind !== "publishable_video",
  );
}
