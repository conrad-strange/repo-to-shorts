import type {Scene} from '../types';

const GITHUB_REPO_PATTERN =
  /(?:https?:\/\/)?github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\.git)?(?:[/?#][^\s，。！？!?；;、]*)?/gi;
const HANDLE_PATTERN = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\.git)?$/;

export const repoHandleFromScene = (scene: Scene, fallback = 'owner/repo') => {
  return (
    repoHandleFromValue(scene.visual.repo_display_url) ||
    repoHandleFromValue(scene.visual.repo_url) ||
    repoHandleFromValue(scene.visual.headline) ||
    fallback
  );
};

export const repoHandleFromValue = (value?: string | null): string | null => {
  const raw = String(value || '').trim();
  if (!raw) {
    return null;
  }
  const match = raw.match(GITHUB_REPO_PATTERN);
  if (match?.[0]) {
    return partsToHandle(stripGithubPrefix(match[0]));
  }
  if (HANDLE_PATTERN.test(raw)) {
    return partsToHandle(raw);
  }
  return null;
};

export const compactGithubLinks = (value: string) => {
  return String(value || '').replace(GITHUB_REPO_PATTERN, (match) => repoHandleFromValue(match) || match);
};

const stripGithubPrefix = (value: string) =>
  value
    .replace(/^https?:\/\//i, '')
    .replace(/^github\.com\//i, '')
    .trim();

const partsToHandle = (value: string) => {
  const parts = stripGithubPrefix(value)
    .split(/[/?#]+/)
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length < 2) {
    return null;
  }
  const owner = parts[0];
  const repo = parts[1].replace(/\.git$/i, '');
  return owner && repo ? `${owner}/${repo}` : null;
};
