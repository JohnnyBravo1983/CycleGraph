import { useProfileStore } from "../state/profileStore";

export async function getPostAuthRoute() {
  await useProfileStore.getState().init();

  const profile = useProfileStore.getState().profile;
  if (!profile) return "/onboarding";

  // Sprint 2.2: bytt denne til ekte felt fra backend (strava_connected)
  const stravaConnected = (profile as any)?.strava_connected === true;
  if (!stravaConnected) return "/profile"; // eller "/connect-strava" når du lager den

  return "/rides";
}
