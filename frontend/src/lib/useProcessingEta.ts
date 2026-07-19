import { onUnmounted, ref, watch, type Ref } from 'vue'

export interface ProcessingEtaInput {
  progressPercent: Ref<number>
  active: Ref<boolean>
  processingStartedAt: Ref<string | null | undefined>
  estimatedCompletionAt: Ref<string | null | undefined>
}

export interface ProcessingEta {
  displayedProgress: Ref<number>
  secondsRemaining: Ref<number | null>
}

/**
 * Drives the processing progress bar and a live "time remaining" countdown.
 *
 * When the backend has a real estimate (learned from this server's own past
 * completions - see backend/app/services/eta.py), progress fills at the
 * actual pace of that estimate instead of an arbitrary animation curve, and
 * the seconds countdown ticks down from it in real time between polls.
 * Before any document has ever finished on this server there's no estimate
 * to use yet, so this falls back to the old behavior: creep toward a
 * ceiling just short of the next real checkpoint, never claiming to be
 * further along than the backend actually is.
 */
export function useProcessingEta(input: ProcessingEtaInput): ProcessingEta {
  const { progressPercent, active, processingStartedAt, estimatedCompletionAt } = input
  const displayedProgress = ref(progressPercent.value)
  const secondsRemaining = ref<number | null>(null)
  let frame: number | null = null

  function stop() {
    if (frame !== null) {
      cancelAnimationFrame(frame)
      frame = null
    }
  }

  function tick() {
    if (!active.value) {
      displayedProgress.value = progressPercent.value
      secondsRemaining.value = null
      frame = null
      return
    }

    const startedAt = processingStartedAt.value ? new Date(processingStartedAt.value).getTime() : null
    const completesAt = estimatedCompletionAt.value ? new Date(estimatedCompletionAt.value).getTime() : null
    const real = progressPercent.value

    if (startedAt !== null && completesAt !== null && completesAt > startedAt) {
      const now = Date.now()
      const totalMs = completesAt - startedAt
      const elapsedMs = now - startedAt
      const timeFraction = Math.min(Math.max(elapsedMs / totalMs, 0), 1)
      const ceiling = real >= 100 ? 100 : 99
      displayedProgress.value = Math.min(Math.max(timeFraction * 100, real), ceiling)
      secondsRemaining.value = Math.max(0, Math.round((completesAt - now) / 1000))
    } else {
      // No estimate yet - same easing-toward-ceiling behavior as before.
      const ceiling = real >= 100 ? 100 : Math.min(real + 12, 96)
      const gap = ceiling - displayedProgress.value
      displayedProgress.value = Math.abs(gap) < 0.1 ? ceiling : displayedProgress.value + gap * 0.045
      secondsRemaining.value = null
    }

    frame = requestAnimationFrame(tick)
  }

  watch(
    [progressPercent, active, processingStartedAt, estimatedCompletionAt],
    () => {
      stop()
      if (active.value) {
        frame = requestAnimationFrame(tick)
      } else {
        displayedProgress.value = progressPercent.value
        secondsRemaining.value = null
      }
    },
    { immediate: true },
  )

  onUnmounted(stop)

  return { displayedProgress, secondsRemaining }
}
