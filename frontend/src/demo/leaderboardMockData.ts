export type LeaderboardEntry = {
  name: string;
  ftp: number;
  weight: number;
  wkg: number;
  isCurrentUser?: boolean;
  lastUpdated?: string;
};

export const leaderboardMockData: LeaderboardEntry[] = [
  { name: "Magnus Nordström", ftp: 385, weight: 74, wkg: 5.2, lastUpdated: "2 days ago" },
  { name: "Sarah Chen", ftp: 340, weight: 71, wkg: 4.8, lastUpdated: "5 days ago" },
  { name: "Lars Pettersen", ftp: 310, weight: 72, wkg: 4.3, lastUpdated: "1 week ago" },
  { name: "Johnny Strømø", ftp: 260, weight: 104.4, wkg: 2.49, isCurrentUser: true, lastUpdated: "Today" },
  { name: "Emma Johansson", ftp: 245, weight: 64, wkg: 3.8, lastUpdated: "3 days ago" },
  { name: "David Martinez", ftp: 230, weight: 66, wkg: 3.5, lastUpdated: "1 week ago" },
  { name: "Anna Kowalski", ftp: 215, weight: 67, wkg: 3.2, lastUpdated: "2 weeks ago" },
  { name: "Tom Wilson", ftp: 200, weight: 67, wkg: 3.0, lastUpdated: "1 month ago" },
];
