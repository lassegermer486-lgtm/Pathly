"use client";

import { useCallback, useSyncExternalStore } from "react";
import { EMPTY_PROFILE, type ProfileInput } from "@/lib/admission";

// Das Profil bleibt im Browser: kein Konto nötig, nichts geht an den Server.
const KEY = "pathly.profil";
const listeners = new Set<() => void>();
let cachedRaw: string | null = null;
let cached: ProfileInput = EMPTY_PROFILE;

function read(): ProfileInput {
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(KEY);
  } catch {
    return cached; // Speicher blockiert: Das Profil gilt dann nur bis zum Neuladen
  }
  if (raw === cachedRaw) return cached;
  cachedRaw = raw;
  try {
    cached = raw ? { ...EMPTY_PROFILE, ...JSON.parse(raw) } : EMPTY_PROFILE;
  } catch {
    cached = EMPTY_PROFILE;
  }
  return cached;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function useProfile() {
  const profile = useSyncExternalStore(subscribe, read, () => EMPTY_PROFILE);
  const setProfile = useCallback((next: ProfileInput) => {
    cached = next;
    try {
      cachedRaw = JSON.stringify(next);
      window.localStorage.setItem(KEY, cachedRaw);
    } catch {
      // siehe oben
    }
    listeners.forEach((l) => l());
  }, []);
  return [profile, setProfile] as const;
}
