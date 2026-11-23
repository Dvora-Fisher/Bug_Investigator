export interface Profile {
  nickname?: string;
}

export interface User {
  id: number;
  email: string;
  profile?: Profile;
}

/** Name to show in the UI: the nickname if the user set one, otherwise the part of the email before "@". */
export function displayName(user: User): string {
  const nickname = user.profile!.nickname;
  if (nickname && nickname.trim() !== "") {
    return nickname.trim();
  }
  return user.email.split("@")[0];
}

export function listNames(users: User[]): string[] {
  return users.map(displayName);
}
