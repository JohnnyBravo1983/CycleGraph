import { useProfileStore } from "../state/profileStore";

type ProfileWithStravaFlag = {
  strava_connected?: boolean;
};

export async function getPostAuthRoute(): Promise<string> {
  await useProfileStore.getState().init();

  const profile = useProfileStore.getState() as unknown as ProfileWithStravaFlag | null;

  if (!profile || Object.keys(profile).length === 0) return "/onboarding";

  // Sprint 2.2+: strava_connected kommer fra backend senere
  const maybeWithStrava = profile as ProfileWithStravaFlag;
  const stravaConnected = maybeWithStrava.strava_connected === true;

  if (!stravaConnected) {
    // I MVP sender vi ikke automatisk til /profile,
    // men denne er klar for /connect-strava senere
    return "/rides";
  }

  return "/rides";
}
