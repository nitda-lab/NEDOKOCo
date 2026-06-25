export type InstanceType = "public" | "friends_plus" | "friends" | "invite_plus" | "invite";

export const INSTANCE_TYPES: { key: InstanceType; label: string }[] = [
  { key: "public", label: "Public" },
  { key: "friends_plus", label: "Friends+" },
  { key: "friends", label: "Friends" },
  { key: "invite_plus", label: "Invite+" },
  { key: "invite", label: "Invite" },
];

export function needsUserId(type: InstanceType): boolean {
  return type !== "public";
}

export function isValidUserId(v: string): boolean {
  return /^usr_[0-9a-f-]{8,}$/i.test(v.trim());
}

export function randomInstanceName(): string {
  return String(Math.floor(Math.random() * 90000) + 10000);
}

export function buildInstanceId(
  type: InstanceType,
  usrId: string | null,
  name: string,
): string | null {
  const region = "region(jp)";
  if (type === "public") return `${name}~${region}`;
  if (!usrId) return null;
  const u = usrId.trim();
  switch (type) {
    case "friends_plus":
      return `${name}~hidden(${u})~${region}`;
    case "friends":
      return `${name}~friends(${u})~${region}`;
    case "invite_plus":
      return `${name}~private(${u})~canRequestInvite~${region}`;
    case "invite":
      return `${name}~private(${u})~${region}`;
    default:
      return null;
  }
}

export function buildLaunchUrl(worldId: string, instanceId: string): string {
  return `https://vrchat.com/home/launch?worldId=${encodeURIComponent(worldId)}&instanceId=${encodeURIComponent(instanceId)}`;
}
