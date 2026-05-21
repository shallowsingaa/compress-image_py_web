import type { DeviceCategory } from './types';

export function detectDevice(): DeviceCategory {
  if (typeof navigator === 'undefined') return 'desktop';
  const ua = navigator.userAgent || '';

  if (
    /iPhone|iPad|iPod/i.test(ua) ||
    (navigator.platform === 'MacIntel' &&
      typeof (navigator as Navigator & { maxTouchPoints?: number }).maxTouchPoints === 'number' &&
      (navigator as Navigator & { maxTouchPoints: number }).maxTouchPoints > 1)
  ) {
    return 'ios';
  }

  if (/OpenHarmony|ArkWeb/i.test(ua) || (/HarmonyOS/i.test(ua) && !/Android/i.test(ua))) {
    return 'harmonyos';
  }

  if (/Android/i.test(ua)) {
    return 'android';
  }

  return 'desktop';
}
