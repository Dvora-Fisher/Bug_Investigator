export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

/**
 * Load a user profile from the API.
 * Returns the profile, null when the user does not exist (HTTP 404),
 * and throws ApiError for any other failed response.
 */
export async function fetchProfile(id, fetchImpl = fetch) {
  const res = await fetchImpl(`/api/users/${id}`);
  return res.json();
}

export function fullName(profile) {
  return profile ? `${profile.firstName} ${profile.lastName}` : "Unknown user";
}
